"""Serve a directory over loopback (``python -m exactus.packages.server``)."""

from __future__ import annotations

from pathlib import Path
from signal import SIGTERM
from sys import modules
from threading import Event
from typing import TYPE_CHECKING

from exactus.packages.argument_parser import ExactusArgumentParser

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from types import FrameType, ModuleType
    from typing import TextIO


def main() -> int:
    """Start, adopt, or stop a detached loopback server.

    The server is captured by this process: it stays usable only while
    this command runs, so the default mode blocks until Ctrl-C and then
    terminates the server and clears its reuse state.

    Returns:
        Zero when the requested action succeeded.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        prog="server",
        description=(
            "Serve a directory on a captured loopback server until "
            "interrupted; --stop terminates a recorded server instead."
        ),
    )
    _ = parser.add_argument("path", type=Path, help="Directory to serve.")
    _ = parser.add_argument(
        "--log",
        type=Path,
        default=Path(".scratch/server.log"),
        help="Server output destination (default: .scratch/server.log).",
    )
    _ = parser.add_argument(
        "--stop",
        action="store_true",
        help="Terminate the recorded server and clear its state.",
    )
    stdout: TextIO = modules["sys"].stdout
    arguments: Namespace = parser.parse_args()
    local: ModuleType = modules["importlib"].import_module(
        name="exactus.packages.server.local",
    )
    control: ModuleType = modules["importlib"].import_module(
        name="exactus.packages.server.process_control",
    )
    directory: Path = arguments.path
    if arguments.stop:
        adopted: tuple[int, int] | None = local.reuse_server(path=directory)
        if adopted is None:
            _ = stdout.write(f"no running server for {directory}\n")
            return 1
        control.terminate_tree(pid=adopted[0])
        local.clear_server_state(path=directory)
        _ = stdout.write(f"stopped pid={adopted[0]}\n")
        return 0
    arguments.log.parent.mkdir(parents=True, exist_ok=True)
    pid: int
    url: str
    reused: bool
    pid, url, reused = local.serve(path=directory, log=arguments.log)
    try:
        if not local.wait_ready(url=url, pid=pid):
            _ = stdout.write(f"server at {url} never accepted a connection\n")
            return 1
        _ = stdout.write(
            f"serve pid={pid} url={url} reused={reused} (Ctrl-C to stop)\n",
        )
        stdout.flush()
        stop: Event = Event()

        def _interrupt(_signum: int, _frame: FrameType | None) -> None:
            """Record a termination request.

            Args:
                _signum: Received signal number.
                _frame: Interrupted stack frame.

            """
            stop.set()

        _ = modules["signal"].signal(signalnum=SIGTERM, handler=_interrupt)
        while not stop.wait(timeout=0.5):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        control.terminate_tree(pid=pid)
        local.clear_server_state(path=directory)
    return 0
