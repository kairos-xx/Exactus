# Copyright (c) 2026
"""Process-tree control and JSON state primitives."""

from __future__ import annotations

from importlib import import_module
from os import getpid
from subprocess import PIPE, Popen
from sys import executable
from textwrap import dedent
from time import monotonic, sleep
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import (
    Constant,
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_equal,
    expect_true,
    private_call,
    require,
)
from exactus.tools.common import process_control as pc

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from types import ModuleType


def _wait(predicate: Callable[[], bool], seconds: float = 10.0) -> bool:
    """Poll until ``predicate`` holds.

    Args:
        predicate: Condition to await.
        seconds: Maximum wait.

    Returns:
        Whether the condition became true.

    """
    deadline: float = monotonic() + seconds
    while monotonic() < deadline:
        if predicate():
            return True
        sleep(0.05)
    return False


def test_process_json_roundtrip(tmp_path: Path) -> None:
    """JSON helpers write atomically and tolerate bad content.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "sub" / "x.json"
    pc.write_json(path=target, payload={"a": 1})
    expect_equal(actual=pc.read_json(path=target), expected={"a": 1})
    expect_none(value=pc.read_json(path=tmp_path / "missing.json"))
    target.write_text(data="[1]", encoding="utf-8")
    expect_none(value=pc.read_json(path=target))
    target.write_text(data="{bad", encoding="utf-8")
    expect_none(value=pc.read_json(path=target))
    expect_equal(actual=len(pc.new_run_id()), expected=32)


def test_process_exists_and_parent_map() -> None:
    """Liveness checks and the parent map include this process."""
    expect_true(condition=pc.process_exists(pid=getpid()))
    expect_false(condition=pc.process_exists(pid=0))
    expect_false(condition=pc.process_exists(pid=-5))
    expect_in(
        member=getpid(),
        container=cast(
            typ="dict[int, int]",
            val=private_call(owner=pc, name="_parent_map"),
        ),
    )


def test_parent_map_without_ps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without /proc, ``ps`` output is parsed and failures degrade.

    Args:
        monkeypatch: Pytest patching helper.

    """
    real_path: type[Path] = pc.Path

    class NoProc:
        """Stand-in for ``/proc`` that is never a directory."""

        @staticmethod
        def is_dir() -> bool:
            """Hide /proc.

            Returns:
                Always false.

            """
            return False

    def make_path(value: str) -> NoProc | Path:
        """Return the fake for ``/proc`` and a real path otherwise.

        Args:
            value: Requested path text.

        Returns:
            The substituted or real path.

        """
        return NoProc() if value == "/proc" else real_path(value)

    monkeypatch.setattr(target=pc, name="Path", value=make_path)

    class Done:
        """Canned ``ps`` result."""

        stdout: str = "1 0\n 22 1\nbad line here\nx y\n"

    monkeypatch.setattr(
        target=pc,
        name="subprocess_run",
        value=Constant(value=Done()),
    )
    expect_equal(
        actual=private_call(owner=pc, name="_parent_map"),
        expected={1: 0, 22: 1},
    )

    def boom(**_: object) -> None:
        """Fail like a missing ``ps`` binary.

        Args:
            **_: Ignored options.

        Raises:
            OSError: Always.

        """
        raise OSError

    monkeypatch.setattr(target=pc, name="subprocess_run", value=boom)
    expect_equal(
        actual=private_call(owner=pc, name="_parent_map"),
        expected={},
    )


def test_terminate_tree_kills_children() -> None:
    """A process and its descendants are terminated."""
    script: str = (
        "import subprocess,sys,time;"
        "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
        "time.sleep(60)"
    )
    parent: Popen[bytes] = Popen(args=[executable, "-c", script])
    try:
        expect_true(
            condition=_wait(
                predicate=lambda: len(pc.descendants(pid=parent.pid)) >= 1,
            ),
        )
        kids: tuple[int, ...] = pc.descendants(pid=parent.pid)
        pc.terminate_tree(pid=parent.pid)
        parent.wait(timeout=10)
        expect_true(
            condition=_wait(
                predicate=lambda: (
                    not any(pc.process_exists(pid=k) for k in kids)
                ),
            ),
        )
    finally:
        parent.kill()
    pc.terminate_tree(pid=0)
    pc.terminate_tree(pid=getpid())


def test_terminate_tree_escalates_to_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Processes ignoring SIGTERM are killed.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=pc.Constants,
        name="term_wait_seconds",
        value=0.2,
    )
    script: str = (
        "import signal,time;"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
        "print('up',flush=True);time.sleep(60)"
    )
    stubborn: Popen[str] = Popen(
        args=[executable, "-c", script],
        stdout=PIPE,
        text=True,
    )
    try:
        expect_equal(
            actual=require(value=stubborn.stdout).readline().strip(),
            expected="up",
        )
        pc.terminate_tree(pid=stubborn.pid)
        expect_not_equal(actual=stubborn.wait(timeout=10), expected=0)
    finally:
        stubborn.kill()


def test_parent_map_from_proc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Linux-style /proc tree is read, skipping malformed entries.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    proc: Path = tmp_path / "proc"
    for name, status in {
        "10": "Name: a\nPPid:\t1\n",
        "11": "Name: b\n",
        "12": "PPid: x\n",
        "13": "PPid: 10\n",
    }.items():
        (proc / name).mkdir(parents=True)
        (proc / name / "status").write_text(data=status, encoding="utf-8")
    real: type[Path] = pc.Path

    def fake_path(value: str) -> Path:
        """Redirect ``/proc`` to the fixture tree.

        Args:
            value: Requested path.

        Returns:
            The substituted path.

        """
        return proc if value == "/proc" else real(value)

    monkeypatch.setattr(target=pc, name="Path", value=fake_path)
    expect_equal(
        actual=private_call(owner=pc, name="_parent_map"),
        expected={10: 1, 13: 10},
    )


def test_replaced_exactus_exits_with_notice() -> None:
    """Exit with a readable notice rather than a signal death.

    Raises:
        RuntimeError: When the readiness stream is missing.

    """
    script: str = dedent(
        text=(
            "    import time\n    from exactus.__main__ import _install_signal"
            "_handlers\n    _install_signal_handlers()\n    print('ready',flus"
            "h=True)\n    time.sleep(60)\n    "
        ),
    )
    process: Popen[bytes] = Popen(
        args=[executable, "-c", script],
        stdout=PIPE,
        stderr=PIPE,
    )
    try:
        if process.stdout is None:
            msg: str = "Missing readiness stream"
            raise RuntimeError(msg)
        expect_equal(actual=process.stdout.readline(), expected=b"ready\n")
        pc.terminate_tree(pid=process.pid, replaced=True)
        _, error = process.communicate(timeout=10)
        expect_equal(actual=process.returncode, expected=130)
        expect_in(member=b"another exactus started", container=error)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)


@pytest.fixture(
    autouse=True,
    params=(
        "exactus.tools.common.process_control",
        "exactus.tools.actions.process_control",
        "exactus.packages.package.process_control",
        "exactus.packages.server.process_control",
    ),
)
def subsystem_contract(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the shared behavior in every shipped subsystem copy.

    Args:
        request: Parametrized implementation module name.
        monkeypatch: Isolated module binding substitutions.

    """
    implementation: ModuleType = import_module(name=request.param)
    monkeypatch.setattr(
        target=import_module(name=__name__),
        name="pc",
        value=implementation,
    )
