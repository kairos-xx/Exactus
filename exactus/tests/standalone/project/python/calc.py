"""Minimal arithmetic for the standalone fixture project."""

from __future__ import annotations


def add(*, left: int, right: int) -> int:
    """Add two integers.

    Args:
        left: First operand.
        right: Second operand.

    Returns:
        The sum of both operands.

    """
    return left + right


def is_even(*, value: int) -> bool:
    """Report whether an integer is even.

    Args:
        value: Integer under test.

    Returns:
        ``True`` when ``value`` divides evenly by two.

    """
    return value % 2 == 0
