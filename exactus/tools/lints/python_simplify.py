# Copyright (c) 2026
"""Perform conservative, scope-aware Python 3.13 AST rewrites.

Ruff owns general formatting and simplification. This module deliberately
restricts edits to directly adjacent statements in one function body, with
one evaluation of the original expression and unchanged control-flow shape.
Every emitted proposal records a stable rule identifier and a safety
justification; rejected candidates record a stable skip reason.
"""

from __future__ import annotations

from ast import (
    AST,
    AnnAssign,
    Assign,
    AsyncFunctionDef,
    Attribute,
    Await,
    BinOp,
    BoolOp,
    Call,
    ClassDef,
    Compare,
    Constant,
    Dict,
    DictComp,
    Expr,
    FormattedValue,
    FunctionDef,
    GeneratorExp,
    Global,
    If,
    IfExp,
    JoinedStr,
    Lambda,
    List,
    ListComp,
    Load,
    Name,
    NamedExpr,
    Nonlocal,
    Return,
    Set,
    SetComp,
    Starred,
    Subscript,
    Tuple,
    UnaryOp,
    expr,
    get_source_segment,
    iter_child_nodes,
    parse,
    stmt,
    walk,
)
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from tokenize import detect_encoding
from typing import TYPE_CHECKING, cast, final

if TYPE_CHECKING:
    from collections.abc import Sequence


@final
@dataclass(frozen=True, slots=True)
class PythonSimplifyProposal:
    """One source-preserving edit proposal.

    Attributes:
        rule: Stable Exactus simplification identifier.
        line: One-based location of the first original statement.
        before: Exact source text to remove.
        after: Replacement source text.
        reason: Safety justification for the rewrite.

    """

    rule: str
    line: int
    before: str
    after: str
    reason: str


@final
@dataclass(frozen=True, slots=True)
class PythonSimplifySkip:
    """One rejected rewrite candidate with its safety reason.

    Attributes:
        rule: Identifier of the guard or rule that rejected it.
        line: One-based location of the first original statement.
        reason: Safety justification for skipping the rewrite.

    """

    rule: str
    line: int
    reason: str


type _Decision = PythonSimplifyProposal | PythonSimplifySkip | None


@final
@dataclass(frozen=True, slots=True)
class PythonSimplifyResult:
    """One source analysis or guarded transformation.

    Attributes:
        source: Final source, equal to input in audit mode.
        proposals: Applicable deterministic proposed rewrites.
        skipped: Rejected candidates and their safety reasons.
        changed: Whether an edit was committed.

    """

    source: str
    proposals: tuple[PythonSimplifyProposal, ...]
    skipped: tuple[PythonSimplifySkip, ...]
    changed: bool


@final
@dataclass(frozen=True, slots=True)
class PairContext:
    """Immutable input for candidate statement replacements.

    Attributes:
        source: Original module text.
        lines: Original lines with their terminators.
        walrus: Whether named expressions are permitted.
        function: Function containing the statements.

    """

    source: str
    lines: Sequence[str]
    walrus: bool
    function: FunctionDef | AsyncFunctionDef


@final
@dataclass(frozen=True, slots=True)
class _Candidate:
    """Validated adjacent statement pair routed to a rule.

    Attributes:
        first: Assignment statement.
        second: Consuming statement.
        context: Source, policy and function identity.
        name: Assigned local identifier.
        initializer: Expression source text.
        line: One-based assignment line.

    """

    first: stmt
    second: stmt
    context: PairContext
    name: str
    initializer: str
    line: int


def _target(*, statement: stmt) -> tuple[Name, expr] | None:
    """Extract a single directly initialized local name.

    Args:
        statement: Assignment statement.

    Returns:
        Name and initializer, or nothing.

    """
    if isinstance(statement, Assign) and len(statement.targets) == 1:
        target: expr = statement.targets[0]
        return (target, statement.value) if isinstance(target, Name) else None
    if (
        isinstance(statement, AnnAssign)
        and isinstance(statement.target, Name)
        and statement.value is not None
    ):
        return statement.target, statement.value
    return None


def _one_use(*, tree: AST, name: str) -> bool:
    """Check that a name is read once across the enclosing function.

    Args:
        tree: Function AST including nested bodies.
        name: Assigned identifier.

    Returns:
        Whether exactly one read was found.

    """
    return (
        sum(
            isinstance(node, Name)
            and node.id == name
            and isinstance(node.ctx, Load)
            for node in walk(node=tree)
        )
        == 1
    )


def _scope_nodes(*, tree: AST) -> frozenset[int]:
    """Collect nodes living inside nested scope bodies.

    Args:
        tree: Enclosing function AST.

    Returns:
        ``id()`` values of every node owned by a nested function,
        lambda, class or comprehension body rather than by the
        enclosing scope itself.

    """
    nested: set[int] = set()
    for node in walk(node=tree):
        if node is tree or not isinstance(
            node,
            (FunctionDef, AsyncFunctionDef, Lambda, ClassDef),
        ):
            continue
        for inner in walk(node=node):
            if inner is not node:
                nested.add(id(inner))
    return frozenset(nested)


def _declares_outer(
    *,
    function: FunctionDef | AsyncFunctionDef,
    name: str,
) -> bool:
    """Detect ``global``/``nonlocal`` declarations of a name.

    Args:
        function: Enclosing function whose own statements are checked.
        name: Assigned identifier.

    Returns:
        Whether the function itself declares the name as outer state,
        making any local-looking assignment a required outer write.

    """
    nested: frozenset[int] = _scope_nodes(tree=function)
    return any(
        isinstance(node, (Global, Nonlocal))
        and name in node.names
        and id(node) not in nested
        for node in walk(node=function)
    )


def _scope_loads(*, second: stmt, name: str) -> list[Name]:
    """Collect enclosing-scope loads of ``name`` inside ``second``.

    Args:
        second: Statement consuming the inlined expression.
        name: Identifier whose loads are inspected.

    Returns:
        Loads owned by the enclosing scope, excluding reads captured
        by nested function, lambda, class or comprehension bodies.

    """
    nested: frozenset[int] = _scope_nodes(tree=second)
    return [
        node
        for node in walk(node=second)
        if isinstance(node, Name)
        and node.id == name
        and isinstance(node.ctx, Load)
        and id(node) not in nested
    ]


def _parents(*, root: AST) -> dict[int, AST]:
    """Map every descendant of ``root`` to its direct parent.

    Args:
        root: Statement or expression whose tree is indexed.

    Returns:
        Child ``id()`` to parent-node mapping.

    """
    parents: dict[int, AST] = {}
    stack: list[AST] = [root]
    while stack:
        current: AST = stack.pop()
        for child in iter_child_nodes(node=current):
            parents[id(child)] = current
            stack.append(child)
    return parents


def _single_use_load(*, second: stmt, name: str) -> Name | None:
    """Find the provably single-evaluated load of ``name`` in ``second``.

    Args:
        second: Statement consuming the inlined expression.
        name: Identifier whose loads are inspected.

    Returns:
        The unique enclosing-scope load when none of its ancestors can
        re-evaluate or defer it — nested scopes, comprehension element
        sections and generator expressions are rejected.

    """
    loads: list[Name] = _scope_loads(second=second, name=name)
    if len(loads) != 1:
        return None
    parents: dict[int, AST] = _parents(root=second)
    node: AST = loads[0]
    while id(node) in parents:
        node = parents[id(node)]
        if isinstance(
            node,
            (
                Lambda,
                FunctionDef,
                AsyncFunctionDef,
                ClassDef,
                ListComp,
                SetComp,
                DictComp,
                GeneratorExp,
            ),
        ):
            return None
    return loads[0]


def _first_evaluated_child(*, node: AST) -> AST | None:
    """Return the operand evaluated first within an expression.

    Args:
        node: Expression that may contain the candidate load.

    Returns:
        The child evaluated first, or nothing for atomic nodes and
        forms whose evaluation order is unsafe to reason about.

    """
    child: AST | None = None
    if isinstance(node, BoolOp):
        child = node.values[0]
    elif isinstance(node, (BinOp, Compare)):
        child = node.left
    elif isinstance(node, UnaryOp):
        child = node.operand
    elif isinstance(node, IfExp):
        child = node.test
    elif isinstance(node, Call):
        child = node.func
    elif isinstance(
        node,
        (Subscript, Attribute, Await, Starred, NamedExpr, FormattedValue),
    ):
        child = node.value
    elif isinstance(node, (Tuple, List, Set)) and node.elts:
        child = node.elts[0]
    elif isinstance(node, Dict) and node.values:
        child = node.keys[0] or node.values[0]
    elif isinstance(node, JoinedStr) and node.values:
        child = node.values[0]
    return child


def _safety_skip(*, pair: _Candidate, rule: str) -> PythonSimplifySkip | None:
    """Apply the shared one-use, outer-state and source-shape gates.

    Args:
        pair: Validated adjacent statement pair.
        rule: Identifier recorded on the rejection.

    Returns:
        A skip record naming the failed gate, or nothing when the
        candidate is safe to evaluate further.

    """
    second: stmt = pair.second
    context: PairContext = pair.context
    reason: str | None = None
    if not _one_use(tree=context.function, name=pair.name):
        reason = "name is read more than once in the function"
    elif _declares_outer(function=context.function, name=pair.name):
        reason = "name is declared global or nonlocal in the function"
    elif second.end_lineno != second.lineno:
        reason = "consuming statement spans multiple lines"
    elif "#" in context.lines[second.lineno - 1]:
        reason = "consuming line contains a comment"
    return (
        None
        if reason is None
        else PythonSimplifySkip(rule=rule, line=pair.line, reason=reason)
    )


def _return_edit(*, pair: _Candidate) -> _Decision:
    """Inline a one-use immediate return without moving comments.

    Args:
        pair: Validated adjacent statement pair.

    Returns:
        Exact edit, or a recorded skip when the return is not eligible.

    """
    guard: PythonSimplifySkip | None = _safety_skip(pair=pair, rule="PYS001")
    if guard is not None:
        return guard
    second: Return = cast(typ="Return", val=pair.second)
    lines: Sequence[str] = pair.context.lines
    line: int = pair.line
    original_line: str = lines[second.lineno - 1]
    newline: str = original_line[
        len(
            original_line.rstrip("""\
\r
"""),
        ) :
    ]
    return PythonSimplifyProposal(
        rule="PYS001",
        line=line,
        before="".join(lines[line - 1 : second.lineno]),
        after=(
            f"{lines[line - 1][: second.col_offset]}"
            f"return "
            f"{pair.initializer}"
            f"{newline}"
        ),
        reason=(
            "single read of a plain local; evaluation order and "
            "count are unchanged"
        ),
    )


def _compose_edit(*, pair: _Candidate) -> _Decision:
    """Inline a one-use local into a return expression it leads.

    Args:
        pair: Validated adjacent statement pair.

    Returns:
        Exact edit, or a recorded skip when the load is not provably
        the first operand evaluated by the return value.

    """
    second: Return = cast(typ="Return", val=pair.second)
    name: str = pair.name
    line: int = pair.line
    loads: list[Name] = _scope_loads(second=second, name=name)
    if not loads:
        return None
    if len(loads) != 1:
        return PythonSimplifySkip(
            rule="PYS005",
            line=line,
            reason="name is loaded more than once in the return",
        )
    guard: PythonSimplifySkip | None = _safety_skip(pair=pair, rule="PYS005")
    if guard is not None:
        return guard
    load: Name = loads[0]
    parents: dict[int, AST] = _parents(root=second)
    node: AST = load
    via_ifexp: bool = False
    while node is not second.value:
        parent: AST | None = parents.get(id(node))
        if parent is None or _first_evaluated_child(node=parent) is not node:
            return PythonSimplifySkip(
                rule="PYS005",
                line=line,
                reason=(
                    "load is not the first evaluated operand; inlining "
                    "would reorder, defer or skip evaluation"
                ),
            )
        if isinstance(parent, IfExp):
            via_ifexp = True
        node = parent
    if load.end_col_offset is None:
        return None
    statement_line: str = pair.context.lines[second.lineno - 1]
    rule: str = "PYS006" if via_ifexp else "PYS005"
    return PythonSimplifyProposal(
        rule=rule,
        line=line,
        before="".join(pair.context.lines[line - 1 : second.lineno]),
        after=(
            f"{statement_line[: load.col_offset]}"
            f"({pair.initializer})"
            f"{statement_line[load.end_col_offset :]}"
        ),
        reason=(
            "load is evaluated first and exactly once; expression "
            "order and short-circuit semantics are preserved"
        ),
    )


def _return_decision(*, pair: _Candidate) -> _Decision:
    """Choose the applicable return-statement rule.

    Args:
        pair: Validated adjacent statement pair.

    Returns:
        ``PYS001`` for a bare-name return, otherwise the conditional
        or composed-expression rules when the name is loaded once.

    """
    second: Return = cast(typ="Return", val=pair.second)
    if isinstance(second.value, Name) and second.value.id == pair.name:
        return _return_edit(pair=pair)
    return _compose_edit(pair=pair)


def _walrus_edit(*, pair: _Candidate) -> _Decision:
    """Fold a directly adjacent assignment into an ``if`` test.

    Args:
        pair: Validated adjacent statement pair.

    Returns:
        Exact edit, a recorded skip, or nothing for tests that do not
        load the assigned name.

    """
    second: If = cast(typ="If", val=pair.second)
    name: str = pair.name
    line: int = pair.line
    context: PairContext = pair.context
    if not isinstance(second.test, Name) or second.test.id != name:
        return None
    lines: Sequence[str] = context.lines
    reason: str | None = None
    if not context.walrus:
        reason = "named expressions are disabled by policy"
    elif _declares_outer(function=context.function, name=name):
        reason = "name is declared global or nonlocal in the function"
    elif second.test.end_lineno != second.lineno:
        reason = "conditional test spans multiple lines"
    elif "#" in lines[second.lineno - 1]:
        reason = "conditional line contains a comment"
    if reason is not None:
        return PythonSimplifySkip(rule="PYS002", line=line, reason=reason)
    conditional_line: str = lines[second.lineno - 1]
    if not conditional_line[second.col_offset :].startswith("if "):
        return PythonSimplifySkip(
            rule="PYS002",
            line=line,
            reason="conditional keyword is not followed by a space",
        )
    start: int = second.test.col_offset
    end: int = second.test.end_col_offset or start
    return PythonSimplifyProposal(
        rule="PYS002",
        line=line,
        before="".join(lines[line - 1 : second.lineno]),
        after=conditional_line[:start]
        + f"({name} := {pair.initializer})"
        + conditional_line[end:],
        reason=(
            "named expression preserves the binding; the test "
            "evaluates the value exactly once"
        ),
    )


def _inline_edit(*, pair: _Candidate, loads: list[Name]) -> _Decision:
    """Inline a one-use intermediate local into a simple statement.

    Args:
        pair: Validated adjacent statement pair.
        loads: Enclosing-scope loads of ``pair.name`` inside
            ``pair.second``.

    Returns:
        Exact edit, or a recorded skip when the use is not provably
        evaluated once, the name is outer state, or the statement is
        compound.

    """
    second: stmt = pair.second
    name: str = pair.name
    line: int = pair.line
    context: PairContext = pair.context
    if len(loads) != 1:
        return PythonSimplifySkip(
            rule="PYS003",
            line=line,
            reason="name is loaded more than once in the statement",
        )
    guard: PythonSimplifySkip | None = _safety_skip(pair=pair, rule="PYS003")
    if guard is not None:
        return guard
    load: Name | None = _single_use_load(second=second, name=name)
    if load is None or load.end_col_offset is None:
        return PythonSimplifySkip(
            rule="PYS003",
            line=line,
            reason=(
                "cannot prove the load is evaluated exactly once in "
                "the enclosing scope"
            ),
        )
    lines: Sequence[str] = context.lines
    statement_line: str = lines[second.lineno - 1]
    return PythonSimplifyProposal(
        rule="PYS003",
        line=line,
        before="".join(lines[line - 1 : second.lineno]),
        after=(
            f"{statement_line[: load.col_offset]}"
            f"({pair.initializer})"
            f"{statement_line[load.end_col_offset :]}"
        ),
        reason=(
            "single read inlined at its only evaluation site; "
            "binding lifetime ends unchanged"
        ),
    )


def _dead_store_edit(*, pair: _Candidate) -> _Decision:
    """Remove a store immediately overwritten by the same name.

    Args:
        pair: Validated adjacent statement pair whose initializer
            must be provably pure.

    Returns:
        Exact edit removing ``first``, a recorded skip, or nothing
        when the second statement does not unconditionally rebind
        the name.

    """
    first: stmt = pair.first
    second: stmt = pair.second
    name: str = pair.name
    line: int = pair.line
    target: expr | None = None
    if isinstance(second, Assign) and len(second.targets) == 1:
        target = second.targets[0]
    if isinstance(second, AnnAssign) and second.value is not None:
        target = second.target
    if not (isinstance(target, Name) and target.id == name):
        return None
    if not isinstance(first, Assign) or not isinstance(first.value, Constant):
        return PythonSimplifySkip(
            rule="PYS004",
            line=line,
            reason=(
                "initializer may have observable effects; only "
                "constant dead stores are removed"
            ),
        )
    if _declares_outer(function=pair.context.function, name=name):
        return PythonSimplifySkip(
            rule="PYS004",
            line=line,
            reason="name is declared global or nonlocal in the function",
        )
    return PythonSimplifyProposal(
        rule="PYS004",
        line=line,
        before=pair.context.lines[line - 1],
        after="",
        reason=(
            "dead store; a constant initializer has no observable "
            "effect before the unconditional rebind"
        ),
    )


def _statement_decision(*, pair: _Candidate) -> _Decision:
    """Choose the applicable simple-statement rule.

    Args:
        pair: Validated adjacent statement pair.

    Returns:
        ``PYS003`` when the statement loads the name, otherwise
        ``PYS004`` when it unconditionally rebinds it.

    """
    second: stmt = pair.second
    if not isinstance(second, (Expr, Assign, AnnAssign)):
        return None
    loads: list[Name] = _scope_loads(second=second, name=pair.name)
    if loads:
        return _inline_edit(pair=pair, loads=loads)
    return _dead_store_edit(pair=pair)


def _edit_pair(
    *,
    first: stmt,
    second: stmt,
    context: PairContext,
) -> _Decision:
    """Plan a rewrite only for neighboring statements in the same scope.

    Args:
        first: Assignment statement.
        second: Next statement.
        context: Source, policy and function identity.

    Returns:
        Exact edit, a recorded skip for a rejected candidate, or
        nothing when the pair has no candidate shape.

    """
    target: tuple[Name, expr] | None = _target(statement=first)
    if target is None:
        return None
    name: Name
    value: expr
    name, value = target
    line: int = first.lineno
    if (
        second.lineno != (first.end_lineno or line) + 1
        or first.col_offset != second.col_offset
    ):
        return None
    decision: _Decision
    if isinstance(first, AnnAssign):
        decision = PythonSimplifySkip(
            rule="PYS000",
            line=line,
            reason="annotated assignment keeps its explicit annotation",
        )
    elif first.end_lineno != line:
        decision = PythonSimplifySkip(
            rule="PYS000",
            line=line,
            reason="multi-line assignment cannot move as one line",
        )
    elif "#" in context.lines[line - 1]:
        decision = PythonSimplifySkip(
            rule="PYS000",
            line=line,
            reason="assignment line contains a comment",
        )
    else:
        decision = _rule_decision(
            pair=_Candidate(
                first=first,
                second=second,
                context=context,
                name=name.id,
                initializer=(
                    get_source_segment(source=context.source, node=value) or ""
                ),
                line=line,
            ),
        )
    return decision


def _rule_decision(*, pair: _Candidate) -> _Decision:
    """Route a validated adjacent pair to the applicable rule.

    Args:
        pair: Validated adjacent statement pair.

    Returns:
        The rule's decision, or nothing for an empty initializer.

    """
    if not pair.initializer:
        return None
    if isinstance(pair.second, Return):
        return _return_decision(pair=pair)
    if isinstance(pair.second, If):
        return _walrus_edit(pair=pair)
    return _statement_decision(pair=pair)


def simplify_python_source(
    *,
    source: str,
    fix: bool = False,
    walrus: bool = True,
) -> PythonSimplifyResult:
    """Find and optionally commit validated adjacent-statement rewrites.

    Args:
        source: Python module text including line endings.
        fix: Whether to commit applicable rewrites.
        walrus: Whether to introduce named expressions.

    Returns:
        Candidate edits and the optional rewritten source.

    Raises:
        SyntaxError: If input or output source fails Python 3.13 parsing.

    """
    tree: AST = parse(source=source, feature_version=(3, 13))
    lines: list[str] = source.splitlines(keepends=True)
    proposals: list[PythonSimplifyProposal] = []
    skipped: list[PythonSimplifySkip] = []
    for function in walk(node=tree):
        if not isinstance(function, (FunctionDef, AsyncFunctionDef)):
            continue
        context: PairContext = PairContext(
            source=source,
            lines=lines,
            walrus=walrus,
            function=function,
        )
        body: list[stmt] = list(function.body)
        for index in range(len(body) - 1):
            decision: _Decision = _edit_pair(
                first=body[index],
                second=body[index + 1],
                context=context,
            )
            if isinstance(decision, PythonSimplifyProposal):
                proposals.append(decision)
            elif decision is not None:
                skipped.append(decision)
    proposals.sort(key=lambda item: item.line)
    skipped.sort(key=lambda item: item.line)
    if not fix or not proposals:
        return PythonSimplifyResult(
            source=source,
            proposals=tuple(proposals),
            skipped=tuple(skipped),
            changed=False,
        )
    changed: str = source
    for accepted in reversed(proposals):
        offset: int = sum(len(line) for line in lines[: accepted.line - 1])
        if changed[offset : offset + len(accepted.before)] != accepted.before:
            skipped.append(
                PythonSimplifySkip(
                    rule=accepted.rule,
                    line=accepted.line,
                    reason=(
                        "edit conflicts with a proposal applied to a "
                        "later line"
                    ),
                ),
            )
            continue
        candidate: str = (
            changed[:offset]
            + accepted.after
            + changed[offset + len(accepted.before) :]
        )
        try:
            _ = parse(source=candidate, feature_version=(3, 13))
        except SyntaxError:
            skipped.append(
                PythonSimplifySkip(
                    rule=accepted.rule,
                    line=accepted.line,
                    reason="rewritten source failed Python 3.13 reparse",
                ),
            )
            continue
        changed = candidate
    skipped.sort(key=lambda item: item.line)
    return PythonSimplifyResult(
        source=changed,
        proposals=tuple(proposals),
        skipped=tuple(skipped),
        changed=changed != source,
    )


def simplify_python_files(
    *,
    files: Sequence[Path],
    fix: bool = False,
    walrus: bool = True,
) -> dict[str, int]:
    """Analyze or rewrite Python files, recording proposed and applied edits.

    Args:
        files: Owned Python source files.
        fix: Whether to save validated rewrites.
        walrus: Whether to consider named expressions.

    Returns:
        Counts suitable for the Exactus report.

    """
    scanned: int = 0
    proposed: int = 0
    skipped: int = 0
    changed: int = 0
    for file in sorted(set(files)):
        try:
            raw: bytes = file.read_bytes()
            encoding: str
            encoding, _ = detect_encoding(
                readline=BytesIO(initial_bytes=raw).readline,
            )
            original: str = raw.decode(encoding=encoding)
            result: PythonSimplifyResult = simplify_python_source(
                source=original,
                fix=fix,
                walrus=walrus,
            )
        except (SyntaxError, UnicodeError):
            continue
        scanned += 1
        proposed += len(result.proposals)
        skipped += len(result.skipped)
        if result.changed and not file.is_symlink():
            with NamedTemporaryFile(dir=file.parent, delete=False) as staged:
                temporary: Path = Path(staged.name)
            try:
                _ = temporary.write_bytes(
                    data=result.source.encode(encoding=encoding),
                )
                temporary.chmod(mode=file.stat().st_mode & 0o777)
                _ = temporary.replace(target=file)
            finally:
                temporary.unlink(missing_ok=True)
            changed += 1
    return {
        "files": scanned,
        "proposals": proposed,
        "skipped": skipped,
        "changed": changed,
    }
