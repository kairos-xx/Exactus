# Copyright (c) 2026
"""Detached exactus worker specifications, results, and lifecycle hooks."""

from __future__ import annotations

from dataclasses import replace
from json import dumps
from pathlib import Path
from typing import TYPE_CHECKING, cast

from exactus.packages.pmanager import (
    Lifecycle,
    ProcessKey,
    ProcessStatus,
    State,
)
from exactus.packages.pmanager.runtime import Descriptor
from exactus.tests.common.support import (
    dig,
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_true,
    set_private,
)
from exactus.tools.common import tool_worker as worker_module
from exactus.tools.common.catalog import ToolSpec
from exactus.tools.common.models import ToolRequest, ToolRunResult
from exactus.tools.common.registry import RunRecord
from exactus.tools.common.tool_worker import (
    ExactusTool,
    build_spec,
    external_descriptors,
    live_status,
    result_from_status,
    tool_context,
    worker_arguments,
)

if TYPE_CHECKING:
    import pytest

    from exactus.tools.common.json_types import JsonValue


def _spec(*, identifier: str = "docs") -> ToolSpec:
    """Build a compact catalog tool.

    Args:
        identifier: Tool identifier.

    Returns:
        Catalog tool definition.

    """
    return ToolSpec(
        identifier=identifier,
        module=f"exactus.tools.{identifier}.main",
        script=f"exactus/tools/{identifier}/main.py",
        output=identifier.upper(),
    )


def _request(tmp_path: Path) -> ToolRequest:
    """Build a worker request rooted in a temporary directory.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Worker request.

    """
    return ToolRequest(
        identifier="docs",
        output=tmp_path / "DOCS",
        arguments=("--include", "src"),
        run_id="run",
        pipeline_run_id="pipeline",
        project_root=tmp_path,
    )


def _status(*, state: State, pid: int = 41) -> ProcessStatus:
    """Build a public pmanager status.

    Args:
        state: Worker state.
        pid: Runtime process identifier.

    Returns:
        Process status.

    """
    return ProcessStatus(
        key=ProcessKey(name="docs", context="exactus:run"),
        state=state,
        progress=0,
        pid=pid,
        reason="",
        exit_code=0 if state is State.COMPLETED else 1,
        attempts=1,
        generation=1,
        children={},
    )


def test_build_spec_leaves_dependency_ordering_to_the_supervisor() -> None:
    """Catalog dependencies never become pmanager ``depends_on`` edges.

    The pipeline supervisor schedules a tool once its dependencies reach
    a terminal state, pass or fail. A pmanager edge would abort the
    dependent's executor when the prerequisite worker exits nonzero —
    exactly how a lints FAIL used to knock out docs and coverage_tests.
    """
    lints: ToolSpec = _spec(identifier="lints")
    docs: ToolSpec = replace(_spec(), dependencies=("lints",))
    streaming: ToolSpec = replace(
        _spec(identifier="kwargs_typehints"),
        dependencies=("lints",),
        streaming_dependencies=True,
    )
    specification: dict[str, JsonValue] = (
        build_spec(tools=(lints, docs, streaming), root=Path.cwd())
        .to_specification()
        .to_mapping()
    )
    for name in ("lints", "docs", "kwargs_typehints"):
        process: JsonValue = cast(
            typ="JsonValue",
            val=dig(document=specification, path=("processes", name)),
        )
        has_no_edge: bool = (
            isinstance(process, dict) and "depends_on" not in process
        )
        expect_true(condition=has_no_edge)
    expect_equal(
        actual=dig(
            document=specification,
            path=("processes", "docs", "executor", "type"),
        ),
        expected="python_class",
    )


def test_context_and_worker_arguments_round_trip(tmp_path: Path) -> None:
    """Context names and structured worker arguments retain every request.

    Args:
        tmp_path: Temporary project root used to derive the context.

    """
    request: ToolRequest = _request(tmp_path=tmp_path)
    positional, keyword = worker_arguments(request=request, spec=_spec())
    context: str = tool_context(root=tmp_path, owner="pipeline")
    workspace, owner = context.split(sep="/", maxsplit=1)
    expect_equal(actual=owner, expected="pipeline")
    expect_equal(actual=len(workspace), expected=64)
    expect_equal(actual=positional, expected=())
    payload: JsonValue = keyword["request"]
    expect_equal(
        actual=dig(document=payload, path=("arguments",)),
        expected=["--include", "src"],
    )
    expect_equal(
        actual=dig(document=payload, path=("project_root",)),
        expected=str(object=tmp_path),
    )


def test_live_status_distinguishes_gone_from_ipc_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing descriptor is dead while an IPC error remains live.

    Args:
        monkeypatch: Attribute patcher for the pmanager client.

    """
    expect_none(
        value=live_status(descriptors=(), name="docs", context="exactus:run"),
    )
    descriptor: Descriptor = Descriptor(
        pid=41,
        port=9000,
        name="docs",
        context="exactus:run",
        args=(),
    )

    def unavailable(**_arguments: JsonValue) -> dict[str, JsonValue]:
        """Raise the same error as an unavailable IPC endpoint.

        Args:
            **_arguments: Ignored request fields.

        Returns:
            Never reached; the function always raises.

        Raises:
            OSError: Always.

        """
        msg: str = "busy"
        raise OSError(msg)

    monkeypatch.setattr(
        target=worker_module.Client,
        name="request",
        value=staticmethod(unavailable),
    )
    current: ProcessStatus | None = live_status(
        descriptors=(descriptor,),
        name="docs",
        context="exactus:run",
    )
    expect_true(condition=current is not None)
    expect_equal(
        actual=current.state if current else None,
        expected=State.STARTING,
    )


def test_result_from_status_prefers_report_and_crashes_when_missing(
    tmp_path: Path,
) -> None:
    """Terminal workers reconstruct reports; missing reports become failures.

    Args:
        tmp_path: Temporary report root.

    """
    request: ToolRequest = _request(tmp_path=tmp_path)
    request.output.mkdir(parents=True)
    _ = (request.output / "result.json").write_text(
        data=dumps(
            obj={
                "tool": "docs",
                "run_id": "run",
                "pipeline_run_id": "pipeline",
                "status": "PASS",
                "passed": True,
                "duration_seconds": 0.1,
                "resume": "documented",
            },
        ),
    )
    result: ToolRunResult = result_from_status(
        request=request,
        spec=_spec(),
        process_status=_status(state=State.COMPLETED),
        started=0.0,
    )
    expect_true(condition=result.passed)
    expect_equal(actual=result.resume, expected="documented")
    (request.output / "result.json").unlink()
    crashed: ToolRunResult = result_from_status(
        request=request,
        spec=_spec(),
        process_status=None,
        started=0.0,
    )
    expect_false(condition=crashed.passed)
    expect_in(member="exited before reporting", container=crashed.resume)


def test_lifecycle_hooks_publish_state_cleanup_and_reap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every lifecycle hook performs its documented stateful behavior.

    Args:
        tmp_path: Temporary worker output.
        monkeypatch: Pytest patching helper.

    """
    instance: ExactusTool = ExactusTool()
    events: list[tuple[str, JsonValue]] = []
    reaped: list[tuple[int, bool]] = []

    def publish(topic: str, payload: JsonValue, _scope: str) -> int:
        """Capture one worker broadcast.

        Args:
            topic: Broadcast topic.
            payload: Broadcast payload.
            _scope: Broadcast scope.

        Returns:
            One delivered listener.

        """
        events.append((topic, payload))
        return 1

    def reap(*, pid: int, include_root: bool = True) -> None:
        """Capture descendant cleanup.

        Args:
            pid: Worker process identifier.
            include_root: Whether the worker itself is included.

        """
        reaped.append((pid, include_root))

    instance.configure_broadcast(sender=publish)
    set_private(owner=instance, name="_identifier", value="docs")
    set_private(owner=instance, name="_run_id", value="run")
    set_private(owner=instance, name="_output", value=tmp_path)
    artifacts: Path = tmp_path / "ARTIFACTS"
    artifacts.mkdir(parents=True)
    for name in ("@activity.json", ".progress.json"):
        _ = (artifacts / name).write_text(data="{}")
    monkeypatch.setattr(
        target=worker_module,
        name="terminate_tree",
        value=reap,
    )
    for lifecycle in (
        Lifecycle.PAUSE,
        Lifecycle.RESUME,
        Lifecycle.RESET,
        Lifecycle.CANCEL,
        Lifecycle.KILL,
    ):
        expect_true(condition=instance.invoke_lifecycle(lifecycle=lifecycle))
    expect_false(condition=(artifacts / "@activity.json").exists())
    expect_false(condition=(artifacts / ".progress.json").exists())
    expect_true(condition=bool(reaped))
    expect_equal(actual=reaped[-1][1], expected=False)
    expect_equal(
        actual=instance.current_status()["lifecycle"],
        expected="killed",
    )
    expect_equal(
        actual=[
            cast(typ="dict[str, JsonValue]", val=payload)["state"]
            for topic, payload in events
            if topic == "exactus.tool.lifecycle"
        ],
        expected=["paused", "running", "reset", "cancelled", "killed"],
    )


def test_control_broadcast_and_external_descriptor_join(
    tmp_path: Path,
) -> None:
    """Control broadcasts acknowledge status and records join by context.

    Args:
        tmp_path: Project root used to derive the nested context.

    """
    instance: ExactusTool = ExactusTool()
    events: list[str] = []

    def publish(topic: str, _payload: JsonValue, _scope: str) -> int:
        """Capture a broadcast topic.

        Args:
            topic: Broadcast topic.
            _payload: Ignored payload.
            _scope: Ignored scope.

        Returns:
            One delivered listener.

        """
        events.append(topic)
        return 1

    instance.configure_broadcast(sender=publish)
    instance.receive_broadcast(
        topic="exactus.tool.control",
        payload={"action": "status"},
    )
    expect_in(member="exactus.tool.status", container=events)
    record: RunRecord = RunRecord(
        kind="tool",
        identifier="docs",
        run_id="run",
        pipeline_run_id=None,
        pid=42,
        output="output/docs",
        targets=(),
        status="RUNNING",
        progress=0.0,
        step="starting",
        detail="",
        created_at="2026-10-12T00:00:00+00:00",
        updated_at="2026-10-12T00:00:00+00:00",
        elapsed_seconds=0.0,
    )
    descriptor: Descriptor = Descriptor(
        pid=41,
        port=9000,
        name="docs",
        context=tool_context(root=tmp_path, owner="run"),
        args=(),
    )
    expect_equal(
        actual=external_descriptors(
            records={"docs": record},
            descriptors=(descriptor,),
            root=tmp_path,
        ),
        expected={"docs": descriptor},
    )
