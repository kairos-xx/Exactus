# Copyright (c) 2026
"""Repair Python lines that remain too long after Ruff formatting.

Ruff's formatter leaves a physical line over the configured width when no
layout of the statement fits. This module repairs those residual lines
conservatively: every candidate rewrite is validated against the Python
AST, scored against Ruff's own E501 diagnostics and accepted only when it
strictly improves the file, so a repair can never change behavior.

:class:`LongLinesAPI` is the stable in-memory and batch facade;
:class:`LongLineRepair` plugs the repair into the Ruff stabilization loop of
the lints tool.
"""

from __future__ import annotations

from ast import AST, Constant, Expr, Expression, dump, expr, parse, walk
from dataclasses import dataclass
from difflib import SequenceMatcher, unified_diff
from importlib import import_module
from inspect import cleandoc
from io import BytesIO, StringIO
from json import JSONDecodeError, loads
from os import fsync
from pathlib import Path
from re import Match, Pattern
from re import compile as compile_pattern
from tempfile import NamedTemporaryFile
from textwrap import wrap
from tokenize import (
    COMMENT,
    FSTRING_END,
    FSTRING_MIDDLE,
    FSTRING_START,
    NAME,
    OP,
    STRING,
    TokenError,
    TokenInfo,
    detect_encoding,
    generate_tokens,
)
from typing import TYPE_CHECKING, Final, Protocol, cast, final

from exactus.tools.common.cli import ExactusCommonTables

if TYPE_CHECKING:
    from subprocess import CompletedProcess
    from types import ModuleType


@final
class Constants:
    """Group module-level constants.

    Attributes:
        default_line_length: Grouped module constant.
        max_passes: Grouped module constant.
        string_prefix_pattern: Grouped module constant.
        word_pattern: Grouped module constant.
        pragma_pattern: Grouped module constant.
        expression_prefixes: Grouped module constant.
        condition_prefixes: Grouped module constant.
        directive_names: Grouped module constant.
        excluded_parts: Grouped module constant.
        triple_quote_length: Grouped module constant.
        min_split_parts: Grouped module constant.
        min_docstring_width: Grouped module constant.
        docstring_block_indent: Grouped module constant.
        docstring_field_indent: Grouped module constant.
        min_section_underline: Grouped module constant.
        min_fstring_text: Grouped module constant.
        min_chain_dots: Grouped module constant.
        field_sections: Grouped module constant.
        tab_size: Grouped module constant.
        pyproject_name: Grouped module constant.

    """

    default_line_length: Final[int] = 79
    max_passes: Final[int] = 256
    string_prefix_pattern: Final[Pattern[str]] = compile_pattern(
        pattern="(?i)^([rubf]*)(['\\\"]{1,3})",
    )
    word_pattern: Final[Pattern[str]] = compile_pattern(
        pattern="[A-Za-z_]\\w*|\"[^\"\\n]*\"?|'[^'\\n]*'?",
    )
    pragma_pattern: Final[Pattern[str]] = compile_pattern(
        pattern=(
            "#\\s*(?:noqa|type:|pyright:|pylint:|flake8:|ruff:|isort:|mypy:|pr"
            "agma:|nosec|fmt:)"
        ),
    )
    expression_prefixes: Final[tuple[str, ...]] = (
        "return ",
        "yield ",
        "assert ",
        "raise ",
    )
    condition_prefixes: Final[tuple[str, ...]] = ("if ", "elif ", "while ")
    directive_names: Final[tuple[str, ...]] = (
        "SPDX-",
        "type:",
        "pyright:",
        "noqa",
        "fmt:",
        "isort:",
        "pragma:",
        "nosec",
        "pylint:",
        "mypy:",
        "flake8:",
        "ruff:",
    )
    excluded_parts: Final[frozenset[str]] = (
        ExactusCommonTables.DEFAULT_EXCLUDED_DIRS
    )
    triple_quote_length: Final[int] = 3
    min_split_parts: Final[int] = 2
    min_docstring_width: Final[int] = 24
    docstring_block_indent: Final[int] = 8
    docstring_field_indent: Final[int] = 4
    min_section_underline: Final[int] = 3
    min_fstring_text: Final[int] = 12
    min_chain_dots: Final[int] = 2
    field_sections: Final[frozenset[str]] = frozenset(
        {
            "Args:",
            "Arguments:",
            "Parameters:",
            "Keyword Args:",
            "Other Parameters:",
            "Attributes:",
            "Raises:",
            "Warns:",
            "Receives:",
            "Returns:",
            "Yields:",
        },
    )
    tab_size: Final[int] = 4
    pyproject_name: Final[str] = "pyproject.toml"


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuration for long-line repair.

    Attributes:
        line_length: Maximum physical line width, tabs expanded to four.
        run_ruff: Whether Ruff formats candidates and scores E501 rows.
        check_only: Compute results without writing files.
        verbose: Report unchanged files too in presentation layers.
        respect_fmt_off: Treat ``# fmt: off`` regions as protected.
        show_diff: Attach a unified diff to every changed result.
        backup: Keep the exact original bytes in ``<name>.bak``.
        reported_e501_lines: One-based rows from an earlier Ruff report
            that seed the first repair pass.
        ruff_command: Executable prefix used to invoke Ruff.

    """

    line_length: int = Constants.default_line_length
    run_ruff: bool = True
    check_only: bool = False
    verbose: bool = False
    respect_fmt_off: bool = True
    show_diff: bool = False
    backup: bool = False
    reported_e501_lines: frozenset[int] = frozenset()
    ruff_command: tuple[str, ...] = ("ruff",)


@dataclass(frozen=True, slots=True)
class Edit:
    """One source edit using absolute character offsets.

    Attributes:
        start: Offset of the first replaced character.
        end: Offset one past the last replaced character.
        replacement: Text written in place of the replaced span.
        reason: Short identifier of the repair that produced the edit.

    """

    start: int
    end: int
    replacement: str
    reason: str


@dataclass(frozen=True, slots=True)
class Result:
    """Outcome for one processed Python file.

    Attributes:
        path: Processed source file.
        changed: Whether the transformed source differs from the original.
        passes: Repair passes executed before the fixpoint.
        unresolved_lines: Long lines left after repair, excluding protected.
        protected_lines: Long lines inside ``# fmt: off`` regions.
        unfixable_lines: Unresolved lines dominated by one indivisible token.
        diff: Unified diff when ``Settings.show_diff`` is set.

    """

    path: Path
    changed: bool
    passes: int
    unresolved_lines: tuple[int, ...]
    protected_lines: tuple[int, ...]
    unfixable_lines: tuple[int, ...]
    diff: str = ""


@dataclass(frozen=True, slots=True)
class TextResult:
    """Outcome for one in-memory Python source transformation.

    Attributes:
        source: Transformed source text.
        changed: Whether ``source`` differs from the input.
        passes: Repair passes executed before the fixpoint.
        unresolved_lines: Long lines left after repair, excluding protected.
        protected_lines: Long lines inside ``# fmt: off`` regions.
        unfixable_lines: Unresolved lines dominated by one indivisible token.
        diff: Unified diff when ``Settings.show_diff`` is set.

    """

    source: str
    changed: bool
    passes: int
    unresolved_lines: tuple[int, ...]
    protected_lines: tuple[int, ...]
    unfixable_lines: tuple[int, ...]
    diff: str = ""


@dataclass(frozen=True, slots=True)
class BatchResult:
    """Aggregate outcome for a deterministic batch transformation.

    Attributes:
        results: Per-file results in discovery order.

    """

    results: tuple[Result, ...]

    @property
    def changed(self) -> bool:
        """Return whether at least one file would change.

        Returns:
            ``True`` when any per-file result changed.

        """
        return any(result.changed for result in self.results)

    @property
    def clean(self) -> bool:
        """Return whether every processed file has no unresolved lines.

        Returns:
            ``True`` when no per-file result has unresolved lines.

        """
        return all(not result.unresolved_lines for result in self.results)

    @property
    def unresolved_count(self) -> int:
        """Return the total unresolved-line count across the batch.

        Returns:
            Sum of unresolved lines over every per-file result.

        """
        return sum(len(result.unresolved_lines) for result in self.results)


@dataclass(frozen=True, order=True, slots=True)
class CandidateScore:
    """Lexicographic quality score for one candidate source.

    Attributes:
        syntax_error: ``1`` when the candidate does not parse.
        semantic_change: ``1`` when the executable AST changed.
        protected_change: ``1`` when a protected region changed.
        e501_count: Residual over-long physical lines.
        overflow: Total columns beyond the configured width.
        explicit_continuations: Backslash continuations introduced.
        changed_characters: Size of the edit relative to the source.

    """

    syntax_error: int
    semantic_change: int
    protected_change: int
    e501_count: int
    overflow: int
    explicit_continuations: int
    changed_characters: int


@dataclass(frozen=True, slots=True)
class RuffDiagnostic:
    """One residual Ruff E501 diagnostic.

    Attributes:
        row: One-based line of the diagnostic.
        column: One-based column of the diagnostic.
        message: Diagnostic message text.

    """

    row: int
    column: int
    message: str


@dataclass(slots=True)
class ReflowState:
    """Mutable traversal state while reflowing docstring lines.

    Attributes:
        section: Header of the docstring section being traversed.
        fenced: Whether the traversal is inside a fenced code block.
        literal_block: Whether the traversal is inside a ``::`` block.

    """

    section: str = ""
    fenced: bool = False
    literal_block: bool = False


@dataclass(frozen=True, slots=True)
class TokenScan:
    """Shared token-stream state for f-string split repairs.

    Attributes:
        source: Complete source text.
        tokens: Tokens of ``source``.
        offsets: Absolute offset of every physical line start.
        long_lines: One-based over-long physical line numbers.

    """

    source: str
    tokens: tuple[TokenInfo, ...]
    offsets: tuple[int, ...]
    long_lines: frozenset[int]


def _run(
    *,
    args: list[str],
    input_text: str,
    text: bool,
    capture_output: bool,
    check: bool,
) -> CompletedProcess[str]:
    """Use the public runner so integrations can replace Ruff execution.

    Args:
        args: Command arguments passed to the runner.
        input_text: Standard-input payload fed to the process.
        text: Whether streams are decoded as text.
        capture_output: Whether standard output and error are captured.
        check: Whether a non-zero exit status raises an error.

    Returns:
        Completed process describing the runner invocation.

    """
    long_lines: ModuleType = import_module(
        name="exactus.tools.lints.long_lines",
    )
    return long_lines.run(
        args=args,
        input=input_text,
        text=text,
        capture_output=capture_output,
        check=check,
    )


class LongLineFixer:
    """Repair residual E501-style Python lines conservatively."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the fixer.

        Args:
            settings: Repair configuration.

        """
        self.settings: Settings = settings
        self._seed_e501_lines: frozenset[int] = settings.reported_e501_lines

    def transform_text(
        self,
        source: str,
        path: Path | None = None,
    ) -> TextResult:
        """Transform Python source in memory without writing a file.

        Args:
            source: Python source to transform.
            path: Configuration identity used by Ruff. Defaults to
                ``stdin.py``.

        Returns:
            Immutable transformation result containing the replacement
            source.

        """
        identity: Path = path if path is not None else Path("stdin.py")
        original: str = source
        passes: int = 0
        seen: set[str] = {source}
        if self.settings.run_ruff:
            source = self._ruff_format_text(source=source, path=identity)
            seen.add(source)
        for _ in range(Constants.max_passes):
            passes += 1
            candidate: str = self._repair_pass(source=source, path=identity)
            if candidate == source or candidate in seen:
                break
            seen.add(candidate)
            source = candidate
        all_long: tuple[int, ...] = self._all_long_lines(source=source)
        protected: tuple[int, ...] = tuple(
            line
            for line in all_long
            if self._is_protected_line(source=source, line_number=line)
        )
        unresolved: tuple[int, ...] = tuple(
            line for line in all_long if line not in protected
        )
        unfixable: tuple[int, ...] = tuple(
            line
            for line in unresolved
            if self._intrinsically_unbreakable(source=source, line_number=line)
        )
        changed: bool = source != original
        return TextResult(
            source=source,
            changed=changed,
            passes=passes,
            unresolved_lines=unresolved,
            protected_lines=protected,
            unfixable_lines=unfixable,
            diff="".join(
                unified_diff(
                    a=original.splitlines(keepends=True),
                    b=source.splitlines(keepends=True),
                    fromfile=str(object=identity),
                    tofile=f"{identity} (fixed)",
                ),
            )
            if changed and self.settings.show_diff
            else "",
        )

    def fix_path(self, path: Path) -> Result:
        """Fix one Python file using the same in-memory API as callers.

        Args:
            path: Python file to repair.

        Returns:
            Processing result with unresolved classifications.

        """
        original_bytes: bytes = path.read_bytes()
        encoding: str = detect_encoding(
            readline=BytesIO(initial_bytes=original_bytes).readline,
        )[0]
        original: str = original_bytes.decode(encoding=encoding)
        transformed: TextResult = self.transform_text(
            source=original,
            path=path,
        )
        if transformed.changed and (not self.settings.check_only):
            self._commit(
                path=path,
                source=transformed.source,
                encoding=encoding,
                original_bytes=original_bytes,
            )
        return Result(
            path=path,
            changed=transformed.changed,
            passes=transformed.passes,
            unresolved_lines=transformed.unresolved_lines,
            protected_lines=transformed.protected_lines,
            unfixable_lines=transformed.unfixable_lines,
            diff=transformed.diff,
        )

    @classmethod
    def _for_line(cls, stripped: str) -> str | None:
        """Parenthesize the iterable expression in a for header.

        Args:
            stripped: Line without indentation.

        Returns:
            Replacement stripped line or ``None``.

        """
        prefix: str = (
            "async for " if stripped.startswith("async for ") else "for "
        )
        if not stripped.startswith(prefix) or not stripped.endswith(":"):
            return None
        body: str = stripped[len(prefix) : -1]
        tokens: tuple[TokenInfo, ...] = cls._tokens(source=body)
        depth: int = 0
        for token in tokens:
            if token.type == OP and token.string in "([{":
                depth += 1
            elif token.type == OP and token.string in ")]}":
                depth -= 1
            elif token.type == NAME and token.string == "in" and (depth == 0):
                split: int = token.end[1]
                target: str = body[: token.start[1]].rstrip()
                iterable: str = body[split:].strip()
                if not iterable or cls._already_wrapped(text=iterable):
                    return None
                return f"{prefix}{target} in ({iterable}):"
        return None

    @classmethod
    def _match_guard_line(cls, stripped: str) -> str | None:
        """Parenthesize the guard expression of one case clause.

        Args:
            stripped: Line without indentation.

        Returns:
            Replacement stripped line or ``None``.

        """
        if not stripped.startswith("case ") or not stripped.endswith(":"):
            return None
        body: str = stripped[5:-1]
        tokens: tuple[TokenInfo, ...] = cls._tokens(source=body)
        depth: int = 0
        for token in tokens:
            if token.type == OP and token.string in "([{":
                depth += 1
            elif token.type == OP and token.string in ")]}":
                depth -= 1
            elif token.type == NAME and token.string == "if" and (depth == 0):
                pattern: str = body[: token.start[1]].rstrip()
                guard: str = body[token.end[1] :].strip()
                if not guard or cls._already_wrapped(text=guard):
                    return None
                return f"case {pattern} if ({guard}):"
        return None

    @classmethod
    def _statement_line(cls, stripped: str) -> str | None:
        """Parenthesize an assignment or expression-bearing statement.

        Args:
            stripped: Line without indentation.

        Returns:
            Replacement stripped line or ``None``.

        """
        if not stripped or stripped.startswith(("#", "from ", "import ")):
            return None
        assignment: int = cls._assignment_operator(text=stripped)
        if assignment >= 0:
            left: str = stripped[: assignment + 1]
            right: str = stripped[assignment + 1 :].strip()
            return (
                None
                if not right or cls._already_wrapped(text=right)
                else f"{left} ({right})"
            )
        for prefix in Constants.expression_prefixes:
            if stripped.startswith(prefix):
                expression: str = stripped[len(prefix) :].strip()
                if prefix == "assert " and "," in expression:
                    return None
                return (
                    None
                    if not expression or cls._already_wrapped(text=expression)
                    else f"{prefix}({expression})"
                )
        return None

    @classmethod
    def _annotation_line(cls, stripped: str) -> str | None:
        """Wrap a simple annotation that has no assigned value.

        Args:
            stripped: Line without indentation.

        Returns:
            Replacement stripped line or ``None``.

        """
        if stripped.startswith(("def ", "async def ", "class ", "type ")):
            return None
        colon: int = cls._top_level_colon(text=stripped)
        if colon <= 0 or cls._assignment_operator(text=stripped) >= 0:
            return None
        target: str = stripped[:colon]
        annotation: str = stripped[colon + 1 :].strip()
        if (
            not target.isidentifier()
            or not annotation
            or cls._already_wrapped(text=annotation)
        ):
            return None
        return f"{target}: ({annotation})"

    @classmethod
    def _decorator_line(cls, stripped: str) -> str | None:
        """Wrap one decorator expression.

        Args:
            stripped: Line without indentation.

        Returns:
            Replacement stripped line or ``None``.

        """
        if not stripped.startswith("@"):
            return None
        expression: str = stripped[1:].strip()
        return (
            None
            if cls._already_wrapped(text=expression)
            else f"@({expression})"
        )

    @classmethod
    def _chain_start(cls: type[LongLineFixer], text: str) -> int:
        """Find the expression start after a simple statement prefix.

        Args:
            text: Stripped source line.

        Returns:
            Expression-start offset or ``-1``.

        """
        assignment: int = cls._assignment_operator(text=text)
        if assignment >= 0:
            return assignment + 1
        for keyword in Constants.expression_prefixes:
            if text.startswith(keyword):
                return len(keyword)
        return 0

    @classmethod
    def _top_level_dots(
        cls: type[LongLineFixer],
        text: str,
    ) -> tuple[int, ...]:
        """Find dotted-chain breakpoints outside delimiters and strings.

        Args:
            text: Expression text.

        Returns:
            Dot offsets suitable for line breaks.

        """
        tokens: tuple[TokenInfo, ...] = cls._tokens(source=text)
        depth: int = 0
        points: list[int] = []
        for token in tokens:
            if token.type == OP and token.string in "([{":
                depth += 1
            elif token.type == OP and token.string in ")]}":
                depth -= 1
            elif token.type == OP and token.string == "." and (depth == 0):
                points.append(
                    cls._line_offsets(source=text)[token.start[0] - 1]
                    + token.start[1],
                )
        return tuple(points)

    @classmethod
    def _assignment_operator(cls: type[LongLineFixer], text: str) -> int:
        """Locate a top-level assignment operator.

        Args:
            text: One logical source line.

        Returns:
            Assignment index or ``-1``.

        """
        depth: int = 0
        for token in cls._tokens(source=text):
            if token.type == OP and token.string in "([{":
                depth += 1
            elif token.type == OP and token.string in ")]}":
                depth -= 1
            elif token.type == OP and token.string == "=" and (depth == 0):
                return token.start[1]
        return -1

    @classmethod
    def _top_level_colon(cls: type[LongLineFixer], text: str) -> int:
        """Locate a top-level colon.

        Args:
            text: One logical source line.

        Returns:
            Colon index or ``-1``.

        """
        depth: int = 0
        for token in cls._tokens(source=text):
            if token.type == OP and token.string in "([{":
                depth += 1
            elif token.type == OP and token.string in ")]}":
                depth -= 1
            elif token.type == OP and token.string == ":" and (depth == 0):
                return token.start[1]
        return -1

    @staticmethod
    def _syntax_valid(source: str) -> bool:
        """Return whether source parses as Python.

        Args:
            source: Candidate Python source.

        Returns:
            ``True`` when the source parses.

        """
        try:
            parse(source=source)
        except SyntaxError:
            return False
        return True

    @staticmethod
    def _is_directive(comment: str) -> bool:
        """Return whether a comment is a tool directive that must not move.

        Args:
            comment: Comment text beginning with ``#``.

        Returns:
            ``True`` for pragma, type-checker and formatter directives.

        """
        body: str = comment.removeprefix("#").lstrip()
        return body.startswith(Constants.directive_names)

    @staticmethod
    def _reflow_fence(
        lines: list[str],
        index: int,
        state: ReflowState,
        result: list[str],
    ) -> int | None:
        """Copy fenced, fence-boundary or blank lines without reflowing.

        Args:
            lines: Dedented docstring lines.
            index: Current line index.
            state: Mutable traversal state.
            result: Accumulated output lines.

        Returns:
            Next index when the line was handled, otherwise ``None``.

        """
        line: str = lines[index]
        stripped: str = line.strip()
        if stripped.startswith(("```", "~~~")):
            state.fenced = not state.fenced
            result.append(line)
            return index + 1
        if state.fenced:
            result.append(line)
            return index + 1
        if not stripped:
            state.literal_block = False
            result.append("")
            return index + 1
        return None

    @staticmethod
    def _numpy_section(lines: list[str], index: int) -> bool:
        """Return whether a line begins a NumPy-style underlined section.

        Args:
            lines: Dedented docstring lines.
            index: Index of the candidate heading line.

        Returns:
            ``True`` when the next line is a dashed underline.

        """
        if index + 1 >= len(lines) or not lines[index].strip():
            return False
        underline: str = lines[index + 1].strip()
        return len(underline) >= Constants.min_section_underline and set(
            underline,
        ) == {"-"}

    @staticmethod
    def _rest_field(text: str) -> tuple[str, str] | None:
        """Split one Sphinx/reST field into prefix and prose description.

        Args:
            text: One stripped docstring line.

        Returns:
            The field prefix and description, or ``None``.

        """
        if not text.startswith(":"):
            return None
        second: int = text.find(":", 1)
        if second < 0:
            return None
        prefix: str = text[: second + 1] + " "
        description: str = text[second + 1 :].strip()
        return (prefix, description) if description else None

    @staticmethod
    def _summary_end(lines: list[str]) -> int:
        """Find the end of the indivisible first summary sentence.

        Args:
            lines: Dedented docstring lines.

        Returns:
            Exclusive line index containing the complete first sentence.

        """
        for index, line in enumerate(iterable=lines):
            has_mid_sentence_end: bool = any(
                mark in line for mark in (". ", "? ", "! ")
            )
            if has_mid_sentence_end or line.rstrip().endswith((".", "?", "!")):
                return index + 1
            if not line.strip():
                return max(1, index)
        return min(1, len(lines))

    @staticmethod
    def _doc_section_header(text: str) -> bool:
        """Return whether text is a recognized documentation section header.

        Args:
            text: One stripped docstring line.

        Returns:
            ``True`` when the line is a section header.

        """
        return text in frozenset(
            {
                "Args:",
                "Arguments:",
                "Parameters:",
                "Keyword Args:",
                "Returns:",
                "Yields:",
                "Raises:",
                "Attributes:",
                "Methods:",
                "Examples:",
                "Example:",
                "Notes:",
                "Note:",
                "Warnings:",
                "Warning:",
                "Todo:",
                "References:",
                "See Also:",
            },
        )

    @staticmethod
    def _wrap_hanging(
        text: str,
        first_prefix: str,
        continuation: str,
        width: int,
    ) -> list[str]:
        """Wrap text with distinct first-line and continuation indentation.

        Args:
            text: Description prose to wrap.
            first_prefix: Prefix of the first output line.
            continuation: Prefix of every following output line.
            width: Maximum line width.

        Returns:
            The wrapped lines.

        """
        words: list[str] = text.split()
        if not words:
            return [first_prefix.rstrip()]
        output: list[str] = []
        current: str = first_prefix
        for word in words:
            candidate: str = f"{current}{word}"
            if len(candidate) <= width or current == first_prefix:
                current = f"{candidate} "
                continue
            output.append(current.rstrip())
            current = f"{continuation}{word} "
        output.append(current.rstrip())
        return output

    @staticmethod
    def _docstring_spans(source: str) -> frozenset[tuple[int, int]]:
        """Return start coordinates for all AST docstring literals.

        Args:
            source: Python source.

        Returns:
            Line and column of every docstring, or nothing for bad source.

        """
        try:
            tree: AST = parse(source=source)
        except SyntaxError:
            return frozenset()
        spans: set[tuple[int, int]] = set()
        for node in walk(node=tree):
            body: list[AST] | None = getattr(node, "body", None)
            if not isinstance(body, list) or not body:
                continue
            first: AST = body[0]
            if (
                isinstance(first, Expr)
                and isinstance(first.value, Constant)
                and isinstance(first.value.value, str)
            ):
                spans.add((first.value.lineno, first.value.col_offset))
        return frozenset(spans)

    @staticmethod
    def _literal_string_value(token_text: str) -> str:
        """Evaluate a non-f-string literal as a string.

        Args:
            token_text: Complete literal token.

        Returns:
            Literal string value.

        Raises:
            TypeError: If the token is not a string constant.

        """
        expression: Expression = parse(source=token_text, mode="eval")
        if not isinstance(expression.body, Constant) or not isinstance(
            expression.body.value,
            str,
        ):
            msg: str = "Token is not a plain string literal."
            raise TypeError(msg)
        return expression.body.value

    @staticmethod
    def _split_value(value: str, width: int) -> tuple[str, ...]:
        """Split a decoded string while preserving its complete value.

        Args:
            value: Decoded string value.
            width: Preferred maximum decoded chunk width.

        Returns:
            Value chunks whose concatenation equals the input.

        """
        if len(value) <= width:
            return (value,)
        parts: list[str] = []
        remaining: str = value
        while len(remaining) > width:
            split_at: int = max(
                remaining.rfind(" ", 1, width + 1),
                remaining.rfind("/", 1, width + 1),
                remaining.rfind("-", 1, width + 1),
                remaining.rfind("_", 1, width + 1),
            )
            if split_at < width // 3:
                split_at = width
            elif remaining[split_at] == " ":
                split_at += 1
            parts.append(remaining[:split_at])
            remaining = remaining[split_at:]
        if remaining:
            parts.append(remaining)
        return tuple(parts)

    @staticmethod
    def _quote(value: str, quote: str) -> str:
        """Render one decoded string chunk as a Python literal.

        Args:
            value: Decoded string chunk.
            quote: Preferred quote character.

        Returns:
            Valid Python string literal.

        """
        return f"{quote}{
            value.replace('\\', '\\\\')
            .replace('\n', '\\n')
            .replace('\r', '\\r')
            .replace('\t', '\\t')
            .replace(quote, f'\\{quote}')
        }{quote}"

    @staticmethod
    def _from_import_line(stripped: str) -> str | None:
        """Parenthesize one single-line ``from`` import.

        Args:
            stripped: Line without leading indentation.

        Returns:
            Replacement stripped line or ``None``.

        """
        if not stripped.startswith("from ") or " import " not in stripped:
            return None
        import_parts: list[str] = stripped.split(sep=" import ", maxsplit=1)
        prefix: str = import_parts[0]
        names: str = import_parts[1]
        if names.startswith("(") or "#" in names:
            return None
        return f"{prefix} import ({names})"

    @staticmethod
    def _with_line(stripped: str) -> str | None:
        """Parenthesize one synchronous or asynchronous ``with`` header.

        Args:
            stripped: Line without indentation.

        Returns:
            Replacement stripped line or ``None``.

        """
        prefix: str = (
            "async with " if stripped.startswith("async with ") else "with "
        )
        if not stripped.startswith(prefix) or not stripped.endswith(":"):
            return None
        body: str = stripped[len(prefix) : -1].strip()
        return None if body.startswith("(") else f"{prefix}({body}):"

    @staticmethod
    def _condition_line(stripped: str) -> str | None:
        """Parenthesize one conditional header.

        Args:
            stripped: Line without indentation.

        Returns:
            Replacement stripped line or ``None``.

        """
        for prefix in Constants.condition_prefixes:
            if stripped.startswith(prefix) and stripped.endswith(":"):
                body: str = stripped[len(prefix) : -1].strip()
                return None if body.startswith("(") else f"{prefix}({body}):"
        return None

    @staticmethod
    def _span_is_parenthesized(source: str, start: int, end: int) -> bool:
        """Check whether an AST span is already directly grouped.

        Args:
            source: Complete source.
            start: Expression start offset.
            end: Expression end offset.

        Returns:
            Whether surrounding non-whitespace characters are ``(`` and ``)``.

        """
        left: int = start - 1
        right: int = end
        while left >= 0 and source[left] in " \t":
            left -= 1
        while right < len(source) and source[right] in " \t":
            right += 1
        return (
            left >= 0
            and right < len(source)
            and (source[left] == "(")
            and (source[right] == ")")
        )

    @staticmethod
    def _already_wrapped(text: str) -> bool:
        """Check whether an expression is visibly outer-parenthesized.

        Args:
            text: Expression text.

        Returns:
            Whether it starts and ends with parentheses.

        """
        return text.startswith("(") and text.endswith(")")

    @staticmethod
    def _same_code_ast(before: str, after: str) -> bool:
        """Compare executable ASTs while ignoring docstring text values.

        Args:
            before: Original source.
            after: Candidate source.

        Returns:
            Whether both sources differ only in docstring text.

        """
        try:
            before_tree: AST = parse(source=before)
            after_tree: AST = parse(source=after)
        except SyntaxError:
            return False
        for tree in (before_tree, after_tree):
            for node in walk(node=tree):
                body: list[AST] | None = getattr(node, "body", None)
                if not isinstance(body, list) or not body:
                    continue
                first: AST = body[0]
                if (
                    isinstance(first, Expr)
                    and isinstance(first.value, Constant)
                    and isinstance(first.value.value, str)
                ):
                    first.value.value = "<docstring>"
        return dump(node=before_tree, include_attributes=False) == dump(
            node=after_tree,
            include_attributes=False,
        )

    @staticmethod
    def _same_ast(before: str, after: str) -> bool:
        """Verify that a rewrite preserves Python AST semantics.

        Args:
            before: Original source.
            after: Candidate source.

        Returns:
            Whether both sources parse to identical ASTs.

        """
        try:
            return dump(
                node=parse(source=before),
                include_attributes=False,
            ) == dump(node=parse(source=after), include_attributes=False)
        except SyntaxError:
            return False

    @staticmethod
    def _tokens(source: str) -> tuple[TokenInfo, ...]:
        """Tokenize source without propagating incomplete-token failures.

        Args:
            source: Source fragment.

        Returns:
            Tokens, or an empty tuple for an incomplete fragment.

        """
        try:
            return tuple(
                generate_tokens(
                    readline=StringIO(initial_value=source).readline,
                ),
            )
        except TokenError:
            return ()

    @staticmethod
    def _line_offsets(source: str) -> tuple[int, ...]:
        """Build absolute offsets for every physical line start.

        Args:
            source: Text to index.

        Returns:
            Absolute line-start offsets.

        """
        offsets: list[int] = [0]
        for index, char in enumerate(iterable=source):
            if char == "\n":
                offsets.append(index + 1)
        return tuple(offsets)

    @staticmethod
    def _apply_edit(source: str, edit: Edit) -> str:
        """Apply one absolute source edit.

        Args:
            source: Original source.
            edit: Edit to apply.

        Returns:
            Edited source.

        """
        return source[: edit.start] + edit.replacement + source[edit.end :]

    def _commit(
        self,
        path: Path,
        source: str,
        encoding: str,
        original_bytes: bytes,
    ) -> None:
        """Atomically commit a validated source transformation.

        Args:
            path: Destination Python source.
            source: Fully validated replacement source.
            encoding: Original Python source encoding.
            original_bytes: Exact original bytes for optional backup.

        """
        mode: int = path.stat().st_mode
        if self.settings.backup:
            backup: Path = path.with_suffix(suffix=f"{path.suffix}.bak")
            if not backup.exists():
                backup.write_bytes(data=original_bytes)
                backup.chmod(mode=mode)
        temporary_name: str = ""
        try:
            with NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(source.encode(encoding=encoding))
                temporary.flush()
                fsync(fd=temporary.fileno())
            temporary_path: Path = Path(temporary_name)
            temporary_path.chmod(mode=mode)
            temporary_path.replace(target=path)
        finally:
            if (
                temporary_name
                and (temporary_path := Path(temporary_name)).exists()
            ):
                temporary_path.unlink()

    def _repair_pass(self, source: str, path: Path) -> str:
        """Apply the first semantics-preserving repair that improves source.

        Repairs are tried in a fixed order, which keeps results
        deterministic. Every candidate is optionally Ruff-formatted, then
        scored. A candidate is accepted only when it strictly improves the
        diagnostic state, preventing oscillation and collateral E501
        regressions.

        Args:
            source: Current Python source.
            path: Source path for Ruff configuration discovery.

        Returns:
            The first improving candidate or the unchanged source.

        """
        repairs: tuple[LineTransformer, ...] = (
            self._expand_semicolon_statement,
            self._hoist_trailing_comment,
            self._wrap_comment,
            self._format_docstring,
            self._split_multiline_string,
            self._split_long_string,
            self._parenthesize_from_import,
            self._parenthesize_with_statement,
            self._parenthesize_condition,
            self._parenthesize_for_statement,
            self._parenthesize_match_guard,
            self._parenthesize_statement,
            self._parenthesize_annotation,
            self._parenthesize_decorator,
            self._split_long_fstring,
            self._parenthesize_ast_expression,
            self._break_chain,
            self._break_with_backslash,
        )
        baseline: CandidateScore = self._score(
            original=source,
            candidate=source,
            path=path,
        )
        for repair in repairs:
            candidate: str | None = repair(source)
            if not candidate or candidate == source:
                continue
            semantic_ok: bool = (
                self._same_code_ast(before=source, after=candidate)
                if repair == self._format_docstring
                else self._same_ast(before=source, after=candidate)
            )
            if not semantic_ok:
                continue
            formatted: str = (
                self._ruff_format_text(source=candidate, path=path)
                if self.settings.run_ruff
                else candidate
            )
            if repair != self._format_docstring and (
                not self._same_ast(before=source, after=formatted)
            ):
                continue
            if (
                self._score(original=source, candidate=formatted, path=path)
                < baseline
            ):
                self._seed_e501_lines = frozenset()
                return formatted
        self._seed_e501_lines = frozenset()
        return source

    def _score(
        self,
        original: str,
        candidate: str,
        path: Path,
    ) -> CandidateScore:
        """Score a candidate with correctness before cosmetic improvement.

        Args:
            original: Source before this repair step.
            candidate: Proposed source after the repair step.
            path: File path used for Ruff configuration.

        Returns:
            Lexicographically comparable candidate score.

        """
        original_lines: list[str] = original.splitlines(keepends=True)
        candidate_lines: list[str] = candidate.splitlines(keepends=True)
        return CandidateScore(
            syntax_error=0 if self._syntax_valid(source=candidate) else 1,
            semantic_change=0
            if self._same_ast(before=original, after=candidate)
            or self._same_code_ast(before=original, after=candidate)
            else 1,
            protected_change=0
            if self._protected_text(source=original)
            == self._protected_text(source=candidate)
            else 1,
            e501_count=len(diagnostics)
            if (diagnostics := self._ruff_e501(source=candidate, path=path))
            else len(self._all_long_lines(source=candidate)),
            overflow=sum(
                max(
                    0,
                    len(line.expandtabs(tabsize=Constants.tab_size))
                    - self.settings.line_length,
                )
                for line in candidate.splitlines()
            ),
            explicit_continuations=candidate.count("\\\n"),
            changed_characters=sum(
                (
                    max(
                        sum((len(line) for line in original_lines[i1:i2])),
                        sum((len(line) for line in candidate_lines[j1:j2])),
                    )
                    for tag, i1, i2, j1, j2 in SequenceMatcher(
                        a=original_lines,
                        b=candidate_lines,
                        autojunk=False,
                    ).get_opcodes()
                    if tag != "equal"
                ),
            ),
        )

    def _ruff_e501(
        self,
        source: str,
        path: Path,
    ) -> tuple[RuffDiagnostic, ...]:
        """Ask Ruff for exact residual E501 diagnostics when available.

        Args:
            source: Candidate source.
            path: File path for configuration discovery.

        Returns:
            E501 diagnostics, or an empty tuple when Ruff is unavailable.

        """
        if not self.settings.run_ruff:
            return ()
        try:
            completed: CompletedProcess[str] = _run(
                args=[
                    *self.settings.ruff_command,
                    "check",
                    "--select",
                    "E501",
                    "--output-format",
                    "json",
                    "--stdin-filename",
                    str(object=path),
                    "-",
                ],
                input_text=source,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError:
            return ()
        try:
            payload: object = loads(s=completed.stdout or "[]")
        except JSONDecodeError:
            return ()
        if not isinstance(payload, list):
            return ()
        diagnostics: list[RuffDiagnostic] = []
        for item in cast(typ="list[object]", val=payload):
            if not isinstance(item, dict):
                continue
            entry: dict[str, object] = cast(typ="dict[str, object]", val=item)
            if entry.get("code") != "E501":
                continue
            location: object = entry.get("location")
            if not isinstance(location, dict):
                continue
            where: dict[str, object] = cast(
                typ="dict[str, object]",
                val=location,
            )
            row: object = where.get("row")
            column: object = where.get("column")
            message: object = entry.get("message")
            if isinstance(row, int) and isinstance(column, int):
                diagnostics.append(
                    RuffDiagnostic(
                        row=row,
                        column=column,
                        message=message
                        if isinstance(message, str)
                        else "E501",
                    ),
                )
        return tuple(diagnostics)

    def _all_long_lines(self, source: str) -> tuple[int, ...]:
        """Return all non-exempt physical lines exceeding configured width.

        Args:
            source: Python source.

        Returns:
            One-based numbers of the over-long, non-exempt lines.

        """
        return tuple(
            (
                number
                for number, line in enumerate(
                    iterable=source.splitlines(),
                    start=1,
                )
                if len(line.expandtabs(tabsize=Constants.tab_size))
                > self.settings.line_length
                and (not self._ignorable_long_line(line=line))
            ),
        )

    def _protected_lines(self, source: str) -> frozenset[int]:
        """Return lines protected by Ruff formatting directives.

        Args:
            source: Python source.

        Returns:
            One-based numbers of lines inside ``# fmt: off`` regions.

        """
        if not self.settings.respect_fmt_off:
            return frozenset()
        protected: set[int] = set()
        disabled: bool = False
        for number, line in enumerate(iterable=source.splitlines(), start=1):
            stripped: str = line.strip().lower()
            if stripped.startswith("# fmt: off"):
                disabled = True
                protected.add(number)
                continue
            if disabled:
                protected.add(number)
            if stripped.startswith("# fmt: on"):
                disabled = False
        return frozenset(protected)

    def _is_protected_line(self, source: str, line_number: int) -> bool:
        """Return whether a physical line is in a protected region.

        Args:
            source: Python source.
            line_number: One-based physical line number.

        Returns:
            ``True`` when the line is protected.

        """
        return line_number in self._protected_lines(source=source)

    def _protected_text(self, source: str) -> tuple[str, ...]:
        """Extract protected physical lines for preservation checks.

        Args:
            source: Python source.

        Returns:
            Text of every protected physical line, in order.

        """
        protected: frozenset[int] = self._protected_lines(source=source)
        return tuple(
            (
                line
                for number, line in enumerate(
                    iterable=source.splitlines(),
                    start=1,
                )
                if number in protected
            ),
        )

    def _intrinsically_unbreakable(
        self,
        source: str,
        line_number: int,
    ) -> bool:
        """Detect a long physical line dominated by one indivisible token.

        Args:
            source: Python source.
            line_number: One-based physical line number.

        Returns:
            ``True`` when one name or string token alone exceeds the width.

        """
        lines: list[str] = source.splitlines()
        if not 1 <= line_number <= len(lines):
            return False
        line: str = lines[line_number - 1]
        usable: int = (
            self.settings.line_length - len(line) + len(line.lstrip())
        )
        tokens: tuple[TokenInfo, ...] = self._tokens(source=line.lstrip())
        words: tuple[str, ...] = (
            tuple(
                token.string
                for token in tokens
                if token.type in {NAME, STRING, FSTRING_MIDDLE}
            )
            if tokens
            else tuple(Constants.word_pattern.findall(string=line.lstrip()))
        )
        return any(
            len(word.expandtabs(tabsize=Constants.tab_size)) > usable
            for word in words
        )

    def _expand_semicolon_statement(self, source: str) -> str:
        """Expand one long line containing top-level semicolon statements.

        Args:
            source: Current source.

        Returns:
            Source with one semicolon line split, or the input.

        """
        lines: list[str] = source.splitlines(keepends=True)
        for line_number in self._long_lines(source=source):
            index: int = line_number - 1
            line: str = lines[index]
            body: str = line.rstrip("\r\n")
            newline: str = line[len(body) :]
            stripped: str = body.lstrip()
            indent: str = body[: len(body) - len(stripped)]
            points: list[int] = []
            depth: int = 0
            for token in self._tokens(source=stripped):
                if token.type == OP and token.string in "([{":
                    depth += 1
                elif token.type == OP and token.string in ")]}":
                    depth -= 1
                elif token.type == OP and token.string == ";" and (depth == 0):
                    points.append(token.start[1])
            if not points:
                continue
            parts: list[str] = []
            start: int = 0
            for point in points:
                parts.append(stripped[start:point].strip())
                start = point + 1
            parts.append(stripped[start:].strip())
            if any(not part for part in parts):
                continue
            lines[index] = (
                "\n".join(f"{indent}{part}" for part in parts) + newline
            )
            candidate: str = "".join(lines)
            if self._same_ast(before=source, after=candidate):
                return candidate
            lines[index] = line
        return source

    def _parenthesize_for_statement(self, source: str) -> str:
        """Unlock formatting for long for/async-for iterable expressions.

        Args:
            source: Current source.

        Returns:
            Rewritten source when applicable.

        """
        return self._rewrite_long_lines(
            source=source,
            transformer=self._for_line,
        )

    def _parenthesize_match_guard(self, source: str) -> str:
        """Unlock formatting for a long guarded match/case clause.

        Args:
            source: Current source.

        Returns:
            Rewritten source when applicable.

        """
        return self._rewrite_long_lines(
            source=source,
            transformer=self._match_guard_line,
        )

    def _hoist_trailing_comment(self, source: str) -> str:
        """Move one trailing comment of a long line onto its own line.

        The comment keeps the indentation of the code it described, so the
        executable AST is untouched. Directive comments stay in place
        because their meaning depends on the line they sit on.

        Args:
            source: Current source.

        Returns:
            Source with one trailing comment hoisted when applicable.

        """
        long_lines: frozenset[int] = frozenset(self._long_lines(source=source))
        lines: list[str] = source.splitlines(keepends=True)
        for token in self._tokens(source=source):
            if token.type != COMMENT or token.start[0] not in long_lines:
                continue
            index: int = token.start[0] - 1
            line: str = lines[index]
            code: str = line[: token.start[1]].rstrip()
            if not code or self._is_directive(comment=token.string):
                continue
            body: str = line.rstrip("\r\n")
            newline: str = line[len(body) :]
            indent: str = body[: len(body) - len(body.lstrip())]
            lines[index] = f"{indent}{token.string}{newline}{code}{newline}"
            candidate: str = "".join(lines)
            if self._same_ast(before=source, after=candidate):
                return candidate
            lines[index] = line
        return source

    def _wrap_comment(self, source: str) -> str:
        """Wrap one long standalone comment without changing executable AST.

        Args:
            source: Current source.

        Returns:
            Source with one ordinary comment wrapped when applicable.

        """
        lines: list[str] = source.splitlines(keepends=True)
        for line_number in self._long_lines(source=source):
            index: int = line_number - 1
            line: str = lines[index]
            body: str = line.rstrip("\r\n")
            newline: str = line[len(body) :]
            stripped: str = body.lstrip()
            indent: str = body[: len(body) - len(stripped)]
            if not stripped.startswith("# ") or self._is_directive(
                comment=stripped,
            ):
                continue
            width: int = max(20, self.settings.line_length - len(indent) - 2)
            pieces: list[str] = wrap(
                text=stripped[2:],
                width=width,
                break_long_words=False,
                break_on_hyphens=False,
            )
            if len(pieces) < Constants.min_split_parts:
                continue
            lines[index] = (
                "\n".join(f"{indent}# {piece}" for piece in pieces) + newline
            )
            candidate: str = "".join(lines)
            if self._same_ast(before=source, after=candidate):
                return candidate
            lines[index] = line
        return source

    def _format_docstring(self, source: str) -> str:
        """Reflow one long docstring using Google-style indentation rules.

        The summary sentence is never divided. Section headers remain on their
        own lines, field descriptions use hanging indentation, and indented
        literal/example blocks are left untouched.

        Args:
            source: Current Python source.

        Returns:
            Source with at most one docstring reflowed.

        """
        tree: AST
        try:
            tree = parse(source=source)
        except SyntaxError:
            return source
        long_lines: frozenset[int] = frozenset(self._long_lines(source=source))
        for node in walk(node=tree):
            body: list[AST] | None = getattr(node, "body", None)
            if not isinstance(body, list) or not body:
                continue
            first: AST = body[0]
            if not isinstance(first, Expr) or not isinstance(
                first.value,
                Constant,
            ):
                continue
            if not isinstance(first.value.value, str):
                continue
            start_line: int | None = getattr(first.value, "lineno", None)
            end_line: int | None = getattr(first.value, "end_lineno", None)
            if start_line is None or end_line is None:
                continue
            if not any(
                line in long_lines for line in range(start_line, end_line + 1)
            ):
                continue
            edit: Edit | None = self._docstring_edit(
                source=source,
                value_node=first.value,
                offsets=self._line_offsets(source=source),
            )
            if edit is not None:
                return self._apply_edit(source=source, edit=edit)
        return source

    def _docstring_edit(
        self,
        source: str,
        value_node: Constant,
        offsets: tuple[int, ...],
    ) -> Edit | None:
        """Build one structured docstring reflow edit.

        Args:
            source: Complete source text.
            value_node: AST string constant used as a docstring.
            offsets: Absolute line-start offsets.

        Returns:
            Reflow edit, or ``None`` when representation is unsupported.

        """
        start_line: int = value_node.lineno
        end_line: int = value_node.end_lineno or start_line
        start_column: int = value_node.col_offset
        end_column: int = value_node.end_col_offset or start_column
        start: int = offsets[start_line - 1] + start_column
        end: int = offsets[end_line - 1] + end_column
        token_text: str = source[start:end]
        match: Match[str] | None = Constants.string_prefix_pattern.match(
            string=token_text,
        )
        if (
            match is None
            or len(match.group(2)) != Constants.triple_quote_length
        ):
            return None
        prefix: str = match.group(1)
        quote: str = match.group(2)
        content: str = token_text[len(prefix) + len(quote) : -len(quote)]
        if "f" in prefix.lower() or "b" in prefix.lower() or "\\" in content:
            return None
        base_indent: str = " " * start_column
        width: int = self.settings.line_length - len(base_indent) - 4
        if width < Constants.min_docstring_width:
            return None
        reflowed: str = self._reflow_docstring_text(text=content, width=width)
        if reflowed == cleandoc(doc=content):
            return None
        rendered_lines: list[str] = reflowed.splitlines()
        if not rendered_lines:
            return None
        rendered_content: str = rendered_lines[0]
        for rendered_line in rendered_lines[1:]:
            rendered_content += (
                f"\n{base_indent}{rendered_line}" if rendered_line else "\n"
            )
        rendered_content += f"\n{base_indent}"
        return Edit(
            start=start,
            end=end,
            replacement=f"{prefix}{quote}{rendered_content}{quote}",
            reason="docstring",
        )

    def _reflow_docstring_text(self, text: str, width: int) -> str:
        """Reflow Google, NumPy and Sphinx/reST docstring prose safely.

        Summary sentences, doctests, fenced/literal code, directives, tables,
        NumPy underlines and reST field syntax are structural and are never
        flattened into ordinary prose.

        Args:
            text: Raw text between triple-quote delimiters.
            width: Maximum semantic docstring width.

        Returns:
            Reflowed, dedented semantic docstring text.

        """
        normalized: str = cleandoc(doc=text)
        if not normalized:
            return normalized
        lines: list[str] = normalized.splitlines()
        summary_end: int = self._summary_end(lines=lines)
        result: list[str] = lines[:summary_end]
        index: int = summary_end
        state: ReflowState = ReflowState()
        while index < len(lines):
            stepped: int | None = self._reflow_fence(
                lines=lines,
                index=index,
                state=state,
                result=result,
            )
            if stepped is None:
                stepped = self._reflow_structural(
                    lines=lines,
                    index=index,
                    state=state,
                    result=result,
                )
            if stepped is None:
                stepped = self._reflow_field(
                    lines=lines,
                    index=index,
                    state=state,
                    result=result,
                    width=width,
                )
            index = (
                stepped
                if stepped is not None
                else self._reflow_paragraph(
                    lines=lines,
                    index=index,
                    state=state,
                    result=result,
                    width=width,
                )
            )
        return "\n".join(result)

    def _reflow_structural(
        self,
        lines: list[str],
        index: int,
        state: ReflowState,
        result: list[str],
    ) -> int | None:
        """Copy one structural docstring line without reflowing it.

        Args:
            lines: Dedented docstring lines.
            index: Current line index.
            state: Mutable traversal state.
            result: Accumulated output lines.

        Returns:
            Next index when the line was structural, otherwise ``None``.

        """
        line: str = lines[index]
        stripped: str = line.strip()
        if self._numpy_section(lines=lines, index=index):
            state.section = f"{stripped}:"
            result.extend((stripped, lines[index + 1]))
            return index + 2
        if self._doc_section_header(text=stripped):
            state.section = stripped
            result.append(stripped)
            return index + 1
        if stripped.endswith("::"):
            state.literal_block = True
            result.append(line)
            return index + 1
        if (
            state.literal_block
            or len(line) - len(line.lstrip())
            >= Constants.docstring_block_indent
            or stripped.startswith((">>>", "...", ".. ", "|", "+-"))
            or (set(stripped) <= {"-", "=", "+", "|", ":", " "})
        ):
            result.append(line)
            return index + 1
        return None

    def _reflow_field(
        self,
        lines: list[str],
        index: int,
        state: ReflowState,
        result: list[str],
        width: int,
    ) -> int | None:
        """Reflow one reST or field-section entry line.

        Args:
            lines: Dedented docstring lines.
            index: Current line index.
            state: Mutable traversal state.
            result: Accumulated output lines.
            width: Maximum semantic docstring width.

        Returns:
            Next index when the line was a field entry, otherwise ``None``.

        """
        line: str = lines[index]
        stripped: str = line.strip()
        indent: int = len(line) - len(line.lstrip())
        rest_field: tuple[str, str] | None = self._rest_field(text=stripped)
        if rest_field is not None:
            prefix, description = rest_field
            result.extend(
                self._wrap_hanging(
                    text=description,
                    first_prefix=prefix,
                    continuation=" " * len(prefix),
                    width=width,
                ),
            )
            return index + 1
        if (
            state.section in Constants.field_sections
            and indent >= Constants.docstring_field_indent
            and (":" in stripped)
        ):
            name, description = stripped.split(sep=":", maxsplit=1)
            if name and description.strip():
                result.extend(
                    self._wrap_hanging(
                        text=description.strip(),
                        first_prefix=f"    {name}: ",
                        continuation=" " * Constants.docstring_block_indent,
                        width=width,
                    ),
                )
                return index + 1
        if (
            state.section.rstrip(":")
            in {"Parameters", "Other Parameters", "Attributes", "Methods"}
            and indent == 0
            and (":" in stripped)
        ):
            result.append(line)
            return index + 1
        return None

    def _reflow_paragraph(
        self,
        lines: list[str],
        index: int,
        state: ReflowState,
        result: list[str],
        width: int,
    ) -> int:
        """Collect and wrap one ordinary docstring paragraph.

        Args:
            lines: Dedented docstring lines.
            index: Current line index.
            state: Mutable traversal state.
            result: Accumulated output lines.
            width: Maximum semantic docstring width.

        Returns:
            Index of the first line after the paragraph.

        """
        paragraph: list[str] = [lines[index].strip()]
        paragraph_indent: str = "    " if state.section.endswith(":") else ""
        index += 1
        while index < len(lines):
            following: str = lines[index]
            following_stripped: str = following.strip()
            following_indent: int = len(following) - len(following.lstrip())
            if (
                not following_stripped
                or self._doc_section_header(text=following_stripped)
                or self._numpy_section(lines=lines, index=index)
                or (following_indent >= Constants.docstring_block_indent)
                or following_stripped.startswith(
                    (">>>", "...", ".. ", "```", "~~~", ":"),
                )
                or (
                    state.section in Constants.field_sections
                    and ":" in following_stripped
                )
            ):
                break
            paragraph.append(following_stripped)
            index += 1
        result.extend(
            wrap(
                text=" ".join(paragraph),
                width=max(
                    Constants.min_fstring_text,
                    width - len(paragraph_indent),
                ),
                initial_indent=paragraph_indent,
                subsequent_indent=paragraph_indent,
                break_long_words=False,
                break_on_hyphens=False,
            ),
        )
        return index

    def _split_multiline_string(self, source: str) -> str:
        """Rewrite one long triple-quoted non-docstring without value changes.

        Args:
            source: Current Python source.

        Returns:
            Source with one multiline literal represented as adjacent literals.

        """
        offsets: tuple[int, ...] = self._line_offsets(source=source)
        for token in self._tokens(source=source):
            if (
                token.type != STRING
                or not any(
                    line in frozenset(self._long_lines(source=source))
                    for line in range(token.start[0], token.end[0] + 1)
                )
                or (
                    match := Constants.string_prefix_pattern.match(
                        string=token.string,
                    )
                )
                is None
                or (len(match.group(2)) != Constants.triple_quote_length)
                or (
                    (token.start[0], token.start[1])
                    in self._docstring_spans(source=source)
                )
                or ("f" in (prefix := match.group(1).lower()))
            ):
                continue
            if "b" in prefix:
                byte_edit: Edit | None = self._multiline_bytes_edit(
                    source=source,
                    token=token,
                    offsets=offsets,
                )
                if byte_edit is not None:
                    return self._apply_edit(source=source, edit=byte_edit)
                continue
            try:
                value: str = self._literal_string_value(
                    token_text=token.string,
                )
            except (SyntaxError, TypeError):
                continue
            source_line: str = source.splitlines()[token.start[0] - 1]
            leading: int = len(source_line) - len(source_line.lstrip())
            statement_indent: str = source_line[:leading]
            indent: str = statement_indent + " " * 4
            width: int = max(12, self.settings.line_length - len(indent) - 2)
            parts: tuple[str, ...] = self._split_multiline_value(
                value=value,
                width=width,
            )
            if len(parts) >= Constants.min_split_parts:
                return self._apply_edit(
                    source=source,
                    edit=Edit(
                        start=offsets[token.start[0] - 1] + token.start[1],
                        end=offsets[token.end[0] - 1] + token.end[1],
                        replacement="(\n"
                        + "\n".join(
                            f"""{indent}{self._quote(value=part, quote='"')}"""
                            for part in parts
                        )
                        + f"\n{statement_indent})",
                        reason="split-multiline-string",
                    ),
                )
        return source

    def _multiline_bytes_edit(
        self,
        source: str,
        token: TokenInfo,
        offsets: tuple[int, ...],
    ) -> Edit | None:
        """Represent a triple-quoted bytes literal as exact adjacent chunks.

        Args:
            source: Complete source text.
            token: Triple-quoted bytes token.
            offsets: Absolute line-start offsets.

        Returns:
            Edit replacing the literal, or ``None``.

        """
        try:
            expression: Expression = parse(source=token.string, mode="eval")
        except SyntaxError:
            return None
        if not isinstance(expression.body, Constant) or not isinstance(
            expression.body.value,
            bytes,
        ):
            return None
        value: bytes = expression.body.value
        source_line: str = source.splitlines()[token.start[0] - 1]
        statement_indent: str = source_line[
            : len(source_line) - len(source_line.lstrip())
        ]
        indent: str = statement_indent + " " * 8
        width: int = max(8, self.settings.line_length - len(indent) - 3)
        chunks: tuple[bytes, ...] = tuple(
            value[index : index + width]
            for index in range(0, len(value), width)
        )
        if len(chunks) < Constants.min_split_parts:
            return None
        return Edit(
            start=offsets[token.start[0] - 1] + token.start[1],
            end=offsets[token.end[0] - 1] + token.end[1],
            replacement="(\n"
            + "\n".join(f"{indent}{chunk!r}" for chunk in chunks)
            + f"\n{statement_indent})",
            reason="split-multiline-bytes",
        )

    def _split_multiline_value(
        self,
        value: str,
        width: int,
    ) -> tuple[str, ...]:
        """Split a multiline value into exactly reconstructable chunks.

        Args:
            value: Decoded multiline string value.
            width: Preferred maximum chunk width.

        Returns:
            Chunks whose concatenation equals ``value``.

        """
        chunks: list[str] = []
        for line in value.splitlines(keepends=True):
            newline_length: int = (
                2
                if line.endswith("\r\n")
                else int(line.endswith(("\n", "\r")))
            )
            body: str = line[:-newline_length] if newline_length else line
            ending: str = line[-newline_length:] if newline_length else ""
            body_parts: tuple[str, ...] = self._split_value(
                value=body,
                width=width,
            )
            if body_parts:
                chunks.extend(body_parts[:-1])
                chunks.append(body_parts[-1] + ending)
            elif ending:
                chunks.append(ending)
        if not chunks and value:
            return (value,)
        return tuple(chunks)

    def _split_long_string(self, source: str) -> str:
        """Split one plain long string into adjacent literals.

        Args:
            source: Current source.

        Returns:
            Source with at most one string literal split.

        """
        for token in self._tokens(source=source):
            if token.type != STRING or token.start[0] not in frozenset(
                self._long_lines(source=source),
            ):
                continue
            edit: Edit | None = self._string_edit(
                token=token,
                offsets=self._line_offsets(source=source),
            )
            if edit is not None:
                return self._apply_edit(source=source, edit=edit)
        return source

    def _string_edit(
        self,
        token: TokenInfo,
        offsets: tuple[int, ...],
    ) -> Edit | None:
        """Create a safe adjacent-literal edit when possible.

        Args:
            token: String token to consider.
            offsets: Absolute line-start offsets.

        Returns:
            Edit when the literal can be split safely, otherwise ``None``.

        """
        match: Match[str] | None = Constants.string_prefix_pattern.match(
            string=token.string,
        )
        if match is None:
            return None
        prefix: str = match.group(1)
        quote: str = match.group(2)
        if (
            "f" in prefix.lower()
            or "b" in prefix.lower()
            or len(quote) == Constants.triple_quote_length
        ):
            return None
        try:
            value: str = self._literal_string_value(token_text=token.string)
        except (SyntaxError, TypeError):
            return None
        indent: str = " " * token.start[1]
        parts: tuple[str, ...] = self._split_value(
            value=value,
            width=max(12, self.settings.line_length - len(indent) - 6),
        )
        if len(parts) < Constants.min_split_parts:
            return None
        return Edit(
            start=offsets[token.start[0] - 1] + token.start[1],
            end=offsets[token.end[0] - 1] + token.end[1],
            replacement="(\n"
            + "\n".join(
                f"{indent}    {self._quote(value=part, quote=quote)}"
                for part in parts
            )
            + f"\n{indent})",
            reason="split-string",
        )

    def _split_long_fstring(self, source: str) -> str:
        """Split static text inside a long f-string without changing its AST.

        Python 3.13 exposes f-string components as dedicated tokens. The
        rewrite uses those boundaries, supports conversions and nested format
        specifications, and wraps adjacent f-strings in parentheses so the
        physical newline is legal implicit continuation.

        Args:
            source: Current source.

        Returns:
            Source with one f-string divided into adjacent f-strings.

        """
        tokens: tuple[TokenInfo, ...] = self._tokens(source=source)
        offsets: tuple[int, ...] = self._line_offsets(source=source)
        long_lines: frozenset[int] = frozenset(self._long_lines(source=source))
        stack: list[tuple[int, TokenInfo]] = []
        ranges: list[tuple[int, int, TokenInfo]] = []
        for index, token in enumerate(iterable=tokens):
            if token.type == FSTRING_START:
                stack.append((index, token))
            elif token.type == FSTRING_END and stack:
                start_index, start_token = stack.pop()
                ranges.append((start_index, index, start_token))
        for start_index, end_index, start_token in ranges:
            candidate: str | None = self._split_fstring_range(
                scan=TokenScan(
                    source=source,
                    tokens=tokens,
                    offsets=offsets,
                    long_lines=long_lines,
                ),
                start_index=start_index,
                end_index=end_index,
                start_token=start_token,
            )
            if candidate is not None:
                return candidate
        return source

    def _split_fstring_range(
        self,
        scan: TokenScan,
        start_index: int,
        end_index: int,
        start_token: TokenInfo,
    ) -> str | None:
        """Build one adjacent-f-string split for a single token range.

        Args:
            scan: Shared token-stream state.
            start_index: Index of the opening FSTRING_START token.
            end_index: Index of the closing FSTRING_END token.
            start_token: Opening token of the f-string.

        Returns:
            Rewritten source, or ``None`` when no split applies.

        """
        if "r" in start_token.string.lower():
            return None
        match: Match[str] | None = Constants.string_prefix_pattern.match(
            string=start_token.string,
        )
        if match is None or len(match.group(2)) != 1:
            return None
        quote: str = match.group(2)
        prefix: str = match.group(1)
        source: str = scan.source
        for token in scan.tokens[start_index + 1 : end_index]:
            if (
                token.type != FSTRING_MIDDLE
                or token.start[0] not in scan.long_lines
            ):
                continue
            boundary: int = self._fstring_boundary(text=token.string)
            if boundary <= 0:
                continue
            absolute: int = (
                scan.offsets[token.start[0] - 1] + token.start[1] + boundary
            )
            literal_start: int = (
                scan.offsets[start_token.start[0] - 1] + start_token.start[1]
            )
            end_token: TokenInfo = scan.tokens[end_index]
            literal_end: int = (
                scan.offsets[end_token.end[0] - 1] + end_token.end[1]
            )
            line_text: str = source.splitlines()[start_token.start[0] - 1]
            leading: int = len(line_text) - len(line_text.lstrip())
            indent: str = line_text[:leading]
            continuation: str = indent + " " * 4
            left: str = source[literal_start:absolute] + quote
            right: str = prefix + quote + source[absolute:literal_end]
            replacement: str = (
                f"(\n{continuation}{left}\n{continuation}{right}\n{indent})"
            )
            candidate: str = (
                source[:literal_start] + replacement + source[literal_end:]
            )
            if self._same_ast(before=source, after=candidate):
                return candidate
        return None

    def _fstring_boundary(self, text: str) -> int:
        """Choose a static f-string split boundary.

        Args:
            text: One FSTRING_MIDDLE token value.

        Returns:
            Character offset after suitable whitespace, or ``-1``.

        """
        if len(text) < Constants.min_fstring_text:
            return -1
        target: int = min(len(text) - 1, self.settings.line_length // 2)
        candidates: tuple[int, ...] = tuple(
            point + 1
            for point in (
                text.rfind(" ", 1, target + 1),
                text.find(" ", target),
            )
            if point > 0
        )
        return (
            min(candidates, key=lambda point: abs(point - target))
            if candidates
            else -1
        )

    def _parenthesize_from_import(self, source: str) -> str:
        """Add import-list parentheses to a long ``from`` import.

        Args:
            source: Current source.

        Returns:
            Rewritten source when applicable.

        """
        return self._rewrite_long_lines(
            source=source,
            transformer=self._from_import_line,
        )

    def _parenthesize_with_statement(self, source: str) -> str:
        """Parenthesize the item list of a long ``with`` statement.

        Args:
            source: Current source.

        Returns:
            Rewritten source when applicable.

        """
        return self._rewrite_long_lines(
            source=source,
            transformer=self._with_line,
        )

    def _parenthesize_condition(self, source: str) -> str:
        """Parenthesize a long ``if``, ``elif``, or ``while`` condition.

        Args:
            source: Current source.

        Returns:
            Rewritten source when applicable.

        """
        return self._rewrite_long_lines(
            source=source,
            transformer=self._condition_line,
        )

    def _parenthesize_statement(self, source: str) -> str:
        """Wrap a long simple-statement expression for Ruff.

        Args:
            source: Current source.

        Returns:
            Rewritten source when applicable.

        """
        return self._rewrite_long_lines(
            source=source,
            transformer=self._statement_line,
        )

    def _parenthesize_annotation(self, source: str) -> str:
        """Parenthesize a long standalone variable annotation.

        Args:
            source: Current source.

        Returns:
            Rewritten source when applicable.

        """
        return self._rewrite_long_lines(
            source=source,
            transformer=self._annotation_line,
        )

    def _parenthesize_decorator(self, source: str) -> str:
        """Parenthesize a long decorator expression.

        Args:
            source: Current source.

        Returns:
            Rewritten source when applicable.

        """
        return self._rewrite_long_lines(
            source=source,
            transformer=self._decorator_line,
        )

    def _parenthesize_ast_expression(self, source: str) -> str:
        """Wrap the widest suitable long-line AST expression.

        This catches binary, boolean and comparison expressions,
        comprehensions, calls, subscripts, lambdas, conditionals and similar
        grammar without maintaining a second Python pretty-printer.

        Args:
            source: Current source.

        Returns:
            Source with one expression parenthesized when safe.

        """
        try:
            tree: AST = parse(source=source)
        except SyntaxError:
            return source
        offsets: tuple[int, ...] = self._line_offsets(source=source)
        long_lines: frozenset[int] = frozenset(self._long_lines(source=source))
        candidates: list[tuple[int, int, int]] = []
        for node in walk(node=tree):
            if not isinstance(node, expr) or isinstance(node, Constant):
                continue
            line: int | None = getattr(node, "lineno", None)
            end_line: int | None = getattr(node, "end_lineno", None)
            column: int | None = getattr(node, "col_offset", None)
            end_column: int | None = getattr(node, "end_col_offset", None)
            if (
                line is None
                or end_line is None
                or column is None
                or (end_column is None)
                or (line != end_line)
                or (line not in long_lines)
            ):
                continue
            start: int = offsets[line - 1] + column
            end: int = offsets[end_line - 1] + end_column
            if end - start < self.settings.line_length // 2:
                continue
            if self._span_is_parenthesized(
                source=source,
                start=start,
                end=end,
            ):
                continue
            candidates.append((-(end - start), start, end))
        for _, start, end in sorted(candidates):
            candidate: str = (
                source[:start] + "(" + source[start:end] + ")" + source[end:]
            )
            if self._same_ast(before=source, after=candidate):
                return candidate
        return source

    def _break_chain(self, source: str) -> str:
        """Parenthesize and vertically split one long dotted chain.

        Args:
            source: Current source.

        Returns:
            Source with one dotted chain rewritten.

        """
        lines: list[str] = source.splitlines(keepends=True)
        for line_number in self._long_lines(source=source):
            index: int = line_number - 1
            line: str = lines[index]
            body: str = line.rstrip("\r\n")
            newline: str = line[len(body) :]
            stripped: str = body.lstrip()
            indent: str = body[: len(body) - len(stripped)]
            if stripped.count(
                ".",
            ) < Constants.min_chain_dots or stripped.startswith("#"):
                continue
            split_at: int = self._chain_start(text=stripped)
            if split_at < 0:
                continue
            prefix: str = stripped[:split_at]
            chain: str = stripped[split_at:].strip()
            if self._already_wrapped(text=chain):
                continue
            points: tuple[int, ...] = self._top_level_dots(text=chain)
            if not points:
                continue
            pieces: list[str] = []
            start: int = 0
            for point in points:
                pieces.append(chain[start:point])
                start = point
            pieces.append(chain[start:])
            continuation: str = indent + "    "
            lines[index] = (
                f"{indent}{prefix}(\n"
                + "\n".join(f"{continuation}{piece}" for piece in pieces)
                + f"\n{indent}){newline}"
            )
            candidate: str = "".join(lines)
            if self._same_ast(before=source, after=candidate):
                return candidate
            lines[index] = line
        return source

    def _break_with_backslash(self, source: str) -> str:
        """Use explicit continuation only as the final fallback.

        Args:
            source: Current source.

        Returns:
            Source with one safe token boundary explicitly continued.

        """
        lines: list[str] = source.splitlines(keepends=True)
        for line_number in self._long_lines(source=source):
            index: int = line_number - 1
            line: str = lines[index]
            body: str = line.rstrip("\r\n")
            newline: str = line[len(body) :]
            stripped: str = body.lstrip()
            indent: str = body[: len(body) - len(stripped)]
            for boundary in self._fallback_boundaries(text=stripped):
                left: str = stripped[:boundary].rstrip()
                right: str = stripped[boundary:].lstrip()
                if not left or not right:
                    continue
                lines[index] = (
                    f"{indent}{left} \\\n{indent}    {right}{newline}"
                )
                candidate: str = "".join(lines)
                if self._same_ast(before=source, after=candidate):
                    return candidate
            lines[index] = line
        return source

    def _fallback_boundaries(self, text: str) -> tuple[int, ...]:
        """Return preferred explicit-continuation token boundaries.

        Args:
            text: One stripped source line.

        Returns:
            Candidate character offsets, best first.

        """
        offsets: tuple[int, ...] = self._line_offsets(source=text)
        candidates: list[int] = []
        for token in self._tokens(source=text):
            if token.type == OP and token.string in {
                ".",
                ",",
                "+",
                "-",
                "*",
                "/",
                "//",
                "%",
                "|",
                "&",
                "^",
                "==",
                "!=",
                "<",
                ">",
                "<=",
                ">=",
                ":=",
            }:
                point: int = offsets[token.start[0] - 1] + token.start[1]
                candidates.append(point + 1 if token.string == "," else point)
            elif token.type == NAME and token.string in {
                "and",
                "or",
                "in",
                "is",
            }:
                candidates.append(offsets[token.start[0] - 1] + token.start[1])
        return tuple(
            sorted(
                set(candidates),
                key=lambda value: (
                    abs(value - self.settings.line_length),
                    -value,
                ),
            ),
        )

    def _rewrite_long_lines(
        self,
        source: str,
        transformer: LineTransformer,
    ) -> str:
        """Try a one-line grammar transformation on each long line.

        Args:
            source: Current source.
            transformer: Stripped-line transformation callback.

        Returns:
            First AST-equivalent candidate, or the original source.

        """
        lines: list[str] = source.splitlines(keepends=True)
        for line_number in self._long_lines(source=source):
            index: int = line_number - 1
            line: str = lines[index]
            body: str = line.rstrip("\r\n")
            newline: str = line[len(body) :]
            stripped: str = body.lstrip()
            indent: str = body[: len(body) - len(stripped)]
            replacement: str | None = transformer(stripped)
            if replacement is None:
                continue
            lines[index] = f"{indent}{replacement}{newline}"
            candidate: str = "".join(lines)
            if self._same_ast(before=source, after=candidate):
                return candidate
            lines[index] = line
        return source

    def _ruff_format_text(self, source: str, path: Path) -> str:
        """Format source through Ruff's stdin interface.

        Args:
            source: Source to format.
            path: Original path, used for Ruff configuration discovery.

        Returns:
            Ruff-formatted source, or input when Ruff is unavailable/fails.

        """
        try:
            completed: CompletedProcess[str] = _run(
                args=[
                    *self.settings.ruff_command,
                    "format",
                    "--stdin-filename",
                    str(object=path),
                    "-",
                ],
                input_text=source,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError:
            return source
        return completed.stdout if completed.returncode == 0 else source

    def _long_lines(self, source: str) -> tuple[int, ...]:
        """Find physical source lines exceeding the configured width.

        Args:
            source: Python source.

        Returns:
            One-based long line numbers.

        """
        protected: frozenset[int] = self._protected_lines(source=source)
        lines: list[str] = source.splitlines()
        physical: set[int] = {
            number
            for number, line in enumerate(iterable=lines, start=1)
            if len(line.expandtabs(tabsize=Constants.tab_size))
            > self.settings.line_length
            and (not self._ignorable_long_line(line=line))
            and (number not in protected)
        }
        physical.update(
            line
            for line in self._seed_e501_lines
            if 1 <= line <= len(lines) and line not in protected
        )
        return tuple(sorted(physical))

    def _ignorable_long_line(self, line: str) -> bool:
        """Identify lines Ruff's E501 intentionally exempts.

        Mirrors Ruff: a single unbroken word, a line ending in a URL that
        starts inside the width, and a line whose trailing pragma comment
        starts inside the width are never reported.

        Args:
            line: Physical source line.

        Returns:
            Whether the line should be left alone.

        """
        stripped: str = line.strip()
        if not stripped or len(stripped.split()) == 1:
            return True
        if (
            stripped.removeprefix("#")
            .lstrip()
            .startswith(Constants.directive_names)
        ):
            return True
        last_word: str = stripped.rsplit(maxsplit=1)[-1]
        limit: int = self.settings.line_length
        if last_word.startswith(("http://", "https://")):
            url_start: int = len(line.rstrip()) - len(last_word)
            if (
                len(line[:url_start].expandtabs(tabsize=Constants.tab_size))
                < limit
            ):
                return True
        pragma: Match[str] | None = Constants.pragma_pattern.search(
            string=line,
        )
        return (
            pragma is not None
            and len(
                line[: pragma.start()].expandtabs(tabsize=Constants.tab_size),
            )
            < limit
        )


class LineTransformer(Protocol):
    """Transform one indentation-free physical Python line."""

    def __call__(self, line: str, /) -> str | None:
        """Return a replacement line or ``None``.

        Args:
            line: Source line without indentation.

        Returns:
            Replacement line or ``None``.

        """
        ...
