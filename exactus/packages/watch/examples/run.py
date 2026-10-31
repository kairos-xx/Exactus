#!/usr/bin/env python3
# Copyright (c) 2026
"""Run the folder watcher directly from Python code.

Without arguments the bundled ``project/`` fixture is watched into two
``results/`` destinations that mirror the configuration examples in
``assets/``: ``project-watch-copy`` keeps destination files when their
source disappears while ``project-mirror`` propagates deletions. An
explicit ``source destination`` pair runs a single watcher instead.
Watchers stop automatically after five seconds.
"""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from sys import path as sys_path
from threading import Thread
from time import monotonic
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from argparse import Action, ArgumentParser, Namespace
    from collections.abc import Callable
if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.watch.core import FolderWatchCopy


@final
class Constants:
    """Group module-level constants.

    Attributes:
        here: Grouped module constant.
        source: Grouped module constant.
        results: Grouped module constant.
        duration: Grouped module constant.

    """

    here: Final[Path] = Path(__file__).resolve().parent
    source: Final[Path] = here / "project"
    results: Final[Path] = here / "results"
    duration: Final[float] = 5.0


def _stopper(*, deadline: float) -> Callable[[], bool]:
    """Return a stop predicate that fires once the deadline passes.

    Args:
        deadline: ``monotonic`` timestamp at which watching ends.

    Returns:
        Zero-argument predicate for ``FolderWatchCopy.run``.

    """

    def expired() -> bool:
        """Return whether the deadline has passed.

        Returns:
            True once ``monotonic`` reaches the deadline.

        """
        return monotonic() >= deadline

    return expired


def _bundled_watchers() -> tuple[FolderWatchCopy, FolderWatchCopy]:
    """Build the copy and mirror watchers matching ``assets/`` configs.

    Returns:
        The basic-copy watcher writing ``project-watch-copy`` and the
        mirror watcher writing ``project-mirror``.

    """
    return (
        FolderWatchCopy(
            source=Constants.source,
            destination=Constants.results / "project-watch-copy",
            interval=0.5,
            settle_time=0.5,
            exclusions=(".git", ".DS_Store", "__pycache__", "*.pyc"),
            inclusions=(),
            mirror_deletes=False,
            verbose=True,
        ),
        FolderWatchCopy(
            source=Constants.source,
            destination=Constants.results / "project-mirror",
            interval=0.25,
            settle_time=0.75,
            exclusions=(
                ".git",
                ".DS_Store",
                ".pytest_cache",
                ".ruff_cache",
                ".coverage",
                "__pycache__",
                "*.pyc",
                "*.tmp",
            ),
            inclusions=(),
            mirror_deletes=True,
            verbose=True,
        ),
    )


def main() -> int:
    """Run the bundled dual-mode demo or one explicit watcher.

    Returns:
        Process exit status.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description="Programmatic exactus.packages.watch example.",
    )
    _source_action: Action = parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=None,
        help="Directory to watch (default: the bundled project/ fixture).",
    )
    _destination_action: Action = parser.add_argument(
        "destination",
        nargs="?",
        type=Path,
        default=None,
        help="Directory receiving changes.",
    )
    arguments: Namespace = parser.parse_args()
    if (arguments.source is None) != (arguments.destination is None):
        parser.error(message="source and destination must be given together")
    deadline: float = monotonic() + Constants.duration
    if arguments.source is not None:
        _ = FolderWatchCopy(
            source=arguments.source,
            destination=arguments.destination,
            interval=0.5,
            settle_time=0.5,
            exclusions=(".git", ".DS_Store", "__pycache__", "*.pyc"),
            inclusions=(),
            mirror_deletes=False,
            verbose=True,
        ).run(initial_sync=True, should_stop=_stopper(deadline=deadline))
        return 0
    watchers: list[Thread] = []
    watcher: FolderWatchCopy
    for watcher in _bundled_watchers():
        worker: Thread = Thread(
            target=watcher.run,
            kwargs={
                "initial_sync": True,
                "should_stop": _stopper(deadline=deadline),
            },
            daemon=True,
        )
        watchers.append(worker)
    threads: tuple[Thread, ...] = tuple(watchers)
    thread: Thread
    for thread in threads:
        thread.start()
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
