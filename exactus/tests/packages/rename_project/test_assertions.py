"""Every assertion helper passes on good input and fails on bad input."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from exactus.tests.packages.rename_project.assertions import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_equal,
    expect_not_in,
    expect_not_none,
    expect_true,
    fail,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def test_helpers_accept_valid_expectations() -> None:
    """Helpers return quietly when the expectation holds."""
    expect_true(condition=True)
    expect_false(condition=False)
    expect_equal(actual=1, expected=1)
    expect_not_equal(actual=1, expected=2)
    expect_in(member="a", container="abc")
    expect_not_in(member="z", container="abc")
    expect_none(value=None)
    expect_not_none(value=0)


def test_helpers_raise_on_violated_expectations() -> None:
    """Each helper raises ``AssertionError`` when the expectation fails."""
    failures: tuple[Callable[[], object], ...] = (
        lambda: expect_true(condition=False, message="x"),
        lambda: expect_false(condition=True, message="x"),
        lambda: expect_equal(actual=1, expected=2, message="x"),
        lambda: expect_not_equal(actual=1, expected=1, message="x"),
        lambda: expect_in(member="z", container="abc", message="x"),
        lambda: expect_not_in(member="a", container="abc", message="x"),
        lambda: expect_none(value=1, message="x"),
        lambda: expect_not_none(value=None, message="x"),
        lambda: fail(message="x"),
    )
    for failure in failures:
        with pytest.raises(expected_exception=AssertionError):
            failure()
