# Copyright (c) 2026 Project contributors
"""Replace verified package servers without stopping unrelated listeners."""

from __future__ import annotations

from ast import Call, ImportFrom, Module, Name, parse, walk
from os import getpid, kill
from pathlib import Path
from shlex import split
from signal import SIGINT
from subprocess import CompletedProcess, TimeoutExpired
from subprocess import run as subprocess_run
from time import monotonic, sleep

from .local import accepts
from .process_control import terminate_tree


def listening(*, port: int) -> bool:
    """Check whether a loopback listener is accepting connections.

    Args:
        port: Requested TCP port.

    Returns:
        Whether the port is occupied.

    """
    return accepts(host="127.0.0.1", port=port, timeout=0.2)


def inline_factory(*, command: str, factory: str | None) -> bool:
    """Recognize an explicitly permitted factory call in inline Python.

    Args:
        command: Verified Python process command line.
        factory: Qualified factory permitted by the caller.

    Returns:
        Whether the inline code imports and calls that factory.

    """
    if factory is None or " -c " not in command:
        return False
    code: str = command.partition(" -c ")[2].strip()
    try:
        tree: Module = parse(source=code)
    except SyntaxError:
        return False
    owner, _, symbol = factory.rpartition(".")
    aliases: set[str] = {
        item.asname or item.name
        for node in walk(node=tree)
        if isinstance(node, ImportFrom) and node.module == owner
        for item in node.names
        if item.name == symbol
    }
    return any(
        isinstance(node, Call)
        and isinstance(node.func, Name)
        and node.func.id in aliases
        for node in walk(node=tree)
    )


def listener_owner(
    *,
    port: int,
    module: str,
    factory: str | None = None,
) -> int | None:
    """Verify the listening PID belongs to the requested package launcher.

    Args:
        port: Requested TCP port.
        module: Exact Python module identifying the permitted launcher.
        factory: Qualified server factory permitted in an inline launcher.

    Returns:
        Verified launcher PID, or None when ownership cannot be established.

    """
    try:
        listeners: CompletedProcess[str] = subprocess_run(
            args=("lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"),
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        pids: set[int] = {
            int(line)
            for line in listeners.stdout.splitlines()
            if line.isdecimal()
        }
        if len(pids) != 1:
            return None
        pid: int = pids.pop()
        if pid == getpid():
            return None
        command: CompletedProcess[str] = subprocess_run(
            args=("ps", "-p", str(object=pid), "-o", "args="),
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        tokens: list[str] = split(s=command.stdout.strip())
    except (OSError, TimeoutExpired, ValueError):
        return None
    if not tokens or not Path(tokens[0]).name.lower().startswith("python"):
        return None
    script_suffix: str = f"/{module.replace('.', '/')}/__main__.py"
    if (
        (
            len(tokens) > 1
            and Path(tokens[1]).as_posix().endswith(script_suffix)
        )
        or any(
            argument == "-m" and tokens[index + 1] == module
            for index, argument in enumerate(iterable=tokens[:-1])
        )
        or inline_factory(command=command.stdout, factory=factory)
    ):
        return pid
    return None


def replace_listener(
    *,
    port: int,
    module: str,
    factory: str | None = None,
) -> int | None:
    """Release a fixed port only for the permitted package server.

    Args:
        port: Requested port; zero retains automatic free-port selection.
        module: Exact module whose existing listener may be replaced.
        factory: Optional qualified factory identifying inline launchers.

    Returns:
        Replaced PID, or None when no listener needed replacement.

    Raises:
        OSError: When another service owns the port or replacement fails.

    """
    if port == 0 or not listening(port=port):
        return None
    pid: int | None = listener_owner(port=port, module=module, factory=factory)
    if pid is None:
        msg: str = (
            f"Port {port} is occupied by an unverified or unrelated service; "
            "it was not stopped."
        )
        raise OSError(msg)
    try:
        kill(pid, SIGINT)
    except ProcessLookupError:
        return pid
    deadline: float = monotonic() + 5
    while listening(port=port) and monotonic() < deadline:
        sleep(0.05)
    if not listening(port=port):
        return pid
    if listener_owner(port=port, module=module, factory=factory) == pid:
        terminate_tree(pid=pid)
    if listening(port=port):
        msg = f"Port {port} did not become available after stopping {module}."
        raise OSError(msg)
    return pid
