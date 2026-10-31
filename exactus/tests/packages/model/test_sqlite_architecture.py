"""Architectural regression checks for application SQLite access."""

from __future__ import annotations

from ast import Attribute, Call, Constant, Name, parse, walk
from pathlib import Path
from re import IGNORECASE
from re import compile as compile_pattern
from typing import Final, final

from exactus.tests.common.support import expect_equal, expect_true


@final
class Constants:
    """Group module-level constants.

    Attributes:
        application: Grouped module constant.
        sql_pattern: Grouped module constant.

    """

    application: Final[tuple[str, ...]] = (
        "exactus/__main__.py",
        "exactus/tools/common/pipeline_supervisor.py",
        "exactus/tools/common/registry.py",
        "exactus/packages/model/pipeline_queries.py",
        "exactus/packages/model/registry_queries.py",
        "exactus/packages/rename_project/rename_project.py",
    )
    sql_pattern: Final = compile_pattern(
        pattern=(
            "^\\s*(?:SELECT\\s+.+\\s+FROM\\s+|INSERT\\s+(?:OR\\s+REPLACE\\s+)?"
            "INTO\\s+|UPDATE\\s+.+\\s+SET\\s+|DELETE\\s+FROM\\s+|CREATE\\s+TAB"
            "LE\\s+|ALTER\\s+TABLE\\s+|DROP\\s+(?:TABLE|INDEX|VIEW|TRIGGER)\\s"
            "+|PRAGMA\\s+\\w+|BEGIN(?:\\s+IMMEDIATE)?\\s*$)"
        ),
        flags=IGNORECASE,
    )


def test_application_does_not_bypass_database_layer() -> None:
    """Keep direct sqlite3 execution out of application modules."""
    for path in (
        Path(__file__).resolve().parents[4] / name
        for name in Constants.application
    ):
        violations: list[int] = [
            node.lineno
            for node in walk(
                node=parse(source=path.read_text(encoding="utf-8")),
            )
            if isinstance(node, Call)
            and isinstance(node.func, Attribute)
            and (node.func.attr in {"execute", "executemany", "executescript"})
            and isinstance(node.func.value, Name)
            and (node.func.value.id in {"connection", "conn"})
        ]
        expect_true(
            condition=not violations,
            message=f"{path}: direct sqlite3 execution at {violations}",
        )


def test_application_has_no_authored_sql_literals() -> None:
    """Prevent SQL grammar text from re-entering production modules."""
    offenders: list[tuple[str, int, str]] = []
    for path in (
        Path(__file__).resolve().parents[4] / name
        for name in Constants.application
    ):
        offenders.extend(
            (path.name, node.lineno, node.value[:100])
            for node in walk(
                node=parse(source=path.read_text(encoding="utf-8")),
            )
            if isinstance(node, Constant)
            and isinstance(node.value, str)
            and Constants.sql_pattern.search(string=node.value)
        )
    expect_equal(actual=offenders, expected=[])


def test_raw_sql_escape_hatch_is_allowlisted() -> None:
    """Permit external schema recreation at exactly one reviewed call site."""
    calls: list[str] = []
    for path in (
        Path(__file__).resolve().parents[4] / name
        for name in Constants.application
    ):
        calls.extend(
            path.name
            for node in walk(
                node=parse(source=path.read_text(encoding="utf-8")),
            )
            if isinstance(node, Call)
            and isinstance(node.func, Attribute)
            and (node.func.attr == "from_external_schema")
            and isinstance(node.func.value, Name)
            and (node.func.value.id == "RawSql")
        )
    expect_equal(actual=calls, expected=["rename_project.py"])


def test_application_never_compiles_sql_itself() -> None:
    """Keep compiler invocation inside the SQLite boundary."""
    violations: list[tuple[str, int]] = []
    for path in (
        Path(__file__).resolve().parents[4] / name
        for name in Constants.application
    ):
        violations.extend(
            (path.name, node.lineno)
            for node in walk(
                node=parse(source=path.read_text(encoding="utf-8")),
            )
            if isinstance(node, Call)
            and isinstance(node.func, Attribute)
            and (node.func.attr == "compile")
            and isinstance(node.func.value, Name)
            and (node.func.value.id in {"SQLiteCompiler", "statement"})
        )
    expect_equal(actual=violations, expected=[])
