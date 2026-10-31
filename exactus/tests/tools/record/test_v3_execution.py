# Copyright (c) 2026 Project contributors
"""Freeze what version-3 flows compute so v4 can prove equivalence."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, final

import pytest
from playwright.sync_api import sync_playwright

from exactus.tests.common.support import expect_equal, private_as
from exactus.tools.record.flow_runner import FlowRunner
from exactus.tools.record.selector_sandbox import RunStreams
from exactus.tools.record.store import WorkspaceCodec

if TYPE_CHECKING:
    from playwright.sync_api import Browser

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.model import Flow
    from exactus.tools.record.workspace_actions import Event


@final
class Constants:
    """Group module-level constants.

    Attributes:
        fixture: Grouped module constant.
        javascript_cases: Grouped module constant.

    """

    fixture: Final[Path] = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "v3"
        / "guards-and-chain.pwflow.json"
    )
    javascript_cases: Final[
        tuple[tuple[str, str, bool, str, int | None], ...]
    ] = (
        (
            "sandbox expression",
            "__EXACTUS_FLOW__.vars.Count + 1",
            True,
            "succeeded",
            4,
        ),
        (
            "sandbox body falls back to a function body",
            "return __EXACTUS_FLOW__.vars.Count + 1;",
            True,
            "succeeded",
            4,
        ),
        (
            "sandbox does not expand templates",
            "{{Count}} + 1",
            True,
            "failed",
            None,
        ),
        ("page expression", "1 + 1", False, "succeeded", 2),
        ("page body is a syntax error", "return 7;", False, "failed", None),
        (
            "page has no flow facade",
            "__EXACTUS_FLOW__.vars.Count",
            False,
            "failed",
            None,
        ),
        (
            "page does not expand templates",
            "{{Count}} + 1",
            False,
            "failed",
            None,
        ),
    )


def _run(
    *,
    tmp_path: Path,
    events: list[Event],
    flow_id: str,
) -> tuple[FlowRunner, dict[str, JsonValue]]:
    """Run actions in a fresh Chromium page.

    Args:
        tmp_path: Disposable artifact folder.
        events: Actions as workspace JSON.
        flow_id: Flow that owns the actions.

    Returns:
        The runner, so its variables can be read, and the run result.

    """
    runner: FlowRunner = FlowRunner(output=tmp_path)
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        result: dict[str, JsonValue] = runner.run(
            page=browser.new_page(),
            message=cast(
                typ="Event",
                val={
                    "flow_id": flow_id,
                    "events": cast(typ="JsonValue", val=events),
                    "capture_images": False,
                },
            ),
        )
        browser.close()
    return (runner, result)


def _fixture_events() -> tuple[str, list[Event]]:
    """Load the guarded chain as the runner's action documents.

    Returns:
        The flow id and its actions in order.

    """
    flow: Flow = WorkspaceCodec.load(path=Constants.fixture).flows[0]
    return (
        flow.flow_id,
        [
            cast(
                typ="Event",
                val=WorkspaceCodec.event_to_json_value(event=item),
            )
            for item in flow.events
        ],
    )


def _statuses(*, result: dict[str, JsonValue]) -> list[JsonValue]:
    """Return each action's status in order.

    Args:
        result: A run result.

    Returns:
        One status per action.

    """
    records: list[JsonValue] = cast(
        typ="list[JsonValue]",
        val=result["action_records"],
    )
    return [
        cast(typ="dict[str, JsonValue]", val=item)["status"]
        for item in records
    ]


def test_guarded_chain_results_are_frozen(tmp_path: Path) -> None:
    """Run the chain once and compare status, variables and per-action state.

    Args:
        tmp_path: Disposable artifact folder.

    """
    flow_id, events = _fixture_events()
    runner, result = _run(tmp_path=tmp_path, events=events, flow_id=flow_id)
    expect_equal(actual=result["status"], expected="succeeded")
    expect_equal(
        actual=_statuses(result=result),
        expected=["succeeded", "succeeded", "succeeded"],
    )
    expect_equal(
        actual=dict(
            private_as(owner=runner, name="_streams", kind=RunStreams).vars,
        ),
        expected={"Count": 3, "Next": 4, "Label": "n=4"},
    )


@pytest.mark.parametrize(
    argnames="case",
    argvalues=Constants.javascript_cases,
    ids=[case[0] for case in Constants.javascript_cases],
)
def test_javascript_paths_are_frozen(
    tmp_path: Path,
    case: tuple[str, str, bool, str, int | None],
) -> None:
    """Freeze each JavaScript path: expression, body, page and template.

    Args:
        tmp_path: Disposable artifact folder.
        case: Case name, source, sandbox flag, expected status and the value
            it publishes as ``Next``.

    """
    _, payload, sandbox, status, value = case
    flow_id, documents = _fixture_events()
    probe: Event = {
        **documents[1],
        "payload": payload,
        "sandbox": sandbox,
        "when_expression": None,
    }
    runner, result = _run(
        tmp_path=tmp_path,
        events=[documents[0], probe],
        flow_id=flow_id,
    )
    expect_equal(actual=_statuses(result=result)[1], expected=status)
    expect_equal(
        actual=dict(
            private_as(owner=runner, name="_streams", kind=RunStreams).vars,
        ).get("Next"),
        expected=value,
    )
