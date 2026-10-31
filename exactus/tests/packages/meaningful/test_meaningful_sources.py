# Copyright (c) 2026
"""Execute package entry points required by meaningful coverage policy."""

from __future__ import annotations

from runpy import run_module
from sys import modules
from typing import TYPE_CHECKING

import pytest

from exactus.packages import project_python
from exactus.tests.common.support import expect_equal

if TYPE_CHECKING:
    from types import ModuleType


@pytest.mark.parametrize(
    argnames=("module", "arguments", "expected"),
    argvalues=[
        (
            "exactus.packages.completion",
            ("bash", "--command", "demo", "--launcher", "demo"),
            0,
        ),
        ("exactus.packages.http_process", ("--help",), 0),
        ("exactus.packages.project_python", (), 2),
        ("exactus.packages.screenshot", ("--help",), 0),
        ("exactus.packages.server", ("--help",), 0),
    ],
)
def test_packages_cli_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
    module: str,
    arguments: tuple[str, ...],
    expected: int,
) -> None:
    """Execute one package CLI through its real ``__main__`` module.

    Args:
        monkeypatch: Replaces process arguments for the entry point.
        module: Package whose entry point runs.
        arguments: Command-line arguments supplied to the package.
        expected: Expected ``SystemExit`` status.

    """
    monkeypatch.setattr(
        target=__import__("sys"),
        name="argv",
        value=[module, *arguments],
        raising=False,
    )
    monkeypatch.setattr(
        target=project_python,
        name="switch_to_project_venv",
        value=lambda: None,
    )
    with pytest.raises(expected_exception=SystemExit) as captured:
        run_module(mod_name=module, run_name="__main__")
    expect_equal(actual=captured.value.code, expected=expected)


@pytest.mark.parametrize(
    argnames="module",
    argvalues=[
        "exactus.packages.guard.examples.run",
        "exactus.packages.rename_project.cli_help",
        "exactus.packages.visual_cause.examples.run",
        "exactus.packages.visual_cause.examples.validate_results",
    ],
)
def test_packages_support_module_executes(module: str) -> None:
    """Execute one support module without invoking its guarded CLI.

    Args:
        module: Support module to execute.

    """
    namespace: dict[str, object] = run_module(
        mod_name=module,
        run_name="coverage_probe",
    )
    expect_equal(actual=namespace["__name__"], expected="coverage_probe")


def test_rename_project_entrypoint_bootstraps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the rename-project bootstrap and delegate to ``main``.

    Args:
        monkeypatch: Prevents the bootstrap from replacing the test process.

    """
    existing: ModuleType | None = modules.get("rename_project")
    monkeypatch.setattr(
        target=project_python,
        name="switch_to_project_venv",
        value=lambda: None,
    )
    monkeypatch.setattr(
        target=__import__("sys"),
        name="argv",
        value=["rename_project", "--help"],
        raising=False,
    )
    try:
        with pytest.raises(expected_exception=SystemExit) as captured:
            run_module(
                mod_name="exactus.packages.rename_project",
                run_name="__main__",
            )
        expect_equal(actual=captured.value.code, expected=0)
    finally:
        if existing is None:
            modules.pop("rename_project", None)
        else:
            modules["rename_project"] = existing
