# Copyright (c) 2026 Project contributors
"""Deterministic graph execution, typed variables, and run snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final, final

from exactus.tools.record.expressions import (
    ExpressionError,
    ExpressionEvaluator,
)
from exactus.tools.record.model import (
    ActionRunRecord,
    ExecutionRun,
    Flow,
    FlowEdge,
    FlowExecutionResult,
    RunStatus,
    RuntimeVariable,
    RunTransition,
    TransitionMode,
    ValueType,
    VariableDefinition,
    VariableScope,
    Workspace,
)

if TYPE_CHECKING:
    from exactus.tools.record.selectors import SelectorDef


@final
class Constants:
    """Group module-level constants.

    Attributes:
        system_flow_succeeded: Grouped module constant.
        system_flow_failed: Grouped module constant.

    """

    system_flow_succeeded: Final[str] = "flow_succeeded"
    system_flow_failed: Final[str] = "flow_failed"


class ExecutionError(ValueError):
    """Represent ExecutionError."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EdgeTraversalCount:
    """Represent EdgeTraversalCount.

    Attributes:
        source_flow_id: Source flow id.
        target_flow_id: Target flow id.
        mode: Mode.
        condition_expression: Condition expression.
        count: Count.

    """

    source_flow_id: str
    target_flow_id: str
    mode: TransitionMode
    condition_expression: str | None
    count: int

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.count < 0:
            msg: str = "Edge traversal count cannot be negative."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionState:
    """Represent ExecutionState.

    Attributes:
        run_id: Run id.
        initial_flow_id: Initial flow id.
        current_flow_id: Current flow id.
        device_mode: Device mode.
        started_at_utc: Started at utc.
        variables: Variables.
        action_records: Action records.
        transitions: Transitions.
        traversal_counts: Traversal counts.
        follow_connections: Whether finishing a flow continues along its
            connections; false runs the initial flow alone.

    """

    run_id: str
    initial_flow_id: str
    current_flow_id: str
    device_mode: str
    started_at_utc: str
    variables: tuple[RuntimeVariable, ...]
    action_records: tuple[ActionRunRecord, ...] = ()
    transitions: tuple[RunTransition, ...] = ()
    traversal_counts: tuple[EdgeTraversalCount, ...] = ()
    follow_connections: bool = True

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if any(
            value.strip() == ""
            for value in (
                self.run_id,
                self.initial_flow_id,
                self.current_flow_id,
                self.started_at_utc,
            )
        ):
            msg: str = "Execution state requires non-empty identity values."
            raise ValueError(msg)
        names: tuple[str, ...] = tuple(
            variable.name for variable in self.variables
        )
        if len(set(names)) != len(names):
            msg = "Execution variables must have unique names."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class FlowDispatchRequest:
    """Represent FlowDispatchRequest.

    Attributes:
        run_id: Run id.
        flow: Flow.
        device_mode: Device mode.
        variables: Variables.
        restore_checkpoint_artifact_id: Restore checkpoint artifact id.
        origin: Origin of the target the flow's local URLs move to.
        selectors: Project selectors the flow's actions may refer to.
        probes: Selector probe variables to measure when the flow ends,
            because a connection condition reads them.
        project_id: Project id.
        project_name: Project name.
        project_revision: Project revision.
        context_base_url: Context base URL.

    """

    run_id: str
    flow: Flow
    device_mode: str
    variables: tuple[RuntimeVariable, ...]
    restore_checkpoint_artifact_id: str | None = None
    origin: str | None = None
    selectors: tuple[SelectorDef, ...] = ()
    probes: tuple[str, ...] = ()
    project_id: str = ""
    project_name: str = ""
    project_revision: str = ""
    context_base_url: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckpointCaptureRequest:
    """Represent CheckpointCaptureRequest.

    Attributes:
        run_id: Run id.
        checkpoint_id: Checkpoint id.
        flow_id: Flow id.
        event_id: Event id.

    """

    run_id: str
    checkpoint_id: str
    flow_id: str
    event_id: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionDecision:
    """Represent ExecutionDecision.

    Attributes:
        state: State.
        next_flow_id: Next flow id.
        completed_run: Completed run.
        selected_edge: Selected edge.

    """

    state: ExecutionState | None
    next_flow_id: str | None
    completed_run: ExecutionRun | None
    selected_edge: FlowEdge | None


class VariableResolver:
    """Represent VariableResolver."""

    @classmethod
    def initial_variables(
        cls,
        *,
        workspace: Workspace,
        supplied: tuple[RuntimeVariable, ...],
    ) -> tuple[RuntimeVariable, ...]:
        """Return initial variables.

        Args:
            workspace: Workspace.
            supplied: Supplied.

        Returns:
            The resulting value.

        Raises:
            ExecutionError: When the operation cannot complete.

        """
        supplied_map: dict[str, RuntimeVariable] = {
            variable.name: variable for variable in supplied
        }
        definitions: dict[str, VariableDefinition] = {
            definition.name: definition for definition in workspace.variables
        }
        unknown: tuple[str, ...] = tuple(
            sorted(name for name in supplied_map if name not in definitions),
        )
        if unknown:
            msg: str = f"Unknown execution variables: {', '.join(unknown)}"
            raise ExecutionError(msg)
        resolved: list[RuntimeVariable] = []
        for definition in workspace.variables:
            supplied_variable: RuntimeVariable | None = supplied_map.get(
                definition.name,
            )
            if supplied_variable is not None:
                cls._validate_type(
                    definition=definition,
                    variable=supplied_variable,
                )
                resolved.append(
                    replace(
                        supplied_variable,
                        secret=definition.scope is VariableScope.CREDENTIAL,
                    ),
                )
                continue
            if definition.default_value is not None:
                resolved.append(
                    RuntimeVariable(
                        name=definition.name,
                        value_type=definition.value_type,
                        value=definition.default_value,
                        secret=False,
                    ),
                )
                continue
            if definition.scope in {
                VariableScope.ENVIRONMENT,
                VariableScope.CREDENTIAL,
            }:
                msg = (
                    f"Runtime value required for {definition.scope.value}"
                    f" variable {definition.name}."
                )
                raise ExecutionError(msg)
        return tuple(resolved)

    @classmethod
    def validate_flow_parameters(
        cls,
        *,
        flow: Flow,
        variables: tuple[RuntimeVariable, ...],
    ) -> tuple[RuntimeVariable, ...]:
        """Return validate flow parameters.

        Args:
            flow: Flow.
            variables: Variables.

        Returns:
            The resulting value.

        Raises:
            ExecutionError: When the operation cannot complete.

        """
        variable_map: dict[str, RuntimeVariable] = {
            variable.name: variable for variable in variables
        }
        additions: list[RuntimeVariable] = []
        for parameter in flow.parameters:
            if (variable := variable_map.get(parameter.name)) is not None:
                if variable.value_type is not parameter.value_type:
                    msg: str = (
                        f"Flow parameter {parameter.name} expects"
                        f" {parameter.value_type.value}, got"
                        f" {variable.value_type.value}."
                    )
                    raise ExecutionError(msg)
                continue
            if parameter.default_value is not None:
                additions.append(
                    RuntimeVariable(
                        name=parameter.name,
                        value_type=parameter.value_type,
                        value=parameter.default_value,
                    ),
                )
                continue
            if parameter.required:
                msg = f"Missing required Flow parameter: {parameter.name}"
                raise ExecutionError(msg)
        return cls.merge(current=variables, updates=tuple(additions))

    @staticmethod
    def merge(
        *,
        current: tuple[RuntimeVariable, ...],
        updates: tuple[RuntimeVariable, ...],
    ) -> tuple[RuntimeVariable, ...]:
        """Return merge.

        Args:
            current: Current.
            updates: Updates.

        Returns:
            The resulting value.

        """
        update_map: dict[str, RuntimeVariable] = {
            variable.name: variable for variable in updates
        }
        merged: list[RuntimeVariable] = [
            update_map.pop(variable.name, variable) for variable in current
        ]
        merged.extend(update_map[name] for name in sorted(update_map))
        return tuple(merged)

    @staticmethod
    def redact(
        *,
        variables: tuple[RuntimeVariable, ...],
    ) -> tuple[RuntimeVariable, ...]:
        """Return redact.

        Args:
            variables: Variables.

        Returns:
            The resulting value.

        """
        return tuple(
            replace(variable, value=None) if variable.secret else variable
            for variable in variables
        )

    @staticmethod
    def _validate_type(
        *,
        definition: VariableDefinition,
        variable: RuntimeVariable,
    ) -> None:
        """Handle validate type.

        Args:
            definition: Definition.
            variable: Variable.

        Raises:
            ExecutionError: When the operation cannot complete.

        """
        if variable.value_type is definition.value_type:
            return
        msg: str = (
            f"Variable {definition.name} expects"
            f" {definition.value_type.value}, got {variable.value_type.value}."
        )
        raise ExecutionError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionStartRequest:
    """Represent ExecutionStartRequest.

    Attributes:
        run_id: Run id.
        initial_flow_id: Initial flow id.
        device_mode: Device mode.
        started_at_utc: Started at utc.
        supplied_variables: Supplied variables.
        follow_connections: Continue along connections after the first flow.

    """

    run_id: str
    initial_flow_id: str
    device_mode: str
    started_at_utc: str
    supplied_variables: tuple[RuntimeVariable, ...] = ()
    follow_connections: bool = True


class ExecutionEngine:
    """Represent ExecutionEngine."""

    @classmethod
    def start(
        cls,
        *,
        workspace: Workspace,
        request: ExecutionStartRequest,
    ) -> ExecutionState:
        """Return start.

        Args:
            workspace: Workspace.
            request: Request.

        Returns:
            The resulting value.

        Raises:
            ExecutionError: When the operation cannot complete.

        """
        flow: Flow = cls._flow(
            workspace=workspace,
            flow_id=request.initial_flow_id,
        )
        if not flow.applies_to(device_mode=request.device_mode):
            msg: str = (
                f"Flow {flow.name} is not scoped to {request.device_mode}."
            )
            raise ExecutionError(msg)
        variables: tuple[RuntimeVariable, ...] = (
            VariableResolver.validate_flow_parameters(
                flow=flow,
                variables=VariableResolver.initial_variables(
                    workspace=workspace,
                    supplied=request.supplied_variables,
                ),
            )
        )
        return ExecutionState(
            run_id=request.run_id,
            initial_flow_id=request.initial_flow_id,
            current_flow_id=request.initial_flow_id,
            device_mode=request.device_mode,
            started_at_utc=request.started_at_utc,
            variables=variables,
            follow_connections=request.follow_connections,
        )

    @classmethod
    def complete_flow(
        cls,
        *,
        workspace: Workspace,
        state: ExecutionState,
        result: FlowExecutionResult,
        finished_at_utc: str,
    ) -> ExecutionDecision:
        """Return complete flow.

        Args:
            workspace: Workspace.
            state: State.
            result: Result.
            finished_at_utc: Finished at utc.

        Returns:
            The resulting value.

        Raises:
            ExecutionError: When the operation cannot complete.

        """
        if result.run_id != state.run_id:
            msg: str = "Flow result run ID does not match active execution."
            raise ExecutionError(msg)
        if result.flow_id != state.current_flow_id:
            msg = "Flow result does not match the active Flow."
            raise ExecutionError(msg)
        variables: tuple[RuntimeVariable, ...] = VariableResolver.merge(
            current=state.variables,
            updates=result.outputs,
        )
        system_variables: tuple[RuntimeVariable, ...] = (
            RuntimeVariable(
                name=Constants.system_flow_succeeded,
                value_type=ValueType.BOOLEAN,
                value=result.status is RunStatus.SUCCEEDED,
            ),
            RuntimeVariable(
                name=Constants.system_flow_failed,
                value_type=ValueType.BOOLEAN,
                value=result.status is RunStatus.FAILED,
            ),
        )
        variables_for_conditions: tuple[RuntimeVariable, ...] = (
            VariableResolver.merge(current=variables, updates=system_variables)
        )
        selected: FlowEdge | None = (
            None
            if result.status is RunStatus.CANCELLED
            or not state.follow_connections
            else cls._select_edge(
                workspace=workspace,
                state=state,
                result=result,
                variables=variables_for_conditions,
            )
        )
        action_records: tuple[ActionRunRecord, ...] = (
            *state.action_records,
            *result.action_records,
        )
        if selected is None:
            terminal_status: RunStatus = (
                RunStatus.CANCELLED
                if result.status is RunStatus.CANCELLED
                else (
                    RunStatus.SUCCEEDED
                    if result.status is RunStatus.SUCCEEDED
                    else RunStatus.FAILED
                )
            )
            run: ExecutionRun = ExecutionRun(
                run_id=state.run_id,
                initial_flow_id=state.initial_flow_id,
                current_flow_id=None,
                device_mode=state.device_mode,
                status=terminal_status,
                started_at_utc=state.started_at_utc,
                finished_at_utc=finished_at_utc,
                action_records=action_records,
                transitions=state.transitions,
                variables=VariableResolver.redact(variables=variables),
                failure_reason=(
                    result.error
                    if terminal_status is RunStatus.FAILED
                    else None
                ),
            )
            return ExecutionDecision(
                state=None,
                next_flow_id=None,
                completed_run=run,
                selected_edge=None,
            )
        next_flow: Flow = cls._flow(
            workspace=workspace,
            flow_id=selected.target_flow_id,
        )
        if not next_flow.applies_to(device_mode=state.device_mode):
            msg = (
                f"Selected Flow {next_flow.name} is not scoped to"
                f" {state.device_mode}."
            )
            raise ExecutionError(msg)
        next_variables: tuple[RuntimeVariable, ...] = (
            VariableResolver.validate_flow_parameters(
                flow=next_flow,
                variables=variables,
            )
        )
        transition: RunTransition = RunTransition(
            source_flow_id=selected.source_flow_id,
            target_flow_id=selected.target_flow_id,
            mode=selected.mode,
            reason=cls._transition_reason(edge=selected, result=result),
        )
        next_state: ExecutionState = replace(
            state,
            current_flow_id=selected.target_flow_id,
            variables=next_variables,
            action_records=action_records,
            transitions=(*state.transitions, transition),
            traversal_counts=cls._increment_count(
                counts=state.traversal_counts,
                edge=selected,
            ),
        )
        return ExecutionDecision(
            state=next_state,
            next_flow_id=selected.target_flow_id,
            completed_run=None,
            selected_edge=selected,
        )

    @classmethod
    def _select_edge(
        cls,
        *,
        workspace: Workspace,
        state: ExecutionState,
        result: FlowExecutionResult,
        variables: tuple[RuntimeVariable, ...],
    ) -> FlowEdge | None:
        """Return select edge.

        Args:
            workspace: Workspace.
            state: State.
            result: Result.
            variables: Variables.

        Returns:
            The resulting value.

        """
        outgoing: tuple[FlowEdge, ...] = tuple(
            sorted(
                (
                    edge
                    for edge in workspace.edges
                    if edge.source_flow_id == state.current_flow_id
                ),
                key=lambda edge: edge.priority,
                reverse=True,
            ),
        )
        available: tuple[FlowEdge, ...] = tuple(
            edge
            for edge in outgoing
            if cls._remaining_traversals(
                counts=state.traversal_counts,
                edge=edge,
            )
            > 0
        )
        if (
            result.status is RunStatus.FAILED
            and (
                retry := next(
                    (
                        edge
                        for edge in available
                        if edge.mode is TransitionMode.RETRY
                    ),
                    None,
                )
            )
            is not None
        ):
            return retry
        if (
            conditional := next(
                (
                    edge
                    for edge in available
                    if edge.mode is TransitionMode.CONDITION
                    and cls._condition_matches(edge=edge, variables=variables)
                ),
                None,
            )
        ) is not None:
            return conditional
        if (
            result.status is RunStatus.SUCCEEDED
            and (
                always := next(
                    (
                        edge
                        for edge in available
                        if edge.mode is TransitionMode.ALWAYS
                    ),
                    None,
                )
            )
            is not None
        ):
            return always
        if (
            fallback := next(
                (
                    edge
                    for edge in available
                    if edge.mode is TransitionMode.FALLBACK
                ),
                None,
            )
        ) is not None:
            return fallback
        return next(
            (
                edge
                for edge in available
                if edge.mode is TransitionMode.FINALLY
            ),
            None,
        )

    @classmethod
    def _remaining_traversals(
        cls,
        *,
        counts: tuple[EdgeTraversalCount, ...],
        edge: FlowEdge,
    ) -> int:
        """Return remaining traversals.

        Args:
            counts: Counts.
            edge: Edge.

        Returns:
            The resulting value.

        """
        count: int = next(
            (
                item.count
                for item in counts
                if cls._same_edge(count=item, edge=edge)
            ),
            0,
        )
        return max(0, edge.max_traversals - count)

    @classmethod
    def _increment_count(
        cls,
        *,
        counts: tuple[EdgeTraversalCount, ...],
        edge: FlowEdge,
    ) -> tuple[EdgeTraversalCount, ...]:
        """Return increment count.

        Args:
            counts: Counts.
            edge: Edge.

        Returns:
            The resulting value.

        """
        if (
            existing := next(
                (
                    item
                    for item in counts
                    if cls._same_edge(count=item, edge=edge)
                ),
                None,
            )
        ) is None:
            return (
                *counts,
                EdgeTraversalCount(
                    source_flow_id=edge.source_flow_id,
                    target_flow_id=edge.target_flow_id,
                    mode=edge.mode,
                    condition_expression=edge.condition_expression,
                    count=1,
                ),
            )
        return tuple(
            replace(item, count=item.count + 1) if item == existing else item
            for item in counts
        )

    @staticmethod
    def _condition_matches(
        *,
        edge: FlowEdge,
        variables: tuple[RuntimeVariable, ...],
    ) -> bool:
        """Return condition matches.

        Args:
            edge: Edge.
            variables: Variables.

        Returns:
            The resulting value.

        Raises:
            ExecutionError: When the operation cannot complete.

        """
        if edge.condition_expression is None:
            return False
        try:
            return ExpressionEvaluator.evaluate(
                expression=edge.condition_expression,
                variables=variables,
            )
        except ExpressionError as error:
            msg: str = (
                f"Invalid edge condition {edge.condition_expression!r}:"
                f" {error}"
            )
            raise ExecutionError(msg) from error

    @staticmethod
    def _same_edge(*, count: EdgeTraversalCount, edge: FlowEdge) -> bool:
        """Return same edge.

        Args:
            count: Count.
            edge: Edge.

        Returns:
            The resulting value.

        """
        return (
            count.source_flow_id == edge.source_flow_id
            and count.target_flow_id == edge.target_flow_id
            and (count.mode is edge.mode)
            and (count.condition_expression == edge.condition_expression)
        )

    @staticmethod
    def _transition_reason(
        *,
        edge: FlowEdge,
        result: FlowExecutionResult,
    ) -> str:
        """Return transition reason.

        Args:
            edge: Edge.
            result: Result.

        Returns:
            The resulting value.

        """
        if edge.mode is TransitionMode.CONDITION:
            return f"condition: {edge.condition_expression}"
        if edge.mode is TransitionMode.RETRY:
            return f"retry after {result.status.value}"
        return edge.mode.value

    @staticmethod
    def _flow(*, workspace: Workspace, flow_id: str) -> Flow:
        """Return flow.

        Args:
            workspace: Workspace.
            flow_id: Flow id.

        Returns:
            The resulting value.

        Raises:
            ExecutionError: When the operation cannot complete.

        """
        if (
            flow := next(
                (
                    candidate
                    for candidate in workspace.flows
                    if candidate.flow_id == flow_id
                ),
                None,
            )
        ) is None:
            msg: str = f"Unknown Flow ID: {flow_id}"
            raise ExecutionError(msg)
        return flow
