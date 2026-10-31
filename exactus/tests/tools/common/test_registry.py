# Copyright (c) 2026
"""The cross-process run registry."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from os import getpid, getppid
from typing import TYPE_CHECKING

from exactus.packages.model.registry_queries import Queries
from exactus.packages.model.sqlite_model import (
    Param,
    connect,
    execute,
    function,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_none,
    expect_true,
    private_call,
    require,
    require_type,
)
from exactus.tools.common import registry as rg
from exactus.tools.common.registry import (
    RunBeat,
    RunClaim,
    RunRecord,
    RunRegistry,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from exactus.packages.model.sqlite_model import Connection, SqlScalar


def _claim(
    run_id: str,
    out: Path,
    *,
    pid: int | None = None,
    targets: tuple[str, ...] = (),
) -> RunClaim:
    """Build a tool claim.

    Args:
        run_id: Run identifier.
        out: Output directory.
        pid: Owning pid; defaults to this process.
        targets: Extra registered targets.

    Returns:
        The claim.

    """
    return RunClaim(
        kind="tool",
        identifier="demo",
        run_id=run_id,
        pipeline_run_id=None,
        pid=pid if pid is not None else getpid(),
        output=out,
        targets=targets,
    )


def _exercise_concurrent_registry(*, database: Path, index: int) -> bool:
    """Complete one registry connection lifecycle from a worker thread.

    Args:
        database: Shared registry database path.
        index: Unique activity and lease suffix.

    Returns:
        Whether the resource lease was acquired.

    """
    registry: RunRegistry = RunRegistry(path=database)
    lease_id: str = f"lease-{index}"
    acquired: bool | None = registry.acquire_resource(
        lease_id=lease_id,
        run_id="concurrent",
        tool="kwargs_typehints",
        resource="workspace:source-tree",
        mode="read",
    )
    registry.publish_activity(
        run_id="concurrent",
        tool="kwargs_typehints",
        item=f"item-{index}",
        state="done",
    )
    registry.release_resource(lease_id=lease_id)
    return acquired is True


def test_for_output_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Registry paths follow the override, ancestor, then sibling rules.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.delenv(name="EXACTUS_REGISTRY", raising=False)
    nested: Path = tmp_path / "EXACTUS_RESULTS" / "LINTS" / "deep"
    expect_equal(
        actual=RunRegistry.for_output(output=nested).path,
        expected=(tmp_path / "EXACTUS_RESULTS").resolve()
        / ".runtime"
        / "runs.db",
    )
    plain: Path = tmp_path / "x" / "out"
    expect_equal(
        actual=RunRegistry.for_output(output=plain).path,
        expected=(tmp_path / "x").resolve() / ".runtime" / "runs.db",
    )
    monkeypatch.setenv(
        name="EXACTUS_REGISTRY",
        value=str(object=tmp_path / "r.db"),
    )
    expect_equal(
        actual=RunRegistry.for_output(output=plain).path,
        expected=tmp_path / "r.db",
    )


def test_concurrent_connection_lifecycles_do_not_deadlock(
    tmp_path: Path,
) -> None:
    """Parallel registry clients serialize SQLite open and close safely.

    Args:
        tmp_path: Per-test temporary directory.

    """
    database: Path = tmp_path / "runs.db"
    registry: RunRegistry = RunRegistry(path=database)
    expect_equal(
        actual=registry.claim(
            request=_claim(run_id="concurrent", out=tmp_path / "output"),
        ),
        expected=(),
    )
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures: list[Future[bool]] = [
            pool.submit(
                _exercise_concurrent_registry,
                database=database,
                index=index,
            )
            for index in range(64)
        ]
        expect_true(
            condition=all(future.result(timeout=10.0) for future in futures),
        )
    connection: Connection = connect(database=database)
    with connection:
        remaining: int = int(
            execute(
                connection=connection,
                statement=Queries.leases.select(
                    columns=(
                        function(
                            name="COUNT",
                            arguments=(Queries.leases.col(name="lease_id"),),
                        ),
                    ),
                ),
            ).fetchone()[0],
        )
    connection.close()
    expect_equal(actual=remaining, expected=0)


def test_claim_beat_finish_live(tmp_path: Path) -> None:
    """A claimed run is visible, updatable, and finishable.

    Args:
        tmp_path: Per-test temporary directory.

    """
    reg: RunRegistry = RunRegistry(path=tmp_path / "db" / "runs.db")
    out: Path = tmp_path / "o"
    expect_equal(
        actual=reg.claim(request=_claim(run_id="a", out=out)),
        expected=(),
    )
    live: tuple[RunRecord, ...] = reg.live()
    expect_equal(actual=[r.run_id for r in live], expected=["a"])
    reg.beat(
        pulse=RunBeat(
            run_id="a",
            progress=0.5,
            step="s",
            detail="d",
            elapsed_seconds=2.0,
        ),
    )
    record: RunRecord = reg.live()[0]
    expect_equal(
        actual=(record.progress, record.step, record.detail),
        expected=(0.5, "s", "d"),
    )
    reg.finish(run_id="a", status="DONE", elapsed_seconds=3.0)
    expect_equal(actual=reg.live(), expected=())
    reg.finish(run_id="missing", status="FAIL", elapsed_seconds=1.0)


def test_activity_ledger_and_source_resource_leases(tmp_path: Path) -> None:
    """File releases and logical source barriers coordinate across runs.

    Args:
        tmp_path: Per-test temporary directory.

    """
    database: Path = tmp_path / "runs.db"
    registry: RunRegistry = RunRegistry(path=database)
    expect_equal(
        actual=registry.claim(
            request=_claim(run_id="reader", out=tmp_path / "reader"),
        ),
        expected=(),
    )
    connection: Connection = connect(database=database)
    with connection:
        source: tuple[SqlScalar, ...] | None = execute(
            connection=connection,
            statement=Queries.runs.select().where(
                predicate=Queries.runs.col(name="run_id").eq(value=Param()),
            ),
            parameters=("reader",),
        ).fetchone()
        row: tuple[SqlScalar, ...] = require(value=source)
        _ = execute(
            connection=connection,
            statement=Queries.insert_run,
            parameters=("writer", *row[1:5], f"{row[5]}-writer", *row[6:]),
        )
    connection.close()
    item: str = str(object=(tmp_path / "source.py").resolve())
    registry.publish_activity(
        run_id="reader",
        tool="readme",
        item=item,
        state="done",
    )
    expect_equal(
        actual=registry.activity_state(run_id="reader", item=item),
        expected="done",
    )
    expect_true(
        condition=registry.acquire_resource(
            lease_id="reader-lease",
            run_id="reader",
            tool="readme",
            resource="workspace:source-tree",
            mode="read",
        )
        is True,
    )
    expect_true(
        condition=registry.acquire_resource(
            lease_id="writer-lease",
            run_id="writer",
            tool="lints",
            resource="workspace:source-tree",
            mode="write",
        )
        is False,
    )
    registry.release_resource(lease_id="reader-lease")
    expect_true(
        condition=registry.acquire_resource(
            lease_id="writer-lease",
            run_id="writer",
            tool="lints",
            resource="workspace:source-tree",
            mode="write",
        )
        is True,
    )
    registry.release_resource(lease_id="writer-lease")


def test_conflicts_and_reaping(tmp_path: Path) -> None:
    """Live foreign runs conflict; dead and same-pid runs are reaped.

    Args:
        tmp_path: Per-test temporary directory.

    """
    reg: RunRegistry = RunRegistry(path=tmp_path / "runs.db")
    out: Path = tmp_path / "o"
    parent: int = getppid()
    expect_equal(
        actual=reg.claim(
            request=_claim(
                run_id="foreign",
                out=out,
                pid=parent,
                targets=(str(object=out.resolve()),),
            ),
        ),
        expected=(),
    )
    conflicts: tuple[RunRecord, ...] | None = reg.claim(
        request=_claim(run_id="mine", out=out),
    )
    conflicts = require(value=conflicts)
    expect_equal(actual=[c.run_id for c in conflicts], expected=["foreign"])
    other: Path = tmp_path / "other"
    by_target: tuple[RunRecord, ...] | None = reg.claim(
        request=_claim(
            run_id="t",
            out=other,
            targets=(str(object=out.resolve()),),
        ),
    )
    by_target = require(value=by_target)
    expect_equal(actual={c.run_id for c in by_target}, expected={"foreign"})
    expect_true(
        condition=reg.claim(
            request=_claim(run_id="dead", out=other, pid=2_000_000_000),
        )
        is not None,
    )
    again: tuple[RunRecord, ...] | None = reg.claim(
        request=_claim(run_id="mine2", out=tmp_path / "third"),
    )
    again = require(value=again)
    expect_equal(
        actual={r.run_id for r in reg.live()},
        expected={"foreign", "mine2"},
    )


def test_prune_old_and_trim_finished(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Old finished rows are pruned and the database compacted.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    db: Path = tmp_path / "runs.db"
    reg: RunRegistry = RunRegistry(path=db)
    expect_equal(
        actual=reg.claim(request=_claim(run_id="old", out=tmp_path / "o")),
        expected=(),
    )
    reg.finish(run_id="old", status="DONE", elapsed_seconds=1.0)
    stale: str = (
        datetime.now(tz=UTC).astimezone() - timedelta(days=30)
    ).isoformat()
    conn: Connection = connect(database=db)
    with conn:
        _ = execute(
            connection=conn,
            statement=Queries.runs.update(
                values=((Queries.runs.col(name="updated_at"), Param()),),
            ),
            parameters=(stale,),
        )
    expect_equal(
        actual=reg.claim(request=_claim(run_id="new", out=tmp_path / "o2")),
        expected=(),
    )
    conn = connect(database=db)
    with conn:
        ids: list[str] = [
            str(object=row[0])
            for row in execute(
                connection=conn,
                statement=Queries.runs.select(
                    columns=(Queries.runs.col(name="run_id"),),
                ),
            ).fetchall()
        ]
    conn.close()
    expect_equal(actual=ids, expected=["new"])
    monkeypatch.setattr(target=rg.RegistryTables, name="max_finished", value=1)
    for index in range(3):
        _ = reg.claim(
            request=_claim(run_id=f"f{index}", out=tmp_path / f"o{index}"),
        )
        reg.finish(run_id=f"f{index}", status="DONE", elapsed_seconds=0.1)
    expect_equal(
        actual=reg.claim(request=_claim(run_id="last", out=tmp_path / "zz")),
        expected=(),
    )


def test_unavailable_registry_degrades(tmp_path: Path) -> None:
    """An unusable database path yields ``None``/empty, never an error.

    Args:
        tmp_path: Per-test temporary directory.

    """
    blocker: Path = tmp_path / "file"
    blocker.write_text(data="x")
    reg: RunRegistry = RunRegistry(path=blocker / "runs.db")
    expect_none(value=reg.claim(request=_claim(run_id="a", out=tmp_path)))
    expect_equal(actual=reg.live(), expected=())
    reg.beat(pulse=RunBeat(run_id="a"))


def _decode(*, row: tuple[object, ...]) -> RunRecord:
    """Decode one registry row through the module's private decoder.

    Args:
        row: Raw database row.

    Returns:
        The decoded run record.

    """
    return require_type(
        value=private_call(owner=rg, name="_record", row=row),
        kind=RunRecord,
    )


def test_record_decoding_is_defensive() -> None:
    """Corrupt columns degrade to inert values."""
    record: RunRecord = _decode(
        row=(
            None,
            1,
            None,
            5,
            True,
            None,
            "{bad",
            None,
            True,
            None,
            None,
            None,
            None,
            "x",
        ),
    )
    expect_equal(actual=record.pid, expected=-1)
    expect_equal(actual=record.targets, expected=())
    expect_equal(actual=record.progress, expected=0.0)
    expect_none(value=record.pipeline_run_id)
    expect_equal(actual=record.elapsed_seconds, expected=0.0)
    scalar: RunRecord = _decode(
        row=(
            "r",
            "k",
            "i",
            "p",
            7,
            "o",
            "5",
            "s",
            0.5,
            "st",
            "d",
            "c",
            "u",
            1.5,
        ),
    )
    expect_equal(actual=scalar.targets, expected=())
    expect_equal(actual=scalar.pid, expected=7)
    listed: RunRecord = _decode(
        row=(
            "r",
            "k",
            "i",
            None,
            7,
            "o",
            '["a", 2]',
            "s",
            1,
            "st",
            "d",
            "c",
            "u",
            1,
        ),
    )
    expect_equal(actual=listed.targets, expected=("a", "2"))


def test_sanitize_bounds_rows_and_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``sanitize`` trims finished rows and ``beat`` clips long text.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    db: Path = tmp_path / "runs.db"
    reg: RunRegistry = RunRegistry(path=db)
    for index in range(5):
        _ = reg.claim(
            request=_claim(run_id=f"r{index}", out=tmp_path / f"o{index}"),
        )
        reg.beat(
            pulse=RunBeat(
                run_id=f"r{index}",
                status="DONE",
                detail="x" * 5000,
            ),
        )
    monkeypatch.setattr(target=rg.RegistryTables, name="max_finished", value=2)
    removed: int = reg.sanitize()
    conn: Connection = connect(database=db)
    with conn:
        rows: list[tuple[str, int]] = [
            (str(object=row[0]), len(str(object=row[1])))
            for row in execute(
                connection=conn,
                statement=Queries.runs.select(
                    columns=(
                        Queries.runs.col(name="run_id"),
                        Queries.runs.col(name="detail"),
                    ),
                ).order_by(values=(Queries.runs.col(name="run_id"),)),
            ).fetchall()
        ]
    conn.close()
    expect_equal(actual=len(rows), expected=2)
    expect_equal(actual=removed, expected=3)
    expect_true(
        condition=all(size <= rg.RegistryTables.max_text for _, size in rows),
    )


def test_runtime_env_limits_bound_finished_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``EXACTUS_RUNTIME_MAX_*`` bound finished rows, never live ones.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.delenv(name=rg.RegistryTables.max_runs_env, raising=False)
    monkeypatch.delenv(name=rg.RegistryTables.max_size_env, raising=False)
    db: Path = tmp_path / "runs.db"
    reg: RunRegistry = RunRegistry(path=db)
    expect_equal(
        actual=reg.claim(
            request=_claim(
                run_id="live",
                out=tmp_path / "live",
                pid=getppid(),
            ),
        ),
        expected=(),
    )
    for index in range(4):
        _ = reg.claim(
            request=_claim(run_id=f"f{index}", out=tmp_path / f"o{index}"),
        )
        reg.finish(run_id=f"f{index}", status="DONE", elapsed_seconds=0.1)
    monkeypatch.setenv(name=rg.RegistryTables.max_runs_env, value="2")
    monkeypatch.setenv(name=rg.RegistryTables.max_size_env, value="0")
    expect_equal(actual=reg.sanitize(), expected=2)
    conn: Connection = connect(database=db)
    with conn:
        ids: set[str] = {
            str(object=row[0])
            for row in execute(
                connection=conn,
                statement=Queries.runs.select(
                    columns=(Queries.runs.col(name="run_id"),),
                ),
            ).fetchall()
        }
    conn.close()
    expect_equal(actual=ids, expected={"live", "f2", "f3"})
    monkeypatch.setenv(name=rg.RegistryTables.max_size_env, value="1")
    expect_equal(actual=reg.sanitize(), expected=2)
    conn = connect(database=db)
    with conn:
        remaining: list[str] = [
            str(object=row[0])
            for row in execute(
                connection=conn,
                statement=Queries.runs.select(
                    columns=(Queries.runs.col(name="run_id"),),
                ),
            ).fetchall()
        ]
    conn.close()
    expect_equal(actual=remaining, expected=["live"])
    expect_equal(actual=reg.sanitize(), expected=0)
