"""Regression cases for hierarchical incremental source reconciliation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from exactus.packages.source_merger import DeltaMetrics
from ast import parse
from textwrap import dedent

import pytest

from exactus.packages.source_merger import (
    DeltaPolicy,
    SnapshotCache,
    SourceMerger,
    measure,
)
from exactus.packages.source_merger.cache import StatementIndex
from exactus.packages.source_merger.model import (
    MergeResult,
    Replacement,
    Snapshot,
    Statement,
)
from exactus.packages.source_merger.patch import apply
from exactus.packages.source_merger.python_parser import PythonParser
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_true,
    fail,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        paste_token_limit: Grouped module constant.
        expected_reuses: Grouped module constant.

    """

    paste_token_limit: Final[int] = 1000
    expected_reuses: Final[int] = 2


def test_reparse_isolated_function_matches_full_parse() -> None:
    """Reparse reuses surrounding units after one edited function."""
    ancestor: str = dedent(
        text=(
            """\
    def f(x):
        return x + 1

    def g(x):
        return x * 9
    """
        ),
    )
    edited: str = ancestor.replace("return x + 1", "return x + 200")
    cache: SnapshotCache = SnapshotCache()
    cache.parse_forks(
        original=ancestor,
        user=ancestor,
        tool=ancestor,
        language="python",
    )
    next_version: tuple[Snapshot, Snapshot, Snapshot] = cache.parse_forks(
        original=ancestor,
        user=edited,
        tool=ancestor,
        language="python",
    )
    expect_equal(
        actual=next_version[1],
        expected=PythonParser().parse(source=edited),
    )
    expect_equal(actual=cache.stats.incremental, expected=1)
    expect_equal(actual=cache.stats.parsed, expected=2)


def test_incremental_handles_unicode_offsets() -> None:
    """Python's byte-indexed AST columns remain correct after Unicode edits."""
    original: str = """\
def f(x):
    return "café" + x

def g(y):
    return y
"""
    edited: str = original.replace('"café" + x', '"café é" + x')
    cache: SnapshotCache = SnapshotCache()
    cache.parse_forks(
        original=original,
        user=original,
        tool=original,
        language="python",
    )
    result: tuple[Snapshot, Snapshot, Snapshot] = cache.parse_forks(
        original=original,
        user=edited,
        tool=original,
        language="python",
    )
    expect_equal(
        actual=result[1],
        expected=PythonParser().parse(source=edited),
    )
    expect_equal(actual=cache.stats.incremental, expected=1)


def test_incremental_falls_back_on_function_rename() -> None:
    """A signature or declaration identity change must get a full parse."""
    old: str = """\
def f(x):
    return x
"""
    changed: str = """\
def renamed(x):
    return x
"""
    cache: SnapshotCache = SnapshotCache()
    cache.parse_forks(original=old, user=old, tool=old, language="python")
    result: tuple[Snapshot, Snapshot, Snapshot] = cache.parse_forks(
        original=old,
        user=changed,
        tool=old,
        language="python",
    )
    expect_equal(
        actual=result[1],
        expected=PythonParser().parse(source=changed),
    )
    expect_equal(actual=cache.stats.incremental, expected=0)


def test_incremental_falls_back_on_new_top_level_declaration() -> None:
    """Appending a new declaration must not be misclassified as a body edit."""
    old: str = """\
def f(x):
    return x
"""
    changed: str = (
        old
        + """\

def g(x):
    return x
"""
    )
    cache: SnapshotCache = SnapshotCache()
    cache.parse_forks(original=old, user=old, tool=old, language="python")
    result: tuple[Snapshot, Snapshot, Snapshot] = cache.parse_forks(
        original=old,
        user=changed,
        tool=old,
        language="python",
    )
    expect_equal(
        actual=result[1],
        expected=PythonParser().parse(source=changed),
    )
    expect_equal(actual=len(result[1].units), expected=2)
    expect_equal(actual=cache.stats.incremental, expected=0)


def test_parse_cache_batches_foreign_snapshots() -> None:
    """JavaScript parser starts only one process for three fork snapshots."""
    cache: SnapshotCache = SnapshotCache()
    snapshots: tuple[Snapshot, ...] = cache.parse_many(
        sources=(
            "function f(x) {return x;}",
            "const f = (x) => x;",
            "const g = (x) => x;",
        ),
        language="javascript",
    )
    expect_true(condition=all(snapshot.valid for snapshot in snapshots))
    expect_equal(actual=cache.stats.batches, expected=1)
    expect_equal(actual=cache.stats.parsed, expected=3)
    cache.parse_many(
        sources=(
            "function f(x) {return x;}",
            "const f = (x) => x;",
            "const g = (x) => x;",
        ),
        language="javascript",
    )
    expect_equal(actual=cache.stats.batches, expected=1)
    expect_equal(actual=cache.stats.reused, expected=3)


def test_cache_is_bounded() -> None:
    """Previous editor snapshots cannot grow session memory without limits."""
    cache: SnapshotCache = SnapshotCache(max_snapshots=2, max_matches=1)
    for source in (
        """\
x = 1
""",
        """\
x = 2
""",
        """\
x = 3
""",
    ):
        expect_true(
            condition=cache.parse(source=source, language="python").valid,
        )
    expect_equal(actual=cache.stats.parsed, expected=3)
    expect_true(
        condition=cache.parse(
            source="""\
x = 1
""",
            language="python",
        ).valid,
    )
    expect_equal(actual=cache.stats.parsed, expected=4)


@pytest.mark.parametrize(
    ("original", "user", "tool", "expected"),
    [
        (
            """\
def f(x):
    return calculate(x, 1)
""",
            """\
def f(x):
    return calculate(x, 2)
""",
            """\
def f(x):
    return calculate(x + 3, 1)
""",
            "calculate(x + 3, 2)",
        ),
        (
            """\
def f(x):
    return (x + 1) * (x + 2)
""",
            """\
def f(x):
    return (x + 3) * (x + 2)
""",
            """\
def f(x):
    return (x + 1) * (x + 4)
""",
            "(x + 3) * (x + 4)",
        ),
        (
            """\
def f(x):
    return calculate(x, 1)
""",
            """\
def f(x):
    return calculate(x, 2)
""",
            (
                """\
def f(x):
    return prepare(x)

def prepare(x):
    return calculate(x+3,1)
"""
            ),
            "calculate(x+3,2)",
        ),
        (
            """\
VALUE = merge(x,1)
""",
            """\
VALUE = merge(x,2)
""",
            (
                """\
from typing import Final, final
@final
class Constants:
    VALUE: Final[int] = merge(x+1,1)
"""
            ),
            "VALUE: Final[int] = merge(x+1,2)",
        ),
    ],
)
def test_independent_expression_mutations(
    *,
    original: str,
    user: str,
    tool: str,
    expected: str,
) -> None:
    """Project changed expression leaves through independent refactoring.

    Args:
        original: Common-ancestor source.
        user: Concurrently edited source.
        tool: Refactored source.
        expected: Fragment expected in the merged result.

    """
    result: MergeResult = SourceMerger(
        original=original,
        user_edited=user,
        tool_refactored=tool,
        language="python",
    ).merge()
    expect_true(condition=result.success, message=str(object=result.conflicts))
    if result.source is None:
        fail(message="result.source is None")
    expect_in(member=expected, container=result.source)
    parse(source=result.source)


def test_competing_expression_edits_fail_closed() -> None:
    """Both forks changing the same literal must not pick a winner."""
    result: MergeResult = SourceMerger(
        original="""\
def f(x):
    return x + 1
""",
        user_edited="""\
def f(x):
    return x + 2
""",
        tool_refactored="""\
def f(x):
    return x + 3
""",
        language="python",
    ).merge()
    expect_false(condition=result.success)
    expect_none(value=result.source)
    expect_true(
        condition=any(
            conflict.kind == "concurrent_change"
            for conflict in result.conflicts
        ),
    )


def test_repeated_merges_share_immutable_cache() -> None:
    """Repeated merges share the immutable snapshot cache."""
    cache: SnapshotCache = SnapshotCache()
    ancestor: str = """\
def f(x):
    return x + 1

def stable(x):
    return x
"""
    tool: str = """\
def f(x: int) -> int:
    return x + 1

def stable(x: int) -> int:
    return x
"""
    for value in (2, 3, 4):
        user: str = ancestor.replace("return x + 1", f"return x + {value}")
        result: MergeResult = SourceMerger(
            original=ancestor,
            user_edited=user,
            tool_refactored=tool,
            language="python",
            snapshot_cache=cache,
        ).merge()
        expect_true(
            condition=result.success,
            message=str(object=result.conflicts),
        )
        if result.source is None:
            fail(message="result.source is None")
        expect_in(member=f"return x + {value}", container=result.source)
    expect_true(condition=cache.stats.incremental >= Constants.expected_reuses)
    expect_true(condition=cache.stats.reused >= Constants.expected_reuses)


def test_index_rejects_ambiguous_duplicate_statements() -> None:
    """Equivalent statements in independent scopes cannot be guessed."""
    snapshot: Snapshot = PythonParser().parse(
        source="""\
def f():
    return 1

def g():
    return 1
""",
    )
    index: StatementIndex = StatementIndex(snapshot=snapshot)
    statement: Statement = snapshot.units[0].statements[0]
    expect_none(value=index.locate(original=statement, preferred=None))
    expect_equal(
        actual=index.locate(original=statement, preferred=snapshot.units[0]),
        expected=statement,
    )


def test_atomic_patch_reconstruction_preserves_insert_order() -> None:
    """Patch reconstruction preserves same-position insert order."""
    expect_equal(
        actual=apply(
            source="abcd",
            replacements=(
                Replacement(start=2, end=2, text="X", scope="first"),
                Replacement(start=2, end=2, text="Y", scope="second"),
            ),
        ),
        expected="abYXcd",
    )
    with pytest.raises(expected_exception=ValueError, match="Overlapping"):
        apply(
            source="abcdef",
            replacements=(
                Replacement(start=2, end=4, text="X", scope="first"),
                Replacement(start=3, end=5, text="Y", scope="second"),
            ),
        )


def test_large_delta_detects_user_paste() -> None:
    """Line-anchored diff still counts substantial pasted text accurately."""
    ancestor: str = """\

""".join(f"def f{i}(x): return {i}" for i in range(200))
    pasted: str = (
        ancestor
        + """\

"""
        + """\

""".join((f"def added{i}(): return {i}") for i in range(300))
    )
    result: DeltaMetrics = measure(
        original=ancestor,
        changed=pasted,
        language="python",
    )
    expect_true(condition=result.inserted_tokens > Constants.paste_token_limit)
    expect_true(condition=result.edit_events > 0)


def test_identity_confidence_threshold_is_active() -> None:
    """A strict policy must reject otherwise plausible renamed declarations."""
    original: str = """\
def f(x):
    return x + 1
"""
    result: MergeResult = SourceMerger(
        original=original,
        user_edited="""\
def f(x):
    return x + 2
""",
        tool_refactored="""\
def g(x):
    return x + 1
""",
        language="python",
        delta_policy=DeltaPolicy(min_identity_confidence=0.999),
    ).merge()
    expect_false(condition=result.success)
    expect_none(value=result.source)


def test_cache_reuses_identical_delta_reports() -> None:
    """Repeated tool fork metrics are not recomputed for each editor event."""
    cache: SnapshotCache = SnapshotCache()
    original: str = """\
def f(x):
    return x + 1
"""
    tool: str = """\
def f(x: int) -> int:
    return x + 1
"""
    for value in (2, 3):
        expect_true(
            condition=SourceMerger(
                original=original,
                user_edited=original.replace("x + 1", (f"x + {value}")),
                tool_refactored=tool,
                language="python",
                snapshot_cache=cache,
            )
            .merge()
            .success,
        )
    expect_true(condition=cache.stats.reused_deltas >= 1)


def test_indentation_only_semantic_change_consumes_delta() -> None:
    """Equal tokens cannot make indentation-only semantic changes free."""
    original: str = dedent(
        text=(
            """\
    def f(x):
        if x:
            print(x)
        print('always')
    """
        ),
    )
    changed: str = original.replace(
        "    print('always')",
        "        print('always')",
    )
    report: DeltaMetrics = measure(
        original=original,
        changed=changed,
        language="python",
    )
    expect_true(condition=report.changed_fraction > 0)
    expect_true(condition=report.replaced_tokens > 0)


def test_assignment_preserves_tool_side_variable_edit() -> None:
    """A name-insensitive fingerprint must not erase another RHS change."""
    result: MergeResult = SourceMerger(
        original="""\
VALUE = x + 1
""",
        user_edited="""\
VALUE = x + 2
""",
        tool_refactored="""\
VALUE: int = y + 1
""",
        language="python",
    ).merge()
    expect_true(condition=result.success, message=str(object=result.conflicts))
    if result.source is None:
        fail(message="result.source is None")
    expect_in(member="VALUE: int = y + 2", container=result.source)


def test_assignment_rejects_same_leaf_parallel_edits() -> None:
    """Concurrent assignment changes to the same literal never auto-merge."""
    result: MergeResult = SourceMerger(
        original="""\
VALUE = x + 1
""",
        user_edited="""\
VALUE = x + 2
""",
        tool_refactored="""\
VALUE: int = x + 3
""",
        language="python",
    ).merge()
    expect_false(condition=result.success)
    expect_none(value=result.source)
