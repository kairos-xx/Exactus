#!/usr/bin/env python3
# Copyright (c) 2026 João Lopes.
"""Demonstrate source-preserving class method organization."""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from sys import path as sys_path
from sys import stdout
from textwrap import dedent
from typing import Final, final

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.organize.core import (
    PythonClassMethodReorderer,
    ReorderResult,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        source: Grouped module constant.

    """

    source: Final[str] = dedent(
        text=(
            '\n        class Example:\n            """Example demonstrating me'
            'thod organization metrics."""\n\n            def _helper(self, *,'
            ' value: int) -> int:\n                """Return a private result.'
            "\n\n                Args:\n                    value: Value retur"
            "ned unchanged.\n\n                Returns:\n                    T"
            'he given value.\n\n                """\n                return va'
            "lue\n\n            # Factory comment moves with the factory.\n   "
            "         @classmethod\n            def create(cls, *, value: int)"
            ' -> "Example":\n                """Create an example.\n\n        '
            "        Args:\n                    value: Creation setting.\n\n  "
            "              Returns:\n                    The new example.\n\n "
            '               """\n                return cls()\n\n            d'
            'ef __init__(self) -> None:\n                """Initialize the exa'
            'mple."""\n        '
        ),
    ).removeprefix("\n")


def main() -> int:
    """Print source before and after organization, then its metrics.

    Returns:
        ``0`` when the reorganized source renders cleanly.

    """
    result: ReorderResult = PythonClassMethodReorderer.reorder_source_detailed(
        source=Constants.source,
    )
    _ = stdout.write(
        f"Before:\n\n"
        f"{Constants.source}"
        f"\nAfter:\n\n"
        f"{result.source}"
        f"\nMetrics: "
        f"{result.metrics.methods_moved}"
        f"/"
        f"{result.metrics.methods_seen}"
        f" methods moved across "
        f"{result.metrics.classes_reordered}"
        f"/"
        f"{result.metrics.classes_seen}"
        f" classes ("
        f"{result.metrics.lines_moved}"
        f" lines relocated)\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
