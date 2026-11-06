"""Parse Python into source-precise, rename-insensitive structural records."""

from __future__ import annotations

from ast import (
    AST,
    AnnAssign,
    Assign,
    AsyncFunctionDef,
    Attribute,
    ClassDef,
    Constant,
    ExceptHandler,
    Expr,
    FunctionDef,
    Lambda,
    Module,
    Name,
    Return,
    dump,
    expr,
    iter_fields,
    walk,
)
from ast import arg as ast_arg
from ast import parse as ast_parse
from ast import stmt as ast_stmt
from io import StringIO
from tokenize import NAME, TokenInfo, generate_tokens, untokenize
from typing import TYPE_CHECKING, cast, final

from exactus.packages.source_merger.model import Snapshot, Statement, Unit

if TYPE_CHECKING:
    from collections.abc import Iterable


@final
class PythonParser:
    """Extract scopes and statements without modifying user source text."""

    @staticmethod
    def offset(*, source: str, line: int, col: int) -> int:
        """Convert AST UTF-8 byte columns to Python string offsets.

        Args:
            source: Complete source text.
            line: One-indexed source line.
            col: Byte-based AST column offset.

        Returns:
            Character offset in the source string.

        """
        lines: list[str] = source.splitlines(keepends=True)
        return sum(map(len, lines[: line - 1])) + len(
            lines[line - 1]
            .encode(encoding="utf-8")[:col]
            .decode(encoding="utf-8"),
        )

    @staticmethod
    def rewrite_names(*, text: str, mapping: dict[str, str]) -> str:
        """Rewrite identifier tokens, excluding strings and comments.

        Args:
            text: Self-contained Python statement source text.
            mapping: Verified, non-colliding local spelling substitutions.

        Returns:
            Text with selected NAME tokens updated.

        Raises:
            ValueError: If a token stream cannot be reconciled.

        """
        if not mapping:
            return text
        try:
            tree: Module = ast_parse(source=text)
        except SyntaxError as error:
            msg: str = (
                f"Cannot resolve identifier scopes in inserted Python code: "
                f"{error}"
            )
            raise ValueError(msg) from error
        locations: set[tuple[int, int]] = {
            (
                node.lineno,
                len(
                    text.splitlines(keepends=True)[node.lineno - 1]
                    .encode(encoding="utf-8")[: node.col_offset]
                    .decode(encoding="utf-8"),
                ),
            )
            for node in walk(node=tree)
            if isinstance(node, Name) and node.id in mapping
        }
        for node in walk(node=tree):
            if (
                isinstance(
                    node,
                    (FunctionDef, AsyncFunctionDef, ClassDef),
                )
                and node.name in mapping
            ):
                msg = (
                    f"Renaming shadowed nested declaration "
                    f"{node.name}"
                    f" requires symbol resolution"
                )
                raise ValueError(msg)
            if isinstance(
                node,
                (FunctionDef, AsyncFunctionDef, Lambda),
            ) and any(
                arg.arg in mapping
                for arg in [
                    *node.args.posonlyargs,
                    *node.args.args,
                    *node.args.kwonlyargs,
                ]
            ):
                msg = "Nested parameter shadows an identifier being renamed"
                raise ValueError(msg)
        tokens: list[TokenInfo] = list(
            generate_tokens(
                readline=StringIO(initial_value=text).readline,
            ),
        )
        return untokenize(
            iterable=[
                item._replace(string=mapping[item.string])
                if item.type == NAME and item.start in locations
                else item
                for item in tokens
            ],
        )

    def parse(self, *, source: str) -> Snapshot:
        """Parse a Python module into callable and statement identity graphs.

        Args:
            source: Python 3.13 source text.

        Returns:
            Snapshot; invalid syntax is returned as an explicit failure.

        """
        try:
            tree: Module = ast_parse(source=source, type_comments=True)
        except (SyntaxError, ValueError) as error:
            return Snapshot(
                source=source,
                units=(),
                statements=(),
                valid=False,
                error=str(object=error),
            )
        units: list[Unit] = []
        statements: list[Statement] = []
        starts: list[int] = [0]
        for line in source.splitlines(keepends=True):
            starts.append(starts[-1] + len(line))
        offsets: tuple[int, ...] = tuple(starts)
        self._visit(
            nodes=tree.body,
            parent="",
            inside_callable=False,
            acc=(units, statements),
            src=(source, offsets),
        )
        return Snapshot(
            source=source,
            units=tuple(units),
            statements=tuple(statements),
            valid=True,
        )

    @classmethod
    def _assignment_shape(cls, *, node: AST, ignore_names: bool) -> str:
        """Serialize an assignment or annotated-assignment node.

        Args:
            node: Assignment AST node.
            ignore_names: Whether to abstract identifier spellings.

        Returns:
            Normalized ``assign(...)`` fingerprint.

        """
        targets: Iterable[expr] = (
            node.targets
            if isinstance(node, Assign)
            else (
                (cast(typ="expr", val=target),)
                if (target := getattr(node, "target", None))
                else ()
            )
        )
        return (
            "assign("
            + ",".join(
                cls._shape(node=target, ignore_names=ignore_names)
                for target in targets
            )
            + ","
            + (
                cls._shape(
                    node=value,
                    ignore_names=ignore_names,
                )
                if (value := getattr(node, "value", None)) is not None
                else "none"
            )
            + ")"
        )

    @classmethod
    def _shape(cls, *, node: AST, ignore_names: bool) -> str:
        """Build a deterministic syntax fingerprint with annotations erased.

        Args:
            node: Python AST node.
            ignore_names: Whether to abstract all bound identifier spellings.

        Returns:
            Serialized recursively normalized syntax tree.

        """
        if isinstance(node, (Assign, AnnAssign)):
            return cls._assignment_shape(
                node=node,
                ignore_names=ignore_names,
            )
        atomic: str | None = cls._atomic_shape(
            node=node,
            ignore_names=ignore_names,
        )
        if atomic is not None:
            return atomic
        if isinstance(node, Attribute):
            return (
                "attr("
                + cls._shape(
                    node=node.value,
                    ignore_names=ignore_names,
                )
                + ","
                + ("attr" if ignore_names else node.attr)
                + ")"
            )
        if isinstance(node, (FunctionDef, AsyncFunctionDef, ClassDef)):
            kind: str = "class" if isinstance(node, ClassDef) else "function"
            return (
                kind
                + "("
                + ",".join(
                    cls._shape(node=child, ignore_names=ignore_names)
                    for child in node.body
                )
                + ")"
            )
        pieces: list[str] = [type(node).__name__]
        for field, value in iter_fields(node=node):
            if field in {
                "annotation",
                "type_comment",
                "type_params",
                "decorator_list",
                "returns",
            }:
                continue
            if isinstance(value, AST):
                pieces.append(
                    cls._shape(node=value, ignore_names=ignore_names),
                )
            elif isinstance(value, list):
                pieces.extend(
                    cls._shape(node=item, ignore_names=ignore_names)
                    for item in cast(typ="list[object]", val=value)
                    if isinstance(item, AST)
                )
            elif field != "ctx":
                pieces.append(str(object=value))
        return "(".join([pieces[0], ",".join(pieces[1:]) + ")"])

    @classmethod
    def _statement(
        cls,
        *,
        source: str,
        node: ast_stmt,
        offsets: tuple[int, ...],
    ) -> Statement:
        """Create a statement record with optional assignment RHS offsets.

        Args:
            source: Complete Python source.
            node: Parsed statement.
            offsets: Line-start offsets used to locate spans.

        Returns:
            Offset-backed statement identity.

        """
        value: expr | None = (
            node.value
            if isinstance(
                node,
                (Assign, AnnAssign, Return, Expr),
            )
            else None
        )
        target: expr | None = (
            node.targets[0]
            if isinstance(node, Assign) and len(node.targets) == 1
            else node.target
            if isinstance(node, AnnAssign)
            else None
        )
        return Statement(
            kind=type(node).__name__,
            start=PythonParser._fast_offset(
                source=source,
                offsets=offsets,
                line=node.lineno,
                col=node.col_offset,
            ),
            end=PythonParser._fast_offset(
                source=source,
                offsets=offsets,
                line=node.end_lineno or node.lineno,
                col=node.end_col_offset or 0,
            ),
            shape=cls._shape(node=node, ignore_names=True),
            exact=cls._shape(node=node, ignore_names=False),
            binding=target.id if isinstance(target, Name) else "",
            annotation=(
                dump(node=node.annotation, include_attributes=False)
                if isinstance(node, AnnAssign)
                else ""
            ),
            value_start=(
                PythonParser._fast_offset(
                    source=source,
                    offsets=offsets,
                    line=value.lineno,
                    col=value.col_offset,
                )
                if value
                else None
            ),
            value_end=(
                PythonParser._fast_offset(
                    source=source,
                    offsets=offsets,
                    line=value.end_lineno or value.lineno,
                    col=value.end_col_offset or 0,
                )
                if value
                else None
            ),
        )

    @classmethod
    def _unit(
        cls,
        *,
        source: str,
        node: FunctionDef | AsyncFunctionDef,
        parent: str,
        offsets: tuple[int, ...],
    ) -> Unit:
        """Create a callable scope preserving annotation spans.

        Args:
            source: Python source text.
            node: Function AST node.
            parent: Containing class or function path.
            offsets: Line-start offsets used to locate spans.

        Returns:
            Callable unit with body statements.

        """
        beginning: int = min(
            (d.lineno for d in node.decorator_list),
            default=node.lineno,
        )
        first: ast_stmt = node.body[0]
        last: ast_stmt = node.body[-1]
        statements: tuple[Statement, ...] = tuple(
            cls._statement(source=source, node=stmt, offsets=offsets)
            for stmt in node.body
        )
        parameters: tuple[str, ...] = tuple(
            a.arg
            for a in [
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            ]
        )
        return Unit(
            kind="async_function"
            if isinstance(node, AsyncFunctionDef)
            else "function",
            name=node.name,
            parent=parent,
            start=PythonParser._fast_offset(
                source=source,
                offsets=offsets,
                line=beginning,
                col=0,
            ),
            end=PythonParser._fast_offset(
                source=source,
                offsets=offsets,
                line=node.end_lineno or node.lineno,
                col=node.end_col_offset or 0,
            ),
            body_start=PythonParser._fast_offset(
                source=source,
                offsets=offsets,
                line=first.lineno,
                col=first.col_offset,
            ),
            body_end=PythonParser._fast_offset(
                source=source,
                offsets=offsets,
                line=last.end_lineno or last.lineno,
                col=last.end_col_offset or 0,
            ),
            statements=statements,
            fingerprint="|".join(stmt.shape for stmt in statements),
            signature=(
                f"{type(node).__name__}"
                f":"
                f"{len(parameters)}"
                f":"
                f"{bool(node.args.vararg)}"
                f":"
                f"{bool(node.args.kwarg)}"
            ),
            param_names=parameters,
            header_semantic="|".join(
                (
                    dump(node=node.args, include_attributes=False),
                    dump(node=node.returns, include_attributes=False)
                    if node.returns
                    else "",
                    *(
                        dump(node=item, include_attributes=False)
                        for item in node.decorator_list
                    ),
                ),
            ),
        )

    @staticmethod
    def _fast_offset(
        *,
        source: str,
        offsets: tuple[int, ...],
        line: int,
        col: int,
    ) -> int:
        """Locate an AST UTF-8 column in amortized O(line length).

        Args:
            source: Original Unicode source text.
            offsets: Precomputed character offsets of each line.
            line: One-based AST line position.
            col: Zero-based AST UTF-8 byte column.

        Returns:
            Character offset in the full source string.

        """
        beginning: int = offsets[line - 1]
        return beginning + len(
            source[beginning : offsets[line]]
            .encode(encoding="utf-8")[:col]
            .decode(encoding="utf-8"),
        )

    @staticmethod
    def _atomic_shape(*, node: AST, ignore_names: bool) -> str | None:
        """Serialize leaf nodes with no child fields.

        Args:
            node: Python AST node.
            ignore_names: Whether to abstract identifier spellings.

        Returns:
            Leaf fingerprint, or None for composite nodes.

        """
        if isinstance(node, Name):
            return "id" if ignore_names else f"id:{node.id}"
        if isinstance(node, ast_arg):
            return "arg" if ignore_names else f"arg:{node.arg}"
        if isinstance(node, Constant):
            return f"{type(node.value).__name__}:{node.value!r}"
        return None

    def _visit(
        self,
        *,
        nodes: list[ast_stmt] | tuple[ast_stmt, ...],
        parent: str,
        inside_callable: bool,
        acc: tuple[list[Unit], list[Statement]],
        src: tuple[str, tuple[int, ...]],
    ) -> None:
        """Visit nested scopes without conflating method and class.

        Args:
            nodes: Statement nodes to visit.
            parent: Containing class or function path.
            inside_callable: Whether the statements sit inside a callable.
            acc: ``(units, statements)`` accumulators.
            src: ``(source, offsets)`` source context.

        """
        units, _ = acc
        source, offsets = src
        for node in nodes:
            if isinstance(node, (FunctionDef, AsyncFunctionDef)):
                unit: Unit = self._unit(
                    source=source,
                    node=node,
                    parent=parent,
                    offsets=offsets,
                )
                units.append(unit)
                self._visit(
                    nodes=node.body,
                    parent=unit.key,
                    inside_callable=True,
                    acc=acc,
                    src=src,
                )
            elif isinstance(node, ClassDef):
                self._visit(
                    nodes=node.body,
                    parent=(f"{parent}.{node.name}") if parent else node.name,
                    inside_callable=inside_callable,
                    acc=acc,
                    src=src,
                )
            else:
                self._record_statement(
                    node=node,
                    parent=parent,
                    inside_callable=inside_callable,
                    acc=acc,
                    src=src,
                )
                for field, value in iter_fields(node=node):
                    if field in {
                        "body",
                        "orelse",
                        "finalbody",
                    }:
                        self._visit(
                            nodes=[
                                item
                                for item in value
                                if isinstance(item, ast_stmt)
                            ],
                            parent=parent,
                            inside_callable=inside_callable,
                            acc=acc,
                            src=src,
                        )
                    elif field == "handlers":
                        for handler in value:
                            if isinstance(handler, ExceptHandler):
                                self._visit(
                                    nodes=handler.body,
                                    parent=parent,
                                    inside_callable=inside_callable,
                                    acc=acc,
                                    src=src,
                                )

    def _record_statement(
        self,
        *,
        node: ast_stmt,
        parent: str,
        inside_callable: bool,
        acc: tuple[list[Unit], list[Statement]],
        src: tuple[str, tuple[int, ...]],
    ) -> None:
        """Record a non-scope statement and its module-level binding.

        Args:
            node: Statement AST node.
            parent: Containing class or function path.
            inside_callable: Whether the statement sits inside a callable.
            acc: ``(units, statements)`` accumulators.
            src: ``(source, offsets)`` source context.

        """
        units, statements = acc
        source, offsets = src
        stmt: Statement = self._statement(
            source=source,
            node=node,
            offsets=offsets,
        )
        if isinstance(node, (Assign, AnnAssign)) and (
            stmt.binding and not inside_callable
        ):
            units.append(
                Unit(
                    kind="assignment",
                    name=stmt.binding,
                    parent=parent,
                    start=PythonParser._fast_offset(
                        source=source,
                        offsets=offsets,
                        line=node.lineno,
                        col=0,
                    ),
                    end=stmt.end,
                    body_start=stmt.value_start or stmt.start,
                    body_end=stmt.value_end or stmt.end,
                    statements=(stmt,),
                    fingerprint=stmt.shape,
                    signature="assignment",
                ),
            )
        statements.append(stmt)
