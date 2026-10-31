# Copyright (c) 2026
"""Cross-invocation exactus ownership and process termination primitives."""

from __future__ import annotations

from contextlib import suppress
from json import JSONDecodeError, dumps, loads
from os import _exit, getpid, isatty, kill, write
from pathlib import Path
from signal import SIGKILL, SIGTERM
from subprocess import CompletedProcess, TimeoutExpired
from subprocess import run as subprocess_run
from tempfile import gettempdir
from time import monotonic, sleep, time
from typing import TYPE_CHECKING, Final, cast, final
from uuid import uuid4

if TYPE_CHECKING:
    from .json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        term_wait_seconds: Grouped module constant.
        poll_seconds: Grouped module constant.
        notice_lifetime_seconds: Grouped module constant.

    """

    term_wait_seconds: Final[float] = 3.0
    poll_seconds: Final[float] = 0.05
    notice_lifetime_seconds: Final[float] = 30.0


def new_run_id() -> str:
    """Return new run id.

    Returns:
        The resulting value.

    """
    return uuid4().hex


def process_exists(*, pid: int) -> bool:
    """Return process exists.

    Args:
        pid: Pid.

    Returns:
        The resulting value.

    """
    if pid <= 0:
        return False
    try:
        kill(pid, 0)
    except OSError:
        return False
    return True


def _parent_map() -> dict[int, int]:
    """Return the child-to-parent process map for this platform.

    Linux exposes ``/proc``; macOS and other POSIX systems answer the
    same question through ``ps``. Either source failing yields an empty
    map so callers degrade to signaling only the root process.

    Returns:
        Mapping of each running process identifier to its parent.

    """
    proc: Path = Path("/proc")
    if proc.is_dir():
        parents: dict[int, int] = {}
        for status in proc.glob(pattern="[0-9]*/status"):
            try:
                child: int = int(status.parent.name)
                parent: int = next(
                    int(line.split()[1])
                    for line in status.read_text(encoding="utf-8").splitlines()
                    if line.startswith("PPid:")
                )
            except (OSError, StopIteration, ValueError):
                continue
            parents[child] = parent
        return parents
    try:
        completed: CompletedProcess[str] = subprocess_run(
            args=("ps", "-eo", "pid=,ppid="),
            check=False,
            capture_output=True,
            text=True,
            timeout=10.0,
        )
    except (OSError, TimeoutExpired):
        return {}
    parents = {}
    for line in completed.stdout.splitlines():
        parts: list[str] = line.split()
        try:
            pid_text, ppid_text = parts
        except ValueError:
            continue
        if pid_text.isdecimal() and ppid_text.isdecimal():
            parents[int(pid_text)] = int(ppid_text)
    return parents


def descendants(*, pid: int) -> tuple[int, ...]:
    """Return descendants.

    Args:
        pid: Pid.

    Returns:
        The resulting value.

    """
    parents: dict[int, int] = _parent_map()
    found: list[int] = []
    frontier: list[int] = [pid]
    while frontier:
        parent: int = frontier.pop()
        children: list[int] = [
            child for child, owner in parents.items() if owner == parent
        ]
        found.extend(children)
        frontier.extend(children)
    return tuple(reversed(found))


def exit_if_replaced(*, output_fd: int = 2) -> None:
    """Exit normally with a notice when another exactus replaced this run.

    Args:
        output_fd: Original terminal stream descriptor.

    """
    marker: Path = Path(gettempdir()) / f"exactus-replaced-{getpid()}.json"
    payload: dict[str, JsonValue] | None = read_json(path=marker)
    if payload is None:
        return
    with suppress(OSError):
        marker.unlink()
    created: (
        bool
        | dict[str, JsonValue]
        | float
        | int
        | list[JsonValue]
        | str
        | None
    ) = payload.get("created_at")
    if (
        not isinstance(created, int | float)
        or not 0 <= time() - created < Constants.notice_lifetime_seconds
    ):
        return
    with suppress(OSError):
        if isatty(output_fd):
            _ = write(output_fd, b"\x1b[?25h")
        _ = write(output_fd, b"\nExactus stopped: another exactus started.\n")
    _exit(status=130)


def terminate_tree(
    *,
    pid: int,
    include_root: bool = True,
    replaced: bool = False,
) -> None:
    """Handle terminate tree.

    Args:
        pid: Pid.
        include_root: Include root.
        replaced: Notify the root that another exactus replaced it.

    """
    if pid <= 0 or (include_root and pid == getpid()):
        return
    targets: tuple[int, ...] = (
        *descendants(pid=pid),
        *((pid,) if include_root else ()),
    )
    marker: Path = Path(gettempdir()) / f"exactus-replaced-{pid}.json"
    if replaced and include_root:
        with suppress(OSError):
            write_json(path=marker, payload={"created_at": time()})
    for target in targets:
        with suppress(OSError):
            kill(target, SIGTERM)
    deadline: float = monotonic() + Constants.term_wait_seconds
    while monotonic() < deadline and any(
        process_exists(pid=target) for target in targets
    ):
        sleep(Constants.poll_seconds)
    for target in targets:
        if process_exists(pid=target):
            with suppress(OSError):
                kill(target, SIGKILL)
    if replaced:
        with suppress(OSError):
            marker.unlink(missing_ok=True)


def read_json(*, path: Path) -> dict[str, JsonValue] | None:
    """Read json.

    Args:
        path: Path.

    Returns:
        The resulting value.

    """
    try:
        value: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=path.read_text(encoding="utf-8")),
        )
    except (OSError, JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def write_json(*, path: Path, payload: dict[str, JsonValue]) -> None:
    """Write json.

    Args:
        path: Path.
        payload: Payload.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path = path.with_suffix(suffix=path.suffix + ".tmp")
    _ = temporary.write_text(
        data=dumps(obj=payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _ = temporary.replace(target=path)
