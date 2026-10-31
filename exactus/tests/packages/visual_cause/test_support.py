# Copyright (c) 2026
"""Validate the shared visual_cause test helpers."""

from __future__ import annotations

import pytest

from exactus.tests.packages.visual_cause.support import (
    Constant,
    dig,
    dig_list,
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_equal,
    expect_not_in,
    expect_true,
    fail,
    private,
    private_as,
    private_call,
    private_clear,
    private_result,
    require,
    require_type,
    set_private,
)


def test_fail_and_expectation_failures() -> None:
    """Assertion helpers raise descriptive ``AssertionError`` values."""
    with pytest.raises(expected_exception=AssertionError, match="nope"):
        fail(message="nope")
    with pytest.raises(expected_exception=AssertionError, match="true"):
        expect_true(condition=False, message="check")
    with pytest.raises(expected_exception=AssertionError, match="false"):
        expect_false(condition=True)
    with pytest.raises(expected_exception=AssertionError, match="expected 2"):
        expect_equal(actual=1, expected=2, message="hint")
    with pytest.raises(expected_exception=AssertionError, match="other than"):
        expect_not_equal(actual=1, expected=1)
    with pytest.raises(expected_exception=AssertionError, match="not found"):
        expect_in(member="x", container="abc")
    with pytest.raises(
        expected_exception=AssertionError,
        match="unexpectedly",
    ):
        expect_not_in(member="a", container="abc")
    with pytest.raises(expected_exception=AssertionError, match="None"):
        expect_none(value=0)


def test_expectation_helpers_accept_good_values() -> None:
    """Assertion helpers pass on valid input."""
    expect_true(condition=True)
    expect_false(condition=False)
    expect_equal(actual=1, expected=1)
    expect_not_equal(actual=1, expected=2)
    expect_in(member="a", container="abc")
    expect_not_in(member="z", container="abc")
    expect_none(value=None)


def test_require_helpers_narrow_and_reject() -> None:
    """``require`` and ``require_type`` narrow values or fail."""
    expect_equal(actual=require(value=3), expected=3)
    expect_equal(actual=require_type(value="x", kind=str), expected="x")
    empty: str | None = None
    with pytest.raises(expected_exception=AssertionError, match="a value"):
        _: str = require(value=empty)
    with pytest.raises(expected_exception=AssertionError, match="str"):
        _ = require_type(value=1, kind=str)


def test_private_helpers_read_write_and_call() -> None:
    """Private reflection helpers read, write, clear, and call members."""

    class Owner:
        """Owner exposing private members for reflection."""

        def __init__(self) -> None:
            """Initialize private state."""
            self._value: int = 7
            self._items: list[int] = [1, 2]

        @staticmethod
        def _double(*, value: int) -> int:
            """Double one value.

            Args:
                value: Input integer.

            Returns:
                Doubled input.

            """
            return value * 2

    owner: Owner = Owner()
    expect_equal(actual=private(owner, "_value"), expected=7)
    expect_equal(actual=private_call(owner, "_double", value=4), expected=8)
    set_private(owner, "_value", 9)
    expect_equal(actual=private(owner, "_value"), expected=9)
    expect_equal(actual=private_as(owner, "_value", int), expected=9)
    expect_equal(
        actual=private_result(owner, "_double", int, value=2),
        expected=4,
    )
    private_clear(owner, "_items")
    expect_equal(actual=private(owner, "_items"), expected=[])


def test_constant_and_dig_helpers() -> None:
    """``Constant`` ignores arguments; ``dig`` walks nested documents."""
    constant: Constant[int] = Constant(value=5)
    expect_equal(actual=constant(1, key=2), expected=5)
    document: object = {"a": [{"b": [10, 20]}]}
    expect_equal(
        actual=dig(document=document, path=("a", 0, "b", 1)),
        expected=20,
    )
    expect_equal(
        actual=dig_list(document=document, path=("a", 0, "b")),
        expected=[10, 20],
    )
