# Copyright (c) 2026
"""Declare the frontend grammar without importing its execution engine."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.tools.common.cli import add_common_arguments

if TYPE_CHECKING:
    from argparse import ArgumentParser


def create_parser() -> ArgumentParser:
    """Create parser.

    Returns:
        The resulting value.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description="Execute Studio flows and report frontend evidence.",
    )
    add_common_arguments(parser=parser, default_output="FRONTEND")
    parser.add_argument(
        "--actions",
        type=Path,
        help="Actions recipe orchestrating discovery and replay.",
    )
    parser.add_argument("--url", help="Optional initial application URL.")
    parser.add_argument(
        "--workspace",
        type=Path,
        help="Studio project to execute.",
    )
    parser.add_argument("--flow", help="Optional workflow entry flow ID.")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--timeout-ms", type=float, default=5000)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent workflow visits; use 1 for serial execution.",
    )
    parser.add_argument("--server-log", type=Path)
    return parser
