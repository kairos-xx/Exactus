# Copyright (c) 2026
"""Track Exactus MCP lifecycle and caller activity for local interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from exactus.packages.server.json_types import JsonValue


@final
class Constants:
    """Group bounded activity-log constants.

    Attributes:
        maximum_records: Maximum completed and active records retained.

    """

    maximum_records: Final[int] = 100


@final
class ServicePhase(StrEnum):
    """Name every visible state of the managed MCP service.

    Attributes:
        STARTING: Local server startup is in progress.
        UPDATING: Local service is ready and tunnel publication is pending.
        RUNNING: Configured local and public transports are ready.
        STOPPING: Graceful service shutdown is in progress.
        STOPPED: No managed service generation is running.
        RESTARTING: The current generation is yielding to its replacement.
        FAILED: Startup or runtime ended with an operational failure.

    """

    STARTING = "Starting"
    UPDATING = "Updating tunnel"
    RUNNING = "Running"
    STOPPING = "Stopping"
    STOPPED = "Stopped"
    RESTARTING = "Restarting"
    FAILED = "Failed"


@final
class CallState(StrEnum):
    """Name the lifecycle state of one safe activity-log entry.

    Attributes:
        ACTIVE: Tool execution is still running.
        SUCCEEDED: Tool execution completed successfully.
        FAILED: Tool execution raised an exception.

    """

    ACTIVE = "active"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@final
@dataclass(frozen=True, slots=True)
class CallRecord:
    """Describe one redacted MCP request and response summary.

    Attributes:
        identifier: Process-local monotonically increasing call identifier.
        name: Registered MCP tool name.
        state: Current call lifecycle state.
        started_at: UTC request start time.
        completed_at: UTC response completion time, when finished.
        duration_ms: Total execution milliseconds, when finished.
        request_metadata: Allowlisted non-secret request summary.
        response_metadata: Allowlisted non-secret response summary.

    """

    identifier: int
    name: str
    state: CallState
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    request_metadata: dict[str, JsonValue]
    response_metadata: dict[str, JsonValue]

    def to_json(self) -> dict[str, JsonValue]:
        """Return a JSON-safe activity dashboard record.

        Returns:
            Redacted request, response, state, and timing metadata.

        """
        return {
            "id": self.identifier,
            "tool": self.name,
            "state": self.state.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                None
                if self.completed_at is None
                else self.completed_at.isoformat()
            ),
            "duration_ms": self.duration_ms,
            "request": self.request_metadata,
            "response": self.response_metadata,
        }


@final
@dataclass(frozen=True, slots=True)
class ActivitySnapshot:
    """Describe one immutable view of current service activity.

    Attributes:
        phase: Current service lifecycle state.
        local_url: Active loopback origin, when known.
        public_url: Active public HTTPS origin, when known.
        active_calls: Number of MCP tool calls currently running.
        call_count: Number of MCP tool calls started in this process.
        last_call: Most recently started MCP tool name.
        last_call_at: UTC time when the most recent call started.
        last_error: Most recent lifecycle or MCP tool failure.

    """

    phase: ServicePhase
    local_url: str | None
    public_url: str | None
    active_calls: int
    call_count: int
    last_call: str | None
    last_call_at: datetime | None
    last_error: str | None

    @property
    def mcp_url(self) -> str | None:
        """Return the preferred MCP endpoint URL when an origin is known.

        Returns:
            Public or local MCP endpoint, otherwise ``None``.

        """
        origin: str | None = self.public_url or self.local_url
        return None if origin is None else f"{origin}/mcp"


@final
class ServiceActivity:
    """Own thread-safe lifecycle and MCP call activity."""

    def __init__(self) -> None:
        """Create an initially stopped activity record."""
        self._lock: RLock = RLock()
        self._phase: ServicePhase = ServicePhase.STOPPED
        self._local_url: str | None = None
        self._public_url: str | None = None
        self._active_calls: int = 0
        self._call_count: int = 0
        self._last_call: str | None = None
        self._last_call_at: datetime | None = None
        self._last_error: str | None = None
        self._next_identifier: int = 1
        self._records: list[CallRecord] = []

    def snapshot(self) -> ActivitySnapshot:
        """Return one consistent immutable activity snapshot.

        Returns:
            Current lifecycle, URL, call, and error values.

        """
        with self._lock:
            return ActivitySnapshot(
                phase=self._phase,
                local_url=self._local_url,
                public_url=self._public_url,
                active_calls=self._active_calls,
                call_count=self._call_count,
                last_call=self._last_call,
                last_call_at=self._last_call_at,
                last_error=self._last_error,
            )

    def mark_starting(self) -> None:
        """Record that a new local server is starting."""
        with self._lock:
            self._phase = ServicePhase.STARTING
            self._local_url = None
            self._public_url = None
            self._last_error = None

    def mark_updating(self, *, local_url: str) -> None:
        """Record local readiness while the public tunnel is updating.

        Args:
            local_url: Ready loopback service origin.

        """
        with self._lock:
            self._phase = ServicePhase.UPDATING
            self._local_url = local_url
            self._public_url = None

    def mark_running(self, *, local_url: str, public_url: str | None) -> None:
        """Record a ready service and its reachable origins.

        Args:
            local_url: Ready loopback service origin.
            public_url: Ready public HTTPS origin, when enabled.

        """
        with self._lock:
            self._phase = ServicePhase.RUNNING
            self._local_url = local_url
            self._public_url = public_url
            self._last_error = None

    def mark_stopping(self) -> None:
        """Record a requested graceful shutdown."""
        with self._lock:
            self._phase = ServicePhase.STOPPING

    def mark_stopped(self) -> None:
        """Record a completed shutdown while preserving call history."""
        with self._lock:
            self._phase = ServicePhase.STOPPED
            self._local_url = None
            self._public_url = None
            self._active_calls = 0

    def mark_restarting(self) -> None:
        """Record that shutdown and subsequent startup were requested."""
        with self._lock:
            self._phase = ServicePhase.RESTARTING
            self._last_error = None

    def mark_failed(self, *, error: str) -> None:
        """Record a terminal lifecycle failure.

        Args:
            error: Concise local failure description.

        """
        with self._lock:
            self._phase = ServicePhase.FAILED
            self._active_calls = 0
            self._last_error = error

    def recent_calls(self, *, limit: int = 50) -> list[dict[str, JsonValue]]:
        """Return newest redacted call records first.

        Args:
            limit: Maximum records to return.

        Returns:
            JSON-safe call records in reverse chronological order.

        """
        with self._lock:
            selected: list[CallRecord] = self._records[-limit:]
            return [record.to_json() for record in reversed(selected)]

    def begin_call(
        self,
        *,
        name: str,
        request_metadata: dict[str, JsonValue] | None = None,
    ) -> int:
        """Record the start of one protected MCP tool call.

        Args:
            name: Registered MCP tool name.
            request_metadata: Allowlisted non-secret request summary.

        Returns:
            Process-local call identifier used to record completion.

        """
        with self._lock:
            identifier: int = self._next_identifier
            self._next_identifier += 1
            started_at: datetime = datetime.now(tz=UTC)
            self._active_calls += 1
            self._call_count += 1
            self._last_call = name
            self._last_call_at = started_at
            self._records.append(
                CallRecord(
                    identifier=identifier,
                    name=name,
                    state=CallState.ACTIVE,
                    started_at=started_at,
                    completed_at=None,
                    duration_ms=None,
                    request_metadata=request_metadata or {},
                    response_metadata={},
                ),
            )
            if len(self._records) > Constants.maximum_records:
                self._records.pop(0)
            return identifier

    def finish_call(
        self,
        *,
        identifier: int,
        response_metadata: dict[str, JsonValue] | None = None,
        error: str | None = None,
    ) -> None:
        """Record completion of one protected MCP tool call.

        Args:
            identifier: Identifier returned by ``begin_call``.
            response_metadata: Allowlisted non-secret response summary.
            error: Concise call failure, or ``None`` after success.

        """
        with self._lock:
            self._active_calls = max(0, self._active_calls - 1)
            if error is not None:
                self._last_error = error
            completed_at: datetime = datetime.now(tz=UTC)
            record_index: int = 0
            while record_index < len(self._records):
                record: CallRecord = self._records[record_index]
                if record.identifier == identifier:
                    duration_ms: int = int(
                        (completed_at - record.started_at).total_seconds()
                        * 1000,
                    )
                    self._records[record_index] = CallRecord(
                        identifier=record.identifier,
                        name=record.name,
                        state=(
                            CallState.FAILED
                            if error is not None
                            else CallState.SUCCEEDED
                        ),
                        started_at=record.started_at,
                        completed_at=completed_at,
                        duration_ms=duration_ms,
                        request_metadata=record.request_metadata,
                        response_metadata=response_metadata or {},
                    )
                    return
                record_index += 1
