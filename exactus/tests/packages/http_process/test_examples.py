# Copyright (c) 2026
"""Exercise the bundled ``http_process`` examples end to end."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from exactus.packages.http_process.examples import inspect_existing, run
from exactus.tests.common.support import expect_in, expect_true

if TYPE_CHECKING:
    import pytest


def test_example_run_starts_discovers_and_stops_a_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The launch example discovers a real ``http.server`` instance.

    Args:
        monkeypatch: Redirects the module-level ``stdout`` binding.

    """
    buffer: StringIO = StringIO()
    monkeypatch.setattr(target=run, name="stdout", value=buffer)
    run.main()
    expect_true(condition=bool(buffer.getvalue().strip()))


def test_inspect_existing_reports_the_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The inspection example prints a result for ``127.0.0.1:8000``.

    Args:
        monkeypatch: Redirects the module-level ``stdout`` binding.

    """
    buffer: StringIO = StringIO()
    monkeypatch.setattr(target=inspect_existing, name="stdout", value=buffer)
    inspect_existing.main()
    expect_in(member="8000", container=buffer.getvalue())
