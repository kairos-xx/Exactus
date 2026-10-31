# Copyright (c) 2026 Project contributors
"""Verify that an action can be added first and configured afterwards."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_not_in,
    expect_true,
    private_call,
)
from exactus.tools.record.store import WorkspaceCodec
from exactus.tools.record.studio.service import StudioService

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.model import TimelineEvent


@pytest.fixture
def service(tmp_path: Path) -> StudioService:
    """Create a Studio service that owns one empty project.

    Args:
        tmp_path: Disposable project folder.

    Returns:
        A running service.

    """
    application: StudioService = StudioService(root=tmp_path, headless=True)
    application.start()
    return application


def _send(*, service: StudioService, command: str, **payload: str) -> None:
    """Send one editor command at the current revision.

    Args:
        service: The running service.
        command: Editor command name.
        **payload: Command fields.

    """
    _ = service.controller.dispatch(
        command=command,
        payload=cast(typ="dict[str, JsonValue]", val=dict(payload)),
        revision=cast(typ="int", val=service.snapshot()["revision"]),
    )


def _only_event(*, service: StudioService) -> TimelineEvent:
    """Return the single action of the first flow.

    Args:
        service: The running service.

    Returns:
        That action.

    """
    events: tuple[TimelineEvent, ...] = service.controller.workspace.flows[
        0
    ].events
    expect_equal(actual=len(events), expected=1)
    return events[0]


def test_a_click_without_a_target_is_added_as_incomplete(
    service: StudioService,
) -> None:
    """Keep an unfinished action in the flow instead of refusing it.

    Args:
        service: Studio service with an empty project.

    """
    try:
        _send(service=service, command="event.add", kind="click")
        event: TimelineEvent = _only_event(service=service)
        expect_true(condition=event.incomplete)
        expect_equal(actual=event.selector, expected=None)
        expect_equal(actual=event.label, expected="Click")
    finally:
        service.stop()


def test_configuring_an_incomplete_action_completes_it(
    service: StudioService,
) -> None:
    """Fill the target in and clear the incomplete state.

    Args:
        service: Studio service with an empty project.

    """
    try:
        _send(service=service, command="event.add", kind="click")
        event: TimelineEvent = _only_event(service=service)
        _send(
            service=service,
            command="event.configure",
            event_id=event.event_id,
            kind="click",
            selector="#save",
        )
        configured: TimelineEvent = _only_event(service=service)
        expect_false(condition=configured.incomplete)
        expect_equal(actual=configured.selector, expected="#save")
        expect_equal(actual=configured.event_id, expected=event.event_id)
    finally:
        service.stop()


def test_a_navigation_label_follows_its_address_until_renamed(
    service: StudioService,
) -> None:
    """Refresh a generated label, but never overwrite a chosen one.

    Args:
        service: Studio service with an empty project.

    """
    try:
        _send(service=service, command="event.add", kind="url_change")
        event: TimelineEvent = _only_event(service=service)
        expect_true(condition=event.incomplete)
        expect_equal(actual=event.label, expected="Navigate")
        _send(
            service=service,
            command="event.configure",
            event_id=event.event_id,
            kind="url_change",
            url="https://example.test/a",
        )
        expect_equal(
            actual=_only_event(service=service).label,
            expected="Navigate to https://example.test/a",
        )
        _send(
            service=service,
            command="event.update",
            event_id=event.event_id,
            label="Open the shop",
            url="https://example.test/a",
        )
        _send(
            service=service,
            command="event.configure",
            event_id=event.event_id,
            kind="url_change",
            url="https://example.test/b",
        )
        configured: TimelineEvent = _only_event(service=service)
        expect_equal(actual=configured.label, expected="Open the shop")
        expect_equal(actual=configured.url, expected="https://example.test/b")
    finally:
        service.stop()


def test_a_value_that_is_wrong_not_blank_is_still_refused(
    service: StudioService,
) -> None:
    """Tolerate only blank settings, never an unsupported one.

    Args:
        service: Studio service with an empty project.

    """
    try:
        with pytest.raises(expected_exception=ValueError, match="HTTP method"):
            _send(
                service=service,
                command="event.add",
                kind="http_call",
                method="TELEPORT",
                url="https://example.test",
                request_config="{}",
            )
        with pytest.raises(expected_exception=ValueError, match="ws://"):
            _send(
                service=service,
                command="event.add",
                kind="websocket_call",
                url="https://example.test",
                request_config="{}",
            )
        expect_equal(
            actual=len(service.controller.workspace.flows[0].events),
            expected=0,
        )
    finally:
        service.stop()


def test_a_flow_with_an_unfinished_action_will_not_run(
    service: StudioService,
) -> None:
    """Name the unfinished action instead of running past it.

    Args:
        service: Studio service with an empty project.

    """
    try:
        _send(service=service, command="event.add", kind="click")
        with pytest.raises(
            expected_exception=ValueError,
            match="Finish setting up 'Click'",
        ):
            private_call(
                owner=service.controller,
                name="_play",
                follow_connections=False,
            )
    finally:
        service.stop()


def test_only_an_unfinished_action_stores_the_incomplete_flag(
    service: StudioService,
) -> None:
    """Keep saved projects unchanged for every complete action.

    Args:
        service: Studio service with an empty project.

    """
    try:
        _send(service=service, command="event.add", kind="screenshot")
        done: TimelineEvent = _only_event(service=service)
        expect_not_in(
            member="incomplete",
            container=cast(
                typ="dict[str, JsonValue]",
                val=WorkspaceCodec.event_to_json_value(event=done),
            ),
        )
        _send(service=service, command="event.add", kind="click")
        unfinished: TimelineEvent = service.controller.workspace.flows[
            0
        ].events[1]
        stored: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=WorkspaceCodec.event_to_json_value(event=unfinished),
        )
        expect_in(member="incomplete", container=stored)
        expect_equal(actual=stored["incomplete"], expected=True)
    finally:
        service.stop()
