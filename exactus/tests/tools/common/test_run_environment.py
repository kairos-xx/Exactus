# Copyright (c) 2026
"""Exercise the canonical run-scoped environment boundary."""

from __future__ import annotations

from subprocess import Popen
from sys import executable
from typing import TYPE_CHECKING, Final

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_not_in,
    expect_true,
)
from exactus.tools.common.execution import execute_exactus
from exactus.tools.common.process_control import process_exists
from exactus.tools.common.registry import (
    RunClaim,
    RunRecord,
    RunRegistry,
    project_root_target,
)
from exactus.tools.common.run_environment import (
    Constants,
    run_scoped,
    sanitized_environ,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from exactus.tools.common.models import ToolRunResult
_RUN_SCOPED: Final[tuple[str, ...]] = (
    "EXACTUS_COLLECT_FILES",
    "EXACTUS_COMPARISON_BASELINE",
    "EXACTUS_CONFIG",
    "EXACTUS_EXPLICIT_ARGUMENTS",
    "EXACTUS_HOST",
    "EXACTUS_ORCHESTRATED",
    "EXACTUS_PIPELINE_RUN_ID",
    "EXACTUS_PMANAGER_WORKER",
    "EXACTUS_PORT",
    "EXACTUS_PROJECT_ROOT",
    "EXACTUS_RECORD_ROOT",
    "EXACTUS_REGISTRY",
    "EXACTUS_REPORTS_ROOT",
    "EXACTUS_REPORT_OUTPUT",
    "EXACTUS_RESULTS",
    "EXACTUS_RESULTS_RELEASE",
    "EXACTUS_ROOT",
    "EXACTUS_RUN_ID",
    "EXACTUS_TOOL",
    "EXACTUS_ACTION__REPORT",
    "EXACTUS_ES__EXTRA",
    "EXACTUS_RECORDER_FLUSH__X",
    "EXACTUS_TOOLS_PAYLOAD__Y",
)
_TOOLCHAIN: Final[tuple[str, ...]] = (
    "EXACTUS_LINTER_TOOLCHAIN",
    "EXACTUS_MCP_CLOUDFLARED",
    "EXACTUS_PROJECT_PYTHON",
    "EXACTUS_TOOLS_CACHE",
    "PATH",
)


def test_run_scoped_matches_the_live_run_contract() -> None:
    """Every run-scoped name and payload prefix is classified."""
    name: str
    for name in _RUN_SCOPED:
        expect_true(condition=run_scoped(name=name))
    for name in _TOOLCHAIN:
        expect_false(condition=run_scoped(name=name))


def test_sanitized_environ_removes_only_run_scoped_state() -> None:
    """Nested runs lose outer coordination but keep toolchain choices."""
    source: dict[str, str] = {
        **dict.fromkeys(_RUN_SCOPED, "live"),
        **dict.fromkeys(_TOOLCHAIN, "/kept"),
        "HOME": "/home",
    }
    environment: dict[str, str] = sanitized_environ(source=source)
    name: str
    for name in _RUN_SCOPED:
        expect_not_in(member=name, container=environment)
    for name in _TOOLCHAIN:
        expect_equal(actual=environment[name], expected="/kept")
    expect_equal(actual=environment["HOME"], expected="/home")
    expect_in(member="EXACTUS_ROOT", container=source)


def test_sanitized_environ_defaults_to_process_environ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default source is ``os.environ``.

    Args:
        monkeypatch: Restore the process environment afterwards.

    """
    monkeypatch.setenv(name="EXACTUS_RUN_ID", value="outer")
    monkeypatch.setenv(name="EXACTUS_PROJECT_PYTHON", value="/python")
    environment: dict[str, str] = sanitized_environ()
    expect_not_in(member="EXACTUS_RUN_ID", container=environment)
    expect_equal(
        actual=environment["EXACTUS_PROJECT_PYTHON"],
        expected="/python",
    )


def test_canonical_set_covers_every_live_export() -> None:
    """The contract names every coordination variable a run exports."""
    named: frozenset[str] = frozenset(_RUN_SCOPED)
    required: frozenset[str] = named - frozenset(
        {
            "EXACTUS_ACTION__REPORT",
            "EXACTUS_ES__EXTRA",
            "EXACTUS_RECORDER_FLUSH__X",
            "EXACTUS_TOOLS_PAYLOAD__Y",
        },
    )
    expect_true(condition=required <= Constants.variables)
    expect_equal(
        actual=Constants.prefixes,
        expected=(
            "EXACTUS_ACTION__",
            "EXACTUS_ES__",
            "EXACTUS_RECORDER_FLUSH__",
            "EXACTUS_TOOLS_PAYLOAD__",
        ),
    )


def test_nested_execution_leaves_foreign_run_untouched(
    tmp_path: Path,
) -> None:
    """A nested tool run claims only its own tree and registry.

    Reproduces the reported defect: a self-contained Exactus run started
    while an outer run is live must never claim, reset, or clear the
    outer run's report tree — the nested claim lands in its own
    ``EXACTUS_RESULTS/.runtime/runs.db`` and its own output directory.

    Args:
        tmp_path: Isolated project tree.

    """
    outer_root: Path = tmp_path / "outer"
    outer_output: Path = outer_root / "EXACTUS_RESULTS" / "LINTS"
    outer_output.mkdir(parents=True)
    sentinel: Path = outer_output / "result.md"
    _ = sentinel.write_text(data="outer report", encoding="utf-8")
    registry: RunRegistry = RunRegistry(
        path=outer_output.parent / ".runtime" / "runs.db",
    )
    sleeper: Popen[bytes] = Popen(
        args=[executable, "-c", "import time;time.sleep(60)"],
    )
    try:
        claimed: tuple[RunRecord, ...] | None = registry.claim(
            request=RunClaim(
                kind="tool",
                identifier="lints",
                run_id="outer-run",
                pipeline_run_id="outer-pipeline",
                pid=sleeper.pid,
                output=outer_output,
                targets=(
                    str(object=outer_output.resolve()),
                    project_root_target(root=outer_root),
                ),
            ),
        )
        expect_equal(actual=claimed, expected=())
        nested: Path = tmp_path / "nested" / "EXACTUS_RESULTS" / "LINTS"
        result: ToolRunResult = execute_exactus(
            analyzer="lints",
            title="Lints",
            main=lambda: 0,
            output=nested,
        )
        expect_equal(actual=result.exit_code, expected=0)
        expect_true(condition=process_exists(pid=sleeper.pid))
        expect_true(condition=sentinel.is_file())
        expect_equal(
            actual=sentinel.read_text(encoding="utf-8"),
            expected="outer report",
        )
        expect_equal(
            actual=[record.run_id for record in registry.live()],
            expected=["outer-run"],
        )
    finally:
        sleeper.terminate()
        _ = sleeper.wait(timeout=10)
