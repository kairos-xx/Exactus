"""Precise source-span operations with overlap and indentation safeguards."""

from __future__ import annotations

from exactus.packages.source_merger.model import Replacement, Statement


def apply(*, source: str, replacements: tuple[Replacement, ...]) -> str:
    """Apply non-overlapping replacements to an immutable source snapshot.

    Args:
        source: Text whose offsets were used to construct the replacements.
        replacements: Insertions and modifications in original coordinates.

    Returns:
        Transformed source text.

    Raises:
        ValueError: Out-of-range or overlapping transformations.

    """
    ordered: list[Replacement] = sorted(
        replacements,
        key=lambda item: (item.start, item.end),
        reverse=True,
    )
    previous: int = len(source)
    pieces: list[str] = []
    for item in ordered:
        if (
            item.start < 0
            or item.end > len(source)
            or item.end > previous
            or item.start > item.end
        ):
            msg: str = f"Overlapping or invalid source patch at {item.scope}"
            raise ValueError(msg)
        pieces.extend((source[item.end : previous], item.text))
        previous = item.start
    pieces.append(source[:previous])
    return "".join(reversed(pieces))


def indent_at(*, source: str, position: int) -> str:
    """Find the indentation prefix of the line containing an offset.

    Args:
        source: Complete source text.
        position: Offset into the text.

    Returns:
        Whitespace prefix at the supplied line.

    """
    line_start: int = (
        source.rfind(
            """\

""",
            0,
            position,
        )
        + 1
    )
    line: str = source[line_start:position]
    return line[: len(line) - len(line.lstrip())]


def reindent(*, text: str, target: str, origin: str = "") -> str:
    """Move a statement's indentation to a new lexical owner.

    Args:
        text: Complete snippet, starting at its first nonspace token.
        target: Indentation expected at the target insertion position.
        origin: Indentation originally preceding the first source token.

    Returns:
        Snippet with continuation indentation preserved relatively.

    """
    lines: list[str] = text.splitlines(keepends=True)
    if not lines:
        return text
    continuation: list[str] = []
    min_indent: int = len(origin)
    continuation.extend(
        target + line[min_indent:] if line.strip() else line
        for line in lines[1:]
    )
    return lines[0] + "".join(continuation)


def insertion(
    *,
    source: str,
    anchor: Statement,
    before: bool,
    snippet: str,
    origin: str = "",
) -> Replacement:
    """Construct a whole-line insertion adjacent to a tracked statement.

    Args:
        source: Refactored source.
        anchor: Statement that survived refactoring.
        before: Insert before rather than after the anchor.
        snippet: New source without leading indentation on its first line.
        origin: Previous indentation before the snippet's first token.

    Returns:
        Safe source patch attached to the tracked statement.

    """
    indentation: str = indent_at(source=source, position=anchor.start)
    contents: str = reindent(
        text=snippet,
        target=indentation,
        origin=origin,
    ).rstrip("""\

""")
    if before:
        position: int = (
            source.rfind(
                """\

""",
                0,
                anchor.start,
            )
            + 1
        )
        return Replacement(
            start=position,
            end=position,
            text=indentation
            + contents
            + """\

""",
            scope="insert before",
        )
    line_end: int = source.find(
        """\

""",
        anchor.end,
    )
    position = len(source) if line_end < 0 else line_end + 1
    if line_end < 0:
        return Replacement(
            start=position,
            end=position,
            text="""\

"""
            + indentation
            + contents,
            scope="insert after",
        )
    return Replacement(
        start=position,
        end=position,
        text=indentation
        + contents
        + """\

""",
        scope="insert after",
    )
