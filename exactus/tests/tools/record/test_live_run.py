# Copyright (c) 2026 Project contributors
"""Tests for immutable live execution-run accumulation."""

from exactus.tools.record.live_run import LiveRunAccumulator, RunProgress
from exactus.tools.record.model import DeviceMode, ExecutionRun, RunStatus


def test_live_run_starts_and_canonical_result_replaces_snapshot() -> None:
    """Handle test live run starts and canonical result replaces snapshot.

    Raises:
        AssertionError: When the operation cannot complete.

    """
    accumulator: LiveRunAccumulator = LiveRunAccumulator()
    partial: ExecutionRun = accumulator.accept(
        progress=RunProgress(
            message_type="run_started",
            run_id="run-1",
            flow_id="flow-a",
            started_at_utc="2026-10-01T16:00:00Z",
        ),
        device_mode=DeviceMode.DESKTOP,
    )
    if partial.status is not RunStatus.RUNNING:
        msg: str = "Partial run is not running."
        raise AssertionError(msg)
    final: ExecutionRun = ExecutionRun(
        run_id="run-1",
        initial_flow_id="flow-a",
        current_flow_id=None,
        device_mode=DeviceMode.DESKTOP,
        status=RunStatus.SUCCEEDED,
        started_at_utc="2026-10-01T16:00:00Z",
        finished_at_utc="2026-10-01T16:00:01Z",
    )
    if accumulator.finalize(run=final) != final:
        msg = "Canonical final run was not returned."
        raise AssertionError(msg)
    if accumulator.get(run_id="run-1") != final:
        msg = "Canonical final run did not replace partial state."
        raise AssertionError(msg)
