# Copyright (c) 2026 Project contributors
"""Run browser Studio as a package with its automation worker."""

from __future__ import annotations

from argparse import SUPPRESS, ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from signal import SIGINT, default_int_handler, signal
from threading import Event
from typing import TYPE_CHECKING

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.browser.session import BrowserSession
from exactus.packages.project_python import auto as _project_python_auto
from exactus.packages.server.ports import replace_listener
from exactus.tools.record.conflict_copies import clear_conflict_copies
from exactus.tools.record.sprint import sprint
from exactus.tools.record.studio.service import StudioService
from exactus.tools.record.studio.window import (
    add_window_argument,
    resolve_window,
)

if TYPE_CHECKING:
    from argparse import Namespace
_project_python_active: bool = _project_python_auto.Constants.activated


@dataclass(frozen=True)
class StudioLaunch:
    """Configure the single browser Studio host.

    Attributes:
        root: Project directory.
        port: Loopback service port, or zero for automatic selection.
        headless: Run the managed test browser without its own window, so the
            Browser panel is the only view of the page.
        open_editor: Allow the editor window; ``--no-open`` vetoes it.
        window: Open the authorized editor in the managed browser and
            stop Studio when that window is closed.
        target_url: Optional initial target URL.
        duration_seconds: Optional bounded session duration.

    """

    root: Path
    port: int = 0
    headless: bool = True
    open_editor: bool = True
    window: bool = False
    target_url: str | None = None
    duration_seconds: float | None = None


def serve(*, options: StudioLaunch) -> StudioService:
    """Serve the chosen project until interrupted or its duration ends.

    Args:
        options: Host, target and lifetime settings.

    Returns:
        Stopped service retaining workspace and execution evidence.

    Raises:
        ValueError: When the duration is not positive.

    """
    duration_seconds: float | None = options.duration_seconds
    if duration_seconds is not None and duration_seconds <= 0:
        msg: str = "Session duration must be positive."
        raise ValueError(msg)
    replaced: int | None = replace_listener(
        port=options.port,
        module="exactus.tools.record.studio",
        factory="exactus.tools.record.studio.service.StudioService",
    )
    if replaced is not None:
        sprint(
            f"Replaced Studio server (PID {replaced}) on port {options.port}.",
        )
    _ = clear_conflict_copies(root=options.root)
    service: StudioService = StudioService(
        root=options.root,
        port=options.port,
        headless=options.headless,
    )
    session: BrowserSession = BrowserSession()
    try:
        service.start()
        sprint(f"Flow Studio ready at {service.origin}/studio/")
        if options.window and options.open_editor:
            session.open(url=service.url)
        if options.target_url is not None:
            service.worker.open_target(url=options.target_url)
        if options.window and options.open_editor:
            _ = session.wait_closed(timeout=duration_seconds)
        else:
            _ = Event().wait(timeout=duration_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        session.close()
        service.stop()
    return service


def main(*, arguments: tuple[str, ...] | None = None) -> int:
    """Start the sole supported browser Studio launch path.

    Args:
        arguments: Explicit CLI tokens or the process arguments.

    Returns:
        Successful process exit code after graceful shutdown.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description="Record, discover and test browser flows.",
    )
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Also show the test browser in its own window, for debugging.",
    )
    # Accepted for older scripts; headless is now the default.
    parser.add_argument("--headless", action="store_true", help=SUPPRESS)
    parser.add_argument("--no-open", action="store_true")
    add_window_argument(parser=parser)
    parser.add_argument("--url")
    args: Namespace
    parser.add_argument("--duration", type=float)
    args = parser.parse_args(args=arguments)
    _ = serve(
        options=StudioLaunch(
            root=args.project,
            port=args.port,
            headless=not args.headed,
            open_editor=not args.no_open,
            window=resolve_window(flag=args.window, start=args.project),
            target_url=args.url,
            duration_seconds=args.duration,
        ),
    )
    return 0


if __name__ == "__main__":
    _ = signal(signalnum=SIGINT, handler=default_int_handler)
    raise SystemExit(main())
