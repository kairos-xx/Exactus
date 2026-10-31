# Copyright (c) 2026
"""Cover the shared directory-inventory helper and its bundle export."""

from __future__ import annotations

from pathlib import Path
from platform import machine, system
from textwrap import dedent
from typing import Final, final

from exactus.packages.zstd_portable import export_package
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_not_in,
)
from exactus.tools.common.directory_inventory import (
    description,
    entry_line,
    heal_directory,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        canonical: Grouped module constant.

    """

    canonical: Final[Path] = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "tools"
        / "common"
        / "directory_inventory.py"
    )


def test_exported_package_ships_the_canonical_helper(tmp_path: Path) -> None:
    """``export_package`` copies the shared helper into the leaf package.

    Args:
        tmp_path: Isolated staging directory.

    """
    package: Path = export_package(
        os_name=system().lower(),
        machine=machine(),
        target=tmp_path,
    )
    expect_equal(
        actual=(package / "directory_inventory.py").read_bytes(),
        expected=Constants.canonical.read_bytes(),
    )


def test_description_extracts_script_docblock(tmp_path: Path) -> None:
    """Strip JSDoc-style block decorations and ``@`` tags from scripts.

    Args:
        tmp_path: Isolated per-test directory.

    """
    script: Path = tmp_path / "widget.js"
    script.write_text(
        data="/**\n * Render the panel.\n * @param root host element\n */\n",
        encoding="utf-8",
    )
    expect_equal(actual=description(path=script), expected="Render the panel.")
    style: Path = tmp_path / "theme.css"
    style.write_text(data="a { color: red; }\n", encoding="utf-8")
    expect_equal(
        actual=description(path=style),
        expected="Provide theme css content.",
    )


def test_heal_directory_skips_history_trees(tmp_path: Path) -> None:
    """Leave ``.history`` snapshot directories undocumented.

    Args:
        tmp_path: Isolated per-test directory.

    """
    directory: Path = tmp_path / ".history" / "snapshot"
    directory.mkdir(parents=True)
    entry: Path = directory / "state.py"
    entry.write_text(data='"""Saved state."""\n', encoding="utf-8")
    heal_directory(directory=directory, entries=[entry])
    expect_false(condition=(directory / "README.md").is_file())


def test_heal_directory_seeds_readme_from_first_candidate(
    tmp_path: Path,
) -> None:
    """Synthesize a heading plus the lead candidate summary without a README.

    Args:
        tmp_path: Isolated per-test directory.

    """
    directory: Path = tmp_path / "pkg"
    directory.mkdir()
    (directory / "alpha.py").write_text(
        data='"""Seed the alpha summary."""\n',
        encoding="utf-8",
    )
    heal_directory(directory=directory, entries=sorted(directory.iterdir()))
    text: str = (directory / "README.md").read_text(encoding="utf-8")
    expect_in(member="# `pkg/`", container=text)
    expect_in(member="Seed the alpha summary.", container=text)


def test_heal_directory_marks_empty_sections(tmp_path: Path) -> None:
    """Emit explicit placeholders when a directory holds no files or folders.

    Args:
        tmp_path: Isolated per-test directory.

    """
    directory: Path = tmp_path / "empty"
    directory.mkdir()
    heal_directory(directory=directory, entries=[])
    text: str = (directory / "README.md").read_text(encoding="utf-8")
    expect_in(member="No direct files besides this README.", container=text)
    expect_in(member="No subdirectories.", container=text)


def test_heal_directory_replaces_managed_block_only(tmp_path: Path) -> None:
    """Replace stale managed rows while preserving surrounding prose.

    Args:
        tmp_path: Isolated per-test directory.

    """
    directory: Path = tmp_path / "managed"
    directory.mkdir()
    readme: Path = directory / "README.md"
    readme.write_text(
        data=(
            dedent(
                text=(
                    "    # Head\n    \n    Intro prose.\n    \n    <!-- ex"
                    "actus:inventory:start -->\n    STALE ROW\n    <!-- ex"
                    "actus:inventory:end -->\n    \n    Tail prose.\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    (directory / "tool.py").write_text(
        data='"""Fresh tool."""\n',
        encoding="utf-8",
    )
    entries: list[Path] = sorted(directory.iterdir())
    heal_directory(directory=directory, entries=entries)
    text: str = readme.read_text(encoding="utf-8")
    expect_in(member="Intro prose.", container=text)
    expect_in(member="Tail prose.", container=text)
    expect_in(member="[`tool.py`](tool.py)", container=text)
    expect_in(member="Fresh tool.", container=text)
    expect_not_in(member="STALE ROW", container=text)


def test_entry_line_links_directories_to_their_readme(tmp_path: Path) -> None:
    """Link subdirectory rows at ``name/README.md`` and quote odd names.

    Args:
        tmp_path: Isolated per-test directory.

    """
    child: Path = tmp_path / "child dir"
    child.mkdir()
    (child / "README.md").write_text(
        data="# Child\n\nKeep the child summary.\n",
        encoding="utf-8",
    )
    line: str = entry_line(entry=child)
    expect_in(member="[`child dir/`]", container=line)
    expect_in(member="child%20dir/README.md", container=line)
    expect_in(member="Keep the child summary.", container=line)
