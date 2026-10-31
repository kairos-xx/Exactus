# Copyright (c) 2026 Project contributors
"""Tests for deterministic viewport, targeting, and Flow models."""

from typing import Final, final

import pytest

from exactus.tools.record.model import (
    ConditionOperator,
    DeviceMode,
    EventKind,
    Flow,
    FlowOutput,
    FlowParameter,
    HttpHeader,
    JsonCondition,
    NetworkExpectation,
    PositionPointerAction,
    QueryCondition,
    RecorderCommand,
    RecorderCommandName,
    TimelineEvent,
    TimelineLayer,
    ValueType,
    ViewportSize,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        mobile_width: Grouped module constant.
        mobile_height: Grouped module constant.
        desktop_width: Grouped module constant.
        desktop_height: Grouped module constant.
        half_width: Grouped module constant.
        half_height: Grouped module constant.
        tablet_width: Grouped module constant.
        tablet_height: Grouped module constant.
        half_scale: Grouped module constant.
        pointer_x: Grouped module constant.
        pointer_y: Grouped module constant.

    """

    mobile_width: Final[int] = 390
    mobile_height: Final[int] = 844
    desktop_width: Final[int] = 1440
    desktop_height: Final[int] = 900
    half_width: Final[int] = 720
    half_height: Final[int] = 450
    tablet_width: Final[int] = 1024
    tablet_height: Final[int] = 1366
    half_scale: Final[float] = 0.5
    pointer_x: Final[int] = 20
    pointer_y: Final[int] = 30


def _require(*, condition: bool, msg: str) -> None:
    """Handle require.

    Args:
        condition: Condition.
        msg: Msg.

    Raises:
        AssertionError: When the operation cannot complete.

    """
    if not condition:
        raise AssertionError(msg)


def _event(
    *,
    kind: EventKind,
    selector: str | None = None,
    position_action: PositionPointerAction | None = None,
    x: int | None = None,
    y: int | None = None,
) -> TimelineEvent:
    """Return event.

    Args:
        kind: Kind.
        selector: Selector.
        position_action: Position action.
        x: X.
        y: Y.

    Returns:
        The resulting value.

    """
    return TimelineEvent(
        event_id="event-1",
        flow_id="flow-1",
        sequence=0,
        elapsed_ms=0,
        layer=TimelineLayer.INTERACTION,
        kind=kind,
        label=kind.value,
        selector=selector,
        position_action=position_action,
        x=x,
        y=y,
    )


def test_viewport_orientation_swaps_only_when_needed() -> None:
    """Handle test viewport orientation swaps only when needed."""
    portrait: ViewportSize = ViewportSize(
        width=Constants.mobile_width,
        height=Constants.mobile_height,
    )
    _require(
        condition=portrait.vertical() == portrait,
        msg="Portrait orientation changed dimensions.",
    )
    _require(
        condition=portrait.horizontal()
        == ViewportSize(
            width=Constants.mobile_height,
            height=Constants.mobile_width,
        ),
        msg="Horizontal orientation did not swap dimensions.",
    )


def test_wait_command_rejects_non_positive_duration() -> None:
    """Handle test wait command rejects non positive duration."""
    with pytest.raises(expected_exception=ValueError, match="positive"):
        RecorderCommand.wait(flow_id="flow-1", milliseconds=0)


def test_viewport_command_contains_mode_size_and_display_scale() -> None:
    """Handle test viewport command contains mode size and display scale."""
    command: RecorderCommand = RecorderCommand.viewport(
        flow_id="flow-1",
        viewport=ViewportSize(
            width=Constants.tablet_width,
            height=Constants.tablet_height,
        ),
        device_mode=DeviceMode.TABLET,
    )
    _require(
        condition=command.name is RecorderCommandName.VIEWPORT,
        msg="Unexpected recorder command name.",
    )
    _require(
        condition=command.device_mode is DeviceMode.TABLET,
        msg="Viewport command device mode mismatch.",
    )
    _require(
        condition=command.width == Constants.tablet_width,
        msg="Viewport command width mismatch.",
    )
    _require(
        condition=command.height == Constants.tablet_height,
        msg="Viewport command height mismatch.",
    )
    _require(
        condition=command.scale == 1.0,
        msg="Viewport command scale mismatch.",
    )


def test_selector_pointer_actions_require_css_selector() -> None:
    """Handle test selector pointer actions require css selector."""
    with pytest.raises(expected_exception=ValueError, match="CSS selector"):
        _event(kind=EventKind.CLICK)


def test_selector_action_rejects_coordinates() -> None:
    """Handle test selector action rejects coordinates."""
    with pytest.raises(
        expected_exception=ValueError,
        match="position_pointer",
    ):
        _event(
            kind=EventKind.DRAG,
            selector="#card",
            x=Constants.pointer_x,
            y=Constants.pointer_y,
        )


def test_explicit_position_pointer_accepts_coordinates() -> None:
    """Handle test explicit position pointer accepts coordinates."""
    event: TimelineEvent = _event(
        kind=EventKind.POSITION_POINTER,
        position_action=PositionPointerAction.RIGHT_CLICK,
        x=Constants.pointer_x,
        y=Constants.pointer_y,
    )
    _require(condition=event.selector is None, msg="Unexpected selector.")
    _require(
        condition=event.x == Constants.pointer_x,
        msg="X coordinate mismatch.",
    )


def test_flow_device_scope_supports_shared_and_selected_modes() -> None:
    """Handle test flow device scope supports shared and selected modes."""
    shared: Flow = Flow(
        flow_id="shared",
        name="Shared",
        task_description="",
        expected_behavior="",
        notes="",
    )
    selected: Flow = Flow(
        flow_id="selected",
        name="Selected",
        task_description="",
        expected_behavior="",
        notes="",
        device_modes=frozenset({DeviceMode.MOBILE, DeviceMode.TABLET}),
    )
    _require(
        condition=shared.applies_to(device_mode=DeviceMode.DESKTOP),
        msg="Shared Flow should apply to desktop.",
    )
    _require(
        condition=selected.applies_to(device_mode=DeviceMode.TABLET),
        msg="Selected Flow should apply to tablet.",
    )
    _require(
        condition=not selected.applies_to(device_mode=DeviceMode.DESKTOP),
        msg="Selected Flow unexpectedly applied to desktop.",
    )


def test_viewport_rejects_out_of_range_edge() -> None:
    """Handle test viewport rejects out of range edge."""
    with pytest.raises(expected_exception=ValueError, match="between"):
        ViewportSize(width=159, height=Constants.mobile_height)


def test_passive_response_cannot_own_network_expectation() -> None:
    """Handle test passive response cannot own network expectation."""
    with pytest.raises(
        expected_exception=ValueError,
        match="executable Flow actions",
    ):
        TimelineEvent(
            event_id="response-1",
            flow_id="flow-1",
            sequence=0,
            elapsed_ms=0,
            layer=TimelineLayer.NETWORK,
            kind=EventKind.RESPONSE,
            label="Observed response",
            url="https://example.test/api/items",
            method="GET",
            status=200,
            expectations=(
                NetworkExpectation(
                    expectation_id="expect-1",
                    label="Unexpected owner",
                ),
            ),
        )


def test_model_validation_rejects_invalid_contract_metadata() -> None:
    """Exercise validation guards for persisted contract metadata."""
    with pytest.raises(expected_exception=ValueError, match="header name"):
        HttpHeader(name="", value="x")
    with pytest.raises(expected_exception=ValueError, match="name cannot"):
        QueryCondition(name="", operator=ConditionOperator.EXISTS)
    with pytest.raises(expected_exception=ValueError, match="require a value"):
        QueryCondition(name="q", operator=ConditionOperator.EQUALS)
    with pytest.raises(expected_exception=ValueError, match="must start"):
        JsonCondition(path="data.id", operator=ConditionOperator.EXISTS)
    with pytest.raises(expected_exception=ValueError, match="Expectation ID"):
        NetworkExpectation(expectation_id="", label="invalid")
    with pytest.raises(expected_exception=ValueError, match="timeout"):
        NetworkExpectation(expectation_id="x", label="invalid", timeout_ms=0)
    with pytest.raises(expected_exception=ValueError, match="parameter name"):
        FlowParameter(name="", value_type=ValueType.STRING)
    with pytest.raises(expected_exception=ValueError, match="Flow outputs"):
        FlowOutput(name="", value_type=ValueType.STRING, expression="")
