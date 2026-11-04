# Copyright (c) 2026
"""Publish honest shard counts with bounded, explicitly estimated liveness."""

from __future__ import annotations

from asyncio import CancelledError, Task, create_task, sleep
from math import isfinite
from time import monotonic
from typing import TYPE_CHECKING, Protocol, Self

from exactus.tools.common.runtime import Progress

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from exactus.tools.common.json_types import JsonValue


class ProgressSink(Protocol):
    """Accept an explicit progress snapshot without changing real counts."""

    def __call__(self, *, progress: Progress) -> None:
        """Publish one snapshot.

        Args:
            progress: Current count, estimate and worker state.

        """
        ...


class ShardProgress:
    """Own a cancellable liveness ticker for one isolated subprocess batch."""

    def __init__(
        self,
        *,
        estimates: tuple[float, ...],
        phase: tuple[str, tuple[float, float]],
        sink: ProgressSink,
        clock: Callable[[], float] = monotonic,
        interval: float = 1.0,
    ) -> None:
        """Bind work estimates and progress ownership without starting tasks.

        Args:
            estimates: Positive expected durations in command order.
            phase: Activity label and overall progress span.
            sink: Progress publisher.
            clock: Monotonic clock, injectable for deterministic tests.
            interval: Positive liveness publication interval in seconds.

        """
        self._estimates: tuple[float, ...] = tuple(
            max(value, 0.001) if isfinite(value) else 60.0
            for value in estimates
        )
        self._phase: tuple[str, tuple[float, float]] = phase
        self._sink: ProgressSink = sink
        self._clock: Callable[[], float] = clock
        self._interval: float = max(interval, 0.001)
        self._active: dict[int, float] = {}
        self._finished: dict[int, int] = {}
        self._share: float = 0.0
        self._ticker: Task[None] | None = None

    def snapshot(
        self,
        *,
        detail: str = "running (estimated progress)",
    ) -> Progress:
        """Calculate a monotonic estimate while keeping real counts.

        Args:
            detail: Honest event or estimated-liveness description.

        Returns:
            Count, bounded time estimate and per-worker state.

        """
        now: float = self._clock()
        weight: float = sum(self._estimates)
        done: float = sum(self._estimates[index] for index in self._finished)
        active: float = sum(
            self._estimates[index]
            * min(0.95, max(0.0, now - started) / self._estimates[index])
            for index, started in self._active.items()
        )
        self._share = max(
            self._share,
            (done + active) / weight if weight else 1.0,
        )
        workers: dict[str, JsonValue] = {
            str(object=index): {
                "state": "RUNNING",
                "completed": 0,
                "total": 1,
                "current": f"shard {index + 1} running (estimated)",
            }
            for index in self._active
        }
        finished_workers: dict[str, JsonValue] = {
            str(object=index): {
                "state": "DONE" if status == 0 else "FAIL",
                "completed": 1,
                "total": 1,
                "current": f"exit {status}",
            }
            for index, status in self._finished.items()
        }
        workers.update(finished_workers)
        return Progress(
            state="RUNNING",
            completed=len(self._finished),
            total=len(self._estimates),
            step=self._phase[0],
            detail=detail,
            span=self._phase[1],
            share=self._share,
            workers=workers,
        )

    def started(self, *, shard: int) -> None:
        """Announce an actually launched shard before its first completion.

        Args:
            shard: Zero-based command index.

        """
        self._active[shard] = self._clock()
        self._sink(
            progress=self.snapshot(
                detail=f"shard {shard + 1}/{len(self._estimates)} started",
            ),
        )

    def finished(self, *, shard: int, status: int) -> None:
        """Record one real subprocess exit and publish its result.

        Args:
            shard: Zero-based command index.
            status: Actual subprocess exit code.

        """
        self._active.pop(shard, None)
        self._finished[shard] = status
        self._sink(
            progress=self.snapshot(
                detail=f"shard {shard + 1}/{len(self._estimates)} exit {
                    status
                }",
            ),
        )

    async def __aenter__(self) -> Self:
        """Start the explicitly owned ticker.

        Returns:
            This batch's progress owner.

        """
        self._ticker = create_task(
            coro=self._tick(),
            name="exactus-shard-progress",
        )
        return self

    async def __aexit__(
        self,
        _kind: type[BaseException] | None,
        _error: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Cancel and join the ticker on every exit path.

        Args:
            _kind: Primary exception type.
            _error: Primary exception instance.
            _traceback: Primary exception traceback.

        """
        if self._ticker is not None:
            self._ticker.cancel()
            try:
                await self._ticker
            except CancelledError:
                pass
            except Exception as failure:
                if _error is None:
                    raise
                _error.add_note(
                    f"Shard progress cleanup also failed: {failure}",
                )
            finally:
                self._ticker = None

    async def _tick(self) -> None:
        """Publish bounded liveness until the owning context closes."""
        while True:
            await sleep(delay=self._interval)
            if self._active:
                self._sink(progress=self.snapshot())
