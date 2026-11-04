# Copyright (c) 2026
"""Tail bounded pytest event records without influencing test execution."""

from __future__ import annotations

from json import loads
from typing import TYPE_CHECKING, Final, cast

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


class EventLimits:
    """Bound telemetry memory, parsing work, and supported identities.

    Attributes:
        tick_bytes: Maximum bytes consumed by one poll.
        line_bytes: Maximum retained partial record.
        tests: Maximum distinct terminal node identities.
        exit_reads: Bounded drain passes after subprocess exit.

    """

    tick_bytes: Final[int] = 262144
    line_bytes: Final[int] = 65536
    tests: Final[int] = 100000
    exit_reads: Final[int] = 64


class ShardEvents:
    """Own a partial-line-safe JSONL reader and one shard's test state."""

    def __init__(self, *, path: Path, expected: int | None = None) -> None:
        """Bind a sidecar without requiring it to exist yet.

        Args:
            path: Unique subprocess-owned events sidecar.
            expected: Known node-shard test count, if available.

        """
        self.path: Path = path
        self.total: int | None = expected
        self.completed: set[str] = set()
        self.current: str = ""
        self.outcome: str = ""
        self.collected: bool = False
        self.available: bool = False
        self.disabled: bool = False
        self._offset: int = 0
        self._pending: bytes = b""

    def poll(self) -> None:
        """Consume complete records, bounded independently of file size."""
        if not self.disabled:
            try:
                with self.path.open(mode="rb") as stream:
                    if stream.seek(0, 2) < self._offset:
                        self.disabled = True
                        return
                    _ = stream.seek(self._offset)
                    chunk: bytes = stream.read(EventLimits.tick_bytes)
            except FileNotFoundError:
                return
            except OSError:
                self.disabled = True
                return
            self._offset += len(chunk)
            records: list[bytes] = (self._pending + chunk).split(sep=b"\n")
            self._pending = records.pop()
            if len(self._pending) > EventLimits.line_bytes:
                self.disabled = True
                self._pending = b""
                return
            for record in records:
                if len(record) > EventLimits.line_bytes:
                    self.disabled = True
                    return
                self._record(record=record)
                if self.disabled:
                    return

    def drain(self) -> None:
        """Read a bounded final backlog after the writer has exited."""
        for _index in range(EventLimits.exit_reads):
            previous: int = self._offset
            self.poll()
            if self.disabled or previous == self._offset:
                break

    def fraction(self) -> float | None:
        """Return measured test completion when collection is known.

        Returns:
            Completed fraction, or ``None`` until a denominator is known.

        """
        if self.total is None or self.disabled:
            return None
        if self.total == 0:
            return 1.0 if self.collected else 0.0
        return min(1.0, len(self.completed) / self.total)

    def _record(self, *, record: bytes) -> None:
        """Validate an optional record before applying bounded state.

        Args:
            record: One complete JSON line.

        """
        try:
            raw: object = loads(s=record)
        except (ValueError, RecursionError):
            return
        if not isinstance(raw, dict):
            return
        entry: dict[str, JsonValue] = cast(typ="dict[str, JsonValue]", val=raw)
        if entry.get("version") != 1:
            return
        self.available = True
        self._apply(entry=entry)

    def _apply(self, *, entry: dict[str, JsonValue]) -> None:
        """Apply a validated schema record.

        Args:
            entry: Decoded version-one event.

        """
        event: object = entry.get("event")
        if event == "collected":
            count: object = entry.get("count")
            if (
                isinstance(count, int)
                and not isinstance(count, bool)
                and 0 <= count <= EventLimits.tests
            ):
                self.total = count
                self.collected = True
            return
        nodeid: object = entry.get("nodeid")
        if not isinstance(nodeid, str) or not nodeid:
            return
        if event == "started":
            self.current = nodeid
            self.outcome = ""
        elif event == "report":
            outcome: object = entry.get("outcome")
            if isinstance(outcome, str):
                self.outcome = outcome
        elif event == "finished":
            if len(self.completed) >= EventLimits.tests:
                self.disabled = True
                return
            self.completed.add(nodeid)
