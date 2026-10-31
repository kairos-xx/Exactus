# Copyright (c) 2026
"""Predicate specs filter list items and drive conditional mapping."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.packages.markdown.errors import MappingError
from exactus.packages.markdown.predicates import Predicates
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        row: Grouped module constant.

    """

    row: Final[dict[str, JsonValue]] = {
        "name": "alpha",
        "score": 7,
        "tags": ["x", "y"],
        "empty": [],
        "none": None,
        "flag": True,
    }


def _check(*, spec: JsonValue) -> bool:
    """Evaluate ``spec`` against ``ROW``.

    Args:
        spec: Predicate specification.

    Returns:
        The predicate result.

    """
    return Predicates.evaluate(
        spec=spec,
        current=Constants.row,
        root=Constants.row,
    )


def _op(*, path: str, op: str, value: JsonValue = None) -> bool:
    """Evaluate one ``$path``/``$op``/``$value`` predicate.

    Args:
        path: Path to test.
        op: Operator name.
        value: Expected operand.

    Returns:
        The predicate result.

    """
    return _check(spec={"$path": path, "$op": op, "$value": value})


def test_comparison_operators() -> None:
    """Numeric and equality operators compare the resolved value."""
    expect_true(condition=_op(path="score", op="eq", value=7))
    expect_true(condition=_op(path="score", op="ne", value=8))
    expect_true(condition=_op(path="score", op="gt", value=6))
    expect_true(condition=_op(path="score", op="gte", value=7))
    expect_true(condition=_op(path="score", op="lt", value=8))
    expect_true(condition=_op(path="score", op="lte", value=7))
    expect_false(condition=_op(path="name", op="gt", value=3))


def test_membership_and_string_operators() -> None:
    """Containment, prefix, suffix and regex operators work on strings."""
    expect_true(condition=_op(path="name", op="in", value=["alpha", "b"]))
    expect_true(condition=_op(path="name", op="not_in", value=["b"]))
    expect_true(condition=_op(path="tags", op="contains", value="x"))
    expect_true(condition=_op(path="name", op="starts_with", value="al"))
    expect_true(condition=_op(path="name", op="ends_with", value="ha"))
    expect_true(condition=_op(path="name", op="regex", value="^a.p"))
    expect_false(condition=_op(path="score", op="starts_with", value="7"))


def test_truthiness_and_type_operators() -> None:
    """Truthy, empty and type operators inspect the value itself."""
    expect_true(condition=_op(path="flag", op="truthy"))
    expect_true(condition=_op(path="empty", op="falsy"))
    expect_true(condition=_op(path="empty", op="empty"))
    expect_true(condition=_op(path="none", op="empty"))
    expect_true(condition=_op(path="tags", op="not_empty"))
    expect_true(condition=_op(path="tags", op="type_is", value="list"))
    expect_true(condition=_op(path="score", op="type_is", value="int"))
    expect_true(condition=_op(path="none", op="type_is", value="null"))
    expect_false(condition=_op(path="score", op="type_is", value="str"))


def test_presence_operators_and_missing_paths() -> None:
    """``exists``/``missing`` test presence; others fail on absence."""
    expect_true(condition=_op(path="none", op="exists"))
    expect_true(condition=_op(path="nope", op="missing"))
    expect_false(condition=_op(path="nope", op="exists"))
    expect_false(condition=_op(path="nope", op="eq", value=None))
    expect_false(condition=_op(path="nope", op="not_in", value=["a"]))


def test_logic_and_shorthand() -> None:
    """Boolean combinators, literals and equality shorthand compose."""
    yes: JsonValue = {"$path": "flag"}
    no: JsonValue = {"$path": "empty"}
    expect_true(condition=_check(spec={"$and": [yes, True]}))
    expect_false(condition=_check(spec={"$and": [yes, no]}))
    expect_true(condition=_check(spec={"$or": [no, yes]}))
    expect_true(condition=_check(spec={"$not": no}))
    expect_true(condition=_check(spec={"name": "alpha", "score": 7}))
    expect_false(condition=_check(spec={"name": "beta"}))
    expect_equal(actual=_check(spec=False), expected=False)
    expect_false(condition=_check(spec={"nope": None}))


def test_invalid_specs_raise_mapping_error() -> None:
    """Bad predicate shapes and operators are reported, not ignored."""
    with pytest.raises(
        expected_exception=MappingError,
        match="object or boolean",
    ):
        _check(spec="oops")
    with pytest.raises(
        expected_exception=MappingError,
        match="Unknown operator",
    ):
        _op(path="score", op="approx", value=1)
    with pytest.raises(expected_exception=MappingError, match="\\$and"):
        _check(spec={"$and": "not-a-list"})
    with pytest.raises(expected_exception=MappingError, match="Invalid regex"):
        _op(path="name", op="regex", value="(")
