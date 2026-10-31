# Copyright (c) 2026 João Lopes.
"""Behavioral tests for exactus.packages.guard."""

from __future__ import annotations

from pathlib import Path
from subprocess import Popen, run
from sys import executable
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from psutil import NoSuchProcess, Process

from exactus.packages.guard import (
    ProcessGuard,
    ProcessSupervisor,
    SupervisionResult,
)


def expect(*, condition: bool, message: str) -> None:
    """Fail when a behavioral expectation is false.

    Args:
        condition: Whether the expectation succeeded.
        message: Failure message when the expectation is false.

    Raises:
        AssertionError: If ``condition`` is false.

    """
    if not condition:
        raise AssertionError(message)


class TestHelpers:
    """Provide process lifecycle assertions."""

    @staticmethod
    def assert_dead(*, pid: int, timeout: float = 5.0) -> None:
        """Assert that a process disappears before a deadline.

        Args:
            pid: Process identifier to inspect.
            timeout: Maximum wait in seconds.

        Raises:
            AssertionError: If the process survives beyond the deadline.

        """
        deadline: float = monotonic() + timeout
        while monotonic() < deadline:
            try:
                if not Process(pid=pid).is_running():
                    return
            except NoSuchProcess:
                return
            sleep(0.01)
        msg: str = f"process {pid} survived cleanup"
        raise AssertionError(msg)


class TestProcessSupervisor:
    """Verify external supervision."""

    @staticmethod
    def test_returns_target_exit_code() -> None:
        """Preserve a target's natural exit status."""
        expected_exit_code: int = 7
        expect(
            condition=ProcessSupervisor(
                command=(executable, "-c", "raise SystemExit(7)"),
            )
            .run()
            .exit_code
            == expected_exit_code,
            message="target exit status was not preserved",
        )

    @staticmethod
    def test_kills_nested_tree() -> None:
        """Discover and clean a nested descendant tree."""
        with TemporaryDirectory() as directory:
            pid_file: Path = Path(directory) / "grandchild.pid"
            child_code: str = (
                f"import pathlib,subprocess,sys,time;p=subprocess.Popen([s"
                f"ys.executable,'-c','import time;time.sleep(60)']);pathli"
                f"b.Path("
                f"{str(object=pid_file)!r}"
                f").write_text(str(p.pid));time.sleep(60)"
            )
            root_code: str = (
                "import pathlib,subprocess,sys,time;"
                f"subprocess.Popen([sys.executable,'-c',{child_code!r}]);"
                f"p=pathlib.Path({str(object=pid_file)!r});"
                "deadline=time.monotonic()+5;"
                'exec("while not p.exists() and time.monotonic()<deadline:'
                '\\n time.sleep(.01)");time.sleep(2)'
            )
            result: SupervisionResult = ProcessSupervisor(
                command=(executable, "-c", root_code),
                poll_interval=0.005,
                grace_seconds=0.1,
            ).run()
            grandchild_pid: int = int(pid_file.read_text(encoding="utf-8"))
            minimum_nested_depth: int = 2
            expect(
                condition=any(
                    record.depth >= minimum_nested_depth
                    for record in result.cleanup.observed
                ),
                message="nested descendant was not observed",
            )
            TestHelpers.assert_dead(pid=grandchild_pid)


class TestProcessGuard:
    """Verify in-process guarding."""

    @staticmethod
    def test_context_cleans_child() -> None:
        """Terminate a child that outlives its guarded block."""
        process: Popen[bytes] | None = None
        with ProcessGuard(poll_interval=0.005, grace_seconds=0.1) as guard:
            process = Popen(
                args=(executable, "-c", "import time;time.sleep(60)"),
            )
            sleep(0.05)
        expect(
            condition=guard.result is not None,
            message="cleanup result missing",
        )
        expect(condition=process is not None, message="child process missing")
        if process is not None:
            TestHelpers.assert_dead(pid=process.pid)

    @staticmethod
    def test_context_preserves_exception() -> None:
        """Never suppress an exception from guarded application code."""

        def fail_inside_guard() -> None:
            """Raise from inside a guarded context for propagation testing.

            Raises:
                RuntimeError: Always, to verify exception propagation.

            """
            with ProcessGuard(poll_interval=0.005, grace_seconds=0.1):
                msg: str = "expected"
                raise RuntimeError(msg)

        caught: bool = False
        try:
            fail_inside_guard()
        except RuntimeError:
            caught = True
        expect(condition=caught, message="guard suppressed the exception")


class TestExamples:
    """Verify every supported example invocation."""

    @staticmethod
    def test_module_example() -> None:
        """Run examples through Python's module execution mode."""
        expect(
            condition=run(
                args=(executable, "-m", "exactus.packages.guard.examples"),
                check=False,
            ).returncode
            == 0,
            message="example invocation failed",
        )

    @staticmethod
    def test_package_path_example() -> None:
        """Run the examples package by directory path."""
        expect(
            condition=run(
                args=(executable, "exactus/packages/guard/examples"),
                check=False,
            ).returncode
            == 0,
            message="example invocation failed",
        )

    @staticmethod
    def test_script_example() -> None:
        """Run the executable example script directly."""
        expect(
            condition=run(
                args=(executable, "exactus/packages/guard/examples/run.py"),
                check=False,
            ).returncode
            == 0,
            message="example invocation failed",
        )
