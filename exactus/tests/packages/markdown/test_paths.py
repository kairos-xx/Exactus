# Copyright (c) 2026
"""JSON paths resolve against a current value or the document root."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from exactus.packages.markdown.paths import Lookup, PathResolver
from exactus.tests.common.support import expect_equal, expect_false

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.

    """

    root: Final[dict[str, JsonValue]] = {
        "a": {"b": [10, 20]},
        "k": 1,
        "n": None,
    }


def _resolve(*, path: str, current: JsonValue = Constants.root) -> Lookup:
    """Resolve ``path`` against ``ROOT`` as the document root.

    Args:
        path: Path expression under test.
        current: Value the relative path starts from.

    Returns:
        The lookup result.

    """
    return PathResolver.resolve(
        current=current,
        path=path,
        root=Constants.root,
    )


def test_nested_and_indexed_path() -> None:
    """Dotted keys and ``[n]`` indexes are walked in order."""
    expect_equal(actual=_resolve(path="a.b[1]"), expected=Lookup.hit(value=20))


def test_empty_and_dot_return_current() -> None:
    """Empty and ``.`` paths mean the current value."""
    expect_equal(
        actual=_resolve(path=""),
        expected=Lookup.hit(value=Constants.root),
    )
    expect_equal(
        actual=_resolve(path="."),
        expected=Lookup.hit(value=Constants.root),
    )


def test_dollar_returns_root_and_anchor_leaves_current() -> None:
    """``$`` and ``$.`` anchor at the root even from a nested value."""
    nested: JsonValue = {"k": 99}
    expect_equal(
        actual=_resolve(path="$", current=nested),
        expected=Lookup.hit(value=Constants.root),
    )
    expect_equal(
        actual=_resolve(path="$.k", current=nested),
        expected=Lookup.hit(value=1),
    )
    expect_equal(
        actual=_resolve(path="k", current=nested),
        expected=Lookup.hit(value=99),
    )


def test_null_value_is_found() -> None:
    """A present key holding null is a hit, not a miss."""
    expect_equal(actual=_resolve(path="n"), expected=Lookup.hit(value=None))


def test_missing_key_index_and_type_mismatch_are_misses() -> None:
    """Absent keys, bad indexes and wrong container kinds miss."""
    for path in ("zzz", "a.b[2]", "k[0]", "a.b.c", "a[0]"):
        expect_false(condition=_resolve(path=path).found, message=path)
    expect_equal(actual=_resolve(path="zzz"), expected=Lookup.miss())
