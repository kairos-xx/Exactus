# Copyright (c) 2026 João Lopes.
"""Conservatively remove unnecessary JavaScript parentheses and braces."""

from __future__ import annotations

from asyncio import run as run_async
from asyncio.subprocess import PIPE, Process, create_subprocess_exec
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from os import cpu_count
from re import Pattern
from re import compile as compile_pattern
from shutil import which
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import TYPE_CHECKING, Final, Self, final

from exactus.packages.steps import trace
from exactus.tools.common.cli import is_reports_tree
from exactus.tools.common.runtime import LaneProgress

if TYPE_CHECKING:
    from pathlib import Path
type Span = tuple[int, int]


@final
class Constants:
    """Describe Constants.

    Attributes:
    delimiter_pair_length: Public value used by this data structure.
    exponent_precedence: Public value used by this data structure.

    """

    delimiter_pair_length: Final[int] = 2
    exponent_precedence: Final[int] = 14


@dataclass(frozen=True, slots=True)
class Replacement:
    """Describe Replacement.

    Attributes:
    start: Public value used by this data structure.
    end: Public value used by this data structure.
    text: Public value used by this data structure.
    kind: Public value used by this data structure.

    """

    start: int
    end: int
    text: str
    kind: str

    @property
    def characters_removed(self) -> int:
        """Characters removed.

        Returns:
            The resulting value.

        """
        return max(0, self.end - self.start - len(self.text))


@dataclass(frozen=True, slots=True)
class TransformationMetrics:
    """Summarize transformations accepted for one source.

    Attributes:
    total: Public value used by this data structure.
    by_kind: Public value used by this data structure.
    characters_removed: Public value used by this data structure.
    parentheses_removed: Public value used by this data structure.
    braces_removed: Public value used by this data structure.

    """

    total: int
    by_kind: tuple[tuple[str, int], ...]
    characters_removed: int
    parentheses_removed: int
    braces_removed: int

    @classmethod
    def from_replacements(
        cls,
        *,
        replacements: tuple[Replacement, ...],
    ) -> Self:
        """From replacements.

        Args:
            replacements: Replacements.

        Returns:
            The resulting value.

        """
        counts: Counter[str] = Counter(
            replacement.kind for replacement in replacements
        )
        parentheses_removed: int = (
            sum(
                replacement.end - replacement.start - len(replacement.text)
                >= Constants.delimiter_pair_length
                and "parenthes" in replacement.kind
                for replacement in replacements
            )
            * Constants.delimiter_pair_length
        )
        braces_removed: int = (
            sum(
                replacement.end - replacement.start - len(replacement.text)
                >= Constants.delimiter_pair_length
                and (
                    "braces" in replacement.kind
                    or replacement.kind == "arrow-expression-body"
                )
                for replacement in replacements
            )
            * Constants.delimiter_pair_length
        )
        return cls(
            total=len(replacements),
            by_kind=tuple(sorted(counts.items())),
            characters_removed=sum(
                replacement.characters_removed for replacement in replacements
            ),
            parentheses_removed=parentheses_removed,
            braces_removed=braces_removed,
        )

    def count(self, *, kind: str) -> int:
        """Count.

        Args:
            kind: Kind.

        Returns:
            The resulting value.

        """
        return dict(self.by_kind).get(kind, 0)


@dataclass(frozen=True, slots=True)
class SourceMetrics:
    """Describe measurable source-size changes.

    Attributes:
    bytes_before: Public value used by this data structure.
    bytes_after: Public value used by this data structure.
    characters_before: Public value used by this data structure.
    characters_after: Public value used by this data structure.
    lines_before: Public value used by this data structure.
    lines_after: Public value used by this data structure.
    blank_lines_before: Public value used by this data structure.
    blank_lines_after: Public value used by this data structure.

    """

    bytes_before: int
    bytes_after: int
    characters_before: int
    characters_after: int
    lines_before: int
    lines_after: int
    blank_lines_before: int
    blank_lines_after: int

    @classmethod
    def compare(cls, *, before: str, after: str) -> Self:
        """Compare.

        Args:
            before: Before.
            after: After.

        Returns:
            The resulting value.

        """
        before_lines: tuple[str, ...] = tuple(before.splitlines())
        after_lines: tuple[str, ...] = tuple(after.splitlines())
        return cls(
            bytes_before=len(before.encode(encoding="utf-8")),
            bytes_after=len(after.encode(encoding="utf-8")),
            characters_before=len(before),
            characters_after=len(after),
            lines_before=len(before_lines),
            lines_after=len(after_lines),
            blank_lines_before=sum(not line.strip() for line in before_lines),
            blank_lines_after=sum(not line.strip() for line in after_lines),
        )

    @property
    def bytes_removed(self) -> int:
        """Bytes removed.

        Returns:
            The resulting value.

        """
        return self.bytes_before - self.bytes_after

    @property
    def characters_removed(self) -> int:
        """Characters removed.

        Returns:
            The resulting value.

        """
        return self.characters_before - self.characters_after

    @property
    def lines_removed(self) -> int:
        """Lines removed.

        Returns:
            The resulting value.

        """
        return self.lines_before - self.lines_after

    @property
    def blank_lines_removed(self) -> int:
        """Blank lines removed.

        Returns:
            The resulting value.

        """
        return self.blank_lines_before - self.blank_lines_after


@dataclass(frozen=True, slots=True)
class ValidationMetrics:
    """Describe JavaScript syntax validation for one result.

    Attributes:
    requested: Public value used by this data structure.
    available: Public value used by this data structure.
    performed: Public value used by this data structure.
    passed: Public value used by this data structure.
    engine: Public value used by this data structure.

    """

    requested: bool
    available: bool
    performed: bool
    passed: bool | None
    engine: str | None


@dataclass(frozen=True, slots=True)
class TextResult:
    """Describe one in-memory simplification.

    Attributes:
    source: Public value used by this data structure.
    changed: Public value used by this data structure.
    transformations: Public value used by this data structure.
    source_metrics: Public value used by this data structure.
    elapsed_seconds: Public value used by this data structure.
    replacements: Public value used by this data structure.

    """

    source: str
    changed: bool
    transformations: TransformationMetrics
    source_metrics: SourceMetrics
    elapsed_seconds: float
    replacements: tuple[Replacement, ...] = ()


@dataclass(frozen=True, slots=True)
class FileResult:
    """Describe simplification and metadata for one JavaScript file.

    Attributes:
    path: Public value used by this data structure.
    changed: Public value used by this data structure.
    written: Public value used by this data structure.
    backup_path: Public value used by this data structure.
    transformations: Public value used by this data structure.
    source_metrics: Public value used by this data structure.
    validation: Public value used by this data structure.
    elapsed_seconds: Public value used by this data structure.
    replacements: Public value used by this data structure.

    """

    path: Path
    changed: bool
    written: bool
    backup_path: Path | None
    transformations: TransformationMetrics
    source_metrics: SourceMetrics
    validation: ValidationMetrics
    elapsed_seconds: float
    replacements: tuple[Replacement, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionMetrics:
    """Aggregate immutable metrics for a multi-file execution.

    Attributes:
    files: Public value used by this data structure.
    elapsed_seconds: Public value used by this data structure.

    """

    files: tuple[FileResult, ...]
    elapsed_seconds: float

    @property
    def files_total(self) -> int:
        """Files total.

        Returns:
            The resulting value.

        """
        return len(self.files)

    @property
    def files_changed(self) -> int:
        """Files changed.

        Returns:
            The resulting value.

        """
        return sum(result.changed for result in self.files)

    @property
    def files_written(self) -> int:
        """Files written.

        Returns:
            The resulting value.

        """
        return sum(result.written for result in self.files)

    @property
    def transformations(self) -> int:
        """Transformations.

        Returns:
            The resulting value.

        """
        return sum(result.transformations.total for result in self.files)

    @property
    def transformations_by_kind(self) -> tuple[tuple[str, int], ...]:
        """Transformations by kind.

        Returns:
            The resulting value.

        """
        counts: Counter[str] = Counter()
        for result in self.files:
            counts.update(dict(result.transformations.by_kind))
        return tuple(sorted(counts.items()))

    @property
    def bytes_removed(self) -> int:
        """Bytes removed.

        Returns:
            The resulting value.

        """
        return sum(
            result.source_metrics.bytes_removed for result in self.files
        )

    @property
    def characters_removed(self) -> int:
        """Characters removed.

        Returns:
            The resulting value.

        """
        return sum(
            result.source_metrics.characters_removed for result in self.files
        )

    @property
    def lines_removed(self) -> int:
        """Lines removed.

        Returns:
            The resulting value.

        """
        return sum(
            result.source_metrics.lines_removed for result in self.files
        )

    @property
    def blank_lines_removed(self) -> int:
        """Blank lines removed.

        Returns:
            The resulting value.

        """
        return sum(
            result.source_metrics.blank_lines_removed for result in self.files
        )


class JavaScriptDelimiterSimplifier:
    """Remove conservative subsets of unnecessary JavaScript delimiters.

    Attributes:
    EXTENSIONS: Public value used by this data structure.
    DEFAULT_EXCLUDES: Public value used by this data structure.
    IDENTIFIER: Public value used by this data structure.
    ARROW_PARAMETER: Public value used by this data structure.
    SIMPLE_PAREN: Public value used by this data structure.
    CONTROL_HEADER: Public value used by this data structure.
    DO_BLOCK: Public value used by this data structure.
    ELSE_BLOCK: Public value used by this data structure.
    UNSAFE_SINGLE_STATEMENT: Public value used by this data structure.

    """

    EXTENSIONS: Final[frozenset[str]] = frozenset({".js", ".mjs", ".cjs"})
    DEFAULT_EXCLUDES: Final[tuple[str, ...]] = (
        "node_modules",
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        "EXACTUS_RESULTS",
        "dist",
        "build",
        ".build-cache",
        "coverage",
        "exactus/bundle",
    )
    IDENTIFIER: Final[str] = "[A-Za-z_$][\\w$]*"
    ARROW_PARAMETER: Final[Pattern[str]] = compile_pattern(
        pattern=f"(?:(async)\\s+)?\\(\\s*({IDENTIFIER})\\s*\\)(\\s*=>)",
    )
    SIMPLE_PAREN: Final[Pattern[str]] = compile_pattern(
        pattern="".join(
            (
                "\\(\\s*(",
                f"(?:{IDENTIFIER}(?:\\s*(?:\\?\\.|\\.)\\s*{IDENTIFIER})*)",
                "|(?:true|false|null|this|super)",
                "|(?:\\d+(?:\\.\\d+)?)",
                "|(?:'(?:\\\\.|[^'\\\\])*')",
                '|(?:"(?:\\\\.|[^"\\\\])*")',
                ")\\s*\\)",
            ),
        ),
    )
    CONTROL_HEADER: Final[Pattern[str]] = compile_pattern(
        pattern="\\b(if|for|while|with)\\s*\\(",
    )
    DO_BLOCK: Final[Pattern[str]] = compile_pattern(pattern="\\bdo\\s*\\{")
    ELSE_BLOCK: Final[Pattern[str]] = compile_pattern(pattern="\\belse\\s*\\{")
    UNSAFE_SINGLE_STATEMENT: Final[Pattern[str]] = compile_pattern(
        pattern=(
            "^\\s*(?:(?:const|let|class|function)\\b|if\\b|(?:async\\s+)?funct"
            "ion\\b)"
        ),
    )

    def __init__(
        self,
        *,
        validate: bool = True,
        remove_control_braces: bool = True,
    ) -> None:
        """Init  .

        Args:
            validate: Validate.
            remove_control_braces: Remove control braces.

        """
        self._validate: bool = validate
        self._remove_control_braces: bool = remove_control_braces
        self._node: str | None = which(cmd="node")

    @classmethod
    def protected_spans(cls, *, source: str) -> tuple[Span, ...]:
        """Return string, comment, template, and regular-expression spans.

        Args:
            source: JavaScript source text.

        Returns:
            Half-open spans containing non-code lexical content.

        """
        return cls._protected_spans(source=source)

    @classmethod
    def inside_protected(
        cls,
        *,
        index: int,
        protected: tuple[Span, ...],
    ) -> bool:
        """Return whether an offset belongs to protected lexical content.

        Args:
            index: Source offset to inspect.
            protected: Protected lexical spans.

        Returns:
            Whether the offset is inside a protected span.

        """
        return cls._inside_protected(index=index, protected=protected)

    def simplify_text(self, *, source: str) -> TextResult:
        """Simplify text.

        Args:
            source: Source.

        Returns:
            The resulting value.

        """
        started: float = perf_counter()
        candidate: str
        replacements: tuple[Replacement, ...]
        candidate, replacements = self._simplify(source=source)
        return TextResult(
            source=candidate,
            changed=candidate != source,
            transformations=TransformationMetrics.from_replacements(
                replacements=replacements,
            ),
            source_metrics=SourceMetrics.compare(
                before=source,
                after=candidate,
            ),
            elapsed_seconds=perf_counter() - started,
            replacements=replacements,
        )

    def simplify_file(
        self,
        *,
        path: Path,
        write: bool = True,
        backup: bool = False,
    ) -> FileResult:
        """Simplify file.

        Args:
            path: Path.
            write: Write.
            backup: Backup.

        Returns:
            The resulting value.

        """
        started: float = perf_counter()
        source: str = path.read_text(encoding="utf-8")
        text_result: TextResult = self.simplify_text(source=source)
        validation: ValidationMetrics = self._validation_metrics(
            path=path,
            source=text_result.source,
            changed=text_result.changed,
        )
        backup_path: Path | None = None
        if text_result.changed and write:
            if backup:
                backup_path = path.with_name(name=path.name + ".bak")
                _ = backup_path.write_text(data=source, encoding="utf-8")
            _ = path.write_text(data=text_result.source, encoding="utf-8")
        return FileResult(
            path=path,
            changed=text_result.changed,
            written=text_result.changed and write,
            backup_path=backup_path,
            transformations=text_result.transformations,
            source_metrics=text_result.source_metrics,
            validation=validation,
            elapsed_seconds=perf_counter() - started,
            replacements=text_result.replacements,
        )

    def simplify_paths(
        self,
        *,
        roots: tuple[Path, ...],
        excludes: tuple[str, ...] = DEFAULT_EXCLUDES,
        write: bool = True,
        backup: bool = False,
    ) -> ExecutionMetrics:
        """Simplify paths.

        Args:
            roots: Roots.
            excludes: Excludes.
            write: Write.
            backup: Backup.

        Returns:
            The resulting value.

        """
        started: float = perf_counter()
        files: tuple[Path, ...] = JavaScriptFiles(
            roots=roots,
            excludes=excludes,
        ).collect()
        results: tuple[FileResult, ...] = tuple(
            self.simplify_file(path=path, write=write, backup=backup)
            for path in files
        )
        return ExecutionMetrics(
            files=results,
            elapsed_seconds=perf_counter() - started,
        )

    @classmethod
    def _arrow_parameter_replacements(
        cls,
        *,
        source: str,
        protected: tuple[Span, ...],
    ) -> list[Replacement]:
        """Arrow parameter replacements.

        Args:
            source: Source.
            protected: Protected.

        Returns:
            The resulting value.

        """
        replacements: list[Replacement] = []
        for match in cls.ARROW_PARAMETER.finditer(string=source):
            if cls._overlaps_protected(span=match.span(), protected=protected):
                continue
            replacements.append(
                Replacement(
                    start=match.start(),
                    end=match.end(),
                    text=f"async {match.group(2)}{match.group(3)}"
                    if match.group(1)
                    else f"{match.group(2)}{match.group(3)}",
                    kind="arrow-parameter-parentheses",
                ),
            )
        return replacements

    @classmethod
    def _arrow_body_replacements(
        cls,
        *,
        source: str,
        protected: tuple[Span, ...],
    ) -> list[Replacement]:
        """Arrow body replacements.

        Args:
            source: Source.
            protected: Protected.

        Returns:
            The resulting value.

        """
        replacements: list[Replacement] = []
        index: int = 0
        length: int = len(source)
        while (arrow := source.find("=>", index)) >= 0:
            index = arrow + 2
            if cls._inside_protected(index=arrow, protected=protected):
                continue
            body_start: int = cls._skip_space(source=source, index=index)
            if body_start >= length or source[body_start] != "{":
                continue
            body_end: int | None = cls._matching_delimiter(
                source=source,
                opening=body_start,
                opener="{",
                closer="}",
                protected=protected,
            )
            if body_end is None:
                continue
            body: str = source[body_start + 1 : body_end]
            expression: str | None = cls._single_return_expression(body=body)
            if expression is None:
                continue
            stripped: str = expression.strip()
            if not stripped:
                continue
            replacement: str = (
                f"({stripped})" if stripped.startswith("{") else stripped
            )
            replacements.append(
                Replacement(
                    start=body_start,
                    end=body_end + 1,
                    text=replacement,
                    kind="arrow-expression-body",
                ),
            )
            index = body_end + 1
        return replacements

    @classmethod
    def _single_return_expression(cls, *, body: str) -> str | None:
        """Single return expression.

        Args:
            body: Body.

        Returns:
            The resulting value.

        """
        protected: tuple[Span, ...] = cls._protected_spans(source=body)
        if cls._contains_comment(source=body):
            return None
        index: int = cls._skip_space_and_comments(
            source=body,
            index=0,
            protected=protected,
        )
        if not body.startswith("return", index):
            return None
        after_return: int = index + len("return")
        if after_return < len(body) and (
            body[after_return].isalnum() or body[after_return] in "_$"
        ):
            return None
        if after_return < len(body) and body[after_return] in "\r\n":
            return None
        expression_start: int = cls._skip_space(
            source=body,
            index=after_return,
        )
        semicolon: int | None = cls._top_level_semicolon(
            source=body,
            start=expression_start,
            protected=protected,
        )
        expression_end: int = len(body) if semicolon is None else semicolon
        tail_start: int = (
            expression_end if semicolon is None else semicolon + 1
        )
        tail: int = cls._skip_space_and_comments(
            source=body,
            index=tail_start,
            protected=protected,
        )
        if tail != len(body):
            return None
        expression: str = body[expression_start:expression_end].strip()
        return expression or None

    @classmethod
    def _expression_parenthesis_replacements(
        cls,
        *,
        source: str,
        protected: tuple[Span, ...],
    ) -> list[Replacement]:
        """Expression parenthesis replacements.

        Args:
            source: Source.
            protected: Protected.

        Returns:
            The resulting value.

        """
        replacements: list[Replacement] = []
        for opening, char in enumerate(iterable=source):
            if char != "(" or cls._inside_protected(
                index=opening,
                protected=protected,
            ):
                continue
            closing: int | None = cls._matching_delimiter(
                source=source,
                opening=opening,
                opener="(",
                closer=")",
                protected=protected,
            )
            if closing is None:
                continue
            inner: str = source[opening + 1 : closing].strip()
            if not inner or cls._parenthesized_expression_must_stay(
                source=source,
                opening=opening,
                closing=closing,
                inner=inner,
            ):
                continue
            replacements.append(
                Replacement(
                    start=opening,
                    end=closing + 1,
                    text=source[opening + 1 : closing],
                    kind="expression-parentheses",
                ),
            )
        return replacements

    @classmethod
    def _parenthesized_expression_must_stay(
        cls,
        *,
        source: str,
        opening: int,
        closing: int,
        inner: str,
    ) -> bool:
        """Parenthesized expression must stay.

        Args:
            source: Source.
            opening: Opening.
            closing: Closing.
            inner: Inner.

        Returns:
            The resulting value.

        """
        if cls._preceded_by_block_comment(source=source, index=opening):
            return True
        previous: int = cls._previous_non_space(
            source=source,
            index=opening - 1,
        )
        following: int = cls._skip_space(source=source, index=closing + 1)
        prefix: str = source[max(0, opening - 32) : opening]
        if (
            compile_pattern(pattern="(?:return|throw|yield)\\s*$").search(
                string=prefix,
            )
            is not None
            and "\n" in source[opening + 1 : closing]
        ):
            return True
        if cls._grouping_syntax_requires_parentheses(
            source=source,
            inner=inner,
            previous=previous,
            following=following,
            prefix=prefix,
        ):
            return True
        following_char: str = (
            source[following] if following < len(source) else ""
        )
        if (
            following < len(source)
            and (
                source[following : following + Constants.delimiter_pair_length]
                == "?."
                or following_char == "`"
            )
            and not cls._is_primary_like_expression(source=inner)
        ):
            return True
        contextual: bool | None = cls._grouping_context_requirement(
            source=source,
            opening=opening,
            inner=inner,
            following_char=following_char,
        )
        return (
            contextual
            if contextual is not None
            else cls._precedence_requires_parentheses(
                source=source,
                opening=opening,
                closing=closing,
                inner=inner,
            )
        )

    @classmethod
    def _grouping_syntax_requires_parentheses(
        cls,
        *,
        source: str,
        inner: str,
        previous: int,
        following: int,
        prefix: str,
    ) -> bool:
        """Determine whether grouping syntax requires parentheses.

        Args:
            source: Source.
            inner: Inner.
            previous: Previous.
            following: Following.
            prefix: Prefix.

        Returns:
            The resulting value.

        """
        control_header: bool = (
            compile_pattern(
                pattern="(?:if|for|while|with|switch|catch)\\s*$",
            ).search(string=prefix)
            is not None
        )
        arrow_parameter: bool = source[following:].lstrip().startswith("=>")
        call_syntax: bool = cls._looks_like_call_parentheses(
            source=source,
            previous=previous,
        )
        condition_assignment: bool = (
            previous >= 0
            and source[previous] in "(;!"
            and cls._weakest_precedence(source=inner) == 1
            and compile_pattern(
                pattern=r"(?:if|while|for|do|switch|with)\s*\([^()]*$",
            ).search(string=source[max(0, previous - 48) : previous + 1])
            is not None
        )
        optional_chain_boundary: bool = "?." in inner and (
            source[following : following + Constants.delimiter_pair_length]
            == "?."
            or (following < len(source) and source[following] in ".(")
        )
        declaration_expression: bool = inner.startswith(
            ("function ", "function(", "class ", "class{"),
        )
        object_arrow: bool = (
            inner.startswith("{")
            and compile_pattern(pattern="=>\\s*$").search(string=prefix)
            is not None
        )
        return any(
            (
                control_header,
                arrow_parameter,
                call_syntax,
                condition_assignment,
                cls._has_top_level_comma(source=inner),
                optional_chain_boundary,
                declaration_expression,
                object_arrow,
            ),
        )

    @classmethod
    def _grouping_context_requirement(
        cls,
        *,
        source: str,
        opening: int,
        inner: str,
        following_char: str,
    ) -> bool | None:
        """Determine the grouping context requirement.

        Args:
            source: Source.
            opening: Opening.
            inner: Inner.
            following_char: Following char.

        Returns:
            The resulting value.

        """
        previous: int = cls._previous_non_space(
            source=source,
            index=opening - 1,
        )
        previous_char: str = source[previous] if previous >= 0 else ""
        prefix: str = source[max(0, opening - 32) : opening]
        if (previous_char, following_char) in {("(", ")"), ("[", "]")}:
            return False
        terminal_context: bool = following_char in {";", ",", "", "\n", "\r"}
        expression_boundary: bool = (
            compile_pattern(pattern="(?:return|throw)\\s*$").search(
                string=prefix,
            )
            is not None
            or cls._preceded_by_assignment(source=source, opening=opening)
            or compile_pattern(pattern="=>\\s*$").search(string=prefix)
            is not None
        )
        if terminal_context and expression_boundary:
            return (
                inner.startswith("{")
                and compile_pattern(pattern="=>\\s*$").search(string=prefix)
                is not None
            )
        if following_char in {".", "[", "("}:
            return not cls._is_primary_like_expression(source=inner)
        return None

    @classmethod
    def _precedence_requires_parentheses(
        cls,
        *,
        source: str,
        opening: int,
        closing: int,
        inner: str,
    ) -> bool:
        """Precedence requires parentheses.

        Args:
            source: Source.
            opening: Opening.
            closing: Closing.
            inner: Inner.

        Returns:
            The resulting value.

        """
        inner_precedence: int | None = cls._weakest_precedence(source=inner)
        if inner_precedence is None:
            return not cls._atomic_context_is_safe(
                source=source,
                opening=opening,
                closing=closing,
            )
        left_operator: tuple[str, int] | None = cls._adjacent_operator_left(
            source=source,
            index=opening,
        )
        right_operator: tuple[str, int] | None = cls._adjacent_operator_right(
            source=source,
            index=closing + 1,
        )
        no_neighbors: bool = left_operator is None and right_operator is None
        if no_neighbors:
            return not cls._full_expression_context(
                source=source,
                opening=opening,
                closing=closing,
            )
        left_requires: bool = (
            left_operator is not None and inner_precedence <= left_operator[1]
        )
        right_requires: bool = (
            right_operator is not None and inner_precedence < right_operator[1]
        )
        equal_right_is_safe: bool = (
            left_operator is None
            and right_operator is not None
            and (inner_precedence == right_operator[1])
            and (inner_precedence != Constants.exponent_precedence)
        )
        return (left_requires or right_requires) and (not equal_right_is_safe)

    @classmethod
    def _has_top_level_comma(cls, *, source: str) -> bool:
        """Has top level comma.

        Args:
            source: Source.

        Returns:
            The resulting value.

        """
        return (
            cls._top_level_token_count(
                source=source,
                symbol=",",
                protected=cls._protected_spans(source=source),
            )
            > 0
        )

    @classmethod
    def _is_primary_like_expression(cls, *, source: str) -> bool:
        """Is primary like expression.

        Args:
            source: Source.

        Returns:
            The resulting value.

        """
        stripped: str = source.strip()
        if "?." in stripped:
            return False
        unary_prefix: bool = compile_pattern(
            pattern=r"(?:await|yield|typeof|void|delete)(?![a-zA-Z0-9_$])",
        ).match(string=stripped) is not None or stripped.startswith(
            ("!", "~", "+", "-"),
        )
        if unary_prefix:
            return False
        return cls._weakest_precedence(source=stripped) is None and (
            not stripped.startswith(
                ("{", "function", "class", "async function"),
            )
        )

    @classmethod
    def _atomic_context_is_safe(
        cls,
        *,
        source: str,
        opening: int,
        closing: int,
    ) -> bool:
        """Atomic context is safe.

        Args:
            source: Source.
            opening: Opening.
            closing: Closing.

        Returns:
            The resulting value.

        """
        previous: int = cls._previous_non_space(
            source=source,
            index=opening - 1,
        )
        following: int = cls._skip_space(source=source, index=closing + 1)
        previous_char: str = source[previous] if previous >= 0 else ""
        following_char: str = (
            source[following] if following < len(source) else ""
        )
        if previous_char in "([{=,:;!?&|+-*/%<>" or previous < 0:
            return following_char != "`"
        return following_char in {";", ",", ")", "]", "}", ".", "[", "("}

    @classmethod
    def _full_expression_context(
        cls,
        *,
        source: str,
        opening: int,
        closing: int,
    ) -> bool:
        """Full expression context.

        Args:
            source: Source.
            opening: Opening.
            closing: Closing.

        Returns:
            The resulting value.

        """
        prefix: str = source[max(0, opening - 32) : opening]
        following: int = cls._skip_space(source=source, index=closing + 1)
        following_char: str = (
            source[following] if following < len(source) else ""
        )
        return following_char in {";", ",", ")", "]", "}"} and (
            compile_pattern(pattern="(?:return|throw)\\s*$").search(
                string=prefix,
            )
            is not None
            or cls._preceded_by_assignment(source=source, opening=opening)
            or compile_pattern(pattern="=>\\s*$").search(string=prefix)
            is not None
        )

    @classmethod
    def _weakest_precedence(cls, *, source: str) -> int | None:
        """Weakest precedence.

        Args:
            source: Source.

        Returns:
            The resulting value.

        """
        operators: tuple[tuple[str, int], ...] = (
            ("=", 1),
            ("?", 2),
            ("??", 3),
            ("||", 4),
            ("&&", 5),
            ("|", 6),
            ("^", 7),
            ("&", 8),
            ("===", 9),
            ("!==", 9),
            ("==", 9),
            ("!=", 9),
            ("<", 10),
            (">", 10),
            ("<=", 10),
            (">=", 10),
            ("in", 10),
            ("instanceof", 10),
            ("<<", 11),
            (">>", 11),
            (">>>", 11),
            ("+", 12),
            ("-", 12),
            ("*", 13),
            ("/", 13),
            ("%", 13),
            ("**", 14),
        )
        found: list[int] = []
        for operator, precedence in operators:
            if cls._has_top_level_operator(source=source, operator=operator):
                found.append(precedence)
        return min(found) if found else None

    @classmethod
    def _has_top_level_operator(cls, *, source: str, operator: str) -> bool:
        """Has top level operator.

        Args:
            source: Source.
            operator: Operator.

        Returns:
            The resulting value.

        """
        protected: tuple[Span, ...] = cls._protected_spans(source=source)
        depths: dict[str, int] = {"(": 0, "[": 0, "{": 0}
        pairs: dict[str, str] = {")": "(", "]": "[", "}": "{"}
        index: int = 0
        while index < len(source):
            span: Span | None = cls._span_at(index=index, protected=protected)
            if span is not None:
                index = span[1]
                continue
            char: str = source[index]
            if char in depths:
                depths[char] += 1
            elif char in pairs:
                depths[pairs[char]] -= 1
            elif not any(depths.values()) and cls._operator_matches(
                source=source,
                operator=operator,
                index=index,
            ):
                return True
            index += 1
        return False

    @classmethod
    def _adjacent_operator_left(
        cls,
        *,
        source: str,
        index: int,
    ) -> tuple[str, int] | None:
        """Adjacent operator left.

        Args:
            source: Source.
            index: Index.

        Returns:
            The resulting value.

        """
        prefix: str = source[:index].rstrip()
        return cls._ending_operator(source=prefix)

    @classmethod
    def _adjacent_operator_right(
        cls,
        *,
        source: str,
        index: int,
    ) -> tuple[str, int] | None:
        """Adjacent operator right.

        Args:
            source: Source.
            index: Index.

        Returns:
            The resulting value.

        """
        suffix: str = source[index:].lstrip()
        return cls._starting_operator(source=suffix)

    @classmethod
    def _ending_operator(cls, *, source: str) -> tuple[str, int] | None:
        """Find the ending operator.

        Args:
            source: Source.

        Returns:
            The resulting value.

        """
        for operator, precedence in cls._operator_table():
            if source.endswith(operator):
                return (operator, precedence)
        return None

    @classmethod
    def _starting_operator(cls, *, source: str) -> tuple[str, int] | None:
        """Find the starting operator.

        Args:
            source: Source.

        Returns:
            The resulting value.

        """
        for operator, precedence in cls._operator_table():
            if source.startswith(operator):
                return (operator, precedence)
        return None

    @classmethod
    def _simple_parenthesis_replacements(
        cls,
        *,
        source: str,
        protected: tuple[Span, ...],
    ) -> list[Replacement]:
        """Find simple parenthesis replacements.

        Args:
            source: Source.
            protected: Protected.

        Returns:
            The resulting value.

        """
        replacements: list[Replacement] = []
        for match in cls.SIMPLE_PAREN.finditer(string=source):
            if cls._overlaps_protected(span=match.span(), protected=protected):
                continue
            before: str = source[match.start() - 1] if match.start() else ""
            after: str = (
                source[match.end()] if match.end() < len(source) else ""
            )
            if cls._parentheses_required_by_context(
                source=source,
                start=match.start(),
                end=match.end(),
                before=before,
                after=after,
            ):
                continue
            replacements.append(
                Replacement(
                    start=match.start(),
                    end=match.end(),
                    text=match.group(1),
                    kind="atomic-parentheses",
                ),
            )
        return replacements

    @classmethod
    def _parentheses_required_by_context(
        cls,
        *,
        source: str,
        start: int,
        end: int,
        before: str,
        after: str,
    ) -> bool:
        """Parentheses required by context.

        Args:
            source: Source.
            start: Start.
            end: End.
            before: Before.
            after: After.

        Returns:
            The resulting value.

        """
        if cls._preceded_by_block_comment(source=source, index=start):
            return True
        prefix: str = source[max(0, start - 16) : start]
        if (
            compile_pattern(
                pattern="(?:if|for|while|with|switch|catch)\\s*$",
            ).search(string=prefix)
            or (before and (before.isalnum() or before in "_$]})"))
            or (after and (after.isalnum() or after in "_$({[`"))
            or source[end:].lstrip().startswith("=>")
            or (
                before == "."
                and start >= (max_start := 2)
                and source[start - max_start] == "?"
            )
        ):
            return True
        inner: str = source[start + 1 : end - 1]
        if (
            compile_pattern(pattern="(?:return|throw|yield)\\s*$").search(
                string=prefix,
            )
            is not None
            and "\n" in inner
        ):
            return True
        following: str = source[end:].lstrip()
        if "?." in inner and following.startswith((".", "(")):
            return True
        return before in "+-" and after == before

    @classmethod
    def _control_brace_replacements(
        cls,
        *,
        source: str,
        protected: tuple[Span, ...],
    ) -> list[Replacement]:
        """Control brace replacements.

        Args:
            source: Source.
            protected: Protected.

        Returns:
            The resulting value.

        """
        replacements: list[Replacement] = []
        replacements.extend(
            cls._header_block_replacements(source=source, protected=protected),
        )
        replacements.extend(
            cls._keyword_block_replacements(
                source=source,
                protected=protected,
                pattern=cls.ELSE_BLOCK,
                keyword="else",
            ),
        )
        replacements.extend(
            cls._keyword_block_replacements(
                source=source,
                protected=protected,
                pattern=cls.DO_BLOCK,
                keyword="do",
            ),
        )
        return replacements

    @classmethod
    def _header_block_replacements(
        cls,
        *,
        source: str,
        protected: tuple[Span, ...],
    ) -> list[Replacement]:
        """Header block replacements.

        Args:
            source: Source.
            protected: Protected.

        Returns:
            The resulting value.

        """
        replacements: list[Replacement] = []
        for match in cls.CONTROL_HEADER.finditer(string=source):
            if cls._overlaps_protected(span=match.span(), protected=protected):
                continue
            opening_paren: int = source.find("(", match.start(), match.end())
            closing_paren: int | None = cls._matching_delimiter(
                source=source,
                opening=opening_paren,
                opener="(",
                closer=")",
                protected=protected,
            )
            if closing_paren is None:
                continue
            block_start: int = cls._skip_space(
                source=source,
                index=closing_paren + 1,
            )
            if block_start >= len(source) or source[block_start] != "{":
                continue
            replacement: Replacement | None = cls._single_statement_block(
                source=source,
                block_start=block_start,
                protected=protected,
                control_keyword=match.group(1),
            )
            if replacement is not None:
                replacements.append(replacement)
        return replacements

    @classmethod
    def _keyword_block_replacements(
        cls,
        *,
        source: str,
        protected: tuple[Span, ...],
        pattern: Pattern[str],
        keyword: str,
    ) -> list[Replacement]:
        """Keyword block replacements.

        Args:
            source: Source.
            protected: Protected.
            pattern: Pattern.
            keyword: Keyword.

        Returns:
            The resulting value.

        """
        replacements: list[Replacement] = []
        for match in pattern.finditer(string=source):
            if cls._overlaps_protected(span=match.span(), protected=protected):
                continue
            block_start: int = source.find("{", match.start(), match.end())
            replacement: Replacement | None = cls._single_statement_block(
                source=source,
                block_start=block_start,
                protected=protected,
                control_keyword=keyword,
            )
            if replacement is not None:
                replacements.append(replacement)
        return replacements

    @classmethod
    def _single_statement_block(
        cls,
        *,
        source: str,
        block_start: int,
        protected: tuple[Span, ...],
        control_keyword: str,
    ) -> Replacement | None:
        """Single statement block.

        Args:
            source: Source.
            block_start: Block start.
            protected: Protected.
            control_keyword: Control keyword.

        Returns:
            The resulting value.

        """
        block_end: int | None = cls._matching_delimiter(
            source=source,
            opening=block_start,
            opener="{",
            closer="}",
            protected=protected,
        )
        if block_end is None:
            return None
        body: str = source[block_start + 1 : block_end]
        if not cls._is_single_safe_statement(body=body):
            return None
        if control_keyword == "if":
            after: str = source[block_end + 1 :]
            if after.lstrip().startswith("else") and cls._starts_with_if(
                body=body,
            ):
                return None
        if not body.strip():
            return None
        return Replacement(
            start=block_start,
            end=block_end + 1,
            text=body if "\n" in body or "\r" in body else body.strip(),
            kind="single-statement-control-braces",
        )

    @classmethod
    def _is_single_safe_statement(cls, *, body: str) -> bool:
        """Is single safe statement.

        Args:
            body: Body.

        Returns:
            The resulting value.

        """
        stripped: str = body.strip()
        if not stripped or cls.UNSAFE_SINGLE_STATEMENT.match(string=stripped):
            return False
        if cls._contains_comment(source=stripped):
            return False
        protected: tuple[Span, ...] = cls._protected_spans(source=stripped)
        semicolons: int = cls._top_level_semicolon_count(
            source=stripped,
            protected=protected,
        )
        if semicolons > 1:
            return False
        if semicolons == 1 and (not stripped.endswith(";")):
            return False
        return not (
            cls._top_level_token_count(
                source=stripped,
                symbol=";",
                protected=protected,
            )
            == 0
            and stripped.startswith("{")
        )

    @classmethod
    def _contains_comment(cls, *, source: str) -> bool:
        """Contains comment.

        Args:
            source: Source.

        Returns:
            The resulting value.

        """
        spans: tuple[Span, ...] = cls._protected_spans(source=source)
        return any(
            (
                source[start : min(end, start + 2)] in {"//", "/*"}
                for start, end in spans
            ),
        )

    @classmethod
    def _protected_spans(cls, *, source: str) -> tuple[Span, ...]:
        """Protected spans.

        Args:
            source: Source.

        Returns:
            The resulting value.

        """
        spans: list[Span] = []
        index: int = 0
        can_start_regex: bool = True
        while index < len(source):
            protected: tuple[int, bool] | None = cls._protected_span_end(
                source=source,
                index=index,
                can_start_regex=can_start_regex,
            )
            if protected is not None:
                end: int
                end, can_start_regex = protected
                spans.append((index, end))
                index = end
                continue
            char: str = source[index]
            if not char.isspace():
                can_start_regex = (
                    not (char.isalnum() or char in "_$)]}")
                    and char in "([{,;:=!?&|+-*%^~<>"
                )
            index += 1
        return tuple(spans)

    @classmethod
    def _protected_span_end(
        cls,
        *,
        source: str,
        index: int,
        can_start_regex: bool,
    ) -> tuple[int, bool] | None:
        """Protected span end.

        Args:
            source: Source.
            index: Index.
            can_start_regex: Can start regex.

        Returns:
            The resulting value.

        """
        char: str = source[index]
        next_char: str = source[index + 1] if index + 1 < len(source) else ""
        if char in {"'", '"'}:
            return (
                cls._scan_quoted(source=source, start=index, quote=char),
                False,
            )
        if char == "`":
            return (cls._scan_template(source=source, start=index), False)
        if char == "/" and next_char == "/":
            end: int = source.find(
                "\n",
                index + Constants.delimiter_pair_length,
            )
            return (len(source) if end < 0 else end, can_start_regex)
        if char == "/" and next_char == "*":
            closing: int = source.find(
                "*/",
                index + Constants.delimiter_pair_length,
            )
            return (
                len(source)
                if closing < 0
                else closing + Constants.delimiter_pair_length,
                can_start_regex,
            )
        if (
            char == "/"
            and can_start_regex
            and (next_char not in {"=", "*", "/"})
        ):
            end = cls._scan_regex(source=source, start=index)
            return (end, False) if end > index + 1 else None
        return None

    @classmethod
    def _top_level_semicolon(
        cls,
        *,
        source: str,
        start: int,
        protected: tuple[Span, ...],
    ) -> int | None:
        """Top level semicolon.

        Args:
            source: Source.
            start: Start.
            protected: Protected.

        Returns:
            The resulting value.

        """
        depths: dict[str, int] = {"(": 0, "[": 0, "{": 0}
        pairs: dict[str, str] = {")": "(", "]": "[", "}": "{"}
        index: int = start
        while index < len(source):
            span: Span | None = cls._span_at(index=index, protected=protected)
            if span is not None:
                index = span[1]
                continue
            char: str = source[index]
            if char in depths:
                depths[char] += 1
            elif char in pairs:
                depths[pairs[char]] -= 1
            elif char == ";" and (not any(depths.values())):
                return index
            index += 1
        return None

    @classmethod
    def _top_level_semicolon_count(
        cls,
        *,
        source: str,
        protected: tuple[Span, ...],
    ) -> int:
        """Top level semicolon count.

        Args:
            source: Source.
            protected: Protected.

        Returns:
            The resulting value.

        """
        return cls._top_level_token_count(
            source=source,
            symbol=";",
            protected=protected,
        )

    @classmethod
    def _top_level_token_count(
        cls,
        *,
        source: str,
        symbol: str,
        protected: tuple[Span, ...],
    ) -> int:
        """Top level token count.

        Args:
            source: Source.
            symbol: Symbol.
            protected: Protected.

        Returns:
            The resulting value.

        """
        depths: dict[str, int] = {"(": 0, "[": 0, "{": 0}
        pairs: dict[str, str] = {")": "(", "]": "[", "}": "{"}
        count: int = 0
        index: int = 0
        while index < len(source):
            span: Span | None = cls._span_at(index=index, protected=protected)
            if span is not None:
                index = span[1]
                continue
            char: str = source[index]
            if char in depths:
                depths[char] += 1
            elif char in pairs:
                depths[pairs[char]] -= 1
            elif char == symbol and (not any(depths.values())):
                count += 1
            index += 1
        return count

    @classmethod
    def _skip_space_and_comments(
        cls,
        *,
        source: str,
        index: int,
        protected: tuple[Span, ...],
    ) -> int:
        """Skip space and comments.

        Args:
            source: Source.
            index: Index.
            protected: Protected.

        Returns:
            The resulting value.

        """
        while index < len(source):
            if source[index].isspace():
                index += 1
                continue
            span: Span | None = cls._span_at(index=index, protected=protected)
            if span is None:
                break
            prefix: str = source[span[0] : min(span[1], span[0] + 2)]
            if prefix not in {"//", "/*"}:
                break
            index = span[1]
        return index

    @staticmethod
    def _previous_non_space(*, source: str, index: int) -> int:
        """Previous non space.

        Args:
            source: Source.
            index: Index.

        Returns:
            The resulting value.

        """
        while index >= 0 and source[index].isspace():
            index -= 1
        return index

    @staticmethod
    def _preceded_by_block_comment(*, source: str, index: int) -> bool:
        """Preceded by block comment.

        Args:
            source: Source.
            index: Index.

        Returns:
            The resulting value.

        """
        previous: int = index - 1
        while previous >= 0 and source[previous].isspace():
            previous -= 1
        return (
            previous >= 1
            and source[previous] == "/"
            and source[previous - 1] == "*"
        )

    @staticmethod
    def _looks_like_call_parentheses(*, source: str, previous: int) -> bool:
        """Determine whether the syntax looks like call parentheses.

        Args:
            source: Source.
            previous: Previous.

        Returns:
            The resulting value.

        """
        if previous < 0:
            return False
        previous_char: str = source[previous]
        if (
            previous_char in ")]"
            or previous_char.isalnum()
            or previous_char in "_$"
        ):
            token_start: int = previous
            while token_start >= 0 and (
                source[token_start].isalnum() or source[token_start] in "_$"
            ):
                token_start -= 1
            if token_start >= 0 and source[token_start] in ".[":
                return True
            token: str = source[token_start + 1 : previous + 1]
            return token not in {
                "return",
                "throw",
                "typeof",
                "void",
                "delete",
                "await",
                "yield",
            }
        return previous_char in ".?"

    @staticmethod
    def _preceded_by_assignment(*, source: str, opening: int) -> bool:
        """Preceded by assignment.

        Args:
            source: Source.
            opening: Opening.

        Returns:
            The resulting value.

        """
        prefix: str = source[max(0, opening - 12) : opening].rstrip()
        return (
            compile_pattern(
                pattern=(
                    "(?:^|[^=!<>])(?:=|\\+=|-=|\\*=|/=|%=|&&=|\\|\\|=|\\?\\?=)"
                    "$"
                ),
            ).search(string=prefix)
            is not None
        )

    @staticmethod
    def _operator_matches(*, source: str, operator: str, index: int) -> bool:
        """Operator matches.

        Args:
            source: Source.
            operator: Operator.
            index: Index.

        Returns:
            The resulting value.

        """
        if not source.startswith(operator, index):
            return False
        before: str = source[index - 1] if index else ""
        after_index: int = index + len(operator)
        after: str = source[after_index] if after_index < len(source) else ""
        if operator.isalpha():
            return not (
                before.isalnum()
                or before in "_$"
                or after.isalnum()
                or (after in "_$")
            )
        ambiguous: frozenset[str] = frozenset(
            {"=", "<", ">", "+", "-", "*", "/", "&", "|", "?"},
        )
        if operator not in ambiguous:
            return True
        longer: tuple[str, ...] = (
            "=>",
            "===",
            "!==",
            "==",
            "!=",
            "<=",
            ">=",
            "<<",
            ">>",
            ">>>",
            "++",
            "--",
            "**",
            "&&",
            "||",
            "??",
            "?.",
            "+=",
            "-=",
            "*=",
            "/=",
            "%=",
            "&&=",
            "||=",
            "??=",
        )
        shadowed: bool = any(
            source.startswith(item, index)
            and item != operator
            and item.startswith(operator)
            for item in longer
        )
        unary: bool = operator in {"+", "-"} and before in "([{:;,=!?&|+-*/%<>"
        return not (shadowed or unary)

    @staticmethod
    def _operator_table() -> tuple[tuple[str, int], ...]:
        """Operator table.

        Returns:
            The resulting value.

        """
        return (
            (">>>", 11),
            ("===", 9),
            ("!==", 9),
            ("instanceof", 10),
            ("**", 14),
            ("??", 3),
            ("||", 4),
            ("&&", 5),
            ("==", 9),
            ("!=", 9),
            ("<=", 10),
            (">=", 10),
            ("<<", 11),
            (">>", 11),
            ("in", 10),
            ("|", 6),
            ("^", 7),
            ("&", 8),
            ("<", 10),
            (">", 10),
            ("+", 12),
            ("-", 12),
            ("*", 13),
            ("/", 13),
            ("%", 13),
            ("!", 15),
            ("~", 15),
            ("typeof", 15),
            ("void", 15),
            ("delete", 15),
            ("await", 15),
            ("yield", 15),
        )

    @staticmethod
    def _starts_with_if(*, body: str) -> bool:
        """Determine whether the body starts with if.

        Args:
            body: Body.

        Returns:
            The resulting value.

        """
        return (
            compile_pattern(pattern="^\\s*if\\b").search(string=body)
            is not None
        )

    @staticmethod
    def _scan_quoted(*, source: str, start: int, quote: str) -> int:
        """Scan quoted.

        Args:
            source: Source.
            start: Start.
            quote: Quote.

        Returns:
            The resulting value.

        """
        index: int = start + 1
        while index < len(source):
            if source[index] == "\\":
                index += 2
            elif source[index] == quote:
                return index + 1
            else:
                index += 1
        return len(source)

    @staticmethod
    def _scan_template(*, source: str, start: int) -> int:
        """Scan template.

        Args:
            source: Source.
            start: Start.

        Returns:
            The resulting value.

        """
        index: int = start + 1
        while index < len(source):
            if source[index] == "\\":
                index += 2
            elif source[index] == "`":
                return index + 1
            else:
                index += 1
        return len(source)

    @staticmethod
    def _scan_regex(*, source: str, start: int) -> int:
        """Scan regex.

        Args:
            source: Source.
            start: Start.

        Returns:
            The resulting value.

        """
        index: int = start + 1
        in_class: bool = False
        while index < len(source):
            char: str = source[index]
            if char == "\\":
                index += 2
                continue
            if char in "\r\n":
                return start + 1
            if char == "[":
                in_class = True
            elif char == "]":
                in_class = False
            elif char == "/" and (not in_class):
                index += 1
                while index < len(source) and (
                    source[index].isalpha() or source[index].isdigit()
                ):
                    index += 1
                return index
            index += 1
        return start + 1

    @staticmethod
    def _matching_delimiter(
        *,
        source: str,
        opening: int,
        opener: str,
        closer: str,
        protected: tuple[Span, ...],
    ) -> int | None:
        """Find the matching delimiter.

        Args:
            source: Source.
            opening: Opening.
            opener: Opener.
            closer: Closer.
            protected: Protected.

        Returns:
            The resulting value.

        """
        depth: int = 0
        index: int = opening
        span_index: int = 0
        while index < len(source):
            while (
                span_index < len(protected)
                and protected[span_index][1] <= index
            ):
                span_index += 1
            if (
                span_index < len(protected)
                and protected[span_index][0]
                <= index
                < protected[span_index][1]
            ):
                index = protected[span_index][1]
                continue
            if source[index] == opener:
                depth += 1
            elif source[index] == closer:
                depth -= 1
                if depth == 0:
                    return index
            index += 1
        return None

    @staticmethod
    def _span_at(*, index: int, protected: tuple[Span, ...]) -> Span | None:
        """Span at.

        Args:
            index: Index.
            protected: Protected.

        Returns:
            The resulting value.

        """
        return next(
            (span for span in protected if span[0] <= index < span[1]),
            None,
        )

    @staticmethod
    def _inside_protected(*, index: int, protected: tuple[Span, ...]) -> bool:
        """Inside protected.

        Args:
            index: Index.
            protected: Protected.

        Returns:
            The resulting value.

        """
        return any((start <= index < end for start, end in protected))

    @staticmethod
    def _overlaps_protected(
        *,
        span: Span,
        protected: tuple[Span, ...],
    ) -> bool:
        """Overlaps protected.

        Args:
            span: Span.
            protected: Protected.

        Returns:
            The resulting value.

        """
        start: int
        end: int
        start, end = span
        return any((start < right and left < end for left, right in protected))

    @staticmethod
    def _skip_space(*, source: str, index: int) -> int:
        """Skip space.

        Args:
            source: Source.
            index: Index.

        Returns:
            The resulting value.

        """
        while index < len(source) and source[index].isspace():
            index += 1
        return index

    @staticmethod
    def _non_overlapping(
        *,
        replacements: list[Replacement],
    ) -> tuple[Replacement, ...]:
        """Non overlapping.

        Args:
            replacements: Replacements.

        Returns:
            The resulting value.

        """
        selected: list[Replacement] = []
        last_end: int = -1
        for replacement in sorted(
            replacements,
            key=lambda item: (item.start, -(item.end - item.start), item.kind),
        ):
            if replacement.start < last_end:
                continue
            selected.append(replacement)
            last_end = replacement.end
        return tuple(selected)

    @staticmethod
    def _apply(*, source: str, replacements: tuple[Replacement, ...]) -> str:
        """Apply.

        Args:
            source: Source.
            replacements: Replacements.

        Returns:
            The resulting value.

        """
        result: str = source
        for replacement in reversed(replacements):
            result = (
                result[: replacement.start]
                + replacement.text
                + result[replacement.end :]
            )
        return result

    def _simplify(self, *, source: str) -> tuple[str, tuple[Replacement, ...]]:
        """Simplify.

        Args:
            source: Source.

        Returns:
            The resulting value.

        """
        current: str = source
        history: list[Replacement] = []
        while True:
            protected: tuple[Span, ...] = self._protected_spans(source=current)
            replacements: list[Replacement] = []
            replacements.extend(
                self._arrow_parameter_replacements(
                    source=current,
                    protected=protected,
                ),
            )
            replacements.extend(
                self._arrow_body_replacements(
                    source=current,
                    protected=protected,
                ),
            )
            replacements.extend(
                self._expression_parenthesis_replacements(
                    source=current,
                    protected=protected,
                ),
            )
            replacements.extend(
                self._simple_parenthesis_replacements(
                    source=current,
                    protected=protected,
                ),
            )
            if self._remove_control_braces:
                replacements.extend(
                    self._control_brace_replacements(
                        source=current,
                        protected=protected,
                    ),
                )
            selected: tuple[Replacement, ...] = self._non_overlapping(
                replacements=replacements,
            )
            if not selected:
                return (current, tuple(history))
            updated: str = self._apply(source=current, replacements=selected)
            if updated == current:
                return (current, tuple(history))
            history.extend(selected)
            current = updated

    def _validation_metrics(
        self,
        *,
        path: Path,
        source: str,
        changed: bool,
    ) -> ValidationMetrics:
        """Calculate validation metrics.

        Args:
            path: Path.
            source: Source.
            changed: Changed.

        Returns:
            The resulting value.

        """
        available: bool = self._node is not None
        performed: bool = changed and self._validate and available
        if performed:
            self._validate_source(path=path, source=source)
        return ValidationMetrics(
            requested=self._validate,
            available=available,
            performed=performed,
            passed=True if performed else None,
            engine=self._node if available else None,
        )

    def _validate_source(self, *, path: Path, source: str) -> None:
        """Validate source.

        Args:
            path: Path.
            source: Source.

        Raises:
            ValueError: Raised when the operation cannot be completed.

        """
        suffix: str = (
            path.suffix if path.suffix in {".mjs", ".cjs"} else ".mjs"
        )
        with NamedTemporaryFile(
            mode="w",
            suffix=suffix,
            encoding="utf-8",
            delete=True,
        ) as temporary:
            _ = temporary.write(source)
            temporary.flush()
            returncode: int
            stderr: str
            returncode, stderr = run_async(
                main=self._run_node_check(path=temporary.name),
            )
        if returncode != 0:
            msg: str = (
                f"Refusing to write "
                f"{path}: transformed source failed "
                f"Node syntax validation.\n{stderr}"
            )
            raise ValueError(msg)

    async def _run_node_check(self, *, path: str) -> tuple[int, str]:
        """Run node check.

        Args:
            path: Path.

        Returns:
            The resulting value.

        """
        process: Process = await create_subprocess_exec(
            self._node or "node",
            "--check",
            path,
            stdout=PIPE,
            stderr=PIPE,
        )
        _, stderr = await process.communicate()
        return (process.returncode or 0, stderr.decode())


class JavaScriptFiles:
    """Discover JavaScript files from files and directories."""

    def __init__(
        self,
        *,
        roots: tuple[Path, ...],
        excludes: tuple[str, ...],
    ) -> None:
        """Init  .

        Args:
            roots: Roots.
            excludes: Excludes.

        """
        self._roots: tuple[Path, ...] = roots
        self._excludes: tuple[str, ...] = excludes

    def collect(self) -> tuple[Path, ...]:
        """Collect.

        Returns:
            The resulting value.

        """
        files: set[Path] = set()
        for root in self._roots:
            if root.is_file():
                if (
                    root.suffix.lower()
                    in JavaScriptDelimiterSimplifier.EXTENSIONS
                ):
                    files.add(root.resolve())
                continue
            if not root.is_dir() or is_reports_tree(directory=root):
                continue
            for directory, dirnames, filenames in root.walk(top_down=True):
                dirnames[:] = [
                    name
                    for name in dirnames
                    if not is_reports_tree(directory=directory / name)
                ]
                files.update(
                    (directory / name).resolve()
                    for name in filenames
                    if (directory / name).suffix.lower()
                    in JavaScriptDelimiterSimplifier.EXTENSIONS
                    and (not self._excluded(path=directory / name))
                )
        return tuple(sorted(files))

    def _excluded(self, *, path: Path) -> bool:
        """Excluded.

        Args:
            path: Path.

        Returns:
            The resulting value.

        """
        normalized: str = path.as_posix()
        return any(
            f"/{exclude.strip('/')}/" in f"/{normalized}/"
            if "/" in exclude
            else exclude in path.parts
            for exclude in self._excludes
        )


@dataclass(frozen=True, slots=True)
class DelimiterFinding:
    """Describe DelimiterFinding.

    Attributes:
    rule: Public value used by this data structure.
    file: Public value used by this data structure.
    line: Public value used by this data structure.
    column: Public value used by this data structure.
    message: Public value used by this data structure.
    severity: Public value used by this data structure.

    """

    rule: str
    file: str
    line: int
    column: int
    message: str
    severity: str = "warning"


@dataclass(frozen=True, slots=True)
class DelimiterHeal:
    """Describe DelimiterHeal.

    Attributes:
    rule: Public value used by this data structure.
    file: Public value used by this data structure.
    action: Public value used by this data structure.
    transformations: Public value used by this data structure.
    characters_removed: Public value used by this data structure.

    """

    rule: str
    file: str
    action: str
    transformations: int
    characters_removed: int


@dataclass(frozen=True, slots=True)
class DelimiterInput:
    """Describe DelimiterInput.

    Attributes:
    root: Public value used by this data structure.
    files: Public value used by this data structure.
    fix: Public value used by this data structure.
    validate: Public value used by this data structure.

    """

    root: Path
    files: tuple[Path, ...]
    fix: bool
    validate: bool = True


@dataclass(frozen=True, slots=True)
class DelimiterResult:
    """Describe DelimiterResult.

    Attributes:
    files: Public value used by this data structure.
    findings: Public value used by this data structure.
    healed: Public value used by this data structure.

    """

    files: int
    findings: tuple[DelimiterFinding, ...]
    healed: tuple[DelimiterHeal, ...]


def _line_column(*, source: str, offset: int) -> tuple[int, int]:
    """Line column.

    Args:
        source: Source.
        offset: Offset.

    Returns:
        The resulting value.

    """
    line: int = source.count("\n", 0, offset) + 1
    line_start: int = source.rfind("\n", 0, offset)
    return (line, offset - line_start)


def _audit_delimiters(
    path: Path,
    *,
    simplifier: JavaScriptDelimiterSimplifier,
    root: Path,
    fix: bool,
) -> DelimiterFinding | DelimiterHeal | None:
    """Audit delimiters.

    Args:
        path: Path.
        simplifier: Simplifier.
        root: Root.
        fix: Fix.

    Returns:
        The resulting value.

    """
    try:
        relative: str = path.relative_to(root).as_posix()
    except ValueError:
        relative = path.as_posix()
    unreadable: DelimiterFinding = DelimiterFinding(
        rule="DEL002",
        file=relative,
        line=0,
        column=0,
        message="JavaScript file could not be read.",
        severity="error",
    )
    outcome: DelimiterFinding | DelimiterHeal | None = None
    if fix:
        try:
            result: FileResult = simplifier.simplify_file(
                path=path,
                write=True,
            )
        except (OSError, UnicodeDecodeError):
            outcome = unreadable
        except ValueError as error:
            outcome = DelimiterFinding(
                rule="DEL003",
                file=relative,
                line=0,
                column=0,
                message=f"Delimiter repair refused: {error}",
                severity="error",
            )
        else:
            if result.written:
                outcome = DelimiterHeal(
                    rule="DEL001",
                    file=relative,
                    action="simplify",
                    transformations=result.transformations.total,
                    characters_removed=result.transformations.characters_removed,
                )
    else:
        try:
            source: str = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            outcome = unreadable
        else:
            checked: TextResult = simplifier.simplify_text(source=source)
            if checked.changed:
                line, column = _line_column(
                    source=source,
                    offset=checked.replacements[0].start,
                )
                outcome = DelimiterFinding(
                    rule="DEL001",
                    file=relative,
                    line=line,
                    column=column,
                    message=(
                        f"{
                            checked.transformations.total
                        } unnecessary delimiter pair(s) can be "
                        f"removed."
                    ),
                )
    return outcome


def scan_delimiters(
    *,
    inputs: DelimiterInput,
    progress_span: tuple[float, float] = (0.0, 1.0),
) -> DelimiterResult:
    """Scan delimiters.

    Args:
        inputs: Inputs.
        progress_span: Overall progress slice used when embedded in lints.

    Returns:
        The resulting value.

    """
    simplifier: JavaScriptDelimiterSimplifier = JavaScriptDelimiterSimplifier(
        validate=inputs.validate,
    )
    workers: int = max(1, min(16, cpu_count() or 4, len(inputs.files)))
    audit: partial[DelimiterFinding | DelimiterHeal | None] = partial(
        _audit_delimiters,
        simplifier=simplifier,
        root=inputs.root,
        fix=inputs.fix,
    )
    lanes: LaneProgress = LaneProgress(
        total=len(inputs.files),
        step="JavaScript delimiters",
        span=progress_span,
    )

    def tracked(path: Path) -> DelimiterFinding | DelimiterHeal | None:
        """Audit one file while publishing its thread activity.

        Args:
            path: JavaScript file assigned to this thread.

        Returns:
            Finding, heal record, or ``None``.

        """
        label: str = str(object=path)
        lanes.begin(item=label)
        try:
            outcome: DelimiterFinding | DelimiterHeal | None = audit(path)
        except Exception as error:
            _ = lanes.finish(item=label, error=str(object=error))
            raise
        _ = lanes.finish(
            item=label,
            error=(
                outcome.message
                if isinstance(outcome, DelimiterFinding)
                and outcome.severity == "error"
                else None
            ),
        )
        trace(
            step=(
                f"delimiters: {label} — "
                + (
                    f"finding: {outcome.message}"
                    if isinstance(outcome, DelimiterFinding)
                    else (
                        f"healed: {outcome.action}"
                        if isinstance(outcome, DelimiterHeal)
                        else "ok"
                    )
                )
            ),
            depth=4,
        )
        return outcome

    pool: ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes: tuple[DelimiterFinding | DelimiterHeal | None, ...] = tuple(
            pool.map(tracked, inputs.files),
        )
    return DelimiterResult(
        files=len(inputs.files),
        findings=tuple(
            outcome
            for outcome in outcomes
            if isinstance(outcome, DelimiterFinding)
        ),
        healed=tuple(
            outcome
            for outcome in outcomes
            if isinstance(outcome, DelimiterHeal)
        ),
    )
