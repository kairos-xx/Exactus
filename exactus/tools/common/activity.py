# Copyright (c) 2026
"""Fixed ``@activity.json`` schema: heartbeat, progress and activity.

Every tool run writes ``<TOOL>/ARTIFACTS/@activity.json`` and every
pipeline run writes ``PIPELINES/<PIPELINE>/ARTIFACTS/@activity.json``.
Both use one document whose key set never changes:

- run identity: ``schema``, ``kind``, ``name``, ``run_id``,
  ``pipeline_run_id``, ``status`` and the ``started_at``/``updated_at``/
  ``finished_at`` timestamps with ``elapsed_seconds``;
- ``heartbeat``: owning ``pid``, whether the run is ``alive``, the
  ``last_beat`` timestamp, the lifecycle ``phase`` and the beat interval;
- ``progress``: ``completed``/``total`` work units, ``fraction`` and
  ``percent``, the current ``step`` and the ``current`` item;
- ``activity``: the most recent events (timestamp, level, message), at
  most ``limit`` of them, with the count of older events dropped;
- ``items`` (pipeline tools, empty for a tool) and ``extra``.

The file is replaced atomically, so a reader never sees a partial write.
"""

from __future__ import annotations

from collections import deque
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from json import JSONDecodeError, dumps, loads
from threading import RLock
from typing import TYPE_CHECKING, Final, Self, cast
from uuid import uuid4

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


class ActivityTables:
    """Constants of the ``@activity.json`` contract.

    Attributes:
        schema: Schema identifier stamped on every document.
        file_name: File name of the document inside ``ARTIFACTS/``.
        event_limit: Most recent events kept in a document.
        levels: Accepted event levels, least to most severe.
        phases: Heartbeat lifecycle phases.
        interval_seconds: Default seconds between two heartbeats.

    """

    schema: Final[str] = "exactus/activity/v1"
    file_name: Final[str] = "@activity.json"
    event_limit: Final[int] = 50
    levels: Final[tuple[str, ...]] = ("debug", "info", "warning", "error")
    phases: Final[tuple[str, ...]] = (
        "starting",
        "running",
        "finished",
        "interrupted",
        "crashed",
    )
    interval_seconds: Final[float] = 1.0

    @staticmethod
    def now() -> str:
        """Return the current UTC time as an ISO-8601 string.

        Returns:
            The current timestamp.

        """
        return datetime.now(tz=UTC).astimezone().isoformat()


def _text(*, value: JsonValue, default: str = "") -> str:
    """Return a JSON value as text, or the default for other types.

    Args:
        value: Decoded JSON value.
        default: Fallback for a non-string value.

    Returns:
        The string value or the default.

    """
    return value if isinstance(value, str) else default


def _optional_text(*, value: JsonValue) -> str | None:
    """Return a JSON value as text, or ``None`` for other types.

    Args:
        value: Decoded JSON value.

    Returns:
        The string value or ``None``.

    """
    return value if isinstance(value, str) else None


def _integer(*, value: JsonValue) -> int | None:
    """Return a JSON value as an integer, rejecting booleans.

    Args:
        value: Decoded JSON value.

    Returns:
        The integer value or ``None``.

    """
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool)
        else None
    )


def _number(*, value: JsonValue) -> float:
    """Return a JSON value as a float, rejecting booleans.

    Args:
        value: Decoded JSON value.

    Returns:
        The numeric value, or ``0.0`` for other types.

    """
    return (
        float(value)
        if isinstance(value, int | float) and not isinstance(value, bool)
        else 0.0
    )


def _mapping(*, value: JsonValue) -> dict[str, JsonValue]:
    """Return a JSON value as an object, or an empty one.

    Args:
        value: Decoded JSON value.

    Returns:
        The object or an empty dictionary.

    """
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True, slots=True, kw_only=True)
class ActivityEvent:
    """One timestamped entry of the activity list.

    Attributes:
        at: ISO-8601 timestamp of the event.
        level: One of ``ActivityTables.levels``.
        message: Human-readable event text.

    """

    at: str
    level: str
    message: str

    @classmethod
    def from_payload(cls: type[Self], *, payload: JsonValue) -> Self | None:
        """Decode one serialized event.

        Args:
            payload: Decoded JSON value.

        Returns:
            The event, or ``None`` when the value is not an event.

        """
        if not isinstance(payload, dict):
            return None
        at: JsonValue = payload.get("at")
        message: JsonValue = payload.get("message")
        if not isinstance(at, str) or not isinstance(message, str):
            return None
        level: str = _text(value=payload.get("level"), default="info")
        return cls(
            at=at,
            level=level if level in ActivityTables.levels else "info",
            message=message,
        )

    def payload(self: Self) -> dict[str, JsonValue]:
        """Serialize the event.

        Returns:
            The ``{"at", "level", "message"}`` object.

        """
        return {"at": self.at, "level": self.level, "message": self.message}


@dataclass(frozen=True, slots=True, kw_only=True)
class ActivityHeartbeat:
    """Liveness block of the document.

    Attributes:
        pid: Owning process identifier, when known.
        alive: Whether the owning run is still executing.
        last_beat: ISO-8601 timestamp of the latest beat.
        phase: One of ``ActivityTables.phases``.
        interval_seconds: Seconds between two beats while alive.

    """

    pid: int | None = None
    alive: bool = False
    last_beat: str | None = None
    phase: str = "starting"
    interval_seconds: float = ActivityTables.interval_seconds

    @classmethod
    def from_payload(cls: type[Self], *, payload: JsonValue) -> Self:
        """Decode a heartbeat block, defaulting missing fields.

        Args:
            payload: Decoded JSON value.

        Returns:
            The heartbeat block.

        """
        fields: dict[str, JsonValue] = _mapping(value=payload)
        alive: JsonValue = fields.get("alive")
        interval: float = _number(value=fields.get("interval_seconds"))
        return cls(
            pid=_integer(value=fields.get("pid")),
            alive=alive if isinstance(alive, bool) else False,
            last_beat=_optional_text(value=fields.get("last_beat")),
            phase=_text(value=fields.get("phase"), default="starting"),
            interval_seconds=interval or ActivityTables.interval_seconds,
        )

    def payload(self: Self) -> dict[str, JsonValue]:
        """Serialize the heartbeat block.

        Returns:
            The heartbeat object.

        """
        return {
            "pid": self.pid,
            "alive": self.alive,
            "last_beat": self.last_beat,
            "phase": self.phase,
            "interval_seconds": self.interval_seconds,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class ActivityProgress:
    """Progress block of the document.

    Attributes:
        completed: Completed logical work units.
        total: Total logical work units (``0`` when unknown).
        fraction: Completion fraction in ``[0, 1]``.
        step: Current step label.
        current: Item being processed, or other detail text.
        workers: Optional independent workflow step and action snapshots.
        hierarchy: Normalized task/subtask/activity progress tree.

    """

    completed: int = 0
    total: int = 0
    fraction: float = 0.0
    step: str = ""
    current: str = ""
    workers: dict[str, JsonValue] | None = None
    hierarchy: dict[str, JsonValue] | None = None

    @classmethod
    def from_payload(cls: type[Self], *, payload: JsonValue) -> Self:
        """Decode a progress block, defaulting missing fields.

        Args:
            payload: Decoded JSON value.

        Returns:
            The progress block.

        """
        fields: dict[str, JsonValue] = _mapping(value=payload)
        workers: JsonValue = fields.get("workers")
        hierarchy: JsonValue = fields.get("hierarchy")
        return cls(
            completed=_integer(value=fields.get("completed")) or 0,
            total=_integer(value=fields.get("total")) or 0,
            fraction=_number(value=fields.get("fraction")),
            step=_text(value=fields.get("step")),
            current=_text(value=fields.get("current")),
            workers=workers if isinstance(workers, dict) else None,
            hierarchy=hierarchy if isinstance(hierarchy, dict) else None,
        )

    def payload(self: Self) -> dict[str, JsonValue]:
        """Serialize the progress block.

        Returns:
            The progress object, ``percent`` derived from ``fraction``.

        """
        fraction: float = min(max(self.fraction, 0.0), 1.0)
        result: dict[str, JsonValue] = {
            "completed": self.completed,
            "total": self.total,
            "fraction": round(number=fraction, ndigits=4),
            "percent": round(number=fraction * 100, ndigits=1),
            "step": self.step,
            "current": self.current,
        }
        if self.workers is not None:
            result["workers"] = dict(self.workers)
        if self.hierarchy is not None:
            result["hierarchy"] = dict(self.hierarchy)
        return result


@dataclass(frozen=True, slots=True, kw_only=True)
class ActivityDocument:
    """One complete ``exactus/activity/v1`` document.

    Attributes:
        kind: Producer kind, ``tool`` or ``pipeline``.
        name: Tool or pipeline identifier.
        status: ``WAITING``/``RUNNING``/``PAUSED``/``DONE``/``FAIL``/
            ``INTERRUPT``.
        run_id: Run identifier.
        pipeline_run_id: Owning pipeline run identifier, when nested.
        started_at: ISO-8601 start timestamp.
        updated_at: ISO-8601 last-write timestamp; now when omitted.
        finished_at: ISO-8601 finish timestamp, once finished.
        elapsed_seconds: Wall-clock duration so far.
        heartbeat: Liveness block.
        progress: Progress block.
        events: Most recent events, oldest first.
        events_dropped: Older events no longer kept.
        event_limit: Maximum number of kept events.
        items: Sub-entity records (pipeline tools).
        extra: Producer-specific fields.

    """

    kind: str
    name: str
    status: str
    run_id: str | None = None
    pipeline_run_id: str | None = None
    started_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None
    elapsed_seconds: float = 0.0
    heartbeat: ActivityHeartbeat = field(default_factory=ActivityHeartbeat)
    progress: ActivityProgress = field(default_factory=ActivityProgress)
    events: tuple[ActivityEvent, ...] = ()
    events_dropped: int = 0
    event_limit: int = ActivityTables.event_limit
    items: tuple[dict[str, JsonValue], ...] = ()
    extra: dict[str, JsonValue] = field(default_factory=dict)

    @classmethod
    def from_payload(cls: type[Self], *, payload: JsonValue) -> Self | None:
        """Decode a document written by ``payload``.

        Args:
            payload: Decoded JSON value.

        Returns:
            The document, or ``None`` when the value is not an
            ``exactus/activity/v1`` document.

        """
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != ActivityTables.schema
        ):
            return None
        kind: JsonValue = payload.get("kind")
        name: JsonValue = payload.get("name")
        status: JsonValue = payload.get("status")
        if not (
            isinstance(kind, str)
            and isinstance(name, str)
            and isinstance(status, str)
        ):
            return None
        activity: dict[str, JsonValue] = _mapping(
            value=payload.get("activity"),
        )
        raw_events: JsonValue = activity.get("events")
        entries: list[JsonValue] = (
            raw_events if isinstance(raw_events, list) else []
        )
        events: tuple[ActivityEvent, ...] = tuple(
            event
            for event in (
                ActivityEvent.from_payload(payload=entry) for entry in entries
            )
            if event is not None
        )
        raw_items: JsonValue = payload.get("items")
        return cls(
            kind=kind,
            name=name,
            status=status,
            run_id=_optional_text(value=payload.get("run_id")),
            pipeline_run_id=_optional_text(
                value=payload.get("pipeline_run_id"),
            ),
            started_at=_optional_text(value=payload.get("started_at")),
            updated_at=_optional_text(value=payload.get("updated_at")),
            finished_at=_optional_text(value=payload.get("finished_at")),
            elapsed_seconds=_number(value=payload.get("elapsed_seconds")),
            heartbeat=ActivityHeartbeat.from_payload(
                payload=payload.get("heartbeat"),
            ),
            progress=ActivityProgress.from_payload(
                payload=payload.get("progress"),
            ),
            events=events,
            events_dropped=_integer(value=activity.get("dropped")) or 0,
            event_limit=(
                _integer(value=activity.get("limit"))
                or ActivityTables.event_limit
            ),
            items=tuple(
                item
                for item in (raw_items if isinstance(raw_items, list) else [])
                if isinstance(item, dict)
            ),
            extra=_mapping(value=payload.get("extra")),
        )

    def payload(self: Self) -> dict[str, JsonValue]:
        """Serialize the document with its fixed key set.

        Only the newest ``event_limit`` events are written; the rest are
        counted in ``activity.dropped``.

        Returns:
            The JSON-compatible document.

        """
        overflow: int = max(len(self.events) - self.event_limit, 0)
        kept: tuple[ActivityEvent, ...] = self.events[overflow:]
        return {
            "schema": ActivityTables.schema,
            "kind": self.kind,
            "name": self.name,
            "run_id": self.run_id,
            "pipeline_run_id": self.pipeline_run_id,
            "status": self.status,
            "started_at": self.started_at,
            "updated_at": (
                self.updated_at
                if self.updated_at is not None
                else ActivityTables.now()
            ),
            "finished_at": self.finished_at,
            "elapsed_seconds": round(number=self.elapsed_seconds, ndigits=3),
            "heartbeat": self.heartbeat.payload(),
            "progress": self.progress.payload(),
            "activity": {
                "limit": self.event_limit,
                "count": len(kept),
                "dropped": self.events_dropped + overflow,
                "events": [event.payload() for event in kept],
            },
            "items": [dict(item) for item in self.items],
            "extra": dict(self.extra),
        }


class ActivityLog:
    """Thread-safe bounded list of recent activity events."""

    def __init__(
        self: Self,
        *,
        limit: int = ActivityTables.event_limit,
    ) -> None:
        """Start an empty log.

        Args:
            limit: Most recent events kept; older ones are counted only.

        """
        self.limit: int = limit
        self._events: deque[ActivityEvent] = deque(maxlen=limit)
        self._recorded: int = 0
        self._lock: RLock = RLock()

    def record(
        self: Self,
        *,
        message: str,
        level: str = "info",
        at: str | None = None,
    ) -> None:
        """Append one event, evicting the oldest when full.

        Args:
            message: Human-readable event text.
            level: One of ``ActivityTables.levels``; others become info.
            at: ISO-8601 timestamp; now when omitted.

        """
        event: ActivityEvent = ActivityEvent(
            at=at if at is not None else ActivityTables.now(),
            level=level if level in ActivityTables.levels else "info",
            message=message,
        )
        with self._lock:
            self._events.append(event)
            self._recorded += 1

    def extend(
        self: Self,
        *,
        events: tuple[ActivityEvent, ...],
        dropped: int = 0,
    ) -> None:
        """Adopt events recorded elsewhere, such as a previous document.

        Args:
            events: Events to append, oldest first.
            dropped: Events the source had already dropped.

        """
        with self._lock:
            self._events.extend(events)
            self._recorded += len(events) + dropped

    def events(self: Self) -> tuple[ActivityEvent, ...]:
        """Return the kept events, oldest first.

        Returns:
            Snapshot of the kept events.

        """
        with self._lock:
            return tuple(self._events)

    def dropped(self: Self) -> int:
        """Return how many recorded events were evicted.

        Returns:
            Count of events no longer kept.

        """
        with self._lock:
            return self._recorded - len(self._events)


class ActivityFile:
    """Atomic reader and writer of ``@activity.json`` documents."""

    @classmethod
    def write(
        cls: type[Self],
        *,
        path: Path,
        document: ActivityDocument,
    ) -> None:
        """Atomically write one activity document.

        Args:
            path: Destination ``@activity.json`` path.
            document: Document to serialize.

        """
        cls.write_json(path=path, payload=document.payload())

    @staticmethod
    def write_json(*, path: Path, payload: dict[str, JsonValue]) -> None:
        """Replace one JSON file atomically.

        The text is written to a hidden temporary file in the same
        directory and moved over ``path``, so readers see either the old
        or the new document, never a partial one.

        Args:
            path: Destination file.
            payload: JSON-compatible document.

        Raises:
            OSError: When the temporary file or its atomic replace fails.

        """
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path = path.with_name(
            name=f".{path.name}.{uuid4().hex}.tmp",
        )
        try:
            _ = temporary.write_text(
                data=dumps(obj=payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _ = temporary.replace(target=path)
        except OSError:
            with suppress(OSError):
                temporary.unlink()
            raise

    @staticmethod
    def read(*, path: Path) -> ActivityDocument | None:
        """Read one activity document.

        Args:
            path: ``@activity.json`` path.

        Returns:
            The decoded document, or ``None`` when the file is missing,
            malformed or uses another schema.

        """
        try:
            payload: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=path.read_text(encoding="utf-8")),
            )
        except (OSError, JSONDecodeError, UnicodeDecodeError):
            return None
        return ActivityDocument.from_payload(payload=payload)
