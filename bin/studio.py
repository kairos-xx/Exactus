#!/usr/bin/env python3
# Copyright (c) 2026 Project contributors
"""Start Flow Studio on a port, replacing any listener.

Kills whatever is bound to the requested port, boots the Studio service for
a project, opens the authorized Flow Studio URL in the managed browser and
exits when that window is closed; ``--no-window`` only serves. This script
ignores ``[tool.exactus.record] window``: it always defaults to the window.
Any interpreter works — the script re-executes itself with
``.venv/bin/python`` on startup:

    python bin/studio.py --port 8880
    ./bin/studio.py --no-window
"""

from __future__ import annotations

from argparse import ArgumentParser, BooleanOptionalAction, Namespace
from os import kill
from pathlib import Path
from signal import SIGKILL, SIGTERM
from socket import socket
from subprocess import CompletedProcess, TimeoutExpired
from subprocess import run as subprocess_run
from threading import Event
from time import monotonic, sleep
from typing import Final, final

try:
    from ._bootstrap import Constants as _BootstrapConstants
except ImportError:
    from _bootstrap import Constants as _BootstrapConstants
from exactus.packages.browser.session import BrowserSession
from exactus.tools.record.sprint import sprint
from exactus.tools.record.studio.service import StudioService


@final
class Constants:
    """Group module-level constants.

    Attributes:
        default_port: Grouped module constant.
        kill_timeout: Grouped module constant.
        poll_interval: Grouped module constant.
        ready_timeout: Grouped module constant.

    """

    default_port: Final[int] = 8880
    kill_timeout: Final[float] = 3.0
    poll_interval: Final[float] = 0.1
    ready_timeout: Final[float] = 10.0


def listening(*, port: int) -> bool:
    """Check whether a loopback listener is accepting connections.

    Args:
        port: TCP port to probe.

    Returns:
        Whether the port is occupied.

    """
    probe: socket = socket()
    with probe:
        probe.settimeout(Constants.poll_interval * 2)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def listener_pids(*, port: int) -> list[int]:
    """Return PIDs holding a TCP listener on a port.

    Args:
        port: TCP port to inspect.

    Returns:
        Sorted owning process identifiers, empty when the port is free.

    """
    try:
        listeners: CompletedProcess[str] = subprocess_run(
            args=("lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"),
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, TimeoutExpired):
        return []
    return sorted(
        {
            int(line)
            for line in listeners.stdout.splitlines()
            if line.isdecimal()
        },
    )


def free_port(*, port: int) -> None:
    """Terminate every process listening on a port, escalating to SIGKILL.

    Args:
        port: TCP port to free.

    """
    for pid in listener_pids(port=port):
        sprint(f"Stopping PID {pid} listening on port {port}.")
        try:
            kill(pid, SIGTERM)
        except ProcessLookupError:
            continue
    deadline: float = monotonic() + Constants.kill_timeout
    while monotonic() < deadline and listening(port=port):
        sleep(Constants.poll_interval)
    for pid in listener_pids(port=port):
        try:
            kill(pid, SIGKILL)
        except ProcessLookupError:
            continue


def main(*, arguments: tuple[str, ...] | None = None) -> int:
    """Start Flow Studio on a port, optionally bound to a browser window.

    Args:
        arguments: Explicit CLI tokens or the process arguments.

    Returns:
        Successful process exit code after graceful shutdown.

    Raises:
        TimeoutError: When the service does not bind the port in time.

    """
    parser: ArgumentParser = ArgumentParser(
        description="Start Flow Studio on a port.",
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=_BootstrapConstants.project_root,
    )
    parser.add_argument("--port", type=int, default=Constants.default_port)
    parser.add_argument("--url", help="Optional initial target URL.")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Also show the test browser in its own window, for debugging.",
    )
    parser.add_argument(
        "--window",
        action=BooleanOptionalAction,
        default=True,
        help=(
            "Open the managed browser window and stop Studio when it is "
            "closed (default: on; --no-window only serves)."
        ),
    )
    args: Namespace = parser.parse_args(args=arguments)
    window: bool = args.window
    free_port(port=args.port)
    service: StudioService = StudioService(
        root=args.project,
        port=args.port,
        headless=not args.headed,
    )
    session: BrowserSession = BrowserSession()
    try:
        service.start()
        deadline: float = monotonic() + Constants.ready_timeout
        while not listening(port=args.port):
            if monotonic() > deadline:
                msg: str = (
                    f"Studio did not bind port {args.port} within "
                    f"{Constants.ready_timeout:g}s."
                )
                raise TimeoutError(msg)
            sleep(Constants.poll_interval)
        sprint(f"Flow Studio ready at {service.origin}/studio/")
        if window:
            session.open(url=service.url)
        if args.url is not None:
            service.worker.open_target(url=args.url)
        _ = session.wait_closed() if window else Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        session.close()
        service.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
