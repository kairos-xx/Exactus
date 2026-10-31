# Copyright (c) 2026
"""Run canonical exactus tools in detached pmanager workers."""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from json import JSONDecodeError, loads
from os import chdir, environ, getpid, pathsep
from pathlib import Path
from sys import executable
from sys import path as import_paths
from time import monotonic
from traceback import format_exc
from typing import TYPE_CHECKING, Final, TypedDict, cast, final

from exactus.packages.pmanager import (
    Executor,
    ProcessClass,
    ProcessPolicy,
    ProcessStatus,
    Spec,
    State,
    cancel,
    kill,
    pause,
    receive,
    reset,
    resume,
    status,
)
from exactus.packages.pmanager.api import ProcessKey
from exactus.packages.pmanager.runtime import Client, Descriptor, Discovery
from exactus.tools.common.cli import activate_exactus_tool_bundle
from exactus.tools.common.execution import (
    CrashDetails,
    ExactusRunIds,
    crashed_exactus,
    execute_exactus,
    release_dependency_workers,
)
from exactus.tools.common.models import ToolRequest, ToolRunResult
from exactus.tools.common.process_control import terminate_tree
from exactus.tools.common.process_layer.access import (
    runtime_dir,
    start_responder,
    stop_responder,
)
from exactus.tools.common.registry import run_context
from exactus.tools.common.runtime import (
    checkpoint_status,
    release_checkpoint_pause,
    request_checkpoint_pause,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping
    from types import ModuleType

    from exactus.packages.pmanager.runtime import JsonValue
    from exactus.tools.common.catalog import ToolSpec
    from exactus.tools.common.process_layer.process_control import (
        IdentityResponder,
    )
    from exactus.tools.common.registry import RunRecord


@final
class Constants:
    """Group module-level constants.

    Attributes:
        repo_root: Grouped module constant.
        terminal: Grouped module constant.

    """

    repo_root: Final[Path] = Path(__file__).resolve().parents[3]
    terminal: Final[frozenset[State]] = frozenset(
        {State.COMPLETED, State.FAILED, State.KILLED, State.CANCELLED},
    )


class WorkerRequest(TypedDict):
    """Describe the JSON-compatible arguments passed to a tool worker.

    Attributes:
        identifier: Canonical catalog tool identifier.
        module: Importable module containing the tool entry point.
        output: Tool report directory relative to the project root.
        arguments: Command-line arguments forwarded to the tool.
        run_id: Unique task/process run identifier.
        pipeline_run_id: Parent pipeline run identifier, when applicable.
        project_root: Project root shared by the workspace context.

    """

    identifier: str
    module: str
    output: str
    arguments: list[str]
    run_id: str
    pipeline_run_id: str | None
    project_root: str | None


def ensure_worker_path() -> None:
    """Expose this checkout to detached pmanager runtime processes."""
    root: str = str(object=Constants.repo_root)
    values: list[str] = [
        value
        for value in environ.get("PYTHONPATH", "").split(sep=pathsep)
        if value
    ]
    if root not in values:
        values.insert(0, root)
        environ["PYTHONPATH"] = pathsep.join(values)


def tool_context(*, root: Path, owner: str) -> str:
    """Return a run context nested under the project-root hash.

    Args:
        root: Project root shared by every participating invocation.
        owner: Pipeline or standalone run identity.

    Returns:
        Stable nested project/run context.

    """
    return run_context(root=root, owner=owner)


def build_spec(*, tools: Iterable[ToolSpec], root: Path) -> Spec:
    """Build the detached worker specification for participating tools.

    Args:
        tools: Catalog tools participating in the run.
        root: Project directory used as the worker subprocess cwd.

    Returns:
        Object-first pmanager specification.

    Catalog dependency edges are deliberately not declared as pmanager
    ``depends_on`` refs: the pipeline supervisor already schedules a tool
    only once its dependencies settle, and pmanager treats a failed
    dependency as a reason to abort the dependent — an exactus tool that
    finishes with findings must never block the tools behind it.

    """
    specification: Spec = Spec(version=3)
    executor: Executor = Executor(
        type_="python_class",
        command=(
            executable,
            "-m",
            "exactus.packages.pmanager.class_runner",
            ExactusTool.__module__,
            ExactusTool.__qualname__,
        ),
        cwd=str(object=root.resolve()),
    )
    tool: ToolSpec
    for tool in tools:
        specification.process(
            name=tool.identifier,
            executor=executor,
            policy=ProcessPolicy(values={"on_create": {"running": "reuse"}}),
        )
    return specification


def worker_arguments(
    *,
    request: ToolRequest,
    spec: ToolSpec,
) -> tuple[tuple[JsonValue, ...], dict[str, JsonValue]]:
    """Encode one exactus request as structured ProcessClass arguments.

    Args:
        request: Tool invocation request.
        spec: Catalog tool definition.

    Returns:
        Positional and keyword values accepted by ``Context.create``.

    """
    return (
        (),
        {
            "request": cast(
                typ="dict[str, JsonValue]",
                val=WorkerRequest(
                    identifier=request.identifier,
                    module=spec.module,
                    output=str(object=request.output),
                    arguments=list(request.arguments),
                    run_id=request.run_id,
                    pipeline_run_id=request.pipeline_run_id,
                    project_root=str(object=request.project_root)
                    if request.project_root is not None
                    else None,
                ),
            ),
        },
    )


def _process_status(
    *,
    descriptor: Descriptor,
    payload: Mapping[str, JsonValue],
) -> ProcessStatus:
    """Convert one IPC info response into the public status model.

    Args:
        descriptor: Discovered worker descriptor.
        payload: Response from the worker's ``info`` command.

    Returns:
        Typed process status.

    """
    raw_state: JsonValue = payload.get("state", State.STARTING.value)
    try:
        state: State = State(str(object=raw_state))
    except ValueError:
        state = State.STARTING
    raw_exit: JsonValue = payload.get("exit_code")
    raw_progress: JsonValue = payload.get("progress", 0)
    raw_attempts: JsonValue = payload.get("attempts", 0)
    raw_generation: JsonValue = payload.get("generation", 1)
    raw_children: JsonValue = payload.get("children", {})
    return ProcessStatus(
        key=ProcessKey(
            name=descriptor.name,
            context=descriptor.context,
            arguments=descriptor.args,
        ),
        state=state,
        progress=int(raw_progress)
        if isinstance(raw_progress, (int, float))
        and (not isinstance(raw_progress, bool))
        else 0,
        pid=descriptor.pid,
        reason=str(object=payload.get("reason", "")),
        exit_code=int(raw_exit)
        if isinstance(raw_exit, (int, float))
        and (not isinstance(raw_exit, bool))
        else None,
        attempts=int(raw_attempts)
        if isinstance(raw_attempts, (int, float))
        and (not isinstance(raw_attempts, bool))
        else 0,
        generation=int(raw_generation)
        if isinstance(raw_generation, (int, float))
        and (not isinstance(raw_generation, bool))
        else 1,
        children=raw_children if isinstance(raw_children, dict) else {},
        custom_status=payload.get("custom_status"),
    )


def live_status(
    *,
    descriptors: Iterable[Descriptor],
    name: str,
    context: str,
) -> ProcessStatus | None:
    """Return live worker status without treating IPC timeouts as death.

    Args:
        descriptors: One shared discovery snapshot for the polling tick.
        name: Process name.
        context: Process context.

    Returns:
        Current status, or ``None`` when discovery proves the worker gone.

    """
    descriptor: Descriptor | None = next(
        (
            item
            for item in descriptors
            if item.name == name and item.context == context
        ),
        None,
    )
    if descriptor is None:
        return None
    try:
        payload: dict[str, JsonValue] = Client.request(
            descriptor=descriptor,
            command="info",
        )
    except OSError:
        payload = {"state": State.STARTING.value}
    return _process_status(descriptor=descriptor, payload=payload)


def _fallback_result(
    *,
    request: ToolRequest,
    process_status: ProcessStatus | None,
    elapsed_seconds: float,
) -> ToolRunResult:
    """Build defaults used while reconstructing a report-backed result.

    Args:
        request: Tool invocation request.
        process_status: Last observed worker status.
        elapsed_seconds: Worker wall time.

    Returns:
        Failed or successful fallback result.

    """
    succeeded: bool = (
        process_status is not None and process_status.state is State.COMPLETED
    )
    return ToolRunResult(
        tool=request.identifier,
        run_id=request.run_id,
        pipeline_run_id=request.pipeline_run_id,
        status="PASS" if succeeded else "FAIL",
        passed=succeeded,
        exit_code=process_status.exit_code
        if process_status is not None and process_status.exit_code is not None
        else 0
        if succeeded
        else 1,
        duration_seconds=round(number=elapsed_seconds, ndigits=3),
        resume="completed" if succeeded else "the worker did not complete",
        report=request.output / "result.md",
        report_json=request.output / "result.json",
        report_web=request.output / "result_web" / "index.html",
    )


def result_from_status(
    *,
    request: ToolRequest,
    spec: ToolSpec,
    process_status: ProcessStatus | None,
    started: float,
) -> ToolRunResult:
    """Resolve a worker outcome from its terminal state and report.

    Args:
        request: Tool invocation request.
        spec: Catalog tool definition.
        process_status: Last status, or ``None`` when the worker vanished.
        started: Monotonic worker start timestamp.

    Returns:
        Report-backed result or a canonical crash result.

    """
    elapsed_seconds: float = monotonic() - started
    fallback: ToolRunResult = _fallback_result(
        request=request,
        process_status=process_status,
        elapsed_seconds=elapsed_seconds,
    )
    try:
        payload: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=fallback.report_json.read_text(encoding="utf-8")),
        )
    except (OSError, JSONDecodeError):
        return crashed_exactus(
            request=request,
            title=spec.identifier.replace("-", " ").title(),
            crash=CrashDetails(
                pid=process_status.pid if process_status is not None else None,
                exit_code=process_status.exit_code
                if process_status is not None
                and process_status.exit_code is not None
                else 1,
                elapsed_seconds=elapsed_seconds,
            ),
        )
    return ToolRunResult.from_report(
        payload=payload,
        output=request.output,
        fallback=fallback,
    )


def kill_context(*, context: str) -> int:
    """Gracefully stop and then reap every worker in a context.

    Args:
        context: pmanager context to terminate.

    Returns:
        Number of matching workers.

    """
    descriptors: tuple[Descriptor, ...] = tuple(
        descriptor
        for descriptor in Discovery.all()
        if descriptor.context == context
    )
    for descriptor in descriptors:
        with suppress(OSError, RuntimeError):
            _ = Client.request(descriptor=descriptor, command="kill")
        terminate_tree(pid=descriptor.pid)
    return len(descriptors)


def pause_worker(*, descriptor: Descriptor, owner: str) -> bool:
    """Acquire an owner-scoped pause lease on one worker.

    Args:
        descriptor: Worker receiving the control request.
        owner: Run requiring the worker to remain paused.

    Returns:
        ``True`` when pmanager accepted the pause lease.

    """
    try:
        response: dict[str, JsonValue] = Client.request(
            descriptor=descriptor,
            command="pause",
            payload={"owner": owner},
        )
    except (OSError, RuntimeError):
        return False
    return response.get("state") == State.PAUSED.value


def resume_worker(*, descriptor: Descriptor, owner: str) -> bool:
    """Release one owner's pause lease on a worker.

    Args:
        descriptor: Worker receiving the control request.
        owner: Run releasing its pause requirement.

    Returns:
        ``True`` only when no other owner still requires a pause.

    """
    try:
        response: dict[str, JsonValue] = Client.request(
            descriptor=descriptor,
            command="start",
            payload={"owner": owner},
        )
    except (OSError, RuntimeError):
        return False
    return response.get("state") != State.PAUSED.value


def reset_worker(*, descriptor: Descriptor) -> bool:
    """Restart one worker generation without replacing its owner process.

    Args:
        descriptor: Worker receiving the reset request.

    Returns:
        Whether pmanager accepted the reset request.

    """
    try:
        response: dict[str, JsonValue] = Client.request(
            descriptor=descriptor,
            command="reset",
        )
    except (OSError, RuntimeError):
        return False
    return bool(response)


def external_descriptors(
    *,
    records: Mapping[str, RunRecord],
    descriptors: Iterable[Descriptor],
    root: Path,
) -> dict[str, Descriptor]:
    """Join live registry records to discovered pmanager workers.

    Args:
        records: External run records keyed by tool identifier.
        descriptors: Shared pmanager discovery snapshot.
        root: Project root owning the records.

    Returns:
        Matching descriptors keyed by tool identifier.

    """
    available: tuple[Descriptor, ...] = tuple(descriptors)
    return {
        identifier: descriptor
        for identifier, record in records.items()
        for descriptor in available
        if descriptor.name == identifier
        and descriptor.context
        == tool_context(
            root=root,
            owner=record.pipeline_run_id or record.run_id,
        )
    }


class ExactusTool(ProcessClass):
    """Execute every catalog tool with a uniform lifecycle surface.

    Attributes:
        kill_timeout: Seconds allowed for graceful worker termination.

    """

    kill_timeout: float = 5.0

    def __init__(self) -> None:
        """Initialize worker lifecycle state."""
        super().__init__()
        self._identifier: str = ""
        self._run_id: str = ""
        self._output: Path | None = None
        self._lifecycle: str = "starting"
        self._cancel_requested: bool = False

    @pause
    def on_pause(self) -> None:
        """Publish the paused lifecycle before the runner stops."""
        self._event(state="paused")

    @resume
    def on_resume(self) -> None:
        """Publish the resumed lifecycle after the runner continues."""
        self._event(state="running")

    @reset
    def on_reset(self) -> None:
        """Clear generation-scoped progress before a restart."""
        output: Path | None = self._output
        if output is not None:
            (output / "ARTIFACTS" / "@activity.json").unlink(missing_ok=True)
            (output / "ARTIFACTS" / ".progress.json").unlink(missing_ok=True)
        self._cancel_requested = False
        self._event(state="reset")

    @cancel
    def on_cancel(self) -> None:
        """Mark cooperative cancellation before the runner exits."""
        self._cancel_requested = True
        if self._output is not None:
            release_dependency_workers(
                analyzer=self._identifier,
                run_id=self._run_id,
                output=self._output,
            )
        self._event(state="cancelled")

    @kill
    def on_kill(self) -> None:
        """Reap tool-spawned descendants before the bounded hard kill."""
        self._cancel_requested = True
        if self._output is not None:
            release_dependency_workers(
                analyzer=self._identifier,
                run_id=self._run_id,
                output=self._output,
            )
        self._event(state="killed")
        terminate_tree(pid=getpid(), include_root=False)

    @status
    def current_status(self) -> dict[str, JsonValue]:
        """Return live exactus progress and lifecycle details.

        Returns:
            JSON-compatible custom worker status.

        """
        fraction: float = 0.0
        step: str = self._lifecycle
        hierarchy: JsonValue = None
        workers: JsonValue = None
        output: Path | None = self._output
        if output is not None:
            try:
                payload: JsonValue = cast(
                    typ="JsonValue",
                    val=loads(
                        s=(output / "ARTIFACTS" / "@activity.json").read_text(
                            encoding="utf-8",
                        ),
                    ),
                )
            except (OSError, JSONDecodeError):
                payload = {}
            if isinstance(payload, dict):
                progress: JsonValue = payload.get("progress")
                if isinstance(progress, dict):
                    raw_fraction: JsonValue = progress.get("fraction", 0.0)
                    raw_step: JsonValue = progress.get("step", step)
                    if isinstance(raw_fraction, float):
                        fraction = raw_fraction
                    elif isinstance(raw_fraction, int) and (
                        not isinstance(raw_fraction, bool)
                    ):
                        fraction = float(raw_fraction)
                    if isinstance(raw_step, str):
                        step = raw_step
                    hierarchy = progress.get("hierarchy")
                    workers = progress.get("workers")
        return {
            "fraction": fraction,
            "step": step,
            "lifecycle": self._lifecycle,
            "run_id": self._run_id,
            "tool": self._identifier,
            "hierarchy": hierarchy,
            "workers": workers,
            "checkpoint": cast(typ="JsonValue", val=checkpoint_status()),
        }

    @receive(topic="exactus.tool.control")
    def control(self, payload: JsonValue) -> None:
        """Handle cooperative control broadcasts.

        Args:
            payload: Control action mapping.

        """
        action: JsonValue = (
            payload.get("action") if isinstance(payload, dict) else None
        )
        owner_value: JsonValue = (
            payload.get("run_id") if isinstance(payload, dict) else None
        )
        owner: str = (
            str(object=owner_value) if owner_value not in (None, "") else "*"
        )
        if action == "cancel":
            self.on_cancel()
        elif action == "checkpoint_pause":
            request_checkpoint_pause(owner=owner)
            self._event(state="checkpoint-waiting")
        elif action == "checkpoint_resume":
            release_checkpoint_pause(owner=owner)
            self._event(state="running")
        elif action == "status":
            self.broadcast(
                topic="exactus.tool.status",
                payload=self.current_status(),
            )

    def run(self, *, request: WorkerRequest) -> int:
        """Execute one catalog tool through the canonical exactus boundary.

        Args:
            request: Structured catalog tool invocation.

        Returns:
            Tool exit status.

        """
        identifier: str = request["identifier"]
        run_id: str = request["run_id"]
        output: str = request["output"]
        pipeline_run_id: str | None = request["pipeline_run_id"]
        project_root: str | None = request["project_root"]
        self._identifier = identifier
        self._run_id = run_id
        self._output = Path(output)
        self._event(state="running")
        responder: IdentityResponder | None = start_responder(
            run_id=pipeline_run_id or run_id,
            runtime=runtime_dir(output=Path(output)),
        )
        try:
            root: Path = (
                Path(project_root) if project_root is not None else Path.cwd()
            )
            chdir(path=root)
            for extra in (
                Constants.repo_root / "exactus",
                Constants.repo_root,
                root,
                root / "src",
            ):
                text: str = str(object=extra)
                if text not in import_paths:
                    import_paths.insert(0, text)
            environ["EXACTUS_ORCHESTRATED"] = "1"
            environ["EXACTUS_PMANAGER_WORKER"] = "1"
            environ["EXACTUS_RUN_ID"] = run_id
            environ["EXACTUS_PROJECT_ROOT"] = str(object=root.resolve())
            if pipeline_run_id is None:
                _ = environ.pop("EXACTUS_PIPELINE_RUN_ID", default=None)
            else:
                environ["EXACTUS_PIPELINE_RUN_ID"] = pipeline_run_id
            _ = activate_exactus_tool_bundle(root=root)
            imported: ModuleType = import_module(name=request["module"])
            tool_main: Callable[..., int] = cast(
                typ="Callable[..., int]",
                val=imported.main,
            )
            result: ToolRunResult = execute_exactus(
                analyzer=identifier,
                title=identifier.replace("-", " ").title(),
                main=lambda: tool_main(arguments=tuple(request["arguments"])),
                output=Path(output),
                run_ids=ExactusRunIds(
                    run_id=run_id,
                    pipeline_run_id=pipeline_run_id,
                ),
            )
        except BaseException:
            artifact: Path = Path(output) / "ARTIFACTS" / "worker-crash.log"
            with suppress(OSError):
                artifact.parent.mkdir(parents=True, exist_ok=True)
                _ = artifact.write_text(data=format_exc(), encoding="utf-8")
            raise
        finally:
            stop_responder(responder=responder)
        return result.exit_code

    def _event(self, *, state: str) -> None:
        """Broadcast one lifecycle state transition.

        Args:
            state: New worker lifecycle state.

        """
        self._lifecycle = state
        self.broadcast(
            topic="exactus.tool.lifecycle",
            payload={
                "tool": self._identifier,
                "run_id": self._run_id,
                "state": state,
                "generation": 1,
            },
        )
