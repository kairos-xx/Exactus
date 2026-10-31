# Copyright (c) 2026
"""Validate the shared scene_description assertion helpers."""

from __future__ import annotations

import pytest

from exactus.tests.packages.scene_description.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_raises,
    expect_true,
    fail,
    require_json_dict,
    require_json_list,
)


def test_fail_raises_assertion_error() -> None:
    """``fail`` always raises ``AssertionError`` with the message."""
    with pytest.raises(
        expected_exception=AssertionError,
        match="custom message",
    ):
        fail(message="custom message")


def test_expect_helpers_reject_bad_values() -> None:
    """Every expectation helper fails with a descriptive message."""
    with pytest.raises(expected_exception=AssertionError, match="true"):
        expect_true(condition=0)
    with pytest.raises(expected_exception=AssertionError, match="false"):
        expect_false(condition=1)
    with pytest.raises(expected_exception=AssertionError, match="2"):
        expect_equal(actual=1, expected=2)
    with pytest.raises(expected_exception=AssertionError, match="in"):
        expect_in(member="x", container=())
    with pytest.raises(expected_exception=AssertionError, match="None"):
        expect_none(value=1)


def test_require_json_helpers_validate_types() -> None:
    """JSON type helpers return values or reject non-matching types."""
    expect_equal(actual=require_json_dict(value={"a": 1}), expected={"a": 1})
    expect_equal(actual=require_json_list(value=[1, 2]), expected=[1, 2])
    with pytest.raises(expected_exception=AssertionError, match="object"):
        require_json_dict(value=[])
    with pytest.raises(expected_exception=AssertionError, match="array"):
        require_json_list(value={})


def test_expect_raises_returns_exception() -> None:
    """``expect_raises`` returns the exception or fails when absent."""
    expected: ValueError = ValueError("boom")

    def raises() -> object:
        """Raise the configured exception.

        Returns:
            Never returns.

        Raises:
            ValueError: Always.

        """
        raise expected

    expect_equal(
        actual=expect_raises(kind=ValueError, call=raises),
        expected=expected,
    )
    with pytest.raises(expected_exception=AssertionError, match="ValueError"):
        _ = expect_raises(kind=ValueError, call=lambda: None)


def test_expect_helpers_accept_good_values() -> None:
    """Every expectation helper passes on valid input."""
    expect_true(condition=1)
    expect_false(condition=0)
    expect_equal(actual=1, expected=1)
    expect_in(member="x", container=("x",))
    expect_none(value=None)
