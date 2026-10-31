# Copyright (c) 2026
"""ANSI-styled ``--help`` output of the ``cli_help`` module."""

from __future__ import annotations

from os import environ
from typing import TYPE_CHECKING
from unittest.mock import patch

from cli_help import paint, pretty_parser, styled
from exactus.tests.packages.rename_project.assertions import (
    expect_equal,
    expect_false,
    expect_in,
    expect_not_in,
    expect_true,
)

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Tty:
    """Terminal-like stdout stand-in."""

    @staticmethod
    def isatty() -> bool:
        """Report a terminal.

        Returns:
            Always true.

        """
        return True


def test_cli_help_styling() -> None:
    """Colors appear only on terminals without NO_COLOR."""
    with (
        patch(target="cli_help.stdout", new=Tty()),
        patch.dict(in_dict=environ, values={}, clear=False),
    ):
        _ = environ.pop("NO_COLOR", None)
        expect_true(condition=styled())
        expect_equal(actual=paint(code="C", text="x"), expected="Cx\033[0m")
        expect_equal(actual=paint(code="1", text=""), expected="")
        parser: ArgumentParser = pretty_parser(
            prog="tool",
            description="d",
            epilog="e",
        )
        _ = parser.add_argument("pos", help="positional")
        _ = parser.add_argument("-o", "--out", metavar="P", help="opt")
        _ = parser.add_argument("--flag", action="store_true")
        expect_in(member="\033[", container=parser.format_help())
        environ["NO_COLOR"] = "1"
        expect_false(condition=styled())
        plain: ArgumentParser = pretty_parser(
            prog="tool",
            description="d",
            epilog="e",
        )
        _ = plain.add_argument("-o", "--out", metavar="P")
        expect_not_in(member="\033[", container=plain.format_help())
        expect_equal(actual=paint(code="1", text="x"), expected="x")
