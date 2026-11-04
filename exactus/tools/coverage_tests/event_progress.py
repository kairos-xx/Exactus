# Copyright (c) 2026
"""Compose measured per-test events with the existing shard lifecycle."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Final

from exactus.tools.common.runtime import Progress, trace
from exactus.tools.coverage_tests.event_stream import ShardEvents

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.coverage_tests.shard_progress import ProgressSink


class EventProgressDefaults:
    """Own bounded optional telemetry policy.

    Attributes:
        grace: Seconds allowed for plugin initialization.
        label: Maximum visible nodeid label length.

    """

    grace: Final[float] = 5.0
    label: Final[int] = 200


def event_arguments(
    *,
    arguments: tuple[str, ...],
) -> tuple[Path | None, int | None]:
    """Read the optional events capability and expected count from argv.

    Args:
        arguments: One subprocess argument vector.

    Returns:
        Events sidecar and optional expected node count.

    """
    values: dict[str, str] = {}
    names: tuple[str, ...] = ("--exactus-events", "--exactus-events-total")
    for index, argument in enumerate(iterable=arguments):
        name, separator, value = argument.partition("=")
        if name in names:
            if separator:
                values[name] = value
            elif index + 1 < len(arguments):
                values[name] = arguments[index + 1]
    raw: str = values.get("--exactus-events", "")
    count: int | None = None
    try:
        if "--exactus-events-total" in values:
            count = max(0, int(values["--exactus-events-total"]))
    except ValueError:
        pass
    return (Path(raw) if raw else None), count


class TestBatchProgress:
    """Overlay bounded event snapshots without replacing task ownership."""

    def __init__(
        self,
        *,
        arguments: tuple[tuple[str, ...], ...],
        estimates: tuple[float, ...],
        sink: ProgressSink,
    ) -> None:
        """Bind all shard channels before any subprocess starts.

        Args:
            arguments: Command vectors carrying optional event capabilities.
            estimates: Existing fallback duration estimates.
            sink: Existing parent progress publisher.

        """
        inputs: tuple[tuple[Path | None, int | None], ...] = tuple(
            event_arguments(arguments=command) for command in arguments
        )
        self._readers: dict[int, ShardEvents] = {
            index: ShardEvents(path=path, expected=count)
            for index, (path, count) in enumerate(iterable=inputs)
            if path is not None
        }
        self._weights: tuple[float, ...] = (
            tuple(float(count or 1) for _path, count in inputs)
            if all(count is not None for _path, count in inputs)
            else tuple(1.0 for _item in inputs)
        )
        self._estimates: tuple[float, ...] = estimates
        self._sink: ProgressSink = sink
        self._started: dict[int, float] = {}
        self._fallback: set[int] = set()
        self._exited: set[int] = set()
        self._share: float = 0.0

    def publish(self, *, progress: Progress) -> None:
        """Publish real worker counts with monotonic phase completion.

        Args:
            progress: Existing shard-lifecycle snapshot.

        """
        if not self._readers:
            self._sink(progress=progress)
            return
        now: float = monotonic()
        workers: dict[str, JsonValue] = dict(progress.workers or {})
        amount: float = 0.0
        done_tests: int = 0
        for index, weight in enumerate(iterable=self._weights):
            raw: JsonValue = workers.get(str(object=index))
            if not isinstance(raw, dict):
                continue
            worker: dict[str, JsonValue] = dict(raw)
            worker, share, count = self._worker(
                index=index,
                worker=worker,
                now=now,
            )
            amount += weight * share
            done_tests += count
            workers[str(object=index)] = worker
        denominator: float = sum(self._weights)
        self._share = max(
            self._share,
            amount / denominator if denominator else 1.0,
        )
        mode: str = (
            "mixed estimated progress"
            if self._fallback
            else "per-test progress"
        )
        self._sink(
            progress=replace(
                progress,
                share=self._share,
                workers=workers,
                detail=f"{done_tests} tests finished; {mode}",
            ),
        )

    def _worker(
        self,
        *,
        index: int,
        worker: dict[str, JsonValue],
        now: float,
    ) -> tuple[dict[str, JsonValue], float, int]:
        """Update one worker's event channel and fallback state.

        Args:
            index: Command index.
            worker: Existing lifecycle fields.
            now: Current monotonic timestamp.

        Returns:
            Worker fields, completion share, and actual finished count.

        """
        state: JsonValue = worker.get("state")
        exited: bool = isinstance(state, str) and state in {"DONE", "FAIL"}
        started: float = self._started.setdefault(index, now)
        reader: ShardEvents | None = self._readers.get(index)
        if reader is not None:
            if exited:
                reader.drain()
            else:
                reader.poll()
        measured: float | None = reader.fraction() if reader else None
        if (
            reader is None
            or reader.disabled
            or (
                not reader.available
                and now - started >= EventProgressDefaults.grace
            )
        ):
            self._fallback.add(index)
        share: float = measured if measured is not None else 0.0
        if index in self._fallback:
            share = min(
                0.95,
                (now - started) / max(self._estimates[index], 0.001),
            )
        count: int = 0
        if reader is not None and (reader.collected or reader.current):
            count = len(reader.completed)
            current: str = (
                f"exit; last test: {reader.current}"
                if exited
                else reader.current
            )
            worker.update(
                completed=count,
                total=reader.total or 0,
                current=(current or "collecting tests")[
                    : EventProgressDefaults.label
                ],
            )
            if exited and index not in self._exited and state == "FAIL":
                trace(
                    step=(
                        f"shard {index + 1} failed; last test: "
                        f"{reader.current}"
                    ),
                    depth=3,
                )
        elif not exited:
            worker["current"] = (
                "running (estimated progress)"
                if index in self._fallback
                else "collecting tests (awaiting events)"
            )
        if exited:
            self._exited.add(index)
        return worker, 1.0 if exited else share, count
