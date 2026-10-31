"""Run project linters in parallel and merge diagnostics into one report.

Discovered Python files are first stabilized with Ruff format and fix
cycles. Each tool's selected files are grouped into worker-sized batches
(one process per chunk) unless its :class:`ToolSpec` opts into per-file
or whole-project execution; derived tools such as ``ruff_docs`` reuse
another tool's diagnostics filtered by rule-code prefix and launch no
process at all. Tool-specific output (JSON envelopes or plain-text
diagnostics) is normalized into :class:`Diagnostic` records, and the
per-file results are aggregated into a single report document written
to disk.
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import (
    contextmanager,
    redirect_stderr,
    redirect_stdout,
    suppress,
)
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from fnmatch import fnmatch
from functools import partial
from json import JSONDecodeError, dumps, loads
from os import cpu_count, environ, getpid, walk
from pathlib import Path
from re import Match
from re import compile as compile_regex
from shutil import get_terminal_size, rmtree, which
from signal import Handlers, Signals, signal
from subprocess import PIPE, Popen
from textwrap import dedent
from threading import Event, Lock, Thread
from time import monotonic
from tomllib import load as load_toml
from typing import (
    TYPE_CHECKING,
    ClassVar,
    NoReturn,
    Protocol,
    Self,
    TextIO,
    cast,
    final,
)
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.steps import step_log, trace
from exactus.packages.tree import render_tree

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable, Mapping
    from re import Pattern
    from types import FrameType, TracebackType
type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
type JsonObject = dict[str, JsonValue]
type SignalHandler = (
    Callable[[int, FrameType | None], None] | Handlers | int | None
)
type StreamMember = (
    str | int | bool | None | Callable[..., str | int | bool | None]
)


def _join(*, parts: tuple[str, ...], separator: str = "") -> str:
    """Join stable fragments without formatter-driven line growth.

    Args:
        parts: Text fragments to join.
        separator: Text placed between fragments.

    Returns:
        Joined text.

    """
    return separator.join(parts)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        output: Grouped module constant.
        report_directory: Grouped module constant.
        artifacts_directory: Grouped module constant.
        files_directory: Grouped module constant.
        files_archive: Grouped module constant.
        files_tree: Grouped module constant.
        activity_name: Grouped module constant.
        activity_schema: Grouped module constant.
        activity_interval_seconds: Grouped module constant.
        activity_event_limit: Grouped module constant.
        log_escape_pattern: Grouped module constant.
        report_readme: Grouped module constant.
        artifacts_readme: Grouped module constant.
        files_readme: Grouped module constant.
        project_root: Grouped module constant.
        pyproject: Grouped module constant.
        excludes: Grouped module constant.
        python_suffixes: Grouped module constant.
        javascript_suffixes: Grouped module constant.
        typescript_suffixes: Grouped module constant.
        typescript_config_names: Grouped module constant.
        style_suffixes: Grouped module constant.
        html_suffixes: Grouped module constant.
        eslint_severity_error: Grouped module constant.
        ruff_conflict_ignores: Grouped module constant.
        batch_pace_seconds: Grouped module constant.
        batch_pace_floor_seconds: Grouped module constant.
        tsc_pattern: Grouped module constant.
        html_pattern: Grouped module constant.
        ansi_pattern: Grouped module constant.
        ansi_reset: Grouped module constant.
        ansi_bold: Grouped module constant.
        ansi_dim: Grouped module constant.
        ansi_red: Grouped module constant.
        ansi_green: Grouped module constant.
        ansi_yellow: Grouped module constant.
        ansi_cyan: Grouped module constant.

    """

    output: ClassVar[str] = "ALL_LINTS_RESULTS/result.json"
    report_directory: ClassVar[str] = "ALL_LINTS_RESULTS"
    artifacts_directory: ClassVar[str] = "ARTIFACTS"
    files_directory: ClassVar[str] = "FILES"
    files_archive: ClassVar[str] = "files.zip"
    files_tree: ClassVar[str] = "TREE.txt"
    activity_name: ClassVar[str] = "@activity.json"
    activity_schema: ClassVar[str] = "exactus/activity/v1"
    activity_interval_seconds: ClassVar[float] = 1.0
    activity_event_limit: ClassVar[int] = 50
    log_escape_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern="\\x1b\\[[0-9;?]*[A-Za-z]",
    )
    report_readme: ClassVar[str] = dedent(
        text=(
            "    # `ALL_LINTS_RESULTS/`\n    \n    Standalone `exactus/package"
            "s/all_lints` run report.\n    \n    ## Contents\n    \n    - [`re"
            "sult.json`](result.json) — merged linter diagnostics report.\n   "
            " - [`ARTIFACTS/`](ARTIFACTS/README.md) — execution evidence: step"
            " trace, activity heartbeat and captured output.\n    - [`FILES/`]"
            "(FILES/README.md) — archive of every file with issues plus its `e"
            "xactus/packages/tree` listing, present when `--collect-files` was"
            " used.\n    "
        ),
    )
    artifacts_readme: ClassVar[str] = dedent(
        text=(
            "    # `ARTIFACTS/`\n    \n    Execution evidence of the standalon"
            "e `exactus/packages/all_lints` run.\n    \n    ## Contents\n    "
            "\n    - [`@activity.json`](%40activity.json) — `exactus/activity/"
            "v1` liveness document with heartbeat, progress and recent events."
            "\n    - [`steps.txt`](steps.txt) — timestamped step trace.\n    -"
            " [`stdout.log`](stdout.log) — captured standard output, ANSI esca"
            "pes stripped.\n    - [`stderr.log`](stderr.log) — captured standa"
            "rd error.\n    "
        ),
    )
    files_readme: ClassVar[str] = dedent(
        text=(
            "    # `FILES/`\n    \n    Every file that produced diagnostics in"
            " `../result.json`, packaged in report order.\n    \n    ## Conten"
            "ts\n    \n    - [`files.zip`](files.zip) — project-relative archi"
            "ve; running `unzip -o ALL_LINTS_RESULTS/FILES/files.zip -d .` fro"
            "m the project root restores the flagged files in place.\n    - [`"
            "TREE.txt`](TREE.txt) — `exactus/packages/tree` listing of the arc"
            "hive members.\n    "
        ),
    )
    project_root: ClassVar[Path] = Path(__file__).resolve().parents[3]
    pyproject: ClassVar[str] = "pyproject.toml"
    excludes: ClassVar[tuple[str, ...]] = (
        "**/node_modules",
        "**/__pycache__",
        "**/.*",
        "mutants",
        "**/mutants",
        "dist",
        "build",
        ".build-cache",
        "exactus/bundle",
    )
    python_suffixes: ClassVar[frozenset[str]] = frozenset({".py", ".pyi"})
    javascript_suffixes: ClassVar[frozenset[str]] = frozenset(
        {".js", ".jsx", ".mjs", ".cjs"},
    )
    typescript_suffixes: ClassVar[frozenset[str]] = frozenset(
        {".ts", ".tsx", ".mts", ".cts"},
    )
    typescript_config_names: ClassVar[tuple[str, ...]] = (
        "jsconfig.json",
        "tsconfig.json",
    )
    style_suffixes: ClassVar[frozenset[str]] = frozenset(
        {".css", ".scss", ".sass", ".less"},
    )
    html_suffixes: ClassVar[frozenset[str]] = frozenset({".html", ".htm"})
    eslint_severity_error: ClassVar[int] = 2
    ruff_conflict_ignores: ClassVar[str] = "D203,D213"
    batch_pace_seconds: ClassVar[float] = 0.15
    batch_pace_floor_seconds: ClassVar[float] = 0.005
    tsc_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=_join(
            parts=(
                "^(?P<file>.+?)\\((?P<line>\\d+),(?P<column>\\d+)\\): ",
                "(?P<severity>error|warning) TS(?P<code>\\d+): ",
                "(?P<message>.*)$",
            ),
        ),
    )
    html_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=_join(
            parts=(
                "^(?P<file>.+?): line (?P<line>\\d+), col ",
                "(?P<column>\\d+), (?P<message>.*?)(?: ",
                "\\((?P<code>[^)]+)\\))?$",
            ),
        ),
    )
    ansi_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern="\\x1b\\[[0-9;]*m",
    )
    ansi_reset: ClassVar[str] = "\x1b[0m"
    ansi_bold: ClassVar[str] = "\x1b[1m"
    ansi_dim: ClassVar[str] = "\x1b[2m"
    ansi_red: ClassVar[str] = "\x1b[31m"
    ansi_green: ClassVar[str] = "\x1b[32m"
    ansi_yellow: ClassVar[str] = "\x1b[33m"
    ansi_cyan: ClassVar[str] = "\x1b[36m"


def _print(*args: str, file: TextIO | None = None, flush: bool = True) -> None:
    """Print and immediately flush a script message.

    Args:
        *args: Values to print.
        file: Stream receiving the message; defaults to the current
            ``stdout``.
        flush: Whether to flush the stream after printing.

    """
    target: TextIO = sys.stdout if file is None else file
    _ = target.write(" ".join(str(object=arg) for arg in args) + "\n")
    if flush:
        _ = target.flush()


def _paint(*, text: str, color: str, enabled: bool = True) -> str:
    """Wrap text in an ANSI color when coloring is enabled.

    Args:
        text: Text to colorize.
        color: ANSI SGR sequence applied before ``text``.
        enabled: When ``False`` return ``text`` unchanged.

    Returns:
        Colorized text, or ``text`` unchanged when ``enabled`` is
        ``False``.

    """
    return f"{color}{text}{Constants.ansi_reset}" if enabled else text


@dataclass(frozen=True, slots=True)
class PreviousReport:
    """Counts recovered from the earlier aggregate report.

    Attributes:
        durations: Per-tool wall-clock durations used for pacing.
        tool_issues: Per-tool diagnostic counts.
        tool_files: Per-tool affected-file counts.
        total_issues: Diagnostics recorded across every tool.
        total_files: Unique files with issues across every tool.
        generated_at: Timestamp of the previous report.

    """

    durations: dict[str, float]
    tool_issues: dict[str, int]
    tool_files: dict[str, int]
    total_issues: int
    total_files: int
    generated_at: str


def _reported_files(*, entry: JsonValue) -> set[str]:
    """Collect file names reported by one previous tool entry.

    Args:
        entry: One tool mapping from a previous report.

    Returns:
        File names listed in the entry's ``files`` array.

    """
    names: set[str] = set()
    if not isinstance(entry, dict):
        return names
    raw_files: JsonValue = entry.get("files")
    if isinstance(raw_files, list):
        for item in raw_files:
            if isinstance(item, dict):
                file_name: JsonValue = item.get("file")
                if isinstance(file_name, str):
                    names.add(file_name)
    return names


def load_previous(*, output: Path) -> PreviousReport | None:
    """Read counts and durations from a previous aggregate report.

    Args:
        output: Report file written by an earlier run.

    Returns:
        Recovered counts, or ``None`` when the report is absent or
        malformed.

    """
    try:
        report: JsonValue = loads(s=output.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(report, dict):
        return None
    tools: JsonValue = report.get("tools")
    if not isinstance(tools, dict):
        return None
    durations: dict[str, float] = {}
    issues: dict[str, int] = {}
    files: dict[str, int] = {}
    unique: set[str] = set()
    for name, entry in tools.items():
        if not isinstance(entry, dict):
            continue
        duration: JsonValue = entry.get("duration_seconds")
        if isinstance(duration, int | float) and (
            not isinstance(duration, bool)
        ):
            durations[name] = float(duration)
        diagnostics: JsonValue = entry.get("diagnostics")
        issues[name] = len(diagnostics) if isinstance(diagnostics, list) else 0
        names: set[str] = _reported_files(entry=entry)
        files[name] = len(names)
        unique |= names
    generated: JsonValue = report.get("generated_at")
    return PreviousReport(
        durations=durations,
        tool_issues=issues,
        tool_files=files,
        total_issues=sum(issues.values()),
        total_files=len(unique),
        generated_at=generated if isinstance(generated, str) else "",
    )


def previous_durations(*, output: Path) -> dict[str, float]:
    """Return reusable tool durations from the previous aggregate report.

    Args:
        output: Aggregate report path.

    Returns:
        Stored durations, or an empty mapping when no valid report exists.

    """
    previous: PreviousReport | None = load_previous(output=output)
    return {} if previous is None else dict(previous.durations)


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Represent one normalized diagnostic.

    Attributes:
        tool: Name of the tool that produced the diagnostic.
        file: Project-relative file path, when the tool reported one.
        line: One-based line number, when known.
        column: One-based column number, when known.
        end_line: One-based end line number, when known.
        end_column: One-based end column number, when known.
        severity: Normalized severity: ``error``, ``warning``, ``info``
            or ``note``.
        code: Tool-specific rule or diagnostic code, when known.
        message: Human-readable diagnostic message.

    """

    tool: str
    file: str | None
    line: int | None
    column: int | None
    end_line: int | None
    end_column: int | None
    severity: str
    code: str | None
    message: str


@dataclass(frozen=True, slots=True)
class FileResult:
    """Represent one single-file linter or stabilizer result.

    Attributes:
        file: Path of the processed file, project-relative for linter
            results and absolute for stabilization results.
        command: Complete argument vector the linter process was
            launched with, empty for stabilization results.
        status: Outcome label: ``passed``, ``failed`` or ``error``.
        exit_code: Process exit code, or ``None`` when no single
            linter process describes the result.
        duration_seconds: Wall-clock runtime of the file processing.
        diagnostics: Normalized diagnostics parsed from the output.
        stdout: Captured standard output, emptied for machine-readable
            parsers whose payload is already reflected in diagnostics.
        stderr: Captured standard error, with known advisory noise
            stripped for ruff.
        format_calls: Ruff format invocations during stabilization.
        fix_calls: Ruff check invocations during stabilization.
        start_size: File size in bytes before stabilization.
        end_size: File size in bytes after stabilization.
        size_delta: File size change caused by stabilization.
        start_datetime: UTC datetime when stabilization started.
        end_datetime: UTC datetime when stabilization finished.
        total: Total number of files in the stabilization batch.
        current: One-based completion index inside the batch.
        started_monotonic: Monotonic timestamp captured when the file
            task began, used to derive per-tool wall-clock spans.

    """

    file: str
    command: list[str]
    status: str
    exit_code: int | None
    duration_seconds: float
    diagnostics: list[Diagnostic]
    stdout: str
    stderr: str
    format_calls: int = 0
    fix_calls: int = 0
    start_size: int = 0
    end_size: int = 0
    size_delta: int = 0
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    total: int = 0
    current: int = 0
    started_monotonic: float = 0.0


@dataclass(frozen=True, slots=True)
class StabilizationStart:
    """Capture the moment one file's stabilization began.

    Attributes:
        size: File size before processing.
        datetime: UTC datetime when processing started.
        time: Monotonic start timestamp.

    """

    size: int
    datetime: datetime
    time: float


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Represent the aggregate result of one tool's file tasks.

    Attributes:
        name: Stable tool name matching its :class:`ToolSpec`.
        status: Outcome label: ``passed``, ``failed`` or ``unavailable``.
        duration_seconds: Wall-clock span from the first file task
            start to the last file task completion.
        total_files: Number of files discovered for the tool.
        completed_files: Number of file tasks that finished.
        diagnostics: Merged diagnostics of every file task.
        files: Per-file results sorted by file path.

    """

    name: str
    status: str
    duration_seconds: float
    total_files: int
    completed_files: int
    diagnostics: list[Diagnostic]
    files: list[FileResult]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Describe a linter and the files it accepts.

    Attributes:
        name: Stable tool name used in progress rows and the report.
        executable: Program resolved on ``PATH`` before tasks launch.
        parser: Key selecting the output parser on the runner.
        suffixes: Lowercase file suffixes the tool accepts.
        arguments: Fixed arguments inserted into every command line.
        file_before_arguments: When ``True`` the file path precedes
            ``arguments``; otherwise it is appended after them.
        command_prefix: Alternative executable vector overriding
            ``executable`` when non-empty.
        project: When ``True`` the tool checks the whole project in one
            process so ``arguments`` already carry the project selector
            and no file path is passed.
        batch: When ``True`` the discovered files are grouped into
            ``batch_chunks`` invocations instead of one process per
            file; ignored when ``project`` is set.
        batch_chunks: Invocation count for ``batch``; ``None`` uses the
            runner's worker count.
        derived_from: Name of another tool whose diagnostics are reused
            instead of launching this tool; filtered by
            ``derived_prefix``.
        derived_prefix: Diagnostic code prefix kept by ``derived_from``.
        derived_exclude: Code prefixes removed after ``derived_prefix``
            matches, for sibling families sharing the prefix.

    """

    name: str
    executable: str
    parser: str
    suffixes: frozenset[str]
    arguments: tuple[str, ...]
    file_before_arguments: bool = False
    command_prefix: tuple[str, ...] = ()
    project: bool = False
    batch: bool = False
    batch_chunks: int | None = None
    derived_from: str | None = None
    derived_prefix: str = ""
    derived_exclude: tuple[str, ...] = ()

    def command(self, *, file: Path) -> list[str]:
        """Build the command for exactly one source file.

        Args:
            file: Project-relative source file.

        Returns:
            Complete process argument vector with the file placed either
            before or after the fixed arguments, or just the fixed
            arguments when the tool checks the whole project at once.

        """
        prefix: tuple[str, ...] = self.command_prefix or (self.executable,)
        if self.project:
            return [*prefix, *self.arguments]
        if self.file_before_arguments:
            return [*prefix, str(object=file), *self.arguments]
        return [*prefix, *self.arguments, str(object=file)]

    def available(self) -> bool:
        """Return whether the command prefix can be launched.

        Returns:
            Whether the resolved executable exists on ``PATH`` or at its
            configured path.

        """
        command: str = (self.command_prefix or (self.executable,))[0]
        candidate: Path = Path(command).expanduser()
        return (
            candidate.is_file()
            if candidate.parent != Path()
            else which(cmd=command) is not None
        )


@dataclass(slots=True)
class ProgressState:
    """Store mutable counters for one progress row.

    Attributes:
        total: Total number of work items in the row.
        completed: Number of work items finished so far.
        issues: Bar positions whose completed work items produced
            diagnostics; rendered in the failure color.

    """

    total: int
    completed: int = 0
    issues: set[int] = field(default_factory=set)


class FinishCallback(Protocol):
    """Define the callback invoked after processing each file."""

    def __call__(self, *, result: FileResult) -> None:
        """Handle a completed file.

        Args:
            result: Completed file processing metadata.

        """
        ...


class FileRepair(Protocol):
    """Define a per-file repair applied inside the stabilization loop."""

    def __call__(self, *, path: Path) -> None:
        """Repair one stabilized Python file in place.

        The stabilizer re-runs Ruff when the file changed, so a repair may
        leave the file in a state Ruff still has to normalize.

        Args:
            path: Python file that Ruff just formatted and fixed.

        """
        ...


class BatchFileRepair(Protocol):
    """Define a batch repair applied inside the stabilization loop."""

    def repair_many(self, *, paths: tuple[Path, ...]) -> None:
        """Repair stabilized Python files in one batch.

        Args:
            paths: Python files Ruff just formatted and fixed.

        """
        ...


class ProgressListener(Protocol):
    """Define the sink notified when audit progress changes."""

    def __call__(self, *, completed: int, total: int, detail: str) -> None:
        """Handle one progress snapshot.

        Args:
            completed: Completed file/tool checks.
            total: Discovered file/tool checks.
            detail: Label describing the latest progress event.

        """
        ...


@dataclass(frozen=True, slots=True)
class RuffStabilizerOptions:
    """Configure Ruff stabilization without widening its constructor.

    Attributes:
        command_prefix: Executable vector used to invoke Ruff.
        unsafe_fixes: Whether ``--unsafe-fixes`` is applied.
        repair: Optional per-file repair run after every Ruff format/fix cycle.
        batch_repair: Optional batch repair run once after every Ruff
            format/fix cycle.

    """

    command_prefix: tuple[str, ...] = ("ruff",)
    unsafe_fixes: bool = False
    repair: FileRepair | None = None
    batch_repair: BatchFileRepair | None = None


class RuffStabilizer:
    """Format and fix Python files with Ruff in parallel until stable."""

    def __init__(
        self,
        *,
        paths: list[Path],
        callback: FinishCallback | None = None,
        max_workers: int | None = None,
        max_iterations: int = 20,
        options: RuffStabilizerOptions | None = None,
    ) -> None:
        """Stabilize multiple Python files concurrently.

        Args:
            paths: Python files to process.
            callback: Optional function called when each file completes.
            max_workers: Maximum number of concurrently processed files.
            max_iterations: Maximum stabilization iterations per operation.
            options: Ruff command prefix and unsafe-fix policy.

        Raises:
            FileNotFoundError: If any target file does not exist.

        """
        self._paths: tuple[Path, ...] = tuple(paths)
        self._callback: FinishCallback | None = callback
        self._max_workers: int | None = max_workers
        self._max_iterations: int = max_iterations
        resolved: RuffStabilizerOptions = options or RuffStabilizerOptions()
        self._command_prefix: tuple[str, ...] = resolved.command_prefix
        self._unsafe_fixes: bool = resolved.unsafe_fixes
        self._repair: FileRepair | None = resolved.repair
        self._batch_repair: BatchFileRepair | None = resolved.batch_repair
        self._lock: Lock = Lock()
        self._processes: set[Popen[bytes]] = set()
        self._processes_lock: Lock = Lock()
        self._current: int = 0
        for path in self._paths:
            if not path.is_file():
                msg: str = f"File does not exist: {path}"
                raise FileNotFoundError(msg)
        if len(self._paths) > 1:
            self._stabilize_batch()
        else:
            executor: ThreadPoolExecutor = ThreadPoolExecutor(
                max_workers=self._max_workers,
            )
            try:
                tuple(executor.map(self._stabilize, self._paths))
            except BaseException:
                self._terminate_processes()
                executor.shutdown(wait=False, cancel_futures=True)
                raise
            else:
                executor.shutdown(wait=True)

    def ruff_format_until_stable(self, *, path: Path) -> int:
        """Run Ruff format until a file stops changing.

        Args:
            path: Python file to format.

        Returns:
            Number of Ruff format process invocations.

        Raises:
            RuntimeError: If formatting does not stabilize.

        """
        for iteration in range(1, self._max_iterations + 1):
            before: bytes = path.read_bytes()
            self._run(args=(*self._command_prefix, "format", str(object=path)))
            if path.read_bytes() == before:
                return iteration
        msg: str = " ".join(
            (
                f"Ruff format did not stabilize {path} after",
                f"{self._max_iterations} iterations.",
            ),
        )
        raise RuntimeError(msg)

    def ruff_fix_until_stable(self, *, path: Path) -> int:
        """Run Ruff check --fix until a file stops changing.

        Args:
            path: Python file to fix.

        Returns:
            Number of Ruff check process invocations.

        Raises:
            RuntimeError: If fixing does not stabilize.

        """
        for iteration in range(1, self._max_iterations + 1):
            before: bytes = path.read_bytes()
            self._run(
                args=(
                    *self._command_prefix,
                    "check",
                    "--select",
                    "ALL",
                    "--ignore",
                    Constants.ruff_conflict_ignores,
                    "--fix",
                    *(("--unsafe-fixes",) if self._unsafe_fixes else ()),
                    str(object=path),
                ),
            )
            if path.read_bytes() == before:
                return iteration
        msg: str = " ".join(
            (
                f"Ruff check did not stabilize {path} after",
                f"{self._max_iterations} iterations.",
            ),
        )
        raise RuntimeError(msg)

    def _final_compact_pass(
        self,
        *,
        paths: tuple[Path, ...],
    ) -> tuple[int, int]:
        """Apply compact formatting and fixes until both stop changing.

        Args:
            paths: Files that completed ordinary stabilization.

        Returns:
            Formatter and fixer invocation counts for each supplied file.

        Raises:
            RuntimeError: If the final formatting/fixing cycle
                does not converge.

        """
        if not paths:
            return (0, 0)
        format_args: tuple[str, ...] = (
            *self._command_prefix,
            "format",
            "--config",
            "format.skip-magic-trailing-comma = true",
            "--config",
            "format.docstring-code-format = true",
            "--config",
            'format.docstring-code-line-length = "dynamic"',
            "--config",
            'format.quote-style = "double"',
            "--config",
            'format.nested-string-quote-style = "preferred"',
            "--config",
            'format.line-ending = "lf"',
            "--config",
            'format.indent-style = "space"',
            *tuple(str(object=path) for path in paths),
        )
        fix_args: tuple[str, ...] = (
            *self._command_prefix,
            "check",
            "--select",
            "ALL",
            "--ignore",
            Constants.ruff_conflict_ignores,
            "--fix",
            *(("--unsafe-fixes",) if self._unsafe_fixes else ()),
            *tuple(str(object=path) for path in paths),
        )
        for iteration in range(1, self._max_iterations + 1):
            before: tuple[bytes, ...] = tuple(
                path.read_bytes() for path in paths
            )
            self._run(args=format_args)
            self._run(args=fix_args)
            if all(
                path.read_bytes() == previous
                for path, previous in zip(paths, before, strict=True)
            ):
                return (iteration, iteration)
        msg: str = (
            "Final Ruff compact pass did not converge "
            f"after {self._max_iterations} cycles."
        )
        raise RuntimeError(msg)

    def _stabilize_batch(self) -> None:
        """Stabilize many files with one Ruff process per complete cycle.

        Ruff natively parallelizes a multi-path invocation. Batching avoids
        launching thousands of short-lived Python processes for repositories
        with hundreds of files while retaining per-file convergence and
        progress records.

        Raises:
            RuntimeError: If any file keeps changing through every cycle.

        """
        active: list[Path] = list(self._paths)
        starts: dict[Path, StabilizationStart] = {
            path: StabilizationStart(
                size=path.stat().st_size,
                datetime=datetime.now(tz=UTC),
                time=monotonic(),
            )
            for path in active
        }
        format_calls: dict[Path, int] = dict.fromkeys(active, 0)
        fix_calls: dict[Path, int] = dict.fromkeys(active, 0)
        for _iteration in range(self._max_iterations):
            cycle: int = _iteration + 1
            before: dict[Path, bytes] = {
                path: path.read_bytes() for path in active
            }
            trace(
                step=(
                    f"stabilize: cycle "
                    f"{cycle} — ruff format ({len(active)} files)"
                ),
                depth=3,
            )
            self._run(
                args=(
                    *self._command_prefix,
                    "format",
                    *(str(object=path) for path in active),
                ),
            )
            trace(
                step=(
                    f"stabilize: cycle "
                    f"{cycle} — ruff check --fix ({len(active)} files)"
                ),
                depth=3,
            )
            self._run(
                args=(
                    *self._command_prefix,
                    "check",
                    "--select",
                    "ALL",
                    "--ignore",
                    Constants.ruff_conflict_ignores,
                    "--fix",
                    *(("--unsafe-fixes",) if self._unsafe_fixes else ()),
                    *(str(object=path) for path in active),
                ),
            )
            path: Path
            if self._batch_repair is not None:
                trace(
                    step=(
                        f"stabilize: cycle "
                        f"{cycle} — batch file repair ({len(active)} files)"
                    ),
                    depth=3,
                )
                self._batch_repair.repair_many(paths=tuple(active))
            elif self._repair is not None:
                trace(
                    step=(
                        f"stabilize: cycle "
                        f"{cycle} — file repair ({len(active)} files)"
                    ),
                    depth=3,
                )
            for path in active:
                format_calls[path] += 1
                fix_calls[path] += 1
                if self._batch_repair is None and self._repair is not None:
                    self._repair(path=path)
            changed: list[Path] = []
            for path in active:
                if path.read_bytes() != before[path]:
                    changed.append(path)
                    continue
                continue
            trace(
                step=(
                    f"stabilize: cycle "
                    f"{cycle} — {len(changed)} files still changing"
                ),
                depth=3,
            )
            if not changed:
                extra_format, extra_fix = self._final_compact_pass(
                    paths=self._paths,
                )
                for completed in self._paths:
                    self._finish(
                        path=completed,
                        format_calls=format_calls[completed] + extra_format,
                        fix_calls=fix_calls[completed] + extra_fix,
                        started=starts[completed],
                    )
                return
            active = changed
        trace(
            step=f"stabilize: failed — {len(active)} files did not converge",
            depth=3,
        )
        msg: str = " ".join(
            (
                "Ruff did not stabilize",
                f"{len(active)} files after",
                f"{self._max_iterations} complete cycles.",
            ),
        )
        raise RuntimeError(msg)

    def _terminate_processes(self) -> None:
        """Kill every in-flight Ruff process owned by the stabilizer."""
        with self._processes_lock:
            running: tuple[Popen[bytes], ...] = tuple(self._processes)
        for process in running:
            if process.poll() is None:
                process.kill()

    def _run(self, *, args: tuple[str, ...]) -> None:
        """Run one registered Ruff subprocess to completion.

        Args:
            args: Full Ruff command line to execute.

        """
        process: Popen[bytes] = Popen(args=args, stdout=PIPE, stderr=PIPE)
        with self._processes_lock:
            self._processes.add(process)
        try:
            _ = process.communicate()
        finally:
            with self._processes_lock:
                _ = self._processes.discard(process)

    def _stabilize(self, path: Path) -> None:
        """Run complete Ruff cycles until a file stabilizes.

        Args:
            path: Python file to stabilize.

        Raises:
            RuntimeError: If the file does not stabilize.

        """
        started: StabilizationStart = StabilizationStart(
            size=path.stat().st_size,
            datetime=datetime.now(tz=UTC),
            time=monotonic(),
        )
        format_calls: int = 0
        fix_calls: int = 0
        for _iteration in range(self._max_iterations):
            trace(
                step=f"stabilize: {path.as_posix()} — cycle {_iteration + 1}",
                depth=4,
            )
            before: bytes = path.read_bytes()
            format_calls += self.ruff_format_until_stable(path=path)
            fix_calls += self.ruff_fix_until_stable(path=path)
            if self._batch_repair is not None:
                self._batch_repair.repair_many(paths=(path,))
            elif self._repair is not None:
                self._repair(path=path)
            if path.read_bytes() == before:
                extra_format, extra_fix = self._final_compact_pass(
                    paths=(path,),
                )
                self._finish(
                    path=path,
                    format_calls=format_calls + extra_format,
                    fix_calls=fix_calls + extra_fix,
                    started=started,
                )
                return
        msg: str = " ".join(
            (
                f"Ruff did not stabilize {path} after",
                f"{self._max_iterations} complete cycles.",
            ),
        )
        raise RuntimeError(msg)

    def _finish(
        self,
        *,
        path: Path,
        format_calls: int,
        fix_calls: int,
        started: StabilizationStart,
    ) -> None:
        """Record completion and invoke the optional callback.

        Args:
            path: Processed file.
            format_calls: Number of Ruff format invocations.
            fix_calls: Number of Ruff check invocations.
            started: Size and timestamps captured before processing.

        """
        end_datetime: datetime = datetime.now(tz=UTC)
        duration: float = monotonic() - started.time
        end_size: int = path.stat().st_size
        trace(
            step=(
                f"stabilize: "
                f"{path.as_posix()}"
                f" — format "
                f"{format_calls}"
                f" calls, fix "
                f"{fix_calls}"
                f" calls, "
                f"{duration:.3f}"
                f"s, "
                f"{end_size - started.size:+d}"
                f"B"
            ),
            depth=4,
        )
        with self._lock:
            self._current += 1
            current: int = self._current
        if self._callback is not None:
            self._callback(
                result=FileResult(
                    file=path.as_posix(),
                    command=[],
                    status="passed",
                    exit_code=None,
                    duration_seconds=duration,
                    diagnostics=[],
                    stdout="",
                    stderr="",
                    format_calls=format_calls,
                    fix_calls=fix_calls,
                    start_size=started.size,
                    end_size=end_size,
                    size_delta=end_size - started.size,
                    start_datetime=started.datetime,
                    end_datetime=end_datetime,
                    total=len(self._paths),
                    current=current,
                    started_monotonic=started.time,
                ),
            )


class ProgressDisplay:
    """Render one global and one per-tool live progress bar.

    The global row counts file/tool tasks, so each completed check advances
    it even while other tools are still checking the same file.
    The display is disabled automatically when standard output is not a
    terminal, so non-interactive runs emit no escape sequences.
    """

    def __init__(
        self,
        *,
        totals: dict[str, int],
        listener: ProgressListener | None = None,
        draw: bool = True,
    ) -> None:
        """Initialize progress state.

        Args:
            totals: Initial file-task count keyed by tool name.
            listener: Optional sink receiving every progress snapshot;
                embedding tools pass one to merge this run into their
                own live progress channel.
            draw: Whether to render the terminal progress block.

        """
        self._states: dict[str, ProgressState] = {
            name: ProgressState(total=total) for name, total in totals.items()
        }
        self._global: ProgressState = ProgressState(total=0)
        self._remaining: dict[str, int] = {}
        self._lock: Lock = Lock()
        self._rendered: bool = False
        self._rows: int = 0
        self._listener: ProgressListener | None = listener
        self._enabled: bool = draw and sys.stdout.isatty()
        self._colored: bool = self._enabled and "NO_COLOR" not in environ
        self._slots: dict[tuple[str, str], int] = {}
        self._global_slots: dict[tuple[str, str], int] = {}

    def render(self) -> None:
        """Render or refresh the complete progress block.

        Does nothing when standard output is not a terminal.
        """
        if not self._enabled:
            return
        with self._lock:
            self._redraw()

    def update(self, *, tool: str, files: list[Path]) -> None:
        """Set one tool's discovered file list and refresh the display.

        Each file/tool check raises the global total and registers work
        still expected for the file.

        Args:
            tool: Tool whose files were just discovered.
            files: Project-relative files the tool will process.

        """
        with self._lock:
            self._states[tool].total = len(files)
            for file in files:
                key: str = file.as_posix()
                if key not in self._remaining:
                    self._remaining[key] = 0
                self._remaining[key] += 1
                self._global.total += 1
            completed: int = self._global.completed
            total: int = self._global.total
            if self._enabled:
                self._redraw()
        self._emit(detail=f"{tool} scanning", completed=completed, total=total)

    def finish(self, *, tool: str, file: str, issues: bool = False) -> None:
        """Record one completed file task and refresh the display.

        Args:
            tool: Tool whose file process just finished.
            file: Project-relative POSIX path of the finished file.
            issues: Whether the completed check produced diagnostics;
                the cell filled by this item renders red.

        """
        with self._lock:
            state: ProgressState = self._states[tool]
            self._slots[tool, file] = state.completed
            if issues:
                state.issues |= {state.completed}
            state.completed += 1
            pending: int = self._remaining.get(file, 0)
            if pending > 0:
                self._remaining[file] = pending - 1
                self._global_slots[tool, file] = self._global.completed
                if issues:
                    self._global.issues |= {self._global.completed}
                self._global.completed += 1
            completed: int = self._global.completed
            total: int = self._global.total
            if self._enabled:
                self._redraw()
        self._emit(detail=f"{tool}: {file}", completed=completed, total=total)

    def flag_issue(self, *, tool: str, file: str) -> None:
        """Mark an already-completed file task as having issues.

        Batched linters pace per-file completions before their combined
        result is known; once the process exits, each file carrying
        diagnostics is flagged so its filled cell turns red.

        Args:
            tool: Tool whose earlier finished file produced diagnostics.
            file: Project-relative POSIX path of the flagged file.

        """
        with self._lock:
            slot: int | None = self._slots.get((tool, file))
            if slot is not None:
                self._states[tool].issues |= {slot}
            global_slot: int | None = self._global_slots.get((tool, file))
            if global_slot is not None:
                self._global.issues |= {global_slot}
            if self._enabled:
                self._redraw()

    def heartbeat(self) -> None:
        """Publish activity without inventing completed work."""
        with self._lock:
            pending: str = ", ".join(
                (
                    f"{name} {state.completed}/{state.total}"
                    for name, state in self._states.items()
                    if state.completed < state.total
                ),
            )
            completed: int = self._global.completed
            total: int = self._global.total
        self._emit(
            detail=f"Checking: {pending}" if pending else "Preparing checks",
            completed=completed,
            total=total,
        )

    @staticmethod
    def _bar(
        *,
        completed: int,
        total: int,
        width: int = 28,
        colored: bool = True,
        issues: set[int] | None = None,
    ) -> str:
        """Create a fixed-width determinate bar.

        Args:
            completed: Finished work items.
            total: Total work items.
            width: Character width of the visual bar.
            colored: When ``True`` the filled segment renders green once
                complete and cyan while in progress, with a dimmed
                empty track.
            issues: Bar positions whose work items produced diagnostics;
                those cells render red while the rest keep the progress
                color.

        Returns:
            Rendered progress bar and percentage.

        """
        ratio: float = 1.0 if total == 0 else min(completed / total, 1.0)
        filled: int = round(number=ratio * width)
        color: str = (
            Constants.ansi_green if ratio >= 1.0 else Constants.ansi_cyan
        )
        flagged: set[int] = (
            {
                min(
                    width - 1,
                    max(0, round(number=(ordinal + 1) / total * width) - 1),
                )
                for ordinal in issues or ()
                if total > 0
            }
            if colored
            else set()
        )
        cells: str = "".join(
            f"{(Constants.ansi_red if index in flagged else color)}█"
            for index in range(filled)
        )
        unfilled: str = "░" * (width - filled)
        bar: str = (
            _join(
                parts=(
                    Constants.ansi_dim,
                    "[",
                    cells,
                    Constants.ansi_dim,
                    unfilled,
                    "]",
                    Constants.ansi_reset,
                ),
            )
            if colored
            else f"[{'█' * filled}{unfilled}]"
        )
        return f"{bar} {ratio * 100:6.2f}% {completed}/{total}"

    def _lines(self) -> list[str]:
        """Build all current progress lines.

        Returns:
            Global row followed by stable per-tool rows.

        """
        width: int = max((len(name) for name in self._states), default=4)
        total: str = self._bar(
            completed=self._global.completed,
            total=self._global.total,
            colored=self._colored,
            issues=self._global.issues,
        )
        return [
            _paint(
                text=f"{'TOTAL'.ljust(width)}",
                color=Constants.ansi_bold,
                enabled=self._colored,
            )
            + f" {total}",
            *(
                " ".join(
                    (
                        f"{name:<{width}}",
                        self._bar(
                            completed=state.completed,
                            total=state.total,
                            colored=self._colored,
                            issues=state.issues,
                        ),
                    ),
                )
                for name, state in self._states.items()
            ),
        ]

    def _emit(self, *, detail: str, completed: int, total: int) -> None:
        """Forward counters snapshotted under ``_lock`` to the listener.

        The callback runs after ``_lock`` is released so a listener
        re-entering the display can never deadlock it.

        Args:
            detail: Label describing the latest progress event.
            completed: Global completed counter at snapshot time.
            total: Global total counter at snapshot time.

        """
        if self._listener is not None:
            self._listener(completed=completed, total=total, detail=detail)

    def _redraw(self) -> None:
        """Write or rewrite the complete progress block."""
        lines: list[str] = self._lines()
        parts: list[str] = []
        if self._rendered:
            parts.append(f"\x1b[{self._rows}F")
        parts.extend(f"\x1b[2K{line}\n" for line in lines)
        _ = sys.stdout.write("".join(parts))
        _ = sys.stdout.flush()
        self._rows = len(lines)
        self._rendered = True


class IgnoreMatcher:
    """Match project-relative paths against merged ignore patterns."""

    def __init__(self, *, patterns: Iterable[str]) -> None:
        """Initialize the matcher.

        Args:
            patterns: Glob-like project ignore patterns.

        """
        self._patterns: tuple[str, ...] = tuple(dict.fromkeys(patterns))

    def matches(self, *, path: Path) -> bool:
        """Return whether a relative path is ignored.

        Args:
            path: Project-relative path.

        Returns:
            True when any configured pattern matches the path or a parent.

        """
        value: str = path.as_posix()
        candidates: tuple[str, ...] = (
            value,
            *[
                parent.as_posix()
                for parent in path.parents
                if parent != Path()
            ],
        )
        return any(
            fnmatch(name=candidate, pat=pattern)
            or fnmatch(name=candidate, pat=pattern.removeprefix("**/"))
            for pattern in self._patterns
            for candidate in candidates
        )


class Configuration:
    """Load merged default and pyproject exclusion rules.

    Exclusion patterns come from three sources merged in order: the
    built-in :data:`Constants.excludes` list, the audit's own
    ``[tool.audit_linters_json]`` section (optionally narrowed per tool),
    and each tool's native ``pyproject.toml`` section.
    """

    def __init__(self, *, root: Path) -> None:
        """Initialize project configuration.

        Args:
            root: Audited project root.

        """
        self._root: Path = root
        self._document: dict[str, JsonValue] = self._load()

    def excludes(self, *, tool: str) -> list[str]:
        """Return merged exclusions for one tool.

        Args:
            tool: Stable audit tool name.

        Returns:
            Deduplicated default, audit-specific, and native exclusions.

        """
        patterns: list[str] = list(Constants.excludes)
        audit: JsonObject = self._tool(name="audit_linters_json")
        patterns.extend(self._strings(value=audit.get("exclude")))
        patterns.extend(self._strings(value=audit.get("extend-exclude")))
        subsection: JsonValue | None = audit.get(tool)
        if isinstance(subsection, dict):
            patterns.extend(self._strings(value=subsection.get("exclude")))
            patterns.extend(
                self._strings(value=subsection.get("extend-exclude")),
            )
        native_name: str = "ruff" if tool in {"ruff", "ruff_docs"} else tool
        native: JsonObject = self._tool(name=native_name)
        for key in ("exclude", "extend-exclude", "project-excludes"):
            patterns.extend(self._strings(value=native.get(key)))
        return list(dict.fromkeys(patterns))

    def output_dir(self) -> str:
        """Return the configured report directory name.

        Returns:
            ``tool.all_lint``/``tool.all_lints`` ``output-dir`` value,
            or :data:`Constants.report_directory` when unset.

        """
        value: JsonValue | None = self._all_lints().get("output-dir")
        return (
            value
            if isinstance(value, str) and value
            else Constants.report_directory
        )

    def collect_files(self) -> bool:
        """Return whether the ``FILES`` bundle is enabled.

        Returns:
            ``tool.all_lint``/``tool.all_lints`` ``collect-files`` flag;
            ``false`` (the default) skips bundle generation.

        """
        return self._all_lints().get("collect-files") is True

    @staticmethod
    def _strings(*, value: JsonValue | None) -> list[str]:
        """Extract strings from a TOML array value.

        Args:
            value: Parsed TOML value.

        Returns:
            String entries only.

        """
        return (
            [item for item in value if isinstance(item, str)]
            if isinstance(value, list)
            else []
        )

    def _all_lints(self) -> JsonObject:
        """Return the merged ``tool.all_lint(s)`` section.

        Returns:
            ``tool.all_lint`` entries overlaid by ``tool.all_lints``
            so either spelling configures the standalone runner.

        """
        alias: JsonObject = self._tool(name="all_lint")
        section: JsonObject = self._tool(name="all_lints")
        return {**alias, **section}

    def _load(self) -> dict[str, JsonValue]:
        """Load pyproject when present.

        Returns:
            Parsed TOML document or an empty mapping.

        """
        path: Path = self._root / Constants.pyproject
        if not path.is_file():
            return {}
        with path.open(mode="rb") as stream:
            return cast(typ="dict[str, JsonValue]", val=load_toml(stream))

    def _tool(self, *, name: str) -> JsonObject:
        """Return a ``tool.<name>`` mapping.

        Args:
            name: Tool section name.

        Returns:
            Section mapping or an empty mapping.

        """
        tools: JsonValue | None = self._document.get("tool")
        section: JsonValue | None = (
            tools.get(name) if isinstance(tools, dict) else None
        )
        return section if isinstance(section, dict) else {}


class AuditRunner:
    """Batch type checkers and run remaining checks per discovered file."""

    def __init__(
        self,
        *,
        root: Path,
        workers: int,
        targets: tuple[str, ...] = (".",),
        excludes: tuple[str, ...] = (),
        pace_estimates: Mapping[str, float] | None = None,
    ) -> None:
        """Initialize the runner.

        Args:
            root: Audited project root.
            workers: Maximum concurrent file processes.
            targets: Relative files, directories or globs to include.
            excludes: Additional relative glob patterns to exclude.
            pace_estimates: Expected per-tool durations in seconds, used to
                spread batch progress across the real runtime; missing tools
                fall back to a fixed per-file pace.

        """
        self._repair: FileRepair | None = None
        self._batch_repair: BatchFileRepair | None = None
        self._root: Path = root.resolve()
        self._workers: int = workers
        self._processes: set[Popen[str]] = set()
        self._processes_lock: Lock = Lock()
        self._configuration: Configuration = Configuration(root=self._root)
        self._targets: tuple[str, ...] = targets or (".",)
        self._excludes: tuple[str, ...] = excludes
        self._pace_estimates: dict[str, float] = dict(pace_estimates or {})

    def use_repair(self, *, repair: FileRepair | None) -> None:
        """Install the repair applied while files are stabilized.

        Args:
            repair: Repair run for every stabilized file inside the Ruff
                format/fix convergence loop, or ``None`` to remove it.

        """
        self._repair = repair

    def use_batch_repair(self, *, repair: BatchFileRepair | None) -> None:
        """Install the batch repair applied while files are stabilized.

        Args:
            repair: Repair run once for all active files after each Ruff
                format/fix cycle, or ``None`` to remove it.

        """
        self._batch_repair = repair

    def discover(self, *, spec: ToolSpec) -> list[Path]:
        """Discover nonignored files accepted by one tool.

        Ignored directories are pruned during the walk, so large trees
        such as virtual environments or dependency folders are never
        descended into.

        Args:
            spec: Tool specification carrying the accepted suffixes and
                the name used to resolve merged exclusions.

        Returns:
            Sorted project-relative paths whose lowercase suffix the spec
            accepts and which no merged ignore pattern matches.

        """
        matcher: IgnoreMatcher = IgnoreMatcher(
            patterns=(
                *self._configuration.excludes(tool=spec.name),
                *self._excludes,
            ),
        )
        found: list[Path] = []
        for directory, dirnames, filenames in walk(top=self._root):
            relative_dir: Path = Path(directory).relative_to(self._root)
            dirnames[:] = [
                name
                for name in dirnames
                if not matcher.matches(path=relative_dir / name)
            ]
            found.extend(
                relative_dir / name
                for name in filenames
                if Path(name).suffix.lower() in spec.suffixes
                and (not matcher.matches(path=relative_dir / name))
                and self._targeted(path=relative_dir / name)
            )
        return sorted(found, key=lambda path: path.as_posix())

    def run_file(self, *, spec: ToolSpec, file: Path) -> FileResult:
        """Run exactly one linter process against one source file.

        Args:
            spec: Tool specification describing the executable and the
                argument layout.
            file: Project-relative file path to lint.

        Returns:
            Completed single-file result carrying parsed diagnostics; an
            ``error`` result when the process cannot be spawned.

        """
        command: list[str] = spec.command(file=file)
        trace(
            step=f"{spec.name}: exec {file.as_posix()} — {len(command)} argv",
            depth=4,
        )
        started: float = monotonic()
        try:
            process: Popen[str] = Popen(
                args=command,
                cwd=self._root,
                stdout=PIPE,
                stderr=PIPE,
                text=True,
                env=environ.copy(),
            )
        except OSError as error:
            trace(
                step=f"{spec.name}: {file.as_posix()} — spawn failed: {error}",
                depth=4,
            )
            return FileResult(
                file=file.as_posix(),
                command=command,
                status="error",
                exit_code=None,
                duration_seconds=round(
                    number=monotonic() - started,
                    ndigits=6,
                ),
                diagnostics=[],
                stdout="",
                stderr=str(object=error),
                started_monotonic=started,
            )
        with self._processes_lock:
            self._processes.add(process)
        try:
            process_stdout, process_stderr = process.communicate()
        finally:
            with self._processes_lock:
                _ = self._processes.discard(process)
        output: str = (
            process_stdout if process_stdout.strip() else process_stderr
        )
        diagnostics: list[Diagnostic] = self._parse(
            spec=spec,
            file=file,
            output=output,
        )
        stderr_text: str = process_stderr
        if spec.parser == "ruff":
            stderr_text = "\n".join(
                line
                for line in stderr_text.splitlines()
                if "D203" not in line
                and "D211" not in line
                and ("D212" not in line)
                and ("D213" not in line)
            )
        machine_parsers: frozenset[str] = frozenset(
            {"ruff", "basedpyright", "eslint", "stylelint", "pyrefly"},
        )
        duration: float = round(number=monotonic() - started, ndigits=6)
        trace(
            step=(
                f"{spec.name}: {file.as_posix()} — exit {process.returncode}, {
                    len(diagnostics)
                } diagnostics, "
                f"{duration}s"
            ),
            depth=4,
        )
        return FileResult(
            file=file.as_posix(),
            command=command,
            status="passed" if process.returncode == 0 else "failed",
            exit_code=process.returncode,
            duration_seconds=duration,
            diagnostics=diagnostics,
            stdout="" if spec.parser in machine_parsers else process_stdout,
            stderr=stderr_text,
            started_monotonic=started,
        )

    def run_all(
        self,
        *,
        specs: list[ToolSpec],
        stabilize: bool = False,
        unsafe_fixes: bool = False,
        listener: ProgressListener | None = None,
        draw: bool = True,
    ) -> list[ToolResult]:
        """Run every file task through one parallel worker pool.

        Tasks are submitted file-major: all tool tasks for one file are
        adjacent in the queue, so a file finishes every tool early and
        the global progress row advances continuously rather than
        waiting for the last tool's batch.

        Args:
            specs: Tool specifications to discover files for and run.
            stabilize: When ``True``, run the Ruff format/fix cycles on
                the files discovered by the ``ruff`` spec before the
                Python-aware linter passes; tools covering other file
                kinds start immediately while stabilization runs. The
                work is reported on a ``stabilize`` row of the same
                progress display.
            unsafe_fixes: Whether stabilization may apply Ruff unsafe fixes.
            listener: Optional sink receiving a progress snapshot for
                every discovery and completion event so embedding tools
                can fold this audit into their own live progress.
            draw: Whether the terminal progress block is rendered.

        Returns:
            One aggregate result per spec in the order the specs were
            given; tools whose executable is missing are reported as
            ``unavailable`` without launching any process.

        """
        started: float = monotonic()
        trace(
            step=(
                f"all lints: start — "
                f"{len(specs)} tools, {self._workers} workers, stabilize={
                    ('on' if stabilize else 'off')
                }"
            ),
            depth=1,
        )
        progress: ProgressDisplay = ProgressDisplay(
            totals=self._totals(specs=specs, stabilize=stabilize),
            listener=listener,
            draw=draw,
        )
        progress.render()
        trace(step="all lints: discover files", depth=2)
        files_by_tool: dict[str, list[Path]] = self._discover_all(specs=specs)
        resolved: dict[str, ToolSpec] = {}
        for spec in specs:
            effective: ToolSpec = spec
            discovered: list[Path] = files_by_tool[spec.name]
            if spec.project:
                config: Path | None = self._project_config()
                trace(
                    step=(
                        f"all lints: {spec.name} project config — "
                        f"{(config.name if config is not None else 'none')}"
                    ),
                    depth=3,
                )
                effective = (
                    replace(
                        spec,
                        arguments=(
                            *spec.arguments,
                            "--project",
                            str(object=config),
                        ),
                    )
                    if config is not None
                    else spec
                )
                discovered = discovered if config is not None else []
            resolved[spec.name] = effective
            files_by_tool[spec.name] = discovered
            trace(
                step=f"all lints: {spec.name} — {len(discovered)} files",
                depth=3,
            )
            progress.update(tool=spec.name, files=discovered)
        collected: dict[str, list[FileResult]] = {
            spec.name: [] for spec in specs
        }
        unavailable, specs_by_file = self._plan(
            specs=specs,
            resolved=resolved,
            files_by_tool=files_by_tool,
            progress=progress,
        )
        trace(
            step=(
                f"all lints: execute — {len(specs_by_file)} files with checks"
            ),
            depth=2,
        )
        collected.update(
            self._execute(
                specs_by_file=specs_by_file,
                stabilize=lambda: self._stabilize_files(
                    files=files_by_tool.get("ruff", []),
                    progress=progress,
                    enabled=stabilize,
                    command_prefix=next(
                        (
                            spec.command_prefix or (spec.executable,)
                            for spec in specs
                            if spec.name == "ruff"
                        ),
                        ("ruff",),
                    ),
                    unsafe_fixes=unsafe_fixes,
                ),
                progress=progress,
            ),
        )
        trace(step="all lints: derive results", depth=2)
        self._derive_results(
            specs=specs,
            files_by_tool=files_by_tool,
            collected=collected,
            unavailable=unavailable,
            progress=progress,
        )
        results: list[ToolResult] = []
        for spec in specs:
            files: list[FileResult] = sorted(
                collected[spec.name],
                key=lambda item: item.file,
            )
            diagnostics: list[Diagnostic] = [
                diagnostic for item in files for diagnostic in item.diagnostics
            ]
            status: str = (
                "unavailable"
                if spec.name in unavailable
                else "failed"
                if any(item.status != "passed" for item in files)
                else "passed"
            )
            trace(
                step=(
                    f"all lints: "
                    f"{spec.name}"
                    f" — "
                    f"{status}"
                    f", "
                    f"{len(files_by_tool[spec.name])}"
                    f" files, "
                    f"{len(diagnostics)}"
                    f" diagnostics"
                ),
                depth=2,
            )
            results.append(
                ToolResult(
                    name=spec.name,
                    status=status,
                    duration_seconds=self._tool_span(files=files),
                    total_files=len(files_by_tool[spec.name]),
                    completed_files=len(files_by_tool[spec.name]),
                    diagnostics=diagnostics,
                    files=files,
                ),
            )
        trace(
            step=(
                f"all lints: finished — "
                f"{round(number=monotonic() - started, ndigits=3)}s"
            ),
            depth=1,
        )
        return results

    @staticmethod
    def _decode_json(*, text: str) -> JsonValue | None:
        """Decode machine-readable tool output.

        Args:
            text: Raw JSON text.

        Returns:
            Decoded value or None for malformed output.

        """
        try:
            return cast(typ="JsonValue", val=loads(s=text))
        except JSONDecodeError:
            return None

    @staticmethod
    def _mapping(*, value: JsonValue | None) -> JsonObject:
        """Return a JSON mapping or an empty mapping.

        Args:
            value: Decoded JSON value.

        Returns:
            The value when it is a mapping, an empty mapping otherwise.

        """
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _sequence(*, value: JsonValue | None) -> list[JsonValue]:
        """Return a JSON sequence or an empty sequence.

        Args:
            value: Decoded JSON value.

        Returns:
            The value when it is a list, an empty list otherwise.

        """
        return value if isinstance(value, list) else []

    @staticmethod
    def _integer(*, value: JsonValue | None) -> int | None:
        """Convert a JSON scalar to an integer when possible.

        Args:
            value: Decoded JSON value.

        Returns:
            The coerced integer, or ``None`` for non-numeric values.

        """
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _string(*, value: JsonValue | None) -> str | None:
        """Convert a scalar JSON value to text.

        Args:
            value: Decoded JSON value.

        Returns:
            The scalar rendered as text, or ``None`` for ``None``,
            lists and mappings.

        """
        return (
            str(object=value)
            if value is not None and (not isinstance(value, (list, dict)))
            else None
        )

    @staticmethod
    def _severity(*, value: str | None, default: str = "error") -> str:
        """Normalize severity text.

        Args:
            value: Tool-specific severity label.
            default: Fallback severity for ``None`` or unrecognized
                input.

        Returns:
            One of ``error``, ``warning``, ``info`` or ``note``, or
            ``default`` when the label is not recognized.

        """
        normalized: str = (value or default).lower()
        if normalized in {"fatal", "error"}:
            return "error"
        if normalized in {"warn", "warning"}:
            return "warning"
        if normalized in {"information", "info"}:
            return "info"
        return "note" if normalized in {"hint", "note"} else default

    @staticmethod
    def _tool_span(*, files: list[FileResult]) -> float:
        """Measure one tool's wall-clock span across its file tasks.

        Args:
            files: Completed file results carrying start timestamps.


        Returns:
            Seconds from the first task start to the last task
            completion, or ``0.0`` when no task ran.

        """
        spans: list[tuple[float, float]] = [
            (
                item.started_monotonic,
                item.started_monotonic + item.duration_seconds,
            )
            for item in files
            if item.started_monotonic
        ]
        if not spans:
            return 0.0
        return round(
            number=max((end for _, end in spans))
            - min((start for start, _ in spans)),
            ndigits=6,
        )

    @staticmethod
    def _totals(*, specs: list[ToolSpec], stabilize: bool) -> dict[str, int]:
        """Build the initial progress row set for one audit run.

        Args:
            specs: Tool specifications to discover files for and run.
            stabilize: Whether a ``stabilize`` row precedes the tools.

        Returns:
            Row names mapped to their starting file counts.

        """
        totals: dict[str, int] = {"stabilize": 0} if stabilize else {}
        return totals | {spec.name: 0 for spec in specs}

    @staticmethod
    def _task_finished(
        future: Future[list[FileResult]],
        *,
        progress: ProgressDisplay,
        name: str,
        files: list[Path],
    ) -> None:
        """Publish a completion even while stabilization is running.

        Args:
            future: Completed or cancelled file check.
            progress: Shared progress sink.
            name: Linter name.
            files: Project-relative checked paths; batched tasks already
                published each file from ``_run_check`` and are now
                flagged so the cells they filled turn red.

        """
        if future.cancelled():
            return
        if len(files) == 1:
            progress.finish(tool=name, file=files[0].as_posix())
        if future.exception() is None:
            for result in future.result():
                if len(files) > 1:
                    trace(
                        step=(
                            f"{name}"
                            f": "
                            f"{result.file}"
                            f" — "
                            f"{result.status}"
                            f", "
                            f"{len(result.diagnostics)}"
                            f" diagnostics"
                        ),
                        depth=4,
                    )
                if result.diagnostics or result.status != "passed":
                    progress.flag_issue(tool=name, file=result.file)

    @staticmethod
    def _plan(
        *,
        specs: list[ToolSpec],
        resolved: dict[str, ToolSpec],
        files_by_tool: dict[str, list[Path]],
        progress: ProgressDisplay,
    ) -> tuple[set[str], dict[str, tuple[Path, list[ToolSpec]]]]:
        """Group executable tool tasks per file.

        Derived specs never queue a process: they reuse another tool's
        results after execution. A derived spec whose source tool is
        unavailable is reported unavailable as well.

        Args:
            specs: Tool specifications in report order.
            resolved: Effective specs keyed by tool name.
            files_by_tool: Discovered files keyed by tool name.
            progress: Display completing unavailable rows immediately.

        Returns:
            The unavailable tool names and the per-file task groups.

        """
        unavailable: set[str] = {
            spec.name for spec in specs if not spec.available()
        }
        for spec in specs:
            if (
                spec.derived_from is not None
                and spec.derived_from in unavailable
            ):
                unavailable.add(spec.name)
        for name in sorted(unavailable):
            trace(
                step=f"all lints: {name} — unavailable, no files checked",
                depth=3,
            )
            for file in files_by_tool[name]:
                progress.finish(tool=name, file=file.as_posix())
        specs_by_file: dict[str, tuple[Path, list[ToolSpec]]] = {}
        for spec in specs:
            if spec.name in unavailable or spec.derived_from is not None:
                continue
            effective: ToolSpec = resolved[spec.name]
            for file in files_by_tool[spec.name]:
                key: str = file.as_posix()
                if key in specs_by_file:
                    specs_by_file[key][1].append(effective)
                else:
                    specs_by_file[key] = (file, [effective])
        return (unavailable, specs_by_file)

    @staticmethod
    def _derive(
        *,
        spec: ToolSpec,
        files: list[Path],
        source: list[FileResult],
    ) -> list[FileResult]:
        """Reuse another tool's results filtered to a rule-code prefix.

        A derived spec never launches a process: its per-file results
        copy the source tool's outcomes with only the diagnostics whose
        codes start with ``derived_prefix``. A source failure carrying
        no diagnostics means the underlying process itself failed, so
        it propagates; a failure caused only by diagnostics outside the
        prefix becomes a pass because the derived rule set is clean.

        Args:
            spec: Derived tool specification.
            files: Files discovered for the derived tool.
            source: Completed results of the ``derived_from`` tool.

        Returns:
            Per-file results covering every derived file present in the
            source results.

        """
        by_file: dict[str, FileResult] = {item.file: item for item in source}
        results: list[FileResult] = []
        for file in files:
            original: FileResult | None = by_file.get(file.as_posix())
            if original is None:
                continue
            diagnostics: list[Diagnostic] = []
            for item in original.diagnostics:
                code: str = item.code or ""
                if code.startswith(spec.derived_prefix) and (
                    not any(
                        code.startswith(skip) for skip in spec.derived_exclude
                    )
                ):
                    diagnostics.append(replace(item, tool=spec.name))
            status: str = (
                original.status
                if original.status != "passed" and (not original.diagnostics)
                else "failed"
                if diagnostics
                else "passed"
            )
            results.append(
                replace(original, diagnostics=diagnostics, status=status),
            )
        return results

    def _targeted(self, *, path: Path) -> bool:
        """Return whether a relative path is inside the requested scope.

        Args:
            path: Project-relative file path being tested.

        Returns:
            Whether ``path`` matches any configured target or glob.

        """
        value: str = path.as_posix()
        for target in self._targets:
            normalized: str = target.removeprefix("./").rstrip("/") or "."
            if normalized == ".":
                return True
            if any(char in normalized for char in "*?["):
                if fnmatch(name=value, pat=normalized):
                    return True
                continue
            if value == normalized or value.startswith(f"{normalized}/"):
                return True
        return False

    def _relative(self, *, value: str | None, fallback: Path) -> str:
        """Normalize a diagnostic path to project-relative form.

        Args:
            value: Path reported by the tool, absolute or relative.
            fallback: Linted file used when ``value`` is ``None``.

        Returns:
            The project-relative POSIX path, ``fallback`` rendered as
            POSIX when ``value`` is ``None``, or the path unchanged when
            it cannot be made relative to the project root.

        """
        if value is None:
            return fallback.as_posix()
        path: Path = Path(value)
        try:
            return (
                path.resolve().relative_to(self._root).as_posix()
                if path.is_absolute()
                else path.as_posix()
            )
        except ValueError:
            return path.as_posix()

    def _discover_all(self, *, specs: list[ToolSpec]) -> dict[str, list[Path]]:
        """Discover every tool's files during one project traversal.

        Tool-specific exclusions are still evaluated independently. A
        directory is pruned only when every tool excludes it, preserving the
        exact per-tool scope while avoiding one complete filesystem walk per
        linter.

        Args:
            specs: Tool specifications whose scopes are required.

        Returns:
            Sorted project-relative files keyed by tool name.

        """
        matchers: dict[str, IgnoreMatcher] = {
            spec.name: IgnoreMatcher(
                patterns=(
                    *self._configuration.excludes(tool=spec.name),
                    *self._excludes,
                ),
            )
            for spec in specs
        }
        found: dict[str, list[Path]] = {spec.name: [] for spec in specs}
        for directory, dirnames, filenames in walk(top=self._root):
            relative_dir: Path = Path(directory).relative_to(self._root)
            dirnames[:] = [
                name
                for name in dirnames
                if not all(
                    matcher.matches(path=relative_dir / name)
                    for matcher in matchers.values()
                )
            ]
            name: str
            for name in filenames:
                path: Path = relative_dir / name
                if not self._targeted(path=path):
                    continue
                suffix: str = Path(name).suffix.lower()
                spec: ToolSpec
                for spec in specs:
                    if suffix in spec.suffixes and (
                        not matchers[spec.name].matches(path=path)
                    ):
                        found[spec.name].append(path)
        return {
            name: sorted(paths, key=lambda path: path.as_posix())
            for name, paths in found.items()
        }

    def _project_config(self) -> Path | None:
        """Locate the TypeScript project configuration at the root.

        ``jsconfig.json`` wins because it is the ``checkJs`` workspace
        configuration an editor type-checks against; ``tsconfig.json``
        is the TypeScript-native fallback.

        Returns:
            Absolute configuration path, or ``None`` when the project
            owns neither file.

        """
        for name in Constants.typescript_config_names:
            candidate: Path = self._root / name
            if candidate.is_file():
                return candidate
        return None

    def _ruff(self, *, tool: str, file: Path, text: str) -> list[Diagnostic]:
        """Parse Ruff JSON for one file.

        Args:
            tool: Reporting tool name (``ruff`` or ``ruff_docs``).
            file: Linted file used when an entry lacks a filename.
            text: Raw JSON array emitted by ``--output-format json``.

        Returns:
            Normalized diagnostics, one per decoded array entry.

        """
        diagnostics: list[Diagnostic] = []
        for value in self._sequence(value=self._decode_json(text=text)):
            item: JsonObject = self._mapping(value=value)
            start: JsonObject = self._mapping(value=item.get("location"))
            end: JsonObject = self._mapping(value=item.get("end_location"))
            diagnostics.append(
                Diagnostic(
                    tool=tool,
                    file=self._relative(
                        value=self._string(value=item.get("filename")),
                        fallback=file,
                    ),
                    line=self._integer(value=start.get("row")),
                    column=self._integer(value=start.get("column")),
                    end_line=self._integer(value=end.get("row")),
                    end_column=self._integer(value=end.get("column")),
                    severity="error",
                    code=self._string(value=item.get("code")),
                    message=self._string(value=item.get("message")) or "",
                ),
            )
        return diagnostics

    def _basedpyright(self, *, file: Path, text: str) -> list[Diagnostic]:
        """Parse BasedPyright's per-file JSON envelope.

        Args:
            file: Linted file used when an entry lacks a path.
            text: Raw JSON object emitted by ``--outputjson``.

        Returns:
            Normalized diagnostics from ``generalDiagnostics`` with
            zero-based positions converted to one-based.

        """
        root: JsonObject = self._mapping(value=self._decode_json(text=text))
        diagnostics: list[Diagnostic] = []
        for value in self._sequence(value=root.get("generalDiagnostics")):
            item: JsonObject = self._mapping(value=value)
            range_value: JsonObject = self._mapping(value=item.get("range"))
            start: JsonObject = self._mapping(value=range_value.get("start"))
            end: JsonObject = self._mapping(value=range_value.get("end"))
            start_line: int | None = self._integer(value=start.get("line"))
            start_column: int | None = self._integer(
                value=start.get("character"),
            )
            end_line: int | None = self._integer(value=end.get("line"))
            end_column: int | None = self._integer(value=end.get("character"))
            diagnostics.append(
                Diagnostic(
                    tool="basedpyright",
                    file=self._relative(
                        value=self._string(value=item.get("file")),
                        fallback=file,
                    ),
                    line=start_line + 1 if start_line is not None else None,
                    column=start_column + 1
                    if start_column is not None
                    else None,
                    end_line=end_line + 1 if end_line is not None else None,
                    end_column=end_column + 1
                    if end_column is not None
                    else None,
                    severity=self._severity(
                        value=self._string(value=item.get("severity")),
                    ),
                    code=self._string(value=item.get("rule")),
                    message=self._string(value=item.get("message")) or "",
                ),
            )
        return diagnostics

    def _eslint(self, *, file: Path, text: str) -> list[Diagnostic]:
        """Parse ESLint JSON for one file.

        Args:
            file: Linted file used when an entry lacks a path.
            text: Raw JSON array emitted by ``--format json``.

        Returns:
            Normalized diagnostics with numeric severities split into
            ``error`` and ``warning``.

        """
        diagnostics: list[Diagnostic] = []
        for value in self._sequence(value=self._decode_json(text=text)):
            result: JsonObject = self._mapping(value=value)
            filename: str = self._relative(
                value=self._string(value=result.get("filePath")),
                fallback=file,
            )
            for message_value in self._sequence(value=result.get("messages")):
                message: JsonObject = self._mapping(value=message_value)
                severity: int | None = self._integer(
                    value=message.get("severity"),
                )
                diagnostics.append(
                    Diagnostic(
                        tool="eslint",
                        file=filename,
                        line=self._integer(value=message.get("line")),
                        column=self._integer(value=message.get("column")),
                        end_line=self._integer(value=message.get("endLine")),
                        end_column=self._integer(
                            value=message.get("endColumn"),
                        ),
                        severity="error"
                        if severity == Constants.eslint_severity_error
                        else "warning",
                        code=self._string(value=message.get("ruleId")),
                        message=self._string(value=message.get("message"))
                        or "",
                    ),
                )
        return diagnostics

    def _stylelint(self, *, file: Path, text: str) -> list[Diagnostic]:
        """Parse Stylelint JSON for one file.

        Args:
            file: Linted file used when an entry lacks a source path.
            text: Raw JSON array emitted by ``--formatter json``.

        Returns:
            Normalized diagnostics, one per entry in ``warnings``.

        """
        diagnostics: list[Diagnostic] = []
        for value in self._sequence(value=self._decode_json(text=text)):
            result: JsonObject = self._mapping(value=value)
            filename: str = self._relative(
                value=self._string(value=result.get("source")),
                fallback=file,
            )
            for warning_value in self._sequence(value=result.get("warnings")):
                warning: JsonObject = self._mapping(value=warning_value)
                diagnostics.append(
                    Diagnostic(
                        tool="stylelint",
                        file=filename,
                        line=self._integer(value=warning.get("line")),
                        column=self._integer(value=warning.get("column")),
                        end_line=self._integer(value=warning.get("endLine")),
                        end_column=self._integer(
                            value=warning.get("endColumn"),
                        ),
                        severity=self._severity(
                            value=self._string(value=warning.get("severity")),
                        ),
                        code=self._string(value=warning.get("rule")),
                        message=self._string(value=warning.get("text")) or "",
                    ),
                )
        return diagnostics

    def _pyrefly(self, *, file: Path, text: str) -> list[Diagnostic]:
        """Parse Pyrefly JSON or JSON-lines output for one file.

        Args:
            file: Linted file used when an entry lacks a path.
            text: Raw output emitted by ``--output-format json``; a JSON
                array, an object carrying ``errors``/``diagnostics``, or
                one JSON object per line.

        Returns:
            Normalized diagnostics collected from whichever envelope was
            emitted.

        """
        decoded: JsonValue | None = self._decode_json(text=text)
        values: list[JsonValue] = self._sequence(value=decoded)
        if isinstance(decoded, dict):
            values = self._sequence(
                value=decoded.get("errors") or decoded.get("diagnostics"),
            )
        if decoded is None:
            values = [
                value
                for line in text.splitlines()
                if (value := self._decode_json(text=line)) is not None
            ]
        diagnostics: list[Diagnostic] = []
        for value in values:
            item: JsonObject = self._mapping(value=value)
            location: JsonObject = self._mapping(
                value=item.get("location") or item.get("range"),
            )
            start: JsonObject = self._mapping(value=location.get("start"))
            end: JsonObject = self._mapping(value=location.get("end"))
            code: str | None = self._string(
                value=item.get("name") or item.get("code"),
            )
            if code == "-2":
                code = None
            diagnostics.append(
                Diagnostic(
                    tool="pyrefly",
                    file=self._relative(
                        value=self._string(
                            value=item.get("path") or item.get("file"),
                        ),
                        fallback=file,
                    ),
                    line=self._integer(
                        value=item.get("line") or start.get("line"),
                    ),
                    column=self._integer(
                        value=item.get("column") or start.get("column"),
                    ),
                    end_line=self._integer(
                        value=item.get("stop_line") or end.get("line"),
                    ),
                    end_column=self._integer(
                        value=item.get("stop_column") or end.get("column"),
                    ),
                    severity=self._severity(
                        value=self._string(value=item.get("severity")),
                    ),
                    code=code,
                    message=self._string(value=item.get("concise_description"))
                    or self._string(value=item.get("description"))
                    or self._string(value=item.get("message"))
                    or "",
                ),
            )
        return diagnostics

    def _typescript(self, *, file: Path, text: str) -> list[Diagnostic]:
        """Parse TypeScript plain diagnostics for one file.

        Args:
            file: Linted file used when a line lacks a path.
            text: Plain ``tsc --pretty false`` output.

        Returns:
            Normalized diagnostics for lines matching
            :data:`Constants.tsc_pattern`.

        """
        diagnostics: list[Diagnostic] = []
        for line_text in text.splitlines():
            match: Match[str] | None = Constants.tsc_pattern.match(
                string=line_text,
            )
            if match is not None:
                diagnostics.append(
                    Diagnostic(
                        tool="typescript",
                        file=self._relative(
                            value=match.group("file"),
                            fallback=file,
                        ),
                        line=int(match.group("line")),
                        column=int(match.group("column")),
                        end_line=None,
                        end_column=None,
                        severity=self._severity(value=match.group("severity")),
                        code=f"TS{match.group('code')}",
                        message=match.group("message"),
                    ),
                )
        return diagnostics

    def _html(self, *, file: Path, text: str) -> list[Diagnostic]:
        """Parse HTML linter plain diagnostics for one file.

        Args:
            file: Linted file used when a line lacks a path.
            text: Plain linter output.

        Returns:
            Normalized diagnostics for lines matching
            :data:`Constants.html_pattern`.

        """
        diagnostics: list[Diagnostic] = []
        for line_text in text.splitlines():
            match: Match[str] | None = Constants.html_pattern.match(
                string=line_text,
            )
            if match is not None:
                diagnostics.append(
                    Diagnostic(
                        tool="htmlint",
                        file=self._relative(
                            value=match.group("file"),
                            fallback=file,
                        ),
                        line=int(match.group("line")),
                        column=int(match.group("column")),
                        end_line=None,
                        end_column=None,
                        severity="error",
                        code=match.group("code"),
                        message=match.group("message"),
                    ),
                )
        return diagnostics

    def _parse(
        self,
        *,
        spec: ToolSpec,
        file: Path,
        output: str,
    ) -> list[Diagnostic]:
        """Dispatch one file process output to its parser.

        Args:
            spec: Tool specification selecting the parser.
            file: Linted file used as the diagnostic path fallback.
            output: Captured process output to parse.

        Returns:
            Normalized diagnostics extracted from the output.

        """
        handlers: dict[str, Callable[[], list[Diagnostic]]] = {
            "ruff": lambda: self._ruff(tool=spec.name, file=file, text=output),
            "basedpyright": lambda: self._basedpyright(file=file, text=output),
            "pyrefly": lambda: self._pyrefly(file=file, text=output),
            "eslint": lambda: self._eslint(file=file, text=output),
            "stylelint": lambda: self._stylelint(file=file, text=output),
            "html": lambda: self._html(file=file, text=output),
            "typescript": lambda: self._typescript(file=file, text=output),
        }
        return handlers[spec.parser]()

    def _execute(
        self,
        *,
        specs_by_file: dict[str, tuple[Path, list[ToolSpec]]],
        stabilize: Callable[[], None],
        progress: ProgressDisplay,
    ) -> dict[str, list[FileResult]]:
        """Submit and drain every file task through the worker pool.

        Args:
            specs_by_file: Relative file path mapped to its tool specs.
            stabilize: Callable running the stabilization stage between
                the non-Python and Python submission waves.
            progress: Display receiving per-file completions.

        Returns:
            Per-tool result buckets for every completed file task.

        """
        collected: dict[str, list[FileResult]] = {}
        futures: dict[Future[list[FileResult]], str] = {}
        pool: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=self._workers,
        )
        stopped: Event = Event()

        def heartbeat() -> None:
            """Keep embedded progress live while subprocesses are busy."""
            while not stopped.wait(timeout=1.0):
                progress.heartbeat()

        ticker: Thread = Thread(target=heartbeat, daemon=True)
        ticker.start()
        try:
            trace(step="all lints: submit non-python checks", depth=2)
            self._submit(
                pool=pool,
                specs_by_file=specs_by_file,
                futures=futures,
                python=False,
                progress=progress,
            )
            stabilize()
            trace(step="all lints: submit python checks", depth=2)
            self._submit(
                pool=pool,
                specs_by_file=specs_by_file,
                futures=futures,
                python=True,
                progress=progress,
            )
            for future in as_completed(fs=futures):
                name: str = futures[future]
                results: list[FileResult] = future.result()
                trace(
                    step=(
                        f"all lints: {name} — task done, "
                        f"{len(results)} file results"
                    ),
                    depth=3,
                )
                collected.setdefault(name, []).extend(results)
        except BaseException:
            self._terminate_processes()
            for pending in futures:
                _ = pending.cancel()
            pool.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            pool.shutdown(wait=True)
        finally:
            stopped.set()
            ticker.join()
        return collected

    def _terminate_processes(self) -> None:
        """Kill every in-flight linter process owned by the runner."""
        with self._processes_lock:
            running: tuple[Popen[str], ...] = tuple(self._processes)
        for process in running:
            if process.poll() is None:
                process.kill()

    def _stabilize_files(
        self,
        *,
        files: list[Path],
        progress: ProgressDisplay,
        enabled: bool,
        command_prefix: tuple[str, ...],
        unsafe_fixes: bool,
    ) -> None:
        """Stabilize discovered Python files before the lint passes.

        Args:
            files: Root-relative files discovered by the ``ruff`` spec.
            progress: Display receiving the ``stabilize`` progress row.
            enabled: Whether the stabilization stage was requested.
            command_prefix: Executable prefix used to invoke Ruff.
            unsafe_fixes: Whether Ruff may apply unsafe fixes.

        """
        command: str = command_prefix[0]
        available: bool = (
            Path(command).expanduser().is_file()
            if Path(command).parent != Path()
            else which(cmd=command) is not None
        )
        if not enabled or not files or (not available):
            reason: str = (
                "disabled"
                if not enabled
                else "no python files"
                if not files
                else f"{command} not installed"
            )
            trace(step=f"all lints: stabilization skipped — {reason}", depth=2)
            return
        trace(
            step=(
                f"all lints: stabilize "
                f"{len(files)} python files (ruff format/fix cycles)"
            ),
            depth=2,
        )
        paths: list[Path] = [self._root / file for file in files]
        progress.update(tool="stabilize", files=files)

        def _finished(*, result: FileResult) -> None:
            """Record one stabilized file in the progress row.

            Args:
                result: Completed file processing metadata.

            """
            progress.finish(
                tool="stabilize",
                file=Path(result.file).relative_to(self._root).as_posix(),
                issues=result.status != "passed" or bool(result.diagnostics),
            )

        RuffStabilizer(
            paths=paths,
            callback=_finished,
            max_workers=self._workers,
            options=RuffStabilizerOptions(
                command_prefix=command_prefix,
                unsafe_fixes=unsafe_fixes,
                repair=self._repair,
                batch_repair=self._batch_repair,
            ),
        )
        trace(step="all lints: stabilization complete", depth=2)

    def _submit(
        self,
        *,
        pool: ThreadPoolExecutor,
        specs_by_file: dict[str, tuple[Path, list[ToolSpec]]],
        futures: dict[Future[list[FileResult]], str],
        python: bool,
        progress: ProgressDisplay,
    ) -> None:
        """Queue file tasks for one half of the workload.

        Non-Python tasks are submitted first, stabilization runs, and
        the Python tasks are submitted afterwards so linter passes see
        the Ruff-stabilized source text.

        Args:
            pool: Worker pool receiving the submitted tasks.
            specs_by_file: Discovered files mapped to their tool specs.
            futures: Future-to-tool-name registry extended in place.
            python: ``True`` to submit Python files, ``False`` for the
                remaining file kinds.
            progress: Sink updated immediately when each task completes.

        """
        batches: dict[str, tuple[ToolSpec, list[Path]]] = {}
        for key in sorted(specs_by_file):
            file, file_specs = specs_by_file[key]
            is_python: bool = any(
                spec.suffixes & Constants.python_suffixes
                for spec in file_specs
            )
            if is_python != python:
                continue
            for spec in file_specs:
                if spec.project or spec.batch:
                    batches.setdefault(spec.name, (spec, []))[1].append(file)
                else:
                    self._queue_check(
                        pool=pool,
                        futures=futures,
                        spec=spec,
                        files=[file],
                        progress=progress,
                    )
        for spec, files in batches.values():
            for chunk in self._chunks(spec=spec, files=files):
                self._queue_check(
                    pool=pool,
                    futures=futures,
                    spec=spec,
                    files=chunk,
                    progress=progress,
                )

    def _chunks(
        self,
        *,
        spec: ToolSpec,
        files: list[Path],
    ) -> list[list[Path]]:
        """Split a batched tool's files across parallel invocations.

        Args:
            spec: Tool specification carrying the chunk count.
            files: Discovered files, nonempty.

        Returns:
            Contiguous file groups, one per invocation; project specs
            always return a single group because their process checks
            the whole project regardless of the file list.

        """
        if spec.project:
            return [files]
        count: int = max(
            1,
            min(spec.batch_chunks or self._workers, len(files)),
        )
        size: int = (len(files) + count - 1) // count
        return [
            files[index : index + size] for index in range(0, len(files), size)
        ]

    def _queue_check(
        self,
        *,
        pool: ThreadPoolExecutor,
        futures: dict[Future[list[FileResult]], str],
        spec: ToolSpec,
        files: list[Path],
        progress: ProgressDisplay,
    ) -> None:
        """Queue a check and attach immediate per-file progress callbacks.

        Args:
            pool: Worker pool launching checks.
            futures: Result futures indexed by linter name.
            spec: Linter configuration.
            files: Nonempty list of requested paths.
            progress: Completion sink.

        """
        future: Future[list[FileResult]] = pool.submit(
            self._run_check,
            spec=spec,
            files=files,
            progress=progress,
        )
        futures[future] = spec.name
        future.add_done_callback(
            fn=partial(
                self._task_finished,
                progress=progress,
                name=spec.name,
                files=files,
            ),
        )

    def _run_check(
        self,
        *,
        spec: ToolSpec,
        files: list[Path],
        progress: ProgressDisplay | None = None,
    ) -> list[FileResult]:
        """Check type-checker targets together without losing per-file results.

        Batched specs receive the extra file paths as arguments while
        project specs already carry the project selector and take none;
        either way a single process produces diagnostics attributed back
        to their owning files, including files outside the requested set.
        Because one process covers every file, its progress is published
        at a steady pace while it runs rather than only when it exits;
        the final file is always held back for the real completion. When
        a previous report supplies an estimated duration for the tool the
        pace spreads the files across that span so the bar sweeps the
        whole run instead of finishing early.

        Args:
            spec: Linter configuration.
            files: Nonempty checked file list.
            progress: Shared sink receiving paced per-file completions.

        Returns:
            Per-file outcomes retaining every diagnostic and process
            failure; files that vanished between discovery and invocation
            produce no outcome.

        """
        surviving: list[Path] = [
            file for file in files if (self._root / file).exists()
        ]
        if not surviving:
            return []
        return self._run_batch(spec=spec, files=surviving, progress=progress)

    def _run_batch(
        self,
        *,
        spec: ToolSpec,
        files: list[Path],
        progress: ProgressDisplay | None = None,
    ) -> list[FileResult]:
        """Invoke one linter process for a batch of surviving files.

        Args:
            spec: Linter configuration.
            files: Nonempty list of files that still exist.
            progress: Shared sink receiving paced per-file completions.

        Returns:
            Per-file outcomes retaining every diagnostic and process
            failure.

        """
        batch: ToolSpec = (
            spec
            if spec.project
            else replace(
                spec,
                arguments=(
                    *spec.arguments,
                    *(str(object=file) for file in files[1:]),
                ),
            )
        )
        trace(
            step=f"{spec.name}: batch — {len(files)} files, one process",
            depth=3,
        )
        emitted: list[Path] = []
        done: Event = Event()
        pace_lock: Lock = Lock()
        interval: float = self._pace_interval(spec=spec, count=len(files))

        def _pace(*, display: ProgressDisplay) -> None:
            """Emit file completions at a steady pace while the batch runs.

            The batch subprocess produces results only when it exits, so a
            paced ticker keeps the progress bar honest. The last file is held
            back so the bar cannot reach 100 percent early; the real
            completion flushes whatever is left.

            Args:
                display: Progress sink receiving paced finishes.

            """
            for paced in files[: len(files) - 1]:
                if done.wait(timeout=interval):
                    return
                with pace_lock:
                    if done.is_set():
                        return
                    emitted.append(paced)
                    display.finish(tool=spec.name, file=paced.as_posix())

        display: ProgressDisplay | None = progress if len(files) > 1 else None
        if display is not None:
            Thread(
                target=_pace,
                kwargs={"display": display},
                daemon=True,
            ).start()
        try:
            result: FileResult = self.run_file(spec=batch, file=files[0])
        finally:
            done.set()
            if display is not None:
                with pace_lock:
                    for pending in files[len(emitted) :]:
                        display.finish(tool=spec.name, file=pending.as_posix())
        buckets: dict[str, list[Diagnostic]] = {
            file.as_posix(): [] for file in files
        }
        names: list[str] = [file.as_posix() for file in files]
        for diagnostic in result.diagnostics:
            key: str = diagnostic.file or files[0].as_posix()
            if key not in buckets:
                buckets[key] = []
                names.append(key)
            buckets[key].append(diagnostic)
        return [
            replace(
                result,
                file=name,
                diagnostics=buckets[name],
                duration_seconds=result.duration_seconds
                if name == names[0]
                else 0.0,
                status=result.status
                if not result.diagnostics
                else "failed"
                if buckets[name]
                else "passed",
            )
            for name in names
        ]

    def _pace_interval(self, *, spec: ToolSpec, count: int) -> float:
        """Return the per-file progress publish interval for one batch.

        Args:
            spec: Linter configuration for the batch.
            count: Files covered by the batch process.

        Returns:
            The estimated duration spread over the files when a previous
            report recorded one for the tool, otherwise the fixed pace.

        """
        estimate: float | None = self._pace_estimates.get(spec.name)
        if estimate is None or count <= 1:
            return Constants.batch_pace_seconds
        return max(Constants.batch_pace_floor_seconds, estimate / (count - 1))

    def _derive_results(
        self,
        *,
        specs: list[ToolSpec],
        files_by_tool: dict[str, list[Path]],
        collected: dict[str, list[FileResult]],
        unavailable: set[str],
        progress: ProgressDisplay,
    ) -> None:
        """Fill derived specs from their source tool's results.

        Args:
            specs: Tool specifications in report order.
            files_by_tool: Discovered files keyed by tool name.
            collected: Executed results extended in place.
            unavailable: Tool names without a runnable executable.
            progress: Display receiving the derived completions.

        """
        for spec in specs:
            if spec.derived_from is None or spec.name in unavailable:
                continue
            derived: list[FileResult] = self._derive(
                spec=spec,
                files=files_by_tool[spec.name],
                source=collected.get(spec.derived_from, []),
            )
            collected[spec.name] = derived
            trace(
                step=(
                    f"all lints: {spec.name} — derived {
                        len(derived)
                    } file results from "
                    f"{spec.derived_from}"
                ),
                depth=3,
            )
            for item in derived:
                progress.finish(
                    tool=spec.name,
                    file=item.file,
                    issues=bool(item.diagnostics),
                )


class ReportBuilder:
    """Build the aggregate JSON document."""

    @classmethod
    def build(
        cls,
        *,
        root: Path,
        started_at: datetime,
        duration_seconds: float,
        results: list[ToolResult],
        previous: PreviousReport | None = None,
    ) -> JsonObject:
        """Build the normalized report.

        Args:
            root: Audited project root.
            started_at: Moment the audit started.
            duration_seconds: Wall-clock runtime of the whole audit.
            results: Aggregate result of every tool.
            previous: Counts recovered from the earlier report, used to
                attach ``delta`` blocks to the summary and each tool.

        Returns:
            JSON-ready document with a ``summary`` block, a per-tool
            ``tools`` mapping and the flat ``diagnostics`` list; each
            tool's ``files`` array lists only files that produced
            diagnostics or did not pass.

        """
        diagnostics: list[Diagnostic] = [
            diagnostic
            for result in results
            for diagnostic in result.diagnostics
        ]
        failed: int = sum(result.status == "failed" for result in results)
        unavailable: int = sum(
            result.status == "unavailable" for result in results
        )
        affected: set[str] = {
            item.file
            for result in results
            for item in result.files
            if item.diagnostics or item.status != "passed"
        }
        summary: JsonObject = {
            "tools": len(results),
            "passed": sum(result.status == "passed" for result in results),
            "failed": failed,
            "unavailable": unavailable,
            "files": sum(result.total_files for result in results),
            "files_with_issues": len(affected),
            "errors": sum(value.severity == "error" for value in diagnostics),
            "warnings": sum(
                value.severity == "warning" for value in diagnostics
            ),
            "diagnostics": len(diagnostics),
        }
        if previous is not None:
            summary["delta"] = {
                "issues": len(diagnostics) - previous.total_issues,
                "files_with_issues": len(affected) - previous.total_files,
                "previous_generated_at": previous.generated_at,
            }
        report: JsonObject = {
            "schema_version": 2,
            "generated_at": datetime.now(tz=UTC).astimezone().isoformat(),
            "started_at": started_at.isoformat(),
            "duration_seconds": round(number=duration_seconds, ndigits=6),
            "root": str(object=root.resolve()),
            "ok": failed == 0 and unavailable == 0,
            "summary": summary,
            "tools": {},
            "diagnostics": [
                cls._diagnostic(diagnostic=value) for value in diagnostics
            ],
        }
        tools: JsonObject = {}
        for result in results:
            tool_affected: int = sum(
                bool(item.diagnostics) or item.status != "passed"
                for item in result.files
            )
            entry: JsonObject = {
                "name": result.name,
                "status": result.status,
                "duration_seconds": result.duration_seconds,
                "total_files": result.total_files,
                "completed_files": result.completed_files,
                "files_with_issues": tool_affected,
                "diagnostics": [
                    cls._diagnostic(diagnostic=value)
                    for value in result.diagnostics
                ],
                "files": [
                    cls._file(result=value)
                    for value in result.files
                    if value.diagnostics or value.status != "passed"
                ],
            }
            if previous is not None:
                entry["delta"] = {
                    "issues": len(result.diagnostics)
                    - previous.tool_issues.get(result.name, 0),
                    "files_with_issues": tool_affected
                    - previous.tool_files.get(result.name, 0),
                }
            tools[result.name] = entry
        report["tools"] = tools
        return report

    @classmethod
    def _file(cls, *, result: FileResult) -> JsonObject:
        """Serialize one file-process result.

        Args:
            result: Single-file result to serialize.

        Returns:
            JSON-ready mapping of the file task fields.

        """
        return {
            "file": result.file,
            "command": cast(typ="list[JsonValue]", val=result.command),
            "status": result.status,
            "exit_code": result.exit_code,
            "duration_seconds": result.duration_seconds,
            "diagnostics": [
                cls._diagnostic(diagnostic=value)
                for value in result.diagnostics
            ],
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    @staticmethod
    def _diagnostic(*, diagnostic: Diagnostic) -> JsonObject:
        """Serialize one diagnostic.

        Args:
            diagnostic: Normalized diagnostic to serialize.

        Returns:
            JSON-ready mapping of the diagnostic fields.

        """
        return {
            "tool": diagnostic.tool,
            "file": diagnostic.file,
            "line": diagnostic.line,
            "column": diagnostic.column,
            "end_line": diagnostic.end_line,
            "end_column": diagnostic.end_column,
            "severity": diagnostic.severity,
            "code": diagnostic.code,
            "message": diagnostic.message,
        }


class _StreamTee:
    """Mirror one text stream into an ANSI-free log file."""

    def __init__(self, *, stream: TextIO, log: TextIO) -> None:
        """Store the wrapped stream and its log copy.

        Args:
            stream: Original stream still receiving every write.
            log: Log file receiving the escape-stripped copy.

        """
        self._stream: TextIO = stream
        self._log: TextIO = log

    def write(self, text: str) -> int:
        """Write text to the stream and its escape-free log copy.

        Args:
            text: Text written to the stream.

        Returns:
            Characters written to the wrapped stream.

        """
        written: int = self._stream.write(text)
        with suppress(OSError):
            _ = self._log.write(
                Constants.log_escape_pattern.sub(repl="", string=text),
            )
        return written

    def writelines(self, lines: Iterable[str]) -> None:
        """Write each line to the stream and its log copy.

        Args:
            lines: Lines written in order.

        """
        line: str
        for line in lines:
            _ = self.write(text=line)

    def flush(self) -> None:
        """Flush both the wrapped stream and the log file."""
        self._stream.flush()
        with suppress(OSError):
            self._log.flush()

    def isatty(self) -> bool:
        """Report the wrapped stream's interactivity.

        Returns:
            Whether the wrapped stream is a terminal.

        """
        return self._stream.isatty()

    def __getattr__(self, name: str) -> StreamMember:
        """Delegate unimplemented stream members to the wrapped stream.

        Args:
            name: Attribute name requested on the tee.

        Returns:
            The wrapped stream's attribute.

        """
        return cast(typ="StreamMember", val=getattr(self._stream, name))


@contextmanager
def _captured_stdio(*, artifacts: Path) -> Generator[None]:
    """Mirror ``stdout`` and ``stderr`` into artifact log files.

    Args:
        artifacts: ``ARTIFACTS/`` directory receiving the logs.

    Yields:
        Nothing; the original streams are restored on exit.

    """
    artifacts.mkdir(parents=True, exist_ok=True)
    original_out: TextIO = sys.stdout
    original_err: TextIO = sys.stderr
    with (
        (artifacts / "stdout.log").open(mode="w", encoding="utf-8") as out_log,
        (artifacts / "stderr.log").open(mode="w", encoding="utf-8") as err_log,
        redirect_stdout(
            new_target=cast(
                typ="TextIO",
                val=_StreamTee(stream=original_out, log=out_log),
            ),
        ),
        redirect_stderr(
            new_target=cast(
                typ="TextIO",
                val=_StreamTee(stream=original_err, log=err_log),
            ),
        ),
    ):
        yield


class _CliActivity:
    """Maintain ``ARTIFACTS/@activity.json`` during a direct CLI run.

    The document follows the ``exactus/activity/v1`` schema shared with
    the orchestrated Exactus tooling: a heartbeat block refreshed every
    second by a daemon thread, a progress block fed by the audit's
    progress listener and a bounded list of recent events.
    """

    def __init__(self, *, path: Path) -> None:
        """Prepare the live activity document state.

        Args:
            path: ``@activity.json`` destination inside ``ARTIFACTS/``.

        """
        self._path: Path = path
        self._run_id: str = uuid4().hex
        self._pipeline_run_id: str | None = environ.get(
            "EXACTUS_PIPELINE_RUN_ID",
        )
        self._started: float = monotonic()
        self._started_at: str = datetime.now(tz=UTC).astimezone().isoformat()
        self._lock: Lock = Lock()
        self._stop: Event = Event()
        self._thread: Thread | None = None
        self._completed: int = 0
        self._total: int = 0
        self._step: str = "starting"
        self._current: str = ""
        self._status: str = "RUNNING"
        self._phase: str = "starting"
        self._exit_code: int | None = None
        self._events: deque[JsonValue] = deque(
            maxlen=Constants.activity_event_limit,
        )
        self._dropped: int = 0
        self._last_detail: str = ""

    def progress(self, *, completed: int, total: int, detail: str) -> None:
        """Fold one audit progress snapshot into the document.

        Args:
            completed: Completed file/tool checks.
            total: Discovered file/tool checks.
            detail: Label describing the latest progress event.

        """
        with self._lock:
            self._completed = completed
            self._total = total
            self._current = detail
            self._step = detail.partition(":")[0].strip() or "running"
            if detail != self._last_detail:
                self._last_detail = detail
                self._record(message=f"step: {detail}")

    def finish(self, *, status: str, exit_code: int) -> None:
        """Record the terminal status before the context exits.

        Args:
            status: Final ``DONE``/``FAIL`` run status.
            exit_code: Reported process exit code.

        """
        with self._lock:
            self._status = status
            self._phase = "finished"
            self._exit_code = exit_code

    def __enter__(self) -> Self:
        """Write the first beat and start the heartbeat thread.

        Returns:
            The live activity session.

        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._phase = "running"
        self._record(message="started: All lints")
        self._write()
        self._thread = Thread(target=self._beat_loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        _error: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Stop the heartbeat and write the terminal document.

        Args:
            exc_type: Exception type when the run failed mid-flight.
            _error: Exception instance unwinding the context.
            _traceback: Exception traceback, unused.

        """
        if exc_type is not None:
            interrupted: bool = issubclass(exc_type, KeyboardInterrupt)
            self._status = "INTERRUPT" if interrupted else "FAIL"
            self._phase = "interrupted" if interrupted else "crashed"
            if self._exit_code is None:
                self._exit_code = 130 if interrupted else 1
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=Constants.activity_interval_seconds * 2)
        with self._lock:
            elapsed: float = monotonic() - self._started
            self._record(
                message=(
                    f"finished: {self._status} (exit status "
                    f"{self._exit_code}) in {elapsed:.3f}s"
                ),
            )
            self._write(finished=True)

    def _record(self, *, message: str, level: str = "info") -> None:
        """Append one timestamped activity event.

        Args:
            message: Human-readable event text.
            level: Event severity label.

        """
        if len(self._events) == Constants.activity_event_limit:
            self._dropped += 1
        event: dict[str, JsonValue] = {
            "at": datetime.now(tz=UTC).astimezone().isoformat(),
            "level": level,
            "message": message,
        }
        self._events.append(event)

    def _beat_loop(self) -> None:
        """Refresh ``last_beat`` until the session stops."""
        while not self._stop.wait(timeout=Constants.activity_interval_seconds):
            with self._lock:
                self._write()

    def _write(self, *, finished: bool = False) -> None:
        """Atomically replace the activity document.

        Args:
            finished: Whether this write closes the run.

        """
        now: str = datetime.now(tz=UTC).astimezone().isoformat()
        fraction: float = self._completed / self._total if self._total else 0.0
        events: list[JsonValue] = list(self._events)
        payload: dict[str, JsonValue] = {
            "schema": Constants.activity_schema,
            "kind": "tool",
            "name": "all_lints",
            "run_id": self._run_id,
            "pipeline_run_id": self._pipeline_run_id,
            "status": self._status,
            "started_at": self._started_at,
            "updated_at": now,
            "finished_at": now if finished else None,
            "elapsed_seconds": round(
                number=monotonic() - self._started,
                ndigits=3,
            ),
            "heartbeat": {
                "pid": getpid(),
                "alive": not finished,
                "last_beat": now,
                "phase": self._phase,
                "interval_seconds": Constants.activity_interval_seconds,
            },
            "progress": {
                "completed": self._completed,
                "total": self._total,
                "fraction": round(number=fraction, ndigits=4),
                "percent": round(number=fraction * 100, ndigits=1),
                "step": self._step,
                "current": self._current,
            },
            "activity": {
                "limit": Constants.activity_event_limit,
                "count": len(events),
                "dropped": self._dropped,
                "events": events,
            },
            "items": [],
            "extra": {"exit_code": self._exit_code},
        }
        temporary: Path = self._path.with_name(
            name=f".{self._path.name}.{uuid4().hex}.tmp",
        )
        try:
            _ = temporary.write_text(
                data=dumps(obj=payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _ = temporary.replace(target=self._path)
        except OSError:
            with suppress(OSError):
                temporary.unlink()


def _write_report_readmes(*, report_dir: Path, artifacts: Path) -> None:
    """Write the README files describing the report tree.

    Args:
        report_dir: Report root directory.
        artifacts: ``ARTIFACTS`` directory inside the report root.

    """
    _ = (report_dir / "README.md").write_text(
        data=Constants.report_readme,
        encoding="utf-8",
    )
    _ = (artifacts / "README.md").write_text(
        data=Constants.artifacts_readme,
        encoding="utf-8",
    )


def _report_issue_files(*, report: JsonObject) -> list[str]:
    """Collect flagged project-relative paths in report order.

    Args:
        report: Aggregate all-lints report document.

    Returns:
        Deduplicated ``file`` entries from every tool's ``files``
        list, preserving first-seen report order.

    """
    members: list[str] = []
    seen: set[str] = set()
    tools: JsonValue | None = report.get("tools")
    if not isinstance(tools, dict):
        return members
    for entry in tools.values():
        if not isinstance(entry, dict):
            continue
        entries: JsonValue | None = entry.get("files")
        if not isinstance(entries, list):
            continue
        for item in entries:
            if not isinstance(item, dict):
                continue
            name: JsonValue | None = item.get("file")
            if isinstance(name, str) and name not in seen:
                seen.add(name)
                members.append(name)
    return members


def _write_files_bundle(
    *,
    report_dir: Path,
    root: Path,
    report: JsonObject,
) -> None:
    """Package every flagged file into the ``FILES`` directory.

    Writes ``files.zip`` with project-relative member names so that
    ``unzip -o ALL_LINTS_RESULTS/FILES/files.zip -d .`` from the
    project root restores the flagged sources in place, a ``TREE.txt``
    listing produced by ``exactus/packages/tree``, and a README.

    Args:
        report_dir: Report root receiving the ``FILES`` directory.
        root: Audited project root the member paths resolve from.
        report: Aggregate all-lints report document.

    """
    files_dir: Path = report_dir / Constants.files_directory
    files_dir.mkdir(parents=True, exist_ok=True)
    archive: Path = files_dir / Constants.files_archive
    with ZipFile(file=archive, mode="w", compression=ZIP_DEFLATED) as bundle:
        for member in _report_issue_files(report=report):
            source: Path = root / member
            if source.is_file():
                bundle.write(filename=source, arcname=member)
    _ = (files_dir / Constants.files_tree).write_text(
        data=render_tree(source=archive),
        encoding="utf-8",
    )
    _ = (files_dir / "README.md").write_text(
        data=Constants.files_readme,
        encoding="utf-8",
    )


class Arguments(Namespace):
    """Provide typed CLI storage.

    Attributes:
        root: Project root to audit.
        output: Report file destination; ``None`` resolves to
            ``result.json`` inside the configured report directory.
        workers: Maximum simultaneous linter processes.
        unsafe_fixes: Whether Ruff applies ``--unsafe-fixes``.
        collect_files: Whether the ``FILES`` bundle is written.

    """

    root: Path
    output: Path | None
    workers: int
    unsafe_fixes: bool
    collect_files: bool


class Cli:
    """Provide the command-line interface."""

    @classmethod
    def main(cls) -> int:
        """Run the audit CLI.

        Returns:
            Zero when every tool passed, one when any tool failed or was
            unavailable, two when argparse aborts on invalid usage, or
            ``130`` when a termination signal interrupts the run.

        """
        previous: dict[Signals, SignalHandler] = cls._trap_signals()
        try:
            arguments: Arguments = cls.parser().parse_args(
                namespace=Arguments(),
            )
            if arguments.workers < 1:
                cls.parser().error(message="--workers must be at least 1")
            root: Path = arguments.root.resolve()
            started_at: datetime = datetime.now(tz=UTC)
            started: float = monotonic()
            specs: list[ToolSpec] = cls.specs()
            configuration: Configuration = Configuration(root=root)
            report_dir: Path = root / configuration.output_dir()
            artifacts: Path = report_dir / Constants.artifacts_directory
            output: Path = (
                report_dir / "result.json"
                if arguments.output is None
                else arguments.output
                if arguments.output.is_absolute()
                else root / arguments.output
            )
            previous_report: PreviousReport | None = load_previous(
                output=output,
            )
            runner: AuditRunner = AuditRunner(
                root=root,
                workers=arguments.workers,
                pace_estimates=previous_report.durations
                if previous_report is not None
                else {},
            )
            with (
                _captured_stdio(artifacts=artifacts),
                _CliActivity(
                    path=artifacts / Constants.activity_name,
                ) as activity,
                step_log(path=artifacts / "steps.txt"),
            ):
                trace(step="all lints: cli run")
                results: list[ToolResult] = runner.run_all(
                    specs=specs,
                    stabilize=True,
                    unsafe_fixes=arguments.unsafe_fixes,
                    listener=activity.progress,
                )
                report: JsonObject = ReportBuilder.build(
                    root=root,
                    started_at=started_at,
                    duration_seconds=monotonic() - started,
                    results=results,
                    previous=previous_report,
                )
                text: str = (
                    dumps(obj=report, indent=2, ensure_ascii=False) + "\n"
                )
                _ = output.write_text(data=text, encoding="utf-8")
                canonical: Path = report_dir / "result.json"
                if output != canonical:
                    _ = canonical.write_text(data=text, encoding="utf-8")
                _write_report_readmes(
                    report_dir=report_dir,
                    artifacts=artifacts,
                )
                files_dir: Path = report_dir / Constants.files_directory
                if arguments.collect_files or configuration.collect_files():
                    _write_files_bundle(
                        report_dir=report_dir,
                        root=root,
                        report=report,
                    )
                else:
                    with suppress(OSError):
                        rmtree(path=files_dir)
                trace(step="all lints: report written")
                _print(cls._summary(results=results, previous=previous_report))
                _print(f"{output}\n")
                activity.finish(
                    status="DONE" if report["ok"] is True else "FAIL",
                    exit_code=0 if report["ok"] is True else 1,
                )
        except KeyboardInterrupt:
            _print("\nInterrupted.", file=sys.stderr)
            return 130
        finally:
            cls._restore_signals(previous=previous)
        return 0 if report["ok"] is True else 1

    @staticmethod
    def parser() -> ArgumentParser:
        """Build the CLI parser.

        Returns:
            Parser with the optional root positional and the ``-o``/
            ``-j``/``--collect-files`` flags, defaulting to the project
            root report.

        """
        parser: ExactusArgumentParser = ExactusArgumentParser(
            description=_join(
                parts=(
                    "Run linters in batched parallel invocations with",
                    "progress.",
                ),
                separator=" ",
            ),
        )
        parser.add_argument(
            "root",
            nargs="?",
            type=Path,
            default=Constants.project_root,
        )
        parser.add_argument(
            "-o",
            "--output",
            type=Path,
            default=None,
            help=_join(
                parts=(
                    "Report destination; defaults to result.json inside",
                    "the configured output directory.",
                ),
                separator=" ",
            ),
        )
        parser.add_argument(
            "-j",
            "--workers",
            type=int,
            default=max(1, min(16, cpu_count() or 4)),
            help="Maximum simultaneous linter processes.",
        )
        parser.add_argument(
            "--unsafe-fixes",
            action="store_true",
            help="Allow Ruff's unsafe fixes during source stabilization.",
        )
        parser.add_argument(
            "--collect-files",
            action="store_true",
            help="Bundle the FILES archive of flagged source files.",
        )
        return parser

    @staticmethod
    def specs() -> list[ToolSpec]:
        """Return canonical single-file linter specifications.

        Returns:
            Specification for every supported tool in stable run order;
            the HTML linter executable prefers ``htmlhint`` when present
            and falls back to ``htmlint``.

        """
        html_executable: str = (
            "htmlhint" if which(cmd="htmlhint") is not None else "htmlint"
        )
        return [
            ToolSpec(
                name="ruff",
                executable="ruff",
                parser="ruff",
                suffixes=Constants.python_suffixes,
                arguments=(
                    "check",
                    "--select",
                    "ALL",
                    "--ignore",
                    Constants.ruff_conflict_ignores,
                    "--output-format",
                    "json",
                ),
                batch=True,
            ),
            ToolSpec(
                name="ruff_docs",
                executable="ruff",
                parser="ruff",
                suffixes=Constants.python_suffixes,
                arguments=(
                    "check",
                    "--select",
                    "D",
                    "--ignore",
                    Constants.ruff_conflict_ignores,
                    "--output-format",
                    "json",
                ),
                derived_from="ruff",
                derived_prefix="D",
                derived_exclude=("DOC",),
            ),
            ToolSpec(
                name="basedpyright",
                executable="basedpyright",
                parser="basedpyright",
                suffixes=Constants.python_suffixes,
                arguments=("--outputjson",),
                file_before_arguments=True,
                batch=True,
                batch_chunks=4,
            ),
            ToolSpec(
                name="pyrefly",
                executable="pyrefly",
                parser="pyrefly",
                suffixes=Constants.python_suffixes,
                arguments=(
                    "check",
                    "--output-format",
                    "json",
                    "--min-severity",
                    "info",
                ),
                batch=True,
                batch_chunks=1,
            ),
            ToolSpec(
                name="eslint",
                executable="eslint",
                parser="eslint",
                suffixes=Constants.javascript_suffixes
                | Constants.typescript_suffixes,
                arguments=("--format", "json", "--no-warn-ignored"),
                file_before_arguments=True,
                batch=True,
            ),
            ToolSpec(
                name="stylelint",
                executable="stylelint",
                parser="stylelint",
                suffixes=Constants.style_suffixes,
                arguments=("--formatter", "json"),
                file_before_arguments=True,
                batch=True,
            ),
            ToolSpec(
                name="htmlint",
                executable=html_executable,
                parser="html",
                suffixes=Constants.html_suffixes,
                arguments=(),
                file_before_arguments=True,
                batch=True,
            ),
            ToolSpec(
                name="typescript",
                executable="tsc",
                parser="typescript",
                suffixes=Constants.javascript_suffixes
                | Constants.typescript_suffixes,
                arguments=("--noEmit", "--pretty", "false"),
                project=True,
            ),
        ]

    @classmethod
    def _summary(
        cls,
        *,
        results: list[ToolResult],
        previous: PreviousReport | None = None,
    ) -> str:
        """Render the final compact tool summary.

        Args:
            results: Aggregate result of every tool.
            previous: Counts recovered from the earlier report, used to
                append ``±N`` deltas to issue columns and totals.

        Returns:
            Newline-terminated table listing status, file counts and
            issue counts per tool followed by unique-file totals by
            suffix family and the count of files with issues; ANSI
            colors decorate statuses and counts when standard output
            is a terminal and ``NO_COLOR`` is unset.

        """
        enabled: bool = sys.stdout.isatty() and "NO_COLOR" not in environ
        status_colors: dict[str, str] = {
            "passed": Constants.ansi_green,
            "failed": Constants.ansi_red,
            "unavailable": Constants.ansi_yellow,
        }
        rows: list[str] = [
            "",
            _paint(
                text="tool          status       files       issues",
                color=Constants.ansi_bold,
                enabled=enabled,
            ),
        ]
        for result in results:
            delta_text: str = ""
            if previous is not None:
                delta_text = cls._delta(
                    delta=len(result.diagnostics)
                    - previous.tool_issues.get(result.name, 0),
                    enabled=enabled,
                )
            rows.append(
                f"{result.name:<13} "
                + _paint(
                    text=f"{result.status:<12}",
                    color=status_colors.get(result.status, ""),
                    enabled=enabled,
                )
                + f" {result.completed_files:>5}/{result.total_files:<5} "
                + _paint(
                    text=f"{len(result.diagnostics):>6}",
                    color=Constants.ansi_red
                    if result.diagnostics
                    else Constants.ansi_dim,
                    enabled=enabled,
                )
                + delta_text,
            )
        seen: set[str] = set()
        issues: set[str] = set()
        for result in results:
            for item in result.files:
                seen.add(item.file)
                if item.diagnostics or item.status != "passed":
                    issues.add(item.file)
        categories: tuple[tuple[str, frozenset[str]], ...] = (
            ("python", Constants.python_suffixes),
            ("css", Constants.style_suffixes),
            (
                "js",
                Constants.javascript_suffixes | Constants.typescript_suffixes,
            ),
            ("html", Constants.html_suffixes),
        )
        totals: list[str] = [f"files: {len(seen)}"]
        totals.extend(
            (
                "".join(
                    (
                        f"{label}: ",
                        str(
                            object=sum(
                                (
                                    1
                                    for name in seen
                                    if Path(name).suffix.lower() in suffixes
                                ),
                            ),
                        ),
                    ),
                )
                for label, suffixes in categories
            ),
        )
        total_issues: int = sum(len(result.diagnostics) for result in results)
        totals.append(
            f"issues: {total_issues}"
            + (
                Cli._delta(
                    delta=total_issues - previous.total_issues,
                    enabled=enabled,
                )
                if previous is not None
                else ""
            ),
        )
        totals.append(
            f"with issues: {len(issues)}"
            + (
                Cli._delta(
                    delta=len(issues) - previous.total_files,
                    enabled=enabled,
                )
                if previous is not None
                else ""
            ),
        )
        width: int = max(20, get_terminal_size().columns)
        separator: str = "   "
        wrapped: list[str] = []
        current: str = ""
        for item in totals:
            candidate: str = (
                item if not current else current + separator + item
            )
            visible: str = Constants.ansi_pattern.sub(
                repl="",
                string=candidate,
            )
            if current and len(visible) > width:
                wrapped.append(current)
                current = item
            else:
                current = candidate
        if current:
            wrapped.append(current)
        rows.append("")
        rows.extend(
            _paint(text=line, color=Constants.ansi_bold, enabled=enabled)
            for line in wrapped
        )
        return "\n".join(rows) + "\n"

    @staticmethod
    def _delta(*, delta: int, enabled: bool) -> str:
        """Render one signed issue delta for the summary table.

        Args:
            delta: Current minus previous count; negative is an
                improvement.
            enabled: Whether ANSI coloring may decorate the text.

        Returns:
            Parenthesized ``±N`` text colored red when the count grew,
            green when it shrank and dim when unchanged.

        """
        return _paint(
            text=f" ({delta:+d})" if delta else " (±0)",
            color=Constants.ansi_red
            if delta > 0
            else Constants.ansi_green
            if delta < 0
            else Constants.ansi_dim,
            enabled=enabled,
        )

    @staticmethod
    def _trap_signals() -> dict[Signals, SignalHandler]:
        """Raise ``KeyboardInterrupt`` for termination signals.

        POSIX shells deliver ``SIGHUP``, ``SIGTERM`` and ``SIGQUIT`` as
        process termination instead of an exception, so they are trapped
        here and funnelled into the same graceful-exit path as
        ``SIGINT``. Signals absent on the platform are skipped.

        Returns:
            Previously installed handlers keyed by signal.

        """
        terminate: tuple[Signals, ...] = tuple(
            Signals.__members__[name]
            for name in ("SIGHUP", "SIGQUIT", "SIGTERM")
            if name in Signals.__members__
        )

        def _interrupt(_signum: int, _frame: FrameType | None) -> NoReturn:
            """Convert a termination signal into a keyboard interrupt.

            Args:
                _signum: Received signal number.
                _frame: Interrupted stack frame.

            Raises:
                KeyboardInterrupt: Always, to unwind the audit cleanly.

            """
            raise KeyboardInterrupt

        return {
            signum: signal(signalnum=signum, handler=_interrupt)
            for signum in terminate
        }

    @staticmethod
    def _restore_signals(*, previous: dict[Signals, SignalHandler]) -> None:
        """Restore the signal handlers replaced by ``_trap_signals``.

        Args:
            previous: Handlers returned by :meth:`_trap_signals`.

        """
        for signum, handler in previous.items():
            _ = signal(signalnum=signum, handler=handler)


def main() -> int:
    """Run the merged linter audit.

    Returns:
        Process exit code from :meth:`Cli.main`, or ``130`` when a
        signal interrupts the run before or after handler setup.

    """
    try:
        return Cli.main()
    except KeyboardInterrupt:
        _print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
