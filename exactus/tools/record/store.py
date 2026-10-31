# Copyright (c) 2026 Project contributors
"""Deterministic Flow workspace state and JSON persistence."""

from __future__ import annotations

from dataclasses import replace
from json import JSONDecodeError, dumps, loads
from os import fsync
from pathlib import Path
from re import fullmatch
from tempfile import NamedTemporaryFile
from typing import Final, cast, final
from urllib.parse import urlsplit

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
    ConditionOperator,
    DeviceMode,
    EventKind,
    ExecutionRun,
    Flow,
    FlowEdge,
    FlowOutput,
    FlowParameter,
    FlowRecording,
    FlowSettings,
    HttpHeader,
    JsonCondition,
    NetworkExpectation,
    OutputBinding,
    OutputSource,
    PositionPointerAction,
    Profile,
    QueryCondition,
    RunStatus,
    RuntimeVariable,
    RunTransition,
    ScreenshotArtifact,
    Target,
    TargetMode,
    TimelineEvent,
    TimelineLayer,
    TransitionMode,
    UrlMatchMode,
    ValueType,
    VariableDefinition,
    VariableScope,
    Workspace,
    default_profiles,
)
from exactus.tools.record.model import Constants as ModelConstants
from exactus.tools.record.project_info import ProjectInfoCodec
from exactus.tools.record.selector_usage import (
    SelectorUsage,
    rename_references,
    usage_index,
)
from exactus.tools.record.selectors import (
    RunMode,
    SelectorCodec,
    SelectorDef,
    TargetScope,
    validate_selectors,
)

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        workspace_version: Grouped module constant.
        previous_fields: Grouped module constant.

    """

    workspace_version: Final[int] = 3
    previous_fields: Final[tuple[str, ...]] = (
        "selector",
        "url",
        "payload",
        "label",
        "when_expression",
    )


class WorkspaceError(ValueError):
    """Represent WorkspaceError."""


class FlowStore:
    """Represent FlowStore."""

    def __init__(self, *, workspace: Workspace) -> None:
        """Handle init.

        Args:
            workspace: Workspace.

        """
        self._workspace: Workspace = workspace

    @property
    def workspace(self) -> Workspace:
        """The workspace value.

        Returns:
            The resulting value.

        """
        return self._workspace

    def get_flow(self, *, flow_id: str) -> Flow:
        """Return get flow.

        Args:
            flow_id: Flow id.

        Returns:
            The resulting value.

        Raises:
            KeyError: When the operation cannot complete.

        """
        if (
            flow := next(
                (
                    candidate
                    for candidate in self._workspace.flows
                    if candidate.flow_id == flow_id
                ),
                None,
            )
        ) is None:
            raise KeyError(flow_id)
        return flow

    def get_event(self, *, flow_id: str, event_id: str) -> TimelineEvent:
        """Return get event.

        Args:
            flow_id: Flow id.
            event_id: Event id.

        Returns:
            The resulting value.

        Raises:
            KeyError: When the operation cannot complete.

        """
        if (
            event := next(
                (
                    candidate
                    for candidate in self.get_flow(flow_id=flow_id).events
                    if candidate.event_id == event_id
                ),
                None,
            )
        ) is None:
            raise KeyError(event_id)
        return event

    def add_flow(self, *, flow: Flow) -> None:
        """Handle add flow.

        Args:
            flow: Flow.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if any(
            candidate.flow_id == flow.flow_id
            for candidate in self._workspace.flows
        ):
            msg: str = f"Duplicate Flow ID: {flow.flow_id}"
            raise ValueError(msg)
        self._workspace = replace(
            self._workspace,
            flows=(*self._workspace.flows, flow),
        )

    def update_flow(self, *, flow_id: str, settings: FlowSettings) -> None:
        """Handle update flow.

        Args:
            flow_id: Flow id.
            settings: Settings.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if settings.name.strip() == "":
            msg: str = "Flow name cannot be empty."
            raise ValueError(msg)
        self._replace_flow(
            flow=self.get_flow(flow_id=flow_id).with_settings(
                settings=replace(settings, name=settings.name.strip()),
            ),
        )

    def delete_flow(self, *, flow_id: str) -> None:
        """Handle delete flow.

        Args:
            flow_id: Flow id.

        """
        self.get_flow(flow_id=flow_id)
        self._workspace = replace(
            self._workspace,
            flows=tuple(
                flow
                for flow in self._workspace.flows
                if flow.flow_id != flow_id
            ),
            edges=tuple(
                edge
                for edge in self._workspace.edges
                if flow_id not in (edge.source_flow_id, edge.target_flow_id)
            ),
            screenshots=tuple(
                artifact
                for artifact in self._workspace.screenshots
                if artifact.flow_id != flow_id
            ),
            variables=tuple(
                definition
                for definition in self._workspace.variables
                if definition.flow_id != flow_id
            ),
            checkpoint_definitions=tuple(
                checkpoint
                for checkpoint in self._workspace.checkpoint_definitions
                if checkpoint.flow_id != flow_id
            ),
            checkpoint_artifacts=tuple(
                artifact
                for artifact in self._workspace.checkpoint_artifacts
                if artifact.flow_id != flow_id
            ),
        )

    def add_recording(self, *, flow_id: str, recording: FlowRecording) -> None:
        """Persist an empty parent before the first captured action arrives.

        Args:
            flow_id: Flow that owns the recording.
            recording: Parent task to add.

        """
        flow: Flow = self.get_flow(flow_id=flow_id)
        self._replace_flow(
            flow=replace(flow, recordings=(*flow.recordings, recording)),
        )

    def save_target(self, *, target: Target) -> None:
        """Replace the application under test.

        Args:
            target: Validated target.

        """
        self._workspace = replace(self._workspace, target=target)

    def save_profile(self, *, profile: Profile) -> None:
        """Add a profile, or replace the one with the same identifier.

        Args:
            profile: Validated browser conditions.

        """
        known: tuple[Profile, ...] = self._workspace.profiles
        self._workspace = replace(
            self._workspace,
            profiles=tuple(
                profile if item.profile_id == profile.profile_id else item
                for item in known
            )
            if any(item.profile_id == profile.profile_id for item in known)
            else (*known, profile),
        )

    def delete_profile(self, *, profile_id: str) -> None:
        """Remove a profile that no flow depends on.

        Args:
            profile_id: Profile to remove.

        Raises:
            WorkspaceError: When it is unknown, the last one, or still in use.

        """
        known: tuple[Profile, ...] = self._workspace.profiles
        if all(item.profile_id != profile_id for item in known):
            msg: str = f"Unknown profile: {profile_id}"
            raise WorkspaceError(msg)
        if len(known) == 1:
            msg = "A project needs at least one profile."
            raise WorkspaceError(msg)
        users: list[str] = [
            flow.name
            for flow in self._workspace.flows
            if profile_id in flow.device_modes
        ]
        if users:
            msg = (
                f"{', '.join(users)} {
                    ('is' if len(users) == 1 else 'are')
                } scoped to this profile. Change their "
                f"scope first."
            )
            raise WorkspaceError(msg)
        self._workspace = replace(
            self._workspace,
            profiles=tuple(
                item for item in known if item.profile_id != profile_id
            ),
        )

    def rename_recording(
        self,
        *,
        flow_id: str,
        recording_id: str,
        label: str,
    ) -> None:
        """Rename a recording parent without touching its actions.

        Args:
            flow_id: Flow that owns the recording.
            recording_id: Parent task to rename.
            label: Nonempty replacement name.

        """
        flow: Flow = self.get_flow(flow_id=flow_id)
        group: FlowRecording = self._recording(
            flow=flow,
            recording_id=recording_id,
        )
        self._replace_flow(
            flow=replace(
                flow,
                recordings=tuple(
                    replace(item, label=label) if item is group else item
                    for item in flow.recordings
                ),
            ),
        )

    def shift_recording(
        self,
        *,
        flow_id: str,
        recording_id: str,
        delta_ms: int,
        limit_ms: int,
    ) -> None:
        """Move a recording parent and all its actions by one time delta.

        The shift is atomic: every child keeps its offset from the parent, so
        selectors, contracts and delays between actions are unchanged.

        Args:
            flow_id: Flow that owns the recording.
            recording_id: Parent task to move.
            delta_ms: Signed shift applied to the parent and every child.
            limit_ms: Latest allowed authored time.

        Raises:
            WorkspaceError: When the shift leaves the timeline.

        """
        flow: Flow = self.get_flow(flow_id=flow_id)
        group: FlowRecording = self._recording(
            flow=flow,
            recording_id=recording_id,
        )
        children: tuple[TimelineEvent, ...] = tuple(
            event
            for event in flow.events
            if event.recording_group_id == recording_id
        )
        earliest: int = min(
            (group.start_ms, *(event.elapsed_ms for event in children)),
        )
        latest: int = max(
            (group.start_ms, *(event.elapsed_ms for event in children)),
        )
        if earliest + delta_ms < 0 or latest + delta_ms > limit_ms:
            msg: str = "The recording would leave the timeline."
            raise WorkspaceError(msg)
        shifted: list[TimelineEvent] = sorted(
            (
                replace(event, elapsed_ms=event.elapsed_ms + delta_ms)
                if event.recording_group_id == recording_id
                else event
                for event in flow.events
            ),
            key=lambda event: (event.elapsed_ms, event.sequence),
        )
        self._replace_flow(
            flow=replace(
                flow.with_events(
                    events=tuple(
                        (
                            event.with_sequence(sequence=position)
                            for position, event in enumerate(iterable=shifted)
                        ),
                    ),
                ),
                recordings=tuple(
                    replace(item, start_ms=item.start_ms + delta_ms)
                    if item is group
                    else item
                    for item in flow.recordings
                ),
            ),
        )

    def delete_recording(self, *, flow_id: str, recording_id: str) -> None:
        """Remove a recording parent, its actions and their evidence.

        Args:
            flow_id: Flow that owns the recording.
            recording_id: Parent task to delete.

        """
        flow: Flow = self.get_flow(flow_id=flow_id)
        _ = self._recording(flow=flow, recording_id=recording_id)
        for event in tuple(
            event
            for event in flow.events
            if event.recording_group_id == recording_id
        ):
            self.delete_event(flow_id=flow_id, event_id=event.event_id)
        remaining: Flow = self.get_flow(flow_id=flow_id)
        self._replace_flow(
            flow=replace(
                remaining,
                recordings=tuple(
                    item
                    for item in remaining.recordings
                    if item.recording_id != recording_id
                ),
            ),
        )

    def append_event(self, *, event: TimelineEvent) -> TimelineEvent:
        """Return append event.

        Args:
            event: Event.

        Returns:
            The resulting value.

        """
        flow: Flow = self.get_flow(flow_id=event.flow_id)
        if (
            existing := next(
                (
                    candidate
                    for candidate in flow.events
                    if candidate.event_id == event.event_id
                ),
                None,
            )
        ) is not None:
            return existing
        appended: TimelineEvent = event.with_sequence(
            sequence=len(flow.events),
        )
        self._replace_flow(
            flow=flow.with_events(events=(*flow.events, appended)),
        )
        return appended

    def update_event(self, *, event: TimelineEvent) -> None:
        """Replace an existing step without changing its identity or order.

        Args:
            event: Recorded timeline event.

        """
        current: TimelineEvent = self.get_event(
            flow_id=event.flow_id,
            event_id=event.event_id,
        )
        self._replace_event(event=replace(event, sequence=current.sequence))

    def delete_event(self, *, flow_id: str, event_id: str) -> None:
        """Handle delete event.

        Args:
            flow_id: Flow id.
            event_id: Event id.

        """
        flow: Flow = self.get_flow(flow_id=flow_id)
        remaining: tuple[TimelineEvent, ...] = tuple(
            (
                event.with_sequence(sequence=index)
                for index, event in enumerate(
                    iterable=(
                        candidate
                        for candidate in flow.events
                        if candidate.event_id != event_id
                    ),
                )
            ),
        )
        self._replace_flow(flow=flow.with_events(events=remaining))
        self._workspace = replace(
            self._workspace,
            screenshots=tuple(
                artifact
                for artifact in self._workspace.screenshots
                if artifact.event_id != event_id or artifact.flow_id != flow_id
            ),
            checkpoint_definitions=tuple(
                checkpoint
                for checkpoint in self._workspace.checkpoint_definitions
                if checkpoint.event_id != event_id
                or checkpoint.flow_id != flow_id
            ),
            checkpoint_artifacts=tuple(
                artifact
                for artifact in self._workspace.checkpoint_artifacts
                if artifact.event_id != event_id or artifact.flow_id != flow_id
            ),
        )

    def move_event(self, *, flow_id: str, event_id: str, offset: int) -> None:
        """Handle move event.

        Args:
            flow_id: Flow id.
            event_id: Event id.
            offset: Offset.

        """
        flow: Flow = self.get_flow(flow_id=flow_id)
        current_index: int = next(
            (
                index
                for index, event in enumerate(iterable=flow.events)
                if event.event_id == event_id
            ),
        )
        target_index: int = max(
            0,
            min(len(flow.events) - 1, current_index + offset),
        )
        if target_index == current_index:
            return
        reordered: list[TimelineEvent] = list(flow.events)
        moved: TimelineEvent = reordered.pop(current_index)
        reordered.insert(target_index, moved)
        self._replace_flow(
            flow=flow.with_events(
                events=tuple(
                    (
                        event.with_sequence(sequence=index)
                        for index, event in enumerate(iterable=reordered)
                    ),
                ),
            ),
        )

    def place_event(self, *, flow_id: str, event_id: str, index: int) -> None:
        """Drop a step at an absolute replay position.

        Each position keeps its authored time slot, so the timeline stays
        monotonic with replay order after the move.

        Args:
            flow_id: Flow id.
            event_id: Event id.
            index: Zero-based destination position.

        """
        flow: Flow = self.get_flow(flow_id=flow_id)
        slots: list[int] = sorted(event.elapsed_ms for event in flow.events)
        reordered: list[TimelineEvent] = list(flow.events)
        moved: TimelineEvent = reordered.pop(
            next(
                (
                    position
                    for position, event in enumerate(iterable=reordered)
                    if event.event_id == event_id
                ),
            ),
        )
        reordered.insert(max(0, min(len(flow.events) - 1, index)), moved)
        self._replace_flow(
            flow=flow.with_events(
                events=tuple(
                    (
                        replace(
                            event,
                            sequence=position,
                            elapsed_ms=slots[position],
                        )
                        for position, event in enumerate(iterable=reordered)
                    ),
                ),
            ),
        )

    def retime_event(
        self,
        *,
        flow_id: str,
        event_id: str,
        elapsed_ms: int,
    ) -> None:
        """Move a step to a new timeline time and order the flow by time.

        Args:
            flow_id: Flow id.
            event_id: Event id.
            elapsed_ms: Non-negative authored start time.

        Raises:
            WorkspaceError: When the step predates its recording parent.

        """
        flow: Flow = self.get_flow(flow_id=flow_id)
        selected: TimelineEvent = self.get_event(
            flow_id=flow_id,
            event_id=event_id,
        )
        if any(
            group.recording_id == selected.recording_group_id
            and elapsed_ms < group.start_ms
            for group in flow.recordings
        ):
            msg: str = "An action cannot start before its recording parent."
            raise WorkspaceError(msg)
        timed: list[TimelineEvent] = sorted(
            (
                replace(event, elapsed_ms=elapsed_ms)
                if event.event_id == event_id
                else event
                for event in flow.events
            ),
            key=lambda event: (
                event.elapsed_ms,
                event.event_id == event_id,
                event.sequence,
            ),
        )
        self._replace_flow(
            flow=flow.with_events(
                events=tuple(
                    (
                        event.with_sequence(sequence=position)
                        for position, event in enumerate(iterable=timed)
                    ),
                ),
            ),
        )

    def add_expectation(
        self,
        *,
        flow_id: str,
        event_id: str,
        expectation: NetworkExpectation,
    ) -> None:
        """Handle add expectation.

        Args:
            flow_id: Flow id.
            event_id: Event id.
            expectation: Expectation.

        Raises:
            ValueError: When the operation cannot complete.

        """
        event: TimelineEvent = self.get_event(
            flow_id=flow_id,
            event_id=event_id,
        )
        if any(
            candidate.expectation_id == expectation.expectation_id
            for candidate in event.expectations
        ):
            msg: str = (
                f"Duplicate expectation ID: {expectation.expectation_id}"
            )
            raise ValueError(msg)
        self._replace_event(
            event=event.with_expectations(
                expectations=(*event.expectations, expectation),
            ),
        )

    def remove_expectation(
        self,
        *,
        flow_id: str,
        event_id: str,
        expectation_id: str,
    ) -> None:
        """Handle remove expectation.

        Args:
            flow_id: Flow id.
            event_id: Event id.
            expectation_id: Expectation id.

        """
        event: TimelineEvent = self.get_event(
            flow_id=flow_id,
            event_id=event_id,
        )
        self._replace_event(
            event=event.with_expectations(
                expectations=tuple(
                    expectation
                    for expectation in event.expectations
                    if expectation.expectation_id != expectation_id
                ),
            ),
        )

    def set_action_contract(
        self,
        *,
        flow_id: str,
        event_id: str,
        contract: ActionContract,
    ) -> None:
        """Handle set action contract.

        Args:
            flow_id: Flow id.
            event_id: Event id.
            contract: Contract.

        """
        self._replace_event(
            event=self.get_event(
                flow_id=flow_id,
                event_id=event_id,
            ).with_contract(contract=contract),
        )

    def set_flow_interface(
        self,
        *,
        flow_id: str,
        parameters: tuple[FlowParameter, ...],
        outputs: tuple[FlowOutput, ...],
    ) -> None:
        """Handle set flow interface.

        Args:
            flow_id: Flow id.
            parameters: Parameters.
            outputs: Outputs.

        """
        self._replace_flow(
            flow=replace(
                self.get_flow(flow_id=flow_id),
                parameters=parameters,
                outputs=outputs,
            ),
        )

    def add_variable(self, *, definition: VariableDefinition) -> None:
        """Handle add variable.

        Args:
            definition: Definition.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if any(
            candidate.name == definition.name
            for candidate in self._workspace.variables
        ):
            msg: str = f"Duplicate variable name: {definition.name}"
            raise ValueError(msg)
        if definition.flow_id is not None:
            self.get_flow(flow_id=definition.flow_id)
        self._workspace = replace(
            self._workspace,
            variables=(*self._workspace.variables, definition),
        )

    def remove_variable(self, *, name: str) -> None:
        """Handle remove variable.

        Args:
            name: Name.

        """
        self._workspace = replace(
            self._workspace,
            variables=tuple(
                definition
                for definition in self._workspace.variables
                if definition.name != name
            ),
        )

    def add_checkpoint_definition(
        self,
        *,
        checkpoint: CheckpointDefinition,
    ) -> None:
        """Handle add checkpoint definition.

        Args:
            checkpoint: Checkpoint.

        Raises:
            ValueError: When the operation cannot complete.

        """
        self.get_flow(flow_id=checkpoint.flow_id)
        if checkpoint.event_id is not None:
            self.get_event(
                flow_id=checkpoint.flow_id,
                event_id=checkpoint.event_id,
            )
        if any(
            candidate.checkpoint_id == checkpoint.checkpoint_id
            for candidate in self._workspace.checkpoint_definitions
        ):
            msg: str = f"Duplicate checkpoint ID: {checkpoint.checkpoint_id}"
            raise ValueError(msg)
        self._workspace = replace(
            self._workspace,
            checkpoint_definitions=(
                *self._workspace.checkpoint_definitions,
                checkpoint,
            ),
        )

    def remove_checkpoint_definition(self, *, checkpoint_id: str) -> None:
        """Handle remove checkpoint definition.

        Args:
            checkpoint_id: Checkpoint id.

        """
        self._workspace = replace(
            self._workspace,
            checkpoint_definitions=tuple(
                checkpoint
                for checkpoint in self._workspace.checkpoint_definitions
                if checkpoint.checkpoint_id != checkpoint_id
            ),
            checkpoint_artifacts=tuple(
                artifact
                for artifact in self._workspace.checkpoint_artifacts
                if artifact.checkpoint_id != checkpoint_id
            ),
        )

    def add_checkpoint_artifact(self, *, artifact: CheckpointArtifact) -> None:
        """Handle add checkpoint artifact.

        Args:
            artifact: Artifact.

        """
        if any(
            candidate.artifact_id == artifact.artifact_id
            for candidate in self._workspace.checkpoint_artifacts
        ):
            return
        self._workspace = replace(
            self._workspace,
            checkpoint_artifacts=(
                *self._workspace.checkpoint_artifacts,
                artifact,
            ),
        )

    def upsert_run(self, *, run: ExecutionRun) -> None:
        """Handle upsert run.

        Args:
            run: Run.

        """
        self._workspace = replace(
            self._workspace,
            runs=(
                *(
                    candidate
                    for candidate in self._workspace.runs
                    if candidate.run_id != run.run_id
                ),
                run,
            ),
        )

    def add_screenshot(self, *, artifact: ScreenshotArtifact) -> None:
        """Handle add screenshot.

        Args:
            artifact: Artifact.

        """
        self.get_event(flow_id=artifact.flow_id, event_id=artifact.event_id)
        if any(
            candidate.artifact_id == artifact.artifact_id
            for candidate in self._workspace.screenshots
        ):
            return
        self._workspace = replace(
            self._workspace,
            screenshots=(*self._workspace.screenshots, artifact),
        )

    def add_edge(self, *, edge: FlowEdge) -> None:
        """Handle add edge.

        Args:
            edge: Edge.

        Raises:
            ValueError: When the operation cannot complete.

        """
        self.get_flow(flow_id=edge.source_flow_id)
        self.get_flow(flow_id=edge.target_flow_id)
        if (
            edge.source_flow_id == edge.target_flow_id
            and edge.mode is not TransitionMode.RETRY
        ):
            msg: str = "Only retry edges may transition to the same Flow."
            raise ValueError(msg)
        if edge in self._workspace.edges:
            return
        self._workspace = replace(
            self._workspace,
            edges=(*self._workspace.edges, edge),
        )

    def replace_edge(self, *, index: int, edge: FlowEdge) -> None:
        """Redefine one saved transition in place, keeping its position.

        Args:
            index: Zero-based position of the transition to redefine.
            edge: Replacement transition.

        Raises:
            ValueError: When the position, a flow or the policy is invalid,
                or the replacement duplicates another transition.

        """
        edges: tuple[FlowEdge, ...] = self._workspace.edges
        if not 0 <= index < len(edges):
            msg: str = "Choose an existing transition to redefine."
            raise ValueError(msg)
        self.get_flow(flow_id=edge.source_flow_id)
        self.get_flow(flow_id=edge.target_flow_id)
        if any(
            (
                candidate == edge
                for position, candidate in enumerate(iterable=edges)
                if position != index
            ),
        ):
            msg = "That transition already exists."
            raise ValueError(msg)
        self._workspace = replace(
            self._workspace,
            edges=(*edges[:index], edge, *edges[index + 1 :]),
        )

    def move_edge(self, *, index: int, to: int) -> None:
        """Move a saved transition to another position in the evaluation order.

        Transitions with equal priority are tried in this order.

        Args:
            index: Zero-based current position.
            to: Zero-based destination position.

        Raises:
            ValueError: When either position is outside the saved transitions.

        """
        edges: list[FlowEdge] = list(self._workspace.edges)
        if not (0 <= index < len(edges) and 0 <= to < len(edges)):
            msg: str = "Choose existing transition positions to reorder."
            raise ValueError(msg)
        edges.insert(to, edges.pop(index))
        self._workspace = replace(self._workspace, edges=tuple(edges))

    def remove_edge(self, *, edge: FlowEdge) -> None:
        """Handle remove edge.

        Args:
            edge: Edge.

        """
        self._workspace = replace(
            self._workspace,
            edges=tuple(
                candidate
                for candidate in self._workspace.edges
                if candidate != edge
            ),
        )

    def get_selector(self, *, selector_id: str) -> SelectorDef:
        """Return one project selector.

        Args:
            selector_id: Stable selector identifier.

        Returns:
            The selector.

        Raises:
            WorkspaceError: When no selector has that identifier.

        """
        for item in self._workspace.selectors:
            if item.selector_id == selector_id:
                return item
        msg: str = f"Unknown selector: {selector_id}"
        raise WorkspaceError(msg)

    def upsert_selector(self, *, selector: SelectorDef) -> None:
        """Add a selector, or replace the one with the same identifier.

        A changed name does not rewrite references; use ``rename_selector``.

        Args:
            selector: Selector to store.

        """
        selectors: list[SelectorDef] = list(self._workspace.selectors)
        for index, item in enumerate(iterable=selectors):
            if item.selector_id == selector.selector_id:
                selectors[index] = selector
                break
        else:
            selectors.append(selector)
        candidate: tuple[SelectorDef, ...] = tuple(selectors)
        validate_selectors(selectors=candidate)
        self._workspace = replace(self._workspace, selectors=candidate)

    def delete_selector(
        self,
        *,
        selector_id: str,
        force: bool = False,
    ) -> None:
        """Remove a selector unless something still depends on it.

        Args:
            selector_id: Selector to remove.
            force: Remove it even when actions, selectors or conditions
                still refer to it; those references then dangle.

        Raises:
            WorkspaceError: When the selector is in use and ``force`` is off.

        """
        _ = self.get_selector(selector_id=selector_id)
        usage: SelectorUsage = usage_index(workspace=self._workspace)[
            selector_id
        ]
        if usage.in_use and (not force):
            msg: str = (
                f"Selector is used by "
                f"{len(usage.actions)} action(s) in {
                    usage.flow_count
                } flow(s), {len(usage.selectors)} selector(s) and {
                    usage.conditions
                } condition(s)."
            )
            raise WorkspaceError(msg)
        self._workspace = replace(
            self._workspace,
            selectors=tuple(
                item
                for item in self._workspace.selectors
                if item.selector_id != selector_id
            ),
        )

    def rename_selector(
        self,
        *,
        selector_id: str,
        name: str,
    ) -> tuple[str, ...]:
        """Rename a selector and rewrite the references that can be.

        Args:
            selector_id: Selector to rename.
            name: Its new, unique name.

        Returns:
            Identifiers of sandbox JavaScript actions that mention the old
            name and must be edited by hand.

        """
        _ = self.get_selector(selector_id=selector_id)
        renamed, flagged = rename_references(
            workspace=self._workspace,
            selector_id=selector_id,
            name=name,
        )
        validate_selectors(selectors=renamed.selectors)
        self._workspace = renamed
        return flagged

    def replace_workspace(self, *, workspace: Workspace) -> None:
        """Handle replace workspace.

        Args:
            workspace: Workspace.

        """
        self._workspace = workspace

    @staticmethod
    def _recording(*, flow: Flow, recording_id: str) -> FlowRecording:
        """Find a recording parent in a flow.

        Args:
            flow: Flow that should contain the parent.
            recording_id: Parent task identifier.

        Returns:
            The matching parent.

        Raises:
            WorkspaceError: When the flow has no such recording.

        """
        for item in flow.recordings:
            if item.recording_id == recording_id:
                return item
        msg: str = f"Unknown recording: {recording_id}"
        raise WorkspaceError(msg)

    def _replace_event(self, *, event: TimelineEvent) -> None:
        """Handle replace event.

        Args:
            event: Event.

        """
        flow: Flow = self.get_flow(flow_id=event.flow_id)
        self._replace_flow(
            flow=flow.with_events(
                events=tuple(
                    event
                    if candidate.event_id == event.event_id
                    else candidate
                    for candidate in flow.events
                ),
            ),
        )

    def _replace_flow(self, *, flow: Flow) -> None:
        """Handle replace flow.

        Args:
            flow: Flow.

        """
        self._workspace = replace(
            self._workspace,
            flows=tuple(
                flow if candidate.flow_id == flow.flow_id else candidate
                for candidate in self._workspace.flows
            ),
        )


class WorkspaceCodec:
    """Represent WorkspaceCodec."""

    @classmethod
    def save(cls, *, path: Path, workspace: Workspace) -> None:
        """Handle save.

        Args:
            path: Path.
            workspace: Workspace.

        """
        data: str = (
            dumps(
                obj=cls.to_json_value(workspace=workspace),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        temporary: str | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=".workspace-",
                delete=False,
            ) as stream:
                temporary = stream.name
                _ = stream.write(data)
                stream.flush()
                fsync(fd=stream.fileno())
            Path(temporary).replace(target=path)
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)

    @classmethod
    def load(cls, *, path: Path) -> Workspace:
        """Return load.

        Args:
            path: Path.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        try:
            value: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=path.read_text(encoding="utf-8")),
            )
        except (JSONDecodeError, OSError) as error:
            raise WorkspaceError(str(object=error)) from error
        return cls.from_json_value(value=value)

    @classmethod
    def to_json_value(cls, *, workspace: Workspace) -> JsonValue:
        """Return to json value.

        Args:
            workspace: Workspace.

        Returns:
            The resulting value.

        """
        return {
            "version": Constants.workspace_version,
            "flows": [
                cls._flow_to_json(flow=flow) for flow in workspace.flows
            ],
            "edges": [
                cls._edge_to_json(edge=edge) for edge in workspace.edges
            ],
            "screenshots": [
                cls._screenshot_to_json(artifact=artifact)
                for artifact in workspace.screenshots
            ],
            "variables": [
                cls._variable_definition_to_json(definition=definition)
                for definition in workspace.variables
            ],
            "checkpoint_definitions": [
                cls._checkpoint_definition_to_json(checkpoint=checkpoint)
                for checkpoint in workspace.checkpoint_definitions
            ],
            "checkpoint_artifacts": [
                cls._checkpoint_artifact_to_json(artifact=artifact)
                for artifact in workspace.checkpoint_artifacts
            ],
            "runs": [cls._run_to_json(run=run) for run in workspace.runs],
            "profiles": [
                cls.profile_to_json(profile=profile)
                for profile in workspace.profiles
            ],
            "target": cls.target_to_json(target=workspace.target),
            "project": ProjectInfoCodec.to_json_value(info=workspace.project),
        }

    @classmethod
    def parse_target(cls, *, value: JsonValue) -> Target:
        """Read and validate a persisted or submitted target.

        A port typed into the address is moved into the port field, so
        ``localhost:3000`` works as people expect.

        Args:
            value: Target object.

        Returns:
            Validated target.

        Raises:
            WorkspaceError: When the target is malformed or unsafe.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="target",
        )
        raw_command: JsonValue = root.get("command", [])
        if not isinstance(raw_command, list) or not all(
            isinstance(item, str) for item in raw_command
        ):
            msg: str = "A service command is a list of text arguments."
            raise WorkspaceError(msg)
        url: str = str(object=root.get("url") or "").strip()
        port: int | None = cls._optional_int(root=root, key="port")
        if url:
            text: str = url if "://" in url else f"http://{url}"
            try:
                embedded: int | None = urlsplit(url=text).port
            except ValueError as error:
                raise WorkspaceError(str(object=error)) from error
            if embedded is not None:
                port = embedded
                url = text.replace(f":{embedded}", "", count=1)
        try:
            return Target(
                mode=TargetMode(str(object=root.get("mode") or "url")),
                url=url,
                port=port,
                command=tuple(str(object=item) for item in raw_command),
                cwd=str(object=root.get("cwd") or ""),
                service_port=cls._optional_int(root=root, key="service_port"),
                path=str(object=root.get("path") or "/"),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def parse_profile(cls, *, value: JsonValue) -> Profile:
        """Read and validate one persisted or submitted profile.

        Args:
            value: Profile object.

        Returns:
            Validated profile; unsupported media features are rejected.

        Raises:
            WorkspaceError: When the profile or its media map is malformed.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="profile",
        )
        media: JsonValue = root.get("media", {})
        if not isinstance(media, dict) or not all(
            isinstance(item, str) for item in media.values()
        ):
            msg: str = "A profile's media settings must be name/value text."
            raise WorkspaceError(msg)
        scale: float = cls._optional_float(root=root, key="scale") or 1.0
        touch: JsonValue = root.get("touch", False)
        mobile: JsonValue = root.get("mobile", False)
        if not isinstance(touch, bool) or not isinstance(mobile, bool):
            msg = (
                "A profile's touch and mobile settings must be true or false."
            )
            raise WorkspaceError(msg)
        try:
            return Profile(
                profile_id=cls._require_str(root=root, key="id"),
                name=cls._require_str(root=root, key="name"),
                width=cls._require_int(root=root, key="width"),
                height=cls._require_int(root=root, key="height"),
                scale=scale,
                screen_width=cls._optional_int(root=root, key="screen_width"),
                screen_height=cls._optional_int(
                    root=root,
                    key="screen_height",
                ),
                touch=touch,
                mobile=mobile,
                media=tuple(
                    sorted(
                        (
                            (name, str(object=item))
                            for name, item in media.items()
                        ),
                    ),
                ),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def from_json_value(cls, *, value: JsonValue) -> Workspace:
        """Return from json value.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="workspace",
        )
        version: int = cls._require_int(root=root, key="version")
        if version != Constants.workspace_version:
            msg: str = "Unsupported workspace version."
            raise WorkspaceError(msg)
        flows: tuple[Flow, ...] = tuple(
            cls._parse_flow(value=item)
            for item in cls._require_list(root=root, key="flows")
        )
        flow_ids: frozenset[str] = frozenset(flow.flow_id for flow in flows)
        if len(flow_ids) != len(flows):
            msg = "Workspace contains duplicate Flow IDs."
            raise WorkspaceError(msg)
        edges: tuple[FlowEdge, ...] = tuple(
            cls._parse_edge(value=item, flow_ids=flow_ids)
            for item in cls._require_list(root=root, key="edges")
        )
        if len(frozenset(edges)) != len(edges):
            msg = "Workspace contains duplicate Flow edges."
            raise WorkspaceError(msg)
        screenshots: tuple[ScreenshotArtifact, ...] = tuple(
            cls._parse_screenshot(value=item, flows=flows)
            for item in cls._require_list(root=root, key="screenshots")
        )
        variables: tuple[VariableDefinition, ...] = tuple(
            cls._parse_variable_definition(value=item, flow_ids=flow_ids)
            for item in cls._require_list(root=root, key="variables")
        )
        if len({definition.name for definition in variables}) != len(
            variables,
        ):
            msg = "Workspace contains duplicate variable names."
            raise WorkspaceError(msg)
        checkpoint_definitions: tuple[CheckpointDefinition, ...] = tuple(
            cls._parse_checkpoint_definition(value=item, flows=flows)
            for item in cls._require_list(
                root=root,
                key="checkpoint_definitions",
            )
        )
        checkpoint_ids: frozenset[str] = frozenset(
            checkpoint.checkpoint_id for checkpoint in checkpoint_definitions
        )
        if len(checkpoint_ids) != len(checkpoint_definitions):
            msg = "Workspace contains duplicate checkpoint IDs."
            raise WorkspaceError(msg)
        checkpoint_artifacts: tuple[CheckpointArtifact, ...] = tuple(
            cls._parse_checkpoint_artifact(
                value=item,
                checkpoint_ids=checkpoint_ids,
            )
            for item in cls._require_list(
                root=root,
                key="checkpoint_artifacts",
            )
        )
        runs: tuple[ExecutionRun, ...] = tuple(
            cls._parse_run(value=item, flow_ids=flow_ids)
            for item in cls._require_list(root=root, key="runs")
        )
        if len({run.run_id for run in runs}) != len(runs):
            msg = "Workspace contains duplicate execution-run IDs."
            raise WorkspaceError(msg)
        profiles: tuple[Profile, ...] = (
            tuple(
                cls.parse_profile(value=item)
                for item in cls._require_list(root=root, key="profiles")
            )
            if "profiles" in root
            else default_profiles()
        )
        if not profiles:
            msg = "A workspace needs at least one profile."
            raise WorkspaceError(msg)
        if len({profile.profile_id for profile in profiles}) != len(profiles):
            msg = "Workspace contains duplicate profile IDs."
            raise WorkspaceError(msg)
        return Workspace(
            flows=flows,
            edges=edges,
            screenshots=screenshots,
            variables=variables,
            checkpoint_definitions=checkpoint_definitions,
            checkpoint_artifacts=checkpoint_artifacts,
            runs=runs,
            profiles=profiles,
            target=cls.parse_target(value=root["target"])
            if "target" in root
            else Target(),
            project=ProjectInfoCodec.from_json_value(
                value=root.get("project"),
            ),
        )

    @classmethod
    def runtime_variable_to_json_value(
        cls,
        *,
        variable: RuntimeVariable,
    ) -> JsonValue:
        """Return runtime variable to json value.

        Args:
            variable: Variable.

        Returns:
            The resulting value.

        """
        return cls._runtime_variable_to_json(variable=variable)

    @classmethod
    def runtime_variable_from_json_value(
        cls,
        *,
        value: JsonValue,
    ) -> RuntimeVariable:
        """Return runtime variable from json value.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return cls._parse_runtime_variable(value=value)

    @classmethod
    def action_record_to_json_value(
        cls,
        *,
        record: ActionRunRecord,
    ) -> JsonValue:
        """Return action record to json value.

        Args:
            record: Record.

        Returns:
            The resulting value.

        """
        return cls._action_record_to_json(record=record)

    @classmethod
    def action_record_from_json_value(
        cls,
        *,
        value: JsonValue,
    ) -> ActionRunRecord:
        """Return action record from json value.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return cls._parse_action_record(value=value)

    @classmethod
    def event_to_json_value(cls, *, event: TimelineEvent) -> JsonValue:
        """Return event to json value.

        Args:
            event: Event.

        Returns:
            The resulting value.

        """
        return {
            "id": event.event_id,
            "sequence": event.sequence,
            "elapsed_ms": event.elapsed_ms,
            "recording_group_id": event.recording_group_id,
            "layer": event.layer.value,
            "kind": event.kind.value,
            "label": event.label,
            "selector": event.selector,
            "url": event.url,
            "method": event.method,
            "status": event.status,
            "payload": event.payload,
            "headers": [
                {"name": header.name, "value": header.value}
                for header in event.headers
            ],
            "share_session_cookies": event.share_session_cookies,
            "caused_by_event_id": event.caused_by_event_id,
            "position_action": None
            if event.position_action is None
            else event.position_action.value,
            "x": event.x,
            "y": event.y,
            "end_x": event.end_x,
            "end_y": event.end_y,
            "expectations": [
                cls._expectation_to_json(expectation=expectation)
                for expectation in event.expectations
            ],
            "contract": cls._contract_to_json(contract=event.contract),
            "selector_id": event.selector_id,
            "targets": event.targets.value,
            "run_mode": event.run_mode.value,
            "pace_between": SelectorCodec.pace_to_json(
                pace=event.pace_between,
            ),
            "sandbox": event.sandbox,
            "output_variable": event.output_variable,
            "when_expression": event.when_expression,
            **({"incomplete": True} if event.incomplete else {}),
            "request_id": event.request_id,
            "initiator_url": event.initiator_url,
            "initiator_stack": list(event.initiator_stack),
            "correlation_id": event.correlation_id,
            "attribution_confidence": event.attribution_confidence,
            "attribution_reasons": list(event.attribution_reasons),
        }

    @staticmethod
    def target_to_json(*, target: Target) -> JsonValue:
        """Return the target as persisted and shown to the editor.

        Args:
            target: The application under test.

        Returns:
            JSON object with the address, port and service settings.

        """
        command: list[JsonValue] = [*target.command]
        return {
            "mode": target.mode.value,
            "url": target.url,
            "port": target.port,
            "command": command,
            "cwd": target.cwd,
            "service_port": target.service_port,
            "path": target.path,
        }

    @staticmethod
    def profile_to_json(*, profile: Profile) -> JsonValue:
        """Return a profile as persisted and shown to the editor.

        Args:
            profile: Browser conditions to describe.

        Returns:
            JSON object with the profile's size, device and media settings.

        """
        return {
            "id": profile.profile_id,
            "name": profile.name,
            "width": profile.width,
            "height": profile.height,
            "scale": profile.scale,
            "screen_width": profile.screen_width,
            "screen_height": profile.screen_height,
            "touch": profile.touch,
            "mobile": profile.mobile,
            "media": dict(profile.media),
        }

    @staticmethod
    def profile_schema() -> JsonValue:
        """Describe every profile setting so the editor builds typed controls.

        Returns:
            Field descriptions with kind, unit, range and options. The editor
            renders from this list; the backend validates the same rules.

        """
        edge_min: int = ModelConstants.minimum_viewport_edge
        edge_max: int = ModelConstants.maximum_viewport_edge
        fields: list[JsonValue] = [
            {
                "id": "width",
                "label": "Width",
                "kind": "length",
                "unit": "px",
                "min": edge_min,
                "max": edge_max,
                "media": "width",
            },
            {
                "id": "height",
                "label": "Height",
                "kind": "length",
                "unit": "px",
                "min": edge_min,
                "max": edge_max,
                "media": "height",
            },
            {
                "id": "aspect-ratio",
                "label": "Aspect ratio",
                "kind": "ratio",
                "derived_from": ["width", "height"],
                "media": "aspect-ratio",
            },
            {
                "id": "orientation",
                "label": "Orientation",
                "kind": "choice",
                "options": ["portrait", "landscape"],
                "derived_from": ["width", "height"],
                "media": "orientation",
            },
            {
                "id": "scale",
                "label": "Resolution",
                "kind": "number",
                "unit": "dppx",
                "min": ModelConstants.minimum_scale,
                "max": ModelConstants.maximum_scale,
                "step": 0.25,
                "media": "resolution",
            },
            {
                "id": "screen_width",
                "label": "Device width",
                "kind": "length",
                "unit": "px",
                "min": edge_min,
                "max": edge_max,
                "optional": True,
                "media": "device-width",
            },
            {
                "id": "screen_height",
                "label": "Device height",
                "kind": "length",
                "unit": "px",
                "min": edge_min,
                "max": edge_max,
                "optional": True,
                "media": "device-height",
            },
            {
                "id": "touch",
                "label": "Primary input",
                "kind": "choice",
                "options": ["mouse", "touch"],
                "media": "pointer, hover, any-pointer, any-hover",
            },
            {
                "id": "mobile",
                "label": "Mobile browser",
                "kind": "toggle",
                "media": "overflow-block",
            },
        ]
        fields.extend(
            (
                {
                    "id": name,
                    "label": name.removeprefix("prefers-")
                    .replace("-", " ")
                    .capitalize(),
                    "kind": "choice",
                    "options": list(options),
                    "media": name,
                    "group": "media",
                }
                for name, options in ModelConstants.supported_media.items()
            ),
        )
        unsupported: list[JsonValue] = [
            *sorted(ModelConstants.unsupported_media),
        ]
        return {"fields": fields, "unsupported": unsupported}

    @classmethod
    def _flow_to_json(cls, *, flow: Flow) -> JsonValue:
        """Return flow to json.

        Args:
            flow: Flow.

        Returns:
            The resulting value.

        """
        device_modes: list[JsonValue] = [*sorted(flow.device_modes)]
        events: list[JsonValue] = [
            cls.event_to_json_value(event=event) for event in flow.events
        ]
        value: dict[str, JsonValue] = {
            "id": flow.flow_id,
            "name": flow.name,
            "task_description": flow.task_description,
            "expected_behavior": flow.expected_behavior,
            "notes": flow.notes,
            "device_modes": device_modes,
            "capture_record_images": flow.capture_record_images,
            "capture_play_images": flow.capture_play_images,
            "parameters": [
                cls._flow_parameter_to_json(parameter=parameter)
                for parameter in flow.parameters
            ],
            "outputs": [
                cls._flow_output_to_json(output=output)
                for output in flow.outputs
            ],
            "events": events,
        }
        if flow.recordings:
            value["recordings"] = [
                {
                    "id": group.recording_id,
                    "label": group.label,
                    "start_ms": group.start_ms,
                }
                for group in flow.recordings
            ]
        return value

    @classmethod
    def _contract_to_json(cls, *, contract: ActionContract) -> JsonValue:
        """Return contract to json.

        Args:
            contract: Contract.

        Returns:
            The resulting value.

        """
        return {
            "preconditions": [
                cls._assertion_to_json(assertion=assertion)
                for assertion in contract.preconditions
            ],
            "postconditions": [
                cls._assertion_to_json(assertion=assertion)
                for assertion in contract.postconditions
            ],
            "outputs": [
                cls._output_binding_to_json(binding=binding)
                for binding in contract.outputs
            ],
            "retry_count": contract.retry_count,
            "retry_delay_ms": contract.retry_delay_ms,
            "continue_on_failure": contract.continue_on_failure,
            "pace": SelectorCodec.pace_to_json(pace=contract.pace),
        }

    @classmethod
    def _checkpoint_artifact_to_json(
        cls,
        *,
        artifact: CheckpointArtifact,
    ) -> JsonValue:
        """Return checkpoint artifact to json.

        Args:
            artifact: Artifact.

        Returns:
            The resulting value.

        """
        return {
            "id": artifact.artifact_id,
            "checkpoint_id": artifact.checkpoint_id,
            "run_id": artifact.run_id,
            "flow_id": artifact.flow_id,
            "event_id": artifact.event_id,
            "url": artifact.url,
            "cookies_json": artifact.cookies_json,
            "local_storage_json": artifact.local_storage_json,
            "session_storage_json": artifact.session_storage_json,
            "indexed_db_json": artifact.indexed_db_json,
            "variables": [
                cls._runtime_variable_to_json(variable=variable)
                for variable in artifact.variables
            ],
        }

    @classmethod
    def _action_record_to_json(cls, *, record: ActionRunRecord) -> JsonValue:
        """Return action record to json.

        Args:
            record: Record.

        Returns:
            The resulting value.

        """
        return {
            "event_id": record.event_id,
            "flow_id": record.flow_id,
            "status": record.status.value,
            "attempt": record.attempt,
            "started_ms": record.started_ms,
            "finished_ms": record.finished_ms,
            "assertions": [
                cls._assertion_result_to_json(result=result)
                for result in record.assertions
            ],
            "observed_event_ids": list(record.observed_event_ids),
            "screenshot_artifact_ids": list(record.screenshot_artifact_ids),
            "outputs": [
                cls._runtime_variable_to_json(variable=variable)
                for variable in record.outputs
            ],
            "error": record.error,
            "response": loads(s=record.response_json)
            if record.response_json is not None
            else None,
            "cause": loads(s=record.cause_json)
            if record.cause_json is not None
            else None,
            "streams": loads(s=record.streams_json)
            if record.streams_json is not None
            else [],
            "unit": None
            if record.unit_index is None
            else {"index": record.unit_index, "count": record.unit_count},
        }

    @classmethod
    def _run_to_json(cls, *, run: ExecutionRun) -> JsonValue:
        """Return run to json.

        Args:
            run: Run.

        Returns:
            The resulting value.

        """
        return {
            "id": run.run_id,
            "initial_flow_id": run.initial_flow_id,
            "current_flow_id": run.current_flow_id,
            "device_mode": run.device_mode,
            "status": run.status.value,
            "started_at_utc": run.started_at_utc,
            "finished_at_utc": run.finished_at_utc,
            "action_records": [
                cls._action_record_to_json(record=record)
                for record in run.action_records
            ],
            "transitions": [
                cls._run_transition_to_json(transition=transition)
                for transition in run.transitions
            ],
            "variables": [
                cls._runtime_variable_to_json(variable=variable)
                for variable in run.variables
            ],
            "failure_reason": run.failure_reason,
        }

    @classmethod
    def _parse_flow(cls, *, value: JsonValue) -> Flow:
        """Return parse flow.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="flow",
        )
        flow_id: str = cls._require_str(root=root, key="id")
        events: tuple[TimelineEvent, ...] = tuple(
            cls._parse_event(value=item, flow_id=flow_id)
            for item in cls._migrate_previous(
                items=cls._require_list(root=root, key="events"),
            )
        )
        device_modes: frozenset[str] = frozenset(
            cls._scope(text=cls._require_string_value(value=item))
            for item in cls._require_list(root=root, key="device_modes")
        )
        try:
            return Flow(
                flow_id=flow_id,
                name=cls._require_str(root=root, key="name"),
                task_description=cls._require_str(
                    root=root,
                    key="task_description",
                ),
                expected_behavior=cls._require_str(
                    root=root,
                    key="expected_behavior",
                ),
                notes=cls._require_str(root=root, key="notes"),
                device_modes=device_modes,
                capture_record_images=cls._require_bool(
                    root=root,
                    key="capture_record_images",
                ),
                capture_play_images=cls._require_bool(
                    root=root,
                    key="capture_play_images",
                ),
                parameters=tuple(
                    cls._parse_flow_parameter(value=item)
                    for item in cls._require_list(root=root, key="parameters")
                ),
                outputs=tuple(
                    cls._parse_flow_output(value=item)
                    for item in cls._require_list(root=root, key="outputs")
                ),
                recordings=tuple(
                    cls._parse_recording(value=item)
                    for item in (
                        cls._require_list(root=root, key="recordings")
                        if "recordings" in root
                        else []
                    )
                ),
                events=tuple(
                    (
                        event.with_sequence(sequence=index)
                        for index, event in enumerate(iterable=events)
                    ),
                ),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def _parse_recording(cls, *, value: JsonValue) -> FlowRecording:
        """Read a persisted recording parent with legacy compatibility.

        Args:
            value: Persisted recording object.

        Returns:
            Validated recording parent.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="recording",
        )
        return FlowRecording(
            recording_id=cls._require_str(root=root, key="id"),
            label=cls._require_str(root=root, key="label"),
            start_ms=cls._require_int(root=root, key="start_ms"),
        )

    @classmethod
    def _migrate_previous(cls, *, items: list[JsonValue]) -> list[JsonValue]:
        """Turn the retired "receive from previous" toggle into a variable.

        Older files marked a step with ``receive_previous`` and read the
        result of the step before it as ``{{previous}}``. The step before now
        names its result and the reading step names that variable instead.

        Args:
            items: Raw event documents of one flow, in flow order.

        Returns:
            The documents, rewritten where the retired toggle was set.

        """
        migrated: list[JsonValue] = [
            dict(item) if isinstance(item, dict) else item for item in items
        ]
        taken: set[str] = {
            name
            for item in migrated
            if (name := cls._variable_of(event=item)) is not None
        }
        for index, item in enumerate(iterable=migrated):
            if not isinstance(item, dict):
                continue
            document: dict[str, JsonValue] = item
            if document.get("receive_previous") is not True:
                continue
            document.pop("receive_previous")
            earlier: JsonValue = migrated[index - 1] if index > 0 else None
            if not isinstance(earlier, dict):
                continue
            name: str | None = cls._variable_of(event=earlier)
            if name is None:
                base: str = f"{earlier.get('label') or 'Action'} Result"
                name = base
                count: int = 2
                while name in taken:
                    name = f"{base} {count}"
                    count += 1
                taken.add(name)
                earlier["output_variable"] = name
            for key in Constants.previous_fields:
                text: JsonValue = document.get(key)
                if isinstance(text, str):
                    document[key] = text.replace(
                        "{{previous}}",
                        f"{{{{{name}}}}}",
                    )
        return migrated

    @classmethod
    def _parse_event(cls, *, value: JsonValue, flow_id: str) -> TimelineEvent:
        """Return parse event.

        Args:
            value: Value.
            flow_id: Flow id.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="event",
        )
        try:
            layer: TimelineLayer = TimelineLayer(
                cls._require_str(root=root, key="layer"),
            )
            kind: EventKind = EventKind(
                cls._require_str(root=root, key="kind"),
            )
            position_action: PositionPointerAction | None = cls._optional_enum(
                root=root,
                key="position_action",
                enum_type=PositionPointerAction,
            )
            event: TimelineEvent = TimelineEvent(
                event_id=cls._require_str(root=root, key="id"),
                flow_id=flow_id,
                sequence=cls._require_int(root=root, key="sequence"),
                elapsed_ms=cls._require_int(root=root, key="elapsed_ms"),
                layer=layer,
                kind=kind,
                label=cls._require_str(root=root, key="label"),
                recording_group_id=cls._optional_str(
                    root=root,
                    key="recording_group_id",
                ),
                selector=cls._optional_str(root=root, key="selector"),
                url=cls._optional_str(root=root, key="url"),
                method=cls._optional_str(root=root, key="method"),
                status=cls._optional_int(root=root, key="status"),
                payload=cls._optional_str(root=root, key="payload"),
                headers=cls._parse_headers(root=root, key="headers"),
                share_session_cookies=cls._require_bool(
                    root=root,
                    key="share_session_cookies",
                ),
                caused_by_event_id=cls._optional_str(
                    root=root,
                    key="caused_by_event_id",
                ),
                position_action=position_action,
                x=cls._optional_int(root=root, key="x"),
                y=cls._optional_int(root=root, key="y"),
                end_x=cls._optional_int(root=root, key="end_x"),
                end_y=cls._optional_int(root=root, key="end_y"),
                expectations=tuple(
                    cls._parse_expectation(value=item)
                    for item in cls._require_list(
                        root=root,
                        key="expectations",
                    )
                ),
                contract=cls._parse_contract(
                    value=cls._require_key(root=root, key="contract"),
                ),
                selector_id=cls._optional_str(root=root, key="selector_id"),
                targets=TargetScope(
                    cls._optional_str(root=root, key="targets")
                    or TargetScope.FIRST.value,
                ),
                run_mode=RunMode(
                    cls._optional_str(root=root, key="run_mode")
                    or RunMode.SEQUENTIAL.value,
                ),
                pace_between=SelectorCodec.pace_from_json(
                    value=root.get("pace_between"),
                ),
                sandbox=root.get("sandbox") is True,
                output_variable=cls._optional_str(
                    root=root,
                    key="output_variable",
                ),
                when_expression=cls._optional_str(
                    root=root,
                    key="when_expression",
                ),
                incomplete=root.get("incomplete") is True,
                request_id=cls._optional_str(root=root, key="request_id"),
                initiator_url=cls._optional_str(
                    root=root,
                    key="initiator_url",
                ),
                initiator_stack=tuple(
                    cls._require_string_value(value=item)
                    for item in cls._require_list(
                        root=root,
                        key="initiator_stack",
                    )
                ),
                correlation_id=cls._optional_str(
                    root=root,
                    key="correlation_id",
                ),
                attribution_confidence=cls._optional_float(
                    root=root,
                    key="attribution_confidence",
                ),
                attribution_reasons=tuple(
                    cls._require_string_value(value=item)
                    for item in cls._require_list(
                        root=root,
                        key="attribution_reasons",
                    )
                ),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error
        return event

    @classmethod
    def _parse_flow_parameter(cls, *, value: JsonValue) -> FlowParameter:
        """Return parse flow parameter.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="Flow parameter",
        )
        try:
            return FlowParameter(
                name=cls._require_str(root=root, key="name"),
                value_type=ValueType(
                    cls._require_str(root=root, key="value_type"),
                ),
                required=cls._require_bool(root=root, key="required"),
                default_value=cls._optional_scalar(
                    root=root,
                    key="default_value",
                ),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def _parse_flow_output(cls, *, value: JsonValue) -> FlowOutput:
        """Return parse flow output.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="Flow output",
        )
        try:
            return FlowOutput(
                name=cls._require_str(root=root, key="name"),
                value_type=ValueType(
                    cls._require_str(root=root, key="value_type"),
                ),
                expression=cls._require_str(root=root, key="expression"),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def _parse_contract(cls, *, value: JsonValue) -> ActionContract:
        """Return parse contract.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="action contract",
        )
        try:
            return ActionContract(
                preconditions=tuple(
                    cls._parse_assertion(value=item)
                    for item in cls._require_list(
                        root=root,
                        key="preconditions",
                    )
                ),
                postconditions=tuple(
                    cls._parse_assertion(value=item)
                    for item in cls._require_list(
                        root=root,
                        key="postconditions",
                    )
                ),
                outputs=tuple(
                    cls._parse_output_binding(value=item)
                    for item in cls._require_list(root=root, key="outputs")
                ),
                retry_count=cls._require_int(root=root, key="retry_count"),
                retry_delay_ms=cls._require_int(
                    root=root,
                    key="retry_delay_ms",
                ),
                continue_on_failure=cls._require_bool(
                    root=root,
                    key="continue_on_failure",
                ),
                pace=SelectorCodec.pace_from_json(value=root.get("pace")),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def _parse_assertion(cls, *, value: JsonValue) -> AssertionSpec:
        """Return parse assertion.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="assertion",
        )
        try:
            return AssertionSpec(
                assertion_id=cls._require_str(root=root, key="id"),
                label=cls._require_str(root=root, key="label"),
                kind=AssertionKind(cls._require_str(root=root, key="kind")),
                operator=AssertionOperator(
                    cls._require_str(root=root, key="operator"),
                ),
                target=cls._require_str(root=root, key="target"),
                selector_id=cls._optional_str(root=root, key="selector_id"),
                expected=cls._optional_str(root=root, key="expected"),
                attribute=cls._optional_str(root=root, key="attribute"),
                timeout_ms=cls._require_int(root=root, key="timeout_ms"),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def _parse_output_binding(cls, *, value: JsonValue) -> OutputBinding:
        """Return parse output binding.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="output binding",
        )
        try:
            return OutputBinding(
                name=cls._require_str(root=root, key="name"),
                value_type=ValueType(
                    cls._require_str(root=root, key="value_type"),
                ),
                source=OutputSource(cls._require_str(root=root, key="source")),
                expression=cls._require_str(root=root, key="expression"),
                selector=cls._optional_str(root=root, key="selector"),
                attribute=cls._optional_str(root=root, key="attribute"),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def _parse_expectation(cls, *, value: JsonValue) -> NetworkExpectation:
        """Return parse expectation.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="network expectation",
        )
        try:
            return NetworkExpectation(
                expectation_id=cls._require_str(root=root, key="id"),
                label=cls._require_str(root=root, key="label"),
                method=cls._optional_str(root=root, key="method"),
                url_pattern=cls._optional_str(root=root, key="url_pattern"),
                url_match=UrlMatchMode(
                    cls._require_str(root=root, key="url_match"),
                ),
                query_conditions=tuple(
                    cls._parse_query_condition(value=item)
                    for item in cls._require_list(
                        root=root,
                        key="query_conditions",
                    )
                ),
                expected_status=cls._optional_int(
                    root=root,
                    key="expected_status",
                ),
                expected_headers=cls._parse_headers(
                    root=root,
                    key="expected_headers",
                ),
                body_match=BodyMatchMode(
                    cls._require_str(root=root, key="body_match"),
                ),
                expected_body=cls._optional_str(
                    root=root,
                    key="expected_body",
                ),
                json_conditions=tuple(
                    cls._parse_json_condition(value=item)
                    for item in cls._require_list(
                        root=root,
                        key="json_conditions",
                    )
                ),
                timeout_ms=cls._require_int(root=root, key="timeout_ms"),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def _parse_query_condition(cls, *, value: JsonValue) -> QueryCondition:
        """Return parse query condition.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="query condition",
        )
        try:
            return QueryCondition(
                name=cls._require_str(root=root, key="name"),
                operator=ConditionOperator(
                    cls._require_str(root=root, key="operator"),
                ),
                value=cls._optional_str(root=root, key="value"),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def _parse_json_condition(cls, *, value: JsonValue) -> JsonCondition:
        """Return parse json condition.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="JSON condition",
        )
        try:
            return JsonCondition(
                path=cls._require_str(root=root, key="path"),
                operator=ConditionOperator(
                    cls._require_str(root=root, key="operator"),
                ),
                value=cls._optional_str(root=root, key="value"),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def _parse_headers(
        cls,
        *,
        root: dict[str, JsonValue],
        key: str,
    ) -> tuple[HttpHeader, ...]:
        """Return parse headers.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        """
        return tuple(
            cls._parse_header(value=item)
            for item in cls._require_list(root=root, key=key)
        )

    @classmethod
    def _parse_header(cls, *, value: JsonValue) -> HttpHeader:
        """Return parse header.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="HTTP header",
        )
        try:
            return HttpHeader(
                name=cls._require_str(root=root, key="name"),
                value=cls._require_str(root=root, key="value"),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def _parse_screenshot(
        cls,
        *,
        value: JsonValue,
        flows: tuple[Flow, ...],
    ) -> ScreenshotArtifact:
        """Return parse screenshot.

        Args:
            value: Value.
            flows: Flows.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="screenshot",
        )
        try:
            artifact: ScreenshotArtifact = ScreenshotArtifact(
                artifact_id=cls._require_str(root=root, key="id"),
                flow_id=cls._require_str(root=root, key="flow_id"),
                event_id=cls._require_str(root=root, key="event_id"),
                phase=CapturePhase(cls._require_str(root=root, key="phase")),
                path=cls._require_str(root=root, key="path"),
                width=cls._require_int(root=root, key="width"),
                height=cls._require_int(root=root, key="height"),
                sha256=cls._require_str(root=root, key="sha256"),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error
        if not any(
            flow.flow_id == artifact.flow_id
            and any(
                event.event_id == artifact.event_id for event in flow.events
            )
            for flow in flows
        ):
            msg: str = "Screenshot references a missing Flow event."
            raise WorkspaceError(msg)
        return artifact

    @classmethod
    def _parse_variable_definition(
        cls,
        *,
        value: JsonValue,
        flow_ids: frozenset[str],
    ) -> VariableDefinition:
        """Return parse variable definition.

        Args:
            value: Value.
            flow_ids: Flow ids.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="variable definition",
        )
        try:
            definition: VariableDefinition = VariableDefinition(
                name=cls._require_str(root=root, key="name"),
                value_type=ValueType(
                    cls._require_str(root=root, key="value_type"),
                ),
                scope=VariableScope(cls._require_str(root=root, key="scope")),
                flow_id=cls._optional_str(root=root, key="flow_id"),
                default_value=cls._optional_scalar(
                    root=root,
                    key="default_value",
                ),
                source_name=cls._optional_str(root=root, key="source_name"),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error
        if (
            definition.flow_id is not None
            and definition.flow_id not in flow_ids
        ):
            msg: str = "Variable definition references a missing Flow."
            raise WorkspaceError(msg)
        return definition

    @classmethod
    def _parse_runtime_variable(cls, *, value: JsonValue) -> RuntimeVariable:
        """Return parse runtime variable.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="runtime variable",
        )
        return RuntimeVariable(
            name=cls._require_str(root=root, key="name"),
            value_type=ValueType(
                cls._require_str(root=root, key="value_type"),
            ),
            value=cls._optional_scalar(root=root, key="value"),
            secret=cls._require_bool(root=root, key="secret"),
        )

    @classmethod
    def _parse_checkpoint_definition(
        cls,
        *,
        value: JsonValue,
        flows: tuple[Flow, ...],
    ) -> CheckpointDefinition:
        """Return parse checkpoint definition.

        Args:
            value: Value.
            flows: Flows.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="checkpoint definition",
        )
        try:
            checkpoint: CheckpointDefinition = CheckpointDefinition(
                checkpoint_id=cls._require_str(root=root, key="id"),
                name=cls._require_str(root=root, key="name"),
                flow_id=cls._require_str(root=root, key="flow_id"),
                event_id=cls._optional_str(root=root, key="event_id"),
                include_cookies=cls._require_bool(
                    root=root,
                    key="include_cookies",
                ),
                include_local_storage=cls._require_bool(
                    root=root,
                    key="include_local_storage",
                ),
                include_session_storage=cls._require_bool(
                    root=root,
                    key="include_session_storage",
                ),
                include_indexed_db=cls._require_bool(
                    root=root,
                    key="include_indexed_db",
                ),
                include_variables=cls._require_bool(
                    root=root,
                    key="include_variables",
                ),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error
        flow: Flow | None = next(
            (
                candidate
                for candidate in flows
                if candidate.flow_id == checkpoint.flow_id
            ),
            None,
        )
        if flow is None:
            msg: str = "Checkpoint definition references a missing Flow."
            raise WorkspaceError(msg)
        if checkpoint.event_id is not None and all(
            event.event_id != checkpoint.event_id for event in flow.events
        ):
            msg = "Checkpoint definition references a missing event."
            raise WorkspaceError(msg)
        return checkpoint

    @classmethod
    def _parse_checkpoint_artifact(
        cls,
        *,
        value: JsonValue,
        checkpoint_ids: frozenset[str],
    ) -> CheckpointArtifact:
        """Return parse checkpoint artifact.

        Args:
            value: Value.
            checkpoint_ids: Checkpoint ids.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="checkpoint artifact",
        )
        try:
            artifact: CheckpointArtifact = CheckpointArtifact(
                artifact_id=cls._require_str(root=root, key="id"),
                checkpoint_id=cls._require_str(root=root, key="checkpoint_id"),
                run_id=cls._require_str(root=root, key="run_id"),
                flow_id=cls._require_str(root=root, key="flow_id"),
                event_id=cls._optional_str(root=root, key="event_id"),
                url=cls._require_str(root=root, key="url"),
                cookies_json=cls._optional_str(root=root, key="cookies_json"),
                local_storage_json=cls._optional_str(
                    root=root,
                    key="local_storage_json",
                ),
                session_storage_json=cls._optional_str(
                    root=root,
                    key="session_storage_json",
                ),
                indexed_db_json=cls._optional_str(
                    root=root,
                    key="indexed_db_json",
                ),
                variables=tuple(
                    cls._parse_runtime_variable(value=item)
                    for item in cls._require_list(root=root, key="variables")
                ),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error
        if artifact.checkpoint_id not in checkpoint_ids:
            msg: str = "Checkpoint artifact references an unknown policy."
            raise WorkspaceError(msg)
        return artifact

    @classmethod
    def _parse_assertion_result(cls, *, value: JsonValue) -> AssertionResult:
        """Return parse assertion result.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="assertion result",
        )
        return AssertionResult(
            assertion_id=cls._require_str(root=root, key="assertion_id"),
            outcome=AssertionOutcome(
                cls._require_str(root=root, key="outcome"),
            ),
            details=cls._require_str(root=root, key="details"),
            actual=cls._optional_str(root=root, key="actual"),
        )

    @classmethod
    def _parse_action_record(cls, *, value: JsonValue) -> ActionRunRecord:
        """Return parse action record.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="action record",
        )
        try:
            return ActionRunRecord(
                event_id=cls._require_str(root=root, key="event_id"),
                flow_id=cls._require_str(root=root, key="flow_id"),
                status=ActionRunStatus(
                    cls._require_str(root=root, key="status"),
                ),
                attempt=cls._require_int(root=root, key="attempt"),
                started_ms=cls._require_int(root=root, key="started_ms"),
                finished_ms=cls._require_int(root=root, key="finished_ms"),
                assertions=tuple(
                    cls._parse_assertion_result(value=item)
                    for item in cls._require_list(root=root, key="assertions")
                ),
                observed_event_ids=tuple(
                    cls._require_string_value(value=item)
                    for item in cls._require_list(
                        root=root,
                        key="observed_event_ids",
                    )
                ),
                screenshot_artifact_ids=tuple(
                    cls._require_string_value(value=item)
                    for item in cls._require_list(
                        root=root,
                        key="screenshot_artifact_ids",
                    )
                ),
                outputs=tuple(
                    cls._parse_runtime_variable(value=item)
                    for item in cls._require_list(root=root, key="outputs")
                ),
                error=cls._optional_str(root=root, key="error"),
                response_json=dumps(obj=root["response"], allow_nan=False)
                if "response" in root
                else None,
                cause_json=dumps(obj=root["cause"], allow_nan=False)
                if root.get("cause") is not None
                else None,
                streams_json=dumps(obj=root["streams"], allow_nan=False)
                if root.get("streams")
                else None,
                unit_index=cls._unit_part(root=root, key="index"),
                unit_count=cls._unit_part(root=root, key="count"),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def _parse_run_transition(cls, *, value: JsonValue) -> RunTransition:
        """Return parse run transition.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="run transition",
        )
        return RunTransition(
            source_flow_id=cls._require_str(root=root, key="source"),
            target_flow_id=cls._require_str(root=root, key="target"),
            mode=TransitionMode(cls._require_str(root=root, key="mode")),
            reason=cls._require_str(root=root, key="reason"),
        )

    @classmethod
    def _parse_run(
        cls,
        *,
        value: JsonValue,
        flow_ids: frozenset[str],
    ) -> ExecutionRun:
        """Return parse run.

        Args:
            value: Value.
            flow_ids: Flow ids.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="execution run",
        )
        try:
            run: ExecutionRun = ExecutionRun(
                run_id=cls._require_str(root=root, key="id"),
                initial_flow_id=cls._require_str(
                    root=root,
                    key="initial_flow_id",
                ),
                current_flow_id=cls._optional_str(
                    root=root,
                    key="current_flow_id",
                ),
                device_mode=cls._scope(
                    text=cls._require_str(root=root, key="device_mode"),
                ),
                status=RunStatus(cls._require_str(root=root, key="status")),
                started_at_utc=cls._require_str(
                    root=root,
                    key="started_at_utc",
                ),
                finished_at_utc=cls._optional_str(
                    root=root,
                    key="finished_at_utc",
                ),
                action_records=tuple(
                    cls._parse_action_record(value=item)
                    for item in cls._require_list(
                        root=root,
                        key="action_records",
                    )
                ),
                transitions=tuple(
                    cls._parse_run_transition(value=item)
                    for item in cls._require_list(root=root, key="transitions")
                ),
                variables=tuple(
                    cls._parse_runtime_variable(value=item)
                    for item in cls._require_list(root=root, key="variables")
                ),
                failure_reason=cls._optional_str(
                    root=root,
                    key="failure_reason",
                ),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error
        referenced_ids: frozenset[str] = frozenset(
            {
                run.initial_flow_id,
                *(transition.source_flow_id for transition in run.transitions),
                *(transition.target_flow_id for transition in run.transitions),
            },
        )
        if not referenced_ids.issubset(flow_ids):
            msg: str = "Execution run references a missing Flow."
            raise WorkspaceError(msg)
        return run

    @classmethod
    def _parse_edge(
        cls,
        *,
        value: JsonValue,
        flow_ids: frozenset[str],
    ) -> FlowEdge:
        """Return parse edge.

        Args:
            value: Value.
            flow_ids: Flow ids.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        root: dict[str, JsonValue] = cls._require_mapping(
            value=value,
            context="edge",
        )
        source: str = cls._require_str(root=root, key="source")
        target: str = cls._require_str(root=root, key="target")
        if source not in flow_ids or target not in flow_ids:
            msg: str = "Flow edge references a missing Flow."
            raise WorkspaceError(msg)
        try:
            return FlowEdge(
                source_flow_id=source,
                target_flow_id=target,
                mode=TransitionMode(cls._require_str(root=root, key="mode")),
                condition_expression=cls._optional_str(
                    root=root,
                    key="condition_expression",
                ),
                priority=cls._require_int(root=root, key="priority"),
                max_traversals=cls._require_int(
                    root=root,
                    key="max_traversals",
                ),
            )
        except ValueError as error:
            raise WorkspaceError(str(object=error)) from error

    @classmethod
    def _require_list(
        cls,
        *,
        root: dict[str, JsonValue],
        key: str,
    ) -> list[JsonValue]:
        """Return require list.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        value: JsonValue = cls._require_key(root=root, key=key)
        if not isinstance(value, list):
            msg: str = f"Expected '{key}' to be a list."
            raise WorkspaceError(msg)
        return value

    @classmethod
    def _require_str(cls, *, root: dict[str, JsonValue], key: str) -> str:
        """Return require str.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        """
        return cls._require_string_value(
            value=cls._require_key(root=root, key=key),
        )

    @classmethod
    def _require_int(cls, *, root: dict[str, JsonValue], key: str) -> int:
        """Return require int.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        value: JsonValue = cls._require_key(root=root, key=key)
        if isinstance(value, bool) or not isinstance(value, int):
            msg: str = f"Expected '{key}' to be an integer."
            raise WorkspaceError(msg)
        return value

    @classmethod
    def _require_bool(cls, *, root: dict[str, JsonValue], key: str) -> bool:
        """Return require bool.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        value: JsonValue = cls._require_key(root=root, key=key)
        if not isinstance(value, bool):
            msg: str = f"Expected '{key}' to be a boolean."
            raise WorkspaceError(msg)
        return value

    @classmethod
    def _optional_enum(
        cls,
        *,
        root: dict[str, JsonValue],
        key: str,
        enum_type: type[PositionPointerAction],
    ) -> PositionPointerAction | None:
        """Return optional enum.

        Args:
            root: Root.
            key: Key.
            enum_type: Enum type.

        Returns:
            The resulting value.

        """
        value: str | None = cls._optional_str(root=root, key=key)
        return None if value is None else enum_type(value)

    @staticmethod
    def _variable_of(*, event: JsonValue) -> str | None:
        """Return the variable name a raw event document produces.

        Args:
            event: Raw event document.

        Returns:
            The name, or None when it produces none.

        """
        if not isinstance(event, dict):
            return None
        name: JsonValue = event.get("output_variable")
        return name if isinstance(name, str) else None

    @staticmethod
    def _scope(*, text: str) -> str:
        """Accept a saved device scope: a profile ID, shared or custom.

        Args:
            text: Scope as saved in a flow or run.

        Returns:
            The same scope when it is well formed.

        Raises:
            ValueError: When the scope could never name a profile.

        """
        if text in {DeviceMode.SHARED, DeviceMode.CUSTOM} or fullmatch(
            pattern=ModelConstants.profile_id_pattern,
            string=text,
        ):
            return text
        msg: str = f"Unknown device scope: {text!r}."
        raise ValueError(msg)

    @staticmethod
    def _expectation_to_json(*, expectation: NetworkExpectation) -> JsonValue:
        """Return expectation to json.

        Args:
            expectation: Expectation.

        Returns:
            The resulting value.

        """
        return {
            "id": expectation.expectation_id,
            "label": expectation.label,
            "method": expectation.method,
            "url_pattern": expectation.url_pattern,
            "url_match": expectation.url_match.value,
            "query_conditions": [
                {
                    "name": condition.name,
                    "operator": condition.operator.value,
                    "value": condition.value,
                }
                for condition in expectation.query_conditions
            ],
            "expected_status": expectation.expected_status,
            "expected_headers": [
                {"name": header.name, "value": header.value}
                for header in expectation.expected_headers
            ],
            "body_match": expectation.body_match.value,
            "expected_body": expectation.expected_body,
            "json_conditions": [
                {
                    "path": condition.path,
                    "operator": condition.operator.value,
                    "value": condition.value,
                }
                for condition in expectation.json_conditions
            ],
            "timeout_ms": expectation.timeout_ms,
        }

    @staticmethod
    def _flow_parameter_to_json(*, parameter: FlowParameter) -> JsonValue:
        """Return flow parameter to json.

        Args:
            parameter: Parameter.

        Returns:
            The resulting value.

        """
        return {
            "name": parameter.name,
            "value_type": parameter.value_type.value,
            "required": parameter.required,
            "default_value": parameter.default_value,
        }

    @staticmethod
    def _flow_output_to_json(*, output: FlowOutput) -> JsonValue:
        """Return flow output to json.

        Args:
            output: Output.

        Returns:
            The resulting value.

        """
        return {
            "name": output.name,
            "value_type": output.value_type.value,
            "expression": output.expression,
        }

    @staticmethod
    def _assertion_to_json(*, assertion: AssertionSpec) -> JsonValue:
        """Return assertion to json.

        Args:
            assertion: Assertion.

        Returns:
            The resulting value.

        """
        return {
            "id": assertion.assertion_id,
            "label": assertion.label,
            "kind": assertion.kind.value,
            "operator": assertion.operator.value,
            "target": assertion.target,
            "selector_id": assertion.selector_id,
            "expected": assertion.expected,
            "attribute": assertion.attribute,
            "timeout_ms": assertion.timeout_ms,
        }

    @staticmethod
    def _output_binding_to_json(*, binding: OutputBinding) -> JsonValue:
        """Return output binding to json.

        Args:
            binding: Binding.

        Returns:
            The resulting value.

        """
        return {
            "name": binding.name,
            "value_type": binding.value_type.value,
            "source": binding.source.value,
            "expression": binding.expression,
            "selector": binding.selector,
            "attribute": binding.attribute,
        }

    @staticmethod
    def _edge_to_json(*, edge: FlowEdge) -> JsonValue:
        """Return edge to json.

        Args:
            edge: Edge.

        Returns:
            The resulting value.

        """
        return {
            "source": edge.source_flow_id,
            "target": edge.target_flow_id,
            "mode": edge.mode.value,
            "condition_expression": edge.condition_expression,
            "priority": edge.priority,
            "max_traversals": edge.max_traversals,
        }

    @staticmethod
    def _variable_definition_to_json(
        *,
        definition: VariableDefinition,
    ) -> JsonValue:
        """Return variable definition to json.

        Args:
            definition: Definition.

        Returns:
            The resulting value.

        """
        return {
            "name": definition.name,
            "value_type": definition.value_type.value,
            "scope": definition.scope.value,
            "flow_id": definition.flow_id,
            "default_value": definition.default_value,
            "source_name": definition.source_name,
        }

    @staticmethod
    def _runtime_variable_to_json(*, variable: RuntimeVariable) -> JsonValue:
        """Return runtime variable to json.

        Args:
            variable: Variable.

        Returns:
            The resulting value.

        """
        return {
            "name": variable.name,
            "value_type": variable.value_type.value,
            "value": None if variable.secret else variable.value,
            "secret": variable.secret,
        }

    @staticmethod
    def _checkpoint_definition_to_json(
        *,
        checkpoint: CheckpointDefinition,
    ) -> JsonValue:
        """Return checkpoint definition to json.

        Args:
            checkpoint: Checkpoint.

        Returns:
            The resulting value.

        """
        return {
            "id": checkpoint.checkpoint_id,
            "name": checkpoint.name,
            "flow_id": checkpoint.flow_id,
            "event_id": checkpoint.event_id,
            "include_cookies": checkpoint.include_cookies,
            "include_local_storage": checkpoint.include_local_storage,
            "include_session_storage": checkpoint.include_session_storage,
            "include_indexed_db": checkpoint.include_indexed_db,
            "include_variables": checkpoint.include_variables,
        }

    @staticmethod
    def _assertion_result_to_json(*, result: AssertionResult) -> JsonValue:
        """Return assertion result to json.

        Args:
            result: Result.

        Returns:
            The resulting value.

        """
        return {
            "assertion_id": result.assertion_id,
            "outcome": result.outcome.value,
            "details": result.details,
            "actual": result.actual,
        }

    @staticmethod
    def _run_transition_to_json(*, transition: RunTransition) -> JsonValue:
        """Return run transition to json.

        Args:
            transition: Transition.

        Returns:
            The resulting value.

        """
        return {
            "source": transition.source_flow_id,
            "target": transition.target_flow_id,
            "mode": transition.mode.value,
            "reason": transition.reason,
        }

    @staticmethod
    def _screenshot_to_json(*, artifact: ScreenshotArtifact) -> JsonValue:
        """Return screenshot to json.

        Args:
            artifact: Artifact.

        Returns:
            The resulting value.

        """
        return {
            "id": artifact.artifact_id,
            "flow_id": artifact.flow_id,
            "event_id": artifact.event_id,
            "phase": artifact.phase.value,
            "path": artifact.path,
            "width": artifact.width,
            "height": artifact.height,
            "sha256": artifact.sha256,
        }

    @staticmethod
    def _unit_part(*, root: dict[str, JsonValue], key: str) -> int | None:
        """Return one number of an action record's ``unit`` object.

        Args:
            root: Action record JSON.
            key: ``index`` or ``count``.

        Returns:
            The number, or ``None`` when the record has no unit.

        Raises:
            WorkspaceError: When the unit is present but malformed.

        """
        unit: JsonValue = root.get("unit")
        if unit is None:
            return None
        if not isinstance(unit, dict):
            msg: str = "Expected 'unit' to be an object or null."
            raise WorkspaceError(msg)
        number: JsonValue = unit.get(key)
        if isinstance(number, bool) or not isinstance(number, int):
            msg = f"Expected unit '{key}' to be an integer."
            raise WorkspaceError(msg)
        return number

    @staticmethod
    def _require_mapping(
        *,
        value: JsonValue,
        context: str,
    ) -> dict[str, JsonValue]:
        """Return require mapping.

        Args:
            value: Value.
            context: Context.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        if not isinstance(value, dict):
            msg: str = f"Expected {context} to be a JSON object."
            raise WorkspaceError(msg)
        return value

    @staticmethod
    def _require_string_value(*, value: JsonValue) -> str:
        """Return require string value.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        if not isinstance(value, str):
            msg: str = "Expected a string value."
            raise WorkspaceError(msg)
        return value

    @staticmethod
    def _optional_str(*, root: dict[str, JsonValue], key: str) -> str | None:
        """Return optional str.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if value is None or isinstance(value, str):
            return value
        msg: str = f"Expected '{key}' to be a string or null."
        raise WorkspaceError(msg)

    @staticmethod
    def _optional_int(*, root: dict[str, JsonValue], key: str) -> int | None:
        """Return optional int.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            msg: str = f"Expected '{key}' to be an integer or null."
            raise WorkspaceError(msg)
        return value

    @staticmethod
    def _optional_float(
        *,
        root: dict[str, JsonValue],
        key: str,
    ) -> float | None:
        """Return optional float.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            msg: str = f"Expected '{key}' to be a number or null."
            raise WorkspaceError(msg)
        return float(value)

    @staticmethod
    def _optional_scalar(
        *,
        root: dict[str, JsonValue],
        key: str,
    ) -> JsonScalar:
        """Return optional scalar.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        value: JsonValue | None = root.get(key)
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        msg: str = f"Expected '{key}' to be a JSON scalar."
        raise WorkspaceError(msg)

    @staticmethod
    def _require_key(*, root: dict[str, JsonValue], key: str) -> JsonValue:
        """Return require key.

        Args:
            root: Root.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            WorkspaceError: When the operation cannot complete.

        """
        if key not in root:
            msg: str = f"Missing required key: {key}"
            raise WorkspaceError(msg)
        return root[key]
