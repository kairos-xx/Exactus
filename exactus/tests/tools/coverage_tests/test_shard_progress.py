# Copyright (c) 2026
"""Verify estimated liveness, real completion counts and ticker cleanup."""

from __future__ import annotations

from asyncio import Event, run, sleep, wait_for
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
    private_call,
)
from exactus.tools.coverage_tests.core import (
    CombinedCoverageRunner,
    CoverageConfig,
)
from exactus.tools.coverage_tests.shard_progress import ShardProgress

if TYPE_CHECKING:
    from pathlib import Path
    from typing import NoReturn

    from exactus.tools.common.runtime import Progress


def test_estimates_advance_without_inventing_completions() -> None:
    """Running work advances a bounded estimate and actual exits own counts."""
    now: list[float] = [0.0]
    events: list[Progress] = []

    def clock() -> float:
        """Return a controlled monotonic time.

        Returns:
            Controlled seconds.

        """
        return now[0]

    def publish(*, progress: Progress) -> None:
        """Capture emitted snapshots.

        Args:
            progress: Current estimate and real counts.

        """
        events.append(progress)

    tracker: ShardProgress = ShardProgress(
        estimates=(10.0, 20.0),
        phase=("pytest shard", (0.2, 0.5)),
        sink=publish,
        clock=clock,
    )
    tracker.started(shard=0)
    now[0] = 5.0
    partial: Progress = tracker.snapshot()
    expect_equal(actual=partial.completed, expected=0)
    expect_true(condition=0.0 < partial.fraction < 1.0)
    tracker.finished(shard=0, status=0)
    tracker.started(shard=1)
    now[0] = 1000.0
    stalled: Progress = tracker.snapshot()
    expect_equal(actual=stalled.completed, expected=1)
    expect_true(condition=stalled.fraction < 1.0)
    now[0] = 6.0
    expect_true(condition=tracker.snapshot().fraction >= stalled.fraction)
    tracker.finished(shard=1, status=1)
    expect_equal(actual=events[-1].completed, expected=2)
    expect_equal(actual=events[-1].fraction, expected=1.0)
    expect_equal(actual=events[-1].span, expected=(0.2, 0.5))
    expect_true(condition=events[-1].workers is not None)


@pytest.mark.parametrize("fail", [False, True])
def test_ticker_is_joined_on_success_and_failure(*, fail: bool) -> None:
    """Context exit never leaves a ticker publishing into another phase.

    Args:
        fail: Whether the owner raises before exiting.

    """

    def fail_owner() -> NoReturn:
        """Raise the modeled owner's failure.

        Raises:
            RuntimeError: Modeled owner failure.

        """
        msg: str = "owner failed"
        raise RuntimeError(msg)

    async def scenario() -> None:
        """Synchronize against a real ticker publication and verify cleanup."""
        ticked: Event = Event()
        events: list[Progress] = []

        def publish(*, progress: Progress) -> None:
            """Signal an actual estimated heartbeat.

            Args:
                progress: Current count and estimate.

            """
            events.append(progress)
            if progress.detail == "running (estimated progress)":
                ticked.set()

        tracker: ShardProgress = ShardProgress(
            estimates=(10.0,),
            phase=("pytest shard", (0.2, 0.6)),
            sink=publish,
            interval=0.001,
        )
        try:
            async with tracker:
                tracker.started(shard=0)
                await wait_for(fut=ticked.wait(), timeout=2.0)
                if fail:
                    fail_owner()
        except RuntimeError as error:
            expect_true(condition=fail)
            expect_equal(actual=str(object=error), expected="owner failed")
        count: int = len(events)
        await sleep(delay=0)
        expect_equal(actual=len(events), expected=count)
        expect_false(condition=events[-1].completed > 0)

    run(main=scenario())


@pytest.mark.parametrize(
    ("estimates", "regular_count"),
    [((40.0, 40.0, 120.0), 2), ((40.0, 40.0), 2), ((120.0,), 0)],
)
def test_exclusive_spans_never_restart_or_reverse(
    tmp_path: Path,
    estimates: tuple[float, ...],
    regular_count: int,
) -> None:
    """Mixed, parallel-only and serial-only plans share a bounded handoff.

    Args:
        tmp_path: Independent root.
        estimates: Expected shard work durations.
        regular_count: Number of parallel commands.

    """
    bounds: tuple[float, float] = (0.2, 0.6)
    runner: CombinedCoverageRunner = CombinedCoverageRunner(
        config=CoverageConfig(
            root=tmp_path,
            output=tmp_path / "out",
            source_roots=(tmp_path,),
            branch=True,
            fail_under=90,
            excluded_dirs=frozenset(),
            pytest_args=(),
            jobs=2,
        ),
    )
    spans: tuple[tuple[float, float], tuple[float, float]] = cast(
        typ="tuple[tuple[float, float], tuple[float, float]]",
        val=private_call(
            owner=runner,
            name="_shard_spans",
            estimates=estimates,
            regular_count=regular_count,
        ),
    )
    expect_equal(actual=spans[0][0], expected=bounds[0])
    expect_equal(actual=spans[0][1], expected=spans[1][0])
    expect_equal(actual=spans[1][1], expected=bounds[1])
    span_min: float = 0.2
    span_max: float = 0.6
    expect_true(condition=span_min <= spans[0][1] <= span_max)
