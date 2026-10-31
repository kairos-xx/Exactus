# Copyright (c) 2026
"""Declare the performance grammar without importing its engine."""

from __future__ import annotations

from argparse import SUPPRESS, ArgumentParser, BooleanOptionalAction
from pathlib import Path

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.tools.common.cli import add_common_arguments


def create_parser() -> ArgumentParser:
    """Create parser.

    Returns:
        The resulting value.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description=(
            "Profile the steps.txt traces recorded under the Exactus "
            "results tree, then emit the performance report bundle plus "
            "the interactive dashboard."
        ),
    )
    add_common_arguments(parser=parser, default_output="PERFORMANCE")
    _ = parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        metavar="PATH",
        help=(
            "trace file, directory, or glob to scan; repeatable "
            "(default: EXACTUS_RESULTS)"
        ),
    )
    _ = parser.add_argument(
        "--serve",
        action=BooleanOptionalAction,
        default=None,
        help="serve the exported dashboard (default: on)",
    )
    _ = parser.add_argument(
        "--open",
        action=BooleanOptionalAction,
        default=None,
        help="open the dashboard in the managed browser (default: on)",
    )
    _ = parser.add_argument(
        "--no-browser",
        action="store_false",
        dest="open",
        help=SUPPRESS,
    )
    _ = parser.add_argument(
        "--chrome",
        type=Path,
        help="Chrome or Chromium executable used to open the dashboard",
    )
    _ = parser.add_argument(
        "--report",
        type=Path,
        help=(
            "write the full JSON report here (default: <output>/report.json)"
        ),
    )
    _ = parser.add_argument(
        "--gap-threshold",
        type=float,
        help="silent-gap threshold in seconds",
    )
    _ = parser.add_argument(
        "--repetition-threshold",
        type=int,
        help="repeated-step count treated as a bottleneck",
    )
    _ = parser.add_argument(
        "--server-timeout",
        type=float,
        help="seconds to wait for the dashboard server",
    )
    _ = parser.add_argument(
        "--summary",
        action="store_true",
        help="print analysis only; do not export or serve",
    )
    return parser
