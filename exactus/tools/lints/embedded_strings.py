# Copyright (c) 2026
"""Verify and render embedded source strings without altering runtime values.

The automatic path never executes evaluated source and never rewrites an
interpolation. Embedded-code formatting is deliberately opt-in and may change
the meaning of string contents, especially HTML and CSS whitespace.
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
    Constant,
    Expr,
    FormattedValue,
    FunctionDef,
    JoinedStr,
    Module,
    Name,
    NodeVisitor,
    dump,
    parse,
    unparse,
    walk,
)
from asyncio import create_subprocess_exec, wait_for
from asyncio import run as run_async
from asyncio import subprocess as asyncio_subprocess
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
from shutil import which
from subprocess import CalledProcessError, CompletedProcess
from textwrap import dedent
from tokenize import COMMENT, TokenError, generate_tokens
from typing import TYPE_CHECKING, Final, Literal, Protocol, final

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
type EmbeddedLanguage = Literal["python", "html", "javascript", "css"]


@final
class Constants:
    """Immutable policy defaults and formatter names.

    Attributes:
        minimum_width: Minimum physical source width supported.
        maximum_width: Maximum physical source width supported.
        max_embedded_bytes: Maximum text submitted to external formatters.
        format_timeout: Maximum seconds a formatter may run.
        ascii_control_limit: First printable ASCII code point.
        ascii_delete: ASCII DEL control code point.
        language_names: Context identifiers for recognized embedded languages.

    """

    minimum_width: Final[int] = 20
    maximum_width: Final[int] = 320
    max_embedded_bytes: Final[int] = 1_000_000
    format_timeout: Final[int] = 30
    ascii_control_limit: Final[int] = 32
    ascii_delete: Final[int] = 127
    language_names: Final[tuple[tuple[str, EmbeddedLanguage], ...]] = (
        ("html", "html"),
        ("markup", "html"),
        ("javascript", "javascript"),
        ("js", "javascript"),
        ("node_probe", "javascript"),
        ("js_source", "javascript"),
        ("js_code", "javascript"),
        ("stylesheet", "css"),
        ("css", "css"),
        ("python", "python"),
        ("python_probe", "python"),
        ("python_source", "python"),
        ("py_source", "python"),
    )


class EmbeddedFormatter(Protocol):
    """Typed boundary for bundled or injected language formatters."""

    def __call__(
        self,
        *,
        source: str,
        language: EmbeddedLanguage,
        line_length: int,
    ) -> str:
        """Return formatted source or raise a narrowly scoped exception.

        Args:
            source: Embedded program text.
            language: Embedded language selection.
            line_length: Desired embedded-program width.

        Returns:
            Formatted embedded code.

        """
        ...


@dataclass(frozen=True, slots=True)
class LiteralIssue:
    """Explain an unmodified literal and its source position.

    Attributes:
        line: One-based source line.
        column: Zero-based UTF-8 byte column.
        reason: Stable rejection reason.

    """

    line: int
    column: int
    reason: str


@dataclass(frozen=True, slots=True)
class LiteralRewrite:
    """Result of a source-only embedded string rewrite.

    Attributes:
        source: Resulting Python source text.
        tree: Verified parse of ``source``; callers may reuse it
            instead of reparsing the rewritten text.
        count: Number of accepted literal replacements.
        issues: Reasons for skipped candidates.
        changed_values: Whether intentional content formatting was applied.

    """

    source: str
    tree: Module
    count: int
    issues: tuple[LiteralIssue, ...]
    changed_values: bool


@dataclass(frozen=True, slots=True)
class LiteralOptions:
    """Immutable configuration for a verified rewrite.

    Attributes:
        line_length: Physical Python source-line width.
        format_embedded: Explicitly enable embedded-program formatting.
        allow_value_changes: Explicitly permit formatted string changes.
        language: Override contextual language detection when supplied.
        strict: Raise rather than report an unrenderable candidate.

    """

    line_length: int = 79
    format_embedded: bool = False
    allow_value_changes: bool = False
    language: EmbeddedLanguage | None = None
    strict: bool = False


@dataclass(frozen=True, slots=True)
class _Candidate:
    """Positioned literal and context to transform.

    Attributes:
        node: Original AST literal expression.
        name: Binding name for language detection.

    """

    node: Constant | JoinedStr
    name: str


@final
class _Collector(NodeVisitor):
    """Collect constant strings without descending into interpolation nodes."""

    def __init__(self) -> None:
        """Initialize collected expressions and docstring protections."""
        self.candidates: list[_Candidate] = []
        self.docstrings: set[int] = set()
        self._names: list[str] = [""]

    def visit(self, node: AST) -> None:
        """Dispatch to the collector, bypassing deprecated Constant paths.

        ``NodeVisitor.visit_Constant`` is a real method that forwards to
        the deprecated ``visit_Str`` machinery, so ``__getattr__``
        dispatch never reaches ``_visit_constant``. Intercepting the
        dispatch here keeps constants on the collector's own handler.

        Args:
            node: AST node being visited.

        """
        if type(node) is Constant:
            self._visit_constant(node=node)
            return
        super().visit(node=node)

    def __getattr__(self, name: str) -> Callable[[AST], None]:
        """Resolve AST visitor methods dynamically.

        Args:
            name: Attribute requested by the AST visitor.

        Returns:
            Corresponding node handler or generic visitor.

        Raises:
            AttributeError: If the requested attribute is not a visitor.

        """
        if not name.startswith("visit_"):
            msg: str = f"{type(self).__name__!s} has no attribute {name!r}"
            raise AttributeError(msg)
        handlers: dict[str, Callable[[AST], None]] = {
            "Module": self._visit_suite,
            "ClassDef": self._visit_suite,
            "FunctionDef": self._visit_suite,
            "AsyncFunctionDef": self._visit_suite,
            "Call": self._visit_call,
            "Assign": self._visit_assign,
            "AnnAssign": self._visit_ann_assign,
            "JoinedStr": self._visit_joined_str,
            "FormattedValue": self._visit_formatted_value,
            "Constant": self._visit_constant,
        }
        return handlers.get(name.removeprefix("visit_"), self.generic_visit)

    def _visit_suite(self, node: AST) -> None:
        """Visit a statement suite while protecting its docstring.

        Args:
            node: Module, class, or function definition.

        """
        if isinstance(node, (Module, ClassDef, FunctionDef, AsyncFunctionDef)):
            self._protect_docstring(node=node)
        self.generic_visit(node=node)

    def _visit_call(self, node: AST) -> None:
        """Infer embedded language from Path(...).write_text calls.

        Args:
            node: Call expression to inspect.

        """
        if not isinstance(node, Call):
            self.generic_visit(node=node)
            return
        if (
            isinstance(node.func, Attribute)
            and node.func.attr == "write_text"
            and isinstance(node.func.value, Call)
            and isinstance(node.func.value.func, Name)
            and node.func.value.func.id == "Path"
            and node.func.value.args
            and isinstance(node.func.value.args[0], Constant)
            and isinstance(node.func.value.args[0].value, str)
        ):
            extension: str = (
                node.func.value.args[0].value.rpartition(".")[-1].lower()
            )
            formats: dict[str, EmbeddedLanguage] = {
                "html": "html",
                "htm": "html",
                "js": "javascript",
                "mjs": "javascript",
                "cjs": "javascript",
                "css": "css",
                "py": "python",
            }
            language: EmbeddedLanguage | None = formats.get(extension)
            if language is not None:
                self.visit(node=node.func)
                for index, argument in enumerate(iterable=node.args):
                    self._names.append(
                        language if index == 0 else self._names[-1],
                    )
                    self.visit(node=argument)
                    _ = self._names.pop()
                for keyword in node.keywords:
                    self._names.append(
                        language if keyword.arg == "data" else self._names[-1],
                    )
                    self.visit(node=keyword.value)
                    _ = self._names.pop()
                return
        self.generic_visit(node=node)

    def _visit_assign(self, node: AST) -> None:
        """Associate a literal with its assignment name.

        Args:
            node: Assignment expression.

        """
        if not isinstance(node, Assign):
            self.generic_visit(node=node)
            return
        binding: str = (
            node.targets[0].id
            if len(node.targets) == 1 and isinstance(node.targets[0], Name)
            else ""
        )
        self._names.append(binding)
        self.visit(node=node.value)
        _ = self._names.pop()

    def _visit_ann_assign(self, node: AST) -> None:
        """Associate an annotated string with its assignment name.

        Args:
            node: Annotated assignment.

        """
        if not isinstance(node, AnnAssign):
            self.generic_visit(node=node)
            return
        if node.value is not None:
            self._names.append(
                node.target.id if isinstance(node.target, Name) else "",
            )
            self.visit(node=node.value)
            _ = self._names.pop()

    def _visit_joined_str(self, node: AST) -> None:
        """Collect an entire f-string without visiting interpolations.

        Args:
            node: Interpolated string.

        """
        if isinstance(node, JoinedStr) and id(node) not in self.docstrings:
            self.candidates.append(_Candidate(node=node, name=self._names[-1]))

    def _visit_formatted_value(self, _node: AST) -> None:
        """Exclude expressions embedded inside f-strings.

        Args:
            _node: Formatted expression.

        """

    def _visit_constant(self, node: AST) -> None:
        """Record eligible string constants.

        Args:
            node: Constant expression.

        """
        if (
            isinstance(node, Constant)
            and isinstance(node.value, str)
            and id(node) not in self.docstrings
        ):
            self.candidates.append(_Candidate(node=node, name=self._names[-1]))

    def _protect_docstring(
        self,
        node: Module | ClassDef | FunctionDef | AsyncFunctionDef,
    ) -> None:
        """Protect the first literal statement in a Python suite.

        Args:
            node: Module, class, or function containing a statement suite.

        """
        if node.body and isinstance(node.body[0], Expr):
            value: AST = node.body[0].value
            if isinstance(value, Constant) and isinstance(value.value, str):
                self.docstrings.add(id(value))


def _source_position(
    *,
    lines: list[str],
    starts: list[int],
    line: int,
    column: int,
) -> int:
    """Map byte-column AST positions to source-string offsets.

    Args:
        lines: Original source split with line endings.
        starts: Character offsets for each line.
        line: One-based source line.
        column: Zero-based UTF-8 byte column.

    Returns:
        Character offset into the original source.

    """
    return starts[line - 1] + len(
        lines[line - 1]
        .encode(encoding="utf-8")[:column]
        .decode(encoding="utf-8"),
    )


def _language(*, name: str) -> EmbeddedLanguage | None:
    """Infer embedded language only from deliberate identifier patterns.

    Args:
        name: Name of the variable containing the literal.

    Returns:
        Language when context is reasonably unambiguous.

    """
    identifier: str = name.lower()
    for marker, language in Constants.language_names:
        if (
            identifier == marker
            or identifier.startswith(f"{marker}_")
            or identifier.endswith(f"_{marker}")
        ):
            return language
    return None


def _tokens(
    *,
    value: str,
    delimiter: str,
    formatted: bool = False,
) -> list[list[str]]:
    """Encode literal characters into indivisible escape-safe tokens.

    Args:
        value: Exact string data, including any true line feeds.
        delimiter: Selected triple-quote string delimiter.
        formatted: Escape literal braces in f-string content.

    Returns:
        Token sequences for each logical line of the string.

    """
    result: list[list[str]] = [[]]
    index: int = 0
    while index < len(value):
        char: str = value[index]
        if (
            char
            == """\

"""
        ):
            result.append([])
        elif value.startswith(delimiter, index):
            result[-1].extend(
                (f"\\{delimiter[0]}", delimiter[1], delimiter[2]),
            )
            index += 2
        elif formatted and char in "{}":
            result[-1].append(char * 2)
        elif char == "\\":
            result[-1].append("\\\\")
        elif char in ("\r", "\t", "\0"):
            result[-1].append({"\r": "\\r", "\t": "\\t", "\0": "\\x00"}[char])
        elif (
            ord(char) < Constants.ascii_control_limit
            or ord(char) == Constants.ascii_delete
        ):
            result[-1].append(f"\\x{ord(char):02x}")
        elif char in ("\u2028", "\u2029"):
            result[-1].append(f"\\u{ord(char):04x}")
        else:
            result[-1].append(char)
        index += 1
    return result


def _break_point(*, tokens: list[str], width: int) -> int:
    """Find a safe token boundary favoring nearby semantic separators.

    Args:
        tokens: Remaining encoded source tokens.
        width: Maximum characters before the continuation backslash.

    Returns:
        Number of complete tokens to emit, or zero when none fit.

    """
    length: int = 0
    boundary: int = 0
    preferred: int = 0
    for index, token in enumerate(iterable=tokens):
        if length + len(token) > width:
            break
        length += len(token)
        boundary = index + 1
        if token in (" ", ",", ";", ")", "]", "}"):
            preferred = boundary
    return preferred if preferred >= boundary // 2 else boundary


def _joined_tokens(
    *,
    node: Constant | JoinedStr,
    delimiter: str,
) -> list[list[str]] | None:
    """Collect safe literal tokens and intact f-string fields.

    Args:
        node: Original literal or interpolated string expression.
        delimiter: Triple quotes to escape within literal content.

    Returns:
        Tokenized logical lines, or ``None`` for unsupported syntax.

    """
    if isinstance(node, Constant):
        return (
            _tokens(value=node.value, delimiter=delimiter)
            if isinstance(node.value, str)
            else None
        )
    lines: list[list[str]] = [[]]
    for part in node.values:
        if isinstance(part, Constant) and isinstance(part.value, str):
            pieces: list[list[str]] = _tokens(
                value=part.value,
                delimiter=delimiter,
                formatted=True,
            )
            lines[-1].extend(pieces[0])
            lines.extend(pieces[1:])
        elif isinstance(part, FormattedValue):
            fragment: str = unparse(ast_obj=JoinedStr(values=[part]))
            quote_length: int = 3 if fragment[1:4] in ('"""', "'''") else 1
            if (
                not fragment.startswith(("f'", 'f"'))
                or fragment[-quote_length:] != fragment[1 : 1 + quote_length]
                or """\

"""
                in fragment
            ):
                return None
            lines[-1].append(fragment[1 + quote_length : -quote_length])
        else:
            return None
    return lines


def _render_delimiter(
    *,
    node: Constant | JoinedStr,
    delimiter: str,
    line_length: int,
    closing_suffix: str,
) -> str | None:
    """Render one delimiter choice using token-boundary continuation.

    Args:
        node: Original literal or interpolated string expression.
        delimiter: Triple quote selection.
        line_length: Maximum physical source width.
        closing_suffix: Existing trailing Python code.

    Returns:
        Candidate source text, or ``None`` if a token cannot fit.

    """
    lines: list[list[str]] | None = _joined_tokens(
        node=node,
        delimiter=delimiter,
    )
    if lines is None:
        return None
    prefix: str = "f" if isinstance(node, JoinedStr) else ""
    fragments: list[str] = [
        f"""\
{prefix}{delimiter}\\
""",
    ]
    for index, tokens in enumerate(iterable=lines):
        remaining: list[str] = tokens.copy()
        closing: bool = index == len(lines) - 1
        required: int = len(delimiter) + (
            len(closing_suffix) if closing else 0
        )
        while remaining:
            if (
                sum(len(token) for token in remaining) + required
                <= line_length
            ):
                fragments.append("".join(remaining))
                remaining.clear()
                break
            boundary: int = _break_point(
                tokens=remaining,
                width=line_length - 1,
            )
            if not boundary:
                return None
            fragments.append(
                "".join(remaining[:boundary])
                + """\
\\
""",
            )
            remaining = remaining[boundary:]
        if not closing:
            fragments.append("""\

""")
    return "".join((*fragments, delimiter))


def _render(
    *,
    node: Constant | JoinedStr,
    line_length: int,
    opening_column: int,
    closing_suffix: str,
) -> str | None:
    """Construct a width-bounded triple literal with identical AST.

    Args:
        node: Original constant string or f-string.
        line_length: Maximum physical source width.
        opening_column: Source position of opening quote.
        closing_suffix: Source characters after the closing literal.

    Returns:
        Safe literal source, or ``None`` when no representation fits.

    """
    if (
        opening_column + (5 if isinstance(node, JoinedStr) else 4)
        > line_length
    ):
        return None
    for delimiter in ('"""', "'''"):
        candidate: str | None = _render_delimiter(
            node=node,
            delimiter=delimiter,
            line_length=line_length,
            closing_suffix=closing_suffix,
        )
        if candidate is None:
            continue
        try:
            parsed: AST = parse(source=candidate, mode="eval").body
        except SyntaxError:
            continue
        if (
            dump(node=parsed, include_attributes=False)
            == dump(node=node, include_attributes=False)
            and all(
                len(line) <= line_length for line in candidate.splitlines()
            )
            and len(candidate.splitlines()[-1]) + len(closing_suffix)
            <= line_length
        ):
            return candidate
    return None


async def _run_checked_async(
    *,
    command: tuple[str, ...],
    input_text: str | None,
    deadline_seconds: float,
) -> CompletedProcess[str]:
    """Execute a process without a shell and return bounded diagnostics.

    Args:
        command: Executable path and literal process arguments.
        input_text: Optional UTF-8 bytes for the child standard input.
        deadline_seconds: Maximum execution time in seconds.

    Returns:
        Completed process with decoded output and return status.

    Raises:
        RuntimeError: If the child fails to finish within the deadline.

    """
    process: asyncio_subprocess.Process = await create_subprocess_exec(
        *command,
        stdin=(
            asyncio_subprocess.PIPE
            if input_text is not None
            else asyncio_subprocess.DEVNULL
        ),
        stdout=asyncio_subprocess.PIPE,
        stderr=asyncio_subprocess.PIPE,
    )
    try:
        stdout: bytes
        stderr: bytes
        stdout, stderr = await wait_for(
            fut=process.communicate(
                input=None
                if input_text is None
                else input_text.encode(encoding="utf-8"),
            ),
            timeout=deadline_seconds,
        )
    except TimeoutError as error:
        process.kill()
        _ = await process.wait()
        msg: str = "Formatter process exceeded its execution deadline"
        raise RuntimeError(msg) from error
    return CompletedProcess[str](
        args=command,
        returncode=process.returncode
        if process.returncode is not None
        else -1,
        stdout=stdout.decode(encoding="utf-8", errors="replace"),
        stderr=stderr.decode(encoding="utf-8", errors="replace"),
    )


def run_checked_command(
    *,
    args: Sequence[str],
    input_text: str | None = None,
    timeout: float = Constants.format_timeout,
    check: bool = False,
) -> CompletedProcess[str]:
    """Run a trusted executable cross-platform with no command shell.

    The worker thread supports synchronous Exactus calls from inside an
    already running event loop. Timeouts terminate and reap the child process.

    Args:
        args: Executable path and literal command arguments.
        input_text: Optional UTF-8 process stdin.
        timeout: Absolute per-child execution deadline in seconds.
        check: Raise on any nonzero child return status.

    Returns:
        Status, stdout, and stderr for the completed child.

    Raises:
        ValueError: If the command or timeout is invalid.
        CalledProcessError: If check is true and the child fails.
        RuntimeError: If the process exceeds its deadline.
        OSError: If the process cannot be started.

    """
    if not args or timeout <= 0:
        msg: str = "A command and positive timeout are required"
        raise ValueError(msg)
    with ThreadPoolExecutor(max_workers=1) as workers:
        completed: CompletedProcess[str] = workers.submit(
            run_async,
            _run_checked_async(
                command=tuple(args),
                input_text=input_text,
                deadline_seconds=timeout,
            ),
        ).result()
    if check and completed.returncode != 0:
        raise CalledProcessError(
            returncode=completed.returncode,
            cmd=tuple(args),
            output=completed.stdout,
            stderr=completed.stderr,
        )
    return completed


def format_embedded_source(
    *,
    source: str,
    language: EmbeddedLanguage,
    line_length: int,
    executable: str | None = None,
) -> str:
    """Format explicitly permitted embedded code via Ruff or Prettier.

    Executes without a shell, including calls from a running event loop.
    Formatting embedded content intentionally permits changing its value.

    Args:
        source: Embedded text, including its original indentation.
        language: Parser language for the selected formatter.
        line_length: Formatting width for the embedded language.
        executable: Explicit Ruff binary for Python source; other
            languages and omitted values resolve on PATH.

    Returns:
        Formatted source text.

    Raises:
        ValueError: If embedded content exceeds the safe input ceiling.
        RuntimeError: If the formatter is missing, times out, or fails.

    """
    if len(source.encode(encoding="utf-8")) > Constants.max_embedded_bytes:
        msg: str = "Embedded source exceeds the formatter input limit"
        raise ValueError(msg)
    resolved: str | None = (
        executable
        if language == "python" and executable is not None
        else which(cmd="ruff" if language == "python" else "prettier")
    )
    if resolved is None:
        msg = f"Missing formatter for embedded {language} source"
        raise RuntimeError(msg)
    command: list[str] = (
        [
            resolved,
            "format",
            "--line-length",
            str(object=line_length),
            "--stdin-filename",
            "embedded.py",
            "-",
        ]
        if language == "python"
        else [
            resolved,
            "--parser",
            {"html": "html", "javascript": "babel", "css": "css"}[language],
            "--print-width",
            str(object=line_length),
        ]
    )
    try:
        return run_checked_command(
            args=command,
            input_text=dedent(text=source),
            check=True,
        ).stdout
    except (OSError, CalledProcessError) as error:
        msg = f"Embedded {language} formatter launch failed: {error}"
        raise RuntimeError(msg) from error


@dataclass(frozen=True, slots=True)
class _Scan:
    """Stable, immutable context for one complete source scan.

    Attributes:
        source: Original Python source text.
        lines: Original physical source lines.
        starts: Character offsets for all line starts.
        comments: Source-line numbers containing comments.
        options: Validated rewrite configuration.
        formatter: Formatter integration or dependency-injected callback.

    """

    source: str
    lines: list[str]
    starts: list[int]
    comments: set[int]
    options: LiteralOptions
    formatter: EmbeddedFormatter


def _scan(
    *,
    source: str,
    options: LiteralOptions,
    formatter: EmbeddedFormatter,
) -> _Scan:
    """Build deterministic byte-offset and comment protection indices.

    Args:
        source: Python file text.
        options: Validated options.
        formatter: Selected embedded formatter.

    Returns:
        Immutable scan context.

    """
    lines: list[str] = source.splitlines(keepends=True)
    starts: list[int] = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    try:
        comments: set[int] = {
            token.start[0]
            for token in generate_tokens(
                readline=StringIO(initial_value=source).readline,
            )
            if token.type == COMMENT
        }
    except (TokenError, IndentationError):
        comments = set(range(1, len(lines) + 1))
    return _Scan(
        source=source,
        lines=lines,
        starts=starts,
        comments=comments,
        options=options,
        formatter=formatter,
    )


def _candidate_rewrite(
    *,
    candidate: _Candidate,
    scan: _Scan,
) -> tuple[int, int, str, bool] | LiteralIssue | None:
    """Propose a verified, nonoverlapping literal replacement.

    Args:
        candidate: String node and language context.
        scan: Original source scan and policy.

    Returns:
        Replacement, skipped reason, or ``None`` when already suitable.

    """
    node: Constant | JoinedStr = candidate.node
    value: str | None = (
        node.value
        if isinstance(node, Constant) and isinstance(node.value, str)
        else None
    )
    has_newline: bool = (
        any(
            isinstance(part, Constant)
            and isinstance(part.value, str)
            and """\

"""
            in part.value
            for part in node.values
        )
        if isinstance(node, JoinedStr)
        else value is not None
        and """\

"""
        in value
    )
    start: int = _source_position(
        lines=scan.lines,
        starts=scan.starts,
        line=node.lineno,
        column=node.col_offset,
    )
    end_line: int = node.end_lineno or node.lineno
    end: int = _source_position(
        lines=scan.lines,
        starts=scan.starts,
        line=end_line,
        column=node.end_col_offset or node.col_offset,
    )
    existing: str = scan.source[start:end]
    language: EmbeddedLanguage | None = scan.options.language or _language(
        name=candidate.name,
    )
    format_requested: bool = (
        scan.options.format_embedded and language is not None
    )
    if format_requested and value is None:
        return LiteralIssue(
            line=node.lineno,
            column=node.col_offset,
            reason="embedded-formatter-does-not-support-fstrings",
        )
    if not format_requested and (
        not has_newline
        or (
            existing.lstrip()
            .lower()
            .startswith(('"""', "'''", 'f"""', "f'''"))
            and all(
                len(line) <= scan.options.line_length
                for line in existing.splitlines()
            )
        )
    ):
        return None
    if any(line in scan.comments for line in range(node.lineno, end_line + 1)):
        return LiteralIssue(
            line=node.lineno,
            column=node.col_offset,
            reason="comment-protected",
        )
    replacement_value: str | None = value
    if format_requested and language is not None and value is not None:
        try:
            replacement_value = scan.formatter(
                source=value,
                language=language,
                line_length=scan.options.line_length,
            )
        except (RuntimeError, ValueError) as error:
            return LiteralIssue(
                line=node.lineno,
                column=node.col_offset,
                reason=f"embedded-formatter-failed: {error}",
            )
    suffix: str = scan.lines[end_line - 1][
        end - scan.starts[end_line - 1] :
    ].rstrip(
        """\
\r
""",
    )
    render_node: Constant | JoinedStr = (
        Constant(value=replacement_value)
        if replacement_value is not None and replacement_value != value
        else node
    )
    rendered: str | None = _render(
        node=render_node,
        line_length=scan.options.line_length,
        opening_column=start - scan.starts[node.lineno - 1],
        closing_suffix=suffix,
    )
    if rendered is None:
        return LiteralIssue(
            line=node.lineno,
            column=node.col_offset,
            reason="unrenderable-width-or-delimiter",
        )
    return (
        (start, end, rendered, replacement_value != value)
        if rendered != existing
        else None
    )


def rewrite_multiline_literals(
    *,
    source: str,
    options: LiteralOptions | None = None,
    formatter: EmbeddedFormatter | None = None,
    tree: Module | None = None,
) -> LiteralRewrite:
    """Convert multiline literals and verify AST identity before returning.

    Automatic mode preserves complete Python AST structure and values.
    Formatting embedded language text requires explicit permission to change
    string values; comments, interpolations, and docstrings remain protected.

    Args:
        source: Complete Python source code.
        options: Immutable safety and language-formatting policy.
        formatter: Optional injected Ruff/Prettier-compatible formatter.
        tree: Pre-parsed module matching ``source``; parsed when omitted.

    Returns:
        Rewritten source with edit count and skipped-candidate reasons.

    Raises:
        SyntaxError: If input is not valid Python.
        ValueError: If options conflict or structural verification fails.
        RuntimeError: If strict mode encounters an unrenderable candidate.

    """
    active: LiteralOptions = options or LiteralOptions()
    if (
        not Constants.minimum_width
        <= active.line_length
        <= Constants.maximum_width
    ):
        msg: str = "line_length must be between 20 and 320"
        raise ValueError(msg)
    if active.format_embedded and not active.allow_value_changes:
        msg = "format_embedded requires allow_value_changes=True"
        raise ValueError(msg)
    original: Module = tree if tree is not None else parse(source=source)
    collector: _Collector = _Collector()
    collector.visit(node=original)
    scan: _Scan = _scan(
        source=source,
        options=active,
        formatter=formatter or format_embedded_source,
    )
    edits: list[tuple[int, int, str, bool]] = []
    issues: list[LiteralIssue] = []
    for candidate in collector.candidates:
        proposal: tuple[int, int, str, bool] | LiteralIssue | None = (
            _candidate_rewrite(candidate=candidate, scan=scan)
        )
        if isinstance(proposal, LiteralIssue):
            issues.append(proposal)
        elif proposal is not None:
            edits.append(proposal)
    if active.strict and issues:
        msg = f"Unrenderable embedded literals: {len(issues)}"
        raise RuntimeError(msg)
    transformed_source: str = source
    newline: str = (
        """\
\r
"""
        if """\
\r
"""
        in source
        and source.count("""\
\r
""")
        == source.count("""\

""")
        else """\

"""
    )
    for start, end, replacement, _ in sorted(edits, reverse=True):
        transformed_source = (
            transformed_source[:start]
            + replacement.replace(
                """\

""",
                newline,
            )
            + transformed_source[end:]
        )
    transformed: Module = original
    if edits:
        transformed = parse(source=transformed_source)
        if (
            _structure(node=original) != _structure(node=transformed)
            if active.allow_value_changes
            else dump(node=original, include_attributes=False)
            != dump(node=transformed, include_attributes=False)
        ):
            msg = (
                "Embedded formatting changed nonliteral Python syntax"
                if active.allow_value_changes
                else "Lossless rewrite unexpectedly changed the Python AST"
            )
            raise ValueError(msg)
    return LiteralRewrite(
        source=transformed_source,
        tree=transformed,
        count=len(edits),
        issues=tuple(issues),
        changed_values=any(changed for _, _, _, changed in edits),
    )


def _structure(*, node: AST) -> str:
    """Compare Python structure while permitting only string-value changes.

    Args:
        node: Original or candidate parsed Python tree.

    Returns:
        AST dump with string constants normalized.

    """
    copied: AST = deepcopy(x=node)
    for item in walk(node=copied):
        if isinstance(item, Constant) and isinstance(item.value, str):
            item.value = ""
    return dump(node=copied, include_attributes=False)
