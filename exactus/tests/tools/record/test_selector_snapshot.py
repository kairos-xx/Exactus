# Copyright (c) 2026 Project contributors
"""Record matched elements as snapshots and warn when they drift."""

from __future__ import annotations

from dataclasses import replace
from json import dumps
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
from exactus.tools.record.model import EventKind, TimelineEvent, TimelineLayer
from exactus.tools.record.selector_snapshot import (
    compare_evidence,
    parse_baseline,
)
from exactus.tools.record.selectors import (
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
        html: Grouped module constant.
        save: Grouped module constant.

    """

    html: Final[str] = dedent(
        text=(
            '    \n    <button id="save" class="primary" data-testid="save"\n '
            '           style="position:absolute;left:20px;top:30px;width:120p'
            'x;height:40px">\n      Save order\n    </button>\n    <button cla'
            'ss="extra" style="position:absolute;left:20px;top:100px">B</butto'
            "n>\n    "
        ),
    )
    save: Final[SelectorDef] = SelectorDef(
        selector_id="sel-save",
        name="save",
        expression='[data-testid="save"]',
    )


@pytest.fixture
def page() -> Iterator[Page]:
    """Create a disposable page with a positioned Save button.

    Yields:
        A Chromium page.

    """
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        opened: Page = browser.new_page()
        opened.set_content(html=Constants.html)
        yield opened
        browser.close()


def _snapshot(*, payload: str | None = None) -> TimelineEvent:
    """Build a snapshot of the stored Save selector.

    Args:
        payload: Baseline evidence as JSON, if one was set.

    Returns:
        The snapshot action.

    """
    return TimelineEvent(
        event_id="snap",
        flow_id="flow-a",
        sequence=0,
        elapsed_ms=0,
        layer=TimelineLayer.INTERACTION,
        kind=EventKind.SNAPSHOT,
        label="Snapshot Save",
        selector_id="sel-save",
        payload=payload,
    )


def _run(*, page: Page, tmp_path: Path, event: TimelineEvent) -> Event:
    """Run one snapshot action.

    Args:
        page: Page with the button.
        tmp_path: Evidence directory.
        event: The action.

    Returns:
        The flow result.

    """
    return FlowRunner(output=tmp_path, timeout_ms=500).run(
        page=page,
        message={
            "flow_id": "flow-a",
            "events": [WorkspaceCodec.event_to_json_value(event=event)],
            "selectors": [SelectorCodec.selector_to_json(item=Constants.save)],
        },
    )


def _records(*, result: Event) -> list[Event]:
    """Return a result's action records.

    Args:
        result: Flow result.

    Returns:
        Its records.

    """
    return cast(typ="list[Event]", val=result["action_records"])


def test_a_snapshot_records_the_element(page: Page, tmp_path: Path) -> None:
    """Store tag, role, text, box and key attributes.

    Args:
        page: Page with the button.
        tmp_path: Evidence directory.

    """
    result: Event = _run(page=page, tmp_path=tmp_path, event=_snapshot())
    record: Event = _records(result=result)[0]
    expect_equal(actual=record["status"], expected="succeeded")
    evidence: object = dig(document=record, path=("response", "evidence"))
    expect_equal(
        actual=dig(document=evidence, path=("tag",)),
        expected="button",
    )
    expect_equal(
        actual=dig(document=evidence, path=("role",)),
        expected="button",
    )
    expect_equal(
        actual=dig(document=evidence, path=("text",)),
        expected="Save order",
    )
    expect_equal(
        actual=dig(document=evidence, path=("rect", "width")),
        expected=120,
    )
    expect_equal(
        actual=dig(document=evidence, path=("attributes", "data-testid")),
        expected="save",
    )
    expect_equal(
        actual=dig(document=record, path=("response", "baseline")),
        expected=False,
    )
    expect_none(value=dig(document=record, path=("response", "drift")))


def test_a_matching_baseline_is_quiet(page: Page, tmp_path: Path) -> None:
    """Report no drift when the element still matches its baseline.

    Args:
        page: Page with the button.
        tmp_path: Evidence directory.

    """
    first: Event = _run(page=page, tmp_path=tmp_path, event=_snapshot())
    baseline: object = dig(
        document=_records(result=first)[0],
        path=("response", "evidence"),
    )
    result: Event = _run(
        page=page,
        tmp_path=tmp_path,
        event=_snapshot(payload=dumps(obj=baseline)),
    )
    record: Event = _records(result=result)[0]
    expect_equal(actual=record["status"], expected="succeeded")
    expect_equal(
        actual=dig(document=record, path=("response", "drift")),
        expected=[],
    )


def test_drift_warns_without_failing_the_flow(
    page: Page,
    tmp_path: Path,
) -> None:
    """Show a warning with the changed fields, and carry on.

    Args:
        page: Page with the button.
        tmp_path: Evidence directory.

    """
    first: Event = _run(page=page, tmp_path=tmp_path, event=_snapshot())
    baseline: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=dig(
            document=_records(result=first)[0],
            path=("response", "evidence"),
        ),
    )
    page.evaluate(
        expression=(
            "document.getElementById('save').textContent = 'Place order'"
        ),
    )
    result: Event = _run(
        page=page,
        tmp_path=tmp_path,
        event=_snapshot(payload=dumps(obj=baseline)),
    )
    record: Event = _records(result=result)[0]
    expect_equal(actual=record["status"], expected="warning")
    expect_equal(actual=result["status"], expected="succeeded")
    expect_equal(
        actual=dig(document=record, path=("cause", "phase")),
        expected="drift",
    )
    changes: object = dig(document=record, path=("cause", "changes"))
    expect_equal(
        actual=dig(document=changes, path=(0, "field")),
        expected="text",
    )
    expect_equal(
        actual=dig(document=record, path=("streams", 0, "level")),
        expected="warn",
    )


def test_snapshots_of_all_targets_make_one_record_each(
    page: Page,
    tmp_path: Path,
) -> None:
    """Snapshot every match separately.

    Args:
        page: Page with the buttons.
        tmp_path: Evidence directory.

    """
    all_buttons: SelectorDef = replace(
        Constants.save,
        expression="button",
        expected_count=2,
    )
    event: TimelineEvent = replace(_snapshot(), targets=TargetScope.ALL)
    result: Event = FlowRunner(output=tmp_path, timeout_ms=500).run(
        page=page,
        message={
            "flow_id": "flow-a",
            "events": [WorkspaceCodec.event_to_json_value(event=event)],
            "selectors": [SelectorCodec.selector_to_json(item=all_buttons)],
        },
    )
    records: list[Event] = _records(result=result)
    expect_equal(actual=len(records), expected=2)
    expect_equal(
        actual=[
            dig(document=r, path=("response", "evidence", "text"))
            for r in records
        ],
        expected=["Save order", "B"],
    )


def test_snapshots_need_an_extended_selector_expression(
    page: Page,
    tmp_path: Path,
) -> None:
    """Explain why a Playwright-only selector cannot be snapshotted.

    Args:
        page: Page with the button.
        tmp_path: Evidence directory.

    """
    event: TimelineEvent = replace(
        _snapshot(),
        selector_id=None,
        selector="role=button[name='Save order']",
    )
    result: Event = _run(page=page, tmp_path=tmp_path, event=event)
    record: Event = _records(result=result)[0]
    expect_equal(actual=record["status"], expected="failed")
    expect_equal(
        actual=dig(document=record, path=("cause", "phase")),
        expected="resolve",
    )
    expect_true(condition=bool(record["error"]))


def test_evidence_comparison_tolerates_small_box_changes() -> None:
    """Ignore a few pixels of movement but report a real change."""
    base: dict[str, JsonValue] = {
        "tag": "button",
        "role": "button",
        "text": "Save",
        "attributes": {"id": "save"},
        "rect": {"x": 10, "y": 10, "width": 100, "height": 40},
    }
    near: dict[str, JsonValue] = {
        **base,
        "rect": {"x": 14, "y": 12, "width": 100, "height": 40},
    }
    far: dict[str, JsonValue] = {
        **base,
        "rect": {"x": 200, "y": 10, "width": 100, "height": 40},
    }
    expect_equal(
        actual=compare_evidence(baseline=base, current=near),
        expected=[],
    )
    changes: list[dict[str, JsonValue]] = compare_evidence(
        baseline=base,
        current=far,
    )
    expect_equal(
        actual=[change["field"] for change in changes],
        expected=["rect"],
    )
    renamed: list[dict[str, JsonValue]] = compare_evidence(
        baseline=base,
        current={**base, "attributes": {"id": "other"}, "text": "Buy"},
    )
    expect_equal(
        actual=[change["field"] for change in renamed],
        expected=["text", "attributes"],
    )


def test_a_stored_baseline_is_read_leniently() -> None:
    """Treat missing or broken baselines as none."""
    expect_none(value=parse_baseline(payload=None))
    expect_none(value=parse_baseline(payload="{"))
    expect_none(value=parse_baseline(payload="[1]"))
    expect_in(
        member="tag",
        container=cast(
            typ="dict[str, JsonValue]",
            val=parse_baseline(payload='{"tag": "a"}'),
        ),
    )
