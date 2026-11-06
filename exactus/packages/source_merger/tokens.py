# Copyright (c) 2026
"""Whitespace-insensitive token-level three-way merge fallback.

The structural merger rejects a user edit whenever the tool also touched
the surrounding text, even when the tool only changed layout. This module
compares significant tokens only, so a tool that re-spaced or re-wrapped
a region does not conflict with a user who changed one token in it.

The merge is deliberately conservative: it accepts only hunks that are
separated from every competing hunk by a guard distance of unchanged
significant tokens, and it refuses identical-position insertions made by
both sides. The tool output is the destination layout.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from subprocess import CompletedProcess
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from json import JSONDecodeError, dumps, loads
from os import environ, pathsep
from re import compile as compile_regex
from subprocess import SubprocessError, run
from sys import executable, stdin, stdout
from sys import path as module_path
from typing import Final, final


@final
class Constants:
    """Group module-level constants.

    Attributes:
        token: Grouped module constant.
        hex: Grouped module constant.
        max_tokens: Grouped module constant.
        timeout_seconds: Grouped module constant.
        guard_tokens: Grouped module constant.
        slide_limit: Grouped module constant.

    """

    token: Final = compile_regex(pattern="\\s+|\\w+|[^\\w\\s]")
    hex: Final = compile_regex(pattern="[0-9A-Fa-f]+")
    max_tokens: Final[int] = 60000
    timeout_seconds: Final[float] = 15.0
    guard_tokens: Final[int] = 3
    slide_limit: Final[int] = 8


@final
@dataclass(frozen=True, slots=True)
class _Piece:
    """One significant token with the whitespace that precedes it.

    Attributes:
        gap: Whitespace immediately before the token.
        text: The significant token.

    """

    gap: str
    text: str


@final
@dataclass(frozen=True, slots=True)
class _Layout:
    """Significant tokens plus the whitespace after the last token.

    Attributes:
        pieces: Significant tokens in source order.
        tail: Whitespace after the final token.

    """

    pieces: tuple[_Piece, ...]
    tail: str

    @property
    def texts(self) -> list[str]:
        """Return the bare significant tokens.

        Returns:
            Token strings without whitespace.

        """
        return [piece.text for piece in self.pieces]


@final
@dataclass(frozen=True, slots=True)
class _Hunk:
    """A replacement of original tokens ``start:stop`` by ``new``.

    Attributes:
        start: First replaced original token index.
        stop: One past the last replaced original token index.
        new: Replacement pieces taken from the editing side.

    """

    start: int
    stop: int
    new: tuple[_Piece, ...]


def _layout(*, source: str) -> _Layout | None:
    """Split source into significant tokens and surrounding whitespace.

    Args:
        source: Complete text.

    Returns:
        The layout, or ``None`` when the text is too large to compare.

    """
    pieces: list[_Piece] = []
    gap: str = ""
    for match in Constants.token.finditer(string=source):
        text: str = match.group()
        if text.isspace():
            gap = text
            continue
        pieces.append(_Piece(gap=gap, text=text))
        gap = ""
        if len(pieces) > Constants.max_tokens:
            return None
    return _Layout(pieces=tuple(pieces), tail=gap)


def _hunks(
    *,
    original: _Layout,
    changed: _Layout,
    fold: bool = False,
) -> list[_Hunk]:
    """Diff significant tokens into replacement hunks.

    Args:
        original: Common ancestor layout.
        changed: One fork's layout.
        fold: Compare ignoring letter case, so a tool that only
            normalizes case (hex colors, keywords) yields no hunk.

    Returns:
        Non-equal opcodes expressed against original token indexes.

    """
    left: list[str] = original.texts
    right: list[str] = changed.texts
    matcher: SequenceMatcher[str] = SequenceMatcher(
        isjunk=None,
        a=[text.casefold() for text in left] if fold else left,
        b=[text.casefold() for text in right] if fold else right,
        autojunk=False,
    )
    return [
        _slid(
            original=original,
            changed=changed,
            hunk=_Hunk(start=i1, stop=i2, new=changed.pieces[j1:j2]),
            origin=j1,
        )
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    ]


def _slid(
    *,
    original: _Layout,
    changed: _Layout,
    hunk: _Hunk,
    origin: int,
) -> _Hunk:
    """Slide a pure insertion to a whole-line boundary when possible.

    Inserting a run before a token that repeats the run's last token is
    the same edit as inserting the rotated run one position earlier, so
    a diff may anchor an inserted line one token off. Whole-line
    boundaries are the stable, reviewable reading of such an edit.

    Args:
        original: Common ancestor layout.
        changed: The fork containing the insertion.
        hunk: Candidate hunk; only pure insertions are moved.
        origin: Index in ``changed`` where the inserted run starts.

    Returns:
        The hunk shifted to a line boundary, or unchanged.

    """
    if hunk.start != hunk.stop or not hunk.new:
        return hunk
    size: int = len(hunk.new)
    texts: list[str] = changed.texts
    for distance in range(Constants.slide_limit + 1):
        for shift in (distance, -distance):
            head: int = origin + shift
            tail: int = head + size
            if head < 0 or tail > len(texts):
                continue
            if not _equivalent(
                texts=texts,
                origin=origin,
                head=head,
                size=size,
            ):
                continue
            starts_line: bool = (
                """\

"""
                in changed.pieces[head].gap
            )
            ends_line: bool = (
                tail == len(texts)
                or """\

"""
                in changed.pieces[tail].gap
            )
            position: int = hunk.start + shift
            if (
                starts_line
                and ends_line
                and (0 <= position <= len(original.pieces))
            ):
                return _Hunk(
                    start=position,
                    stop=position,
                    new=changed.pieces[head:tail],
                )
    return hunk


def _equivalent(
    *,
    texts: list[str],
    origin: int,
    head: int,
    size: int,
) -> bool:
    """Report whether two run placements produce identical token streams.

    Args:
        texts: Token texts of the changed fork.
        origin: Original placement of the inserted run.
        head: Candidate placement.
        size: Run length.

    Returns:
        ``True`` when every token between the two placements repeats.

    """
    low, high = sorted((origin, head))
    return all(
        texts[index] == texts[index + size] for index in range(low, high)
    )


def _line_insertion(*, hunk: _Hunk) -> bool:
    """Report whether a hunk inserts text starting on its own line.

    Args:
        hunk: Candidate hunk.

    Returns:
        ``True`` for a pure insertion whose first token begins a line.

    """
    return (
        hunk.start == hunk.stop
        and bool(hunk.new)
        and (
            """\

"""
            in hunk.new[0].gap
        )
    )


def _conflicts(*, base: _Layout, left: _Hunk, right: _Hunk) -> bool:
    """Report whether two hunks are too close to merge safely.

    A line-start insertion only conflicts with a hunk that rewrites the
    region it lands inside, or that inserts at the same position.
    Otherwise hunks conflict when they overlap, touch, or sit closer
    than the guard distance; a line break between them relaxes the guard
    when at least one unchanged token separates them.

    Args:
        base: Common ancestor layout, used to find line breaks.
        left: Hunk from one fork.
        right: Hunk from the other fork.

    Returns:
        ``True`` when they overlap or are too close to combine.

    """
    for point, other in ((left, right), (right, left)):
        if _line_insertion(hunk=point):
            if other.start == other.stop:
                return other.start == point.start
            return other.start < point.start < other.stop
    first, second = (
        (left, right) if left.start <= right.start else (right, left)
    )
    if (
        first.stop > second.start
        or first.start == first.stop == second.start == second.stop
    ):
        return True
    stable: int = second.start - first.stop
    if stable >= Constants.guard_tokens:
        return False
    if stable < 1:
        return True
    window: range = range(first.stop, min(second.start + 1, len(base.pieces)))
    return not any(
        """\

"""
        in base.pieces[index].gap
        for index in window
    )


def _positions(*, original: _Layout, tool: _Layout) -> dict[int, int]:
    """Map original token boundaries to tool token boundaries.

    Unchanged tokens map to their tool index. The start of a region the
    tool rewrote maps to the start of its replacement, so an insertion
    that touches the region lands before it.

    Args:
        original: Common ancestor layout.
        tool: Tool-refactored layout.

    Returns:
        Original-to-tool index map.

    """
    matcher: SequenceMatcher[str] = SequenceMatcher(
        isjunk=None,
        a=[text.casefold() for text in original.texts],
        b=[text.casefold() for text in tool.texts],
        autojunk=False,
    )
    mapping: dict[int, int] = {}
    for tag, i1, i2, j1, _ in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                mapping[i1 + offset] = j1 + offset
        else:
            mapping.setdefault(i1, j1)
    mapping[len(original.pieces)] = len(tool.pieces)
    return mapping


def _line_start(*, pieces: list[_Piece], index: int) -> int:
    """Move a position back to the start of its destination line.

    Args:
        pieces: Destination tokens.
        index: Candidate insertion index.

    Returns:
        Index of the first token on the same line.

    """
    position: int = index
    while (
        0 < position < len(pieces)
        and """\

"""
        not in pieces[position].gap
    ):
        position -= 1
    return position


def _recased(
    *,
    new: tuple[_Piece, ...],
    old: _Piece,
    tool: _Piece,
) -> tuple[_Piece, ...]:
    """Carry a tool's hex-digit case normalization onto user tokens.

    Args:
        new: The user's replacement tokens.
        old: The ancestor token being replaced.
        tool: The tool's version of that token.

    Returns:
        Replacement tokens, lower- or upper-cased when the tool only
        changed the case of a hex-digit token.

    """
    if old.text == tool.text or old.text.casefold() != tool.text.casefold():
        return new
    convert: Callable[[str], str] = (
        str.lower if tool.text == tool.text.lower() else str.upper
    )
    return tuple(
        replace(piece, text=convert(piece.text))
        if Constants.hex.fullmatch(string=piece.text)
        else piece
        for piece in new
    )


def _render(*, pieces: list[_Piece], tail: str) -> str:
    """Join pieces and the trailing whitespace into text.

    Args:
        pieces: Output tokens with their preceding whitespace.
        tail: Whitespace after the last token.

    Returns:
        The merged text.

    """
    return "".join(piece.gap + piece.text for piece in pieces) + tail


def merge_tokens(
    *,
    original: str,
    user_edited: str,
    tool_refactored: str,
) -> str | None:
    """Merge disjoint user token edits into the tool's layout.

    Args:
        original: Common ancestor text.
        user_edited: The user's fork.
        tool_refactored: The tool's fork, used as destination layout.

    Returns:
        Merged text, or ``None`` when hunks conflict, are adjacent, or
        the inputs are too large to compare.

    """
    base: _Layout | None = _layout(source=original)
    user: _Layout | None = _layout(source=user_edited)
    tool: _Layout | None = _layout(source=tool_refactored)
    if base is None or user is None or tool is None:
        return None
    user_hunks: list[_Hunk] = _hunks(original=base, changed=user)
    tool_hunks: list[_Hunk] = _hunks(original=base, changed=tool, fold=True)
    for mine in user_hunks:
        for theirs in tool_hunks:
            if _conflicts(base=base, left=mine, right=theirs):
                return None
    mapping: dict[int, int] = _positions(original=base, tool=tool)
    output: list[_Piece] = list(tool.pieces)
    for hunk in sorted(user_hunks, key=lambda item: item.start, reverse=True):
        if not _apply(
            base=base,
            tool=tool,
            hunk=hunk,
            mapping=mapping,
            output=output,
        ):
            return None
    touches_end: bool = _appends(hunks=user_hunks, size=len(base.pieces))
    return _render(pieces=output, tail=user.tail if touches_end else tool.tail)


def _apply(
    *,
    base: _Layout,
    tool: _Layout,
    hunk: _Hunk,
    mapping: dict[int, int],
    output: list[_Piece],
) -> bool:
    """Project one user hunk onto the tool's token stream in place.

    Args:
        base: Common ancestor layout.
        tool: Tool-refactored layout.
        hunk: User hunk expressed against the ancestor.
        mapping: Ancestor-to-tool token boundary map.
        output: Destination tokens, edited in place.

    Returns:
        ``False`` when the hunk's region has no counterpart in the tool
        output; ``True`` once the hunk is applied.

    """
    start: int | None = mapping.get(hunk.start)
    if start is None:
        return False
    if hunk.start == hunk.stop:
        if _line_insertion(hunk=hunk):
            start = _line_start(pieces=output, index=start)
        output[start:start] = list(hunk.new)
        return True
    last: int | None = mapping.get(hunk.stop - 1)
    if last is None:
        return False
    replaced: tuple[_Piece, ...] = hunk.new
    if hunk.stop - hunk.start == 1 and len(hunk.new) == 1:
        replaced = _recased(
            new=hunk.new,
            old=base.pieces[hunk.start],
            tool=tool.pieces[start],
        )
    fresh: list[_Piece] = list(replaced)
    if fresh:
        fresh[0] = replace(fresh[0], gap=output[start].gap)
    output[start : last + 1] = fresh
    return True


def _appends(*, hunks: list[_Hunk], size: int) -> bool:
    """Report whether any hunk reaches the end of the original text.

    Args:
        hunks: User hunks against the original.
        size: Original significant token count.

    Returns:
        ``True`` when the user changed the end of the file.

    """
    return any(hunk.stop >= size for hunk in hunks)


def merge_tokens_bounded(
    *,
    original: str,
    user_edited: str,
    tool_refactored: str,
    timeout: float | None = None,
) -> str | None:
    """Run :func:`merge_tokens` in a child process with a hard deadline.

    The sequence diff is quadratic on repetitive input and cannot be
    interrupted in-process, so the work is delegated to a short-lived
    child that is killed when the deadline passes. A pathological input
    therefore costs at most ``timeout`` seconds and degrades to the
    caller's conservative path.

    Args:
        original: Common ancestor text.
        user_edited: The user's fork.
        tool_refactored: The tool's fork, used as destination layout.
        timeout: Seconds allowed; ``Constants.timeout_seconds`` when
            omitted.

    Returns:
        Merged text, or ``None`` on conflict, timeout or child failure.

    """
    limit: float = Constants.timeout_seconds if timeout is None else timeout
    child_environment: dict[str, str] = dict(environ)
    child_environment["PYTHONPATH"] = pathsep.join(
        entry for entry in module_path if entry
    )
    try:
        completed: CompletedProcess[str] = run(
            args=[executable, "-m", "exactus.packages.source_merger.tokens"],
            input=dumps(
                obj={
                    "original": original,
                    "user": user_edited,
                    "tool": tool_refactored,
                },
            ),
            capture_output=True,
            text=True,
            timeout=limit,
            check=False,
            env=child_environment,
        )
    except (OSError, SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    try:
        outcome: dict[str, str] = loads(
            s=completed.stdout,
        )
    except JSONDecodeError:
        return None
    merged: str | None = outcome.get("merged")
    return merged if isinstance(merged, str) else None


def main() -> int:
    """Merge the JSON request on standard input and print the outcome.

    Returns:
        Process exit status; ``0`` whenever a decision was printed.

    """
    request: dict[str, str] = loads(s=stdin.read())
    merged: str | None = merge_tokens(
        original=request["original"],
        user_edited=request["user"],
        tool_refactored=request["tool"],
    )
    _ = stdout.write(dumps(obj={"merged": merged}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
