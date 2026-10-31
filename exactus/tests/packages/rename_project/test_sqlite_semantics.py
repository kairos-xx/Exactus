"""SQLite safety tests for the project renamer."""

from __future__ import annotations

from sys import modules

import pytest

pytest.importorskip(modname="tree_sitter")
pytest.importorskip(modname="tree_sitter_language_pack")
from typing import TYPE_CHECKING, Final, final

from exactus.packages.model.sqlite_model import (
    Connection,
    Identifier,
    Literal,
    RawSql,
    Table,
    connect,
    execute,
    pragma,
)
from exactus.tests.packages.rename_project.assertions import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
)
from rename_project import (
    Options,
    Plan,
    RenameError,
    SqliteCellEdit,
    apply_plan,
    build_plan,
    move,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from types import ModuleType


@final
class Constants:
    """Group module-level constants.

    Attributes:
        rp: Grouped module constant.

    """

    rp: Final[ModuleType] = modules["rename_project"]


type Cell = str | int | float | bytes | None


def _ddl(*, connection: Connection, statements: tuple[str, ...]) -> None:
    """Replay fixture schema DDL through the structural boundary.

    Args:
        connection: Fixture database connection.
        statements: External schema statements to apply.

    """
    for value in statements:
        _ = execute(
            connection=connection,
            statement=RawSql.from_external_schema(value=value),
        )


def _project(tmp_path: Path) -> Path:
    """Project.

    Args:
        tmp_path: Per-test temporary directory.

    Returns:
        The resulting value.

    """
    root: Path = tmp_path / "abc_cde"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        data='[project]\nname = "abc-cde"\n',
        encoding="utf-8",
    )
    return root


def _plan(root: Path, *, dotted: bool = True, schema: bool = False) -> Plan:
    """Plan.

    Args:
        root: Value for ``root``.
        dotted: Value for ``dotted``.
        schema: Value for ``schema``.

    Returns:
        The resulting value.

    """
    return build_plan(
        root=root,
        options=Options(
            new_name="foo_bar",
            dotted=dotted,
            rename_root=False,
            use_git=False,
            sqlite_schema=schema,
        ),
    )


def test_sqlite_text_updates_and_blob_is_untouched(tmp_path: Path) -> None:
    """SQLite text updates and blob is untouched.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    database: Path = root / "state.sqlite"
    connection: Connection = connect(database=database)
    _ddl(
        connection=connection,
        statements=(
            "CREATE TABLE settings (id INTEGER PRIMARY KEY, value TEXT, "
            "payload BLOB)",
        ),
    )
    settings: Table = Table(name="settings")
    _ = execute(
        connection=connection,
        statement=settings.insert(
            columns=(settings.col(name="value"), settings.col(name="payload")),
        ),
        parameters=("abc-cde / abc_cde / abc.cde", b"abc_cde"),
    )
    connection.commit()
    connection.close()
    plan: Plan = _plan(root=root)
    expect_equal(actual=len(plan.sqlite_edits), expected=1)
    apply_plan(plan=plan)
    connection = connect(database=database)
    row: tuple[Cell, ...] = execute(
        connection=connection,
        statement=settings.select(
            columns=(settings.col(name="value"), settings.col(name="payload")),
        ),
    ).fetchone()
    integrity: tuple[Cell, ...] = execute(
        connection=connection,
        statement=pragma(name="integrity_check"),
    ).fetchone()
    connection.close()
    expect_equal(
        actual=row,
        expected=("foo-bar / foo_bar / foo.bar", b"abc_cde"),
    )
    expect_equal(actual=integrity, expected=("ok",))


def test_sqlite_without_rowid_composite_primary_key(tmp_path: Path) -> None:
    """SQLite without rowid composite primary key.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    database: Path = root / "state.db"
    connection: Connection = connect(database=database)
    _ddl(
        connection=connection,
        statements=(
            "CREATE TABLE labels (scope TEXT, ident INTEGER, value TEXT, "
            "PRIMARY KEY(scope, ident)) WITHOUT ROWID",
        ),
    )
    labels: Table = Table(name="labels")
    _ = execute(
        connection=connection,
        statement=labels.insert(
            columns=(
                labels.col(name="scope"),
                labels.col(name="ident"),
                labels.col(name="value"),
            ),
        ),
        parameters=("scope", 7, "abc_cde"),
    )
    connection.commit()
    connection.close()
    plan: Plan = _plan(root=root)
    expect_equal(actual=len(plan.sqlite_edits), expected=1)
    edit: SqliteCellEdit = plan.sqlite_edits[0]
    expect_equal(actual=edit.locator_columns, expected=("scope", "ident"))
    apply_plan(plan=plan)
    connection = connect(database=database)
    value: tuple[Cell, ...] = execute(
        connection=connection,
        statement=labels.select(columns=(labels.col(name="value"),)),
    ).fetchone()
    connection.close()
    expect_equal(actual=value, expected=("foo_bar",))


def test_sqlite_generated_column_is_not_written(tmp_path: Path) -> None:
    """SQLite generated column is not written.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    database: Path = root / "state.sqlite3"
    connection: Connection = connect(database=database)
    _ddl(
        connection=connection,
        statements=(
            "CREATE TABLE names (value TEXT, generated TEXT GENERATED "
            "ALWAYS AS (value) STORED)",
        ),
    )
    names: Table = Table(name="names")
    _ = execute(
        connection=connection,
        statement=names.insert(columns=(names.col(name="value"),)),
        parameters=("abc_cde",),
    )
    connection.commit()
    connection.close()
    plan: Plan = _plan(root=root)
    expect_equal(
        actual=[edit.column for edit in plan.sqlite_edits],
        expected=["value"],
    )
    apply_plan(plan=plan)
    connection = connect(database=database)
    row: tuple[Cell, ...] = execute(
        connection=connection,
        statement=names.select(
            columns=(names.col(name="value"), names.col(name="generated")),
        ),
    ).fetchone()
    connection.close()
    expect_equal(actual=row, expected=("foo_bar", "foo_bar"))


def test_sqlite_schema_match_is_guarded_not_rewritten(tmp_path: Path) -> None:
    """SQLite schema match is guarded not rewritten.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    database: Path = root / "state.sqlite"
    connection: Connection = connect(database=database)
    _ddl(
        connection=connection,
        statements=("CREATE TABLE abc_cde (id INTEGER PRIMARY KEY)",),
    )
    connection.commit()
    connection.close()
    plan: Plan = _plan(root=root)
    expect_false(condition=bool(plan.sqlite_edits))
    expect_true(
        condition=any(
            (
                reason == "SQLite schema reference"
                for _path, _line, _text, reason in plan.guarded
            ),
        ),
    )


def test_sqlite_wal_database_is_updated_consistently(tmp_path: Path) -> None:
    """SQLite wal database is updated consistently.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    database: Path = root / "state.sqlite"
    connection: Connection = connect(database=database)
    _ = execute(
        connection=connection,
        statement=pragma(name="journal_mode", value=Literal(value="WAL")),
    ).fetchone()
    _ddl(
        connection=connection,
        statements=("CREATE TABLE values_table (value TEXT)",),
    )
    values_table: Table = Table(name="values_table")
    _ = execute(
        connection=connection,
        statement=values_table.insert(
            columns=(values_table.col(name="value"),),
        ),
        parameters=("abc_cde",),
    )
    connection.commit()
    connection.close()
    plan: Plan = _plan(root=root)
    apply_plan(plan=plan)
    connection = connect(database=database)
    value: tuple[Cell, ...] = execute(
        connection=connection,
        statement=values_table.select(
            columns=(values_table.col(name="value"),),
        ),
    ).fetchone()
    integrity: tuple[Cell, ...] = execute(
        connection=connection,
        statement=pragma(name="integrity_check"),
    ).fetchone()
    connection.close()
    expect_equal(actual=value, expected=("foo_bar",))
    expect_equal(actual=integrity, expected=("ok",))


def test_sqlite_is_restored_when_later_filesystem_step_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SQLite is restored when later filesystem step fails.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    root: Path = _project(tmp_path=tmp_path)
    database: Path = root / "state.sqlite"
    connection: Connection = connect(database=database)
    _ddl(
        connection=connection,
        statements=("CREATE TABLE settings (value TEXT)",),
    )
    settings: Table = Table(name="settings")
    _ = execute(
        connection=connection,
        statement=settings.insert(columns=(settings.col(name="value"),)),
        parameters=("abc_cde",),
    )
    connection.commit()
    connection.close()
    (root / "abc_cde.txt").write_text(data="unrelated", encoding="utf-8")
    plan: Plan = _plan(root=root)
    original_move: Callable[..., None] = move

    def fail_move(*, source: Path, destination: Path) -> None:
        """Fail move.

        Args:
            source: Value for ``source``.
            destination: Value for ``destination``.

        Raises:
            OSError: When the operation cannot complete.

        """
        _ = source
        _ = destination
        msg: str = "injected move failure"
        raise OSError(msg)

    monkeypatch.setattr(target=Constants.rp, name="move", value=fail_move)
    with pytest.raises(expected_exception=RenameError):
        apply_plan(plan=plan)
    monkeypatch.setattr(target=Constants.rp, name="move", value=original_move)
    connection = connect(database=database)
    value: tuple[Cell, ...] = execute(
        connection=connection,
        statement=settings.select(columns=(settings.col(name="value"),)),
    ).fetchone()
    integrity: tuple[Cell, ...] = execute(
        connection=connection,
        statement=pragma(name="integrity_check"),
    ).fetchone()
    connection.close()
    expect_equal(actual=value, expected=("abc_cde",))
    expect_equal(actual=integrity, expected=("ok",))


def test_sqlite_schema_table_column_dependencies_are_propagated(
    tmp_path: Path,
) -> None:
    """SQLite schema table column dependencies are propagated.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    database: Path = root / "state.sqlite"
    connection: Connection = connect(database=database)
    _ = execute(
        connection=connection,
        statement=pragma(name="foreign_keys", value=Literal(value="ON")),
    )
    _ddl(
        connection=connection,
        statements=(
            "CREATE TABLE abc_cde (abc_cde INTEGER PRIMARY KEY, value TEXT)",
            "CREATE TABLE child (id INTEGER PRIMARY KEY, parent INTEGER "
            "REFERENCES abc_cde(abc_cde))",
            "CREATE INDEX linked_idx ON abc_cde(abc_cde)",
            "CREATE VIEW linked_view AS SELECT abc_cde FROM abc_cde",
            "CREATE TRIGGER linked_trigger AFTER UPDATE OF abc_cde ON "
            "abc_cde BEGIN UPDATE child SET parent=NEW.abc_cde WHERE "
            "parent=OLD.abc_cde; END",
        ),
    )
    abc_cde: Table = Table(name="abc_cde")
    child: Table = Table(name="child")
    _ = execute(
        connection=connection,
        statement=abc_cde.insert(
            columns=(abc_cde.col(name="abc_cde"), abc_cde.col(name="value")),
        ),
        parameters=(1, "abc_cde"),
    )
    _ = execute(
        connection=connection,
        statement=child.insert(columns=(child.col(name="parent"),)),
        parameters=(1,),
    )
    connection.commit()
    connection.close()
    plan: Plan = _plan(root=root, schema=True)
    planned: set[tuple[str, str, str]] = {
        (edit.kind, edit.old, edit.new) for edit in plan.sqlite_schema_edits
    }
    expect_true(
        condition=planned
        >= {("table", "abc_cde", "foo_bar"), ("column", "abc_cde", "foo_bar")},
    )
    apply_plan(plan=plan)
    connection = connect(database=database)
    schema_table: Table = Table(name="sqlite_schema")
    schema: str = "\n".join(
        str(object=row[0])
        for row in execute(
            connection=connection,
            statement=schema_table.select(
                columns=(schema_table.col(name="sql"),),
            ).where(predicate=schema_table.col(name="sql").is_not_null()),
        ).fetchall()
    )
    foreign_keys: list[tuple[Cell, ...]] = execute(
        connection=connection,
        statement=pragma(name="foreign_key_check"),
    ).fetchall()
    integrity: tuple[Cell, ...] = execute(
        connection=connection,
        statement=pragma(name="integrity_check"),
    ).fetchone()
    foo_bar: Table = Table(name="foo_bar")
    value: tuple[Cell, ...] = execute(
        connection=connection,
        statement=foo_bar.select(columns=(foo_bar.col(name="value"),)),
    ).fetchone()
    connection.close()
    expect_in(member='"foo_bar"', container=schema)
    expect_equal(actual=foreign_keys, expected=[])
    expect_equal(actual=integrity, expected=("ok",))
    expect_equal(actual=value, expected=("foo_bar",))


def test_sqlite_schema_is_opt_in(tmp_path: Path) -> None:
    """SQLite schema is opt in.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    database: Path = root / "state.sqlite"
    connection: Connection = connect(database=database)
    _ddl(
        connection=connection,
        statements=("CREATE TABLE abc_cde (abc_cde TEXT)",),
    )
    connection.commit()
    connection.close()
    plan: Plan = _plan(root=root)
    expect_equal(actual=plan.sqlite_schema_edits, expected=[])


def test_sqlite_schema_collision_is_guarded(tmp_path: Path) -> None:
    """SQLite schema collision is guarded.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    database: Path = root / "state.sqlite"
    connection: Connection = connect(database=database)
    _ddl(
        connection=connection,
        statements=(
            "CREATE TABLE abc_cde(id INTEGER)",
            "CREATE TABLE foo_bar(id INTEGER)",
        ),
    )
    connection.commit()
    connection.close()
    plan: Plan = _plan(root=root, schema=True)
    expect_false(
        condition=any(
            edit.kind == "table" and edit.old == "abc_cde"
            for edit in plan.sqlite_schema_edits
        ),
    )
    expect_true(
        condition=any(
            (
                reason == "SQLite table rename collision"
                for _path, _line, _text, reason in plan.guarded
            ),
        ),
    )


def test_sqlite_ambiguous_column_rename_rolls_back(tmp_path: Path) -> None:
    """SQLite ambiguous column rename rolls back.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    database: Path = root / "state.sqlite"
    connection: Connection = connect(database=database)
    _ddl(
        connection=connection,
        statements=(
            "CREATE TABLE source(abc_cde INTEGER)",
            "CREATE TABLE other(foo_bar INTEGER)",
            "CREATE VIEW linked AS SELECT abc_cde FROM source JOIN other",
        ),
    )
    connection.commit()
    connection.close()
    plan: Plan = _plan(root=root, schema=True)
    with pytest.raises(expected_exception=RenameError):
        apply_plan(plan=plan)
    connection = connect(database=database)
    columns: list[tuple[Cell, ...]] = execute(
        connection=connection,
        statement=pragma(name="table_xinfo", call=Identifier(value="source")),
    ).fetchall()
    integrity: tuple[Cell, ...] = execute(
        connection=connection,
        statement=pragma(name="integrity_check"),
    ).fetchone()
    connection.close()
    expect_equal(
        actual=[str(object=row[1]) for row in columns],
        expected=["abc_cde"],
    )
    expect_equal(actual=integrity, expected=("ok",))


def test_sqlite_schema_restored_after_later_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SQLite schema restored after later failure.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    root: Path = _project(tmp_path=tmp_path)
    database: Path = root / "state.sqlite"
    connection: Connection = connect(database=database)
    _ddl(
        connection=connection,
        statements=("CREATE TABLE abc_cde(id INTEGER)",),
    )
    connection.commit()
    connection.close()
    (root / "abc_cde.txt").write_text(data="unrelated", encoding="utf-8")
    plan: Plan = _plan(root=root, schema=True)

    def fail_move(*, source: Path, destination: Path) -> None:
        """Fail move.

        Args:
            source: Value for ``source``.
            destination: Value for ``destination``.

        Raises:
            OSError: When the operation cannot complete.

        """
        _ = source
        _ = destination
        msg: str = "injected move failure"
        raise OSError(msg)

    monkeypatch.setattr(target=Constants.rp, name="move", value=fail_move)
    with pytest.raises(expected_exception=RenameError):
        apply_plan(plan=plan)
    connection = connect(database=database)
    schema_table: Table = Table(name="sqlite_schema")
    table: tuple[Cell, ...] = execute(
        connection=connection,
        statement=schema_table.select(
            columns=(schema_table.col(name="name"),),
        ).where(
            predicate=schema_table.col(name="type").eq(
                value=Literal(value="table"),
            ),
        ),
    ).fetchone()
    integrity: tuple[Cell, ...] = execute(
        connection=connection,
        statement=pragma(name="integrity_check"),
    ).fetchone()
    connection.close()
    expect_equal(actual=table, expected=("abc_cde",))
    expect_equal(actual=integrity, expected=("ok",))


def test_sqlite_named_index_is_recreated_with_new_name(tmp_path: Path) -> None:
    """SQLite named index is recreated with new name.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    database: Path = root / "state.sqlite"
    connection: Connection = connect(database=database)
    _ddl(
        connection=connection,
        statements=(
            "CREATE TABLE records(value INTEGER)",
            "CREATE INDEX abc_cde ON records(value)",
        ),
    )
    connection.commit()
    connection.close()
    plan: Plan = _plan(root=root, schema=True)
    expect_true(
        condition=any(
            edit.kind == "index" and edit.old == "abc_cde"
            for edit in plan.sqlite_schema_edits
        ),
    )
    apply_plan(plan=plan)
    connection = connect(database=database)
    schema_table: Table = Table(name="sqlite_schema")
    index: tuple[Cell, ...] = execute(
        connection=connection,
        statement=schema_table.select(
            columns=(schema_table.col(name="name"),),
        ).where(
            predicate=schema_table.col(name="type").eq(
                value=Literal(value="index"),
            ),
        ),
    ).fetchone()
    integrity: tuple[Cell, ...] = execute(
        connection=connection,
        statement=pragma(name="integrity_check"),
    ).fetchone()
    connection.close()
    expect_equal(actual=index, expected=("foo_bar",))
    expect_equal(actual=integrity, expected=("ok",))
