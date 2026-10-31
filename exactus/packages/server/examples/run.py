#!/usr/bin/env python3
# Copyright (c) 2026
"""Runnable demonstration of the ``exactus.packages.server`` reuse contract.

Serves the bundled ``web/`` directory through ``local.serve``, verifies
the identity ping and a real page fetch, then shows ``reuse_server``
adopting the surviving process instead of stacking a second server on
the same content. Artifacts — the server log and the reuse state cache —
land in ``.scratch/`` (or under the ``scratch`` argument) and the demo
always terminates the server on exit. Run it from a source checkout:

    python -m exactus.packages.server.examples
"""

from __future__ import annotations

from contextlib import suppress
from http.client import HTTPConnection
from importlib import import_module
from os import environ
from pathlib import Path
from sys import path as sys_path
from sys import stdout
from typing import Final, final

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.server import local
from exactus.packages.server import process_control as pc


@final
class Constants:
    """Group module-level constants.

    Attributes:
        here: Grouped module constant.
        site: Grouped module constant.
        scratch: Grouped module constant.

    """

    here: Final[Path] = Path(__file__).resolve().parent
    site: Final[Path] = here / "web"
    scratch: Final[Path] = here / ".scratch"


def _fetch(*, port: int, path: str, timeout: float = 5.0) -> str:
    """Fetch one path from the demo server.

    Args:
        port: Loopback port the demo server listens on.
        path: URL path to request.
        timeout: HTTP request timeout in seconds.

    Returns:
        The decoded response body.

    """
    connection: HTTPConnection = HTTPConnection(
        host="127.0.0.1",
        port=port,
        timeout=timeout,
    )
    try:
        connection.request(method="GET", url=path)
        return connection.getresponse().read().decode(encoding="utf-8")
    finally:
        connection.close()


def main(*, scratch: Path | None = None) -> int:
    """Run the serve, ping, fetch and reuse demonstration.

    Args:
        scratch: Artifact directory overriding the default
            ``.scratch/`` — tests pass a temporary directory to stay
            hermetic.

    Returns:
        ``0`` when the server answered the identity ping, served
        ``index.html`` and was adopted by ``reuse_server``; ``1``
        otherwise.

    """
    workspace: Path = scratch or Constants.scratch
    workspace.mkdir(parents=True, exist_ok=True)
    previous_cache: str | None = environ.get("XDG_CACHE_HOME")
    environ["XDG_CACHE_HOME"] = str(object=workspace / "cache")
    pid, url, reused = local.serve(
        path=Constants.site,
        log=workspace / "server.log",
    )
    try:
        if not local.wait_ready(url=url, pid=pid):
            _ = stdout.write(f"server at {url} never accepted a connection\n")
            return 1
        adopted: tuple[int, int] | None = local.reuse_server(
            path=Constants.site,
        )
        if adopted is None:
            _ = stdout.write("reuse_server did not adopt the running server\n")
            return 1
        adopted_pid, port = adopted
        body: str = _fetch(port=port, path="/index.html")
        _ = stdout.write(
            f"serve    pid={pid} url={url} reused={reused}\n"
            f"adopt    pid={adopted_pid} "
            f"same_process={adopted_pid == pid}\n"
            "ping     "
            f"{('ok' if local.ping_server(port=port) else 'failed')}\n"
            f"index    {body.splitlines()[0]!r}\n",
        )
        return 0
    finally:
        stdout.flush()
        pc.terminate_tree(pid=pid)
        local.clear_server_state(path=Constants.site)
        if previous_cache is None:
            del environ["XDG_CACHE_HOME"]
        else:
            environ["XDG_CACHE_HOME"] = previous_cache


if __name__ == "__main__":
    raise SystemExit(main())
