# Copyright (c) 2026
"""Coverage for the ``exactus/packages/model/examples`` demonstration."""

from __future__ import annotations

from io import StringIO
from runpy import run_module, run_path

import pytest

from exactus.packages.model.examples import run
from exactus.tests.common.support import expect_equal, expect_in


def test_example_main_runs_the_in_memory_demo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main`` compiles the schema, executes it, and prints the row.

    Args:
        monkeypatch: Redirects the module-level ``stdout`` binding.

    """
    buffer: StringIO = StringIO()
    monkeypatch.setattr(target=run, name="stdout", value=buffer)
    expect_equal(actual=run.main(), expected=0)
    output: str = buffer.getvalue()
    expect_in(member="CREATE TABLE", container=output)
    expect_in(member="INSERT INTO", container=output)
    expect_in(member="fetched:", container=output)
    expect_in(member="ship model migration", container=output)


def test_example_run_py_executes_as_script() -> None:
    """Execute ``run.py`` with ``__name__`` equal to ``__main__``."""
    with pytest.raises(expected_exception=SystemExit) as captured:
        _ = run_path(path_name=str(object=run.__file__), run_name="__main__")
    expect_equal(actual=captured.value.code, expected=0)


def test_examples_main_module_runs_the_demo() -> None:
    """Execute ``examples/__main__.py`` as the ``__main__`` module."""
    with pytest.raises(expected_exception=SystemExit) as captured:
        _ = run_module(
            mod_name="exactus.packages.model.examples",
            run_name="__main__",
        )
    expect_equal(actual=captured.value.code, expected=0)
