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
            """\

        class Example:
            \"""Example demonstrating method organization metrics.\"""

            def _helper(self, *, value: int) -> int:
                \"""Return a private result.

                Args:
                    value: Value returned unchanged.

                Returns:
                    The given value.

                \"""
                return value

            # Factory comment moves with the factory.
            @classmethod
            def create(cls, *, value: int) -> "Example":
                \"""Create an example.

                Args:
                    value: Creation setting.

                Returns:
                    The new example.

                \"""
                return cls()

            def __init__(self) -> None:
                \"""Initialize the example.\"""
        """
        ),
    ).removeprefix("""\

""")


def main() -> int:
    """Print source before and after organization, then its metrics.

    Returns:
        ``0`` when the reorganized source renders cleanly.

    """
    result: ReorderResult = PythonClassMethodReorderer.reorder_source_detailed(
        source=Constants.source,
    )
    _ = stdout.write(
        f"""\
Before:

{Constants.source}
After:

{result.source}
Metrics: {result.metrics.methods_moved}/{result.metrics.methods_seen} methods \
moved across {result.metrics.classes_reordered}/{result.metrics.classes_seen} \
classes ({result.metrics.lines_moved} lines relocated)
""",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
