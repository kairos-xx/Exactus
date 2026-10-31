# Copyright (c) 2026
"""Exercise the bundled ``todo_sync`` synchronization example."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from exactus.packages.todo_sync.examples import run
from exactus.tests.common.support import expect_equal, expect_in, expect_true

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_example_synchronizes_a_scratch_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The demo copies ``TODO.md`` into a scratch dir and syncs it.

    Args:
        tmp_path: Isolated scratch destination.
        monkeypatch: Redirects the module-level ``stdout`` binding.

    """
    buffer: StringIO = StringIO()
    monkeypatch.setattr(target=run, name="stdout", value=buffer)
    scratch: Path = tmp_path / "scratch"
    expect_equal(actual=run.main(scratch=scratch), expected=0)
    expect_true(condition=(scratch / "TODO.md").is_file())
    expect_true(condition=(scratch / "TODO.html").is_file())
    output: str = buffer.getvalue()
    expect_in(member="sync      TODO.md:", container=output)
    expect_in(member="dashboard TODO.html:", container=output)
    expect_in(member="complete  ", container=output)
    expect_true(condition=run.Constants.source.is_file())
