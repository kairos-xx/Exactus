# Copyright (c) 2026
"""Exercise the merged linter audit: parsers, excludes, specs and report."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from io import StringIO
from json import dumps, loads
from pathlib import Path
from runpy import run_module
from signal import SIG_DFL, Signals, getsignal
from sys import executable
from textwrap import dedent
from threading import Event
from time import monotonic, sleep
from typing import TYPE_CHECKING, Final, NoReturn, cast
from zipfile import ZipFile

import pytest

from exactus.packages import project_python
from exactus.packages.all_lints import (
    Arguments,
    AuditRunner,
    Cli,
    Configuration,
    Constants,
    Diagnostic,
    FileResult,
    ReportBuilder,
    RuffStabilizer,
    RuffStabilizerOptions,
    ToolResult,
    ToolSpec,
)
from exactus.packages.all_lints import core as core_module
from exactus.packages.all_lints.examples import run as example_module
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_true,
    fail,
    private,
    private_call,
    require_type,
    set_private,
)

if TYPE_CHECKING:
    from types import ModuleType

    from exactus.packages.all_lints.core import (
        FinishCallback,
        JsonObject,
        JsonValue,
        ProgressListener,
    )
sys: ModuleType = __import__("sys")
PARALLEL_LIMIT: Final[float] = 1.5
SLEEP_SECONDS: Final[float] = 0.3
MAX_CALLS: Final[int] = 4


def make_runner(tmp_path: Path) -> AuditRunner:
    """Build a runner rooted at ``tmp_path``.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Configured runner.

    """
    return AuditRunner(root=tmp_path, workers=16)


def ruff_diagnostic(*, runner: AuditRunner, payload: object) -> Diagnostic:
    """Parse one ruff diagnostic payload and return the first entry.

    Args:
        runner: Runner holding the private parser.
        payload: JSON-encodable ruff output.

    Returns:
        The single normalized diagnostic.

    """
    diagnostics: list[Diagnostic] = cast(
        typ="list[Diagnostic]",
        val=private_call(
            owner=runner,
            name="_ruff",
            tool="ruff",
            file=Path("src/app.py"),
            text=dumps(obj=payload),
        ),
    )
    expect_equal(actual=len(diagnostics), expected=1)
    return diagnostics[0]


def make_result(*, diagnostics: list[Diagnostic]) -> ToolResult:
    """Build a failed aggregate result for report assertions.

    Args:
        diagnostics: Diagnostics attached to the tool and its file.

    Returns:
        Failed single-file tool result.

    """
    return ToolResult(
        name="ruff",
        status="failed",
        duration_seconds=0.5,
        total_files=1,
        completed_files=1,
        diagnostics=diagnostics,
        files=[
            FileResult(
                file="app.py",
                command=["ruff", "check", "app.py"],
                status="failed",
                exit_code=1,
                duration_seconds=0.5,
                diagnostics=diagnostics,
                stdout="",
                stderr="",
            ),
        ],
    )


class FakeProcess:
    """Minimal ``Popen`` stand-in returning captured empty output."""

    def __init__(self) -> None:
        """Start the fake process with a successful return code."""
        self.returncode: int = 0

    @staticmethod
    def communicate() -> tuple[str, str]:
        """Return empty captured stdout and stderr.

        Returns:
            Empty stdout and stderr strings.

        """
        return "", ""

    def poll(self) -> int:
        """Report the stored return code.

        Returns:
            Process exit status.

        """
        return self.returncode

    def kill(self) -> None:
        """Pretend to kill an already finished process."""


def noop_run(_self: RuffStabilizer, *, args: tuple[str, ...]) -> None:
    """Pretend one Ruff invocation succeeded without touching the file.

    Args:
        _self: Stabilizer instance the patched method is bound to.
        args: Complete argument vector the subprocess was launched with.

    """
    expect_true(condition=bool(args), message="argument vector required")


def fail_run(_self: RuffStabilizer, *, args: tuple[str, ...]) -> NoReturn:
    """Fail the test; no Ruff subprocess may be spawned.

    Args:
        _self: Stabilizer instance the patched method is bound to.
        args: Complete argument vector the subprocess was launched with.

    """
    fail(message=f"unexpected stabilize subprocess call: {args}")


def fail_popen(*_args: object, **_kwargs: object) -> NoReturn:
    """Fail the test; no linter subprocess may be spawned.

    Args:
        _args: Positional arguments handed to ``Popen``.
        _kwargs: Keyword arguments handed to ``Popen``.

    """
    fail(message=f"unexpected Popen call: {_args} {_kwargs}")


class PendingProcess:
    """Fake process that reports running until ``kill`` is invoked."""

    def __init__(self) -> None:
        """Start the fake process in the running state."""
        self.killed: bool = False

    def poll(self) -> int | None:
        """Report no exit status until the process is killed.

        Returns:
            ``None`` while running, a signal status after ``kill``.

        """
        return -9 if self.killed else None

    def kill(self) -> None:
        """Record that the process received a kill request."""
        self.killed = True


def missing_which(cmd: str) -> None:
    """Report every executable as missing from ``PATH``.

    Args:
        cmd: Queried executable name.

    """
    expect_true(condition=bool(cmd), message="executable name required")


def present_which(cmd: str) -> str:
    """Report every executable as present on ``PATH``.

    Args:
        cmd: Queried executable name.

    Returns:
        A fake absolute path under ``/bin``.

    """
    return f"/bin/{cmd}"


def collect_into(*, results: list[FileResult]) -> FinishCallback:
    """Build a finish callback appending results into ``results``.

    Args:
        results: List receiving each completed file result.

    Returns:
        Callback recording every completed result in order.

    """

    def collect(*, result: FileResult) -> None:
        """Record one completed file result.

        Args:
            result: Completed file processing metadata.

        """
        results.append(result)

    return collect


def test_severity_normalization(tmp_path: Path) -> None:
    """Tool-specific severities map onto the normalized scale.

    Args:
        tmp_path: Per-test temporary directory.

    """
    runner: AuditRunner = make_runner(tmp_path=tmp_path)
    for value, expected in (
        ("fatal", "error"),
        ("error", "error"),
        ("warn", "warning"),
        ("warning", "warning"),
        ("info", "info"),
        ("hint", "note"),
        ("bogus", "note"),
    ):
        expect_equal(
            actual=private_call(
                owner=runner,
                name="_severity",
                value=value,
                default="note",
            ),
            expected=expected,
        )


def test_ruff_parser(tmp_path: Path) -> None:
    """Ruff JSON entries normalize with project-relative paths.

    Args:
        tmp_path: Per-test temporary directory.

    """
    runner: AuditRunner = make_runner(tmp_path=tmp_path)
    diagnostic: Diagnostic = ruff_diagnostic(
        runner=runner,
        payload=[
            {
                "filename": str(object=tmp_path / "src" / "app.py"),
                "location": {"row": 3, "column": 5},
                "end_location": {"row": 3, "column": 9},
                "code": "E501",
                "message": "line too long",
            },
        ],
    )
    expect_equal(actual=diagnostic.tool, expected="ruff")
    expect_equal(actual=diagnostic.file, expected="src/app.py")
    expect_equal(actual=diagnostic.line, expected=3)
    expect_equal(actual=diagnostic.column, expected=5)
    expect_equal(actual=diagnostic.end_column, expected=9)
    expect_equal(actual=diagnostic.severity, expected="error")
    expect_equal(actual=diagnostic.code, expected="E501")


def test_eslint_parser(tmp_path: Path) -> None:
    """ESLint numeric severities split into error and warning.

    Args:
        tmp_path: Per-test temporary directory.

    """
    runner: AuditRunner = make_runner(tmp_path=tmp_path)
    diagnostics: list[Diagnostic] = cast(
        typ="list[Diagnostic]",
        val=private_call(
            owner=runner,
            name="_eslint",
            file=Path("web/app.js"),
            text=dumps(
                obj=[
                    {
                        "filePath": str(object=tmp_path / "web" / "app.js"),
                        "messages": [
                            {
                                "line": 2,
                                "column": 7,
                                "severity": Constants.eslint_severity_error,
                                "ruleId": "no-undef",
                                "message": "undefined name",
                            },
                            {
                                "line": 4,
                                "column": 1,
                                "severity": 1,
                                "ruleId": "no-unused-vars",
                                "message": "unused",
                            },
                        ],
                    },
                ],
            ),
        ),
    )
    expect_equal(actual=len(diagnostics), expected=2)
    expect_equal(actual=diagnostics[0].severity, expected="error")
    expect_equal(actual=diagnostics[1].severity, expected="warning")
    expect_equal(actual=diagnostics[0].file, expected="web/app.js")
    expect_equal(actual=diagnostics[0].code, expected="no-undef")


def test_typescript_parser(tmp_path: Path) -> None:
    """TypeScript text diagnostics match the configured pattern.

    Args:
        tmp_path: Per-test temporary directory.

    """
    runner: AuditRunner = make_runner(tmp_path=tmp_path)
    text: str = (
        f"{tmp_path}/src/main.ts(12,4): error TS2322: type mismatch\n"
        "not a diagnostic line\n"
    )
    diagnostics: list[Diagnostic] = cast(
        typ="list[Diagnostic]",
        val=private_call(
            owner=runner,
            name="_typescript",
            file=Path("src/main.ts"),
            text=text,
        ),
    )
    expect_equal(actual=len(diagnostics), expected=1)
    expect_equal(actual=diagnostics[0].line, expected=12)
    expect_equal(actual=diagnostics[0].column, expected=4)
    expect_equal(actual=diagnostics[0].code, expected="TS2322")
    expect_equal(actual=diagnostics[0].severity, expected="error")


def test_excludes_default_without_pyproject(tmp_path: Path) -> None:
    """Missing pyproject falls back to the built-in exclude list.

    Args:
        tmp_path: Per-test temporary directory.

    """
    patterns: list[str] = Configuration(root=tmp_path).excludes(tool="ruff")
    expect_equal(actual=patterns, expected=list(Constants.excludes))


def test_excludes_merge_pyproject(tmp_path: Path) -> None:
    """Per-tool pyproject ignore lists merge without duplicates.

    Args:
        tmp_path: Per-test temporary directory.

    """
    (tmp_path / "pyproject.toml").write_text(
        data=(
            dedent(
                text=(
                    '    [tool.ruff]\n    extend-exclude = ["fixtures", "d'
                    'ist"]\n    [tool.basedpyright]\n    exclude = ["**/st'
                    'ubs"]\n    [tool.pyrefly]\n    project-excludes = ["*'
                    '*/gen/**"]\n    '
                ),
            )
        ),
        encoding="utf-8",
    )
    configuration: Configuration = Configuration(root=tmp_path)
    ruff: list[str] = configuration.excludes(tool="ruff")
    expect_in(member="**/node_modules", container=ruff)
    expect_in(member="fixtures", container=ruff)
    expect_equal(
        actual=len([item for item in ruff if item == "dist"]),
        expected=1,
    )
    expect_in(
        member="fixtures",
        container=configuration.excludes(tool="ruff_docs"),
    )
    expect_in(
        member="**/stubs",
        container=configuration.excludes(tool="basedpyright"),
    )
    expect_in(
        member="**/gen/**",
        container=configuration.excludes(tool="pyrefly"),
    )


def test_specs_build_single_file_commands() -> None:
    """Specs build complete per-file command lines."""
    specs: list[ToolSpec] = Cli.specs()
    by_name: dict[str, ToolSpec] = {spec.name: spec for spec in specs}
    file: Path = Path("src/app.py")
    ruff: list[str] = by_name["ruff"].command(file=file)
    expect_in(member="check", container=ruff)
    expect_in(member="--select", container=ruff)
    expect_in(member="ALL", container=ruff)
    expect_in(member="--output-format", container=ruff)
    expect_equal(actual=ruff[-1], expected="src/app.py")
    ruff_docs: list[str] = by_name["ruff_docs"].command(file=file)
    expect_in(member="D", container=ruff_docs)
    eslint: list[str] = by_name["eslint"].command(file=Path("web/app.ts"))
    expect_equal(actual=eslint[1], expected="web/app.ts")
    expect_in(member="--format", container=eslint)
    stylelint: list[str] = by_name["stylelint"].command(
        file=Path("styles/app.css"),
    )
    expect_equal(actual=stylelint[1], expected="styles/app.css")
    expect_in(member="--formatter", container=stylelint)
    basedpyright: list[str] = by_name["basedpyright"].command(file=file)
    expect_equal(
        actual=[arg for arg in basedpyright if arg.startswith("--")],
        expected=["--outputjson"],
    )
    pyrefly: list[str] = by_name["pyrefly"].command(file=file)
    expect_in(member="--min-severity", container=pyrefly)
    expect_in(member="info", container=pyrefly)
    typescript: ToolSpec = by_name["typescript"]
    expect_true(
        condition=".ts" in typescript.suffixes
        and ".js" in typescript.suffixes,
        message="typescript spec must accept .ts and .js",
    )
    expect_true(
        condition=typescript.project,
        message="typescript spec must check the whole project at once",
    )
    expect_true(
        condition="web/app.ts"
        not in typescript.command(file=Path("web/app.ts")),
        message="typescript spec must not pass file arguments to tsc",
    )


def test_report_builder_shape(tmp_path: Path) -> None:
    """Aggregated reports carry summary counts and diagnostics.

    Args:
        tmp_path: Per-test temporary directory.

    """
    result: ToolResult = make_result(
        diagnostics=[
            Diagnostic(
                tool="ruff",
                file="app.py",
                line=1,
                column=1,
                end_line=None,
                end_column=None,
                severity="error",
                code="E225",
                message="missing whitespace",
            ),
        ],
    )
    report: JsonObject = ReportBuilder.build(
        root=tmp_path,
        started_at=datetime.now(tz=UTC).astimezone(),
        duration_seconds=0.5,
        results=[result],
    )
    summary: object = report.get("summary")
    expect_true(condition=isinstance(summary, dict))
    tools: object = report.get("tools")
    expect_true(condition=isinstance(tools, dict))
    diagnostics: object = report.get("diagnostics")
    expect_true(condition=isinstance(diagnostics, list))
    expect_equal(actual=report.get("ok"), expected=False)


def test_report_files_list_only_files_with_issues(tmp_path: Path) -> None:
    """Per-tool ``files`` arrays keep only files that reported issues.

    Args:
        tmp_path: Per-test temporary directory.

    """
    diagnostic: Diagnostic = Diagnostic(
        tool="ruff",
        file="bad.py",
        line=1,
        column=1,
        end_line=None,
        end_column=None,
        severity="error",
        code="E501",
        message="line too long",
    )
    result: ToolResult = make_result(diagnostics=[diagnostic])
    with_clean: ToolResult = replace(
        result,
        total_files=2,
        completed_files=2,
        files=[
            replace(
                result.files[0],
                file="clean.py",
                status="passed",
                exit_code=0,
                diagnostics=[],
            ),
            replace(result.files[0], file="bad.py"),
        ],
    )
    report: JsonObject = ReportBuilder.build(
        root=tmp_path,
        started_at=datetime.now(tz=UTC).astimezone(),
        duration_seconds=0.5,
        results=[with_clean],
    )
    tools: JsonObject = cast(
        typ="JsonObject",
        val=require_type(value=report.get("tools"), kind=dict),
    )
    ruff: JsonObject = cast(
        typ="JsonObject",
        val=require_type(value=tools.get("ruff"), kind=dict),
    )
    files: list[JsonValue] = cast(
        typ="list[JsonValue]",
        val=require_type(value=ruff.get("files"), kind=list),
    )
    expect_equal(actual=len(files), expected=1)
    entry: JsonObject = cast(
        typ="JsonObject",
        val=require_type(value=files[0], kind=dict),
    )
    expect_equal(actual=entry.get("file"), expected="bad.py")


def test_parse_pyrefly_diagnostics(tmp_path: Path) -> None:
    """Pyrefly errors map name, description and end position fields.

    Pyrefly emits a numeric internal ``code`` (``-2`` when no rule
    code applies); the human-readable rule lives in ``name`` and the
    summary in ``concise_description``. Entries without ``name`` keep
    ``None`` instead of the meaningless numeric code.

    Args:
        tmp_path: Per-test temporary directory.

    """
    runner: AuditRunner = make_runner(tmp_path=tmp_path)
    diagnostics: list[Diagnostic] = cast(
        typ="list[Diagnostic]",
        val=private_call(
            owner=runner,
            name="_pyrefly",
            file=Path("pkg/app.py"),
            text=dumps(
                obj={
                    "errors": [
                        {
                            "line": 6,
                            "column": 1,
                            "stop_line": 6,
                            "stop_column": 33,
                            "path": "pkg/app.py",
                            "code": -2,
                            "name": "missing-import",
                            "description": "long text",
                            "concise_description": "Cannot find module `core`",
                            "severity": "error",
                        },
                        {
                            "line": 9,
                            "column": 5,
                            "path": "pkg/app.py",
                            "code": -2,
                            "severity": "warning",
                            "description": "plain failure",
                        },
                    ],
                },
            ),
        ),
    )
    expect_equal(actual=len(diagnostics), expected=2)
    first: Diagnostic = diagnostics[0]
    expect_equal(actual=first.code, expected="missing-import")
    expect_equal(actual=first.message, expected="Cannot find module `core`")
    expect_equal(actual=first.end_line, expected=6)
    expect_equal(actual=first.end_column, expected=33)
    second: Diagnostic = diagnostics[1]
    expect_none(value=second.code)
    expect_equal(actual=second.message, expected="plain failure")
    expect_equal(actual=second.severity, expected="warning")


def test_parse_dispatches_to_tool_parser(tmp_path: Path) -> None:
    """Spec parser names route output to the matching decoder.

    Args:
        tmp_path: Per-test temporary directory.

    """
    runner: AuditRunner = make_runner(tmp_path=tmp_path)
    spec: ToolSpec = ToolSpec(
        name="ruff",
        executable="ruff",
        parser="ruff",
        suffixes=Constants.python_suffixes,
        arguments=("check", "--output-format", "json"),
    )
    diagnostics: list[Diagnostic] = cast(
        typ="list[Diagnostic]",
        val=private_call(
            owner=runner,
            name="_parse",
            spec=spec,
            file=Path("app.py"),
            output=dumps(
                obj=[
                    {
                        "location": {"row": 1, "column": 2},
                        "code": "E501",
                        "message": "line too long",
                    },
                ],
            ),
        ),
    )
    expect_equal(actual=len(diagnostics), expected=1)
    expect_equal(actual=diagnostics[0].tool, expected="ruff")
    expect_equal(actual=diagnostics[0].file, expected="app.py")


def test_summary_table() -> None:
    """Summary tables list per-tool file counts and issue totals."""
    result: ToolResult = make_result(diagnostics=[])
    text: str = cast(
        typ="str",
        val=private_call(owner=Cli, name="_summary", results=[result]),
    )
    expect_in(member="ruff", container=text)
    expect_in(member="files", container=text)
    expect_in(member="issues", container=text)
    expect_in(member="1/1", container=text)


def test_summary_table_reports_unique_file_totals() -> None:
    """The footer dedupes files shared by tools and groups by suffix."""
    base: ToolResult = make_result(diagnostics=[])
    passed: FileResult = replace(
        base.files[0],
        status="passed",
        exit_code=0,
        diagnostics=[],
    )
    issue: FileResult = replace(base.files[0], file="bad.py")
    results: list[ToolResult] = [
        replace(base, files=[issue, replace(passed, file="ok.py")]),
        replace(base, name="pyrefly", files=[replace(passed, file="ok.py")]),
        replace(
            base,
            name="eslint",
            files=[
                replace(passed, file="app.js"),
                replace(passed, file="mod.ts"),
            ],
        ),
        replace(
            base,
            name="stylelint",
            files=[replace(passed, file="site.css")],
        ),
        replace(
            base,
            name="htmlint",
            files=[replace(passed, file="page.html")],
        ),
    ]
    text: str = cast(
        typ="str",
        val=private_call(owner=Cli, name="_summary", results=results),
    )
    expect_in(member="files: 6", container=text)
    expect_in(member="python: 2", container=text)
    expect_in(member="css: 1", container=text)
    expect_in(member="js: 2", container=text)
    expect_in(member="html: 1", container=text)
    expect_in(member="with issues: 1", container=text)


def test_run_all_parallel(tmp_path: Path) -> None:
    """File tasks execute concurrently preserving spec order.

    Args:
        tmp_path: Per-test temporary directory.

    """
    for index in range(3):
        (tmp_path / f"file{index}.py").write_text(data="x = 1\n")
    specs: list[ToolSpec] = [
        ToolSpec(
            name=f"tool{index}",
            executable=executable,
            parser="ruff",
            suffixes=frozenset({".py"}),
            arguments=("-c", f"import time; time.sleep({SLEEP_SECONDS})"),
        )
        for index in range(3)
    ]
    started: float = monotonic()
    results: list[ToolResult] = make_runner(tmp_path=tmp_path).run_all(
        specs=specs,
    )
    elapsed: float = monotonic() - started
    expect_true(
        condition=elapsed < PARALLEL_LIMIT,
        message=f"took {elapsed:.2f}s",
    )
    expect_equal(
        actual=[result.name for result in results],
        expected=["tool0", "tool1", "tool2"],
    )
    expect_equal(
        actual=[result.status for result in results],
        expected=["passed", "passed", "passed"],
    )
    expect_equal(
        actual=[result.completed_files for result in results],
        expected=[3, 3, 3],
    )


def test_run_all_tool_durations_reflect_process_spans(tmp_path: Path) -> None:
    """Per-tool duration is its own task span, not the stage span.

    Args:
        tmp_path: Per-test temporary directory.

    """
    (tmp_path / "file.py").write_text(data="x = 1\n")
    specs: list[ToolSpec] = [
        ToolSpec(
            name="quick",
            executable=executable,
            parser="ruff",
            suffixes=frozenset({".py"}),
            arguments=("-c", "print('[]')"),
        ),
        ToolSpec(
            name="slow",
            executable=executable,
            parser="ruff",
            suffixes=frozenset({".py"}),
            arguments=("-c", f"import time; time.sleep({SLEEP_SECONDS * 3})"),
        ),
    ]
    results: list[ToolResult] = make_runner(tmp_path=tmp_path).run_all(
        specs=specs,
        draw=False,
    )
    quick, slow = results
    expect_true(
        condition=quick.duration_seconds < SLEEP_SECONDS * 3,
        message=f"quick tool billed {quick.duration_seconds:.2f}s",
    )
    expect_true(
        condition=slow.duration_seconds >= SLEEP_SECONDS * 3,
        message=f"slow tool billed {slow.duration_seconds:.2f}s",
    )
    expect_true(
        condition=quick.duration_seconds < slow.duration_seconds,
        message="distinct tools reported a shared stage duration",
    )
    expect_true(
        condition=all(
            item.started_monotonic
            for result in results
            for item in result.files
        ),
        message="file tasks did not record a start timestamp",
    )


def test_run_all_forwards_progress_to_listener(tmp_path: Path) -> None:
    """Discovery and completion events reach an embedding listener.

    Args:
        tmp_path: Per-test temporary directory.

    """
    (tmp_path / "file.py").write_text(data="x = 1\n")
    snapshots: list[tuple[int, int, str]] = []

    def _listener(*, completed: int, total: int, detail: str) -> None:
        """Record one progress snapshot emitted by the runner.

        Args:
            completed: Files finished by every tool that claimed them.
            total: Files discovered across every tool so far.
            detail: Label describing the latest progress event.

        """
        snapshots.append((completed, total, detail))

    spec: ToolSpec = ToolSpec(
        name="tool",
        executable=executable,
        parser="ruff",
        suffixes=frozenset({".py"}),
        arguments=("-c", "print('[]')"),
    )
    results: list[ToolResult] = make_runner(tmp_path=tmp_path).run_all(
        specs=[spec],
        listener=_listener,
        draw=False,
    )
    expect_equal(actual=results[0].status, expected="passed")
    expect_true(
        condition=(0, 1, "tool scanning") in snapshots,
        message="discovery snapshot missing",
    )
    expect_true(
        condition=snapshots[-1][0] == 1 and snapshots[-1][1] == 1,
        message="final snapshot did not reach full completion",
    )
    expect_true(
        condition=any(
            detail.startswith("tool:") for _, _, detail in snapshots
        ),
        message="completion snapshot missing",
    )


def test_shared_discovery_preserves_each_tool_scope(tmp_path: Path) -> None:
    """One inventory traversal retains suffix and exclusion semantics.

    Args:
        tmp_path: Per-test temporary directory.

    """
    source: Path = tmp_path / "src"
    source.mkdir()
    _ = (source / "app.py").write_text(data="value = 1\n")
    _ = (source / "app.js").write_text(data="const value = 1;\n")
    ignored: Path = tmp_path / "node_modules"
    ignored.mkdir()
    _ = (ignored / "hidden.py").write_text(data="hidden = 1\n")
    specs: list[ToolSpec] = [
        ToolSpec(
            name="python",
            executable=executable,
            parser="ruff",
            suffixes=frozenset({".py"}),
            arguments=(),
        ),
        ToolSpec(
            name="javascript",
            executable=executable,
            parser="eslint",
            suffixes=frozenset({".js"}),
            arguments=(),
        ),
    ]
    runner: AuditRunner = make_runner(tmp_path=tmp_path)
    discovered: dict[str, list[Path]] = cast(
        typ="dict[str, list[Path]]",
        val=private_call(owner=runner, name="_discover_all", specs=specs),
    )
    expect_equal(actual=discovered["python"], expected=[Path("src/app.py")])
    expect_equal(
        actual=discovered["javascript"],
        expected=[Path("src/app.js")],
    )


def test_cli_defaults() -> None:
    """Defaults point at the packaged project root report."""
    arguments: Arguments = Cli.parser().parse_args(
        args=[],
        namespace=Arguments(),
    )
    expect_none(value=arguments.output)
    expect_equal(actual=arguments.root, expected=Constants.project_root)
    expect_false(condition=arguments.unsafe_fixes)
    expect_false(condition=arguments.collect_files)


def test_progress_counts_checks_not_fully_checked_files() -> None:
    """One completed check advances progress while another tool is pending."""
    snapshots: list[tuple[int, int]] = []

    def listener(*, completed: int, total: int, detail: str) -> None:
        """Capture live work counts.

        Args:
            completed: Completed checks.
            total: Discovered checks.
            detail: Activity description.

        """
        expect_true(condition=bool(detail))
        snapshots.append((completed, total))

    display: core_module.ProgressDisplay = core_module.ProgressDisplay(
        totals={"fast": 0, "slow": 0},
        listener=listener,
        draw=False,
    )
    display.update(tool="fast", files=[Path("file.py")])
    display.update(tool="slow", files=[Path("file.py")])
    display.finish(tool="fast", file="file.py")
    expect_equal(actual=snapshots[-1], expected=(1, 2))
    display.heartbeat()
    expect_equal(actual=snapshots[-1], expected=(1, 2))
    display.finish(tool="slow", file="file.py")
    expect_equal(actual=snapshots[-1], expected=(2, 2))


def test_typechecker_batches_keep_diagnostics(tmp_path: Path) -> None:
    """Launch a type checker once and retain findings on their owning file.

    Args:
        tmp_path: Per-test temporary directory.

    """
    for name in ("a.py", "b.py"):
        _ = (tmp_path / name).write_text(data="x = 1\n", encoding="utf-8")
    spec: ToolSpec = ToolSpec(
        name="basedpyright",
        executable=executable,
        parser="basedpyright",
        suffixes=frozenset({".py"}),
        arguments=(
            "-c",
            "import json; print(json.dumps({'generalDiagnostics': "
            "[{'file':'b.py','severity':'error','message':'bad type'}]}))",
        ),
        batch=True,
        batch_chunks=1,
    )
    results: list[ToolResult] = make_runner(tmp_path=tmp_path).run_all(
        specs=[spec],
        draw=False,
    )
    expect_equal(actual=len(results[0].files), expected=2)
    expect_equal(actual=len(results[0].diagnostics), expected=1)
    expect_equal(actual=results[0].diagnostics[0].file, expected="b.py")
    expect_equal(
        actual=results[0].files[0].command,
        expected=results[0].files[1].command,
    )


def test_batched_tool_paces_progress_during_the_run(tmp_path: Path) -> None:
    """A slow batch publishes finishes over time, not all at the end.

    The first two files pace at ``batch_pace_seconds`` while the
    process still runs; the last file is always flushed by the real
    completion, so the totals stay exact.

    Args:
        tmp_path: Per-test temporary directory.

    """
    for name in ("a.py", "b.py", "c.py"):
        _ = (tmp_path / name).write_text(data="x = 1\n", encoding="utf-8")
    spec: ToolSpec = ToolSpec(
        name="basedpyright",
        executable=executable,
        parser="basedpyright",
        suffixes=frozenset({".py"}),
        arguments=(
            "-c",
            "import json, time; time.sleep(0.6); "
            "print(json.dumps({'generalDiagnostics': []}))",
        ),
        batch=True,
        batch_chunks=1,
    )
    finishes: list[tuple[float, int]] = []

    def record(*, completed: int, total: int, detail: str) -> None:
        """Capture one progress snapshot's time and count.

        Args:
            completed: Completed checks.
            total: Discovered checks.
            detail: Activity description.

        """
        expect_true(condition=total >= completed and bool(detail))
        finishes.append((monotonic(), completed))

    results: list[ToolResult] = make_runner(tmp_path=tmp_path).run_all(
        specs=[spec],
        draw=False,
        listener=record,
    )
    # Heartbeats republish the current count; count the completion transitions.
    counts: list[int] = []
    for _, count in finishes:
        if not counts or counts[-1] != count:
            counts.append(count)
    expect_equal(actual=counts, expected=[0, 1, 2, 3])
    expect_true(
        condition=finishes[1][0] < finishes[-1][0],
        message="batch finishes must be spread over the run",
    )
    expect_equal(actual=results[0].status, expected="passed")


def test_batched_tool_paces_progress_against_the_estimated_duration(
    tmp_path: Path,
) -> None:
    """A pace estimate spreads finishes across the expected runtime.

    Without an estimate each file waits ``batch_pace_seconds``; with a
    shorter measured duration the same files finish pacing long before
    the real completion, so the bar reflects the batch's true span.

    Args:
        tmp_path: Per-test temporary directory.

    """
    for name in ("a.py", "b.py", "c.py", "d.py", "e.py"):
        _ = (tmp_path / name).write_text(data="x = 1\n", encoding="utf-8")
    sleep_seconds: Final = 0.4
    spec: ToolSpec = ToolSpec(
        name="basedpyright",
        executable=executable,
        parser="basedpyright",
        suffixes=frozenset({".py"}),
        arguments=(
            "-c",
            f"import json, time; time.sleep({sleep_seconds}); "
            "print(json.dumps({'generalDiagnostics': []}))",
        ),
        batch=True,
        batch_chunks=1,
    )
    finishes: list[tuple[float, int]] = []

    def record(*, completed: int, total: int, detail: str) -> None:
        """Capture one progress snapshot's time and count.

        Args:
            completed: Completed checks.
            total: Discovered checks.
            detail: Activity description.

        """
        expect_true(condition=total >= completed and bool(detail))
        finishes.append((monotonic(), completed))

    runner: AuditRunner = AuditRunner(
        root=tmp_path,
        workers=16,
        pace_estimates={"basedpyright": 0.2},
    )
    results: list[ToolResult] = runner.run_all(
        specs=[spec],
        draw=False,
        listener=record,
    )
    # Heartbeats republish the current count; count the completion transitions.
    beats: list[tuple[float, int]] = []
    for finish in finishes:
        if not beats or finish[1] != beats[-1][1]:
            beats.append(finish)
    counts: list[int] = [count for _, count in beats]
    expect_equal(actual=counts, expected=[0, 1, 2, 3, 4, 5])
    span: float = beats[-2][0] - beats[1][0]
    max_span: float = 0.4
    expect_true(
        condition=span < max_span,
        message="estimated pacing must emit all but the last file "
        "within the estimate, not at the fixed per-file pace",
    )
    expect_equal(actual=results[0].status, expected="passed")


def test_previous_durations_reads_the_last_report(tmp_path: Path) -> None:
    """Reuse stored tool durations; ignore missing or malformed reports.

    Args:
        tmp_path: Per-test temporary directory.

    """
    report: Path = tmp_path / "report.json"
    _ = report.write_text(
        data=dumps(
            obj={
                "tools": {
                    "basedpyright": {"duration_seconds": 9.44},
                    "ruff": {"duration_seconds": "slow"},
                    "tsc": "not-an-object",
                },
            },
        ),
        encoding="utf-8",
    )
    expect_equal(
        actual=core_module.previous_durations(output=report),
        expected={"basedpyright": 9.44},
    )
    expect_equal(
        actual=core_module.previous_durations(
            output=tmp_path / "missing.json",
        ),
        expected={},
    )
    _ = report.write_text(data="not json", encoding="utf-8")
    expect_equal(
        actual=core_module.previous_durations(output=report),
        expected={},
    )


def test_batched_warning_diagnostic_fails_its_file(tmp_path: Path) -> None:
    """A warn diagnostic fails the owning file even when the tool exits 0.

    Pyrefly 0.63 exits 0 on warnings while newer releases exit 1; the
    per-file verdict must come from the diagnostics, not the process
    exit code, so both binaries report the same outcome.

    Args:
        tmp_path: Per-test temporary directory.

    """
    for name in ("a.py", "b.py"):
        _ = (tmp_path / name).write_text(data="x = 1\n", encoding="utf-8")
    spec: ToolSpec = ToolSpec(
        name="pyrefly",
        executable=executable,
        parser="pyrefly",
        suffixes=frozenset({".py"}),
        arguments=(
            "-c",
            "import json; print(json.dumps({'errors': [{'line': 1, "
            "'column': 1, 'path': 'b.py', 'code': -2, 'severity': "
            "'warn', 'name': 'unnecessary-type-conversion', "
            "'description': 'needless'}]}))",
        ),
        batch=True,
        batch_chunks=1,
    )
    results: list[ToolResult] = make_runner(tmp_path=tmp_path).run_all(
        specs=[spec],
        draw=False,
    )
    statuses: dict[str, str] = {
        item.file: item.status for item in results[0].files
    }
    expect_equal(
        actual=statuses,
        expected={"a.py": "passed", "b.py": "failed"},
    )
    expect_equal(actual=results[0].diagnostics[0].severity, expected="warning")


def test_typescript_project_run_attributes_findings(tmp_path: Path) -> None:
    """The tsc project check runs once and attributes findings per file.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = (tmp_path / "jsconfig.json").write_text(data="{}\n", encoding="utf-8")
    for name in ("a.js", "b.js"):
        _ = (tmp_path / name).write_text(data="let x = 1;\n", encoding="utf-8")
    spec: ToolSpec = ToolSpec(
        name="typescript",
        executable=executable,
        parser="typescript",
        suffixes=frozenset({".js"}),
        arguments=(
            "-c",
            "import sys; "
            "print('b.js(1,5): error TS7006: implicit any'); "
            "sys.exit(1)",
        ),
        project=True,
    )
    results: list[ToolResult] = make_runner(tmp_path=tmp_path).run_all(
        specs=[spec],
        draw=False,
    )
    expect_equal(actual=results[0].status, expected="failed")
    expect_equal(actual=results[0].total_files, expected=2)
    expect_equal(actual=len(results[0].diagnostics), expected=1)
    expect_equal(actual=results[0].diagnostics[0].file, expected="b.js")
    statuses: dict[str, str] = {
        item.file: item.status for item in results[0].files
    }
    expect_equal(
        actual=statuses,
        expected={"a.js": "passed", "b.js": "failed"},
    )
    expect_in(member="--project", container=results[0].files[0].command)
    expect_true(
        condition=results[0].files[0].command[-1].endswith("jsconfig.json"),
        message="tsc must run against the discovered project config",
    )


def test_typescript_skips_without_project_config(tmp_path: Path) -> None:
    """The tsc project check covers no files without a project config.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = (tmp_path / "a.js").write_text(data="let x = 1;\n", encoding="utf-8")
    spec: ToolSpec = ToolSpec(
        name="typescript",
        executable=executable,
        parser="typescript",
        suffixes=frozenset({".js"}),
        arguments=("-c", "print('unreachable')"),
        project=True,
    )
    results: list[ToolResult] = make_runner(tmp_path=tmp_path).run_all(
        specs=[spec],
        draw=False,
    )
    expect_equal(actual=results[0].status, expected="passed")
    expect_equal(actual=results[0].total_files, expected=0)
    expect_equal(actual=results[0].diagnostics, expected=[])


def test_tool_spec_uses_command_prefix() -> None:
    """Bundled launchers may prefix a linter subcommand."""
    spec: ToolSpec = ToolSpec(
        name="ruff",
        executable="ruff",
        parser="ruff",
        suffixes=frozenset({".py"}),
        arguments=("check",),
        command_prefix=("/bundle/exactus", "ruff"),
    )
    expect_equal(
        actual=spec.command(file=Path("app.py")),
        expected=["/bundle/exactus", "ruff", "check", "app.py"],
    )


def test_missing_file_falls_back(tmp_path: Path) -> None:
    """Missing diagnostic paths fall back to the linted file.

    Args:
        tmp_path: Per-test temporary directory.

    """
    runner: AuditRunner = make_runner(tmp_path=tmp_path)
    expect_equal(
        actual=private_call(
            owner=runner,
            name="_relative",
            value=None,
            fallback=Path("pkg/app.py"),
        ),
        expected="pkg/app.py",
    )


def test_file_result_stabilizer_defaults() -> None:
    """Linter file results default the stabilization counters.

    The merged result type serves linter processes and Ruff
    stabilization alike; linter results leave the stabilizer fields at
    their defaults.
    """
    result: FileResult = FileResult(
        file="app.py",
        command=["ruff", "check", "app.py"],
        status="passed",
        exit_code=0,
        duration_seconds=0.1,
        diagnostics=[],
        stdout="",
        stderr="",
    )
    expect_equal(actual=result.format_calls, expected=0)
    expect_equal(actual=result.fix_calls, expected=0)
    expect_equal(actual=result.size_delta, expected=0)
    expect_equal(actual=result.total, expected=0)
    expect_equal(actual=result.current, expected=0)
    expect_none(value=result.start_datetime)
    expect_none(value=result.end_datetime)


def test_stabilizer_rejects_missing_files(tmp_path: Path) -> None:
    """Stabilization fails fast when a target file does not exist.

    Args:
        tmp_path: Per-test temporary directory.

    """
    with pytest.raises(
        expected_exception=FileNotFoundError,
        match="does not exist",
    ):
        RuffStabilizer(paths=[tmp_path / "missing.py"])


def test_stabilizer_reports_stable_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An already-stable file completes after one call per operation.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    target: Path = tmp_path / "app.py"
    target.write_text(data="x = 1\n", encoding="utf-8")
    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=noop_run)
    results: list[FileResult] = []
    RuffStabilizer(paths=[target], callback=collect_into(results=results))
    expect_equal(actual=len(results), expected=1)
    result: FileResult = results[0]
    expect_equal(actual=result.file, expected=target.as_posix())
    expect_equal(actual=result.status, expected="passed")
    expect_none(value=result.exit_code)
    expect_equal(actual=result.format_calls, expected=2)
    expect_equal(actual=result.fix_calls, expected=2)
    expect_equal(actual=result.size_delta, expected=0)
    expect_equal(actual=result.start_size, expected=result.end_size)
    expect_equal(actual=result.total, expected=1)
    expect_equal(actual=result.current, expected=1)
    expect_true(
        condition=result.start_datetime is not None,
        message="expected a stabilization start datetime",
    )
    expect_true(
        condition=result.end_datetime is not None,
        message="expected a stabilization end datetime",
    )


class RecordingRepair:
    """Repair that rewrites the file once, then leaves it alone."""

    def __init__(self) -> None:
        """Start with no recorded calls."""
        self.paths: list[Path] = []

    def __call__(self, *, path: Path) -> None:
        """Record the call and change the file on the first one.

        Args:
            path: Stabilized file handed to the repair.

        """
        self.paths.append(path)
        if len(self.paths) == 1:
            _ = path.write_text(data="x = 2\n", encoding="utf-8")


def test_stabilizer_reruns_ruff_after_a_repair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A repair that changes the file forces another complete Ruff cycle.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    target: Path = tmp_path / "app.py"
    _ = target.write_text(data="x = 1\n", encoding="utf-8")
    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=noop_run)
    repair: RecordingRepair = RecordingRepair()
    results: list[FileResult] = []
    RuffStabilizer(
        paths=[target],
        callback=collect_into(results=results),
        options=RuffStabilizerOptions(repair=repair),
    )
    expect_equal(actual=repair.paths, expected=[target, target])
    expect_equal(actual=results[0].format_calls, expected=3)
    expect_equal(actual=results[0].fix_calls, expected=3)


def test_runner_exposes_the_repair_installer(tmp_path: Path) -> None:
    """The audit runner stores the repair handed to ``use_repair``.

    Args:
        tmp_path: Per-test temporary directory.

    """
    runner: AuditRunner = make_runner(tmp_path=tmp_path)
    repair: RecordingRepair = RecordingRepair()
    runner.use_repair(repair=repair)
    expect_true(condition=private(owner=runner, name="_repair") is repair)


def test_stabilizer_tracks_batch_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batch counters advance once per file in submission order.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    paths: list[Path] = []
    for index in range(3):
        path: Path = tmp_path / f"file{index}.py"
        path.write_text(data="x = 1\n", encoding="utf-8")
        paths.append(path)
    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=noop_run)
    results: list[FileResult] = []
    RuffStabilizer(
        paths=paths,
        callback=collect_into(results=results),
        max_workers=1,
    )
    expect_equal(actual=len(results), expected=3)
    expect_equal(actual=[item.current for item in results], expected=[1, 2, 3])
    expect_equal(actual=[item.total for item in results], expected=[3, 3, 3])


def test_stabilizer_rechecks_after_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mutating Ruff call triggers one extra stabilization cycle.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    target: Path = tmp_path / "app.py"
    target.write_text(data="x = 1\n", encoding="utf-8")
    start_size: int = target.stat().st_size
    calls: list[tuple[str, ...]] = []

    def fake_run(_self: RuffStabilizer, *, args: tuple[str, ...]) -> None:
        """Append a comment on the first invocation only.

        Args:
            _self: Stabilizer instance the patched method is bound to.
            args: Complete argument vector.

        """
        calls.append(args)
        if len(calls) == 1:
            target.write_bytes(data=target.read_bytes() + b"# stabilized\n")

    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=fake_run)
    results: list[FileResult] = []
    RuffStabilizer(
        paths=[target],
        callback=collect_into(results=results),
        max_workers=1,
    )
    expect_equal(actual=len(results), expected=1)
    result: FileResult = results[0]
    expect_equal(actual=result.format_calls, expected=4)
    expect_equal(actual=result.fix_calls, expected=3)
    expect_equal(actual=result.start_size, expected=start_size)
    expect_equal(
        actual=result.end_size,
        expected=start_size + len(b"# stabilized\n"),
    )
    expect_equal(actual=result.size_delta, expected=len(b"# stabilized\n"))


def test_stabilizer_forwards_unsafe_fixes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsafe Ruff fixes are opt-in and limited to the fix command.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    target: Path = tmp_path / "app.py"
    target.write_text(data="x = 1\n", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def fake_run(_self: RuffStabilizer, *, args: tuple[str, ...]) -> None:
        """Record each Ruff invocation without touching the file.

        Args:
            _self: Stabilizer instance the patched method is bound to.
            args: Complete argument vector.

        """
        calls.append(args)

    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=fake_run)
    RuffStabilizer(
        paths=[target],
        options=RuffStabilizerOptions(unsafe_fixes=True),
        max_workers=1,
    )
    fix_calls: list[tuple[str, ...]] = [
        call for call in calls if "check" in call
    ]
    expect_true(condition=bool(fix_calls))
    expect_true(condition=all("--unsafe-fixes" in call for call in fix_calls))


def test_stabilizer_fails_when_never_stable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file that keeps changing raises after exhausting cycles.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    target: Path = tmp_path / "app.py"
    target.write_text(data="x = 1\n", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def fake_run(_self: RuffStabilizer, *, args: tuple[str, ...]) -> None:
        """Mutate the file on every other invocation.

        Args:
            _self: Stabilizer instance the patched method is bound to.
            args: Complete argument vector.

        """
        calls.append(args)
        if len(calls) % 2:
            target.write_bytes(data=target.read_bytes() + b"x")

    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=fake_run)
    with pytest.raises(expected_exception=RuntimeError, match="stabilize"):
        RuffStabilizer(paths=[target], max_iterations=2)


def test_run_all_stabilize_skips_without_ruff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing ruff executable skips the stabilization stage.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    (tmp_path / "app.py").write_text(data="x = 1\n", encoding="utf-8")
    monkeypatch.setattr(target=core_module, name="which", value=missing_which)
    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=fail_run)
    monkeypatch.setattr(target=core_module, name="Popen", value=fail_popen)
    results: list[ToolResult] = make_runner(tmp_path=tmp_path).run_all(
        specs=Cli.specs(),
        stabilize=True,
    )
    expect_true(
        condition=all(result.status == "unavailable" for result in results),
        message="expected every tool to report unavailable",
    )


def test_run_all_stabilize_without_ruff_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A spec list without ruff skips stabilization entirely.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    (tmp_path / "app.py").write_text(data="x = 1\n", encoding="utf-8")
    monkeypatch.setattr(target=core_module, name="which", value=present_which)
    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=fail_run)
    monkeypatch.setattr(target=core_module, name="Popen", value=fail_popen)
    expect_equal(
        actual=make_runner(tmp_path=tmp_path).run_all(
            specs=[],
            stabilize=True,
        ),
        expected=[],
    )


def test_run_all_stabilize_without_python_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty discovery set stabilizes no file and spawns nothing.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    specs: list[ToolSpec] = Cli.specs()
    monkeypatch.setattr(target=core_module, name="which", value=present_which)
    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=fail_run)
    monkeypatch.setattr(target=core_module, name="Popen", value=fail_popen)
    results: list[ToolResult] = make_runner(tmp_path=tmp_path).run_all(
        specs=specs,
        stabilize=True,
    )
    expect_true(
        condition=all(result.total_files == 0 for result in results),
        message="expected every tool to discover zero files",
    )


def test_run_all_stabilize_runs_ruff_on_discovered_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stabilization shares the lint display as one progress row.

    The ``stabilize`` row must be registered on the single
    :class:`ProgressDisplay` used by the lint phase so a file counts
    toward the global total only after stabilization and every linter
    pass over it have finished.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    target: Path = tmp_path / "app.py"
    target.write_text(data="x = 1\n", encoding="utf-8")
    specs: list[ToolSpec] = Cli.specs()
    calls: list[tuple[str, ...]] = []
    displays: list[dict[str, int]] = []
    real_display: type = core_module.ProgressDisplay

    def fake_run(_self: RuffStabilizer, *, args: tuple[str, ...]) -> None:
        """Record each stabilize invocation without touching the file.

        Args:
            _self: Stabilizer instance the patched method is bound to.
            args: Complete argument vector.

        """
        calls.append(args)

    def fake_popen(*, args: object, **_kwargs: object) -> FakeProcess:
        """Record each linter invocation and return a fake process.

        Args:
            args: Command vector passed as the ``args`` keyword.
            _kwargs: Remaining ``Popen`` keyword arguments.

        Returns:
            Fake finished process with empty output.

        """
        calls.append(tuple(cast(typ="list[str]", val=args)))
        return FakeProcess()

    def recording(
        *,
        totals: dict[str, int],
        listener: object = None,
        draw: bool = True,
    ) -> object:
        """Capture every constructed progress display's rows.

        Args:
            totals: Row names and initial counts handed to the display.
            listener: Optional snapshot sink accepted for compatibility.
            draw: Whether the display renders to the terminal.

        Returns:
            A real progress display after recording its rows.

        """
        displays.append(totals)
        return real_display(
            totals=totals,
            listener=cast(typ="ProgressListener | None", val=listener),
            draw=draw,
        )

    monkeypatch.setattr(target=core_module, name="which", value=present_which)
    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=fake_run)
    monkeypatch.setattr(target=core_module, name="Popen", value=fake_popen)
    monkeypatch.setattr(
        target=core_module,
        name="ProgressDisplay",
        value=recording,
    )
    results: list[ToolResult] = make_runner(tmp_path=tmp_path).run_all(
        specs=specs,
        stabilize=True,
    )
    expect_true(
        condition=all(result.status == "passed" for result in results),
        message="expected every tool to pass",
    )
    expect_equal(actual=len(displays), expected=1)
    expect_equal(actual=next(iter(displays[0])), expected="stabilize")
    expect_equal(actual=displays[0]["stabilize"], expected=0)
    expect_true(
        condition=any(
            "format" in args and Path(args[-1]) == target.resolve()
            for args in calls
        ),
        message="expected a ruff format invocation for app.py",
    )
    expect_true(
        condition=any(
            "check" in args
            and "--fix" in args
            and Path(args[-1]) == target.resolve()
            for args in calls
        ),
        message="expected a ruff check --fix invocation for app.py",
    )


def test_run_all_stabilize_lets_other_tools_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-Python tools run while the Ruff stabilization pass runs.

    The JavaScript lint task must already be executing when the first
    stabilization subprocess launches; if stabilization gated every
    submission the release flag would stay unset and the recorded
    observation would be ``False``.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    (tmp_path / "app.py").write_text(data="x = 1\n", encoding="utf-8")
    (tmp_path / "a.js").write_text(data="const x = 1\n", encoding="utf-8")
    specs: list[ToolSpec] = [
        ToolSpec(
            name="eslint",
            executable="eslintbin",
            parser="ruff",
            suffixes=frozenset({".js"}),
            arguments=("lint",),
        ),
        ToolSpec(
            name="ruff",
            executable="ruff",
            parser="ruff",
            suffixes=Constants.python_suffixes,
            arguments=("check",),
        ),
    ]
    released: Event = Event()
    observed: list[bool] = []

    def gated_run(_self: RuffStabilizer, *, args: tuple[str, ...]) -> None:
        """Record whether eslint already ran when stabilization ran.

        Args:
            _self: Stabilizer instance the patched method is bound to.
            args: Complete argument vector.

        """
        if "format" in args or "--fix" in args:
            observed.append(released.wait(timeout=10.0))

    def gated_popen(*, args: object, **_kwargs: object) -> FakeProcess:
        """Release the stabilization gate once eslint starts.

        Args:
            args: Command vector passed as the ``args`` keyword.
            _kwargs: Remaining ``Popen`` keyword arguments.

        Returns:
            Fake finished process with empty output.

        """
        if cast(typ="list[str]", val=args)[0] == "eslintbin":
            released.set()
        return FakeProcess()

    monkeypatch.setattr(target=core_module, name="which", value=present_which)
    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=gated_run)
    monkeypatch.setattr(target=core_module, name="Popen", value=gated_popen)
    results: list[ToolResult] = make_runner(tmp_path=tmp_path).run_all(
        specs=specs,
        stabilize=True,
    )
    expect_true(
        condition=bool(observed) and all(observed),
        message="expected eslint to start before stabilization finished",
    )
    expect_true(
        condition=all(result.status == "passed" for result in results),
        message="expected every tool to pass",
    )


def test_terminate_processes_kills_registered_children(tmp_path: Path) -> None:
    """Interrupt cleanup kills every in-flight linter child process.

    Args:
        tmp_path: Per-test temporary directory.

    """
    process: PendingProcess = PendingProcess()
    runner: AuditRunner = make_runner(tmp_path=tmp_path)
    set_private(owner=runner, name="_processes", value={process})
    private_call(owner=runner, name="_terminate_processes")
    expect_true(
        condition=process.killed,
        message="expected the running process to be killed",
    )


def test_main_keyboard_interrupt_returns_130(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """A ``KeyboardInterrupt`` during the run exits 130 cleanly.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.
        capfd: Pytest output capture fixture; ``_print`` resolves
            ``sys.stderr`` at call time and file-descriptor capture
            also covers any child-process output.

    """

    def interrupted(*_args: object, **_kwargs: object) -> NoReturn:
        """Raise ``KeyboardInterrupt`` as a delivered signal would.

        Args:
            _args: Positional arguments handed to ``run_all``.
            _kwargs: Keyword arguments handed to ``run_all``.

        Raises:
            KeyboardInterrupt: Always, simulating a delivered signal.

        """
        raise KeyboardInterrupt

    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["all_lints", str(object=tmp_path)],
    )
    monkeypatch.setattr(target=AuditRunner, name="run_all", value=interrupted)
    expect_equal(actual=Cli.main(), expected=130)
    expect_in(member="Interrupted.", container=capfd.readouterr().err)
    expect_equal(actual=getsignal(signalnum=Signals.SIGTERM), expected=SIG_DFL)


def test_main_writes_lint_report_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A direct CLI run emits the ``ALL_LINTS_RESULTS`` artifact tree.

    Args:
        tmp_path: Per-test temporary directory used as the audit root.
        monkeypatch: Pytest patching helper.

    """

    def empty_run_all(*_args: object, **kwargs: object) -> list[ToolResult]:
        """Report progress, then return an empty result set.

        Args:
            _args: Positional arguments handed to ``run_all``.
            kwargs: Keyword arguments handed to ``run_all``.

        Returns:
            Empty result list.

        """
        listener: ProgressListener = cast(
            typ="ProgressListener",
            val=kwargs["listener"],
        )
        listener(completed=1, total=1, detail="ruff: app.py")
        return []

    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["all_lints", str(object=tmp_path), "--collect-files"],
    )
    monkeypatch.setattr(
        target=AuditRunner,
        name="run_all",
        value=empty_run_all,
    )
    expect_equal(actual=Cli.main(), expected=0)
    report_dir: Path = tmp_path / "ALL_LINTS_RESULTS"
    artifacts: Path = report_dir / "ARTIFACTS"
    files_dir: Path = report_dir / "FILES"
    for path in (
        report_dir / "result.json",
        report_dir / "README.md",
        artifacts / "steps.txt",
        artifacts / "@activity.json",
        artifacts / "stdout.log",
        artifacts / "stderr.log",
        artifacts / "README.md",
        files_dir / "README.md",
        files_dir / "files.zip",
        files_dir / "TREE.txt",
    ):
        expect_true(
            condition=path.is_file(),
            message=f"expected generated file {path}",
        )
    activity: JsonObject = cast(
        typ="JsonObject",
        val=loads(
            s=(artifacts / "@activity.json").read_text(encoding="utf-8"),
        ),
    )
    expect_equal(actual=activity["schema"], expected="exactus/activity/v1")
    expect_equal(actual=activity["status"], expected="DONE")
    heartbeat: JsonObject = cast(typ="JsonObject", val=activity["heartbeat"])
    expect_true(
        condition=heartbeat["alive"] is False,
        message="expected the finished heartbeat to stop",
    )
    expect_equal(actual=heartbeat["phase"], expected="finished")
    expect_equal(actual=heartbeat["interval_seconds"], expected=1.0)
    extra: JsonObject = cast(typ="JsonObject", val=activity["extra"])
    expect_equal(actual=extra["exit_code"], expected=0)
    expect_in(
        member="all lints: cli run",
        container=(artifacts / "steps.txt").read_text(encoding="utf-8"),
    )
    expect_in(
        member="tool",
        container=(artifacts / "stdout.log").read_text(encoding="utf-8"),
    )
    report: JsonObject = cast(
        typ="JsonObject",
        val=loads(s=(report_dir / "result.json").read_text(encoding="utf-8")),
    )
    expect_true(
        condition=report["ok"] is True,
        message="expected an empty successful report",
    )


def test_embedded_run_writes_no_lint_report(tmp_path: Path) -> None:
    """Embedded ``AuditRunner`` use creates no ``ALL_LINTS_RESULTS``.

    Args:
        tmp_path: Per-test temporary directory used as the audit root.

    """
    runner: AuditRunner = make_runner(tmp_path=tmp_path)
    _ = runner.run_all(specs=[])
    expect_false(
        condition=(tmp_path / "ALL_LINTS_RESULTS").exists(),
        message="embedded runs must not create ALL_LINTS_RESULTS",
    )


def test_main_fail_report_records_fail_activity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing audit records ``FAIL`` activity and exits one.

    Args:
        tmp_path: Per-test temporary directory used as the audit root.
        monkeypatch: Pytest patching helper.

    """
    diagnostic: Diagnostic = Diagnostic(
        tool="ruff",
        file="bad.py",
        line=1,
        column=1,
        end_line=None,
        end_column=None,
        severity="error",
        code="E501",
        message="line too long",
    )
    result: ToolResult = make_result(diagnostics=[diagnostic])

    def failed_run_all(*_args: object, **_kwargs: object) -> list[ToolResult]:
        """Return one failing tool result.

        Args:
            _args: Positional arguments handed to ``run_all``.
            _kwargs: Keyword arguments handed to ``run_all``.

        Returns:
            A single failed tool result.

        """
        return [result]

    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["all_lints", str(object=tmp_path)],
    )
    monkeypatch.setattr(
        target=AuditRunner,
        name="run_all",
        value=failed_run_all,
    )
    expect_equal(actual=Cli.main(), expected=1)
    activity: JsonObject = cast(
        typ="JsonObject",
        val=loads(
            s=(
                tmp_path / "ALL_LINTS_RESULTS" / "ARTIFACTS" / "@activity.json"
            ).read_text(encoding="utf-8"),
        ),
    )
    expect_equal(actual=activity["status"], expected="FAIL")
    extra: JsonObject = cast(typ="JsonObject", val=activity["extra"])
    expect_equal(actual=extra["exit_code"], expected=1)


def test_main_custom_output_also_writes_canonical_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--output`` redirects the report but ``result.json`` still lands.

    Args:
        tmp_path: Per-test temporary directory used as the audit root.
        monkeypatch: Pytest patching helper.

    """

    def empty_run_all(*_args: object, **_kwargs: object) -> list[ToolResult]:
        """Return an empty result set.

        Args:
            _args: Positional arguments handed to ``run_all``.
            _kwargs: Keyword arguments handed to ``run_all``.

        Returns:
            Empty result list.

        """
        return []

    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["all_lints", str(object=tmp_path), "-o", "custom.json"],
    )
    monkeypatch.setattr(
        target=AuditRunner,
        name="run_all",
        value=empty_run_all,
    )
    expect_equal(actual=Cli.main(), expected=0)
    custom: Path = tmp_path / "custom.json"
    canonical: Path = tmp_path / "ALL_LINTS_RESULTS" / "result.json"
    expect_true(
        condition=custom.is_file() and canonical.is_file(),
        message="expected both the custom output and canonical result",
    )
    expect_equal(
        actual=custom.read_text(encoding="utf-8"),
        expected=canonical.read_text(encoding="utf-8"),
    )


def test_main_collect_files_writes_files_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--collect-files`` enables the ``FILES`` bundle.

    Args:
        tmp_path: Per-test temporary directory used as the audit root.
        monkeypatch: Pytest patching helper.

    """

    def empty_run_all(*_args: object, **_kwargs: object) -> list[ToolResult]:
        """Return an empty result set.

        Args:
            _args: Positional arguments handed to ``run_all``.
            _kwargs: Keyword arguments handed to ``run_all``.

        Returns:
            Empty result list.

        """
        return []

    monkeypatch.setattr(
        target=AuditRunner,
        name="run_all",
        value=empty_run_all,
    )
    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["all_lints", str(object=tmp_path)],
    )
    expect_equal(actual=Cli.main(), expected=0)
    report_dir: Path = tmp_path / "ALL_LINTS_RESULTS"
    expect_false(
        condition=(report_dir / "FILES").exists(),
        message="FILES stays off without --collect-files",
    )
    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["all_lints", str(object=tmp_path), "--collect-files"],
    )
    expect_equal(actual=Cli.main(), expected=0)
    expect_true(
        condition=(report_dir / "result.json").is_file(),
        message="expected the canonical result.json",
    )
    expect_true(
        condition=(report_dir / "FILES" / "files.zip").is_file(),
        message="--collect-files must write the FILES bundle",
    )
    expect_true(
        condition=(report_dir / "FILES" / "TREE.txt").is_file(),
        message="--collect-files must write the FILES tree listing",
    )
    expect_true(
        condition=(report_dir / "FILES" / "README.md").is_file(),
        message="--collect-files must write the FILES README",
    )


def test_main_files_bundle_archives_flagged_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``FILES/files.zip`` stores flagged files in report order.

    Args:
        tmp_path: Per-test temporary directory used as the audit root.
        monkeypatch: Pytest patching helper.

    """
    _ = (tmp_path / "b.py").write_text(data="b = 1\n", encoding="utf-8")
    package: Path = tmp_path / "pkg"
    package.mkdir()
    module: Path = package / "mod.py"
    _ = module.write_text(data="mod = 1\n", encoding="utf-8")
    diagnostic: Diagnostic = Diagnostic(
        tool="ruff",
        file="b.py",
        line=1,
        column=1,
        end_line=None,
        end_column=None,
        severity="error",
        code="E501",
        message="line too long",
    )

    def file_entry(*, name: str) -> FileResult:
        """Build one failed file result.

        Args:
            name: Project-relative file path.

        Returns:
            Failed file result carrying one diagnostic.

        """
        return FileResult(
            file=name,
            command=["ruff", "check", name],
            status="failed",
            exit_code=1,
            duration_seconds=0.1,
            diagnostics=[replace(diagnostic, file=name)],
            stdout="",
            stderr="",
        )

    def failed_run_all(*_args: object, **_kwargs: object) -> list[ToolResult]:
        """Return one failing tool result with two flagged files.

        Args:
            _args: Positional arguments handed to ``run_all``.
            _kwargs: Keyword arguments handed to ``run_all``.

        Returns:
            A single failed tool result.

        """
        return [
            ToolResult(
                name="ruff",
                status="failed",
                duration_seconds=0.5,
                total_files=2,
                completed_files=2,
                diagnostics=[diagnostic],
                files=[file_entry(name="b.py"), file_entry(name="pkg/mod.py")],
            ),
        ]

    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["all_lints", str(object=tmp_path), "--collect-files"],
    )
    monkeypatch.setattr(
        target=AuditRunner,
        name="run_all",
        value=failed_run_all,
    )
    expect_equal(actual=Cli.main(), expected=1)
    files_dir: Path = tmp_path / "ALL_LINTS_RESULTS" / "FILES"
    archive: Path = files_dir / "files.zip"
    restored: Path = tmp_path / "restored"
    with ZipFile(file=archive) as bundle:
        names: list[str] = bundle.namelist()
        bundle.extractall(path=restored)
    expect_equal(actual=names, expected=["b.py", "pkg/mod.py"])
    tree_text: str = (files_dir / "TREE.txt").read_text(encoding="utf-8")
    expect_in(member="b.py", container=tree_text)
    expect_in(member="mod.py", container=tree_text)
    expect_true(
        condition=(files_dir / "README.md").is_file(),
        message="expected the FILES README",
    )
    expect_equal(
        actual=(restored / "pkg" / "mod.py").read_text(encoding="utf-8"),
        expected="mod = 1\n",
    )


def test_pyproject_configures_report_dir_and_collect_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``tool.all_lint`` steers the report directory and FILES bundle.

    Args:
        tmp_path: Per-test temporary directory used as the audit root.
        monkeypatch: Pytest patching helper.

    """

    def empty_run_all(*_args: object, **_kwargs: object) -> list[ToolResult]:
        """Return an empty result set.

        Args:
            _args: Positional arguments handed to ``run_all``.
            _kwargs: Keyword arguments handed to ``run_all``.

        Returns:
            Empty result list.

        """
        return []

    _ = (tmp_path / "pyproject.toml").write_text(
        data=dedent(
            text=(
                '    [tool.all_lint]\n    output-dir = "CUSTOM_RESULTS"\n '
                "   collect-files = true\n    "
            ),
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["all_lints", str(object=tmp_path)],
    )
    monkeypatch.setattr(
        target=AuditRunner,
        name="run_all",
        value=empty_run_all,
    )
    expect_equal(actual=Cli.main(), expected=0)
    custom_dir: Path = tmp_path / "CUSTOM_RESULTS"
    expect_true(
        condition=(custom_dir / "result.json").is_file(),
        message="expected result.json under the configured output-dir",
    )
    expect_true(
        condition=(custom_dir / "FILES" / "files.zip").is_file(),
        message="collect-files = true must write the FILES bundle",
    )
    expect_false(
        condition=(tmp_path / "ALL_LINTS_RESULTS").exists(),
        message="configured output-dir replaces the default directory",
    )


def test_configuration_all_lints_defaults(tmp_path: Path) -> None:
    """Unset ``tool.all_lint`` falls back to the canonical defaults.

    Args:
        tmp_path: Per-test temporary directory used as the audit root.

    """
    configuration: Configuration = Configuration(root=tmp_path)
    expect_equal(
        actual=configuration.output_dir(),
        expected=Constants.report_directory,
    )
    expect_false(condition=configuration.collect_files())


def test_main_function_delegates_to_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The module-level ``main`` delegates to :meth:`Cli.main`.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=Cli, name="main", value=lambda: 7)
    expect_equal(actual=core_module.main(), expected=7)

    def interrupted() -> NoReturn:
        """Raise ``KeyboardInterrupt`` as a delivered signal would.

        Raises:
            KeyboardInterrupt: Always, simulating a delivered signal.

        """
        raise KeyboardInterrupt

    monkeypatch.setattr(target=Cli, name="main", value=interrupted)
    expect_equal(actual=core_module.main(), expected=130)


def test_stream_tee_mirrors_and_strips_escapes() -> None:
    """The tee keeps the stream raw and the log escape-free."""
    stream: StringIO = StringIO()
    log: StringIO = StringIO()
    tee: object = private_call(
        owner=core_module,
        name="_StreamTee",
        stream=stream,
        log=log,
    )
    _ = private_call(owner=tee, name="write", text="\x1b[31mred\x1b[0m\n")
    private_call(owner=tee, name="writelines", lines=["a\n", "\x1b[2Kb\n"])
    private_call(owner=tee, name="flush")
    expect_equal(
        actual=stream.getvalue(),
        expected="\x1b[31mred\x1b[0m\na\n\x1b[2Kb\n",
    )
    expect_equal(actual=log.getvalue(), expected="red\na\nb\n")
    expect_true(
        condition=private_call(owner=tee, name="isatty") is False,
        message="expected the StringIO stream to report non-tty",
    )
    expect_equal(
        actual=private(owner=tee, name="encoding"),
        expected=stream.encoding,
    )


def test_cli_activity_lifecycle_and_interrupt(tmp_path: Path) -> None:
    """The activity document records runs, interrupts and crashes.

    Args:
        tmp_path: Per-test temporary directory.

    """

    def document(*, name: str) -> JsonObject:
        """Read back one activity document.

        Args:
            name: Artifact directory name under ``tmp_path``.

        Returns:
            Parsed ``@activity.json`` payload.

        """
        return cast(
            typ="JsonObject",
            val=loads(
                s=(tmp_path / name / "@activity.json").read_text(
                    encoding="utf-8",
                ),
            ),
        )

    done: object = private_call(
        owner=core_module,
        name="_CliActivity",
        path=tmp_path / "done" / "@activity.json",
    )
    private_call(owner=done, name="__enter__")
    private_call(
        owner=done,
        name="progress",
        completed=1,
        total=2,
        detail="ruff: a.py",
    )
    private_call(
        owner=done,
        name="progress",
        completed=1,
        total=2,
        detail="ruff: a.py",
    )
    private_call(owner=done, name="finish", status="DONE", exit_code=0)
    private_call(
        owner=done,
        name="__exit__",
        exc_type=None,
        _error=None,
        _traceback=None,
    )
    finished: JsonObject = document(name="done")
    expect_equal(actual=finished["status"], expected="DONE")
    expect_true(
        condition=cast(typ="JsonObject", val=finished["heartbeat"])["alive"]
        is False,
        message="expected the finished heartbeat to stop",
    )
    for name, exc_type, status, phase in (
        ("interrupted", KeyboardInterrupt, "INTERRUPT", "interrupted"),
        ("crashed", RuntimeError, "FAIL", "crashed"),
    ):
        activity: object = private_call(
            owner=core_module,
            name="_CliActivity",
            path=tmp_path / name / "@activity.json",
        )
        private_call(owner=activity, name="__enter__")
        private_call(
            owner=activity,
            name="__exit__",
            exc_type=exc_type,
            _error=exc_type(),
            _traceback=None,
        )
        payload: JsonObject = document(name=name)
        expect_equal(actual=payload["status"], expected=status)
        heartbeat: JsonObject = cast(
            typ="JsonObject",
            val=payload["heartbeat"],
        )
        expect_equal(actual=heartbeat["phase"], expected=phase)
        expect_equal(actual=heartbeat["interval_seconds"], expected=1.0)


def test_cli_activity_beats_and_drops_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The heartbeat thread rewrites the document on its interval.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=Constants,
        name="activity_interval_seconds",
        value=0.01,
    )
    activity: object = private_call(
        owner=core_module,
        name="_CliActivity",
        path=tmp_path / "beat" / "@activity.json",
    )
    private_call(owner=activity, name="__enter__")
    for index in range(60):
        private_call(
            owner=activity,
            name="progress",
            completed=index,
            total=60,
            detail=f"ruff: file-{index}.py",
        )
    sleep(0.05)
    private_call(
        owner=activity,
        name="__exit__",
        exc_type=None,
        _error=None,
        _traceback=None,
    )
    payload: JsonObject = cast(
        typ="JsonObject",
        val=loads(
            s=(tmp_path / "beat" / "@activity.json").read_text(
                encoding="utf-8",
            ),
        ),
    )
    feed: JsonObject = cast(typ="JsonObject", val=payload["activity"])
    expect_true(
        condition=cast(typ="int", val=feed["dropped"]) > 0,
        message="expected bounded events to drop the oldest entries",
    )
    progress: JsonObject = cast(typ="JsonObject", val=payload["progress"])
    expect_equal(actual=progress["completed"], expected=59)


def test_cli_activity_tolerates_unwritable_path(tmp_path: Path) -> None:
    """A failing document write degrades the activity file silently.

    Args:
        tmp_path: Per-test temporary directory.

    """
    activity: object = private_call(
        owner=core_module,
        name="_CliActivity",
        path=tmp_path / "gone" / "@activity.json",
    )
    private_call(owner=activity, name="__enter__")
    set_private(
        owner=activity,
        name="_path",
        value=tmp_path / "missing" / "dir" / "@activity.json",
    )
    private_call(
        owner=activity,
        name="__exit__",
        exc_type=None,
        _error=None,
        _traceback=None,
    )


def test_progress_display_tracks_and_renders(
    capfd: pytest.CaptureFixture[str],
) -> None:
    """The display tracks per-tool and global progress and renders it.

    Args:
        capfd: Pytest output capture fixture.

    """
    snapshots: list[tuple[object, object, object]] = []

    def listener(*, completed: int, total: int, detail: str) -> None:
        """Collect one progress snapshot.

        Args:
            completed: Completed file/tool checks.
            total: Discovered file/tool checks.
            detail: Label describing the latest progress event.

        """
        snapshots.append((completed, total, detail))

    display: core_module.ProgressDisplay = core_module.ProgressDisplay(
        totals={"ruff": 0, "pyrefly": 0},
        listener=listener,
    )
    set_private(owner=display, name="_enabled", value=True)
    set_private(owner=display, name="_colored", value=True)
    display.update(tool="ruff", files=[Path("a.py")])
    display.update(tool="pyrefly", files=[Path("a.py"), Path("b.py")])
    display.finish(tool="ruff", file="a.py", issues=True)
    display.finish(tool="pyrefly", file="a.py")
    display.finish(tool="ruff", file="unknown.py")
    display.flag_issue(tool="pyrefly", file="a.py")
    display.flag_issue(tool="pyrefly", file="unknown.py")
    display.heartbeat()
    display.render()
    display.render()
    set_private(owner=display, name="_colored", value=False)
    display.render()
    out: str = capfd.readouterr().out
    expect_in(member="TOTAL", container=out)
    expect_true(
        condition=any(detail == "ruff scanning" for _, _, detail in snapshots),
        message="expected a scanning snapshot for ruff",
    )
    expect_true(
        condition=any(detail == "ruff: a.py" for _, _, detail in snapshots),
        message="expected a completion snapshot for ruff",
    )


def test_progress_display_disabled_is_silent(
    capfd: pytest.CaptureFixture[str],
) -> None:
    """A disabled display renders nothing and still publishes events.

    Args:
        capfd: Pytest output capture fixture.

    """
    snapshots: list[tuple[object, object, object]] = []

    def listener(*, completed: int, total: int, detail: str) -> None:
        """Collect one progress snapshot.

        Args:
            completed: Completed file/tool checks.
            total: Discovered file/tool checks.
            detail: Label describing the latest progress event.

        """
        snapshots.append((completed, total, detail))

    display: core_module.ProgressDisplay = core_module.ProgressDisplay(
        totals={"ruff": 0},
        listener=listener,
        draw=False,
    )
    display.heartbeat()
    display.render()
    expect_equal(actual=capfd.readouterr().out, expected="")
    expect_true(
        condition=any(
            detail == "Preparing checks" for _, _, detail in snapshots
        ),
        message="expected a preparing-checks snapshot",
    )


def test_main_module_switches_to_project_python(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The all-lints module switches interpreter before its CLI runs.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    calls: list[str] = []
    monkeypatch.setattr(
        target=project_python,
        name="switch_to_project_venv",
        value=lambda: calls.append("switch"),
    )
    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["all_lints", str(object=tmp_path), "--output", "report.json"],
    )
    with pytest.raises(expected_exception=SystemExit):
        run_module(mod_name="exactus.packages.all_lints", run_name="__main__")
    expect_equal(actual=calls, expected=["switch"])


def test_examples_module_switches_to_project_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The all-lints example uses the same automatic interpreter switch.

    Args:
        monkeypatch: Pytest patching helper.

    """
    calls: list[str] = []
    monkeypatch.setattr(
        target=project_python,
        name="switch_to_project_venv",
        value=lambda: calls.append("switch"),
    )
    monkeypatch.setattr(target=example_module, name="main", value=lambda: 0)
    with pytest.raises(expected_exception=SystemExit) as captured:
        run_module(
            mod_name="exactus.packages.all_lints.examples",
            run_name="__main__",
        )
    expect_equal(actual=captured.value.code, expected=0)
    expect_equal(actual=calls, expected=["switch"])


def test_final_compact_pass_uses_expected_ruff_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compact formatting occurs after ordinary stabilization.

    Args:
        tmp_path: Temporary directory.
        monkeypatch: Pytest patching helper.

    """
    target: Path = tmp_path / "compact.py"
    target.write_text(data="x = 1\n", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def record(_self: RuffStabilizer, *, args: tuple[str, ...]) -> None:
        """Record Ruff arguments.

        Args:
            _self: Stabilizer instance.
            args: Ruff invocation.

        """
        calls.append(args)

    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=record)
    RuffStabilizer(
        paths=[target],
        options=RuffStabilizerOptions(unsafe_fixes=True),
    )
    expect_equal(actual=len(calls), expected=4)
    expect_true(
        condition="format.skip-magic-trailing-comma = true" in calls[2],
    )
    expect_true(condition="format.docstring-code-format = true" in calls[2])
    expect_true(
        condition='format.docstring-code-line-length = "dynamic"' in calls[2],
    )
    expect_true(condition="--unsafe-fixes" in calls[3])
    expect_equal(actual=calls[3][1], expected="check")


def test_final_compact_pass_retries_after_final_fix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A final Ruff fix that changes content triggers another compact cycle.

    Args:
        tmp_path: Temporary directory.
        monkeypatch: Pytest patching helper.

    """
    target: Path = tmp_path / "compact.py"
    target.write_text(data="x = 1\n", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def mutate(_self: RuffStabilizer, *, args: tuple[str, ...]) -> None:
        """Change the source on the first final fix.

        Args:
            _self: Stabilizer instance.
            args: Ruff invocation.

        """
        calls.append(args)
        if len(calls) == MAX_CALLS:
            target.write_text(data="x = 2\n", encoding="utf-8")

    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=mutate)
    results: list[FileResult] = []
    RuffStabilizer(paths=[target], callback=collect_into(results=results))
    expect_equal(actual=len(calls), expected=6)
    expect_equal(actual=results[0].format_calls, expected=3)
    expect_equal(actual=results[0].fix_calls, expected=3)
