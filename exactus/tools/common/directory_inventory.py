# Copyright (c) 2026
"""Maintain a managed, bottom-up directory inventory in README documents."""

from __future__ import annotations

from ast import get_docstring, parse
from contextlib import suppress
from re import DOTALL, search, sub
from re import compile as compile_pattern
from typing import TYPE_CHECKING, Final, final
from urllib.parse import quote

if TYPE_CHECKING:
    from pathlib import Path
    from re import Match, Pattern


@final
class Constants:
    """Group module-level constants.

    Attributes:
        start: Grouped module constant.
        end: Grouped module constant.
        max_text_bytes: Grouped module constant.
        inventory_blocks: Grouped module constant.

    """

    start: Final[str] = "<!-- exactus:inventory:start -->"
    end: Final[str] = "<!-- exactus:inventory:end -->"
    max_text_bytes: Final[int] = 1 << 20
    inventory_blocks: Final[Pattern[str]] = compile_pattern(
        pattern=(
            "<!-- (?P<owner>exactus|audit):inventory:"
            "start -->.*?<!-- (?P=owner):inventory:end -->"
        ),
        flags=DOTALL,
    )


def description(*, path: Path) -> str:
    """Summarize a file's docstring or a child directory's README introduction.

    Args:
        path: File or child directory to describe.

    Returns:
        A single-line description suitable for a directory inventory.

    """
    candidate: Path = path / "README.md" if path.is_dir() else path
    text: str = ""
    try:
        if candidate.stat().st_size <= Constants.max_text_bytes:
            text = candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        pass
    summary: str = ""
    if candidate.suffix == ".py":
        with suppress(SyntaxError):
            summary = get_docstring(node=parse(source=text)) or ""
    elif candidate.suffix in (".js", ".mjs", ".cjs", ".css"):
        match: Match[str] | None = search(
            pattern="/\\*\\*(.*?)\\*/",
            string=text,
            flags=16,
        )
        if match:
            summary = sub(
                pattern="(?m)^\\s*\\* ?",
                repl="",
                string=match.group(1),
            ).strip()
            summary = summary.split(sep="@", maxsplit=1)[0].strip()
    elif candidate.suffix == ".md":
        paragraphs: list[str] = text.split(sep="\n\n")
        for paragraph in paragraphs:
            stripped: str = paragraph.strip()
            if stripped and (
                not stripped.startswith(("#", "<!--", "-", "|", "```"))
            ):
                summary = stripped
                break
    summary = " ".join(summary.split(sep="\n\n", maxsplit=1)[0].split())
    if not summary:
        label: str = path.stem.replace("_", " ").replace("-", " ")
        suffix: str = path.suffix.lstrip(".") or "project"
        summary = (
            f"Contain {label} resources and their directory inventory."
            if path.is_dir()
            else f"Provide {label} {suffix} content."
        )
    return summary.replace("[", "\\[").replace("]", "\\]")


def entry_line(*, entry: Path) -> str:
    """Render one relative link and description in the standard list format.

    Args:
        entry: Direct file or subdirectory.

    Returns:
        A Markdown inventory list item.

    """
    suffix: str = "/" if entry.is_dir() else ""
    destination: str = quote(string=entry.name, safe="") + (
        "/README.md" if suffix else ""
    )
    summary: str = description(path=entry)
    return f"- [`{entry.name}{suffix}`]({destination}) — {summary}"


def heal_directory(*, directory: Path, entries: list[Path]) -> None:
    """Consolidate generated inventories while preserving authored prose.

    Args:
        directory: Directory whose children have already been healed.
        entries: Eligible direct files and folders to document.

    """
    if ".history" in directory.parts:
        return
    entries = [entry for entry in entries if entry.name != ".history"]
    readme: Path = directory / "README.md"
    body: str = (
        readme.read_text(encoding="utf-8")
        if readme.is_file()
        else f"# `{directory.name or 'Project'}/`\n\n"
    )
    if not readme.is_file():
        candidates: list[Path] = sorted(
            entries,
            key=lambda entry: (
                entry.name != "__init__.py",
                entry.is_dir(),
                entry.name,
            ),
        )
        if candidates:
            body += description(path=candidates[0]) + "\n\n"
    lines: list[str] = [
        Constants.start,
        "## Directory contents",
        "",
        "### Files",
        "",
    ]
    files: list[Path] = [
        entry
        for entry in entries
        if not entry.is_dir() and entry.name != "README.md"
    ]
    folders: list[Path] = [entry for entry in entries if entry.is_dir()]
    lines.extend(entry_line(entry=entry) for entry in files)
    if not files:
        lines.append("No direct files besides this README.")
    lines.extend(("", "### Subdirectories", ""))
    lines.extend(entry_line(entry=entry) for entry in folders)
    if not folders:
        lines.append("No subdirectories.")
    lines.extend(("", Constants.end))
    block: str = "\n".join(lines)
    match: Match[str] | None = Constants.inventory_blocks.search(string=body)
    if match is not None:
        before: str = body[: match.start()]
        after: str = Constants.inventory_blocks.sub(
            repl="",
            string=body[match.end() :],
        )
        updated: str = before + block + after
    else:
        updated = body.rstrip() + "\n\n" + block + "\n"
    if updated != body:
        _ = readme.write_text(data=updated, encoding="utf-8")
