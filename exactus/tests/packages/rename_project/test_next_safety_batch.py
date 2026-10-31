"""Regression tests for SQL, Unicode geometry, golden projects, rollback.

Covers SQL identifiers, UTF-8 column geometry, golden-project rewrites, and
transactional rollback.
"""

from __future__ import annotations

from sys import modules
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.packages.model.sqlite_model import (
    ColumnDefinition,
    Literal,
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
    FileEdit,
    Options,
    Plan,
    RenameError,
    apply_plan,
    build_plan,
    move,
    python_safe_dotted_spans,
    span_contained,
    sql_safe_dotted_spans,
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


def _table(*, name: str, columns: tuple[tuple[str, bool], ...]) -> Table:
    """Build typed fixture-table metadata.

    Args:
        name: Table name.
        columns: ``(column, nullable)`` pairs.

    Returns:
        The table metadata.

    """
    return Table(
        name=name,
        definitions=tuple(
            ColumnDefinition(
                name=column,
                affinity="TEXT",
                nullable=nullable,
                primary_key=False,
            )
            for column, nullable in columns
        ),
    )


def _options(*, new_name: str = "foo_bar") -> Options:
    """Options.

    Args:
        new_name: Value for ``new_name``.

    Returns:
        The resulting value.

    """
    return Options(
        new_name=new_name,
        old_names=("abc_cde",),
        rename_root=False,
        use_git=False,
        dotted=True,
        sqlite_schema=True,
        github=False,
    )


def test_python_ast_utf8_columns_are_character_columns() -> None:
    """Python AST UTF-8 columns are character columns."""
    text: str = 'x = "é"; y = "abc.cde"\n'
    spans: dict[int, tuple[tuple[int, int], ...]] = python_safe_dotted_spans(
        text=text,
    )
    start: int = text.index("abc.cde")
    expect_true(
        condition=span_contained(
            span=(start, start + len("abc.cde")),
            containers=spans[1],
        ),
    )


def test_sql_dotted_identifier_excludes_literal_and_comments() -> None:
    """SQL dotted identifier excludes literal and comments."""
    text: str = (
        "SELECT abc.cde FROM abc_cde AS abc; SELECT 'abc.cde'; -- abc.cde\n"
    )
    spans: dict[int, tuple[tuple[int, int], ...]] = sql_safe_dotted_spans(
        text=text,
    )
    first: int = text.index("abc.cde")
    literal: int = text.index("abc.cde", first + 1)
    comment: int = text.index("abc.cde", literal + 1)
    expect_true(
        condition=span_contained(span=(first, first + 7), containers=spans[1]),
    )
    expect_false(
        condition=span_contained(
            span=(literal, literal + 7),
            containers=spans[1],
        ),
    )
    expect_false(
        condition=span_contained(
            span=(comment, comment + 7),
            containers=spans[1],
        ),
    )


def test_sql_file_rewrites_identifier_not_dotted_literal(
    tmp_path: Path,
) -> None:
    """SQL file rewrites identifier not dotted literal.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "abc_cde"
    root.mkdir()
    sql: Path = root / "schema.sql"
    sql.write_text(
        data="SELECT abc.cde FROM abc_cde AS abc; SELECT 'abc.cde';\n",
        encoding="utf-8",
    )
    plan: Plan = build_plan(root=root, options=_options())
    edit: FileEdit = next(item for item in plan.edits if item.path == sql)
    after: str = edit.after.decode()
    expect_in(member="foo_bar", container=after)
    expect_in(member="foo.bar", container=after)
    expect_in(member="'abc.cde'", container=after)


def test_golden_project_updates_files_and_sqlite(tmp_path: Path) -> None:
    """Golden project updates files and SQLite.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "abc_cde"
    root.mkdir()
    (root / "NOTES.txt").write_text(data="Abc Cde\n", encoding="utf-8")
    (root / "queries.sql").write_text(
        data="SELECT abc_cde FROM abc_cde;\n",
        encoding="utf-8",
    )
    database: Path = root / "state.sqlite"
    fixture: Table = _table(name="abc_cde", columns=(("abc_cde", False),))
    with connect(database=database) as connection:
        _ = execute(connection=connection, statement=fixture.create())
        _ = execute(
            connection=connection,
            statement=fixture.insert(),
            parameters=("abc_cde",),
        )
    plan: Plan = build_plan(root=root, options=_options())
    apply_plan(plan=plan)
    expect_equal(
        actual=(root / "NOTES.txt").read_text(encoding="utf-8"),
        expected="Foo Bar\n",
    )
    expect_in(
        member="foo_bar",
        container=(root / "queries.sql").read_text(encoding="utf-8"),
    )
    schema: Table = Table(name="sqlite_schema")
    renamed: Table = Table(name="foo_bar")
    with connect(database=database) as connection:
        names: set[str] = {
            str(object=row[0])
            for row in execute(
                connection=connection,
                statement=schema.select(
                    columns=(schema.col(name="name"),),
                ).where(
                    predicate=schema.col(name="type").eq(
                        value=Literal(value="table"),
                    ),
                ),
            )
        }
        expect_in(member="foo_bar", container=names)
        expect_equal(
            actual=execute(
                connection=connection,
                statement=renamed.select(
                    columns=(renamed.col(name="foo_bar"),),
                ),
            ).fetchone(),
            expected=("foo_bar",),
        )
        integrity: tuple[Cell, ...] = execute(
            connection=connection,
            statement=pragma(name="integrity_check"),
        ).fetchone()
        expect_equal(actual=integrity, expected=("ok",))


def test_failure_after_database_mutation_restores_everything(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failure after database mutation restores everything.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    root: Path = tmp_path / "abc_cde"
    root.mkdir()
    note: Path = root / "abc_cde.txt"
    note.write_text(data="abc_cde\n", encoding="utf-8")
    database: Path = root / "state.sqlite"
    fixture: Table = _table(name="abc_cde", columns=(("value", True),))
    with connect(database=database) as connection:
        _ = execute(connection=connection, statement=fixture.create())
        _ = execute(
            connection=connection,
            statement=fixture.insert(),
            parameters=("abc_cde",),
        )
    plan: Plan = build_plan(root=root, options=_options())
    original_move: Callable[..., None] = move

    def fail_move(*, source: Path, destination: Path) -> None:
        """Fail move.

        Args:
            source: Value for ``source``.
            destination: Value for ``destination``.

        Raises:
            OSError: When the operation cannot complete.

        """
        if source == note:
            msg: str = "injected move failure"
            raise OSError(msg)
        original_move(source=source, destination=destination)

    monkeypatch.setattr(target=Constants.rp, name="move", value=fail_move)
    with pytest.raises(expected_exception=RenameError):
        apply_plan(plan=plan)
    expect_true(condition=note.exists())
    expect_equal(actual=note.read_text(encoding="utf-8"), expected="abc_cde\n")
    with connect(database=database) as connection:
        expect_equal(
            actual=execute(
                connection=connection,
                statement=fixture.select(columns=(fixture.col(name="value"),)),
            ).fetchone(),
            expected=("abc_cde",),
        )
        integrity: tuple[Cell, ...] = execute(
            connection=connection,
            statement=pragma(name="integrity_check"),
        ).fetchone()
        expect_equal(actual=integrity, expected=("ok",))


def test_application_sql_reference_inventory(tmp_path: Path) -> None:
    """Application SQL reference inventory.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "abc_cde"
    root.mkdir()
    app: Path = root / "app.py"
    app.write_text(
        data='QUERY = "SELECT abc_cde FROM abc_cde"\n',
        encoding="utf-8",
    )
    database: Path = root / "state.sqlite"
    with connect(database=database) as connection:
        _ = execute(
            connection=connection,
            statement=_table(
                name="abc_cde",
                columns=(("abc_cde", True),),
            ).create(),
        )
    plan: Plan = build_plan(root=root, options=_options())
    found: set[tuple[Path, str, str]] = {
        (ref.path, ref.symbol, ref.kind) for ref in plan.sql_references
    }
    expect_in(member=(app, "abc_cde", "table"), container=found)
    expect_in(member=(app, "abc_cde", "column"), container=found)
