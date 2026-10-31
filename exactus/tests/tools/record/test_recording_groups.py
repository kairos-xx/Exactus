# Copyright (c) 2026 Project contributors
"""Persist recording parents and preserve capture ownership and cadence."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.record import flow_runner
from exactus.tools.record.flow_runner import FlowRunner
from exactus.tools.record.model import (
    EventKind,
    Flow,
    FlowRecording,
    TimelineEvent,
    TimelineLayer,
    Workspace,
)
from exactus.tools.record.store import FlowStore, WorkspaceCodec
from exactus.tools.record.studio import worker as worker_module
from exactus.tools.record.studio.demo import demo_workspace
from exactus.tools.record.studio.worker import ManagedBrowserWorker

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from playwright.sync_api import Page

    from exactus.tools.record.workspace_actions import Event


def _boundary(owner: object, *, name: str) -> Callable[..., None]:
    """Bind a private boundary the test deliberately exercises.

    Args:
        owner: Object owning the private method.
        name: Private method name.

    Returns:
        The bound callable.

    """
    return cast(typ="Callable[..., None]", val=getattr(owner, name))


def test_recording_parent_round_trip() -> None:
    """An empty parent and its captured children survive saving."""
    store: FlowStore = FlowStore(
        workspace=demo_workspace(url="http://localhost/"),
    )
    flow_id: str = store.workspace.flows[0].flow_id
    group: FlowRecording = FlowRecording(
        recording_id="take-1",
        label="Recording 1",
        start_ms=400,
    )
    store.add_recording(flow_id=flow_id, recording=group)
    empty: Workspace = WorkspaceCodec.from_json_value(
        value=WorkspaceCodec.to_json_value(workspace=store.workspace),
    )
    expect_equal(actual=empty.flows[0].recordings, expected=(group,))
    event: TimelineEvent = TimelineEvent(
        event_id="captured",
        flow_id=flow_id,
        sequence=-1,
        elapsed_ms=800,
        layer=TimelineLayer.INTERACTION,
        kind=EventKind.CLICK,
        label="Click Save",
        selector="#save",
        recording_group_id=group.recording_id,
    )
    store.append_event(event=event)
    loaded: Workspace = WorkspaceCodec.from_json_value(
        value=WorkspaceCodec.to_json_value(workspace=store.workspace),
    )
    expect_equal(actual=loaded.flows[0].recordings, expected=(group,))
    expect_equal(
        actual=loaded.flows[0].events[-1].recording_group_id,
        expected="take-1",
    )
    expect_equal(actual=loaded.flows[0].events[-1].elapsed_ms, expected=800)
    with pytest.raises(expected_exception=ValueError, match="unique"):
        store.add_recording(flow_id=flow_id, recording=group)
    with pytest.raises(expected_exception=ValueError, match="parent"):
        store.append_event(
            event=replace(
                event,
                event_id="orphan",
                recording_group_id="missing",
            ),
        )
    with pytest.raises(expected_exception=ValueError, match="before"):
        store.retime_event(
            flow_id=flow_id,
            event_id="captured",
            elapsed_ms=399,
        )


def _two_takes() -> tuple[FlowStore, str]:
    """Build a flow with two recording parents and interleaved actions.

    Returns:
        The store and the owning flow identifier.

    """
    store: FlowStore = FlowStore(
        workspace=demo_workspace(url="http://localhost/"),
    )
    flow_id: str = store.workspace.flows[0].flow_id
    base: int = max(
        (event.elapsed_ms for event in store.workspace.flows[0].events),
        default=0,
    )
    for take, start in (("take-1", base + 1000), ("take-2", base + 9000)):
        store.add_recording(
            flow_id=flow_id,
            recording=FlowRecording(
                recording_id=take,
                label=take,
                start_ms=start,
            ),
        )
        for index in range(2):
            _ = store.append_event(
                event=TimelineEvent(
                    event_id=f"{take}-{index}",
                    flow_id=flow_id,
                    sequence=-1,
                    elapsed_ms=start + index * 250,
                    layer=TimelineLayer.INTERACTION,
                    kind=EventKind.CLICK,
                    label=f"Click {index}",
                    selector=f"#{take}-{index}",
                    recording_group_id=take,
                ),
            )
    return store, flow_id


def test_recording_parent_rename_shift_and_delete() -> None:
    """Group operations are atomic and keep children tied to their parent."""
    store, flow_id = _two_takes()
    before: Flow = store.workspace.flows[0]
    other: tuple[TimelineEvent, ...] = tuple(
        event
        for event in before.events
        if event.recording_group_id != "take-1"
    )
    start: int = next(
        item.start_ms
        for item in before.recordings
        if item.recording_id == "take-1"
    )
    store.rename_recording(
        flow_id=flow_id,
        recording_id="take-1",
        label="Login",
    )
    expect_equal(
        actual=next(
            item.label
            for item in store.workspace.flows[0].recordings
            if item.recording_id == "take-1"
        ),
        expected="Login",
    )
    store.shift_recording(
        flow_id=flow_id,
        recording_id="take-1",
        delta_ms=500,
        limit_ms=3_600_000,
    )
    after: Flow = store.workspace.flows[0]
    moved: tuple[TimelineEvent, ...] = tuple(
        e for e in after.events if e.recording_group_id == "take-1"
    )
    expect_equal(
        actual=[e.elapsed_ms for e in moved],
        expected=[start + 500, start + 750],
    )
    expect_equal(
        actual=[e.event_id for e in moved],
        expected=["take-1-0", "take-1-1"],
    )
    expect_equal(
        actual=[e.sequence for e in after.events],
        expected=list(range(len(after.events))),
    )
    expect_equal(
        actual=next(
            item.start_ms
            for item in after.recordings
            if item.recording_id == "take-1"
        ),
        expected=start + 500,
    )
    with pytest.raises(expected_exception=ValueError, match="timeline"):
        store.shift_recording(
            flow_id=flow_id,
            recording_id="take-1",
            delta_ms=-10_000_000,
            limit_ms=3_600_000,
        )
    with pytest.raises(expected_exception=ValueError, match="timeline"):
        store.shift_recording(
            flow_id=flow_id,
            recording_id="take-2",
            delta_ms=3_600_000,
            limit_ms=3_600_000,
        )
    with pytest.raises(expected_exception=ValueError, match="Unknown"):
        store.rename_recording(flow_id=flow_id, recording_id="nope", label="x")
    store.delete_recording(flow_id=flow_id, recording_id="take-1")
    final: Flow = store.workspace.flows[0]
    expect_equal(
        actual=[item.recording_id for item in final.recordings],
        expected=["take-2"],
    )
    expect_true(
        condition=all(e.recording_group_id != "take-1" for e in final.events),
    )
    expect_equal(
        actual=[e.sequence for e in final.events],
        expected=list(range(len(final.events))),
    )
    expect_equal(actual=len(final.events), expected=len(other))


def test_capture_clock_pause_resume_and_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recording starts at zero, ignores pauses and stays pinned to its flow.

    Args:
        tmp_path: Disposable recording output.
        monkeypatch: Restore the deterministic monotonic clock.

    """
    clock: list[float] = [500.0]
    monkeypatch.setattr(
        target=worker_module,
        name="monotonic",
        value=lambda: clock[0],
    )
    worker: ManagedBrowserWorker = ManagedBrowserWorker(output=tmp_path)
    messages: list[Event] = []
    worker.emit = messages.append
    page: Page = cast(
        typ="Page",
        val=SimpleNamespace(
            url="http://localhost/",
            evaluate=lambda **_: None,
        ),
    )
    command: Event = {
        "name": "record",
        "flow_id": "one",
        "recording_group_id": "take",
        "recording_start_ms": 700,
    }
    command_boundary: Callable[..., None] = _boundary(
        owner=worker,
        name="_command",
    )
    forward_boundary: Callable[..., None] = _boundary(
        owner=worker,
        name="_forward",
    )
    command_boundary(page=page, message=command)
    expect_equal(actual=messages[0]["elapsed_ms"], expected=700)
    clock[0] = 500.25
    command_boundary(
        page=page,
        message={"name": "active_flow", "flow_id": "two"},
    )
    forward_boundary(
        action={
            "type": "click",
            "target": {"locators": [{"kind": "css", "value": "#save"}]},
        },
    )
    expect_equal(actual=messages[-1]["flow_id"], expected="one")
    expect_equal(actual=messages[-1]["elapsed_ms"], expected=950)
    expect_equal(actual=messages[-1]["selector"], expected="#save")
    command_boundary(page=page, message={"name": "pause"})
    clock[0] = 600.0
    command_boundary(page=page, message=command)
    expect_equal(actual=len(messages), expected=2)
    clock[0] = 600.5
    forward_boundary(
        action={
            "type": "click",
            "target": {"locators": [{"kind": "css", "value": "#next"}]},
        },
    )
    expect_equal(actual=messages[-1]["elapsed_ms"], expected=1450)
    expect_equal(actual=messages[-1]["recording_group_id"], expected="take")
    command_boundary(page=page, message={"name": "pause"})
    command_boundary(
        page=page,
        message={
            "name": "record",
            "flow_id": "two",
            "recording_group_id": "new",
        },
    )
    expect_equal(actual=messages[-1]["elapsed_ms"], expected=0)
    expect_equal(actual=messages[-1]["flow_id"], expected="two")


def test_recorded_playback_waits_and_can_cancel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wait between captured children, but never delay ordinary authored steps.

    Args:
        tmp_path: Disposable replay evidence directory.
        monkeypatch: Restore the deterministic playback clock.

    """
    clock: list[float] = [100.0]
    waits: list[float] = []

    def wait(*, timeout: float) -> None:
        """Advance the fake browser clock.

        Args:
            timeout: Cancellable wait duration in milliseconds.

        """
        waits.append(timeout)
        clock[0] += timeout / 1000

    monkeypatch.setattr(
        target=flow_runner,
        name="monotonic",
        value=lambda: clock[0],
    )
    page: Page = cast(typ="Page", val=SimpleNamespace(wait_for_timeout=wait))
    runner: FlowRunner = FlowRunner(output=tmp_path, emit=lambda _: None)
    event: TimelineEvent = TimelineEvent(
        event_id="first",
        flow_id="one",
        sequence=0,
        elapsed_ms=300,
        layer=TimelineLayer.INTERACTION,
        kind=EventKind.CLICK,
        label="Click",
        selector="#go",
        recording_group_id="take",
    )
    origins: dict[str, tuple[float, int]] = {}
    pace_recording: Callable[..., None] = _boundary(
        owner=runner,
        name="_pace_recording",
    )
    pace_recording(page=page, event=event, origins=origins)
    pace_recording(
        page=page,
        event=replace(event, elapsed_ms=550),
        origins=origins,
    )
    tolerance_ms: float = 2
    expect_true(condition=abs(sum(waits) - 250) < tolerance_ms)
    count: int = len(waits)
    pace_recording(
        page=page,
        event=replace(event, recording_group_id=None, elapsed_ms=10000),
        origins=origins,
    )
    runner.cancelled = lambda: True
    pace_recording(
        page=page,
        event=replace(event, elapsed_ms=10000),
        origins=origins,
    )
    expect_equal(actual=len(waits), expected=count)
