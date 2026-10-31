# Copyright (c) 2026 Project contributors
"""Pause, resume and step a run between actions, in a real Chromium page."""

from __future__ import annotations

from json import dumps
from threading import Condition, Thread
from typing import TYPE_CHECKING, Final, cast, final

from playwright.sync_api import sync_playwright

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
    private_as,
)
from exactus.tools.record.flow_runner import FlowRunner
from exactus.tools.record.model import EventKind, TimelineEvent, TimelineLayer
from exactus.tools.record.run_gate import RunGate
from exactus.tools.record.selector_sandbox import RunStreams
from exactus.tools.record.store import WorkspaceCodec

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from playwright.sync_api import Browser, Page

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.workspace_actions import Event


@final
class Constants:
    """Group module-level constants.

    Attributes:
        wait_seconds: Grouped module constant.

    """

    wait_seconds: Final[float] = 20.0


class _Messages:
    """Collect what the runner emits and let a test wait for it."""

    def __init__(self) -> None:
        """Start empty."""
        self._condition: Condition = Condition()
        self._items: list[Event] = []

    def add(self, message: Event) -> None:
        """Record one emitted message and wake any waiter.

        Args:
            message: What the runner emitted.

        """
        with self._condition:
            self._items.append(message)
            self._condition.notify_all()

    def wait_for(self, *, check: Callable[[list[Event]], bool]) -> bool:
        """Block until the collected messages satisfy a condition.

        Args:
            check: Condition over every message so far.

        Returns:
            Whether the condition held before the timeout.

        """
        with self._condition:
            return self._condition.wait_for(
                predicate=lambda: check(self._items),
                timeout=Constants.wait_seconds,
            )

    def gates(self) -> list[tuple[str, str]]:
        """Return each ``run_gate`` message as ``(state, event_id)``.

        Returns:
            The gate reports in the order they arrived.

        """
        with self._condition:
            return [
                (str(object=item["state"]), str(object=item["event_id"]))
                for item in self._items
                if item.get("type") == "run_gate"
            ]


def _set_variable(*, index: int) -> Event:
    """Serialize an action that sets one numeric variable.

    Args:
        index: Position in the flow; also names the variable and its value.

    Returns:
        The event as workspace JSON.

    """
    event: TimelineEvent = TimelineEvent(
        event_id=f"e{index}",
        flow_id="flow",
        sequence=index,
        elapsed_ms=index * 10,
        layer=TimelineLayer.INTERACTION,
        kind=EventKind.SET_VARIABLE,
        label=f"Set {index}",
        output_variable=f"v{index}",
        payload=dumps(
            obj={"value": str(object=index), "value_type": "integer"},
        ),
    )
    return cast(
        typ="Event",
        val=WorkspaceCodec.event_to_json_value(event=event),
    )


def _start(*, runner: FlowRunner, outcome: list[Event]) -> Thread:
    """Run three actions on a thread that owns its own browser.

    Args:
        runner: Runner to execute; its gate decides when actions proceed.
        outcome: Receives the run result.

    Returns:
        The started thread.

    """
    events: list[Event] = [_set_variable(index=index) for index in range(3)]

    def execute() -> None:
        """Own the Playwright objects and run the flow."""
        with sync_playwright() as playwright:
            browser: Browser = playwright.chromium.launch()
            page: Page = browser.new_page()
            outcome.append(
                runner.run(
                    page=page,
                    message=cast(
                        typ="Event",
                        val={
                            "flow_id": "flow",
                            "events": cast(typ="JsonValue", val=events),
                            "capture_images": False,
                        },
                    ),
                ),
            )
            browser.close()

    thread: Thread = Thread(target=execute, daemon=True)
    thread.start()
    return thread


def _variables(*, runner: FlowRunner) -> dict[str, JsonValue]:
    """Return the variables a runner holds now.

    Args:
        runner: Runner being observed.

    Returns:
        A copy of its run variables.

    """
    return dict(
        private_as(owner=runner, name="_streams", kind=RunStreams).vars,
    )


def _held_before(*, messages: _Messages, event_id: str) -> bool:
    """Wait until the run reports being held before an action.

    Args:
        messages: What the runner emitted so far.
        event_id: The action the run should be held before.

    Returns:
        Whether it was held before that action in time.

    """
    return messages.wait_for(
        check=lambda items: (
            ("paused", event_id)
            in [
                (str(object=item["state"]), str(object=item["event_id"]))
                for item in items
                if item.get("type") == "run_gate"
            ]
        ),
    )


def test_a_free_gate_never_blocks_the_runner() -> None:
    """Return at once, without announcing, while nothing is paused."""
    gate: RunGate = RunGate()
    calls: list[str] = []
    gate.wait_turn(
        cancelled=lambda: False,
        on_hold=lambda: calls.append("hold"),
        on_release=lambda: calls.append("release"),
    )
    expect_equal(actual=calls, expected=[])
    expect_false(condition=gate.paused)


def test_cancellation_releases_a_held_runner() -> None:
    """Let a stopped run leave the gate instead of waiting forever."""
    gate: RunGate = RunGate()
    gate.pause()
    cancelled: list[bool] = [False]
    calls: list[str] = []
    thread: Thread = Thread(
        target=gate.wait_turn,
        kwargs={
            "cancelled": lambda: cancelled[0],
            "on_hold": lambda: calls.append("hold"),
            "on_release": lambda: calls.append("release"),
        },
        daemon=True,
    )
    thread.start()
    thread.join(timeout=0.3)
    expect_true(condition=thread.is_alive())
    cancelled[0] = True
    thread.join(timeout=Constants.wait_seconds)
    expect_false(condition=thread.is_alive())
    expect_equal(actual=calls, expected=["hold", "release"])


def test_pause_step_and_resume_hold_a_real_run(tmp_path: Path) -> None:
    """Start paused, step one action at a time, then run to the end.

    Args:
        tmp_path: Disposable artifact folder.

    """
    messages: _Messages = _Messages()
    gate: RunGate = RunGate()
    runner: FlowRunner = FlowRunner(output=tmp_path, emit=messages.add)
    runner.gate = gate
    gate.pause()
    outcome: list[Event] = []
    thread: Thread = _start(runner=runner, outcome=outcome)
    expect_true(condition=_held_before(messages=messages, event_id="e0"))
    expect_equal(actual=_variables(runner=runner), expected={})
    gate.step()
    expect_true(condition=_held_before(messages=messages, event_id="e1"))
    expect_equal(actual=_variables(runner=runner), expected={"v0": 0})
    gate.step()
    expect_true(condition=_held_before(messages=messages, event_id="e2"))
    expect_equal(actual=_variables(runner=runner), expected={"v0": 0, "v1": 1})
    gate.resume()
    thread.join(timeout=Constants.wait_seconds)
    expect_false(condition=thread.is_alive())
    expect_equal(actual=outcome[0]["status"], expected="succeeded")
    expect_equal(
        actual=_variables(runner=runner),
        expected={"v0": 0, "v1": 1, "v2": 2},
    )
    expect_equal(
        actual=[state for state, _ in messages.gates()],
        expected=[
            "paused",
            "running",
            "paused",
            "running",
            "paused",
            "running",
        ],
    )
