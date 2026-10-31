# Copyright (c) 2026
"""Enforce reusable package boundaries and approved integrations."""

from __future__ import annotations

from ast import AST, Import, ImportFrom, parse, walk
from pathlib import Path
from typing import Final, final

import pytest

from exactus.tests.common.support import expect_equal


@final
class Constants:
    """Group module-level constants.

    Attributes:
        repo: Grouped module constant.
        packages: Grouped module constant.
        common: Grouped module constant.
        common_dependencies: Grouped module constant.
        package_dependencies: Grouped module constant.

    """

    repo: Final[Path] = Path(__file__).resolve().parents[4]
    packages: Final[tuple[str, ...]] = (
        "exactus/packages/completion",
        "exactus/packages/markdown",
        "exactus/packages/rename_project",
        "exactus/packages/server",
        "exactus/packages/watch",
        "exactus/packages/project_python",
    )
    common: Final[str] = "exactus.tools.common"
    common_dependencies: Final[tuple[str, ...]] = (
        "exactus.tools.common.process_layer",
        "exactus.tools.common",
        "exactus.tools.reports",
        "exactus.packages.argument_parser",
        "exactus.packages.markdown",
        "exactus.packages.model",
        "exactus.packages.pmanager",
        "exactus.packages.project_python",
        "exactus.packages.steps",
        "exactus.packages.tree",
    )
    package_dependencies: Final[dict[str, tuple[str, ...]]] = {
        "exactus/packages/completion": ("exactus.packages.argument_parser",),
        "exactus/packages/markdown": ("exactus.packages.argument_parser",),
        "exactus/packages/rename_project": (
            "exactus.packages.argument_parser",
            "exactus.packages.model",
        ),
        "exactus/packages/server": ("exactus.packages.argument_parser",),
        "exactus/packages/watch": ("exactus.packages.argument_parser",),
    }


def _imported(*, path: Path) -> list[tuple[int, str]]:
    """List every imported module of a source file.

    Args:
        path: Python source file; nested and ``TYPE_CHECKING`` imports
            are included.

    Returns:
        Pairs of line number and absolute dotted module name.

    """
    names: list[tuple[int, str]] = []
    node: AST
    for node in walk(node=parse(source=path.read_text(encoding="utf-8"))):
        if isinstance(node, Import):
            names.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ImportFrom) and node.level == 0 and node.module:
            names.append((node.lineno, node.module))
            names.extend(
                (node.lineno, f"{node.module}.{alias.name}")
                for alias in node.names
            )
    return names


def _within(*, module: str, package: str) -> bool:
    """Report whether a module is a package or lives inside it.

    Args:
        module: Dotted module name.
        package: Dotted package name.

    Returns:
        True when ``module`` equals or is nested in ``package``.

    """
    return module == package or module.startswith(f"{package}.")


@pytest.mark.parametrize("folder", Constants.packages)
def test_packages_are_self_contained(folder: str) -> None:
    """Exactus packages never reach back into the project itself.

    Args:
        folder: Repo-relative independently reusable package.

    """
    offenders: list[str] = []
    for path in sorted((Constants.repo / folder).rglob(pattern="*.py")):
        for line, module in _imported(path=path):
            own: str = folder.replace("/", ".")
            allowed: tuple[str, ...] = (
                own,
                *Constants.package_dependencies.get(folder, ()),
            )
            if module.startswith(("exactus.", "scripts.")) and not any(
                _within(module=module, package=name) for name in allowed
            ):
                offenders.append(
                    f"{path.relative_to(Constants.repo)}:{line} {module}",
                )
    expect_equal(actual=offenders, expected=[])


def test_suite_tools_skip_build_scripts() -> None:
    """Runtime suite modules never depend on the project build scripts."""
    offenders: list[str] = []
    for path in sorted(
        (Constants.repo / "exactus/tools").rglob(pattern="*.py"),
    ):
        for line, module in _imported(path=path):
            if _within(
                module=module,
                package="exactus.scripts",
            ) or module.startswith("scripts."):
                offenders.append(
                    f"{path.relative_to(Constants.repo)}:{line} {module}",
                )
    expect_equal(actual=offenders, expected=[])


def test_tools_common_imports_only_itself() -> None:
    """``exactus.tools.common`` only touches markdown/reports helpers."""
    offenders: list[str] = []
    path: Path
    allowed: tuple[str, ...] = Constants.common_dependencies
    for path in sorted(
        (Constants.repo / "exactus/tools/common").rglob(pattern="*.py"),
    ):
        line: int
        module: str
        for line, module in _imported(path=path):
            if _within(module=module, package="exactus") and (
                not any(
                    _within(module=module, package=name) for name in allowed
                )
            ):
                offenders.append(
                    f"{path.relative_to(Constants.repo)}:{line} {module}",
                )
    expect_equal(actual=offenders, expected=[])
