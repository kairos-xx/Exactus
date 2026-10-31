# Copyright (c) 2026 Project contributors
"""Command-line entry point for the reusable TODO synchronizer."""

from argparse import Action, ArgumentParser, Namespace
from collections.abc import Sequence
from json import dumps
from pathlib import Path
from sys import stdout
from typing import Protocol, Self

from exactus.packages.argument_parser import ExactusArgumentParser

from .sync import synchronize
from .watch import read_state, running, start, stop, watch


class ModeGroup(Protocol):
    """Public structural interface for mutually exclusive CLI switches."""

    def add_argument(self: Self, *name_or_flags: str, action: str) -> Action:
        """Register a mutually exclusive command-line switch.

        Args:
            name_or_flags: Flag spellings accepted for this mode.
            action: Argparse action used to store the parsed value.

        Returns:
            Registered action whose help text may be configured.

        """
        ...


class Args(Namespace):
    """Concrete command-line types shared with argparse.

    Attributes:
        path: Source Markdown document to synchronize.
        check: Check freshness without writing.
        watch: Start a detached watcher.
        watch_child: Run the watcher in the foreground.
        watch_stop: Request cooperative shutdown of the owned watcher.
        watch_status: Print persisted diagnostic watcher state.
        no_html: Disable HTML generation.
        interval: Polling interval in seconds.
        normalize: Normalize task headers during one-shot synchronization.

    """

    path: Path = Path("exactus/docs/todo/TODO.md")
    check: bool = False
    watch: bool = False
    watch_child: bool = False
    watch_stop: bool = False
    watch_status: bool = False
    no_html: bool = False
    interval: float = 0.5
    normalize: bool = False


def main(argv: Sequence[str] | None = None) -> int:
    """Run one-shot synchronization, freshness checking or watcher control.

    Args:
        argv: Explicit command-line arguments, or None for process arguments.

    Returns:
        Zero on success, or one for stale output or an absent watcher.

    """
    parser: ArgumentParser = ExactusArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("exactus/docs/todo/TODO.md"),
    )
    modes: ModeGroup = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument(
        "--watch",
        action="store_true",
    ).help = "Start a detached watcher."
    modes.add_argument(
        "--watch-child",
        action="store_true",
    ).help = "Watch in the foreground."
    modes.add_argument("--watch-stop", action="store_true")
    modes.add_argument("--watch-status", action="store_true")
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Only synchronize Markdown.",
    )
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Normalize task headers once; combine with --check to audit.",
    )
    args: Args = parser.parse_args(args=argv, namespace=Args())
    if args.normalize and (
        args.watch or args.watch_child or args.watch_stop or args.watch_status
    ):
        parser.error(
            message="--normalize is only valid for one-shot sync or --check",
        )
    path: Path = Path(args.path).absolute()
    try:
        if args.watch_status:
            stdout.write(dumps(obj=read_state(path=path), indent=2) + "\n")
            return 0 if running(path=path) else 1
        if args.watch_stop:
            return stop(path=path)
        if args.watch:
            return start(
                path=path,
                interval=args.interval,
                html=not args.no_html,
            )
        if args.watch_child:
            return watch(
                path=path,
                interval=args.interval,
                html=not args.no_html,
            )
        changed: bool = synchronize(
            path=path,
            check=args.check,
            html=not args.no_html,
            normalize_tasks=args.normalize,
        )
        status: str = (
            "out of sync"
            if args.check and changed
            else "updated"
            if changed
            else "in sync"
        )
        stdout.write(f"{path}: {status}\n")
        return int(args.check and changed)
    except (OSError, ValueError) as exc:
        parser.exit(status=2, message=f"Progress sync failed: {exc}\n")
