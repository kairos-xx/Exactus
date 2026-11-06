# Copyright (c) 2026
"""Exercise the recursive-launch containment guard."""

from __future__ import annotations

import pytest

from exactus.tests.common.support import expect_equal
from exactus.tools.common.nesting_guard import (
    Constants,
    NestingError,
    enter,
)


def test_first_generation_starts_at_one() -> None:
    """A process with no inherited depth is generation one."""
    environment: dict[str, str] = {}
    expect_equal(actual=enter(environment=environment), expected=1)
    expect_equal(
        actual=environment[Constants.depth_variable],
        expected="1",
    )


def test_each_generation_increments_the_inherited_depth() -> None:
    """Children inherit the parent's depth plus one."""
    environment: dict[str, str] = {Constants.depth_variable: "4"}
    expect_equal(actual=enter(environment=environment), expected=5)


def test_malformed_depth_restarts_from_zero() -> None:
    """A corrupt counter never blocks a legitimate launch."""
    environment: dict[str, str] = {Constants.depth_variable: "many"}
    expect_equal(actual=enter(environment=environment), expected=1)


def test_limit_refuses_another_generation() -> None:
    """A process inheriting the maximum depth refuses to start."""
    environment: dict[str, str] = {
        Constants.depth_variable: str(object=Constants.max_depth),
    }
    with pytest.raises(
        expected_exception=NestingError,
        match="recursive Exactus launch detected",
    ):
        _ = enter(environment=environment)
    expect_equal(
        actual=environment[Constants.depth_variable],
        expected=str(object=Constants.max_depth),
    )


def test_last_allowed_generation_still_starts() -> None:
    """One below the limit is the deepest process that may run."""
    environment: dict[str, str] = {
        Constants.depth_variable: str(object=Constants.max_depth - 1),
    }
    expect_equal(
        actual=enter(environment=environment),
        expected=Constants.max_depth,
    )


def test_repeated_entry_from_one_process_does_not_inflate_depth() -> None:
    """In-process callers can enter far more often than the limit."""
    environment: dict[str, str] = {}
    depths: set[int] = {
        enter(environment=environment, process=4242)
        for _ in range(Constants.max_depth * 3)
    }
    expect_equal(actual=depths, expected={1})


def test_a_child_process_counts_one_generation_deeper() -> None:
    """A different pid inheriting the environment increments the depth."""
    environment: dict[str, str] = {}
    expect_equal(actual=enter(environment=environment, process=1), expected=1)
    expect_equal(actual=enter(environment=environment, process=2), expected=2)
    expect_equal(actual=enter(environment=environment, process=2), expected=2)
    expect_equal(actual=enter(environment=environment, process=3), expected=3)
