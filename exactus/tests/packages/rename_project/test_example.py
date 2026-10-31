# Copyright (c) 2026
"""The ``examples/run.py`` demo renames only a throwaway copy."""

from __future__ import annotations

from importlib import import_module
from sys import path as sys_path
from typing import TYPE_CHECKING

from exactus.packages.rename_project.examples import run
from exactus.tests.packages.rename_project.assertions import (
    expect_equal,
    expect_in,
    expect_true,
)

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

    import pytest


def test_example_renames_only_the_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The demo leaves a renamed ``demo_app`` and a pristine template.

    Args:
        tmp_path: Isolated scratch destination.
        monkeypatch: Redirects the example's work directory.

    """
    work: Path = tmp_path / "scratch"
    monkeypatch.setattr(target=run.Constants, name="work", value=work)
    expect_equal(actual=run.main(), expected=0)
    renamed: Path = work / "demo_app"
    expect_true(condition=(renamed / "pyproject.toml").is_file())
    expect_in(
        member='name = "demo-app"',
        container=(renamed / "pyproject.toml").read_text(encoding="utf-8"),
    )
    module: Path = renamed / "src" / "demo_app" / "cli.py"
    expect_true(condition=module.is_file())
    expect_in(
        member="from demo_app import Constants, DemoApp",
        container=module.read_text(encoding="utf-8"),
    )
    template_module: Path = (
        run.Constants.template / "src" / "project" / "cli.py"
    )
    expect_in(
        member="from project import Constants, Project",
        container=template_module.read_text(encoding="utf-8"),
    )


def test_template_cli_prints_the_project_banner(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The template ``project.cli`` runs its banner entry point.

    Args:
        capsys: Captured banner output.

    """
    source: Path = run.Constants.template / "src"
    sys_path.insert(0, str(object=source))
    try:
        cli: ModuleType = import_module(name="project.cli")
    finally:
        sys_path.remove(str(object=source))
    expect_equal(actual=cli.main(), expected=0)
    expect_in(member="Project 0.1.0", container=capsys.readouterr().out)
