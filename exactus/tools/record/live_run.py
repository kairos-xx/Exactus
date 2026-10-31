# Copyright (c) 2026 Project contributors
"""Incremental immutable execution-run telemetry for the desktop inspector."""

from __future__ import annotations

from dataclasses import dataclass, replace

from exactus.tools.record.model import (
    ActionRunRecord,
    ExecutionRun,
    RunStatus,
    RuntimeVariable,
    RunTransition,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class RunProgress:
    """Represent RunProgress.

    Attributes:
        message_type: Message type.
        run_id: Run id.
        flow_id: Flow id.
        event_id: Event id.
        status: Status.
        started_at_utc: Started at utc.
        finished_at_utc: Finished at utc.
        action_record: Action record.
        transition: Transition.
        variables: Variables.
        error: Error.

    """

    message_type: str
    run_id: str
    flow_id: str | None = None
    event_id: str | None = None
    status: RunStatus | None = None
    started_at_utc: str | None = None
    finished_at_utc: str | None = None
    action_record: ActionRunRecord | None = None
    transition: RunTransition | None = None
    variables: tuple[RuntimeVariable, ...] = ()
    error: str | None = None


class LiveRunAccumulator:
    """Represent LiveRunAccumulator."""

    def __init__(self) -> None:
        """Handle init."""
        self._runs: dict[str, ExecutionRun] = {}

    def get(self, *, run_id: str) -> ExecutionRun | None:
        """Return get.

        Args:
            run_id: Run id.

        Returns:
            The resulting value.

        """
        return self._runs.get(run_id)

    def accept(
        self,
        *,
        progress: RunProgress,
        device_mode: str,
    ) -> ExecutionRun:
        """Return accept.

        Args:
            progress: Progress.
            device_mode: Device mode.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        current: ExecutionRun | None = self._runs.get(progress.run_id)
        if current is None:
            if progress.flow_id is None or progress.started_at_utc is None:
                msg: str = "First run progress requires Flow and start time."
                raise ValueError(msg)
            current = ExecutionRun(
                run_id=progress.run_id,
                initial_flow_id=progress.flow_id,
                current_flow_id=progress.flow_id,
                device_mode=device_mode,
                status=RunStatus.RUNNING,
                started_at_utc=progress.started_at_utc,
            )
        action_records: tuple[ActionRunRecord, ...] = current.action_records
        if progress.action_record is not None:
            action_records = (
                *(
                    record
                    for record in action_records
                    if not (
                        record.flow_id == progress.action_record.flow_id
                        and record.event_id == progress.action_record.event_id
                        and record.attempt == progress.action_record.attempt
                    )
                ),
                progress.action_record,
            )
        transitions: tuple[RunTransition, ...] = current.transitions
        if progress.transition is not None:
            transitions = (*transitions, progress.transition)
        status: RunStatus = progress.status or current.status
        finished_at_utc: str | None = (
            progress.finished_at_utc
            if status is not RunStatus.RUNNING
            else None
        )
        updated: ExecutionRun = replace(
            current,
            current_flow_id=progress.flow_id or current.current_flow_id,
            status=status,
            finished_at_utc=finished_at_utc,
            action_records=action_records,
            transitions=transitions,
            variables=(progress.variables or current.variables),
            failure_reason=progress.error or current.failure_reason,
        )
        self._runs[progress.run_id] = updated
        return updated

    def finalize(self, *, run: ExecutionRun) -> ExecutionRun:
        """Return finalize.

        Args:
            run: Run.

        Returns:
            The resulting value.

        """
        self._runs[run.run_id] = run
        return run
