# Copyright (c) 2026 Project contributors
"""The default CLI source and report live under ``exactus/docs/todo``."""

from pathlib import Path

import pytest

from exactus.packages.todo_sync.cli import main
from exactus.tests.common.support import expect_equal


def test_default_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running without --path writes both outputs to exactus/docs/todo.

    Args:
        tmp_path: Isolated workspace containing the default TODO document.
        monkeypatch: Restore the caller's working directory after the test.

    """
    source: Path = tmp_path / "exactus" / "docs" / "todo" / "TODO.md"
    source.parent.mkdir(parents=True)
    source.write_text(data="# Plan\n- [ ] Task\n", encoding="utf-8")
    monkeypatch.chdir(path=tmp_path)
    expect_equal(actual=main(argv=[]), expected=0)
    expect_equal(
        actual=source.with_suffix(suffix=".html").exists(),
        expected=True,
    )
    expect_equal(actual=main(argv=["--check"]), expected=0)
    expect_equal(
        actual=(tmp_path / "exactus" / "docs" / "TODO.md").exists(),
        expected=False,
    )
