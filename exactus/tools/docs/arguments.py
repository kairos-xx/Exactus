# Copyright (c) 2026
"""Declare the docs grammar without importing its execution engine."""

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
        description="Exactus Python Google docstrings and JavaScript JSDoc.",
    )
    add_common_arguments(parser=parser, default_output="DOCS")
    _ = consume(
        value=parser.add_argument(
            "--language",
            choices=("both", "python", "javascript"),
            default="both",
        ),
    )
    _ = consume(
        value=parser.add_argument("--public-only", action="store_true"),
    )
    _ = consume(
        value=parser.add_argument("--no-js-check", action="store_true"),
    )
    _ = consume(
        value=parser.add_argument(
            "--fail-on",
            choices=("error", "warning", "info", "never"),
            default="warning",
        ),
    )
    return parser
