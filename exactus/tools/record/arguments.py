# Copyright (c) 2026
"""Declare the record grammar without importing its execution engine."""

from __future__ import annotations

from argparse import ArgumentParser, BooleanOptionalAction
from pathlib import Path
from typing import Final, final

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.tools.common.cli import add_common_arguments


@final
class Constants:
    """Group module-level constants.

    Attributes:
        workspace_name: Grouped module constant.

    """

    workspace_name: Final[str] = "recording.pwflow.json"


"Canonical recorder workspace artifact name."


def create_parser() -> ArgumentParser:
    """Create the recorder command-line parser.

    Returns:
        Parser exposing the recorder flags plus the common root/output
        arguments.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description=(
            "Record real browser interactions, export them as a replayable"
            " Playwright program and a Exactus Record workspace, replay them,"
            " or drive Exactus Record as its recorder/player; then emit the"
            " RECORD report bundle."
        ),
    )
    add_common_arguments(parser=parser, default_output="RECORD")
    _ = parser.add_argument(
        "--url",
        default=None,
        type=str,
        help=(
            "Absolute URL to open in the recorder, replay against, or open in"
            " the managed Studio test browser."
        ),
    )
    _ = parser.add_argument(
        "--width",
        type=int,
        default=1440,
        help="Viewport width in CSS pixels.",
    )
    _ = parser.add_argument(
        "--height",
        type=int,
        default=1000,
        help="Viewport height in CSS pixels.",
    )
    _ = parser.add_argument(
        "--timeout-ms",
        type=float,
        default=5000.0,
        help="Navigation and per-action timeout in milliseconds.",
    )
    _ = parser.add_argument(
        "--preserve-timing",
        action="store_true",
        default=False,
        help="Emit recorded inter-action delays in generated programs.",
    )
    _ = parser.add_argument(
        "--replay",
        type=Path,
        default=None,
        help=(
            "Replay an actions.normalized.json program or a Exactus Record"
            " .pwflow.json workspace instead of recording."
        ),
    )
    _ = parser.add_argument(
        "--flow",
        default=None,
        help="Flow id to replay from a workspace (default: the first Flow).",
    )
    _ = parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run the managed test browser without a visible window.",
    )
    _ = parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Loopback Studio service port; zero selects an available port.",
    )
    _ = parser.add_argument(
        "--no-open",
        action="store_true",
        help="Serve Studio without opening the editor browser.",
    )
    _ = parser.add_argument(
        "--window",
        action=BooleanOptionalAction,
        default=False,
        help=(
            "Open the managed browser window with Studio and stop Studio "
            "when that window is closed."
        ),
    )
    _ = parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional Studio session duration in seconds.",
    )
    _ = parser.add_argument(
        "--flow-id",
        default="exactus-recording",
        help="Flow id used when exporting to a Exactus Record workspace.",
    )
    _ = parser.add_argument(
        "--flow-name",
        default="Exactus recording",
        help="Flow name used when exporting to a Exactus Record workspace.",
    )
    _ = parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help=(
            "Extra destination for the exported workspace (always written as"
            f" {Constants.workspace_name} in the output)."
        ),
    )
    _ = parser.add_argument(
        "--crawl",
        action="store_true",
        help="Discover action sequences and export a Studio project.",
    )
    _ = parser.add_argument("--max-depth", type=int, default=2)
    _ = parser.add_argument("--max-states", type=int, default=20)
    for flag in ("capture-ui-changes", "follow-links", "click-controls"):
        _ = parser.add_argument(
            f"--{flag}",
            action=BooleanOptionalAction,
            default=True,
        )
    _ = parser.add_argument(
        "--include-selector",
        default=None,
        help="Optional CSS selector limiting discovery targets.",
    )
    return parser
