# Copyright (c) 2026
"""Validate the constrained Exactus runner."""

from asyncio import run
from asyncio.subprocess import Process
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from exactus.packages.exactus_mcp import runner as runner_module
from exactus.packages.exactus_mcp.runner import (
    CheckResult,
    ExactusCommandRunner,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_true,
    private_call,
)


def test_report_summary_reads_status_and_findings(tmp_path: Path) -> None:
    """Machine report metadata is parsed without weakening JSON types.

    Args:
        tmp_path: Isolated report directory.

    """
    report: Path = tmp_path / "result.json"
    _ = report.write_text(
        data=('{"status":"PASS","summary":{"findings_total":3}}'),
        encoding="utf-8",
    )
    expect_equal(
        actual=private_call(
            owner=ExactusCommandRunner,
            name="_report_summary",
            path=report,
        ),
        expected=("PASS", 3),
    )


def test_run_rejects_parent_traversal_before_process_start(
    tmp_path: Path,
) -> None:
    """Remote include globs cannot escape the configured project.

    Args:
        tmp_path: Fixed synthetic project root.

    """
    runner: ExactusCommandRunner = ExactusCommandRunner(
        root=tmp_path,
        timeout=1.0,
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="unsafe include pattern",
    ):
        _ = run(main=runner.run(tool="docs", includes=("../outside.py",)))


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("broken", ("INVALID", 0)),
        ("[]", ("INVALID", 0)),
        ("{}", ("UNKNOWN", 0)),
        ('{"status":1,"summary":[]}', ("UNKNOWN", 0)),
        ('{"status":"FAIL","summary":{"findings_total":true}}', ("FAIL", 0)),
        ('{"status":"FAIL","summary":{"findings_total":"4"}}', ("FAIL", 0)),
    ],
)
def test_report_summary_rejects_malformed_fields(
    tmp_path: Path,
    body: str,
    expected: tuple[str, int],
) -> None:
    """Malformed reports never become successful checks or boolean counts.

    Args:
        tmp_path: Isolated report directory.
        body: Candidate report JSON.
        expected: Required summary.

    """
    report: Path = tmp_path / "result.json"
    _ = report.write_text(data=body, encoding="utf-8")
    expect_equal(
        actual=private_call(
            owner=ExactusCommandRunner,
            name="_report_summary",
            path=report,
        ),
        expected=expected,
    )
    expect_equal(
        actual=private_call(
            owner=ExactusCommandRunner,
            name="_report_summary",
            path=tmp_path / "missing",
        ),
        expected=("INVALID", 0),
    )


@pytest.mark.parametrize(
    "includes",
    [("/absolute",), ("x" * 513,), ("safe",) * 65],
)
def test_run_rejects_unsafe_include_limits(
    tmp_path: Path,
    includes: tuple[str, ...],
) -> None:
    """Absolute, oversized and excessive globs fail before process creation.

    Args:
        tmp_path: Configured project root.
        includes: Invalid include selection.

    """
    with pytest.raises(
        expected_exception=ValueError,
        match=r"unsafe include pattern|at most 64",
    ):
        run(
            main=ExactusCommandRunner(root=tmp_path, timeout=1.0).run(
                tool="docs",
                includes=includes,
            ),
        )


@pytest.mark.parametrize(
    ("body", "expected_status"),
    [
        (None, "MISSING"),
        ("not JSON", "INVALID"),
        ('{"status":"PASS","summary":{"findings_total":2}}', "PASS"),
    ],
)
def test_run_collects_reports_and_bounds_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    body: str | None,
    expected_status: str,
) -> None:
    """Execute only a dry fixed-root command and return its bounded report.

    Args:
        tmp_path: Configured project root.
        monkeypatch: Subprocess boundary replacement.
        body: Optional generated machine report.
        expected_status: Required check status.

    """
    runner: ExactusCommandRunner = ExactusCommandRunner(
        root=tmp_path,
        timeout=1.0,
    )
    report: Path = tmp_path / "EXACTUS_RESULTS" / "DOCS" / "result.json"
    report.parent.mkdir(parents=True)
    if body is not None:
        _ = report.write_text(data=body, encoding="utf-8")
    process: MagicMock = MagicMock(spec=Process)
    process.returncode = 3
    process.communicate = AsyncMock(
        return_value=(b"x" * 16001 + b"\xff", None),
    )
    spawn: AsyncMock = AsyncMock(return_value=process)
    monkeypatch.setattr(
        target=runner_module,
        name="create_subprocess_exec",
        value=spawn,
    )
    result: CheckResult = run(
        main=runner.run(tool="docs", includes=("src/**",)),
    )
    expect_equal(actual=result.exit_code, expected=3)
    expect_equal(actual=result.report_path, expected=report)
    expect_equal(actual=len(result.output), expected=16000)
    expect_true(condition=result.output.endswith("\ufffd"))
    expect_in(member="--dry", container=spawn.call_args.args)
    expect_equal(
        actual=spawn.call_args.args[-2:],
        expected=("--include", "src/**"),
    )
    expect_equal(actual=spawn.call_args.kwargs["cwd"], expected=tmp_path)
    expect_equal(actual=result.status, expected=expected_status)
    expect_equal(
        actual=result.to_json()["findings"],
        expected=2 if result.status == "PASS" else 0,
    )
    if body is None:
        expect_equal(
            actual=runner.read_report(tool="docs", report_format="json"),
            expected="No json report exists for docs.",
        )
    else:
        expect_equal(
            actual=runner.read_report(tool="docs", report_format="json"),
            expected=body,
        )
    _ = report.with_suffix(suffix=".md").write_text(
        data="# Docs\n",
        encoding="utf-8",
    )
    expect_equal(
        actual=runner.read_report(tool="docs", report_format="markdown"),
        expected="# Docs\n",
    )
    expect_in(member="docs", container=runner.list_tools())


def test_report_path_rejects_unknown_tool(tmp_path: Path) -> None:
    """An unknown tool identifier cannot resolve a report location.

    Args:
        tmp_path: Configured project root.

    """
    with pytest.raises(
        expected_exception=ValueError,
        match="unknown Exactus tool",
    ):
        private_call(
            owner=ExactusCommandRunner(root=tmp_path, timeout=1.0),
            name="_report_path",
            tool="not-a-tool",
        )


@pytest.mark.parametrize("force_kill", [False, True])
def test_run_timeout_reaps_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    force_kill: bool,
) -> None:
    """A timed-out report terminates its child, escalating when necessary.

    Args:
        tmp_path: Configured project root.
        monkeypatch: Subprocess boundary replacement.
        force_kill: Whether termination also times out.

    """
    process: MagicMock = MagicMock(spec=Process)
    process.communicate = AsyncMock(side_effect=TimeoutError())
    process.wait = AsyncMock(
        side_effect=[TimeoutError(), 0] if force_kill else [0],
    )
    monkeypatch.setattr(
        target=runner_module,
        name="create_subprocess_exec",
        value=AsyncMock(return_value=process),
    )
    result: CheckResult = run(
        main=ExactusCommandRunner(root=tmp_path, timeout=1.0).run(
            tool="docs",
            includes=(),
        ),
    )
    expect_equal(actual=result.status, expected="TIMEOUT")
    expect_equal(actual=result.exit_code, expected=124)
    expect_equal(actual=result.report, expected=None)
    process.terminate.assert_called_once_with()
    expect_equal(actual=process.kill.call_count, expected=int(force_kill))
