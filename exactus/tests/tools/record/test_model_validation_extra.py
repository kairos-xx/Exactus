"""Validation-path coverage for immutable domain records."""

import pytest

from exactus.tools.record.model import (
    ActionContract,
    ActionRunRecord,
    ActionRunStatus,
    AssertionKind,
    AssertionOperator,
    AssertionSpec,
    BodyMatchMode,
    CapturePhase,
    CheckpointArtifact,
    CheckpointDefinition,
    ConditionOperator,
    DeviceMode,
    ExecutionRun,
    Flow,
    FlowEdge,
    FlowOutput,
    FlowParameter,
    HttpHeader,
    JsonCondition,
    NetworkExpectation,
    OutputBinding,
    OutputSource,
    QueryCondition,
    RunStatus,
    RuntimeVariable,
    ScreenshotArtifact,
    TransitionMode,
    ValueType,
    VariableDefinition,
    VariableScope,
)


def test_small_record_validation_failures() -> None:
    """Check small record types reject invalid input."""
    with pytest.raises(
        expected_exception=ValueError,
        match="header name cannot be empty",
    ):
        HttpHeader(name="", value="x")
    with pytest.raises(
        expected_exception=ValueError,
        match="Query-condition name cannot be empty",
    ):
        QueryCondition(name="", operator=ConditionOperator.EXISTS)
    with pytest.raises(
        expected_exception=ValueError,
        match="query operators require a value",
    ):
        QueryCondition(name="x", operator=ConditionOperator.EQUALS)
    with pytest.raises(expected_exception=ValueError, match="must start"):
        JsonCondition(path="x", operator=ConditionOperator.EXISTS)
    with pytest.raises(
        expected_exception=ValueError,
        match="JSON operators require a value",
    ):
        JsonCondition(path="$.x", operator=ConditionOperator.EQUALS)
    with pytest.raises(
        expected_exception=ValueError,
        match="Expectation ID cannot be empty",
    ):
        NetworkExpectation(expectation_id="", label="x")
    with pytest.raises(
        expected_exception=ValueError,
        match="timeout must be positive",
    ):
        NetworkExpectation(expectation_id="x", label="x", timeout_ms=0)
    with pytest.raises(
        expected_exception=ValueError,
        match="requires an expected body",
    ):
        NetworkExpectation(
            expectation_id="x",
            label="x",
            body_match=BodyMatchMode.EXACT_TEXT,
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="Flow parameter name cannot be empty",
    ):
        FlowParameter(name="", value_type=ValueType.STRING)
    with pytest.raises(
        expected_exception=ValueError,
        match="cannot define defaults",
    ):
        FlowParameter(
            name="x",
            value_type=ValueType.STRING,
            required=True,
            default_value="x",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="require a name and expression",
    ):
        FlowOutput(name="", value_type=ValueType.STRING, expression="x")
    with pytest.raises(
        expected_exception=ValueError,
        match="Runtime variable name cannot be empty",
    ):
        RuntimeVariable(name="", value_type=ValueType.STRING, value=None)


def test_variable_assertion_and_output_validation() -> None:
    """Check variable, assertion and output validation rules."""
    with pytest.raises(
        expected_exception=ValueError,
        match="Variable name cannot be empty",
    ):
        VariableDefinition(
            name="",
            value_type=ValueType.STRING,
            scope=VariableScope.RUN,
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="require a Flow ID",
    ):
        VariableDefinition(
            name="x",
            value_type=ValueType.STRING,
            scope=VariableScope.FLOW,
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="Only Flow-scoped variables may carry a Flow ID",
    ):
        VariableDefinition(
            name="x",
            value_type=ValueType.STRING,
            scope=VariableScope.RUN,
            flow_id="f",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="require a source name",
    ):
        VariableDefinition(
            name="x",
            value_type=ValueType.STRING,
            scope=VariableScope.ENVIRONMENT,
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="cannot persist defaults",
    ):
        VariableDefinition(
            name="x",
            value_type=ValueType.STRING,
            scope=VariableScope.CREDENTIAL,
            source_name="X",
            default_value="bad",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="Assertion ID cannot be empty",
    ):
        AssertionSpec(
            assertion_id="",
            label="x",
            kind=AssertionKind.URL,
            operator=AssertionOperator.EXISTS,
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="Assertion timeout must be positive",
    ):
        AssertionSpec(
            assertion_id="a",
            label="x",
            kind=AssertionKind.URL,
            operator=AssertionOperator.EXISTS,
            timeout_ms=0,
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="require a selector target or reference",
    ):
        AssertionSpec(
            assertion_id="a",
            label="x",
            kind=AssertionKind.DOM_TEXT,
            operator=AssertionOperator.EXISTS,
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="require an attribute name",
    ):
        AssertionSpec(
            assertion_id="a",
            label="x",
            kind=AssertionKind.DOM_ATTRIBUTE,
            operator=AssertionOperator.EXISTS,
            target="#x",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="require an expected value",
    ):
        AssertionSpec(
            assertion_id="a",
            label="x",
            kind=AssertionKind.URL,
            operator=AssertionOperator.EQUALS,
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="require a name and expression",
    ):
        OutputBinding(
            name="",
            value_type=ValueType.STRING,
            source=OutputSource.URL,
            expression="x",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="require a CSS selector",
    ):
        OutputBinding(
            name="x",
            value_type=ValueType.STRING,
            source=OutputSource.DOM_TEXT,
            expression="x",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="outputs require an attribute name",
    ):
        OutputBinding(
            name="x",
            value_type=ValueType.STRING,
            source=OutputSource.DOM_ATTRIBUTE,
            expression="x",
            selector="#x",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="retry values cannot be negative",
    ):
        ActionContract(retry_count=-1)


def test_flow_edge_artifact_and_run_validation() -> None:
    """Check flow edge, artifact and run validation rules."""
    duplicate: FlowParameter = FlowParameter(
        name="x",
        value_type=ValueType.STRING,
    )
    output: FlowOutput = FlowOutput(
        name="x",
        value_type=ValueType.STRING,
        expression="x",
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="at least one device mode",
    ):
        Flow(
            flow_id="f",
            name="f",
            task_description="",
            expected_behavior="",
            notes="",
            device_modes=frozenset(),
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="Shared scope cannot be combined",
    ):
        Flow(
            flow_id="f",
            name="f",
            task_description="",
            expected_behavior="",
            notes="",
            device_modes=frozenset({DeviceMode.SHARED, DeviceMode.MOBILE}),
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="parameter names must be unique",
    ):
        Flow(
            flow_id="f",
            name="f",
            task_description="",
            expected_behavior="",
            notes="",
            parameters=(duplicate, duplicate),
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="output names must be unique",
    ):
        Flow(
            flow_id="f",
            name="f",
            task_description="",
            expected_behavior="",
            notes="",
            outputs=(output, output),
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="max traversals must be positive",
    ):
        FlowEdge(source_flow_id="a", target_flow_id="b", max_traversals=0)
    with pytest.raises(
        expected_exception=ValueError,
        match="Conditional Flow edges require an expression",
    ):
        FlowEdge(
            source_flow_id="a",
            target_flow_id="b",
            mode=TransitionMode.CONDITION,
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="Only conditional Flow edges may define an expression",
    ):
        FlowEdge(
            source_flow_id="a",
            target_flow_id="b",
            condition_expression="x",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="only through a retry edge",
    ):
        FlowEdge(source_flow_id="a", target_flow_id="a")
    with pytest.raises(
        expected_exception=ValueError,
        match="Screenshot dimensions must be positive",
    ):
        ScreenshotArtifact(
            artifact_id="a",
            flow_id="f",
            event_id="e",
            phase=CapturePhase.RECORD,
            path="x",
            width=0,
            height=1,
            sha256="x",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="Screenshot path cannot be empty",
    ):
        ScreenshotArtifact(
            artifact_id="a",
            flow_id="f",
            event_id="e",
            phase=CapturePhase.RECORD,
            path="",
            width=1,
            height=1,
            sha256="x",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="Checkpoint definitions require ID and name",
    ):
        CheckpointDefinition(checkpoint_id="", name="x", flow_id="f")
    with pytest.raises(
        expected_exception=ValueError,
        match="Checkpoint artifacts require non-empty IDs",
    ):
        CheckpointArtifact(
            artifact_id="",
            checkpoint_id="c",
            run_id="r",
            flow_id="f",
            event_id=None,
            url="",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="attempts and timestamps must be positive",
    ):
        ActionRunRecord(
            event_id="e",
            flow_id="f",
            status=ActionRunStatus.SUCCEEDED,
            attempt=0,
            started_ms=0,
            finished_ms=0,
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="finish time cannot precede",
    ):
        ActionRunRecord(
            event_id="e",
            flow_id="f",
            status=ActionRunStatus.SUCCEEDED,
            attempt=1,
            started_ms=2,
            finished_ms=1,
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="require non-empty IDs",
    ):
        ExecutionRun(
            run_id="",
            initial_flow_id="f",
            current_flow_id=None,
            device_mode=DeviceMode.DESKTOP,
            status=RunStatus.RUNNING,
            started_at_utc="x",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="cannot have a finish timestamp",
    ):
        ExecutionRun(
            run_id="r",
            initial_flow_id="f",
            current_flow_id=None,
            device_mode=DeviceMode.DESKTOP,
            status=RunStatus.RUNNING,
            started_at_utc="x",
            finished_at_utc="y",
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="require a finish timestamp",
    ):
        ExecutionRun(
            run_id="r",
            initial_flow_id="f",
            current_flow_id=None,
            device_mode=DeviceMode.DESKTOP,
            status=RunStatus.SUCCEEDED,
            started_at_utc="x",
        )
