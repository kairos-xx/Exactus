# Copyright (c) 2026
"""Declare the self_test grammar without importing its engine."""

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
            "Self-diagnose the exactus runtime: generate a minimal"
            " fixture project in a temporary directory, probe every"
            " expected tool (system executables first, the bundled"
            " toolchain as fallback), run the unified pipeline against"
            " the fixture, and verify every generated report is fresh,"
            " PASS, and issue-free."
        ),
    )
    add_common_arguments(parser=parser, default_output="SELF_TEST")
    return parser
