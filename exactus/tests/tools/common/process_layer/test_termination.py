# Copyright (c) 2026
"""Verified-tree process termination behavior."""

from pathlib import Path
from sqlite3 import connect
from subprocess import DEVNULL, Popen
from sys import executable
from time import sleep
from typing import Final, cast, final

import pytest
from psutil import Error, Process

from exactus.tests.common.support import (
    expect_equal,
    expect_true,
    private_call,
)
from exactus.tools.common.process_layer.process_control import RunIdentity
from exactus.tools.common.process_layer.process_termination import (
    ProcessTerminator,
    TerminationResult,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        tree_min: Grouped module constant.
        stale_pid: Grouped module constant.
        schema: Grouped module constant.

    """

    tree_min: Final[int] = 2
    stale_pid: Final[int] = 999999
    schema: Final[str] = (
        "CREATE TABLE runs "
        "(status TEXT, run_id TEXT, pipeline_run_id TEXT, pid INTEGER)"
    )


def _spawn_sleeper() -> Popen[bytes]:
    """Spawn a detached child that stays alive until terminated.

    Returns:
        Detached sleeping child process.

    """
    return Popen(
        args=[executable, "-c", "import time; sleep(120)"],
        stdin=DEVNULL,
        stdout=DEVNULL,
        stderr=DEVNULL,
    )


def _identity(*, pid: int, created_at: float, runs_db: Path) -> RunIdentity:
    """Build a verified identity for a live spawned child.

    Args:
        pid: Spawned child process identifier.
        created_at: Child process creation timestamp.
        runs_db: Runtime database path recorded in the identity.

    Returns:
        Run identity describing the spawned child.

    """
    return RunIdentity(
        root_pid=pid,
        run_id="run-test",
        runs_db=str(object=runs_db),
        created_at=created_at,
        instance_id="instance-test",
    )


def _seed_runs_db(database: Path, *, pids: tuple[int, ...]) -> None:
    """Record RUNNING rows in a minimal runtime database.

    Args:
        database: Runtime database to create.
        pids: Process identifiers recorded as running.

    """
    with connect(database=database) as connection:
        _ = connection.execute(Constants.schema)
        for pid in pids:
            _ = connection.execute(
                "INSERT INTO runs VALUES ('RUNNING', 'run-test', NULL, ?)",
                (pid,),
            )
        connection.commit()


def test_terminator_rejects_nonfinite_timeouts() -> None:
    """Nonfinite grace periods are rejected at construction."""
    with pytest.raises(expected_exception=ValueError, match="finite"):
        _ = ProcessTerminator(grace_period=float("inf"))
    with pytest.raises(expected_exception=ValueError, match="finite"):
        _ = ProcessTerminator(kill_timeout=-1.0)


def test_result_properties() -> None:
    """Result counters expose aggregate termination outcomes."""
    result: TerminationResult = TerminationResult(
        root_pid=1,
        run_id="r",
        runs_db="db",
        discovered=(1, 2),
        terminated=(2,),
        killed=(3,),
        already_exited=(),
        failed=(),
        skipped=(),
        duration=0.1,
    )
    expect_true(condition=result.success)
    expect_equal(actual=result.count, expected=2)
    failing: TerminationResult = TerminationResult(
        root_pid=1,
        run_id="r",
        runs_db="db",
        discovered=(),
        terminated=(),
        killed=(),
        already_exited=(),
        failed=(9,),
        skipped=(),
        duration=0.0,
    )
    expect_true(condition=not failing.success)


def test_terminate_refuses_self() -> None:
    """The terminator never targets its own process."""
    identity: RunIdentity = RunIdentity(
        root_pid=Process().pid,
        run_id="self",
        runs_db="missing.db",
        created_at=Process().create_time(),
        instance_id="i",
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="current process",
    ):
        _ = ProcessTerminator().terminate(identity=identity)


def test_terminate_absent_root_marks_exited(tmp_path: Path) -> None:
    """A dead root is reported as already exited, never signalled.

    Args:
        tmp_path: Isolated filesystem root.

    """
    popen: Popen[bytes] = _spawn_sleeper()
    created_at: float = Process(pid=popen.pid).create_time()
    popen.kill()
    popen.wait()
    identity: RunIdentity = _identity(
        pid=popen.pid,
        created_at=created_at + 9999.0,
        runs_db=tmp_path / "runs.db",
    )
    result: TerminationResult = ProcessTerminator().terminate(
        identity=identity,
    )
    expect_equal(actual=result.already_exited, expected=(popen.pid,))
    expect_equal(actual=result.terminated, expected=())


def test_terminate_kills_verified_tree(tmp_path: Path) -> None:
    """A live verified process tree is terminated end to end.

    Args:
        tmp_path: Isolated filesystem root.

    """
    parent: Popen[bytes] = Popen(
        args=[
            executable,
            "-c",
            (
                "import subprocess,sys,time;"
                "subprocess.Popen([sys.executable,'-c','import time;"
                "time.sleep(120)']);"
                "time.sleep(120)"
            ),
        ],
        stdin=DEVNULL,
        stdout=DEVNULL,
        stderr=DEVNULL,
    )
    try:
        root: Process = Process(pid=parent.pid)
        grandchildren: int = 0
        for _ in range(50):
            try:
                grandchildren = len(root.children(recursive=True))
            except (Error, OSError):
                grandchildren = 0
            if grandchildren:
                break
            sleep(0.1)
        identity: RunIdentity = _identity(
            pid=parent.pid,
            created_at=root.create_time(),
            runs_db=tmp_path / "runs.db",
        )
        result: TerminationResult = ProcessTerminator(
            grace_period=1.0,
            kill_timeout=3.0,
        ).terminate(identity=identity)
        expect_true(
            condition=result.success,
            message="tree termination failed",
        )
        expect_true(condition=result.count >= 1)
        if grandchildren:
            expect_true(
                condition=len(result.discovered) >= Constants.tree_min,
                message="grandchild missing from discovered tree",
            )
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait()


def test_database_pids_outside_tree_are_skipped(tmp_path: Path) -> None:
    """Database-listed PIDs outside the tree land in ``skipped``.

    Args:
        tmp_path: Isolated filesystem root.

    """
    popen: Popen[bytes] = _spawn_sleeper()
    try:
        database: Path = tmp_path / "runs.db"
        _seed_runs_db(database=database, pids=(popen.pid, Constants.stale_pid))
        identity: RunIdentity = _identity(
            pid=popen.pid,
            created_at=Process(pid=popen.pid).create_time(),
            runs_db=database,
        )
        result: TerminationResult = ProcessTerminator(
            grace_period=1.0,
        ).terminate(identity=identity)
        expect_true(condition=Constants.stale_pid in result.skipped)
    finally:
        if popen.poll() is None:
            popen.kill()
            popen.wait()


def test_missing_database_yields_empty_pid_set(tmp_path: Path) -> None:
    """A nonexistent runtime database contributes no PIDs.

    Args:
        tmp_path: Isolated filesystem root.

    """
    pids: set[int] = cast(
        typ="set[int]",
        val=private_call(
            owner=ProcessTerminator,
            name="_database_pids",
            identity=RunIdentity(
                root_pid=1,
                run_id="r",
                runs_db=str(object=tmp_path / "absent.db"),
                created_at=0.0,
                instance_id="i",
            ),
        ),
    )
    expect_equal(actual=pids, expected=set[int]())
