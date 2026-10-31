# Copyright (c) 2026
"""Validate every browser-side JavaScript source asset."""

from pathlib import Path
from subprocess import CompletedProcess, run
from typing import Final, final

import pytest

from exactus.tests.packages.visual_cause.support import (
    expect_equal,
    expect_true,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        js_root: Grouped module constant.
        js_files: Grouped module constant.

    """

    js_root: Final[Path] = (
        Path(__file__).parents[4]
        / "exactus"
        / "packages"
        / "visual_cause"
        / "js"
    )
    js_files: Final[tuple[Path, ...]] = tuple(
        sorted(js_root.glob(pattern="*.js")),
    )


def test_all_browser_js_assets_are_discovered() -> None:
    """Require every browser program asset to participate in tests."""
    expect_true(condition=Constants.js_files)
    expect_equal(
        actual={path.name for path in Constants.js_files},
        expected={
            "container_rules.js",
            "css_variables.js",
            "disable_declaration.js",
            "disable_declarations.js",
            "disable_rule.js",
            "dom_elements.js",
            "elements.js",
            "install_helpers.js",
            "override_element.js",
            "prepare.js",
            "rules.js",
        },
    )


@pytest.mark.parametrize(
    "path",
    Constants.js_files,
    ids=lambda path: path.name,
)
def test_browser_js_parses(path: Path) -> None:
    """Require every browser JavaScript file to parse successfully.

    Args:
        path: JavaScript source file under test.

    """
    source: str = path.read_text(encoding="utf-8")
    completed: CompletedProcess[str] = run(
        args=["node", "--check", "--input-type=commonjs"],
        input=f"const __exactusBrowserProgram = {source};\n",
        text=True,
        capture_output=True,
        check=False,
    )
    expect_equal(
        actual=completed.returncode,
        expected=0,
        message=completed.stderr,
    )
