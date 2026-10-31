# Copyright (c) 2026 Project contributors
"""Build small projects that use selectors, for the selector tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, final

from exactus.tools.record.model import (
    EventKind,
    FlowEdge,
    TimelineEvent,
    TransitionMode,
    Workspace,
)
from exactus.tools.record.selectors import Pace, SelectorDef, TargetScope
from exactus.tools.record.store import WorkspaceCodec
from exactus.tools.record.workspace_actions import (
    actions_to_events,
    build_flow,
    build_workspace,
)

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


def flow_json(*, flow_id: str) -> dict[str, JsonValue]:
    """Return a one-click flow in the current schema.

    Args:
        flow_id: Flow identifier.

    Returns:
        The flow's JSON object.

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
        flow_id=flow_id,
    )
    return build_flow(flow_id=flow_id, name=flow_id.upper(), events=events)


def project() -> Workspace:
    """Build two flows that use the ``card`` selector in several ways.

    Returns:
        A project with selectors ``card`` and ``title`` and one connection.

    """
    base: Workspace = WorkspaceCodec.from_json_value(
        value=build_workspace(
            flows=[flow_json(flow_id="f1"), flow_json(flow_id="f2")],
        ),
    )
    first, second = base.flows
    clicker: TimelineEvent = replace(
        first.events[0],
        selector=None,
        selector_id="sel-card",
    )
    script: TimelineEvent = replace(
        first.events[0],
        event_id="f1-js",
        sequence=1,
        kind=EventKind.JAVASCRIPT,
        selector=None,
        selector_id=None,
        payload="document.querySelector('[extended-selector=\"card\"]')",
        sandbox=True,
    )
    paced: TimelineEvent = replace(
        second.events[0],
        selector=None,
        selector_id="sel-card",
        targets=TargetScope.ALL,
        pace_between=Pace(until="sel_card_count >= 3"),
    )
    return replace(
        base,
        flows=(
            replace(first, events=(clicker, script)),
            replace(second, events=(paced,)),
        ),
        edges=(
            FlowEdge(
                source_flow_id="f1",
                target_flow_id="f2",
                mode=TransitionMode.CONDITION,
                condition_expression="flow_succeeded and sel_card_exists",
            ),
        ),
        selectors=(
            SelectorDef(
                selector_id="sel-card",
                name="card",
                expression=".card",
            ),
            SelectorDef(
                selector_id="sel-title",
                name="title",
                expression='children([extended-selector="card"], .title)',
            ),
        ),
    )


@final
class Constants:
    """Group module-level constants.

    Attributes:
        page_url: Grouped module constant.

    """

    page_url: Final[str] = (
        Path(__file__).parent / "web_selector" / "index.html"
    ).as_uri()
