# Copyright (c) 2026 Project contributors
"""Tests for Flow graph state and deterministic persistence."""

from pathlib import Path
from typing import Final, final

import pytest

from exactus.tools.record.model import (
    ActionContract,
    ActionRunRecord,
    ActionRunStatus,
    AssertionKind,
    AssertionOperator,
    AssertionOutcome,
    AssertionResult,
    AssertionSpec,
    BodyMatchMode,
    CapturePhase,
    CheckpointArtifact,
    CheckpointDefinition,
    DeviceMode,
    EventKind,
    ExecutionRun,
    Flow,
    FlowEdge,
    FlowOutput,
    FlowParameter,
    FlowSettings,
    HttpHeader,
    NetworkExpectation,
    OutputBinding,
    OutputSource,
    RunStatus,
    RuntimeVariable,
    RunTransition,
    ScreenshotArtifact,
    TimelineEvent,
    TimelineLayer,
    TransitionMode,
    UrlMatchMode,
    ValueType,
    VariableDefinition,
    VariableScope,
    Workspace,
)
from exactus.tools.record.store import (
    FlowStore,
    JsonValue,
    WorkspaceCodec,
    WorkspaceError,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        edge_count: Grouped module constant.

    """

    edge_count: Final[int] = 5


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


def _flow(*, flow_id: str, name: str) -> Flow:
    """Return flow.

    Args:
        flow_id: Flow id.
        name: Name.

    Returns:
        The resulting value.

    """
    return Flow(
        flow_id=flow_id,
        name=name,
        task_description=f"Task {name}",
        expected_behavior=f"Expected {name}",
        notes=f"Notes {name}",
    )


def _event(*, event_id: str, flow_id: str, elapsed_ms: int) -> TimelineEvent:
    """Return event.

    Args:
        event_id: Event id.
        flow_id: Flow id.
        elapsed_ms: Elapsed ms.

    Returns:
        The resulting value.

    """
    return TimelineEvent(
        event_id=event_id,
        flow_id=flow_id,
        sequence=-1,
        elapsed_ms=elapsed_ms,
        layer=TimelineLayer.INTERACTION,
        kind=EventKind.CLICK,
        label="Click",
        selector="#target",
    )


def test_flow_graph_allows_branching_and_cycles() -> None:
    """Handle test flow graph allows branching and cycles."""
    store: FlowStore = FlowStore(
        workspace=Workspace(
            flows=(
                _flow(flow_id="a", name="A"),
                _flow(flow_id="b", name="B"),
                _flow(flow_id="c", name="C"),
                _flow(flow_id="d", name="D"),
            ),
            edges=(),
        ),
    )
    for edge in (
        FlowEdge(source_flow_id="a", target_flow_id="b"),
        FlowEdge(source_flow_id="a", target_flow_id="c"),
        FlowEdge(source_flow_id="b", target_flow_id="c"),
        FlowEdge(source_flow_id="c", target_flow_id="d"),
        FlowEdge(source_flow_id="d", target_flow_id="a"),
    ):
        store.add_edge(edge=edge)
    _require(
        condition=len(store.workspace.edges) == Constants.edge_count,
        msg="Unexpected Flow edge count.",
    )


def test_flow_graph_rejects_direct_self_loop() -> None:
    """Handle test flow graph rejects direct self loop."""
    store: FlowStore = FlowStore(
        workspace=Workspace(flows=(_flow(flow_id="a", name="A"),), edges=()),
    )
    with pytest.raises(expected_exception=ValueError, match="itself"):
        store.add_edge(edge=FlowEdge(source_flow_id="a", target_flow_id="a"))


def test_event_append_move_and_delete_resequence() -> None:
    """Handle test event append move and delete resequence."""
    store: FlowStore = FlowStore(
        workspace=Workspace(flows=(_flow(flow_id="a", name="A"),), edges=()),
    )
    store.append_event(event=_event(event_id="1", flow_id="a", elapsed_ms=10))
    store.append_event(event=_event(event_id="2", flow_id="a", elapsed_ms=20))
    store.append_event(event=_event(event_id="3", flow_id="a", elapsed_ms=30))
    store.move_event(flow_id="a", event_id="3", offset=-2)
    store.delete_event(flow_id="a", event_id="2")
    events: tuple[TimelineEvent, ...] = store.get_flow(flow_id="a").events
    _require(
        condition=tuple(event.event_id for event in events) == ("3", "1"),
        msg="Unexpected event order after timeline edits.",
    )
    _require(
        condition=tuple(event.sequence for event in events) == (0, 1),
        msg="Timeline sequence values were not compacted.",
    )


def test_place_and_retime_keep_replay_order_and_time_aligned() -> None:
    """Dropping a step keeps time slots; retiming reorders by time."""
    store: FlowStore = FlowStore(
        workspace=Workspace(flows=(_flow(flow_id="a", name="A"),), edges=()),
    )
    store.append_event(event=_event(event_id="1", flow_id="a", elapsed_ms=10))
    store.append_event(event=_event(event_id="2", flow_id="a", elapsed_ms=20))
    store.append_event(event=_event(event_id="3", flow_id="a", elapsed_ms=30))
    store.place_event(flow_id="a", event_id="1", index=2)
    events: tuple[TimelineEvent, ...] = store.get_flow(flow_id="a").events
    _require(
        condition=tuple(event.event_id for event in events) == ("2", "3", "1"),
        msg="Placing a step did not move it to the requested position.",
    )
    _require(
        condition=tuple(event.elapsed_ms for event in events) == (10, 20, 30),
        msg="Placed steps must keep the time slots of their new positions.",
    )
    store.retime_event(flow_id="a", event_id="2", elapsed_ms=25)
    events = store.get_flow(flow_id="a").events
    _require(
        condition=tuple(event.event_id for event in events) == ("3", "2", "1"),
        msg="Retiming a step did not reorder the flow by time.",
    )
    _require(
        condition=tuple(event.sequence for event in events) == (0, 1, 2),
        msg="Sequence values were not compacted after retiming.",
    )


def test_edges_redefine_in_place_and_reorder() -> None:
    """Transitions can be redefined without moving and then reordered."""
    store: FlowStore = FlowStore(
        workspace=Workspace(
            flows=(
                _flow(flow_id="a", name="A"),
                _flow(flow_id="b", name="B"),
                _flow(flow_id="c", name="C"),
            ),
            edges=(),
        ),
    )
    store.add_edge(edge=FlowEdge(source_flow_id="a", target_flow_id="b"))
    store.add_edge(edge=FlowEdge(source_flow_id="a", target_flow_id="c"))
    redefined: FlowEdge = FlowEdge(
        source_flow_id="b",
        target_flow_id="c",
        mode=TransitionMode.FALLBACK,
    )
    store.replace_edge(index=0, edge=redefined)
    _require(
        condition=store.workspace.edges[0] == redefined,
        msg="A redefined transition must keep its position.",
    )
    with pytest.raises(expected_exception=ValueError, match="already exists"):
        store.replace_edge(index=1, edge=redefined)
    with pytest.raises(expected_exception=ValueError, match="existing"):
        store.replace_edge(index=7, edge=redefined)
    store.move_edge(index=1, to=0)
    _require(
        condition=store.workspace.edges[1] == redefined,
        msg="Moving a transition did not change the evaluation order.",
    )
    with pytest.raises(expected_exception=ValueError, match="existing"):
        store.move_edge(index=0, to=9)


def test_expectation_and_screenshot_round_trip(tmp_path: Path) -> None:
    """Handle test expectation and screenshot round trip.

    Args:
        tmp_path: Tmp path.

    """
    expectation: NetworkExpectation = NetworkExpectation(
        expectation_id="expectation-1",
        label="created response",
        method="POST",
        url_pattern="*/api/items*",
        url_match=UrlMatchMode.GLOB,
        expected_status=201,
        expected_headers=(
            HttpHeader(name="Content-Type", value="application/json"),
        ),
        body_match=BodyMatchMode.JSON_CONTAINS,
        expected_body='{"ok":true}',
    )
    event: TimelineEvent = TimelineEvent(
        event_id="event-1",
        flow_id="a",
        sequence=0,
        elapsed_ms=125,
        layer=TimelineLayer.NETWORK,
        kind=EventKind.HTTP_CALL,
        label="POST /api/items",
        url="https://example.test/api/items",
        method="POST",
        payload='{"name":"A"}',
        headers=(HttpHeader(name="X-Test", value="1"),),
        share_session_cookies=True,
        expectations=(expectation,),
    )
    flow: Flow = Flow(
        flow_id="a",
        name="A",
        task_description="Task A",
        expected_behavior="Expected A",
        notes="Notes A",
        device_modes=frozenset({DeviceMode.MOBILE, DeviceMode.TABLET}),
        capture_record_images=True,
        capture_play_images=True,
        events=(event,),
    )
    workspace: Workspace = Workspace(
        flows=(flow,),
        edges=(),
        screenshots=(
            ScreenshotArtifact(
                artifact_id="shot-1",
                flow_id="a",
                event_id="event-1",
                phase=CapturePhase.PLAY,
                path="shots/event-1.png",
                width=390,
                height=844,
                sha256="abc",
            ),
        ),
    )
    path: Path = tmp_path / "test.pwflow.json"
    WorkspaceCodec.save(path=path, workspace=workspace)
    _require(
        condition=WorkspaceCodec.load(path=path) == workspace,
        msg="Workspace did not round-trip exactly.",
    )


@pytest.mark.parametrize("version", [1, 2, 4])
def test_workspace_rejects_unsupported_versions(
    tmp_path: Path,
    version: int,
) -> None:
    """Reject older formats instead of synthesizing compatibility defaults.

    Args:
        tmp_path: Disposable project files.
        version: Unsupported workspace schema.

    """
    path: Path = tmp_path / "unsupported.pwflow.json"
    path.write_text(data=f'{{"version":{version},"flows":[],"edges":[]}}')
    with pytest.raises(expected_exception=WorkspaceError, match="Unsupported"):
        WorkspaceCodec.load(path=path)


def test_workspace_v3_comprehensive_round_trip() -> None:
    """Round-trip contracts, variables, checkpoints, and execution evidence."""
    assertion: AssertionSpec = AssertionSpec(
        assertion_id="assert-1",
        label="visible",
        kind=AssertionKind.DOM_VISIBLE,
        operator=AssertionOperator.EXISTS,
        target="#app",
    )
    binding: OutputBinding = OutputBinding(
        name="title",
        value_type=ValueType.STRING,
        source=OutputSource.DOM_TEXT,
        expression="text",
        selector="h1",
    )
    contract: ActionContract = ActionContract(
        preconditions=(assertion,),
        postconditions=(),
        outputs=(binding,),
        retry_count=1,
        retry_delay_ms=25,
        continue_on_failure=True,
    )
    event: TimelineEvent = TimelineEvent(
        event_id="event-contract",
        flow_id="flow-rich",
        sequence=0,
        elapsed_ms=10,
        layer=TimelineLayer.INTERACTION,
        kind=EventKind.CLICK,
        label="Click app",
        selector="#app",
        contract=contract,
        request_id="request-1",
        initiator_url="https://example.test",
        initiator_stack=("frame",),
        correlation_id="correlation-1",
        caused_by_event_id="cause-1",
        attribution_confidence=0.9,
        attribution_reasons=("same request",),
    )
    flow: Flow = Flow(
        flow_id="flow-rich",
        name="Rich",
        task_description="Task",
        expected_behavior="Expected",
        notes="Notes",
        parameters=(FlowParameter(name="input", value_type=ValueType.STRING),),
        outputs=(
            FlowOutput(
                name="output",
                value_type=ValueType.STRING,
                expression="input",
            ),
        ),
        events=(event,),
    )
    runtime: RuntimeVariable = RuntimeVariable(
        name="token",
        value_type=ValueType.STRING,
        value="secret",
        secret=True,
    )
    assertion_result: AssertionResult = AssertionResult(
        assertion_id="assert-1",
        outcome=AssertionOutcome.SUCCEEDED,
        details="visible",
        actual="true",
    )
    action_record: ActionRunRecord = ActionRunRecord(
        event_id="event-contract",
        flow_id="flow-rich",
        status=ActionRunStatus.SUCCEEDED,
        attempt=1,
        started_ms=0,
        finished_ms=5,
        assertions=(assertion_result,),
        observed_event_ids=("network-1",),
        screenshot_artifact_ids=("shot-1",),
        outputs=(runtime,),
    )
    transition: RunTransition = RunTransition(
        source_flow_id="flow-rich",
        target_flow_id="flow-rich",
        mode=TransitionMode.RETRY,
        reason="retry",
    )
    run: ExecutionRun = ExecutionRun(
        run_id="run-rich",
        initial_flow_id="flow-rich",
        current_flow_id=None,
        device_mode=DeviceMode.DESKTOP,
        status=RunStatus.SUCCEEDED,
        started_at_utc="2026-10-02T10:00:00Z",
        finished_at_utc="2026-10-02T10:00:01Z",
        action_records=(action_record,),
        transitions=(transition,),
        variables=(runtime,),
    )
    checkpoint: CheckpointDefinition = CheckpointDefinition(
        checkpoint_id="checkpoint-1",
        name="Ready",
        flow_id="flow-rich",
        event_id="event-contract",
        include_indexed_db=True,
    )
    artifact: CheckpointArtifact = CheckpointArtifact(
        artifact_id="checkpoint-artifact-1",
        checkpoint_id="checkpoint-1",
        run_id="run-rich",
        flow_id="flow-rich",
        event_id="event-contract",
        url="https://example.test",
        cookies_json="[]",
        local_storage_json="{}",
        session_storage_json="{}",
        indexed_db_json="{}",
        variables=(runtime,),
    )
    workspace: Workspace = Workspace(
        flows=(flow,),
        edges=(
            FlowEdge(
                source_flow_id="flow-rich",
                target_flow_id="flow-rich",
                mode=TransitionMode.RETRY,
            ),
        ),
        variables=(
            VariableDefinition(
                name="count",
                value_type=ValueType.INTEGER,
                scope=VariableScope.WORKSPACE,
                default_value=1,
            ),
        ),
        checkpoint_definitions=(checkpoint,),
        checkpoint_artifacts=(artifact,),
        runs=(run,),
    )
    encoded: JsonValue = WorkspaceCodec.to_json_value(workspace=workspace)
    decoded: Workspace = WorkspaceCodec.from_json_value(value=encoded)
    _require(
        condition=decoded.flows[0].events[0].contract == contract
        and decoded.checkpoint_definitions == (checkpoint,)
        and (decoded.runs[0].run_id == "run-rich"),
        msg="Comprehensive v3 workspace fields did not round-trip.",
    )


def test_store_mutation_surface_updates_canonical_workspace() -> None:
    """Exercise editor-facing store mutation operations."""
    flow: Flow = _flow(flow_id="mutate", name="Before")
    event: TimelineEvent = _event(
        event_id="event",
        flow_id="mutate",
        elapsed_ms=1,
    )
    store: FlowStore = FlowStore(workspace=Workspace(flows=(flow,), edges=()))
    store.append_event(event=event)
    store.update_flow(
        flow_id="mutate",
        settings=FlowSettings(
            name="After",
            task_description="Task",
            expected_behavior="Expected",
            notes="Notes",
            device_modes=frozenset({DeviceMode.DESKTOP}),
            capture_record_images=True,
            capture_play_images=True,
        ),
    )
    expectation: NetworkExpectation = NetworkExpectation(
        expectation_id="mutation-expectation",
        label="response",
    )
    store.add_expectation(
        flow_id="mutate",
        event_id="event",
        expectation=expectation,
    )
    store.remove_expectation(
        flow_id="mutate",
        event_id="event",
        expectation_id="mutation-expectation",
    )
    contract: ActionContract = ActionContract(retry_count=1)
    store.set_action_contract(
        flow_id="mutate",
        event_id="event",
        contract=contract,
    )
    store.set_flow_interface(
        flow_id="mutate",
        parameters=(FlowParameter(name="input", value_type=ValueType.STRING),),
        outputs=(
            FlowOutput(
                name="output",
                value_type=ValueType.STRING,
                expression="input",
            ),
        ),
    )
    definition: VariableDefinition = VariableDefinition(
        name="local",
        value_type=ValueType.STRING,
        scope=VariableScope.WORKSPACE,
        default_value="value",
    )
    store.add_variable(definition=definition)
    store.remove_variable(name="local")
    checkpoint: CheckpointDefinition = CheckpointDefinition(
        checkpoint_id="mutation-checkpoint",
        name="Mutation",
        flow_id="mutate",
        event_id="event",
    )
    store.add_checkpoint_definition(checkpoint=checkpoint)
    artifact: CheckpointArtifact = CheckpointArtifact(
        artifact_id="mutation-artifact",
        checkpoint_id="mutation-checkpoint",
        run_id="mutation-run",
        flow_id="mutate",
        event_id="event",
        url="about:blank",
    )
    store.add_checkpoint_artifact(artifact=artifact)
    store.add_checkpoint_artifact(artifact=artifact)
    run: ExecutionRun = ExecutionRun(
        run_id="mutation-run",
        initial_flow_id="mutate",
        current_flow_id=None,
        device_mode=DeviceMode.DESKTOP,
        status=RunStatus.SUCCEEDED,
        started_at_utc="start",
        finished_at_utc="finish",
    )
    store.upsert_run(run=run)
    store.upsert_run(run=run)
    screenshot: ScreenshotArtifact = ScreenshotArtifact(
        artifact_id="mutation-shot",
        flow_id="mutate",
        event_id="event",
        phase=CapturePhase.PLAY,
        path="shot.png",
        width=10,
        height=10,
        sha256="hash",
    )
    store.add_screenshot(artifact=screenshot)
    store.add_screenshot(artifact=screenshot)
    store.remove_checkpoint_definition(checkpoint_id="mutation-checkpoint")
    _require(
        condition=store.get_flow(flow_id="mutate").name == "After"
        and (not store.workspace.variables)
        and (not store.workspace.checkpoint_definitions)
        and (len(store.workspace.runs) == 1)
        and (len(store.workspace.screenshots) == 1),
        msg="Store mutation surface produced unexpected state.",
    )


def test_store_rejects_duplicate_and_missing_references() -> None:
    """Exercise store duplicate and referential-integrity guards."""
    flow: Flow = _flow(flow_id="guard", name="Guard")
    event: TimelineEvent = _event(
        event_id="event",
        flow_id="guard",
        elapsed_ms=1,
    )
    store: FlowStore = FlowStore(workspace=Workspace(flows=(flow,), edges=()))
    store.append_event(event=event)
    with pytest.raises(expected_exception=ValueError, match="Duplicate Flow"):
        store.add_flow(flow=flow)
    with pytest.raises(expected_exception=KeyError, match="missing"):
        store.get_flow(flow_id="missing")
    with pytest.raises(expected_exception=KeyError, match="missing"):
        store.get_event(flow_id="guard", event_id="missing")
    expectation: NetworkExpectation = NetworkExpectation(
        expectation_id="duplicate",
        label="Duplicate",
    )
    store.add_expectation(
        flow_id="guard",
        event_id="event",
        expectation=expectation,
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="Duplicate expectation",
    ):
        store.add_expectation(
            flow_id="guard",
            event_id="event",
            expectation=expectation,
        )
    definition: VariableDefinition = VariableDefinition(
        name="duplicate",
        value_type=ValueType.STRING,
        scope=VariableScope.WORKSPACE,
    )
    store.add_variable(definition=definition)
    with pytest.raises(
        expected_exception=ValueError,
        match="Duplicate variable",
    ):
        store.add_variable(definition=definition)
    checkpoint: CheckpointDefinition = CheckpointDefinition(
        checkpoint_id="duplicate",
        name="Duplicate",
        flow_id="guard",
        event_id="event",
    )
    store.add_checkpoint_definition(checkpoint=checkpoint)
    with pytest.raises(
        expected_exception=ValueError,
        match="Duplicate checkpoint",
    ):
        store.add_checkpoint_definition(checkpoint=checkpoint)
    with pytest.raises(expected_exception=KeyError, match="missing"):
        store.add_edge(
            edge=FlowEdge(source_flow_id="guard", target_flow_id="missing"),
        )
    second: Flow = _flow(flow_id="second", name="Second")
    store.add_flow(flow=second)
    edge: FlowEdge = FlowEdge(source_flow_id="guard", target_flow_id="second")
    store.add_edge(edge=edge)
    store.remove_edge(edge=edge)
    store.delete_flow(flow_id="second")
    _require(
        condition=len(store.workspace.flows) == 1,
        msg="Flow cleanup failed.",
    )


def test_update_flow_rejects_empty_name() -> None:
    """Check updating a flow to an empty name fails."""
    store: FlowStore = FlowStore(
        workspace=Workspace(flows=(_flow(flow_id="f", name="F"),), edges=()),
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="Flow name cannot be empty",
    ):
        store.update_flow(
            flow_id=store.workspace.flows[0].flow_id,
            settings=FlowSettings(
                name=" ",
                task_description="",
                expected_behavior="",
                notes="",
                device_modes=frozenset({DeviceMode.SHARED}),
                capture_record_images=False,
                capture_play_images=False,
            ),
        )
