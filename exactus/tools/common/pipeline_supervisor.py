# Copyright (c) 2026
"""Provide transactional ownership and reset coordination for pipelines."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, Literal, Self, final

from exactus.packages.model.pipeline_queries import Queries
from exactus.packages.model.sqlite_model import connect
from exactus.packages.model.sqlite_model import execute as execute_sql
from exactus.tools.common.process_control import process_exists, write_json
from exactus.tools.common.progress import utc_now

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.packages.model.sqlite_model import (
        Compilable,
        Connection,
        Cursor,
        Parameters,
    )
    from exactus.tools.common.json_types import JsonValue
type ClaimMode = Literal["owner", "observer", "wait"]
type ColumnValue = str | int | float | bytes | None


def _execute(
    *,
    connection: Connection,
    statement: Compilable,
    parameters: Parameters = (),
) -> Cursor:
    """Run one coordination statement and return its cursor.

    ``sqlite3.Connection.execute`` accepts positional-only arguments, so
    statement execution flows through this keyword-shaped wrapper.

    Args:
        connection: Open coordination database connection.
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


@final
class Constants:
    """Store coordination protocol constants.

    Attributes:
        database: Runtime SQLite database filename.
        directory: Directory containing inspectable request documents.
        running: State of an accepting owner.
        sealed: State of an owner that is finalizing.
        pending: State of a request awaiting reset.
        applied: State of a request whose generation started.
        failed: State of a rejected reset request.
        complete: State of an observer whose owner completed.
        detached: State of an interrupted observer.
        retention_days: Terminal request retention period.

    """

    database: Final[str] = "pipelines.db"
    directory: Final[str] = "pipeline_requests"
    running: Final[str] = "RUNNING"
    sealed: Final[str] = "SEALED"
    pending: Final[str] = "PENDING"
    applied: Final[str] = "APPLIED"
    failed: Final[str] = "FAILED"
    complete: Final[str] = "COMPLETE"
    detached: Final[str] = "DETACHED"
    retention_days: Final[int] = 7


@dataclass(frozen=True, slots=True, kw_only=True)
class PipelineOwner:
    """Describe one named pipeline owner.

    Attributes:
        pipeline: Canonical pipeline identifier.
        run_id: Unique owner identity.
        pid: Owner process identifier.
        fingerprint: Effective configuration hash.
        state: Owner lifecycle state.
        generation: Current work generation.
        started_at: ISO-8601 creation timestamp.
        updated_at: ISO-8601 update timestamp.

    """

    pipeline: str
    run_id: str
    pid: int
    fingerprint: str
    state: str
    generation: int
    started_at: str
    updated_at: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PipelineRequest:
    """Describe one invocation observing a pipeline owner.

    Attributes:
        request_id: Unique observer identity.
        pipeline: Canonical pipeline identifier.
        pipeline_run_id: Shared owner identity.
        fingerprint: Requested configuration hash.
        pid: Observer process identifier.
        tty: Observer terminal, when interactive.
        state: Request lifecycle state.
        generation: Applied generation, when known.
        requested_at: ISO-8601 creation timestamp.
        updated_at: ISO-8601 update timestamp.
        detail: Human-readable timeline detail.
        error: Reset failure, when applicable.

    """

    request_id: str
    pipeline: str
    pipeline_run_id: str
    fingerprint: str
    pid: int
    tty: str | None
    state: str
    generation: int | None
    requested_at: str
    updated_at: str
    detail: str
    error: str | None = None

    def payload(self: Self) -> dict[str, JsonValue]:
        """Return an inspectable JSON request document.

        Returns:
            Serialized fields plus current observer liveness.

        """
        return {
            "schema": "exactus-pipeline-request/v2",
            "request_id": self.request_id,
            "pipeline": self.pipeline,
            "pipeline_run_id": self.pipeline_run_id,
            "fingerprint": self.fingerprint,
            "pid": self.pid,
            "tty": self.tty,
            "state": self.state,
            "generation": self.generation,
            "requested_at": self.requested_at,
            "updated_at": self.updated_at,
            "detail": self.detail,
            "error": self.error,
            "observer_alive": process_exists(pid=self.pid),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class PipelineClaim:
    """Describe one transactional pipeline admission decision.

    Attributes:
        mode: Owner, observer, or wait admission mode.
        owner: Current authoritative owner.
        request: Observer request, when admitted.
        detail: Human-readable decision detail.

    """

    mode: ClaimMode
    owner: PipelineOwner
    request: PipelineRequest | None
    detail: str


class PipelineCoordinator:
    """Serialize pipeline claims and finalization through SQLite."""

    def __init__(self: Self, *, runtime: Path) -> None:
        """Bind the supervisor to a shared runtime directory.

        Args:
            runtime: Shared ``EXACTUS_RESULTS/.runtime`` directory.

        """
        self.runtime: Path = runtime
        self.path: Path = runtime / Constants.database
        self.requests_root: Path = runtime / Constants.directory
        with closing(thing=self._connect()):
            pass

    def claim(
        self: Self,
        *,
        pipeline: str,
        run_id: str,
        pid: int,
        fingerprint: str,
        tty: str | None,
    ) -> PipelineClaim:
        """Atomically elect an owner, admit an observer, or require waiting.

        Args:
            pipeline: Canonical pipeline identifier.
            run_id: Candidate owner or observer identity.
            pid: Calling process identifier.
            fingerprint: Effective configuration hash.
            tty: Calling terminal, when interactive.

        Returns:
            Transactional admission decision.

        Raises:
            RuntimeError: If a live-owner decision loses its owner record.

        """
        now: str = utc_now()
        connection: Connection
        with closing(thing=self._connect()) as connection:
            _ = _execute(
                connection=connection,
                statement=Queries.begin_immediate,
            )
            row: tuple[ColumnValue, ...] | None = _execute(
                connection=connection,
                statement=Queries.select_owner,
                parameters=(pipeline,),
            ).fetchone()
            current: PipelineOwner | None = (
                self._owner(row=row) if row is not None else None
            )
            if not self._is_live(owner=current):
                owner: PipelineOwner = PipelineOwner(
                    pipeline=pipeline,
                    run_id=run_id,
                    pid=pid,
                    fingerprint=fingerprint,
                    state=Constants.running,
                    generation=1,
                    started_at=now,
                    updated_at=now,
                )
                self._elect(connection=connection, owner=owner)
                _ = _execute(connection=connection, statement=Queries.commit)
                return PipelineClaim(
                    mode="owner",
                    owner=owner,
                    request=None,
                    detail="elected as pipeline owner",
                )
            if current is None:
                msg: str = "live pipeline claim has no owner record"
                raise RuntimeError(msg)
            if (
                current.state == Constants.running
                and current.fingerprint == fingerprint
            ):
                request: PipelineRequest = PipelineRequest(
                    request_id=run_id,
                    pipeline=current.pipeline,
                    pipeline_run_id=current.run_id,
                    fingerprint=current.fingerprint,
                    pid=pid,
                    tty=tty,
                    state=Constants.pending,
                    generation=None,
                    requested_at=now,
                    updated_at=now,
                    detail="waiting for owner to reset shared work",
                )
                self._join(connection=connection, request=request)
                _ = _execute(connection=connection, statement=Queries.commit)
                self._materialize(request=request)
                return PipelineClaim(
                    mode="observer",
                    owner=current,
                    request=request,
                    detail=request.detail,
                )
            _ = _execute(connection=connection, statement=Queries.commit)
            detail: str = (
                "owner is finalizing"
                if current.state == Constants.sealed
                else "configuration differs from active owner"
            )
            return PipelineClaim(
                mode="wait",
                owner=current,
                request=None,
                detail=detail,
            )

    def owner(self: Self, *, pipeline: str) -> PipelineOwner | None:
        """Return the stored owner of a named pipeline.

        Args:
            pipeline: Canonical pipeline identifier.

        Returns:
            Current owner, if recorded.

        """
        connection: Connection
        with closing(thing=self._connect()) as connection:
            row: tuple[ColumnValue, ...] | None = _execute(
                connection=connection,
                statement=Queries.select_owner,
                parameters=(pipeline,),
            ).fetchone()
        return self._owner(row=row) if row is not None else None

    def requests(
        self: Self,
        *,
        pipeline_run_id: str,
        state: str,
    ) -> tuple[PipelineRequest, ...]:
        """Return one owner's requests in deterministic order.

        Args:
            pipeline_run_id: Owner pipeline identity.
            state: Lifecycle state to select.

        Returns:
            Matching observer requests.

        """
        connection: Connection
        with closing(thing=self._connect()) as connection:
            rows: list[tuple[ColumnValue, ...]] = _execute(
                connection=connection,
                statement=Queries.select_requests,
                parameters=(pipeline_run_id, state),
            ).fetchall()
        return tuple(map(self._request, rows))

    def get(self: Self, *, request_id: str) -> PipelineRequest | None:
        """Return one observer request.

        Args:
            request_id: Observer identity.

        Returns:
            Current request, if recorded.

        """
        connection: Connection
        with closing(thing=self._connect()) as connection:
            row: tuple[ColumnValue, ...] | None = _execute(
                connection=connection,
                statement=Queries.select_request,
                parameters=(request_id,),
            ).fetchone()
        return self._request(row) if row is not None else None

    def acknowledge(
        self: Self,
        *,
        requests: tuple[PipelineRequest, ...],
        generation: int,
        detail: str,
    ) -> None:
        """Commit a coalesced request batch to a work generation.

        Args:
            requests: Pending requests included in the generation.
            generation: New shared generation.
            detail: Observer timeline detail.

        """
        self._settle(
            requests=requests,
            state=Constants.applied,
            generation=generation,
            detail=detail,
            error=None,
        )

    def fail_requests(
        self: Self,
        *,
        requests: tuple[PipelineRequest, ...],
        error: str,
    ) -> None:
        """Publish a reset delivery failure.

        Args:
            requests: Requests whose reset failed.
            error: Human-readable failure detail.

        """
        self._settle(
            requests=requests,
            state=Constants.failed,
            generation=None,
            detail="owner could not apply the shared reset",
            error=error,
        )

    def settle_observer(
        self: Self,
        *,
        request_id: str,
        state: str,
        detail: str,
    ) -> None:
        """Record how an observer stopped waiting.

        Args:
            request_id: Observer identity.
            state: Terminal observer state.
            detail: Human-readable terminal detail.

        """
        now: str = utc_now()
        connection: Connection
        with closing(thing=self._connect()) as connection:
            _ = _execute(
                connection=connection,
                statement=Queries.settle_observer,
                parameters=(state, now, detail, request_id, Constants.applied),
            )
            _ = _execute(connection=connection, statement=Queries.commit)
        current: PipelineRequest | None = self.get(request_id=request_id)
        if current is not None:
            self._materialize(request=current)

    def seal(self: Self, *, pipeline: str, run_id: str) -> bool:
        """Seal an idle owner when no observer request is pending.

        Args:
            pipeline: Canonical pipeline identifier.
            run_id: Owner identity.

        Returns:
            Whether finalization won the admission race.

        """
        now: str = utc_now()
        connection: Connection
        with closing(thing=self._connect()) as connection:
            _ = _execute(
                connection=connection,
                statement=Queries.begin_immediate,
            )
            pending: tuple[ColumnValue, ...] | None = _execute(
                connection=connection,
                statement=Queries.select_pending,
                parameters=(run_id, Constants.pending),
            ).fetchone()
            if pending is not None:
                _ = _execute(connection=connection, statement=Queries.commit)
                return False
            _ = _execute(
                connection=connection,
                statement=Queries.seal_owner,
                parameters=(
                    Constants.sealed,
                    now,
                    pipeline,
                    run_id,
                    Constants.running,
                ),
            )
            _ = _execute(connection=connection, statement=Queries.commit)
            return connection.total_changes == 1

    def finish(self: Self, *, pipeline: str, run_id: str, state: str) -> None:
        """Publish a terminal owner state and prune old evidence.

        Args:
            pipeline: Canonical pipeline identifier.
            run_id: Owner identity.
            state: Terminal pipeline state.

        """
        connection: Connection
        with closing(thing=self._connect()) as connection:
            _ = _execute(
                connection=connection,
                statement=Queries.finish_owner,
                parameters=(state, utc_now(), pipeline, run_id),
            )
            _ = _execute(connection=connection, statement=Queries.commit)
        self.prune()

    def prune(self: Self) -> None:
        """Remove terminal observer evidence after the retention period."""
        cutoff: str = (
            datetime.now(tz=UTC).astimezone()
            - timedelta(days=Constants.retention_days)
        ).isoformat()
        terminal: tuple[str, str, str] = (
            Constants.failed,
            Constants.complete,
            Constants.detached,
        )
        connection: Connection
        with closing(thing=self._connect()) as connection:
            rows: list[tuple[ColumnValue, ...]] = _execute(
                connection=connection,
                statement=Queries.select_terminal,
                parameters=(cutoff, *terminal),
            ).fetchall()
            _ = _execute(
                connection=connection,
                statement=Queries.delete_terminal,
                parameters=(cutoff, *terminal),
            )
            _ = _execute(connection=connection, statement=Queries.commit)
        request_id: ColumnValue
        pipeline_run_id: ColumnValue
        for request_id, pipeline_run_id in rows:
            path: Path = (
                self.requests_root
                / str(object=pipeline_run_id)
                / f"{request_id}.json"
            )
            path.unlink(missing_ok=True)

    @staticmethod
    def _owner(*, row: tuple[ColumnValue, ...]) -> PipelineOwner:
        """Decode an owner row.

        Args:
            row: Owner columns in declared schema order.

        Returns:
            Typed owner record.

        """
        (
            pipeline,
            run_id,
            pid,
            fingerprint,
            state,
            generation,
            started_at,
            updated_at,
        ) = row
        return PipelineOwner(
            pipeline=str(object=pipeline),
            run_id=str(object=run_id),
            pid=(
                pid
                if isinstance(pid, int) and (not isinstance(pid, bool))
                else -1
            ),
            fingerprint=str(object=fingerprint),
            state=str(object=state),
            generation=(
                generation
                if isinstance(generation, int)
                and (not isinstance(generation, bool))
                else 0
            ),
            started_at=str(object=started_at),
            updated_at=str(object=updated_at),
        )

    @staticmethod
    def _request(row: tuple[ColumnValue, ...], /) -> PipelineRequest:
        """Decode a request row.

        Args:
            row: Request columns in declared schema order.

        Returns:
            Typed observer request.

        """
        (
            request_id,
            pipeline,
            pipeline_run_id,
            fingerprint,
            pid,
            tty,
            state,
            generation,
            requested_at,
            updated_at,
            detail,
            error,
        ) = row
        return PipelineRequest(
            request_id=str(object=request_id),
            pipeline=str(object=pipeline),
            pipeline_run_id=str(object=pipeline_run_id),
            fingerprint=str(object=fingerprint),
            pid=(
                pid
                if isinstance(pid, int) and (not isinstance(pid, bool))
                else -1
            ),
            tty=tty if isinstance(tty, str) else None,
            state=str(object=state),
            generation=(
                generation
                if isinstance(generation, int)
                and (not isinstance(generation, bool))
                else None
            ),
            requested_at=str(object=requested_at),
            updated_at=str(object=updated_at),
            detail=str(object=detail),
            error=error if isinstance(error, str) else None,
        )

    @staticmethod
    def _is_live(*, owner: PipelineOwner | None) -> bool:
        """Return whether an owner still controls its pipeline.

        Args:
            owner: Current stored owner.

        Returns:
            Whether the owner process and lifecycle are active.

        """
        return (
            owner is not None
            and owner.state in {Constants.running, Constants.sealed}
            and process_exists(pid=owner.pid)
        )

    @staticmethod
    def _elect(*, connection: Connection, owner: PipelineOwner) -> None:
        """Store an owner election inside the caller's transaction.

        Args:
            connection: Active immediate transaction.
            owner: Elected owner record.

        """
        _ = _execute(
            connection=connection,
            statement=Queries.upsert_owner,
            parameters=(
                owner.pipeline,
                owner.run_id,
                owner.pid,
                owner.fingerprint,
                owner.state,
                owner.generation,
                owner.started_at,
                owner.updated_at,
            ),
        )

    @staticmethod
    def _join(*, connection: Connection, request: PipelineRequest) -> None:
        """Store a compatible observer inside the caller's transaction.

        Args:
            connection: Active immediate transaction.
            request: Compatible pending observer request.

        """
        _ = _execute(
            connection=connection,
            statement=Queries.insert_request,
            parameters=(
                request.request_id,
                request.pipeline,
                request.pipeline_run_id,
                request.fingerprint,
                request.pid,
                request.tty,
                request.state,
                request.generation,
                request.requested_at,
                request.updated_at,
                request.detail,
                request.error,
            ),
        )

    def _connect(self: Self) -> Connection:
        """Open a configured, schema-ready database connection.

        A concurrent output reset may remove the runtime database while an
        owner process is still executing. Reapplying the idempotent schema on
        every new connection lets that owner reattach instead of querying an
        empty replacement database.

        Returns:
            Connection with a busy timeout and the coordination schema.

        """
        self.runtime.mkdir(parents=True, exist_ok=True)
        connection: Connection = connect(database=self.path, timeout=30.0)
        _ = _execute(connection=connection, statement=Queries.busy_timeout)
        _ = _execute(connection=connection, statement=Queries.owners_schema)
        _ = _execute(connection=connection, statement=Queries.requests_schema)
        _ = _execute(connection=connection, statement=Queries.requests_index)
        connection.commit()
        return connection

    def _settle(
        self: Self,
        *,
        requests: tuple[PipelineRequest, ...],
        state: str,
        generation: int | None,
        detail: str,
        error: str | None,
    ) -> None:
        """Update one request batch atomically.

        Args:
            requests: Requests to update.
            state: New lifecycle state.
            generation: Applied generation, when available.
            detail: Observer timeline detail.
            error: Reset error, when applicable.

        """
        now: str = utc_now()
        connection: Connection
        with closing(thing=self._connect()) as connection:
            _ = _execute(
                connection=connection,
                statement=Queries.begin_immediate,
            )
            request: PipelineRequest
            for request in requests:
                _ = _execute(
                    connection=connection,
                    statement=Queries.settle_request,
                    parameters=(
                        state,
                        generation,
                        now,
                        detail,
                        error,
                        request.request_id,
                        Constants.pending,
                    ),
                )
            if requests and state == Constants.applied:
                _ = _execute(
                    connection=connection,
                    statement=Queries.bump_owner_generation,
                    parameters=(
                        generation,
                        now,
                        requests[0].pipeline_run_id,
                        Constants.running,
                    ),
                )
            _ = _execute(connection=connection, statement=Queries.commit)
        for request in requests:
            current: PipelineRequest | None = self.get(
                request_id=request.request_id,
            )
            if current is not None:
                self._materialize(request=current)

    def _materialize(self: Self, *, request: PipelineRequest) -> None:
        """Write one request document for external inspection.

        Args:
            request: Current observer request.

        """
        write_json(
            path=(
                self.requests_root
                / request.pipeline_run_id
                / f"{request.request_id}.json"
            ),
            payload=request.payload(),
        )
