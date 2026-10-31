"""Behavioral tests for the typed SQLite compiler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, NoReturn

import pytest

from exactus.packages.model.registry_queries import (
    Queries,
    live_processes_for_run,
)
from exactus.packages.model.sqlite_model import (
    Connection,
    ConstraintError,
    Database,
    Identifier,
    Param,
    Parameters,
    PrimaryKey,
    RawSql,
    Select,
    SQLiteCompiler,
    SqlScalar,
    Table,
    alter_rename_column,
    alter_rename_table,
    connect,
    drop,
    execute,
    pragma,
    quote_identifier,
)
from exactus.tests.common.support import expect_equal, expect_in, require


def test_registry_statements_execute_end_to_end() -> None:
    """Insert and heartbeat a registry run through compiled statements."""
    connection: Connection = connect(database=":memory:")
    execute(connection=connection, statement=Queries.schema)
    execute(connection=connection, statement=Queries.work_schema)
    run: Parameters = (
        "r",
        "tool",
        "demo",
        None,
        7,
        "artifacts/out",
        "[]",
        "RUNNING",
        0.0,
        "start",
        "",
        "a",
        "a",
        0.0,
    )
    execute(
        connection=connection,
        statement=Queries.insert_run,
        parameters=run,
    )
    expect_equal(
        actual=execute(
            connection=connection,
            statement=Queries.select_live,
            parameters=("RUNNING",),
        ).fetchone(),
        expected=run,
    )
    execute(
        connection=connection,
        statement=Queries.beat_run,
        parameters=("b", None, 0.5, None, "detail", 1.25, "r"),
    )
    row: tuple[SqlScalar, ...] = require(
        value=execute(
            connection=connection,
            statement=Queries.select_live,
            parameters=("RUNNING",),
        ).fetchone(),
    )
    expect_equal(actual=row[8:11], expected=(0.5, "start", "detail"))


def test_upsert_preserves_key_and_updates_mutable_values() -> None:
    """Upsert a work row twice and keep the last mutable values."""
    connection: Connection = connect(database=":memory:")
    execute(connection=connection, statement=Queries.work_schema)
    execute(
        connection=connection,
        statement=Queries.upsert_work,
        parameters=("r", "tool", "item", "A", "", "1"),
    )
    execute(
        connection=connection,
        statement=Queries.upsert_work,
        parameters=("r", "other", "item", "B", "e", "2"),
    )
    expect_equal(
        actual=execute(
            connection=connection,
            statement=Queries.select_work,
            parameters=("r", "item"),
        ).fetchone(),
        expected=("B",),
    )


def test_dynamic_identifier_operations_are_safe() -> None:
    """Quote hostile identifiers in every structural DDL operation."""
    connection: Connection = connect(database=":memory:")
    Table(name='odd"table')
    execute(
        connection=connection,
        statement=RawSql(value='CREATE TABLE "odd""table" ("a" TEXT)'),
    )
    execute(
        connection=connection,
        statement=alter_rename_column(table='odd"table', old="a", new='b"c'),
    )
    execute(
        connection=connection,
        statement=alter_rename_table(table='odd"table', new='new"table'),
    )
    columns: list[tuple[SqlScalar, ...]] = execute(
        connection=connection,
        statement=pragma(
            name="table_xinfo",
            call=Identifier(value='new"table'),
        ),
    ).fetchall()
    expect_equal(actual=columns[0][1], expected='b"c')


def test_drop_rejects_non_schema_object_kinds() -> None:
    """Reject DROP operations outside the supported object kinds."""
    with pytest.raises(
        expected_exception=ValueError,
        match="Unsupported DROP kind",
    ):
        drop(kind="table; drop table x", name="x")


def test_identifier_quoting_rejects_invalid_and_escapes_quotes() -> None:
    """Escape embedded quotes and reject empty or NUL identifiers."""
    expect_equal(actual=quote_identifier(value='a"b'), expected='"a""b"')
    with pytest.raises(expected_exception=ValueError, match="nonempty"):
        quote_identifier(value="")
    with pytest.raises(expected_exception=ValueError, match="NUL-free"):
        quote_identifier(value="a\0b")


def test_dataclass_schema_maps_optional_and_composite_primary_key() -> None:
    """Derive composite keys and optional columns from a dataclass."""

    @dataclass(frozen=True, slots=True)
    class Row:
        left: Annotated[str, PrimaryKey()]
        right: Annotated[int, PrimaryKey()]
        note: str | None

    connection: Connection = connect(database=":memory:")
    table: Table = Table(model=Row, name="sample")
    execute(connection=connection, statement=table.create())
    execute(
        connection=connection,
        statement=table.insert(),
        parameters=("x", 1, None),
    )
    with pytest.raises(expected_exception=ConstraintError):
        execute(
            connection=connection,
            statement=table.insert(),
            parameters=("x", 1, "again"),
        )


def test_generated_kill_query_is_executable_sql() -> None:
    """Execute the generated live-process query against the registry."""
    connection: Connection = connect(database=":memory:")
    execute(connection=connection, statement=Queries.schema)
    run: Parameters = (
        "owner",
        "tool",
        "demo",
        None,
        42,
        "o",
        "[]",
        "RUNNING",
        0.0,
        "",
        "",
        "a",
        "a",
        0.0,
    )
    execute(
        connection=connection,
        statement=Queries.insert_run,
        parameters=run,
    )
    statement: Select = live_processes_for_run(run_id="owner")
    expect_equal(
        actual=execute(connection=connection, statement=statement).fetchall(),
        expected=[(42,)],
    )


def test_identifier_torture_and_compiler_determinism() -> None:
    """Compile exotic identifiers deterministically with quoting."""
    values: tuple[str, ...] = (
        "select",
        "table name",
        'a"b',
        "åçčêñt",
        "table.with.dots",
    )
    for value in values:
        statement: Select = Table(name=value).select(
            columns=(Table(name=value).col(name=value),),
        )
        first: str = SQLiteCompiler.compile(statement=statement).sql
        second: str = SQLiteCompiler.compile(statement=statement).sql
        expect_equal(actual=first, expected=second)
        expect_in(member=value.replace('"', '""'), container=first)


def test_database_decode_and_transaction() -> None:
    """Decode a dataclass row inside an explicit transaction."""

    @dataclass(frozen=True, slots=True)
    class Item:
        name: str
        count: int

    table: Table = Table(name="odd table", model=Item)
    connection: Connection = connect(database=":memory:", isolation_level=None)
    database: Database = Database(connection=connection)
    database.execute(statement=table.create())
    database.begin(immediate=True)
    database.execute(statement=table.insert(), parameters=("x", 3))
    database.commit()
    selected: Select = table.select().where(
        predicate=table.col(name="name").eq(value=Param()),
    )
    expect_equal(
        actual=database.decode_one(
            table=table,
            statement=selected,
            parameters=("x",),
        ),
        expected=Item(name="x", count=3),
    )


def test_external_sql_escape_hatch_rejects_empty() -> None:
    """Reject blank external schema SQL at the escape hatch."""
    with pytest.raises(expected_exception=ValueError, match="nonempty"):
        RawSql.from_external_schema(value="   ")


def test_null_predicates_and_transaction_rollback() -> None:
    """Roll back a transaction and compile IS NULL predicates."""

    @dataclass(frozen=True, slots=True)
    class Nullable:
        value: str | None

    def abort_after_insert() -> NoReturn:
        """Insert a row then raise to force the transaction to roll back.

        Raises:
            RuntimeError: When the operation cannot complete.

        """
        database.execute(statement=table.insert(), parameters=(None,))
        msg: str = "rollback"
        raise RuntimeError(msg)

    table: Table = Table(name="nullable", model=Nullable)
    connection: Connection = connect(database=":memory:", isolation_level=None)
    database: Database = Database(connection=connection)
    database.execute(statement=table.create())
    with (
        pytest.raises(expected_exception=RuntimeError),
        database.transaction(immediate=True),
    ):
        abort_after_insert()
    expect_equal(
        actual=database.fetch_all(statement=table.select()),
        expected=[],
    )
    expect_in(
        member="IS NULL",
        container=SQLiteCompiler.compile(
            statement=table.select().where(
                predicate=table.col(name="value").is_null(),
            ),
        ).sql,
    )
