# Copyright (c) 2026
"""Cover the bundled ``meaningful`` CLI example entry point."""

from __future__ import annotations

from pathlib import Path
from runpy import run_path
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.packages.meaningful.cli import MeaningfulCli
from exactus.tests.common.support import expect_equal, expect_true

if TYPE_CHECKING:
    from collections.abc import Sequence


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
        / "meaningful"
        / "examples"
        / "cli"
        / "run.py"
    )


def test_example_module_runs_as_a_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the example file's ``__main__`` entry with a stubbed CLI.

    Args:
        monkeypatch: Pytest patching helper.

    """
    observed: list[Sequence[str]] = []

    def fake_run(*, arguments: Sequence[str]) -> int:
        """Record the requested arguments instead of analyzing.

        Args:
            arguments: CLI tokens forwarded by the example.

        Returns:
            Always zero.

        """
        observed.append(tuple(arguments))
        return 0

    monkeypatch.setattr(
        target=MeaningfulCli,
        name="run",
        value=staticmethod(fake_run),
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=Constants.example), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=0)
    expect_true(condition=len(observed) == 1)
