"""Tests for the fixture project's ``python.calc`` module."""

from __future__ import annotations

from typing import Final, final

from python.calc import add, is_even


@final
class Constants:
    """Group module-level constants.

    Attributes:
        sum_expected: Grouped module constant.

    """

    sum_expected: Final[int] = 5


def _expect(*, condition: bool, message: str) -> None:
    """Raise ``AssertionError`` when ``condition`` is false.

    Args:
        condition: Evaluated expectation.
        message: Failure description.

    Raises:
        AssertionError: When ``condition`` is false.

    """
    if not condition:
        raise AssertionError(message)


def test_add_sums_operands() -> None:
    """``add`` returns the sum of its operands."""
    _expect(
        condition=add(left=2, right=3) == Constants.sum_expected,
        message="add did not sum its operands",
    )


def test_is_even_flags_parity() -> None:
    """``is_even`` reports even and odd values."""
    _expect(condition=is_even(value=4), message="4 should be even")
    _expect(condition=not is_even(value=5), message="5 should be odd")
