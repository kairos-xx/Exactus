# Copyright (c) 2026 Project contributors
"""Run actions that use stored selectors, several targets and pacing."""

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
    expect_none,
    expect_true,
)
from exactus.tools.record.flow_runner import FlowRunner
from exactus.tools.record.model import (
    ActionContract,
    EventKind,
    TimelineEvent,
    TimelineLayer,
)
from exactus.tools.record.selectors import (
    Pace,
    SelectorCodec,
    SelectorDef,
    TargetScope,
)
from exactus.tools.record.store import WorkspaceCodec

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from playwright.sync_api import Page

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.workspace_actions import Event


@final
class Constants:
    """Group module-level constants.

    Attributes:
        minimum_gap_ms: Grouped module constant.
        html: Grouped module constant.
        buttons: Grouped module constant.

    """

    minimum_gap_ms: Final[int] = 120
    html: Final[str] = dedent(
        text=(
            '    \n    <button class="b" data-p="2" id="b1">one</button>\n    '
            '<button class="b" data-p="3" id="b2">two</button>\n    <button cl'
            'ass="b" data-p="1" id="b3">three</button>\n    <script>\n      wi'
            'ndow.log = [];\n      document.querySelectorAll(".b").forEach((b)'
            ' =>\n        b.addEventListener("click", () => window.log.push(b.'
            "id)));\n    </script>\n    "
        ),
    )
    buttons: Final[SelectorDef] = SelectorDef(
        selector_id="sel-b",
        name="buttons",
        expression="sort(.b, [data-p])",
        expected_count=3,
    )


@pytest.fixture
def page() -> Iterator[Page]:
    """Create a disposable page with three clickable buttons.

    Yields:
        A Chromium page whose clicks are recorded in ``window.log``.

    """
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        opened: Page = browser.new_page()
        opened.set_content(html=Constants.html)
        yield opened
        browser.close()


def _click(*, event_id: str = "click", sequence: int = 0) -> TimelineEvent:
    """Build a click on the first button.

    Args:
        event_id: Action identifier.
        sequence: Position in the flow.

    Returns:
        A click action; tests change its targeting with ``replace``.

    """
    return TimelineEvent(
        event_id=event_id,
        flow_id="test",
        sequence=sequence,
        elapsed_ms=0,
        layer=TimelineLayer.INTERACTION,
        kind=EventKind.CLICK,
        label="Click",
        selector="#b1",
    )


def _run(
    *,
    page: Page,
    tmp_path: Path,
    events: list[TimelineEvent],
    selectors: tuple[SelectorDef, ...] = (),
) -> tuple[Event, list[Event]]:
    """Run actions through the real runner.

    Args:
        page: Page with the buttons.
        tmp_path: Evidence directory.
        events: Actions in order.
        selectors: Stored selectors the actions may use.

    Returns:
        The flow result and its action records.

    """
    result: Event = FlowRunner(output=tmp_path, timeout_ms=800).run(
        page=page,
        message={
            "flow_id": "test",
            "events": [
                WorkspaceCodec.event_to_json_value(event=event)
                for event in events
            ],
            "selectors": [
                SelectorCodec.selector_to_json(item=item) for item in selectors
            ],
        },
    )
    return (result, cast(typ="list[Event]", val=result["action_records"]))


def _log(*, page: Page) -> list[str]:
    """Return the ids of the buttons clicked so far.

    Args:
        page: Page with the buttons.

    Returns:
        Click order recorded by the page.

    """
    return cast(typ="list[str]", val=page.evaluate(expression="window.log"))


def test_all_targets_run_in_the_selectors_own_order(
    page: Page,
    tmp_path: Path,
) -> None:
    """Click every match, ordered by the selector's sort.

    Args:
        page: Page with the buttons.
        tmp_path: Evidence directory.

    """
    event: TimelineEvent = replace(
        _click(),
        selector=None,
        selector_id="sel-b",
        targets=TargetScope.ALL,
    )
    result, records = _run(
        page=page,
        tmp_path=tmp_path,
        events=[event],
        selectors=(Constants.buttons,),
    )
    expect_equal(actual=result["status"], expected="succeeded")
    expect_equal(actual=_log(page=page), expected=["b3", "b1", "b2"])
    expect_equal(
        actual=[record["unit"] for record in records],
        expected=[
            {"index": 0, "count": 3},
            {"index": 1, "count": 3},
            {"index": 2, "count": 3},
        ],
    )


def test_first_target_only_acts_on_the_first_match(
    page: Page,
    tmp_path: Path,
) -> None:
    """Click only the first element in the selector's order.

    Args:
        page: Page with the buttons.
        tmp_path: Evidence directory.

    """
    anything: SelectorDef = replace(Constants.buttons, expected_count=None)
    event: TimelineEvent = replace(
        _click(),
        selector=None,
        selector_id="sel-b",
    )
    _, records = _run(
        page=page,
        tmp_path=tmp_path,
        events=[event],
        selectors=(anything,),
    )
    expect_equal(actual=_log(page=page), expected=["b3"])
    expect_none(value=records[0]["unit"])


def test_inline_expressions_and_plain_selectors_expand(
    page: Page,
    tmp_path: Path,
) -> None:
    """Support ``ext=`` expressions and ``all`` on ordinary selectors.

    Args:
        page: Page with the buttons.
        tmp_path: Evidence directory.

    """
    inline: TimelineEvent = replace(
        _click(),
        selector="ext=sort(.b, -[data-p])",
        targets=TargetScope.ALL,
    )
    _ = _run(page=page, tmp_path=tmp_path, events=[inline])
    expect_equal(actual=_log(page=page), expected=["b2", "b1", "b3"])
    page.evaluate(expression="window.log.length = 0")
    plain: TimelineEvent = replace(
        _click(),
        selector=".b",
        targets=TargetScope.ALL,
    )
    _ = _run(page=page, tmp_path=tmp_path, events=[plain])
    expect_equal(actual=_log(page=page), expected=["b1", "b2", "b3"])


def test_an_unresolvable_selector_fails_with_a_cause(
    page: Page,
    tmp_path: Path,
) -> None:
    """Report the count, not a Playwright timeout, when nothing matches.

    Args:
        page: Page with the buttons.
        tmp_path: Evidence directory.

    """
    missing: SelectorDef = replace(
        Constants.buttons,
        expression=".nothing",
        expected_count=1,
    )
    event: TimelineEvent = replace(
        _click(),
        selector=None,
        selector_id="sel-b",
    )
    result, records = _run(
        page=page,
        tmp_path=tmp_path,
        events=[event],
        selectors=(missing,),
    )
    expect_equal(actual=result["status"], expected="failed")
    expect_equal(actual=records[0]["status"], expected="failed")
    expect_equal(
        actual=dig(document=records[0], path=("cause", "phase")),
        expected="count",
    )
    expect_equal(actual=_log(page=page), expected=[])


def test_unknown_selector_ids_are_reported(page: Page, tmp_path: Path) -> None:
    """Fail with a clear message for a selector that was deleted.

    Args:
        page: Page with the buttons.
        tmp_path: Evidence directory.

    """
    event: TimelineEvent = replace(
        _click(),
        selector=None,
        selector_id="sel-gone",
    )
    _, records = _run(page=page, tmp_path=tmp_path, events=[event])
    expect_in(
        member="Unknown selector: sel-gone",
        container=str(object=records[0]["error"]),
    )


def test_tolerated_failures_warn_and_the_flow_continues(
    page: Page,
    tmp_path: Path,
) -> None:
    """Mark a tolerated failure as a warning and run the next action.

    Args:
        page: Page with the buttons.
        tmp_path: Evidence directory.

    """
    broken: TimelineEvent = replace(
        _click(),
        selector="#nope",
        contract=ActionContract(continue_on_failure=True),
    )
    later: TimelineEvent = replace(_click(event_id="later", sequence=1))
    result, records = _run(
        page=page,
        tmp_path=tmp_path,
        events=[broken, later],
    )
    expect_equal(
        actual=[record["status"] for record in records],
        expected=["warning", "succeeded"],
    )
    expect_equal(actual=_log(page=page), expected=["b1"])
    expect_equal(actual=result["status"], expected="failed")
    expect_in(
        member="#nope",
        container=str(
            object=dig(document=records[0], path=("cause", "resolved_css")),
        ),
    )


def test_a_failed_target_skips_the_remaining_targets(
    page: Page,
    tmp_path: Path,
) -> None:
    """Stop after the first failing target unless failures are tolerated.

    Args:
        page: Page with the buttons.
        tmp_path: Evidence directory.

    """
    page.evaluate(expression="document.getElementById('b2').disabled = true")
    event: TimelineEvent = replace(
        _click(),
        selector=".b",
        targets=TargetScope.ALL,
    )
    _, records = _run(page=page, tmp_path=tmp_path, events=[event])
    expect_equal(
        actual=[record["status"] for record in records],
        expected=["succeeded", "failed", "skipped"],
    )
    expect_equal(actual=_log(page=page), expected=["b1"])
    expect_equal(
        actual=dig(document=records[1], path=("cause", "phase")),
        expected="timeout",
    )
    expect_equal(
        actual=dig(document=records[1], path=("cause", "target_index")),
        expected=1,
    )


def test_tolerated_target_failures_keep_the_rest_running(
    page: Page,
    tmp_path: Path,
) -> None:
    """Carry on with later targets when the action tolerates failure.

    Args:
        page: Page with the buttons.
        tmp_path: Evidence directory.

    """
    page.evaluate(expression="document.getElementById('b2').disabled = true")
    event: TimelineEvent = replace(
        _click(),
        selector=".b",
        targets=TargetScope.ALL,
        contract=ActionContract(continue_on_failure=True),
    )
    _, records = _run(page=page, tmp_path=tmp_path, events=[event])
    expect_equal(
        actual=[record["status"] for record in records],
        expected=["succeeded", "warning", "succeeded"],
    )
    expect_equal(actual=_log(page=page), expected=["b1", "b3"])


def test_pause_between_targets_and_after_the_action(
    page: Page,
    tmp_path: Path,
) -> None:
    """Wait the configured time between targets.

    Args:
        page: Page with the buttons.
        tmp_path: Evidence directory.

    """
    event: TimelineEvent = replace(
        _click(),
        selector=".b",
        targets=TargetScope.ALL,
        pace_between=Pace(delay_ms=150),
        contract=ActionContract(pace=Pace(delay_ms=150)),
    )
    follower: TimelineEvent = replace(_click(event_id="after", sequence=1))
    _, records = _run(page=page, tmp_path=tmp_path, events=[event, follower])
    gaps: list[int] = [
        cast(typ="int", val=records[index + 1]["started_ms"])
        - cast(typ="int", val=records[index]["finished_ms"])
        for index in range(3)
    ]
    expect_true(condition=all(gap >= Constants.minimum_gap_ms for gap in gaps))


def test_record_payload_matches_the_json_contract(
    page: Page,
    tmp_path: Path,
) -> None:
    """Keep ``cause`` and ``unit`` present, even when empty.

    Args:
        page: Page with the buttons.
        tmp_path: Evidence directory.

    """
    _, records = _run(page=page, tmp_path=tmp_path, events=[_click()])
    expect_none(value=records[0]["cause"])
    expect_none(value=records[0]["unit"])
    parsed: JsonValue = WorkspaceCodec.action_record_to_json_value(
        record=WorkspaceCodec.action_record_from_json_value(value=records[0]),
    )
    expect_equal(
        actual=dig(document=parsed, path=("status",)),
        expected="succeeded",
    )
