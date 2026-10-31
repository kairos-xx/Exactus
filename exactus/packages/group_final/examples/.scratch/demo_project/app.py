"""Demonstration module containing Final constants."""

from typing import Final


def make_name() -> str:
    """Build a demonstration value."""
    return "Exactus"


NAME: Final[str] = make_name()
COUNT: Final[int] = 3


def describe() -> str:
    """Return text that references both constants."""
    return f"{NAME}: {COUNT}"
