# Copyright (c) 2026
"""Verify cache ownership, content refresh and mutable-tree isolation."""

from __future__ import annotations

from ast import Assign
from typing import TYPE_CHECKING

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.common.source_cache import (
    SourceCache,
    SourceRecord,
    source_record,
    source_text,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_mutation_and_external_edits_are_isolated(tmp_path: Path) -> None:
    """Reuse stable source while keeping mutable AST consumers independent.

    Args:
        tmp_path: Independent source tree.

    """
    path: Path = tmp_path / "sample.py"
    path.write_text(
        data="""\
value = 1
""",
        encoding="utf-8",
    )
    with SourceCache(max_entries=1) as cache:
        first: SourceRecord = source_record(path=path)
        expect_true(condition=source_record(path=path).tree is first.tree)
        private: SourceRecord = source_record(path=path, mutable=True)
        private.tree.body.clear()
        expect_true(
            condition=isinstance(
                source_record(path=path).tree.body[0],
                Assign,
            ),
        )
        path.write_text(
            data="""\
value = 2
""",
            encoding="utf-8",
        )
        expect_equal(
            actual=source_text(path=path),
            expected="""\
value = 2
""",
        )
        expect_false(condition=source_record(path=path).tree is first.tree)
        cache.invalidate(path=path)
        expect_equal(
            actual=cache.read(path=path).source,
            expected="""\
value = 2
""",
        )
        other: Path = tmp_path / "other.py"
        other.write_text(
            data="""\
other = 3
""",
            encoding="utf-8",
        )
        cache.read(path=other)
        expect_equal(
            actual=source_record(path=path).source,
            expected="""\
value = 2
""",
        )
    expect_false(condition=source_record(path=path).tree is first.tree)


def test_nested_cache_context_restores_ownership(tmp_path: Path) -> None:
    """An inner run releases only its own snapshots on exit.

    Args:
        tmp_path: Independent source tree.

    """
    path: Path = tmp_path / "sample.py"
    path.write_text(
        data="""\
value = 1
""",
        encoding="utf-8",
    )
    with SourceCache():
        outer: SourceRecord = source_record(path=path)
        with SourceCache():
            expect_false(condition=source_record(path=path).tree is outer.tree)
        expect_true(condition=source_record(path=path).tree is outer.tree)
