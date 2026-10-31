# Copyright (c) 2026
"""Cover the exclusive todo_sync watcher lifecycle."""

from __future__ import annotations

from json import dumps, loads
from time import time
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.packages.todo_sync import watch as watch_module
from exactus.tests.common.support import expect_equal, expect_true

if TYPE_CHECKING:
    from pathlib import Path


@final
class Constants:
    """Group module-level constants.

    Attributes:
        document: Grouped module constant.
        interval: Grouped module constant.
        wakeups: Grouped module constant.

    """

    document: Final[str] = "- [ ] pending\n- [x] done\n"
    interval: Final[float] = 0.01
    wakeups: Final[int] = 2


def _write_source(tmp_path: Path) -> Path:
    """Create the watched Markdown document.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        The written document path.

    """
    source: Path = tmp_path / "todo.md"
    source.write_text(data=Constants.document, encoding="utf-8")
    return source


def _read_token(source: Path) -> str:
    """Read the watcher token recorded in the lock state.

    Args:
        source: Watched document path.

    Returns:
        The recorded watcher token.

    """
    state: dict[str, object] = loads(
        s=(watch_module.lock_path(path=source) / "state.json").read_text(
            encoding="utf-8",
        ),
    )
    return str(object=state["token"])


def test_watch_exits_on_the_token_matched_stop_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stop file carrying the watcher token ends the loop cleanly.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    lock: Path = watch_module.lock_path(path=source.resolve())

    def request_stop(seconds: float) -> None:
        """Write the token-matched stop request after one iteration.

        Args:
            seconds: Requested sleep duration (unused).

        """
        _ = seconds
        stop: Path = lock / "stop"
        if not stop.exists():
            stop.write_text(
                data=_read_token(source=source.resolve()),
                encoding="utf-8",
            )

    monkeypatch.setattr(target=watch_module, name="sleep", value=request_stop)
    expect_equal(
        actual=watch_module.watch(
            path=source,
            interval=Constants.interval,
            html=False,
        ),
        expected=0,
    )
    expect_true(condition=not lock.exists())


def test_watch_exits_on_keyboard_interrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ctrl-C ends the loop and removes the ownership lock.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    lock: Path = watch_module.lock_path(path=source.resolve())

    def interrupt(seconds: float) -> None:
        """Raise ``KeyboardInterrupt`` as if the user pressed Ctrl-C.

        Args:
            seconds: Requested sleep duration (unused).

        Raises:
            KeyboardInterrupt: Always.

        """
        _ = seconds
        raise KeyboardInterrupt

    monkeypatch.setattr(target=watch_module, name="sleep", value=interrupt)
    expect_equal(
        actual=watch_module.watch(
            path=source,
            interval=Constants.interval,
            html=False,
        ),
        expected=0,
    )
    expect_true(condition=not lock.exists())


def test_watch_records_stat_failures_and_recovers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A vanished source records the error and keeps watching.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    lock: Path = watch_module.lock_path(path=source.resolve())
    calls: list[bool] = []

    def remove_then_stop(seconds: float) -> None:
        """Remove the source once, then request a token-matched stop.

        Args:
            seconds: Requested sleep duration (unused).

        """
        _ = seconds
        calls.append(True)
        if len(calls) == 1:
            source.unlink()
            return
        stop: Path = lock / "stop"
        stop.write_text(
            data=_read_token(source=source.resolve()),
            encoding="utf-8",
        )

    monkeypatch.setattr(
        target=watch_module,
        name="sleep",
        value=remove_then_stop,
    )
    expect_equal(
        actual=watch_module.watch(
            path=source,
            interval=Constants.interval,
            html=False,
        ),
        expected=0,
    )
    expect_true(condition=len(calls) == Constants.wakeups)


def test_watch_rejects_a_nonpositive_interval(tmp_path: Path) -> None:
    """A nonpositive polling interval fails before any lock is created.

    Args:
        tmp_path: Pytest temporary directory.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    with pytest.raises(expected_exception=ValueError, match="finite"):
        watch_module.watch(path=source, interval=0.0)


def test_detached_child_reads_environment_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The child entry point forwards its environment to ``watch``.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    observed: list[tuple[Path, float, bool]] = []

    def fake_watch(*, path: Path, interval: float, html: bool) -> int:
        """Record the forwarded watcher configuration.

        Args:
            path: Document to watch.
            interval: Polling interval in seconds.
            html: Whether to maintain the HTML dashboard.

        Returns:
            Always zero.

        """
        observed.append((path, interval, html))
        return 0

    monkeypatch.setattr(target=watch_module, name="watch", value=fake_watch)
    monkeypatch.setenv(name="TODO_SYNC_PATH", value=str(object=source))
    monkeypatch.setenv(name="TODO_SYNC_INTERVAL", value="0.25")
    monkeypatch.setenv(name="TODO_SYNC_HTML", value="0")
    expect_equal(actual=watch_module.detached_child(), expected=0)
    expect_equal(actual=observed, expected=[(source, 0.25, False)])


def test_start_rejects_a_nonpositive_interval(tmp_path: Path) -> None:
    """An invalid interval fails before touching ownership state.

    Args:
        tmp_path: Pytest temporary directory.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    with pytest.raises(expected_exception=ValueError, match="finite"):
        watch_module.start(path=source, interval=0.0)


def test_start_returns_when_a_watcher_is_live(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh heartbeat short-circuits spawning a second watcher.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = _write_source(tmp_path=tmp_path)

    def live(*, path: Path) -> bool:
        """Report the watcher as live.

        Args:
            path: Document associated with the watcher.

        Returns:
            Always ``True``.

        """
        _ = path
        return True

    monkeypatch.setattr(target=watch_module, name="running", value=live)
    expect_equal(
        actual=watch_module.start(path=source, interval=Constants.interval),
        expected=0,
    )


def test_start_rejects_a_stale_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lock without a heartbeat requires manual recovery.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    resolved: Path = source.resolve()
    watch_module.lock_path(path=resolved).mkdir()

    def dead(*, path: Path) -> bool:
        """Report the watcher as absent.

        Args:
            path: Document associated with the watcher.

        Returns:
            Always ``False``.

        """
        _ = path
        return False

    monkeypatch.setattr(target=watch_module, name="running", value=dead)
    with pytest.raises(expected_exception=ValueError, match="recovery"):
        watch_module.start(path=source, interval=Constants.interval)


def test_start_returns_once_the_child_publishes_a_heartbeat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A spawned child whose heartbeat appears satisfies ``start``.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    spawned: list[bool] = []

    class ChildStub:
        """Stand-in for the detached watcher process."""

        @staticmethod
        @staticmethod
        def poll() -> None:
            """Report the child as still running."""
            return

    def fake_popen(*args: object, **kwargs: object) -> ChildStub:
        """Return the synthetic child process.

        Args:
            args: Positional spawn arguments (unused).
            kwargs: Keyword spawn arguments (unused).

        Returns:
            The child stub.

        """
        _ = args
        _ = kwargs
        spawned.append(True)
        return ChildStub()

    def running_after_spawn(*, path: Path) -> bool:
        """Report live only after the child was spawned.

        Args:
            path: Document associated with the watcher.

        Returns:
            Whether the synthetic child was spawned.

        """
        _ = path
        return bool(spawned)

    monkeypatch.setattr(target=watch_module, name="Popen", value=fake_popen)
    monkeypatch.setattr(
        target=watch_module,
        name="running",
        value=running_after_spawn,
    )

    def skip_sleep(seconds: float) -> None:
        """Accept sleep requests without delaying.

        Args:
            seconds: Requested sleep duration (unused).

        """
        _ = seconds

    monkeypatch.setattr(target=watch_module, name="sleep", value=skip_sleep)
    expect_equal(
        actual=watch_module.start(path=source, interval=Constants.interval),
        expected=0,
    )
    expect_equal(actual=spawned, expected=[True])


def test_start_fails_when_the_child_exits_early(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child that exits before its heartbeat raises ``ValueError``.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = _write_source(tmp_path=tmp_path)

    class ChildStub:
        """Stand-in for a watcher child that exits immediately."""

        @staticmethod
        def poll() -> int:
            """Report the child as exited.

            Returns:
                A nonzero exit status.

            """
            return 1

    def fake_popen(*args: object, **kwargs: object) -> ChildStub:
        """Return the exited child stub.

        Args:
            args: Positional spawn arguments (unused).
            kwargs: Keyword spawn arguments (unused).

        Returns:
            The child stub.

        """
        _ = args
        _ = kwargs
        return ChildStub()

    def dead(*, path: Path) -> bool:
        """Report no live watcher.

        Args:
            path: Document associated with the watcher.

        Returns:
            Always ``False``.

        """
        _ = path
        return False

    monkeypatch.setattr(target=watch_module, name="Popen", value=fake_popen)
    monkeypatch.setattr(target=watch_module, name="running", value=dead)
    with pytest.raises(expected_exception=ValueError, match="failed"):
        watch_module.start(path=source, interval=Constants.interval)


def test_start_fails_when_the_heartbeat_never_arrives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing heartbeat past the deadline terminates the child.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    events: list[str] = []

    class ChildStub:
        """Stand-in for a watcher child that never reports ready."""

        @staticmethod
        def poll() -> None:
            """Report the child as still running."""
            return

        @staticmethod
        def terminate() -> None:
            """Record the termination request."""
            events.append("terminate")

        @staticmethod
        def wait(*, timeout: float) -> int:
            """Record the reap wait.

            Args:
                timeout: Wait bound in seconds.

            Returns:
                Always zero.

            """
            _ = timeout
            events.append("wait")
            return 0

    def fake_popen(*args: object, **kwargs: object) -> ChildStub:
        """Return the unresponsive child stub.

        Args:
            args: Positional spawn arguments (unused).
            kwargs: Keyword spawn arguments (unused).

        Returns:
            The child stub.

        """
        _ = args
        _ = kwargs
        return ChildStub()

    ticks: list[float] = [100.0]

    def fake_monotonic() -> float:
        """Advance past the startup deadline on the second read.

        Returns:
            Increasing synthetic timestamps.

        """
        ticks[0] += 10.0
        return ticks[0]

    def dead(*, path: Path) -> bool:
        """Report no live watcher.

        Args:
            path: Document associated with the watcher.

        Returns:
            Always ``False``.

        """
        _ = path
        return False

    monkeypatch.setattr(target=watch_module, name="Popen", value=fake_popen)
    monkeypatch.setattr(
        target=watch_module,
        name="monotonic",
        value=fake_monotonic,
    )
    monkeypatch.setattr(target=watch_module, name="running", value=dead)
    with pytest.raises(expected_exception=ValueError, match="timed out"):
        watch_module.start(path=source, interval=Constants.interval)
    expect_equal(actual=events, expected=["terminate", "wait"])


def test_stop_returns_when_no_lock_exists(tmp_path: Path) -> None:
    """A document without a lock has nothing to stop.

    Args:
        tmp_path: Pytest temporary directory.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    expect_equal(actual=watch_module.stop(path=source), expected=0)


def test_stop_rejects_a_stale_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lock without a fresh heartbeat fails closed.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    watch_module.lock_path(path=source.resolve()).mkdir()

    def dead(*, path: Path) -> bool:
        """Report no live watcher.

        Args:
            path: Document associated with the watcher.

        Returns:
            Always ``False``.

        """
        _ = path
        return False

    monkeypatch.setattr(target=watch_module, name="running", value=dead)
    with pytest.raises(expected_exception=ValueError, match="killed"):
        watch_module.stop(path=source)


def test_stop_writes_the_token_and_returns_when_the_lock_closes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stop request carries the stored token and waits for cleanup.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    resolved: Path = source.resolve()
    lock: Path = watch_module.lock_path(path=resolved)
    lock.mkdir()
    marker: str = "watcher-marker"
    (lock / "state.json").write_text(
        data=dumps(
            obj={
                "pid": 4321,
                "path": str(object=resolved),
                "token": marker,
                "heartbeat": time(),
            },
        ),
        encoding="utf-8",
    )
    removed: list[bool] = []

    def drop_lock(seconds: float) -> None:
        """Remove the lock as the exiting watcher would.

        Args:
            seconds: Requested sleep duration (unused).

        """
        _ = seconds
        removed.append(True)
        (lock / "stop").unlink(missing_ok=True)
        (lock / "state.json").unlink(missing_ok=True)
        lock.rmdir()

    monkeypatch.setattr(target=watch_module, name="sleep", value=drop_lock)
    expect_equal(actual=watch_module.stop(path=source), expected=0)
    expect_equal(actual=removed, expected=[True])


def test_stop_fails_when_the_watcher_ignores_the_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persistent lock past the deadline raises ``ValueError``.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = _write_source(tmp_path=tmp_path)
    resolved: Path = source.resolve()
    lock: Path = watch_module.lock_path(path=resolved)
    lock.mkdir()
    (lock / "state.json").write_text(
        data=dumps(
            obj={
                "pid": 4321,
                "path": str(object=resolved),
                "token": "watcher-marker",
                "heartbeat": time(),
            },
        ),
        encoding="utf-8",
    )
    ticks: list[float] = [100.0]

    def fake_monotonic() -> float:
        """Advance past the shutdown deadline on each read.

        Returns:
            Increasing synthetic timestamps.

        """
        ticks[0] += 10.0
        return ticks[0]

    monkeypatch.setattr(
        target=watch_module,
        name="monotonic",
        value=fake_monotonic,
    )
    with pytest.raises(expected_exception=ValueError, match="not exited"):
        watch_module.stop(path=source)
