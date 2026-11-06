# Copyright (c) 2026
"""Exercise the live-edit reconciliation entry point."""

from __future__ import annotations

from exactus.packages.source_merger.live import LiveMerge, merge_live_edit
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_none,
    expect_true,
    fail,
)


def test_unsupported_suffix_is_declined() -> None:
    """Files without a known grammar are never merged."""
    expect_none(
        value=merge_live_edit(
            suffix=".txt",
            original=b"a",
            tool=b"b",
            user=b"c",
        ),
    )


def test_undecodable_bytes_are_declined() -> None:
    """Non-UTF-8 content falls back to the conservative path."""
    expect_none(
        value=merge_live_edit(
            suffix=".py",
            original=b"\xff",
            tool=b"\xfe",
            user=b"\xfd",
        ),
    )


def test_independent_python_edits_merge_exactly() -> None:
    """A structural merge reports ``exact`` and keeps both edits."""
    merged: LiveMerge | None = merge_live_edit(
        suffix=".py",
        original=b"def a():\n    return 1\n\n\ndef b():\n    return 2\n",
        tool=b"def a() -> int:\n    return 1\n\n\ndef b():\n    return 2\n",
        user=b"def a():\n    return 1\n\n\ndef b():\n    return 3\n",
    )
    if merged is None:
        fail(message="independent edits did not merge")
    expect_true(condition=merged.exact)
    expect_equal(
        actual=merged.data,
        expected=(
            b"def a() -> int:\n    return 1\n\n\ndef b():\n    return 3\n"
        ),
    )


def test_ambiguous_structure_uses_the_reviewable_token_merge() -> None:
    """Duplicate selectors need the token fallback, flagged not exact."""
    base: bytes = (
        b".x {\n  color: red;\n}\n.x {\n  color: blue;\n}\n"
        b".y {\n  margin: 0px;\n}\n.z {\n  top: 1px;\n}\n"
    )
    merged: LiveMerge | None = merge_live_edit(
        suffix=".css",
        original=base,
        tool=base.replace(b"0px", b"0"),
        user=base.replace(b"top: 1px", b"top: 9px"),
    )
    if merged is None:
        fail(message="token fallback did not merge")
    expect_false(condition=merged.exact)
    expect_equal(
        actual=merged.data,
        expected=base.replace(b"0px", b"0").replace(b"1px", b"9px"),
    )


def test_conflicting_python_edits_are_declined() -> None:
    """Both forks changing the same value is a genuine conflict."""
    expect_none(
        value=merge_live_edit(
            suffix=".py",
            original=b"x = 1\n",
            tool=b"x = 2\n",
            user=b"x = 3\n",
        ),
    )
