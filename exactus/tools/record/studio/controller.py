# Copyright (c) 2026 Project contributors
"""HTML-first Exactus Record host window."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from json import dumps
from pathlib import Path
from re import Match, Pattern
from re import compile as compile_pattern
from typing import TYPE_CHECKING, Final, Protocol, final
from urllib.parse import SplitResult, urlsplit
from uuid import uuid4

from exactus.packages.server import local, process_control
from exactus.tools.record.discovery import CrawlRequest
from exactus.tools.record.execution import (
    ExecutionDecision,
    ExecutionEngine,
    ExecutionError,
    ExecutionStartRequest,
    ExecutionState,
    FlowDispatchRequest,
)
from exactus.tools.record.live_run import LiveRunAccumulator, RunProgress
from exactus.tools.record.model import (
    AssertionKind,
    AssertionOperator,
    AssertionSpec,
    CheckpointArtifact,
    DeviceMode,
    EventKind,
    ExecutionRun,
    ExpectationResult,
    Flow,
    FlowEdge,
    FlowExecutionResult,
    FlowParameter,
    FlowRecording,
    FlowSettings,
    PositionPointerAction,
    Profile,
    RecorderCommand,
    RunStatus,
    RuntimeVariable,
    ScreenshotArtifact,
    Target,
    TargetMode,
    TimelineEvent,
    TimelineLayer,
    TransitionMode,
    ValueType,
    ViewportSize,
    Workspace,
)
from exactus.tools.record.project_info import ProjectInfo
from exactus.tools.record.recorder_protocol import (
    RecorderInbound,
    RecorderProtocol,
)
from exactus.tools.record.selector_probes import (
    edge_probe_names,
    validate_condition,
)
from exactus.tools.record.store import FlowStore, JsonValue, WorkspaceCodec
from exactus.tools.record.studio.action_commands import (
    ActionFields,
    reconfigured_event,
)
from exactus.tools.record.studio.demo import (
    demo_site,
    demo_target,
    demo_workspace,
)
from exactus.tools.record.studio.persistence import WorkspaceFiles
from exactus.tools.record.studio.project_commands import (
    new_info,
    project_view,
    updated_workspace,
)
from exactus.tools.record.studio.projects import Constants as ProjectConstants
from exactus.tools.record.studio.projects import ProjectError
from exactus.tools.record.studio.selector_commands import (
    delete_selector,
    record_validation,
    save_selector,
    selector_view,
    test_message,
    updated_event,
)

if TYPE_CHECKING:
    from exactus.tools.record.studio.events import EventBus
    from exactus.tools.record.studio.projects import (
        ProjectLibrary,
        ProjectSummary,
    )
    from exactus.tools.record.studio.target_service import TargetService
    from exactus.tools.record.studio.worker import BrowserWorker


@final
class Constants:
    """Group module-level constants.

    Attributes:
        max_wait_ms: Grouped module constant.
        max_timeline_ms: Grouped module constant.
        max_label_length: Grouped module constant.
        max_crawl_depth: Grouped module constant.
        max_crawl_states: Grouped module constant.
        max_scroll_delta: Grouped module constant.
        max_key_length: Grouped module constant.
        max_pointer_button: Grouped module constant.
        max_pointer_buttons: Grouped module constant.
        ask_token: Grouped module constant.

    """

    max_wait_ms: Final[int] = 60000
    max_timeline_ms: Final[int] = 3600000
    max_label_length: Final[int] = 80
    max_crawl_depth: Final[int] = 10
    max_crawl_states: Final[int] = 200
    max_scroll_delta: Final[int] = 2000
    max_key_length: Final[int] = 80
    max_pointer_button: Final[int] = 4
    max_pointer_buttons: Final[int] = 31
    ask_token: Final[Pattern[str]] = compile_pattern(
        pattern="\\{\\{ask:([^{}]+)\\}\\}",
    )


class _MissingSettingError(ValueError):
    """Signal that an action setting is still blank.

    Only this error lets an action be saved as incomplete; every other
    problem, such as an unsupported method, is still refused.
    """


class _EditorCommandHandler(Protocol):
    """Represent _EditorCommandHandler."""

    def __call__(self, data: dict[str, JsonValue]) -> None:
        """Handle call.

        Args:
            data: Data.

        """
        ...


@dataclass(frozen=True, slots=True)
class _EventDetails:
    """Normalized fields for one authored timeline action.

    Attributes:
        label: Human-readable action label.
        payload: Action payload, such as code or a JSON specification.
        selector: Element selector the action targets.
        selector_id: Reusable project selector the action targets.
        url: Address the action navigates to or requests.
        method: HTTP method for request actions.
        position_action: Pointer action for absolute-position steps.
        x: Horizontal viewport coordinate.
        y: Vertical viewport coordinate.

    """

    label: str
    payload: str | None = None
    selector: str | None = None
    selector_id: str | None = None
    url: str | None = None
    method: str | None = None
    position_action: PositionPointerAction | None = None
    x: int | None = None
    y: int | None = None


def _answer(*, match: Match[str], inputs: dict[str, str]) -> str:
    """Return the answer for one ``{{ask:Label}}`` token.

    Args:
        match: Token match whose first group is the label.
        inputs: Answers keyed by token label.

    Returns:
        The answer text.

    Raises:
        ValueError: When the label has no answer.

    """
    label: str = match.group(1)
    if label not in inputs:
        msg: str = f"Provide a value for “{label}”."
        raise ValueError(msg)
    return inputs[label]


def _fill(*, text: str | None, inputs: dict[str, str]) -> str | None:
    """Substitute answers into one action field.

    Args:
        text: Authored field text, or None when the field is unused.
        inputs: Answers keyed by token label.

    Returns:
        The text with every token replaced, preserving None.

    """
    if text is None:
        return None
    return Constants.ask_token.sub(
        repl=lambda match: _answer(match=match, inputs=inputs),
        string=text,
    )


def _with_inputs(*, workspace: Workspace, inputs: dict[str, str]) -> Workspace:
    """Substitute per-run ``{{ask:Label}}`` answers into every action.

    Args:
        workspace: Saved workspace; never mutated.
        inputs: Answers keyed by token label.

    Returns:
        A workspace whose actions carry the answers.

    """
    flows: list[Flow] = [
        replace(
            flow,
            events=tuple(
                replace(
                    event,
                    selector=_fill(text=event.selector, inputs=inputs),
                    url=_fill(text=event.url, inputs=inputs),
                    payload=_fill(text=event.payload, inputs=inputs),
                    label=_fill(text=event.label, inputs=inputs)
                    or event.label,
                    when_expression=_fill(
                        text=event.when_expression,
                        inputs=inputs,
                    ),
                )
                for event in flow.events
            ),
        )
        for flow in workspace.flows
    ]
    return replace(workspace, flows=tuple(flows))


def _flow_parameters(*, value: JsonValue) -> tuple[FlowParameter, ...]:
    """Read the flow inputs an editor form sent.

    Args:
        value: List of ``{name, value_type, required, default_value}``.

    Returns:
        The inputs, in the order the form listed them.

    Raises:
        TypeError: When the list or one of its rows has the wrong shape.

    """
    if not isinstance(value, list):
        msg: str = "Flow inputs must be a list."
        raise TypeError(msg)
    parameters: list[FlowParameter] = []
    for row in value:
        if not isinstance(row, dict):
            msg = "Each flow input must be an object."
            raise TypeError(msg)
        default: JsonValue = row.get("default_value")
        required: bool = row.get("required") is not False
        parameters.append(
            FlowParameter(
                name=str(object=row.get("name", "")).strip(),
                value_type=ValueType(
                    str(object=row.get("value_type", "string")),
                ),
                required=required,
                default_value=None
                if required or default in (None, "")
                else str(object=default),
            ),
        )
    return tuple(parameters)


def _boolean(*, answer: str) -> bool:
    """Read "true" or "false" typed for a yes/no input.

    Args:
        answer: What the person typed.

    Returns:
        The boolean it names.

    Raises:
        ValueError: When it names neither.

    """
    if (lowered := answer.strip().lower()) not in {"true", "false"}:
        raise ValueError(answer)
    return lowered == "true"


def _typed(*, parameter: FlowParameter, answer: str) -> RuntimeVariable:
    """Turn the text typed for a flow input into a typed run variable.

    Args:
        parameter: The input being answered.
        answer: What the person typed.

    Returns:
        The variable the run starts with.

    Raises:
        ValueError: When the answer does not fit the input's type.

    """
    value: str | int | float | bool
    try:
        match parameter.value_type:
            case ValueType.INTEGER:
                value = int(answer)
            case ValueType.FLOAT:
                value = float(answer)
            case ValueType.BOOLEAN:
                value = _boolean(answer=answer)
            case _:
                value = answer
    except ValueError as error:
        msg: str = (
            f"“{parameter.name}” expects a {parameter.value_type.value}."
        )
        raise ValueError(msg) from error
    return RuntimeVariable(
        name=parameter.name,
        value_type=parameter.value_type,
        value=value,
    )


def _supplied(
    *,
    flow: Flow,
    answers: dict[str, str],
) -> tuple[RuntimeVariable, ...]:
    """Build the run variables for a flow's inputs from typed answers.

    Args:
        flow: The flow about to run.
        answers: Typed text keyed by input name.

    Returns:
        A variable for each answered input; unanswered ones keep defaults.

    Raises:
        ValueError: When a required input has no answer.

    """
    supplied: list[RuntimeVariable] = []
    for parameter in flow.parameters:
        if answers.get(parameter.name):
            supplied.append(
                _typed(parameter=parameter, answer=answers[parameter.name]),
            )
        elif parameter.required:
            msg: str = f"Provide a value for “{parameter.name}”."
            raise ValueError(msg)
    return tuple(supplied)


class StudioController:
    """Own one workspace and immutable execution inputs for the service."""

    def __init__(
        self,
        *,
        worker: BrowserWorker,
        events: EventBus,
        persistence: WorkspaceFiles,
        targets: TargetService,
        library: ProjectLibrary,
    ) -> None:
        """Initialize workspace ownership independently of HTTP.

        Args:
            worker: Service-owned target browser boundary.
            events: Bounded ordered event publication.
            persistence: Safe project-local workspace and artifact access.
            targets: Starts and probes the application under test.
            library: The Studio's projects, one folder each.

        """
        initial_flow: Flow = Flow(
            flow_id="flow-1",
            name="Flow A",
            task_description="",
            expected_behavior="",
            notes="",
        )
        self._store = FlowStore(
            workspace=persistence.recover()
            or Workspace(flows=(initial_flow,), edges=()),
        )
        self._active_flow_id = self._store.workspace.flows[0].flow_id
        default: Profile = next(
            (
                item
                for item in self._store.workspace.profiles
                if item.profile_id == DeviceMode.DESKTOP
            ),
            self._store.workspace.profiles[0],
        )
        self._device_mode: str = default.profile_id
        self._viewport: ViewportSize = default.size
        self._shown: Profile | None = None
        self._revision = 1
        self._next_flow_number = 2
        self._clients = 0
        self._dirty = persistence.recovered
        self._recording_state = "idle"
        self._target_state = "closed"
        self._target_url = "about:blank"
        self._target_inspection: JsonValue = None
        self._selector_test: JsonValue = None
        self._crawl_state: dict[str, JsonValue] = {"state": "idle"}
        self._recording_session_id: str | None = None
        self._live_runs = LiveRunAccumulator()
        self._execution_state: ExecutionState | None = None
        self._run_control: str = "running"
        self._run_held_before: str | None = None
        self._execution_workspace: Workspace | None = None
        self._worker = worker
        self._targets = targets
        self._target_check: JsonValue = None
        self._open_after_start: bool = False
        self._bridge = events
        self._persistence = persistence
        self._library = library
        self._project: str = library.slug_of(folder=persistence.root)
        self._demo_pid: int | None = None

    @property
    def persistence(self) -> WorkspaceFiles:
        """Files of the project that is open now.

        Returns:
            The persistence of the active project, which changes when another
            project is opened.

        """
        return self._persistence

    @property
    def project_slug(self) -> str:
        """Identifier of the project that is open now.

        Returns:
            The open project's slug.

        """
        return self._project

    @property
    def library(self) -> ProjectLibrary:
        """The Studio's projects.

        Returns:
            The library the gallery lists.

        """
        return self._library

    @property
    def workspace(self) -> Workspace:
        """Immutable current workspace.

        Returns:
            Current domain state.

        """
        return self._store.workspace

    def dispatch(
        self,
        command: str,
        payload: JsonValue,
        revision: int,
    ) -> JsonValue:
        """Return dispatch command.

        Args:
            command: Command.
            payload: Payload.
            revision: Revision.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if (
            command not in {"workspace.snapshot", "screenshot.open"}
            and revision != self._revision
        ):
            msg: str = (
                f"Stale editor revision "
                f"{revision}; current revision is {self._revision}."
            )
            raise ValueError(msg)
        if command == "workspace.snapshot":
            return self._snapshot()
        data: dict[str, JsonValue] = (
            payload if isinstance(payload, dict) else {}
        )
        handlers: dict[str, _EditorCommandHandler] = {
            "demo.open": self._command_demo,
            "browser.input": self._command_input,
            "crawl.start": self._command_crawl,
            "actions.run": self._command_actions,
            "crawl.cancel": self._command_cancel,
            "flow.select": self._command_select_flow,
            "flow.create": self._command_create_flow,
            "flow.delete": self._command_delete_flow,
            "workspace.open": self._command_open_workspace,
            "workspace.save": self._command_save_workspace,
            "browser.navigate": self._command_navigate,
            "viewport.preset": self._command_preset,
            "target.save": self._command_save_target,
            "target.check": self._command_check_target,
            "target.start": self._command_start_service,
            "target.stop": self._command_stop_service,
            "profile.save": self._command_save_profile,
            "profile.delete": self._command_delete_profile,
            "recorder.record": self._command_record,
            "recorder.pause": self._command_pause,
            "run.play": self._command_play,
            "run.cancel": self._command_cancel,
            "run.pause": self._command_pause_run,
            "run.resume": self._command_resume_run,
            "run.step": self._command_step_run,
            "browser.open": self._command_browser_open,
            "browser.close": self._command_browser_close,
            "browser.select": self._command_browser_select,
            "recorder.stop": self._command_stop,
            "flow.update": self._command_update_flow,
            "event.update": self._command_update_event,
            "event.add": self._command_add_event,
            "event.configure": self._command_configure_event,
            "edge.add": self._command_add_edge,
            "edge.remove": self._command_remove_edge,
            "edge.update": self._command_update_edge,
            "edge.move": self._command_move_edge,
            "event.delete": self._command_delete_event,
            "event.duplicate": self._command_duplicate_event,
            "recording.rename": self._command_rename_recording,
            "recording.retime": self._command_retime_recording,
            "recording.delete": self._command_delete_recording,
            "event.move": self._command_move_event,
            "event.reorder": self._command_reorder_event,
            "event.retime": self._command_retime_event,
            "event.assert": self._command_assert_event,
            "event.assert.remove": self._command_remove_assertion,
            "screenshot.open": self._command_open_screenshot,
            "selector.save": self._command_selector_save,
            "selector.delete": self._command_selector_delete,
            "selector.test": self._command_selector_test,
            "project.create": self._command_project_create,
            "project.open": self._command_project_open,
            "project.update": self._command_project_update,
            "project.duplicate": self._command_project_duplicate,
            "project.delete": self._command_project_delete,
            "project.import": self._command_project_import,
        }
        if (handler := handlers.get(command)) is None:
            msg = f"Unknown editor command: {command}"
            raise ValueError(msg)
        handler(data=data)
        return self._snapshot()

    def stop_demo(self) -> None:
        """Stop the processes this Studio service started: demo and target."""
        self._targets.stop(wait=True)
        if self._demo_pid is not None:
            process_control.terminate_tree(pid=self._demo_pid)
            local.clear_server_state(path=demo_site())
            self._demo_pid = None

    def receive(self, *, message: dict[str, JsonValue]) -> None:
        """Accept a typed worker message on the service's serialized boundary.

        Args:
            message: Worker event or target lifecycle update.

        """
        kind: JsonValue = message.get("type")
        if kind in {"frontend_progress", "actions_state", "run_gate"}:
            self._receive_status(kind=str(object=kind), message=message)
            return
        if kind in {"crawl_state", "crawl_result"}:
            self._receive_crawl(message=message)
            return
        if kind in {"target_state", "target_service"}:
            if kind == "target_state":
                self._receive_target(message=message)
            else:
                self._receive_service(message=message)
            return
        if kind in {"target_inspection", "selector_test"}:
            self._receive_page_result(kind=kind, message=message)
            return
        if kind == "worker_error":
            if self._execution_state is not None:
                self._fail_execution(
                    message=str(
                        object=message.get("error") or "Worker failed.",
                    ),
                )
            self._recording_state = "idle"
            self._crawl_state = {"state": "failed"}
            self._recording_session_id = None
            self._protocol_error(
                message=str(object=message.get("error") or "Worker failed."),
            )
            return
        self._receive_decoded(
            decoded=RecorderProtocol.decode_message(
                line=dumps(obj=message).encode(),
            ),
        )

    @classmethod
    def _editor_edge(cls, *, data: dict[str, JsonValue]) -> FlowEdge:
        """Parse an editor transition without changing the workspace.

        Args:
            data: Transition fields supplied by the editor.

        Returns:
            Validated transition for the workspace store.

        """
        return FlowEdge(
            source_flow_id=cls._required_string(data=data, key="source"),
            target_flow_id=cls._required_string(data=data, key="target"),
            mode=TransitionMode(
                value=cls._required_string(data=data, key="mode"),
            ),
            condition_expression=str(object=data["condition_expression"])
            if data.get("condition_expression")
            else None,
            priority=int(str(object=data.get("priority", "0"))),
            max_traversals=int(str(object=data.get("max_traversals", "1"))),
        )

    @classmethod
    def _setting(
        cls,
        *,
        data: dict[str, JsonValue],
        key: str,
        draft: bool,
    ) -> str:
        """Return a setting, accepting a blank one while an action is drafted.

        Args:
            data: Command payload.
            key: Setting name.
            draft: Whether blank settings are tolerated.

        Returns:
            The setting, or an empty string for a blank drafted setting.

        """
        if draft and (not data.get(key)):
            return ""
        return cls._required_string(data=data, key=key)

    @staticmethod
    def _required_string(*, data: dict[str, JsonValue], key: str) -> str:
        """Return required string.

        Args:
            data: Data.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            _MissingSettingError: When ``key`` is absent, empty, or not a
                string.

        """
        value: JsonValue = data.get(key)
        if not isinstance(value, str) or value == "":
            msg: str = f"{key} must be a non-empty string."
            raise _MissingSettingError(msg)
        return value

    @staticmethod
    def _validate_pointer_input(
        *,
        action: str,
        data: dict[str, JsonValue],
    ) -> None:
        """Validate pointer buttons, touch identity, and wheel deltas.

        Args:
            action: Pointer action name.
            data: Command payload carrying the pointer fields.

        Raises:
            ValueError: When a field is outside its supported range.

        """
        if action in {"pointer_down", "pointer_up"} and (
            not (
                isinstance(data.get("button"), int)
                and (not isinstance(data.get("button"), bool))
                and (
                    0
                    <= int(str(object=data["button"]))
                    <= Constants.max_pointer_button
                )
            )
        ):
            msg: str = "Pointer button is outside the supported range."
            raise ValueError(msg)
        if action == "pointer_move" and (
            not (
                isinstance(data.get("buttons"), int)
                and (not isinstance(data.get("buttons"), bool))
                and (
                    0
                    <= int(str(object=data["buttons"]))
                    <= Constants.max_pointer_buttons
                )
            )
        ):
            msg = "Pointer buttons are outside the supported range."
            raise ValueError(msg)
        if str(object=action).startswith("touch_") and (
            not (
                isinstance(data.get("pointer_id"), int)
                and (not isinstance(data.get("pointer_id"), bool))
                and (0 <= int(str(object=data["pointer_id"])) <= 2**31 - 1)
            )
        ):
            msg = "Touch pointer ID is outside the supported range."
            raise ValueError(msg)
        if action == "wheel" and any(
            not -Constants.max_scroll_delta
            <= float(str(object=data.get(key)))
            <= Constants.max_scroll_delta
            for key in ("dx", "dy")
        ):
            msg = "Scroll input is outside the supported range."
            raise ValueError(msg)

    @staticmethod
    def _event_elapsed(
        *,
        flow: Flow,
        recording_group_id: str | None,
        gap_ms: int,
    ) -> int:
        """Place an action after its recording peer or the global tail.

        Args:
            flow: Flow receiving the action.
            recording_group_id: Recording the action belongs to, if any.
            gap_ms: Pause inserted before the action.

        Returns:
            The elapsed time for the new action in milliseconds.

        Raises:
            ValueError: When the recording group is unknown.

        """
        if recording_group_id is None:
            return (
                max(
                    (event.elapsed_ms for event in flow.events),
                    default=-gap_ms,
                )
                + gap_ms
            )
        group: FlowRecording | None = next(
            (
                item
                for item in flow.recordings
                if item.recording_id == recording_group_id
            ),
            None,
        )
        if group is None:
            msg: str = f"Unknown recording: {recording_group_id}"
            raise ValueError(msg)
        return (
            max(
                (
                    event.elapsed_ms
                    for event in flow.events
                    if event.recording_group_id == recording_group_id
                ),
                default=group.start_ms,
            )
            + gap_ms
        )

    def _receive_status(
        self,
        *,
        kind: str,
        message: dict[str, JsonValue],
    ) -> None:
        """Mirror a progress or state report that changes no saved data.

        Args:
            kind: ``frontend_progress``, ``actions_state`` or ``run_gate``.
            message: The worker's report.

        """
        if kind == "run_gate":
            self._receive_run_gate(message=message)
            return
        if kind == "frontend_progress":
            self._crawl_state["progress"] = dict(message)
        else:
            self._crawl_state = dict(message)
        self._changed(dirty=False)

    def _command_input(self, data: dict[str, JsonValue]) -> None:
        """Validate scaled live-panel input before forwarding to Playwright.

        Args:
            data: Pointer coordinates or a keyboard key on the target viewport.

        Raises:
            ValueError: When input is unsupported or outside the target.

        """
        if self._target_state != "ready":
            msg: str = "Open the target before interacting with its live view."
            raise ValueError(msg)
        if self._execution_state is not None:
            msg = "Stop playback before interacting with the target."
            raise ValueError(msg)
        action: JsonValue = data.get("action")
        pointer_actions: set[str] = {
            "click",
            "inspect",
            "pointer_down",
            "pointer_move",
            "pointer_up",
            "touch_cancel",
            "touch_end",
            "touch_move",
            "touch_start",
            "wheel",
        }
        if action not in {
            *pointer_actions,
            "key",
            "key_down",
            "key_up",
            "pointer_leave",
        }:
            msg = "Unsupported live target input."
            raise ValueError(msg)
        if action in pointer_actions:
            self._validate_pointer_position(data=data)
        self._validate_pointer_input(action=str(object=action), data=data)
        if action in {"key", "key_down", "key_up"}:
            self._validate_keyboard_input(data=data)
        self._worker.input_target(message=data)

    def _validate_pointer_position(
        self,
        *,
        data: dict[str, JsonValue],
    ) -> None:
        """Require a coordinate inside the configured target viewport.

        Args:
            data: Command payload carrying ``x`` and ``y``.

        Raises:
            ValueError: When the pointer is outside the target viewport.

        """
        x: float = float(str(object=data.get("x")))
        y: float = float(str(object=data.get("y")))
        if not (
            0 <= x < self._viewport.width and 0 <= y < self._viewport.height
        ):
            msg: str = "Pointer is outside the target viewport."
            raise ValueError(msg)

    def _validate_keyboard_input(self, *, data: dict[str, JsonValue]) -> None:
        """Validate a browser keyboard event.

        Args:
            data: Command payload carrying ``key`` and optionally ``code``.

        Raises:
            ValueError: When the key or code is missing, too long or invalid.

        """
        value: str = self._required_string(data=data, key="key")
        if len(value) > Constants.max_key_length:
            msg: str = "Keyboard input is too long."
            raise ValueError(msg)
        code: JsonValue = data.get("code")
        if code is not None and (
            not isinstance(code, str) or len(code) > Constants.max_key_length
        ):
            msg = "Keyboard code is invalid."
            raise ValueError(msg)

    def _command_demo(self, data: dict[str, JsonValue]) -> None:
        """Open a real demo target and its editable, connected flow graph.

        Args:
            data: Replacement confirmation when a workspace has local edits.

        Raises:
            ValueError: When an operation is active, edits are unconfirmed,
                or the managed demo server does not become ready.

        """
        if (
            self._recording_state != "idle"
            or self._execution_state is not None
            or self._crawl_state.get("state") == "running"
        ):
            msg: str = "Stop the active operation before opening the demo."
            raise ValueError(msg)
        if self._dirty and data.get("replace") is not True:
            msg = (
                "Save or confirm replacing your edits before opening the demo."
            )
            raise ValueError(msg)
        self.stop_demo()
        pid: int
        url: str
        reused: bool
        pid, url, reused = local.serve(
            path=demo_site(),
            log=self._persistence.root / ".studio" / "demo-server.log",
        )
        self._demo_pid = None if reused else pid
        if not local.wait_ready(url=url, pid=pid):
            self.stop_demo()
            msg = "The demo server did not become ready."
            raise ValueError(msg)
        served: SplitResult = urlsplit(url=url)
        workspace: Workspace = replace(
            demo_workspace(url=url),
            target=Target(
                url=f"{served.scheme}://{served.hostname}",
                port=served.port,
            ),
        )
        if data.get("project") is True:
            slug: str = self._library.ensure(
                info=ProjectInfo(
                    name="Demo flow",
                    description="Sample flows against the bundled demo site.",
                    tags=("demo",),
                ),
                workspace=workspace,
            )
            if slug != self._project:
                self._activate_project(slug=slug)
        self._open_workspace(
            data={
                "workspace": WorkspaceCodec.to_json_value(workspace=workspace),
            },
        )
        self._target_url = url
        self._show()
        self._worker.open_target(url=url)

    def _command_actions(self, data: dict[str, JsonValue]) -> None:
        """Run and retain a declarative orchestration recipe.

        Args:
            data: Complete Actions document.

        Raises:
            ValueError: When an operation is already active.
            OSError: When the orchestration recipe cannot start.
            RuntimeError: When the orchestration recipe fails to launch.

        """
        if (
            self._recording_state == "recording"
            or self._execution_state is not None
            or self._crawl_state.get("state") == "running"
        ):
            msg: str = "Stop the active operation before running Actions."
            raise ValueError(msg)
        self._crawl_state = {"state": "running", "operation": "actions"}
        self._changed(dirty=False)
        try:
            self._worker.actions(
                specification=data,
                root=self._persistence.root,
            )
        except (ValueError, OSError, RuntimeError):
            self._crawl_state = {"state": "idle"}
            self._changed(dirty=False)
            raise

    def _command_crawl(self, data: dict[str, JsonValue]) -> None:
        """Discover replayable target states.

        Args:
            data: Bounded exploration options; the project's target is used
                unless an explicit ``url`` is given.

        Raises:
            ValueError: When discovery limits or current state are invalid.

        """
        depth: int = int(str(object=data.get("max_depth", "2")))
        states: int = int(str(object=data.get("max_states", "20")))
        if (
            not 1 <= depth <= Constants.max_crawl_depth
            or not 1 <= states <= Constants.max_crawl_states
        ):
            msg: str = "Use depth 1-10 and state limit 1-200."
            raise ValueError(msg)
        if (
            self._recording_state == "recording"
            or self._execution_state is not None
            or self._crawl_state.get("state") == "running"
        ):
            msg = "Stop the active operation before crawling."
            raise ValueError(msg)
        for field in ("capture_ui_changes", "follow_links", "click_controls"):
            if field in data and (not isinstance(data[field], bool)):
                msg = f"{field} must be a boolean."
                raise ValueError(msg)
        self._worker.crawl(
            request=CrawlRequest(
                url=self._address(data=data),
                max_depth=depth,
                max_states=states,
                capture_ui_changes=data.get("capture_ui_changes", True)
                is True,
                follow_links=data.get("follow_links", True) is True,
                click_controls=data.get("click_controls", True) is True,
                include_selector=str(object=data.get("include_selector") or "")
                or None,
            ),
        )
        self._crawl_state = {"state": "running"}
        self._changed(dirty=False)

    def _command_browser_open(self, data: dict[str, JsonValue]) -> None:
        """Open a fresh service-owned target context.

        Args:
            data: Optional initial target URL.

        """
        self._show()
        self._worker.open_target(url=self._address(data=data))

    def _address(self, *, data: dict[str, JsonValue]) -> str:
        """Choose what the target browser opens.

        Args:
            data: Command payload that may carry an explicit ``url``.

        Returns:
            The explicit URL, else the project's configured address.

        Raises:
            ValueError: When a service is configured but not running.

        """
        explicit: JsonValue = data.get("url")
        if isinstance(explicit, str) and explicit:
            return explicit
        target: Target = self._store.workspace.target
        service_url: str | None = self._targets.base_url
        if target.mode is TargetMode.SERVICE and service_url is None:
            msg: str = "Start the service in Settings first."
            raise ValueError(msg)
        return target.address(service_url=service_url)

    def _configured_address(self) -> str | None:
        """Return where the browser would open, or None when it cannot yet.

        Returns:
            The project's address, or None while a service is not running.

        """
        target: Target = self._store.workspace.target
        service_url: str | None = self._targets.base_url
        if target.mode is TargetMode.SERVICE and service_url is None:
            return None
        return target.address(service_url=service_url)

    def _command_save_target(self, data: dict[str, JsonValue]) -> None:
        """Save where the application under test is reached.

        Args:
            data: Target fields from the Settings page.

        """
        target: Target = WorkspaceCodec.parse_target(value=data.get("target"))
        if target.mode is TargetMode.URL:
            self._targets.stop()
        self._store.save_target(target=target)
        self._target_check = None
        self._changed()

    def _command_check_target(self, data: dict[str, JsonValue]) -> None:
        """Probe the configured address and report whether it answers.

        Args:
            data: Unused command payload.

        """
        _ = data
        self._target_check = self._targets.check(
            target=self._store.workspace.target,
        )
        self._changed(dirty=False)

    def _command_start_service(self, data: dict[str, JsonValue]) -> None:
        """Start the configured service; Studio never does it on its own.

        Args:
            data: ``open`` asks for the browser to open on the detected page.

        Raises:
            ValueError: When the configured service cannot be started.

        """
        self._open_after_start = data.get("open") is True
        try:
            self._targets.start(target=self._store.workspace.target)
        except ValueError:
            self._open_after_start = False
            raise

    def _command_stop_service(self, data: dict[str, JsonValue]) -> None:
        """Stop the service Studio started.

        Args:
            data: Unused command payload.

        """
        _ = data
        self._targets.stop()
        self._changed(dirty=False)

    def _command_browser_close(self, data: dict[str, JsonValue]) -> None:
        """Close only the service-owned target.

        Args:
            data: Unused command payload.

        """
        _ = data
        self._worker.close_target()

    def _command_browser_select(self, data: dict[str, JsonValue]) -> None:
        """Choose a target page from the managed context.

        Args:
            data: Stable target page identifier.

        """
        self._worker.select_target(
            page_id=self._required_string(data=data, key="page_id"),
        )

    def _command_stop(self, data: dict[str, JsonValue]) -> None:
        """Stop recording without discarding the workspace.

        Args:
            data: Unused command payload.

        """
        self._command_pause(data=data)
        self._recording_state = "idle"
        self._recording_session_id = None
        self._changed(dirty=False)

    def _command_pause_run(self, data: dict[str, JsonValue]) -> None:
        """Hold the running flow before its next action.

        Args:
            data: Unused command payload.

        Raises:
            ValueError: When no run is in progress.

        """
        _ = data
        if self._execution_state is None:
            msg: str = "Start a run before pausing it."
            raise ValueError(msg)
        self._run_control = "pausing"
        self._worker.pause_run()
        self._changed(dirty=False)

    def _command_resume_run(self, data: dict[str, JsonValue]) -> None:
        """Let a held flow continue to its end.

        Args:
            data: Unused command payload.

        Raises:
            ValueError: When no run is in progress.

        """
        _ = data
        if self._execution_state is None:
            msg: str = "No run is waiting to continue."
            raise ValueError(msg)
        self._run_control = "running"
        self._worker.resume_run()
        self._changed(dirty=False)

    def _command_step_run(self, data: dict[str, JsonValue]) -> None:
        """Run one action, holding a flow that is paused or not yet started.

        Args:
            data: Unused command payload.

        """
        if self._execution_state is None:
            self._require_player()
            self._worker.pause_run()
            self._run_control = "pausing"
            self._play(
                follow_connections=data.get("scope") != "flow",
                inputs={},
                flow_inputs={},
            )
            return
        self._worker.step_run()
        self._run_control = "running"
        self._changed(dirty=False)

    def _receive_run_gate(self, *, message: dict[str, JsonValue]) -> None:
        """Mirror where the runner is held, for the editor.

        Args:
            message: ``run_gate`` message naming the state and next action.

        """
        state: str = str(object=message.get("state") or "running")
        self._run_control = state
        self._run_held_before = (
            str(object=message.get("event_id")) if state == "paused" else None
        )
        self._changed(dirty=False)

    def _end_run_control(self) -> None:
        """Forget pause state when a workflow finishes, fails or is stopped."""
        self._run_control = "running"
        self._run_held_before = None
        self._worker.resume_run()

    def _command_cancel(self, data: dict[str, JsonValue]) -> None:
        """Signal cancellation while retaining completed step evidence.

        Args:
            data: Unused command payload.

        """
        _ = data
        self._worker.cancel()

    def _receive_service(self, *, message: dict[str, JsonValue]) -> None:
        """Publish the service's state and open the browser on request.

        Args:
            message: Service state with its detected address.

        """
        state: JsonValue = message.get("state")
        if self._open_after_start and state in {"running", "failed", "exited"}:
            self._open_after_start = False
            if state == "running" and self._target_state not in {
                "ready",
                "opening",
            }:
                self._show()
                self._worker.open_target(url=self._address(data={}))
        self._changed(dirty=False)

    def _target_suggestion(self) -> JsonValue:
        """Offer the demo server while the project has no target of its own.

        Returns:
            The suggested target, or None once a target is configured.

        """
        current: Target = self._store.workspace.target
        if current != Target() or (suggestion := demo_target()) is None:
            return None
        return WorkspaceCodec.target_to_json(target=suggestion)

    def _receive_page_result(
        self,
        *,
        kind: JsonValue,
        message: dict[str, JsonValue],
    ) -> None:
        """Keep an answer the browser worker computed about the target page.

        Args:
            kind: ``target_inspection`` or ``selector_test``.
            message: The worker message.

        """
        if kind == "selector_test":
            self._receive_selector_test(message=message)
            return
        self._target_inspection = message
        self._bridge.emit_event(
            name="target.inspected",
            payload={"target_inspection": message},
        )

    def _receive_selector_test(self, *, message: dict[str, JsonValue]) -> None:
        """Keep a selector test result and note where the selector passed.

        Args:
            message: Worker message carrying ``result``.

        """
        result: JsonValue = message.get("result")
        if not isinstance(result, dict):
            return
        self._selector_test = result
        if record_validation(store=self._store, result=result):
            self._changed()
        self._bridge.emit_event(
            name="selector.tested",
            payload={"selector_test": result},
        )

    def _receive_crawl(self, *, message: dict[str, JsonValue]) -> None:
        """Track discovery progress and absorb a finished crawl document.

        Args:
            message: Crawl lifecycle update with an optional workspace.

        """
        self._crawl_state = {
            key: value for key, value in message.items() if key != "workspace"
        }
        document: JsonValue = message.get("workspace")
        if message.get("type") == "crawl_result" and isinstance(
            document,
            dict,
        ):
            self._open_workspace(data={"workspace": document})
            self._active_flow_id = max(
                self._store.workspace.flows,
                key=lambda flow: len(flow.events),
            ).flow_id
            self._changed()
        else:
            self._changed(dirty=False)

    def _receive_target(self, *, message: dict[str, JsonValue]) -> None:
        """Mirror managed-browser lifecycle and fail a run on closure.

        Args:
            message: Target lifecycle update with state and URL.

        """
        self._target_state = str(object=message.get("state") or "closed")
        self._target_url = str(object=message.get("url") or "about:blank")
        self._clients = 1 if self._target_state == "ready" else 0
        if not self._clients:
            self._recording_state = "idle"
            self._recording_session_id = None
            if self._execution_state is not None:
                self._fail_execution(
                    message="Test browser closed during the run.",
                )
        self._changed(dirty=False)

    def _receive_decoded(self, *, decoded: RecorderInbound) -> None:
        """Route one decoded recorder message to its typed handler.

        Args:
            decoded: Canonical recorder message.

        """
        if isinstance(decoded, TimelineEvent):
            self._receive_event(event=decoded)
        elif isinstance(decoded, ScreenshotArtifact):
            self._receive_screenshot(artifact=decoded)
        elif isinstance(decoded, FlowExecutionResult):
            self._receive_flow_result(result=decoded)
        elif isinstance(decoded, ExpectationResult):
            self._receive_expectation_result(result=decoded)
        elif isinstance(decoded, CheckpointArtifact):
            self._receive_checkpoint(artifact=decoded)
        else:
            self._receive_run_progress(progress=decoded)

    def _command_select_flow(self, data: dict[str, JsonValue]) -> None:
        """Handle command select flow.

        Args:
            data: Data.

        """
        self._select_flow(
            flow_id=self._required_string(data=data, key="flow_id"),
        )

    def _command_create_flow(self, data: dict[str, JsonValue]) -> None:
        """Handle command create flow.

        Args:
            data: Data.

        """
        _ = data
        self._create_flow()

    def _command_delete_flow(self, data: dict[str, JsonValue]) -> None:
        """Handle command delete flow.

        Args:
            data: Data.

        """
        self._delete_flow(
            flow_id=self._required_string(data=data, key="flow_id"),
        )

    def _command_open_workspace(self, data: dict[str, JsonValue]) -> None:
        """Handle command open workspace.

        Args:
            data: Data.

        """
        self._open_workspace(data=data)

    def _command_save_workspace(self, data: dict[str, JsonValue]) -> None:
        """Handle command save workspace.

        Args:
            data: Data.

        """
        self._save_workspace(data=data)

    def _command_navigate(self, data: dict[str, JsonValue]) -> None:
        """Handle command navigate.

        Args:
            data: Data.

        """
        self._worker.navigate(
            value=self._required_string(data=data, key="url"),
        )

    def _profile(self) -> Profile:
        """Return the profile the target is shown under.

        Returns:
            The active profile, or the first one when it was removed.

        """
        profiles: tuple[Profile, ...] = self._store.workspace.profiles
        return next(
            (
                item
                for item in profiles
                if item.profile_id == self._device_mode
            ),
            profiles[0],
        )

    def _require_idle_target(self) -> None:
        """Refuse a change of browser conditions while the target is in use.

        Raises:
            ValueError: When a run, recording or discovery is active.

        """
        if (
            self._recording_state != "idle"
            or self._execution_state is not None
            or self._crawl_state.get("state") == "running"
        ):
            msg: str = "Stop the active operation before changing the profile."
            raise ValueError(msg)

    def _show(self, *, size: ViewportSize | None = None) -> None:
        """Show the target under the active profile, optionally resized.

        Args:
            size: Ad-hoc viewport that replaces the profile's own size.

        """
        profile: Profile = self._profile()
        if size is not None:
            profile = replace(profile, width=size.width, height=size.height)
        shown: Profile | None = self._shown
        self._shown = profile
        self._viewport = profile.size
        if (
            self._target_state == "ready"
            and shown is not None
            and (shown.device_settings != profile.device_settings)
        ):
            self._target_state = "opening"
        self._worker.set_profile(profile=profile)

    def _command_preset(self, data: dict[str, JsonValue]) -> None:
        """Show the target under a saved profile or an ad-hoc size.

        Args:
            data: Profile ID (or ``custom``), plus optional size overrides.

        Raises:
            ValueError: When the profile is unknown or the scope is shared.

        """
        self._require_idle_target()
        mode: str = self._required_string(data=data, key="mode")
        if mode == DeviceMode.SHARED:
            msg: str = "Shared is a flow scope, not a viewport preset."
            raise ValueError(msg)
        if mode != DeviceMode.CUSTOM and all(
            item.profile_id != mode for item in self._store.workspace.profiles
        ):
            msg = f"Unknown profile: {mode}"
            raise ValueError(msg)
        previous: str = self._device_mode
        self._device_mode = mode
        size: ViewportSize = (
            self._viewport
            if mode == DeviceMode.CUSTOM
            else self._profile().size
        )
        if "width" in data or "height" in data:
            size = ViewportSize(
                width=int(str(object=data["width"])),
                height=int(str(object=data["height"])),
            )
        orientation: JsonValue = data.get("orientation")
        if orientation == "portrait":
            size = size.vertical()
        elif orientation == "landscape":
            size = size.horizontal()
        try:
            self._show(size=size)
        except ValueError:
            self._device_mode = previous
            raise
        self._changed(dirty=False)

    def _command_save_profile(self, data: dict[str, JsonValue]) -> None:
        """Add or change a profile; unsupported media features are refused.

        Args:
            data: Profile fields as described by the profile schema.

        """
        profile: Profile = WorkspaceCodec.parse_profile(
            value=data.get("profile"),
        )
        if profile.profile_id == self._device_mode:
            self._require_idle_target()
        self._store.save_profile(profile=profile)
        if profile.profile_id == self._device_mode:
            self._show()
        self._changed()

    def _command_delete_profile(self, data: dict[str, JsonValue]) -> None:
        """Remove a profile that no flow is scoped to.

        Args:
            data: Profile identifier.

        """
        profile_id: str = self._required_string(data=data, key="profile_id")
        if profile_id == self._device_mode:
            self._require_idle_target()
        self._store.delete_profile(profile_id=profile_id)
        if profile_id == self._device_mode:
            self._device_mode = self._store.workspace.profiles[0].profile_id
            self._show()
        self._changed()

    def _command_record(self, data: dict[str, JsonValue]) -> None:
        """Handle command record.

        Args:
            data: Data.

        """
        _ = data
        self._require_player()
        self._record()

    def _command_pause(self, data: dict[str, JsonValue]) -> None:
        """Handle command pause.

        Args:
            data: Data.

        """
        _ = data
        self._pause()

    def _command_play(self, data: dict[str, JsonValue]) -> None:
        """Handle command play.

        Args:
            data: Data.

        """
        self._require_player()
        raw_inputs: JsonValue = data.get("inputs")
        inputs: dict[str, str] = (
            {
                str(object=key): str(object=value)
                for key, value in raw_inputs.items()
            }
            if isinstance(raw_inputs, dict)
            else {}
        )
        raw_flow: JsonValue = data.get("flow_inputs")
        self._play(
            follow_connections=data.get("scope") != "flow",
            inputs=inputs,
            flow_inputs={
                str(object=key): str(object=value)
                for key, value in raw_flow.items()
            }
            if isinstance(raw_flow, dict)
            else {},
        )

    def _command_update_flow(self, data: dict[str, JsonValue]) -> None:
        """Save editable Flow docs and independent screenshot policies.

        Args:
            data: Input bytes or canonical document.

        """
        flow: Flow = self._store.get_flow(flow_id=self._active_flow_id)
        self._store.update_flow(
            flow_id=flow.flow_id,
            settings=FlowSettings(
                name=self._required_string(data=data, key="name"),
                task_description=str(
                    object=data.get("task_description", flow.task_description),
                ),
                expected_behavior=str(
                    object=data.get(
                        "expected_behavior",
                        flow.expected_behavior,
                    ),
                ),
                notes=flow.notes,
                device_modes=self._scopes(data=data)
                if "device_scope" in data or "device_scopes" in data
                else flow.device_modes,
                capture_record_images=data.get("capture_record_images")
                is True,
                capture_play_images=data.get("capture_play_images") is True,
                parameters=_flow_parameters(value=data["parameters"])
                if "parameters" in data
                else None,
            ),
        )
        self._changed()

    def _scope(self, *, data: dict[str, JsonValue]) -> str:
        """Return a flow scope that names shared, custom or a saved profile.

        Args:
            data: Command payload carrying ``device_scope``.

        Returns:
            The requested scope.

        Raises:
            ValueError: When it names no saved profile.

        """
        scope: str = str(object=data["device_scope"])
        if scope in {DeviceMode.SHARED, DeviceMode.CUSTOM} or any(
            item.profile_id == scope for item in self._store.workspace.profiles
        ):
            return scope
        msg: str = f"Unknown profile: {scope}"
        raise ValueError(msg)

    def _scopes(self, *, data: dict[str, JsonValue]) -> frozenset[str]:
        """Validate one or more profile scopes from the editor.

        Args:
            data: Command payload carrying legacy or multi-profile scope.

        Returns:
            Validated, non-empty profile identifiers.

        Raises:
            ValueError: When no scope is supplied or one is unknown.

        """
        raw: JsonValue = data.get("device_scopes")
        values: list[JsonValue] = (
            raw if isinstance(raw, list) else [data.get("device_scope")]
        )
        scopes: frozenset[str] = frozenset(
            self._scope(data={"device_scope": item}) for item in values
        )
        if DeviceMode.SHARED in scopes and len(scopes) > 1:
            msg: str = "Shared scope cannot be combined with named profiles."
            raise ValueError(msg)
        return scopes

    def _command_update_event(self, data: dict[str, JsonValue]) -> None:
        """Edit a step using the existing model's targeting validation.

        Args:
            data: Input bytes or canonical document.

        """
        event: TimelineEvent = self._store.get_event(
            flow_id=self._active_flow_id,
            event_id=self._required_string(data=data, key="event_id"),
        )
        self._store.update_event(
            event=updated_event(
                event=event,
                data=data,
                selectors=self._store.workspace.selectors,
                label=self._required_string(data=data, key="label"),
            ),
        )
        self._changed()

    def _command_project_create(self, data: dict[str, JsonValue]) -> None:
        """Create a project in its own folder and open it.

        Args:
            data: ``name`` (unique), optional ``description``, ``tags``,
                ``author``, ``version`` and ``base_url``; ``replace``
                confirms discarding unsaved edits of the project now open.

        """
        self._require_idle(action="creating a project")
        self._require_saved_or_confirmed(data=data)
        summary: ProjectSummary = self._library.create(
            info=new_info(data=data),
            base_url=str(object=data.get("base_url") or ""),
        )
        self._activate_project(slug=summary.slug)

    def _command_project_open(self, data: dict[str, JsonValue]) -> None:
        """Open a project from the library.

        Args:
            data: ``slug`` of the project; ``replace`` confirms discarding
                unsaved edits of the project now open.

        """
        self._require_idle(action="opening a project")
        slug: str = self._required_string(data=data, key="slug")
        self._library.get(slug=slug)
        if slug != self._project:
            self._require_saved_or_confirmed(data=data)
        self._activate_project(slug=slug)

    def _command_project_update(self, data: dict[str, JsonValue]) -> None:
        """Change the open project's name, details and base address.

        Args:
            data: Changed fields; see ``updated_workspace``.

        """
        self._store.replace_workspace(
            workspace=updated_workspace(
                workspace=self._store.workspace,
                library=self._library,
                active=self._project,
                data=data,
            ),
        )
        self._target_check = None
        self._changed()

    def _command_project_duplicate(self, data: dict[str, JsonValue]) -> None:
        """Copy a project's flows, selectors and settings under a new name.

        Args:
            data: ``slug`` to copy and the unique ``name`` of the copy.

        """
        self._library.duplicate(
            slug=self._required_string(data=data, key="slug"),
            name=self._required_string(data=data, key="name"),
        )
        self._changed(dirty=False)

    def _command_project_delete(self, data: dict[str, JsonValue]) -> None:
        """Delete a project that is not the one open.

        Args:
            data: ``slug`` of the project to delete.

        Raises:
            ValueError: When it is the project that is open.

        """
        slug: str = self._required_string(data=data, key="slug")
        if slug == self._project:
            msg: str = "Open another project before deleting this one."
            raise ValueError(msg)
        self._library.delete(slug=slug)
        self._changed(dirty=False)

    def _command_project_import(self, data: dict[str, JsonValue]) -> None:
        """Add a project from an exported document, and optionally open it.

        Args:
            data: ``workspace`` document, optional ``name``; ``open`` opens
                it, and ``replace`` confirms discarding unsaved edits.

        Raises:
            ProjectError: When the document is not an exported project.

        """
        document: JsonValue = data.get("workspace")
        if not isinstance(document, dict):
            msg: str = "Choose an exported project to import."
            raise ProjectError(msg)
        opening: bool = data.get("open") is True
        if opening:
            self._require_idle(action="opening a project")
            self._require_saved_or_confirmed(data=data)
        summary: ProjectSummary = self._library.import_document(
            document=document,
            name=str(object=data.get("name") or ""),
        )
        if opening:
            self._activate_project(slug=summary.slug)
        else:
            self._changed(dirty=False)

    def _require_idle(self, *, action: str) -> None:
        """Refuse to change projects while something is running.

        Args:
            action: What the person asked for, for the message.

        Raises:
            ValueError: When a recording, run or crawl is active.

        """
        if (
            self._recording_state != "idle"
            or self._execution_state is not None
            or self._crawl_state.get("state") == "running"
        ):
            msg: str = f"Stop the active operation before {action}."
            raise ValueError(msg)

    def _require_saved_or_confirmed(
        self,
        *,
        data: dict[str, JsonValue],
    ) -> None:
        """Refuse to leave unsaved edits behind unless that was confirmed.

        Args:
            data: Command payload, where ``replace`` confirms.

        Raises:
            ValueError: When edits are unsaved and not confirmed.

        """
        if self._dirty and data.get("replace") is not True:
            msg: str = "Save your changes or confirm discarding them first."
            raise ValueError(msg)

    def _activate_project(self, *, slug: str) -> None:
        """Make a project the open one: its files, evidence and target.

        Args:
            slug: A project that exists.

        """
        if self._dirty:
            self._persistence.discard_recovery()
        persistence: WorkspaceFiles = WorkspaceFiles(
            root=self._library.folder(slug=slug),
        )
        saved: Workspace = persistence.open(
            data={"filename": ProjectConstants.file_name},
        )
        recovered: Workspace | None = persistence.recover()
        workspace: Workspace = (
            saved if recovered is None or recovered == saved else recovered
        )
        self._persistence = persistence
        self._project = slug
        self._store.replace_workspace(workspace=workspace)
        self._targets.stop()
        self._targets.set_root(root=persistence.root)
        self._worker.close_target()
        self._worker.set_output(output=persistence.artifact_root)
        self._recording_state = "idle"
        self._recording_session_id = None
        self._target_check = None
        self._selector_test = None
        self._target_inspection = None
        self._active_flow_id = workspace.flows[0].flow_id
        if all(
            item.profile_id != self._device_mode for item in workspace.profiles
        ):
            self._device_mode = workspace.profiles[0].profile_id
        self._show()
        self._dirty = workspace is not saved
        self._library.touch(slug=slug)
        self._changed(dirty=self._dirty)

    def _command_selector_save(self, data: dict[str, JsonValue]) -> None:
        """Create or edit a project selector.

        Args:
            data: Selector fields; see ``save_selector``.

        """
        save_selector(store=self._store, data=data)
        self._changed()

    def _command_selector_delete(self, data: dict[str, JsonValue]) -> None:
        """Delete a selector that nothing depends on, or force it.

        Args:
            data: ``selector_id`` and optionally ``force``.

        """
        delete_selector(store=self._store, data=data)
        self._changed()

    def _command_selector_test(self, data: dict[str, JsonValue]) -> None:
        """Test an expression against the live target page.

        The result arrives asynchronously as a ``selector_test`` message.

        Args:
            data: Expression, expected count, checks and selector id.

        Raises:
            ValueError: When the target is not open, or a run is active.

        """
        if self._target_state != "ready":
            msg: str = "Open the target before testing a selector."
            raise ValueError(msg)
        if self._execution_state is not None:
            msg = "Stop playback before testing a selector."
            raise ValueError(msg)
        self._worker.input_target(
            message=test_message(
                data=data,
                selectors=self._store.workspace.selectors,
            ),
        )

    def _command_add_event(self, data: dict[str, JsonValue]) -> None:
        """Append a supported browser action or screenshot checkpoint.

        Args:
            data: Input bytes or canonical document.


        Raises:
            ValueError: When the requested step kind or duration is invalid.

        """
        kind: str = self._required_string(data=data, key="kind")
        supported: dict[str, tuple[EventKind, TimelineLayer]] = {
            "javascript": (EventKind.JAVASCRIPT, TimelineLayer.INTERACTION),
            "wait": (EventKind.WAIT, TimelineLayer.TIMING),
            "screenshot": (EventKind.NOTE, TimelineLayer.TIMING),
            "click": (EventKind.CLICK, TimelineLayer.INTERACTION),
            "double_click": (
                EventKind.DOUBLE_CLICK,
                TimelineLayer.INTERACTION,
            ),
            "right_click": (EventKind.RIGHT_CLICK, TimelineLayer.INTERACTION),
            "hover": (EventKind.HOVER, TimelineLayer.INTERACTION),
            "drag": (EventKind.DRAG, TimelineLayer.INTERACTION),
            "scroll": (EventKind.SCROLL, TimelineLayer.INTERACTION),
            "gesture": (EventKind.GESTURE, TimelineLayer.INTERACTION),
            "position_pointer": (
                EventKind.POSITION_POINTER,
                TimelineLayer.INTERACTION,
            ),
            "input_text": (EventKind.INPUT_TEXT, TimelineLayer.INTERACTION),
            "select_option": (
                EventKind.SELECT_OPTION,
                TimelineLayer.INTERACTION,
            ),
            "keystroke": (EventKind.KEYSTROKE, TimelineLayer.INTERACTION),
            "check": (EventKind.CHECK, TimelineLayer.INTERACTION),
            "uncheck": (EventKind.UNCHECK, TimelineLayer.INTERACTION),
            "url_change": (EventKind.URL_CHANGE, TimelineLayer.NAVIGATION),
            "http_call": (EventKind.HTTP_CALL, TimelineLayer.NETWORK),
            "websocket_call": (
                EventKind.WEBSOCKET_CALL,
                TimelineLayer.WEBSOCKET,
            ),
            "extract_value": (
                EventKind.EXTRACT_VALUE,
                TimelineLayer.INTERACTION,
            ),
            "set_variable": (
                EventKind.SET_VARIABLE,
                TimelineLayer.INTERACTION,
            ),
            "viewport": (EventKind.VIEWPORT, TimelineLayer.TIMING),
            "snapshot": (EventKind.SNAPSHOT, TimelineLayer.INTERACTION),
        }
        if kind not in supported:
            msg: str = (
                "Choose a wait, screenshot, navigation or browser action."
            )
            raise ValueError(msg)
        details, incomplete = self._resolved_details(kind=kind, data=data)
        event_kind, layer = supported[kind]
        flow: Flow = self._store.get_flow(flow_id=self._active_flow_id)
        gap_ms: int = int(str(object=data.get("gap_ms") or "500"))
        if gap_ms < 0 or gap_ms > Constants.max_wait_ms:
            msg = "Timeline gap must be between 0 and 60000 ms."
            raise ValueError(msg)
        recording_group_id: str | None = (
            str(object=data.get("recording_group_id") or "").strip() or None
        )
        elapsed: int = self._event_elapsed(
            flow=flow,
            recording_group_id=recording_group_id,
            gap_ms=gap_ms,
        )
        self._store.append_event(
            event=TimelineEvent(
                event_id=uuid4().hex,
                flow_id=self._active_flow_id,
                sequence=0,
                elapsed_ms=elapsed,
                layer=layer,
                kind=event_kind,
                selector=details.selector,
                selector_id=details.selector_id,
                url=details.url,
                label=details.label,
                recording_group_id=recording_group_id,
                payload=details.payload,
                method=details.method,
                share_session_cookies=str(
                    object=data.get("share_session_cookies") or "false",
                ).lower()
                == "true",
                position_action=details.position_action,
                x=details.x,
                y=details.y,
                output_variable=str(
                    object=data.get("output_variable") or "",
                ).strip()
                or None,
                sandbox=event_kind is EventKind.JAVASCRIPT,
                when_expression=str(
                    object=data.get("when_expression") or "",
                ).strip()
                or None,
                incomplete=incomplete,
            ),
        )
        self._changed()

    def _command_configure_event(self, data: dict[str, JsonValue]) -> None:
        """Save new settings for an action that is already in the flow.

        Args:
            data: ``event_id``, the action ``kind`` and the same settings
                ``event.add`` takes, plus the targeting and failure policy.

        """
        event: TimelineEvent = self._store.get_event(
            flow_id=self._active_flow_id,
            event_id=self._required_string(data=data, key="event_id"),
        )
        details, incomplete = self._resolved_details(
            kind=self._required_string(data=data, key="kind"),
            data=data,
        )
        self._store.update_event(
            event=reconfigured_event(
                event=event,
                fields=ActionFields(
                    label=details.label,
                    payload=details.payload,
                    selector=details.selector,
                    selector_id=details.selector_id,
                    url=details.url,
                    method=details.method,
                    position_action=details.position_action,
                    x=details.x,
                    y=details.y,
                    incomplete=incomplete,
                ),
                data=data,
                selectors=self._store.workspace.selectors,
            ),
        )
        self._changed()

    def _resolved_details(
        self,
        *,
        kind: str,
        data: dict[str, JsonValue],
    ) -> tuple[_EventDetails, bool]:
        """Normalize action fields, keeping an unfinished action editable.

        A blank required setting does not refuse the action. It is saved as
        incomplete so it can sit in the flow, be selected and be finished in
        Properties. Any other invalid value is still refused.

        Args:
            kind: Action identifier chosen in the library.
            data: Command payload with the submitted fields.

        Returns:
            The normalized fields and whether settings are still missing.

        """
        try:
            return (self._event_details(kind=kind, data=data), False)
        except _MissingSettingError:
            return (
                self._event_details(kind=kind, data=data, draft=True),
                True,
            )

    def _event_details(
        self,
        *,
        kind: str,
        data: dict[str, JsonValue],
        draft: bool = False,
    ) -> _EventDetails:
        """Normalize one action-library submission.

        Args:
            kind: Action identifier chosen in the library.
            data: Command payload with the submitted fields.
            draft: Whether blank required settings are tolerated.

        Returns:
            The normalized action fields.

        """
        if kind == "screenshot":
            details: _EventDetails = _EventDetails(
                label="Capture screenshot",
                payload="__screenshot__",
            )
        elif kind == "wait":
            details = self._wait_details(data=data, draft=draft)
        elif kind == "javascript":
            details = _EventDetails(
                label="JavaScript call",
                payload=self._setting(data=data, key="payload", draft=draft),
                selector=str(object=data.get("selector") or "") or None,
                selector_id=str(object=data.get("selector_id") or "") or None,
            )
        elif kind == "url_change":
            url: str = self._setting(data=data, key="url", draft=draft)
            details = _EventDetails(
                label=f"Navigate to {url}" if url else "Navigate",
                url=url or None,
            )
        elif kind == "http_call":
            details = self._http_details(data=data, draft=draft)
        elif kind == "websocket_call":
            details = self._websocket_details(data=data, draft=draft)
        elif kind == "set_variable":
            details = _EventDetails(
                label="Set variable",
                payload=self._setting(data=data, key="payload", draft=draft),
            )
        elif kind == "viewport":
            details = self._viewport_details(data=data)
        elif kind == "position_pointer":
            details = self._position_details(data=data)
        else:
            details = self._targeted_details(kind=kind, data=data, draft=draft)
        return details

    def _wait_details(
        self,
        *,
        data: dict[str, JsonValue],
        draft: bool,
    ) -> _EventDetails:
        """Normalize a condition-based wait action.

        Args:
            data: Command payload with the wait condition, value and timeout.
            draft: Whether a blank wait value is tolerated.

        Returns:
            The normalized action fields.

        Raises:
            ValueError: When the timeout or condition is unsupported.

        """
        wait_for: str = self._required_string(data=data, key="wait_for")
        wait_value: str = self._setting(data=data, key="payload", draft=draft)
        timeout_ms: int = int(
            self._required_string(data=data, key="timeout_ms"),
        )
        if timeout_ms < 1 or timeout_ms > Constants.max_wait_ms:
            msg: str = "Wait timeout must be between 1 and 60000 ms."
            raise ValueError(msg)
        if wait_for not in {"element", "text", "url", "expression"}:
            msg = "Wait for an element, text, URL or expression."
            raise ValueError(msg)
        return _EventDetails(
            label=f"Wait for {wait_for}",
            payload=dumps(
                obj={
                    "condition": wait_for,
                    "value": wait_value,
                    "timeout_ms": timeout_ms,
                },
                sort_keys=True,
            ),
        )

    def _http_details(
        self,
        *,
        data: dict[str, JsonValue],
        draft: bool,
    ) -> _EventDetails:
        """Normalize an HTTP request action.

        Args:
            data: Command payload with the request definition.
            draft: Whether a blank URL is tolerated.

        Returns:
            The normalized action fields.

        Raises:
            ValueError: When the HTTP method is unsupported.

        """
        url: str = self._setting(data=data, key="url", draft=draft)
        method: str = self._required_string(data=data, key="method").upper()
        methods: set[str] = {
            "DELETE",
            "GET",
            "HEAD",
            "OPTIONS",
            "PATCH",
            "POST",
            "PUT",
        }
        if method not in methods:
            msg: str = "Choose a supported HTTP method."
            raise ValueError(msg)
        return _EventDetails(
            label=f"{method} {url}" if url else f"{method} request",
            payload=self._required_string(data=data, key="request_config"),
            url=url or None,
            method=method,
        )

    def _websocket_details(
        self,
        *,
        data: dict[str, JsonValue],
        draft: bool,
    ) -> _EventDetails:
        """Normalize an executable WebSocket session action.

        Args:
            data: Command payload with the portable session definition.
            draft: Whether a blank URL is tolerated.

        Returns:
            The normalized action fields.

        Raises:
            ValueError: When the URL cannot address a WebSocket endpoint.

        """
        url: str = self._setting(data=data, key="url", draft=draft)
        if url and (not url.startswith(("ws://", "wss://"))):
            msg: str = "Use a ws:// or wss:// URL for a WebSocket session."
            raise ValueError(msg)
        return _EventDetails(
            label=f"WebSocket {url}" if url else "WebSocket session",
            payload=self._required_string(data=data, key="request_config"),
            url=url or None,
        )

    def _viewport_details(
        self,
        *,
        data: dict[str, JsonValue],
    ) -> _EventDetails:
        """Normalize a rotate or resize action.

        Args:
            data: Command payload with the viewport action and size.

        Returns:
            The normalized action fields.

        Raises:
            ValueError: When the action or size is unsupported.

        """
        action: str = self._required_string(data=data, key="viewport_action")
        if action == "rotate":
            return _EventDetails(
                label="Rotate viewport",
                payload=dumps(obj={"action": action}, sort_keys=True),
            )
        if action != "resize":
            msg: str = "Choose rotate or resize for the viewport action."
            raise ValueError(msg)
        resized: ViewportSize = ViewportSize(
            width=int(self._required_string(data=data, key="width")),
            height=int(self._required_string(data=data, key="height")),
        )
        return _EventDetails(
            label=f"Resize viewport to {resized.width} x {resized.height}",
            payload=dumps(
                obj={
                    "action": action,
                    "width": resized.width,
                    "height": resized.height,
                },
                sort_keys=True,
            ),
        )

    def _position_details(
        self,
        *,
        data: dict[str, JsonValue],
    ) -> _EventDetails:
        """Normalize an absolute pointer action.

        Args:
            data: Command payload with the pointer action and coordinates.

        Returns:
            The normalized action fields.

        """
        action: PositionPointerAction = PositionPointerAction(
            self._required_string(data=data, key="position_action"),
        )
        x: int = int(self._required_string(data=data, key="x"))
        y: int = int(self._required_string(data=data, key="y"))
        operation: str = action.value.replace("_", " ").capitalize()
        return _EventDetails(
            label=f"{operation} at {x}, {y}",
            position_action=action,
            x=x,
            y=y,
        )

    def _targeted_details(
        self,
        *,
        kind: str,
        data: dict[str, JsonValue],
        draft: bool,
    ) -> _EventDetails:
        """Normalize an action that targets one page element.

        Args:
            kind: Action identifier chosen in the library.
            data: Command payload with the selector and action fields.
            draft: Whether a blank selector or payload is tolerated.

        Returns:
            The normalized action fields.

        """
        selector_id: str | None = (
            str(object=data["selector_id"])
            if data.get("selector_id")
            else None
        )
        selector: str | None = (
            None
            if selector_id is not None
            else self._setting(data=data, key="selector", draft=draft) or None
        )
        payload_kinds: set[str] = {
            "drag",
            "extract_value",
            "gesture",
            "input_text",
            "keystroke",
            "scroll",
            "select_option",
        }
        return _EventDetails(
            label=kind.replace("_", " ").capitalize(),
            payload=self._setting(data=data, key="payload", draft=draft)
            if kind in payload_kinds
            else None,
            selector=selector,
            selector_id=selector_id,
        )

    def _command_add_edge(self, data: dict[str, JsonValue]) -> None:
        """Connect two flows using an execution transition.

        Args:
            data: Source, destination and transition policy.

        Raises:
            ValueError: When either flow does not exist.

        """
        edge: FlowEdge = self._editor_edge(data=data)
        self._check_edge_condition(edge=edge)
        try:
            self._store.add_edge(edge=edge)
        except KeyError as error:
            msg: str = "Choose existing flows for this connection."
            raise ValueError(msg) from error
        self._changed()

    def _command_remove_edge(self, data: dict[str, JsonValue]) -> None:
        """Disconnect a saved execution transition.

        Args:
            data: Source, destination and transition policy.

        """
        self._store.remove_edge(edge=self._editor_edge(data=data))
        self._changed()

    def _command_update_edge(self, data: dict[str, JsonValue]) -> None:
        """Redefine a saved transition without changing its position.

        Args:
            data: Position of the transition and its new fields.

        """
        edge: FlowEdge = self._editor_edge(data=data)
        self._check_edge_condition(edge=edge)
        self._store.replace_edge(
            index=int(self._required_string(data=data, key="index")),
            edge=edge,
        )
        self._changed()

    def _check_edge_condition(self, *, edge: FlowEdge) -> None:
        """Reject a connection condition that cannot be evaluated.

        Args:
            edge: The connection about to be saved.

        """
        if edge.condition_expression:
            validate_condition(
                expression=edge.condition_expression,
                selectors=self._store.workspace.selectors,
            )

    def _command_move_edge(self, data: dict[str, JsonValue]) -> None:
        """Move a saved transition to another position in the order.

        Args:
            data: Current and destination positions.

        """
        self._store.move_edge(
            index=int(self._required_string(data=data, key="index")),
            to=int(self._required_string(data=data, key="to")),
        )
        self._changed()

    def _command_delete_event(self, data: dict[str, JsonValue]) -> None:
        """Remove a selected step and its associated evidence.

        Args:
            data: Input bytes or canonical document.

        """
        self._store.delete_event(
            flow_id=self._active_flow_id,
            event_id=self._required_string(data=data, key="event_id"),
        )
        self._changed()

    def _command_duplicate_event(self, data: dict[str, JsonValue]) -> None:
        """Copy a step and place the copy right after it.

        The copy keeps the step's checks and network expectations, with fresh
        identifiers so each stays unique inside the flow.

        Args:
            data: Carries ``event_id`` of the step to copy.

        """
        flow_id: str = self._active_flow_id
        source: TimelineEvent = self._store.get_event(
            flow_id=flow_id,
            event_id=self._required_string(data=data, key="event_id"),
        )
        position: int = next(
            (
                index
                for index, event in enumerate(
                    iterable=self._store.get_flow(flow_id=flow_id).events,
                )
                if event.event_id == source.event_id
            ),
        )
        copy: TimelineEvent = replace(
            source,
            event_id=uuid4().hex,
            expectations=tuple(
                replace(item, expectation_id=uuid4().hex)
                for item in source.expectations
            ),
            contract=replace(
                source.contract,
                preconditions=tuple(
                    replace(item, assertion_id=uuid4().hex)
                    for item in source.contract.preconditions
                ),
                postconditions=tuple(
                    replace(item, assertion_id=uuid4().hex)
                    for item in source.contract.postconditions
                ),
            ),
        )
        appended: TimelineEvent = self._store.append_event(event=copy)
        self._store.place_event(
            flow_id=flow_id,
            event_id=appended.event_id,
            index=position + 1,
        )
        self._changed()

    def _idle_recording(self, *, data: dict[str, JsonValue]) -> str:
        """Return a recording parent that is not capturing right now.

        Args:
            data: Command payload carrying ``recording_id``.

        Returns:
            Identifier of an existing, inactive recording parent.

        Raises:
            ValueError: When the parent is the active capture session.

        """
        recording_id: str = self._required_string(
            data=data,
            key="recording_id",
        )
        if recording_id == self._recording_session_id:
            msg: str = "Stop the recording before changing its parent task."
            raise ValueError(msg)
        return recording_id

    def _command_rename_recording(self, data: dict[str, JsonValue]) -> None:
        """Rename a recording parent task.

        Args:
            data: Recording identifier and nonempty label.

        Raises:
            ValueError: When the label is empty or too long.

        """
        label: str = " ".join(
            self._required_string(data=data, key="label").split(),
        )
        if not label or len(label) > Constants.max_label_length:
            msg: str = "A recording name needs 1 to 80 characters."
            raise ValueError(msg)
        self._store.rename_recording(
            flow_id=self._active_flow_id,
            recording_id=self._idle_recording(data=data),
            label=label,
        )
        self._changed()

    def _command_retime_recording(self, data: dict[str, JsonValue]) -> None:
        """Shift a recording parent and all its actions by one delta.

        Args:
            data: Recording identifier and signed ``delta_ms``.

        Raises:
            TypeError: When ``delta_ms`` is not a whole number.

        """
        delta: JsonValue = data.get("delta_ms")
        if isinstance(delta, bool) or not isinstance(delta, (int, str)):
            msg: str = "delta_ms must be a whole number of milliseconds."
            raise TypeError(msg)
        self._store.shift_recording(
            flow_id=self._active_flow_id,
            recording_id=self._idle_recording(data=data),
            delta_ms=int(delta),
            limit_ms=Constants.max_timeline_ms,
        )
        self._changed()

    def _command_delete_recording(self, data: dict[str, JsonValue]) -> None:
        """Delete a recording parent with its actions as one operation.

        Args:
            data: Recording identifier.

        """
        self._store.delete_recording(
            flow_id=self._active_flow_id,
            recording_id=self._idle_recording(data=data),
        )
        self._changed()

    def _command_move_event(self, data: dict[str, JsonValue]) -> None:
        """Move one step up or down in replay order.

        Args:
            data: Input bytes or canonical document.


        Raises:
            ValueError: When the offset is not ``-1`` or ``1``.

        """
        offset: int = int(self._required_string(data=data, key="offset"))
        if offset not in {-1, 1}:
            msg: str = "Move offset must be -1 or 1."
            raise ValueError(msg)
        self._store.move_event(
            flow_id=self._active_flow_id,
            event_id=self._required_string(data=data, key="event_id"),
            offset=offset,
        )
        self._changed()

    def _command_reorder_event(self, data: dict[str, JsonValue]) -> None:
        """Drop one step at an absolute position in replay order.

        Args:
            data: Input bytes or canonical document.


        Raises:
            ValueError: When the step or index does not exist.

        """
        event_id: str = self._required_string(data=data, key="event_id")
        index: int = int(self._required_string(data=data, key="index"))
        flow: Flow = self._store.get_flow(flow_id=self._active_flow_id)
        if not any(event.event_id == event_id for event in flow.events):
            msg: str = f"Unknown step: {event_id}"
            raise ValueError(msg)
        if not 0 <= index < len(flow.events):
            msg = "Reorder index must name an existing step position."
            raise ValueError(msg)
        self._store.place_event(
            flow_id=self._active_flow_id,
            event_id=event_id,
            index=index,
        )
        self._changed()

    def _command_retime_event(self, data: dict[str, JsonValue]) -> None:
        """Drop one step at a new timeline time and reorder the flow by time.

        Args:
            data: Input bytes or canonical document.


        Raises:
            ValueError: When the step does not exist or the time is invalid.

        """
        event_id: str = self._required_string(data=data, key="event_id")
        elapsed: int = int(self._required_string(data=data, key="elapsed_ms"))
        flow: Flow = self._store.get_flow(flow_id=self._active_flow_id)
        if not any(event.event_id == event_id for event in flow.events):
            msg: str = f"Unknown step: {event_id}"
            raise ValueError(msg)
        if not 0 <= elapsed <= Constants.max_timeline_ms:
            msg = "Timeline time must be between zero and one hour."
            raise ValueError(msg)
        self._store.retime_event(
            flow_id=self._active_flow_id,
            event_id=event_id,
            elapsed_ms=elapsed,
        )
        self._changed()

    def _command_assert_event(self, data: dict[str, JsonValue]) -> None:
        """Attach an explicit browser assertion after the selected action.

        Args:
            data: Input bytes or canonical document.


        Raises:
            ValueError: When the assertion kind is not supported.

        """
        event_id: str = self._required_string(data=data, key="event_id")
        event: TimelineEvent = self._store.get_event(
            flow_id=self._active_flow_id,
            event_id=event_id,
        )
        kind: AssertionKind = AssertionKind(
            self._required_string(data=data, key="kind"),
        )
        if kind not in {
            AssertionKind.DOM_VISIBLE,
            AssertionKind.DOM_TEXT,
            AssertionKind.URL,
            AssertionKind.TITLE,
        }:
            msg: str = "Choose visible element, text, URL, or title."
            raise ValueError(msg)
        if kind is not AssertionKind.DOM_VISIBLE and (
            not str(object=data.get("expected") or "").strip()
        ):
            msg = "Enter the text this check must find."
            raise ValueError(msg)
        assertion: AssertionSpec = AssertionSpec(
            assertion_id=uuid4().hex,
            label=f"Check {kind.value}",
            kind=kind,
            operator=AssertionOperator.EXISTS
            if kind is AssertionKind.DOM_VISIBLE
            else AssertionOperator.CONTAINS,
            target=str(object=data.get("target") or ""),
            selector_id=str(object=data.get("selector_id") or "") or None,
            expected=str(object=data.get("expected") or ""),
        )
        self._store.set_action_contract(
            flow_id=self._active_flow_id,
            event_id=event_id,
            contract=replace(
                event.contract,
                postconditions=(*event.contract.postconditions, assertion),
            ),
        )
        self._changed()

    def _command_remove_assertion(self, data: dict[str, JsonValue]) -> None:
        """Remove a postcondition while preserving the action contract.

        Args:
            data: Input bytes or canonical document.

        Raises:
            ValueError: When the selected check no longer exists.

        """
        event_id: str = self._required_string(data=data, key="event_id")
        assertion_id: str = self._required_string(
            data=data,
            key="assertion_id",
        )
        event: TimelineEvent = self._store.get_event(
            flow_id=self._active_flow_id,
            event_id=event_id,
        )
        remaining: tuple[AssertionSpec, ...] = tuple(
            item
            for item in event.contract.postconditions
            if item.assertion_id != assertion_id
        )
        if len(remaining) == len(event.contract.postconditions):
            msg: str = "Check no longer exists. Select the step again."
            raise ValueError(msg)
        self._store.set_action_contract(
            flow_id=self._active_flow_id,
            event_id=event_id,
            contract=replace(event.contract, postconditions=remaining),
        )
        self._changed()

    def _command_open_screenshot(self, data: dict[str, JsonValue]) -> None:
        """Validate a persisted screenshot before browser preview.

        Args:
            data: Input bytes or canonical document.


        Raises:
            ValueError: When the artifact is missing on disk.

        """
        artifact_id: str = self._required_string(data=data, key="artifact_id")
        artifact: ScreenshotArtifact | None = next(
            (
                item
                for item in self._store.workspace.screenshots
                if item.artifact_id == artifact_id
            ),
            None,
        )
        if artifact is None or not Path(artifact.path).is_file():
            msg: str = (
                "Screenshot file is missing. Run the Flow to capture it again."
            )
            raise ValueError(msg)
        self._persistence.artifact(
            workspace=self._store.workspace,
            artifact_id=artifact_id,
        )

    def _snapshot(self) -> dict[str, JsonValue]:
        """Return snapshot.

        Returns:
            The resulting value.

        """
        workspace: JsonValue = WorkspaceCodec.to_json_value(
            workspace=self._store.workspace,
        )
        return {
            "crawl": dict(self._crawl_state),
            "dirty": self._dirty,
            "saved_path": self._persistence.saved_name,
            "recording_state": self._recording_state,
            "recording_session_id": self._recording_session_id,
            "target_state": self._target_state,
            "target_url": self._target_url,
            "target_inspection": self._target_inspection,
            "revision": self._revision,
            "active_flow_id": self._active_flow_id,
            "device_mode": self._device_mode,
            "profile_schema": WorkspaceCodec.profile_schema(),
            "target_service": self._targets.snapshot(),
            "target_suggestion": self._target_suggestion(),
            "target_address": self._configured_address(),
            "target_check": self._target_check,
            "viewport": {
                "width": self._viewport.width,
                "height": self._viewport.height,
            },
            "recorder_clients": self._clients,
            "execution_run_id": self._execution_state.run_id
            if self._execution_state is not None
            else None,
            "run_control": {
                "state": self._run_control,
                "before_event_id": self._run_held_before,
            },
            "workspace": self._persistence.public_document(value=workspace),
            "selector_test": self._selector_test,
            **selector_view(workspace=self._store.workspace),
            **project_view(
                library=self._library,
                active=self._project,
                workspace=self._store.workspace,
            ),
        }

    def _changed(self, *, dirty: bool = True) -> None:
        """Handle changed.

        Args:
            dirty: Whether the workspace now diverges from disk.

        """
        self._revision += 1
        self._dirty = self._dirty or dirty
        self._persistence.persist_recovery(workspace=self._store.workspace)
        self._bridge.emit_event(
            name="workspace.changed",
            payload=self._snapshot(),
        )

    def _select_flow(self, *, flow_id: str) -> None:
        """Handle select flow.

        Args:
            flow_id: Flow id.

        """
        self._store.get_flow(flow_id=flow_id)
        self._active_flow_id = flow_id
        self._worker.broadcast(
            command=RecorderCommand.active_flow(flow_id=flow_id),
        )
        self._changed()

    def _create_flow(self) -> None:
        """Handle create flow."""
        while True:
            flow_id: str = f"flow-{self._next_flow_number}"
            self._next_flow_number += 1
            if all(
                flow.flow_id != flow_id for flow in self._store.workspace.flows
            ):
                break
        flow: Flow = Flow(
            flow_id=flow_id,
            name=f"Flow {self._next_flow_number - 1}",
            task_description="",
            expected_behavior="",
            notes="",
        )
        self._store.add_flow(flow=flow)
        self._active_flow_id = flow_id
        self._worker.broadcast(
            command=RecorderCommand.active_flow(flow_id=flow_id),
        )
        self._changed()

    def _delete_flow(self, *, flow_id: str) -> None:
        """Handle delete flow.

        Args:
            flow_id: Flow id.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if len(self._store.workspace.flows) <= 1:
            msg: str = "A workspace must retain at least one Flow."
            raise ValueError(msg)
        if (
            self._recording_state != "idle"
            or self._execution_state is not None
        ):
            msg = "Stop recording or playback before deleting a flow."
            raise ValueError(msg)
        self._store.delete_flow(flow_id=flow_id)
        if self._active_flow_id == flow_id:
            self._active_flow_id = self._store.workspace.flows[0].flow_id
        self._changed()

    def _record(self) -> None:
        """Handle record.

        Raises:
            ValueError: When the arguments are invalid.

        """
        if self._execution_state is not None:
            msg: str = "A workflow is running; cancel it before recording."
            raise ValueError(msg)
        flow: Flow = self._store.get_flow(flow_id=self._active_flow_id)
        if self._recording_session_id is not None:
            flow = next(
                candidate
                for candidate in self._store.workspace.flows
                if any(
                    group.recording_id == self._recording_session_id
                    for group in candidate.recordings
                )
            )
        else:
            self._recording_session_id = uuid4().hex
            self._store.add_recording(
                flow_id=flow.flow_id,
                recording=FlowRecording(
                    recording_id=self._recording_session_id,
                    label=f"Recording {len(flow.recordings) + 1}",
                    start_ms=max(
                        (event.elapsed_ms for event in flow.events),
                        default=-1,
                    )
                    + 1,
                ),
            )
            flow = self._store.get_flow(flow_id=flow.flow_id)
        group: FlowRecording = next(
            item
            for item in flow.recordings
            if item.recording_id == self._recording_session_id
        )
        self._recording_state = "recording"
        self._worker.broadcast(
            command=RecorderCommand.record(
                flow_id=flow.flow_id,
                device_mode=self._device_mode,
                capture_images=flow.capture_record_images,
                recording_group_id=group.recording_id,
                recording_start_ms=group.start_ms,
            ),
        )
        self._changed()

    def _require_player(self) -> None:
        """Explain how to connect when the external recorder is missing.

        Raises:
            ValueError: When the recorder is disconnected or the active
                device mode is unsupported.

        """
        if self._crawl_state.get("state") == "running":
            msg = "Finish or cancel discovery before recording or running."
            raise ValueError(msg)
        if not self._clients:
            msg: str = (
                "Open the managed test browser before recording or running."
            )
            raise ValueError(msg)
        flow: Flow = self._store.get_flow(flow_id=self._active_flow_id)
        if (
            DeviceMode.SHARED not in flow.device_modes
            and self._device_mode not in flow.device_modes
        ):
            msg = "Choose a device supported by this Flow."
            raise ValueError(msg)

    def _pause(self) -> None:
        """Handle pause."""
        self._worker.broadcast(
            command=RecorderCommand.pause(flow_id=self._active_flow_id),
        )
        self._recording_state = "paused"
        self._changed(dirty=False)

    def _play(
        self,
        *,
        follow_connections: bool = True,
        inputs: dict[str, str] | None = None,
        flow_inputs: dict[str, str] | None = None,
    ) -> None:
        """Run the active flow, and optionally what its connections lead to.

        Args:
            follow_connections: False runs only the active flow.
            inputs: Values for ``{{ask:Label}}`` tokens, asked per run.
            flow_inputs: Typed text for the flow's own inputs, by name.

        Raises:
            ValueError: When the flow is empty or the device mode is
                unsupported.

        """
        flow: Flow = self._store.get_flow(flow_id=self._active_flow_id)
        if not flow.events:
            msg: str = "Record or add a step before running this Flow."
            raise ValueError(msg)
        unfinished: TimelineEvent | None = next(
            (
                event
                for candidate in (
                    (flow,)
                    if not follow_connections
                    else self._store.workspace.flows
                )
                for event in candidate.events
                if event.incomplete
            ),
            None,
        )
        if unfinished is not None:
            msg = (
                f"Finish setting up "
                f"'{unfinished.label}' in Properties before running."
            )
            raise ValueError(msg)
        if (
            DeviceMode.SHARED not in flow.device_modes
            and self._device_mode not in flow.device_modes
        ):
            msg = "Choose a device supported by this Flow."
            raise ValueError(msg)
        if self._execution_state is not None:
            msg = "A workflow is already running."
            raise ValueError(msg)
        if self._recording_state == "recording":
            msg = "Pause recording before running tests."
            raise ValueError(msg)
        workspace: Workspace = _with_inputs(
            workspace=self._store.workspace,
            inputs=inputs or {},
        )
        state: ExecutionState = ExecutionEngine.start(
            workspace=workspace,
            request=ExecutionStartRequest(
                run_id=uuid4().hex,
                initial_flow_id=flow.flow_id,
                device_mode=self._device_mode,
                started_at_utc=datetime.now(tz=UTC).isoformat(),
                follow_connections=follow_connections,
                supplied_variables=_supplied(
                    flow=flow,
                    answers=flow_inputs or {},
                ),
            ),
        )
        self._execution_workspace = workspace
        self._execution_state = state
        self._dispatch_execution(state=state)

    def _dispatch_execution(self, *, state: ExecutionState) -> None:
        """Dispatch the next flow and retain one combined workflow run.

        Args:
            state: Immutable state produced by the execution engine.

        """
        run: ExecutionRun = ExecutionRun(
            run_id=state.run_id,
            initial_flow_id=state.initial_flow_id,
            current_flow_id=state.current_flow_id,
            device_mode=state.device_mode,
            started_at_utc=state.started_at_utc,
            status=RunStatus.RUNNING,
            action_records=state.action_records,
            transitions=state.transitions,
        )
        self._live_runs.finalize(run=run)
        self._store.upsert_run(run=run)
        self._changed()
        workspace: Workspace = (
            self._execution_workspace or self._store.workspace
        )
        self._worker.broadcast_dispatch(
            request=FlowDispatchRequest(
                run_id=state.run_id,
                flow=next(
                    flow
                    for flow in workspace.flows
                    if flow.flow_id == state.current_flow_id
                ),
                device_mode=state.device_mode,
                variables=state.variables,
                origin=self._store.workspace.target.origin(
                    service_url=self._targets.base_url,
                ),
                selectors=workspace.selectors,
                probes=edge_probe_names(
                    workspace=workspace,
                    flow_id=state.current_flow_id,
                ),
                project_id=self._project,
                project_name=workspace.project.name,
                project_revision=workspace.project.version,
                context_base_url=workspace.target.address(),
            ),
        )

    def _open_workspace(self, *, data: dict[str, JsonValue]) -> None:
        """Import a validated current-schema workspace without file dialogs.

        Args:
            data: Uploaded workspace document or safe project filename.

        Raises:
            ValueError: When the arguments are invalid.

        """
        workspace: Workspace = self._persistence.open(data=data)
        if not workspace.flows:
            msg: str = "A workspace must contain at least one Flow."
            raise ValueError(msg)
        if self._recording_session_id is not None:
            self._pause()
        self._recording_state = "idle"
        self._recording_session_id = None
        self._store.replace_workspace(workspace=workspace)
        self._targets.stop()
        self._target_check = None
        self._active_flow_id = workspace.flows[0].flow_id
        if self._device_mode != DeviceMode.CUSTOM and all(
            item.profile_id != self._device_mode for item in workspace.profiles
        ):
            self._device_mode = workspace.profiles[0].profile_id
        self._show()
        self._dirty = "workspace" in data
        self._changed(dirty=self._dirty)

    def _save_workspace(self, *, data: dict[str, JsonValue]) -> None:
        """Atomically save the workspace within the explicit project root.

        Args:
            data: Optional relative project filename.

        """
        self._persistence.save(workspace=self._store.workspace, data=data)
        self._dirty = False
        self._changed(dirty=False)

    def _receive_event(self, *, event: TimelineEvent) -> None:
        """Handle receive event.

        Args:
            event: Event.

        """
        self._store.append_event(event=event)
        self._changed()

    def _receive_screenshot(self, *, artifact: ScreenshotArtifact) -> None:
        """Handle receive screenshot.

        Args:
            artifact: Artifact.

        """
        self._store.add_screenshot(artifact=artifact)
        self._changed()

    def _receive_expectation_result(
        self,
        *,
        result: ExpectationResult,
    ) -> None:
        """Handle receive expectation result.

        Args:
            result: Result.

        """
        self._bridge.emit_event(
            name="expectation.result",
            payload={
                "expectation_id": result.expectation_id,
                "outcome": result.outcome.value,
            },
        )

    def _receive_flow_result(self, *, result: FlowExecutionResult) -> None:
        """Handle receive flow result.

        Args:
            result: Result.

        """
        state: ExecutionState | None = self._execution_state
        if state is not None and result.run_id == state.run_id:
            try:
                decision: ExecutionDecision = ExecutionEngine.complete_flow(
                    workspace=self._execution_workspace
                    or self._store.workspace,
                    state=state,
                    result=result,
                    finished_at_utc=datetime.now(tz=UTC).isoformat(),
                )
            except ExecutionError as error:
                self._fail_execution(message=str(object=error))
                return
            self._execution_state = decision.state
            if decision.state is not None:
                self._dispatch_execution(state=decision.state)
            elif decision.completed_run is not None:
                self._store.upsert_run(
                    run=self._live_runs.finalize(run=decision.completed_run),
                )
                self._execution_workspace = None
                self._end_run_control()
                self._changed()
        self._bridge.emit_event(
            name="flow.result",
            payload={
                "flow_id": result.flow_id,
                "status": result.status.value,
                "error": result.error,
            },
        )

    def _fail_execution(self, *, message: str) -> None:
        """Finish an interrupted workflow without losing accumulated evidence.

        Args:
            message: Failure reason displayed in the run inspector.

        """
        state: ExecutionState | None = self._execution_state
        if state is None:
            return
        run: ExecutionRun | None = self._live_runs.get(run_id=state.run_id)
        if run is not None:
            self._store.upsert_run(
                run=self._live_runs.finalize(
                    run=replace(
                        run,
                        status=RunStatus.FAILED,
                        finished_at_utc=datetime.now(tz=UTC).isoformat(),
                        failure_reason=message,
                    ),
                ),
            )
        self._execution_state = None
        self._execution_workspace = None
        self._end_run_control()
        self._changed()
        self._bridge.emit_event(
            name="flow.result",
            payload={"status": "failed", "error": message},
        )

    def _receive_checkpoint(self, *, artifact: CheckpointArtifact) -> None:
        """Handle receive checkpoint.

        Args:
            artifact: Artifact.

        """
        self._store.add_checkpoint_artifact(artifact=artifact)
        self._changed()

    def _receive_run_progress(self, *, progress: RunProgress) -> None:
        """Handle receive run progress.

        Args:
            progress: Progress.

        """
        if (
            self._execution_state is not None
            and progress.run_id == self._execution_state.run_id
            and (progress.message_type == "run_finished")
        ):
            return
        run: ExecutionRun = self._live_runs.accept(
            progress=progress,
            device_mode=self._device_mode,
        )
        self._store.upsert_run(run=run)
        self._changed()

    def _set_client_count(self, *, count: int) -> None:
        """Handle set client count.

        Args:
            count: Count.

        """
        self._clients = count
        if count == 0 and self._execution_state is not None:
            self._fail_execution(
                message="Test browser disconnected during the workflow.",
            )
        self._changed()

    def _protocol_error(self, *, message: str) -> None:
        """Handle protocol error.

        Args:
            message: Message.

        """
        self._bridge.emit_event(
            name="protocol.error",
            payload={"message": message},
        )
