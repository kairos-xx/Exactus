"""Hardening and torture tests for the structural SQLite layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, NoReturn, cast

import pytest

from exactus.packages.model.sqlite_model import (
    BinaryExpression,
    Codec,
    Column,
    Connection,
    ConstraintError,
    Database,
    Identifier,
    Literal,
    Param,
    ParameterError,
    PrimaryKey,
    RawSql,
    SchemaReport,
    Select,
    SQLiteCompiler,
    Table,
    TraceEvent,
    UnsupportedFeatureError,
    alter_rename_column,
    alter_rename_table,
    command,
    connect,
    drop,
    function,
    pragma,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_not_in,
    expect_true,
)


class _Lcg:
    """Deterministic linear congruential generator for fuzz inputs."""

    def __init__(self, *, seed: int) -> None:
        """Store the generator seed.

        Args:
            seed: Initial generator state.

        """
        self._state = seed

    def next(self, *, limit: int) -> int:
        """Advance the generator and return a value below ``limit``.

        Args:
            limit: Exclusive upper bound for the produced value.

        Returns:
            A deterministic pseudo-random integer.

        """
        self._state = (
            self._state * 6364136223846793005 + 1442695040888963407
        ) % 2**64
        return self._state % limit


def test_schema_round_trip_and_drift_detection() -> None:
    """Verify a freshly created table matches its dataclass schema."""

    @dataclass(frozen=True, slots=True)
    class Row:
        key: Annotated[str, PrimaryKey()]
        count: int
        note: str | None

    table: Table = Table(name="schema torture", model=Row)
    database: Database = Database(connection=connect(database=":memory:"))
    database.execute(statement=table.create())
    report: SchemaReport = database.verify_schema(table=table)
    expect_true(condition=report.matches)
    expect_equal(actual=report.differences, expected=())


def test_cardinality_scalar_and_batch_operations() -> None:
    """Exercise scalar lookups, batch inserts, and arity errors."""

    @dataclass(frozen=True, slots=True)
    class Row:
        key: Annotated[str, PrimaryKey()]
        value: int

    table: Table = Table(name="batch", model=Row)
    database: Database = Database(connection=connect(database=":memory:"))
    database.execute(statement=table.create())
    database.execute_many(
        statement=table.insert(),
        parameter_sets=(("a", 1), ("b", 2), ("c", 3)),
    )
    selected: Select = table.select(columns=(table.col(name="value"),)).where(
        predicate=table.col(name="key").eq(value=Param()),
    )
    expect_equal(
        actual=database.scalar(statement=selected, parameters=("b",)),
        expected=2,
    )
    with pytest.raises(expected_exception=ParameterError):
        database.fetch_optional(statement=table.select())
    with pytest.raises(expected_exception=ParameterError):
        database.execute_many(
            statement=table.insert(),
            parameter_sets=(("bad",),),
        )


def test_nested_transactions_use_savepoints() -> None:
    """Roll back only the inner unit when a nested transaction fails."""

    @dataclass(frozen=True, slots=True)
    class Row:
        value: str

    def abort_inner() -> NoReturn:
        """Insert inside the savepoint then raise to roll it back.

        Raises:
            RuntimeError: When the operation cannot complete.

        """
        database.execute(statement=table.insert(), parameters=("inner",))
        msg: str = "rollback inner"
        raise RuntimeError(msg)

    table: Table = Table(name="nested", model=Row)
    connection: Connection = connect(database=":memory:", isolation_level=None)
    database: Database = Database(connection=connection)
    database.execute(statement=table.create())
    with database.transaction():
        database.execute(statement=table.insert(), parameters=("outer",))
        with (
            pytest.raises(expected_exception=RuntimeError),
            database.transaction(),
        ):
            abort_inner()
        database.execute(statement=table.insert(), parameters=("outer2",))
    expect_equal(
        actual=database.fetch_many(statement=table.select()),
        expected=[("outer",), ("outer2",)],
    )


def test_trace_never_contains_parameter_values() -> None:
    """Report only parameter counts, never values, in trace events."""

    @dataclass(frozen=True, slots=True)
    class Row:
        secret: str

    events: list[TraceEvent] = []
    table: Table = Table(name="trace", model=Row)
    database: Database = Database(
        connection=connect(database=":memory:"),
        trace=events.append,
    )
    database.execute(statement=table.create())
    database.execute(statement=table.insert(), parameters=("TOP-SECRET",))
    expect_equal(actual=events[-1].parameter_count, expected=1)
    expect_not_in(member="TOP-SECRET", container=repr(events))


def test_constraint_translation_preserves_cause() -> None:
    """Wrap sqlite3 integrity failures and keep the original cause."""

    @dataclass(frozen=True, slots=True)
    class Row:
        key: Annotated[str, PrimaryKey()]

    table: Table = Table(name="constraints", model=Row)
    database: Database = Database(connection=connect(database=":memory:"))
    database.execute(statement=table.create())
    database.execute(statement=table.insert(), parameters=("same",))
    with pytest.raises(expected_exception=ConstraintError) as caught:
        database.execute(statement=table.insert(), parameters=("same",))
    expect_true(condition=caught.value.__cause__ is not None)


def test_codec_is_explicit_and_bidirectional() -> None:
    """Round-trip a value through an explicit codec pair."""
    codec: Codec[int, str] = Codec[int, str](encode=str, decode=int)
    expect_equal(actual=codec.encode(42), expected="42")
    expect_equal(actual=codec.decode("42"), expected=42)


def test_expression_boolean_evaluation_is_rejected() -> None:
    """Forbid Python truthiness checks on SQL expressions."""
    expression: BinaryExpression = (
        Table(name="x").col(name="y").eq(value=Literal(value=1))
    )
    with pytest.raises(expected_exception=TypeError):
        bool(expression)


def test_empty_in_has_deterministic_sqlite_semantics() -> None:
    """Compile an empty IN list to a portable false predicate."""

    @dataclass(frozen=True, slots=True)
    class Row:
        value: int

    table: Table = Table(name="empty_in", model=Row)
    database: Database = Database(connection=connect(database=":memory:"))
    database.execute(statement=table.create())
    database.execute(statement=table.insert(), parameters=(1,))
    selected: Select = table.select().where(
        predicate=table.col(name="value").in_(values=()),
    )
    expect_equal(actual=database.fetch_many(statement=selected), expected=[])


def test_randomized_identifier_and_value_round_trip() -> None:
    """Round-trip exotic identifiers and values through the full stack."""
    fuzz: _Lcg = _Lcg(seed=84721)
    alphabet: str = 'abc XYZ_-.åçčêñt"select'
    for index in range(75):
        name: str = "t_" + "".join(
            alphabet[fuzz.next(limit=len(alphabet))]
            for _ in range(1 + fuzz.next(limit=18))
        )
        if "\x00" in name:
            continue

        @dataclass(frozen=True, slots=True)
        class Row:
            key: str
            number: int
            note: str | None

        table: Table = Table(name=name, model=Row)
        database: Database = Database(connection=connect(database=":memory:"))
        database.execute(statement=table.create())
        values: tuple[str, int, str | None] = (
            f"k-{index}-'\"",
            fuzz.next(limit=200001) - 100000,
            None if index % 3 == 0 else f"v-{index}",
        )
        database.execute(statement=table.insert(), parameters=values)
        expect_equal(
            actual=database.decode_optional(
                table=table,
                statement=table.select(),
            ),
            expected=Row(*values),
        )
        first: str = SQLiteCompiler.compile(statement=table.select()).sql
        second: str = SQLiteCompiler.compile(statement=table.select()).sql
        expect_equal(actual=first, expected=second)


def test_structural_ddl_commands_and_error_paths() -> None:
    """Drive DDL helpers, fixed commands, and their error paths."""
    connection: Connection = connect(database=":memory:", isolation_level=None)
    database: Database = Database(connection=connection)
    Table(name="old name")
    database.execute(
        statement=RawSql.from_external_schema(
            value='CREATE TABLE "old name" ("old column" TEXT)',
        ),
    )
    database.execute(
        statement=alter_rename_column(
            table="old name",
            old="old column",
            new="new column",
        ),
    )
    database.execute(
        statement=alter_rename_table(table="old name", new="new name"),
    )
    expect_equal(
        actual=database.fetch_many(
            statement=Table(name="new name").select(
                columns=(Column(name="new column"),),
            ),
        ),
        expected=[],
    )
    expect_true(
        condition=SQLiteCompiler.compile(
            statement=pragma(name="foreign_keys", value=Literal(value=True)),
        ).sql.startswith("PRAGMA"),
    )
    expect_equal(
        actual=SQLiteCompiler.compile(statement=command(name="vacuum")).sql,
        expected="VACUUM",
    )
    expect_true(
        condition=SQLiteCompiler.compile(
            statement=drop(kind="view", name="v"),
        ).sql.startswith("DROP VIEW"),
    )
    with pytest.raises(expected_exception=UnsupportedFeatureError):
        function(name="random", arguments=())
    with pytest.raises(
        expected_exception=ValueError,
        match="Unsupported SQLite command",
    ):
        command(name="unknown")
    with pytest.raises(expected_exception=ValueError, match="nonempty"):
        Identifier(value="")


def test_decode_many_exactly_one_and_schema_drift() -> None:
    """Decode rows, require exactly one, and report schema drift."""

    @dataclass(frozen=True, slots=True)
    class Row:
        key: str
        value: int

    table: Table = Table(name="decode", model=Row)
    database: Database = Database(connection=connect(database=":memory:"))
    database.execute(statement=table.create())
    database.execute_many(
        statement=table.insert(),
        parameter_sets=(("a", 1), ("b", 2)),
    )
    expect_equal(
        actual=cast(
            typ="list[Row]",
            val=database.decode_many(table=table, statement=table.select()),
        ),
        expected=[Row(key="a", value=1), Row(key="b", value=2)],
    )
    with pytest.raises(expected_exception=ParameterError):
        database.fetch_exactly_one(
            statement=table.select().where(
                predicate=table.col(name="key").eq(
                    value=Literal(value="missing"),
                ),
            ),
        )
    drift_database: Database = Database(
        connection=connect(database=":memory:"),
    )
    drift_database.execute(
        statement=RawSql.from_external_schema(
            value='CREATE TABLE "decode" ("key" TEXT, "extra" TEXT)',
        ),
    )
    report: SchemaReport = drift_database.verify_schema(table=table)
    expect_false(condition=report.matches)
    expect_true(
        condition={item.kind for item in report.differences}
        >= {"missing_column", "extra_column"},
    )
