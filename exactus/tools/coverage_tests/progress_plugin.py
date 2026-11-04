# Copyright (c) 2026
"""Publish optional pytest events without affecting test outcomes."""

from __future__ import annotations

from json import dumps
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from typing import Literal, TextIO

    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.main import Session
    from _pytest.reports import TestReport


class EventOpener(Protocol):
    """Retain a helper's Path opener independently of test monkeypatches."""

    def __call__(self, *, mode: Literal["a"], encoding: str) -> TextIO:
        """Open the bound sidecar for appending text.

        Args:
            mode: Append mode required by the event stream.
            encoding: JSONL text encoding.

        Returns:
            Context-managed text stream.

        """
        ...


class ProgressEvents:
    """Own one shard's optional append-only progress channel."""

    def __init__(self, *, output: Path) -> None:
        """Bind a helper-owned output without opening a descriptor.

        Args:
            output: Unique JSONL sidecar for this subprocess.

        """
        self._output: Path = output
        self._open_stream: EventOpener = output.open
        self._disabled: bool = False

    def ready(self) -> None:
        """Announce channel availability before potentially slow collection."""
        self._emit(event="ready")

    def pytest_collection_finish(self, session: Session) -> None:
        """Publish the actual collected count for this shard.

        Args:
            session: Collected pytest session.

        """
        self._emit(event="collected", count=len(session.items))

    def pytest_runtest_logstart(
        self,
        nodeid: str,
        location: tuple[str, int | None, str],
    ) -> None:
        """Identify the test that has entered setup.

        Args:
            nodeid: Full pytest node identity.
            location: Pytest source location.

        """
        _ = location
        self._emit(event="started", nodeid=nodeid)

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        """Record outcomes without counting completion before teardown.

        Args:
            report: Setup, call, or teardown report.

        """
        self._emit(
            event="report",
            nodeid=report.nodeid,
            when=report.when,
            outcome=report.outcome,
        )

    def pytest_runtest_logfinish(
        self,
        nodeid: str,
        location: tuple[str, int | None, str],
    ) -> None:
        """Count a completed protocol including teardown and setup skips.

        Args:
            nodeid: Full pytest node identity.
            location: Pytest source location.

        """
        _ = location
        self._emit(event="finished", nodeid=nodeid)

    def _emit(self, *, event: str, **fields: str | int) -> None:
        """Append one bounded event, disabling telemetry on I/O failure.

        Args:
            event: Stable event category.
            **fields: Small JSON event fields.

        """
        if self._disabled:
            return
        try:
            with self._open_stream(
                mode="a",
                encoding="utf-8",
            ) as stream:
                _ = stream.write(
                    dumps(obj={"version": 1, "event": event, **fields})
                    + """\

""",
                )
                stream.flush()
        except (OSError, UnicodeError):
            self._disabled = True


def pytest_addoption(parser: Parser) -> None:
    """Register the optional internal progress destination.

    Args:
        parser: Pytest option parser.

    """
    _ = parser.addoption(
        "--exactus-events",
        action="store",
        default=None,
        help="Write optional per-test Exactus progress events.",
    )
    _ = parser.addoption(
        "--exactus-events-total",
        action="store",
        default=None,
        help="Expected node-shard test count for the parent tracker.",
    )


def pytest_configure(config: Config) -> None:
    """Register a session-owned writer when an events path is supplied.

    Args:
        config: Active pytest configuration and plugin owner.

    """
    output: object = config.getoption(name="--exactus-events")
    if isinstance(output, str) and output:
        writer: ProgressEvents = ProgressEvents(output=Path(output))
        writer.ready()
        _ = config.pluginmanager.register(
            plugin=writer,
            name="exactus-progress-events",
        )
