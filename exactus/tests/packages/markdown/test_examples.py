# Copyright (c) 2026
"""The generic engine example renders to its checked-in expected output."""

from __future__ import annotations

from pathlib import Path
from typing import Final, final

from exactus.packages.markdown import render_report
from exactus.packages.markdown.examples import run
from exactus.tests.common.support import expect_equal


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        examples: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[4]
    examples: Final[Path] = (
        root / "exactus" / "packages" / "markdown" / "examples" / "assets"
    )


def test_generic_example_matches_golden() -> None:
    """The example template reproduces the golden Markdown exactly."""
    rendered: str = render_report(
        result=Constants.examples / "data.json",
        template=Constants.examples / "template.md",
        mapping=Constants.examples / "mapping.json",
    )
    golden: str = (Constants.examples / "expected.md").read_text(
        encoding="utf-8",
    )
    expect_equal(actual=rendered, expected=golden)


def test_run_script_returns_zero() -> None:
    """The runnable example renders the bundle and matches its golden."""
    expect_equal(actual=run.main(), expected=0)
