# Copyright (c) 2026
"""Declare the readme grammar without importing its execution engine."""

from __future__ import annotations

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
        description=(
            "Require a README.md documenting every direct entry in each "
            "documented directory, then emit the README report bundle."
        ),
    )
    add_common_arguments(parser=parser, default_output="README")
    return parser
