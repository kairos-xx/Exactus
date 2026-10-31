# Copyright (c) 2026
"""Cover the bundled ``markdown`` example entry point."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from runpy import run_path
from sys import modules
from typing import Final, final

import pytest

from exactus.packages import markdown as markdown_package
from exactus.tests.common.support import expect_equal, expect_in


@final
class Constants:
    """Group module-level constants.

    Attributes:
        example: Grouped module constant.
        assets: Grouped module constant.

    """

    example: Final[Path] = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "markdown"
        / "examples"
        / "run.py"
    )
    assets: Final[Path] = example.parent / "assets"


def test_example_module_runs_as_a_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the example file's ``__main__`` entry against golden output.

    Args:
        monkeypatch: Pytest patching helper.

    """
    output: StringIO = StringIO()
    monkeypatch.setattr(target=modules["sys"], name="stdout", value=output)
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=Constants.example), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=0)
    golden: str = (Constants.assets / "expected.md").read_text(
        encoding="utf-8",
    )
    expect_equal(actual=output.getvalue(), expected=golden)


def test_example_module_reports_a_golden_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A render that differs from the golden file exits with one.

    Args:
        monkeypatch: Pytest patching helper.

    """
    errors: StringIO = StringIO()

    def mismatch(*, result: Path, template: Path, mapping: Path) -> str:
        """Return output that differs from the golden file.

        Args:
            result: Result document path (unused).
            template: Template path (unused).
            mapping: Field mapping path (unused).

        Returns:
            Fixed mismatched text.

        """
        _ = result
        _ = template
        _ = mapping
        return "different\n"

    monkeypatch.setattr(
        target=markdown_package,
        name="render_report",
        value=mismatch,
    )
    monkeypatch.setattr(target=modules["sys"], name="stdout", value=StringIO())
    monkeypatch.setattr(target=modules["sys"], name="stderr", value=errors)
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=Constants.example), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=1)
    expect_in(member="differs", container=errors.getvalue())
