# Copyright (c) 2026 Project contributors
"""Verify the workspace codec keeps selector fields and run causes."""

from __future__ import annotations

from json import dumps, loads
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import dig, expect_equal, expect_none
from exactus.tools.record.model import (
    ActionRunRecord,
    ActionRunStatus,
    TimelineEvent,
)
from exactus.tools.record.selectors import Pace, RunMode, TargetScope
from exactus.tools.record.store import WorkspaceCodec, WorkspaceError
from exactus.tools.record.workspace_actions import (
    actions_to_events,
    build_flow,
    build_workspace,
)

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


def _document() -> dict[str, JsonValue]:
    """Return a one-action workspace document in the current schema.

    Returns:
        A workspace whose only action clicks ``#go``.

    """
    events: list[dict[str, JsonValue]] = actions_to_events(
        actions=cast(
            typ="list[dict[str, JsonValue]]",
            val=[
                {
                    "type": "click",
                    "target": {"locators": [{"kind": "css", "value": "#go"}]},
                },
            ],
        ),
        flow_id="f1",
    )
    return build_workspace(
        flows=[build_flow(flow_id="f1", name="Flow", events=events)],
    )


def _first_event(*, document: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Return the editable JSON of the first action.

    Args:
        document: Workspace document.

    Returns:
        The action's JSON object.

    """
    return cast(
        typ="dict[str, JsonValue]",
        val=dig(document=document, path=("flows", 0, "events", 0)),
    )


def test_old_documents_load_with_defaults() -> None:
    """Treat a document without the new keys as a plain first-match action."""
    event: TimelineEvent = (
        WorkspaceCodec.from_json_value(value=_document()).flows[0].events[0]
    )
    expect_none(value=event.selector_id)
    expect_equal(actual=event.targets, expected=TargetScope.FIRST)
    expect_equal(actual=event.run_mode, expected=RunMode.SEQUENTIAL)
    expect_none(value=event.pace_between)
    expect_none(value=event.contract.pace)
    expect_equal(actual=event.sandbox, expected=False)


def test_selector_fields_round_trip() -> None:
    """Keep the reference, the targeting mode and both paces."""
    document: dict[str, JsonValue] = _document()
    raw: dict[str, JsonValue] = _first_event(document=document)
    contract: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=raw["contract"],
    )
    raw.update(
        selector=None,
        selector_id="sel-1",
        targets="all",
        run_mode="sequential",
        pace_between={
            "delay_ms": 20,
            "until": "sel_card_count >= 3",
            "poll_ms": 50,
            "timeout_ms": 900,
        },
    )
    contract["pace"] = {
        "delay_ms": 5,
        "until": None,
        "poll_ms": 100,
        "timeout_ms": 5000,
    }
    event: TimelineEvent = (
        WorkspaceCodec.from_json_value(value=document).flows[0].events[0]
    )
    expect_equal(actual=event.selector_id, expected="sel-1")
    expect_equal(actual=event.targets, expected=TargetScope.ALL)
    expect_equal(
        actual=event.pace_between,
        expected=Pace(
            delay_ms=20,
            until="sel_card_count >= 3",
            poll_ms=50,
            timeout_ms=900,
        ),
    )
    expect_equal(actual=event.contract.pace, expected=Pace(delay_ms=5))
    again: JsonValue = WorkspaceCodec.event_to_json_value(event=event)
    expect_equal(
        actual=dig(document=again, path=("selector_id",)),
        expected="sel-1",
    )
    expect_equal(actual=dig(document=again, path=("targets",)), expected="all")
    expect_equal(
        actual=dig(document=again, path=("contract", "pace", "delay_ms")),
        expected=5,
    )
    expect_equal(
        actual=loads(s=dumps(obj=again))["pace_between"]["until"],
        expected="sel_card_count >= 3",
    )


@pytest.mark.parametrize(
    "change",
    [
        {"targets": "some"},
        {"run_mode": "later"},
        {"selector": "#x", "selector_id": "sel-1"},
        {"pace_between": {"delay_ms": -1}},
        {"run_mode": "parallel", "targets": "all"},
    ],
)
def test_invalid_selector_fields_are_workspace_errors(
    change: dict[str, JsonValue],
) -> None:
    """Report bad targeting data as a workspace error.

    Args:
        change: Event fields that cannot be combined or parsed.

    """
    document: dict[str, JsonValue] = _document()
    _first_event(document=document).update(change)
    with pytest.raises(expected_exception=(WorkspaceError, ValueError)):
        _ = WorkspaceCodec.from_json_value(value=document)


def test_run_records_keep_cause_unit_and_warning_status() -> None:
    """Round-trip the failure cause and the target position."""
    record: ActionRunRecord = ActionRunRecord(
        event_id="e1",
        flow_id="f1",
        status=ActionRunStatus.WARNING,
        attempt=1,
        started_ms=0,
        finished_ms=5,
        error="No match",
        response_json="null",
        cause_json='{"phase": "count", "found_count": 0}',
        unit_index=1,
        unit_count=3,
    )
    value: JsonValue = WorkspaceCodec.action_record_to_json_value(
        record=record,
    )
    expect_equal(
        actual=dig(document=value, path=("status",)),
        expected="warning",
    )
    expect_equal(
        actual=dig(document=value, path=("unit", "count")),
        expected=3,
    )
    expect_equal(
        actual=dig(document=value, path=("cause", "phase")),
        expected="count",
    )
    expect_equal(
        actual=WorkspaceCodec.action_record_from_json_value(value=value),
        expected=record,
    )
    plain: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=WorkspaceCodec.action_record_to_json_value(
            record=ActionRunRecord(
                event_id="e1",
                flow_id="f1",
                status=ActionRunStatus.SUCCEEDED,
                attempt=1,
                started_ms=0,
                finished_ms=1,
            ),
        ),
    )
    expect_none(value=plain["cause"])
    expect_none(value=plain["unit"])


def test_a_half_described_unit_is_rejected() -> None:
    """Refuse a unit with an index but no count."""
    with pytest.raises(expected_exception=ValueError, match="unit count"):
        _ = ActionRunRecord(
            event_id="e1",
            flow_id="f1",
            status=ActionRunStatus.SUCCEEDED,
            attempt=1,
            started_ms=0,
            finished_ms=1,
            unit_index=0,
        )
