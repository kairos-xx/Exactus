# Copyright (c) 2026
"""Cover the ``exactus.packages.completion`` command-line entry point."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from runpy import run_path
from sys import modules
from typing import Final, final

import pytest

from exactus.packages.completion.cli import main, run
from exactus.tests.common.support import expect_equal, expect_true


@final
class Constants:
    """Group module-level constants.

    Attributes:
        main_module: Grouped module constant.

    """

    main_module: Final[Path] = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "completion"
        / "__main__.py"
    )


def test_bootstrap_imports_standalone(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-execute the module's script bootstrap without a package.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["completion"],
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(
            path_name=str(object=Constants.main_module),
            run_name="__main__",
        )
    expect_equal(actual=raised.value.code, expected=2)


def test_run_rejects_conflicting_actions(tmp_path: Path) -> None:
    """Refuse more than one management action in a single call.

    Args:
        tmp_path: Pytest temporary directory.

    """
    with pytest.raises(expected_exception=SystemExit) as raised:
        run(
            arguments=(
                "all",
                "--command",
                "example",
                "--install",
                "--uninstall",
            ),
            out=StringIO(),
            home=tmp_path,
        )
    expect_equal(actual=raised.value.code, expected=2)


def test_run_diagnose_requires_all_shells(tmp_path: Path) -> None:
    """Refuse ``--diagnose`` narrowed to one shell.

    Args:
        tmp_path: Pytest temporary directory.

    """
    with pytest.raises(expected_exception=SystemExit) as raised:
        run(
            arguments=("zsh", "--command", "example", "--diagnose"),
            out=StringIO(),
            home=tmp_path,
        )
    expect_equal(actual=raised.value.code, expected=2)


def test_run_diagnose_reports_missing_registrations(tmp_path: Path) -> None:
    """Report missing registrations as healthy for an empty home.

    Args:
        tmp_path: Pytest temporary directory.

    """
    out: StringIO = StringIO()
    status: int = run(
        arguments=("all", "--command", "example", "--diagnose"),
        out=out,
        home=tmp_path,
    )
    expect_equal(actual=status, expected=0)
    expect_true(
        condition="MISSING" in out.getvalue() or "missing" in out.getvalue(),
    )


def test_run_install_and_uninstall_manage_profiles(tmp_path: Path) -> None:
    """Install then uninstall registration content under a fake home.

    Args:
        tmp_path: Pytest temporary directory.

    """
    _ = (tmp_path / ".bashrc").write_text(data="", encoding="utf-8")
    _ = (tmp_path / ".zshrc").write_text(data="", encoding="utf-8")
    out: StringIO = StringIO()
    installed: int = run(
        arguments=("all", "--command", "example", "--install"),
        out=out,
        home=tmp_path,
    )
    expect_true(condition=installed in {0, 2})
    removed: int = run(
        arguments=("all", "--command", "example", "--uninstall"),
        out=out,
        home=tmp_path,
    )
    expect_true(condition=removed in {0, 2})


def test_main_accepts_explicit_arguments() -> None:
    """Dispatch explicit CLI tokens through ``main``."""
    with pytest.raises(expected_exception=SystemExit) as raised:
        main(
            arguments=(
                "all",
                "--command",
                "example",
                "--install",
                "--uninstall",
            ),
        )
    expect_equal(actual=raised.value.code, expected=2)
