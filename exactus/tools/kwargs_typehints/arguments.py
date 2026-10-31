# Copyright (c) 2026
"""Declare the kwargs_typehints CLI grammar."""

from __future__ import annotations

from typing import TYPE_CHECKING

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.tools.common.cli import add_common_arguments, consume

if TYPE_CHECKING:
    from argparse import ArgumentParser


def create_parser() -> ArgumentParser:
    """Create parser.

    Returns:
        The resulting value.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description="Exactus kwargs, bare imports, and explicit type hints.",
    )
    add_common_arguments(parser=parser, default_output="KWARGS_TYPEHINTS")
    _ = consume(
        value=parser.add_argument(
            "--allow-bare-import",
            action="append",
            default=["pytest", "lints"],
            metavar="MODULE",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "-s",
            "--strict",
            action="store_true",
            help=(
                "also report bindings that cannot carry an annotation "
                "(loop, with, except, match, and comprehension targets); "
                "without it only plain `name = value` assignments are "
                "reported"
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--python",
            default=None,
            metavar="INTERPRETER",
            help=(
                "interpreter or virtual-environment directory whose "
                "version/platform steer inference; defaults to the "
                "project .venv, then requires-python probes, then self"
            ),
        ),
    )
    return parser
