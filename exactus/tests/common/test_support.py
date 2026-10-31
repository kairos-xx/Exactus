# Copyright (c) 2026
"""The shared assertion and reflection helpers fail loudly when violated."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from exactus.tests.common import support as sp

if TYPE_CHECKING:
    from collections.abc import Callable


def _raises(*, check: Callable[[], object]) -> None:
    """Require ``check`` to raise ``AssertionError``.

    Args:
        check: Zero-argument callable expected to fail.

    """
    with pytest.raises(expected_exception=AssertionError):
        _ = check()


def test_helpers_pass_on_valid_input() -> None:
    """Valid expectations return without raising."""
    sp.expect_true(condition=True)
    sp.expect_false(condition=False)
    sp.expect_equal(actual=1, expected=1)
    sp.expect_not_equal(actual=1, expected=2)
    sp.expect_in(member="a", container="abc")
    sp.expect_not_in(member="z", container="abc")
    sp.expect_none(value=None)
    sp.expect_equal(actual=sp.require(value=3), expected=3)
    sp.expect_equal(actual=sp.require_type(value="x", kind=str), expected="x")


def test_helpers_raise_on_violations() -> None:
    """Each helper reports a violated expectation."""
    _raises(check=lambda: sp.fail(message="x"))
    _raises(check=lambda: sp.expect_true(condition=False))
    _raises(check=lambda: sp.expect_false(condition=True))
    _raises(check=lambda: sp.expect_equal(actual=1, expected=2))
    _raises(check=lambda: sp.expect_not_equal(actual=1, expected=1))
    _raises(check=lambda: sp.expect_in(member="z", container="abc"))
    _raises(check=lambda: sp.expect_not_in(member="a", container="abc"))
    _raises(check=lambda: sp.expect_none(value=1))
    _raises(check=lambda: sp.require(value=None))
    _raises(check=lambda: sp.require_type(value=1, kind=str))
