# Copyright (c) 2026
"""ANSI-styled ``--help``/``-h`` output shared by the root scripts.

``pretty_parser`` builds an ``ArgumentParser`` whose help is colorized
when attached to a terminal: a bold ``usage:`` prefix with the program
name in cyan, bold section titles, cyan option flags, dimmed
metavariables, and green positionals. Colors are suppressed on non-TTY
output and when the ``NO_COLOR`` environment variable is set, so
piped or captured help stays plain.
"""

from __future__ import annotations

from argparse import Action, ArgumentParser, RawDescriptionHelpFormatter
from os import environ
from sys import stdout
from typing import Final, final

from exactus.packages.argument_parser import ExactusArgumentParser


@final
class Constants:
    """Group module-level constants.

    Attributes:
        reset: Grouped module constant.
        bold: Grouped module constant.
        dim: Grouped module constant.
        green: Grouped module constant.
        yellow: Grouped module constant.
        cyan: Grouped module constant.

    """

    reset: Final[str] = "\x1b[0m"
    bold: Final[str] = "\x1b[1m"
    dim: Final[str] = "\x1b[2m"
    green: Final[str] = "\x1b[32m"
    yellow: Final[str] = "\x1b[33m"
    cyan: Final[str] = "\x1b[36m"


def styled() -> bool:
    """Return whether ANSI styling may be emitted on stdout.

    Returns:
        ``True`` when stdout is a terminal and ``NO_COLOR`` is unset.

    """
    return "NO_COLOR" not in environ and stdout.isatty()


def paint(*, code: str, text: str) -> str:
    """Wrap ``text`` in an ANSI ``code`` when styling is enabled.

    Args:
        code: SGR escape body such as ``"1"`` or ``"36"``.
        text: Text to wrap; empty text passes through untouched.

    Returns:
        ``text`` wrapped in ``code``/reset, or ``text`` unchanged.

    """
    return f"{code}{text}{Constants.reset}" if styled() and text else text


class PrettyHelpFormatter(RawDescriptionHelpFormatter):
    """argparse formatter adding ANSI color to the help layout.

    Keeps ``description``/``epilog`` line breaks verbatim (raw text)
    so styled example blocks in the epilog survive rendering.

    """

    def format_help(self) -> str:
        """Return the full help with a styled leading usage line.

        argparse renders the usage line through its private internals,
        so styling is applied by post-processing: the ``usage:`` prefix
        turns bold and the program name (which opens the usage line)
        turns bold cyan.

        Returns:
            Rendered help text.

        """
        rendered: str = super().format_help()
        if not styled():
            return rendered
        if rendered.startswith("usage: "):
            rendered = paint(code=Constants.bold, text="usage:") + rendered[6:]
        return rendered.replace(
            self._prog,
            paint(code=Constants.bold + Constants.cyan, text=self._prog),
            count=1,
        )

    def start_section(self, heading: str | None) -> None:
        """Begin a help section with a bold heading.

        Args:
            heading: Section title such as ``options``.

        """
        super().start_section(
            heading=(
                paint(code=Constants.bold + Constants.yellow, text=heading)
                if heading
                else heading
            ),
        )

    def _format_action_invocation(self, action: Action) -> str:
        """Return the invocation with cyan flags and dim metavariables.

        Args:
            action: Action whose invocation is rendered.

        Returns:
            ``-o PATH, --output PATH`` style text, colorized on TTYs.

        """
        invocation: str = super()._format_action_invocation(action=action)
        if not styled():
            return invocation
        if not action.option_strings:
            return paint(code=Constants.green, text=invocation)
        chunks: list[str] = []
        for part in invocation.split(sep=", "):
            flag, _, tail = part.partition(" ")
            rendered: str = paint(code=Constants.cyan, text=flag)
            if tail:
                rendered += " " + paint(
                    code=Constants.dim + Constants.yellow,
                    text=tail,
                )
            chunks.append(rendered)
        return ", ".join(chunks)


def pretty_parser(
    *,
    prog: str,
    description: str,
    epilog: str = "",
) -> ArgumentParser:
    """Create an ``ArgumentParser`` with the ANSI help formatter.

    Args:
        prog: Program name shown in the usage line.
        description: Paragraph printed below the usage line.
        epilog: Extra text rendered dimmed after the option list;
            handy for usage examples.

    Returns:
        Parser whose ``-h``/``--help`` output is ANSI-styled on TTYs.

    """
    return ExactusArgumentParser(
        prog=prog,
        description=description,
        epilog=paint(code=Constants.dim, text=epilog) or None,
        formatter_class=PrettyHelpFormatter,
    )
