# Copyright (c) 2026 Project contributors
"""Normalize checklist headers without changing task states or obligations."""

from __future__ import annotations

from re import compile as re_compile
from typing import TYPE_CHECKING, Final, final

from .core import SyncTodoTables, visible_lines

if TYPE_CHECKING:
    from re import Match, Pattern


class Patterns:
    """Shared normalized task syntax and metadata detection.

    Attributes:
        NORMAL: Complete normalized header with identity and metadata.
        BOX: Checkbox marker, indentation and remaining task label.
        BOLD: Leading emphasized title and trailing description.
        PRIORITY: Explicit P0 through P3 priority tokens.
        META: Leading legacy glyphs or normalized metadata labels.
        START_PRIORITY: Priority prefix inside a legacy task title.
        SEPARATOR: Leading punctuation separating header and description.

    """

    _NORMAL_PARTS: Final[tuple[str, ...]] = (
        r"^\*\*([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\d+)\*\* ",
        r"\*\*(P[0-3]|Untriaged)\*\* ",
        r"\*\*(Frontend|Backend|Documentation|Testing / QA|",
        r"DevOps / Release|Uncategorized)\*\* — .+",
    )
    _META_PARTS: Final[tuple[str, ...]] = (
        r"^(?:[□◆¶✓▲]\s*|\*\*(?:P[0-3]|Untriaged|Frontend|Backend|",
        r"Documentation|Testing / QA|DevOps / Release|",
        r"Uncategorized)\*\*\s*)",
    )
    NORMAL: Final[Pattern[str]] = re_compile(pattern="".join(_NORMAL_PARTS))
    BOX: Final[Pattern[str]] = re_compile(
        pattern="^(\\s*)[-*+]\\s+\\[([xX ])\\]\\s+(.*)$",
    )
    BOLD: Final[Pattern[str]] = re_compile(pattern="^\\*\\*([^*]+)\\*\\*(.*)$")
    PRIORITY: Final[Pattern[str]] = re_compile(pattern="\\bP[0-3]\\b")
    META: Final[Pattern[str]] = re_compile(pattern="".join(_META_PARTS))
    START_PRIORITY: Final[Pattern[str]] = re_compile(
        pattern="^P[0-3]\\s*[·:—-]\\s*",
    )
    SEPARATOR: Final[Pattern[str]] = re_compile(
        pattern="^\\s*(?:—|---|--|-|:)\\s*",
    )


def category(
    *,
    label: str,
    ident: str,
    fallback: str = "Uncategorized",
) -> str:
    """Suggest a category without overriding an explicit source category.

    Args:
        label: Original task label, including any explicit metadata.
        ident: Existing or allocated task identity used for family fallback.
        fallback: Category inherited when no explicit or inferred value exists.

    Returns:
        Explicit, inferred or fallback human-readable category.

    """
    explicit: Match[str] | None = SyncTodoTables.CATEGORY.search(string=label)
    if explicit is not None and explicit.lastgroup is not None:
        return SyncTodoTables.CATEGORY_LABELS[explicit.lastgroup]
    for words, assigned in Constants.category_rules:
        if re_compile(pattern=f"\\b(?:{words})\\b").search(
            string=label.casefold(),
        ):
            return assigned
    prefix: str = (
        re_compile(pattern="\\d.*$").sub(repl="", string=ident).rstrip("-")
    )
    if prefix.startswith("UI"):
        return "Frontend"
    return Constants.family_categories.get(prefix, fallback)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        category_rules: Grouped module constant.
        family_categories: Grouped module constant.

    """

    category_rules: Final[tuple[tuple[str, str], ...]] = (
        (
            (
                "verify|qualify|tests?|testing|coverage|regressions?|lint|pyri"
                "ght|ruff"
            ),
            "Testing / QA",
        ),
        (
            "document|documentation|readme|docstrings?|handbook",
            "Documentation",
        ),
        (
            "package|packaging|wheel|bundle|deploy|release|install|ci",
            "DevOps / Release",
        ),
        (
            (
                "backend|server|protocol|api|runner|store|crawler|serializatio"
                "n|parser"
            ),
            "Backend",
        ),
        (
            (
                "ui|frontend|panels?|docking|icons?|toolbar|graph|timeline|wid"
                "gets?|layout|hover|browser|picker"
            ),
            "Frontend",
        ),
    )
    family_categories: Final[dict[str, str]] = {
        "W": "Frontend",
        "H": "Frontend",
        "S": "Frontend",
        "LT": "Frontend",
        "EV": "Testing / QA",
        "PQ": "Testing / QA",
        "TQ": "Testing / QA",
        "QA": "Testing / QA",
        "D": "Documentation",
        "B": "DevOps / Release",
        "R": "DevOps / Release",
        "A": "Backend",
        "F": "Backend",
        "C": "Backend",
        "N": "Backend",
    }


def identity(*, label: str, used: set[str], parent: str | None) -> str:
    """Retain IDs or allocate a collision-free root/child identifier.

    Args:
        label: Task label that may already contain an identity.
        used: Identities reserved elsewhere in the source document.
        parent: Parent identity for nested tasks, or None for root tasks.

    Returns:
        Preserved identity or first available identity in the parent family.

    """
    tagged: Match[str] | None = SyncTodoTables.TASK.match(string=label)
    if tagged is not None:
        return tagged[1]
    prefix: str = parent if parent is not None else "TODO"
    digits: int = 2 if parent is not None else 3
    number: int = 1
    while f"{prefix}-{number:0{digits}d}" in used:
        number += 1
    return f"{prefix}-{number:0{digits}d}"


def priority_for(
    *,
    label: str,
    parent: str | None,
    headings: dict[int, str],
) -> str:
    """Keep ambiguity explicit instead of assigning invented urgency.

    Args:
        label: Task label to scan for explicit urgency tokens.
        parent: Priority inherited from the enclosing task, when present.
        headings: Heading-depth priorities inherited by top-level tasks.

    Returns:
        One explicit or inherited priority, or Untriaged when ambiguous.

    """
    explicit: set[str] = set(Patterns.PRIORITY.findall(string=label))
    if explicit:
        return next(iter(explicit)) if len(explicit) == 1 else "Untriaged"
    if parent is not None:
        return parent
    return next(
        (value for _level, value in sorted(headings.items(), reverse=True)),
        "Untriaged",
    )


def description(*, label: str, ident: str) -> str:
    """Remove legacy header fields but retain description text and emphasis.

    Args:
        label: Original task label containing legacy header fields.
        ident: Identity removed from the leading emphasized title.

    Returns:
        Description with legacy metadata removed and emphasis retained.

    """
    body: str = label
    bold: Match[str] | None = Patterns.BOLD.match(string=label)
    if (
        SyncTodoTables.TASK.match(string=label) is not None
        and bold is not None
    ):
        title: str = Patterns.SEPARATOR.sub(
            repl="",
            string=bold[1][len(ident) :],
        )
        title = Patterns.START_PRIORITY.sub(repl="", string=title)
        body = (f"**{title}**" if title else "") + bold[2]
    body = body.lstrip()
    meta: Match[str] | None
    while (meta := Patterns.META.match(string=body)) is not None:
        body = body[meta.end() :].lstrip()
    return Patterns.SEPARATOR.sub(repl="", string=body)


def normalize(*, text: str) -> str:
    """Write uniform headers, preserving states, descriptions and existing IDs.

    Missing urgency remains Untriaged. Suggested categories are written into
    source for review; already-normalized headers are never reclassified.

    Args:
        text: Complete Markdown source, including fences and comments.

    Returns:
        Normalized source with existing states and line endings preserved.

    """
    source: list[str] = text.splitlines(keepends=True)
    visible: list[str] = list(visible_lines(text=text))
    box: Match[str] | None
    match: Match[str] | None
    used: set[str] = {
        match[1]
        for line in visible
        if (box := Patterns.BOX.match(string=line)) is not None
        and (match := SyncTodoTables.TASK.match(string=box[3])) is not None
    }
    parents: list[tuple[int, str, str, str]] = []
    headings: dict[int, str] = {}
    for index, line in enumerate(iterable=visible):
        heading: Match[str] | None = SyncTodoTables.HEADING.match(string=line)
        if heading is not None:
            depth: int = len(heading[1])
            headings = {
                level: value
                for level, value in headings.items()
                if level < depth
            }
            candidates: set[str] = set(
                Patterns.PRIORITY.findall(string=heading[2]),
            )
            if candidates:
                headings[depth] = (
                    next(iter(candidates))
                    if len(candidates) == 1
                    else "Untriaged"
                )
            parents.clear()
            continue
        box = Patterns.BOX.match(string=line)
        if box is None:
            continue
        indent: str
        state: str
        label: str
        indent, state, label = box.groups()
        depth = len(indent.expandtabs(tabsize=4))
        parents = [parent for parent in parents if parent[0] < depth]
        existing: Match[str] | None
        if (existing := Patterns.NORMAL.match(string=label)) is not None:
            parents.append((depth, existing[1], existing[2], existing[3]))
            continue
        ident: str = identity(
            label=label,
            used=used,
            parent=parents[-1][1] if parents else None,
        )
        used.add(ident)
        priority: str = priority_for(
            label=label,
            parent=parents[-1][2] if parents else None,
            headings=headings,
        )
        assigned: str = category(
            label=label,
            ident=ident,
            fallback=parents[-1][3] if parents else "Uncategorized",
        )
        body: str = description(label=label, ident=ident)
        ending: str = source[index][len(source[index].rstrip("\r\n")) :]
        source[index] = "".join(
            (
                f"{indent}- [{state}] **{ident}** **{priority}** ",
                f"**{assigned}** — {body}{ending}",
            ),
        )
        parents.append((depth, ident, priority, assigned))
    return "".join(source)
