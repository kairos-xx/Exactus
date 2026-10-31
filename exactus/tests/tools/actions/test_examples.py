# Copyright (c) 2026
"""Run the public actions example against its bundled recipe."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.actions.examples import run as actions_example

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_actions_example(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bundled recipe discovers and verifies its owned example server.

    Args:
        tmp_path: Isolated output directory.
        monkeypatch: Restore command arguments.

    """
    monkeypatch.setattr(
        target=import_module(name="sys"),
        name="argv",
        value=["example", "--output", str(object=tmp_path)],
    )
    expect_equal(actual=actions_example.main(), expected=0)
    expect_true(condition=any(tmp_path.rglob(pattern="*.png")))
    expect_true(condition=any(tmp_path.rglob(pattern="*.json")))
