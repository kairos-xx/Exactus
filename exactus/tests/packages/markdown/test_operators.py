# Copyright (c) 2026
"""Operator edge cases for non-matching operand types."""

from __future__ import annotations

from exactus.packages.markdown.operators import Operators
from exactus.tests.common.support import expect_false, expect_true


def test_contains_on_strings_and_scalars() -> None:
    """``contains`` handles strings and rejects scalar containers."""
    expect_true(condition=Operators.contains(actual="alpha", expected="lph"))
    expect_false(condition=Operators.contains(actual="alpha", expected=1))
    expect_false(condition=Operators.contains(actual=5, expected=5))


def test_in_on_strings_and_scalars() -> None:
    """``in`` handles string operands and rejects scalar operands."""
    expect_true(condition=Operators.in_(actual="lph", expected="alpha"))
    expect_false(condition=Operators.in_(actual=1, expected="alpha"))
    expect_false(condition=Operators.in_(actual=1, expected=1))
    expect_true(condition=Operators.not_in(actual=1, expected=1))


def test_regex_requires_strings() -> None:
    """``regex`` is false when either side is not a string."""
    expect_false(condition=Operators.regex(actual=1, expected="1"))


def test_type_is_distinguishes_bool_from_int() -> None:
    """``type_is`` treats booleans as ``bool`` only."""
    expect_true(condition=Operators.type_is(actual=True, expected="bool"))
    expect_false(condition=Operators.type_is(actual=True, expected="int"))


def test_ordering_rejects_bool_and_mixed_types() -> None:
    """Ordering operators are false for booleans and mixed operand types."""
    expect_false(condition=Operators.gt(actual=True, expected=0))
    expect_false(condition=Operators.lt(actual=1, expected=True))
    expect_false(condition=Operators.gt(actual="a", expected=1))
    expect_true(condition=Operators.lt(actual="a", expected="b"))
