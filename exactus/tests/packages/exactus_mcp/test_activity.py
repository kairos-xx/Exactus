# Copyright (c) 2026
"""Validate Exactus MCP lifecycle and caller activity tracking."""

from typing import TYPE_CHECKING

from exactus.packages.exactus_mcp.activity import (
    ActivitySnapshot,
    ServiceActivity,
    ServicePhase,
)
from exactus.tests.common.support import expect_equal

if TYPE_CHECKING:
    from exactus.packages.server.json_types import JsonValue


def test_activity_tracks_lifecycle_urls_and_calls() -> None:
    """Snapshots expose explicit lifecycle and protected-call activity."""
    activity: ServiceActivity = ServiceActivity()
    activity.mark_starting()
    activity.mark_updating(local_url="http://127.0.0.1:6100")
    activity.mark_running(
        local_url="http://127.0.0.1:6100",
        public_url="https://example.ngrok-free.app",
    )
    identifier: int = activity.begin_call(
        name="run_exactus_check",
        request_metadata={"tool": "docs"},
    )
    running: ActivitySnapshot = activity.snapshot()
    expect_equal(actual=running.phase, expected=ServicePhase.RUNNING)
    expect_equal(actual=running.active_calls, expected=1)
    expect_equal(actual=running.call_count, expected=1)
    expect_equal(actual=running.last_call, expected="run_exactus_check")
    expect_equal(
        actual=running.mcp_url,
        expected="https://example.ngrok-free.app/mcp",
    )
    activity.finish_call(
        identifier=identifier,
        response_metadata={"status": "PASS"},
    )
    expect_equal(actual=activity.snapshot().active_calls, expected=0)
    recent: list[dict[str, JsonValue]] = activity.recent_calls()
    expect_equal(actual=recent[0]["state"], expected="succeeded")
    expect_equal(actual=recent[0]["request"], expected={"tool": "docs"})
    expect_equal(actual=recent[0]["response"], expected={"status": "PASS"})


def test_activity_preserves_last_failure_until_a_new_start() -> None:
    """A failure remains visible until the next deliberate startup."""
    activity: ServiceActivity = ServiceActivity()
    activity.mark_failed(error="ngrok exited")
    failed: ActivitySnapshot = activity.snapshot()
    expect_equal(actual=failed.phase, expected=ServicePhase.FAILED)
    expect_equal(actual=failed.last_error, expected="ngrok exited")
    activity.mark_starting()
    expect_equal(actual=activity.snapshot().last_error, expected=None)
