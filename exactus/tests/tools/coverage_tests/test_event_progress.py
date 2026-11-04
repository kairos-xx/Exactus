# Copyright (c) 2026
"""Verify measured shard overlays, bounded fallback and crash visibility."""

from __future__ import annotations

from json import dumps
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.common.runtime import Progress
from exactus.tools.coverage_tests import event_progress
from exactus.tools.coverage_tests.event_progress import (
    TestBatchProgress as BatchProgress,
)
from exactus.tools.coverage_tests.event_progress import (
    event_arguments,
)

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


def _write(*, path: Path, records: tuple[dict[str, JsonValue], ...]) -> None:
    """Write controlled version-one sidecar records.

    Args:
        path: Events file.
        records: Ordered payloads.

    """
    path.write_text(
        data="".join(
            dumps(obj={"version": 1, **record})
            + """\

"""
            for record in records
        ),
        encoding="utf-8",
    )


def _tracker(
    *,
    paths: tuple[Path, ...],
    counts: tuple[int | None, ...],
    snapshots: list[Progress],
) -> BatchProgress:
    """Build an overlay with a controlled sink.

    Args:
        paths: Per-command events paths.
        counts: Optional known node counts.
        snapshots: Captured publications.

    Returns:
        Event-aware batch overlay.

    """

    def capture(*, progress: Progress) -> None:
        """Capture one snapshot.

        Args:
            progress: Published event state.

        """
        snapshots.append(progress)

    return BatchProgress(
        arguments=tuple(
            (f"--exactus-events={path}",)
            + (
                (f"--exactus-events-total={count}",)
                if count is not None
                else ()
            )
            for path, count in zip(paths, counts, strict=True)
        ),
        estimates=tuple(100.0 for _path in paths),
        sink=capture,
    )


def _state(*, states: tuple[str, ...]) -> Progress:
    """Build the unmodified shard-count lifecycle snapshot.

    Args:
        states: Active or exited subprocess states.

    Returns:
        Base snapshot whose outer counts remain real shard exits.

    """
    return Progress(
        state="RUNNING",
        completed=sum(state != "RUNNING" for state in states),
        total=len(states),
        step="pytest shard",
        workers={
            str(object=index): {"state": state}
            for index, state in enumerate(iterable=states)
        },
    )


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (
            ("--exactus-events=a.jsonl", "--exactus-events-total=3"),
            (Path("a.jsonl"), 3),
        ),
        (
            ("--exactus-events", "a.jsonl", "--exactus-events-total", "bad"),
            (Path("a.jsonl"), None),
        ),
        (("-m", "pytest"), (None, None)),
    ],
)
def test_event_capability_arguments(
    arguments: tuple[str, ...],
    expected: tuple[Path | None, int | None],
) -> None:
    """Accept both option spellings and tolerate absent or malformed counts.

    Args:
        arguments: Subprocess arguments.
        expected: Parsed capability.

    """
    expect_equal(
        actual=event_arguments(arguments=arguments),
        expected=expected,
    )


def test_real_counts_weight_node_shards(tmp_path: Path) -> None:
    """Known totals produce actual global test fractions across workers.

    Args:
        tmp_path: Isolated events directory.

    """
    paths: tuple[Path, ...] = (tmp_path / "a", tmp_path / "b")
    snapshots: list[Progress] = []
    tracker: BatchProgress = _tracker(
        paths=paths,
        counts=(1, 3),
        snapshots=snapshots,
    )
    for path, count in zip(paths, (1, 3), strict=True):
        _write(
            path=path,
            records=(
                {"event": "collected", "count": count},
                {"event": "started", "nodeid": "test_file.py::running"},
                {"event": "finished", "nodeid": "test_file.py::previous"},
            ),
        )
    tracker.publish(progress=_state(states=("RUNNING", "RUNNING")))
    expect_equal(actual=snapshots[-1].share, expected=0.5)
    expect_equal(actual=snapshots[-1].completed, expected=0)
    expect_true(condition="2 tests finished" in snapshots[-1].detail)
    tracker.publish(progress=_state(states=("DONE", "FAIL")))
    expect_equal(actual=snapshots[-1].share, expected=1.0)
    expect_true(condition="running" in str(object=snapshots[-1].workers))


def test_ready_channel_never_times_out_a_slow_test(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A healthy channel stays measured during slow collection or tests.

    Args:
        tmp_path: Isolated events directory.
        monkeypatch: Controlled clock binding.

    """
    now: list[float] = [0.0]

    def clock() -> float:
        """Return controlled time.

        Returns:
            Current test timestamp.

        """
        return now[0]

    monkeypatch.setattr(target=event_progress, name="monotonic", value=clock)
    path: Path = tmp_path / "events"
    snapshots: list[Progress] = []
    tracker: BatchProgress = _tracker(
        paths=(path,),
        counts=(2,),
        snapshots=snapshots,
    )
    _write(path=path, records=({"event": "ready"},))
    tracker.publish(progress=_state(states=("RUNNING",)))
    now[0] = 500.0
    tracker.publish(progress=_state(states=("RUNNING",)))
    expect_equal(actual=snapshots[-1].share, expected=0.0)
    expect_true(condition="estimated" not in snapshots[-1].detail)


def test_missing_channel_falls_back_without_losing_monotonicity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unavailable sidecar retains bounded estimates and actual exits.

    Args:
        tmp_path: Missing sidecar directory.
        monkeypatch: Controlled clock binding.

    """
    now: list[float] = [0.0]

    def clock() -> float:
        """Return controlled time.

        Returns:
            Current test timestamp.

        """
        return now[0]

    monkeypatch.setattr(target=event_progress, name="monotonic", value=clock)
    snapshots: list[Progress] = []
    tracker: BatchProgress = _tracker(
        paths=(tmp_path / "absent",),
        counts=(None,),
        snapshots=snapshots,
    )
    tracker.publish(progress=_state(states=("RUNNING",)))
    now[0] = 50.0
    tracker.publish(progress=_state(states=("RUNNING",)))
    expect_equal(actual=snapshots[-1].share, expected=0.5)
    expect_true(condition="estimated" in snapshots[-1].detail)
    now[0] = 1.0
    tracker.publish(progress=_state(states=("RUNNING",)))
    expect_equal(actual=snapshots[-1].share, expected=0.5)


def test_file_mode_uses_fixed_shard_weights(tmp_path: Path) -> None:
    """Late collection does not change an already published denominator.

    Args:
        tmp_path: Isolated file-shard sidecars.

    """
    paths: tuple[Path, ...] = (tmp_path / "a", tmp_path / "b")
    snapshots: list[Progress] = []
    tracker: BatchProgress = _tracker(
        paths=paths,
        counts=(None, None),
        snapshots=snapshots,
    )
    _write(
        path=paths[0],
        records=(
            {"event": "collected", "count": 1},
            {"event": "finished", "nodeid": "a"},
        ),
    )
    tracker.publish(progress=_state(states=("RUNNING",)))
    expect_equal(actual=snapshots[-1].share, expected=0.5)
    _write(path=paths[1], records=({"event": "collected", "count": 100},))
    tracker.publish(progress=_state(states=("RUNNING", "RUNNING")))
    expect_equal(actual=snapshots[-1].share, expected=0.5)
