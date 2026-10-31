# Copyright (c) 2026
"""Cover the bundled ``common`` examples entry points."""

from __future__ import annotations

from io import StringIO
from os import getpid
from pathlib import Path
from runpy import run_path
from sys import modules
from typing import Final, final

import pytest

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.common.examples import run as demo
from exactus.tools.common.registry import RunClaim, RunRegistry


@final
class Constants:
    """Group module-level constants.

    Attributes:
        repo: Grouped module constant.
        markdown_example: Grouped module constant.

    """

    repo: Final[Path] = Path(__file__).resolve().parents[4]
    markdown_example: Final[Path] = (
        repo
        / "exactus"
        / "tools"
        / "common"
        / "templates"
        / "markdown"
        / "examples"
        / "run.py"
    )


def test_markdown_template_example_validates_fixtures() -> None:
    """The markdown example parses every bundled fixture pair."""
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(
            path_name=str(object=Constants.markdown_example),
            run_name="__main__",
        )
    expect_equal(actual=raised.value.code, expected=0)


def test_prepare_project_builds_an_intentionally_imperfect_fixture() -> None:
    """``prepare_project`` writes source files and an inventory."""
    root: Path = demo.prepare_project(file_count=3)
    expect_true(condition=(root / "pyproject.toml").is_file())
    expect_true(condition=(root / "README.md").is_file())
    expect_true(condition=(root / "src" / "module_000.py").is_file())
    expect_true(condition=(root / ".demo-logs").is_dir())


def test_prepare_project_rejects_an_empty_fixture() -> None:
    """``prepare_project`` refuses a zero-file fixture."""
    with pytest.raises(expected_exception=ValueError, match="at least 1"):
        demo.prepare_project(file_count=0)


def test_invocations_plan_overlapping_collisions(tmp_path: Path) -> None:
    """``invocations`` returns four staggered launches.

    Args:
        tmp_path: Pytest temporary directory.

    """
    plans: tuple[demo.Invocation, ...] = demo.invocations(root=tmp_path)
    expect_equal(actual=len(plans), expected=4)
    expect_equal(
        actual=[plan.label for plan in plans],
        expected=[
            "pipeline",
            "pipeline-reset",
            "pipeline-reset-again",
            "kwargs-rerun",
        ],
    )


def test_main_prepare_only_prints_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--prepare-only`` prints the commands without launching them.

    Args:
        monkeypatch: Pytest patching helper.

    """
    out: StringIO = StringIO()
    monkeypatch.setattr(target=demo, name="stdout", value=out)
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["demo", "--files", "2", "--prepare-only"],
    )
    expect_equal(actual=demo.main(), expected=0)
    expect_true(condition="pipeline-reset" in out.getvalue())


def _immediate_process() -> type:
    """Build a ``Popen`` stand-in that finishes instantly.

    Returns:
        A factory class mimicking ``Popen``.

    """

    class Process:
        """Fake process that reports immediate success."""

        pid: int = 4321
        returncode: int = 0

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            """Accept the launch arguments without spawning."""

        @staticmethod
        def poll() -> int:
            """Report the process as finished.

            Returns:
                Always ``0``.

            """
            return 0

        @staticmethod
        def wait(timeout: float | None = None) -> int:
            """Return the recorded exit status.

            Args:
                timeout: Ignored timeout.

            Returns:
                Always ``0``.

            """
            _ = timeout
            return 0

        def terminate(self) -> None:
            """Accept termination requests silently."""

    return Process


def test_run_demo_monitors_stubbed_processes_until_settled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``run_demo`` launches, polls, and scores every stubbed invocation.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=demo, name="Popen", value=_immediate_process())
    monkeypatch.setattr(target=demo.Constants, name="poll_seconds", value=0.01)
    monkeypatch.setattr(
        target=demo.Constants,
        name="launch_grace_seconds",
        value=0.01,
    )
    (tmp_path / ".demo-logs").mkdir()
    plans: tuple[demo.Invocation, ...] = (
        demo.Invocation(label="one", delay_seconds=0.0, command=("true",)),
        demo.Invocation(label="two", delay_seconds=0.0, command=("true",)),
    )
    expect_equal(actual=demo.run_demo(root=tmp_path, plans=plans), expected=0)
    expect_true(condition=(tmp_path / ".demo-logs" / "one.log").is_file())


def test_transcript_failed_detects_coordinator_markers(tmp_path: Path) -> None:
    """``transcript_failed`` spots infrastructure failures in logs.

    Args:
        tmp_path: Pytest temporary directory.

    """
    logs: Path = tmp_path / ".demo-logs"
    logs.mkdir()
    invocation: demo.Invocation = demo.Invocation(
        label="crash",
        delay_seconds=0.0,
        command=("true",),
    )
    _ = (logs / "crash.log").write_text(
        data="Traceback (most recent call last)\n",
        encoding="utf-8",
    )
    expect_true(
        condition=demo.transcript_failed(root=tmp_path, invocation=invocation),
    )
    clean: demo.Invocation = demo.Invocation(
        label="clean",
        delay_seconds=0.0,
        command=("true",),
    )
    _ = (logs / "clean.log").write_text(data="ok\n", encoding="utf-8")
    expect_true(
        condition=not demo.transcript_failed(root=tmp_path, invocation=clean),
    )


def test_registry_snapshot_handles_missing_and_live_databases(
    tmp_path: Path,
) -> None:
    """``registry_snapshot`` degrades without a database and lists rows.

    Args:
        tmp_path: Pytest temporary directory.

    """
    expect_equal(actual=demo.registry_snapshot(root=tmp_path), expected=())
    database_dir: Path = tmp_path / "EXACTUS_RESULTS" / ".runtime"
    database_dir.mkdir(parents=True)
    registry: RunRegistry = RunRegistry(path=database_dir / "runs.db")
    _ = registry.claim(
        request=RunClaim(
            kind="task",
            identifier="probe",
            run_id="run-1",
            pipeline_run_id=None,
            pid=getpid(),
            output=tmp_path,
            targets=(),
        ),
    )
    rows: tuple[str, ...] = demo.registry_snapshot(root=tmp_path)
    expect_true(condition=len(rows) == 1)
    expect_true(condition="probe" in rows[0])
