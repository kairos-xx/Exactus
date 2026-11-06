# Copyright (c) 2026
"""Verify the hard cut: retired ``clean`` spellings are rejected."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess, run
from sys import executable
from typing import Final, final

from exactus.tests.common.support import expect_equal, expect_in
from exactus.tools.common.run_environment import sanitized_environ


@final
class Constants:
    """Group module-level constants.

    Attributes:
        entrypoint: Grouped module constant.
        timeout_seconds: Grouped module constant.

    """

    entrypoint: Final[Path] = (
        Path(__file__).resolve().parents[3] / "__main__.py"
    )
    timeout_seconds: Final[int] = 120


def _invoke(*, arguments: tuple[str, ...], cwd: Path) -> CompletedProcess[str]:
    """Run the real entrypoint in an isolated environment.

    Args:
        arguments: Command line after the entrypoint.
        cwd: Directory whose ``pyproject.toml`` is resolved.

    Returns:
        The completed process with captured text output.

    """
    return run(
        args=[executable, str(object=Constants.entrypoint), *arguments],
        cwd=cwd,
        env=sanitized_environ(),
        capture_output=True,
        text=True,
        check=False,
        timeout=Constants.timeout_seconds,
    )


def test_clean_flag_is_rejected_with_status_two(tmp_path: Path) -> None:
    """``exactus --clean`` is unknown input, not an alias of ``--clear``.

    Args:
        tmp_path: Independent working directory.

    """
    result: CompletedProcess[str] = _invoke(
        arguments=("--clean",),
        cwd=tmp_path,
    )
    expect_equal(actual=result.returncode, expected=2)
    expect_in(member="--clean", container=result.stderr)


def test_top_level_clean_option_is_unknown(tmp_path: Path) -> None:
    """``[tool.exactus] clean = true`` raises an unknown-option error.

    Args:
        tmp_path: Independent project root.

    """
    (tmp_path / "pyproject.toml").write_text(
        data=(
            """\
[project]
name = "retired-clean"
version = "0"

[tool.exactus]
clean = true
"""
        ),
        encoding="utf-8",
    )
    result: CompletedProcess[str] = _invoke(
        arguments=("--list-tools",),
        cwd=tmp_path,
    )
    expect_equal(actual=result.returncode, expected=2)
    expect_in(member="clean: unknown option", container=result.stderr)
