# Copyright (c) 2026 Project contributors
"""Verify selector references, targeting modes and lanes on actions."""

from __future__ import annotations

from dataclasses import replace

import pytest

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.record.model import (
    ActionContract,
    ActionLane,
    ActionRunStatus,
    EventKind,
    PositionPointerAction,
    TimelineEvent,
    TimelineLayer,
    Workspace,
    lane_of,
)
from exactus.tools.record.selectors import Pace, RunMode, TargetScope


def _event(
    *,
    kind: EventKind = EventKind.CLICK,
    selector: str | None = None,
    selector_id: str | None = "sel-1",
) -> TimelineEvent:
    """Build a valid action; tests change one targeting field with ``replace``.

    Args:
        kind: Action kind.
        selector: Inline selector.
        selector_id: Reusable selector reference.

    Returns:
        The action; validation runs on creation.

    """
    return TimelineEvent(
        event_id="e1",
        flow_id="f1",
        sequence=0,
        elapsed_ms=0,
        layer=TimelineLayer.INTERACTION,
        kind=kind,
        label="Action",
        selector=selector,
        selector_id=selector_id,
    )


def test_a_selector_reference_satisfies_the_selector_requirement() -> None:
    """Let ``selector_id`` stand in for the inline selector."""
    expect_equal(actual=_event().selector_id, expected="sel-1")
    expect_equal(
        actual=_event(selector="#go", selector_id=None).selector,
        expected="#go",
    )
    with pytest.raises(expected_exception=ValueError, match="CSS selector"):
        _ = _event(selector=None, selector_id=None)


def test_selector_and_selector_id_are_exclusive() -> None:
    """Reject an action that names both an inline and a reusable selector."""
    with pytest.raises(expected_exception=ValueError, match="not both"):
        _ = _event(selector="#go", selector_id="sel-1")


def test_position_pointer_cannot_use_a_selector_id() -> None:
    """Keep coordinate actions free of selectors."""
    with pytest.raises(expected_exception=ValueError, match="selectors"):
        _ = TimelineEvent(
            event_id="e1",
            flow_id="f1",
            sequence=0,
            elapsed_ms=0,
            layer=TimelineLayer.INTERACTION,
            kind=EventKind.POSITION_POINTER,
            label="Point",
            selector_id="sel-1",
            position_action=PositionPointerAction.HOVER,
            x=1,
            y=2,
        )


def test_all_targets_need_a_selector_and_pace_needs_all() -> None:
    """Allow ``all`` and a pause between targets only with a selector."""
    waiting: TimelineEvent = _event(kind=EventKind.WAIT, selector_id=None)
    with pytest.raises(
        expected_exception=ValueError,
        match="needs a selector",
    ):
        _ = replace(waiting, targets=TargetScope.ALL)
    with pytest.raises(
        expected_exception=ValueError,
        match="targets set to all",
    ):
        _ = replace(_event(), pace_between=Pace(delay_ms=10))
    event: TimelineEvent = replace(
        _event(),
        targets=TargetScope.ALL,
        pace_between=Pace(delay_ms=10),
    )
    expect_equal(actual=event.pace_between, expected=Pace(delay_ms=10))


def test_parallel_is_limited_to_free_lane_kinds() -> None:
    """Allow parallel only for kinds that do not own an input device."""
    allowed: TimelineEvent = replace(
        _event(kind=EventKind.JAVASCRIPT),
        sandbox=True,
        targets=TargetScope.ALL,
        run_mode=RunMode.PARALLEL,
    )
    expect_equal(actual=allowed.run_mode, expected=RunMode.PARALLEL)
    for kind in (EventKind.CLICK, EventKind.HOVER, EventKind.KEYSTROKE):
        with pytest.raises(expected_exception=ValueError, match="parallel"):
            _ = replace(
                _event(kind=kind),
                targets=TargetScope.ALL,
                run_mode=RunMode.PARALLEL,
            )
    with pytest.raises(
        expected_exception=ValueError,
        match="targets set to all",
    ):
        _ = replace(
            _event(kind=EventKind.JAVASCRIPT),
            run_mode=RunMode.PARALLEL,
        )


def test_sandbox_is_for_javascript_only() -> None:
    """Reject the sandbox flag on other kinds."""
    expect_true(
        condition=replace(
            _event(kind=EventKind.JAVASCRIPT),
            sandbox=True,
        ).sandbox,
    )
    with pytest.raises(expected_exception=ValueError, match="sandbox"):
        _ = replace(_event(kind=EventKind.CLICK), sandbox=True)


def test_javascript_that_targets_elements_needs_the_sandbox() -> None:
    """Only the sandbox can hand elements to a script."""
    with pytest.raises(expected_exception=ValueError, match="sandbox"):
        _ = replace(_event(kind=EventKind.JAVASCRIPT), targets=TargetScope.ALL)


def test_snapshot_needs_a_selector() -> None:
    """Require a target for snapshot actions."""
    expect_equal(
        actual=_event(kind=EventKind.SNAPSHOT).kind,
        expected=EventKind.SNAPSHOT,
    )
    with pytest.raises(expected_exception=ValueError, match="CSS selector"):
        _ = _event(kind=EventKind.SNAPSHOT, selector_id=None)


@pytest.mark.parametrize(
    ("kind", "lane"),
    [
        (EventKind.CLICK, ActionLane.POINTER),
        (EventKind.CHECK, ActionLane.POINTER),
        (EventKind.SCROLL, ActionLane.POINTER),
        (EventKind.KEYSTROKE, ActionLane.KEYBOARD),
        (EventKind.INPUT_TEXT, ActionLane.FREE),
        (EventKind.JAVASCRIPT, ActionLane.FREE),
        (EventKind.SNAPSHOT, ActionLane.FREE),
        (EventKind.WAIT, ActionLane.FREE),
    ],
)
def test_lane_of_follows_the_input_device(
    kind: EventKind,
    lane: ActionLane,
) -> None:
    """Map each kind to the device it occupies.

    Args:
        kind: Action kind.
        lane: Expected lane.

    """
    expect_equal(actual=lane_of(kind=kind), expected=lane)


def test_contract_pace_and_warning_status_exist() -> None:
    """Expose the new contract field and run status."""
    contract: ActionContract = ActionContract(pace=Pace(delay_ms=5))
    expect_equal(actual=contract.pace, expected=Pace(delay_ms=5))
    expect_equal(actual=ActionContract().pace, expected=None)
    expect_equal(actual=ActionRunStatus.WARNING.value, expected="warning")
    expect_equal(actual=Workspace(flows=(), edges=()).selectors, expected=())
