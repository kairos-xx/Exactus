# Copyright (c) 2026
"""User-facing ``exactus completion`` command.

Prints a shell registration script to stdout, or installs, removes,
and diagnoses user-level registration for the supported shells.
"""

from __future__ import annotations

from pathlib import Path
from sys import stdout
from typing import TYPE_CHECKING, Final, final

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.completion.install import (
    InstallResult,
    InstallStatus,
    Registration,
    diagnose,
    install,
    uninstall,
)
from exactus.packages.completion.launcher import resolve_launcher
from exactus.packages.completion.model import CompletionShell
from exactus.packages.completion.profiles import profile_paths
from exactus.packages.completion.shells import render

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from collections.abc import Sequence
    from typing import TextIO


@final
class Constants:
    """Group module-level constants.

    Attributes:
        command_name: Grouped module constant.

    """

    command_name: Final[str] = "exactus"


"Registered command name offered to every shell."


def create_parser() -> ArgumentParser:
    """Build the argument parser for the completion command.

    Returns:
        Parser accepting a shell and an optional management action.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        prog="exactus completion",
        description=(
            "Print, install, remove, or diagnose exactus's shell completion"
            " registration."
        ),
    )
    _ = parser.add_argument(
        "shell",
        choices=[shell.value for shell in CompletionShell] + ["all"],
        help="target shell (or 'all' for management actions)",
    )
    _ = parser.add_argument(
        "--install",
        action="store_true",
        help="install the registration into the user-level location",
    )
    _ = parser.add_argument(
        "--uninstall",
        action="store_true",
        help="remove exactus-owned registration content",
    )
    _ = parser.add_argument(
        "--diagnose",
        action="store_true",
        help="report registration health for the supported shells",
    )
    return parser


def _shells(*, argument: str) -> tuple[CompletionShell, ...]:
    """Resolve a shell argument into concrete shells.

    Args:
        argument: Shell name or ``all``.

    Returns:
        The selected shells.

    """
    if argument == "all":
        return tuple(CompletionShell)
    return (CompletionShell(argument),)


def run(
    *,
    arguments: Sequence[str],
    out: TextIO | None = None,
    home: Path | None = None,
) -> int:
    """Run the completion command.

    Args:
        arguments: Arguments after ``completion``.
        out: Output stream; ``sys.stdout`` when ``None``.
        home: User home directory override for tests; defaults to the
            real home.

    Returns:
        ``0`` on success, ``2`` for usage or management failures.

    """
    stream: TextIO = stdout if out is None else out
    target_home: Path = Path.home() if home is None else home
    parser: ArgumentParser = create_parser()
    options: Namespace = parser.parse_args(args=list(arguments))
    actions: int = sum((options.install, options.uninstall, options.diagnose))
    if actions > 1:
        parser.error(
            message="choose at most one of --install/--uninstall/--diagnose",
        )
    launcher: tuple[str, ...] = resolve_launcher(
        command_name=Constants.command_name,
    )
    if options.diagnose:
        if options.shell != "all":
            parser.error(message="--diagnose requires shell 'all'")
        unhealthy: bool = False
        for diagnosis in diagnose(
            launcher=launcher,
            home=target_home,
            command_name=Constants.command_name,
        ):
            unhealthy = unhealthy or diagnosis.status not in (
                InstallStatus.HEALTHY,
                InstallStatus.MISSING,
            )
            _ = stream.write(
                f"{diagnosis.shell.value:<11} {diagnosis.status.value:<16}"
                f" {diagnosis.path} — {diagnosis.detail}\n",
            )
        return 0 if not unhealthy else 1
    shells: tuple[CompletionShell, ...] = _shells(argument=options.shell)
    if options.install or options.uninstall:
        status: int = 0
        locations: tuple[tuple[CompletionShell, Path], ...] = (
            tuple(
                (item.shell, item.path)
                for item in diagnose(
                    launcher=launcher,
                    home=target_home,
                    command_name=Constants.command_name,
                )
            )
            if options.uninstall
            else profile_paths(
                home=target_home,
                command_name=Constants.command_name,
            )
        )
        for shell, profile in locations:
            if shell not in shells:
                continue
            result: InstallResult = (
                install(
                    shell=shell,
                    command_name=Constants.command_name,
                    launcher=launcher,
                    home=target_home,
                    registration=Registration(path=profile, revision=""),
                )
                if options.install
                else uninstall(
                    shell=shell,
                    home=target_home,
                    command_name=Constants.command_name,
                    profile=profile,
                )
            )
            _ = stream.write(f"{result.detail}\n")
            if result.status in (
                InstallStatus.BROKEN,
                InstallStatus.LAUNCHER_MISSING,
            ):
                status = 2
        return status
    if options.shell == "all":
        parser.error(message="'all' requires --install/--uninstall/--diagnose")
    _ = stream.write(
        render(
            shell=shells[0],
            command_name=Constants.command_name,
            launcher=launcher,
        ),
    )
    return 0
