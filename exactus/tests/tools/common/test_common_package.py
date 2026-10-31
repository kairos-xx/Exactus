# Copyright (c) 2026
"""The common package is a leaf: it imports nothing else from the repo."""

from __future__ import annotations

from ast import Import, ImportFrom, Module, parse, walk
from pathlib import Path
from typing import Final, final

from exactus.tests.common.support import expect_equal, expect_true


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        common: Grouped module constant.
        allowed: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[4]
    common: Final[Path] = root / "exactus" / "tools" / "common"
    allowed: Final[tuple[str, ...]] = (
        "exactus.tools.common.process_layer",
        "exactus.tools.common",
        "exactus.packages.argument_parser",
        "exactus.packages.markdown",
        "exactus.packages.model",
        "exactus.packages.pmanager",
        "exactus.packages.project_python",
        "exactus.packages.steps",
        "exactus.packages.tree",
        "exactus.tools.reports",
    )


def _repo_imports(*, path: Path) -> list[str]:
    """List repo-internal modules imported by one source file.

    Args:
        path: Python source file to inspect.

    Returns:
        Dotted module names that start with ``exactus``.

    """
    found: list[str] = []
    for node in walk(node=parse(source=path.read_text(encoding="utf-8"))):
        if isinstance(node, ImportFrom) and node.module:
            found.append(node.module)
        elif isinstance(node, Import):
            found.extend(alias.name for alias in node.names)
    return [name for name in found if name.split(sep=".")[0] == "exactus"]


def test_common_modules_exist() -> None:
    """The three primitives live under exactus/tools/common."""
    for name in ("sprint.py", "process_control.py", "json_types.py"):
        expect_true(
            condition=(Constants.common / name).is_file(),
            message=name,
        )


def test_common_imports_only_itself() -> None:
    """Common may import only itself plus its approved package helpers."""
    for path in sorted(Constants.common.glob(pattern="*.py")):
        for name in _repo_imports(path=path):
            expect_true(
                condition=name.startswith(Constants.allowed),
                message=f"{path.name} imports {name}",
            )


def test_common_init_has_no_imports() -> None:
    """The package initializer holds only a docstring and the future import."""
    tree: Module = parse(
        source=(Constants.common / "__init__.py").read_text(encoding="utf-8"),
    )
    modules: list[str | None] = [
        node.module for node in tree.body if isinstance(node, ImportFrom)
    ]
    expect_equal(actual=modules, expected=["__future__"])
    expect_equal(actual=len(tree.body), expected=2)
