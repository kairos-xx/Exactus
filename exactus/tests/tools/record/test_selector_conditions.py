# Copyright (c) 2026 Project contributors
"""Wait for conditions that read selector probes, and feed connections."""

from __future__ import annotations

from dataclasses import replace
from textwrap import dedent
from typing import TYPE_CHECKING, Final, cast, final

import pytest
from playwright.sync_api import Browser, sync_playwright

from exactus.tests.common.support import (
    dig,
    expect_equal,
    expect_in,
    expect_true,
)
from exactus.tests.tools.record.selector_support import project
from exactus.tools.record.flow_runner import FlowRunner
from exactus.tools.record.model import (
    ActionContract,
    EventKind,
    FlowEdge,
    RuntimeVariable,
    TimelineEvent,
    TimelineLayer,
    TransitionMode,
    ValueType,
    Workspace,
)
from exactus.tools.record.selector_probes import (
    ProbeRef,
    edge_probe_names,
    probe_refs,
    probe_variables,
)
from exactus.tools.record.selector_resolver import SelectorResolver
from exactus.tools.record.selectors import Pace, SelectorCodec, SelectorDef
from exactus.tools.record.store import WorkspaceCodec

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from playwright.sync_api import Page

    from exactus.tools.record.workspace_actions import Event


@final
class Constants:
    """Group module-level constants.

    Attributes:
        minimum_wait_ms: Grouped module constant.
        html: Grouped module constant.
        rows: Grouped module constant.
        late: Grouped module constant.

    """

    minimum_wait_ms: Final[int] = 250
    html: Final[str] = dedent(
        text=(
            '    \n    <p class="row" id="r1">one</p><p class="row" id="r2">tw'
            'o</p>\n    <p class="row" id="r3" style="display:none">three</p>'
            '\n    <button id="go">Go</button>\n    '
        ),
    )
    rows: Final[SelectorDef] = SelectorDef(
        selector_id="sel-rows",
        name="rows",
        expression=".row",
        expected_count=None,
    )
    late: Final[SelectorDef] = SelectorDef(
        selector_id="sel-late",
        name="late",
        expression=".late",
        expected_count=None,
    )


@pytest.fixture
def page() -> Iterator[Page]:
    """Create a disposable page with three rows, one hidden.

    Yields:
        A Chromium page.

    """
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        opened: Page = browser.new_page()
        opened.set_content(html=Constants.html)
        yield opened
        browser.close()


def test_probe_references_are_found_once_in_order() -> None:
    """Read each probe a condition mentions a single time."""
    refs: tuple[ProbeRef, ...] = probe_refs(
        conditions=(
            "sel_rows_count >= 2 and not sel_spinner_exists",
            "sel_rows_count < 9 or sel_rows_text == 'a'",
        ),
    )
    expect_equal(
        actual=[ref.variable for ref in refs],
        expected=["sel_rows_count", "sel_spinner_exists", "sel_rows_text"],
    )
    expect_equal(actual=refs[1].selector_name, expected="spinner")
    expect_equal(actual=refs[1].probe, expected="exists")


def test_probes_measure_the_page(page: Page) -> None:
    """Publish count, existence, visibility, text and enabled state.

    Args:
        page: Page with three rows, one hidden.

    """
    refs: tuple[ProbeRef, ...] = probe_refs(
        conditions=(
            "sel_rows_count sel_rows_exists sel_rows_visible sel_rows_text "
            "sel_rows_enabled sel_late_exists",
        ),
    )
    variables: tuple[RuntimeVariable, ...] = probe_variables(
        resolver=SelectorResolver(
            page=page,
            selectors=(Constants.rows, Constants.late),
        ),
        selectors=(Constants.rows, Constants.late),
        refs=refs,
    )
    measured: dict[str, object] = {
        variable.name: variable.value for variable in variables
    }
    expect_equal(actual=measured["sel_rows_count"], expected=3)
    expect_equal(actual=measured["sel_rows_exists"], expected=True)
    expect_equal(actual=measured["sel_rows_visible"], expected=False)
    expect_equal(actual=measured["sel_rows_text"], expected="one")
    expect_equal(actual=measured["sel_late_exists"], expected=False)
    expect_equal(
        actual=next(
            v for v in variables if v.name == "sel_rows_count"
        ).value_type,
        expected=ValueType.INTEGER,
    )


def test_a_probe_for_a_missing_selector_is_an_error(page: Page) -> None:
    """Name the selector that does not exist.

    Args:
        page: Page with rows.

    """
    with pytest.raises(expected_exception=ValueError, match="'ghost'"):
        _ = probe_variables(
            resolver=SelectorResolver(page=page),
            selectors=(),
            refs=probe_refs(conditions=("sel_ghost_count > 0",)),
        )


def _click(
    *,
    event_id: str,
    sequence: int,
    pace: Pace | None = None,
) -> TimelineEvent:
    """Build a click on the Go button, optionally followed by a wait.

    Args:
        event_id: Action identifier.
        sequence: Position in the flow.
        pace: Wait applied after the action.

    Returns:
        The action.

    """
    return TimelineEvent(
        event_id=event_id,
        flow_id="flow-a",
        sequence=sequence,
        elapsed_ms=0,
        layer=TimelineLayer.INTERACTION,
        kind=EventKind.CLICK,
        label=event_id,
        selector="#go",
        contract=ActionContract(pace=pace),
    )


def _run(
    *,
    page: Page,
    tmp_path: Path,
    events: list[TimelineEvent],
    extra: dict[str, object] | None = None,
) -> Event:
    """Run actions with the test selectors.

    Args:
        page: Page with the rows.
        tmp_path: Evidence directory.
        events: Actions in order.
        extra: More fields for the run message.

    Returns:
        The flow result.

    """
    message: Event = cast(
        typ="Event",
        val={
            "flow_id": "flow-a",
            "events": [
                WorkspaceCodec.event_to_json_value(event=event)
                for event in events
            ],
            "selectors": [
                SelectorCodec.selector_to_json(item=item)
                for item in (Constants.rows, Constants.late)
            ],
            **(extra or {}),
        },
    )
    return FlowRunner(output=tmp_path, timeout_ms=800).run(
        page=page,
        message=message,
    )


def test_a_pace_waits_for_a_condition_that_becomes_true(
    page: Page,
    tmp_path: Path,
) -> None:
    """Hold the next action until an element appears.

    Args:
        page: Page with the rows.
        tmp_path: Evidence directory.

    """
    _ = page.evaluate(
        expression=dedent(
            text=(
                "    () => setTimeout(() => {\n                const late "
                '= document.createElement("p");\n                late.clas'
                'sName = "late";\n                document.body.append(lat'
                "e);\n            }, 1500)"
            ),
        ),
    )
    result: Event = _run(
        page=page,
        tmp_path=tmp_path,
        events=[
            _click(
                event_id="first",
                sequence=0,
                pace=Pace(
                    until="sel_late_exists",
                    poll_ms=50,
                    timeout_ms=6000,
                ),
            ),
            _click(event_id="second", sequence=1),
        ],
    )
    records: list[Event] = cast(
        typ="list[Event]",
        val=result["action_records"],
    )
    expect_equal(actual=result["status"], expected="succeeded")
    expect_equal(
        actual=[record["event_id"] for record in records],
        expected=["first", "second"],
    )
    gap: int = cast(typ="int", val=records[1]["started_ms"]) - cast(
        typ="int",
        val=records[0]["finished_ms"],
    )
    expect_true(condition=gap >= Constants.minimum_wait_ms)


def test_a_condition_that_never_holds_fails_the_gate(
    page: Page,
    tmp_path: Path,
) -> None:
    """Report a gate timeout and skip what follows.

    Args:
        page: Page with the rows.
        tmp_path: Evidence directory.

    """
    result: Event = _run(
        page=page,
        tmp_path=tmp_path,
        events=[
            _click(
                event_id="first",
                sequence=0,
                pace=Pace(until="sel_late_exists", poll_ms=50, timeout_ms=200),
            ),
            _click(event_id="second", sequence=1),
        ],
    )
    records: list[Event] = cast(
        typ="list[Event]",
        val=result["action_records"],
    )
    expect_equal(
        actual=[record["status"] for record in records],
        expected=["succeeded", "failed", "skipped"],
    )
    expect_equal(
        actual=dig(document=records[1], path=("cause", "phase")),
        expected="gate",
    )
    expect_in(
        member="Timed out after 200 ms",
        container=str(object=records[1]["error"]),
    )
    expect_equal(actual=result["status"], expected="failed")


def test_a_tolerated_gate_failure_lets_the_flow_continue(
    page: Page,
    tmp_path: Path,
) -> None:
    """Show a warning and run the next action anyway.

    Args:
        page: Page with the rows.
        tmp_path: Evidence directory.

    """
    first: TimelineEvent = replace(
        _click(
            event_id="first",
            sequence=0,
            pace=Pace(until="sel_late_exists", poll_ms=50, timeout_ms=150),
        ),
        contract=ActionContract(
            continue_on_failure=True,
            pace=Pace(until="sel_late_exists", poll_ms=50, timeout_ms=150),
        ),
    )
    result: Event = _run(
        page=page,
        tmp_path=tmp_path,
        events=[first, _click(event_id="second", sequence=1)],
    )
    records: list[Event] = cast(
        typ="list[Event]",
        val=result["action_records"],
    )
    expect_equal(
        actual=[record["status"] for record in records],
        expected=["succeeded", "warning", "succeeded"],
    )


def test_an_invalid_condition_fails_at_once(
    page: Page,
    tmp_path: Path,
) -> None:
    """Do not poll for a condition that cannot be evaluated.

    Args:
        page: Page with the rows.
        tmp_path: Evidence directory.

    """
    result: Event = _run(
        page=page,
        tmp_path=tmp_path,
        events=[
            _click(
                event_id="first",
                sequence=0,
                pace=Pace(until="missing_variable > 1", timeout_ms=5000),
            ),
        ],
    )
    records: list[Event] = cast(
        typ="list[Event]",
        val=result["action_records"],
    )
    expect_in(
        member="Unknown variable",
        container=str(object=records[1]["error"]),
    )
    expect_equal(
        actual=dig(document=records[1], path=("cause", "phase")),
        expected="gate",
    )


def test_connection_probes_come_back_as_flow_outputs(
    page: Page,
    tmp_path: Path,
) -> None:
    """Measure what the leaving connections read, when the flow ends.

    Args:
        page: Page with the rows.
        tmp_path: Evidence directory.

    """
    result: Event = _run(
        page=page,
        tmp_path=tmp_path,
        events=[_click(event_id="first", sequence=0)],
        extra={"probes": ["sel_rows_count", "sel_rows_exists"]},
    )
    outputs: list[Event] = cast(typ="list[Event]", val=result["outputs"])
    expect_equal(
        actual={item["name"]: item["value"] for item in outputs},
        expected={"sel_rows_count": 3, "sel_rows_exists": True},
    )


def test_edge_probe_names_come_from_the_leaving_connections() -> None:
    """Ask only for the probes a flow's own connections read."""
    base: Workspace = project()
    workspace: Workspace = replace(
        base,
        edges=(
            FlowEdge(
                source_flow_id="f1",
                target_flow_id="f2",
                mode=TransitionMode.CONDITION,
                condition_expression="flow_succeeded and sel_card_exists",
            ),
            FlowEdge(
                source_flow_id="f2",
                target_flow_id="f1",
                mode=TransitionMode.CONDITION,
                condition_expression="sel_other_count > 1",
            ),
        ),
    )
    expect_equal(
        actual=edge_probe_names(workspace=workspace, flow_id="f1"),
        expected=("sel_card_exists",),
    )
    expect_equal(
        actual=edge_probe_names(workspace=workspace, flow_id="f3"),
        expected=(),
    )
