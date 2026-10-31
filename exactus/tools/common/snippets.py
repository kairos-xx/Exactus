# Copyright (c) 2026
"""Capture numbered source excerpts around report findings.

A finding that names a project file and a line gets an ``excerpt``: the
target line plus up to ``context`` lines on each side, clipped to the
file. Reading is bounded (bytes scanned, bytes per line, characters per
line, context depth), binary files are skipped, and a path whose real
location falls outside the project root (``..``, absolute paths, escaping
symlinks) is refused, so no excerpt ever shows text from outside it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Self

if TYPE_CHECKING:
    from io import BufferedReader

    from exactus.tools.common.json_types import JsonValue


class SnippetLimits:
    """Bounds and lookup tables of the excerpt reader.

    Attributes:
        default_context: Context lines when nothing configures them.
        max_context: Deepest context captured on each side of a line.
        max_scan_bytes: Bytes read before giving up on reaching a line.
        max_line_bytes: Bytes read from one line before it is clipped.
        max_line_chars: Characters kept from one line.
        sniff_bytes: Leading bytes searched for NUL to detect binaries.
        ellipsis: Suffix of a clipped line.
        languages: Fenced-code language keyed by lower-case suffix.
        names: Fenced-code language keyed by exact file name.
        fallback: Language of files no table names.

    """

    default_context: Final[int] = 3
    max_context: Final[int] = 50
    max_scan_bytes: Final[int] = 16 * 1024 * 1024
    max_line_bytes: Final[int] = 4096
    max_line_chars: Final[int] = 400
    sniff_bytes: Final[int] = 8192
    ellipsis: Final[str] = " …"
    languages: Final[dict[str, str]] = {
        ".py": "python",
        ".pyi": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".json": "json",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".sh": "shell",
        ".bash": "shell",
        ".zsh": "shell",
        ".css": "css",
        ".html": "html",
        ".htm": "html",
        ".ini": "ini",
        ".cfg": "ini",
    }
    names: Final[dict[str, str]] = {
        "Dockerfile": "dockerfile",
        "Makefile": "makefile",
    }
    fallback: Final[str] = "text"


@dataclass(frozen=True, slots=True)
class ExcerptLine:
    """One numbered source line of an excerpt.

    Attributes:
        n: One-based line number in the file.
        text: Line text without its line ending, possibly clipped.
        target: Whether this is the line the finding points at.

    """

    n: int
    text: str
    target: bool

    def payload(self: Self) -> dict[str, JsonValue]:
        """Return the JSON form of this line.

        Returns:
            ``n``, ``text`` and ``target``.

        """
        return {"n": self.n, "text": self.text, "target": self.target}


@dataclass(frozen=True, slots=True)
class Excerpt:
    """Numbered lines around one finding line.

    Attributes:
        line: Target line number.
        context: Context lines requested on each side.
        language: Fenced-code language derived from the file name.
        lines: Captured lines in file order, clipped to the file.
        clipped: Whether any captured line was cut short.

    """

    line: int
    context: int
    language: str
    lines: tuple[ExcerptLine, ...]
    clipped: bool

    def payload(self: Self) -> dict[str, JsonValue]:
        """Return the JSON form stored on a finding.

        Returns:
            ``language``, ``line``, ``context``, ``start``, ``end``,
            ``clipped`` and the ``lines`` list.

        """
        return {
            "language": self.language,
            "line": self.line,
            "context": self.context,
            "start": self.lines[0].n,
            "end": self.lines[-1].n,
            "clipped": self.clipped,
            "lines": [row.payload() for row in self.lines],
        }


class SnippetSource:
    """Locate and read project files for excerpts."""

    @classmethod
    def read(
        cls,
        *,
        path: Path,
        first: int,
        last: int,
    ) -> list[tuple[int, str, bool]] | None:
        """Read the numbered lines ``first`` to ``last`` of a text file.

        Lines are split like Python's universal newlines (LF, CRLF and a
        lone CR).

        Args:
            path: Resolved regular file.
            first: First one-based line to keep.
            last: Last one-based line to keep.

        Returns:
            ``(number, text, clipped)`` rows (fewer near the end of the
            file), or ``None`` for binary or unreadable files and files
            whose wanted lines lie beyond the scan limit.

        """
        rows: list[tuple[int, str, bool]] = []
        number: int = 0
        scanned: int = 0
        handle: BufferedReader
        try:
            with path.open(mode="rb") as handle:
                if (
                    b"\0"
                    in handle.peek(SnippetLimits.sniff_bytes)[
                        : SnippetLimits.sniff_bytes
                    ]
                ):
                    return None
                while number < last:
                    line: tuple[bytes, int, int] | None = cls._line(
                        handle=handle,
                    )
                    if line is None:
                        break
                    raw: bytes
                    rest: int
                    consumed: int
                    raw, rest, consumed = line
                    number += 1
                    scanned += consumed
                    if scanned > SnippetLimits.max_scan_bytes:
                        return None
                    if number >= first:
                        text: str
                        clipped: bool
                        text, clipped = cls._decode(raw=raw, clipped=rest > 0)
                        rows.append((number, text, clipped))
        except OSError:
            return None
        return rows

    @staticmethod
    def language(*, path: Path) -> str:
        """Return the fenced-code language of a file.

        Args:
            path: File path; only its name is used.

        Returns:
            A language such as ``python``, or ``text``.

        """
        named: str | None = SnippetLimits.names.get(path.name)
        if named is not None:
            return named
        return SnippetLimits.languages.get(
            path.suffix.lower(),
            SnippetLimits.fallback,
        )

    @staticmethod
    def locate(*, root: Path, path: str | Path) -> Path | None:
        """Resolve a project path, refusing anything outside the root.

        Args:
            root: Project root.
            path: Path relative to the root.

        Returns:
            The resolved regular file, or ``None`` when it is missing,
            not a regular file, or resolves outside the root.

        """
        try:
            base: Path = root.resolve(strict=True)
            resolved: Path = (base / path).resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            return None
        if not resolved.is_relative_to(base) or not resolved.is_file():
            return None
        return resolved

    @staticmethod
    def _decode(*, raw: bytes, clipped: bool) -> tuple[str, bool]:
        """Decode one line and clip it to the character limit.

        Args:
            raw: Kept line bytes, line ending excluded.
            clipped: Whether bytes of the line were left unread.

        Returns:
            The text and whether it was clipped.

        """
        text: str = raw.decode(encoding="utf-8", errors="replace")
        if len(text) > SnippetLimits.max_line_chars:
            text = text[: SnippetLimits.max_line_chars]
            clipped = True
        shown: str = f"{text}{SnippetLimits.ellipsis}" if clipped else text
        return (shown, clipped)

    @staticmethod
    def _line(*, handle: BufferedReader) -> tuple[bytes, int, int] | None:
        """Read one line the way Python's universal newlines split them.

        CRLF, a lone CR and LF each end a line, so the numbering matches
        what compilers and linters report and no raw carriage return
        reaches the excerpt text. At most ``SnippetLimits.max_line_bytes``
        bytes of the line are kept; the rest is skipped, and a line
        running past ``SnippetLimits.max_scan_bytes`` stops early.

        Args:
            handle: File positioned at the start of a line.

        Returns:
            ``(kept, skipped, consumed)``: the kept line bytes without
            the ending, how many line bytes were skipped and how many
            bytes were consumed in total; ``None`` at the end of the file.

        """
        kept: bytearray = bytearray()
        skipped: int = 0
        consumed: int = 0
        while consumed <= SnippetLimits.max_scan_bytes:
            chunk: bytes = handle.peek(1)
            if not chunk:
                return (bytes(kept), skipped, consumed) if consumed else None
            cut: int = min(
                (
                    index
                    for index in (chunk.find(b"\r"), chunk.find(b"\n"))
                    if index >= 0
                ),
                default=-1,
            )
            part: bytes = chunk if cut < 0 else chunk[:cut]
            room: int = max(0, SnippetLimits.max_line_bytes - len(kept))
            kept.extend(part[:room])
            skipped += max(0, len(part) - room)
            consumed += len(part)
            if cut < 0:
                _ = handle.read(len(part))
                continue
            ending: bytes = handle.read(cut + 1)[cut:]
            consumed += 1
            if ending == b"\r" and handle.peek(1)[:1] == b"\n":
                _ = handle.read(1)
                consumed += 1
            break
        return (bytes(kept), skipped, consumed)


def excerpt(
    *,
    root: Path,
    path: str | Path,
    line: int,
    context: int,
) -> Excerpt | None:
    """Capture the numbered lines around one line of a project file.

    Args:
        root: Project root; nothing outside it is read.
        path: File path relative to ``root``.
        line: One-based target line.
        context: Lines wanted on each side; negative counts as ``0`` and
            the depth is capped at ``SnippetLimits.max_context``.

    Returns:
        The excerpt, or ``None`` when the line is not positive, the file
        is missing, binary, unreadable, outside the root, or shorter than
        ``line``.

    """
    if line < 1:
        return None
    requested: int = max(0, context)
    span: int = min(requested, SnippetLimits.max_context)
    source: Path | None = SnippetSource.locate(root=root, path=path)
    if source is None:
        return None
    rows: list[tuple[int, str, bool]] | None = SnippetSource.read(
        path=source,
        first=max(1, line - span),
        last=line + span,
    )
    if rows is None or all(number != line for number, _, _ in rows):
        return None
    return Excerpt(
        line=line,
        context=requested,
        language=SnippetSource.language(path=Path(path)),
        lines=tuple(
            ExcerptLine(n=number, text=text, target=number == line)
            for number, text, _ in rows
        ),
        clipped=any(clipped for _, _, clipped in rows),
    )


def finding_excerpt(
    *,
    finding: JsonValue,
    root: Path,
    context: int,
) -> JsonValue:
    """Return a finding with its ``excerpt`` added when one is available.

    Args:
        finding: One normalized finding.
        root: Project root.
        context: Context lines on each side.

    Returns:
        The finding, with ``excerpt`` when it has a string ``path`` and a
        positive integer ``line`` whose file can be read; otherwise the
        finding unchanged.

    """
    if not isinstance(finding, dict):
        return finding
    path: JsonValue = finding.get("path")
    line: JsonValue = finding.get("line")
    if (
        not isinstance(path, str)
        or not path
        or isinstance(line, bool)
        or not isinstance(line, int)
    ):
        return finding
    captured: Excerpt | None = excerpt(
        root=root,
        path=path,
        line=line,
        context=context,
    )
    if captured is None:
        return finding
    return {**finding, "excerpt": captured.payload()}


def with_excerpts(
    *,
    payload: dict[str, JsonValue],
    root: Path,
    context: int,
) -> dict[str, JsonValue]:
    """Add excerpts to every finding of a normalized report payload.

    Args:
        payload: Report data holding a ``findings`` list.
        root: Project root the finding paths are relative to.
        context: Context lines on each side.

    Returns:
        A copy of ``payload`` whose findings carry excerpts; the payload
        itself when it has no findings list.

    """
    findings: JsonValue = payload.get("findings")
    if not isinstance(findings, list):
        return payload
    return {
        **payload,
        "project_root": str(object=root.resolve()),
        "findings": [
            finding_excerpt(finding=finding, root=root, context=context)
            for finding in findings
        ],
    }
