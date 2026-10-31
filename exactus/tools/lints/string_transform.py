# Copyright (c) 2026
"""Source-preserving string dedenting, splitting and f-string formatting."""

from __future__ import annotations

from ast import (
    AST,
    Add,
    Assign,
    AsyncFunctionDef,
    BinOp,
    Call,
    ClassDef,
    Constant,
    Expr,
    FormattedValue,
    FunctionDef,
    ImportFrom,
    JoinedStr,
    Module,
    dump,
    expr,
    parse,
    stmt,
    unparse,
    walk,
)
from dataclasses import dataclass, replace
from io import BytesIO, StringIO
from os import fsync
from pathlib import Path
from re import Match, search
from shutil import which
from subprocess import CompletedProcess, run
from tempfile import NamedTemporaryFile, TemporaryDirectory
from textwrap import dedent
from tokenize import (
    COMMENT,
    FSTRING_START,
    OP,
    STRING,
    TokenError,
    TokenInfo,
    detect_encoding,
    generate_tokens,
)
from typing import TYPE_CHECKING, Final, Literal, final

if TYPE_CHECKING:
    from collections.abc import Sequence


@final
class Constants:
    """Group module-level constants.

    Attributes:
        implicit_strings: Grouped module constant.
        min_split_parts: Grouped module constant.
        min_line_width: Grouped module constant.
        max_line_width: Grouped module constant.
        min_fragment_width: Grouped module constant.
        strategies: Grouped module constant.

    """

    implicit_strings: Final[int] = 2
    min_split_parts: Final[int] = 2
    min_line_width: Final[int] = 20
    max_line_width: Final[int] = 320
    min_fragment_width: Final[int] = 4
    strategies: Final[tuple[str, ...]] = ("preserve", "split", "smart")


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """Transformed source, syntax tree, number of replacements, and status.

    Attributes:
        source: Transformed source text.
        tree: Parsed syntax tree of the transformed source.
        count: Number of literal replacements applied.
        changed: Whether any replacement was applied.

    """

    source: str
    tree: Module
    count: int
    changed: bool


@dataclass(frozen=True, slots=True)
class CallFormatOptions:
    """Options controlling call expansion inside f-string expressions.

    Attributes:
        enabled: Expand calls inside f-string expressions.
        minimum_arguments: Minimum arguments for an expanded call.
        ruff_executable: Ruff binary; auto-discovered when ``None``.
        line_length: Formatter line width.

    """

    enabled: bool = True
    minimum_arguments: int = 3
    ruff_executable: str | None = None
    line_length: int = 88


type MultilineStrategy = Literal["preserve", "split", "smart"]


@dataclass(frozen=True, slots=True)
class SplitOptions:
    """Width discovery and policy settings for literal splitting.

    Attributes:
        max_line_size: Legacy explicit width; ``None`` discovers Ruff
            settings.
        line_length: Preferred explicit width; overrides ``max_line_size``.
        ruff_executable: Ruff binary used for effective settings resolution.
        ruff_args: Additional Ruff check arguments such as ``--config``.
        multiline_strategy: Preserve, split, or smart triple-quote handling.
        split_fstrings: Whether to consider f-strings.
        split_raw_strings: Whether to consider raw literals.
        split_bytes: Whether to consider byte literals.
        preserve_docstrings: Protect docstring expressions.
        preserve_comments: Protect token spans containing comments.
        format_interpolations: Expand eligible oversized f-string calls.
        verify_semantics: Retained for compatibility; checks are mandatory.

    """

    max_line_size: int | None = None
    line_length: int | None = None
    ruff_executable: str | None = None
    ruff_args: tuple[str, ...] = ()
    multiline_strategy: MultilineStrategy = "smart"
    split_fstrings: bool = True
    split_raw_strings: bool = True
    split_bytes: bool = True
    preserve_docstrings: bool = True
    preserve_comments: bool = True
    format_interpolations: bool = False
    verify_semantics: bool = True


@dataclass(frozen=True, slots=True)
class TransformOptions(SplitOptions):
    """Split options plus call formatting for the combined transform.

    Attributes:
        format_interpolations: Expand eligible oversized f-string calls.
        call_format: Ruff-backed call formatting configuration.

    """

    format_interpolations: bool = True
    call_format: CallFormatOptions | None = None


def offsets(*, lines: list[str]) -> list[int]:
    """Return the cumulative character offset at each line start.

    Args:
        lines: Source lines, including line endings.

    Returns:
        Starting offset of every line plus the total length.

    """
    offsets: list[int] = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    return offsets


def position(*, offsets: list[int], point: tuple[int, int]) -> int:
    """Map a ``(row, column)`` token position to a character offset.

    Args:
        offsets: Line-start offsets.
        point: One-based row and zero-based column.

    Returns:
        Absolute character offset.

    """
    row, column = point
    return offsets[row - 1] + column


def _bounds(*, offsets: list[int], node: expr | stmt) -> tuple[int, int]:
    """Return the character offsets covered by an AST node.

    Args:
        offsets: Line-start offsets for the source.
        node: Positioned AST node.

    Returns:
        ``(start, end)`` character offsets.

    """
    return (
        position(offsets=offsets, point=(node.lineno, node.col_offset)),
        position(
            offsets=offsets,
            point=(
                node.end_lineno or node.lineno,
                node.end_col_offset or node.col_offset,
            ),
        ),
    )


def _docstring_spans(
    *,
    original: Module,
    offsets: list[int],
) -> set[tuple[int, int]]:
    """Find docstring spans that must not be rewritten.

    Args:
        original: Parsed source module.
        offsets: Line-start offsets for the source.

    Returns:
        ``(start, end)`` offsets of docstring expressions.

    """
    excluded: set[tuple[int, int]] = set()
    for parent in walk(node=original):
        if not (
            isinstance(
                parent,
                (Module, ClassDef, FunctionDef, AsyncFunctionDef),
            )
            and parent.body
        ):
            continue
        first: AST = parent.body[0]
        if isinstance(first, Expr) and isinstance(
            first.value,
            (Constant, JoinedStr),
        ):
            excluded.add(_bounds(offsets=offsets, node=first.value))
    return excluded


def flatten(node: expr) -> list[Constant | FormattedValue] | None:
    """Flatten literals and f-string expressions in evaluation order.

    Args:
        node: Candidate expression.

    Returns:
        Ordered literal parts, or ``None`` when the node mixes other
        expression kinds.

    """
    if isinstance(node, BinOp) and isinstance(node.op, Add):
        left: list[Constant | FormattedValue] | None = flatten(node=node.left)
        right: list[Constant | FormattedValue] | None = flatten(
            node=node.right,
        )
        return left + right if left is not None and right is not None else None
    if isinstance(node, Constant) and isinstance(node.value, str):
        return [node]
    if not isinstance(node, JoinedStr):
        return None
    values: list[Constant | FormattedValue] = []
    for value in node.values:
        if not isinstance(value, (Constant, FormattedValue)):
            return None
        values.append(value)
    return values


def signature(*, values: Sequence[expr]) -> tuple[str, list[str]]:
    """Separate literal text from interpolation syntax in a string body.

    Args:
        values: String body parts.

    Returns:
        Literal fragments with sentinel markers plus the dumped
        interpolation expressions.

    """
    fragments: list[str] = []
    expressions: list[str] = []
    for item in values:
        if isinstance(item, Constant) and isinstance(item.value, str):
            fragments.append(item.value)
        else:
            fragments.append(f"\x01{len(expressions)}\x02")
            expressions.append(dump(node=item, include_attributes=False))
    return ("".join(fragments), expressions)


def escape(
    *,
    parts: list[Constant | FormattedValue],
    is_fstring: bool,
    quote: str,
) -> list[str] | None:
    """Escape literal parts and unparse interpolations for one quote style.

    Args:
        parts: Flattened literal parts.
        is_fstring: Whether any part interpolates.
        quote: Triple-quote delimiter being tried.

    Returns:
        Rendered chunks, or ``None`` when a part cannot be a literal.

    """
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, Constant):
            if not isinstance(part.value, str):
                return None
            value: str = part.value
            if is_fstring:
                value = value.replace("{", "{{").replace("}", "}}")
            value = (
                value.replace("\\", "\\\\")
                .replace("\r", "\\r")
                .replace("\x00", "\\x00")
            )
            chunks.append(value.replace(quote, "\\" + quote))
        else:
            fragment: str = unparse(ast_obj=JoinedStr(values=[part]))
            chunks.append(fragment[2:-1])
    return chunks


def verified(
    *,
    candidate: str,
    parts: list[Constant | FormattedValue],
    is_fstring: bool,
) -> bool:
    """Check a rendered candidate reproduces the original literal.

    Args:
        candidate: Candidate triple-quoted, possibly interpolated string.
        parts: Flattened original parts.
        is_fstring: Whether the original interpolates.

    Returns:
        Whether parsing ``candidate`` preserves text and expressions.

    """
    try:
        expression: AST = parse(source=candidate, mode="eval").body
    except SyntaxError:
        return False
    if is_fstring:
        if not isinstance(expression, JoinedStr):
            return False
        original_text, original_expr = signature(values=parts)
        rendered_text, rendered_expr = signature(values=expression.values)
        if (
            original_expr != rendered_expr
            or dedent(text=rendered_text) != original_text
        ):
            return False
        probe: str = "\x01\n\x02"
        original_probe: str = original_text
        rendered_probe: str = rendered_text
        for index in range(len(original_expr)):
            sentinel: str = f"\x01{index}\x02"
            original_probe = original_probe.replace(sentinel, probe)
            rendered_probe = rendered_probe.replace(sentinel, probe)
        return dedent(text=rendered_probe) == original_probe
    joined: str = "".join(
        part.value
        for part in parts
        if isinstance(part, Constant) and isinstance(part.value, str)
    )
    return (
        isinstance(expression, Constant)
        and isinstance(expression.value, str)
        and (dedent(text=expression.value) == joined)
    )


def render(*, parts: list[Constant | FormattedValue]) -> str | None:
    """Render strings with verified interpolation and literal semantics.

    Args:
        parts: Flattened literal parts in evaluation order.

    Returns:
        ``dedent(text=...)`` call source, or ``None`` when no quote style
        round-trips the literal.

    """
    is_fstring: bool = any(isinstance(part, FormattedValue) for part in parts)
    for quote in ('"""', "'''"):
        chunks: list[str] | None = escape(
            parts=parts,
            is_fstring=is_fstring,
            quote=quote,
        )
        if chunks is None:
            return None
        content: str = "".join(chunks)
        lines: list[str] = content.split(sep="\n")
        body: str = "\n".join(
            f"    {line}" if line.strip() or index == len(lines) - 1 else ""
            for index, line in enumerate(iterable=lines)
        )
        if content.endswith("\n"):
            body = body.removesuffix("\n")
        candidate: str = (
            f"{('f' if is_fstring else '')}{quote}\\\n{body}{quote}"
        )
        if verified(candidate=candidate, parts=parts, is_fstring=is_fstring):
            return f"dedent(text={candidate})"
    return None


def implicit_tokens(
    *,
    tokens: list[TokenInfo],
    start: int,
    end: int,
    offsets: list[int],
) -> bool:
    """Return whether the span covers multiple adjacent string tokens.

    Args:
        tokens: Tokenized source.
        start: Span start offset.
        end: Span end offset.
        offsets: Line-start offsets.

    Returns:
        Whether at least two string tokens fit inside the span.

    """
    strings: list[TokenInfo] = [
        token
        for token in tokens
        if token.type in (STRING, FSTRING_START)
        and start <= position(offsets=offsets, point=token.start)
        and (position(offsets=offsets, point=token.end) <= end)
    ]
    return len(strings) >= Constants.implicit_strings


def _patches(
    *,
    original: Module,
    offsets: list[int],
    tokens: list[TokenInfo],
    excluded: set[tuple[int, int]],
) -> list[tuple[int, int, str]]:
    """Collect replacement patches for multi-line string expressions.

    Args:
        original: Parsed source module.
        offsets: Line-start offsets.
        tokens: Tokenized source.
        excluded: Docstring spans to skip.

    Returns:
        ``(start, end, replacement)`` patches.

    """
    patches: list[tuple[int, int, str]] = []
    for node in walk(node=original):
        if not isinstance(node, (BinOp, Constant, JoinedStr)):
            continue
        parts: list[Constant | FormattedValue] | None = flatten(node=node)
        if parts is None or not any(
            isinstance(part, Constant) and "\n" in str(object=part.value)
            for part in parts
        ):
            continue
        start, end = _bounds(offsets=offsets, node=node)
        if (start, end) in excluded:
            continue
        if isinstance(node, (Constant, JoinedStr)) and (
            not implicit_tokens(
                tokens=tokens,
                start=start,
                end=end,
                offsets=offsets,
            )
        ):
            continue
        replacement: str | None = render(parts=parts)
        if replacement is not None:
            patches.append((start, end, replacement))
    return patches


def select(
    *,
    patches: list[tuple[int, int, str]],
) -> list[tuple[int, int, str]]:
    """Keep non-overlapping patches, preferring outer spans first.

    Args:
        patches: Candidate replacements.

    Returns:
        Non-overlapping patches in source order.

    """
    selected: list[tuple[int, int, str]] = []
    for patch in sorted(patches, key=lambda item: (item[0], -item[1])):
        if not selected or patch[0] >= selected[-1][1]:
            selected.append(patch)
    return selected


def apply(*, source: str, selected: list[tuple[int, int, str]]) -> str:
    """Apply patches from last to first so offsets stay valid.

    Args:
        source: Original source.
        selected: Ordered non-overlapping patches.

    Returns:
        Patched source.

    """
    result: str = source
    for start, end, replacement in reversed(selected):
        result = result[:start] + replacement + result[end:]
    return result


def _textwrap_imports(*, updated: Module) -> list[ImportFrom]:
    """Return absolute ``textwrap`` imports in a parsed module.

    Args:
        updated: Parsed transformed module.

    Returns:
        Matching ``ImportFrom`` nodes.

    """
    return [
        node
        for node in updated.body
        if isinstance(node, ImportFrom)
        and node.module == "textwrap"
        and (node.level == 0)
    ]


def merge_dedent(
    *,
    result: str,
    compatible: ImportFrom,
    offsets: list[int],
) -> str:
    """Extend an existing textwrap import with ``dedent``.

    Args:
        result: Transformed source.
        compatible: Import without a star name.
        offsets: Line-start offsets for ``result``.

    Returns:
        Source with ``dedent`` importable.

    """
    start, end = _bounds(offsets=offsets, node=compatible)
    if all(name.asname is None for name in compatible.names):
        names: list[str] = sorted(
            {name.name for name in compatible.names} | {"dedent"},
        )
        return (
            result[:start]
            + "from textwrap import "
            + ", ".join(names)
            + result[end:]
        )
    return result[:start] + "from textwrap import dedent\n" + result[start:]


def insertion_offset(*, updated: Module, updated_lines: list[str]) -> int:
    """Return the offset after the docstring and future imports.

    Args:
        updated: Parsed transformed module.
        updated_lines: Transformed source lines.

    Returns:
        Character offset where a new import can be inserted.

    """
    insertion_line: int = 0
    if (
        updated.body
        and isinstance(updated.body[0], Expr)
        and isinstance(updated.body[0].value, Constant)
        and isinstance(updated.body[0].value.value, str)
    ):
        insertion_line = updated.body[0].end_lineno or insertion_line
    for statement in updated.body:
        if (
            isinstance(statement, ImportFrom)
            and statement.module == "__future__"
        ):
            insertion_line = max(
                insertion_line,
                statement.end_lineno or statement.lineno,
            )
    return sum(len(line) for line in updated_lines[:insertion_line])


def _header_end(*, original: Module, offsets_list: list[int]) -> int:
    """Return the offset after the module docstring and import header.

    Args:
        original: Parsed module whose positions describe the source.
        offsets_list: Line-start offsets for the same source.

    Returns:
        Offset after the docstring and top-level ``__future__``/``textwrap``
        imports; edits beyond it leave the header region intact.

    """
    boundary: int = 0
    if (
        original.body
        and isinstance(original.body[0], Expr)
        and isinstance(original.body[0].value, Constant)
        and isinstance(original.body[0].value.value, str)
    ):
        boundary = offsets_list[original.body[0].end_lineno or 1]
    for statement in original.body:
        if isinstance(statement, ImportFrom) and statement.module in (
            "__future__",
            "textwrap",
        ):
            boundary = max(
                boundary,
                offsets_list[statement.end_lineno or statement.lineno],
            )
    return boundary


def with_dedent_import(*, result: str, updated: Module | None = None) -> str:
    """Ensure ``from textwrap import dedent`` in transformed source.

    Args:
        result: Transformed source containing dedent calls.
        updated: AST whose top-level positions match ``result``; parsed
            when omitted. Callers may pass an earlier tree when edits left
            the header region intact.

    Returns:
        Source with the import merged into an existing textwrap import or
        inserted after the docstring and future imports.

    """
    if updated is None:
        updated = parse(source=result)
    imports: list[ImportFrom] = _textwrap_imports(updated=updated)
    available: bool = any(
        any(
            name.name == "dedent" and name.asname is None
            for name in node.names
        )
        for node in imports
    )
    if available:
        return result
    compatible: ImportFrom | None = next(
        (
            node
            for node in imports
            if all((name.name != "*" for name in node.names))
        ),
        None,
    )
    updated_lines: list[str] = result.splitlines(keepends=True)
    if compatible is not None:
        return merge_dedent(
            result=result,
            compatible=compatible,
            offsets=offsets(lines=updated_lines),
        )
    offset: int = insertion_offset(
        updated=updated,
        updated_lines=updated_lines,
    )
    return result[:offset] + "from textwrap import dedent\n" + result[offset:]


def ruff_call(*, call: str, executable: str, line_length: int) -> str | None:
    """Format a temporary f-string call using Ruff without editing its source.

    Args:
        call: A syntactically valid multiline call expression.
        executable: Ruff executable path.
        line_length: Ruff formatter line width.

    Returns:
        Ruff-formatted call, or None if Ruff cannot safely format it.

    """
    with TemporaryDirectory(prefix="string-dedent-") as folder:
        path: Path = Path(folder) / "snippet.py"
        path.write_text(data=f'_ = f"{{{call}}}"\n', encoding="utf-8")
        for command in (("check", "--select", "ALL", "--fix"), ("format",)):
            process: CompletedProcess[str] = run(
                args=[
                    executable,
                    *command,
                    "--isolated",
                    "--target-version",
                    "py313",
                    "--line-length",
                    str(object=line_length),
                    str(object=path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if process.returncode not in (0, 1):
                return None
        formatted: str = path.read_text(encoding="utf-8")
        try:
            parsed: Module = parse(source=formatted)
            assignment: stmt = parsed.body[0]
            if not isinstance(assignment, Assign):
                return None
            value: expr = assignment.value
            if not isinstance(value, JoinedStr):
                return None
            field: FormattedValue | None = next(
                (
                    part
                    for part in value.values
                    if isinstance(part, FormattedValue)
                ),
                None,
            )
            if field is None or dump(
                node=field.value,
                include_attributes=False,
            ) != dump(
                node=parse(source=call, mode="eval").body,
                include_attributes=False,
            ):
                return None
            lines: list[str] = formatted.splitlines(keepends=True)
            offsets_list: list[int] = offsets(lines=lines)
            start, end = _bounds(offsets=offsets_list, node=field.value)
            return formatted[start:end]
        except (SyntaxError, ValueError, IndexError):
            return None


def _top_level_commas(
    *,
    call_tokens: list[TokenInfo],
    opening: TokenInfo,
) -> tuple[int | None, list[int]]:
    """Find top-level commas and the closing parenthesis of a call.

    Args:
        call_tokens: Tokens of a single-line call expression.
        opening: The call's ``(`` token.

    Returns:
        Closing column and top-level comma columns.

    """
    depth: int = 0
    commas: list[int] = []
    closing: int | None = None
    for token in call_tokens:
        if token.start < opening.start or token.type != OP:
            continue
        if token.string in ("(", "[", "{"):
            depth += 1
        elif token.string in (")", "]", "}"):
            depth -= 1
            if depth == 0:
                closing = token.start[1]
                break
        elif token.string == "," and depth == 1:
            commas.append(token.start[1])
    return (closing, commas)


def _call_arguments(
    *,
    original_call: str,
) -> tuple[int, int, list[str]] | None:
    """Split a single-line call into top-level argument chunks.

    Args:
        original_call: Single-line call expression source.

    Returns:
        ``(open end, close column, chunks)`` or ``None`` when the call
        cannot be split safely.

    """
    call_tokens: list[TokenInfo] = list(
        generate_tokens(
            readline=StringIO(initial_value=original_call).readline,
        ),
    )
    opening: TokenInfo | None = next(
        (
            token
            for token in call_tokens
            if token.type == OP and token.string == "("
        ),
        None,
    )
    if opening is None:
        return None
    closing, commas = _top_level_commas(
        call_tokens=call_tokens,
        opening=opening,
    )
    if closing is None or not commas:
        return None
    previous: int = opening.end[1]
    chunks: list[str] = []
    for comma in commas:
        chunks.append(original_call[previous:comma].strip())
        previous = comma + 1
    tail: str = original_call[previous:closing].strip()
    if tail:
        chunks.append(tail)
    return (opening.end[1], closing, chunks)


def _staged_call(
    *,
    original_call: str,
    node: Call,
    opening_end: int,
    closing: int,
    chunks: list[str],
) -> str | None:
    """Rebuild a call with one argument per line, keeping its AST.

    Args:
        original_call: Single-line call expression source.
        node: The call's AST node.
        opening_end: Column just after the opening parenthesis.
        closing: Column of the closing parenthesis.
        chunks: Top-level argument chunks.

    Returns:
        Multiline call source with an identical AST, or ``None``.

    """
    staged: str = (
        original_call[:opening_end]
        + "\n"
        + "\n".join(f"    {chunk}," for chunk in chunks[:-1])
        + f"\n    {chunks[-1]}\n"
        + original_call[closing:]
    )
    try:
        if dump(
            node=parse(source=staged, mode="eval").body,
            include_attributes=False,
        ) != dump(node=node, include_attributes=False):
            return None
    except SyntaxError:
        return None
    return staged


def _staged_source(
    *,
    node: Call,
    source: str,
    offsets: list[int],
    minimum_arguments: int,
) -> tuple[int, int, str] | None:
    """Stage a multiline form of one eligible call, keeping its AST.

    Args:
        node: Call expression inside a ``FormattedValue``.
        source: Complete source text.
        offsets: Line-start offsets for ``source``.
        minimum_arguments: Minimum arguments for an expanded call.

    Returns:
        ``(start, end, staged call)`` or ``None`` when ineligible.

    """
    if len(node.args) + len(node.keywords) < minimum_arguments:
        return None
    start, end = _bounds(offsets=offsets, node=node)
    original_call: str = source[start:end]
    if "\n" in original_call or "\r" in original_call:
        return None
    split: tuple[int, int, list[str]] | None = _call_arguments(
        original_call=original_call,
    )
    if split is None:
        return None
    opening_end, closing, chunks = split
    if len(chunks) < minimum_arguments:
        return None
    staged: str | None = _staged_call(
        original_call=original_call,
        node=node,
        opening_end=opening_end,
        closing=closing,
        chunks=chunks,
    )
    if staged is None:
        return None
    return (start, end, staged)


def _call_patch(
    *,
    node: Call,
    source: str,
    original: Module,
    offsets: list[int],
    options: CallFormatOptions,
) -> tuple[int, int, str] | None:
    """Return a Ruff-formatted patch for one eligible f-string call.

    Args:
        node: Call expression inside a ``FormattedValue``.
        source: Complete source text.
        original: Parsed ``source`` module.
        offsets: Line-start offsets for ``source``.
        options: Call-expansion settings.

    Returns:
        ``(start, end, replacement)`` or ``None`` when ineligible.

    """
    staged_parts: tuple[int, int, str] | None = _staged_source(
        node=node,
        source=source,
        offsets=offsets,
        minimum_arguments=options.minimum_arguments,
    )
    if staged_parts is None or options.ruff_executable is None:
        return None
    start, end, staged = staged_parts
    formatted: str | None = ruff_call(
        call=staged,
        executable=options.ruff_executable,
        line_length=options.line_length,
    )
    if formatted is None or formatted == source[start:end]:
        return None
    indent: str = " " * (start - offsets[node.lineno - 1])
    formatted = formatted.replace("\n", "\n" + indent)
    try:
        candidate: str = source[:start] + formatted + source[end:]
        if dump(
            node=parse(source=candidate),
            include_attributes=False,
        ) != dump(node=original, include_attributes=False):
            return None
    except SyntaxError:
        return None
    return (start, end, formatted)


def _fstring_call_patches(
    *,
    source: str,
    original: Module,
    offsets: list[int],
    options: CallFormatOptions,
) -> list[tuple[int, int, str]]:
    """Format eligible f-string calls using isolated temporary Ruff snippets.

    Args:
        source: Original source code.
        original: Parsed module.
        offsets: Character offsets.
        options: Call-expansion settings.

    Returns:
        Nonoverlapping source patches verified against their original AST.

    """
    resolved: CallFormatOptions = replace(
        options,
        ruff_executable=options.ruff_executable or which(cmd="ruff"),
    )
    if resolved.ruff_executable is None:
        return []
    patches: list[tuple[int, int, str]] = []
    for parent in walk(node=original):
        if not isinstance(parent, FormattedValue):
            continue
        for node in walk(node=parent.value):
            if not isinstance(node, Call):
                continue
            patch: tuple[int, int, str] | None = _call_patch(
                node=node,
                source=source,
                original=original,
                offsets=offsets,
                options=resolved,
            )
            if patch is not None:
                patches.append(patch)
    return select(patches=patches)


def convert_strings(
    file: str | Path,
    tree: Module | None = None,
    *,
    write: bool = True,
    dry_run: bool = False,
    call_format: CallFormatOptions | None = None,
) -> ConversionResult:
    """Rewrite implicit and explicit string concatenations in source.

    Args:
        file: UTF-8 source path.
        tree: AST matching the file; parsed from the source when omitted.
        write: Persist the transformed source when changes exist.
        dry_run: Prevent writes even when write is true.
        call_format: F-string call expansion options; ``None`` applies
            ``CallFormatOptions`` defaults.

    Returns:
        Converted source, parsed AST, replacement count, and changed flag.

    Raises:
        OSError: Reading or writing failed.
        SyntaxError: Original source is not valid Python.

    """
    path: Path = Path(file)
    source: str = path.read_text(encoding="utf-8")
    original: Module = tree if tree is not None else parse(source=source)
    lines: list[str] = source.splitlines(keepends=True)
    offsets_list: list[int] = offsets(lines=lines)
    tokens: list[TokenInfo] = list(
        generate_tokens(readline=StringIO(initial_value=source).readline),
    )
    excluded: set[tuple[int, int]] = _docstring_spans(
        original=original,
        offsets=offsets_list,
    )
    patches: list[tuple[int, int, str]] = _patches(
        original=original,
        offsets=offsets_list,
        tokens=tokens,
        excluded=excluded,
    )
    selected: list[tuple[int, int, str]] = select(patches=patches)
    result: str = apply(source=source, selected=selected)
    if selected:
        header_end: int = _header_end(
            original=original,
            offsets_list=offsets_list,
        )
        header_intact: bool = all(
            start >= header_end for start, _, _ in selected
        )
        result = with_dedent_import(
            result=result,
            updated=original if header_intact else None,
        )
    formatting: CallFormatOptions = call_format or CallFormatOptions()
    if formatting.enabled:
        current: Module = (
            original if result == source else parse(source=result)
        )
        current_offsets: list[int] = offsets(
            lines=result.splitlines(keepends=True),
        )
        call_patches: list[tuple[int, int, str]] = _fstring_call_patches(
            source=result,
            original=current,
            offsets=current_offsets,
            options=formatting,
        )
        updated_tree: Module = current
        if call_patches:
            result = apply(source=result, selected=call_patches)
            updated_tree = parse(source=result)
    else:
        call_patches = []
        updated_tree = original if result == source else parse(source=result)
    if (selected or call_patches) and write and (not dry_run):
        path.write_text(data=result, encoding="utf-8")
    return ConversionResult(
        source=result,
        tree=updated_tree,
        count=len(selected) + len(call_patches),
        changed=bool(selected or call_patches),
    )


@dataclass(frozen=True, slots=True)
class Skipped:
    """Location and reason for a conservatively rejected expression.

    Attributes:
        line: One-based source line of the rejected expression.
        column: Zero-based source column of the rejected expression.
        reason: Human-readable rejection rationale.

    """

    line: int
    column: int
    reason: str


@dataclass(frozen=True, slots=True)
class SplitResult:
    """Source and diagnostics after attempting safe literal splits.

    Attributes:
        source: Transformed source text.
        count: Number of literal splits applied.
        changed: Whether any split was applied.
        skipped: Diagnostics for rejected candidates.

    """

    source: str
    count: int
    changed: bool
    skipped: tuple[Skipped, ...] = ()


def literal_parts(value: str | bytes, width: int) -> list[str] | None:
    """Split at code-point boundaries, retaining exact escape semantics.

    Args:
        value: Literal content to split.
        width: Maximum rendered fragment width.

    Returns:
        Quoted fragments, or ``None`` when no safe split exists.

    """
    parts: list[str] = []
    rest: str | bytes = value
    while rest:
        low: int = 1
        high: int = len(rest)
        best: int = 0
        while low <= high:
            middle: int = (low + high) // 2
            preview: str = repr(rest[:middle])
            if len(preview.expandtabs(tabsize=8)) <= width:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        if not best:
            return None
        parts.append(repr(rest[:best]))
        rest = rest[best:]
    return parts


def offset(lines: list[str], starts: list[int], line: int, column: int) -> int:
    """Convert UTF-8 AST byte column to a source character offset.

    Args:
        lines: Source lines including line terminators.
        starts: Character offset where each line begins.
        line: One-based source line.
        column: UTF-8 byte column within the line.

    Returns:
        Zero-based character offset into the source.

    """
    return starts[line - 1] + len(
        lines[line - 1]
        .encode(encoding="utf-8")[:column]
        .decode(encoding="utf-8"),
    )


def atomic_write(path: Path, content: str | bytes) -> None:
    """Replace a source file atomically, retaining its permission bits.

    Args:
        path: Destination file replaced atomically.
        content: Text or bytes written to the file.

    """
    with NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as stream:
        temporary: Path = Path(stream.name)
        try:
            stream.write(
                content.encode(encoding="utf-8")
                if isinstance(content, str)
                else content,
            )
            stream.flush()
            fsync(fd=stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.chmod(mode=path.stat().st_mode)
        temporary.replace(target=path)
    finally:
        temporary.unlink(missing_ok=True)


def resolve_line_length(
    *,
    file: str | Path,
    line_length: int | None = None,
    ruff_executable: str | None = None,
    ruff_args: tuple[str, ...] = (),
) -> int:
    """Read Ruff's effective formatter width for the target file.

    Args:
        file: File whose configuration Ruff should resolve.
        line_length: Explicit override, taking highest precedence.
        ruff_executable: Explicit Ruff executable, or discover on PATH.
        ruff_args: Additional Ruff check arguments, such as --config overrides.

    Returns:
        Resolved formatter width, or 88 when Ruff is not installed.

    Raises:
        ValueError: An explicit or resolved width is outside Ruff's range.
        RuntimeError: Ruff fails or returns an unrecognized settings report.

    """
    if line_length is not None:
        if (
            not Constants.min_line_width
            <= line_length
            <= Constants.max_line_width
        ):
            msg: str = "line_length must be between 20 and 320"
            raise ValueError(msg)
        return line_length
    executable: str | None = ruff_executable or which(cmd="ruff")
    if executable is None:
        if ruff_executable is not None:
            msg = f"Ruff executable was not found: {ruff_executable}"
            raise RuntimeError(msg)
        return 88
    completed: CompletedProcess[str] = run(
        args=[
            executable,
            "check",
            str(object=Path(file).resolve()),
            *ruff_args,
            "--show-settings",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        msg = f"Ruff settings resolution failed: {completed.stderr.strip()}"
        raise RuntimeError(msg)
    match: Match[str] | None = search(
        pattern="(?m)^formatter\\.line_width\\s*=\\s*(\\d+)\\s*$",
        string=completed.stdout,
    )
    if match is None:
        msg = "Ruff settings did not contain formatter.line_width"
        raise RuntimeError(msg)
    width: int = int(match.group(1))
    if not Constants.min_line_width <= width <= Constants.max_line_width:
        msg = f"Invalid Ruff formatter.line_width: {width}"
        raise ValueError(msg)
    return width


@dataclass(frozen=True, slots=True)
class _LoadedSource:
    """Decoded source file with its AST and line-ending convention.

    Attributes:
        original: Raw file bytes.
        encoding: Detected file encoding.
        source: Decoded source text.
        newline: Dominant line ending.
        parsed: Parsed module AST.

    """

    original: bytes
    encoding: str
    source: str
    newline: str
    parsed: Module


def _loaded_source(
    *,
    file: str | Path,
    tree: Module | None,
) -> tuple[Path, _LoadedSource]:
    """Read, decode, and parse a source file.

    Args:
        file: Python source path.
        tree: AST matching the file; parsed from the source when omitted.

    Returns:
        The path and its decoded, parsed contents.

    Raises:
        SyntaxError: Invalid Python input.
        OSError: File I/O error.

    """
    path: Path = Path(file)
    original: bytes = path.read_bytes()
    encoding: str = detect_encoding(
        readline=BytesIO(initial_bytes=original).readline,
    )[0]
    source: str = original.decode(encoding=encoding)
    parsed: Module = tree if tree is not None else parse(source=source)
    newline: str = (
        "\r\n"
        if b"\r\n" in original and b"\n" not in original.replace(b"\r\n", b"")
        else "\n"
    )
    return (
        path,
        _LoadedSource(
            original=original,
            encoding=encoding,
            source=source,
            newline=newline,
            parsed=parsed,
        ),
    )


@dataclass(frozen=True, slots=True)
class _ScanContext:
    """Shared read-only inputs for per-node candidate decisions.

    Attributes:
        source: Complete source text.
        lines: Source lines including endings.
        starts: Line-start offsets.
        newline: Source line-ending convention.
        protected: Docstring positions to skip.
        options: Splitting policy settings.
        width_limit: Maximum allowed physical width.

    """

    source: str
    lines: list[str]
    starts: list[int]
    newline: str
    protected: set[tuple[int, int]]
    options: SplitOptions
    width_limit: int


def _docstring_positions(*, parsed: Module) -> set[tuple[int, int]]:
    """Return the ``(line, column)`` positions of docstring literals.

    Args:
        parsed: Parsed source module.

    Returns:
        Positions protected from splitting.

    """
    protected: set[tuple[int, int]] = set()
    for parent in walk(node=parsed):
        if isinstance(
            parent,
            (Module, FunctionDef, AsyncFunctionDef, ClassDef),
        ) and (
            parent.body
            and isinstance(parent.body[0], Expr)
            and isinstance(parent.body[0].value, Constant)
            and isinstance(parent.body[0].value.value, str)
        ):
            value: Constant = parent.body[0].value
            protected.add((value.lineno, value.col_offset))
    return protected


def _eligible_span(
    *,
    node: Constant | JoinedStr,
    context: _ScanContext,
) -> tuple[int, int, str] | None:
    """Return the node's source span when it may be split.

    Args:
        node: Literal candidate.
        context: Shared scan inputs.

    Returns:
        ``(start, end, span)`` or ``None`` for ineligible nodes.

    """
    if (
        (node.lineno, node.col_offset) in context.protected
        or node.end_lineno is None
        or node.end_col_offset is None
    ):
        return None
    start: int = offset(
        lines=context.lines,
        starts=context.starts,
        line=node.lineno,
        column=node.col_offset,
    )
    end: int = offset(
        lines=context.lines,
        starts=context.starts,
        line=node.end_lineno,
        column=node.end_col_offset,
    )
    original: str = context.source[start:end]
    if not original:
        return None
    if all(
        len(line.rstrip("\r\n").expandtabs(tabsize=8)) <= context.width_limit
        for line in context.lines[node.lineno - 1 : node.end_lineno]
    ):
        return None
    if isinstance(node, JoinedStr) and (not context.options.split_fstrings):
        return None
    if (
        isinstance(node, Constant)
        and isinstance(node.value, bytes)
        and (not context.options.split_bytes)
    ):
        return None
    return (start, end, original)


def _tokenizable(*, node: expr, original: str) -> list[TokenInfo] | Skipped:
    """Tokenize a literal span and apply the single-literal requirement.

    Args:
        node: Literal candidate, used for diagnostics.
        original: Source span covering the node.

    Returns:
        Span tokens, or a skip diagnostic when tokenization fails or the
        span holds several literals.

    """
    try:
        tokens: list[TokenInfo] = list(
            generate_tokens(
                readline=StringIO(initial_value=original).readline,
            ),
        )
    except (IndentationError, SyntaxError, ValueError, TokenError):
        return Skipped(
            line=node.lineno,
            column=node.col_offset,
            reason="cannot tokenize source span",
        )
    return tokens


def _strategy_allows(
    *,
    tokens: list[TokenInfo],
    options: SplitOptions,
) -> bool:
    """Apply raw-string and triple-quote strategy gates.

    Args:
        tokens: Tokenized literal span.
        options: Literal-kind and multiline switches.

    Returns:
        Whether splitting may proceed.

    """
    literals: list[TokenInfo] = [
        token for token in tokens if token.type in (STRING, FSTRING_START)
    ]
    if not literals:
        return True
    return all(
        _strategy_allows_literal(text=token.string, options=options)
        for token in literals
    )


def _strategy_allows_literal(*, text: str, options: SplitOptions) -> bool:
    """Apply the raw-string and triple-quote gates to one literal token.

    Args:
        text: Literal token source.
        options: Literal-kind and multiline switches.

    Returns:
        Whether splitting may proceed for this literal.

    """
    prefix: str = text[: len(text) - len(text.lstrip("rRuUbBfF"))].lower()
    if "r" in prefix and (not options.split_raw_strings):
        return False
    return not (
        text[len(prefix) :].startswith(('"""', "'''"))
        and options.multiline_strategy == "preserve"
    )


def _fstring_chunks(*, text: str, width: int) -> tuple[list[str], str]:
    """Split literal f-string text into width-bounded fragments.

    Args:
        text: Literal portion of a ``JoinedStr``.
        width: Maximum fragment width including the ``f`` prefix.

    Returns:
        Rendered fragments plus the unsplittable remainder.

    """
    pieces: list[str] = []
    remaining: str = text
    while remaining:
        best: int = len(remaining)
        while (
            best
            and len(
                "f"
                + repr(remaining[:best].replace("{", "{{").replace("}", "}}")),
            )
            > width
        ):
            best -= 1
        if not best:
            break
        pieces.append(
            "f" + repr(remaining[:best].replace("{", "{{").replace("}", "}}")),
        )
        remaining = remaining[best:]
    return (pieces, remaining)


def _joined_parts(*, node: JoinedStr, width: int) -> list[str] | None:
    """Return width-bounded pieces for a ``JoinedStr``, or ``None``.

    Args:
        node: F-string node.
        width: Maximum rendered fragment width.

    Returns:
        Fragments when every value fits, else ``None``.

    """
    pieces: list[str] = []
    remaining: str = ""
    for item in node.values:
        if isinstance(item, Constant) and isinstance(item.value, str):
            chunks, remaining = _fstring_chunks(text=item.value, width=width)
            pieces.extend(chunks)
            if remaining:
                break
        elif isinstance(item, FormattedValue):
            fragment: str = unparse(ast_obj=JoinedStr(values=[item]))
            if len(fragment) > width:
                break
            pieces.append(fragment)
        else:
            break
    if remaining or len(pieces) < Constants.min_split_parts:
        return None
    return pieces


def _split_parts(
    *,
    node: Constant | JoinedStr,
    width: int,
) -> list[str] | None:
    """Return split fragments for a literal node, or ``None``.

    Args:
        node: Literal node.
        width: Maximum rendered fragment width.

    Returns:
        Fragment list, or ``None`` when indivisible.

    """
    if isinstance(node, JoinedStr):
        return _joined_parts(node=node, width=width)
    if isinstance(node.value, (str, bytes)):
        return literal_parts(value=node.value, width=width)
    return None


def _verified_split(
    *,
    node: expr,
    parts: list[str],
    leading: str,
    context: _ScanContext,
) -> str | Skipped:
    """Build the parenthesized replacement and verify AST equivalence.

    Args:
        node: Original literal node.
        parts: Fragment sources.
        leading: Indentation prefix for continuation lines.
        context: Shared scan inputs.

    Returns:
        Replacement source, or a skip diagnostic.

    """
    replacement: str = (
        "("
        + context.newline
        + "".join(f"{leading}    {part}{context.newline}" for part in parts)
        + f"{leading})"
    )
    if any(
        len(line) > context.width_limit
        for line in replacement.expandtabs(tabsize=8).splitlines()
    ):
        return Skipped(
            line=node.lineno,
            column=node.col_offset,
            reason="replacement exceeds width",
        )
    try:
        candidate: AST = parse(source=replacement, mode="eval").body
    except SyntaxError:
        return Skipped(
            line=node.lineno,
            column=node.col_offset,
            reason="invalid replacement",
        )
    if dump(node=candidate, include_attributes=False) != dump(
        node=node,
        include_attributes=False,
    ):
        return Skipped(
            line=node.lineno,
            column=node.col_offset,
            reason="replacement AST differs",
        )
    return replacement


def _split_candidate(
    *,
    node: Constant | JoinedStr,
    context: _ScanContext,
) -> tuple[int, int, str] | Skipped | None:
    """Return a verified split patch, a skip diagnostic, or ``None``.

    Args:
        node: Literal candidate.
        context: Shared scan inputs.

    Returns:
        ``(start, end, replacement)``, a ``Skipped`` diagnostic, or
        ``None`` for silently ineligible nodes.

    """
    span: tuple[int, int, str] | None = _eligible_span(
        node=node,
        context=context,
    )
    if span is None:
        return None
    start, end, original = span
    tokens: list[TokenInfo] | Skipped = _tokenizable(
        node=node,
        original=original,
    )
    if isinstance(tokens, Skipped):
        return tokens
    if not _strategy_allows(tokens=tokens, options=context.options):
        return None
    diagnostic: str = ""
    if context.options.preserve_comments and any(
        token.type == COMMENT for token in tokens
    ):
        diagnostic = "comment inside literal span"
    else:
        indent: str = context.lines[node.lineno - 1][
            : start - context.starts[node.lineno - 1]
        ]
        leading: str = indent[: len(indent) - len(indent.lstrip(" \t"))]
        width: int = (
            context.width_limit - len(leading.expandtabs(tabsize=8)) - 4
        )
        if width < Constants.min_fragment_width:
            diagnostic = "insufficient indentation budget"
        else:
            parts: list[str] | None = _split_parts(node=node, width=width)
            if parts is None or len(parts) < Constants.min_split_parts:
                diagnostic = "literal indivisible within width"
            else:
                replacement: str | Skipped = _verified_split(
                    node=node,
                    parts=parts,
                    leading=leading,
                    context=context,
                )
                return (
                    replacement
                    if isinstance(replacement, Skipped)
                    else (start, end, replacement)
                )
    return Skipped(line=node.lineno, column=node.col_offset, reason=diagnostic)


def _collect_splits(
    *,
    context: _ScanContext,
    parsed: Module,
) -> tuple[list[tuple[int, int, str, AST]], list[Skipped]]:
    """Gather verified patches and diagnostics for every literal node.

    Args:
        context: Shared scan inputs.
        parsed: Original module AST.

    Returns:
        Candidate patches paired with their original nodes, and skip
        diagnostics in source order.

    """
    patches: list[tuple[int, int, str, AST]] = []
    skipped: list[Skipped] = []
    non_expression: set[int] = {
        id(child)
        for joined in walk(node=parsed)
        if isinstance(joined, JoinedStr)
        for child in joined.values
        if isinstance(child, Constant)
    }
    non_expression.update(
        id(descendant)
        for field in walk(node=parsed)
        if isinstance(field, FormattedValue) and field.format_spec is not None
        for descendant in walk(node=field.format_spec)
    )
    for node in walk(node=parsed):
        if id(node) in non_expression:
            continue
        if isinstance(node, Constant):
            if not isinstance(node.value, (str, bytes)):
                continue
        elif not isinstance(node, JoinedStr):
            continue
        outcome: tuple[int, int, str] | Skipped | None = _split_candidate(
            node=node,
            context=context,
        )
        if outcome is None:
            continue
        if isinstance(outcome, Skipped):
            skipped.append(outcome)
        else:
            patches.append((*outcome, node))
    return (patches, skipped)


def _apply_verified(
    *,
    source: str,
    patches: list[tuple[int, int, str, AST]],
    skipped: list[Skipped] | None = None,
) -> tuple[str, int]:
    """Apply non-overlapping patches verified against their original nodes.

    Args:
        source: Current source text.
        patches: Candidate ``(start, end, replacement, node)`` spans whose
            replacement must parse to an AST identical to ``node``.
        skipped: Optional diagnostic sink recording rejected patches.

    Returns:
        Updated source and accepted patch count.

    """
    result: str = source
    count: int = 0
    boundary: int = len(source) + 1
    ordered: list[tuple[int, int, str, AST]] = sorted(
        patches,
        key=lambda patch: (patch[0], patch[1]),
        reverse=True,
    )
    for start, end, replacement, node in ordered:
        if end > boundary:
            continue
        try:
            differs: bool = dump(
                node=parse(source=replacement, mode="eval").body,
                include_attributes=False,
            ) != dump(node=node, include_attributes=False)
        except SyntaxError:
            if skipped is not None:
                skipped.append(
                    Skipped(line=1, column=0, reason="invalid replacement"),
                )
            continue
        if differs:
            if skipped is not None:
                skipped.append(
                    Skipped(
                        line=1,
                        column=0,
                        reason="replacement AST differs",
                    ),
                )
            continue
        result = result[:start] + replacement + result[end:]
        count += 1
        boundary = start
    return (result, count)


def split_strings(
    file: str | Path,
    *,
    tree: Module | None = None,
    write: bool = True,
    dry_run: bool = False,
    options: SplitOptions | None = None,
) -> SplitResult:
    """Split provably equivalent oversized literals; report unsafe cases.

    Args:
        file: UTF-8 Python source path.
        tree: AST matching the source; parsed when omitted.
        write: Persist successful changes.
        dry_run: Override writing without preventing candidate generation.
        options: Width and policy settings; ``None`` applies defaults.

    Returns:
        Transformed source, count, and rejected candidate diagnostics.

    Raises:
        ValueError: Invalid settings.
        SyntaxError: Invalid Python input.
        OSError: File I/O error.

    """
    resolved: SplitOptions = options or SplitOptions()
    if resolved.multiline_strategy not in Constants.strategies:
        msg: str = "Invalid maximum line length or multiline strategy"
        raise ValueError(msg)
    path, loaded = _loaded_source(file=file, tree=tree)
    lines: list[str] = loaded.source.splitlines(keepends=True)
    context: _ScanContext = _ScanContext(
        source=loaded.source,
        lines=lines,
        starts=offsets(lines=lines),
        newline=loaded.newline,
        protected=_docstring_positions(parsed=loaded.parsed)
        if resolved.preserve_docstrings
        else set(),
        options=resolved,
        width_limit=resolve_line_length(
            file=file,
            line_length=resolved.line_length
            if resolved.line_length is not None
            else resolved.max_line_size,
            ruff_executable=resolved.ruff_executable,
            ruff_args=resolved.ruff_args,
        ),
    )
    skipped: list[Skipped]
    patches, skipped = _collect_splits(context=context, parsed=loaded.parsed)
    result, count = _apply_verified(source=loaded.source, patches=patches)
    if resolved.format_interpolations:
        interp_lines: list[str] = result.splitlines(keepends=True)
        context = replace(
            context,
            source=result,
            lines=interp_lines,
            starts=offsets(lines=interp_lines),
        )
        result, extra, additional = _format_interpolations(
            context=context,
            parsed=loaded.parsed
            if result == loaded.source
            else parse(source=result),
        )
        count += extra
        skipped.extend(additional)
    if count and write and (not dry_run):
        atomic_write(
            path=path,
            content=result.encode(encoding=loaded.encoding),
        )
    return SplitResult(
        source=result,
        count=count,
        changed=bool(count),
        skipped=tuple(skipped),
    )


def _interpolation_args(
    *,
    call: Call,
    argument_indent: str,
    width_limit: int,
) -> list[str] | None:
    """Render call arguments one per line, or ``None`` when too wide.

    Args:
        call: Call expression inside a ``FormattedValue``.
        argument_indent: Indentation prefix applied to each argument.
        width_limit: Maximum allowed physical width.

    Returns:
        Unparsed arguments, or ``None`` when any cannot fit.

    """
    args: list[str] = [unparse(ast_obj=arg) for arg in call.args]
    args.extend(
        "**" + unparse(ast_obj=kw.value)
        if kw.arg is None
        else kw.arg + "=" + unparse(ast_obj=kw.value)
        for kw in call.keywords
    )
    if any(
        "\n" in arg or len(argument_indent + arg + ",") > width_limit
        for arg in args
    ):
        return None
    return args


def _verified_interpolation(
    *,
    call: Call,
    candidate: str,
    start: int,
    end: int,
) -> tuple[int, int, str] | Skipped:
    """Verify a candidate expansion reproduces the call AST.

    Args:
        call: Original call node.
        candidate: Rendered multiline call source.
        start: Replacement span start offset.
        end: Replacement span end offset.

    Returns:
        ``(start, end, candidate)`` or a skip diagnostic.

    """
    try:
        differs: bool = dump(
            node=parse(source=candidate, mode="eval").body,
            include_attributes=False,
        ) != dump(node=call, include_attributes=False)
    except SyntaxError:
        return Skipped(
            line=call.lineno,
            column=call.col_offset,
            reason="invalid interpolation",
        )
    if differs:
        return Skipped(
            line=call.lineno,
            column=call.col_offset,
            reason="interpolation AST differs",
        )
    return (start, end, candidate)


def _interpolation_candidate(
    *,
    call: Call,
    context: _ScanContext,
) -> tuple[int, int, str] | Skipped | None:
    """Return a verified call expansion patch, a skip reason, or ``None``.

    Args:
        call: Call expression inside a ``FormattedValue``.
        context: Shared scan inputs.

    Returns:
        ``(start, end, replacement)``, a ``Skipped`` diagnostic, or
        ``None`` for silently ineligible fields.

    """
    if call.end_lineno is None or call.end_col_offset is None:
        return None
    start: int = offset(
        lines=context.lines,
        starts=context.starts,
        line=call.lineno,
        column=call.col_offset,
    )
    end: int = offset(
        lines=context.lines,
        starts=context.starts,
        line=call.end_lineno,
        column=call.end_col_offset,
    )
    segment: str = context.source[start:end]
    if "#" in segment:
        return Skipped(
            line=call.lineno,
            column=call.col_offset,
            reason="comment-sensitive interpolation",
        )
    if (
        "\n" in segment
        or "\r" in segment
        or len(
            context.lines[call.lineno - 1]
            .rstrip("\r\n")
            .expandtabs(tabsize=8),
        )
        <= context.width_limit
    ):
        return None
    if len(call.args) + len(call.keywords) < Constants.min_split_parts:
        return Skipped(
            line=call.lineno,
            column=call.col_offset,
            reason="call cannot be expanded safely",
        )
    opening: int = segment.find("(")
    if opening < 0 or not segment.endswith(")"):
        return Skipped(
            line=call.lineno,
            column=call.col_offset,
            reason="unsupported call syntax",
        )
    indent: str = context.lines[call.lineno - 1][
        : start - context.starts[call.lineno - 1]
    ]
    leading: str = indent[: len(indent) - len(indent.lstrip(" \t"))]
    argument_indent: str = leading + "    "
    args: list[str] | None = _interpolation_args(
        call=call,
        argument_indent=argument_indent,
        width_limit=context.width_limit,
    )
    return (
        Skipped(
            line=call.lineno,
            column=call.col_offset,
            reason="argument exceeds width",
        )
        if args is None
        else _verified_interpolation(
            call=call,
            candidate=segment[: opening + 1]
            + context.newline
            + "".join(
                argument_indent + arg + "," + context.newline for arg in args
            )
            + leading
            + ")",
            start=start,
            end=end,
        )
    )


def _format_interpolations(
    *,
    context: _ScanContext,
    parsed: Module,
) -> tuple[str, int, list[Skipped]]:
    """Expand oversized calls in f-string fields without altering the AST.

    Args:
        context: Shared scan inputs describing the current source.
        parsed: Module AST matching ``context.source``.

    Returns:
        Rewritten source, accepted replacement count, and skip diagnostics.

    """
    original: Module = parsed
    patches: list[tuple[int, int, str, AST]] = []
    skipped: list[Skipped] = []
    for parent in walk(node=original):
        if not isinstance(parent, JoinedStr):
            continue
        for field in walk(node=parent):
            if not isinstance(field, FormattedValue) or not isinstance(
                field.value,
                Call,
            ):
                continue
            outcome: tuple[int, int, str] | Skipped | None = (
                _interpolation_candidate(call=field.value, context=context)
            )
            if outcome is None:
                continue
            if isinstance(outcome, Skipped):
                skipped.append(outcome)
            else:
                patches.append((*outcome, field.value))
    result, count = _apply_verified(
        source=context.source,
        patches=patches,
        skipped=skipped,
    )
    return (result, count, skipped)


@dataclass(frozen=True, slots=True)
class TransformResult:
    """Combined transformation result and rejected-split diagnostics.

    Attributes:
        source: Fully transformed source.
        tree: Parsed transformed module.
        count: Total accepted replacements.
        changed: Whether any replacement was accepted.
        skipped: Diagnostics for untransformable oversized strings.

    """

    source: str
    tree: Module
    count: int
    changed: bool
    skipped: tuple[Skipped, ...]


def transform_strings(
    file: str | Path,
    *,
    tree: Module | None = None,
    write: bool = True,
    dry_run: bool = False,
    options: TransformOptions | None = None,
) -> TransformResult:
    """Run dedent conversion followed by width-limited splitting.

    Args:
        file: Input Python file.
        tree: AST matching the original source; parsed when omitted.
        write: Persist successful transformations.
        dry_run: Prevent writes when enabled.
        options: Combined transform settings; ``None`` applies defaults.

    Returns:
        Combined result and diagnostics.

    Raises:
        OSError: Source or temporary-file operations fail.
        SyntaxError: Source is invalid Python.

    """
    resolved: TransformOptions = options or TransformOptions()
    resolved_width: int = resolve_line_length(
        file=file,
        line_length=resolved.line_length
        if resolved.line_length is not None
        else resolved.max_line_size,
        ruff_executable=resolved.ruff_executable,
        ruff_args=resolved.ruff_args,
    )
    path: Path = Path(file)
    original_bytes: bytes = path.read_bytes()
    encoding: str = detect_encoding(
        readline=BytesIO(initial_bytes=original_bytes).readline,
    )[0]
    source: str = original_bytes.decode(encoding=encoding)
    parsed: Module = tree if tree is not None else parse(source=source)
    with TemporaryDirectory(prefix="string-transform-") as folder:
        staged: Path = Path(folder) / "source.py"
        staged.write_bytes(data=original_bytes)
        call_format: CallFormatOptions | None = resolved.call_format
        effective_call_format: CallFormatOptions = (
            replace(
                call_format,
                line_length=resolved_width,
                ruff_executable=resolved.ruff_executable
                or call_format.ruff_executable,
            )
            if call_format is not None
            else CallFormatOptions(
                line_length=resolved_width,
                ruff_executable=resolved.ruff_executable,
            )
        )
        if encoding.lower().replace("_", "-") in ("utf-8", "utf-8-sig"):
            dedented: ConversionResult = convert_strings(
                file=staged,
                tree=parsed,
                write=True,
                call_format=effective_call_format,
            )
        else:
            dedented = ConversionResult(
                source=source,
                tree=parsed,
                count=0,
                changed=False,
            )
        split: SplitResult = split_strings(
            file=staged,
            tree=dedented.tree,
            write=True,
            options=replace(resolved, line_length=resolved_width),
        )
        result_bytes: bytes = staged.read_bytes()
    result: str = result_bytes.decode(encoding=encoding)
    if result_bytes == original_bytes:
        transformed: Module = parsed
    elif not split.changed:
        transformed = dedented.tree
    else:
        transformed = parse(source=result)
    count: int = dedented.count + split.count
    if count and write and (not dry_run) and (result_bytes != original_bytes):
        atomic_write(path=path, content=result_bytes)
    return TransformResult(
        source=result,
        tree=transformed,
        count=count,
        changed=result_bytes != original_bytes,
        skipped=split.skipped,
    )
