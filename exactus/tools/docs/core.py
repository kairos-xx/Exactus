# Copyright (c) 2026
# Copyright (c) 2026
"""Exactus Python docstrings and JavaScript JSDoc from one Python program.

The scanner is read-only. It discovers Python and JavaScript source files,
compares documentation contracts with implementation signatures/behavior, and
writes deterministic Markdown and JSON reports with patch-ready suggestions.
JavaScript analysis is implemented in Python; Node is used only for optional
syntax validation through ``node --check`` when available.
"""

from __future__ import annotations

from ast import (
    AST,
    AnnAssign,
    Assign,
    AsyncFunctionDef,
    Attribute,
    Call,
    ClassDef,
    FunctionDef,
    Module,
    Name,
    Raise,
    Return,
    Yield,
    YieldFrom,
    arg,
    expr,
    get_docstring,
    iter_child_nodes,
    parse,
    stmt,
    unparse,
)
from asyncio import Semaphore, create_subprocess_exec, gather, run
from asyncio.subprocess import PIPE
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from fnmatch import fnmatchcase
from pathlib import Path
from re import Match, Pattern, finditer, fullmatch, search, sub
from re import compile as recompile
from re import match as rematch
from subprocess import CompletedProcess
from threading import Thread
from typing import (
    TYPE_CHECKING,
    Final,
    Literal,
    NotRequired,
    Self,
    TypedDict,
    Unpack,
    cast,
)

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.steps import trace
from exactus.tools.common.cli import (
    ExactusCommonTables,
    consume,
    exactus_tool_prefix,
    is_reports_tree,
)
from exactus.tools.common.runtime import emit_progress
from exactus.tools.common.snippets import SnippetLimits, finding_excerpt
from exactus.tools.reports.bundle import ReportBundle, ReportPaths

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from asyncio.subprocess import Process
    from collections.abc import Callable

    from exactus.tools.common.json_types import JsonValue
type Language = Literal["python", "javascript"]
type Confidence = Literal["high", "medium", "low"]
type Severity = Literal["error", "warning", "info"]
type SymbolKind = Literal[
    "module",
    "class",
    "function",
    "method",
    "staticmethod",
    "classmethod",
    "property",
    "arrow",
    "getter",
    "setter",
]


class Constants:
    """Represent constants.

    Attributes:
        exclude_dirs: Exclude dirs.
        python_sections: Python sections.
        js_exempt_names: Js exempt names.
        python_exempt_dunders: Python exempt dunders.
        severity_rank: Severity rank.
        code_titles: Short title of each finding code.
        id_prefix: Prefix of generated finding identifiers.
        excluded_reason: Reason recorded for glob-filtered files.
        default_includes: Include globs reported when none is given.
        builtin_excludes: Globs describing the fixed skip rules.

    """

    exclude_dirs: Final[frozenset[str]] = (
        ExactusCommonTables.DEFAULT_EXCLUDED_DIRS
    )
    python_sections: Final[tuple[str, ...]] = (
        "Args",
        "Returns",
        "Raises",
        "Yields",
        "Attributes",
    )
    js_exempt_names: Final[frozenset[str]] = frozenset(
        {
            "adoptedCallback",
            "afterMount",
            "afterUnmount",
            "attributeChangedCallback",
            "beforeMount",
            "beforeUnmount",
            "connectedCallback",
            "constructor",
            "destroy",
            "disconnectedCallback",
            "dispose",
            "firstUpdated",
            "init",
            "mount",
            "render",
            "shouldUpdate",
            "toJSON",
            "toString",
            "unmount",
            "updated",
            "valueOf",
        },
    )
    python_exempt_dunders: Final[frozenset[str]] = frozenset(
        {
            "__aenter__",
            "__aexit__",
            "__call__",
            "__enter__",
            "__exit__",
            "__init__",
        },
    )
    severity_rank: Final[dict[str, int]] = {
        "info": 1,
        "warning": 2,
        "error": 3,
    }
    code_titles: Final[dict[str, str]] = {
        "DOC001": "Missing documentation",
        "DOC002": "Missing parameter documentation",
        "DOC003": "Stale parameter documentation",
        "DOC004": "Missing return documentation",
        "DOC005": "Return and yield mismatch",
        "DOC006": "Missing exception documentation",
        "DOC007": "Missing attribute documentation",
        "DOC008": "Malformed documentation",
        "DOC009": "Analysis failure",
        "DOC010": "Missing description",
        "DOC011": "Stale exception documentation",
        "DOC012": "Stale attribute documentation",
    }
    id_prefix: Final[str] = "DOCS"
    excluded_reason: Final[str] = "excluded by include/exclude rules"
    default_includes: Final[dict[str, tuple[str, ...]]] = {
        "python": ("**/*.py",),
        "javascript": ("**/*.js", "**/*.mjs", "**/*.cjs"),
    }
    builtin_excludes: Final[tuple[str, ...]] = ("**/*.min.js",)


class Code(StrEnum):
    """Represent code.

    Attributes:
        MISSING_DOCUMENTATION: Missing documentation.
        MISSING_PARAMETER: Missing parameter.
        STALE_PARAMETER: Stale parameter.
        MISSING_RETURN: Missing return.
        RETURN_YIELD_MISMATCH: Return yield mismatch.
        MISSING_EXCEPTION: Missing exception.
        MISSING_ATTRIBUTE: Missing attribute.
        MALFORMED_DOCUMENTATION: Malformed documentation.
        ANALYSIS_FAILURE: Analysis failure.
        MISSING_DESCRIPTION: Missing description.
        STALE_EXCEPTION: Stale exception.
        STALE_ATTRIBUTE: Stale attribute.

    """

    MISSING_DOCUMENTATION = "DOC001"
    MISSING_PARAMETER = "DOC002"
    STALE_PARAMETER = "DOC003"
    MISSING_RETURN = "DOC004"
    RETURN_YIELD_MISMATCH = "DOC005"
    MISSING_EXCEPTION = "DOC006"
    MISSING_ATTRIBUTE = "DOC007"
    MALFORMED_DOCUMENTATION = "DOC008"
    ANALYSIS_FAILURE = "DOC009"
    MISSING_DESCRIPTION = "DOC010"
    STALE_EXCEPTION = "DOC011"
    STALE_ATTRIBUTE = "DOC012"


@dataclass(frozen=True, slots=True)
class Config:
    """Represent config.

    Attributes:
        root: Root.
        markdown: Markdown.
        json_output: Json output.
        languages: Languages.
        exclude_dirs: Exclude dirs.
        exclude_hidden_dirs: Exclude hidden dirs.
        public_only: Public only.
        validate_javascript: Validate javascript.
        fail_on: Fail on.
        includes: Include globs narrowing exactused files.
        excludes: Exclude globs narrowing exactused files.
        include_files: Explicit single-file scope when ``root`` is a
            file, overriding directory discovery.
        context_lines: Source lines captured around each finding line.

    """

    root: Path
    markdown: Path
    json_output: Path
    languages: frozenset[Language]
    exclude_dirs: frozenset[str]
    exclude_hidden_dirs: bool
    public_only: bool
    validate_javascript: bool
    fail_on: Severity | None
    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()
    include_files: tuple[Path, ...] = ()
    context_lines: int = SnippetLimits.default_context


@dataclass(frozen=True, slots=True)
class Skip:
    """One discovered source file that was not exactused.

    Attributes:
        target: Root-relative file path.
        reason: Why the file was not exactused.

    """

    target: str
    reason: str


@dataclass(frozen=True, slots=True)
class Finding:
    """Represent finding.

    Attributes:
        code: Code.
        language: Language.
        severity: Severity.
        confidence: Confidence.
        file: File.
        line: Line.
        column: Column.
        kind: Kind.
        qualname: Qualname.
        signature: Signature.
        message: Message.
        reason: Reason.
        suggestion: Suggestion.
        subject: Documented member name within the symbol.

    """

    code: Code
    language: Language
    severity: Severity
    confidence: Confidence
    file: Path
    line: int
    column: int
    kind: SymbolKind
    qualname: str
    signature: str
    message: str
    reason: str
    suggestion: str
    subject: str = ""

    def relative_dict(self: Self, root: Path) -> dict[str, str | int]:
        """Return a JSON-safe finding relative to the repository root.

        Args:
            root: Repository root.

        Returns:
            Serialized finding values.

        """
        return {
            "code": self.code,
            "language": self.language,
            "severity": self.severity,
            "confidence": self.confidence,
            "file": str(object=self.file.relative_to(root)),
            "line": self.line,
            "column": self.column,
            "kind": self.kind,
            "qualname": self.qualname,
            "signature": self.signature,
            "subject": self.subject,
            "message": self.message,
            "reason": self.reason,
            "suggestion": self.suggestion,
        }


@dataclass(slots=True)
class Statistics:
    """Represent statistics.

    Attributes:
        discovered: Discovered.
        parsed: Parsed.
        failed: Failed.
        symbols: Symbols.
        documented: Documented.
        findings: Findings.

    """

    discovered: int = 0
    parsed: int = 0
    failed: int = 0
    symbols: int = 0
    documented: int = 0
    findings: int = 0


def empty_statistics() -> dict[Language, Statistics]:
    """Return zeroed counters for every exactused language.

    A named factory rather than a lambda gives the literal keys their
    declared `Language` type instead of plain `str`.

    Returns:
        One empty `Statistics` per language.

    """
    return {"python": Statistics(), "javascript": Statistics()}


def empty_lines() -> dict[Language, int]:
    """Return a zeroed line counter for every exactused language.

    Returns:
        Zero lines per language.

    """
    return {"python": 0, "javascript": 0}


@dataclass(slots=True)
class Report:
    """Represent report.

    Attributes:
        findings: Findings.
        statistics: Statistics.
        lines: Lines of the successfully read sources, per language.

    """

    findings: list[Finding] = field(default_factory=list)
    statistics: dict[Language, Statistics] = field(
        default_factory=empty_statistics,
    )
    lines: dict[Language, int] = field(default_factory=empty_lines)

    def add(self: Self, finding: Finding) -> None:
        """Append one finding and update counters.

        Args:
            finding: Finding to append.

        """
        self.findings.append(finding)
        self.statistics[finding.language].findings += 1


@dataclass(frozen=True, slots=True)
class ParsedGoogleDoc:
    """Represent parsed google doc.

    Attributes:
        summary: Summary.
        sections: Sections.
        malformed: Malformed.

    """

    summary: str
    sections: dict[str, tuple[str, ...]]
    malformed: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JsDoc:
    """Represent js doc.

    Attributes:
        summary: Summary.
        params: Params.
        returns: Returns.
        yields: Yields.
        throws: Throws.
        properties: Properties.
        malformed: Malformed.

    """

    summary: str
    params: tuple[str, ...]
    returns: bool
    yields: bool
    throws: tuple[str, ...]
    properties: tuple[str, ...]
    malformed: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JsDocBlock:
    """Represent js doc block.

    Attributes:
        start: Start.
        end: End.
        content: Content.

    """

    start: int
    end: int
    content: str


@dataclass(frozen=True, slots=True)
class JsSymbol:
    """Represent js symbol.

    Attributes:
        name: Name.
        qualname: Qualname.
        kind: Kind.
        start: Start.
        body_start: Body start.
        body_end: Body end.
        params_text: Params text.
        signature: Signature.
        is_async: Is async.
        is_generator: Is generator.

    """

    name: str
    qualname: str
    kind: SymbolKind
    start: int
    body_start: int | None
    body_end: int | None
    params_text: str
    signature: str
    is_async: bool
    is_generator: bool


class Text:
    """Pure text utilities shared by both analyzers."""

    @classmethod
    def description(
        cls: type[Self],
        name: str,
        kind: SymbolKind,
        *,
        returns: bool = False,
    ) -> str:
        """Infer a concise documentation summary from a symbol name.

        Args:
            name: Symbol name.
            kind: Symbol kind.
            returns: Whether the callable produces a value.

        Returns:
            Imperative/indicative summary sentence.

        """
        words: list[str] = cls.words(name=name)
        if not words:
            return "Document this symbol."
        phrase: str = " ".join(words)
        if kind == "class":
            return f"Represent {phrase}."
        if name.startswith(("is_", "has_", "can_", "should_")) or words[0] in {
            "is",
            "has",
            "can",
            "should",
        }:
            return f"Return whether {' '.join(words[1:]) or phrase}."
        verbs: dict[str, str] = {
            "add": "Add",
            "analyze": "Analyze",
            "build": "Build",
            "calculate": "Calculate",
            "check": "Check",
            "collect": "Collect",
            "create": "Create",
            "delete": "Delete",
            "discover": "Discover",
            "find": "Find",
            "format": "Format",
            "get": "Return",
            "iter": "Iterate over",
            "load": "Load",
            "parse": "Parse",
            "read": "Read",
            "remove": "Remove",
            "render": "Render",
            "scan": "Scan",
            "set": "Set",
            "update": "Update",
            "validate": "Validate",
            "write": "Write",
        }
        return (
            f"{verbs[words[0]]} {' '.join(words[1:])}."
            if words[0] in verbs and len(words) > 1
            else f"{'Return' if returns else 'Handle'} {phrase}."
        )

    @classmethod
    def parameter_description(cls: type[Self], name: str) -> str:
        """Infer a short parameter description.

        Args:
            name: Parameter name.

        Returns:
            Description fragment.

        """
        words: str = " ".join(cls.words(name=name)) or name
        return f"{words[:1].upper()}{words[1:]}."

    @classmethod
    def balanced_split(cls: type[Self], value: str) -> tuple[str, ...]:
        """Split a comma list without splitting nested expressions.

        Args:
            value: Parameter-list source.

        Returns:
            Top-level comma-separated fragments.

        """
        parts: list[str] = []
        start: int = 0
        depths: dict[str, int] = {"(": 0, "[": 0, "{": 0}
        closing: dict[str, str] = {")": "(", "]": "[", "}": "{"}
        quote: str | None = None
        escaped: bool = False
        index: int
        char: str
        for index, char in enumerate(iterable=value):
            if quote is not None:
                quote, escaped = cls._quoted_state(
                    char=char,
                    quote=quote,
                    escaped=escaped,
                )
                continue
            if char in {"'", '"', "`"}:
                quote = char
            elif char in depths:
                depths[char] += 1
            elif char in closing:
                opening: str = closing[char]
                depths[opening] = max(0, depths[opening] - 1)
            elif char == "," and not any(depths.values()):
                if part := value[start:index].strip():
                    parts.append(part)
                start = index + 1
        if part := value[start:].strip():
            parts.append(part)
        return tuple(parts)

    @staticmethod
    def words(name: str) -> list[str]:
        """Split snake/camel/pascal identifiers into lowercase words.

        Args:
            name: Identifier to split.

        Returns:
            Lowercase component words.

        """
        spaced: str = sub(
            pattern=r"(?<=[a-z0-9])(?=[A-Z])",
            repl=" ",
            string=name.replace("_", " ").strip("_"),
        )
        words: list[str] = list(map(str.lower, filter(None, spaced.split())))
        return words

    @staticmethod
    def line_column(source: str, offset: int) -> tuple[int, int]:
        """Convert a character offset to one-based line and zero-based column.

        Args:
            source: Full source text.
            offset: Character offset.

        Returns:
            Line and column pair.

        """
        line: int = source.count("\n", 0, offset) + 1
        previous: int = source.rfind("\n", 0, offset)
        return line, offset if previous < 0 else offset - previous - 1

    @staticmethod
    def _quoted_state(
        char: str,
        quote: str,
        *,
        escaped: bool,
    ) -> tuple[str | None, bool]:
        """Advance quoted-string state for a splitter character.

        Args:
            char: Current character.
            quote: Active quote delimiter.
            escaped: Whether the previous character was a backslash.

        Returns:
            Updated quote and escape state.

        """
        if escaped:
            return quote, False
        if char == "\\":
            return quote, True
        return (None if char == quote else quote), False


class PythonFindingArgs(TypedDict):
    """Represent python finding args.

    Attributes:
        code: Code.
        file: File.
        node: Node.
        kind: Kind.
        qualname: Qualname.
        signature: Signature.
        confidence: Confidence.
        message: Message.
        reason: Reason.
        suggestion: Suggestion.
        subject: Subject.

    """

    code: Code
    file: Path
    node: AST
    kind: SymbolKind
    qualname: str
    signature: str
    confidence: NotRequired[Confidence]
    message: str
    reason: str
    suggestion: str
    subject: NotRequired[str]


class PythonAnalyzer:
    """Analyze Google-style Python documentation contracts."""

    def __init__(self: Self, config: Config, report: Report) -> None:
        """Initialize the analyzer.

        Args:
            config: Scanner configuration.
            report: Shared report accumulator.

        """
        self._config: Config = config
        self._report: Report = report

    def analyze(self: Self, file: Path) -> None:
        """Analyze one Python file.

        Args:
            file: Python source path.

        """
        stats: Statistics = self._report.statistics["python"]
        stats.discovered += 1
        error: OSError | UnicodeError | SyntaxError
        try:
            source: str = file.read_text(encoding="utf-8")
            module: Module = parse(source=source, filename=str(object=file))
        except (OSError, UnicodeError, SyntaxError) as error:
            stats.failed += 1
            self._report.add(
                finding=Finding(
                    code=Code.ANALYSIS_FAILURE,
                    language="python",
                    severity="error",
                    confidence="high",
                    file=file,
                    line=getattr(error, "lineno", 1) or 1,
                    column=getattr(error, "offset", 1) or 1,
                    kind="module",
                    qualname=file.stem,
                    signature="",
                    message=f"Python analysis failed: {error}",
                    reason="The source could not be read or parsed.",
                    suggestion=(
                        "Fix the source/read error and rerun the exactus."
                    ),
                ),
            )
            return
        stats.parsed += 1
        self._report.lines["python"] += _count_lines(text=source)
        stats.symbols += 1
        if get_docstring(node=module, clean=False) is None:
            self._finding(
                code=Code.MISSING_DOCUMENTATION,
                file=file,
                node=module,
                kind="module",
                qualname=file.stem,
                signature="module",
                message="Missing module docstring.",
                reason="The module has no runtime docstring.",
                suggestion=(
                    '"""Describe this module and its public '
                    'responsibilities."""'
                ),
            )
        else:
            stats.documented += 1
        statement: stmt
        for statement in module.body:
            if isinstance(statement, ClassDef):
                self._exactus_class(file=file, node=statement, prefix="")
            elif isinstance(statement, (FunctionDef, AsyncFunctionDef)):
                self._exactus_function(
                    file=file,
                    node=statement,
                    qualname=statement.name,
                    in_class=False,
                )

    @classmethod
    def _signature(
        cls: type[Self],
        node: FunctionDef | AsyncFunctionDef,
    ) -> str:
        """Build a source-like callable signature.

        Args:
            node: Callable definition.

        Returns:
            Signature string.

        """
        positional: list[arg] = [*node.args.posonlyargs, *node.args.args]
        defaults: list[expr | None] = [
            *([None] * (len(positional) - len(node.args.defaults))),
            *node.args.defaults,
        ]
        parts: list[str] = []
        index: int
        parameter: arg
        for index, parameter in enumerate(iterable=positional):
            annotation: str = cls._annotation(node=parameter.annotation)
            rendered: str = (
                f"{parameter.arg}: {annotation}"
                if annotation
                else parameter.arg
            )
            if (default := defaults[index]) is not None:
                rendered += f" = {unparse(ast_obj=default)}"
            parts.append(rendered)
            if index + 1 == len(node.args.posonlyargs):
                parts.append("/")
        if node.args.vararg is not None:
            annotation = cls._annotation(node=node.args.vararg.annotation)
            parts.append(
                f"*{node.args.vararg.arg}: {annotation}"
                if annotation
                else f"*{node.args.vararg.arg}",
            )
        elif node.args.kwonlyargs:
            parts.append("*")
        for parameter, default in zip(
            node.args.kwonlyargs,
            node.args.kw_defaults,
            strict=True,
        ):
            annotation = cls._annotation(node=parameter.annotation)
            rendered = (
                f"{parameter.arg}: {annotation}"
                if annotation
                else parameter.arg
            )
            parts.append(
                f"{rendered} = {unparse(ast_obj=default)}"
                if default is not None
                else rendered,
            )
        if node.args.kwarg is not None:
            annotation = cls._annotation(node=node.args.kwarg.annotation)
            parts.append(
                f"**{node.args.kwarg.arg}: {annotation}"
                if annotation
                else f"**{node.args.kwarg.arg}",
            )
        returns: str = cls._annotation(node=node.returns)
        prefix: str = "async " if isinstance(node, AsyncFunctionDef) else ""
        return (
            f"{prefix}{node.name}({', '.join(parts)})"
            f"{f' -> {returns}' if returns else ''}"
        )

    @classmethod
    def _raises(
        cls: type[Self],
        node: FunctionDef | AsyncFunctionDef,
    ) -> tuple[str, ...]:
        """Infer directly raised exception names.

        Args:
            node: Callable definition.

        Returns:
            Unique exception names in source order.

        """
        names: list[str] = []
        child: AST
        for child in cls._direct_nodes(node=node):
            if not isinstance(child, Raise) or child.exc is None:
                continue
            exception: expr = (
                child.exc.func if isinstance(child.exc, Call) else child.exc
            )
            name: str | None = (
                exception.id
                if isinstance(exception, Name)
                else (
                    exception.attr
                    if isinstance(exception, Attribute)
                    else None
                )
            )
            if (
                name is not None
                and name not in names
                and (isinstance(child.exc, Call) or name[:1].isupper())
            ):
                names.append(name)
        return tuple(names)

    @classmethod
    def _yields(cls: type[Self], node: FunctionDef | AsyncFunctionDef) -> bool:
        """Return whether a callable directly yields values.

        Args:
            node: Callable definition.

        Returns:
            True when a direct ``yield``/``yield from`` exists.

        """
        child: AST
        for child in cls._direct_nodes(node=node):
            if isinstance(child, (Yield, YieldFrom)):
                return True
        return False

    @classmethod
    def _returns_value(
        cls: type[Self],
        node: FunctionDef | AsyncFunctionDef,
    ) -> bool:
        """Return whether a callable directly returns a value.

        Args:
            node: Callable definition.

        Returns:
            True when a non-empty return exists or annotation implies a value.

        """
        child: AST
        for child in cls._direct_nodes(node=node):
            if isinstance(child, Return) and child.value is not None:
                return True
        annotation: str = cls._annotation(node=node.returns)
        return bool(
            annotation and annotation not in {"None", "NoReturn", "Never"},
        )

    @classmethod
    def _parse_doc(cls: type[Self], doc: str) -> ParsedGoogleDoc:
        """Parse relevant Google-style sections.

        Args:
            doc: Raw docstring.

        Returns:
            Parsed documentation.

        """
        lines: list[str] = doc.splitlines()
        summary: str = next(
            (line.strip() for line in lines if line.strip()),
            "",
        )
        sections: dict[str, list[str]]
        malformed: list[str]
        sections, malformed = cls._section_entries(lines=lines)
        return ParsedGoogleDoc(
            summary=summary,
            sections={key: tuple(value) for key, value in sections.items()},
            malformed=tuple(malformed),
        )

    @classmethod
    def _suggest_function(
        cls: type[Self],
        node: FunctionDef | AsyncFunctionDef,
        *,
        kind: SymbolKind,
    ) -> str:
        """Generate a complete Google-style callable docstring.

        Args:
            node: Callable definition.
            kind: Callable kind.

        Returns:
            Suggested docstring including useful sections only.

        """
        yields: bool = cls._yields(node=node)
        returns: bool = cls._returns_value(node=node) and not yields
        lines: list[str] = [
            '"""'
            + Text.description(
                name=node.name,
                kind=kind,
                returns=returns or yields,
            ),
        ]
        if parameters := cls._parameters(node=node, method=kind != "function"):
            lines.extend(["", "Args:"])
            lines.extend(map(cls._parameter_entry, parameters))
        if yields:
            lines.extend(
                ["", "Yields:", "    Values produced by the iterator."],
            )
        elif returns:
            lines.extend(["", "Returns:", "    The resulting value."])
        if raises := cls._raises(node=node):
            lines.extend(["", "Raises:"])
            lines.extend(map(cls._raises_entry, raises))
        lines.append('"""')
        return "\n".join(lines)

    @classmethod
    def _suggest_class(cls: type[Self], node: ClassDef) -> str:
        """Generate a complete class docstring.

        Args:
            node: Class definition.

        Returns:
            Suggested class docstring.

        """
        lines: list[str] = [
            '"""' + Text.description(name=node.name, kind="class"),
        ]
        if attributes := cls._class_attributes(node=node):
            lines.extend(["", "Attributes:"])
            lines.extend(map(cls._parameter_entry, attributes))
        lines.append('"""')
        return "\n".join(lines)

    @staticmethod
    def _annotation(node: expr | None) -> str:
        """Render an annotation as source text.

        Args:
            node: Annotation node.

        Returns:
            Rendered annotation or an empty string.

        """
        return unparse(ast_obj=node) if node is not None else ""

    @staticmethod
    def _parameters(
        node: FunctionDef | AsyncFunctionDef,
        *,
        method: bool,
    ) -> tuple[str, ...]:
        """Return documentable parameter names.

        Args:
            node: Callable definition.
            method: Whether the callable is a class member.

        Returns:
            Parameter names excluding conventional receivers for methods.

        """
        all_params: list[arg] = [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ]
        names: list[str] = []
        parameter: arg
        for parameter in all_params:
            if method and parameter.arg in {"self", "cls"}:
                continue
            names.append(parameter.arg)
        if node.args.vararg is not None:
            names.append(node.args.vararg.arg)
        if node.args.kwarg is not None:
            names.append(node.args.kwarg.arg)
        return tuple(names)

    @staticmethod
    def _direct_nodes(node: FunctionDef | AsyncFunctionDef) -> tuple[AST, ...]:
        """Return descendants while excluding nested callable/class scopes.

        Args:
            node: Callable whose own behavior is being inspected.

        Returns:
            Descendants belonging to the callable's direct semantic scope.

        """
        found: list[AST] = []
        stack: list[AST] = [*reversed(node.body)]
        while stack:
            current: AST = stack.pop()
            found.append(current)
            if isinstance(current, (FunctionDef, AsyncFunctionDef, ClassDef)):
                continue
            stack.extend(reversed(list(iter_child_nodes(node=current))))
        return tuple(found)

    @staticmethod
    def _class_attributes(node: ClassDef) -> tuple[str, ...]:
        """Return directly declared public class attributes.

        Args:
            node: Class definition.

        Returns:
            Public annotated/assigned class attribute names.

        """
        names: list[str] = []
        statement: stmt
        for statement in node.body:
            name: str | None = None
            if isinstance(statement, AnnAssign) and isinstance(
                statement.target,
                Name,
            ):
                name = statement.target.id
            elif isinstance(statement, Assign) and len(statement.targets) == 1:
                target: expr = statement.targets[0]
                name = target.id if isinstance(target, Name) else None
            if (
                name is not None
                and not name.startswith("_")
                and name not in names
            ):
                names.append(name)
        return tuple(names)

    @staticmethod
    def _section_entries(
        *,
        lines: list[str],
    ) -> tuple[dict[str, list[str]], list[str]]:
        """Collect section entries and malformed entry lines.

        Deeper-indented lines continue the previous ``Args``/``Raises``/
        ``Attributes`` entry, as Google style allows for wrapped text.

        Args:
            lines: Docstring lines.

        Returns:
            Entry names (or text for ``Returns``/``Yields``) per section, and
            malformed entry messages.

        """
        sections: dict[str, list[str]] = {}
        malformed: list[str] = []
        current: str | None = None
        section_pattern: Pattern[str] = recompile(
            pattern=r"^(Args|Returns|Raises|Yields|Attributes|Notes|Examples|"
            r"Warnings|References|See Also):\s*$",
        )
        entry_pattern: Pattern[str] = recompile(
            pattern=(
                r"^\s{4,}([*]{0,2}[A-Za-z_][\w.]*)(?:\s*\([^)]*\))?\s*:\s*.+$"
            ),
        )
        entry_indent: int | None = None
        line: str
        for line in lines:
            if match := section_pattern.match(string=line.strip()):
                current = match.group(1)
                entry_indent = None
                _ = consume(value=sections.setdefault(match.group(1), []))
                continue
            if current is None or not line.strip():
                continue
            indent: int = len(line) - len(line.lstrip())
            if current not in {"Args", "Raises", "Attributes"}:
                sections[current].append(line.strip())
            elif entry_indent is not None and indent > entry_indent:
                continue
            elif match := entry_pattern.match(string=line):
                entry: str = match.group(1).lstrip("*")
                sections[current].append(
                    entry.rsplit(sep=".", maxsplit=1)[-1]
                    if current == "Raises"
                    else entry,
                )
                entry_indent = indent
            elif line.startswith((" ", "\t")):
                malformed.append(f"Malformed {current} entry: {line.strip()}")
            else:
                current = None
        return sections, malformed

    @staticmethod
    def _parameter_entry(name: str) -> str:
        """Return one Google-style ``Args``/``Attributes`` entry line.

        Args:
            name: Documented parameter or attribute name.

        Returns:
            Indented docstring entry line.

        """
        return f"    {name}: {Text.parameter_description(name=name)}"

    @staticmethod
    def _raises_entry(name: str) -> str:
        """Return one Google-style ``Raises`` entry line.

        Args:
            name: Documented exception name.

        Returns:
            Indented docstring entry line.

        """
        return f"    {name}: When the operation cannot complete."

    @staticmethod
    def _kind(
        node: FunctionDef | AsyncFunctionDef,
        *,
        in_class: bool,
    ) -> SymbolKind:
        """Classify a Python callable.

        Args:
            node: Callable definition.
            in_class: Whether the callable is a direct class member.

        Returns:
            Symbol kind.

        """
        decorators: set[str] = set()
        decorator: expr
        for decorator in node.decorator_list:
            decorators.add(unparse(ast_obj=decorator))
        if "property" in decorators:
            return "property"
        if "staticmethod" in decorators:
            return "staticmethod"
        if "classmethod" in decorators:
            return "classmethod"
        return "method" if in_class else "function"

    @staticmethod
    def _overloads(*, node: FunctionDef | AsyncFunctionDef) -> bool:
        """Return whether a callable declares an ``@overload`` signature.

        Overload signatures are typing-only stubs that cannot carry a
        runtime docstring, so documentation checks skip them.

        Args:
            node: Callable definition.

        Returns:
            Whether any decorator is ``overload``.

        """
        return any(
            unparse(ast_obj=decorator).rsplit(sep=".", maxsplit=1)[-1]
            == "overload"
            for decorator in node.decorator_list
        )

    def _finding(self: Self, **kwargs: Unpack[PythonFindingArgs]) -> None:
        """Handle finding.

        Args:
            kwargs: Kwargs.

        """
        code: Code = kwargs["code"]
        file: Path = kwargs["file"]
        node: AST = kwargs["node"]
        kind: SymbolKind = kwargs["kind"]
        qualname: str = kwargs["qualname"]
        signature: str = kwargs["signature"]
        confidence: Confidence = kwargs.get("confidence", "high")
        details: dict[str, str] = {
            "message": kwargs["message"],
            "reason": kwargs["reason"],
            "suggestion": kwargs["suggestion"],
        }
        self._report.add(
            finding=Finding(
                code=code,
                language="python",
                severity="warning",
                confidence=confidence,
                file=file,
                line=getattr(node, "lineno", 1),
                column=getattr(node, "col_offset", 0),
                kind=kind,
                qualname=qualname,
                signature=signature,
                message=details["message"],
                reason=details["reason"],
                suggestion=details["suggestion"],
                subject=kwargs.get("subject", ""),
            ),
        )

    def _exactus_nested_functions(
        self: Self,
        *,
        file: Path,
        node: FunctionDef | AsyncFunctionDef,
        qualname: str,
    ) -> None:
        """Exactus functions directly nested in a callable.

        Args:
            file: Source file.
            node: Callable whose nested functions are exactused.
            qualname: Qualified name of the containing callable.

        """
        child: AST
        for child in self._direct_nodes(node=node):
            if isinstance(child, (FunctionDef, AsyncFunctionDef)):
                self._exactus_function(
                    file=file,
                    node=child,
                    qualname=f"{qualname}.<locals>.{child.name}",
                    in_class=False,
                )

    def _exactus_function(
        self: Self,
        *,
        file: Path,
        node: FunctionDef | AsyncFunctionDef,
        qualname: str,
        in_class: bool,
    ) -> None:
        """Exactus one Python callable.

        Args:
            file: Source file.
            node: Callable definition.
            qualname: Qualified name.
            in_class: Whether this is a class member.

        """
        kind: SymbolKind = self._kind(node=node, in_class=in_class)
        if (
            self._overloads(node=node)
            or (
                self._config.public_only
                and node.name.startswith("_")
                and not node.name.startswith("__")
            )
            or (
                node.name.startswith("__")
                and node.name.endswith("__")
                and node.name not in Constants.python_exempt_dunders
            )
        ):
            return
        self._report.statistics["python"].symbols += 1
        suggestion: str = self._suggest_function(node=node, kind=kind)
        signature: str = self._signature(node=node)
        if (doc := get_docstring(node=node, clean=False)) is None:
            self._finding(
                code=Code.MISSING_DOCUMENTATION,
                file=file,
                node=node,
                kind=kind,
                qualname=qualname,
                signature=signature,
                message="Missing Google-style docstring.",
                reason="The callable has no runtime docstring.",
                suggestion=suggestion,
            )
            self._exactus_nested_functions(
                file=file,
                node=node,
                qualname=qualname,
            )
            return
        self._report.statistics["python"].documented += 1
        parsed: ParsedGoogleDoc = self._parse_doc(doc=doc)
        if not parsed.summary or parsed.summary in {'"""', "'''"}:
            self._finding(
                code=Code.MISSING_DESCRIPTION,
                file=file,
                node=node,
                kind=kind,
                qualname=qualname,
                signature=signature,
                message="Docstring has no useful summary.",
                reason=(
                    "A documentation contract should explain "
                    "the callable purpose."
                ),
                suggestion=suggestion,
            )
        expected_params: set[str] = set(
            self._parameters(node=node, method=kind != "function"),
        )
        documented_params: set[str] = set(parsed.sections.get("Args", ()))
        name: str
        for name in sorted(expected_params - documented_params):
            self._finding(
                code=Code.MISSING_PARAMETER,
                file=file,
                node=node,
                kind=kind,
                qualname=qualname,
                signature=signature,
                message=f"Parameter `{name}` is undocumented.",
                reason=(
                    "The parameter exists in the callable signature "
                    "but not in Args."
                ),
                suggestion=suggestion,
                subject=name,
            )
        for name in sorted(documented_params - expected_params):
            self._finding(
                code=Code.STALE_PARAMETER,
                file=file,
                node=node,
                kind=kind,
                qualname=qualname,
                signature=signature,
                message=f"Documented parameter `{name}` is stale.",
                reason=(
                    "Args documents a name absent from the callable signature."
                ),
                suggestion=suggestion,
                subject=name,
            )
        yields: bool = self._yields(node=node)
        returns: bool = self._returns_value(node=node) and not yields
        if yields and "Yields" not in parsed.sections:
            self._finding(
                code=Code.RETURN_YIELD_MISMATCH,
                file=file,
                node=node,
                kind=kind,
                qualname=qualname,
                signature=signature,
                message="Generator is missing a Yields section.",
                reason="The callable directly contains yield/yield from.",
                suggestion=suggestion,
            )
        elif returns and "Returns" not in parsed.sections:
            self._finding(
                code=Code.MISSING_RETURN,
                file=file,
                node=node,
                kind=kind,
                qualname=qualname,
                signature=signature,
                message="Value-returning callable is missing Returns.",
                reason=(
                    "The implementation returns a value "
                    "or has a value annotation."
                ),
                suggestion=suggestion,
            )
        expected_raises: set[str] = set(self._raises(node=node))
        documented_raises: set[str] = set(parsed.sections.get("Raises", ()))
        for name in sorted(expected_raises - documented_raises):
            self._finding(
                code=Code.MISSING_EXCEPTION,
                file=file,
                node=node,
                kind=kind,
                qualname=qualname,
                signature=signature,
                message=f"Raised exception `{name}` is undocumented.",
                reason="A direct raise exists in this callable scope.",
                suggestion=suggestion,
                subject=name,
            )
        malformed: str
        for malformed in parsed.malformed:
            self._finding(
                code=Code.MALFORMED_DOCUMENTATION,
                file=file,
                node=node,
                kind=kind,
                qualname=qualname,
                signature=signature,
                message=malformed,
                reason=(
                    "The section entry does not match Google-style structure."
                ),
                suggestion=suggestion,
                confidence="medium",
            )
        self._exactus_nested_functions(file=file, node=node, qualname=qualname)

    def _exactus_class(
        self: Self,
        *,
        file: Path,
        node: ClassDef,
        prefix: str,
    ) -> None:
        """Exactus one Python class and recurse through members.

        Args:
            file: Source file.
            node: Class definition.
            prefix: Parent qualified-name prefix.

        """
        qualname: str = f"{prefix}.{node.name}" if prefix else node.name
        if not (self._config.public_only and node.name.startswith("_")):
            self._report.statistics["python"].symbols += 1
            suggestion: str = self._suggest_class(node=node)
            if (doc := get_docstring(node=node, clean=False)) is None:
                self._finding(
                    code=Code.MISSING_DOCUMENTATION,
                    file=file,
                    node=node,
                    kind="class",
                    qualname=qualname,
                    signature=f"class {node.name}",
                    message="Missing class docstring.",
                    reason="The class has no runtime docstring.",
                    suggestion=suggestion,
                )
            else:
                self._report.statistics["python"].documented += 1
                parsed: ParsedGoogleDoc = self._parse_doc(doc=doc)
                expected: set[str] = set(self._class_attributes(node=node))
                documented: set[str] = set(
                    parsed.sections.get("Attributes", ()),
                )
                name: str
                for name in sorted(expected - documented):
                    self._finding(
                        code=Code.MISSING_ATTRIBUTE,
                        file=file,
                        node=node,
                        kind="class",
                        qualname=qualname,
                        signature=f"class {node.name}",
                        message=f"Public attribute `{name}` is undocumented.",
                        reason="The class directly declares the attribute.",
                        suggestion=suggestion,
                        subject=name,
                    )
                instance_attributes: set[str] = {
                    child.target.attr
                    for method in node.body
                    if isinstance(method, (FunctionDef, AsyncFunctionDef))
                    for child in self._direct_nodes(node=method)
                    if isinstance(child, AnnAssign)
                    and isinstance(child.target, Attribute)
                    and isinstance(child.target.value, Name)
                    and child.target.value.id == "self"
                }
                for name in sorted(
                    documented - expected - instance_attributes,
                ):
                    self._finding(
                        code=Code.STALE_ATTRIBUTE,
                        file=file,
                        node=node,
                        kind="class",
                        qualname=qualname,
                        signature=f"class {node.name}",
                        message=(
                            f"Documented attribute `{name}` "
                            "is not directly declared."
                        ),
                        reason=(
                            "Attributes documents a name absent from direct "
                            "class assignments."
                        ),
                        suggestion=suggestion,
                        confidence="medium",
                        subject=name,
                    )
        statement: stmt
        for statement in node.body:
            if isinstance(statement, (FunctionDef, AsyncFunctionDef)):
                self._exactus_function(
                    file=file,
                    node=statement,
                    qualname=f"{qualname}.{statement.name}",
                    in_class=True,
                )
            elif isinstance(statement, ClassDef):
                self._exactus_class(file=file, node=statement, prefix=qualname)


class JavaScriptAnalyzer:
    """Analyze JSDoc using Python-only structural lexical recognition."""

    _identifier: Final[str] = r"[$A-Za-z_][$\w]*"
    _class_pattern: Final[Pattern[str]] = recompile(
        pattern=(
            rf"(?m)^[ \t]*(?:export\s+default\s+|export\s+)?"
            rf"class\s+({_identifier})\b"
        ),
    )
    _function_pattern: Final[Pattern[str]] = recompile(
        pattern=(
            rf"(?m)^[ \t]*(?:export[ \t]+default[ \t]+|export[ \t]+)?"
            rf"(?P<async>async[ \t]+)?function[ \t]*(?P<generator>\*)?"
            rf"[ \t]*(?P<name>{_identifier})[ \t]*\("
        ),
    )
    _variable_pattern: Final[Pattern[str]] = recompile(
        pattern=(
            rf"(?m)^[ \t]*(?:export[ \t]+)?(?:const|let|var)[ \t]+"
            rf"(?P<name>{_identifier})[ \t]*=[ \t]*"
            rf"(?:(?P<async>async)[ \t]+)?"
        ),
    )
    _method_pattern: Final[Pattern[str]] = recompile(
        pattern=(
            rf"(?m)^[ \t]*(?P<static>static[ \t]+)?"
            rf"(?P<async>async[ \t]+)?(?P<kind>get[ \t]+|set[ \t]+)?"
            rf"(?P<generator>\*)?[ \t]*(?P<name>#?{_identifier})[ \t]*\("
        ),
    )

    def __init__(self: Self, config: Config, report: Report) -> None:
        """Initialize the analyzer.

        Args:
            config: Scanner configuration.
            report: Shared report accumulator.

        """
        self._config: Config = config
        self._report: Report = report
        self._prepared: dict[Path, tuple[str | None, str | None]] = {}
        self._prepare_thread: Thread | None = None

    def prepare(self: Self, *, files: tuple[Path, ...]) -> None:
        """Read and prevalidate JavaScript files in one concurrent batch.

        Args:
            files: JavaScript files that will be analyzed.

        """
        if not files or not self._config.validate_javascript:
            return
        node: tuple[str, ...] | None = exactus_tool_prefix(
            tool="node",
            root=self._config.root,
        )
        if node is None:
            return
        sources: list[tuple[Path, str]] = []
        file: Path
        for file in files:
            try:
                source: str = file.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            sources.append((file, source))
        result: tuple[Path, str, str | None]
        for result in run(
            main=self._prepare_sources(sources=tuple(sources), node=node),
        ):
            self._prepared[result[0]] = (result[1], result[2])

    def prepare_background(self: Self, *, files: tuple[Path, ...]) -> None:
        """Start JavaScript preparation while Python analysis proceeds.

        Args:
            files: JavaScript files that will be analyzed.

        """
        if not files or not self._config.validate_javascript:
            return
        thread: Thread = Thread(
            target=self.prepare,
            kwargs={"files": files},
            name="docs-javascript-validation",
            daemon=False,
        )
        self._prepare_thread = thread
        thread.start()

    def finish_prepare(self: Self) -> None:
        """Wait for background JavaScript preparation to finish."""
        thread: Thread | None = self._prepare_thread
        if thread is None:
            return
        thread.join()
        self._prepare_thread = None

    def analyze(self: Self, file: Path) -> None:
        """Analyze one JavaScript file.

        Args:
            file: JavaScript source path.

        """
        stats: Statistics = self._report.statistics["javascript"]
        stats.discovered += 1
        if (source := self._source(file=file)) is None:
            return
        stats.parsed += 1
        self._report.lines["javascript"] += _count_lines(text=source)
        masked: str
        blocks: tuple[JsDocBlock, ...]
        masked, blocks = self._mask(source=source)
        symbol: JsSymbol
        for symbol in self._symbols(source=source, masked=masked):
            self._exactus_symbol(
                file=file,
                source=source,
                masked=masked,
                blocks=blocks,
                symbol=symbol,
            )

    _regex_keywords: Final[frozenset[str]] = frozenset(
        {
            "await",
            "case",
            "delete",
            "do",
            "else",
            "in",
            "instanceof",
            "new",
            "of",
            "return",
            "throw",
            "typeof",
            "void",
            "yield",
        },
    )

    @classmethod
    def _mask(
        cls: type[Self],
        source: str,
    ) -> tuple[str, tuple[JsDocBlock, ...]]:
        """Mask strings/comments while retaining source offsets.

        Args:
            source: JavaScript source.

        Returns:
            Masked source and discovered JSDoc blocks.

        """
        chars: list[str] = list(source)
        blocks: list[JsDocBlock] = []
        index: int = 0
        while index < len(source):
            pair: str = source[index : index + 2]
            if pair == "//":
                end: int = source.find("\n", index + 2)
                end = len(source) if end < 0 else end
            elif pair == "/*":
                end = cls._block_comment_end(source=source, start=index)
                if source[index : index + 3] == "/**":
                    blocks.append(
                        JsDocBlock(
                            start=index,
                            end=end,
                            content=source[index:end],
                        ),
                    )
            elif source[index] == "/":
                regex_end: int | None = cls._regex_end(
                    source=source,
                    start=index,
                )
                if regex_end is None:
                    index += 1
                    continue
                end = regex_end
            elif source[index] in {"'", '"', "`"}:
                end = cls._string_end(source=source, start=index)
            else:
                index += 1
                continue
            cls._blank_span(chars=chars, start=index, end=end)
            index = end
        return "".join(chars), tuple(blocks)

    @classmethod
    def _regex_opens(cls: type[Self], *, source: str, start: int) -> bool:
        """Return whether the `/` at `start` opens a regex literal.

        A `/` is a division operator when the previous significant token can
        end an expression; otherwise it opens a regex literal.

        Args:
            source: JavaScript source.
            start: Offset of the candidate `/`.

        Returns:
            Whether the slash opens a regex literal.

        """
        previous: int = start - 1
        while previous >= 0 and source[previous] in " \t":
            previous -= 1
        if previous < 0:
            return True
        char: str = source[previous]
        if char in ")]}'\"`":
            return False
        if char.isalnum() or char in "_$":
            word_match: Match[str] | None = search(
                pattern=r"[$A-Za-z_][$\w]*$",
                string=source[: previous + 1],
            )
            return (
                word_match is not None
                and word_match.group(0) in cls._regex_keywords
            )
        return True

    @classmethod
    def _regex_end(cls: type[Self], source: str, start: int) -> int | None:
        """Return the end offset of a regex literal, if `start` opens one.

        A `/` is a division operator when the previous significant token can
        end an expression; otherwise it opens a regex literal. Strings and
        comments before `start` have already been consumed, so scanning
        backward over the original source lands on real code.

        Args:
            source: JavaScript source.
            start: Offset of the candidate `/`.

        Returns:
            Offset just past the closing slash and flags, or `None` when the
            slash is a division operator or the literal is malformed.

        """
        if not cls._regex_opens(source=source, start=start):
            return None
        index: int = start + 1
        in_class: bool = False
        while index < len(source):
            char: str = source[index]
            if char == "\\":
                index += 2
                continue
            if char == "\n":
                return None
            if char == "[":
                in_class = True
            elif char == "]":
                in_class = False
            elif char == "/" and not in_class:
                index += 1
                while index < len(source) and source[index].isalnum():
                    index += 1
                return index
            index += 1
        return None

    @classmethod
    def _clean_jsdoc_lines(cls: type[Self], content: str) -> list[str]:
        """Strip JSDoc comment markers from block content.

        Args:
            content: Raw JSDoc block text.

        Returns:
            Cleaned lines with comment markers removed.

        """
        return list(
            map(
                cls._clean_jsdoc_line,
                content.removeprefix("/**").removesuffix("*/").splitlines(),
            ),
        )

    @classmethod
    def _parse_doc(cls: type[Self], block: JsDocBlock) -> JsDoc:
        """Parse core JSDoc tags.

        Args:
            block: JSDoc block.

        Returns:
            Structured documentation.

        """
        cleaned: list[str] = cls._clean_jsdoc_lines(content=block.content)
        summary: str = cls._jsdoc_summary(cleaned=cleaned)
        params: list[str] = []
        throws: list[str] = []
        properties: list[str] = []
        malformed: list[str] = []
        returns: bool = False
        yields: bool = False
        line: str
        for line in cleaned:
            if not line.startswith("@"):
                continue
            if line.startswith("@param"):
                match: Match[str] | None = rematch(
                    pattern=r"\[?([.$A-Za-z_][$\w.]*)",
                    string=cls._after_type(text=line.removeprefix("@param")),
                )
                (params if match else malformed).append(
                    match.group(1).split(sep=".", maxsplit=1)[0]
                    if match
                    else f"Malformed tag: {line}",
                )
            elif line.startswith(("@returns", "@return")):
                returns = True
            elif line.startswith(("@yields", "@yield")):
                yields = True
            elif line.startswith(("@throws", "@throw", "@exception")):
                match = rematch(
                    pattern=r"@(?:throws|throw|exception)(?:\s+\{([^}]*)\})?",
                    string=line,
                )
                if match and match.group(1):
                    throws.append(match.group(1).strip())
                else:
                    malformed.append(f"Malformed tag: {line}")
            elif line.startswith("@property"):
                match = rematch(
                    pattern=(
                        r"@property(?:\s+\{[^}]*\})?\s+\[?"
                        r"([.$A-Za-z_][$\w.]*)"
                    ),
                    string=line,
                )
                if match:
                    properties.append(
                        match.group(1).split(sep=".", maxsplit=1)[0],
                    )
                else:
                    malformed.append(f"Malformed tag: {line}")
        return JsDoc(
            summary=summary,
            params=tuple(dict.fromkeys(params)),
            returns=returns,
            yields=yields,
            throws=tuple(dict.fromkeys(throws)),
            properties=tuple(dict.fromkeys(properties)),
            malformed=tuple(malformed),
        )

    @classmethod
    def _parameters(cls: type[Self], text: str) -> tuple[tuple[str, str], ...]:
        """Return statically identifiable JavaScript parameters and types.

        Args:
            text: Raw parameter-list source.

        Returns:
            Name/type pairs.

        """
        result: list[tuple[str, str]] = []
        value: str
        for value in Text.balanced_split(value=text):
            name: str | None = cls._param_name(value=value)
            if name is not None:
                result.append((name, cls._param_type(value=value)))
        return tuple(result)

    @classmethod
    def _behavior(
        cls: type[Self],
        masked: str,
        symbol: JsSymbol,
    ) -> tuple[bool, bool, tuple[str, ...]]:
        """Infer return/yield/throw behavior from a symbol body.

        Args:
            masked: Masked source.
            symbol: Symbol metadata.

        Returns:
            Return-value flag, yield flag, and recognized exceptions.

        """
        if (
            symbol.kind == "class"
            or symbol.body_start is None
            or symbol.body_end is None
        ):
            return False, symbol.is_generator, ()
        body: str = masked[symbol.body_start : symbol.body_end + 1]
        returns: bool = bool(
            search(pattern=r"\breturn\s+(?!;|})", string=body),
        )
        yields: bool = symbol.is_generator or bool(
            search(pattern=r"\byield\b", string=body),
        )
        throws: tuple[str, ...] = tuple(
            dict.fromkeys(
                map(
                    cls._thrown_name,
                    finditer(
                        pattern=r"\bthrow\s+new\s+([$A-Za-z_][$\w]*)\b",
                        string=body,
                    ),
                ),
            ),
        )
        return returns and not yields, yields, throws

    @classmethod
    def _suggest(cls: type[Self], symbol: JsSymbol, masked: str) -> str:
        """Generate a JSDoc suggestion from signature and body behavior.

        Args:
            symbol: JavaScript symbol.
            masked: Masked JavaScript source.

        Returns:
            Suggested JSDoc block.

        """
        returns: bool
        yields: bool
        throws: tuple[str, ...]
        returns, yields, throws = cls._behavior(masked=masked, symbol=symbol)
        lines: list[str] = [
            "/**",
            " * "
            + Text.description(
                name=symbol.name.lstrip("#"),
                kind=symbol.kind,
                returns=returns or yields,
            ),
        ]
        name: str
        type_name: str
        for name, type_name in cls._parameters(text=symbol.params_text):
            lines.append(
                "".join(
                    (
                        f" * @param {{{type_name}}} {name} ",
                        Text.parameter_description(name=name),
                    ),
                ),
            )
        if yields:
            lines.append(" * @yields {*} Values produced by the iterator.")
        elif returns:
            lines.append(" * @returns {*} The resulting value.")
        lines.extend(map(cls._throws_entry, throws))
        lines.append(" */")
        return "\n".join(lines)

    @classmethod
    def _body_after_params(
        cls: type[Self],
        masked: str,
        close_paren: int,
    ) -> tuple[int | None, int | None]:
        """Locate a callable block body after its parameter list.

        Args:
            masked: Masked source.
            close_paren: Closing parameter parenthesis offset.

        Returns:
            Opening/closing brace offsets, if present.

        """
        cursor: int = close_paren + 1
        while cursor < len(masked) and masked[cursor].isspace():
            cursor += 1
        if masked.startswith("=>", cursor):
            cursor += 2
            while cursor < len(masked) and masked[cursor].isspace():
                cursor += 1
        if cursor >= len(masked) or masked[cursor] != "{":
            return None, None
        brace: int = cursor
        return brace, cls._matching(
            masked=masked,
            start=brace,
            opening="{",
            closing="}",
        )

    @staticmethod
    def _blank_span(chars: list[str], start: int, end: int) -> None:
        """Blank a source span while preserving newline positions.

        Args:
            chars: Mutable source characters.
            start: Inclusive span start.
            end: Exclusive span end.

        """
        position: int
        for position in range(start, end):
            if chars[position] != "\n":
                chars[position] = " "

    @staticmethod
    def _string_end(source: str, start: int) -> int:
        """Return the exclusive end of a quoted JavaScript string.

        Args:
            source: JavaScript source.
            start: Opening quote offset.

        Returns:
            Exclusive string end or source length for an unterminated string.

        """
        quote: str = source[start]
        position: int = start + 1
        while position < len(source):
            if source[position] == "\\":
                position += 2
            elif source[position] == quote:
                return position + 1
            else:
                position += 1
        return len(source)

    @staticmethod
    def _block_comment_end(source: str, start: int) -> int:
        """Return the exclusive end of a JavaScript block comment.

        Args:
            source: JavaScript source.
            start: Comment opening offset.

        Returns:
            Exclusive comment end.

        """
        end: int = source.find("*/", start + 2)
        return len(source) if end < 0 else end + 2

    @staticmethod
    def _matching(
        masked: str,
        start: int,
        opening: str,
        closing: str,
    ) -> int | None:
        """Find the matching delimiter in masked source.

        Args:
            masked: Source with strings/comments masked.
            start: Opening-delimiter offset.
            opening: Opening delimiter.
            closing: Closing delimiter.

        Returns:
            Matching delimiter offset, if found.

        """
        depth: int = 0
        index: int
        for index in range(start, len(masked)):
            if masked[index] == opening:
                depth += 1
            elif masked[index] == closing and (depth := depth - 1) == 0:
                return index
        return None

    @staticmethod
    def _brace_depth(masked: str, start: int, end: int) -> int:
        """Return brace nesting depth for a masked source interval.

        Args:
            masked: Source with comments and strings masked.
            start: Offset of the owning opening brace.
            end: Offset where depth is measured.

        Returns:
            Net brace depth.

        """
        return masked.count("{", start, end) - masked.count("}", start, end)

    @staticmethod
    def _preceding_doc(
        source: str,
        blocks: tuple[JsDocBlock, ...],
        start: int,
    ) -> JsDocBlock | None:
        """Return the nearest whitespace-adjacent JSDoc block.

        Args:
            source: JavaScript source.
            blocks: JSDoc blocks.
            start: Symbol start offset.

        Returns:
            Adjacent JSDoc block, if present.

        """
        candidate_list: list[JsDocBlock] = []
        candidate: JsDocBlock
        for candidate in blocks:
            if candidate.end > start:
                continue
            candidate_list.append(candidate)
        if not candidate_list:
            return None
        block: JsDocBlock = max(
            candidate_list,
            key=lambda candidate: candidate.end,
        )
        return block if source[block.end : start].strip() == "" else None

    @staticmethod
    def _clean_jsdoc_line(line: str) -> str:
        """Strip comment markers from one JSDoc content line.

        Args:
            line: Raw JSDoc block line.

        Returns:
            Cleaned line text.

        """
        return sub(pattern=r"^\s*\*\s?", repl="", string=line).strip()

    @staticmethod
    def _jsdoc_summary(cleaned: list[str]) -> str:
        """Return the first non-tag description line.

        Args:
            cleaned: Cleaned JSDoc lines.

        Returns:
            Summary text or an empty string.

        """
        line: str
        for line in cleaned:
            if line and not line.startswith("@"):
                return line
        return ""

    @staticmethod
    def _after_type(*, text: str) -> str:
        """Return tag text after an optional, possibly nested, type.

        JSDoc object types nest braces (``{{a?: number}}``), so the closing
        brace is found by depth rather than by the first ``}``.

        Args:
            text: Tag text following the tag name.

        Returns:
            The remaining text with leading whitespace removed.

        """
        stripped: str = text.lstrip()
        if not stripped.startswith("{"):
            return stripped
        depth: int = 0
        index: int
        character: str
        for index, character in enumerate(iterable=stripped):
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    return stripped[index + 1 :].lstrip()
        return ""

    @staticmethod
    def _param_name(value: str) -> str | None:
        """Extract the root name from a JavaScript parameter fragment.

        Args:
            value: Parameter source fragment.

        Returns:
            Root parameter name when statically identifiable.

        """
        stripped: str = value.strip().removeprefix("...").strip()
        if stripped.startswith(("{", "[")):
            return None
        match: Match[str] | None = rematch(
            pattern=r"([$A-Za-z_][$\w]*)",
            string=stripped,
        )
        return match.group(1) if match else None

    @staticmethod
    def _param_type(value: str) -> str:
        """Infer a conservative JSDoc type from a parameter default.

        Args:
            value: Parameter fragment.

        Returns:
            JSDoc type expression.

        """
        default: str = (
            value.split(sep="=", maxsplit=1)[1].strip() if "=" in value else ""
        )
        type_name: str = "*"
        if fullmatch(pattern=r"(?:true|false)", string=default):
            type_name = "boolean"
        elif fullmatch(pattern=r"[-+]?\d+(?:\.\d+)?", string=default):
            type_name = "number"
        elif default.startswith(("'", '"', "`")):
            type_name = "string"
        elif default.startswith("["):
            type_name = "Array"
        elif default.startswith("{"):
            type_name = "Object"
        elif "=>" in default or default.startswith("function"):
            type_name = "Function"
        return type_name

    @staticmethod
    def _thrown_name(match: Match[str]) -> str:
        """Return the thrown type name captured by one match.

        Args:
            match: ``throw new`` pattern match.

        Returns:
            Captured exception type name.

        """
        return match.group(1)

    @staticmethod
    def _throws_entry(name: str) -> str:
        """Return one JSDoc ``@throws`` entry line.

        Args:
            name: Documented exception type name.

        Returns:
            JSDoc ``@throws`` line.

        """
        return f" * @throws {{{name}}} When the operation cannot complete."

    @staticmethod
    async def _node_check(
        *,
        source: str,
        node: tuple[str, ...],
    ) -> CompletedProcess[str]:
        """Validate JavaScript syntax with the resolved Node command.

        Args:
            source: JavaScript source text.
            node: Node command prefix, either an installed executable or
                the offline Linux AMD64 bundle plus ``node``.

        Returns:
            Completed Node syntax-check process.

        """
        process: Process = await create_subprocess_exec(
            *node,
            "--input-type=module",
            "--check",
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
        )
        stdout: bytes
        stderr: bytes
        stdout, stderr = await process.communicate(input=source.encode())
        return CompletedProcess(
            args=(*node, "--input-type=module", "--check"),
            returncode=process.returncode or 0,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
        )

    def _class_symbols(
        self: Self,
        source: str,
        masked: str,
    ) -> tuple[list[JsSymbol], list[tuple[int, int, str]]]:
        """Discover JavaScript classes and direct methods.

        Args:
            source: Original source.
            masked: Masked source preserving offsets.

        Returns:
            Symbols and class source ranges.

        """
        symbols: list[JsSymbol] = []
        ranges: list[tuple[int, int, str]] = []
        match: Match[str]
        for match in self._class_pattern.finditer(string=masked):
            brace: int = masked.find("{", match.end())
            end: int | None = (
                self._matching(
                    masked=masked,
                    start=brace,
                    opening="{",
                    closing="}",
                )
                if brace >= 0
                else None
            )
            if brace < 0 or end is None:
                continue
            name: str = match.group(1)
            ranges.append((brace, end, name))
            symbols.append(
                JsSymbol(
                    name=name,
                    qualname=name,
                    kind="class",
                    start=match.start(),
                    body_start=brace,
                    body_end=end,
                    params_text="",
                    signature=f"class {name}",
                    is_async=False,
                    is_generator=False,
                ),
            )
            symbols.extend(
                self._class_methods(
                    source=source,
                    masked=masked,
                    class_name=name,
                    brace=brace,
                    end=end,
                ),
            )
        return symbols, ranges

    def _class_methods(
        self: Self,
        source: str,
        masked: str,
        class_name: str,
        brace: int,
        end: int,
    ) -> tuple[JsSymbol, ...]:
        """Discover direct methods inside one JavaScript class.

        Args:
            source: Original source.
            masked: Masked source.
            class_name: Owning class name.
            brace: Opening class brace.
            end: Closing class brace.

        Returns:
            Direct method symbols.

        """
        symbols: list[JsSymbol] = []
        region: str = masked[brace + 1 : end]
        match: Match[str]
        for match in self._method_pattern.finditer(string=region):
            absolute: int = brace + 1 + match.start()
            line_start: int = masked.rfind("\n", brace + 1, absolute) + 1
            if (
                self._brace_depth(masked=masked, start=brace, end=absolute)
                != 1
                or masked[line_start:absolute].strip()
            ):
                continue
            open_paren: int = brace + match.end()
            close: int | None = self._matching(
                masked=masked,
                start=open_paren,
                opening="(",
                closing=")",
            )
            if close is None:
                continue
            body_start: int | None
            body_end: int | None
            body_start, body_end = self._body_after_params(
                masked=masked,
                close_paren=close,
            )
            # A class-field expression can begin with a call on a new
            # line. A method declaration must have its own block body.
            if body_start is None or body_end is None:
                continue
            method_name: str = match.group("name")
            raw_kind: str = (match.group("kind") or "").strip()
            method_kind: SymbolKind = (
                "getter"
                if raw_kind == "get"
                else "setter"
                if raw_kind == "set"
                else "method"
            )
            parameters: str = source[open_paren + 1 : close]
            symbols.append(
                JsSymbol(
                    name=method_name,
                    qualname=f"{class_name}.{method_name}",
                    kind=method_kind,
                    start=absolute,
                    body_start=body_start,
                    body_end=body_end,
                    params_text=parameters,
                    signature=(
                        f"{'async ' if match.group('async') else ''}"
                        f"{method_name}({parameters.strip()})"
                    ),
                    is_async=bool(match.group("async")),
                    is_generator=bool(match.group("generator")),
                ),
            )
        return tuple(symbols)

    def _function_symbols(
        self: Self,
        source: str,
        masked: str,
        class_ranges: list[tuple[int, int, str]],
    ) -> tuple[JsSymbol, ...]:
        """Discover named JavaScript function declarations.

        Args:
            source: Original source.
            masked: Masked source.
            class_ranges: Class source ranges to exclude.

        Returns:
            Function symbols outside classes.

        """
        symbols: list[JsSymbol] = []
        match: Match[str]
        for match in self._function_pattern.finditer(string=masked):
            in_class: bool = False
            start: int
            end: int
            for start, end, _ in class_ranges:
                if start <= match.start() <= end:
                    in_class = True
                    break
            if in_class:
                continue
            open_paren: int = match.end() - 1
            close: int | None = self._matching(
                masked=masked,
                start=open_paren,
                opening="(",
                closing=")",
            )
            if close is None:
                continue
            body_start: int | None
            body_end: int | None
            body_start, body_end = self._body_after_params(
                masked=masked,
                close_paren=close,
            )
            name: str = match.group("name")
            parameters: str = source[open_paren + 1 : close]
            symbols.append(
                JsSymbol(
                    name=name,
                    qualname=name,
                    kind="function",
                    start=match.start(),
                    body_start=body_start,
                    body_end=body_end,
                    params_text=parameters,
                    signature=(
                        f"{'async ' if match.group('async') else ''}"
                        f"function{'*' if match.group('generator') else ''} "
                        f"{name}({parameters.strip()})"
                    ),
                    is_async=bool(match.group("async")),
                    is_generator=bool(match.group("generator")),
                ),
            )
        return tuple(symbols)

    def _variable_symbol(
        self: Self,
        source: str,
        masked: str,
        match: Match[str],
    ) -> JsSymbol | None:
        """Build an arrow/function-expression symbol from a variable match.

        Args:
            source: Original source.
            masked: Masked source.
            match: Variable-declaration match.

        Returns:
            Discovered symbol when the initializer is callable.

        """
        cursor: int = match.end()
        name: str = match.group("name")
        if masked.startswith("function", cursor):
            return self._function_expression_symbol(
                source=source,
                masked=masked,
                match=match,
                cursor=cursor,
                name=name,
            )
        return self._arrow_symbol(
            source=source,
            masked=masked,
            match=match,
            cursor=cursor,
            name=name,
        )

    def _function_expression_symbol(
        self: Self,
        source: str,
        masked: str,
        match: Match[str],
        cursor: int,
        name: str,
    ) -> JsSymbol | None:
        """Build a symbol for a variable-bound function expression.

        Args:
            source: Original source.
            masked: Masked source.
            match: Variable-declaration match.
            cursor: Initializer offset.
            name: Variable name.

        Returns:
            Function-expression symbol when parseable.

        """
        function_match: Match[str] | None = rematch(
            pattern=r"function\s*\*?\s*(?:[$A-Za-z_][$\w]*)?\s*\(",
            string=masked[cursor:],
        )
        if function_match is None:
            return None
        open_paren: int = cursor + function_match.end() - 1
        close: int | None = self._matching(
            masked=masked,
            start=open_paren,
            opening="(",
            closing=")",
        )
        if close is None:
            return None
        parameters: str = source[open_paren + 1 : close]
        body_start: int | None
        body_end: int | None
        body_start, body_end = self._body_after_params(
            masked=masked,
            close_paren=close,
        )
        return JsSymbol(
            name=name,
            qualname=name,
            kind="arrow",
            start=match.start(),
            body_start=body_start,
            body_end=body_end,
            params_text=parameters,
            signature=f"{name} = ({parameters.strip()}) =>",
            is_async=bool(match.group("async")),
            is_generator=(
                "*" in function_match.group(0).split(sep="(", maxsplit=1)[0]
            ),
        )

    def _arrow_symbol(
        self: Self,
        source: str,
        masked: str,
        match: Match[str],
        cursor: int,
        name: str,
    ) -> JsSymbol | None:
        """Build a symbol for a variable-bound arrow function.

        Args:
            source: Original source.
            masked: Masked source.
            match: Variable-declaration match.
            cursor: Initializer offset.
            name: Variable name.

        Returns:
            Arrow symbol when parseable.

        """
        boundary: int = len(masked)
        index: int
        for index in (masked.find(";", cursor), masked.find("\n", cursor)):
            if index >= 0 and index < boundary:
                boundary = index
        open_paren: int = masked.find("(", cursor, boundary)
        arrow: int = masked.find("=>", cursor)
        if open_paren < 0 or arrow < 0 or open_paren > arrow:
            return self._single_parameter_arrow(
                masked=masked,
                match=match,
                cursor=cursor,
                name=name,
            )
        close: int | None = self._matching(
            masked=masked,
            start=open_paren,
            opening="(",
            closing=")",
        )
        if (
            close is None
            or rematch(pattern=r"\s*=>", string=masked[close + 1 :]) is None
        ):
            return None
        parameters: str = source[open_paren + 1 : close]
        body_start: int | None
        body_end: int | None
        body_start, body_end = self._body_after_params(
            masked=masked,
            close_paren=close,
        )
        return JsSymbol(
            name=name,
            qualname=name,
            kind="arrow",
            start=match.start(),
            body_start=body_start,
            body_end=body_end,
            params_text=parameters,
            signature=f"{name} = ({parameters.strip()}) =>",
            is_async=bool(match.group("async")),
            is_generator=False,
        )

    def _single_parameter_arrow(
        self: Self,
        masked: str,
        match: Match[str],
        cursor: int,
        name: str,
    ) -> JsSymbol | None:
        """Build a symbol for an unparenthesized one-parameter arrow.

        Args:
            masked: Masked source.
            match: Variable-declaration match.
            cursor: Initializer offset.
            name: Variable name.

        Returns:
            Arrow symbol when parseable.

        """
        single: Match[str] | None = rematch(
            pattern=rf"(?P<param>{self._identifier})\s*=>",
            string=masked[cursor:],
        )
        if single is None:
            return None
        parameters: str = single.group("param")
        arrow: int = cursor + single.end() - 2
        after_arrow: int = arrow + 2
        brace: int = masked.find("{", after_arrow)
        line_end: int = masked.find("\n", after_arrow)
        body_start: int | None = (
            brace
            if brace >= 0 and (line_end < 0 or brace < line_end)
            else None
        )
        body_end: int | None = (
            self._matching(
                masked=masked,
                start=body_start,
                opening="{",
                closing="}",
            )
            if body_start is not None
            else None
        )
        return JsSymbol(
            name=name,
            qualname=name,
            kind="arrow",
            start=match.start(),
            body_start=body_start,
            body_end=body_end,
            params_text=parameters,
            signature=f"{name} = ({parameters}) =>",
            is_async=bool(match.group("async")),
            is_generator=False,
        )

    def _variable_symbols(
        self: Self,
        source: str,
        masked: str,
        class_ranges: list[tuple[int, int, str]],
    ) -> tuple[JsSymbol, ...]:
        """Discover variable-bound JavaScript callables.

        Args:
            source: Original source.
            masked: Masked source.
            class_ranges: Class source ranges to exclude.

        Returns:
            Callable symbols outside classes.

        """
        symbols: list[JsSymbol] = []
        match: Match[str]
        for match in self._variable_pattern.finditer(string=masked):
            in_class: bool = False
            start: int
            end: int
            for start, end, _ in class_ranges:
                if start <= match.start() <= end:
                    in_class = True
                    break
            if in_class:
                continue
            if symbol := self._variable_symbol(
                source=source,
                masked=masked,
                match=match,
            ):
                symbols.append(symbol)
        return tuple(symbols)

    def _symbols(self: Self, source: str, masked: str) -> tuple[JsSymbol, ...]:
        """Discover documentable JavaScript symbols.

        Args:
            source: Original source.
            masked: Masked source preserving offsets.

        Returns:
            Deterministically ordered symbols.

        """
        class_symbols: list[JsSymbol]
        class_ranges: list[tuple[int, int, str]]
        class_symbols, class_ranges = self._class_symbols(
            source=source,
            masked=masked,
        )
        symbols: tuple[JsSymbol, ...] = (
            *class_symbols,
            *self._function_symbols(
                source=source,
                masked=masked,
                class_ranges=class_ranges,
            ),
            *self._variable_symbols(
                source=source,
                masked=masked,
                class_ranges=class_ranges,
            ),
        )
        unique: dict[tuple[int, str], JsSymbol] = {}
        symbol: JsSymbol
        for symbol in symbols:
            unique[(symbol.start, symbol.qualname)] = symbol
        return tuple(
            sorted(
                unique.values(),
                key=lambda symbol: (symbol.start, symbol.qualname),
            ),
        )

    def _finding(
        self: Self,
        *,
        code: Code,
        file: Path,
        source: str,
        symbol: JsSymbol,
        confidence: Confidence = "high",
        **details: str,
    ) -> None:
        """Handle finding.

        Args:
            code: Code.
            file: File.
            source: Source.
            symbol: Symbol.
            confidence: Confidence.
            details: Details, optionally naming a member ``subject``.

        """
        line: int
        column: int
        line, column = Text.line_column(source=source, offset=symbol.start)
        self._report.add(
            finding=Finding(
                code=code,
                language="javascript",
                severity="warning",
                confidence=confidence,
                file=file,
                line=line,
                column=column,
                kind=symbol.kind,
                qualname=symbol.qualname,
                signature=symbol.signature,
                message=details["message"],
                reason=details["reason"],
                suggestion=details["suggestion"],
                subject=details.get("subject", ""),
            ),
        )

    async def _validate_one(
        self: Self,
        *,
        file: Path,
        source: str,
        node: tuple[str, ...],
        semaphore: Semaphore,
    ) -> tuple[Path, str, str | None]:
        """Validate one JavaScript source under the shared concurrency bound.

        Args:
            file: JavaScript source path.
            source: JavaScript source text.
            node: Resolved Node command.
            semaphore: Shared subprocess concurrency bound.

        Returns:
            File, source, and optional validation error.

        """
        async with semaphore:
            result: CompletedProcess[str] = await self._node_check(
                source=source,
                node=node,
            )
        return (
            file,
            source,
            None
            if result.returncode == 0
            else (
                result.stderr.strip() or "JavaScript syntax validation failed."
            ),
        )

    async def _prepare_sources(
        self: Self,
        *,
        sources: tuple[tuple[Path, str], ...],
        node: tuple[str, ...],
    ) -> tuple[tuple[Path, str, str | None], ...]:
        """Validate JavaScript sources concurrently with bounded processes.

        Args:
            sources: Read JavaScript source files.
            node: Resolved Node command.

        Returns:
            Validation results in deterministic input order.

        """
        semaphore: Semaphore = Semaphore(value=16)
        return tuple(
            await gather(
                *(
                    self._validate_one(
                        file=file,
                        source=source,
                        node=node,
                        semaphore=semaphore,
                    )
                    for file, source in sources
                ),
            ),
        )

    def _validate(self: Self, source: str) -> str | None:
        """Validate balanced JavaScript delimiters when configured.

        Args:
            source: JavaScript source text.

        Returns:
            Error text for unbalanced delimiters, otherwise None.

        """
        if not self._config.validate_javascript:
            return None
        node: tuple[str, ...] | None = exactus_tool_prefix(
            tool="node",
            root=self._config.root,
        )
        if node is not None:
            result: CompletedProcess[str] = run(
                main=self._node_check(source=source, node=node),
            )
            return (
                None
                if result.returncode == 0
                else (
                    result.stderr.strip()
                    or "JavaScript syntax validation failed."
                )
            )
        masked: str = self._mask(source=source)[0]
        pairs: dict[str, str] = {")": "(", "]": "[", "}": "{"}
        stack: list[str] = []
        char: str
        for char in masked:
            if char in "([{":
                stack.append(char)
            elif char in pairs and (not stack or stack.pop() != pairs[char]):
                return "JavaScript contains unbalanced delimiters."
        return "JavaScript contains unbalanced delimiters." if stack else None

    def _source(self: Self, file: Path) -> str | None:
        """Read and optionally syntax-check one JavaScript source file.

        Args:
            file: JavaScript source path.

        Returns:
            Source text when readable and valid, otherwise None.

        """
        stats: Statistics = self._report.statistics["javascript"]
        prepared: tuple[str | None, str | None] | None = self._prepared.pop(
            file,
            None,
        )
        if prepared is not None:
            source: str | None = prepared[0]
            error_text: str | None = prepared[1]
            if source is not None and error_text is None:
                return source
            if source is not None:
                stats.failed += 1
                self._report.add(
                    finding=Finding(
                        code=Code.ANALYSIS_FAILURE,
                        language="javascript",
                        severity="error",
                        confidence="high",
                        file=file,
                        line=1,
                        column=0,
                        kind="module",
                        qualname=file.stem,
                        signature="",
                        message="JavaScript syntax validation failed.",
                        reason=error_text
                        or "JavaScript syntax validation failed.",
                        suggestion=(
                            "Fix the syntax error and rerun the exactus."
                        ),
                    ),
                )
                return None
        try:
            source = file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            stats.failed += 1
            self._report.add(
                finding=Finding(
                    code=Code.ANALYSIS_FAILURE,
                    language="javascript",
                    severity="error",
                    confidence="high",
                    file=file,
                    line=1,
                    column=0,
                    kind="module",
                    qualname=file.stem,
                    signature="",
                    message=f"JavaScript read failed: {error}",
                    reason="The source could not be read.",
                    suggestion="Fix the read error and rerun the exactus.",
                ),
            )
            return None
        if error := self._validate(source=source):
            stats.failed += 1
            self._report.add(
                finding=Finding(
                    code=Code.ANALYSIS_FAILURE,
                    language="javascript",
                    severity="error",
                    confidence="high",
                    file=file,
                    line=1,
                    column=0,
                    kind="module",
                    qualname=file.stem,
                    signature="",
                    message="JavaScript syntax validation failed.",
                    reason=error,
                    suggestion="Fix the syntax error and rerun the exactus.",
                ),
            )
            return None
        return source

    def _exactus_symbol(
        self: Self,
        file: Path,
        source: str,
        masked: str,
        blocks: tuple[JsDocBlock, ...],
        symbol: JsSymbol,
    ) -> None:
        """Exactus one discovered JavaScript symbol.

        Args:
            file: Source file.
            source: Original source text.
            masked: Masked source text.
            blocks: Discovered JSDoc blocks.
            symbol: Symbol to exactus.

        """
        if symbol.name in Constants.js_exempt_names or (
            self._config.public_only and symbol.name.startswith(("_", "#"))
        ):
            return
        self._report.statistics["javascript"].symbols += 1
        suggestion: str = self._suggest(symbol=symbol, masked=masked)
        block: JsDocBlock | None = self._preceding_doc(
            source=source,
            blocks=blocks,
            start=symbol.start,
        )
        if block is None:
            self._finding(
                code=Code.MISSING_DOCUMENTATION,
                file=file,
                source=source,
                symbol=symbol,
                message="Missing JSDoc block.",
                reason=("No whitespace-adjacent JSDoc precedes this symbol."),
                suggestion=suggestion,
            )
            return
        self._report.statistics["javascript"].documented += 1
        parsed: JsDoc = self._parse_doc(block=block)
        self._exactus_js_contract(
            file=file,
            source=source,
            contract=(masked, symbol, parsed, suggestion),
        )

    def _exactus_js_contract(
        self: Self,
        *,
        file: Path,
        source: str,
        contract: tuple[str, JsSymbol, JsDoc, str],
    ) -> None:
        """Handle exactus js contract.

        Args:
            file: File.
            source: Source.
            contract: Contract.

        """
        masked: str
        symbol: JsSymbol
        parsed: JsDoc
        suggestion: str
        masked, symbol, parsed, suggestion = contract
        if not parsed.summary:
            self._finding(
                code=Code.MISSING_DESCRIPTION,
                file=file,
                source=source,
                symbol=symbol,
                message="JSDoc has no useful summary.",
                reason="The block contains no non-tag description line.",
                suggestion=suggestion,
            )
        expected: set[str] = set()
        name: str
        for name, _ in self._parameters(text=symbol.params_text):
            expected.add(name)
        documented: set[str] = set(parsed.params)
        for name in sorted(expected - documented):
            self._finding(
                code=Code.MISSING_PARAMETER,
                file=file,
                source=source,
                symbol=symbol,
                message=f"Parameter `{name}` is undocumented.",
                reason=(
                    "The parameter exists in the signature but not in @param."
                ),
                suggestion=suggestion,
                subject=name,
            )
        for name in sorted(documented - expected):
            self._finding(
                code=Code.STALE_PARAMETER,
                file=file,
                source=source,
                symbol=symbol,
                message=f"Documented parameter `{name}` is stale.",
                reason=(
                    "@param documents a name absent from the static signature."
                ),
                suggestion=suggestion,
                subject=name,
            )
        returns: bool
        yields: bool
        throws: tuple[str, ...]
        returns, yields, throws = self._behavior(masked=masked, symbol=symbol)
        if yields and not (parsed.yields or parsed.returns):
            self._finding(
                code=Code.RETURN_YIELD_MISMATCH,
                file=file,
                source=source,
                symbol=symbol,
                message="Generator is missing @yields.",
                reason="The function is a generator or contains yield.",
                suggestion=suggestion,
            )
        elif returns and not parsed.returns:
            self._finding(
                code=Code.MISSING_RETURN,
                file=file,
                source=source,
                symbol=symbol,
                message="Value-returning callable is missing @returns.",
                reason="The callable body contains a value return.",
                suggestion=suggestion,
            )
        documented_throws: set[str] = set(parsed.throws)
        for name in sorted(set(throws) - documented_throws):
            self._finding(
                code=Code.MISSING_EXCEPTION,
                file=file,
                source=source,
                symbol=symbol,
                message=f"Thrown exception `{name}` is undocumented.",
                reason=(
                    "The body contains a statically recognized "
                    "throw new expression."
                ),
                suggestion=suggestion,
                confidence="medium",
                subject=name,
            )
        malformed: str
        for malformed in parsed.malformed:
            self._finding(
                code=Code.MALFORMED_DOCUMENTATION,
                file=file,
                source=source,
                symbol=symbol,
                message=malformed,
                reason=(
                    "The JSDoc tag cannot be parsed into "
                    "the expected contract."
                ),
                suggestion=suggestion,
                confidence="medium",
            )


def _counts(*, values: list[str]) -> dict[str, JsonValue]:
    """Count occurrences of each value.

    Args:
        values: Values to count.

    Returns:
        Sorted value-to-count mapping.

    """
    return {value: values.count(value) for value in sorted(set(values))}


def _blocking(*, config: Config, finding: Finding) -> bool:
    """Report whether a finding fails the run under ``--fail-on``.

    Args:
        config: Runtime configuration carrying the failure threshold.
        finding: Documentation-contract finding.

    Returns:
        ``True`` when the finding meets the failure threshold.

    """
    return (
        config.fail_on is not None
        and Constants.severity_rank[finding.severity]
        >= Constants.severity_rank[config.fail_on]
    )


def _normalized_finding(
    *,
    index: int,
    config: Config,
    finding: Finding,
) -> dict[str, JsonValue]:
    """Return one finding in the normalized shape.

    Args:
        index: One-based position in the ordered result.
        config: Runtime configuration.
        finding: Documentation-contract finding.

    Returns:
        Normalized finding keeping every legacy field.

    """
    relative: dict[str, str | int] = finding.relative_dict(root=config.root)
    code: str = finding.code.value
    qualified: str = (
        f"{finding.qualname}.{finding.subject}"
        if finding.subject
        else finding.qualname
    )
    return {
        "id": f"{Constants.id_prefix}-{index:03d}",
        "title": f"{Constants.code_titles.get(code, code)}: {qualified}",
        "path": finding.file.relative_to(config.root).as_posix(),
        "rule": code,
        "blocking": _blocking(config=config, finding=finding),
        **relative,
    }


def _scope(*, config: Config, skipped: tuple[Skip, ...]) -> JsonValue:
    """Return the ``scope`` block of a documentation exactus.

    Args:
        config: Runtime configuration.
        skipped: Discovered files left out by the include/exclude globs.

    Returns:
        Include globs, exclude globs and skipped targets.

    """
    includes: list[str] = list(config.includes)
    if not includes:
        language: str
        for language in sorted(config.languages):
            includes.extend(Constants.default_includes[language])
    excludes: list[str] = [
        *config.excludes,
        *(
            pattern if "/" in pattern else f"**/{pattern}/**"
            for pattern in sorted(config.exclude_dirs)
        ),
        *(("**/.*/**",) if config.exclude_hidden_dirs else ()),
        *Constants.builtin_excludes,
    ]
    return {
        "include": cast(typ="JsonValue", val=includes),
        "exclude": cast(typ="JsonValue", val=excludes),
        "skipped": [
            {"target": skip.target, "reason": skip.reason} for skip in skipped
        ],
    }


def _extension(
    *,
    config: Config,
    report: Report,
    rules: list[str],
) -> JsonValue:
    """Return the ``extension`` block of a documentation exactus.

    Args:
        config: Runtime configuration.
        report: Collected findings and per-language counters.
        rules: Finding codes in report order.

    Returns:
        Per-language documentation statistics, rule counts, the failure
        threshold and the documentation metrics.

    """
    languages: list[JsonValue] = []
    language: Language
    for language in sorted(config.languages):
        statistics: Statistics = report.statistics[language]
        languages.append(
            {
                **asdict(obj=statistics),
                "language": language,
                "coverage_percent": (
                    round(
                        number=statistics.documented
                        * 100
                        / statistics.symbols,
                        ndigits=1,
                    )
                    if statistics.symbols
                    else None
                ),
            },
        )
    return {
        "languages": languages,
        "rules": [
            {"rule": rule, "title": title, "count": rules.count(rule)}
            for rule, title in Constants.code_titles.items()
        ],
        "fail_on": config.fail_on or "never",
        "metrics": _metrics(config=config, report=report),
    }


def _count_lines(*, text: str) -> int:
    """Count the lines of a text the way ``_measure`` counts files.

    Lines end at a line feed; a last line without one still counts, so
    code and Markdown line totals use the same rule.

    Args:
        text: Decoded file text.

    Returns:
        Number of lines; ``0`` for empty text.

    """
    return text.count("\n") + (0 if not text or text.endswith("\n") else 1)


def _metrics(*, config: Config, report: Report) -> JsonValue:
    """Return code volume for the docstring and JSDoc analysis.

    Args:
        config: Runtime configuration.
        report: Collected per-language counters.

    Returns:
        Successfully analyzed files and lines per language.

    """
    return {
        "languages": [
            {
                "language": language,
                "files_analyzed": report.statistics[language].parsed,
                "lines_analyzed": report.lines[language],
            }
            for language in sorted(config.languages)
        ],
    }


def report_data(
    *,
    config: Config,
    report: Report,
    eligible: int,
    skipped: tuple[Skip, ...],
) -> dict[str, JsonValue]:
    """Return the normalized JSON payload of one documentation exactus.

    Args:
        config: Runtime configuration.
        report: Collected findings (sorted) and per-language counters.
        eligible: Source files discovered under the root.
        skipped: Discovered files left out by the include/exclude globs.

    Returns:
        ``summary``, ``scope``, ``findings`` and ``extension`` blocks
        plus the legacy ``root`` and ``statistics`` keys.

    """
    statistics: dict[str, JsonValue] = {
        language: cast(
            typ="JsonValue",
            val=asdict(obj=report.statistics[language]),
        )
        for language in sorted(config.languages)
    }
    rules: list[str] = [finding.code.value for finding in report.findings]
    return {
        "root": str(object=config.root),
        "statistics": statistics,
        "summary": {
            "targets_eligible": eligible,
            "targets_analyzed": eligible - len(skipped),
            "findings_total": len(report.findings),
            "severity": _counts(
                values=[finding.severity for finding in report.findings],
            ),
        },
        "scope": _scope(config=config, skipped=skipped),
        "findings": [
            finding_excerpt(
                finding=_normalized_finding(
                    index=index,
                    config=config,
                    finding=finding,
                ),
                root=config.root,
                context=config.context_lines,
            )
            for index, finding in enumerate(iterable=report.findings, start=1)
        ],
        "extension": _extension(config=config, report=report, rules=rules),
    }


class DocumentationExactus:
    """Coordinate discovery, analysis, reporting, and exit status."""

    def __init__(
        self: Self,
        config: Config,
        *,
        file_filter: Callable[[Path], bool] | None = None,
    ) -> None:
        """Initialize the exactus.

        Args:
            config: Runtime configuration.
            file_filter: Optional predicate restricting discovered files.

        """
        self._config: Config = config
        self._file_filter: Callable[[Path], bool] | None = file_filter
        self._report: Report = Report()
        self._python: PythonAnalyzer = PythonAnalyzer(
            config=config,
            report=self._report,
        )
        self._javascript: JavaScriptAnalyzer = JavaScriptAnalyzer(
            config=config,
            report=self._report,
        )

    def files(self: Self) -> tuple[Path, ...]:
        """Discover source files deterministically.

        Returns:
            Sorted source paths.

        """
        return self._discover()

    def run(self: Self) -> int:
        """Execute the exactus and write reports.

        Returns:
            Process exit status.

        """
        trace(step="stage: analyze docstrings", depth=1)
        files: tuple[Path, ...]
        files = self._discover()
        trace(step=f"docs: {len(files)} files discovered", depth=2)
        left_out: list[Skip] = []
        eligible: list[Path] = []
        file: Path
        for file in files:
            if self._file_filter is not None and not self._file_filter(file):
                left_out.append(
                    Skip(
                        target=file.relative_to(self._config.root).as_posix(),
                        reason=Constants.excluded_reason,
                    ),
                )
            else:
                eligible.append(file)
        python_files: tuple[Path, ...] = tuple(
            file for file in eligible if file.suffix == ".py"
        )
        javascript_files: tuple[Path, ...] = tuple(
            file for file in eligible if file.suffix != ".py"
        )
        self._javascript.prepare_background(files=javascript_files)
        progress_interval: int = max(1, len(eligible) // 32)
        completed: int = 0
        for file in python_files:
            self._python.analyze(file=file)
            completed += 1
            if completed % progress_interval == 0:
                emit_progress(
                    state="RUNNING",
                    completed=completed,
                    total=len(eligible),
                    step="analyzing docstrings",
                    detail=file.name,
                )
        self._javascript.finish_prepare()
        for file in javascript_files:
            self._javascript.analyze(file=file)
            completed += 1
            if completed % progress_interval == 0 or completed == len(
                eligible,
            ):
                emit_progress(
                    state="RUNNING",
                    completed=completed,
                    total=len(eligible),
                    step="analyzing docstrings",
                    detail=file.name,
                )
        self._report.findings.sort(
            key=lambda finding: (
                finding.file.as_posix().casefold(),
                finding.line,
                finding.column,
                finding.code.value,
                finding.qualname,
            ),
        )
        trace(
            step=(
                f"docs: {len(self._report.findings)} findings, "
                f"{len(left_out)} excluded"
            ),
            depth=2,
        )
        trace(step="stage: report", depth=1)
        _ = consume(
            value=ReportBundle.write(
                paths=ReportPaths(
                    markdown=self._config.markdown,
                    json=self._config.json_output,
                    web=self._config.markdown.with_name(
                        name=f"{self._config.markdown.stem}_web",
                    ),
                ),
                analyzer="documentation",
                title="Documentation Exactus",
                # The stamp stage renders result.md from
                # templates/markdown/.
                markdown="",
                data=report_data(
                    config=self._config,
                    report=self._report,
                    eligible=len(files),
                    skipped=tuple(left_out),
                ),
            ),
        )
        trace(
            step=f"report: bundle written — {self._config.markdown}",
            depth=2,
        )
        trace(step="stage: fail-on gate", depth=1)
        if self._config.fail_on is None:
            trace(step="docs: gate disabled — status 0", depth=2)
            return 0
        threshold: int = Constants.severity_rank[self._config.fail_on]
        finding: Finding
        for finding in self._report.findings:
            if Constants.severity_rank[finding.severity] >= threshold:
                trace(
                    step=(
                        f"docs: {finding.code.value} at "
                        f"{finding.file.as_posix()}:{finding.line} meets "
                        f"gate {self._config.fail_on} — status 1"
                    ),
                    depth=2,
                )
                return 1
        trace(step="docs: gate passed — status 0", depth=2)
        return 0

    def _excluded_directory(self: Self, *, root: Path, directory: str) -> bool:
        """Determine whether a directory matches an exclusion pattern.

        Args:
            root: Parent directory containing the candidate.
            directory: Candidate directory name.

        Returns:
            Whether the directory must be excluded.

        """
        if self._config.exclude_hidden_dirs and directory.startswith("."):
            return True
        if is_reports_tree(directory=root / directory):
            return True
        relative: str = (
            (root / directory).relative_to(self._config.root).as_posix()
        )
        pattern: str
        for pattern in self._config.exclude_dirs:
            if fnmatchcase(
                name=relative if "/" in pattern else directory,
                pat=pattern,
            ) or (
                pattern.endswith("/**")
                and relative == pattern[:-3].rstrip("/")
            ):
                return True
        return False

    def _relative_finding(
        self: Self,
        finding: Finding,
    ) -> dict[str, str | int]:
        """Return one finding serialized relative to the project root.

        Args:
            finding: Documentation-contract finding.

        Returns:
            Serialized finding values.

        """
        return finding.relative_dict(root=self._config.root)

    def _discover(self: Self) -> tuple[Path, ...]:
        """Walk the root once, collecting Python and JavaScript sources.

        Returns:
            Sorted source paths.

        """
        if self._config.include_files:
            suffixes: frozenset[str] = frozenset(
                {
                    *(".py" if "python" in self._config.languages else ()),
                    *(
                        (".js", ".mjs", ".cjs")
                        if "javascript" in self._config.languages
                        else ()
                    ),
                },
            )
            return tuple(
                path
                for path in self._config.include_files
                if path.suffix in suffixes
                and not path.name.endswith(".min.js")
            )
        paths: list[Path] = []
        root: Path
        directories: list[str]
        filenames: list[str]
        for root, directories, filenames in self._config.root.walk(
            top_down=True,
        ):
            kept: list[str] = []
            directory: str
            for directory in directories:
                if self._excluded_directory(root=root, directory=directory):
                    continue
                kept.append(directory)
            directories[:] = kept
            filename: str
            for filename in filenames:
                path: Path = root / filename
                if (
                    "python" in self._config.languages and path.suffix == ".py"
                ) or (
                    "javascript" in self._config.languages
                    and path.suffix in {".js", ".mjs", ".cjs"}
                    and not path.name.endswith(".min.js")
                ):
                    paths.append(path)
        return tuple(sorted(paths, key=Path.as_posix))


def parse_args() -> Config:
    """Parse command-line arguments.

    Returns:
        Validated runtime configuration.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description="Exactus Python Google docstrings and JavaScript JSDoc.",
    )
    _ = consume(value=parser.add_argument("root", nargs="?", default="."))
    _ = consume(
        value=parser.add_argument(
            "--markdown",
            default="DOCUMENTATION_EXACTUS.md",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--json",
            dest="json_output",
            default="DOCUMENTATION_EXACTUS.json",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--language",
            choices=("both", "python", "javascript"),
            default="both",
        ),
    )
    _ = consume(value=parser.add_argument("--exclude", action="append"))
    _ = consume(
        value=parser.add_argument("--public-only", action="store_true"),
    )
    _ = consume(
        value=parser.add_argument("--no-js-check", action="store_true"),
    )
    _ = consume(
        value=parser.add_argument(
            "--fail-on",
            choices=("error", "warning", "info", "never"),
            default="never",
        ),
    )
    args: Namespace = parser.parse_args()
    root: Path = Path(cast(typ="str", val=args.root)).resolve()
    include_files: tuple[Path, ...] = ()
    if root.is_file():
        include_files = (root,)
        root = root.parent
    language: str = cast(typ="str", val=args.language)
    languages: frozenset[Language] = (
        frozenset({"python", "javascript"})
        if language == "both"
        else frozenset({cast(typ="Language", val=language)})
    )
    explicit_excludes: list[str] | None = cast(
        typ="list[str] | None",
        val=args.exclude,
    )
    return Config(
        root=root,
        markdown=(root / cast(typ="str", val=args.markdown)).resolve(),
        json_output=(root / cast(typ="str", val=args.json_output)).resolve(),
        languages=languages,
        exclude_dirs=(
            frozenset(explicit_excludes)
            if explicit_excludes is not None
            else Constants.exclude_dirs
        ),
        exclude_hidden_dirs=explicit_excludes is None,
        public_only=cast(typ="bool", val=args.public_only),
        validate_javascript=not cast(typ="bool", val=args.no_js_check),
        fail_on=(
            None
            if (fail_on := cast(typ="str", val=args.fail_on)) == "never"
            else cast(typ="Severity", val=fail_on)
        ),
        include_files=include_files,
    )


def main() -> int:
    """Run the documentation exactus.

    Returns:
        Process exit status.

    """
    return DocumentationExactus(config=parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
