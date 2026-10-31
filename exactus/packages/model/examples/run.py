#!/usr/bin/env python3
# Copyright (c) 2026
"""Demonstrate the structural SQLite model against an in-memory database.

A dataclass derives the ``notes`` table schema, the compiler renders every
statement as inspectable SQL, and the ``Database`` boundary executes the
same structural statements against ``:memory:`` so the demo leaves no files
behind.
"""

from __future__ import annotations

from contextlib import closing, suppress
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from sys import path as sys_path
from sys import stdout
from typing import Annotated, Final, final

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.model import (
    Compilable,
    Database,
    Literal,
    Param,
    PrimaryKey,
    SQLiteCompiler,
    Table,
    connect,
)


@dataclass(frozen=True, slots=True)
class NoteRow:
    """One example note record.

    Attributes:
        note_id: Note identifier.
        title: Note title.
        done: Completion flag.

    """

    note_id: Annotated[str, PrimaryKey()]
    title: str
    done: int


@final
class Constants:
    """Group module-level constants.

    Attributes:
        notes: Grouped module constant.
        open_title: Grouped module constant.

    """

    notes: Final[Table] = Table.from_dataclass(model=NoteRow, name="notes")
    open_title: Final[str] = "ship model migration"


def _show(*, statement: Compilable) -> None:
    """Print one statement's compiled SQL.

    Args:
        statement: Structural statement to compile and display.

    """
    _ = stdout.write(f"{SQLiteCompiler.compile(statement=statement).sql};\n")


def main() -> int:
    """Compile and run a small typed schema, insert, and select.

    Returns:
        ``0`` when the compiled statements execute and decode cleanly.

    """
    notes: Table = Constants.notes
    insert: Compilable = notes.insert()
    select: Compilable = (
        notes.select()
        .where(predicate=notes.col(name="title").eq(value=Param()))
        .order_by(values=(notes.col(name="note_id"),))
        .limit(value=Literal(value=1))
    )
    _show(statement=notes.create())
    _show(statement=notes.create_index(name="notes_done", columns=("done",)))
    _show(statement=insert)
    _show(statement=select)
    with closing(thing=connect(database=":memory:")) as connection:
        database: Database = Database(connection=connection)
        _ = database.execute(statement=notes.create())
        _ = database.execute(
            statement=notes.create_index(name="notes_done", columns=("done",)),
        )
        _ = database.execute(
            statement=insert,
            parameters=("n1", Constants.open_title, 0),
        )
        _ = database.execute(
            statement=insert,
            parameters=("n2", "archive scratch work", 1),
        )
        database.commit()
        row: tuple[object, ...] | None = database.execute(
            statement=select,
            parameters=(Constants.open_title,),
        ).fetchone()
    _ = stdout.write(f"\nfetched: {row}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
