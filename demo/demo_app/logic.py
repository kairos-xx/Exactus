# Copyright (c) 2026
"""Pure demo behavior shared with the Python test fixture."""

from __future__ import annotations


def next_status(*, value: str) -> str:
    """Return the next demo status label.

    Args:
        value: Current status label.

    Returns:
        ``Active`` for ``Ready`` and ``Ready`` otherwise.

    """
    return "Active" if value == "Ready" else "Ready"
