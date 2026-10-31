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

if __package__ in {None, ""}:
    import_paths.append(str(object=Path(__file__).resolve().parents[5]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.browser.session import BrowserSession
from exactus.packages.server import local
from exactus.packages.server.process_control import terminate_tree


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


def main() -> int:
    """Launch the demo; leave its reusable background server running.

    Returns:
        Zero once the user closes the managed browser.

    """
    url: str = start_demo(log=Path(gettempdir()) / "exactus-js-console.log")
    _ = stdout.write(f"{url}\n")
    stdout.flush()
    session: BrowserSession = BrowserSession()
    try:
        session.open(url=url)
        _ = session.wait_closed()
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
