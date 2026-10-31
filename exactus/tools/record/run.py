# Copyright (c) 2026 Project contributors
"""Run saved Studio flows as unattended functional tests and captures."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from json import dumps, loads
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Final, Literal, cast, final
from uuid import uuid4
from xml.etree.ElementTree import Element, SubElement, tostring

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.tools.record.diagnostics import DiagnosticCollector
from exactus.tools.record.execution import (
    ExecutionDecision,
    ExecutionEngine,
    ExecutionStartRequest,
    ExecutionState,
)
from exactus.tools.record.flow_runner import FlowRunner
from exactus.tools.record.model import (
    DeviceMode,
    FlowExecutionResult,
    RunStatus,
)
from exactus.tools.record.profile_emulation import (
    ProfileEmulator,
    context_options,
)
from exactus.tools.record.recorder_protocol import RecorderProtocol
from exactus.tools.record.store import Workspace, WorkspaceCodec

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from collections.abc import Callable

    from exactus.tools.record.json_types import JsonValue
    from exactus.tools.record.model import Flow, Profile
    from exactus.tools.record.recorder_protocol import RecorderInbound
    from exactus.tools.record.workspace_actions import Event


@final
class Constants:
    """Group module-level constants.

    Attributes:
        mobile_max_width: Grouped module constant.
        tablet_max_width: Grouped module constant.

    """

    mobile_max_width: Final[int] = 600
    tablet_max_width: Final[int] = 1100


@dataclass(frozen=True)
class BrowserOptions:
    """Browser viewport and capture options.

    Attributes:
        width: Width recorded by this structure.
        height: Height recorded by this structure.
        headless: Headless recorded by this structure.
        screenshots: Screenshots recorded by this structure.
        scale: Screenshot device scale.
        timeout_ms: Maximum wait for each browser action.
        color_scheme: Browser light or dark preference.
        is_mobile: Enable mobile viewport emulation.
        has_touch: Enable browser touch events.
        cancelled: Optional cooperative cancellation predicate.
        emit: Optional observer of completed replay steps.
        workers: Maximum concurrent independent workflows; one is serial.

    """

    width: int = 1440
    height: int = 900
    headless: bool = True
    screenshots: bool = False
    scale: float = 1.0
    timeout_ms: float = 5000
    color_scheme: Literal["light", "dark"] = "light"
    is_mobile: bool = False
    has_touch: bool = False
    cancelled: Callable[[], bool] | None = None
    emit: Callable[[Event], None] | None = None
    workers: int = 4


@dataclass(slots=True)
class ReplayProgress:
    """Count completed replay events without counting retry attempts twice.

    Attributes:
        observer: Receiver of normalized progress messages.
        total: Number of saved workflow events.
        completed: Number of distinct attempted events.
        seen: Event identities already counted.
        lock: Serialize counters and observer calls across workers.

    """

    observer: Callable[[Event], None] | None
    total: int
    completed: int = 0
    seen: set[str] = field(default_factory=set)
    lock: Lock = field(default_factory=Lock, repr=False)

    def __call__(self, event: Event) -> None:
        """Report each attempted event once.

        Args:
            event: Player event.

        """
        if event.get("type") != "action_result":
            return
        record: JsonValue = event.get("action_record")
        identity: str = f"{event.get('run_id')}/{event.get('flow_id')}/"
        if isinstance(record, dict):
            identity += str(object=record.get("event_id"))
        with self.lock:
            if identity not in self.seen:
                self.seen.add(identity)
                self.completed += 1
            if self.observer is not None:
                self.observer(
                    {
                        "type": "frontend_progress",
                        "completed": self.completed,
                        "total": max(self.total, self.completed, 1),
                        "step": "Replay steps",
                        "detail": identity,
                    },
                )


@dataclass(slots=True)
class WorkflowProgress:
    """Aggregate independent workflow progress without premature completion.

    Attributes:
        observer: Receiver of combined replay progress.
        budgets: Reachable action count for each independent entry point.
        completed: Distinct action identities completed by each entry.
        finished: Entry points whose connected replay has returned.
        active: Current action or terminal status for each started entry.
        lock: Serialize state changes and observer publication.

    """

    observer: Callable[[Event], None] | None
    budgets: dict[str, int]
    completed: dict[str, set[str]] = field(default_factory=dict)
    finished: set[str] = field(default_factory=set)
    active: dict[str, str] = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock, repr=False)

    def __call__(self, event: Event) -> None:
        """Publish one combined fraction after an action or workflow finishes.

        Args:
            event: Worker event carrying its independent entry identity.

        """
        kind: JsonValue = event.get("type")
        if kind not in {
            "action_started",
            "action_result",
            "workflow_started",
            "workflow_finished",
        }:
            return
        entry: str = str(object=event.get("workflow_entry"))
        with self.lock:
            if kind == "workflow_finished":
                self.finished.add(entry)
                self.active[entry] = str(object=event.get("status", "done"))
            elif kind == "workflow_started":
                self.active[entry] = "starting browser"
            elif kind == "action_started":
                self.active[entry] = str(
                    object=event.get("event_id", "action"),
                )
            else:
                record: JsonValue = event.get("action_record")
                if not isinstance(record, dict):
                    return
                run_id: JsonValue = event.get("run_id")
                flow_id: JsonValue = event.get("flow_id")
                event_id: JsonValue = record.get("event_id")
                identity: str = f"{run_id}/{flow_id}/{event_id}"
                self.completed.setdefault(entry, set()).add(identity)
            total: int = sum(self.budgets.values())
            work: float = sum(
                (
                    (
                        budget
                        if lane in self.finished
                        else min(len(self.completed.get(lane, set())), budget)
                        * 0.98
                    )
                    for lane, budget in self.budgets.items()
                ),
            )
            workers: dict[str, JsonValue] = {
                lane: {
                    "completed": len(self.completed.get(lane, set())),
                    "total": max(budget, len(self.completed.get(lane, set()))),
                    "finished": lane in self.finished,
                    "progress": round(
                        number=(
                            1.0
                            if lane in self.finished
                            else min(
                                len(self.completed.get(lane, set())),
                                budget,
                            )
                            / budget
                            * 0.98
                        ),
                        ndigits=6,
                    ),
                    "action": self.active.get(lane, "waiting"),
                }
                for lane, budget in self.budgets.items()
            }
            if self.observer is not None:
                completed: int = len(self.completed.get(entry, set()))
                budget: int = self.budgets.get(entry, 1)
                self.observer(
                    {
                        "type": "frontend_progress",
                        "workers": workers,
                        "completed": len(self.finished),
                        "total": len(self.budgets),
                        "fraction": work / max(total, 1),
                        "step": "Replay workflows",
                        "detail": (
                            f"{len(self.finished)}/{len(self.budgets)}"
                            f" workflows finished; {entry}:"
                            f" {completed}/{budget}"
                            f" steps; {self.active.get(entry, 'waiting')}"
                        ),
                    },
                )


def _workflow_size(*, workspace: Workspace, entry: Flow) -> int:
    """Count reachable actions separately for each independent replay.

    Args:
        workspace: Saved flow graph.
        entry: Independent entry point whose connections will be replayed.

    Returns:
        Positive action budget including reachable connected flows.

    """
    reachable: set[str] = {entry.flow_id}
    pending: list[str] = [entry.flow_id]
    while pending:
        current: str = pending.pop()
        for edge in workspace.edges:
            if (
                edge.source_flow_id == current
                and edge.target_flow_id not in reachable
            ):
                reachable.add(edge.target_flow_id)
                pending.append(edge.target_flow_id)
    return max(
        sum(
            len(flow.events)
            for flow in workspace.flows
            if flow.flow_id in reachable
        ),
        1,
    )


@dataclass(frozen=True)
class WorkflowCapture:
    """Group workflow artifact and browser settings.

    Attributes:
        output: Destination for screenshots and results.
        browser: Viewport and capture policy.
        evidence: Collection receiving runtime telemetry.
        diagnostics: Browser diagnostic collector for this workflow.
        profile: Profile the entry flow is scoped to, when it has one.
        emulator: Keeps the profile's device emulation after screenshots.

    """

    output: Path
    browser: BrowserOptions
    evidence: list[JsonValue]
    diagnostics: DiagnosticCollector
    profile: Profile | None = None
    emulator: ProfileEmulator | None = None


def _entry_mode(*, capture: WorkflowCapture, initial_flow: Flow) -> str:
    """Name the device scope a workflow runs under.

    Args:
        capture: Artifact, viewport and profile settings.
        initial_flow: Entry point selected for this test.

    Returns:
        The scoped profile's ID, ``custom`` for a legacy custom scope, or the
        built-in size class of the command-line viewport.

    """
    if capture.profile is not None:
        return capture.profile.profile_id
    if (
        DeviceMode.CUSTOM in initial_flow.device_modes
        and DeviceMode.SHARED not in initial_flow.device_modes
    ):
        return DeviceMode.CUSTOM
    if capture.browser.width <= Constants.mobile_max_width:
        return DeviceMode.MOBILE
    if capture.browser.width <= Constants.tablet_max_width:
        return DeviceMode.TABLET
    return DeviceMode.DESKTOP


def _device_restorer(
    *,
    capture: WorkflowCapture,
) -> Callable[[Page], None] | None:
    """Return the hook that keeps device emulation after screenshots.

    Args:
        capture: Artifact, viewport and profile settings.

    Returns:
        A restoring callback, or None when no profile is emulated.

    """
    emulator: ProfileEmulator | None = capture.emulator
    profile: Profile | None = capture.profile
    if emulator is None or profile is None:
        return None

    def restore(shot: Page) -> None:
        """Put touch emulation back after a full-page screenshot.

        Args:
            shot: Page that was just captured.

        """
        emulator.restore(page=shot, profile=profile)

    return restore


def _run_chain(
    *,
    page: Page,
    workspace: Workspace,
    initial_flow: Flow,
    capture: WorkflowCapture,
) -> Event:
    """Execute a connected workflow in one browser context.

    Args:
        page: Browser page shared by connected flows.
        workspace: Saved graph and action definitions.
        initial_flow: Entry point selected for this test.
        capture: Artifact, viewport and telemetry settings.

    Returns:
        Combined action results and transitions for one workflow test.

    Raises:
        TypeError: When the player emits an invalid flow result.

    """
    mode: str = _entry_mode(capture=capture, initial_flow=initial_flow)
    initial_state: ExecutionState = ExecutionEngine.start(
        workspace=workspace,
        request=ExecutionStartRequest(
            run_id=uuid4().hex,
            initial_flow_id=initial_flow.flow_id,
            device_mode=mode,
            started_at_utc=datetime.now(tz=UTC).isoformat(),
        ),
    )
    state: ExecutionState | None = initial_state
    run_id: str = initial_state.run_id
    records: list[JsonValue] = []

    def emit(message: Event) -> None:
        """Collect execution evidence and attribute browser diagnostics.

        Args:
            message: Single execution or progress event.

        """
        capture.evidence.append(message)
        if capture.browser.emit is not None:
            capture.browser.emit(message)
        if message.get("type") == "action_started":
            capture.diagnostics.phase(
                phase="action",
                action=f"{message.get('flow_id')}/{message.get('event_id')}",
            )

    while state is not None:
        flow: Flow = next(
            flow
            for flow in workspace.flows
            if flow.flow_id == state.current_flow_id
        )
        result: Event = FlowRunner(
            output=capture.output,
            emit=emit,
            timeout_ms=capture.browser.timeout_ms,
            cancelled=capture.browser.cancelled,
            after_capture=_device_restorer(capture=capture),
        ).run(
            page=page,
            message={
                "run_id": state.run_id,
                "origin": workspace.target.origin(),
                "flow_id": flow.flow_id,
                "name": flow.name,
                "capture_images": (
                    capture.browser.screenshots or flow.capture_play_images
                ),
                "parameters": [
                    parameter.name for parameter in flow.parameters
                ],
                "outputs": [item.name for item in flow.outputs],
                "events": [
                    WorkspaceCodec.event_to_json_value(event=event)
                    for event in flow.events
                ],
            },
        )
        decoded: RecorderInbound = RecorderProtocol.decode_message(
            line=dumps(obj=result).encode(encoding="utf-8"),
        )
        if not isinstance(decoded, FlowExecutionResult):
            msg: str = "Player did not return a flow result."
            raise TypeError(msg)
        raw_records: JsonValue = result.get("action_records")
        if isinstance(raw_records, list):
            records.extend(raw_records)
        decision: ExecutionDecision = ExecutionEngine.complete_flow(
            workspace=workspace,
            state=state,
            result=decoded,
            finished_at_utc=datetime.now(tz=UTC).isoformat(),
        )
        state = decision.state
        if decision.completed_run is not None:
            return {
                "run_id": run_id,
                "flow_id": initial_flow.flow_id,
                "status": decision.completed_run.status.value,
                "error": decision.completed_run.failure_reason,
                "action_records": records,
                "transitions": [
                    {
                        "source": transition.source_flow_id,
                        "target": transition.target_flow_id,
                        "mode": transition.mode.value,
                    }
                    for transition in decision.completed_run.transitions
                ],
            }
    return {"flow_id": initial_flow.flow_id, "status": RunStatus.FAILED.value}


def scoped_profile(*, workspace: Workspace, flow: Flow) -> Profile | None:
    """Find the profile an entry flow is scoped to.

    Args:
        workspace: Saved project with its profiles.
        flow: Entry point about to run.

    Returns:
        The profile when the flow targets exactly one saved profile; None for
        shared flows, which use the command-line browser options.

    """
    scopes: frozenset[str] = frozenset(flow.device_modes) - {
        DeviceMode.SHARED,
        DeviceMode.CUSTOM,
    }
    if len(scopes) != 1:
        return None
    (scope,) = scopes
    return next(
        (item for item in workspace.profiles if item.profile_id == scope),
        None,
    )


def _run_entry(
    *,
    flow: Flow,
    workspace: Workspace,
    output: Path,
    url: str | None,
    browser: BrowserOptions,
) -> tuple[Event, list[JsonValue]]:
    """Replay one connected workflow with thread-local browser resources.

    Args:
        flow: Independent workflow entry point.
        workspace: Saved graph shared for read-only execution.
        output: Destination for uniquely identified run artifacts.
        url: Optional initial application URL.
        browser: Browser configuration and synchronized progress observer.

    Returns:
        Workflow result and its ordered runtime evidence.

    """
    evidence: list[JsonValue] = []
    with sync_playwright() as playwright:
        browser_instance: Browser = playwright.chromium.launch(
            headless=browser.headless,
        )
        try:
            profile: Profile | None = scoped_profile(
                workspace=workspace,
                flow=flow,
            )
            emulator: ProfileEmulator = ProfileEmulator()
            context: BrowserContext = (
                browser_instance.new_context(
                    **context_options(profile=profile),
                )
                if profile is not None
                else browser_instance.new_context(
                    color_scheme=browser.color_scheme,
                    is_mobile=browser.is_mobile,
                    has_touch=browser.has_touch,
                    device_scale_factor=browser.scale,
                    viewport={
                        "width": browser.width,
                        "height": browser.height,
                    },
                )
            )
            collector: DiagnosticCollector = DiagnosticCollector(
                variant=flow.flow_id,
            )
            try:
                page: Page = context.new_page()
                if profile is not None:
                    emulator.apply(page=page, profile=profile)
                collector.attach_sync(page=page)
                page.set_default_navigation_timeout(timeout=browser.timeout_ms)
                if url:
                    page.goto(url=url)
                result: Event = _run_chain(
                    page=page,
                    workspace=workspace,
                    initial_flow=flow,
                    capture=WorkflowCapture(
                        output=output,
                        browser=browser,
                        evidence=evidence,
                        diagnostics=collector,
                        profile=profile,
                        emulator=emulator,
                    ),
                )
            except (
                PlaywrightError,
                TimeoutError,
                ValueError,
                TypeError,
                RuntimeError,
                OSError,
            ) as error:
                result = cast(
                    typ="Event",
                    val={
                        "flow_id": flow.flow_id,
                        "status": "failed",
                        "error": str(object=error),
                        "action_records": cast(typ="list[JsonValue]", val=[]),
                    },
                )
            finally:
                context.close()
            result["diagnostics"] = [
                DiagnosticCollector.serialize(event=event)
                for event in collector.events
            ]
            return (result, evidence)
        finally:
            browser_instance.close()


def run_workspace(
    *,
    path: Path,
    output: Path,
    flow_id: str | None = None,
    url: str | None = None,
    browser: BrowserOptions | None = None,
) -> Event:
    """Run workflow entry points and their saved connections.

    Write JSON and JUnit evidence to ``output``.

    Args:
        path: Workspace JSON file to replay.
        output: Directory receiving ``result.json`` and ``junit.xml``.
        flow_id: Optional entry flow ID; omit to run workflow entry points.
        url: Optional initial page; recorded navigations still execute.
        browser: Viewport and capture options.

    Returns:
        Report as an ``Event`` payload.

    Raises:
        ValueError: When workers is not positive or the flow is missing.

    """
    browser = browser or BrowserOptions()
    if browser.workers < 1:
        msg = "Workflow workers must be positive."
        raise ValueError(msg)
    workspace: Workspace = WorkspaceCodec.from_json_value(
        value=loads(s=path.read_text(encoding="utf-8")),
    )
    destinations: set[str] = {
        edge.target_flow_id
        for edge in workspace.edges
        if edge.source_flow_id != edge.target_flow_id
    }
    flows: list[Flow] = [
        flow
        for flow in workspace.flows
        if flow.flow_id == flow_id
        or (flow_id is None and flow.flow_id not in destinations)
    ]
    if flow_id is None and (not flows):
        flows = list(workspace.flows[:1])
    if not flows:
        msg: str = f"Flow {flow_id!r} not found in {path}"
        raise ValueError(msg)
    output.mkdir(parents=True, exist_ok=True)
    results: list[Event] = []
    evidence: list[JsonValue] = []
    progress: WorkflowProgress = WorkflowProgress(
        observer=browser.emit,
        budgets={
            flow.flow_id: _workflow_size(workspace=workspace, entry=flow)
            for flow in flows
        },
    )

    def run_entry(flow: Flow) -> tuple[Event, list[JsonValue]]:
        """Execute an entry without sharing Playwright objects between threads.

        Args:
            flow: Workflow entry selected by this run.

        Returns:
            Result and local runtime evidence.

        """

        def emit_event(event: Event) -> None:
            """Attribute step progress to its independent workflow worker.

            Args:
                event: Player event from this worker.

            """
            progress(event={**event, "workflow_entry": flow.flow_id})

        progress(
            event={"type": "workflow_started", "workflow_entry": flow.flow_id},
        )
        result: tuple[Event, list[JsonValue]] = _run_entry(
            flow=flow,
            workspace=workspace,
            output=output,
            url=url,
            browser=replace(browser, emit=emit_event),
        )
        progress(
            event={
                "type": "workflow_finished",
                "workflow_entry": flow.flow_id,
                "status": result[0].get("status"),
            },
        )
        return result

    executor: ThreadPoolExecutor = ThreadPoolExecutor(
        max_workers=min(browser.workers, len(flows)),
        thread_name_prefix="exactus-flow",
    )
    with executor:
        for result, flow_evidence in executor.map(run_entry, flows):
            results.append(result)
            evidence.extend(flow_evidence)
    was_cancelled: bool
    failures: int = sum(result["status"] == "failed" for result in results)
    was_cancelled = any(result["status"] == "cancelled" for result in results)
    report: Event = {
        "status": (
            "cancelled"
            if was_cancelled
            else "failed"
            if failures
            else "succeeded"
        ),
        "flows": cast(typ="JsonValue", val=results),
        "evidence": evidence,
    }
    (output / "result.json").write_text(
        data=dumps(obj=report, indent=2) + "\n",
        encoding="utf-8",
    )
    suite: Element[str] = Element(
        "testsuite",
        name="Flow Studio",
        tests=str(object=len(results)),
        failures=str(object=failures),
    )
    for result in results:
        case: Element[str] = SubElement(
            suite,
            "testcase",
            classname="flow_studio",
            name=str(object=result["flow_id"]),
        )
        if result["status"] == "cancelled":
            SubElement(case, "skipped", message="Workflow cancelled")
        if result["status"] == "failed":
            SubElement(
                case,
                "failure",
                message=str(object=result.get("error") or "Flow failed"),
            ).text = dumps(obj=result, indent=2)
    (output / "junit.xml").write_text(
        data=tostring(element=suite, encoding="unicode") + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    """Run Studio workspaces from the command line.

    Returns:
        Exit status: ``1`` if any flow failed, otherwise ``0``.

    """
    parser: ArgumentParser = ExactusArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--flow",
        help="Entry flow ID; omit to test workflow entry points",
    )
    parser.add_argument(
        "--url",
        help="Optional initial page; recorded navigations still execute",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("EXACTUS_RESULTS/FLOWS"),
    )
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--screenshots",
        action="store_true",
        help="Capture every executed step",
    )
    args: Namespace = parser.parse_args()
    if args.workers <= 0:
        parser.error(message="Workflow workers must be positive.")
    if args.width <= 0 or args.height <= 0:
        parser.error(message="Viewport dimensions must be positive.")
    report: Event = run_workspace(
        path=args.workspace,
        output=args.output,
        flow_id=args.flow,
        url=args.url,
        browser=BrowserOptions(
            width=args.width,
            height=args.height,
            headless=not args.headed,
            screenshots=args.screenshots,
            workers=args.workers,
        ),
    )
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
