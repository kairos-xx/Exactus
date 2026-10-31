"""Cover the shebang_update examples demonstration."""

from __future__ import annotations

from io import StringIO
from runpy import run_module, run_path
from shutil import rmtree
from typing import TYPE_CHECKING

import pytest

from exactus.packages.shebang_update import Settings, core
from exactus.packages.shebang_update.examples import run
from exactus.tests.common.support import expect_equal, expect_in

if TYPE_CHECKING:
    from pathlib import Path


def test_example_repairs_only_the_stale_script(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rebuild the demo project and fix only its stale shebang.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    work: Path = tmp_path / "demo_project"
    monkeypatch.setattr(target=run.Constants, name="work", value=work)
    sink: StringIO = StringIO()
    monkeypatch.setattr(target=run, name="stdout", value=sink)
    monkeypatch.setattr(target=core, name="stdout", value=StringIO())
    expect_equal(actual=run.main(), expected=0)
    expected: str = Settings(root=work).shebang.decode()
    expect_equal(
        actual=(work / "tools" / "build.py").read_bytes().splitlines()[0],
        expected=expected.encode(),
    )
    expect_equal(
        actual=(work / "tools" / "already_ok.py").read_bytes().splitlines()[0],
        expected=expected.encode(),
    )
    expect_in(
        member="previous/checkout",
        container=(work / ".venv" / "bin" / "activate.py").read_text(
            encoding="utf-8",
        ),
    )
    output: str = sink.getvalue()
    expect_in(member="scratch project:", container=output)
    expect_in(member="tools/build.py now reads:", container=output)


def test_example_module_runs_as_a_script() -> None:
    """Execute ``run.py`` with ``__name__`` equal to ``__main__``."""
    scratch: Path = run.Constants.work.parent
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


def test_examples_main_module_runs_the_demo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute ``examples/__main__.py`` as the ``__main__`` module.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    work: Path = tmp_path / "demo_project"
    monkeypatch.setattr(target=run.Constants, name="work", value=work)
    monkeypatch.setattr(target=run, name="stdout", value=StringIO())
    monkeypatch.setattr(target=core, name="stdout", value=StringIO())
    with pytest.raises(expected_exception=SystemExit) as captured:
        _ = run_module(
            mod_name="exactus.packages.shebang_update.examples",
            run_name="__main__",
        )
    expect_equal(actual=captured.value.code, expected=0)
    expect_equal(
        actual=(work / "tools" / "build.py").read_bytes().splitlines()[0],
        expected=Settings(root=work).shebang,
    )
