# Copyright (c) 2026 Project contributors
"""Strict NDJSON protocol shared by GUI, recorder, and execution player."""

from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError, dumps, loads
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from exactus.tools.record.execution import (
        CheckpointCaptureRequest,
        FlowDispatchRequest,
    )
from exactus.tools.record.live_run import RunProgress
from exactus.tools.record.model import (
    ActionRunRecord,
    CapturePhase,
    CheckpointArtifact,
    CheckpointDefinition,
    EventKind,
    ExpectationOutcome,
    ExpectationResult,
    Flow,
    FlowExecutionResult,
    HttpHeader,
    PositionPointerAction,
    RecorderCommand,
    RunStatus,
    RunTransition,
    ScreenshotArtifact,
    TimelineEvent,
    TimelineLayer,
    TransitionMode,
)
from exactus.tools.record.selectors import SelectorCodec
from exactus.tools.record.store import WorkspaceCodec

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type RecorderInbound = (
    TimelineEvent
    | ScreenshotArtifact
    | ExpectationResult
    | FlowExecutionResult
    | CheckpointArtifact
    | RunProgress
)


@dataclass(frozen=True, slots=True)
class _FlowPayloadRequest:
    """Represent  FlowPayloadRequest.

    Attributes:
        flow: Flow.
        device_mode: Device mode.
        message_type: Message type.
        run_id: Run id.
        variables: Variables.
        restore_checkpoint_artifact_id: Restore checkpoint artifact id.
        origin: Origin of the target the flow's local URLs move to.

    """

    flow: Flow
    device_mode: str
    message_type: str
    run_id: str | None
    variables: tuple[JsonValue, ...] = ()
    restore_checkpoint_artifact_id: str | None = None
    origin: str | None = None


class RecorderProtocolError(ValueError):
    """Represent RecorderProtocolError."""


class RecorderProtocol:
    """Represent RecorderProtocol."""

    @classmethod
    def encode_command(cls, *, command: RecorderCommand) -> bytes:
        """Return encode command.

        Args:
            command: Command.

        Returns:
            The resulting value.

        """
        value: dict[str, JsonValue] = {
            "type": "command",
            "name": command.name.value,
            "flow_id": command.flow_id,
            "milliseconds": command.milliseconds,
            "width": command.width,
            "height": command.height,
            "scale": command.scale,
            "device_mode": command.device_mode,
            "capture_images": command.capture_images,
        }
        if command.recording_group_id is not None:
            value["recording_group_id"] = command.recording_group_id
            value["recording_start_ms"] = command.recording_start_ms
        return cls._encode(value=value)

    @classmethod
    def encode_play_request(cls, *, flow: Flow, device_mode: str) -> bytes:
        """Return encode play request.

        Args:
            flow: Flow.
            device_mode: Device mode.

        Returns:
            The resulting value.

        """
        return cls._encode(
            value=cls._flow_payload(
                request=_FlowPayloadRequest(
                    flow=flow,
                    device_mode=device_mode,
                    message_type="play_flow",
                    run_id=None,
                ),
            ),
        )

    @classmethod
    def encode_dispatch_request(cls, *, request: FlowDispatchRequest) -> bytes:
        """Return encode dispatch request.

        Args:
            request: Request.

        Returns:
            The resulting value.

        """
        payload: dict[str, JsonValue] = cls._flow_payload(
            request=_FlowPayloadRequest(
                flow=request.flow,
                device_mode=request.device_mode,
                message_type="execute_flow",
                run_id=request.run_id,
                variables=tuple(
                    WorkspaceCodec.runtime_variable_to_json_value(
                        variable=variable,
                    )
                    for variable in request.variables
                ),
                restore_checkpoint_artifact_id=(
                    request.restore_checkpoint_artifact_id
                ),
                origin=request.origin,
            ),
        )
        payload["selectors"] = [
            SelectorCodec.selector_to_json(item=item)
            for item in request.selectors
        ]
        payload["project"] = {
            "id": request.project_id,
            "name": request.project_name,
            "revision": request.project_revision,
        }
        payload["context"] = {
            "id": request.device_mode,
            "name": request.device_mode,
            "base_url": request.context_base_url,
            "origin": request.origin or "",
        }
        probes: list[JsonValue] = cast(
            typ="list[JsonValue]",
            val=list(request.probes),
        )
        payload["probes"] = probes
        return cls._encode(value=payload)

    @classmethod
    def encode_checkpoint_capture(
        cls,
        *,
        request: CheckpointCaptureRequest,
        definition: CheckpointDefinition,
    ) -> bytes:
        """Return encode checkpoint capture.

        Args:
            request: Request.
            definition: Definition.

        Returns:
            The resulting value.

        """
        value: dict[str, JsonValue] = {
            "type": "capture_checkpoint",
            "run_id": request.run_id,
            "checkpoint_id": request.checkpoint_id,
            "flow_id": request.flow_id,
            "event_id": request.event_id,
            "include_cookies": definition.include_cookies,
            "include_local_storage": definition.include_local_storage,
            "include_session_storage": definition.include_session_storage,
            "include_indexed_db": definition.include_indexed_db,
            "include_variables": definition.include_variables,
        }
        return cls._encode(value=value)

    @classmethod
    def encode_checkpoint_restore(
        cls,
        *,
        run_id: str,
        artifact_id: str,
    ) -> bytes:
        """Return encode checkpoint restore.

        Args:
            run_id: Run id.
            artifact_id: Artifact id.

        Returns:
            The resulting value.

        """
        return cls._encode(
            value={
                "type": "restore_checkpoint",
                "run_id": run_id,
                "artifact_id": artifact_id,
            },
        )

    @classmethod
    def encode_cancel_run(cls, *, run_id: str) -> bytes:
        """Return encode cancel run.

        Args:
            run_id: Run id.

        Returns:
            The resulting value.

        """
        return cls._encode(value={"type": "cancel_run", "run_id": run_id})

    @classmethod
    def decode_message(cls, *, line: bytes) -> RecorderInbound:
        """Return decode message.

        Args:
            line: Line.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._decode_root(line=line)
        message_type: str = cls._string(root=root, key="type")
        if message_type == "event":
            return cls._event_from_root(root=root)
        if message_type == "screenshot":
            return cls._screenshot_from_root(root=root)
        if message_type == "expectation_result":
            return cls._expectation_result_from_root(root=root)
        if message_type == "flow_result":
            return cls._flow_result_from_root(root=root)
        if message_type == "checkpoint":
            return cls._checkpoint_from_root(root=root)
        if message_type in {
            "run_started",
            "flow_started",
            "action_started",
            "action_result",
            "transition_taken",
            "run_finished",
        }:
            return cls._run_progress_from_root(
                root=root,
                message_type=message_type,
            )
        msg: str = f"Unsupported recorder msg type: {message_type}"
        raise RecorderProtocolError(msg)

    @classmethod
    def decode_event(cls, *, line: bytes) -> TimelineEvent:
        """Return decode event.

        Args:
            line: Line.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        decoded: RecorderInbound = cls.decode_message(line=line)
        if not isinstance(decoded, TimelineEvent):
            msg: str = "Recorder msg is not an event."
            raise RecorderProtocolError(msg)
        return decoded

    @classmethod
    def _event_from_root(cls, *, root: dict[str, JsonValue]) -> TimelineEvent:
        """Return event from root.

        Args:
            root: Root.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        try:
            position_action: PositionPointerAction | None = (
                None
                if (
                    raw_action := cls._optional_string(
                        root=root,
                        key="position_action",
                    )
                )
                is None
                else PositionPointerAction(raw_action)
            )
            return TimelineEvent(
                event_id=cls._string(root=root, key="event_id"),
                flow_id=cls._string(root=root, key="flow_id"),
                sequence=-1,
                elapsed_ms=cls._non_negative_integer(
                    root=root,
                    key="elapsed_ms",
                ),
                layer=TimelineLayer(cls._string(root=root, key="layer")),
                kind=EventKind(cls._string(root=root, key="kind")),
                label=cls._string(root=root, key="label"),
                recording_group_id=cls._optional_string(
                    root=root,
                    key="recording_group_id",
                ),
                selector=cls._optional_string(root=root, key="selector"),
                url=cls._optional_string(root=root, key="url"),
                method=cls._optional_string(root=root, key="method"),
                status=cls._optional_integer(root=root, key="status"),
                payload=cls._optional_string(root=root, key="payload"),
                headers=cls._headers(root=root, key="headers"),
                share_session_cookies=cls._optional_boolean(
                    root=root,
                    key="share_session_cookies",
                    default=False,
                ),
                caused_by_event_id=cls._optional_string(
                    root=root,
                    key="caused_by_event_id",
                ),
                position_action=position_action,
                x=cls._optional_integer(root=root, key="x"),
                y=cls._optional_integer(root=root, key="y"),
                end_x=cls._optional_integer(root=root, key="end_x"),
                end_y=cls._optional_integer(root=root, key="end_y"),
                request_id=cls._optional_string(root=root, key="request_id"),
                initiator_url=cls._optional_string(
                    root=root,
                    key="initiator_url",
                ),
                initiator_stack=cls._string_list(
                    root=root,
                    key="initiator_stack",
                ),
                correlation_id=cls._optional_string(
                    root=root,
                    key="correlation_id",
                ),
                attribution_confidence=cls._optional_number(
                    root=root,
                    key="attribution_confidence",
                ),
                attribution_reasons=cls._string_list(
                    root=root,
                    key="attribution_reasons",
                ),
            )
        except ValueError as error:
            raise RecorderProtocolError(str(object=error)) from error

    @classmethod
    def _screenshot_from_root(
        cls,
        *,
        root: dict[str, JsonValue],
    ) -> ScreenshotArtifact:
        """Return screenshot from root.

        Args:
            root: Root.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        try:
            return ScreenshotArtifact(
                artifact_id=cls._string(root=root, key="artifact_id"),
                flow_id=cls._string(root=root, key="flow_id"),
                event_id=cls._string(root=root, key="event_id"),
                phase=CapturePhase(cls._string(root=root, key="phase")),
                path=cls._string(root=root, key="path"),
                width=cls._positive_integer(root=root, key="width"),
                height=cls._positive_integer(root=root, key="height"),
                sha256=cls._string(root=root, key="sha256"),
            )
        except ValueError as error:
            raise RecorderProtocolError(str(object=error)) from error

    @classmethod
    def _expectation_result_from_root(
        cls,
        *,
        root: dict[str, JsonValue],
    ) -> ExpectationResult:
        """Return expectation result from root.

        Args:
            root: Root.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        try:
            return ExpectationResult(
                result_id=cls._string(root=root, key="result_id"),
                flow_id=cls._string(root=root, key="flow_id"),
                event_id=cls._string(root=root, key="event_id"),
                expectation_id=cls._string(root=root, key="expectation_id"),
                outcome=ExpectationOutcome(
                    cls._string(root=root, key="outcome"),
                ),
                details=cls._string(root=root, key="details"),
                matched_url=cls._optional_string(root=root, key="matched_url"),
                actual_status=cls._optional_integer(
                    root=root,
                    key="actual_status",
                ),
                actual_body=cls._optional_string(root=root, key="actual_body"),
            )
        except ValueError as error:
            raise RecorderProtocolError(str(object=error)) from error

    @classmethod
    def _run_progress_from_root(
        cls,
        *,
        root: dict[str, JsonValue],
        message_type: str,
    ) -> RunProgress:
        """Return run progress from root.

        Args:
            root: Root.
            message_type: Message type.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        run_id: str = cls._string(root=root, key="run_id")
        flow_id: str | None = cls._optional_string(root=root, key="flow_id")
        event_id: str | None = cls._optional_string(root=root, key="event_id")
        started_at_utc: str | None = cls._optional_string(
            root=root,
            key="started_at_utc",
        )
        finished_at_utc: str | None = cls._optional_string(
            root=root,
            key="finished_at_utc",
        )
        error: str | None = cls._optional_string(root=root, key="error")
        status_text: str | None = cls._optional_string(root=root, key="status")
        status: RunStatus | None = (
            None if status_text is None else RunStatus(status_text)
        )
        action_record: ActionRunRecord | None = None
        if message_type == "action_result":
            record_value: JsonValue = root.get("action_record")
            if not isinstance(record_value, dict):
                msg: str = "action_result requires action_record."
                raise RecorderProtocolError(msg)
            action_record = WorkspaceCodec.action_record_from_json_value(
                value=record_value,
            )
        transition: RunTransition | None = None
        if message_type == "transition_taken":
            source: str = cls._string(root=root, key="source_flow_id")
            target: str = cls._string(root=root, key="target_flow_id")
            mode: TransitionMode = TransitionMode(
                cls._string(root=root, key="mode"),
            )
            transition = RunTransition(
                source_flow_id=source,
                target_flow_id=target,
                mode=mode,
                reason=cls._string(root=root, key="reason"),
            )
        return RunProgress(
            message_type=message_type,
            run_id=run_id,
            flow_id=flow_id,
            event_id=event_id,
            status=status,
            started_at_utc=started_at_utc,
            finished_at_utc=finished_at_utc,
            action_record=action_record,
            transition=transition,
            error=error,
        )

    @classmethod
    def _flow_result_from_root(
        cls,
        *,
        root: dict[str, JsonValue],
    ) -> FlowExecutionResult:
        """Return flow result from root.

        Args:
            root: Root.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        try:
            return FlowExecutionResult(
                run_id=cls._string(root=root, key="run_id"),
                flow_id=cls._string(root=root, key="flow_id"),
                status=RunStatus(cls._string(root=root, key="status")),
                action_records=tuple(
                    WorkspaceCodec.action_record_from_json_value(value=item)
                    for item in cls._list(root=root, key="action_records")
                ),
                outputs=tuple(
                    WorkspaceCodec.runtime_variable_from_json_value(value=item)
                    for item in cls._list(root=root, key="outputs")
                ),
                error=cls._optional_string(root=root, key="error"),
            )
        except ValueError as error:
            raise RecorderProtocolError(str(object=error)) from error

    @classmethod
    def _checkpoint_from_root(
        cls,
        *,
        root: dict[str, JsonValue],
    ) -> CheckpointArtifact:
        """Return checkpoint from root.

        Args:
            root: Root.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        try:
            return CheckpointArtifact(
                artifact_id=cls._string(root=root, key="artifact_id"),
                checkpoint_id=cls._string(root=root, key="checkpoint_id"),
                run_id=cls._string(root=root, key="run_id"),
                flow_id=cls._string(root=root, key="flow_id"),
                event_id=cls._optional_string(root=root, key="event_id"),
                url=cls._string(root=root, key="url"),
                cookies_json=cls._optional_string(
                    root=root,
                    key="cookies_json",
                ),
                local_storage_json=cls._optional_string(
                    root=root,
                    key="local_storage_json",
                ),
                session_storage_json=cls._optional_string(
                    root=root,
                    key="session_storage_json",
                ),
                indexed_db_json=cls._optional_string(
                    root=root,
                    key="indexed_db_json",
                ),
                variables=tuple(
                    WorkspaceCodec.runtime_variable_from_json_value(value=item)
                    for item in cls._list(root=root, key="variables")
                ),
            )
        except ValueError as error:
            raise RecorderProtocolError(str(object=error)) from error

    @classmethod
    def _decode_root(cls, *, line: bytes) -> dict[str, JsonValue]:
        """Return decode root.

        Args:
            line: Line.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        try:
            value: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=line.decode(encoding="utf-8")),
            )
        except (UnicodeDecodeError, JSONDecodeError) as error:
            raise RecorderProtocolError(str(object=error)) from error
        return cls._mapping(value=value, context="recorder msg")

    @classmethod
    def _non_negative_integer(
        cls,
        *,
        root: dict[str, JsonValue],
        key: str,
    ) -> int:
        """Return non negative integer.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        value: int = cls._integer(root=root, key=key)
        if value < 0:
            msg: str = f"'{key}' cannot be negative."
            raise RecorderProtocolError(msg)
        return value

    @classmethod
    def _positive_integer(cls, *, root: dict[str, JsonValue], key: str) -> int:
        """Return positive integer.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        value: int = cls._integer(root=root, key=key)
        if value <= 0:
            msg: str = f"'{key}' must be positive."
            raise RecorderProtocolError(msg)
        return value

    @classmethod
    def _headers(
        cls,
        *,
        root: dict[str, JsonValue],
        key: str,
    ) -> tuple[HttpHeader, ...]:
        """Return headers.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if value is None:
            return ()
        if not isinstance(value, list):
            msg: str = f"Expected list field '{key}'."
            raise RecorderProtocolError(msg)
        headers: list[HttpHeader] = []
        for item in value:
            mapping: dict[str, JsonValue] = cls._mapping(
                value=item,
                context="HTTP header",
            )
            try:
                headers.append(
                    HttpHeader(
                        name=cls._string(root=mapping, key="name"),
                        value=cls._string(root=mapping, key="value"),
                    ),
                )
            except ValueError as error:
                raise RecorderProtocolError(str(object=error)) from error
        return tuple(headers)

    @staticmethod
    def _flow_payload(*, request: _FlowPayloadRequest) -> dict[str, JsonValue]:
        """Return flow payload.

        Args:
            request: Request.

        Returns:
            The resulting value.

        """
        return {
            "type": request.message_type,
            "run_id": request.run_id,
            "flow_id": request.flow.flow_id,
            "name": request.flow.name,
            "device_mode": request.device_mode,
            "capture_images": request.flow.capture_play_images,
            "task_description": request.flow.task_description,
            "expected_behavior": request.flow.expected_behavior,
            "parameters": [
                {
                    "name": parameter.name,
                    "value_type": parameter.value_type.value,
                    "required": parameter.required,
                    "default_value": parameter.default_value,
                }
                for parameter in request.flow.parameters
            ],
            "outputs": [
                {
                    "name": output.name,
                    "value_type": output.value_type.value,
                    "expression": output.expression,
                }
                for output in request.flow.outputs
            ],
            "variables": list(request.variables),
            "origin": request.origin,
            "restore_checkpoint_artifact_id": (
                request.restore_checkpoint_artifact_id
            ),
            "events": [
                WorkspaceCodec.event_to_json_value(event=event)
                for event in request.flow.events
            ],
            "recordings": [
                {
                    "id": group.recording_id,
                    "label": group.label,
                    "start_ms": group.start_ms,
                }
                for group in request.flow.recordings
            ],
        }

    @staticmethod
    def _encode(*, value: dict[str, JsonValue]) -> bytes:
        """Return encode.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return (
            dumps(obj=value, ensure_ascii=False, separators=(",", ":")).encode(
                encoding="utf-8",
            )
            + b"\n"
        )

    @staticmethod
    def _mapping(*, value: JsonValue, context: str) -> dict[str, JsonValue]:
        """Return mapping.

        Args:
            value: Value.
            context: Context.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        if not isinstance(value, dict):
            msg: str = f"Expected {context} to be a JSON object."
            raise RecorderProtocolError(msg)
        return value

    @staticmethod
    def _string(*, root: dict[str, JsonValue], key: str) -> str:
        """Return string.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if not isinstance(value, str) or value == "":
            msg: str = f"Expected non-empty string field '{key}'."
            raise RecorderProtocolError(msg)
        return value

    @staticmethod
    def _integer(*, root: dict[str, JsonValue], key: str) -> int:
        """Return integer.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            msg: str = f"Expected integer field '{key}'."
            raise RecorderProtocolError(msg)
        return value

    @staticmethod
    def _optional_string(
        *,
        root: dict[str, JsonValue],
        key: str,
    ) -> str | None:
        """Return optional string.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if value is None or isinstance(value, str):
            return value
        msg: str = f"Expected string or null field '{key}'."
        raise RecorderProtocolError(msg)

    @staticmethod
    def _optional_integer(
        *,
        root: dict[str, JsonValue],
        key: str,
    ) -> int | None:
        """Return optional integer.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            msg: str = f"Expected integer or null field '{key}'."
            raise RecorderProtocolError(msg)
        return value

    @staticmethod
    def _optional_number(
        *,
        root: dict[str, JsonValue],
        key: str,
    ) -> float | None:
        """Return optional number.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            msg: str = f"Expected numeric or null field '{key}'."
            raise RecorderProtocolError(msg)
        return float(value)

    @staticmethod
    def _optional_boolean(
        *,
        root: dict[str, JsonValue],
        key: str,
        default: bool,
    ) -> bool:
        """Return optional boolean.

        Args:
            root: Root.
            key: Key.
            default: Default.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if value is None:
            return default
        if not isinstance(value, bool):
            msg: str = f"Expected boolean field '{key}'."
            raise RecorderProtocolError(msg)
        return value

    @staticmethod
    def _list(*, root: dict[str, JsonValue], key: str) -> list[JsonValue]:
        """Return list.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if not isinstance(value, list):
            msg: str = f"Expected list field '{key}'."
            raise RecorderProtocolError(msg)
        return value

    @staticmethod
    def _string_list(
        *,
        root: dict[str, JsonValue],
        key: str,
    ) -> tuple[str, ...]:
        """Return string list.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            RecorderProtocolError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if value is None:
            return ()
        if not isinstance(value, list):
            msg: str = f"Expected list field '{key}'."
            raise RecorderProtocolError(msg)
        strings: list[str] = []
        for item in value:
            if not isinstance(item, str):
                msg = f"Expected string entries in '{key}'."
                raise RecorderProtocolError(msg)
            strings.append(item)
        return tuple(strings)
