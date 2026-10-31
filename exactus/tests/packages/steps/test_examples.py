# Copyright (c) 2026
"""Coverage for the ``exactus/packages/steps/examples`` demonstration."""

from __future__ import annotations

from io import StringIO
from runpy import run_module, run_path
from shutil import rmtree
from typing import TYPE_CHECKING

import pytest

from exactus.packages.steps.examples import run
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_example_writes_and_prints_the_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Emit the simulated run and print the resulting trace.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    work: Path = tmp_path / ".scratch"
    destination: Path = work / "ARTIFACTS" / "steps.txt"
    monkeypatch.setattr(target=run.Constants, name="work", value=work)
    monkeypatch.setattr(
        target=run.Constants,
        name="destination",
        value=destination,
    )
    sink: StringIO = StringIO()
    monkeypatch.setattr(target=run, name="stdout", value=sink)
    expect_equal(actual=run.main(), expected=0)
    expect_true(condition=destination.is_file())
    rendered: str = destination.read_text(encoding="utf-8")
    expect_in(member="demo: run start", container=rendered)
    expect_in(member="stage: collect", container=rendered)
    expect_in(
        member="nested step_log reused the active log",
        container=rendered,
    )
    expect_in(member="demo: run finished", container=rendered)
    expect_false(condition=(work / "nested.txt").exists())
    output: str = sink.getvalue()
    expect_in(member="step trace:", container=output)
    expect_in(member="nested exists: False", container=output)


def test_example_module_runs_as_a_script() -> None:
    """Execute ``run.py`` with ``__name__`` equal to ``__main__``."""
    scratch: Path = run.Constants.work
    try:
        with pytest.raises(expected_exception=SystemExit) as captured:
            _ = run_path(
                path_name=str(object=run.__file__),
                run_name="__main__",
            )
    finally:
        if scratch.exists():
            rmtree(path=scratch)
    expect_equal(actual=captured.value.code, expected=0)


def test_examples_main_module_runs_the_demo() -> None:
    """Execute ``examples/__main__.py`` as the ``__main__`` module."""
    scratch: Path = run.Constants.work
    try:
        with pytest.raises(expected_exception=SystemExit) as captured:
            _ = run_module(
                mod_name="exactus.packages.steps.examples",
                run_name="__main__",
            )
    finally:
        if scratch.exists():
            rmtree(path=scratch)
    expect_equal(actual=captured.value.code, expected=0)


def test_package_main_module_runs_the_demo() -> None:
    """Execute the steps entry point as the ``__main__`` module."""
    scratch: Path = run.Constants.here.parent / ".scratch"
    try:
        with pytest.raises(expected_exception=SystemExit) as captured:
            _ = run_module(
                mod_name="exactus.packages.steps",
                run_name="__main__",
            )
    finally:
        if scratch.exists():
            rmtree(path=scratch)
    expect_equal(actual=captured.value.code, expected=0)
