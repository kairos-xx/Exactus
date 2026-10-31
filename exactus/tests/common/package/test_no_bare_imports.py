# Copyright (c) 2026
"""No exactus tool module imports a sibling through a bare module name."""

from __future__ import annotations

from ast import ImportFrom, Module, parse, walk
from pathlib import Path
from typing import Final, final

from exactus.tests.common.support import expect_equal


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        tools: Grouped module constant.
        siblings: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[4]
    tools: Final[Path] = root / "exactus" / "tools"
    siblings: Final[frozenset[str]] = frozenset(
        path.stem for path in tools.rglob(pattern="*.py")
    )


def test_no_bare_sibling_imports() -> None:
    """``from _common import x`` style imports are forbidden."""
    offenders: list[str] = []
    for path in sorted(Constants.tools.rglob(pattern="*.py")):
        tree: Module = parse(source=path.read_text(encoding="utf-8"))
        offenders.extend(
            f"{path.relative_to(Constants.tools)}:{node.lineno}"
            for node in walk(node=tree)
            if isinstance(node, ImportFrom)
            and node.level == 0
            and (node.module in Constants.siblings)
        )
    expect_equal(actual=offenders, expected=[])
