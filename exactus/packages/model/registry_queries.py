"""Typed registry schema and statements without handwritten SQL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Final

from exactus.packages.model.sqlite_model import (
    BinaryExpression,
    BinaryOperator,
    Command,
    CreateTable,
    Delete,
    Insert,
    Literal,
    Param,
    Pragma,
    PredicateNode,
    PrimaryKey,
    Select,
    Table,
    Update,
    command,
    function,
    pragma,
    upsert,
)


@dataclass(frozen=True, slots=True)
class RunRow:
    """One live or finished exactus run record.

    Attributes:
        run_id: Run id.
        kind: Kind.
        identifier: Identifier.
        pipeline_run_id: Pipeline run id.
        pid: Pid.
        output: Output.
        targets: Targets.
        status: Status.
        progress: Progress.
        step: Step.
        detail: Detail.
        created_at: Created at.
        updated_at: Updated at.
        elapsed_seconds: Elapsed seconds.

    """

    run_id: Annotated[str, PrimaryKey()]
    kind: str
    identifier: str
    pipeline_run_id: str | None
    pid: int
    output: str
    targets: str
    status: str
    progress: float
    step: str
    detail: str
    created_at: str
    updated_at: str
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class WorkRow:
    """Per-tool progress item owned by one run.

    Attributes:
        run_id: Run id.
        tool: Tool.
        item: Item.
        state: State.
        error: Error.
        updated_at: Updated at.

    """

    run_id: Annotated[str, PrimaryKey()]
    tool: str
    item: Annotated[str, PrimaryKey()]
    state: str
    error: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class LeaseRow:
    """One cross-process reader/writer resource lease.

    Attributes:
        lease_id: Lease id.
        run_id: Run id.
        tool: Tool.
        resource: Resource.
        mode: Mode.
        state: State.
        updated_at: Updated at.

    """

    lease_id: Annotated[str, PrimaryKey()]
    run_id: str
    tool: str
    resource: str
    mode: str
    state: str
    updated_at: str


class Queries:
    """Precompiled table handles and statements for the registry.

    Attributes:
        runs: Runs.
        work: Work.
        schema: Schema.
        work_schema: Work schema.
        upsert_work: Upsert work.
        select_work: Select work.
        delete_work: Delete work.
        prune_work: Prune work.
        leases: Leases.
        resource_schema: Resource schema.
        prune_resources: Prune resources.
        insert_resource: Insert resource.
        select_resource_conflicts: Select resource conflicts.
        activate_resource: Activate resource.
        delete_resource: Delete resource.
        delete_run_resources: Delete run resources.
        select_live: Select live.
        count_runs: Count runs.
        count_finished: Count finished.
        insert_run: Insert run.
        reap_run: Reap run.
        prune_runs: Prune runs.
        trim_runs: Trim runs.
        beat_run: Beat run.
        commit: Commit.
        rollback: Rollback.
        begin_immediate: Begin immediate.
        vacuum: Vacuum.
        journal_mode: Journal mode.
        checkpoint: Checkpoint.

    """

    runs: Final[Table] = Table.from_dataclass(model=RunRow, name="runs")
    work: Final[Table] = Table.from_dataclass(
        model=WorkRow,
        name="work_activities",
    )
    schema: Final[CreateTable] = runs.create()
    work_schema: Final[CreateTable] = work.create()
    upsert_work: Final[Insert] = upsert(
        table=work,
        columns=work.columns,
        conflict=(work.col(name="run_id"), work.col(name="item")),
        updates=(
            work.col(name="state"),
            work.col(name="error"),
            work.col(name="updated_at"),
        ),
    )
    select_work: Final[Select] = work.select(
        columns=(work.col(name="state"),),
    ).where(
        predicate=work.col(name="run_id")
        .eq(value=Param())
        .and_(other=work.col(name="item").eq(value=Param())),
    )
    delete_work: Final[Delete] = work.delete().where(
        predicate=work.col(name="run_id").eq(value=Param()),
    )
    prune_work: Final[Delete] = work.delete().where(
        predicate=work.col(name="run_id").not_in(
            statement=runs.select(columns=(runs.col(name="run_id"),)),
        ),
    )
    leases: Final[Table] = Table.from_dataclass(
        model=LeaseRow,
        name="resource_leases",
    )
    resource_schema: Final[CreateTable] = leases.create()
    prune_resources: Final[Delete] = leases.delete().where(
        predicate=leases.col(name="run_id").not_in(
            statement=runs.select(columns=(runs.col(name="run_id"),)).where(
                predicate=runs.col(name="status").eq(value=Param()),
            ),
        ),
    )
    insert_resource: Final[Insert] = leases.insert(replace=True)
    select_resource_conflicts: Final[Select] = (
        leases.select(columns=(leases.col(name="lease_id"),))
        .where(
            predicate=leases.col(name="resource")
            .eq(value=Param())
            .and_(
                other=leases.col(name="lease_id")
                .ne(value=Param())
                .and_(other=leases.col(name="run_id").ne(value=Param())),
            )
            .and_(
                other=leases.col(name="state")
                .eq(value=Literal(value="active"))
                .or_(
                    other=BinaryExpression(
                        left=Param(),
                        operator=BinaryOperator.EQ,
                        right=Literal(value="read"),
                    )
                    .and_(
                        other=leases.col(name="mode").eq(
                            value=Literal(value="write"),
                        ),
                    )
                    .and_(
                        other=leases.col(name="state").eq(
                            value=Literal(value="waiting"),
                        ),
                    ),
                ),
            )
            .and_(
                other=BinaryExpression(
                    left=Param(),
                    operator=BinaryOperator.EQ,
                    right=Literal(value="write"),
                ).or_(
                    other=leases.col(name="mode").eq(
                        value=Literal(value="write"),
                    ),
                ),
            ),
        )
        .limit(value=Literal(value=1))
    )
    activate_resource: Final[Update] = leases.update(
        values=(
            (leases.col(name="state"), Literal(value="active")),
            (leases.col(name="updated_at"), Param()),
        ),
    ).where(predicate=leases.col(name="lease_id").eq(value=Param()))
    delete_resource: Final[Delete] = leases.delete().where(
        predicate=leases.col(name="lease_id").eq(value=Param()),
    )
    delete_run_resources: Final[Delete] = leases.delete().where(
        predicate=leases.col(name="run_id").eq(value=Param()),
    )
    select_live: Final[Select] = runs.select().where(
        predicate=runs.col(name="status").eq(value=Param()),
    )
    count_runs: Final[Select] = runs.select(
        columns=(
            function(name="COUNT", arguments=(runs.col(name="run_id"),)),
        ),
    )
    count_finished: Final[Select] = runs.select(
        columns=(
            function(name="COUNT", arguments=(runs.col(name="run_id"),)),
        ),
    ).where(predicate=runs.col(name="status").ne(value=Param()))
    insert_run: Final[Insert] = runs.insert(replace=True)
    reap_run: Final[Update] = runs.update(
        values=(
            (runs.col(name="status"), Param()),
            (runs.col(name="updated_at"), Param()),
        ),
    ).where(predicate=runs.col(name="run_id").eq(value=Param()))
    prune_runs: Final[Delete] = runs.delete().where(
        predicate=runs.col(name="status")
        .ne(value=Param())
        .and_(other=runs.col(name="updated_at").lt(value=Param())),
    )
    trim_runs: Final[Delete] = runs.delete().where(
        predicate=runs.col(name="status")
        .ne(value=Param())
        .and_(
            other=runs.col(name="run_id").not_in(
                statement=runs.select(columns=(runs.col(name="run_id"),))
                .where(predicate=runs.col(name="status").ne(value=Param()))
                .order_by(values=(runs.col(name="updated_at").desc(),))
                .limit(value=Param()),
            ),
        ),
    )
    beat_run: Final[Update] = runs.update(
        values=(
            (runs.col(name="updated_at"), Param()),
            (
                runs.col(name="status"),
                function(
                    name="COALESCE",
                    arguments=(Param(), runs.col(name="status")),
                ),
            ),
            (
                runs.col(name="progress"),
                function(
                    name="COALESCE",
                    arguments=(Param(), runs.col(name="progress")),
                ),
            ),
            (
                runs.col(name="step"),
                function(
                    name="COALESCE",
                    arguments=(Param(), runs.col(name="step")),
                ),
            ),
            (
                runs.col(name="detail"),
                function(
                    name="COALESCE",
                    arguments=(Param(), runs.col(name="detail")),
                ),
            ),
            (
                runs.col(name="elapsed_seconds"),
                function(
                    name="COALESCE",
                    arguments=(Param(), runs.col(name="elapsed_seconds")),
                ),
            ),
        ),
    ).where(predicate=runs.col(name="run_id").eq(value=Param()))
    commit: Final[Command] = command(name="commit")
    rollback: Final[Command] = command(name="rollback")
    begin_immediate: Final[Command] = command(name="begin_immediate")
    vacuum: Final[Command] = command(name="vacuum")
    journal_mode: Final[Pragma] = pragma(
        name="journal_mode",
        value=Literal(value="WAL"),
    )
    checkpoint: Final[Pragma] = pragma(
        name="wal_checkpoint",
        call=Literal(value="TRUNCATE"),
    )


def live_processes_for_run(*, run_id: str) -> Select:
    """Build the process-id query used by the generated kill script.

    Args:
        run_id: Run id.

    Returns:
        The resulting value.

    """
    running: PredicateNode = Queries.runs.col(name="status").eq(
        value=Literal(value="RUNNING"),
    )
    owner: PredicateNode = (
        Queries.runs.col(name="run_id")
        .eq(value=Literal(value=run_id))
        .or_(
            other=Queries.runs.col(name="pipeline_run_id").eq(
                value=Literal(value=run_id),
            ),
        )
    )
    return Queries.runs.select(columns=(Queries.runs.col(name="pid"),)).where(
        predicate=running.and_(other=owner),
    )
