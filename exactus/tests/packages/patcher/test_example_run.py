# Copyright (c) 2026
"""Cover the bundled ``patcher`` example entry point."""

from __future__ import annotations

from pathlib import Path
from runpy import run_path
from typing import Final, final

import pytest

from exactus.tests.common.support import expect_equal


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
        / "patcher"
        / "examples"
        / "run.py"
    )


def test_example_module_runs_as_a_script() -> None:
    """Execute the example file's ``__main__`` entry for real."""
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=Constants.example), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=0)
