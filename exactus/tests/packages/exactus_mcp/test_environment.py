# Copyright (c) 2026
"""Tests for deterministic .env loading."""

from pathlib import Path

from exactus.packages.exactus_mcp.environment import EnvironmentLoader


def expect_equal(*, actual: object, expected: object) -> None:
    """Fail when two test values differ.

    Args:
        actual: Observed value.
        expected: Required value.

    Raises:
        AssertionError: If the values differ.

    """
    if actual != expected:
        msg: str = f"expected {expected!r}, got {actual!r}"
        raise AssertionError(msg)


def test_environment_loader_preserves_existing_values(tmp_path: Path) -> None:
    """Process environment values take precedence over .env values.

    Args:
        tmp_path: Per-test scratch directory.

    """
    _ = (tmp_path / ".env").write_text(
        data="A=file\nB='two'\n",
        encoding="utf-8",
    )
    values: dict[str, str] = {"A": "process"}
    loaded: Path | None = EnvironmentLoader.load(
        values=values,
        directory=tmp_path,
    )
    expect_equal(actual=loaded, expected=tmp_path / ".env")
    expect_equal(actual=values, expected={"A": "process", "B": "two"})
