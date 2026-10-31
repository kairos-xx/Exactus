# Copyright (c) 2026
"""Exercise the packages-wide example runner without spawning demos."""

from __future__ import annotations

from io import StringIO
from runpy import run_module
from subprocess import TimeoutExpired, run
from sys import executable, modules
from typing import TYPE_CHECKING

import pytest

from exactus.packages import __main__ as runner
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
)

if TYPE_CHECKING:
    from pathlib import Path
    from subprocess import CompletedProcess


def _example(
    name: str,
    *,
    script: bool = False,
    daemon: bool = False,
) -> runner.Example:
    """Build a synthetic example under the packages root.

    Args:
        name: Packages package name.
        script: Whether ``run.py`` carries a shebang.
        daemon: Whether a clean run stays alive past the timeout.

    Returns:
        Synthetic example descriptor.

    """
    return runner.Example(
        name=name,
        directory=runner.Constants.packages / name / "examples",
        script=script,
        daemon=daemon,
    )


def _popen(exit_code: int | None) -> tuple[object, object]:
    """Build a ``Popen`` stand-in and its matching tree killer.

    Args:
        exit_code: Status ``wait`` returns; ``None`` means timeout.

    Returns:
        Factory callable mimicking ``Popen`` and a ``terminate_tree``
        stand-in that kills every spawned fake.

    """
    created: list[Process] = []

    class Process:
        def __init__(self) -> None:
            """Init."""
            self.pid: int = 4321
            self.killed: bool = False

        def wait(self, timeout: float | None = None) -> int:
            """Return the scripted outcome.

            Args:
                timeout: Seconds before timing out.

            Returns:
                Scripted exit status.

            Raises:
                TimeoutExpired: When the scripted outcome is a timeout.

            """
            _ = timeout
            if exit_code is None and (not self.killed):
                raise TimeoutExpired(cmd="demo", timeout=0)
            return exit_code if exit_code is not None else -9

        def kill(self) -> None:
            """Record termination of the synthetic process."""
            self.killed = True

    def spawn(**_kwargs: object) -> object:
        """Return the scripted process.

        Args:
            **_kwargs: Ignored launch arguments.

        Returns:
            Scripted process handle.

        """
        process: Process = Process()
        created.append(process)
        return process

    def kill_tree(**_kwargs: object) -> None:
        """Mark every spawned fake as terminated.

        Args:
            **_kwargs: Ignored ``terminate_tree`` arguments.

        """
        for process in created:
            process.kill()

    return (spawn, kill_tree)


@pytest.mark.parametrize(
    "command",
    [
        (executable, "exactus/packages", "--help"),
        (executable, "-m", "exactus.packages", "--help"),
    ],
)
def test_packages_entrypoint_forms(command: tuple[str, ...]) -> None:
    """Both directory and module execution expose the runner CLI.

    Args:
        command: Interpreter and packages invocation form to execute.

    """
    completed: CompletedProcess[str] = run(
        args=command,
        cwd=runner.Constants.packages.parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    expect_equal(actual=completed.returncode, expected=0)
    expect_in(member="Restrict the run", container=completed.stdout)


def test_packages_main_module_runs_the_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``exactus/packages/__main__.py`` executes the runner CLI in place.

    Args:
        monkeypatch: Points ``sys.argv`` at the help flag.

    """
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["exactus.packages", "--help"],
    )
    with pytest.raises(expected_exception=SystemExit) as captured:
        _ = run_module(mod_name="exactus.packages", run_name="__main__")
    expect_equal(actual=captured.value.code, expected=0)


def test_packages_runs_every_example_without_errors() -> None:
    """Run every discovered example cleanly via the packages entry point."""
    completed: CompletedProcess[str] = run(
        args=(executable, "-m", "exactus.packages"),
        cwd=runner.Constants.packages.parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    expect_true(
        condition=completed.returncode == 0,
        message=(
            f"exit={completed.returncode}\n"
            f"{completed.stdout[-2000:]}\n{completed.stderr[-1000:]}"
        ),
    )
    expect_in(member="0 failed", container=completed.stdout)


def test_discover_finds_sorted_runnable_examples() -> None:
    """Discovery lists every bundled ``examples/run.py`` once."""
    examples: tuple[runner.Example, ...] = runner.discover()
    names: list[str] = [item.name for item in examples]
    expect_equal(actual=names, expected=sorted(names))
    expect_in(member="markdown", container=names)
    expect_in(member="watch", container=names)
    by_name: dict[str, runner.Example] = {item.name: item for item in examples}
    expect_true(condition=by_name["watch"].daemon)
    expect_false(condition=by_name["markdown"].daemon)
    expect_equal(
        actual=all((item.directory / "run.py").is_file() for item in examples),
        expected=True,
    )


def test_forms_reflects_the_script_flag() -> None:
    """Shebang examples gain the direct-script invocation form."""
    expect_equal(
        actual=runner.forms(example=_example(name="x")),
        expected=("module", "folder"),
    )
    expect_equal(
        actual=runner.forms(example=_example(name="x", script=True)),
        expected=("module", "folder", "script"),
    )


def test_launch_reports_ok_fail_and_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``launch`` maps exit codes and timeouts onto report statuses.

    Args:
        tmp_path: Log destination for synthetic runs.
        monkeypatch: Replaces ``Popen`` with scripted processes.

    """
    spawn: object
    kill_tree: object
    spawn, kill_tree = _popen(exit_code=0)
    monkeypatch.setattr(target=runner, name="Popen", value=spawn)
    monkeypatch.setattr(target=runner, name="terminate_tree", value=kill_tree)
    ok: runner.Report = runner.launch(
        example=_example(name="demo"),
        form="module",
        timeout=1.0,
        logs=tmp_path,
    )
    expect_equal(actual=ok.status, expected="ok")
    expect_equal(actual=ok.exit_code, expected=0)
    expect_true(condition=ok.log.is_file())
    expect_in(member="demo", container=ok.log.name)
    spawn, kill_tree = _popen(exit_code=3)
    monkeypatch.setattr(target=runner, name="Popen", value=spawn)
    monkeypatch.setattr(target=runner, name="terminate_tree", value=kill_tree)
    failed: runner.Report = runner.launch(
        example=_example(name="demo"),
        form="folder",
        timeout=1.0,
        logs=tmp_path,
    )
    expect_equal(actual=failed.status, expected="fail")
    expect_equal(actual=failed.exit_code, expected=3)
    spawn, kill_tree = _popen(exit_code=None)
    monkeypatch.setattr(target=runner, name="Popen", value=spawn)
    monkeypatch.setattr(target=runner, name="terminate_tree", value=kill_tree)
    timed: runner.Report = runner.launch(
        example=_example(name="demo"),
        form="script",
        timeout=1.0,
        logs=tmp_path,
    )
    expect_equal(actual=timed.status, expected="timeout")
    expect_true(condition=timed.exit_code is None)
    alive: runner.Report = runner.launch(
        example=_example(name="demo", daemon=True),
        form="module",
        timeout=1.0,
        logs=tmp_path,
    )
    expect_equal(actual=alive.status, expected="alive")


def test_show_prints_status_and_failure_tail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``show`` writes one line, plus the log tail for failures.

    Args:
        tmp_path: Log destination for synthetic runs.
        monkeypatch: Redirects the module-level ``stdout`` binding.

    """
    buffer: StringIO = StringIO()
    monkeypatch.setattr(target=runner, name="stdout", value=buffer)
    ok_log: Path = tmp_path / "ok.log"
    ok_log.write_text(data="quiet\n", encoding="utf-8")
    runner.show(
        report=runner.Report(
            example=_example(name="demo"),
            form="module",
            status="ok",
            exit_code=0,
            seconds=0.1,
            log=ok_log,
        ),
    )
    expect_in(member="demo", container=buffer.getvalue())
    expect_in(member="ok", container=buffer.getvalue())
    fail_log: Path = tmp_path / "fail.log"
    fail_log.write_text(data="boom\n", encoding="utf-8")
    runner.show(
        report=runner.Report(
            example=_example(name="demo"),
            form="script",
            status="fail",
            exit_code=2,
            seconds=0.2,
            log=fail_log,
        ),
    )
    expect_in(member="boom", container=buffer.getvalue())


def test_main_rejects_unknown_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown example names exit ``2`` and list the known set.

    Args:
        monkeypatch: Redirects the module-level ``stdout`` binding.

    """
    buffer: StringIO = StringIO()
    monkeypatch.setattr(target=runner, name="stdout", value=buffer)
    expect_equal(
        actual=runner.main(arguments=("definitely-not-real",)),
        expected=2,
    )
    expect_in(member="unknown examples:", container=buffer.getvalue())


def test_main_runs_stubbed_examples(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main`` aggregates per-form reports into the exit status.

    Args:
        tmp_path: Log destination for the synthetic reports.
        monkeypatch: Replaces discovery, launch, and ``stdout``.

    """
    buffer: StringIO = StringIO()
    monkeypatch.setattr(target=runner, name="stdout", value=buffer)
    log: Path = tmp_path / "demo.log"
    log.write_text(data="output\n", encoding="utf-8")

    def discover_stub() -> tuple[runner.Example, ...]:
        """Return two synthetic examples.

        Returns:
            Fixed example pair.

        """
        return (_example(name="alpha"), _example(name="beta", daemon=True))

    def launch_stub(
        *,
        example: runner.Example,
        form: str,
        timeout: float,
        logs: Path,
    ) -> runner.Report:
        """Return an ``ok`` report for ``alpha`` and ``fail`` otherwise.

        Args:
            example: Invoked example.
            form: Invocation form.
            timeout: Ignored timeout.
            logs: Ignored log directory.

        Returns:
            Synthetic run report.

        """
        _ = timeout
        _ = logs
        healthy: bool = example.name == "alpha"
        return runner.Report(
            example=example,
            form=form,
            status="ok" if healthy else "fail",
            exit_code=0 if healthy else 1,
            seconds=0.0,
            log=log,
        )

    monkeypatch.setattr(target=runner, name="discover", value=discover_stub)
    monkeypatch.setattr(target=runner, name="launch", value=launch_stub)
    expect_equal(actual=runner.main(arguments=()), expected=1)
    expect_in(member="2/4", container=buffer.getvalue())
    expect_equal(actual=runner.main(arguments=("alpha",)), expected=0)
