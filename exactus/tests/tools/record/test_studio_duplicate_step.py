# Copyright (c) 2026 Project contributors
"""Verify that a step can be duplicated in place."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import expect_equal, expect_true, private_as
from exactus.tools.record.model import (
    AssertionKind,
    AssertionOperator,
    AssertionSpec,
    Flow,
    TimelineEvent,
)
from exactus.tools.record.store import FlowStore
from exactus.tools.record.studio.service import StudioService

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


@pytest.fixture
def service(tmp_path: Path) -> StudioService:
    """Create a Studio service that owns one empty project.

    Args:
        tmp_path: Disposable project folder.

    Returns:
        A running service; the fixture teardown stops it.

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


def test_a_duplicate_follows_its_source_with_fresh_ids(
    service: StudioService,
) -> None:
    """Place the copy after the original, with its own identifiers.

    Args:
        service: Studio service with an empty project.

    """
    try:
        _send(service=service, command="event.add", kind="screenshot")
        _send(
            service=service,
            command="event.add",
            kind="wait",
            wait_for="text",
            payload="Saved",
            timeout_ms="300",
        )
        flow: Flow = service.controller.workspace.flows[0]
        first: TimelineEvent = flow.events[0]
        check: AssertionSpec = AssertionSpec(
            assertion_id="keep-me",
            label="Visible",
            kind=AssertionKind.DOM_VISIBLE,
            operator=AssertionOperator.EXISTS,
            target="#go",
        )
        store: FlowStore = private_as(
            owner=service.controller,
            name="_store",
            kind=FlowStore,
        )
        store.update_event(
            event=first.with_contract(
                contract=replace(first.contract, postconditions=(check,)),
            ),
        )
        _send(
            service=service,
            command="event.duplicate",
            event_id=first.event_id,
        )
        events: tuple[TimelineEvent, ...] = service.controller.workspace.flows[
            0
        ].events
        expect_equal(actual=len(events), expected=3)
        expect_equal(actual=events[0].event_id, expected=first.event_id)
        copy: TimelineEvent = events[1]
        expect_true(condition=copy.event_id != first.event_id)
        expect_equal(actual=copy.kind, expected=first.kind)
        expect_true(
            condition=copy.contract.postconditions[0].assertion_id
            != "keep-me",
        )
        expect_equal(
            actual=[event.sequence for event in events],
            expected=[0, 1, 2],
        )
    finally:
        service.stop()
