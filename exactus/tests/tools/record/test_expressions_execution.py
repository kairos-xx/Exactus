# Copyright (c) 2026 Project contributors
"""Behavioral coverage for expression and execution engines."""

from typing import Final, final

import pytest

from exactus.tools.record.execution import (
    EdgeTraversalCount,
    ExecutionDecision,
    ExecutionEngine,
    ExecutionError,
    ExecutionStartRequest,
    ExecutionState,
    VariableResolver,
)
from exactus.tools.record.expressions import (
    ExpressionError,
    ExpressionEvaluator,
    ValueCodec,
)
from exactus.tools.record.model import (
    DeviceMode,
    Flow,
    FlowEdge,
    FlowExecutionResult,
    FlowParameter,
    RunStatus,
    RuntimeVariable,
    TransitionMode,
    ValueType,
    VariableDefinition,
    VariableScope,
    Workspace,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        expected_integer: Grouped module constant.
        expected_float: Grouped module constant.
        expected_variable_count: Grouped module constant.
        coerced_integer: Grouped module constant.
        coerced_float: Grouped module constant.

    """

    expected_integer: Final[int] = 4
    expected_float: Final[float] = 2.5
    expected_variable_count: Final[int] = 2
    coerced_integer: Final[int] = 12
    coerced_float: Final[float] = 1.5


def _variable(
    *,
    name: str,
    value_type: ValueType,
    value: str | float | bool | None,
    secret: bool = False,
) -> RuntimeVariable:
    """Return one runtime variable.

    Args:
        name: Name.
        value_type: Value type.
        value: Value.
        secret: Secret.

    Returns:
        The resulting value.

    """
    return RuntimeVariable(
        name=name,
        value_type=value_type,
        value=value,
        secret=secret,
    )


def test_value_codec_and_expression_language() -> None:
    """Exercise typed coercion, helpers, comparisons, and interpolation."""
    variables: tuple[RuntimeVariable, ...] = (
        _variable(name="name", value_type=ValueType.STRING, value="alpha"),
        _variable(name="count", value_type=ValueType.INTEGER, value=3),
        _variable(name="enabled", value_type=ValueType.BOOLEAN, value=True),
    )
    if (
        ValueCodec.coerce(value_type=ValueType.INTEGER, value="4")
        != Constants.expected_integer
    ):
        pytest.fail(reason="Integer coercion failed.")
    if (
        ValueCodec.coerce(value_type=ValueType.FLOAT, value="2.5")
        != Constants.expected_float
    ):
        pytest.fail(reason="Float coercion failed.")
    if (
        ValueCodec.coerce(value_type=ValueType.BOOLEAN, value="yes")
        is not True
    ):
        pytest.fail(reason="Boolean coercion failed.")
    if (
        ValueCodec.coerce(value_type=ValueType.JSON, value='{"b":2,"a":1}')
        != '{"a":1,"b":2}'
    ):
        pytest.fail(reason="JSON normalization failed.")
    if ValueCodec.render(variable=variables[2]) != "true":
        pytest.fail(reason="Boolean rendering failed.")
    expressions: tuple[str, ...] = (
        "enabled and count >= 3",
        "name == 'alpha'",
        "name != 'beta'",
        "count > 2 and count <= 3",
        "contains(name, 'ph')",
        "exists(name)",
        "matches(name, '^a.*a$')",
        "name in 'alphabet'",
        "not (count < 3)",
    )
    for expression in expressions:
        ExpressionEvaluator.validate(expression=expression)
        if not ExpressionEvaluator.evaluate(
            expression=expression,
            variables=variables,
        ):
            pytest.fail(reason=f"Expression failed: {expression}")
    rendered: str = ExpressionEvaluator.interpolate(
        template="${name}-${count}-${enabled}",
        variables=variables,
    )
    if rendered != "alpha-3-true":
        pytest.fail(reason="Template interpolation failed.")


def test_expression_failures_are_explicit() -> None:
    """Reject unsafe, malformed, secret, and non-boolean expressions."""
    secret: RuntimeVariable = _variable(
        name="secret",
        value_type=ValueType.STRING,
        value="token",
        secret=True,
    )
    for expression in ("", "__import__('os')", "name + 'x'"):
        with pytest.raises(expected_exception=ExpressionError):
            ExpressionEvaluator.validate(expression=expression)
    with pytest.raises(expected_exception=ExpressionError):
        ExpressionEvaluator.evaluate(expression="contains('a')", variables=())
    with pytest.raises(expected_exception=ExpressionError):
        ExpressionEvaluator.evaluate(expression="missing == 1", variables=())
    with pytest.raises(expected_exception=ExpressionError):
        ExpressionEvaluator.evaluate(expression="1", variables=())
    with pytest.raises(expected_exception=ExpressionError):
        ExpressionEvaluator.interpolate(
            template="${secret}",
            variables=(secret,),
        )
    with pytest.raises(expected_exception=ExpressionError):
        ValueCodec.coerce(value_type=ValueType.BOOLEAN, value="maybe")
    with pytest.raises(expected_exception=ExpressionError):
        ValueCodec.coerce(value_type=ValueType.JSON, value=3)


def test_execution_engine_selects_condition_and_completes() -> None:
    """Run a conditional transition followed by terminal completion."""
    first: Flow = Flow(
        flow_id="a",
        name="A",
        task_description="",
        expected_behavior="",
        notes="",
        device_modes=frozenset({DeviceMode.DESKTOP}),
    )
    second: Flow = Flow(
        flow_id="b",
        name="B",
        task_description="",
        expected_behavior="",
        notes="",
        device_modes=frozenset({DeviceMode.DESKTOP}),
    )
    edge: FlowEdge = FlowEdge(
        source_flow_id="a",
        target_flow_id="b",
        mode=TransitionMode.CONDITION,
        condition_expression="flow_succeeded",
        priority=10,
        max_traversals=2,
    )
    workspace: Workspace = Workspace(flows=(first, second), edges=(edge,))
    state: ExecutionState = ExecutionEngine.start(
        workspace=workspace,
        request=ExecutionStartRequest(
            run_id="run-1",
            initial_flow_id="a",
            device_mode=DeviceMode.DESKTOP,
            started_at_utc="2026-10-02T10:00:00Z",
        ),
    )
    decision: ExecutionDecision = ExecutionEngine.complete_flow(
        workspace=workspace,
        state=state,
        result=FlowExecutionResult(
            run_id="run-1",
            flow_id="a",
            status=RunStatus.SUCCEEDED,
        ),
        finished_at_utc="2026-10-02T10:00:01Z",
    )
    if decision.next_flow_id != "b" or decision.state is None:
        pytest.fail(reason="Conditional transition was not selected.")
    terminal: ExecutionDecision = ExecutionEngine.complete_flow(
        workspace=workspace,
        state=decision.state,
        result=FlowExecutionResult(
            run_id="run-1",
            flow_id="b",
            status=RunStatus.SUCCEEDED,
        ),
        finished_at_utc="2026-10-02T10:00:02Z",
    )
    if (
        terminal.completed_run is None
        or terminal.completed_run.status is not RunStatus.SUCCEEDED
    ):
        pytest.fail(reason="Execution did not terminate successfully.")


def test_running_one_flow_does_not_follow_its_connections() -> None:
    """A single-flow run completes after the first flow, edge or not."""
    flows: tuple[Flow, ...] = tuple(
        Flow(
            flow_id=flow_id,
            name=flow_id.upper(),
            task_description="",
            expected_behavior="",
            notes="",
            device_modes=frozenset({DeviceMode.DESKTOP}),
        )
        for flow_id in ("a", "b")
    )
    workspace: Workspace = Workspace(
        flows=flows,
        edges=(
            FlowEdge(
                source_flow_id="a",
                target_flow_id="b",
                mode=TransitionMode.ALWAYS,
            ),
        ),
    )
    state: ExecutionState = ExecutionEngine.start(
        workspace=workspace,
        request=ExecutionStartRequest(
            run_id="run-2",
            initial_flow_id="a",
            device_mode=DeviceMode.DESKTOP,
            started_at_utc="2026-10-08T10:00:00Z",
            follow_connections=False,
        ),
    )
    decision: ExecutionDecision = ExecutionEngine.complete_flow(
        workspace=workspace,
        state=state,
        result=FlowExecutionResult(
            run_id="run-2",
            flow_id="a",
            status=RunStatus.SUCCEEDED,
        ),
        finished_at_utc="2026-10-08T10:00:01Z",
    )
    if (
        decision.next_flow_id is not None
        or decision.completed_run is None
        or decision.completed_run.status is not RunStatus.SUCCEEDED
    ):
        pytest.fail(reason="The run must end after the first flow.")


def test_variable_resolution_and_execution_errors() -> None:
    """Cover defaults, secrets, merges, redaction, and execution guards."""
    definitions: tuple[VariableDefinition, ...] = (
        VariableDefinition(
            name="count",
            value_type=ValueType.INTEGER,
            scope=VariableScope.WORKSPACE,
            default_value=2,
        ),
        VariableDefinition(
            name="token",
            value_type=ValueType.STRING,
            scope=VariableScope.CREDENTIAL,
            source_name="TOKEN",
        ),
    )
    flow: Flow = Flow(
        flow_id="a",
        name="A",
        task_description="",
        expected_behavior="",
        notes="",
    )
    workspace: Workspace = Workspace(
        flows=(flow,),
        edges=(),
        variables=definitions,
    )
    supplied: tuple[RuntimeVariable, ...] = (
        _variable(name="token", value_type=ValueType.STRING, value="secret"),
    )
    resolved: tuple[RuntimeVariable, ...] = VariableResolver.initial_variables(
        workspace=workspace,
        supplied=supplied,
    )
    if (
        len(resolved) != Constants.expected_variable_count
        or not next(item for item in resolved if item.name == "token").secret
    ):
        pytest.fail(reason="Variable resolution failed.")
    redacted: tuple[RuntimeVariable, ...] = VariableResolver.redact(
        variables=resolved,
    )
    if (
        next(item for item in redacted if item.name == "token").value
        is not None
    ):
        pytest.fail(reason="Secret redaction failed.")
    with pytest.raises(expected_exception=ExecutionError):
        VariableResolver.initial_variables(
            workspace=workspace,
            supplied=(
                _variable(
                    name="unknown",
                    value_type=ValueType.STRING,
                    value="x",
                ),
            ),
        )
    with pytest.raises(expected_exception=ExecutionError):
        ExecutionEngine.start(
            workspace=workspace,
            request=ExecutionStartRequest(
                run_id="r",
                initial_flow_id="missing",
                device_mode=DeviceMode.DESKTOP,
                started_at_utc="now",
            ),
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="cannot be negative",
    ):
        EdgeTraversalCount(
            source_flow_id="a",
            target_flow_id="b",
            mode=TransitionMode.ALWAYS,
            condition_expression=None,
            count=-1,
        )


def test_variable_resolver_parameter_guards_and_defaults() -> None:
    """Cover required runtime values and Flow parameter resolution."""
    environment: VariableDefinition = VariableDefinition(
        name="environment",
        value_type=ValueType.STRING,
        scope=VariableScope.ENVIRONMENT,
        source_name="ENVIRONMENT",
    )
    workspace: Workspace = Workspace(
        flows=(),
        edges=(),
        variables=(environment,),
    )
    with pytest.raises(
        expected_exception=ExecutionError,
        match="Runtime value required",
    ):
        VariableResolver.initial_variables(workspace=workspace, supplied=())
    flow: Flow = Flow(
        flow_id="parameters",
        name="Parameters",
        task_description="",
        expected_behavior="",
        notes="",
        parameters=(
            FlowParameter(name="required", value_type=ValueType.STRING),
            FlowParameter(
                name="defaulted",
                value_type=ValueType.INTEGER,
                required=False,
                default_value=3,
            ),
        ),
    )
    with pytest.raises(
        expected_exception=ExecutionError,
        match="Missing required",
    ):
        VariableResolver.validate_flow_parameters(flow=flow, variables=())
    wrong: RuntimeVariable = _variable(
        name="required",
        value_type=ValueType.INTEGER,
        value=1,
    )
    with pytest.raises(
        expected_exception=ExecutionError,
        match="expects string",
    ):
        VariableResolver.validate_flow_parameters(
            flow=flow,
            variables=(wrong,),
        )
    supplied: RuntimeVariable = _variable(
        name="required",
        value_type=ValueType.STRING,
        value="ready",
    )
    resolved: tuple[RuntimeVariable, ...] = (
        VariableResolver.validate_flow_parameters(
            flow=flow,
            variables=(supplied,),
        )
    )
    if len(resolved) != Constants.expected_variable_count:
        pytest.fail(reason="Default Flow parameter was not added.")


def test_value_codec_edge_cases() -> None:
    """Check the codec round-trips and rejects unusual values."""
    if ValueCodec.coerce(
        value_type=ValueType.STRING,
        value=Constants.coerced_integer,
    ) != str(object=Constants.coerced_integer):
        pytest.fail(reason="String coercion failed.")
    if (
        ValueCodec.coerce(value_type=ValueType.INTEGER, value="12")
        != Constants.coerced_integer
    ):
        pytest.fail(reason="Integer coercion failed.")
    if (
        ValueCodec.coerce(value_type=ValueType.FLOAT, value="1.5")
        != Constants.coerced_float
    ):
        pytest.fail(reason="Float coercion failed.")
    if (
        ValueCodec.coerce(value_type=ValueType.BOOLEAN, value="yes")
        is not True
    ):
        pytest.fail(reason="Boolean 'yes' coercion failed.")
    if (
        ValueCodec.coerce(value_type=ValueType.BOOLEAN, value="off")
        is not False
    ):
        pytest.fail(reason="Boolean 'off' coercion failed.")
    if (
        ValueCodec.coerce(value_type=ValueType.JSON, value='{"b":2,"a":1}')
        != '{"a":1,"b":2}'
    ):
        pytest.fail(reason="JSON normalization failed.")
    if (
        ValueCodec.render(
            variable=RuntimeVariable(
                name="x",
                value_type=ValueType.STRING,
                value=None,
            ),
        )
        != ""
    ):
        pytest.fail(reason="None rendering failed.")
    if (
        ValueCodec.render(
            variable=RuntimeVariable(
                name="x",
                value_type=ValueType.BOOLEAN,
                value=True,
            ),
        )
        != "true"
    ):
        pytest.fail(reason="Boolean rendering failed.")
    for value_type, value in [
        (ValueType.INTEGER, True),
        (ValueType.FLOAT, False),
        (ValueType.BOOLEAN, "maybe"),
        (ValueType.JSON, 1),
        (ValueType.JSON, "{"),
    ]:
        with pytest.raises(expected_exception=ExpressionError):
            ValueCodec.coerce(value_type=value_type, value=value)


def test_value_codec_none() -> None:
    """Check ``None`` round-trips through the codec."""
    if ValueCodec.coerce(value_type=ValueType.STRING, value=None) is not None:
        pytest.fail(reason="None coercion failed.")
