# Copyright (c) 2026
"""The README analyzer flags undocumented directory entries."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING, cast

from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_true,
    private_call,
    require_type,
)
from exactus.tools.readme import core as readme_core

if TYPE_CHECKING:
    from pathlib import Path


def test_readme_directory_exactus_flags_undocumented_entries(
    tmp_path: Path,
) -> None:
    """Undocumented files and directories each surface a finding.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = (tmp_path / "README.md").write_text(data="# dir\n")
    _ = (tmp_path / "module.py").write_text(data="")
    (tmp_path / "pkg").mkdir()
    findings: object = private_call(
        owner=readme_core,
        name="_directory_exactus",
        directory=tmp_path,
        root=tmp_path,
    )
    expect_true(condition=isinstance(findings, list))
    rules: set[str] = {
        require_type(value=finding, kind=readme_core.ReadmeFinding).rule
        for finding in cast(typ="list[object]", val=findings)
    }
    expect_in(member="RDM002", container=rules)
    expect_in(member="RDM003", container=rules)


def test_readme_exactus_repairs_missing_inventories(tmp_path: Path) -> None:
    """Fix mode creates missing READMEs and extends existing inventories.

    Args:
        tmp_path: Per-test temporary directory.

    """
    docs: Path = tmp_path / "docs"
    guide: Path = docs / "guide"
    guide.mkdir(parents=True)
    _ = (docs / "README.md").write_text(
        data=(
            dedent(
                text=(
                    "    # Docs\n    \n    ## Files\n    \n    - `existing"
                    ".md` — Existing.\n    \n    ## Subdirectories\n    \n"
                    "    - `existing/` — Existing.\n    \n    ## Usage\n  "
                    "  \n    Keep this last.\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    _ = (docs / "topic.md").write_text(data="topic\n", encoding="utf-8")
    _ = (guide / "example.py").write_text(data="", encoding="utf-8")
    result: readme_core.ReadmeExactusResult = readme_core.readme(
        inputs=readme_core.ReadmeExactusInput(
            root=tmp_path,
            includes=(),
            excludes=(),
            fix=True,
        ),
    )
    expect_equal(actual=result.findings, expected=())
    docs_body: str = (docs / "README.md").read_text(encoding="utf-8")
    guide_body: str = (guide / "README.md").read_text(encoding="utf-8")
    expect_in(member="`guide/`", container=docs_body)
    expect_in(member="`topic.md`", container=docs_body)
    expect_in(member="`example.py`", container=guide_body)
    expect_in(member="Keep this last.", container=docs_body)
    block: str = docs_body.split(
        sep="<!-- exactus:inventory:start -->",
        maxsplit=1,
    )[1]
    expect_true(
        condition=block.index("### Files")
        < block.index("`topic.md`")
        < block.index("### Subdirectories")
        < block.index("`guide/`"),
    )


def test_readme_exactus_dry_leaves_files_unchanged(tmp_path: Path) -> None:
    """Dry mode reports violations without writing project files.

    Args:
        tmp_path: Per-test temporary directory.

    """
    docs: Path = tmp_path / "docs"
    docs.mkdir()
    result: readme_core.ReadmeExactusResult = readme_core.readme(
        inputs=readme_core.ReadmeExactusInput(
            root=tmp_path,
            includes=(),
            excludes=(),
        ),
    )
    expect_true(condition=bool(result.findings))
    expect_true(condition=not (docs / "README.md").exists())
