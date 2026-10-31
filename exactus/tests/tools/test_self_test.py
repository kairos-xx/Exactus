"""Test self-diagnostic boundaries without running the nested tool suite."""

from __future__ import annotations

from io import StringIO
from json import dumps, loads
from pathlib import Path
from subprocess import CompletedProcess, Popen, TimeoutExpired
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest

from exactus.tests.common.support import expect_equal, expect_in, expect_true
from exactus.tools.self_test import main as self_test

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


@pytest.mark.parametrize("zipped", [False, True])
def test_self_commands_preserve_interpreter_and_import_context(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    zipped: bool,
) -> None:
    """Source and zipapp probes reuse the correct interpreter and environment.

    Args:
        monkeypatch: Process environment and launch-context replacement.
        tmp_path: Synthetic launcher location.
        zipped: Whether the launcher is a zipapp.

    """
    monkeypatch.setattr(
        target=self_test,
        name="argv",
        value=[str(object=tmp_path / "exactus.pyz")],
    )
    monkeypatch.setattr(
        target=self_test,
        name="is_zipfile",
        value=MagicMock(return_value=zipped),
    )
    monkeypatch.setenv(name="EXACTUS_PROJECT_PYTHON", value="/test/python")
    monkeypatch.setenv(name="PYTHONPATH", value="/inherited")
    command: list[str] = self_test.self_command("--help")
    expect_equal(actual=command[0], expected="/test/python")
    expect_equal(actual=command[-1], expected="--help")
    environment: dict[str, str] | None = self_test.subprocess_env()
    if zipped:
        expect_equal(actual=environment, expected=None)
        expect_equal(
            actual=command[1],
            expected=str(object=tmp_path / "exactus.pyz"),
        )
    else:
        expect_equal(actual=command[1:3], expected=["-m", "exactus"])
        expect_true(
            condition=environment is not None
            and environment["PYTHONPATH"].endswith("/inherited"),
        )
    launcher: MagicMock = MagicMock(return_value=None)
    monkeypatch.setattr(
        target=self_test,
        name="bundle_launcher",
        value=launcher,
    )
    expect_equal(actual=self_test.bundle_command("node"), expected=None)
    expect_equal(actual=self_test.describe_bundle("node")[0], expected=False)
    expect_equal(actual=self_test.bundle_tools(), expected=None)
    launcher.return_value = tmp_path / "__main__.py"
    expect_equal(
        actual=self_test.bundle_command("node"),
        expected=[
            "/test/python",
            str(object=tmp_path / "__main__.py"),
            "node",
        ],
    )


def test_pipeline_environment_removes_only_run_scoped_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nested pipelines cannot reuse outer orchestration identities.

    Args:
        monkeypatch: Explicit synthetic process environment.

    """
    monkeypatch.setattr(
        target=self_test,
        name="subprocess_env",
        value=MagicMock(
            return_value={
                "EXACTUS_RUN_ID": "outer",
                "EXACTUS_PROJECT_PYTHON": "/python",
                "PATH": "/bin",
            },
        ),
    )
    environment: dict[str, str] = self_test.pipeline_env()
    expect_equal(actual="EXACTUS_RUN_ID" in environment, expected=False)
    expect_equal(
        actual=environment["EXACTUS_PROJECT_PYTHON"],
        expected="/python",
    )
    expect_equal(actual=environment["PATH"], expected="/bin")


@pytest.mark.parametrize(
    "outcome",
    ["ok", "stderr", "stdout", "empty", "timeout", "missing"],
)
def test_describe_command_reports_process_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    """Distinguish success, nonzero exit, timeout and executable failures.

    Args:
        monkeypatch: Subprocess boundary replacement.
        outcome: Simulated child outcome.

    """
    execute: MagicMock = MagicMock(
        return_value=CompletedProcess(
            args=["tool"],
            returncode=0 if outcome == "ok" else 2,
            stdout=b"line\nlast line" if outcome == "stdout" else b"",
            stderr=b"failure" if outcome == "stderr" else b"",
        ),
    )
    if outcome == "timeout":
        execute.side_effect = TimeoutExpired(cmd="tool", timeout=3)
    elif outcome == "missing":
        execute.side_effect = OSError("missing")
    monkeypatch.setattr(target=self_test, name="run", value=execute)
    monkeypatch.setattr(
        target=self_test,
        name="subprocess_env",
        value=MagicMock(return_value=None),
    )
    ok, reason = self_test.describe_command(
        command=["tool"],
        timeout=3,
        cwd=Path.cwd(),
    )
    expect_equal(actual=ok, expected=outcome == "ok")
    if not ok:
        expect_in(
            member={
                "stderr": "failure",
                "stdout": "last line",
                "empty": "no output",
                "timeout": "timed out",
                "missing": "could not start",
            }[outcome],
            container=reason,
        )
    expect_equal(actual=execute.call_args.kwargs["timeout"], expected=3)


@pytest.mark.parametrize("source", ["system", "bundle", "none"])
def test_tool_probes_use_system_then_bundle(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    """Fallback probes preserve their selected source and failure reasons.

    Args:
        monkeypatch: Executable and command boundary replacement.
        source: Available tool provider.

    """
    monkeypatch.setattr(
        target=self_test,
        name="which",
        value=MagicMock(return_value="/tool" if source == "system" else None),
    )
    monkeypatch.setattr(
        target=self_test,
        name="describe_command",
        value=MagicMock(return_value=(source == "system", "system failed")),
    )
    monkeypatch.setattr(
        target=self_test,
        name="describe_bundle",
        value=MagicMock(return_value=(source == "bundle", "bundle failed")),
    )
    result: tuple[bool, str, str] = self_test.probe_tool(tool="ruff")
    expect_equal(actual=result[0], expected=source != "none")
    expect_equal(actual=result[2], expected=source)


@pytest.mark.parametrize(
    "mode",
    ["missing", "stale", "invalid", "array", "pass", "fail"],
)
def test_generated_report_requires_fresh_successful_evidence(
    tmp_path: Path,
    mode: str,
) -> None:
    """Reject stale, malformed or failed reports without masking findings.

    Args:
        tmp_path: Isolated report root.
        mode: Report evidence variant.

    """
    report: Path = tmp_path / "EXACTUS_RESULTS" / "DOCS" / "result.json"
    report.parent.mkdir(parents=True)
    if mode != "missing":
        body: str = {"invalid": "broken", "array": "[]"}.get(
            mode,
            dumps(
                obj={
                    "status": "FAIL" if mode == "fail" else "PASS",
                    "passed": mode != "fail",
                    "run": {"exit_code": 1 if mode == "fail" else 0},
                    "summary": {"findings_total": 2 if mode == "fail" else 0},
                },
            ),
        )
        _ = report.write_text(data=body, encoding="utf-8")
    ok, reason, detail = self_test.probe_report(
        project=tmp_path,
        relative="DOCS",
        started=float("inf") if mode == "stale" else 0.0,
    )
    expect_equal(actual=ok, expected=mode == "pass")
    expect_equal(actual=detail["path"], expected=str(object=report))
    if mode == "fail":
        expect_in(member="findings_total=2", container=reason)
        expect_in(member="exit_code=1", container=reason)


@pytest.mark.parametrize("failed", [False, True])
def test_main_writes_real_report_from_controlled_checks(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed: bool,
) -> None:
    """Exercise report generation without invoking any diagnostic commands.

    Args:
        tmp_path: Isolated output root.
        monkeypatch: Diagnostic execution boundary replacement.
        failed: Whether the synthetic check fails.

    """

    def checks(
        *,
        checks: self_test.Checks,
        project: Path,
        artifacts: Path,
    ) -> None:
        """Record controlled diagnostics after verifying fixture creation.

        Args:
            checks: Accumulated outcomes.
            project: Generated fixture root.
            artifacts: Report artifact directory.

        """
        expect_true(condition=(project / "pyproject.toml").is_file())
        expect_equal(actual=artifacts.name, expected="ARTIFACTS")
        checks.note(
            kind="tool",
            name="fixture",
            status="FAIL" if failed else "PASS",
            reason="synthetic failure" if failed else "",
            detail={"source": "test"},
        )
        checks.note(
            kind="tool",
            name="unavailable",
            status="SKIP",
            reason="not installed",
        )

    monkeypatch.setattr(target=self_test, name="run_checks", value=checks)
    monkeypatch.setattr(target=self_test, name="stdout", value=StringIO())
    output: Path = tmp_path / "reports"
    expect_equal(
        actual=self_test.main(
            arguments=(
                str(object=tmp_path),
                "--output-dir",
                str(object=output),
            ),
        ),
        expected=int(failed),
    )
    payload: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=(output / "result.json").read_text(encoding="utf-8")),
    )
    expect_equal(
        actual=payload["status"],
        expected="FAIL" if failed else "PASS",
    )
    expect_in(
        member="fixture",
        container=(output / "result.md").read_text(encoding="utf-8"),
    )


@pytest.mark.parametrize(
    "mode",
    ["cli-fail", "no-browser", "browser", "site-fail"],
)
def test_run_checks_orchestrates_boundaries_and_cleans_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """Check orchestration decisions using doubles, never a nested pipeline.

    Args:
        tmp_path: Isolated diagnostic project.
        monkeypatch: Probe and helper-process boundary replacement.
        mode: Available facilities and failure mode.

    """
    server: MagicMock = MagicMock(spec=Popen)
    display: MagicMock = MagicMock(spec=Popen)
    stop: MagicMock = MagicMock(return_value=0)
    pipeline: MagicMock = MagicMock(return_value=(True, ""))
    monkeypatch.setattr(
        target=self_test,
        name="describe",
        value=MagicMock(return_value=(mode != "cli-fail", "cli failure")),
    )
    monkeypatch.setattr(
        target=self_test,
        name="describe_bundle",
        value=MagicMock(side_effect=[(False, "version failed"), (True, "")]),
    )
    monkeypatch.setattr(
        target=self_test,
        name="probe_tools",
        value=MagicMock(return_value=[]),
    )
    monkeypatch.setattr(
        target=self_test,
        name="probe_chromium",
        value=MagicMock(return_value=(mode == "browser", "", "system")),
    )
    monkeypatch.setattr(
        target=self_test,
        name="serve_display",
        value=MagicMock(return_value=display if mode == "browser" else None),
    )
    monkeypatch.setattr(
        target=self_test,
        name="free_port",
        value=MagicMock(return_value=6100),
    )
    site: MagicMock = MagicMock(return_value=server)
    if mode == "site-fail":
        site.side_effect = RuntimeError("site failed")
    monkeypatch.setattr(target=self_test, name="serve_site", value=site)
    monkeypatch.setattr(
        target=self_test,
        name="probe_pipeline",
        value=pipeline,
    )
    monkeypatch.setattr(
        target=self_test,
        name="probe_report",
        value=MagicMock(return_value=(True, "", {})),
    )
    monkeypatch.setattr(target=self_test, name="stop_process", value=stop)
    checks: self_test.Checks = self_test.Checks()
    self_test.run_checks(checks=checks, project=tmp_path, artifacts=tmp_path)
    if mode == "cli-fail":
        expect_equal(actual=checks.failed, expected=["exactus"])
        site.assert_not_called()
    elif mode == "site-fail":
        expect_in(member="demo-site", container=checks.failed)
        pipeline.assert_not_called()
    else:
        expect_equal(
            actual=pipeline.call_args.kwargs["url"],
            expected="http://127.0.0.1:6100/" if mode == "browser" else None,
        )
        expect_equal(
            actual=stop.call_count,
            expected=2 if mode == "browser" else 1,
        )


@pytest.mark.parametrize("exit_code", [0, 2])
def test_pipeline_probe_builds_scoped_command_and_records_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int,
) -> None:
    """Verify pipeline arguments and polling without starting a pipeline.

    Args:
        tmp_path: Isolated pipeline project and log root.
        monkeypatch: Child process and clock boundary replacement.
        exit_code: Simulated nested process result.

    """
    process: MagicMock = MagicMock(spec=Popen)
    process.poll.side_effect = [None, exit_code]
    process.returncode = exit_code
    factory: MagicMock = MagicMock(return_value=process)
    monkeypatch.setattr(target=self_test, name="Popen", value=factory)
    monkeypatch.setattr(target=self_test, name="sleep", value=MagicMock())
    monkeypatch.setattr(
        target=self_test,
        name="self_command",
        value=MagicMock(return_value=["python", "-m", "exactus"]),
    )
    monkeypatch.setattr(
        target=self_test,
        name="pipeline_env",
        value=MagicMock(return_value={}),
    )
    checks: self_test.Checks = self_test.Checks()
    ok, reason = self_test.probe_pipeline(
        checks=checks,
        project=tmp_path,
        url="http://127.0.0.1:6100/",
        log=tmp_path / "pipeline.log",
    )
    expect_equal(actual=ok, expected=exit_code == 0)
    expect_equal(actual=bool(reason), expected=exit_code != 0)
    expect_in(member="self_test", container=factory.call_args.kwargs["args"])
    expect_in(
        member="record::--headless",
        container=factory.call_args.kwargs["args"],
    )


@pytest.mark.parametrize("force_kill", [False, True])
def test_stop_process_escalates_only_after_timeout(
    *,
    force_kill: bool,
) -> None:
    """Reap helpers with terminate before escalating to kill.

    Args:
        force_kill: Whether graceful termination times out.

    """
    process: MagicMock = MagicMock(spec=Popen)
    process.wait.side_effect = (
        [TimeoutExpired(cmd="helper", timeout=15), 0] if force_kill else [0]
    )
    expect_equal(
        actual=self_test.stop_process(
            process=cast(typ="Popen[bytes]", val=process),
        ),
        expected=0,
    )
    process.terminate.assert_called_once_with()
    expect_equal(actual=process.kill.call_count, expected=int(force_kill))


@pytest.mark.parametrize(
    "source",
    ["system", "host", "playwright", "bundle", "none"],
)
def test_chromium_probe_respects_provider_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    """Find browsers only through controlled executable and cache paths.

    Args:
        tmp_path: Isolated browser installation tree.
        monkeypatch: Browser discovery boundary replacement.
        source: Available browser provider.

    """
    cache: Path = tmp_path / "bundle" / "embedded"
    playwright: Path = tmp_path / "playwright"
    host: Path = tmp_path / "chrome"
    monkeypatch.setattr(
        target=self_test.Constants,
        name="cache_root",
        value=cache,
    )
    monkeypatch.setattr(
        target=self_test,
        name="which",
        value=MagicMock(
            return_value="/chrome" if source == "system" else None,
        ),
    )
    monkeypatch.setattr(
        target=self_test,
        name="host_browsers",
        value=MagicMock(return_value=(host,) if source == "host" else ()),
    )
    monkeypatch.setattr(
        target=self_test,
        name="playwright_browsers",
        value=MagicMock(return_value=playwright),
    )
    monkeypatch.setattr(
        target=self_test,
        name="describe_command",
        value=MagicMock(return_value=(True, "")),
    )
    if source in {"bundle", "playwright"}:
        directory: Path = cache.parent if source == "bundle" else playwright
        directory.mkdir(parents=True)
        _ = (directory / "chrome").write_bytes(data=b"synthetic browser")
    result: tuple[bool, str, str] = self_test.probe_chromium()
    expect_equal(actual=result[0], expected=source != "none")
    expect_equal(
        actual=result[2],
        expected="system" if source == "host" else source,
    )


def test_browser_candidates_honor_overrides_and_deduplicate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Honor configured browsers while ignoring absent and duplicate files.

    Args:
        tmp_path: Isolated browser tree.
        monkeypatch: Browser environment replacement.

    """
    browser: Path = tmp_path / "chrome"
    _ = browser.write_bytes(data=b"browser")
    monkeypatch.setenv(name="CHROME_PATH", value=str(object=browser))
    monkeypatch.setenv(name="PROGRAMFILES", value=str(object=tmp_path))
    expect_in(member=browser, container=tuple(self_test.browser_candidates()))
    monkeypatch.setattr(
        target=self_test,
        name="browser_candidates",
        value=MagicMock(return_value=(browser, browser, tmp_path / "missing")),
    )
    expect_equal(actual=tuple(self_test.host_browsers()), expected=(browser,))
    monkeypatch.setenv(
        name="PLAYWRIGHT_BROWSERS_PATH",
        value=str(object=tmp_path / "missing"),
    )
    expect_equal(actual=self_test.playwright_browsers(), expected=None)
    monkeypatch.setenv(
        name="PLAYWRIGHT_BROWSERS_PATH",
        value=str(object=tmp_path),
    )
    expect_equal(actual=self_test.playwright_browsers(), expected=tmp_path)
    monkeypatch.delenv(name="PLAYWRIGHT_BROWSERS_PATH")
    monkeypatch.setattr(
        target=Path,
        name="home",
        value=MagicMock(return_value=tmp_path),
    )
    expect_equal(actual=self_test.playwright_browsers(), expected=None)
    expected: Path = tmp_path / ".cache" / "ms-playwright"
    expected.mkdir(parents=True)
    expect_equal(actual=self_test.playwright_browsers(), expected=expected)


@pytest.mark.parametrize("available", [False, True])
def test_probe_tools_records_missing_declarations_and_sources(
    *,
    monkeypatch: pytest.MonkeyPatch,
    available: bool,
) -> None:
    """Bundle listings refine planned checks without hiding missing tools.

    Args:
        monkeypatch: Tool listing and probe boundary replacement.
        available: Whether a bundle listing is available.

    """
    monkeypatch.setattr(
        target=self_test.Constants,
        name="expected_tools",
        value=frozenset({"ruff", "node"}),
    )
    monkeypatch.setattr(
        target=self_test,
        name="bundle_tools",
        value=MagicMock(return_value=["ruff"] if available else None),
    )
    monkeypatch.setattr(
        target=self_test,
        name="probe_tool",
        value=MagicMock(return_value=(True, "", "system")),
    )
    checks: self_test.Checks = self_test.Checks()
    expect_equal(
        actual=self_test.probe_tools(checks=checks),
        expected=["node", "ruff"],
    )
    expect_equal(actual=checks.failed, expected=[])
    expect_in(
        member="node" if available else "list-tools",
        container=checks.skipped,
    )


@pytest.mark.parametrize("exit_code", [0, 1])
def test_bundle_listing_uses_its_resolved_launcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int,
) -> None:
    """Parse only successful bundle listings and preserve sorted tool names.

    Args:
        tmp_path: Synthetic bundle launcher location.
        monkeypatch: Bundle dispatch boundary replacement.
        exit_code: Listing process exit status.

    """
    monkeypatch.setattr(
        target=self_test,
        name="bundle_launcher",
        value=MagicMock(return_value=tmp_path / "__main__.py"),
    )
    monkeypatch.setattr(
        target=self_test,
        name="run",
        value=MagicMock(
            return_value=CompletedProcess(
                args=[],
                returncode=exit_code,
                stdout="ruff node",
                stderr="",
            ),
        ),
    )
    expect_equal(
        actual=self_test.bundle_tools(),
        expected=["node", "ruff"] if exit_code == 0 else None,
    )


@pytest.mark.parametrize("ready", [False, True])
def test_demo_site_waits_for_readiness_and_kills_failed_start(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ready: bool,
) -> None:
    """Bound readiness probing and keep demo assets confined to the fixture.

    Args:
        tmp_path: Isolated demo site root.
        monkeypatch: Process, clock and connection boundary replacement.
        ready: Whether the local server becomes reachable.

    """
    process: MagicMock = MagicMock(spec=Popen)
    monkeypatch.setattr(
        target=self_test,
        name="Popen",
        value=MagicMock(return_value=process),
    )
    monkeypatch.setattr(
        target=self_test,
        name="monotonic",
        value=MagicMock(side_effect=[0.0, 0.0, 31.0]),
    )
    monkeypatch.setattr(target=self_test, name="sleep", value=MagicMock())
    connect: MagicMock = MagicMock()
    if not ready:
        connect.side_effect = OSError("not listening")
    monkeypatch.setattr(
        target=self_test,
        name="create_connection",
        value=connect,
    )
    if ready:
        expect_equal(
            actual=self_test.serve_site(directory=tmp_path, port=6100),
            expected=process,
        )
        process.kill.assert_not_called()
    else:
        with pytest.raises(
            expected_exception=RuntimeError,
            match="demo site did not start",
        ):
            self_test.serve_site(directory=tmp_path, port=6100)
        process.kill.assert_called_once_with()
    expect_true(condition=(tmp_path / "site" / "index.html").is_file())
