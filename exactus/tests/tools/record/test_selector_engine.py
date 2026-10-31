# Copyright (c) 2026 Project contributors
"""Verify the ExtendedSelector package engine and its loader."""

from __future__ import annotations

from pathlib import Path
from typing import Final, final

import pytest

from exactus.tests.common.support import expect_false, expect_in, expect_true
from exactus.tools.record.selector_engine import engine_script, engine_source


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        package_files: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[4]
    package_files: Final[tuple[str, ...]] = (
        "extended-selector.js",
        "extended-selector-editor.js",
        "extended-selector-editor.css",
    )


@pytest.mark.parametrize("name", Constants.package_files)
def test_package_files_match_the_library(name: str) -> None:
    """Require each runtime resource in the ExtendedSelector package.

    Args:
        name: Required resource file name.

    """
    source: Path = (
        Constants.root
        / "exactus"
        / "packages"
        / "extended_selector"
        / "editor"
        / name
    )
    expect_true(condition=source.is_file())
    expect_true(condition=len(source.read_bytes()) > 0)


def test_engine_script_is_a_plain_script() -> None:
    """Publish the engine as one global without module syntax."""
    script: str = engine_script()
    expect_false(condition="export " in script)
    expect_in(
        member="class ExtendedSelector extends EventTarget",
        container=script,
    )
    expect_true(
        condition=script.rstrip().endswith(
            "globalThis.__EXACTUS_ES__ = ExtendedSelector;",
        ),
    )
    expect_in(member='static VERSION = "2.1.0"', container=engine_source())
