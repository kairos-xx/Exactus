# Copyright (c) 2026
"""Perform conservative, scope-aware Python 3.13 AST rewrites.

Ruff owns general formatting and simplification. This module deliberately
restricts edits to directly adjacent statements in one function body, with
one evaluation of the original expression and unchanged control-flow shape.
"""

from __future__ import annotations

from ast import (
    AST,
    AnnAssign,
    Assign,
    AsyncFunctionDef,
    FunctionDef,
    If,
    Load,
    Name,
    Return,
    expr,
    get_source_segment,
    parse,
    stmt,
    walk,
)
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from tokenize import detect_encoding
from typing import TYPE_CHECKING, final

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

    """

    rule: str
    line: int
    before: str
    after: str


@final
@dataclass(frozen=True, slots=True)
class PythonSimplifyResult:
    """One source analysis or guarded transformation.

    Attributes:
        source: Final source, equal to input in audit mode.
        proposals: Applicable deterministic proposed rewrites.
        changed: Whether an edit was committed.

    """

    source: str
    proposals: tuple[PythonSimplifyProposal, ...]
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


def _return_edit(
    *,
    second: Return,
    context: PairContext,
    name: str,
    initializer: str,
    line: int,
) -> PythonSimplifyProposal | None:
    """Inline a one-use immediate return without moving comments.

    Args:
        second: Return statement to replace.
        context: Original source and enclosing function.
        name: Assigned local identifier.
        initializer: Expression source text.
        line: One-based assignment line.

    Returns:
        Exact edit, or nothing if the return is not eligible.

    """
    lines: Sequence[str] = context.lines
    if (
        not isinstance(second.value, Name)
        or second.value.id != name
        or not _one_use(tree=context.function, name=name)
        or second.end_lineno != second.lineno
        or "#" in lines[second.lineno - 1]
    ):
        return None
    original_line: str = lines[second.lineno - 1]
    newline: str = original_line[len(original_line.rstrip("\r\n")) :]
    return PythonSimplifyProposal(
        rule="PYS001",
        line=line,
        before="".join(lines[line - 1 : second.lineno]),
        after=(
            f"{lines[line - 1][: second.col_offset]}"
            f"return "
            f"{initializer}"
            f"{newline}"
        ),
    )


def _walrus_edit(
    *,
    second: If,
    context: PairContext,
    name: str,
    initializer: str,
    line: int,
) -> PythonSimplifyProposal | None:
    """Fold a directly adjacent assignment into an ``if`` test.

    Args:
        second: Following conditional.
        context: Source and policy.
        name: Name assigned before the conditional.
        initializer: Original assignment expression.
        line: One-based assignment line.

    Returns:
        Exact edit, or nothing for unsupported tests.

    """
    lines: Sequence[str] = context.lines
    if (
        not context.walrus
        or not isinstance(second.test, Name)
        or second.test.id != name
        or second.test.end_lineno != second.lineno
        or "#" in lines[second.lineno - 1]
    ):
        return None
    conditional_line: str = lines[second.lineno - 1]
    if not conditional_line[second.col_offset :].startswith("if "):
        return None
    start: int = second.test.col_offset
    end: int = second.test.end_col_offset or start
    return PythonSimplifyProposal(
        rule="PYS002",
        line=line,
        before="".join(lines[line - 1 : second.lineno]),
        after=conditional_line[:start]
        + f"({name} := {initializer})"
        + conditional_line[end:],
    )


def _edit_pair(
    *,
    first: stmt,
    second: stmt,
    context: PairContext,
) -> PythonSimplifyProposal | None:
    """Plan a rewrite only for neighboring statements in the same scope.

    Args:
        first: Assignment statement.
        second: Next statement.
        context: Source, policy and function identity.

    Returns:
        Exact edit when its preconditions are satisfied.

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
        or first.end_lineno != line
        or "#" in context.lines[line - 1]
    ):
        return None
    initializer: str = (
        get_source_segment(
            source=context.source,
            node=value,
        )
        or ""
    )
    if not initializer:
        return None
    if isinstance(second, Return):
        return _return_edit(
            second=second,
            context=context,
            name=name.id,
            initializer=initializer,
            line=line,
        )
    return (
        _walrus_edit(
            second=second,
            context=context,
            name=name.id,
            initializer=initializer,
            line=line,
        )
        if isinstance(second, If)
        else None
    )


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
            proposal: PythonSimplifyProposal | None = _edit_pair(
                first=body[index],
                second=body[index + 1],
                context=context,
            )
            if proposal is not None:
                proposals.append(proposal)
    proposals.sort(key=lambda item: item.line)
    if not fix or not proposals:
        return PythonSimplifyResult(
            source=source,
            proposals=tuple(proposals),
            changed=False,
        )
    changed: str = source
    for accepted in reversed(proposals):
        offset: int = sum(len(line) for line in lines[: accepted.line - 1])
        if changed[offset : offset + len(accepted.before)] == accepted.before:
            changed = (
                changed[:offset]
                + accepted.after
                + changed[offset + len(accepted.before) :]
            )
    _ = parse(source=changed, feature_version=(3, 13))
    return PythonSimplifyResult(
        source=changed,
        proposals=tuple(proposals),
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
    return {"files": scanned, "proposals": proposed, "changed": changed}
