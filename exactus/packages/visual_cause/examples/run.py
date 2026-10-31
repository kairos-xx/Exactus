#!/usr/bin/env python3
# Copyright (c) 2026
"""Run the CSS visual-cause analyzer against its bundled demo."""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from shutil import rmtree
from sys import path as sys_path
from tempfile import gettempdir

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.server import local
from exactus.packages.server.process_control import terminate_tree
from exactus.packages.visual_cause import CssVisualCause, Settings
from exactus.packages.visual_cause.examples.validate_results import (
    main as validate_demo_results,
)


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


def main() -> None:
    """Analyze the bundled demo served over loopback HTTP.

    A freshly spawned server is terminated afterwards; an adopted server
    remains the responsibility of its original owner.

    Raises:
        RuntimeError: When the demo server does not become ready.

    """
    root: Path = Path(__file__).resolve().parent
    demo: Path = root / "web"
    output: Path = root / "results"
    if output.exists():
        rmtree(path=output)
    pid: int
    origin: str
    reused: bool
    pid, origin, reused = start_demo(
        demo=demo,
        log=Path(gettempdir()) / "exactus-visual-cause.log",
    )
    try:
        if not local.wait_ready(url=origin, pid=pid):
            msg: str = "The demo server did not become ready."
            raise RuntimeError(msg)
        CssVisualCause(
            settings=Settings(
                url=f"{origin}index.html",
                css_a=demo / "a.css",
                css_b=demo / "b.css",
                output=output,
                width=1180,
                height=900,
                threshold=8,
                max_candidates=80,
                timeout_ms=5000,
                parallel_workers=1,
                recycle_after=12,
                analysis_budget_seconds=120.0,
                advanced_analysis=False,
            ),
        ).run()
        validate_demo_results()
    finally:
        if not reused:
            terminate_tree(pid=pid)
            local.clear_server_state(path=demo)


if __name__ == "__main__":
    main()
