#!/usr/bin/env python3
# Copyright (c) 2026
"""Shared exactus runtime state, progress, and summary protocol."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from os import environ
from pathlib import Path
from threading import Event, Lock, get_native_id
from time import sleep
from typing import TYPE_CHECKING, ClassVar, Final, cast, final

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from exactus.tools.common.catalog import ToolSpec
    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.common.registry import RunRecord
from exactus.packages.steps import trace
from exactus.tools.common.catalog import Constants as CatalogConstants
from exactus.tools.common.registry import RunRegistry


@final
class Constants:
    """Group module-level constants.

    Attributes:
        tool_env: Grouped module constant.
        run_id_env: Grouped module constant.
        source_resource: Grouped module constant.

    """

    tool_env: Final[str] = "EXACTUS_TOOL"
    run_id_env: Final[str] = "EXACTUS_RUN_ID"
    source_resource: Final[str] = "workspace:source-tree"


@dataclass(slots=True)
class _CheckpointState:
    """Hold mutable process-local checkpoint counters.

    Attributes:
        active: Number of activities currently inside a checkpoint boundary.

    """

    active: int = 0


_lock: Final[Lock] = Lock()
_current: Final[dict[str, JsonValue]] = {}
_checkpoint_pause: Final[Event] = Event()
_checkpoint_lock: Final[Lock] = Lock()
_checkpoint_owners: Final[set[str]] = set()
_checkpoint_state: Final[_CheckpointState] = _CheckpointState()


def request_checkpoint_pause(*, owner: str = "*") -> None:
    """Pause worker threads when they next complete an activity.

    Args:
        owner: Independent process requiring the checkpoint.

    """
    with _checkpoint_lock:
        _checkpoint_owners.add(owner)
        _checkpoint_pause.set()


def release_checkpoint_pause(*, owner: str = "*") -> None:
    """Release one owner's activity-boundary checkpoint lease.

    Args:
        owner: Independent process releasing its checkpoint.

    """
    with _checkpoint_lock:
        if owner == "*":
            _checkpoint_owners.clear()
        else:
            _checkpoint_owners.discard(owner)
        if not _checkpoint_owners:
            _checkpoint_pause.clear()


def checkpoint_status() -> dict[str, JsonValue]:
    """Return the cooperative activity-boundary state.

    Returns:
        Normalized checkpoint state for process-to-process inspection.

    """
    with _checkpoint_lock:
        active: int = _checkpoint_state.active
        owners: list[JsonValue] = cast(
            typ="list[JsonValue]",
            val=sorted(_checkpoint_owners),
        )
    requested: bool = _checkpoint_pause.is_set()
    return {
        "requested": requested,
        "active": active,
        "ready": requested and active == 0,
        "owners": owners,
    }


def _work_registry() -> RunRegistry | None:
    """Return the workspace activity ledger configured by execution.

    Returns:
        Shared registry, or ``None`` outside a managed exactus run.

    """
    path: str | None = environ.get("EXACTUS_REGISTRY")
    return RunRegistry(path=Path(path)) if path else None


def _dependencies(*, analyzer: str) -> frozenset[str]:
    """Return transitive catalog prerequisites of a task.

    Args:
        analyzer: Canonical task identifier.

    Returns:
        Transitive prerequisite identifiers.

    """
    pending: list[str] = [analyzer]
    found: set[str] = set()
    while pending:
        tool: ToolSpec | None = CatalogConstants.exactus_catalog.tool(
            identifier=pending.pop(),
        )
        if tool is None:
            continue
        for dependency in tool.dependencies:
            if dependency not in found:
                found.add(dependency)
                pending.append(dependency)
    return frozenset(found)


def _wait_for_item(*, item: str) -> None:
    """Wait until every live prerequisite releases this work item.

    Args:
        item: File or logical activity identity.

    """
    registry: RunRegistry | None = _work_registry()
    analyzer: str = environ.get(Constants.tool_env, "")
    run_id: str = environ.get(Constants.run_id_env, "")
    dependencies: frozenset[str] = _dependencies(analyzer=analyzer)
    if registry is None or not dependencies:
        return
    normalized: str = str(object=Path(item).resolve())
    while True:
        blockers: tuple[RunRecord, ...] = tuple(
            record
            for record in registry.live()
            if record.kind == "tool"
            and record.run_id != run_id
            and (record.identifier in dependencies)
            and (
                registry.activity_state(run_id=record.run_id, item=normalized)
                not in {"released", "done", "failed"}
            )
        )
        if not blockers:
            return
        sleep(0.05)


def wait_for_dependencies() -> None:
    """Wait until every live prerequisite process reaches a terminal state."""
    registry: RunRegistry | None = _work_registry()
    analyzer: str = environ.get(Constants.tool_env, "")
    run_id: str = environ.get(Constants.run_id_env, "")
    dependencies: frozenset[str] = _dependencies(analyzer=analyzer)
    if registry is None or not dependencies:
        return
    while any(
        record.kind == "tool"
        and record.run_id != run_id
        and record.identifier in dependencies
        for record in registry.live()
    ):
        sleep(0.05)


def _activity_boundary() -> None:
    """Wait cooperatively after a complete thread activity."""
    while _checkpoint_pause.is_set():
        sleep(0.05)


def _start_activity() -> None:
    """Enter an activity only after any checkpoint has been released."""
    while True:
        _activity_boundary()
        with _checkpoint_lock:
            if not _checkpoint_pause.is_set():
                _checkpoint_state.active += 1
                return


def _finish_activity() -> None:
    """Leave one complete activity before honoring a checkpoint."""
    with _checkpoint_lock:
        _checkpoint_state.active = max(_checkpoint_state.active - 1, 0)


def _acquire_resource(
    *,
    resource: str,
    mode: str,
    identity: str,
) -> tuple[RunRegistry, str] | None:
    """Acquire a shared reader/writer lease for one logical activity.

    Args:
        resource: Shared logical resource.
        mode: ``read`` or ``write``.
        identity: Stable activity identity within the current thread.

    Returns:
        Registry and lease identity, or ``None`` outside a managed run.

    """
    registry: RunRegistry | None = _work_registry()
    run_id: str = environ.get(Constants.run_id_env, "")
    tool: str = environ.get(Constants.tool_env, "")
    if registry is None or not run_id or (not tool):
        return None
    lease_id: str = f"{run_id}:{get_native_id()}:{resource}:{identity}"
    while True:
        acquired: bool | None = registry.acquire_resource(
            lease_id=lease_id,
            run_id=run_id,
            tool=tool,
            resource=resource,
            mode=mode,
        )
        if acquired is None:
            return None
        if acquired:
            return (registry, lease_id)
        sleep(0.05)


@contextmanager
def source_activity(
    *,
    mode: str,
    identity: str,
    enabled: bool = True,
) -> Generator[None]:
    """Protect a file or whole logical subtask with a source-tree lease.

    Args:
        mode: ``read`` for consumers or ``write`` for source mutation.
        identity: Stable activity label used for inspection.
        enabled: Skip resource coordination when the phase is read-only.

    Yields:
        Control while the source-tree lease is active.

    """
    if not enabled:
        yield
        return
    _start_activity()
    lease: tuple[RunRegistry, str] | None = _acquire_resource(
        resource=Constants.source_resource,
        mode=mode,
        identity=identity,
    )
    registry: RunRegistry | None = lease[0] if lease is not None else None
    run_id: str = environ.get(Constants.run_id_env, "")
    tool: str = environ.get(Constants.tool_env, "")
    item: str = f"activity:{identity}"
    if registry is not None and run_id and tool:
        registry.publish_activity(
            run_id=run_id,
            tool=tool,
            item=item,
            state="running",
        )
    completed: bool = False
    try:
        yield
        completed = True
    finally:
        if registry is not None and run_id and tool:
            registry.publish_activity(
                run_id=run_id,
                tool=tool,
                item=item,
                state="done" if completed else "failed",
            )
        if lease is not None:
            lease[0].release_resource(lease_id=lease[1])
        _finish_activity()
        _activity_boundary()


def run_source_activity[ResultT](
    *,
    mode: str,
    identity: str,
    action: Callable[[], ResultT],
    enabled: bool = True,
) -> ResultT:
    """Run one operation under a source-tree reader/writer lease.

    Args:
        mode: ``read`` or ``write``.
        identity: Stable logical activity label.
        action: Operation executed while the lease is active.
        enabled: Skip coordination for a read-only phase.

    Returns:
        Operation result.

    """
    with source_activity(mode=mode, identity=identity, enabled=enabled):
        return action()


@dataclass(frozen=True, slots=True)
class Progress:
    """Represent progress.

    Attributes:
        state: State.
        completed: Completed.
        total: Total.
        step: Step.
        detail: Detail.
        span: ``(start, end)`` slice of the overall bar this phase
            fills, so a multi-phase tool never restarts at zero.
        workers: Optional per-worker step counts and current actions.
        share: Explicit phase completion in ``[0, 1]`` when it is finer
            than ``completed/total`` (which then stay real counts).
        error: Process-level error detail, when emitted.

    """

    state: str
    completed: int
    total: int
    step: str
    detail: str = ""
    span: tuple[float, float] = (0.0, 1.0)
    share: float | None = None
    workers: dict[str, JsonValue] | None = None
    error: str = ""

    @property
    def fraction(self) -> float:
        """Completion fraction clamped to the ``[0, 1]`` range.

        Returns:
            The resulting value.

        """
        raw: float = (
            self.share
            if self.share is not None
            else self.completed / max(self.total, 1)
        )
        return min(max(raw, 0.0), 1.0)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProgressNode:
    """Represent one normalized hierarchical progress node.

    Attributes:
        level: Pipeline, task, subtask, or activity.
        identifier: Stable node identifier within its parent.
        state: Lifecycle state.
        completed: Completed work units.
        total: Total work units.
        fraction: Current completion fraction.
        step: Current processing stage.
        current: Current file or logical item.
        error: Structured error payload, when any.
        children: Nested normalized nodes.

    """

    level: str
    identifier: str
    state: str
    completed: int
    total: int
    fraction: float
    step: str
    current: str
    error: JsonValue = None
    children: tuple[JsonValue, ...] = ()

    def payload(self) -> dict[str, JsonValue]:
        """Serialize this node.

        Returns:
            JSON-compatible progress node.

        """
        return {
            "level": self.level,
            "id": self.identifier,
            "state": self.state,
            "completed": self.completed,
            "total": self.total,
            "fraction": round(
                number=min(max(self.fraction, 0.0), 1.0),
                ndigits=6,
            ),
            "step": self.step,
            "current": self.current,
            "error": self.error,
            "children": list(self.children),
        }


def _worker_nodes(*, workers: dict[str, JsonValue] | None) -> list[JsonValue]:
    """Normalize per-thread snapshots as subtask nodes.

    Args:
        workers: Worker snapshots keyed by thread identity.

    Returns:
        Normalized subtask nodes.

    """
    nodes: list[JsonValue] = []
    for identifier, raw in (workers or {}).items():
        fields: dict[str, JsonValue] = raw if isinstance(raw, dict) else {}
        current: str = str(object=fields.get("current", ""))
        error_value: JsonValue = fields.get("error")
        error: JsonValue = (
            {"message": str(object=error_value)}
            if error_value not in (None, "")
            else None
        )
        state: str = str(object=fields.get("state", "running"))
        activity: dict[str, JsonValue] = ProgressNode(
            level="activity",
            identifier=current or "current",
            state=state,
            completed=int(state in {"done", "failed"}),
            total=1,
            fraction=1.0 if state in {"done", "failed"} else 0.0,
            step=current,
            current=current,
            error=error,
        ).payload()
        nodes.append(
            ProgressNode(
                level="subtask",
                identifier=identifier,
                state=state,
                completed=int(state in {"done", "failed"}),
                total=1,
                fraction=1.0 if state in {"done", "failed"} else 0.0,
                step=current,
                current=current,
                error=error,
                children=(activity,),
            ).payload(),
        )
    return nodes


def emit_progress(
    *,
    state: str,
    completed: int,
    total: int,
    step: str,
    detail: str = "",
) -> None:
    """Publish whole-tool progress for standalone and orchestrated runs.

    Args:
        state: Lifecycle state such as WAITING, RUNNING, DONE, or FAIL.
        completed: Completed logical work units.
        total: Total logical work units.
        step: Current logical step label.
        detail: Optional human-readable detail.

    """
    publish_progress(
        progress=Progress(
            state=state,
            completed=completed,
            total=total,
            step=step,
            detail=detail,
        ),
    )


def publish_progress(*, progress: Progress) -> None:
    """Publish one progress snapshot to the tool's progress channel.

    Multi-phase tools set ``progress.span`` so each phase's own
    ``completed/total`` fills only its slice of the overall bar (for
    example ``(0.3, 0.5)``) instead of restarting at zero. Published
    Fractions reflect the current work graph. A reset or a newly discovered
    work item may therefore move progress backwards.

    Args:
        progress: Snapshot to publish.

    """
    progress = replace(
        progress,
        completed=max(progress.completed, 0),
        total=max(progress.total, 1),
    )
    start, end = (min(max(value, 0.0), 1.0) for value in progress.span)
    with _lock:
        fraction: float = start + progress.fraction * max(end - start, 0.0)
        _current.clear()
        _current.update(
            {
                "progress": round(number=fraction, ndigits=6),
                "completed": progress.completed,
                "total": progress.total,
                "step": progress.step,
                "detail": progress.detail,
            },
        )
        if progress.workers is not None:
            _current["workers"] = dict(progress.workers)
        activity: dict[str, JsonValue] = ProgressNode(
            level="activity",
            identifier=progress.step or "current",
            state=progress.state,
            completed=progress.completed,
            total=progress.total,
            fraction=progress.fraction,
            step=progress.step,
            current=progress.detail,
            error={"message": progress.error} if progress.error else None,
        ).payload()
        _current["hierarchy"] = ProgressNode(
            level="task",
            identifier=environ.get(Constants.tool_env, "standalone"),
            state=progress.state,
            completed=progress.completed,
            total=progress.total,
            fraction=fraction,
            step=progress.step,
            current=progress.detail,
            error={"message": progress.error} if progress.error else None,
            children=(*_worker_nodes(workers=progress.workers), activity),
        ).payload()
    detail: str = f" — {progress.detail}" if progress.detail else ""
    trace(
        step=(
            f"progress: {progress.step}{detail} "
            f"({progress.completed}/{progress.total})"
        ),
        depth=3,
    )


def current_progress() -> dict[str, JsonValue]:
    """Return the latest in-process progress snapshot.

    Returns:
        A copy safe for heartbeat publication.

    """
    with _lock:
        return dict(_current)


def clear_progress() -> None:
    """Clear progress retained from an earlier run in this process."""
    with _lock:
        _current.clear()


def release_activities(
    *,
    items: list[Path] | frozenset[Path],
    stable: bool = True,
) -> None:
    """Publish available file activities for dependent processes.

    A provisional release lets a dependent process work between source-writing
    phases. The dependent must reconcile its snapshot after prerequisites
    terminate. A stable release means no later phase will mutate the files.

    Args:
        items: Files available to dependent processes.
        stable: Whether prerequisite source work is final.

    """
    registry: RunRegistry | None = _work_registry()
    run_id: str = environ.get(Constants.run_id_env, "")
    tool: str = environ.get(Constants.tool_env, "")
    if registry is None or not run_id or (not tool):
        return
    for item in items:
        registry.publish_activity(
            run_id=run_id,
            tool=tool,
            item=str(object=item.resolve()),
            state="done" if stable else "released",
        )


@final
class LaneProgress:
    """Run-wide completed-unit counter shared by parallel lanes.

    Concurrent console-version lanes each feed one ``completed/total``
    pair, so emitted progress reflects the whole tool's work instead of
    restarting at zero for every lane.

    Attributes:
        total: Total logical work units across every lane.

    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_completed",
        "_leases",
        "_lock",
        "_span",
        "_step",
        "_workers",
        "total",
    )

    def __init__(
        self,
        *,
        total: int,
        step: str = "parallel work",
        span: tuple[float, float] = (0.0, 1.0),
    ) -> None:
        """Store the run-wide work-unit total.

        Args:
            total: Total logical work units across every lane.
            step: Process-level label for the thread group.
            span: Slice of the process progress owned by this group.

        """
        self.total: int = max(total, 1)
        self._completed: int = 0
        self._lock: Lock = Lock()
        self._step: str = step
        self._span: tuple[float, float] = span
        self._workers: dict[str, JsonValue] = {}
        self._leases: dict[str, tuple[RunRegistry, str] | None] = {}

    @property
    def completed(self) -> int:
        """Number of units completed so far.

        Returns:
            Completed logical work units across every lane.

        """
        with self._lock:
            return self._completed

    def advance(self) -> int:
        """Mark one work unit complete and return the new count.

        Returns:
            Completed logical work units including this unit.

        """
        return self.finish(item="work item")

    def begin(self, *, item: str) -> None:
        """Publish one thread starting a work item.

        Args:
            item: File or logical unit handled by the current thread.

        """
        normalized: str = str(object=Path(item).resolve())
        _wait_for_item(item=normalized)
        _start_activity()
        worker: str = str(object=get_native_id())
        lease: tuple[RunRegistry, str] | None = _acquire_resource(
            resource=Constants.source_resource,
            mode="read",
            identity=normalized,
        )
        registry: RunRegistry | None = _work_registry()
        run_id: str = environ.get(Constants.run_id_env, "")
        tool: str = environ.get(Constants.tool_env, "")
        if registry is not None and run_id and tool:
            registry.publish_activity(
                run_id=run_id,
                tool=tool,
                item=normalized,
                state="running",
            )
        with self._lock:
            self._leases[worker] = lease
            self._workers[worker] = {
                "state": "running",
                "current": normalized,
                "errors": 0,
            }
            self._publish(detail=normalized)

    def finish(self, *, item: str, error: str | None = None) -> int:
        """Publish one thread completing or failing a work item.

        Args:
            item: File or logical unit handled by the current thread.
            error: Failure detail emitted by that thread, when any.

        Returns:
            Completed logical work units across every lane.

        """
        normalized: str = str(object=Path(item).resolve())
        worker: str = str(object=get_native_id())
        with self._lock:
            self._completed += 1
            snapshot: dict[str, JsonValue] = {
                "state": "failed" if error else "done",
                "current": normalized,
                "errors": int(error is not None),
            }
            if error is not None:
                snapshot["error"] = error
            self._workers[worker] = snapshot
            lease: tuple[RunRegistry, str] | None = self._leases.pop(
                worker,
                None,
            )
            self._publish(detail=normalized)
            completed: int = self._completed
        registry: RunRegistry | None = _work_registry()
        run_id: str = environ.get(Constants.run_id_env, "")
        tool: str = environ.get(Constants.tool_env, "")
        if registry is not None and run_id and tool:
            registry.publish_activity(
                run_id=run_id,
                tool=tool,
                item=normalized,
                state="failed" if error else "done",
                error=error or "",
            )
        if lease is not None:
            lease[0].release_resource(lease_id=lease[1])
        _finish_activity()
        _activity_boundary()
        return completed

    def _publish(self, *, detail: str) -> None:
        """Publish the locked aggregate into the process channel.

        Args:
            detail: Most recently changed work item.

        """
        publish_progress(
            progress=Progress(
                state="RUNNING",
                completed=self._completed,
                total=self.total,
                step=self._step,
                detail=detail,
                span=self._span,
                workers=dict(self._workers),
            ),
        )
