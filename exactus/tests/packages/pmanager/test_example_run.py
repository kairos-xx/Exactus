# Copyright (c) 2026
"""Cover the bundled ``pmanager`` example entry point."""

from __future__ import annotations

from pathlib import Path
from runpy import run_path
from typing import Final, final

import pytest

from exactus.packages.pmanager.examples.api import run as api_example
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
        / "pmanager"
        / "examples"
        / "run.py"
    )


def test_example_module_runs_as_a_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the example file's ``__main__`` entry with a stubbed API run.

    Args:
        monkeypatch: Pytest patching helper.

    """
    observed: list[bool] = []

    def fake_main() -> int:
        """Record the delegation instead of running the pipeline.

        Returns:
            Always zero.

        """
        observed.append(True)
        return 0

    monkeypatch.setattr(target=api_example, name="main", value=fake_main)
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=Constants.example), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=0)
    expect_equal(actual=observed, expected=[True])
