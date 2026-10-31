# Copyright (c) 2026 Project contributors
"""Tests for selector-first recorder NDJSON and playback protocol."""

from json import loads
from typing import Final, cast, final

import pytest

from exactus.tests.common.support import (
    dig,
    expect_equal,
    private_call,
    private_result,
)
from exactus.tools.record.execution import (
    CheckpointCaptureRequest,
    FlowDispatchRequest,
)
from exactus.tools.record.live_run import RunProgress
from exactus.tools.record.model import (
    BodyMatchMode,
    CapturePhase,
    CheckpointDefinition,
    DeviceMode,
    EventKind,
    ExpectationOutcome,
    ExpectationResult,
    Flow,
    HttpHeader,
    NetworkExpectation,
    PositionPointerAction,
    RecorderCommand,
    ScreenshotArtifact,
    TimelineEvent,
    TimelineLayer,
)
from exactus.tools.record.recorder_protocol import (
    RecorderInbound,
    RecorderProtocol,
    RecorderProtocolError,
)
from exactus.tools.record.selectors import SelectorDef

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        wait_ms: Grouped module constant.
        x: Grouped module constant.
        y: Grouped module constant.

    """

    wait_ms: Final[int] = 750
    x: Final[int] = 10
    y: Final[int] = 20


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


def test_command_encoder_includes_active_flow() -> None:
    """Handle test command encoder includes active flow."""
    encoded: bytes = RecorderProtocol.encode_command(
        command=RecorderCommand.wait(
            flow_id="flow-7",
            milliseconds=Constants.wait_ms,
        ),
    )
    value: JsonValue = cast(typ="JsonValue", val=loads(s=encoded))
    if not isinstance(value, dict):
        pytest.fail(reason="Encoded command is not a JSON object.")
    _require(condition=value["type"] == "command", msg="Type mismatch.")
    _require(
        condition=value["flow_id"] == "flow-7",
        msg="Encoded Flow ID mismatch.",
    )


def test_selector_event_accepts_selector_without_coordinates() -> None:
    """Handle test selector event accepts selector without coordinates."""
    event: TimelineEvent = RecorderProtocol.decode_event(
        line=(
            b'{"type":"event","event_id":"e1","flow_id":"flow-1","elapsed_'
            b'ms":22,"layer":"interaction","kind":"drag","label":"Drag car'
            b'd","selector":"#card"}'
        ),
    )
    _require(condition=event.kind is EventKind.DRAG, msg="Kind mismatch.")
    _require(condition=event.selector == "#card", msg="Selector mismatch.")
    _require(condition=event.x is None, msg="Unexpected X coordinate.")


def test_selector_event_rejects_coordinate_fallback() -> None:
    """Handle test selector event rejects coordinate fallback."""
    with pytest.raises(
        expected_exception=RecorderProtocolError,
        match="position_pointer",
    ):
        RecorderProtocol.decode_event(
            line=(
                b'{"type":"event","event_id":"e1","flow_id":"flow-1","elap'
                b'sed_ms":22,"layer":"interaction","kind":"drag","label":"'
                b'Drag card","selector":"#card","x":10,"y":20}'
            ),
        )


def test_position_pointer_event_accepts_explicit_coordinates() -> None:
    """Handle test position pointer event accepts explicit coordinates."""
    event: TimelineEvent = RecorderProtocol.decode_event(
        line=(
            b'{"type":"event","event_id":"p1","flow_id":"flow-1","elapsed_'
            b'ms":22,"layer":"interaction","kind":"position_pointer","labe'
            b'l":"Point click","position_action":"click","x":10,"y":20}'
        ),
    )
    _require(
        condition=event.position_action is PositionPointerAction.CLICK,
        msg="Position action mismatch.",
    )
    _require(condition=event.x == Constants.x, msg="X coordinate mismatch.")
    _require(condition=event.y == Constants.y, msg="Y coordinate mismatch.")


def test_event_decoder_accepts_websocket_keyframe() -> None:
    """Handle test event decoder accepts websocket keyframe."""
    event: TimelineEvent = RecorderProtocol.decode_event(
        line=(
            b'{"type":"event","event_id":"ws1","flow_id":"flow-1","elapsed'
            b'_ms":55,"layer":"websocket","kind":"websocket_received","lab'
            b'el":"WS receive","url":"wss://example.test/socket","payload"'
            b':"pong"}'
        ),
    )
    _require(
        condition=event.layer is TimelineLayer.WEBSOCKET,
        msg="WebSocket layer mismatch.",
    )
    _require(condition=event.payload == "pong", msg="Payload mismatch.")


def test_screenshot_message_decodes_record_artifact() -> None:
    """Handle test screenshot message decodes record artifact."""
    msg: RecorderInbound = RecorderProtocol.decode_message(
        line=(
            b'{"type":"screenshot","artifact_id":"shot-1","flow_id":"flow-1","'
            b'event_id":"e1","phase":"record","path":"shots/e1.png","width":39'
            b'0,"height":844,"sha256":"abc"}'
        ),
    )
    if not isinstance(msg, ScreenshotArtifact):
        pytest.fail(reason="Expected a screenshot artifact.")
    _require(
        condition=msg.phase is CapturePhase.RECORD,
        msg="Screenshot phase mismatch.",
    )


def test_expectation_result_message_decodes() -> None:
    """Handle test expectation result message decodes."""
    msg: RecorderInbound = RecorderProtocol.decode_message(
        line=(
            b'{"type":"expectation_result","result_id":"r1","flow_id":"flow-1"'
            b',"event_id":"e1","expectation_id":"x1","outcome":"pass","details'
            b'":"matched","actual_status":200}'
        ),
    )
    if not isinstance(msg, ExpectationResult):
        pytest.fail(reason="Expected an expectation result.")
    _require(
        condition=msg.outcome is ExpectationOutcome.SUCCEEDED,
        msg="Expectation result mismatch.",
    )


def test_play_request_contains_flow_actions_and_capture_policy() -> None:
    """Handle test play request contains flow actions and capture policy."""
    flow: Flow = Flow(
        flow_id="flow-1",
        name="Checkout",
        task_description="Buy",
        expected_behavior="Success",
        notes="",
        capture_play_images=True,
        events=(
            TimelineEvent(
                event_id="e1",
                flow_id="flow-1",
                sequence=0,
                elapsed_ms=0,
                layer=TimelineLayer.INTERACTION,
                kind=EventKind.CLICK,
                label="Checkout",
                selector="#checkout",
            ),
        ),
    )
    value: JsonValue = cast(
        typ="JsonValue",
        val=loads(
            s=RecorderProtocol.encode_play_request(
                flow=flow,
                device_mode=DeviceMode.MOBILE,
            ),
        ),
    )
    if not isinstance(value, dict):
        pytest.fail(reason="Play request was not a JSON object.")
    _require(
        condition=value["capture_images"] is True,
        msg="Play capture policy mismatch.",
    )
    _require(
        condition=value["device_mode"] == "mobile",
        msg="Play device mode mismatch.",
    )


def test_event_decoder_rejects_unknown_kind() -> None:
    """Handle test event decoder rejects unknown kind."""
    with pytest.raises(expected_exception=RecorderProtocolError):
        RecorderProtocol.decode_event(
            line=(
                b'{"type":"event","event_id":"bad","flow_id":"flow-1","elapsed'
                b'_ms":0,"layer":"interaction","kind":"unknown","label":"Bad"}'
            ),
        )


def test_play_request_serializes_http_post_session_and_expectation() -> None:
    """Handle HTTP play-request serialization."""
    flow: Flow = Flow(
        flow_id="flow-api",
        name="API",
        task_description="Create item",
        expected_behavior="Created",
        notes="",
        events=(
            TimelineEvent(
                event_id="call-1",
                flow_id="flow-api",
                sequence=0,
                elapsed_ms=0,
                layer=TimelineLayer.NETWORK,
                kind=EventKind.HTTP_CALL,
                label="Create",
                url="https://example.test/api/items",
                method="POST",
                headers=(
                    HttpHeader(name="Content-Type", value="application/json"),
                ),
                payload='{"name":"A"}',
                share_session_cookies=True,
                expectations=(
                    NetworkExpectation(
                        expectation_id="expect-1",
                        label="Created",
                        method="POST",
                        expected_status=201,
                        body_match=BodyMatchMode.JSON_CONTAINS,
                        expected_body='{"created":true}',
                    ),
                ),
            ),
        ),
    )
    value: JsonValue = cast(
        typ="JsonValue",
        val=loads(
            s=RecorderProtocol.encode_play_request(
                flow=flow,
                device_mode=DeviceMode.DESKTOP,
            ),
        ),
    )
    if not isinstance(value, dict):
        pytest.fail(reason="Play request was not a JSON object.")
    events_value: JsonValue | None = value.get("events")
    if not isinstance(events_value, list) or len(events_value) != 1:
        pytest.fail(reason="Expected one serialized HTTP action.")
    event_value: JsonValue = events_value[0]
    if not isinstance(event_value, dict):
        pytest.fail(reason="Serialized HTTP action was not an object.")
    _require(
        condition=event_value.get("method") == "POST",
        msg="HTTP method was not serialized.",
    )
    _require(
        condition=event_value.get("share_session_cookies") is True,
        msg="Session-cookie policy was not serialized.",
    )
    expectations_value: JsonValue | None = event_value.get("expectations")
    _require(
        condition=isinstance(expectations_value, list)
        and len(expectations_value) == 1,
        msg="Expected-response contract was not serialized.",
    )


def test_run_started_progress_decodes() -> None:
    """Handle test run started progress decodes."""
    msg: RecorderInbound = RecorderProtocol.decode_message(
        line=(
            b'{"type":"run_started","run_id":"run-1","flow_id":"flow-1","start'
            b'ed_at_utc":"2026-10-01T16:00:00Z"}'
        ),
    )
    _require(
        condition=isinstance(msg, RunProgress),
        msg="Progress type mismatch.",
    )
    if not isinstance(msg, RunProgress):
        pytest.fail(reason="Progress narrowing failed.")
    _require(condition=msg.run_id == "run-1", msg="Run ID mismatch.")


def test_protocol_decodes_terminal_checkpoint_and_progress_variants() -> None:
    """Decode terminal and progress message variants."""
    messages: tuple[bytes, ...] = (
        (
            b'{"type":"flow_result","run_id":"r","flow_id":"f","status":"succe'
            b'eded","action_records":[],"outputs":[]}'
        ),
        (
            b'{"type":"checkpoint","artifact_id":"a","checkpoint_id":"c","run_'
            b'id":"r","flow_id":"f","url":"https://example.test","variables":['
            b"]}"
        ),
        (
            b'{"type":"action_result","run_id":"r","flow_id":"f","event_id":"e'
            b'","action_record":{"event_id":"e","flow_id":"f","status":"succee'
            b'ded","attempt":1,"started_ms":0,"finished_ms":1,"assertions":[],'
            b'"observed_event_ids":[],"screenshot_artifact_ids":[],"outputs":['
            b"]}}"
        ),
        (
            b'{"type":"transition_taken","run_id":"r","flow_id":"b","source_fl'
            b'ow_id":"a","target_flow_id":"b","mode":"always","reason":"comple'
            b'te"}'
        ),
        (
            b'{"type":"run_finished","run_id":"r","flow_id":"f","status":"succ'
            b'eeded","finished_at_utc":"2026-10-02T10:00:00Z"}'
        ),
    )
    decoded: tuple[RecorderInbound, ...] = tuple(
        RecorderProtocol.decode_message(line=line) for line in messages
    )
    _require(
        condition=len(decoded) == len(messages),
        msg="Protocol variant count mismatch.",
    )


def test_protocol_encodes_execution_control_messages() -> None:
    """Encode execution-control messages."""
    flow: Flow = Flow(
        flow_id="flow-control",
        name="Control",
        task_description="",
        expected_behavior="",
        notes="",
    )
    dispatch: FlowDispatchRequest = FlowDispatchRequest(
        run_id="run-control",
        flow=flow,
        device_mode=DeviceMode.DESKTOP,
        variables=(),
    )
    capture: CheckpointCaptureRequest = CheckpointCaptureRequest(
        run_id="run-control",
        checkpoint_id="checkpoint-control",
        flow_id="flow-control",
        event_id=None,
    )
    definition: CheckpointDefinition = CheckpointDefinition(
        checkpoint_id="checkpoint-control",
        name="Control",
        flow_id="flow-control",
    )
    payloads: tuple[bytes, ...] = (
        RecorderProtocol.encode_dispatch_request(request=dispatch),
        RecorderProtocol.encode_checkpoint_capture(
            request=capture,
            definition=definition,
        ),
        RecorderProtocol.encode_checkpoint_restore(
            run_id="run-control",
            artifact_id="artifact-control",
        ),
        RecorderProtocol.encode_cancel_run(run_id="run-control"),
    )
    if not all(payload.endswith(b"\n") for payload in payloads):
        pytest.fail(reason="Execution control payload framing failed.")


def test_dispatch_carries_the_projects_selectors() -> None:
    """Send the stored selectors so the player can resolve them."""
    flow: Flow = Flow(
        flow_id="flow-selectors",
        name="Selectors",
        task_description="",
        expected_behavior="",
        notes="",
    )
    payload: bytes = RecorderProtocol.encode_dispatch_request(
        request=FlowDispatchRequest(
            run_id="run-selectors",
            flow=flow,
            device_mode=DeviceMode.DESKTOP,
            variables=(),
            selectors=(
                SelectorDef(
                    selector_id="sel-1",
                    name="card",
                    expression=".card",
                ),
            ),
        ),
    )
    document: JsonValue = loads(s=payload)
    selectors: JsonValue = cast(
        typ="JsonValue",
        val=dig(document=document, path=("selectors",)),
    )
    expect_equal(
        actual=dig(document=selectors, path=(0, "expression")),
        expected=".card",
    )
    expect_equal(
        actual=dig(document=selectors, path=(0, "name")),
        expected="card",
    )


def test_protocol_rejects_malformed_message_shapes() -> None:
    """Reject malformed protocol messages."""
    invalid: tuple[bytes, ...] = (
        b"not-json",
        b"[]",
        b'{"type":"unknown"}',
        b'{"type":"action_result","run_id":"r"}',
        b'{"type":"transition_taken","run_id":"r"}',
        (
            b'{"type":"flow_result","run_id":"r","flow_id":"f","status":"runni'
            b'ng","action_records":[],"outputs":[]}'
        ),
        (
            b'{"type":"checkpoint","artifact_id":"","checkpoint_id":"c","run_i'
            b'd":"r","flow_id":"f","url":"x","variables":[]}'
        ),
    )
    for line in invalid:
        with pytest.raises(expected_exception=RecorderProtocolError):
            RecorderProtocol.decode_message(line=line)
    with pytest.raises(expected_exception=RecorderProtocolError):
        RecorderProtocol.decode_event(
            line=(
                b'{"type":"run_started","run_id":"r","flow_id":"f","started_at'
                b'_utc":"now"}'
            ),
        )


def test_protocol_scalar_validation_helpers() -> None:
    """Check the protocol's scalar validation helpers."""
    bad_cases: tuple[tuple[str, dict[str, JsonValue]], ...] = (
        ("_non_negative_integer", {"x": -1}),
        ("_positive_integer", {"x": 0}),
        ("_integer", {"x": True}),
        ("_optional_string", {"x": 1}),
        ("_optional_integer", {"x": True}),
        ("_optional_number", {"x": True}),
        ("_list", {"x": "bad"}),
        ("_string_list", {"x": "bad"}),
        ("_headers", {"x": "bad"}),
    )
    for name, root in bad_cases:
        with pytest.raises(expected_exception=RecorderProtocolError):
            private_call(owner=RecorderProtocol, name=name, root=root, key="x")
    with pytest.raises(expected_exception=RecorderProtocolError):
        private_call(
            owner=RecorderProtocol,
            name="_optional_boolean",
            root={"x": "bad"},
            key="x",
            default=False,
        )
    with pytest.raises(expected_exception=RecorderProtocolError):
        private_call(
            owner=RecorderProtocol,
            name="_string_list",
            root={"x": [1]},
            key="x",
        )
    with pytest.raises(expected_exception=RecorderProtocolError):
        private_call(
            owner=RecorderProtocol,
            name="_headers",
            root={"x": [{"name": "", "value": "v"}]},
            key="x",
        )
    _require(
        condition=private_result(
            owner=RecorderProtocol,
            name="_optional_boolean",
            kind=bool,
            root={},
            key="x",
            default=True,
        ),
        msg="Defaulted optional boolean should be True.",
    )
    expect_equal(
        actual=private_result(
            owner=RecorderProtocol,
            name="_string_list",
            kind=tuple,
            root={},
            key="x",
        ),
        expected=(),
    )
    expect_equal(
        actual=private_result(
            owner=RecorderProtocol,
            name="_headers",
            kind=tuple,
            root={},
            key="x",
        ),
        expected=(),
    )
