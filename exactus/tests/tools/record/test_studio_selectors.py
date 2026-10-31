# Copyright (c) 2026 Project contributors
"""Drive the selector editor commands through a real Studio service."""

from __future__ import annotations

from time import monotonic, sleep
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.tests.common.support import (
    dig,
    dig_list,
    expect_equal,
    expect_in,
    expect_none,
    expect_true,
)
from exactus.tools.record.model import EventKind, TimelineEvent, TransitionMode
from exactus.tools.record.selectors import TargetScope
from exactus.tools.record.studio.service import StudioService

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        live_timeout_s: Grouped module constant.

    """

    live_timeout_s: Final[int] = 15


@pytest.fixture
def service(tmp_path: Path) -> Iterator[StudioService]:
    """Run an isolated Studio service with an empty project.

    Args:
        tmp_path: Disposable project folder.

    Yields:
        The running service.

    """
    application: StudioService = StudioService(root=tmp_path, headless=True)
    application.start()
    try:
        yield application
    finally:
        application.stop()


def _send(
    *,
    service: StudioService,
    command: str,
    payload: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    """Send one editor command at the current revision.

    Args:
        service: The running service.
        command: Editor command name.
        payload: Command fields.

    Returns:
        The snapshot the command returns.

    """
    reply: JsonValue = service.controller.dispatch(
        command=command,
        payload=payload,
        revision=cast(typ="int", val=service.snapshot()["revision"]),
    )
    return cast(typ="dict[str, JsonValue]", val=reply)


def _event(*, service: StudioService) -> TimelineEvent:
    """Return the first action of the first flow.

    Args:
        service: The running service.

    Returns:
        The action.

    """
    return service.controller.workspace.flows[0].events[0]


def _save_card(*, service: StudioService) -> str:
    """Save a selector named ``card`` and return its identifier.

    Args:
        service: The running service.

    Returns:
        The new selector's identifier.

    """
    snapshot: dict[str, JsonValue] = _send(
        service=service,
        command="selector.save",
        payload={
            "name": "card",
            "expression": ".card",
            "expected_count": "any",
            "checks": ['[aria-disabled!="true"]', " "],
        },
    )
    return str(
        object=dig(document=snapshot, path=("selectors", 0, "selector_id")),
    )


def test_saving_creates_then_edits_a_selector(service: StudioService) -> None:
    """Create a selector, then change it and rename it in place.

    Args:
        service: The running service.

    """
    selector_id: str = _save_card(service=service)
    created: dict[str, JsonValue] = service.snapshot()
    expect_equal(
        actual=dig(document=created, path=("selectors", 0, "name")),
        expected="card",
    )
    expect_none(
        value=dig(document=created, path=("selectors", 0, "expected_count")),
    )
    expect_equal(
        actual=dig_list(document=created, path=("selectors", 0, "checks")),
        expected=['[aria-disabled!="true"]'],
    )
    edited: dict[str, JsonValue] = _send(
        service=service,
        command="selector.save",
        payload={
            "selector_id": selector_id,
            "name": "panel",
            "expression": "sort(.card, [data-p])",
            "expected_count": 2,
            "checks": [],
        },
    )
    expect_equal(
        actual=len(dig_list(document=edited, path=("selectors",))),
        expected=1,
    )
    expect_equal(
        actual=dig(document=edited, path=("selectors", 0, "name")),
        expected="panel",
    )
    expect_equal(
        actual=dig(document=edited, path=("selectors", 0, "expected_count")),
        expected=2,
    )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"name": "1bad", "expression": ".x"}, "start with a letter"),
        ({"name": "ok", "expression": "  "}, "expression"),
        ({"name": "card", "expression": ".other"}, "unique names"),
    ],
)
def test_names_and_expressions_are_validated(
    service: StudioService,
    payload: dict[str, JsonValue],
    message: str,
) -> None:
    """Reject a bad name, a blank expression and a duplicate name.

    Args:
        service: The running service.
        payload: Fields that cannot be saved.
        message: Text the error must contain.

    """
    _ = _save_card(service=service)
    with pytest.raises(expected_exception=ValueError, match=message):
        _ = _send(service=service, command="selector.save", payload=payload)


def test_an_action_can_use_a_selector_and_its_targeting(
    service: StudioService,
) -> None:
    """Point a step at a stored selector with scope, pacing and tolerance.

    Args:
        service: The running service.

    """
    selector_id: str = _save_card(service=service)
    _ = _send(
        service=service,
        command="event.add",
        payload={"kind": "click", "selector": "#go"},
    )
    event: TimelineEvent = _event(service=service)
    _ = _send(
        service=service,
        command="event.update",
        payload={
            "event_id": event.event_id,
            "label": "Click every card",
            "selector": "",
            "payload": "",
            "selector_id": selector_id,
            "targets": "all",
            "run_mode": "sequential",
            "pace_between": {"delay_ms": 50, "until": "sel_card_exists"},
            "continue_on_failure": True,
        },
    )
    updated: TimelineEvent = _event(service=service)
    expect_equal(actual=updated.selector_id, expected=selector_id)
    expect_none(value=updated.selector)
    expect_equal(actual=updated.targets, expected=TargetScope.ALL)
    expect_true(condition=updated.contract.continue_on_failure)
    snapshot: dict[str, JsonValue] = service.snapshot()
    usage: object = dig(
        document=snapshot,
        path=("selector_usage", selector_id),
    )
    expect_equal(actual=dig(document=usage, path=("flows",)), expected=1)
    with pytest.raises(
        expected_exception=ValueError,
        match="needs a selector named",
    ):
        _ = _send(
            service=service,
            command="event.update",
            payload={
                "event_id": event.event_id,
                "label": "x",
                "selector_id": selector_id,
                "pace": {"until": "sel_ghost_count > 0"},
            },
        )
    with pytest.raises(expected_exception=ValueError, match="parallel"):
        _ = _send(
            service=service,
            command="event.update",
            payload={
                "event_id": event.event_id,
                "label": "x",
                "selector_id": selector_id,
                "targets": "all",
                "run_mode": "parallel",
            },
        )


def test_a_selector_in_use_cannot_be_deleted_without_force(
    service: StudioService,
) -> None:
    """Guard deletion, then allow it when forced.

    Args:
        service: The running service.

    """
    selector_id: str = _save_card(service=service)
    _ = _send(
        service=service,
        command="event.add",
        payload={"kind": "snapshot", "selector_id": selector_id},
    )
    expect_equal(
        actual=_event(service=service).kind,
        expected=EventKind.SNAPSHOT,
    )
    with pytest.raises(expected_exception=ValueError, match="1 action"):
        _ = _send(
            service=service,
            command="selector.delete",
            payload={"selector_id": selector_id},
        )
    gone: dict[str, JsonValue] = _send(
        service=service,
        command="selector.delete",
        payload={"selector_id": selector_id, "force": True},
    )
    expect_equal(
        actual=dig_list(document=gone, path=("selectors",)),
        expected=[],
    )
    expect_equal(
        actual=dig(
            document=gone,
            path=("selector_problems", 0, "selector_id"),
        ),
        expected=selector_id,
    )


def test_connection_conditions_are_checked_when_saved(
    service: StudioService,
) -> None:
    """Refuse a connection whose probe names no selector.

    Args:
        service: The running service.

    """
    _ = _save_card(service=service)
    _ = _send(service=service, command="flow.create", payload={})
    first, second = (
        flow.flow_id for flow in service.controller.workspace.flows
    )
    good: dict[str, JsonValue] = {
        "source": first,
        "target": second,
        "mode": TransitionMode.CONDITION.value,
        "condition_expression": "flow_succeeded and sel_card_exists",
    }
    _ = _send(service=service, command="edge.add", payload=good)
    expect_equal(actual=len(service.controller.workspace.edges), expected=1)
    with pytest.raises(
        expected_exception=ValueError,
        match="needs a selector named",
    ):
        _ = _send(
            service=service,
            command="edge.add",
            payload={
                **good,
                "target": first,
                "source": second,
                "condition_expression": "sel_ghost_exists",
            },
        )


def test_testing_a_selector_in_the_live_page(
    service: StudioService,
    demo_url: str,
) -> None:
    """Resolve an expression in the real target page and remember the page.

    Args:
        service: The running service.
        demo_url: Base address of the served demo site.

    """
    with pytest.raises(expected_exception=ValueError, match="Open the target"):
        _ = _send(
            service=service,
            command="selector.test",
            payload={"expression": "a", "expected_count": "any"},
        )
    selector_id: str = _save_card(service=service)
    _ = _send(
        service=service,
        command="selector.save",
        payload={
            "selector_id": selector_id,
            "name": "card",
            "expression": "a",
            "expected_count": "any",
            "checks": [],
        },
    )
    _ = _send(
        service=service,
        command="browser.open",
        payload={"url": demo_url},
    )
    deadline: float = monotonic() + Constants.live_timeout_s
    while service.snapshot().get("target_state") != "ready":
        expect_true(condition=monotonic() < deadline)
        sleep(0.05)
    _ = _send(
        service=service,
        command="selector.test",
        payload={
            "selector_id": selector_id,
            "expression": "a",
            "expected_count": "any",
            "checks": [],
        },
    )
    while service.snapshot().get("selector_test") is None:
        expect_true(condition=monotonic() < deadline)
        sleep(0.05)
    result: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=service.snapshot()["selector_test"],
    )
    expect_true(condition=result["ok"] is True)
    expect_true(condition=cast(typ="int", val=result["count"]) > 0)
    first: object = dig(document=result, path=("matches", 0))
    expect_in(
        member="rect",
        container=cast(typ="dict[str, JsonValue]", val=first),
    )
    expect_true(condition=bool(dig(document=first, path=("css",))))
    validated: object = dig(
        document=service.snapshot(),
        path=("selectors", 0, "validated_on"),
    )
    expect_equal(
        actual=dig(document=validated, path=(0, "url")).__class__,
        expected=str,
    )
