# Copyright (c) 2026
"""Cover the bundled ``all_lints`` example entry point."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from runpy import run_path
from sys import modules
from typing import Final, final

import pytest

from exactus.tests.common.support import expect_equal, expect_in


@final
class Constants:
    """Group module-level constants.

    Attributes:
        example: Grouped module constant.

    """

    example: Final[Path] = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "all_lints"
        / "examples"
        / "run.py"
    )


def test_example_module_runs_as_a_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the example file's ``__main__`` entry for real.

    Args:
        monkeypatch: Pytest patching helper.

    """
    output: StringIO = StringIO()
    monkeypatch.setattr(target=modules["sys"], name="stdout", value=output)
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=Constants.example), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=0)
    rendered: str = output.getvalue()
    expect_in(member="scratch project", container=rendered)
    expect_in(member="merged ruff excludes", container=rendered)
    expect_in(member="commands for app.py", container=rendered)
    expect_in(member='"tool": "ruff"', container=rendered)
