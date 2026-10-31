# Copyright (c) 2026
"""The fixed ``@activity.json`` schema, its bounded log and atomic file."""

from __future__ import annotations

from json import dumps, loads
from pathlib import Path
from signal import SIGUSR1, getsignal, raise_signal, signal
from threading import Thread
from typing import TYPE_CHECKING, Final, NoReturn, cast, final

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_none,
    expect_true,
    private,
    require_type,
)
from exactus.tools.common.activity import (
    ActivityDocument,
    ActivityEvent,
    ActivityFile,
    ActivityHeartbeat,
    ActivityLog,
    ActivityProgress,
    ActivityTables,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from threading import RLock
    from types import FrameType

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        top_keys: Grouped module constant.

    """

    top_keys: Final[frozenset[str]] = frozenset(
        {
            "schema",
            "kind",
            "name",
            "run_id",
            "pipeline_run_id",
            "status",
            "started_at",
            "updated_at",
            "finished_at",
            "elapsed_seconds",
            "heartbeat",
            "progress",
            "activity",
            "items",
            "extra",
        },
    )


def _document(*, events: tuple[ActivityEvent, ...] = ()) -> ActivityDocument:
    """Build a fully populated document.

    Args:
        events: Activity events to include.

    Returns:
        A document whose values survive serialization unchanged.

    """
    return ActivityDocument(
        kind="tool",
        name="demo",
        status="RUNNING",
        run_id="r1",
        pipeline_run_id="p1",
        started_at="2026-10-03T10:00:00+00:00",
        updated_at="2026-10-03T10:00:05+00:00",
        finished_at=None,
        elapsed_seconds=5.25,
        heartbeat=ActivityHeartbeat(
            pid=4242,
            alive=True,
            last_beat="2026-10-03T10:00:05+00:00",
            phase="running",
            interval_seconds=1.0,
        ),
        progress=ActivityProgress(
            completed=3,
            total=4,
            fraction=0.75,
            step="scan",
            current="pkg/mod.py",
        ),
        events=events,
        items=({"name": "lints", "status": "PASS"},),
        extra={"exit_code": None},
    )


def _object(*, value: object) -> dict[str, JsonValue]:
    """Narrow a decoded JSON value to an object.

    Args:
        value: Decoded JSON value.

    Returns:
        The value as a JSON object.

    """
    return cast(
        typ="dict[str, JsonValue]",
        val=require_type(value=value, kind=dict),
    )


def test_payload_has_the_fixed_key_set() -> None:
    """Every document carries the same top-level and block keys."""
    payload: dict[str, JsonValue] = _document().payload()
    expect_equal(actual=frozenset(payload), expected=Constants.top_keys)
    expect_equal(actual=payload["schema"], expected="exactus/activity/v1")
    expect_equal(
        actual=frozenset(_object(value=payload["heartbeat"])),
        expected=frozenset(
            {"pid", "alive", "last_beat", "phase", "interval_seconds"},
        ),
    )
    progress: dict[str, JsonValue] = _object(value=payload["progress"])
    expect_equal(
        actual=frozenset(progress),
        expected=frozenset(
            {"completed", "total", "fraction", "percent", "step", "current"},
        ),
    )
    expect_equal(actual=progress["percent"], expected=75.0)
    expect_equal(
        actual=frozenset(_object(value=payload["activity"])),
        expected=frozenset({"limit", "count", "dropped", "events"}),
    )
    minimal: dict[str, JsonValue] = ActivityDocument(
        kind="pipeline",
        name="unified",
        status="WAITING",
    ).payload()
    expect_equal(actual=frozenset(minimal), expected=Constants.top_keys)
    expect_true(condition=isinstance(minimal["updated_at"], str))


def test_document_round_trips_through_json() -> None:
    """``from_payload(payload())`` restores an equal document."""
    log: ActivityLog = ActivityLog()
    log.record(message="started", at="2026-10-03T10:00:00+00:00")
    log.record(
        message="stderr: 2 lines",
        level="warning",
        at="2026-10-03T10:00:01+00:00",
    )
    document: ActivityDocument = _document(events=log.events())
    decoded: ActivityDocument | None = ActivityDocument.from_payload(
        payload=cast(
            typ="JsonValue",
            val=loads(s=dumps(obj=document.payload())),
        ),
    )
    expect_equal(actual=decoded, expected=document)


def test_progress_fraction_is_clamped() -> None:
    """Out-of-range fractions serialize inside ``[0, 1]``."""
    expect_equal(
        actual=ActivityProgress(fraction=1.5).payload()["percent"],
        expected=100.0,
    )
    expect_equal(
        actual=ActivityProgress(fraction=-1.0).payload()["fraction"],
        expected=0.0,
    )


def test_log_keeps_only_the_newest_events() -> None:
    """The log evicts the oldest events and counts them as dropped."""
    log: ActivityLog = ActivityLog(limit=3)
    index: int
    for index in range(5):
        log.record(message=f"event {index}", level="nonsense")
    events: tuple[ActivityEvent, ...] = log.events()
    expect_equal(
        actual=[event.message for event in events],
        expected=["event 2", "event 3", "event 4"],
    )
    expect_equal(actual={event.level for event in events}, expected={"info"})
    expect_equal(actual=log.dropped(), expected=2)
    log.extend(events=events[:1], dropped=4)
    expect_equal(actual=log.dropped(), expected=7)
    expect_equal(actual=log.events()[-1].message, expected="event 2")


class _Recorder:
    """Signal handler that records one event into an activity log."""

    def __init__(self, *, log: ActivityLog) -> None:
        """Remember the log.

        Args:
            log: Log the handler records into.

        """
        self.log: ActivityLog = log

    def __call__(self, signum: int, frame: FrameType | None) -> None:
        """Record the interruption.

        Args:
            signum: Received signal number.
            frame: Interrupted stack frame.

        """
        del signum, frame
        self.log.record(message="interrupted")


def test_log_records_from_a_signal_handler_holding_the_lock() -> None:
    """A signal handler can record while the main thread holds the lock.

    The runner's SIGTERM handler records into the same log the main
    thread may be writing when the signal arrives.
    """
    log: ActivityLog = ActivityLog()
    lock: RLock = cast(typ="RLock", val=private(owner=log, name="_lock"))
    previous: Callable[[int, FrameType | None], object] | int | None = (
        getsignal(signalnum=SIGUSR1)
    )
    with lock:
        expect_true(
            condition=lock.acquire(blocking=False),
            message="the activity log lock must be reentrant",
        )
        lock.release()
        _ = signal(signalnum=SIGUSR1, handler=_Recorder(log=log))
        try:
            raise_signal(SIGUSR1)
        finally:
            _ = signal(signalnum=SIGUSR1, handler=previous)
    expect_equal(
        actual=[event.message for event in log.events()],
        expected=["interrupted"],
    )


def test_document_bounds_the_written_events() -> None:
    """Events beyond the limit are cut from the payload and counted."""
    events: tuple[ActivityEvent, ...] = tuple(
        ActivityEvent(at=f"t{index}", level="info", message=f"m{index}")
        for index in range(ActivityTables.event_limit + 5)
    )
    activity: dict[str, JsonValue] = _object(
        value=_events_payload(events=events, dropped=2)["activity"],
    )
    written: list[JsonValue] = cast(
        typ="list[JsonValue]",
        val=require_type(value=activity["events"], kind=list),
    )
    expect_equal(actual=len(written), expected=ActivityTables.event_limit)
    expect_equal(actual=activity["count"], expected=ActivityTables.event_limit)
    expect_equal(actual=activity["dropped"], expected=7)
    expect_equal(actual=_object(value=written[0])["message"], expected="m5")


def _events_payload(
    *,
    events: tuple[ActivityEvent, ...],
    dropped: int,
) -> dict[str, JsonValue]:
    """Serialize a minimal document holding ``events``.

    Args:
        events: Events to serialize.
        dropped: Events already dropped before the document.

    Returns:
        The serialized document.

    """
    return ActivityDocument(
        kind="tool",
        name="demo",
        status="RUNNING",
        events=events,
        events_dropped=dropped,
    ).payload()


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {
            "schema": "exactus-run/v1",
            "kind": "tool",
            "name": "x",
            "status": "R",
        },
        {"schema": "exactus/activity/v1", "kind": "tool", "status": "R"},
    ],
)
def test_foreign_payloads_are_rejected(payload: JsonValue) -> None:
    """Other schemas and incomplete documents decode to ``None``.

    Args:
        payload: Decoded JSON value that is not an activity document.

    """
    expect_none(value=ActivityDocument.from_payload(payload=payload))


def test_malformed_blocks_fall_back_to_defaults() -> None:
    """Bad block values decode to defaults; bad events are skipped."""
    decoded: ActivityDocument | None = ActivityDocument.from_payload(
        payload={
            "schema": "exactus/activity/v1",
            "kind": "tool",
            "name": "x",
            "status": "RUNNING",
            "heartbeat": {"pid": True, "alive": "yes", "interval_seconds": 0},
            "progress": [],
            "activity": {
                "events": [
                    {"at": "t", "level": "loud", "message": "kept"},
                    {"at": 1, "message": "dropped"},
                    "junk",
                ],
            },
            "items": [{"name": "a"}, 3],
            "extra": "x",
        },
    )
    document: ActivityDocument = require_type(
        value=decoded,
        kind=ActivityDocument,
    )
    expect_none(value=document.heartbeat.pid)
    expect_false(condition=document.heartbeat.alive)
    expect_equal(
        actual=document.heartbeat.interval_seconds,
        expected=ActivityTables.interval_seconds,
    )
    expect_equal(actual=document.progress, expected=ActivityProgress())
    expect_equal(
        actual=document.events,
        expected=(ActivityEvent(at="t", level="info", message="kept"),),
    )
    expect_equal(actual=document.items, expected=({"name": "a"},))
    expect_equal(actual=document.extra, expected={})


def test_file_write_is_atomic_and_leaves_no_temporaries(
    tmp_path: Path,
) -> None:
    """Writes replace the file whole and clean their temporary files.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "ARTIFACTS" / "@activity.json"
    expect_none(value=ActivityFile.read(path=path))
    ActivityFile.write(path=path, document=_document())
    ActivityFile.write(
        path=path,
        document=ActivityDocument(kind="tool", name="demo", status="DONE"),
    )
    expect_equal(
        actual=[child.name for child in path.parent.iterdir()],
        expected=["@activity.json"],
    )
    read: ActivityDocument = require_type(
        value=ActivityFile.read(path=path),
        kind=ActivityDocument,
    )
    expect_equal(actual=read.status, expected="DONE")
    _ = path.write_text(data="{broken", encoding="utf-8")
    expect_none(value=ActivityFile.read(path=path))


def test_failed_replace_keeps_the_previous_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A write that cannot be published leaves the old document intact.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    path: Path = tmp_path / "@activity.json"
    ActivityFile.write(path=path, document=_document())
    before: str = path.read_text(encoding="utf-8")

    def refuse(self: Path, target: Path) -> NoReturn:
        """Fail like a filesystem that cannot rename.

        Args:
            self: Temporary file being published.
            target: Destination path.

        Raises:
            OSError: Always.

        """
        msg: str = f"cannot move {self.name} to {target.name}"
        raise OSError(msg)

    monkeypatch.setattr(target=Path, name="replace", value=refuse)
    with pytest.raises(expected_exception=OSError, match="cannot move"):
        ActivityFile.write(
            path=path,
            document=ActivityDocument(kind="tool", name="x", status="DONE"),
        )
    expect_equal(actual=path.read_text(encoding="utf-8"), expected=before)
    expect_equal(
        actual=[child.name for child in tmp_path.iterdir()],
        expected=["@activity.json"],
    )


def test_concurrent_readers_never_see_partial_documents(
    tmp_path: Path,
) -> None:
    """A reader polling during many writes always decodes a document.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "@activity.json"
    ActivityFile.write(path=path, document=_document())

    def write_many() -> None:
        """Rewrite the document repeatedly with growing event lists."""
        log: ActivityLog = ActivityLog()
        index: int
        for index in range(200):
            log.record(message=f"beat {index}" + "x" * index)
            ActivityFile.write(
                path=path,
                document=_document(events=log.events()),
            )

    writer: Thread = Thread(target=write_many)
    writer.start()
    failures: list[int] = [
        attempt
        for attempt in range(400)
        if ActivityFile.read(path=path) is None
    ]
    writer.join()
    expect_equal(actual=failures, expected=[])
    expect_equal(
        actual=sorted(child.name for child in tmp_path.iterdir()),
        expected=["@activity.json"],
    )


def test_worker_progress_survives_activity_file_roundtrip(
    tmp_path: Path,
) -> None:
    """Retain live worker steps and actions in the on-disk heartbeat.

    Args:
        tmp_path: Atomic heartbeat destination.

    """
    workers: dict[str, JsonValue] = {
        "flow-a": {
            "completed": 2,
            "total": 5,
            "progress": 0.392,
            "finished": False,
            "action": "submit form",
        },
    }
    path: Path = tmp_path / "@activity.json"
    ActivityFile.write(
        path=path,
        document=ActivityDocument(
            kind="tool",
            name="frontend",
            status="RUNNING",
            progress=ActivityProgress(fraction=0.4, workers=workers),
        ),
    )
    restored: ActivityDocument | None = ActivityFile.read(path=path)
    expect_true(condition=restored is not None)
    if restored is not None:
        expect_equal(actual=restored.progress.workers, expected=workers)
        expect_equal(
            actual=restored.progress.payload()["percent"],
            expected=40,
        )
