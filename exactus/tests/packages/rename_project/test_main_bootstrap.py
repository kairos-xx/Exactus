# Copyright (c) 2026
"""Cover the rename_project package bootstrap entry points."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from runpy import run_path
from sys import modules, path
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.tests.common.support import expect_equal, expect_true

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType


@final
class Constants:
    """Group module-level constants.

    Attributes:
        package: Grouped module constant.
        main_module: Grouped module constant.
        cli_example: Grouped module constant.

    """

    package: Final[Path] = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "rename_project"
    )
    main_module: Final[Path] = package / "__main__.py"
    cli_example: Final[Path] = (
        package / "examples" / "project" / "src" / "project" / "cli.py"
    )


def test_main_attribute_imports_the_cli_entry_point() -> None:
    """Resolve ``main`` through the package ``__getattr__`` hook."""
    package: ModuleType = import_module(name="exactus.packages.rename_project")
    entry: object = package.main
    expect_true(condition=callable(entry))


def test_getattr_rejects_unknown_attributes() -> None:
    """Raise ``AttributeError`` for names the package does not export."""
    package: ModuleType = import_module(name="exactus.packages.rename_project")
    with pytest.raises(expected_exception=AttributeError, match="missing"):
        _ = package.missing_attribute


def test_main_module_uses_the_secondary_import_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fall back to the unqualified ``project_python`` import candidate.

    Args:
        monkeypatch: Pytest patching helper.

    """
    real_import: Callable[..., ModuleType] = import_module

    def fail_primary(name: str, package: str | None = None) -> ModuleType:
        """Fail only the qualified ``exactus.packages.project_python`` lookup.

        Args:
            name: Requested module name.
            package: Anchor package for relative imports.

        Returns:
            The real import result for every other candidate.

        Raises:
            ImportError: When ``exactus.packages.project_python`` is requested.

        """
        if name == "exactus.packages.project_python":
            raise ImportError(name)
        return real_import(name, package=package)

    monkeypatch.setattr(
        target=modules["importlib"],
        name="import_module",
        value=fail_primary,
    )
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["rename_project", "--help"],
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(
            path_name=str(object=Constants.main_module),
            run_name="__main__",
        )
    expect_equal(actual=raised.value.code, expected=0)


def test_main_module_survives_without_project_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Set ``switch`` to ``None`` when both import candidates fail.

    Args:
        monkeypatch: Pytest patching helper.

    """
    real_import: Callable[..., ModuleType] = import_module

    def fail_everything(name: str, package: str | None = None) -> ModuleType:
        """Reject the virtual-environment bootstrap lookups.

        Args:
            name: Requested module name.
            package: Anchor package for relative imports.

        Returns:
            The real import result for every other candidate.

        Raises:
            ImportError: When a ``project_python`` candidate is requested.

        """
        if name in {"exactus.packages.project_python", "project_python"}:
            raise ImportError(name)
        return real_import(name, package=package)

    monkeypatch.setattr(
        target=modules["importlib"],
        name="import_module",
        value=fail_everything,
    )
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["rename_project", "--help"],
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(
            path_name=str(object=Constants.main_module),
            run_name="__main__",
        )
    expect_equal(actual=raised.value.code, expected=0)


def test_cli_example_runs_as_a_script(monkeypatch: pytest.MonkeyPatch) -> None:
    """Execute the bundled example CLI module as ``__main__``.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=modules["sys"],
        name="path",
        value=[str(object=Constants.cli_example.parent.parent), *path],
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(
            path_name=str(object=Constants.cli_example),
            run_name="__main__",
        )
    expect_equal(actual=raised.value.code, expected=0)
