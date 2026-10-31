# Copyright (c) 2026 Project contributors
"""Synchronize the managed progress dashboard in TODO.md."""

from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass, field
from json import dumps
from os import getpid
from pathlib import Path
from re import Match, Pattern
from re import compile as re_compile
from time import time_ns
from typing import TYPE_CHECKING, ClassVar, final

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class SyncTodoDefaults:
    """Immutable scalar configuration values.

    Attributes:
        end: Managed dashboard block end marker.
        start: Managed dashboard block start marker.
        summary_start: Optional top summary block start marker.
        summary_end: Optional top summary block end marker.

    """

    start: str = "<!-- ROADMAP_PROGRESS_DASHBOARD_START -->"
    end: str = "<!-- ROADMAP_PROGRESS_DASHBOARD_END -->"
    summary_start: str = "<!-- ROADMAP_PROGRESS_SUMMARY_START -->"
    summary_end: str = "<!-- ROADMAP_PROGRESS_SUMMARY_END -->"


@final
class SyncTodoTables:
    """Shared lookup tables and compiled values.

    Attributes:
        CATEGORY: Explicit category glyph or label matcher.
        CATEGORY_LABELS: Display names for dashboard task categories.
        CATEGORY_ORDER: Stable category ordering in generated tables.
        CHECKBOX: Markdown task checkbox line.
        DEFAULT_PATH: TODO.md path resolved beside this script.
        FENCE: Fenced code block boundary.
        HEADING: ATX heading line.
        LIST_ITEM: New list item that ends a task-label continuation.
        ONGOING: ONGOING keyword inside a checkbox label.
        HEARTBEAT_INTERVAL: Seconds between watchdog heartbeat writes.
        HEARTBEAT_STALE: Seconds without a heartbeat before the watchdog
            is reported as stale.
        PID_SUFFIX: Watchdog state-file suffix beside TODO.md.
        PRIORITY: Priority tag such as ``P1``.
        STAMP_FORMAT: ``strftime`` layout for the last-update timestamp.
        TASK: Tagged task label such as ``**DIS-001** **P0**``.
        TEXT_PREFIX: Leading identifier and category text removed from labels.
        WATCH_INTERVAL: Seconds between watchdog polls.
        WORKSTREAM_LEVEL: Heading depth of top-level roadmap groups.
        DETAIL_LEVEL: Deepest heading depth shown in the grouped workstream
            table.

    """

    WORKSTREAM_LEVEL: ClassVar[int] = 2
    DETAIL_LEVEL: ClassVar[int] = 5
    DEFAULT_PATH: ClassVar[Path] = Path("exactus/docs/todo/TODO.md")
    CHECKBOX: ClassVar[Pattern[str]] = re_compile(
        pattern=r"^\s*[-*+]\s+\[([xX ])\]\s+(.*)$",
    )
    LIST_ITEM: ClassVar[Pattern[str]] = re_compile(
        pattern=r"^\s*(?:[-*+]|\d{1,9}[.)])\s",
    )
    TEXT_PREFIX: ClassVar[Pattern[str]] = re_compile(
        pattern=(
            r"^(?:P[0-3]|Untriaged)\s+(?:Frontend|Backend|Documentation|"
            r"Testing / QA|DevOps / Release|Uncategorized)\s+—\s*"
            r"|^(?:[A-Z]+-\d+\s+)?P[0-3]\s+"
        ),
    )
    FENCE: ClassVar[Pattern[str]] = re_compile(
        pattern=r"^ {0,3}(`{3,}|~{3,})(.*)$",
    )
    HEADING: ClassVar[Pattern[str]] = re_compile(
        pattern=r"^(#{1,6})\s+(.+?)\s*#*\s*$",
    )
    ONGOING: ClassVar[Pattern[str]] = re_compile(
        pattern=r"\bONGOING\b",
        flags=0,
    )
    PRIORITY: ClassVar[Pattern[str]] = re_compile(pattern=r"\bP([0-3])\b")
    TASK: ClassVar[Pattern[str]] = re_compile(
        pattern=(r"^\*\*([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\d+)\b"),
    )
    CATEGORY: ClassVar[Pattern[str]] = re_compile(
        pattern=(
            r"(?P<frontend>□|\*\*Frontend\*\*)|(?P<backend>◆|\*\*Backend\*\*)|"
            r"(?P<documentation>¶|\*\*Documentation\*\*)|"
            r"(?P<testing>✓|\*\*Testing / QA\*\*)|"
            r"(?P<devops>▲|\*\*DevOps / Release\*\*)|"
            r"(?P<uncategorized>\*\*Uncategorized\*\*)"
        ),
    )
    CATEGORY_ORDER: ClassVar[tuple[str, ...]] = (
        "frontend",
        "backend",
        "documentation",
        "testing",
        "devops",
        "uncategorized",
    )
    CATEGORY_LABELS: ClassVar[dict[str, str]] = {
        "frontend": "Frontend",
        "backend": "Backend",
        "documentation": "Documentation",
        "testing": "Testing / QA",
        "devops": "DevOps / Release",
        "uncategorized": "Uncategorized",
    }
    WATCH_INTERVAL: ClassVar[float] = 0.5
    HEARTBEAT_INTERVAL: ClassVar[float] = 2.0
    HEARTBEAT_STALE: ClassVar[float] = 10.0
    PID_SUFFIX: ClassVar[str] = ".sync-todo.pid"
    STAMP_FORMAT: ClassVar[str] = "%d/%m/%Y %H:%M:%S"


@dataclass(frozen=True, slots=True)
class Task:
    """One tagged checklist item.

    Attributes:
        done: Whether the checkbox is checked.
        ident: Stable task identifier such as ``DIS-001``.
        priority: Priority tag such as ``P0``.
        category: Broad engineering category inferred from the task glyph.

    """

    ident: str
    priority: str
    category: str
    done: bool


@dataclass(slots=True)
class Counts:
    """Store checkbox totals for one roadmap section.

    Attributes:
        anchor: Unique document fragment for the owning heading.
        done: Checked checkbox count.
        level: Heading depth (``0`` for unsectioned items).
        ongoing: Unchecked items tagged ONGOING.
        open: Unchecked checkbox count.
        tasks: Tagged tasks owned by the section.
        title: Heading text of the owning section.

    """

    title: str
    level: int
    anchor: str = ""
    done: int = 0
    open: int = 0
    ongoing: int = 0
    tasks: list[Task] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Return total checklist items.

        Returns:
            Sum of done and open counts.

        """
        return self.done + self.open


def _dashboard_bounds(text: str) -> tuple[int, int] | None:
    """Return managed-dashboard bounds.

    Args:
        text: TODO.md content to inspect.

    Returns:
        ``(start, end)`` character offsets of the managed block, or
        ``None`` when no markers exist.

    Raises:
        ValueError: When markers are duplicated or reversed.

    """
    defaults: type[SyncTodoDefaults] = SyncTodoDefaults
    if defaults.start not in text and defaults.end not in text:
        return None
    if text.count(defaults.start) != 1 or text.count(defaults.end) != 1:
        msg: str = "Expected exactly one progress marker pair."
        raise ValueError(msg)
    start: int = text.index(defaults.start)
    end: int = text.index(defaults.end)
    if end < start:
        msg = "Progress markers are reversed."
        raise ValueError(msg)
    return start, end + len(defaults.end)


def visible_lines(text: str) -> Iterator[str]:
    """Yield lines outside fences, comments and the managed dashboard.

    Args:
        text: TODO.md content to filter.

    Yields:
        Lines with fenced blocks, HTML comments, and the managed block
        blanked out.

    """
    if (bounds := _dashboard_bounds(text=text)) is not None:
        text = (
            text[: bounds[0]]
            + "\n" * text[bounds[0] : bounds[1]].count("\n")
            + text[bounds[1] :]
        )
    fence: str = ""
    in_comment: bool = False
    for line in text.splitlines():
        if fence:
            if (
                (match := SyncTodoTables.FENCE.match(string=line)) is not None
                and match[1][0] == fence[0]
                and len(match[1]) >= len(fence)
                and not match[2].strip()
            ):
                fence = ""
            yield ""
            continue
        if (
            not in_comment
            and (match := SyncTodoTables.FENCE.match(string=line)) is not None
        ):
            fence = match[1]
            yield ""
            continue
        visible: str = ""
        remaining: str = line
        while remaining:
            if in_comment:
                if (close := remaining.find("-->")) < 0:
                    break
                remaining = remaining[close + 3 :]
                in_comment = False
            elif (opening := remaining.find("<!--")) < 0:
                visible += remaining
                break
            else:
                visible += remaining[:opening]
                remaining = remaining[opening + 4 :]
                in_comment = True
        yield visible


def task_priority(label: str) -> str:
    """Read explicit header priority before legacy description annotations.

    Args:
        label: Task label containing normalized or legacy priority metadata.

    Returns:
        Explicit priority label, or an empty string when unspecified.

    """
    header: Match[str] | None = re_compile(
        pattern=r"^\*\*[A-Z][A-Z0-9-]*\*\* \*\*(P[0-3]|Untriaged)\*\*",
    ).match(string=label)
    if header is not None:
        return header[1]
    legacy: Match[str] | None = SyncTodoTables.PRIORITY.search(string=label)
    return f"P{legacy[1]}" if legacy is not None else ""


def _count_item(
    current: Counts,
    priorities: dict[str, tuple[int, int]],
    checkbox: Match[str],
) -> None:
    """Accumulate one checkbox item into section and priority counts.

    Args:
        current: Section receiving the item.
        priorities: Per-priority ``(done, open)`` totals to update.
        checkbox: Matched checkbox line.

    """
    tables: type[SyncTodoTables] = SyncTodoTables
    checked: bool = checkbox[1].lower() == "x"
    current.done += int(checked)
    current.open += int(not checked)
    current.ongoing += int(
        not checked
        and SyncTodoTables.ONGOING.search(string=checkbox[2]) is not None,
    )
    category: str = "uncategorized"
    if (
        category_match := tables.CATEGORY.search(string=checkbox[2])
    ) is not None:
        category = next(
            name
            for name in tables.CATEGORY_ORDER
            if category_match.group(name) is not None
        )
    tag: Match[str] | None = tables.TASK.match(string=checkbox[2])
    priority: str = task_priority(label=checkbox[2])
    current.tasks.append(
        Task(
            ident=tag[1] if tag is not None else "",
            priority=priority,
            category=category,
            done=checked,
        ),
    )
    if priority:
        key: str = priority
        done, open_count = priorities.get(key, (0, 0))
        priorities[key] = (done + int(checked), open_count + int(not checked))


def parse(text: str) -> tuple[list[Counts], dict[str, tuple[int, int]]]:
    """Count real checkboxes and priority annotations.

    Args:
        text: TODO.md content to scan.

    Returns:
        Section counts plus per-priority ``(done, open)`` totals.

    """
    sections: list[Counts] = []
    current: Counts = Counts(title="Unsectioned", level=0)
    sections.append(current)
    priorities: dict[str, tuple[int, int]] = {}
    used: dict[str, int] = {}
    for line in visible_lines(text=text):
        if (heading := SyncTodoTables.HEADING.match(string=line)) is not None:
            slug: str = _anchor(title=heading[2])
            seen: int = used.get(slug, 0)
            used[slug] = seen + 1
            current = Counts(
                title=heading[2],
                level=len(heading[1]),
                anchor=slug if seen == 0 else f"{slug}-{seen}",
            )
            sections.append(current)
            continue
        if (
            checkbox := SyncTodoTables.CHECKBOX.match(string=line)
        ) is not None:
            _count_item(
                current=current,
                priorities=priorities,
                checkbox=checkbox,
            )
    kept: list[Counts] = []
    for index, section in enumerate(iterable=sections):
        if section.total:
            kept.append(section)
            continue
        for child in sections[index + 1 :]:
            if child.level <= section.level:
                break
            if child.total:
                kept.append(section)
                break
    return kept, priorities


def _workstream_rows(sections: list[Counts], anchors: list[str]) -> list[str]:
    """Render rolled-up workstream table rows.

    Args:
        sections: Parsed section counts in document order.
        anchors: Per-section heading anchors.

    Returns:
        Markdown table rows with descendant counts rolled up.

    """
    tables: type[SyncTodoTables] = SyncTodoTables
    rows: list[str] = []
    for index, section in enumerate(iterable=sections):
        if (
            section.level < tables.WORKSTREAM_LEVEL
            or section.level > tables.DETAIL_LEVEL
        ):
            continue
        title: str = section.title.replace("|", "\\|")
        indent: str = "&nbsp;" * max(
            0,
            (section.level - tables.WORKSTREAM_LEVEL) * 2,
        )
        roll_done: int = section.done
        roll_open: int = section.open
        for child in sections[index + 1 :]:
            if child.level <= section.level:
                break
            roll_done += child.done
            roll_open += child.open
        roll_total: int = roll_done + roll_open
        percent: float = 100.0 * roll_done / roll_total if roll_total else 0.0
        rows.append(
            "".join(
                (
                    f"| {indent}[{title}](#{anchors[index]}) | ",
                    f"{roll_done} | {roll_open} | ",
                    f"{roll_total} | {percent:.1f}% |",
                ),
            ),
        )
    return rows


def _category_rows(sections: list[Counts]) -> list[str]:
    """Render progress rows grouped by broad engineering category.

    Tasks without an explicit category glyph remain Uncategorized.

    Args:
        sections: Parsed section counts in document order.

    Returns:
        Markdown table rows for frontend, backend, documentation,
        testing/QA, and DevOps/release work.

    """
    tables: type[SyncTodoTables] = SyncTodoTables
    counts: dict[str, list[int]] = {
        category: [0, 0] for category in tables.CATEGORY_ORDER
    }
    for section in sections:
        for task in section.tasks:
            values: list[int] = counts[task.category]
            values[0] += int(task.done)
            values[1] += int(not task.done)
    rows: list[str] = []
    for category in tables.CATEGORY_ORDER:
        done, open_count = counts[category]
        total: int = done + open_count
        percent: float = 100.0 * done / total if total else 0.0
        rows.append(
            "".join(
                (
                    f"| {tables.CATEGORY_LABELS[category]} | ",
                    f"{done} | {open_count} | {total} | ",
                    f"{percent:.1f}% |",
                ),
            ),
        )
    return rows


def _matrix_rows(sections: list[Counts], anchors: list[str]) -> list[str]:
    """Render per-task priority matrix rows.

    Args:
        sections: Parsed section counts in document order.
        anchors: Per-section heading anchors.

    Returns:
        Markdown matrix rows grouped by owning section.

    """
    tables: type[SyncTodoTables] = SyncTodoTables
    rows: list[str] = []
    for index, section in enumerate(iterable=sections):
        if not any(task.ident for task in section.tasks):
            continue
        title: str = section.title.replace("|", "\\|")
        indent: str = "&nbsp;" * max(
            0,
            (section.level - tables.WORKSTREAM_LEVEL) * 2,
        )
        rows.append(f"| {indent}[{title}](#{anchors[index]}) | | | | | | |")
        for task in section.tasks:
            if not task.ident:
                continue
            mark: str = "●" if task.done else "○"
            cells: list[str] = [
                "●" if task.priority == f"P{column}" else ""
                for column in range(4)
            ]
            cells.append("●" if task.priority in {"", "Untriaged"} else "")
            rows.append(
                "".join(
                    (
                        (
                            f"| [{task.ident} "
                            f"{SyncTodoTables.CATEGORY_LABELS[task.category]}]"
                            f"(#{anchors[index]}) | "
                        ),
                        f"{' | '.join(cells)} | ",
                        f"{mark} |",
                    ),
                ),
            )
    return rows


def _anchor(title: str) -> str:
    """Return the GitHub heading anchor for a section title.

    Args:
        title: Heading text to slugify.

    Returns:
        Lowercase anchor with punctuation dropped and spaces dashed.

    """
    kept: str = "".join(
        char for char in title.lower() if char.isalnum() or char in " _-"
    )
    return kept.replace(" ", "-")


def _render(text: str) -> str:
    """Render the complete managed dashboard.

    Args:
        text: TODO.md content to summarize.

    Returns:
        Markdown block bounded by the dashboard markers.

    """
    defaults: type[SyncTodoDefaults] = SyncTodoDefaults
    sections, priorities = parse(text=text)
    done: int = sum(section.done for section in sections)
    total: int = sum(section.total for section in sections)
    open_count: int = total - done
    ongoing: int = sum(section.ongoing for section in sections)
    percent: float = 100.0 * done / total if total else 0.0
    lines: list[str] = [
        defaults.start,
        "",
        "## Overall implementation status",
        "",
        (
            "> Generated from real Markdown checkboxes outside fenced "
            "examples, HTML"
        ),
        "> comments and this managed block. Only `[x]` counts as complete.",
        "> Every checkbox counts equally, including parent and child items.",
        "> These totals are not release-readiness evidence.",
        "",
        "".join(
            (
                '<div role="progressbar" aria-label="Roadmap completion" ',
                f'aria-valuenow="{done}" aria-valuemin="0" ',
                f'aria-valuemax="{total}" ',
                'style="width:100%;height:1.5rem;background:#e5e7eb;',
                'border-radius:.75rem;overflow:hidden;">',
            ),
        ),
        "".join(
            (
                f'<div style="width:{percent:.1f}%;height:100%;',
                f'background:hsl({percent * 1.2:.1f} 80% 45%);"></div>',
            ),
        ),
        "</div>",
        f"<p><strong>{done}/{total} ({percent:.1f}%)</strong></p>",
        "",
        "".join(
            (
                f"**Done:** {done} · **Open:** {open_count} · ",
                f"**ONGOING:** {ongoing} · **Total:** {total}",
            ),
        ),
        "",
        "### Priority progress",
        "",
        "| Priority | Done | Open | Total | Progress |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    if priorities:
        for priority in sorted(priorities):
            p_done, p_open = priorities[priority]
            p_total: int = p_done + p_open
            p_percent: float = 100.0 * p_done / p_total if p_total else 0.0
            lines.append(
                "".join(
                    (
                        f"| {priority} | {p_done} | {p_open} | {p_total} | ",
                        f"{p_percent:.1f}% |",
                    ),
                ),
            )
    else:
        lines.append("| — | 0 | 0 | 0 | — |")
    anchors: list[str] = [section.anchor for section in sections]
    lines.extend(
        [
            "",
            "### Engineering category progress",
            "",
            (
                "> Categories come from explicit task labels in the source "
                "Markdown (legacy glyphs remain supported). "
                "Unmarked tasks are Uncategorized."
            ),
            "",
            "| Category | Done | Open | Total | Progress |",
            "| --- | ---: | ---: | ---: | ---: |",
            *_category_rows(sections=sections),
            "",
            "### Workstream progress",
            "",
            "| Workstream | Done | Open | Total | Progress |",
            "| --- | ---: | ---: | ---: | ---: |",
            *_workstream_rows(sections=sections, anchors=anchors),
            "",
            "### Priority task matrix",
            "",
            "| Task | P0 | P1 | P2 | P3 | Untriaged | Done |",
            "| --- | :---: | :---: | :---: | :---: | :---: | :---: |",
            *_matrix_rows(sections=sections, anchors=anchors),
        ],
    )
    lines.extend(
        [
            "",
            "Regenerate: `python -m exactus.packages.todo_sync`  ",
            "Check freshness: `python -m exactus.packages.todo_sync --check`",
            "",
            defaults.end,
        ],
    )
    return "\n".join(lines)


def render_html(text: str) -> str:
    """Render the self-contained interactive TODO.html dashboard.

    Args:
        text: Synchronized TODO Markdown.

    Returns:
        Complete standalone HTML document.

    """
    tasks: list[dict[str, bool | int | list[int] | list[str] | str]] = []
    section: str = "Unsectioned"
    section_line: int = 1
    headings: dict[int, tuple[str, int]] = {}
    lines: list[str] = list(visible_lines(text=text))
    index: int = 0
    while index < len(lines):
        line_number: int = index + 1
        line: str = lines[index]
        index += 1
        if (heading := SyncTodoTables.HEADING.match(string=line)) is not None:
            depth: int = len(heading[1])
            headings = {d: h for d, h in headings.items() if d < depth}
            headings[depth] = (heading[2], line_number)
            section = heading[2]
            section_line = line_number
            continue
        if (checkbox := SyncTodoTables.CHECKBOX.match(string=line)) is None:
            continue
        label: str = checkbox[2]
        while index < len(lines):
            continuation: str = lines[index]
            if (
                not (stripped := continuation.strip())
                or continuation[:1] not in (" ", "\t")
                or SyncTodoTables.LIST_ITEM.match(string=continuation)
                is not None
            ):
                break
            label = f"{label} {stripped}"
            index += 1
        tag: Match[str] | None = SyncTodoTables.TASK.match(string=label)
        category: str = "uncategorized"
        if (
            category_match := SyncTodoTables.CATEGORY.search(string=label)
        ) is not None:
            category = next(
                name
                for name in SyncTodoTables.CATEGORY_ORDER
                if category_match.group(name) is not None
            )
        ident: str = tag[1] if tag is not None else ""
        clean: str = label
        for glyph in ("□", "◆", "¶", "✓", "▲"):
            clean = clean.replace(glyph, "")
        clean = " ".join(clean.replace("**", "").split())
        if ident and clean.startswith(f"{ident} "):
            clean = clean[len(ident) + 1 :]
        clean = SyncTodoTables.TEXT_PREFIX.sub(repl="", string=clean)
        tasks.append(
            {
                "done": checkbox[1].lower() == "x",
                "id": ident,
                "prefix": (
                    re_compile(pattern=r"\d+$")
                    .sub(repl="", string=ident)
                    .rstrip("-")
                    if ident
                    else ""
                ),
                "priority": task_priority(label=label),
                "category": SyncTodoTables.CATEGORY_LABELS[category],
                "workstream": section,
                "wpath": [h[0] for d, h in sorted(headings.items()) if d > 1]
                or [section],
                "wlines": [h[1] for d, h in sorted(headings.items()) if d > 1]
                or [section_line],
                "section": section,
                "line": line_number,
                "ongoing": SyncTodoTables.ONGOING.search(string=label)
                is not None,
                "text": clean,
            },
        )
    web: Path = Path(__file__).parent / "web"
    template: str = (web / "dashboard.html").read_text(encoding="utf-8")
    data: str = dumps(obj={"tasks": tasks, "md": text})
    script: str = (web / "dashboard.js").read_text(encoding="utf-8")
    stylesheet: str = (web / "dashboard.css").read_text(encoding="utf-8")
    return (
        template.replace(
            "__DASHBOARD_STYLE__",
            "data:text/css;base64,"
            + b64encode(s=stylesheet.encode()).decode(),
        )
        .replace(
            "__DASHBOARD_SCRIPT__",
            "data:text/javascript;base64,"
            + b64encode(s=script.encode()).decode(),
        )
        .replace("__TASK_DATA__", data.replace("</", "<\\/"))
    )


def completion(text: str) -> float:
    """Return overall checkbox completion for one document.

    Args:
        text: TODO.md content to measure.

    Returns:
        Completion percentage, or ``0.0`` when nothing is tracked.

    """
    sections, _priorities = parse(text=text)
    done: int = sum(section.done for section in sections)
    total: int = sum(section.total for section in sections)
    return 100.0 * done / total if total else 0.0


def atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` atomically via a sibling temp file.

    A torn or overlapping write previously left NUL-padded gaps inside
    TODO.md. Writing the full payload to a sibling temporary file and
    renaming it over the destination makes each update all-or-nothing.

    Args:
        path: Destination file path.
        text: Complete replacement content.

    """
    temp: Path = path.with_name(
        name=f".{path.name}.{getpid()}.{time_ns()}.tmp",
    )
    created: bool = False
    try:
        with temp.open(mode="x", encoding="utf-8") as sink:
            created = True
            # Preserve existing permissions; new generated files stay private.
            temp.chmod(mode=path.stat().st_mode if path.exists() else 0o600)
            _ = sink.write(text)
        _ = temp.replace(target=path)
    finally:
        if created:
            temp.unlink(missing_ok=True)


def update(text: str) -> str:
    """Insert or replace the managed dashboard idempotently.

    Args:
        text: TODO.md content to update.

    Returns:
        Content carrying a current managed dashboard block.

    Raises:
        ValueError: Optional summary markers are incomplete or reversed.

    """
    defaults: type[SyncTodoDefaults] = SyncTodoDefaults
    if (
        defaults.start not in text
        and defaults.end not in text
        and not any(
            SyncTodoTables.CHECKBOX.match(string=line)
            for line in visible_lines(text=text)
        )
    ):
        return text
    block: str = _render(text=text)
    if defaults.summary_start in text or defaults.summary_end in text:
        if (
            text.count(defaults.summary_start) != 1
            or text.count(defaults.summary_end) != 1
        ):
            msg: str = "Expected one complete progress summary block"
            raise ValueError(msg)
        start: int = text.index(defaults.summary_start)
        end: int = text.index(defaults.summary_end)
        if end < start:
            msg = "Progress summary markers are reversed"
            raise ValueError(msg)
        summary: str
        separator: str
        details: str
        summary, separator, details = block.partition("### Priority progress")
        summary = summary.removeprefix(defaults.start).strip()
        replacement: str = (
            f"{defaults.summary_start}\n\n{summary}\n\n{defaults.summary_end}"
        )
        text = (
            text[:start]
            + replacement
            + text[end + len(defaults.summary_end) :]
        )
        block = f"{defaults.start}\n\n{separator}{details}"
    if (bounds := _dashboard_bounds(text=text)) is not None:
        return text[: bounds[0]] + block + text[bounds[1] :]
    insertion: int = (
        text.find("\n") + 1 if text.startswith("# ") and "\n" in text else 0
    )
    return text[:insertion] + "\n" + block + "\n\n" + text[insertion:]
