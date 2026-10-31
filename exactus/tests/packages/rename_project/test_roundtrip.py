"""Renaming forth and back reproduces the original project exactly.

Markdown headings are normalized to Title Case by design, so the fixture
uses a Title Case heading; every other spelling must survive unchanged.
"""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING, Final, final

from exactus.packages.model.sqlite_model import (
    ColumnDefinition,
    Table,
    connect,
    execute,
)
from exactus.tests.packages.rename_project.assertions import expect_equal
from rename_project import main

if TYPE_CHECKING:
    from pathlib import Path


@final
class Constants:
    """Group module-level constants.

    Attributes:
        old: Grouped module constant.
        new: Grouped module constant.
        files: Grouped module constant.

    """

    old: Final[str] = "abc_cde"
    new: Final[str] = "foo_bar"
    files: Final[dict[str, str]] = {
        "pyproject.toml": '[project]\nname = "abc-cde"\n',
        "README.md": (
            dedent(
                text=(
                    "    # Abc Cde\n    \n    Install `abc-cde`, then run "
                    "abc_cde.\n    AbcCde is the class.\n    "
                ),
            )
        ),
        "abc_cde/__init__.py": (
            '"""abc_cde package."""\n\nABC_CDE = "abc-cde"\n'
        ),
        "abc_cde/core.py": (
            dedent(
                text=(
                    "    from abc_cde import ABC_CDE\n    \n    \n    clas"
                    's AbcCde:\n        """The abc_cde engine."""\n    \n '
                    '       name = "abc_cde"\n    '
                ),
            )
        ),
        "web/index.html": (
            dedent(
                text=(
                    '    <title>Abc Cde</title>\n    <link rel="stylesheet'
                    '" href="abc-cde.css">\n    <script src="/static/abc_c'
                    'de.js"></script>\n    <p>abc cde documentation</p>\n '
                    "   "
                ),
            )
        ),
        "web/abc-cde.css": ".abc-cde { color: red }\n/* abc cde */\n",
        "web/abc_cde.js": (
            dedent(
                text=(
                    "    const abcCde = new AbcCde();\n    // abc_cde clie"
                    "nt\n    const url = 'https://example.com/abc-cde/api'"
                    ";\n    "
                ),
            )
        ),
        "config/settings.json": '{"name": "abc-cde", "module": "abc_cde"}\n',
        "config/settings.xml": (
            "<project><name>Abc Cde</name><id>abc-cde</id></project>\n"
        ),
        "config/data.csv": "name,module\nabc cde,abc_cde\n",
        "db/schema.sql": "-- abc_cde schema\nSELECT 1;\n",
        "exactus/docs/abc_cde.md": "See abc_cde and ABC CDE.\n",
    }


def _snapshot(*, root: Path) -> dict[str, bytes]:
    """Read every file below ``root`` keyed by its relative path.

    Args:
        root: Project directory.

    Returns:
        Relative POSIX path to file bytes.

    """
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob(pattern="*"))
        if path.is_file()
    }


def _build(*, tmp_path: Path) -> Path:
    """Create the sample project, including a SQLite database.

    Args:
        tmp_path: Per-test temporary directory.

    Returns:
        The project root.

    """
    root: Path = tmp_path / Constants.old
    for relative, content in Constants.files.items():
        path: Path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(data=content, encoding="utf-8")
    notes: Table = Table(
        name="notes",
        definitions=(
            ColumnDefinition(
                name="body",
                affinity="TEXT",
                nullable=True,
                primary_key=False,
            ),
        ),
    )
    with connect(database=root / "db" / "state.sqlite") as connection:
        _ = execute(connection=connection, statement=notes.create())
        _ = execute(
            connection=connection,
            statement=notes.insert(),
            parameters=("abc_cde note",),
        )
    return root


def test_rename_there_and_back_is_lossless(tmp_path: Path) -> None:
    """A→B then B→A restores every text file byte for byte.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _build(tmp_path=tmp_path)
    before: dict[str, bytes] = {
        key: value
        for key, value in _snapshot(root=root).items()
        if not key.endswith(".sqlite")
    }
    forward: int = main(
        arguments=[
            str(object=root),
            "--name",
            Constants.new,
            "--yes",
            "--no-github",
        ],
    )
    expect_equal(actual=forward, expected=0)
    moved: Path = tmp_path / Constants.new
    expect_equal(actual=moved.is_dir(), expected=True)
    back: int = main(
        arguments=[
            str(object=moved),
            "--name",
            Constants.old,
            "--from",
            Constants.new,
            "--yes",
            "--no-github",
        ],
    )
    expect_equal(actual=back, expected=0)
    after: dict[str, bytes] = {
        key: value
        for key, value in _snapshot(root=tmp_path / Constants.old).items()
        if not key.endswith(".sqlite")
    }
    expect_equal(actual=sorted(after), expected=sorted(before))
    for key, value in before.items():
        expect_equal(actual=after[key], expected=value, message=key)
