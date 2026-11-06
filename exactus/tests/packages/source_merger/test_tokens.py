# Copyright (c) 2026
"""Exercise the whitespace-insensitive token-level merge fallback."""

from __future__ import annotations

from time import monotonic
from typing import Final, final

from exactus.packages.source_merger.tokens import (
    merge_tokens,
    merge_tokens_bounded,
)
from exactus.tests.common.support import expect_equal, expect_true


@final
class Constants:
    """Group module-level constants.

    Attributes:
        base: Grouped module constant.
        tool: Grouped module constant.
        deadline_tolerance: Grouped module constant.

    """

    base: Final[str] = """\
a = 1
b   =   2
c = 3
d = 4
e = 5
f = 6
g = 7
"""
    tool: Final[str] = """\
a = 1
b = 2
c = 3
d = 4
e = 5
f = 6
g = 7
"""
    deadline_tolerance: Final[float] = 20.0


def test_literal_edit_on_respaced_line_merges() -> None:
    """A user token edit survives a tool-only whitespace change."""
    user: str = Constants.base.replace("b   =   2", "b   =   20")
    merged: str | None = merge_tokens(
        original=Constants.base,
        user_edited=user,
        tool_refactored=Constants.tool,
    )
    expect_equal(
        actual=merged,
        expected=Constants.tool.replace("b = 2", "b = 20"),
    )


def test_disjoint_edits_from_both_sides_merge() -> None:
    """Edits far apart from each other are both kept."""
    user: str = Constants.base.replace("g = 7", "g = 70")
    tool: str = Constants.tool.replace("a = 1", "a: int = 1")
    merged: str | None = merge_tokens(
        original=Constants.base,
        user_edited=user,
        tool_refactored=tool,
    )
    expect_equal(actual=merged, expected=tool.replace("g = 7", "g = 70"))


def test_overlapping_edits_conflict() -> None:
    """Both forks changing the same token yields no merge."""
    merged: str | None = merge_tokens(
        original=Constants.base,
        user_edited=Constants.base.replace("c = 3", "c = 30"),
        tool_refactored=Constants.tool.replace("c = 3", "c = 31"),
    )
    expect_true(condition=merged is None)


def test_same_line_edits_within_guard_conflict() -> None:
    """Edits sharing a line closer than the guard distance are refused."""
    merged: str | None = merge_tokens(
        original="""\
x = a + b
""",
        user_edited="""\
x = a + b2
""",
        tool_refactored="""\
x = a2 + b
""",
    )
    expect_true(condition=merged is None)


def test_edits_on_adjacent_lines_merge() -> None:
    """Edits on different lines with a stable token between them merge."""
    merged: str | None = merge_tokens(
        original=Constants.base,
        user_edited=Constants.base.replace("d = 4", "d = 40"),
        tool_refactored=Constants.tool.replace("c = 3", "c = 31"),
    )
    expect_equal(
        actual=merged,
        expected=Constants.tool.replace("c = 3", "c = 31").replace(
            "d = 4",
            "d = 40",
        ),
    )


def test_user_append_keeps_user_tail() -> None:
    """Text appended by the user lands after the tool's layout."""
    merged: str | None = merge_tokens(
        original=Constants.base,
        user_edited=Constants.base
        + """\

h = 8
""",
        tool_refactored=Constants.tool,
    )
    expect_equal(
        actual=merged,
        expected=Constants.tool
        + """\

h = 8
""",
    )


def test_oversized_input_is_refused() -> None:
    """Inputs beyond the token budget fall back to conflict."""
    big: str = "x " * 70000
    merged: str | None = merge_tokens(
        original=big,
        user_edited=big,
        tool_refactored=big,
    )
    expect_true(condition=merged is None)


def test_inserted_line_ambiguity_is_slid_to_the_line_boundary() -> None:
    """An insertion before a repeated token keeps whole-line layout."""
    original: str = """\
<a>
</b>
"""
    tool: str = """\
<a>
  </b>
"""
    user: str = """\
<a>
<p>x</p>
</b>
"""
    merged: str | None = merge_tokens(
        original=original,
        user_edited=user,
        tool_refactored=tool,
    )
    expect_equal(
        actual=merged,
        expected="""\
<a>
<p>x</p>
  </b>
""",
    )


def test_case_only_tool_change_yields_to_user_value() -> None:
    """The user's value wins and adopts the tool's hex-digit casing."""
    merged: str | None = merge_tokens(
        original="""\
c: #00FF00;
d: 1;
""",
        user_edited="""\
c: #FF00FF;
d: 1;
""",
        tool_refactored="""\
c: #00ff00;
d: 1;
""",
    )
    expect_equal(
        actual=merged,
        expected="""\
c: #ff00ff;
d: 1;
""",
    )


def test_line_insertion_beside_deleted_region_merges() -> None:
    """A new line next to text the tool deleted is not a conflict."""
    merged: str | None = merge_tokens(
        original="""\
a = 1
import re
b = 2
""",
        user_edited="""\
a = 1
def f():
    pass
import re
b = 2
""",
        tool_refactored="""\
a = 1
b = 2
""",
    )
    expect_equal(
        actual=merged,
        expected="""\
a = 1
def f():
    pass
b = 2
""",
    )


def test_bounded_merge_matches_the_in_process_result() -> None:
    """The isolated child returns exactly what the library would."""
    user: str = Constants.base.replace("b   =   2", "b   =   20")
    expected: str | None = merge_tokens(
        original=Constants.base,
        user_edited=user,
        tool_refactored=Constants.tool,
    )
    expect_equal(
        actual=merge_tokens_bounded(
            original=Constants.base,
            user_edited=user,
            tool_refactored=Constants.tool,
        ),
        expected=expected,
    )


def test_bounded_merge_gives_up_at_the_deadline() -> None:
    """A pathological repetitive diff costs the deadline, not minutes."""
    base: str = (
        """\
a = 1
"""
        * 1200
    )
    tool: str = (
        """\
a = 1
b = 2
"""
        * 600
    )
    started: float = monotonic()
    merged: str | None = merge_tokens_bounded(
        original=base,
        user_edited=base
        + """\
z = 9
""",
        tool_refactored=tool,
        timeout=2.0,
    )
    expect_true(condition=merged is None)
    expect_true(
        condition=monotonic() - started < Constants.deadline_tolerance,
        message="the deadline did not stop the child",
    )
