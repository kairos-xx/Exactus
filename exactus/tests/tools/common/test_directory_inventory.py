# Copyright (c) 2026
"""Verify semantic, bottom-up README inventories and idempotent repairs."""

from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
)
from exactus.tools.readme.core import ReadmeExactusInput, readme

if TYPE_CHECKING:
    from exactus.tools.readme.core import ReadmeExactusResult


def test_bottom_up_docstrings_child_summaries_and_updates(
    tmp_path: Path,
) -> None:
    """Propagate child summaries and preserve prose in refreshed rows.

    Args:
        tmp_path: Isolated per-test directory.

    """
    child: Path = tmp_path / "feature"
    grandchild: Path = child / "engine"
    grandchild.mkdir(parents=True)
    (grandchild / "run.py").write_text(
        data='"""Replay saved browser actions and retain evidence."""\n',
    )
    (child / "README.md").write_text(
        data=dedent(
            text=(
                "    # Feature\n    \n    Record and replay browser sessio"
                "ns.\n    \n    ## Usage\n    \n    Keep my examples.\n   "
                " "
            ),
        ),
    )
    inputs: ReadmeExactusInput = ReadmeExactusInput(
        root=tmp_path,
        includes=(),
        excludes=(),
        fix=True,
    )
    result: ReadmeExactusResult = readme(inputs=inputs)
    expect_equal(actual=result.findings, expected=())
    text: str = (grandchild / "README.md").read_text()
    expect_in(
        member="Replay saved browser actions and retain evidence.",
        container=text,
    )
    parent: str = (tmp_path / "README.md").read_text()
    expect_in(member="Record and replay browser sessions.", container=parent)
    before: dict[Path, int] = {
        path: path.stat().st_mtime_ns
        for path in tmp_path.rglob(pattern="README.md")
    }
    _ = readme(inputs=inputs)
    expect_equal(
        actual={path: path.stat().st_mtime_ns for path in before},
        expected=before,
    )
    (grandchild / "run.py").rename(target=grandchild / "replay.py")
    _ = readme(inputs=inputs)
    current: str = (grandchild / "README.md").read_text()
    expect_not_in(member="`run.py`", container=current)
    expect_in(member="[`replay.py`](replay.py)", container=current)
    expect_true(
        condition=(child / "README.md").read_text().startswith("# Feature"),
    )
    expect_in(
        member="Keep my examples.",
        container=(child / "README.md").read_text(),
    )


@pytest.mark.parametrize("legacy_first", [False, True])
def test_repair_removes_obsolete_and_duplicate_generated_blocks(
    *,
    tmp_path: Path,
    legacy_first: bool,
) -> None:
    """Replace stale generated references without changing authored content.

    Args:
        tmp_path: Isolated documentation tree.
        legacy_first: Whether the obsolete block precedes the current one.

    """
    docs: Path = tmp_path / "docs"
    docs.mkdir()
    blocks: list[str] = [
        dedent(
            text=(
                "    <!-- exactus:inventory:start -->\n    - [deleted](del"
                "eted.md)\n    <!-- exactus:inventory:end -->"
            ),
        ),
        dedent(
            text=(
                "    <!-- audit:inventory:start -->\n    - [old status](st"
                "atus/README.md)\n    <!-- audit:inventory:end -->"
            ),
        ),
    ]
    if legacy_first:
        blocks.reverse()
    path: Path = docs / "README.md"
    path.write_text(
        data="# Documentation\n\nKeep the introduction.\n\n"
        + "\n\nKeep the middle guidance.\n\n".join(blocks)
        + dedent(
            text=(
                "    \n    \n    Keep this historical mention: `exactus/do"
                "cs/status/README.md`.\n    "
            ),
        )
        + "\n<!-- exactus:inventory:start -->\nDuplicate generated block.\n"
        + "<!-- exactus:inventory:end -->\n",
    )
    (docs / "current.md").write_text(data="Current guidance.\n")
    inputs: ReadmeExactusInput = ReadmeExactusInput(
        root=tmp_path,
        includes=(),
        excludes=(),
        fix=True,
    )
    result: ReadmeExactusResult = readme(inputs=inputs)
    expect_equal(actual=result.findings, expected=())
    text: str = path.read_text()
    expect_equal(
        actual=text.count("<!-- exactus:inventory:start -->"),
        expected=1,
    )
    expect_not_in(member="audit:inventory", container=text)
    expect_not_in(member="(status/README.md)", container=text)
    expect_not_in(member="(deleted.md)", container=text)
    expect_not_in(member="Duplicate generated block.", container=text)
    expect_in(member="[`current.md`](current.md)", container=text)
    expect_in(member="Keep the introduction.", container=text)
    expect_in(member="Keep the middle guidance.", container=text)
    expect_in(member="`exactus/docs/status/README.md`", container=text)
    before: int = path.stat().st_mtime_ns
    _ = readme(inputs=inputs)
    expect_equal(actual=path.stat().st_mtime_ns, expected=before)
