"""Preserve tool line wrapping during independent Python literal edits."""

from __future__ import annotations

from ast import (
    AST,
    Constant,
    Module,
    get_source_segment,
    iter_fields,
    parse,
    stmt,
    walk,
)
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from exactus.packages.source_merger.model import Replacement, Statement
from exactus.packages.source_merger.python_parser import PythonParser

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


def _statement_node(*, source: str, record: Statement) -> stmt | None:
    """Find the exact AST statement corresponding to a source-offset record.

    Args:
        source: Complete Python program text.
        record: Statement identity and offset record.

    Returns:
        Matching AST statement or None if it cannot be uniquely determined.

    """
    try:
        tree: Module = parse(source=source)
    except SyntaxError:
        return None
    matches: list[stmt] = [
        node
        for node in walk(node=tree)
        if isinstance(node, stmt)
        and PythonParser.offset(
            source=source,
            line=node.lineno,
            col=node.col_offset,
        )
        == record.start
        and PythonParser.offset(
            source=source,
            line=node.end_lineno or node.lineno,
            col=node.end_col_offset or 0,
        )
        == record.end
    ]
    return matches[0] if len(matches) == 1 else None


def _fields(
    *,
    node: AST,
) -> Iterator[tuple[str, AST | list[AST] | str | int | bool | None]]:
    """Yield semantic AST fields for syntax equivalence inspection.

    Args:
        node: Node to enumerate.

    Yields:
        Semantic field names and child values.

    """
    for name, value in iter_fields(node=node):
        if name in {
            "ctx",
            "type_comment",
            "type_params",
            "annotation",
            "returns",
            "decorator_list",
        }:
            continue
        if isinstance(value, (AST, list, str, int, bool)) or value is None:
            yield name, value


@final
@dataclass(frozen=True, slots=True)
class LiteralFork:
    """One fork of a statement being reconciled.

    Attributes:
        source: Fork module text.
        record: Statement record in that fork.

    """

    source: str
    record: Statement


@final
@dataclass(slots=True)
class _Ctx:
    """Shared state for the constant-only subtree walk.

    Attributes:
        tool_source: Refactored module for patch offsets.
        user_source: User module for replacement snippets.
        changes: Accumulated literal replacements.

    """

    tool_source: str
    user_source: str
    changes: list[Replacement]


def _compare_constants(
    *,
    old: AST,
    own: AST,
    latest: AST,
    ctx: _Ctx,
) -> bool:
    """Record a literal replacement when the tool kept the ancestor value.

    Args:
        old: Ancestor constant.
        own: User-edited constant.
        latest: Tool-side constant.
        ctx: Shared walk state.

    Returns:
        Whether the constants align without conflict.

    """
    if not (
        isinstance(old, Constant)
        and isinstance(own, Constant)
        and isinstance(latest, Constant)
    ):
        return True
    if old.value == own.value:
        return True
    if old.value != latest.value:
        return False
    ctx.changes.append(
        Replacement(
            start=PythonParser.offset(
                source=ctx.tool_source,
                line=latest.lineno,
                col=latest.col_offset,
            ),
            end=PythonParser.offset(
                source=ctx.tool_source,
                line=latest.end_lineno or latest.lineno,
                col=latest.end_col_offset or 0,
            ),
            text=get_source_segment(source=ctx.user_source, node=own)
            or repr(own.value),
            scope="literal",
        ),
    )
    return True


def _compare_lists(
    *,
    old_value: FieldValue,
    own_value: FieldValue,
    latest_value: FieldValue,
    ctx: _Ctx,
) -> bool:
    """Compare same-length list fields recursively.

    Args:
        old_value: Ancestor list field.
        own_value: User list field.
        latest_value: Tool list field.
        ctx: Shared walk state.

    Returns:
        Whether every item reconciles.

    """
    if not (
        isinstance(old_value, list)
        and isinstance(own_value, list)
        and isinstance(latest_value, list)
    ):
        return False
    if len(old_value) != len(own_value) or len(old_value) != len(latest_value):
        return False
    for base_item, own_item, tool_item in zip(
        old_value,
        own_value,
        latest_value,
        strict=True,
    ):
        if not (
            isinstance(base_item, AST)
            and isinstance(own_item, AST)
            and isinstance(tool_item, AST)
        ):
            return False
        if not _compare(
            old=base_item,
            own=own_item,
            latest=tool_item,
            ctx=ctx,
        ):
            return False
    return True


type FieldValue = AST | Sequence["FieldValue"] | str | int | bool | None


def _compare_field(
    *,
    triple: tuple[
        tuple[str, FieldValue],
        tuple[str, FieldValue],
        tuple[str, FieldValue],
    ],
    ctx: _Ctx,
) -> bool:
    """Compare one aligned field across three forks.

    Args:
        triple: ``((name, old), (user_name, own), (tool_name, latest))``.
        ctx: Shared walk state.

    Returns:
        Whether the field reconciles.

    """
    (
        (name, old_value),
        (user_name, own_value),
        (
            tool_name,
            latest_value,
        ),
    ) = triple
    if name != user_name or name != tool_name:
        return False
    if isinstance(old_value, AST):
        return (
            isinstance(own_value, AST)
            and isinstance(latest_value, AST)
            and _compare(
                old=old_value,
                own=own_value,
                latest=latest_value,
                ctx=ctx,
            )
        )
    if isinstance(old_value, list):
        return _compare_lists(
            old_value=old_value,
            own_value=own_value,
            latest_value=latest_value,
            ctx=ctx,
        )
    return old_value == own_value


def _compare(*, old: AST, own: AST, latest: AST, ctx: _Ctx) -> bool:
    """Check AST shape and collect constant-only source edits.

    Args:
        old: Ancestor node.
        own: User-edited node.
        latest: Tool-side node.
        ctx: Shared walk state.

    Returns:
        Whether the subtree reconciles as literal-only changes.

    """
    if type(old) is not type(own) or type(old) is not type(latest):
        return False
    if isinstance(old, Constant):
        return _compare_constants(old=old, own=own, latest=latest, ctx=ctx)
    for triple in zip(
        _fields(node=old),
        _fields(node=own),
        _fields(node=latest),
        strict=False,
    ):
        if not _compare_field(triple=triple, ctx=ctx):
            return False
    return True


def literal_replacements(
    *,
    original: LiteralFork,
    user: LiteralFork,
    tool: LiteralFork,
) -> tuple[Replacement, ...] | None:
    """Transfer literal-only changes onto matching tool AST leaf positions.

    Args:
        original: Common-ancestor statement and module.
        user: Modified user statement and module.
        tool: Matching refactored statement and module.

    Returns:
        Source patches if every changed AST leaf is a safely tracked literal,
        or None when statement-level replacement is required.

    """
    base: stmt | None = _statement_node(
        source=original.source,
        record=original.record,
    )
    edited: stmt | None = _statement_node(
        source=user.source,
        record=user.record,
    )
    target: stmt | None = _statement_node(
        source=tool.source,
        record=tool.record,
    )
    if base is None or edited is None or target is None:
        return None
    ctx: _Ctx = _Ctx(
        tool_source=tool.source,
        user_source=user.source,
        changes=[],
    )
    if not _compare(old=base, own=edited, latest=target, ctx=ctx) or (
        not ctx.changes
    ):
        return None
    return tuple(ctx.changes)
