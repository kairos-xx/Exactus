# Copyright (c) 2026
"""Frontend progress uses completed work and ignores repeated attempts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.common.runtime import clear_progress, current_progress
from exactus.tools.frontend.progress import FrontendProgress
from exactus.tools.record.run import ReplayProgress, WorkflowProgress

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


def test_recipe_progress_advances_through_discovery_and_replay() -> None:
    """Publish intermediate progress across both Actions phases."""
    clear_progress()
    progress: FrontendProgress = FrontendProgress(actions=2)
    progress(event={"type": "actions_state", "state": "running"})
    progress(event={"type": "frontend_progress", "completed": 1, "total": 6})
    first: JsonValue = current_progress()["progress"]
    progress(event={"type": "frontend_progress", "completed": 6, "total": 6})
    second: JsonValue = current_progress()["progress"]
    progress(event={"type": "actions_state", "state": "running"})
    progress(event={"type": "frontend_progress", "fraction": 0.5})
    third: JsonValue = current_progress()["progress"]
    discovery_share: float = 0.49
    expect_true(
        condition=isinstance(first, float) and 0 < first < discovery_share,
    )
    expect_equal(actual=second, expected=0.49)
    expect_equal(actual=third, expected=0.735)
    clear_progress()


def test_replay_counts_retries_once() -> None:
    """Count distinct event IDs while preserving runtime completion details."""
    clear_progress()
    progress: ReplayProgress = ReplayProgress(
        observer=FrontendProgress(),
        total=3,
    )
    event: dict[str, JsonValue] = {
        "type": "action_result",
        "run_id": "run",
        "flow_id": "flow",
        "action_record": {"event_id": "first"},
    }
    progress(event=event)
    first: JsonValue = current_progress()["progress"]
    progress(event=event)
    expect_equal(actual=current_progress()["progress"], expected=first)
    progress(event={**event, "action_record": {"event_id": "second"}})
    expect_equal(actual=progress.completed, expected=2)
    fraction: JsonValue = current_progress()["progress"]
    expect_true(condition=isinstance(fraction, float) and 0 < fraction < 1)
    clear_progress()


def test_parallel_progress_waits_for_all_workers_and_counts_retries_once() -> (
    None
):
    """Publish combined worker completion through the heartbeat percentage."""
    clear_progress()
    progress: WorkflowProgress = WorkflowProgress(
        observer=FrontendProgress(),
        budgets={"short": 2, "long": 6},
    )
    event: dict[str, JsonValue] = {
        "type": "action_result",
        "workflow_entry": "short",
        "run_id": "first",
        "flow_id": "shared",
        "action_record": {"event_id": "one"},
    }
    progress(event=event)
    initial: JsonValue = current_progress()["progress"]
    progress(event=event)
    expect_equal(actual=current_progress()["progress"], expected=initial)
    progress(event={**event, "action_record": {"event_id": "two"}})
    progress(event={"type": "workflow_finished", "workflow_entry": "short"})
    expect_equal(actual=current_progress()["progress"], expected=0.245)
    # The same connected flow/action in another worker is separate work.
    progress(event={**event, "workflow_entry": "long", "run_id": "second"})
    expect_equal(actual=current_progress()["completed"], expected=1)
    expect_equal(actual=current_progress()["total"], expected=2)
    share: JsonValue = current_progress()["progress"]
    first_worker_share: float = 0.245
    replay_share: float = 0.98
    expect_true(
        condition=isinstance(share, float)
        and first_worker_share < share < replay_share,
    )
    workers: JsonValue = current_progress()["workers"]
    expect_true(condition=isinstance(workers, dict))
    if isinstance(workers, dict):
        lane: JsonValue = workers["long"]
        expect_true(condition=isinstance(lane, dict))
        if isinstance(lane, dict):
            expect_equal(actual=lane["completed"], expected=1)
            expect_equal(actual=lane["total"], expected=6)
    progress(
        event={
            "type": "action_started",
            "workflow_entry": "long",
            "event_id": "next action",
        },
    )
    expect_equal(actual=current_progress()["progress"], expected=share)
    expect_true(
        condition="next action" in str(object=current_progress()["detail"]),
    )
    # A branch or early failure can finish without visiting every saved action.
    progress(event={"type": "workflow_finished", "workflow_entry": "long"})
    expect_equal(actual=current_progress()["progress"], expected=0.98)
    expect_equal(actual=current_progress()["completed"], expected=2)
    clear_progress()
