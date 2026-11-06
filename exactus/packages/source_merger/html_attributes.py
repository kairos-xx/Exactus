"""Conservative three-way HTML attribute reconciliation by source spans."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from re import Match, Pattern
from re import compile as re_compile
from re import match as re_match
from typing import final

from exactus.packages.source_merger.model import (
    AppliedChange,
    MergeConflict,
    Replacement,
    Unit,
)


@final
@dataclass(frozen=True, slots=True)
class _Attribute:
    """HTML attribute with raw spelling and offset-preserving syntax.

    Attributes:
        name: Case-preserving HTML attribute name.
        value: Parsed semantic attribute value, or None for boolean attributes.
        start: Start of leading whitespace before the attribute.
        end: End of the attribute token.
        raw: Original attribute token with leading whitespace.

    """

    name: str
    value: str | None
    start: int
    end: int
    raw: str


def _read(*, source: str, unit: Unit) -> tuple[str, dict[str, _Attribute]]:
    """Read the element's opening tag without normalizing its serialization.

    Args:
        source: Complete HTML snapshot.
        unit: Syntax record of the element.

    Returns:
        Tag name and its unambiguous attribute mapping.

    Raises:
        ValueError: The tag contains syntactically ambiguous attributes.

    """
    opening: str = source[unit.start : unit.body_start]
    match: Match[str] | None = re_match(
        pattern=r"<\s*([\w:-]+)",
        string=opening,
    )
    if match is None:
        msg: str = f"Cannot recognize the opening tag at {unit.key}"
        raise ValueError(msg)
    pattern: Pattern[str] = re_compile(
        pattern=r"\s+([:\w.-]+)(?:\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+))?",
    )
    attributes: dict[str, _Attribute] = {}
    position: int = match.end()
    while position < len(opening) and opening[position] not in ">/":
        found: Match[str] | None = pattern.match(string=opening, pos=position)
        if found is None:
            msg = f"Ambiguous attribute syntax for {unit.key}"
            raise ValueError(msg)
        name: str = found.group(1).lower()
        value: str | None = found.group(2)
        if name in attributes:
            msg = f"Duplicate attribute {name} on {unit.key}"
            raise ValueError(msg)
        attributes[name] = _Attribute(
            name=name,
            value=unescape(
                s=value[1:-1] if value and value[:1] in {"'", '"'} else value,
            )
            if value
            else None,
            start=unit.start + found.start(),
            end=unit.start + found.end(),
            raw=found.group(),
        )
        position = found.end()
    return match.group(1), attributes


@final
@dataclass(frozen=True, slots=True)
class Fork:
    """One fork of a reconciled element.

    Attributes:
        source: Fork HTML text.
        unit: Matched element unit in that fork.

    """

    source: str
    unit: Unit


def _attribute_decision(
    *,
    name: str,
    previous: _Attribute | None,
    own: _Attribute | None,
    candidate: _Attribute | None,
    keys: tuple[str, str],
) -> tuple[Replacement | None, MergeConflict | None, str | None]:
    """Decide the fate of one attribute across all three forks.

    Args:
        name: Attribute name being reconciled.
        previous: Ancestor attribute value.
        own: User-edited attribute value.
        candidate: Tool-refactored attribute value.
        keys: Ancestor and refactored element keys.

    Returns:
        Patch, conflict, or inserted raw text; all None for no change.

    """
    original_key, tool_key = keys
    patch: Replacement | None = None
    conflict: MergeConflict | None = None
    inserted: str | None = None
    unchanged: bool = (
        previous is not None
        and own is not None
        and previous.value == own.value
    ) or (previous is None and own is None)
    if unchanged:
        pass
    elif (candidate.value if candidate else None) != (
        previous.value if previous else None
    ):
        if not (
            own is not None
            and candidate is not None
            and own.value == candidate.value
        ):
            conflict = MergeConflict(
                kind="concurrent_change",
                scope=original_key,
                detail=(f"Both forks changed HTML attribute {name}"),
            )
    elif own is not None and candidate is not None:
        patch = Replacement(
            start=candidate.start,
            end=candidate.end,
            text=own.raw,
            scope=tool_key,
        )
    elif own is not None:
        inserted = own.raw
    return patch, conflict, inserted


def reconcile(
    *,
    original: Fork,
    user: Fork,
    tool: Fork,
) -> tuple[list[Replacement], list[MergeConflict], list[AppliedChange]]:
    """Apply independent user attribute edits to relocated HTML opening tags.

    Args:
        original: Common ancestor element and its HTML.
        user: User-edited element and its HTML.
        tool: Refactored element and its HTML.

    Returns:
        Disjoint opening-tag patches, conflicts, and audit records.

    """
    try:
        original_tag, old_attrs = _read(
            source=original.source,
            unit=original.unit,
        )
        user_tag, new_attrs = _read(source=user.source, unit=user.unit)
        _, tool_attrs = _read(source=tool.source, unit=tool.unit)
    except ValueError as error:
        return (
            [],
            [
                MergeConflict(
                    kind="unsupported_transformation",
                    scope=original.unit.key,
                    detail=str(object=error),
                ),
            ],
            [],
        )
    if original_tag != user_tag:
        return (
            [],
            [
                MergeConflict(
                    kind="structural_change",
                    scope=original.unit.key,
                    detail="User changed the HTML tag name",
                ),
            ],
            [],
        )
    patches: list[Replacement] = []
    conflicts: list[MergeConflict] = []
    applied: list[AppliedChange] = []
    inserted: list[str] = []
    for name in sorted(set(old_attrs) | set(new_attrs)):
        patch, conflict, inserted_raw = _attribute_decision(
            name=name,
            previous=old_attrs.get(name),
            own=new_attrs.get(name),
            candidate=tool_attrs.get(name),
            keys=(original.unit.key, tool.unit.key),
        )
        if conflict is not None:
            conflicts.append(conflict)
            continue
        if patch is not None:
            patches.append(patch)
        if inserted_raw is not None:
            inserted.append(inserted_raw)
        if patch is not None or inserted_raw is not None:
            applied.append(
                AppliedChange(
                    scope=original.unit.key,
                    operation="html_attribute",
                    detail=(f"Reconciled attribute {name}"),
                ),
            )
    insertion: Replacement | None = _insertion_patch(
        tool_source=tool.source,
        tool=tool.unit,
        inserted=inserted,
    )
    if insertion is not None:
        patches.append(insertion)
    return patches, conflicts, applied


def _insertion_patch(
    *,
    tool_source: str,
    tool: Unit,
    inserted: list[str],
) -> Replacement | None:
    """Place new attributes just before the tag closing bracket.

    Args:
        tool_source: Refactored HTML text.
        tool: Refactored element unit.
        inserted: Raw attribute fragments to add.

    Returns:
        Patch inserting the fragments, or None when nothing was added.

    """
    if not inserted:
        return None
    closing: int = tool.body_start - 1
    while closing > tool.start and tool_source[closing - 1].isspace():
        closing -= 1
    if tool_source[closing - 1 : closing] == "/":
        closing -= 1
    return Replacement(
        start=closing,
        end=closing,
        text="".join(inserted),
        scope=tool.key,
    )
