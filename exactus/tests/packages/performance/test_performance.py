# Copyright (c) 2026 João Lopes.
"""Tests for parsing, analysis, dashboard export, serving, and CLI behavior."""

from http.client import HTTPConnection, HTTPResponse
from json import loads
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import pytest

from exactus.packages.performance import (
    DashboardExporter,
    Performance,
    PerformanceAnalyzer,
    StepParser,
)
from exactus.packages.performance import session as session_module
from exactus.packages.performance.cli import PerformanceCli
from exactus.packages.performance.config import PerformanceConfig
from exactus.packages.performance.examples.run import main as example_main
from exactus.packages.performance.report import Constants, PerformanceReport
from exactus.tests.common.support import require

if TYPE_CHECKING:
    from exactus.packages.performance.model import (
        ActorStat,
        PerformanceRun,
        ResourceSummary,
        StepEvent,
    )
    from exactus.packages.performance.session import DashboardSession


def expect_equal[T](*, actual: T, expected: T) -> None:
    """Assert equality without a bare assert statement.

    Args:
        actual: Observed value.
        expected: Required value.

    """
    if actual != expected:
        pytest.fail(reason=f"expected {expected!r}, got {actual!r}")


def trace_text() -> str:
    """Return a deterministic trace covering stages, gaps, and repetition.

    Returns:
        Representative trace content.

    """
    return dedent(
        text=(
            "    2026-01-01T00:00:00.000+00:00 +    0.000s tool: start\n    20"
            "26-01-01T00:00:00.010+00:00 +    0.010s   collect\n    2026-01-01"
            "T00:00:00.020+00:00 +    0.020s     item\n    2026-01-01T00:00:00"
            ".030+00:00 +    0.030s     item\n    2026-01-01T00:00:00.040+00:0"
            "0 +    0.040s     item\n    2026-01-01T00:00:02.000+00:00 +    2."
            "000s   report\n    2026-01-01T00:00:02.500+00:00 +    2.500s tool"
            ": done\n    "
        ),
    )


def write_trace(*, root: Path, tool: str = "LINTS") -> Path:
    """Write one Exactus-shaped trace fixture.

    Args:
        root: Temporary project root.
        tool: Tool directory name.

    Returns:
        Written trace path.

    """
    path: Path = root / "EXACTUS_RESULTS" / tool / "ARTIFACTS" / "steps.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(data=trace_text(), encoding="utf-8")
    return path


def test_parser_discovers_and_parses(tmp_path: Path) -> None:
    """Discover nested traces and parse depth and elapsed time.

    Args:
        tmp_path: Pytest temporary directory.

    """
    path: Path = write_trace(root=tmp_path)
    discovered: tuple[Path, ...] = StepParser.discover(paths=(tmp_path, path))
    expect_equal(actual=discovered, expected=(path.resolve(),))
    expect_equal(actual=StepParser.tool_name(path=path), expected="lints")
    events: tuple[StepEvent, ...] = StepParser.parse_file(path=path)
    expect_equal(actual=len(events), expected=7)
    expect_equal(actual=events[1].depth, expected=1)
    expect_equal(actual=events[2].depth, expected=2)
    expect_equal(actual=events[-1].elapsed, expected=2.5)


def test_parser_ignores_malformed_lines(tmp_path: Path) -> None:
    """Ignore malformed input while retaining valid events.

    Args:
        tmp_path: Pytest temporary directory.

    """
    path: Path = tmp_path / "steps.txt"
    _ = path.write_text(
        data="bad\n2026-01-01T00:00:00Z + 0.100s valid\n",
        encoding="utf-8",
    )
    events: tuple[StepEvent, ...] = StepParser.parse_file(path=path)
    expect_equal(actual=len(events), expected=1)
    expect_equal(
        actual=StepParser.tool_name(path=path),
        expected=tmp_path.name,
    )


def test_analyzer_builds_stages_and_bottlenecks(tmp_path: Path) -> None:
    """Infer stages, stalls, repetition, rate, and duration.

    Args:
        tmp_path: Pytest temporary directory.

    """
    run: PerformanceRun = PerformanceAnalyzer.analyze_file(
        path=write_trace(root=tmp_path),
        repetition_threshold=3,
    )
    expect_equal(actual=run.duration, expected=2.5)
    expect_equal(actual=len(run.stages), expected=2)
    expect_equal(actual=run.stages[0].name, expected="collect")
    expect_equal(actual=run.largest_gap, expected=1.96)
    kinds: set[str] = {item.kind for item in run.bottlenecks}
    expect_equal(actual=kinds, expected={"gap", "repeat"})


def test_empty_analysis_is_safe(tmp_path: Path) -> None:
    """Analyze an empty trace without division or indexing failures.

    Args:
        tmp_path: Pytest temporary directory.

    """
    run: PerformanceRun = PerformanceAnalyzer.analyze_events(
        tool="empty",
        source=tmp_path / "steps.txt",
        events=(),
    )
    expect_equal(actual=run.duration, expected=0.0)
    expect_equal(actual=run.event_rate, expected=0.0)
    expect_equal(actual=run.largest_gap, expected=0.0)
    expect_equal(actual=run.stages, expected=())


def test_export_writes_assets_and_raw_lines(tmp_path: Path) -> None:
    """Export profiler assets and the requested tool-to-lines JSON mapping.

    Args:
        tmp_path: Pytest temporary directory.

    """
    trace: Path = write_trace(root=tmp_path)
    destination: Path = tmp_path / "dashboard"
    index: Path = Performance.export(paths=(trace,), destination=destination)
    expect_equal(actual=index.is_file(), expected=True)
    for name in (
        "index.html",
        "styles/style.css",
        "styles/tokens/primary.css",
        "styles/components/graph/style.css",
        "code.js",
        "steps.json",
        "data.js",
    ):
        expect_equal(actual=(destination / name).is_file(), expected=True)
    data: dict[str, list[str]] = cast(
        typ="dict[str, list[str]]",
        val=loads(s=(destination / "steps.json").read_text(encoding="utf-8")),
    )
    expect_equal(actual=list(data), expected=["lints"])
    expect_equal(actual=len(data["lints"]), expected=7)
    script: str = (destination / "data.js").read_text(encoding="utf-8")
    prefix: str = "window.__PERFORMANCE_STEPS__ = JSON.parse(`"
    expect_equal(actual=script.startswith(prefix), expected=True)
    expect_equal(actual=script.endswith("`);\n"), expected=True)
    cooked: str = (
        script.removeprefix(prefix)
        .removesuffix("`);\n")
        .replace("\\\\", "\x00")
        .replace("\\`", "`")
        .replace("\\$", "$")
        .replace("\x00", "\\")
    )
    expect_equal(
        actual=cast(typ="dict[str, list[str]]", val=loads(s=cooked)),
        expected=data,
    )


def test_exporter_accepts_preanalyzed_runs(tmp_path: Path) -> None:
    """Export an explicitly supplied immutable run collection.

    Args:
        tmp_path: Pytest temporary directory.

    """
    run: PerformanceRun = PerformanceAnalyzer.analyze_file(
        path=write_trace(root=tmp_path),
    )
    index: Path = DashboardExporter.export(
        runs=(run,),
        destination=tmp_path / "direct",
    )
    expect_equal(actual=index.name, expected="index.html")


def test_server_serves_exported_index(tmp_path: Path) -> None:
    """Serve the exported dashboard over an ephemeral loopback port.

    Args:
        tmp_path: Pytest temporary directory.

    """
    trace: Path = write_trace(root=tmp_path)
    session: DashboardSession = Performance.serve(
        paths=(trace,),
        destination=tmp_path / "web",
        open_browser_window=False,
    )
    try:
        connection: HTTPConnection = HTTPConnection(
            host="127.0.0.1",
            port=int(session.url.split(sep=":")[2].split(sep="/")[0]),
        )
        connection.request(method="GET", url="/index.html")
        response: HTTPResponse = connection.getresponse()
        body: bytes = response.read()
        expect_equal(actual=response.status, expected=200)
        expect_equal(actual=b"Performance Observatory" in body, expected=True)
        connection.close()
    finally:
        session.close()


def test_cli_summary_export_and_missing(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Exercise CLI summary, export, and missing-trace exit paths.

    Args:
        tmp_path: Pytest temporary directory.
        capfd: Captured file-descriptor output fixture.

    """
    trace: Path = write_trace(root=tmp_path)
    expect_equal(
        actual=PerformanceCli.run(arguments=(str(object=trace), "--summary")),
        expected=0,
    )
    _ = capfd.readouterr()
    output: Path = tmp_path / "cli-dashboard"
    expect_equal(
        actual=PerformanceCli.run(
            arguments=(
                str(object=trace),
                "--output",
                str(object=output),
                "--no-serve",
            ),
        ),
        expected=0,
    )
    expect_equal(actual=(output / "index.html").is_file(), expected=True)
    expect_equal(
        actual=PerformanceCli.run(
            arguments=(str(object=tmp_path / "missing"),),
        ),
        expected=2,
    )


def test_cli_serve_shutdown_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise interactive CLI serving and clean interrupt shutdown.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    trace: Path = write_trace(root=tmp_path)

    class FakeSession:
        """Record close calls for the CLI session branch."""

        url: str = "http://127.0.0.1:43210/index.html"

        def __init__(self) -> None:
            """Initialize call-state flags."""
            self.close_called: bool = False

        def close(self) -> None:
            """Record session close."""
            self.close_called = True

    fake: FakeSession = FakeSession()

    def fake_serve(
        *,
        directory: Path,
        open_browser_window: bool = True,
        executable: Path | None = None,
        server_timeout: float = 10.0,
    ) -> FakeSession:
        """Return the fake dashboard session.

        Args:
            directory: Ignored dashboard directory.
            open_browser_window: Ignored browser flag.
            executable: Ignored browser executable override.
            server_timeout: Ignored server readiness timeout.

        Returns:
            Shared fake session.

        """
        _ = (directory, open_browser_window, executable, server_timeout)
        return fake

    def interrupt_sleep(secs: float) -> None:
        """Interrupt the CLI wait loop.

        Args:
            secs: Ignored sleep duration.

        Raises:
            KeyboardInterrupt: Always, to emulate Ctrl+C.

        """
        _ = secs
        raise KeyboardInterrupt

    monkeypatch.setattr(
        target=(
            "exactus.packages.performance.session.DashboardLauncher.serve"
        ),
        name=staticmethod(fake_serve),
    )
    monkeypatch.setattr(
        target="exactus.packages.performance.api.sleep",
        name=interrupt_sleep,
    )
    expect_equal(
        actual=PerformanceCli.run(
            arguments=(str(object=trace), "--serve", "--no-browser"),
        ),
        expected=0,
    )
    expect_equal(actual=fake.close_called, expected=True)


def test_example_runs(capfd: pytest.CaptureFixture[str]) -> None:
    """Run the comprehensive example successfully.

    Args:
        capfd: Captured file-descriptor output fixture.

    """
    expect_equal(actual=example_main(), expected=0)
    _ = capfd.readouterr()


def test_dashboard_launcher_uses_package_lifecycles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delegate serving, browser launch, and cleanup to package modules.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    directory: Path = tmp_path / "dashboard"
    directory.mkdir()
    terminated: list[int] = []
    cleared: list[Path] = []

    class FakeBrowser:
        """Record browser launch and close operations."""

        def __init__(self) -> None:
            """Initialize lifecycle state."""
            self.url: str | None = None
            self.closed: bool = False

        def launch_chrome(
            self,
            url: str,
            *,
            executable: Path | None = None,
        ) -> None:
            """Record the requested dashboard URL.

            Args:
                url: Dashboard URL.
                executable: Optional browser executable.

            """
            _ = executable
            self.url = url

        def close(self) -> None:
            """Record lifecycle close."""
            self.closed = True

    browser: FakeBrowser = FakeBrowser()

    def fake_serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
        """Return a fixed owned server triple.

        Args:
            path: Ignored served directory.
            log: Ignored log path.

        Returns:
            Fake process id, origin, and reuse flag.

        """
        _ = (path, log)
        return 123, "http://127.0.0.1:4567/", False

    def fake_wait_ready(*, url: str, pid: int, timeout: float) -> bool:
        """Report the fake server as ready.

        Args:
            url: Ignored server URL.
            pid: Ignored process id.
            timeout: Ignored readiness timeout.

        Returns:
            Always true.

        """
        _ = (url, pid, timeout)
        return True

    def fake_clear_server_state(*, path: Path) -> None:
        """Record cleared server-state paths.

        Args:
            path: Cleared server-state directory.

        """
        cleared.append(path)

    def fake_terminate_tree(*, pid: int) -> None:
        """Record terminated process ids.

        Args:
            pid: Terminated process id.

        """
        terminated.append(pid)

    monkeypatch.setattr(
        target=session_module.local,
        name="serve",
        value=fake_serve,
    )
    monkeypatch.setattr(
        target=session_module.local,
        name="wait_ready",
        value=fake_wait_ready,
    )
    monkeypatch.setattr(
        target=session_module.local,
        name="clear_server_state",
        value=fake_clear_server_state,
    )
    monkeypatch.setattr(
        target=session_module,
        name="terminate_tree",
        value=fake_terminate_tree,
    )
    monkeypatch.setattr(
        target=session_module,
        name="BrowserLifecycle",
        value=lambda: browser,
    )
    session: DashboardSession = session_module.DashboardLauncher.serve(
        directory=directory,
    )
    expect_equal(
        actual=session.url,
        expected="http://127.0.0.1:4567/index.html",
    )
    expect_equal(actual=browser.url, expected=session.url)
    session.close()
    expect_equal(actual=browser.closed, expected=True)
    expect_equal(actual=terminated, expected=[123])
    expect_equal(actual=cleared, expected=[directory.resolve()])


def test_reused_dashboard_server_is_not_terminated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave an adopted package server running on close.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    directory: Path = tmp_path / "dashboard"
    directory.mkdir()
    terminated: list[int] = []

    def fake_serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
        """Return a fixed reused server triple.

        Args:
            path: Ignored served directory.
            log: Ignored log path.

        Returns:
            Fake process id, origin, and reuse flag.

        """
        _ = (path, log)
        return 321, "http://127.0.0.1:7654/", True

    def fake_wait_ready(*, url: str, pid: int, timeout: float) -> bool:
        """Report the fake server as ready.

        Args:
            url: Ignored server URL.
            pid: Ignored process id.
            timeout: Ignored readiness timeout.

        Returns:
            Always true.

        """
        _ = (url, pid, timeout)
        return True

    def fake_terminate_tree(*, pid: int) -> None:
        """Record terminated process ids.

        Args:
            pid: Terminated process id.

        """
        terminated.append(pid)

    monkeypatch.setattr(
        target=session_module.local,
        name="serve",
        value=fake_serve,
    )
    monkeypatch.setattr(
        target=session_module.local,
        name="wait_ready",
        value=fake_wait_ready,
    )
    monkeypatch.setattr(
        target=session_module,
        name="terminate_tree",
        value=fake_terminate_tree,
    )
    session: DashboardSession = session_module.DashboardLauncher.serve(
        directory=directory,
        open_browser_window=False,
    )
    session.close()
    expect_equal(actual=terminated, expected=[])


def test_config_reads_pyproject_and_cli_precedence(tmp_path: Path) -> None:
    """Resolve defaults, pyproject settings, and explicit overrides.

    Args:
        tmp_path: Pytest temporary directory.

    """
    _ = (tmp_path / "pyproject.toml").write_text(
        data=(
            dedent(
                text=(
                    '    [tool.performance]\n    sources = ["configured"]'
                    '\n    output = "configured-output"\n    serve = false'
                    "\n    open = false\n    gap-threshold = 1.5\n    repe"
                    "tition-threshold = 20\n    server-timeout = 4.0\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    configured: PerformanceConfig = PerformanceConfig.load(project=tmp_path)
    expect_equal(actual=configured.sources, expected=("configured",))
    expect_equal(actual=configured.serve, expected=False)
    expect_equal(actual=configured.open, expected=False)
    expect_equal(actual=configured.gap_threshold, expected=1.5)
    overridden: PerformanceConfig = PerformanceConfig.load(
        project=tmp_path,
        sources=("explicit",),
        serve=True,
        open_browser=True,
    )
    expect_equal(actual=overridden.sources, expected=("explicit",))
    expect_equal(actual=overridden.serve, expected=True)
    expect_equal(actual=overridden.open, expected=True)


def test_config_defaults_without_pyproject(tmp_path: Path) -> None:
    """Use canonical defaults when the project has no configuration.

    Args:
        tmp_path: Pytest temporary directory.

    """
    config: PerformanceConfig = PerformanceConfig.load(project=tmp_path)
    expect_equal(actual=config.sources, expected=(".",))
    expect_equal(actual=config.serve, expected=True)
    expect_equal(actual=config.open, expected=True)
    expect_equal(
        actual=config.output,
        expected=(tmp_path / "performance").resolve(),
    )


def test_config_rejects_invalid_table_values(tmp_path: Path) -> None:
    """Reject non-conforming ``tool.performance`` values.

    Args:
        tmp_path: Pytest temporary directory.

    """
    invalid: tuple[tuple[str, str], ...] = (
        ('sources = "x"', "sources"),
        ("serve = 1", "boolean"),
        ("open = 1", "boolean"),
        ("output = 5", "string"),
        ("chrome = 5", "optional"),
        ("gap-threshold = " + '"x"', "numeric"),
        ("repetition-threshold = " + '"x"', "integer"),
        ("server-timeout = " + '"x"', "numeric"),
    )
    for line, kind in invalid:
        _ = (tmp_path / "pyproject.toml").write_text(
            data=f"[tool.performance]\n{line}\n",
            encoding="utf-8",
        )
        with pytest.raises(expected_exception=ValueError, match=kind):
            PerformanceConfig.load(project=tmp_path)


def test_config_rejects_out_of_range_values(tmp_path: Path) -> None:
    """Reject resolved settings outside their valid ranges.

    Args:
        tmp_path: Pytest temporary directory.

    """
    for line in (
        "gap-threshold = -1.0",
        "repetition-threshold = 0",
        "server-timeout = 0.0",
    ):
        _ = (tmp_path / "pyproject.toml").write_text(
            data=f"[tool.performance]\n{line}\n",
            encoding="utf-8",
        )
        with pytest.raises(
            expected_exception=ValueError,
            match=r"threshold|timeout",
        ):
            PerformanceConfig.load(project=tmp_path)


def test_config_handles_non_table_tool_sections(tmp_path: Path) -> None:
    """Treat non-table ``tool`` or ``performance`` values as empty.

    Args:
        tmp_path: Pytest temporary directory.

    """
    _ = (tmp_path / "pyproject.toml").write_text(
        data='tool = "x"\n',
        encoding="utf-8",
    )
    config: PerformanceConfig = PerformanceConfig.load(project=tmp_path)
    expect_equal(actual=config.serve, expected=True)
    _ = (tmp_path / "pyproject.toml").write_text(
        data='tool.performance = "x"\n',
        encoding="utf-8",
    )
    config = PerformanceConfig.load(project=tmp_path)
    expect_equal(actual=config.serve, expected=True)


def test_config_root_and_paths_expansion(tmp_path: Path) -> None:
    """Resolve roots from files and expand absolute and glob sources.

    Args:
        tmp_path: Pytest temporary directory.

    """
    project: Path = tmp_path / "nested" / "project"
    traces: Path = project / "traces"
    traces.mkdir(parents=True)
    _ = (project / "pyproject.toml").write_text(
        data="[tool.performance]\n",
        encoding="utf-8",
    )
    marker: Path = traces / "a.steps.txt"
    _ = marker.write_text(data="x", encoding="utf-8")
    from_file: PerformanceConfig = PerformanceConfig.load(
        project=project / "pyproject.toml",
    )
    expect_equal(actual=from_file.project, expected=project.resolve())
    from_child: PerformanceConfig = PerformanceConfig.load(
        project=traces / "inner",
    )
    expect_equal(actual=from_child.project, expected=project.resolve())
    absolute: str = str(object=marker)
    expanded: PerformanceConfig = PerformanceConfig(
        project=project,
        sources=(absolute, "traces/*.steps.txt", "missing"),
        output=project / "out",
        serve=True,
        open=False,
        chrome=None,
        gap_threshold=0.25,
        repetition_threshold=10,
        server_timeout=10.0,
    )
    paths: tuple[Path, ...] = expanded.paths()
    expect_equal(
        actual=paths,
        expected=((project / "missing").resolve(), marker.resolve()),
    )


def test_launcher_fails_when_server_never_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminate an owned server that never reports readiness.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    directory: Path = tmp_path / "dashboard"
    directory.mkdir()
    terminated: list[int] = []
    cleared: list[Path] = []

    def fake_serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
        """Return an owned server triple.

        Args:
            path: Ignored served directory.
            log: Ignored log path.

        Returns:
            Fake process id, origin, and reuse flag.

        """
        _ = (path, log)
        return 77, "http://127.0.0.1:1/", False

    def fake_wait_ready(*, url: str, pid: int, timeout: float) -> bool:
        """Report the fake server as never ready.

        Args:
            url: Ignored server URL.
            pid: Ignored process id.
            timeout: Ignored readiness timeout.

        Returns:
            Always false.

        """
        _ = (url, pid, timeout)
        return False

    def fake_terminate_tree(*, pid: int) -> None:
        """Record terminated process ids.

        Args:
            pid: Terminated process id.

        """
        terminated.append(pid)

    def fake_clear_server_state(*, path: Path) -> None:
        """Record cleared server-state paths.

        Args:
            path: Cleared server-state directory.

        """
        cleared.append(path)

    monkeypatch.setattr(
        target=session_module.local,
        name="serve",
        value=fake_serve,
    )
    monkeypatch.setattr(
        target=session_module.local,
        name="wait_ready",
        value=fake_wait_ready,
    )
    monkeypatch.setattr(
        target=session_module,
        name="terminate_tree",
        value=fake_terminate_tree,
    )
    monkeypatch.setattr(
        target=session_module.local,
        name="clear_server_state",
        value=fake_clear_server_state,
    )
    with pytest.raises(expected_exception=RuntimeError, match="not ready"):
        session_module.DashboardLauncher.serve(directory=directory)
    expect_equal(actual=terminated, expected=[77])
    expect_equal(actual=cleared, expected=[directory.resolve()])


def test_launcher_keeps_reused_server_when_not_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave an adopted server running when readiness fails.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    directory: Path = tmp_path / "dashboard"
    directory.mkdir()
    terminated: list[int] = []

    def fake_serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
        """Return a reused server triple.

        Args:
            path: Ignored served directory.
            log: Ignored log path.

        Returns:
            Fake process id, origin, and reuse flag.

        """
        _ = (path, log)
        return 88, "http://127.0.0.1:1/", True

    def fake_wait_ready(*, url: str, pid: int, timeout: float) -> bool:
        """Report the fake server as never ready.

        Args:
            url: Ignored server URL.
            pid: Ignored process id.
            timeout: Ignored readiness timeout.

        Returns:
            Always false.

        """
        _ = (url, pid, timeout)
        return False

    monkeypatch.setattr(
        target=session_module.local,
        name="serve",
        value=fake_serve,
    )
    monkeypatch.setattr(
        target=session_module.local,
        name="wait_ready",
        value=fake_wait_ready,
    )

    def fake_terminate_tree(*, pid: int) -> None:
        """Record terminated process ids.

        Args:
            pid: Terminated process id.

        """
        terminated.append(pid)

    monkeypatch.setattr(
        target=session_module,
        name="terminate_tree",
        value=fake_terminate_tree,
    )
    with pytest.raises(expected_exception=RuntimeError, match="not ready"):
        session_module.DashboardLauncher.serve(directory=directory)
    expect_equal(actual=terminated, expected=[])


def test_launcher_cleans_up_when_browser_launch_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminate the owned server when Chrome launch raises.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    directory: Path = tmp_path / "dashboard"
    directory.mkdir()
    terminated: list[int] = []
    cleared: list[Path] = []

    class FailingBrowser:
        """Raise during launch to exercise the cleanup path."""

        @staticmethod
        def launch_chrome(url: str, *, executable: Path | None = None) -> None:
            """Fail the launch unconditionally.

            Args:
                url: Ignored dashboard URL.
                executable: Ignored browser executable.

            Raises:
                FileNotFoundError: Always, emulating a missing browser.

            """
            _ = (url, executable)
            msg: str = "browser missing"
            raise FileNotFoundError(msg)

    def fake_serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
        """Return an owned server triple.

        Args:
            path: Ignored served directory.
            log: Ignored log path.

        Returns:
            Fake process id, origin, and reuse flag.

        """
        _ = (path, log)
        return 99, "http://127.0.0.1:1/", False

    def fake_wait_ready(*, url: str, pid: int, timeout: float) -> bool:
        """Report the fake server as ready.

        Args:
            url: Ignored server URL.
            pid: Ignored process id.
            timeout: Ignored readiness timeout.

        Returns:
            Always true.

        """
        _ = (url, pid, timeout)
        return True

    monkeypatch.setattr(
        target=session_module.local,
        name="serve",
        value=fake_serve,
    )
    monkeypatch.setattr(
        target=session_module.local,
        name="wait_ready",
        value=fake_wait_ready,
    )

    def fake_terminate_tree(*, pid: int) -> None:
        """Record terminated process ids.

        Args:
            pid: Terminated process id.

        """
        terminated.append(pid)

    def fake_clear_server_state(*, path: Path) -> None:
        """Record cleared server-state paths.

        Args:
            path: Cleared server-state directory.

        """
        cleared.append(path)

    monkeypatch.setattr(
        target=session_module,
        name="terminate_tree",
        value=fake_terminate_tree,
    )
    monkeypatch.setattr(
        target=session_module.local,
        name="clear_server_state",
        value=fake_clear_server_state,
    )
    monkeypatch.setattr(
        target=session_module,
        name="BrowserLifecycle",
        value=FailingBrowser,
    )
    with pytest.raises(expected_exception=FileNotFoundError):
        session_module.DashboardLauncher.serve(directory=directory)
    expect_equal(actual=terminated, expected=[99])
    expect_equal(actual=cleared, expected=[directory.resolve()])


def test_parser_reads_trailers_and_embedded_durations() -> None:
    """Trailers, span pairs and ``in Xs`` phrases become typed fields."""
    stamp: str = "2026-01-01T00:00:00Z"
    events: tuple[StepEvent, ...] = StepParser.parse_lines(
        lines=(
            f"{stamp} +   1.000s exec: python — exit 0 in 4.006s",
            f"{stamp} +   1.100s   pool: /a/b.py — format 2 calls @thread=W_1",
            f"{stamp} +   2.000s stage: build @span=7",
            f"{stamp} +   3.500s stage: build — done @span=7 @dur=1.500s",
        ),
    )
    expect_equal(actual=events[0].measured, expected=4.006)
    expect_equal(actual=events[0].actor, expected="exec")
    expect_equal(actual=events[1].thread, expected="W_1")
    expect_equal(actual=events[1].depth, expected=1)
    expect_equal(
        actual=events[1].template,
        expected="pool: <path> — format # calls",
    )
    expect_equal(actual=events[2].phase, expected="begin")
    expect_equal(actual=events[2].measured, expected=1.5)
    expect_equal(actual=events[3].phase, expected="end")
    expect_equal(actual=events[3].message, expected="stage: build — done")


def test_analyzer_attributes_time_per_actor_template_and_thread(
    tmp_path: Path,
) -> None:
    """Inferred time is attributed per lane and aggregated usefully.

    Args:
        tmp_path: Pytest temporary directory.

    """
    stamp: str = "2026-01-01T00:00:00Z"
    path: Path = tmp_path / "steps.txt"
    _ = path.write_text(
        data="\n".join(
            (
                f"{stamp} +   0.000s tool: start",
                f"{stamp} +   0.100s lint: file 1.py @thread=W_1",
                f"{stamp} +   0.200s lint: file 2.py @thread=W_2",
                f"{stamp} +   2.100s lint: file 3.py @thread=W_1",
                f"{stamp} +   3.000s tool: done",
            ),
        )
        + "\n",
        encoding="utf-8",
    )
    run: PerformanceRun = PerformanceAnalyzer.analyze_file(
        path=path,
        gap_threshold=0.5,
    )
    expect_equal(actual=run.actors[0].name, expected="tool")
    expect_equal(actual=run.actors[0].inferred, expected=3.0)
    lint: ActorStat = next(item for item in run.actors if item.name == "lint")
    expect_equal(actual=lint.count, expected=3)
    expect_equal(actual=run.templates[0].template, expected="tool: start")
    expect_equal(actual=len(run.threads), expected=3)
    expect_equal(actual=run.slowest[0].duration, expected=3.0)
    expect_equal(actual=run.slowest[0].source, expected="inferred")
    expect_equal(actual=round(number=run.silent, ndigits=3), expected=2.8)


def test_samples_are_parsed_and_summarized(tmp_path: Path) -> None:
    """``~sample`` lines become resources and never count as events.

    Args:
        tmp_path: Pytest temporary directory.

    """
    stamp: str = "2026-01-01T00:00:00Z"
    path: Path = tmp_path / "steps.txt"
    _ = path.write_text(
        data="\n".join(
            (
                f"{stamp} +   0.000s tool: start",
                f"{stamp} +   1.000s ~sample cpu=50.0 rss=100.0 threads=4 "
                "procs=2 read=2.00 write=1.00 ioscope=proc",
                f"{stamp} +   2.000s ~sample cpu=150.0 rss=300.0 threads=8 "
                "procs=5 read=0.00 write=3.00 ioscope=proc",
                f"{stamp} +   2.000s tool: done",
            ),
        )
        + "\n",
        encoding="utf-8",
    )
    run: PerformanceRun = PerformanceAnalyzer.analyze_file(path=path)
    expect_equal(actual=len(run.events), expected=2)
    expect_equal(actual=len(run.samples), expected=2)
    summary: ResourceSummary = require(value=run.resources)
    expect_equal(actual=summary.mean_cpu, expected=100.0)
    expect_equal(actual=summary.peak_cpu, expected=150.0)
    expect_equal(actual=summary.peak_rss, expected=300.0)
    expect_equal(actual=summary.read, expected=2.0)
    expect_equal(actual=summary.write, expected=4.0)
    expect_equal(actual=summary.peak_procs, expected=5)


def test_report_is_machine_readable_and_written_without_a_server(
    tmp_path: Path,
) -> None:
    """The JSON report carries the schema and is exported with the site.

    Args:
        tmp_path: Pytest temporary directory.

    """
    stamp: str = "2026-01-01T00:00:00Z"
    path: Path = tmp_path / "steps.txt"
    _ = path.write_text(
        data=f"{stamp} +   0.000s tool: start\n"
        f"{stamp} +   2.000s tool: done\n",
        encoding="utf-8",
    )
    run: PerformanceRun = PerformanceAnalyzer.analyze_file(path=path)
    written: Path = PerformanceReport.write(
        runs=(run,),
        path=tmp_path / "out" / "report.json",
    )
    payload: dict[str, object] = loads(s=written.read_text(encoding="utf-8"))
    expect_equal(actual=payload["schema"], expected=Constants.schema)
    expect_equal(
        actual=len(cast(typ="list[object]", val=payload["tools"])),
        expected=1,
    )
    index: Path = DashboardExporter.export(
        runs=(run,),
        destination=tmp_path / "site",
    )
    expect_equal(
        actual=(index.parent / "report.json").is_file(),
        expected=True,
    )
    expect_equal(
        actual="download-report" in index.read_text(encoding="utf-8"),
        expected=True,
    )
