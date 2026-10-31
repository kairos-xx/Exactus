# Copyright (c) 2026 Project contributors
"""Preserve private Markdown permissions and keep new HTML owner-only."""

from pathlib import Path

from exactus.packages.todo_sync import synchronize
from exactus.tests.common.support import expect_equal


def test_private_output(tmp_path: Path) -> None:
    """Atomic replacement must not make a private checklist world-readable.

    Args:
        tmp_path: Isolated directory containing the private source document.

    """
    path: Path = tmp_path / "TODO.md"
    path.write_text(data="- [ ] private task\n", encoding="utf-8")
    path.chmod(mode=0o600)
    synchronize(path=path)
    expect_equal(actual=path.stat().st_mode & 0o777, expected=0o600)
    expect_equal(
        actual=path.with_suffix(suffix=".html").stat().st_mode & 0o777,
        expected=0o600,
    )
