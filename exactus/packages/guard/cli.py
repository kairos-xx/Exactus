# Copyright (c) 2026 João Lopes.
"""Command-line entry point for external process supervision."""

from __future__ import annotations

from argparse import REMAINDER, ArgumentParser, Namespace
from sys import argv
from typing import TYPE_CHECKING

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.guard.supervisor import (
    ProcessSupervisor,
    SupervisionResult,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class CliArguments(Namespace):
    """Strongly typed command-line namespace.

    Attributes:
        poll_interval: Descendant discovery interval in seconds.
        grace_seconds: Grace period before force-killing descendants.

    """

    poll_interval: float = 0.02
    grace_seconds: float = 1.5

    def __init__(self) -> None:
        """Initialize typed parser destinations."""
        super().__init__()
        self.command: list[str] = []


class Cli:
    """Parse command-line arguments and execute the process supervisor."""

    @classmethod
    def run(cls, *, arguments: Sequence[str]) -> int:
        """Execute one supervised command and return its exit status.

        Args:
            arguments: Command-line tokens excluding the executable name.

        Returns:
            Exit status produced by the supervised target.

        """
        namespace: CliArguments = cls.parser().parse_args(
            args=arguments,
            namespace=CliArguments(),
        )
        result: SupervisionResult = ProcessSupervisor(
            command=namespace.command,
            poll_interval=namespace.poll_interval,
            grace_seconds=namespace.grace_seconds,
        ).run()
        return result.exit_code

    @staticmethod
    def parser() -> ArgumentParser:
        """Build the command-line parser.

        Returns:
            Configured process-guard argument parser.

        """
        parser: ArgumentParser = ExactusArgumentParser(
            prog="process-guard",
            description="Run a command and clean its surviving subprocesses.",
        )
        _ = parser.add_argument(
            "--poll-interval",
            type=float,
            default=0.02,
            help="descendant discovery interval in seconds",
        )
        _ = parser.add_argument(
            "--grace-seconds",
            type=float,
            default=1.5,
            help="grace period before force-killing descendants",
        )
        _ = parser.add_argument(
            "command",
            nargs=REMAINDER,
            help="command and arguments to supervise",
        )
        return parser


def main() -> int:
    """Run the command-line application.

    Returns:
        Exit status produced by the supervised target.

    """
    return Cli.run(arguments=argv[1:])
