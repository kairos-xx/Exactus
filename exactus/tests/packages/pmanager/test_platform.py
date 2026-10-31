# Copyright (c) 2026 João Lopes.
"""Cross-platform backend contract tests."""

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from exactus.packages.pmanager import _platform as module
from exactus.packages.pmanager._platform import (
    PlatformError,
    PosixBackend,
    WindowsBackend,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_true,
    require_type,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


def test_posix_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise POSIX discovery, detach, and signal operations.

    Args:
        monkeypatch: Test input.

    """
    result: SimpleNamespace = SimpleNamespace(
        stdout="1 cmd one\n\ninvalid\n2 cmd two\n",
    )

    def _run_stub(**_kwargs: object) -> SimpleNamespace:
        """Return the captured command result.

        Args:
            **_kwargs: Ignored run arguments.

        Returns:
            Constructed test value.

        """
        return result

    monkeypatch.setattr(target=module, name="run", value=_run_stub)
    monkeypatch.setattr(
        target=PosixBackend,
        name="_proc_root",
        value=Path("/missing-proc-fixture"),
    )
    signals: list[tuple[int, int]] = []

    def _kill(pid: int, signal: int) -> None:
        """Record each signal sent to a process.

        Args:
            pid: Test input.
            signal: Test input.

        """
        signals.append((pid, signal))

    monkeypatch.setattr(target=module, name="kill", value=_kill)
    backend: PosixBackend | WindowsBackend = PosixBackend()
    expect_equal(
        actual=backend.command_lines(),
        expected=((1, "cmd one"), (2, "cmd two")),
    )
    expect_equal(
        actual=backend.detached_kwargs(),
        expected={"start_new_session": True, "close_fds": True},
    )
    backend.pause(pid=7)
    backend.resume(pid=7)
    backend.terminate(pid=7)
    expect_equal(actual=len(signals), expected=3)


def test_posix_proc_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discover process command lines without requiring a ``ps`` binary.

    Args:
        tmp_path: Isolated synthetic proc filesystem.
        monkeypatch: Test input.

    """
    first: Path = tmp_path / "12"
    second: Path = tmp_path / "3"
    ignored: Path = tmp_path / "self"
    for directory in (first, second, ignored):
        directory.mkdir()
    _ = (first / "cmdline").write_bytes(data=b"python\0-m\0worker\0")
    _ = (second / "cmdline").write_bytes(data=b"")
    _ = (ignored / "cmdline").write_bytes(data=b"ignored\0")
    monkeypatch.setattr(target=PosixBackend, name="_proc_root", value=tmp_path)
    backend: PosixBackend = PosixBackend()
    expect_equal(
        actual=backend.command_lines(),
        expected=((12, "python -m worker"),),
    )


def test_windows_discovery_and_detach(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise Windows CIM discovery and detached flags.

    Args:
        monkeypatch: Test input.

    """
    outputs: Iterator[SimpleNamespace] = iter(
        (
            SimpleNamespace(returncode=1, stdout=""),
            SimpleNamespace(
                returncode=0,
                stdout='{"ProcessId":3,"CommandLine":"python worker"}',
            ),
            SimpleNamespace(
                returncode=0,
                stdout=(
                    '[{"ProcessId":4,"CommandLine":"a"},{"ProcessId":5,"Comman'
                    'dLine":null}]'
                ),
            ),
        ),
    )

    def _run_stub(**_kwargs: object) -> SimpleNamespace:
        """Yield the next scripted command result.

        Args:
            **_kwargs: Ignored run arguments.

        Returns:
            Constructed test value.

        """
        return next(outputs)

    monkeypatch.setattr(target=module, name="run", value=_run_stub)
    backend: WindowsBackend = WindowsBackend()
    expect_equal(actual=backend.command_lines(), expected=())
    expect_equal(
        actual=backend.command_lines(),
        expected=((3, "python worker"),),
    )
    expect_equal(actual=backend.command_lines(), expected=((4, "a"), (5, "")))
    settings: dict[str, bool | int] = backend.detached_kwargs()
    flags: bool | int = settings["creationflags"]
    flags = require_type(value=flags, kind=int)
    expect_true(condition=(flags & 8) != 0)
    expect_true(condition=(flags & 512) != 0)
    expect_true(condition=settings["close_fds"] is True)


def test_windows_pause_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise Windows suspend/resume success and failures.

    Args:
        monkeypatch: Test input.

    """
    results: Iterator[SimpleNamespace] = iter(
        (
            SimpleNamespace(returncode=0),
            SimpleNamespace(returncode=0),
            SimpleNamespace(returncode=1),
        ),
    )

    def _run_stub(**_kwargs: object) -> SimpleNamespace:
        """Yield the next scripted command result.

        Args:
            **_kwargs: Ignored run arguments.

        Returns:
            Constructed test value.

        """
        return next(results)

    monkeypatch.setattr(target=module, name="run", value=_run_stub)
    backend: WindowsBackend = WindowsBackend()
    backend.pause(pid=10)
    backend.resume(pid=10)
    with pytest.raises(expected_exception=PlatformError):
        backend.pause(pid=10)
    with pytest.raises(expected_exception=PlatformError):
        backend.powershell_process_action(pid=10, method="Bad")


def test_windows_terminate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise Windows tree termination success and failure.

    Args:
        monkeypatch: Test input.

    """

    class Process:
        """Minimal taskkill process."""

        calls: int = 0

        @classmethod
        def wait(cls) -> int:
            """Return alternating taskkill results.

            Returns:
                Alternating taskkill result.

            """
            cls.calls += 1
            return 0 if cls.calls == 1 else 1

    def _popen(**_kwargs: object) -> Process:
        """Return the alternating taskkill stub.

        Args:
            **_kwargs: Ignored spawn arguments.

        Returns:
            Constructed test value.

        """
        return Process()

    monkeypatch.setattr(target=module, name="Popen", value=_popen)
    backend: WindowsBackend = WindowsBackend()
    backend.terminate(pid=11)
    with pytest.raises(expected_exception=PlatformError):
        backend.terminate(pid=11)
