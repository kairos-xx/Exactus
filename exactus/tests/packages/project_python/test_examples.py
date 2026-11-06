# Copyright (c) 2026
"""Exercise the ``project_python`` re-exec example delegation chain."""

from __future__ import annotations

from importlib import import_module, util
from pathlib import Path
from runpy import run_path
from sys import modules
from types import SimpleNamespace
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.packages.project_python.examples import run
from exactus.tests.common.support import expect_equal, expect_not_equal

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType


@final
class Constants:
    """Group module-level constants.

    Attributes:
        repo: Grouped module constant.
        script: Grouped module constant.

    """

    repo: Final[Path] = Path(__file__).resolve().parents[4]
    script: Final[Path] = (
        repo
        / "exactus"
        / "packages"
        / "project_python"
        / "examples"
        / "__main__.py"
    )


def test_example_switches_venv_then_runs_the_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main`` re-execs into the venv and invokes the real tool.

    Args:
        monkeypatch: Replaces dynamic imports with recording stubs.

    """
    calls: list[str] = []

    def switch() -> None:
        """Record the virtual-environment switch request."""
        calls.append("switch")

    def tool() -> int:
        """Return a synthetic tool exit status.

        Returns:
            Fixed success code.

        """
        calls.append("tool")
        return 0

    def import_stub(*, name: str) -> object:
        """Return stub modules for the two dynamic imports.

        Args:
            name: Module path requested by the example.

        Returns:
            Namespace exposing the attribute the example reads.

        """
        calls.append(name)
        if name == "exactus.packages.project_python":
            return SimpleNamespace(switch_to_project_venv=switch)
        return SimpleNamespace(main=tool)

    monkeypatch.setattr(target=run, name="import_module", value=import_stub)
    expect_equal(actual=run.main(), expected=0)
    expect_equal(
        actual=calls,
        expected=[
            "exactus.packages.project_python",
            "switch",
            "exactus.packages.package.build",
            "tool",
        ],
    )


def test_example_swaps_and_restores_build_constants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main`` redirects ``Constants`` paths for the demo and restores them.

    Args:
        tmp_path: Pytest fixture used by this test.
        monkeypatch: Replaces dynamic imports with recording stubs.

    """
    del tmp_path
    constants: SimpleNamespace = SimpleNamespace(
        check="original-check",
        dist="original-dist",
        tree="original-tree",
    )
    seen: dict[str, object] = {}

    def switch() -> None:
        """Accept the virtual-environment switch request."""

    def tool() -> int:
        """Capture the swapped constants while the tool runs.

        Returns:
            Fixed tool exit status.

        """
        seen["check"] = constants.check
        seen["dist"] = constants.dist
        seen["tree"] = constants.tree
        return 7

    def import_stub(*, name: str) -> object:
        """Return stub modules for the two dynamic imports.

        Args:
            name: Module path requested by the example.

        Returns:
            Namespace exposing the attribute the example reads.

        """
        if name == "exactus.packages.project_python":
            return SimpleNamespace(switch_to_project_venv=switch)
        return SimpleNamespace(main=tool, Constants=constants)

    monkeypatch.setattr(target=run, name="import_module", value=import_stub)
    expect_equal(actual=run.main(), expected=7)
    expect_equal(actual=constants.check, expected="original-check")
    expect_equal(actual=constants.dist, expected="original-dist")
    expect_equal(actual=constants.tree, expected="original-tree")
    expect_not_equal(actual=seen["check"], expected="original-check")
    expect_not_equal(actual=seen["dist"], expected="original-dist")
    expect_not_equal(actual=seen["tree"], expected="original-tree")


def test_examples_main_switches_venv_and_delegates_to_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``__main__`` shim switches environments then exits with the tool.

    Args:
        monkeypatch: Replaces dynamic imports with recording stubs.

    """
    calls: list[str] = []
    real_import: Callable[..., ModuleType] = import_module

    def switch() -> None:
        """Record the virtual-environment switch request."""
        calls.append("switch")

    def tool() -> int:
        """Return a synthetic tool exit status.

        Returns:
            Fixed example exit code.

        """
        calls.append("tool")
        return 5

    def import_stub(name: str, package: str | None = None) -> object:
        """Stub the switch and example-module imports, delegate the rest.

        Args:
            name: Requested module name.
            package: Anchor package for relative imports.

        Returns:
            The real import result for every other candidate.

        """
        calls.append(name)
        if name == "exactus.packages.project_python":
            return SimpleNamespace(switch_to_project_venv=switch)
        if name == "exactus.packages.project_python.examples.run":
            return SimpleNamespace(main=tool)
        return real_import(name, package=package)

    monkeypatch.setattr(
        target=modules["importlib"],
        name="import_module",
        value=import_stub,
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=Constants.script), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=5)
    expect_equal(
        actual=calls,
        expected=[
            "exactus.packages.project_python",
            "switch",
            "exactus.packages.project_python.examples.run",
            "tool",
        ],
    )


def test_examples_main_falls_back_to_unqualified_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ImportError`` on the qualified name retries with ``project_python``.

    Args:
        monkeypatch: Replaces dynamic imports with recording stubs.

    """
    calls: list[str] = []
    real_import: Callable[..., ModuleType] = import_module

    def switch() -> None:
        """Record the virtual-environment switch request."""
        calls.append("switch")

    def tool() -> int:
        """Return a synthetic tool exit status.

        Returns:
            Fixed example exit code.

        """
        calls.append("tool")
        return 0

    def import_stub(name: str, package: str | None = None) -> object:
        """Fail the qualified import, stub the unqualified fallback.

        Args:
            name: Requested module name.
            package: Anchor package for relative imports.

        Returns:
            The real import result for every other candidate.

        Raises:
            ImportError: For the qualified
                ``exactus.packages.project_python`` name.

        """
        if name == "exactus.packages.project_python":
            raise ImportError(name)
        if name == "project_python":
            calls.append(name)
            return SimpleNamespace(switch_to_project_venv=switch)
        if name == "exactus.packages.project_python.examples.run":
            return SimpleNamespace(main=tool)
        return real_import(name, package=package)

    monkeypatch.setattr(
        target=modules["importlib"],
        name="import_module",
        value=import_stub,
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=Constants.script), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=0)
    expect_equal(actual=calls, expected=["project_python", "switch", "tool"])


def test_examples_main_runs_the_tool_without_a_switch_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both candidates fail the tool still runs and propagates its exit.

    Args:
        monkeypatch: Replaces dynamic imports with recording stubs.

    """
    calls: list[str] = []
    real_import: Callable[..., ModuleType] = import_module

    def tool() -> int:
        """Return a synthetic tool exit status.

        Returns:
            Fixed example exit code.

        """
        calls.append("tool")
        return 3

    def import_stub(name: str, package: str | None = None) -> object:
        """Fail both switch candidates and stub the example module.

        Args:
            name: Requested module name.
            package: Anchor package for relative imports.

        Returns:
            The real import result for every other candidate.

        Raises:
            ImportError: For either virtual-environment switch candidate.

        """
        if name in ("exactus.packages.project_python", "project_python"):
            raise ImportError(name)
        if name == "exactus.packages.project_python.examples.run":
            return SimpleNamespace(main=tool)
        return real_import(name, package=package)

    monkeypatch.setattr(
        target=modules["importlib"],
        name="import_module",
        value=import_stub,
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=Constants.script), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=3)
    expect_equal(actual=calls, expected=["tool"])


def test_examples_main_prepends_repo_root_without_exactus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing ``exactus`` install bootstraps ``sys.path`` from ``__file__``.

    Args:
        monkeypatch: Replaces the spec lookup and dynamic imports with stubs.

    """
    original: list[str] = list(modules["sys"].path)
    copied: list[str] = list(original)
    calls: list[str] = []
    real_import: Callable[..., ModuleType] = import_module

    def _missing_spec(*_ignored: object, **_named: object) -> None:
        """Report ``exactus`` as uninstalled for every lookup.

        Args:
            _ignored: Positional arguments (unused).
            _named: Keyword arguments (unused).

        """

    def switch() -> None:
        """Record the virtual-environment switch request."""
        calls.append("switch")

    def tool() -> int:
        """Return a synthetic tool exit status.

        Returns:
            Fixed example exit code.

        """
        calls.append("tool")
        return 0

    def import_stub(name: str, package: str | None = None) -> object:
        """Stub the switch and example-module imports, delegate the rest.

        Args:
            name: Requested module name.
            package: Anchor package for relative imports.

        Returns:
            The real import result for every other candidate.

        """
        if name == "exactus.packages.project_python":
            return SimpleNamespace(switch_to_project_venv=switch)
        if name == "exactus.packages.project_python.examples.run":
            return SimpleNamespace(main=tool)
        return real_import(name, package=package)

    monkeypatch.setattr(target=util, name="find_spec", value=_missing_spec)
    monkeypatch.setattr(target=modules["sys"], name="path", value=copied)
    monkeypatch.setattr(
        target=modules["importlib"],
        name="import_module",
        value=import_stub,
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=Constants.script), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=0)
    expect_equal(actual=calls, expected=["switch", "tool"])
    expect_equal(
        actual=copied,
        expected=[str(object=Constants.script.parents[4]), *original],
    )
