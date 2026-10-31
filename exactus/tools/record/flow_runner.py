# Copyright (c) 2026 Project contributors
"""Execute Studio flows with assertions and durable browser evidence.

The same runner powers the service-owned browser and unattended tests.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from json import dumps, loads
from re import Match, Pattern, search
from re import compile as compile_pattern
from textwrap import dedent
from time import monotonic, time
from typing import TYPE_CHECKING, Final, Protocol, cast, final
from urllib.parse import (
    SplitResult,
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)
from uuid import uuid4

from PIL import Image
from playwright.sync_api import (
    APIRequestContext,
    Browser,
    BrowserContext,
    CDPSession,
    Cookie,
    FloatRect,
    Locator,
    Page,
    Response,
    ViewportSize,
)
from playwright.sync_api import Error as PlaywrightError

from exactus.tools.record.action_recorder import (
    Action,
    ActionReplayer,
    JsonValue,
    ReplayOptions,
)
from exactus.tools.record.assertions import AssertionEvaluator
from exactus.tools.record.expectations import NetworkExpectationEvaluator
from exactus.tools.record.expressions import (
    ExpressionError,
    ExpressionEvaluator,
)
from exactus.tools.record.http_request import (
    HttpResult,
    PreparedRequest,
    cookie_header,
    send_request,
)
from exactus.tools.record.model import (
    AssertionKind,
    AssertionOutcome,
    AssertionResult,
    AssertionSpec,
    BodyMatchMode,
    EventKind,
    Flow,
    HttpHeader,
    NetworkExpectation,
    RuntimeVariable,
    TimelineEvent,
    TimelineLayer,
)
from exactus.tools.record.rebase import rebase_url
from exactus.tools.record.response_paths import read_json_path, read_xml_path
from exactus.tools.record.selector_probes import (
    ProbeRef,
    probe_refs,
    probe_variables,
)
from exactus.tools.record.selector_resolver import Resolution, SelectorResolver
from exactus.tools.record.selector_sandbox import (
    RunStreams,
    SandboxCall,
    SandboxResult,
    StreamEntry,
    merge,
    run_sandbox,
)
from exactus.tools.record.selector_snapshot import (
    compare_evidence,
    parse_baseline,
)
from exactus.tools.record.selector_targets import (
    TargetPlanner,
    Unit,
    failure_cause,
)
from exactus.tools.record.selectors import (
    Pace,
    RunMode,
    SelectorCodec,
    SelectorDef,
)
from exactus.tools.record.store import WorkspaceCodec
from exactus.tools.record.workspace_actions import (
    Event,
    build_workspace,
    event_action,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from exactus.tools.record.run_gate import RunGate


@final
class Constants:
    """Group module-level constants.

    Attributes:
        path_token: Grouped module constant.
        path_step: Grouped module constant.

    """

    path_token: Final[Pattern[str]] = compile_pattern(
        pattern=(
            "\\{\\{(?P<name>[^{}.\\[\\]|]+)(?P<path>(?:\\.[^{}.\\[\\]|]+|\\[\\"
            "d+\\])*)(?:\\|(?P<getter>keys|values|count))?\\}\\}"
        ),
    )
    path_step: Final[Pattern[str]] = compile_pattern(
        pattern="\\.([^{}.\\[\\]|]+)|\\[(\\d+)\\]",
    )


class _CDPSender(Protocol):
    """Typed subset of a Chrome DevTools Protocol session."""

    def send(
        self,
        method: str,
        params: dict[str, JsonValue] | None = None,
    ) -> dict[str, JsonValue]:
        """Send one protocol command.

        Args:
            method: Protocol method name, such as ``Input.dispatchTouchEvent``.
            params: Method parameters, or None when the method takes none.

        Returns:
            The protocol result object.

        """
        ...


def _ignore_message(message: Event) -> None:
    """Discard messages when callers only need the returned result.

    Args:
        message: Message for this operation.

    """
    _ = message


@dataclass(slots=True, kw_only=True)
class _Progress:
    """Track one flow run while its actions execute.

    Attributes:
        run_id: Identifier of the run.
        flow_id: Flow being run.
        origin: Monotonic start time, for action timestamps.
        capture: Whether to capture screenshots after actions.
        records: Action records produced so far.
        recording_origins: Playback clocks of recording groups.
        failed: Whether any action has failed.
        stop: Whether remaining actions must be skipped.

    """

    run_id: str
    flow_id: str
    origin: float
    capture: bool
    records: list[Event]
    recording_origins: dict[str, tuple[float, int]]
    failed: bool = False
    stop: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceRequest:
    """Describe what a screenshot belongs to and how to leave the page.

    Attributes:
        flow_id: Flow the screenshot belongs to.
        event_id: Action the screenshot belongs to.
        phase: Record or play phase.
        after_capture: Called once the page is captured. A full-page capture
            makes Chromium drop touch emulation, so callers that emulate a
            device use this to put it back before the next action.

    """

    flow_id: str
    event_id: str
    phase: str
    after_capture: Callable[[Page], None] | None = None


def capture_evidence(
    *,
    page: Page,
    output: Path,
    request: EvidenceRequest,
) -> Event:
    """Capture a PNG with dimensions and an integrity hash.

    Args:
        page: Browser page for replay and assertions.
        output: Destination for generated artifacts.
        request: Owner of the screenshot and post-capture restoration.


    Returns:
        Screenshot artifact record.

    """
    artifact_id: str = uuid4().hex
    directory: Path = output.resolve() / "screenshots"
    directory.mkdir(parents=True, exist_ok=True)
    path: Path = directory / f"{artifact_id}.png"
    data: bytes = page.screenshot(
        path=path,
        full_page=True,
        animations="disabled",
    )
    if request.after_capture is not None:
        request.after_capture(page)
    with Image.open(fp=BytesIO(initial_bytes=data)) as image:
        width, height = image.size
    return {
        "type": "screenshot",
        "artifact_id": artifact_id,
        "flow_id": request.flow_id,
        "event_id": request.event_id,
        "phase": request.phase,
        "path": str(object=path),
        "width": width,
        "height": height,
        "sha256": sha256(data=data).hexdigest(),
    }


class FlowRunner:
    """Replay actions, check contracts, and report every attempted step."""

    def __init__(
        self,
        *,
        output: Path,
        timeout_ms: float = 5000,
        emit: Callable[[Event], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
        after_capture: Callable[[Page], None] | None = None,
    ) -> None:
        """Configure the artifact directory, timeout, and protocol sink.

        Args:
            output: Destination for generated artifacts.
            timeout_ms: Timeout ms for this operation.
            emit: Callback receiving replay progress.
            cancelled: Cooperative cancellation signal from the service.
            after_capture: Restores device emulation after a screenshot.

        """
        self.gate: RunGate | None = None
        self.after_capture = after_capture
        self.output = output
        self.timeout_ms = timeout_ms
        self.emit = emit or _ignore_message
        self.cancelled = cancelled or (lambda: False)
        self._origin: str | None = None
        self._run_id: str = ""
        self._selectors: tuple[SelectorDef, ...] = ()
        self._streams: RunStreams = RunStreams()
        self._batch: dict[tuple[str, int | None], SandboxResult] = {}
        self._variables: tuple[RuntimeVariable, ...] = ()
        self._resolver: SelectorResolver | None = None
        self._project: dict[str, JsonValue] = {}
        self._context: dict[str, JsonValue] = {}
        self._flow_name: str = ""
        self._device_mode: str = ""

    def run(self, *, page: Page, message: Event) -> Event:
        """Execute one Flow and emit run and artifact messages.

        Args:
            page: Browser page for replay and assertions.
            message: Message for this operation.


        Returns:
            Flow result event.

        Raises:
            ValueError: When the message lacks steps or requests unsupported
                features.

        """
        flow_id: str = str(object=message.get("flow_id") or "flow")
        run_id: str = str(object=message.get("run_id") or uuid4().hex)
        target_origin: JsonValue = message.get("origin")
        self._origin = (
            target_origin
            if isinstance(target_origin, str) and target_origin
            else None
        )
        raw_events: JsonValue = message.get("events")
        if not isinstance(raw_events, list) or not raw_events:
            msg: str = "A functional test requires at least one step."
            raise ValueError(msg)
        document: Event = build_workspace(
            flows=[
                {
                    "id": flow_id,
                    "name": str(object=message.get("name") or flow_id),
                    "task_description": "",
                    "expected_behavior": "",
                    "notes": "",
                    "device_modes": ["shared"],
                    "events": raw_events,
                    "recordings": message.get("recordings", []),
                    "capture_record_images": False,
                    "capture_play_images": False,
                    "parameters": [],
                    "outputs": [],
                },
            ],
        )
        document.update(
            version=3,
            variables=[],
            checkpoint_definitions=[],
            checkpoint_artifacts=[],
            runs=[],
        )
        for raw in raw_events:
            if isinstance(raw, dict):
                event_document: dict[str, JsonValue] = raw
                event_document.setdefault("initiator_stack", [])
                event_document.setdefault("attribution_reasons", [])
                event_document.setdefault(
                    "contract",
                    {
                        "preconditions": [],
                        "postconditions": [],
                        "outputs": [],
                        "retry_count": 0,
                        "retry_delay_ms": 0,
                        "continue_on_failure": False,
                    },
                )
        flow: Flow = WorkspaceCodec.from_json_value(value=document).flows[0]
        if message.get("outputs") or message.get(
            "restore_checkpoint_artifact_id",
        ):
            msg = (
                "Flow outputs and checkpoint restoration "
                "are not supported by this player yet."
            )
            raise ValueError(msg)
        page.set_default_timeout(timeout=self.timeout_ms)
        self.emit(
            {
                "type": "run_started",
                "run_id": run_id,
                "flow_id": flow_id,
                "started_at_utc": datetime.now(tz=UTC).isoformat(),
            },
        )
        self._run_id = run_id
        raw_project: JsonValue = message.get("project")
        raw_context: JsonValue = message.get("context")
        self._project = raw_project if isinstance(raw_project, dict) else {}
        self._context = raw_context if isinstance(raw_context, dict) else {}
        self._flow_name = str(object=message.get("name") or flow.name)
        self._device_mode = str(object=message.get("device_mode") or "shared")
        self._selectors = self._selectors_in(message=message)
        self._streams = RunStreams()
        self._batch = {}
        self._variables = self._variables_in(message=message)
        self._streams.vars.update(
            {
                variable.name: variable.value
                for variable in self._variables
                if variable.value is not None
            },
        )
        self._resolver = SelectorResolver(
            page=page,
            selectors=self._selectors,
            timeout_ms=int(self.timeout_ms),
        )
        progress: _Progress = _Progress(
            run_id=run_id,
            flow_id=flow_id,
            origin=monotonic(),
            capture=message.get("capture_images") is True,
            records=[],
            recording_origins={},
        )
        planner: TargetPlanner = TargetPlanner(
            page=page,
            selectors=self._selectors,
            timeout_ms=int(self.timeout_ms),
        )
        for event in sorted(flow.events, key=lambda item: item.sequence):
            self._hold_for_gate(event=event)
            self._execute_event(
                page=page,
                event=event,
                planner=planner,
                progress=progress,
            )
        records: list[Event] = progress.records
        failed: bool = progress.failed
        result: Event = {
            "type": "flow_result",
            "run_id": run_id,
            "flow_id": flow_id,
            "status": "cancelled"
            if self.cancelled()
            else "failed"
            if failed
            else "succeeded",
            "action_records": cast(typ="JsonValue", val=records),
            "outputs": self._probe_outputs(message=message),
            "error": "One or more steps failed." if failed else None,
        }
        self.emit(
            {
                "type": "run_finished",
                "run_id": run_id,
                "flow_id": flow_id,
                "status": result["status"],
                "finished_at_utc": datetime.now(tz=UTC).isoformat(),
                "error": result["error"],
            },
        )
        return result

    @classmethod
    def _perform_gesture(cls, *, page: Page, event: TimelineEvent) -> None:
        """Dispatch a touch gesture at the target element.

        Args:
            page: Page receiving touch events.
            event: Gesture action and JSON options.

        Raises:
            TypeError: When the options are not a JSON object.
            ValueError: When the target or gesture is invalid.

        """
        raw: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=event.payload or "{}"),
        )
        if not isinstance(raw, dict):
            msg: str = "Touch gesture requires an object specification."
            raise TypeError(msg)
        locator: Locator = page.locator(selector=event.selector or "body")
        box: FloatRect | None = locator.bounding_box()
        if box is None:
            msg = "Touch gesture target is not visible."
            raise ValueError(msg)
        center_x: float = box["x"] + box["width"] / 2
        center_y: float = box["y"] + box["height"] / 2
        gesture: str = str(object=raw.get("gesture") or "tap")
        if gesture == "tap":
            page.touchscreen.tap(x=center_x, y=center_y)
            return
        duration_ms: int = int(str(object=raw.get("duration_ms") or 350))
        distance: float = float(str(object=raw.get("distance") or 180))
        direction: str = str(object=raw.get("direction") or "up")
        vectors: dict[str, tuple[float, float]] = {
            "down": (0.0, distance),
            "left": (-distance, 0.0),
            "right": (distance, 0.0),
            "up": (0.0, -distance),
        }
        delta_x, delta_y = vectors.get(direction, vectors["up"])
        session: CDPSession = page.context.new_cdp_session(page=page)
        try:
            if gesture == "long_press":
                cls._dispatch_touch(
                    session=session,
                    event_type="touchStart",
                    points=((center_x, center_y),),
                )
                page.wait_for_timeout(timeout=duration_ms)
                cls._dispatch_touch(
                    session=session,
                    event_type="touchEnd",
                    points=(),
                )
                return
            if gesture == "pinch":
                scale: float = float(str(object=raw.get("scale") or 1.5))
                start: float = min(box["width"], box["height"]) / 8
                finish: float = start * scale
                cls._dispatch_touch(
                    session=session,
                    event_type="touchStart",
                    points=(
                        (center_x - start, center_y),
                        (center_x + start, center_y),
                    ),
                )
                cls._dispatch_touch(
                    session=session,
                    event_type="touchMove",
                    points=(
                        (center_x - finish, center_y),
                        (center_x + finish, center_y),
                    ),
                )
            elif gesture == "swipe":
                cls._dispatch_touch(
                    session=session,
                    event_type="touchStart",
                    points=((center_x, center_y),),
                )
                page.wait_for_timeout(timeout=max(1, duration_ms // 2))
                cls._dispatch_touch(
                    session=session,
                    event_type="touchMove",
                    points=((center_x + delta_x, center_y + delta_y),),
                )
            else:
                msg = f"Unsupported touch gesture: {gesture}"
                raise ValueError(msg)
            page.wait_for_timeout(timeout=max(1, duration_ms // 2))
            cls._dispatch_touch(
                session=session,
                event_type="touchEnd",
                points=(),
            )
        finally:
            session.detach()

    @classmethod
    def _coerce_response_capture(
        cls,
        *,
        name: str,
        value: JsonValue,
        value_type: str,
    ) -> JsonValue:
        """Convert a selected response value to its authored variable type.

        Args:
            name: Variable receiving the value.
            value: Selected response value.
            value_type: ``string``, ``integer``, ``float``, ``boolean`` or
                ``json``.

        Returns:
            Converted JSON-compatible value.

        Raises:
            ValueError: When the conversion is unsupported or invalid.

        """
        supported: set[str] = {"boolean", "float", "integer", "json", "string"}
        if value_type not in supported:
            msg: str = f"Unsupported response variable type: {value_type}"
            raise ValueError(msg)
        try:
            if value_type == "json":
                result: JsonValue = value
            elif value_type == "string":
                result = "" if value is None else cls._stringify(value=value)
            elif value_type == "integer":
                result = int(str(object=value))
            elif value_type == "float":
                result = float(str(object=value))
            elif isinstance(value, bool):
                result = value
            else:
                boolean_values: dict[str, bool] = {
                    "false": False,
                    "no": False,
                    "0": False,
                    "true": True,
                    "yes": True,
                    "1": True,
                }
                result = boolean_values[str(object=value).strip().lower()]
        except (KeyError, TypeError, ValueError) as error:
            msg = f"Response variable {name!r} is not a valid {value_type}."
            raise ValueError(msg) from error
        return result

    @staticmethod
    def _perform_snapshot(
        *,
        page: Page,
        event: TimelineEvent,
        unit: Unit,
    ) -> JsonValue:
        """Record the matched element and compare it with its baseline.

        Args:
            page: Page for this operation.
            event: Snapshot action; its payload holds the baseline.
            unit: Target whose evidence was gathered while resolving.

        Returns:
            Evidence, page address and any drift from the baseline.

        """
        current: dict[str, JsonValue] = unit.evidence or {}
        baseline: dict[str, JsonValue] | None = parse_baseline(
            payload=event.payload,
        )
        drift: list[dict[str, JsonValue]] | None = (
            None
            if baseline is None
            else compare_evidence(baseline=baseline, current=current)
        )
        return {
            "evidence": current,
            "url": page.url,
            "selector_id": unit.selector_id,
            "baseline": baseline is not None,
            "drift": cast(typ="JsonValue", val=drift),
        }

    @staticmethod
    def _gate_cause(*, pace: Pace, message: str) -> dict[str, JsonValue]:
        """Describe a wait that failed.

        Args:
            pace: The pace that failed.
            message: What went wrong.

        Returns:
            A structured ``gate`` cause.

        """
        return {
            "phase": "gate",
            "message": message,
            "expression": pace.until,
            "timeout_ms": pace.timeout_ms,
        }

    @staticmethod
    def _is_failure(*, record: Event) -> bool:
        """Tell whether an action record counts as a failure.

        Drift from a snapshot baseline is a warning that does not fail the
        flow; a failure the author chose to tolerate still counts.

        Args:
            record: Action record.

        Returns:
            True for failed records and tolerated failures.

        """
        if record["status"] == "failed":
            return True
        cause: JsonValue = record.get("cause")
        return record["status"] == "warning" and (
            not (isinstance(cause, dict) and cause.get("phase") == "drift")
        )

    @staticmethod
    def _variables_in(*, message: Event) -> tuple[RuntimeVariable, ...]:
        """Read the run's variables from a run message.

        Args:
            message: Run message that may carry a ``variables`` list.

        Returns:
            The variables, or none.

        """
        items: JsonValue = message.get("variables")
        if not isinstance(items, list):
            return ()
        return tuple(
            WorkspaceCodec.runtime_variable_from_json_value(value=item)
            for item in items
        )

    @staticmethod
    def _selectors_in(*, message: Event) -> tuple[SelectorDef, ...]:
        """Read the project's selectors from a run message.

        Args:
            message: Run message that may carry a ``selectors`` list.

        Returns:
            The selectors, or none.

        """
        items: JsonValue = message.get("selectors")
        if not isinstance(items, list):
            return ()
        return SelectorCodec.from_json_value(
            value={"version": 1, "selectors": items},
        )

    @staticmethod
    def _perform_viewport(*, page: Page, event: TimelineEvent) -> None:
        """Resize or rotate the live page viewport.

        Args:
            page: Page receiving the viewport change.
            event: Viewport action carrying its JSON specification.

        Raises:
            TypeError: When the specification is not a JSON object.
            ValueError: When the page viewport is invalid.

        """
        raw: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=event.payload or "{}"),
        )
        if not isinstance(raw, dict):
            msg: str = "Viewport action requires an object specification."
            raise TypeError(msg)
        action: str = str(object=raw.get("action") or "")
        current: ViewportSize | None = page.viewport_size
        if action == "rotate" and current is not None:
            width: int = current["height"]
            height: int = current["width"]
        elif action == "resize":
            width = int(str(object=raw.get("width") or 0))
            height = int(str(object=raw.get("height") or 0))
        else:
            msg = "Viewport action requires a current viewport to rotate."
            raise ValueError(msg)
        page.set_viewport_size(
            viewport_size={"width": width, "height": height},
        )

    @staticmethod
    def _dispatch_touch(
        *,
        session: CDPSession,
        event_type: str,
        points: tuple[tuple[float, float], ...],
    ) -> None:
        """Send one Chrome touch event.

        Args:
            session: Page CDP session.
            event_type: Chrome touch event name.
            points: Active touch coordinates.

        """
        sender: _CDPSender = cast(typ="_CDPSender", val=session)
        sender.send(
            method="Input.dispatchTouchEvent",
            params={
                "type": event_type,
                "touchPoints": [
                    {"x": x, "y": y, "id": index + 1}
                    for index, (x, y) in enumerate(iterable=points)
                ],
            },
        )

    @staticmethod
    def _request_config(*, event: TimelineEvent) -> dict[str, JsonValue]:
        """Read the portable mini-REST-client payload.

        Args:
            event: HTTP event.

        Returns:
            Request configuration, or a legacy body wrapper.

        """
        try:
            value: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=event.payload or "{}"),
            )
        except ValueError:
            return {"body": event.payload or ""}
        return (
            value if isinstance(value, dict) else {"body": event.payload or ""}
        )

    @staticmethod
    def _validation_actual(
        *,
        response: TimelineEvent,
        kind: str,
        path: str,
    ) -> str | None:
        """Select one response value for REST validation.

        Args:
            response: Observed response event.
            kind: Source to read: ``status``, ``header`` or ``json``.
            path: Header name or JSON path, depending on ``kind``.

        Returns:
            The selected text, or None when the source is absent.

        """
        if kind == "status":
            return str(object=response.status)
        if kind == "header":
            return next(
                (
                    item.value
                    for item in response.headers
                    if item.name.lower() == path.lower()
                ),
                None,
            )
        if kind != "json":
            return response.payload or ""
        try:
            current: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=response.payload or "null"),
            )
        except ValueError:
            return None
        for part in path.split(sep=".") if path else ():
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                index: int = int(part)
                current = current[index] if index < len(current) else None
            else:
                return None
        return (
            None
            if current is None
            else current
            if isinstance(current, str)
            else dumps(obj=current)
        )

    @staticmethod
    def _validation_passes(
        *,
        actual: str | None,
        operator: str,
        expected: str,
    ) -> bool:
        """Evaluate one REST validation operator.

        Args:
            actual: Value read from the response, or None when absent.
            operator: ``exists``, ``contains``, ``matches`` or equality.
            expected: Authored value the response is compared against.

        Returns:
            Whether the response satisfies the check.

        """
        if operator == "exists":
            return actual is not None
        if actual is None:
            return False
        if operator == "contains":
            return expected in actual
        if operator == "matches":
            return search(pattern=expected, string=actual) is not None
        return actual == expected

    @staticmethod
    def _stringify(*, value: JsonValue) -> str:
        """Render one variable value into text.

        Args:
            value: Run variable value.

        Returns:
            The value itself when text, otherwise its JSON encoding.

        """
        return (
            value
            if isinstance(value, str)
            else dumps(obj=value, ensure_ascii=False)
        )

    @staticmethod
    def _getter(*, getter: str, value: JsonValue) -> JsonValue | None:
        """Read a dictionary or list as a whole.

        Args:
            getter: ``keys``, ``values`` or ``count``.
            value: The addressed value.

        Returns:
            The result, or None when the getter does not fit the value.

        """
        if getter == "count":
            return len(value) if isinstance(value, dict | list | str) else None
        if isinstance(value, dict):
            members: dict[str, JsonValue] = value
            if getter == "keys":
                names: list[JsonValue] = list(members)
                return names
            return list(members.values())
        if isinstance(value, list) and getter == "values":
            return value
        return None

    @staticmethod
    def _response_capture_source(
        *,
        response: dict[str, JsonValue],
        source: str,
    ) -> JsonValue:
        """Select the root value named by one response mapping.

        Args:
            response: REST response or WebSocket session result.
            source: Authored response source.

        Returns:
            Root value before applying an optional path.

        """
        if source == "message_json":
            message: JsonValue = response.get("last_message")
            if not isinstance(message, str):
                return None
            try:
                return cast(typ="JsonValue", val=loads(s=message))
            except ValueError:
                return None
        if source == "message_text":
            return response.get("last_message")
        return response.get(source)

    def _request_validations(
        self,
        *,
        config: dict[str, JsonValue],
        response: TimelineEvent,
    ) -> None:
        """Validate common REST response properties.

        Args:
            config: REST-client specification.
            response: Observed response.

        Raises:
            ValueError: When a configured check fails.

        """
        validations: JsonValue = config.get("validations")
        if not isinstance(validations, list):
            return
        for item in validations:
            if not isinstance(item, dict):
                continue
            kind: str = str(object=item.get("kind") or "status")
            path: str = str(object=item.get("path") or "")
            operator: str = str(object=item.get("operator") or "equals")
            expected: str = str(object=item.get("expected") or "")
            actual: str | None = self._validation_actual(
                response=response,
                kind=kind,
                path=path,
            )
            passed: bool = self._validation_passes(
                actual=actual,
                operator=operator,
                expected=self._template(value=expected) or "",
            )
            if not passed:
                msg: str = (
                    f"REST response {kind} {operator} check failed: "
                    f"expected {expected!r}, got {actual!r}."
                )
                raise ValueError(msg)

    def _actual(
        self,
        *,
        page: Page,
        spec: AssertionSpec,
    ) -> tuple[str | None, bool]:
        """Actual for recorded flow execution.

        Args:
            page: Page for this operation.
            spec: Spec for this operation.

        Returns:
            The verified result of this operation.

        Raises:
            ValueError: When input or state does not satisfy the contract.

        """
        kind: AssertionKind = spec.kind
        if kind is AssertionKind.URL:
            return (page.url, True)
        if kind is AssertionKind.TITLE:
            return (page.title(), True)
        if kind in {
            AssertionKind.LOCAL_STORAGE,
            AssertionKind.SESSION_STORAGE,
        }:
            storage: str = (
                "localStorage"
                if kind is AssertionKind.LOCAL_STORAGE
                else "sessionStorage"
            )
            stored: str | None = page.evaluate(
                expression=f"key => {storage}.getItem(key)",
                arg=spec.target,
            )
            return (stored, stored is not None)
        if kind is AssertionKind.CONSOLE:
            msg: str = (
                "Console assertions are not supported by this player yet."
            )
            raise ValueError(msg)
        if kind is AssertionKind.COOKIE:
            cookie: Cookie | None = next(
                (
                    item
                    for item in page.context.cookies()
                    if item.get("name") == spec.target
                ),
                None,
            )
            return (
                (None, False)
                if cookie is None
                else (cookie.get("value"), True)
            )
        if kind is AssertionKind.JAVASCRIPT:
            evaluated: JsonValue = page.evaluate(expression=spec.target)
            return (
                None if evaluated is None else str(object=evaluated),
                evaluated is not None,
            )
        return self._dom_actual(page=page, spec=spec)

    def _dom_actual(
        self,
        *,
        page: Page,
        spec: AssertionSpec,
    ) -> tuple[str | None, bool]:
        """Dom actual for recorded flow execution.

        Args:
            page: Page for this operation.
            spec: Spec for this operation.

        Returns:
            The verified result of this operation.

        Raises:
            ValueError: When input or state does not satisfy the contract.

        """
        kind: AssertionKind = spec.kind
        selector: str = self._assertion_css(spec=spec)
        locator: Locator = page.locator(selector=selector)
        if kind is AssertionKind.DOM_COUNT:
            return (str(object=locator.count()), True)
        if kind is AssertionKind.DOM_VISIBLE:
            return (None, locator.is_visible())
        if kind is AssertionKind.DOM_HIDDEN:
            return (None, locator.is_hidden())
        if kind is AssertionKind.DOM_TEXT:
            return (
                locator.inner_text(timeout=100) if locator.count() else None,
                locator.count() > 0,
            )
        if kind is AssertionKind.DOM_ATTRIBUTE:
            value: str | None = (
                locator.get_attribute(name=spec.attribute or "", timeout=100)
                if locator.count()
                else None
            )
            return (value, value is not None)
        msg: str = f"Unsupported assertion kind: {kind}"
        raise ValueError(msg)

    def _assertion_css(self, *, spec: AssertionSpec) -> str:
        """Resolve the exact CSS used by one DOM assertion.

        Args:
            spec: Assertion naming a selector reference or an expression.

        Returns:
            CSS the assertion evaluates.

        Raises:
            ValueError: When the selector is unknown or does not resolve.

        """
        selector: str = spec.target
        if spec.selector_id:
            stored: SelectorDef | None = next(
                (
                    item
                    for item in self._selectors
                    if item.selector_id == spec.selector_id
                ),
                None,
            )
            if stored is None:
                msg: str = f"Unknown assertion selector: {spec.selector_id}"
                raise ValueError(msg)
            if self._resolver is None:
                msg = "Selector resolver is not ready."
                raise ValueError(msg)
            resolution: Resolution = self._resolver.resolve_selector(
                selector=stored,
            )
            if resolution.error is not None:
                raise ValueError(resolution.error)
            if not resolution.ok:
                msg = (
                    f"Selector {stored.name} matched {
                        resolution.count
                    }; its saved count or checks did not "
                    f"pass."
                )
                raise ValueError(msg)
            selector = resolution.matches[0].css or ""
            if not selector:
                msg = f"Selector {stored.name} could not produce exact CSS."
                raise ValueError(msg)
        return selector

    def _assert(self, *, page: Page, spec: AssertionSpec) -> Event:
        """Assert for recorded flow execution.

        Args:
            page: Page for this operation.
            spec: Spec for this operation.

        Returns:
            The verified result of this operation.

        Raises:
            ValueError: When the arguments are invalid.

        """
        deadline: float = monotonic() + spec.timeout_ms / 1000
        while True:
            if self.cancelled():
                msg: str = "Run cancelled."
                raise ValueError(msg)
            try:
                actual, exists = self._actual(page=page, spec=spec)
                result: AssertionResult = AssertionEvaluator.evaluate(
                    assertion=spec,
                    actual=actual,
                    exists=exists,
                )
            except PlaywrightError:
                result = AssertionEvaluator.evaluate(
                    assertion=spec,
                    actual=None,
                    exists=False,
                )
            if (
                result.outcome is AssertionOutcome.SUCCEEDED
                or monotonic() >= deadline
            ):
                return {
                    "assertion_id": result.assertion_id,
                    "outcome": result.outcome.value,
                    "details": result.details,
                    "actual": result.actual,
                }
            page.wait_for_timeout(timeout=50)

    def _perform(
        self,
        *,
        page: Page,
        event: TimelineEvent,
        unit: Unit,
        raw: Event,
    ) -> JsonValue:
        """Perform for recorded flow execution.

        Args:
            page: Page for this operation.
            event: Event for this operation.
            unit: Target the action runs on.
            raw: Raw for this operation.

        Returns:
            The serializable action response when available.

        Raises:
            ValueError: When input or state does not satisfy the contract.

        """
        handled, value = self._perform_special(
            page=page,
            event=event,
            unit=unit,
        )
        if handled:
            return value
        action: Action | None = event_action(event=raw)
        if action is None:
            if event.kind not in {
                EventKind.NOTE,
                EventKind.REQUEST,
                EventKind.RESPONSE,
                EventKind.CONSOLE,
                EventKind.WEBSOCKET_OPEN,
                EventKind.WEBSOCKET_SENT,
                EventKind.WEBSOCKET_RECEIVED,
                EventKind.WEBSOCKET_CLOSE,
                EventKind.WEBSOCKET_ERROR,
            }:
                msg: str = f"Unsupported executable step: {event.kind}"
                raise ValueError(msg)
            return None
        responses: list[Response] = []

        def observe_response(response: Response) -> None:
            """Collect responses during the replayed action.

            Args:
                response: Response for this operation.

            """
            responses.append(response)

        page.on(event="response", f=observe_response)
        try:
            if action.get("type") == "navigation":
                page.goto(
                    url=rebase_url(
                        url=str(object=action["url"]),
                        origin=self._origin,
                    ),
                )
            else:
                ActionReplayer(
                    url=page.url,
                    actions=(),
                    options=ReplayOptions(timeout_ms=self.timeout_ms),
                ).perform(page=page, action=action)
            for expectation in event.expectations:
                self._network_check(
                    page=page,
                    event=event,
                    expectation=expectation,
                    responses=responses,
                )
        finally:
            page.remove_listener(event="response", f=observe_response)

    def _perform_special(
        self,
        *,
        page: Page,
        event: TimelineEvent,
        unit: Unit,
    ) -> tuple[bool, JsonValue]:
        """Run actions that do not use the recorder replay adapter.

        Args:
            page: Page the action runs against.
            event: Action to perform.
            unit: Target unit supplying the resolved element.

        Returns:
            Whether the action was handled, and its result value.

        """
        value: JsonValue
        if event.kind is EventKind.JAVASCRIPT:
            value = self._perform_javascript(page=page, event=event, unit=unit)
        elif event.kind is EventKind.SNAPSHOT:
            value = self._perform_snapshot(page=page, event=event, unit=unit)
        elif event.kind in {EventKind.HTTP_CALL, EventKind.WEBSOCKET_CALL}:
            value = self._perform_request(page=page, event=event)
        elif event.kind is EventKind.EXTRACT_VALUE:
            value = self._perform_extract(page=page, event=event)
        elif event.kind is EventKind.SET_VARIABLE:
            value = self._perform_set_variable(event=event)
        elif event.kind is EventKind.VIEWPORT:
            self._perform_viewport(page=page, event=event)
            return (True, None)
        elif event.kind is EventKind.GESTURE:
            self._perform_gesture(page=page, event=event)
            return (True, None)
        elif event.kind is EventKind.WAIT:
            self._perform_wait(page=page, event=event)
            return (True, None)
        else:
            return (False, None)
        if event.output_variable is not None:
            self._streams.vars[event.output_variable] = value
        return (True, value)

    def _perform_request(
        self,
        *,
        page: Page,
        event: TimelineEvent,
    ) -> JsonValue:
        """Execute one REST request or bounded WebSocket session.

        Args:
            page: Project browser page supplying the runtime context.
            event: Authored network action.

        Returns:
            Serializable response or session result.

        """
        if event.kind is EventKind.HTTP_CALL:
            return self._perform_http(page=page, event=event)
        return self._perform_websocket(page=page, event=event)

    def _hold_for_gate(self, *, event: TimelineEvent) -> None:
        """Wait while the run is paused, telling the service what comes next.

        Args:
            event: The action about to run.

        """
        if self.gate is None:
            return
        self.gate.wait_turn(
            cancelled=self.cancelled,
            on_hold=lambda: self._announce_gate(state="paused", event=event),
            on_release=lambda: self._announce_gate(
                state="running",
                event=event,
            ),
        )

    def _announce_gate(self, *, state: str, event: TimelineEvent) -> None:
        """Tell the service whether the run is held before an action.

        Args:
            state: ``paused`` or ``running``.
            event: The action the run is held before, or about to run.

        """
        self.emit(
            {
                "type": "run_gate",
                "run_id": self._run_id,
                "state": state,
                "event_id": event.event_id,
            },
        )

    def _perform_extract(
        self,
        *,
        page: Page,
        event: TimelineEvent,
    ) -> JsonValue:
        """Read one typed value from the resolved action target.

        Args:
            page: Page holding the target element.
            event: Extraction action naming the value to read.

        Returns:
            The extracted value.

        """
        config: dict[str, JsonValue] = self._request_config(event=event)
        locator: Locator = page.locator(
            selector=event.selector or "body",
        ).first
        extraction: str = str(object=config.get("extract") or "text")
        if extraction == "count":
            result: JsonValue = page.locator(
                selector=event.selector or "body",
            ).count()
        elif extraction == "checked":
            result = locator.is_checked()
        elif extraction == "attribute":
            result = locator.get_attribute(
                name=str(object=config.get("attribute") or ""),
            )
        elif extraction in {"float", "int", "value"}:
            value: str = locator.input_value()
            if extraction == "float":
                result = float(value)
            elif extraction == "int":
                result = int(value)
            else:
                result = value
        else:
            result = locator.inner_text()
        return result

    def _perform_set_variable(self, *, event: TimelineEvent) -> JsonValue:
        """Create a typed run variable from an authored value.

        Args:
            event: Action carrying the value, its type and its name.

        Returns:
            The converted value.

        """
        config: dict[str, JsonValue] = self._request_config(event=event)
        value: str = (
            self._template(value=str(object=config.get("value") or "")) or ""
        )
        value_type: str = str(object=config.get("value_type") or "text")
        if value_type == "boolean":
            return value.lower() in {"1", "true", "yes"}
        if value_type == "float":
            return float(value)
        if value_type == "integer":
            return int(value)
        if value_type == "json":
            return cast(typ="JsonValue", val=loads(s=value))
        return value

    def _perform_javascript(
        self,
        *,
        page: Page,
        event: TimelineEvent,
        unit: Unit,
    ) -> JsonValue:
        """Evaluate a recorded JavaScript step.

        Args:
            page: Page for this operation.
            event: Event for this operation.
            unit: Target the action runs on.

        Returns:
            The serializable action response when available.

        Raises:
            ValueError: When the step has no payload, or the sandboxed script
                throws.

        """
        if not event.payload:
            msg: str = "JavaScript actions require a function or expression."
            raise ValueError(msg)
        if event.sandbox:
            result: SandboxResult = (
                self._batch.pop((event.event_id, unit.index), None)
                or run_sandbox(
                    page=page,
                    call=self._sandbox_call(
                        event=event,
                        script=event.payload,
                        targets=unit.targets,
                        indices=(unit.position,),
                        count=unit.count,
                    ),
                    streams=self._streams,
                    selectors=self._selectors,
                )[0]
            )
            merge(
                streams=self._streams,
                result=result,
                flow_id=event.flow_id,
                action_id=event.event_id,
                unit=unit.index,
            )
            if result.error is not None:
                raise ValueError(result.error)
            return result.value
        return cast(
            typ="JsonValue",
            val=loads(
                s=dumps(
                    obj=page.evaluate(expression=event.payload),
                    allow_nan=False,
                ),
            ),
        )

    def _sandbox_call(
        self,
        *,
        event: TimelineEvent,
        script: str,
        targets: tuple[str, ...] = (),
        indices: tuple[int, ...] = (0,),
        count: int | None = None,
    ) -> SandboxCall:
        """Freeze the safe project and invocation facts for one snippet.

        Args:
            event: Timeline event whose flow and action identity apply.
            script: Snippet source evaluated in the page sandbox.
            targets: Selector targets passed to the snippet.
            indices: Match indices applied to each target.
            count: Optional expected match count.

        Returns:
            Immutable sandbox invocation payload.

        """
        return SandboxCall(
            script=script,
            flow_id=event.flow_id,
            action_id=event.event_id,
            run_id=self._run_id,
            targets=targets,
            indices=indices,
            count=count,
            flow_name=self._flow_name,
            action_kind=event.kind.value,
            action_label=event.label,
            project_id=str(object=self._project.get("id") or ""),
            project_name=str(object=self._project.get("name") or ""),
            project_revision=str(object=self._project.get("revision") or ""),
            context_id=str(
                object=self._context.get("id") or self._device_mode,
            ),
            context_name=str(
                object=self._context.get("name") or self._device_mode,
            ),
            context_base_url=str(
                object=self._context.get("base_url")
                or self._context.get("baseUrl")
                or "",
            ),
            context_origin=str(object=self._context.get("origin") or ""),
        )

    def _perform_http(self, *, page: Page, event: TimelineEvent) -> JsonValue:
        """Replay a recorded HTTP call with or without session cookies.

        Args:
            page: Page for this operation.
            event: Event for this operation.

        Returns:
            The response description, including status, headers and body.

        Raises:
            ValueError: When no browser context is available.

        """
        if event.share_session_cookies:
            return self._http(
                page=page,
                request=page.context.request,
                event=event,
            )
        browser: Browser | None = page.context.browser
        if browser is None:
            msg: str = "HTTP action needs a browser context."
            raise ValueError(msg)
        context: BrowserContext = browser.new_context()
        try:
            return self._http(page=page, request=context.request, event=event)
        finally:
            context.close()

    def _perform_wait(self, *, page: Page, event: TimelineEvent) -> None:
        """Wait for a browser condition, retaining legacy delay support.

        Args:
            page: Page for this operation.
            event: Event for this operation.

        Raises:
            TypeError: When the specification is not a JSON object.
            ValueError: When the specification is invalid or the run is
                cancelled mid-wait.

        """
        raw: str = event.payload or "0"
        if raw.isdigit():
            self._perform_legacy_delay(page=page, milliseconds=int(raw))
            return
        try:
            request: JsonValue = cast(typ="JsonValue", val=loads(s=raw))
        except ValueError as error:
            msg: str = "Wait action has an invalid condition."
            raise ValueError(msg) from error
        if not isinstance(request, dict):
            msg = "Wait action has an invalid condition."
            raise TypeError(msg)
        condition: str = str(object=request.get("condition") or "")
        value: str = (
            self._template(value=str(object=request.get("value") or "")) or ""
        )
        timeout_ms: int = int(
            str(object=request.get("timeout_ms") or self.timeout_ms),
        )
        if condition == "element":
            page.locator(selector=value).wait_for(
                state="visible",
                timeout=timeout_ms,
            )
        elif condition == "text":
            page.get_by_text(text=value).first.wait_for(
                state="visible",
                timeout=timeout_ms,
            )
        elif condition == "url":
            page.wait_for_url(url=value, timeout=timeout_ms)
        elif condition == "expression":
            page.wait_for_function(expression=value, timeout=timeout_ms)
        else:
            msg = f"Unsupported wait condition: {condition}"
            raise ValueError(msg)

    def _perform_legacy_delay(self, *, page: Page, milliseconds: int) -> None:
        """Replay an older fixed-delay event without blocking cancellation.

        Args:
            page: Page whose clock advances.
            milliseconds: Recorded delay.

        Raises:
            ValueError: When the run is cancelled.

        """
        deadline: float = monotonic() + milliseconds / 1000
        while monotonic() < deadline:
            if self.cancelled():
                msg: str = "Run cancelled."
                raise ValueError(msg)
            page.wait_for_timeout(
                timeout=min(50, max(0, (deadline - monotonic()) * 1000)),
            )

    def _network_check(
        self,
        *,
        page: Page,
        event: TimelineEvent,
        expectation: NetworkExpectation,
        responses: list[Response],
    ) -> None:
        """Network check for recorded flow execution.

        Args:
            page: Page for this operation.
            event: Event for this operation.
            expectation: Expectation for this operation.
            responses: Responses for this operation.

        Raises:
            ValueError: When input or state does not satisfy the contract.

        """
        deadline: float = monotonic() + expectation.timeout_ms / 1000
        matched: bool = False
        details: str = "No matching response before timeout."
        while not matched:
            if self.cancelled():
                msg = "Run cancelled."
                raise ValueError(msg)
            for response in responses:
                observed: TimelineEvent = TimelineEvent(
                    event_id=uuid4().hex,
                    flow_id=event.flow_id,
                    sequence=0,
                    elapsed_ms=0,
                    layer=TimelineLayer.NETWORK,
                    kind=EventKind.RESPONSE,
                    label="Observed response",
                    url=response.url,
                    method=response.request.method,
                    status=response.status,
                    payload=None,
                    headers=tuple(
                        (
                            HttpHeader(name=name, value=value)
                            for name, value in response.headers.items()
                        ),
                    ),
                )
                identity: NetworkExpectation = replace(
                    expectation,
                    expected_status=None,
                    expected_headers=(),
                    body_match=BodyMatchMode.NONE,
                    expected_body=None,
                    json_conditions=(),
                )
                relevant, _ = NetworkExpectationEvaluator.evaluate(
                    expectation=identity,
                    response=observed,
                )
                if not relevant:
                    continue
                observed = replace(observed, payload=response.text())
                matched, details = NetworkExpectationEvaluator.evaluate(
                    expectation=expectation,
                    response=observed,
                )
                if matched:
                    break
            if matched or monotonic() >= deadline:
                break
            page.wait_for_timeout(timeout=50)
        self.emit(
            {
                "type": "expectation_result",
                "result_id": uuid4().hex,
                "flow_id": event.flow_id,
                "event_id": event.event_id,
                "expectation_id": expectation.expectation_id,
                "outcome": "pass" if matched else "timeout",
                "details": details,
            },
        )
        if not matched:
            msg: str = f"{expectation.label}: {details}"
            raise ValueError(msg)

    def _http(
        self,
        *,
        page: Page,
        request: APIRequestContext,
        event: TimelineEvent,
    ) -> JsonValue:
        """Send one request and validate its response.

        Args:
            page: Page whose live DOM supplies selector bindings.
            request: Request context that sends the call.
            event: Event for this operation.

        Returns:
            The response description, including status, headers and body.

        Raises:
            ValueError: When input or state does not satisfy the contract.

        """
        config: dict[str, JsonValue] = self._request_config(event=event)
        self._request_bindings(page=page, config=config)
        headers: dict[str, str] = self._request_headers(config=config)
        body: str = (
            self._template(value=str(object=config.get("body") or "")) or ""
        )
        cookies: str | None = cookie_header(rows=config.get("cookies"))
        if cookies:
            authored: str = headers.get("Cookie", "")
            headers["Cookie"] = (
                f"{authored}; {cookies}" if authored else cookies
            )
        sent: HttpResult = send_request(
            context=request,
            request=PreparedRequest(
                method=event.method or "GET",
                url=self._request_url(event=event, config=config),
                headers=headers,
                body=body,
                timeout_ms=float(
                    str(object=config.get("timeout_ms") or self.timeout_ms),
                ),
            ),
        )
        observation: TimelineEvent = TimelineEvent(
            event_id=uuid4().hex,
            flow_id=event.flow_id,
            sequence=0,
            elapsed_ms=0,
            layer=TimelineLayer.NETWORK,
            kind=EventKind.RESPONSE,
            label="HTTP response",
            url=sent["url"],
            method=event.method,
            status=sent["status"],
            payload=sent["body"],
            headers=tuple(
                (
                    HttpHeader(name=name, value=value)
                    for name, value in sent["headers"].items()
                ),
            ),
        )
        for expectation in event.expectations:
            matched, details = NetworkExpectationEvaluator.evaluate(
                expectation=expectation,
                response=observation,
            )
            if not matched:
                msg: str = f"{expectation.label}: {details}"
                raise ValueError(msg)
        self._request_validations(config=config, response=observation)
        result: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=sent,
        )
        self._publish_response_captures(config=config, response=result)
        return result

    def _perform_websocket(
        self,
        *,
        page: Page,
        event: TimelineEvent,
    ) -> JsonValue:
        """Run one bounded WebSocket session in the project browser context.

        Args:
            page: Browser page whose origin, cookies and network apply.
            event: Authored WebSocket action.

        Returns:
            Negotiated protocol, received frames and close details.

        Raises:
            TypeError: The page did not return a session result object.

        """
        config: dict[str, JsonValue] = self._request_config(event=event)
        protocols_value: JsonValue = config.get("protocols")
        protocols: list[str] = (
            [str(object=item) for item in protocols_value]
            if isinstance(protocols_value, list)
            else []
        )
        timeout_ms: int = int(
            str(object=config.get("timeout_ms") or self.timeout_ms),
        )
        receive_count: int = int(str(object=config.get("receive_count") or 0))
        argument: dict[str, JsonValue] = {
            "url": self._template(value=event.url) or "",
            "protocols": cast(typ="JsonValue", val=protocols),
            "message": self._template(
                value=str(object=config.get("message") or ""),
            )
            or "",
            "receiveCount": receive_count,
            "timeoutMs": timeout_ms,
        }
        raw: JsonValue = cast(
            typ="JsonValue",
            val=page.evaluate(
                expression=(
                    dedent(
                        text=(
                            "    async ({\n      url, protocols, message, "
                            "receiveCount, timeoutMs\n    }) => await new "
                            "Promise((resolve, reject) => {\n      const s"
                            "ocket = protocols.length > 0\n        ? new W"
                            "ebSocket(url, protocols)\n        : new WebSo"
                            "cket(url);\n      const messages = [];\n     "
                            " const timer = setTimeout(() => {\n        so"
                            'cket.close(1000, "Exactus timeout");\n       '
                            " reject(new Error(`WebSocket session timed ou"
                            "t after ${timeoutMs} ms`));\n      }, timeout"
                            'Ms);\n      socket.addEventListener("open", ('
                            ") => {\n        if (message) socket.send(mess"
                            "age);\n        if (receiveCount === 0) socket"
                            '.close(1000, "Exactus completed");\n      });'
                            '\n      socket.addEventListener("message", ev'
                            "ent => {\n        messages.push(\n          t"
                            'ypeof event.data === "string" ? event.data : '
                            "`[Binary frame]`\n        );\n        if (mes"
                            "sages.length >= receiveCount) {\n          so"
                            'cket.close(1000, "Exactus completed");\n     '
                            "   }\n      });\n      socket.addEventListene"
                            'r("error", () => {\n        clearTimeout(time'
                            'r);\n        reject(new Error("WebSocket conn'
                            'ection failed"));\n      });\n      socket.ad'
                            'dEventListener("close", event => {\n        c'
                            "learTimeout(timer);\n        resolve({\n     "
                            "     url,\n          protocol: socket.protoco"
                            "l,\n          messages,\n          last_messa"
                            "ge: messages.at(-1) ?? null,\n          close"
                            "_code: event.code,\n          close_reason: e"
                            "vent.reason\n        });\n      });\n    })"
                        ),
                    )
                ),
                arg=argument,
            ),
        )
        if not isinstance(raw, dict):
            msg: str = "WebSocket session returned an invalid result."
            raise TypeError(msg)
        self._publish_response_captures(config=config, response=raw)
        return raw

    def _request_url(
        self,
        *,
        event: TimelineEvent,
        config: dict[str, JsonValue],
    ) -> str:
        """Resolve an HTTP URL and append enabled parameter rows.

        Args:
            event: REST action owning the URL.
            config: Portable request configuration.

        Returns:
            Absolute URL with expanded query parameters.

        """
        base: str = rebase_url(
            url=self._template(value=event.url) or "",
            origin=self._origin,
        )
        query_value: JsonValue = config.get("query")
        if not isinstance(query_value, list):
            return base
        parts: SplitResult = urlsplit(url=base)
        query: list[tuple[str, str]] = list(parse_qsl(qs=parts.query))
        for item in query_value:
            if not isinstance(item, dict) or item.get("enabled") is False:
                continue
            name: str = (
                self._template(value=str(object=item.get("key") or "")) or ""
            )
            if not name:
                continue
            value: str = (
                self._template(value=str(object=item.get("value") or "")) or ""
            )
            query.append((name, value))
        return urlunsplit(
            components=(
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query=query),
                parts.fragment,
            ),
        )

    def _publish_response_captures(
        self,
        *,
        config: dict[str, JsonValue],
        response: dict[str, JsonValue],
    ) -> None:
        """Publish configured response values into the run variable stream.

        Args:
            config: Portable request configuration.
            response: REST response or WebSocket session result.

        Raises:
            ValueError: When a required path is absent or conversion fails.

        """
        captures: JsonValue = config.get("captures")
        if not isinstance(captures, list):
            return
        for item in captures:
            if not isinstance(item, dict):
                continue
            name: str = str(object=item.get("name") or "").strip()
            if not name:
                continue
            source: str = str(object=item.get("source") or "json")
            path: str = str(object=item.get("path") or "").strip()
            body: JsonValue = response.get("body")
            selected: JsonValue
            if item.get("mode") == "fixed":
                selected = item.get("value")
            elif source == "xml":
                selected = (
                    read_xml_path(text=body, path=path)
                    if isinstance(body, str)
                    else None
                )
            else:
                selected = read_json_path(
                    value=self._response_capture_source(
                        response=response,
                        source=source,
                    ),
                    path=path,
                )
            if selected is None and item.get("required") is not False:
                msg: str = (
                    f"Response variable {name!r} could not read "
                    f"{source}{f'.{path}' if path else ''}."
                )
                raise ValueError(msg)
            if selected is None:
                self._streams.vars[name] = None
                continue
            self._streams.vars[name] = self._coerce_response_capture(
                name=name,
                value=selected,
                value_type=str(object=item.get("value_type") or "string"),
            )

    def _request_bindings(
        self,
        *,
        page: Page,
        config: dict[str, JsonValue],
    ) -> None:
        """Extract typed DOM values into the chain variable map.

        Args:
            page: Page containing source elements.
            config: REST-client specification.

        """
        bindings: JsonValue = config.get("bindings")
        if not isinstance(bindings, list):
            return
        for value in bindings:
            if not isinstance(value, dict):
                continue
            name: str = str(object=value.get("name") or "").strip()
            selector: str = (
                self._template(value=str(object=value.get("selector") or ""))
                or ""
            )
            if not name or not selector:
                continue
            locator: Locator = page.locator(
                selector=self._binding_css(selector=selector),
            ).first
            extraction: str = str(object=value.get("extract") or "text")
            if extraction == "checked":
                extracted: JsonValue = locator.is_checked()
            elif extraction in {"int", "float", "value"}:
                text: str = locator.input_value()
                extracted = (
                    int(text)
                    if extraction == "int"
                    else float(text)
                    if extraction == "float"
                    else text
                )
            elif extraction == "attribute":
                extracted = locator.get_attribute(
                    name=str(object=value.get("attribute") or ""),
                )
            else:
                extracted = locator.inner_text()
            self._streams.vars[name] = extracted

    def _binding_css(self, *, selector: str) -> str:
        """Compile an extended selector binding to exact CSS.

        Args:
            selector: Plain CSS or an ``ext=`` extended selector.

        Returns:
            CSS the binding evaluates.

        Raises:
            ValueError: When the extended selector cannot be resolved.

        """
        if not selector.startswith("ext="):
            return selector
        if self._resolver is None:
            msg: str = "Selector resolver is not ready."
            raise ValueError(msg)
        resolution: Resolution = self._resolver.resolve(
            expression=selector.removeprefix("ext="),
            expected_count=None,
        )
        if not resolution.ok:
            cause: dict[str, JsonValue] = resolution.cause()
            raise ValueError(str(object=cause.get("message") or cause))
        css: str | None = resolution.matches[0].css
        if not css:
            msg = "Extended selector binding did not produce exact CSS."
            raise ValueError(msg)
        return css

    def _request_headers(
        self,
        *,
        config: dict[str, JsonValue],
    ) -> dict[str, str]:
        """Parse and expand one ``Name: value`` header per line.

        Args:
            config: REST-client specification.

        Returns:
            Expanded request headers.

        """
        result: dict[str, str] = {}
        headers: JsonValue = config.get("headers")
        if isinstance(headers, list):
            for item in headers:
                if not isinstance(item, dict) or item.get("enabled") is False:
                    continue
                name: str = (
                    self._template(value=str(object=item.get("key") or ""))
                    or ""
                )
                if name:
                    result[name] = (
                        self._template(
                            value=str(object=item.get("value") or ""),
                        )
                        or ""
                    )
            return result
        for line in str(object=headers or "").splitlines():
            name, separator, value = line.partition(":")
            if separator and name.strip():
                result[name.strip()] = (
                    self._template(value=value.strip()) or ""
                )
        return result

    def _checks(
        self,
        *,
        page: Page,
        specs: tuple[AssertionSpec, ...],
        checks: list[Event],
    ) -> None:
        """Check the recorded flow contracts.

        Args:
            page: Page for this operation.
            specs: Specs for this operation.
            checks: Checks for this operation.

        Raises:
            ValueError: When input or state does not satisfy the contract.

        """
        for spec in specs:
            checks.append(self._assert(page=page, spec=spec))
            if checks[-1]["outcome"] != "pass":
                msg: str = str(object=checks[-1]["details"])
                raise ValueError(msg)

    def _attempt(
        self,
        *,
        page: Page,
        event: TimelineEvent,
        unit: Unit,
        options: Event,
    ) -> Event:
        """Attempt for recorded flow execution.

        Args:
            page: Page for this operation.
            event: Event for this operation.
            unit: Target the attempt runs on.
            options: Options for this operation.

        Returns:
            The verified result of this operation.

        """
        origin: float = cast(typ="float", val=options["origin"])
        started: int = int((monotonic() - origin) * 1000)
        checks: list[Event] = []
        artifacts: list[str] = []
        response: JsonValue = None
        error: str | None = None
        cause: dict[str, JsonValue] | None = None
        mark: int = len(self._streams.entries)
        status: str = "skipped" if options["stop"] else "succeeded"
        stage: str = "execute"
        if not options["stop"] and unit.cause is not None:
            status, cause = ("failed", unit.cause)
            error = str(object=unit.cause.get("message"))
        elif not options["stop"]:
            try:
                stage = "check"
                self._checks(
                    page=page,
                    specs=event.contract.preconditions,
                    checks=checks,
                )
                stage = "execute"
                response = self._perform(
                    page=page,
                    event=event,
                    unit=unit,
                    raw=cast(
                        typ="Event",
                        val=WorkspaceCodec.event_to_json_value(event=event),
                    ),
                )
                stage = "check"
                self._checks(
                    page=page,
                    specs=event.contract.postconditions,
                    checks=checks,
                )
            except (PlaywrightError, TypeError, ValueError) as failure:
                status, error = (
                    "skipped" if self.cancelled() else "failed",
                    str(object=failure),
                )
                cause = failure_cause(failure=failure, unit=unit, stage=stage)
            if options["capture"] or event.payload == "__screenshot__":
                try:
                    artifact: Event = capture_evidence(
                        page=page,
                        output=self.output,
                        request=EvidenceRequest(
                            flow_id=event.flow_id,
                            event_id=event.event_id,
                            phase="play",
                            after_capture=self.after_capture,
                        ),
                    )
                    self.emit(artifact)
                    artifacts.append(str(object=artifact["artifact_id"]))
                except (PlaywrightError, OSError) as failure:
                    status, error = (
                        "failed",
                        f"{error or ''} Screenshot: {failure}",
                    )
        drift: JsonValue = (
            cast(typ="dict[str, JsonValue]", val=response).get("drift")
            if event.kind is EventKind.SNAPSHOT and isinstance(response, dict)
            else None
        )
        if status == "succeeded" and drift:
            status = "warning"
            cause = {
                "phase": "drift",
                "message": "The element no longer resembles its baseline.",
                "changes": drift,
                "resolved_css": event.selector,
                "target_index": unit.index,
                "selector_id": unit.selector_id,
            }
            error = str(object=cause["message"])
        if (
            status == "failed"
            and options["final"]
            and event.contract.continue_on_failure
        ):
            status = "warning"
        if cause is not None and status in {"failed", "warning"}:
            _ = self._streams.add(
                entry=StreamEntry(
                    level="warn" if cause.get("phase") == "drift" else "error",
                    source="tool",
                    message=error or "",
                    flow_id=event.flow_id,
                    action_id=event.event_id,
                    unit=unit.index,
                    cause=cause,
                    at=int(time() * 1000),
                ),
            )
        return {
            "event_id": event.event_id,
            "flow_id": event.flow_id,
            "status": status,
            "attempt": options["attempt"],
            "started_ms": started,
            "finished_ms": int((monotonic() - origin) * 1000),
            "assertions": cast(typ="JsonValue", val=checks),
            "observed_event_ids": [],
            "screenshot_artifact_ids": cast(typ="JsonValue", val=artifacts),
            "outputs": [],
            "response": response,
            "kind": event.kind.value,
            "label": event.label,
            "script": event.payload
            if event.kind is EventKind.JAVASCRIPT
            else None,
            "error": error,
            "cause": cast(typ="JsonValue", val=cause),
            "streams": cast(typ="JsonValue", val=self._streams.entries[mark:]),
            "unit": None
            if unit.index is None
            else {"index": unit.index, "count": unit.count},
        }

    def _sleep(self, *, page: Page, milliseconds: int) -> None:
        """Wait, yielding to cancellation every 50 ms.

        Args:
            page: Managed browser page.
            milliseconds: Time to wait.

        """
        deadline: float = monotonic() + milliseconds / 1000
        while monotonic() < deadline and (not self.cancelled()):
            page.wait_for_timeout(
                timeout=min(50, max(1, (deadline - monotonic()) * 1000)),
            )

    def _condition_holds(self, *, expression: str) -> bool:
        """Evaluate a condition against the run's variables and probes.

        Args:
            expression: Condition in the connection-condition language.

        Returns:
            Whether the condition is true right now.

        Raises:
            ValueError: When the page cannot be probed.

        """
        if self._resolver is None:
            msg: str = "Conditions need a running page."
            raise ValueError(msg)
        refs: tuple[ProbeRef, ...] = probe_refs(conditions=(expression,))
        probes: tuple[RuntimeVariable, ...] = probe_variables(
            resolver=self._resolver,
            selectors=self._selectors,
            refs=refs,
        )
        return ExpressionEvaluator.evaluate(
            expression=expression,
            variables=(*self._variables, *probes),
        )

    def _pace(self, *, page: Page, pace: Pace) -> dict[str, JsonValue] | None:
        """Wait out a pace: its delay, then its condition.

        Args:
            page: Managed browser page.
            pace: Pause to apply.

        Returns:
            ``None`` when the wait finished, else the cause of the failure.

        """
        self._sleep(page=page, milliseconds=pace.delay_ms)
        if pace.until is None:
            return None
        limit: float = monotonic() + pace.timeout_ms / 1000
        while True:
            try:
                holds: bool = self._condition_holds(expression=pace.until)
            except (ExpressionError, ValueError) as error:
                return self._gate_cause(pace=pace, message=str(object=error))
            if holds or self.cancelled():
                return None
            if monotonic() >= limit:
                return self._gate_cause(
                    pace=pace,
                    message=(
                        f"Timed out after "
                        f"{pace.timeout_ms} ms waiting for: {pace.until}"
                    ),
                )
            page.wait_for_timeout(timeout=pace.poll_ms)

    def _gate(
        self,
        *,
        page: Page,
        event: TimelineEvent,
        pace: Pace,
        progress: _Progress,
        unit: Unit | None,
    ) -> None:
        """Apply a pace; record a failure when its condition is not met.

        Args:
            page: Managed browser page.
            event: The action the pace belongs to.
            pace: Pause to apply.
            progress: State of the run, updated in place.
            unit: The target just finished, for pauses between targets.

        """
        cause: dict[str, JsonValue] | None = self._pace(page=page, pace=pace)
        if cause is None:
            return
        tolerated: bool = event.contract.continue_on_failure
        message: str = str(object=cause["message"])
        index: int | None = None if unit is None else unit.index
        stamp: int = int((monotonic() - progress.origin) * 1000)
        entry: dict[str, JsonValue] = self._streams.add(
            entry=StreamEntry(
                level="error",
                source="tool",
                message=message,
                flow_id=event.flow_id,
                action_id=event.event_id,
                unit=index,
                cause=cause,
                at=int(time() * 1000),
            ),
        )
        record: Event = {
            "event_id": event.event_id,
            "flow_id": event.flow_id,
            "status": "warning" if tolerated else "failed",
            "attempt": 1,
            "started_ms": stamp,
            "finished_ms": stamp,
            "assertions": [],
            "observed_event_ids": [],
            "screenshot_artifact_ids": [],
            "outputs": [],
            "response": None,
            "kind": event.kind.value,
            "label": f"{event.label} (wait)",
            "script": None,
            "error": message,
            "cause": cause,
            "streams": [entry],
            "unit": None
            if unit is None or unit.index is None
            else {"index": unit.index, "count": unit.count},
        }
        progress.records.append(record)
        self.emit(
            {
                "type": "action_result",
                "run_id": progress.run_id,
                "flow_id": progress.flow_id,
                "action_record": record,
            },
        )
        progress.failed = True
        progress.stop = not tolerated

    def _pace_recording(
        self,
        *,
        page: Page,
        event: TimelineEvent,
        origins: dict[str, tuple[float, int]],
    ) -> None:
        """Honor captured cadence, yielding to cancellation every 50 ms.

        Args:
            page: Managed browser page.
            event: Next executable child.
            origins: Playback clock for each recording parent.

        """
        if event.recording_group_id is None:
            return
        origin: tuple[float, int] = origins.setdefault(
            event.recording_group_id,
            (monotonic(), event.elapsed_ms),
        )
        deadline: float = origin[0] + (event.elapsed_ms - origin[1]) / 1000
        while monotonic() < deadline and (not self.cancelled()):
            page.wait_for_timeout(
                timeout=min(50, max(1, (deadline - monotonic()) * 1000)),
            )

    def _execute_event(
        self,
        *,
        page: Page,
        event: TimelineEvent,
        planner: TargetPlanner,
        progress: _Progress,
    ) -> None:
        """Run one action on every target it resolves to.

        Args:
            page: Managed browser page.
            event: Action to run.
            planner: Resolves the action's selector into targets.
            progress: State of the run, updated in place.

        """
        if not progress.stop:
            self._pace_recording(
                page=page,
                event=event,
                origins=progress.recording_origins,
            )
        self.emit(
            {
                "type": "action_started",
                "run_id": progress.run_id,
                "flow_id": progress.flow_id,
                "event_id": event.event_id,
            },
        )
        progress.stop = progress.stop or self.cancelled()
        conditional_skip: bool = (
            not progress.stop
            and event.when_expression is not None
            and (not self._condition(page=page, event=event))
        )
        expanded: TimelineEvent = replace(
            event,
            selector=self._template(value=event.selector),
        )
        units: tuple[Unit, ...] = (
            (Unit(event=expanded),)
            if progress.stop or conditional_skip
            else planner.plan(event=expanded)
        )
        if not conditional_skip:
            self._prefetch_batch(page=page, event=expanded, units=units)
        for position, unit in enumerate(iterable=units):
            self._run_unit(
                page=page,
                event=expanded,
                unit=unit,
                progress=progress,
                conditional_skip=conditional_skip,
            )
            if (
                position < len(units) - 1
                and expanded.pace_between is not None
                and (not progress.stop)
            ):
                self._gate(
                    page=page,
                    event=expanded,
                    pace=expanded.pace_between,
                    progress=progress,
                    unit=unit,
                )
        if expanded.contract.pace is not None and (not progress.stop):
            self._gate(
                page=page,
                event=expanded,
                pace=expanded.contract.pace,
                progress=progress,
                unit=None,
            )

    def _prefetch_batch(
        self,
        *,
        page: Page,
        event: TimelineEvent,
        units: tuple[Unit, ...],
    ) -> None:
        """Run a parallel sandbox action on all its targets at once.

        The snippets run together inside one page evaluation, so they truly
        overlap. Each target's result is kept until its turn to be recorded.

        Args:
            page: Managed browser page.
            event: The action as authored.
            units: Its targets.

        """
        if not (
            event.kind is EventKind.JAVASCRIPT
            and event.sandbox
            and (event.run_mode is RunMode.PARALLEL)
            and (len(units) > 1)
            and event.payload
            and all(unit.cause is None for unit in units)
        ):
            return
        results: tuple[SandboxResult, ...] = run_sandbox(
            page=page,
            call=self._sandbox_call(
                event=event,
                script=event.payload,
                targets=units[0].targets,
                indices=tuple(unit.position for unit in units),
                count=len(units),
            ),
            streams=self._streams,
            selectors=self._selectors,
        )
        for unit, result in zip(units, results, strict=True):
            self._batch[event.event_id, unit.index] = result

    def _run_unit(
        self,
        *,
        page: Page,
        event: TimelineEvent,
        unit: Unit,
        progress: _Progress,
        conditional_skip: bool = False,
    ) -> None:
        """Run one target, retrying it according to the action's contract.

        Args:
            page: Managed browser page.
            event: The action as authored.
            unit: The target to run.
            progress: State of the run, updated in place.
            conditional_skip: Whether an unmet If condition skips the action.

        """
        progress.stop = progress.stop or self.cancelled()
        retries: int = (
            0 if unit.cause is not None else event.contract.retry_count
        )
        for attempt in range(1, retries + 2):
            record: Event = self._attempt(
                page=page,
                event=unit.event,
                unit=unit,
                options={
                    "attempt": attempt,
                    "origin": progress.origin,
                    "stop": progress.stop or conditional_skip,
                    "capture": progress.capture,
                    "final": attempt > retries,
                },
            )
            progress.records.append(record)
            self.emit(
                {
                    "type": "action_result",
                    "run_id": progress.run_id,
                    "flow_id": progress.flow_id,
                    "action_record": record,
                },
            )
            if not self._is_failure(record=record):
                return
            if attempt <= retries:
                page.wait_for_timeout(timeout=event.contract.retry_delay_ms)
            else:
                progress.failed = True
                progress.stop = not event.contract.continue_on_failure

    def _condition(self, *, page: Page, event: TimelineEvent) -> bool:
        """Evaluate an authored chain condition in the action sandbox.

        Args:
            page: Page whose isolated world evaluates the expression.
            event: Guarded action.

        Returns:
            Whether the guarded action should run.

        Raises:
            ValueError: When the condition fails to evaluate.

        """
        results: tuple[SandboxResult, ...] = run_sandbox(
            page=page,
            call=self._sandbox_call(
                event=event,
                script=f"Boolean({event.when_expression})",
            ),
            streams=self._streams,
            selectors=self._selectors,
        )
        result: SandboxResult = results[0]
        if result.error is not None:
            raise ValueError(result.error)
        return result.value is True

    def _template(self, *, value: str | None) -> str | None:
        """Expand ``{{name}}`` placeholders from run variables.

        Args:
            value: Authored text or selector.

        Returns:
            Expanded text, preserving None.

        """
        if value is None:
            return None
        rendered: str = value
        for name, item in self._streams.vars.items():
            rendered = rendered.replace(
                f"{{{{{name}}}}}",
                self._stringify(value=item),
            )
        return Constants.path_token.sub(
            repl=lambda match: self._resolve_path(match=match),
            string=rendered,
        )

    def _resolve_path(self, *, match: Match[str]) -> str:
        """Resolve a variable path, with an optional getter, in run variables.

        ``{{Name.key}}`` and ``{{Name[0]}}`` address a value;
        ``{{Name|keys}}``, ``{{Name|values}}`` and ``{{Name|count}}`` read a
        dictionary or list as a whole.

        Args:
            match: One path token match.

        Returns:
            The addressed value, or the untouched token when unresolved.

        """
        name: str = match.group("name")
        if name not in self._streams.vars:
            return match.group(0)
        current: JsonValue = self._streams.vars[name]
        for key, index in Constants.path_step.findall(
            string=match.group("path"),
        ):
            if key and isinstance(current, dict):
                children: dict[str, JsonValue] = current
                if key not in children:
                    return match.group(0)
                current = children[key]
            elif index and isinstance(current, list):
                items: list[JsonValue] = current
                if int(index) >= len(items):
                    return match.group(0)
                current = items[int(index)]
            else:
                return match.group(0)
        if (getter := match.group("getter")) is None:
            return self._stringify(value=current)
        read: JsonValue | None = self._getter(getter=getter, value=current)
        return match.group(0) if read is None else self._stringify(value=read)

    def _probe_outputs(self, *, message: Event) -> list[JsonValue]:
        """Measure the probes the outgoing connections read.

        The values travel back as flow outputs, so the connection conditions
        see them like any other variable.

        Args:
            message: Run message that may list ``probes`` to measure.

        Returns:
            Runtime variables as JSON; empty when nothing was asked for.

        """
        names: JsonValue = message.get("probes")
        if not isinstance(names, list) or not names or self._resolver is None:
            return []
        try:
            variables: tuple[RuntimeVariable, ...] = probe_variables(
                resolver=self._resolver,
                selectors=self._selectors,
                refs=probe_refs(conditions=(" ".join(map(str, names)),)),
            )
        except ValueError:
            return []
        return [
            WorkspaceCodec.runtime_variable_to_json_value(variable=variable)
            for variable in variables
        ]
