"""Declare the visual-cause command-line grammar."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.tools.common.cli import add_common_arguments

if TYPE_CHECKING:
    from argparse import ArgumentParser


def create_parser() -> ArgumentParser:
    """Return the visual-cause parser.

    Returns:
        Configured argument parser.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description=(
            "Explain causal visual differences between rendered pages."
        ),
    )
    add_common_arguments(parser=parser, default_output="VISUAL_CAUSE")
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--url")
    parser.add_argument("--html", type=Path)
    parser.add_argument("--landing", default="index.html")
    parser.add_argument("--url-b")
    parser.add_argument("--html-b", type=Path)
    parser.add_argument("--landing-b", default="index.html")
    parser.add_argument("--css-a", type=Path)
    parser.add_argument("--css-b", type=Path)
    parser.add_argument("--viewport", action="append", default=[])
    parser.add_argument("--accept", action="append", default=[])
    parser.add_argument("--warning", action="append", default=[])
    parser.add_argument("--fail", action="append", default=[])
    parser.add_argument(
        "--default-level",
        choices=("accept", "warning", "fail"),
        default="fail",
    )
    parser.add_argument(
        "--fail-on",
        choices=("findings", "pixels", "never"),
        default="findings",
    )
    parser.add_argument("--threshold", type=int, default=8)
    parser.add_argument("--max-candidates", type=int, default=200)
    parser.add_argument("--parallel-workers", type=int, default=4)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--screenshot-scale", type=float, default=2.0)
    parser.add_argument("--native-styles-a", action="store_true")
    parser.add_argument("--native-styles-b", action="store_true")
    return parser
