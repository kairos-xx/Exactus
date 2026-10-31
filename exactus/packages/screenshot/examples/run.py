#!/usr/bin/env python3
# Copyright (c) 2026
"""Capture a served page at mobile and desktop viewport sizes."""

from __future__ import annotations

from asyncio import run, to_thread
from contextlib import suppress
from importlib import import_module
from pathlib import Path
from sys import path as sys_path
from sys import stdout
from tempfile import gettempdir

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from typing import TYPE_CHECKING

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.screenshot import CaptureSpec, Screenshot
from exactus.packages.server import local
from exactus.packages.server.process_control import terminate_tree

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace


def start_demo(*, demo: Path, log: Path) -> tuple[int, str, bool]:
    """Serve the bundled demo page through the shared loopback server.

    Args:
        demo: Demo directory containing ``index.html``.
        log: Destination for the background server's access log.

    Returns:
        Tuple of the serving process id, its ready URL, and whether an
        existing server was adopted rather than spawned.

    """
    existing: tuple[int, int] | None = local.reuse_server(path=demo)
    if existing is not None:
        return existing[0], f"http://127.0.0.1:{existing[1]}/", True
    return local.serve(path=demo, log=log)


async def capture(*, url: str, output: Path) -> tuple[Path, ...]:
    """Capture the page's full body at three viewport widths.

    Args:
        url: Served page to capture.
        output: Directory receiving PNG files.

    Returns:
        Paths of the saved screenshots.

    """
    await to_thread(output.mkdir, parents=True, exist_ok=True)
    paths: list[Path] = []
    for width in (390, 1440, 1728):
        destination: Path = output / f"page-{width}.png"
        _ = await Screenshot.capture(
            url=url,
            target="body",
            spec=CaptureSpec(path=destination, width=width, height=900),
        )
        paths.append(destination)
    return tuple(paths)


def main() -> int:
    """Capture screenshots of the bundled demo or a supplied URL.

    Without a positional URL the bundled ``web/`` page is served through
    the shared loopback server; a freshly spawned server is terminated
    afterwards while an adopted server stays with its owner.

    Returns:
        Zero after every screenshot is saved.

    Raises:
        RuntimeError: When the bundled demo server does not become
            ready.

    """
    parser: ArgumentParser = ExactusArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="Page to capture (default: the bundled web/ demo).",
    )
    _ = parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "results",
    )
    arguments: Namespace = parser.parse_args()
    url: str | None = arguments.url
    owned: tuple[int, Path] | None = None
    if url is None:
        demo: Path = Path(__file__).resolve().parent / "web"
        pid: int
        origin: str
        reused: bool
        pid, origin, reused = start_demo(
            demo=demo,
            log=Path(gettempdir()) / "exactus-screenshot.log",
        )
        if not local.wait_ready(url=origin, pid=pid):
            if not reused:
                terminate_tree(pid=pid)
                local.clear_server_state(path=demo)
            msg: str = "The demo server did not become ready."
            raise RuntimeError(msg)
        if not reused:
            owned = (pid, demo)
        url = f"{origin}index.html"
    try:
        for destination in run(main=capture(url=url, output=arguments.output)):
            _ = stdout.write(f"{destination}\n")
    finally:
        if owned is not None:
            terminate_tree(pid=owned[0])
            local.clear_server_state(path=owned[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
