# Copyright (c) 2026 Project contributors
"""Exclusive, cooperative watchers: a persisted PID never authorizes a kill."""

from json import dumps, loads
from math import isfinite
from os import environ, getpid, stat_result
from pathlib import Path
from subprocess import DEVNULL, Popen
from sys import executable
from time import monotonic, sleep, time
from typing import Final, cast
from uuid import uuid4

from .core import atomic_write, completion
from .sync import synchronize

type StateValue = (
    str | int | float | bool | list[StateValue] | dict[str, StateValue] | None
)


class Constants:
    """Watcher timing policy.

    Attributes:
        STALE_SECONDS: Maximum heartbeat age accepted as a live watcher.

    """

    STALE_SECONDS: Final[int] = 10


def lock_path(*, path: Path) -> Path:
    """Return the atomic ownership directory associated with one source.

    Args:
        path: Source document associated with the watcher.

    Returns:
        Sibling directory holding ownership and diagnostic state.

    """
    return path.with_name(name=f".{path.name}.todo-sync")


def read_state(*, path: Path) -> dict[str, StateValue]:
    """Read diagnostic watcher state without trusting a stored PID.

    Args:
        path: Source document whose ownership directory is inspected.

    Returns:
        JSON state mapping, or an empty mapping for missing or invalid state.

    """
    try:
        data: StateValue = loads(
            s=(lock_path(path=path) / "state.json").read_text(
                encoding="utf-8",
            ),
        )
    except (OSError, ValueError):
        return {}
    return (
        cast(typ="dict[str, StateValue]", val=data)
        if isinstance(data, dict)
        else {}
    )


def running(*, path: Path) -> bool:
    """Require a fresh heartbeat, positive PID and matching source.

    Args:
        path: Source document whose watcher identity is checked.

    Returns:
        Whether diagnostic state identifies a recent matching watcher.

    """
    state: dict[str, StateValue] = read_state(path=path)
    heartbeat: StateValue = state.get("heartbeat")
    pid: StateValue = state.get("pid")
    return (
        isinstance(pid, int)
        and not isinstance(pid, bool)
        and pid > 0
        and isinstance(heartbeat, (int, float))
        and not isinstance(heartbeat, bool)
        and isfinite(heartbeat)
        and 0 <= time() - heartbeat <= Constants.STALE_SECONDS
        and state.get("path") == str(object=path.resolve())
        and isinstance(state.get("token"), str)
    )


def watch(*, path: Path, interval: float = 0.5, html: bool = True) -> int:
    """Synchronize in the foreground until Ctrl-C or an owned stop request.

    Directory creation reserves a single watcher. Stale or malformed locks
    fail closed and require explicit manual recovery, never automatic killing.

    Args:
        path: Existing Markdown document to synchronize.
        interval: Finite positive polling interval in seconds.
        html: Whether to maintain the sibling HTML dashboard.

    Returns:
        Zero after Ctrl-C or a token-matched cooperative stop request.

    Raises:
        ValueError: If the polling interval is nonpositive or nonfinite.

    """
    if not isfinite(interval) or interval <= 0:
        msg: str = "Watch interval must be finite and greater than zero."
        raise ValueError(msg)
    path = path.resolve(strict=True)
    lock: Path = lock_path(path=path)
    lock.mkdir()
    token: str = uuid4().hex
    state: dict[str, StateValue] = {
        "pid": getpid(),
        "path": str(object=path),
        "token": token,
        "heartbeat": time(),
        "percent": 0.0,
        "percent_delta": 0.0,
        "last_update": 0.0,
        "error": "",
    }
    signature: tuple[int, int, int] | None = None
    previous: float | None = None
    try:
        while True:
            request: Path = lock / "stop"
            if (
                request.exists()
                and request.read_text(encoding="utf-8") == token
            ):
                return 0
            try:
                stat: stat_result = path.stat()
                current: tuple[int, int, int] = (
                    stat.st_ino,
                    stat.st_size,
                    stat.st_mtime_ns,
                )
                # Repair missing HTML even when Markdown is unchanged.
                if current != signature or (
                    html and not path.with_suffix(suffix=".html").exists()
                ):
                    synchronize(path=path, html=html)
                    percent: float = completion(
                        text=path.read_text(encoding="utf-8"),
                    )
                    state["percent_delta"] = (
                        percent - previous if previous is not None else 0.0
                    )
                    state["percent"] = percent
                    previous = percent
                    state["last_update"] = time()
                    state["error"] = ""
                    stat = path.stat()
                    signature = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
            except (OSError, ValueError) as exc:
                state["error"] = str(object=exc)
            state["heartbeat"] = time()
            atomic_write(
                path=lock / "state.json",
                text=dumps(obj=state, indent=2) + "\n",
            )
            sleep(interval)
    except KeyboardInterrupt:
        return 0
    finally:
        # Only files belonging to this exclusive watcher are removed.
        (lock / "stop").unlink(missing_ok=True)
        (lock / "state.json").unlink(missing_ok=True)
        lock.rmdir()


def detached_child() -> int:
    """Run the fixed child entry point with environment-carried configuration.

    Data is never interpolated into executable Python or a shell command.

    Returns:
        Exit status of the foreground watcher configured by the parent.

    """
    return watch(
        path=Path(environ["TODO_SYNC_PATH"]),
        interval=float(environ["TODO_SYNC_INTERVAL"]),
        html=environ["TODO_SYNC_HTML"] == "1",
    )


def start(*, path: Path, interval: float = 0.5, html: bool = True) -> int:
    """Detach a watcher, waiting for its ready heartbeat or startup failure.

    Args:
        path: Existing source document to watch.
        interval: Finite positive polling interval in seconds.
        html: Whether the child maintains the sibling HTML dashboard.

    Returns:
        Zero when an existing watcher is live or the new child is ready.

    Raises:
        ValueError: If the interval is invalid, ownership requires recovery,
            or the owned child fails to publish a ready heartbeat.

    """
    if not isfinite(interval) or interval <= 0:
        msg: str = "Watch interval must be finite and greater than zero."
        raise ValueError(msg)
    path = path.resolve(strict=True)
    if running(path=path):
        return 0
    if lock_path(path=path).exists():
        msg = (
            "Watcher lock exists without a fresh heartbeat; "
            "inspect it before manual recovery."
        )
        raise ValueError(msg)
    environment: dict[str, str] = dict(environ)
    environment["TODO_SYNC_PATH"] = str(object=path)
    environment["TODO_SYNC_INTERVAL"] = str(object=interval)
    environment["TODO_SYNC_HTML"] = "1" if html else "0"
    log: Path = path.with_name(name=f".{path.name}.todo-sync.log")
    with log.open(mode="ab") as sink:
        process: Popen[bytes] = Popen(
            args=[
                executable,
                "-c",
                (
                    "from exactus.packages.todo_sync.watch import "
                    "detached_child; "
                    "raise SystemExit(detached_child())"
                ),
            ],
            env=environment,
            cwd=Path(__file__).resolve().parents[3],
            stdin=DEVNULL,
            stdout=sink,
            stderr=sink,
            start_new_session=True,
        )
    deadline: float = monotonic() + 5
    while monotonic() < deadline:
        if process.poll() is not None:
            msg = f"Watcher startup failed; inspect {log}."
            raise ValueError(msg)
        if running(path=path):
            return 0
        sleep(0.05)
    # This handle is the child we just created, not an untrusted persisted PID.
    process.terminate()
    process.wait(timeout=5)
    msg = f"Watcher startup timed out; inspect {log}."
    raise ValueError(msg)


def stop(*, path: Path) -> int:
    """Request token-matched shutdown; never signal a PID read from disk.

    Args:
        path: Source document associated with the watcher to stop.

    Returns:
        Zero when no watcher exists or the owned watcher exits.

    Raises:
        ValueError: If ownership is stale or shutdown misses its deadline.

    """
    path = path.resolve()
    if not lock_path(path=path).exists():
        return 0
    if not running(path=path):
        msg: str = (
            "Watcher heartbeat is absent or stale; no process was killed."
        )
        raise ValueError(msg)
    state: dict[str, StateValue] = read_state(path=path)
    atomic_write(
        path=lock_path(path=path) / "stop",
        text=str(object=state["token"]),
    )
    deadline: float = monotonic() + 5
    while monotonic() < deadline:
        if not lock_path(path=path).exists():
            return 0
        sleep(0.05)
    msg = (
        "Stop requested but watcher has not exited yet; no process was killed."
    )
    raise ValueError(msg)
