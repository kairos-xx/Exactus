# Copyright (c) 2026
"""Exercise the ``project_python`` re-exec example delegation chain."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from exactus.packages.project_python.examples import run
from exactus.tests.common.support import expect_equal, expect_not_equal

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


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
