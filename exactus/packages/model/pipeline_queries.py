"""Typed pipeline schema and statements without handwritten SQL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Final

from exactus.packages.model.sqlite_model import (
    Command,
    CreateIndex,
    CreateTable,
    Delete,
    Insert,
    Literal,
    Param,
    Pragma,
    PrimaryKey,
    Select,
    Table,
    Unique,
    Update,
    command,
    pragma,
    upsert,
)


@dataclass(frozen=True, slots=True)
class OwnerRow:
    """One named pipeline owner record.

    Attributes:
        pipeline: Pipeline.
        run_id: Run id.
        pid: Pid.
        fingerprint: Fingerprint.
        state: State.
        generation: Generation.
        started_at: Started at.
        updated_at: Updated at.

    """

    pipeline: Annotated[str, PrimaryKey()]
    run_id: Annotated[str, Unique()]
    pid: int
    fingerprint: str
    state: str
    generation: int
    started_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class RequestRow:
    """One pipeline observer request record.

    Attributes:
        request_id: Request id.
        pipeline: Pipeline.
        pipeline_run_id: Pipeline run id.
        fingerprint: Fingerprint.
        pid: Pid.
        tty: Tty.
        state: State.
        generation: Generation.
        requested_at: Requested at.
        updated_at: Updated at.
        detail: Detail.
        error: Error.

    """

    request_id: Annotated[str, PrimaryKey()]
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
    error: str | None


class Queries:
    """Precompiled table handles and statements for the coordinator.

    Attributes:
        owners: Owners.
        requests: Requests.
        owners_schema: Owners schema.
        requests_schema: Requests schema.
        requests_index: Requests index.
        busy_timeout: Busy timeout.
        begin_immediate: Begin immediate.
        commit: Commit.
        rollback: Rollback.
        select_owner: Select owner.
        upsert_owner: Upsert owner.
        insert_request: Insert request.
        select_request: Select request.
        select_requests: Select requests.
        settle_request: Settle request.
        settle_observer: Settle observer.
        bump_owner_generation: Bump owner generation.
        select_pending: Select pending.
        seal_owner: Seal owner.
        finish_owner: Finish owner.
        select_terminal: Select terminal.
        delete_terminal: Delete terminal.

    """

    owners: Final[Table] = Table.from_dataclass(
        model=OwnerRow,
        name="pipeline_owners",
    )
    requests: Final[Table] = Table.from_dataclass(
        model=RequestRow,
        name="pipeline_requests",
    )
    owners_schema: Final[CreateTable] = owners.create()
    requests_schema: Final[CreateTable] = requests.create()
    requests_index: Final[CreateIndex] = requests.create_index(
        name="pipeline_requests_owner_state",
        columns=("pipeline_run_id", "state", "requested_at"),
    )
    busy_timeout: Final[Pragma] = pragma(
        name="busy_timeout",
        value=Literal(value=30000),
    )
    begin_immediate: Final[Command] = command(name="begin_immediate")
    commit: Final[Command] = command(name="commit")
    rollback: Final[Command] = command(name="rollback")
    select_owner: Final[Select] = owners.select().where(
        predicate=owners.col(name="pipeline").eq(value=Param()),
    )
    upsert_owner: Final[Insert] = upsert(
        table=owners,
        columns=owners.columns,
        conflict=(owners.col(name="pipeline"),),
        updates=(
            owners.col(name="run_id"),
            owners.col(name="pid"),
            owners.col(name="fingerprint"),
            owners.col(name="state"),
            owners.col(name="generation"),
            owners.col(name="started_at"),
            owners.col(name="updated_at"),
        ),
    )
    insert_request: Final[Insert] = requests.insert()
    select_request: Final[Select] = requests.select().where(
        predicate=requests.col(name="request_id").eq(value=Param()),
    )
    select_requests: Final[Select] = (
        requests.select()
        .where(
            predicate=requests.col(name="pipeline_run_id")
            .eq(value=Param())
            .and_(other=requests.col(name="state").eq(value=Param())),
        )
        .order_by(
            values=(
                requests.col(name="requested_at"),
                requests.col(name="request_id"),
            ),
        )
    )
    settle_request: Final[Update] = requests.update(
        values=(
            (requests.col(name="state"), Param()),
            (requests.col(name="generation"), Param()),
            (requests.col(name="updated_at"), Param()),
            (requests.col(name="detail"), Param()),
            (requests.col(name="error"), Param()),
        ),
    ).where(
        predicate=requests.col(name="request_id")
        .eq(value=Param())
        .and_(other=requests.col(name="state").eq(value=Param())),
    )
    settle_observer: Final[Update] = requests.update(
        values=(
            (requests.col(name="state"), Param()),
            (requests.col(name="updated_at"), Param()),
            (requests.col(name="detail"), Param()),
        ),
    ).where(
        predicate=requests.col(name="request_id")
        .eq(value=Param())
        .and_(other=requests.col(name="state").eq(value=Param())),
    )
    bump_owner_generation: Final[Update] = owners.update(
        values=(
            (owners.col(name="generation"), Param()),
            (owners.col(name="updated_at"), Param()),
        ),
    ).where(
        predicate=owners.col(name="run_id")
        .eq(value=Param())
        .and_(other=owners.col(name="state").eq(value=Param())),
    )
    select_pending: Final[Select] = (
        requests.select(columns=(requests.col(name="request_id"),))
        .where(
            predicate=requests.col(name="pipeline_run_id")
            .eq(value=Param())
            .and_(other=requests.col(name="state").eq(value=Param())),
        )
        .limit(value=Literal(value=1))
    )
    seal_owner: Final[Update] = owners.update(
        values=(
            (owners.col(name="state"), Param()),
            (owners.col(name="updated_at"), Param()),
        ),
    ).where(
        predicate=owners.col(name="pipeline")
        .eq(value=Param())
        .and_(other=owners.col(name="run_id").eq(value=Param()))
        .and_(other=owners.col(name="state").eq(value=Param())),
    )
    finish_owner: Final[Update] = owners.update(
        values=(
            (owners.col(name="state"), Param()),
            (owners.col(name="updated_at"), Param()),
        ),
    ).where(
        predicate=owners.col(name="pipeline")
        .eq(value=Param())
        .and_(other=owners.col(name="run_id").eq(value=Param())),
    )
    select_terminal: Final[Select] = requests.select(
        columns=(
            requests.col(name="request_id"),
            requests.col(name="pipeline_run_id"),
        ),
    ).where(
        predicate=requests.col(name="updated_at")
        .lt(value=Param())
        .and_(
            other=requests.col(name="state").in_(
                values=(Param(), Param(), Param()),
            ),
        ),
    )
    delete_terminal: Final[Delete] = requests.delete().where(
        predicate=requests.col(name="updated_at")
        .lt(value=Param())
        .and_(
            other=requests.col(name="state").in_(
                values=(Param(), Param(), Param()),
            ),
        ),
    )
