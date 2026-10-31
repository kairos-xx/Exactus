# Copyright (c) 2026
"""ANSI-styled ``--help`` formatting shared by the root scripts."""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO, cast

from exactus.packages.package import inventory_cli
from exactus.packages.package.inventory_cli import (
    Constants,
    PrettyHelpFormatter,
    paint,
    pretty_parser,
    styled,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_not_in,
    expect_true,
)

if TYPE_CHECKING:
    from argparse import ArgumentParser

    import pytest


class _Tty:
    """Minimal stdout stand-in reporting a terminal."""

    @staticmethod
    def isatty() -> bool:
        """Report terminal capability.

        Returns:
            Always ``True`` for the styled-path tests.

        """
        return True


def _force_tty(*, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend stdout is a color-capable terminal.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    monkeypatch.delenv(name="NO_COLOR", raising=False)
    monkeypatch.setattr(target=inventory_cli, name="stdout", value=cast_tty())


def cast_tty() -> TextIO:
    """Return the TTY stub as a ``TextIO`` object.

    Returns:
        The stub typed for monkeypatching ``stdout``.

    """
    return cast(typ="TextIO", val=_Tty())


def test_styled_is_false_without_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-terminal stdout keeps styling disabled.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    monkeypatch.delenv(name="NO_COLOR", raising=False)
    expect_false(condition=styled())


def test_styled_is_true_on_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """A terminal stdout without ``NO_COLOR`` enables styling.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _force_tty(monkeypatch=monkeypatch)
    expect_true(condition=styled())


def test_styled_honours_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    """``NO_COLOR`` disables styling even on a terminal.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _force_tty(monkeypatch=monkeypatch)
    monkeypatch.setenv(name="NO_COLOR", value="1")
    expect_false(condition=styled())


def test_paint_wraps_text_on_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """On a terminal ``paint`` wraps text in the SGR code and reset.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _force_tty(monkeypatch=monkeypatch)
    expect_equal(
        actual=paint(code=Constants.bold, text="hi"),
        expected=f"{Constants.bold}hi{Constants.reset}",
    )


def test_paint_passes_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty text is returned unchanged even on a terminal.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _force_tty(monkeypatch=monkeypatch)
    expect_equal(actual=paint(code=Constants.bold, text=""), expected="")


def test_paint_passes_text_without_tty() -> None:
    """Without a terminal ``paint`` returns the text untouched."""
    expect_equal(actual=paint(code=Constants.bold, text="hi"), expected="hi")


def test_format_help_styles_usage_and_prog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Styled help bolds ``usage:`` and paints the program name.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _force_tty(monkeypatch=monkeypatch)
    parser: ArgumentParser = pretty_parser(prog="exactus", description="demo")
    rendered: str = parser.format_help()
    expect_in(member=f"{Constants.bold}usage:", container=rendered)
    expect_in(
        member=f"{Constants.bold}{Constants.cyan}exactus",
        container=rendered,
    )


def test_format_help_plain_without_tty() -> None:
    """Without a terminal the help text carries no escapes."""
    parser: ArgumentParser = pretty_parser(prog="exactus", description="demo")
    rendered: str = parser.format_help()
    expect_in(member="usage: exactus", container=rendered)
    expect_not_in(member=Constants.bold, container=rendered)


def test_format_help_styles_headings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Styled help paints section headings bold yellow.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _force_tty(monkeypatch=monkeypatch)
    parser: ArgumentParser = pretty_parser(prog="exactus", description="demo")
    _ = parser.add_argument("--output")
    rendered: str = parser.format_help()
    expect_in(
        member=f"{Constants.bold}{Constants.yellow}options",
        container=rendered,
    )


def test_invocation_paints_option_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Option flags render cyan with dimmed metavariables on TTYs.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _force_tty(monkeypatch=monkeypatch)
    parser: ArgumentParser = pretty_parser(prog="exactus", description="demo")
    _ = parser.add_argument("-o", "--output", metavar="PATH")
    rendered: str = parser.format_help()
    expect_in(member=f"{Constants.cyan}--output", container=rendered)
    expect_in(
        member=f"{Constants.dim}{Constants.yellow}PATH",
        container=rendered,
    )


def test_invocation_paints_positionals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Positional arguments render green on a terminal.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _force_tty(monkeypatch=monkeypatch)
    parser: ArgumentParser = pretty_parser(prog="exactus", description="demo")
    _ = parser.add_argument("root")
    rendered: str = parser.format_help()
    expect_in(member=f"{Constants.green}root", container=rendered)


def test_invocations_plain_without_tty() -> None:
    """Plain help lists flags and positionals without escapes."""
    parser: ArgumentParser = pretty_parser(prog="exactus", description="demo")
    _ = parser.add_argument("-o", "--output", metavar="PATH")
    _ = parser.add_argument("root")
    rendered: str = parser.format_help()
    expect_not_in(member=Constants.cyan, container=rendered)
    expect_not_in(member=Constants.green, container=rendered)


def test_pretty_parser_renders_dimmed_epilog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The epilog text is dimmed when styling is enabled.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _force_tty(monkeypatch=monkeypatch)
    parser: ArgumentParser = pretty_parser(
        prog="exactus",
        description="demo",
        epilog="examples",
    )
    rendered: str = parser.format_help()
    expect_in(
        member=f"{Constants.dim}examples{Constants.reset}",
        container=rendered,
    )


def test_formatter_is_pretty() -> None:
    """``pretty_parser`` uses the ANSI help formatter class."""
    parser: ArgumentParser = pretty_parser(prog="exactus", description="demo")
    expect_true(
        condition=isinstance(
            parser.formatter_class(prog="exactus"),
            PrettyHelpFormatter,
        ),
        message="formatter mismatch",
    )
