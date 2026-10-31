#!/usr/bin/env python3
# Copyright (c) 2026
"""Discover and verify a bundled page using a named-output Actions recipe."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from sys import path as import_path
from threading import Thread
from typing import TYPE_CHECKING

if __package__ in {None, ""}:
    import_path.insert(0, str(object=Path(__file__).resolve().parents[4]))
from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.tools.actions.runner import load_actions, run_actions

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace

    from exactus.tools.record.store import JsonValue


def main() -> int:
    """Serve the example page, run its recipe, and stop the owned server.

    Returns:
        Zero when the recipe succeeds, otherwise one.

    """
    parser: ArgumentParser = ExactusArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--output",
        type=Path,
        default=Path(".scratch/actions-example"),
    )
    arguments: Namespace = parser.parse_args()
    here: Path = Path(__file__).resolve().parent
    server: ThreadingHTTPServer = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(SimpleHTTPRequestHandler, directory=str(object=here)),
    )
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        recipe: dict[str, JsonValue] = load_actions(
            path=here / "assets" / "actions.json",
        )
        steps: (
            bool
            | dict[str, JsonValue]
            | float
            | int
            | list[JsonValue]
            | str
            | None
        ) = recipe["actions"]
        if isinstance(steps, list) and isinstance(steps[0], dict):
            options: JsonValue = steps[0]["arguments"]
            if isinstance(options, dict):
                options["url"] = (
                    f"http://127.0.0.1:{server.server_port}/web/index.html"
                )
        report: dict[str, JsonValue] = run_actions(
            specification=recipe,
            root=here,
            output=arguments.output,
        )
        return int(report["status"] != "succeeded")
    finally:
        server.shutdown()
        server.server_close()
