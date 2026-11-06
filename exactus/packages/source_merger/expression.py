"""Conservative expression reconciliation inside matched Python."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
from ast import AST, dump, expr, get_source_segment, iter_fields, parse

from exactus.packages.source_merger.model import Replacement
from exactus.packages.source_merger.python_parser import PythonParser


def _stable(*, left: AST, right: AST) -> bool:
    """Compare expression semantics without source coordinates.

    Args:
        left: First expression subtree.
        right: Second expression subtree.

    Returns:
        Whether both subtrees are structurally identical.

    """
    return dump(node=left, include_attributes=False) == dump(
        node=right,
        include_attributes=False,
    )


type FieldValue = AST | Sequence["FieldValue"] | str | int | bool | None


def _align_field(
    *,
    before: FieldValue,
    after: FieldValue,
    current: FieldValue,
    reconcile: Callable[..., bool],
) -> bool:
    """Align one AST field across three expression forks.

    Args:
        before: Ancestor field value.
        after: User-edited field value.
        current: Refactored field value.
        reconcile: Recursive subtree comparator.

    Returns:
        Whether the field reconciles without ambiguity.

    """
    if isinstance(before, AST):
        return (
            isinstance(after, AST)
            and isinstance(current, AST)
            and reconcile(old=before, own=after, latest=current)
        )
    if not isinstance(before, list):
        return after in (before, current)
    if (
        not isinstance(after, list)
        or not isinstance(current, list)
        or len(before) != len(after)
        or len(before) != len(current)
    ):
        return False
    for first, second, third in zip(before, after, current, strict=True):
        if not (
            isinstance(first, AST)
            and isinstance(second, AST)
            and isinstance(third, AST)
        ):
            if first != second:
                return False
        elif not reconcile(old=first, own=second, latest=third):
            return False
    return True


def _align_children(
    *,
    old_fields: dict[str, AST | list[AST] | str | int | bool | None],
    own_fields: dict[str, AST | list[AST] | str | int | bool | None],
    tool_fields: dict[str, AST | list[AST] | str | int | bool | None],
    reconcile: Callable[..., bool],
) -> bool:
    """Traverse child fields, rejecting unalignable parallel edits.

    Args:
        old_fields: Ancestor field map.
        own_fields: User-edited field map.
        tool_fields: Refactored field map.
        reconcile: Recursive subtree comparator.

    Returns:
        Whether every shared field reconciles.

    """
    for name, before in old_fields.items():
        if not _align_field(
            before=before,
            after=own_fields[name],
            current=tool_fields[name],
            reconcile=reconcile,
        ):
            return False
    return True


def _parse_exprs(
    *,
    old_text: str,
    user_text: str,
    tool_text: str,
) -> tuple[expr, expr, expr]:
    """Parse all three expression forks for structural comparison.

    Args:
        old_text: Renamed ancestor expression.
        user_text: Renamed user expression.
        tool_text: Refactored expression.

    Returns:
        Ancestor, user, and tool expression roots.

    Raises:
        ValueError: Any fork failed to parse as an expression.

    """
    try:
        base: expr = parse(source=old_text, mode="eval").body
        edited: expr = parse(source=user_text, mode="eval").body
        target: expr = parse(source=tool_text, mode="eval").body
    except (SyntaxError, ValueError) as error:
        msg: str = f"Cannot compare changed Python expressions safely: {error}"
        raise ValueError(msg) from error
    return base, edited, target


@final
@dataclass(frozen=True, slots=True)
class Texts:
    """Expression text in all three forks.

    Attributes:
        original: Ancestor RHS/return expression text.
        user: User-edited expression text.
        tool: Tool-refactored expression text.

    """

    original: str
    user: str
    tool: str


def project_python_expression(
    *,
    texts: Texts,
    tool_start: int,
    mapping: dict[str, str],
    scope: str,
) -> tuple[Replacement, ...] | None:
    """Project user expression mutations into the refactored expression.

    Existing tool-side changes at other expression paths are retained. The
    algorithm rejects competing edits to a shared subtree and any node shape
    that cannot be aligned without guessing. It never evaluates source code.

    Args:
        texts: Ancestor, user-edited, and refactored expression text.
        tool_start: Absolute offset of the target expression in the tool file.
        mapping: Proven old-to-new identifier spellings.
        scope: Location recorded for proposed patches.

    Returns:
        Nonoverlapping source-span patches; None for ambiguous mutations.

    Raises:
        ValueError: Identifier rewriting or expression parsing was unsafe.

    """
    old_text: str = PythonParser.rewrite_names(
        text=texts.original,
        mapping=mapping,
    )
    user_text: str = PythonParser.rewrite_names(
        text=texts.user,
        mapping=mapping,
    )
    base, edited, target = _parse_exprs(
        old_text=old_text,
        user_text=user_text,
        tool_text=texts.tool,
    )
    patches: list[Replacement] = []

    def emit(*, own: AST, latest: AST) -> bool:
        """Stage a user subtree at the corresponding refactored span.

        Args:
            own: User-edited expression subtree.
            latest: Refactored expression subtree.

        Returns:
            Whether the subtree was staged without overlap.

        """
        if not isinstance(own, expr) or not isinstance(latest, expr):
            return False
        snippet: str | None = get_source_segment(
            source=user_text,
            node=own,
        )
        if snippet is None:
            return False
        patches.append(
            Replacement(
                start=tool_start
                + PythonParser.offset(
                    source=texts.tool,
                    line=latest.lineno,
                    col=latest.col_offset,
                ),
                end=tool_start
                + PythonParser.offset(
                    source=texts.tool,
                    line=latest.end_lineno or latest.lineno,
                    col=latest.end_col_offset or 0,
                ),
                text=snippet,
                scope=scope,
            ),
        )
        return True

    def reconcile(*, old: AST, own: AST, latest: AST) -> bool:
        """Descend to the smallest independent mutated expression subtree.

        Args:
            old: Ancestor expression subtree.
            own: User-edited expression subtree.
            latest: Refactored expression subtree.

        Returns:
            Whether the subtree reconciled without ambiguity.

        """
        if _stable(left=old, right=own):
            return True
        if _stable(left=own, right=latest):
            return True
        unchanged: bool = _stable(left=old, right=latest)
        initial: int = len(patches)
        old_fields: dict[
            str,
            AST | list[AST] | str | int | bool | None,
        ] = dict(
            iter_fields(node=old),
        )
        own_fields: dict[
            str,
            AST | list[AST] | str | int | bool | None,
        ] = dict(
            iter_fields(node=own),
        )
        tool_fields: dict[
            str,
            AST | list[AST] | str | int | bool | None,
        ] = dict(
            iter_fields(node=latest),
        )
        diverged: bool = (
            type(old) is not type(own)
            or type(old) is not type(latest)
            or old_fields.keys() != own_fields.keys()
            or old_fields.keys() != tool_fields.keys()
        )
        if diverged:
            return emit(own=own, latest=latest) if unchanged else False
        if _align_children(
            old_fields=old_fields,
            own_fields=own_fields,
            tool_fields=tool_fields,
            reconcile=reconcile,
        ):
            return True
        if not unchanged:
            return False
        del patches[initial:]
        return emit(own=own, latest=latest)

    return (
        tuple(patches)
        if reconcile(old=base, own=edited, latest=target)
        else None
    )
