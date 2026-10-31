# Copyright (c) 2026
"""Resolve the Studio window setting from CLI flag and pyproject."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import expect_false, expect_true
from exactus.tools.record.studio.window import resolve_window

if TYPE_CHECKING:
    from pathlib import Path


def _project(*, root: Path, body: str) -> Path:
    """Write a rooted pyproject.

    Args:
        root: Project directory.
        body: Contents of the ``[tool.exactus.record]`` table.

    Returns:
        The project directory.

    """
    _ = (root / "pyproject.toml").write_text(
        data=f"[tool.exactus]\nroot = true\n[tool.exactus.record]\n{body}",
        encoding="utf-8",
    )
    return root


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ignore any ambient EXACTUS_CONFIG override.

    Args:
        monkeypatch: Environment patcher.

    """
    monkeypatch.delenv(name="EXACTUS_CONFIG", raising=False)


_ = _isolated_config


def test_default_is_false(tmp_path: Path) -> None:
    """No setting and no flag leaves the window disabled.

    Args:
        tmp_path: Disposable project directory.

    """
    expect_false(
        condition=resolve_window(
            flag=None,
            start=_project(root=tmp_path, body=""),
        ),
    )


def test_pyproject_enables_and_flag_overrides(tmp_path: Path) -> None:
    """The pyproject value applies unless the CLI flag says otherwise.

    Args:
        tmp_path: Disposable project directory.

    """
    root: Path = _project(root=tmp_path, body="window = true\n")
    expect_true(condition=resolve_window(flag=None, start=root))
    expect_false(condition=resolve_window(flag=False, start=root))
    expect_true(condition=resolve_window(flag=True, start=root))
