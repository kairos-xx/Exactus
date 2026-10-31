# Copyright (c) 2026
"""Thin dispatch modules and path-plumbing files."""

from __future__ import annotations

from pathlib import Path
from runpy import run_path
from sys import path as sys_path
from typing import Final, final
from unittest.mock import patch

import pytest

from exactus import __main__ as entry
from exactus.tests.common.support import expect_equal, expect_true

pytestmark: pytest.MarkDecorator = pytest.mark.usefixtures("isolated_check")


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[4]


def test_package_entrypoint_owns_dispatcher() -> None:
    """The package entrypoint owns the CLI implementation directly."""
    expect_equal(actual=entry.Check.__module__, expected="exactus.__main__")
    expect_equal(
        actual=entry.Application.__module__,
        expected="exactus.__main__",
    )


def test_module_runs_as_script() -> None:
    """Executing the module as ``__main__`` exits via the dispatcher."""
    with (
        patch(target="sys.argv", new=["exactus", "--list-pipelines"]),
        pytest.raises(expected_exception=SystemExit) as caught,
    ):
        _ = run_path(
            path_name=str(object=Constants.root / "exactus" / "__main__.py"),
            run_name="__main__",
        )
    expect_equal(actual=caught.value.code, expected=0)


@pytest.mark.parametrize(
    "module",
    [
        "exactus/tools/coverage_tests/main.py",
        "exactus/tools/lints/main.py",
        "exactus/tools/record/main.py",
        "exactus/tools/frontend/main.py",
    ],
)
def test_loose_script_bootstrap(module: str) -> None:
    """Loose-script execution reinserts the repository root into ``sys.path``.

    Args:
        module: Tool module path relative to the repository root.

    """
    target: Path = Constants.root / module
    kept: list[str] = [
        item
        for item in sys_path
        if Path(item or ".").resolve() != Constants.root
    ]
    with patch(target="sys.path", new=kept):
        _ = run_path(path_name=str(object=target))
    expect_true(
        condition=any(
            Path(item or ".").resolve() == Constants.root for item in kept
        ),
    )
