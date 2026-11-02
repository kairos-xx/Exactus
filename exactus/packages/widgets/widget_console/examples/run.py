#!/usr/bin/env python3
# Copyright (c) 2026 Project contributors
"""Start the loopback console widget demo and open the managed browser."""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from sys import path as import_paths
from sys import stdout
from tempfile import gettempdir
from typing import TYPE_CHECKING

if __package__ in {None, ""}:
    import_paths.append(str(object=Path(__file__).resolve().parents[5]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.browser.session import BrowserSession
from exactus.packages.server import local
from exactus.packages.server.process_control import terminate_tree

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Sequence


def start_demo(*, log: Path) -> str:
    """Serve ``packages/`` so the demo can reach sibling widget packages.

    Args:
        log: Destination for the background server's access log.

    Returns:
        Ready demo URL on an automatically allocated loopback port.

    Raises:
        RuntimeError: When the spawned server fails its readiness check.

    """
    root: Path = Path(__file__).resolve().parents[3]
    page: str = "widgets/widget_console/examples/web/index.html"
    existing: tuple[int, int] | None = local.reuse_server(path=root)
    if existing is not None:
        return f"http://127.0.0.1:{existing[1]}/{page}"
    pid: int
    origin: str
    reused: bool
    pid, origin, reused = local.serve(path=root, log=log)
    if not local.wait_ready(url=origin, pid=pid):
        if not reused:
            terminate_tree(pid=pid)
            local.clear_server_state(path=root)
        msg: str = "The console widget demo server did not become ready."
        raise RuntimeError(msg)
    return f"{origin}{page}"


def main(*, arguments: Sequence[str] | None = None) -> int:
    """Launch the demo; leave its reusable background server running.

    Args:
        arguments: Explicit CLI tokens or the process arguments.

    Returns:
        Zero once the user closes the managed browser; in ``--headless``
        mode once the page loaded.

    """
    parser: ExactusArgumentParser = ExactusArgumentParser(
        description=__doc__,
    )
    _ = parser.add_argument(
        "--headless",
        action="store_true",
        help="Load the demo in a headless browser instead of a window.",
    )
    _ = parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Seconds to keep the browser alive after it loads.",
    )
    args: Namespace = parser.parse_args(args=arguments)
    url: str = start_demo(log=Path(gettempdir()) / "exactus-js-console.log")
    _ = stdout.write(f"{url}\n")
    stdout.flush()
    session: BrowserSession = BrowserSession(headless=args.headless)
    ready: bool = True
    try:
        session.open(url=url)
        if args.headless:
            ready = session.wait_ready(timeout=args.timeout)
        if ready and (not args.headless or args.timeout is not None):
            _ = session.wait_closed(timeout=args.timeout)
    finally:
        session.close()
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
