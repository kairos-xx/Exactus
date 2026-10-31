#!/usr/bin/env python3
# Copyright (c) 2026
"""Cross-process exactus run registry backed by an embedded database.

``EXACTUS_RESULTS/.runtime/runs.db`` is the shared source of truth describing
which exactus runs are alive: their owning process, the output directory
they write, the targets they registered, their progress, and their
lifecycle status.  A fresh run claims a row first and terminates every
live row that writes the same output directory or touches an
intersecting target, so reruns never race a stale writer.

SQLite in WAL mode serializes claims through an immediate transaction
while beats and reads proceed concurrently from any number of
processes.  Every operation is best-effort: a damaged or locked
registry degrades to the per-directory heartbeat contract instead of
failing the exactus.
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from json import dumps, loads
from os import environ
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Final, Self, cast

from exactus.packages.model.registry_queries import Queries as Constants
from exactus.packages.model.sqlite_model import (
    Compilable,
    Connection,
    Cursor,
    Literal,
    SQLiteLayerError,
    connect,
    pragma,
)
from exactus.packages.model.sqlite_model import Error as SqliteError
from exactus.packages.model.sqlite_model import execute as execute_sql
from exactus.tools.common.process_control import process_exists

if TYPE_CHECKING:
    from collections.abc import Generator

    from exactus.tools.common.json_types import JsonValue


class RegistryTables:
    """Static schema and lookup values for the run registry.

    Attributes:
        database_name: Registry database filename.
        env_path: Environment variable overriding the database path.
        project_root_env: Environment variable carrying the project root.
        exactus_root_name: Ancestor directory name anchoring the registry.
        busy_timeout_seconds: SQLite lock wait for each connection.
        retention: Finished rows older than this are pruned on claim.
        max_text: Longest ``step``/``detail`` text stored per run.
        journal_limit_bytes: Size the write-ahead log is truncated to.
        max_finished: Newest finished rows kept regardless of age.
        max_size_bytes: Default byte cap on the registry database files.
        size_trim_batch: Finished rows deleted per size-cap iteration.
        max_runs_env: Environment variable overriding ``max_finished``.
        max_size_env: Environment variable overriding ``max_size_bytes``.
        live_status: Row status marking a run as actively owned.
        columns: Canonical ``runs`` column order used by ``SELECT``.

    """

    database_name: Final[str] = "runs.db"
    env_path: Final[str] = "EXACTUS_REGISTRY"
    project_root_env: Final[str] = "EXACTUS_PROJECT_ROOT"
    exactus_root_name: Final[str] = "EXACTUS_RESULTS"
    busy_timeout_seconds: Final[float] = 10.0
    retention: Final[timedelta] = timedelta(days=7)
    max_finished: Final[int] = 500
    max_size_bytes: Final[int] = 67108864
    size_trim_batch: Final[int] = 50
    max_text: Final[int] = 512
    journal_limit_bytes: Final[int] = 1048576
    max_runs_env: Final[str] = "EXACTUS_RUNTIME_MAX_RUNS"
    max_size_env: Final[str] = "EXACTUS_RUNTIME_MAX_SIZE"
    live_status: Final[str] = "RUNNING"
    columns: Final[tuple[str, ...]] = (
        "run_id",
        "kind",
        "identifier",
        "pipeline_run_id",
        "pid",
        "output",
        "targets",
        "status",
        "progress",
        "step",
        "detail",
        "created_at",
        "updated_at",
        "elapsed_seconds",
    )


type ColumnValue = str | int | float | bytes | None
_connection_lock: Final[RLock] = RLock()


def workspace_context(*, root: Path) -> str:
    """Return the deterministic pmanager context for one project root.

    Args:
        root: Project root shared by participating tools.

    Returns:
        SHA-256 identity of the normalized project root.

    """
    normalized: str = str(object=root.resolve())
    return sha256(data=normalized.encode(encoding="utf-8")).hexdigest()


def run_context(*, root: Path, owner: str) -> str:
    """Return one invocation child context inside a workspace context.

    Args:
        root: Project root shared by participating tools.
        owner: Pipeline or standalone run identity.

    Returns:
        Nested ``workspace/run`` pmanager context.

    """
    return f"{workspace_context(root=root)}/{owner}"


@dataclass(frozen=True, slots=True)
class RunClaim:
    """Ownership facts registered by one starting run.

    Attributes:
        kind: Run kind: ``tool`` or ``pipeline``.
        identifier: Tool or pipeline identifier.
        run_id: Unique run identifier.
        pipeline_run_id: Owning pipeline run identifier, when any.
        pid: Owning process identifier.
        output: Directory receiving the run's report bundle.
        targets: Registered file or directory targets of the run.

    """

    kind: str
    identifier: str
    run_id: str
    pipeline_run_id: str | None
    pid: int
    output: Path
    targets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RunBeat:
    """Optional progress fields refreshed by one heartbeat.

    Attributes:
        run_id: Claimed run identifier.
        status: Replacement lifecycle status, when changing.
        progress: Completion fraction, when reported.
        step: Current logical step label, when reported.
        detail: Optional human-readable detail.
        elapsed_seconds: Run wall-clock duration, when reported.

    """

    run_id: str
    status: str | None = None
    progress: float | None = None
    step: str | None = None
    detail: str | None = None
    elapsed_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class RunRecord:
    """One registered exactus run row.

    Attributes:
        run_id: Unique run identifier.
        kind: Run kind: ``tool`` or ``pipeline``.
        identifier: Tool or pipeline identifier.
        pipeline_run_id: Owning pipeline run identifier, when any.
        pid: Owning process identifier.
        output: Directory receiving the run's report bundle.
        targets: Registered file or directory targets of the run.
        status: Lifecycle status such as RUNNING, DONE, or INTERRUPT.
        progress: Completion fraction in the ``[0, 1]`` range.
        step: Current logical step label.
        detail: Optional human-readable detail.
        created_at: ISO-8601 registration timestamp.
        updated_at: ISO-8601 last beat timestamp.
        elapsed_seconds: Run wall-clock duration at the last beat.

    """

    run_id: str
    kind: str
    identifier: str
    pipeline_run_id: str | None
    pid: int
    output: str
    targets: tuple[str, ...]
    status: str
    progress: float
    step: str
    detail: str
    created_at: str
    updated_at: str
    elapsed_seconds: float


def _clip(*, text: str | None) -> str | None:
    """Limit stored text to ``RegistryTables.max_text`` characters.

    Args:
        text: Text to store, or ``None`` to keep the stored value.

    Returns:
        The text, clipped with an ellipsis when too long.

    """
    limit: int = RegistryTables.max_text
    if text is None or len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _max_runs() -> int:
    """Resolve the cap on retained finished runs.

    ``EXACTUS_RUNTIME_MAX_RUNS`` overrides the built-in default when it
    holds a positive integer; a missing or malformed value falls back to
    ``RegistryTables.max_finished``.

    Returns:
        Finished rows the registry keeps, newest first.

    """
    raw: str | None = environ.get(RegistryTables.max_runs_env)
    if raw:
        with suppress(ValueError):
            parsed: int = int(raw)
            if parsed >= 1:
                return parsed
    return RegistryTables.max_finished


def _max_size() -> int:
    """Resolve the byte cap on the registry database files.

    ``EXACTUS_RUNTIME_MAX_SIZE`` overrides the built-in default when it
    holds an integer byte count; ``0`` disables the cap, and a missing
    or malformed value falls back to ``RegistryTables.max_size_bytes``.

    Returns:
        Byte cap enforced on ``runs.db`` and its journal files.

    """
    raw: str | None = environ.get(RegistryTables.max_size_env)
    if raw:
        with suppress(ValueError):
            return max(0, int(raw))
    return RegistryTables.max_size_bytes


def _text(value: ColumnValue) -> str:
    """Coerce one registry column to text.

    Args:
        value: Raw column value.

    Returns:
        The string form, or empty for ``None``.

    """
    return value if isinstance(value, str) else ""


def _record(row: tuple[ColumnValue, ...]) -> RunRecord:
    """Build one run record from a canonical ``SELECT`` row.

    Args:
        row: Row in ``RegistryTables.columns`` order.

    Returns:
        The decoded run record; malformed scalar fields degrade to
        inert values so a corrupt row can never claim a live process.

    """
    (
        run_id,
        kind,
        identifier,
        pipeline_run_id,
        pid,
        output,
        targets,
        status,
        progress,
        step,
        detail,
        created_at,
        updated_at,
        elapsed_seconds,
    ) = row
    raw_targets: JsonValue = []
    if isinstance(targets, str):
        with suppress(ValueError):
            raw_targets = cast(typ="JsonValue", val=loads(s=targets))
    decoded_targets: tuple[str, ...] = ()
    if isinstance(raw_targets, list | tuple):
        decoded_targets = tuple(
            str(object=target)
            for target in cast(
                typ="list[JsonValue] | tuple[JsonValue, ...]",
                val=raw_targets,
            )
        )
    return RunRecord(
        run_id=_text(value=run_id),
        kind=_text(value=kind),
        identifier=_text(value=identifier),
        pipeline_run_id=pipeline_run_id
        if isinstance(pipeline_run_id, str)
        else None,
        pid=pid
        if isinstance(pid, int) and (not isinstance(pid, bool))
        else -1,
        output=_text(value=output),
        targets=decoded_targets,
        status=_text(value=status),
        progress=progress
        if isinstance(progress, int | float)
        and (not isinstance(progress, bool))
        else 0.0,
        step=_text(value=step),
        detail=_text(value=detail),
        created_at=_text(value=created_at),
        updated_at=_text(value=updated_at),
        elapsed_seconds=elapsed_seconds
        if isinstance(elapsed_seconds, int | float)
        and (not isinstance(elapsed_seconds, bool))
        else 0.0,
    )


def _execute(
    *,
    connection: Connection,
    statement: Compilable,
    parameters: tuple[ColumnValue, ...] = (),
) -> Cursor:
    """Run one registry statement and return its cursor.

    ``sqlite3.Connection.execute`` accepts positional-only arguments, so
    statement execution flows through this keyword-shaped wrapper.

    Args:
        connection: Open registry database connection.
        statement: Structural statement.
        parameters: Values bound to statement placeholders.

    Returns:
        The cursor produced by the statement.

    """
    return execute_sql(
        connection=connection,
        statement=statement,
        parameters=parameters,
    )


class RunRegistry:
    """Shared exactus-run registry persisted in an embedded database.

    Every operation opens a short-lived connection. Connection creation,
    schema setup, and close are serialized inside each process because the
    platform SQLite library uses process-global WAL file-descriptor state.
    Database transactions still coordinate independent processes.
    """

    def __init__(self, *, path: Path) -> None:
        """Bind the registry to one database path.

        Args:
            path: SQLite database file receiving run rows.

        """
        self.path: Path = path

    @classmethod
    def for_output(cls: type[Self], *, output: Path) -> Self:
        """Resolve the registry governing one analyzer output directory.

        Args:
            output: Analyzer report directory.

        Returns:
            Registry anchored at the nearest ``EXACTUS_RESULTS`` ancestor, at
            the
            ``EXACTUS_REGISTRY`` override when set, or beside the
            output directory as a last resort.

        """
        if override := environ.get(RegistryTables.env_path):
            return cls(path=Path(override))
        resolved: Path = output.resolve()
        if reports_root := environ.get("EXACTUS_REPORTS_ROOT"):
            configured: Path = Path(reports_root).resolve()
            if resolved.is_relative_to(configured):
                return cls(
                    path=configured
                    / ".runtime"
                    / RegistryTables.database_name,
                )
        ancestor: Path
        for ancestor in (resolved, *resolved.parents):
            if ancestor.name.upper() == RegistryTables.exactus_root_name:
                return cls(
                    path=ancestor / ".runtime" / RegistryTables.database_name,
                )
        return cls(
            path=resolved.parent / ".runtime" / RegistryTables.database_name,
        )

    def acquire_resource(
        self,
        *,
        lease_id: str,
        run_id: str,
        tool: str,
        resource: str,
        mode: str,
    ) -> bool | None:
        """Try to acquire one cross-process reader/writer resource lease.

        Waiting writers prevent new readers, while active readers finish their
        current activity before the writer proceeds.

        Args:
            lease_id: Stable lease identity for one process thread.
            run_id: Owning task run.
            tool: Canonical task identifier.
            resource: Shared logical resource.
            mode: ``read`` or ``write``.

        Returns:
            Whether the lease became active, or ``None`` if unavailable.

        """
        if mode not in {"read", "write"}:
            return None
        try:
            with self._connection() as connection:
                _ = _execute(
                    connection=connection,
                    statement=Constants.begin_immediate,
                )
                now: str = datetime.now(tz=UTC).astimezone().isoformat()
                _ = _execute(
                    connection=connection,
                    statement=Constants.prune_resources,
                    parameters=(RegistryTables.live_status,),
                )
                _ = _execute(
                    connection=connection,
                    statement=Constants.insert_resource,
                    parameters=(
                        lease_id,
                        run_id,
                        tool,
                        resource,
                        mode,
                        "waiting",
                        now,
                    ),
                )
                conflict: tuple[ColumnValue, ...] | None = cast(
                    typ="tuple[ColumnValue, ...] | None",
                    val=_execute(
                        connection=connection,
                        statement=Constants.select_resource_conflicts,
                        parameters=(resource, lease_id, run_id, mode, mode),
                    ).fetchone(),
                )
                if conflict is None:
                    _ = _execute(
                        connection=connection,
                        statement=Constants.activate_resource,
                        parameters=(now, lease_id),
                    )
                _ = _execute(connection=connection, statement=Constants.commit)
        except (OSError, SqliteError, SQLiteLayerError):
            return None
        return conflict is None

    def release_resource(self, *, lease_id: str) -> None:
        """Release one reader/writer resource lease.

        Args:
            lease_id: Lease to remove.

        """
        with (
            suppress(OSError, SqliteError, SQLiteLayerError),
            self._connection() as connection,
        ):
            _ = _execute(
                connection=connection,
                statement=Constants.delete_resource,
                parameters=(lease_id,),
            )
            _ = _execute(connection=connection, statement=Constants.commit)

    def publish_activity(
        self,
        *,
        run_id: str,
        tool: str,
        item: str,
        state: str,
        error: str = "",
    ) -> None:
        """Publish one file/activity boundary for cross-process consumers.

        Args:
            run_id: Owning task run.
            tool: Canonical task identifier.
            item: Normalized file or logical work identity.
            state: Activity lifecycle state.
            error: Failure detail, when any.

        """
        with (
            suppress(OSError, SqliteError, SQLiteLayerError),
            self._connection() as connection,
        ):
            _ = _execute(
                connection=connection,
                statement=Constants.upsert_work,
                parameters=(
                    run_id,
                    tool,
                    item,
                    state,
                    _clip(text=error) or "",
                    datetime.now(tz=UTC).astimezone().isoformat(),
                ),
            )
            _ = _execute(connection=connection, statement=Constants.commit)

    def activity_state(self, *, run_id: str, item: str) -> str | None:
        """Return the latest state of one run's file/activity.

        Args:
            run_id: Owning task run.
            item: Normalized file or logical work identity.

        Returns:
            Published state, or ``None`` before the first activity event.

        """
        try:
            with self._connection() as connection:
                row: tuple[ColumnValue, ...] | None = cast(
                    typ="tuple[ColumnValue, ...] | None",
                    val=_execute(
                        connection=connection,
                        statement=Constants.select_work,
                        parameters=(run_id, item),
                    ).fetchone(),
                )
        except (OSError, SqliteError, SQLiteLayerError):
            return None
        return _text(value=row[0]) if row else None

    def claim(self, *, request: RunClaim) -> tuple[RunRecord, ...] | None:
        """Register one run and return every live run it conflicts with.

        The claim runs inside an immediate transaction: concurrent
        claims serialize, so a later claim always observes the earlier
        row as a live conflict and the latest run wins.  ``RUNNING``
        rows whose process no longer exists, or that belong to the
        claiming process itself, are reaped as ``INTERRUPT``.

        Args:
            request: Ownership facts for the claiming run.

        Returns:
            Live records conflicting on output directory or target
            intersection, or ``None`` when the registry is unavailable
            and callers must fall back to heartbeat ownership.

        """
        now: str = datetime.now(tz=UTC).astimezone().isoformat()
        output: str = str(object=request.output.resolve())
        wanted: frozenset[str] = frozenset((output, *request.targets))
        try:
            with self._connection() as connection:
                try:
                    _ = _execute(
                        connection=connection,
                        statement=Constants.begin_immediate,
                    )
                    rows: list[tuple[ColumnValue, ...]] = cast(
                        typ="list[tuple[ColumnValue, ...]]",
                        val=_execute(
                            connection=connection,
                            statement=Constants.select_live,
                            parameters=(RegistryTables.live_status,),
                        ).fetchall(),
                    )
                    live: list[RunRecord] = []
                    for row in rows:
                        record: RunRecord = _record(row=row)
                        if not process_exists(pid=record.pid) or (
                            record.pid == request.pid
                            and record.run_id != request.run_id
                        ):
                            _ = _execute(
                                connection=connection,
                                statement=Constants.reap_run,
                                parameters=("INTERRUPT", now, record.run_id),
                            )
                        else:
                            live.append(record)
                    cutoff: str = (
                        datetime.now(tz=UTC).astimezone()
                        - RegistryTables.retention
                    ).isoformat()
                    pruned: int = (
                        _execute(
                            connection=connection,
                            statement=Constants.prune_runs,
                            parameters=(RegistryTables.live_status, cutoff),
                        ).rowcount
                        + _execute(
                            connection=connection,
                            statement=Constants.trim_runs,
                            parameters=(
                                RegistryTables.live_status,
                                RegistryTables.live_status,
                                _max_runs(),
                            ),
                        ).rowcount
                        + _execute(
                            connection=connection,
                            statement=Constants.prune_work,
                        ).rowcount
                    )
                    _ = _execute(
                        connection=connection,
                        statement=Constants.delete_work,
                        parameters=(request.run_id,),
                    )
                    _ = _execute(
                        connection=connection,
                        statement=Constants.delete_run_resources,
                        parameters=(request.run_id,),
                    )
                    _ = _execute(
                        connection=connection,
                        statement=Constants.insert_run,
                        parameters=(
                            request.run_id,
                            request.kind,
                            request.identifier,
                            request.pipeline_run_id,
                            request.pid,
                            output,
                            dumps(obj=list(request.targets)),
                            RegistryTables.live_status,
                            0.0,
                            "starting",
                            "",
                            now,
                            now,
                            0.0,
                        ),
                    )
                    conflicts: tuple[RunRecord, ...] = tuple(
                        record
                        for record in live
                        if record.run_id != request.run_id
                        and record.pid != request.pid
                        and (
                            record.output == output
                            or frozenset(record.targets) & wanted
                        )
                    )
                    _ = _execute(
                        connection=connection,
                        statement=Constants.commit,
                    )
                    if pruned:
                        self._compact(connection=connection)
                except BaseException:
                    with suppress(SqliteError, SQLiteLayerError):
                        _ = _execute(
                            connection=connection,
                            statement=Constants.rollback,
                        )
                    raise
        except (OSError, SqliteError, SQLiteLayerError):
            return None
        else:
            return conflicts

    def sanitize(self) -> int:
        """Prune stale rows and shrink the database file.

        Finished rows older than the retention window, and finished rows
        beyond the newest ``_max_runs``, are deleted; when anything was
        removed the file is vacuumed and the write-ahead log truncated.
        The oldest finished rows are then removed in batches until the
        database fits the ``_max_size`` byte cap or none remain. Safe to
        call at any time and idempotent.

        Returns:
            Number of rows removed; ``0`` when the registry is unavailable.

        """
        try:
            with self._connection() as connection:
                cutoff: str = (
                    datetime.now(tz=UTC).astimezone()
                    - RegistryTables.retention
                ).isoformat()
                pruned: int = (
                    _execute(
                        connection=connection,
                        statement=Constants.prune_runs,
                        parameters=(RegistryTables.live_status, cutoff),
                    ).rowcount
                    + _execute(
                        connection=connection,
                        statement=Constants.trim_runs,
                        parameters=(
                            RegistryTables.live_status,
                            RegistryTables.live_status,
                            _max_runs(),
                        ),
                    ).rowcount
                    + _execute(
                        connection=connection,
                        statement=Constants.prune_work,
                    ).rowcount
                )
                _ = _execute(connection=connection, statement=Constants.commit)
                if pruned:
                    self._compact(connection=connection)
                pruned += self._cap_size(connection=connection)
        except (OSError, SqliteError, SQLiteLayerError):
            return 0
        return pruned

    def beat(self, *, pulse: RunBeat) -> None:
        """Refresh one run's progress fields and liveness timestamp.

        Text fields are clipped to ``max_text`` characters so a verbose
        step or detail can never bloat the database.

        Args:
            pulse: Fields to refresh; ``None`` keeps the stored value.

        """
        with (
            suppress(OSError, SqliteError, SQLiteLayerError),
            self._connection() as connection,
        ):
            _ = _execute(
                connection=connection,
                statement=Constants.beat_run,
                parameters=(
                    datetime.now(tz=UTC).astimezone().isoformat(),
                    pulse.status,
                    pulse.progress,
                    _clip(text=pulse.step),
                    _clip(text=pulse.detail),
                    pulse.elapsed_seconds,
                    pulse.run_id,
                ),
            )
            _ = _execute(connection=connection, statement=Constants.commit)

    def finish(
        self,
        *,
        run_id: str,
        status: str,
        elapsed_seconds: float,
    ) -> None:
        """Stamp one run's terminal lifecycle status.

        Args:
            run_id: Claimed run identifier.
            status: Terminal status such as DONE, FAIL, or INTERRUPT.
            elapsed_seconds: Final run wall-clock duration.

        """
        self.beat(
            pulse=RunBeat(
                run_id=run_id,
                status=status,
                progress=1.0 if status == "DONE" else None,
                elapsed_seconds=elapsed_seconds,
            ),
        )
        _ = self.sanitize()

    def live(self) -> tuple[RunRecord, ...]:
        """Return every registered run whose process is still alive.

        Returns:
            Live run records, or empty when the registry is unavailable.

        """
        try:
            with self._connection() as connection:
                rows: list[tuple[ColumnValue, ...]] = cast(
                    typ="list[tuple[ColumnValue, ...]]",
                    val=_execute(
                        connection=connection,
                        statement=Constants.select_live,
                        parameters=(RegistryTables.live_status,),
                    ).fetchall(),
                )
        except (OSError, SqliteError, SQLiteLayerError):
            return ()
        return tuple(
            record
            for record in (_record(row=row) for row in rows)
            if process_exists(pid=record.pid)
        )

    @staticmethod
    def _compact(*, connection: Connection) -> None:
        """Return freed pages and the write-ahead log to the filesystem.

        SQLite never shrinks its file after deletes on its own, so once
        rows are pruned the database is vacuumed and the write-ahead log
        (which receives the vacuumed pages) is checkpointed and truncated;
        both are best-effort when other runs hold the database.

        Args:
            connection: Open connection outside any transaction.

        """
        with suppress(SqliteError, SQLiteLayerError):
            _ = _execute(connection=connection, statement=Constants.vacuum)
            _ = _execute(connection=connection, statement=Constants.checkpoint)

    def _cap_size(self, *, connection: Connection) -> int:
        """Delete the oldest finished rows until the database fits its cap.

        Every iteration commits, vacuums, and checkpoints before the file
        size is measured again, so freed pages actually shrink the
        footprint. Live ``RUNNING`` rows are never touched.

        Args:
            connection: Open connection outside any transaction.

        Returns:
            Number of finished rows removed.

        """
        limit: int = _max_size()
        removed: int = 0
        while limit > 0 and self._footprint() > limit:
            row: tuple[ColumnValue, ...] | None = cast(
                typ="tuple[ColumnValue, ...] | None",
                val=_execute(
                    connection=connection,
                    statement=Constants.count_finished,
                    parameters=(RegistryTables.live_status,),
                ).fetchone(),
            )
            finished: ColumnValue = row[0] if row else 0
            if (
                not isinstance(finished, int)
                or isinstance(finished, bool)
                or finished < 1
            ):
                break
            deleted: int = (
                _execute(
                    connection=connection,
                    statement=Constants.trim_runs,
                    parameters=(
                        RegistryTables.live_status,
                        RegistryTables.live_status,
                        max(0, finished - RegistryTables.size_trim_batch),
                    ),
                ).rowcount
                + _execute(
                    connection=connection,
                    statement=Constants.prune_work,
                ).rowcount
            )
            _ = _execute(connection=connection, statement=Constants.commit)
            if deleted < 1:
                break
            removed += deleted
            self._compact(connection=connection)
        return removed

    def _footprint(self) -> int:
        """Return the registry's size on disk, journals included.

        Returns:
            Combined byte size of ``runs.db`` and its WAL/SHM files.

        """
        total: int = 0
        for suffix in ("", "-wal", "-shm"):
            with suppress(OSError):
                total += (
                    self.path.with_name(name=f"{self.path.name}{suffix}")
                    .stat()
                    .st_size
                )
        return total

    def _connect(self) -> Connection:
        """Open a schema-initialized WAL connection to the database.

        Returns:
            Connected database handle owned by the caller.

        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection: Connection = connect(
            database=str(object=self.path),
            timeout=RegistryTables.busy_timeout_seconds,
        )
        _ = _execute(connection=connection, statement=Constants.journal_mode)
        _ = _execute(
            connection=connection,
            statement=pragma(
                name="journal_size_limit",
                value=Literal(value=RegistryTables.journal_limit_bytes),
            ),
        )
        _ = _execute(connection=connection, statement=Constants.schema)
        _ = _execute(connection=connection, statement=Constants.work_schema)
        _ = _execute(
            connection=connection,
            statement=Constants.resource_schema,
        )
        return connection

    @contextmanager
    def _connection(self) -> Generator[Connection]:
        """Own one complete process-serialized connection lifecycle.

        Yields:
            Schema-initialized connection closed before another local thread
            may open the registry.

        """
        with _connection_lock:
            connection: Connection = self._connect()
            try:
                yield connection
            finally:
                connection.close()
