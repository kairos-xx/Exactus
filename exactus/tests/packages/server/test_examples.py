# Copyright (c) 2026
"""Coverage for the ``exactus/server/examples`` demonstration."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from exactus.packages.server import local
from exactus.packages.server.examples import run
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_none,
    expect_true,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_example_serves_pings_and_reuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run the demo end to end against the bundled site.

    Args:
        tmp_path: Per-test scratch directory.
        monkeypatch: Pytest patching helper.

    """
    sink: StringIO = StringIO()
    monkeypatch.setattr(target=run, name="stdout", value=sink)
    expect_equal(actual=run.main(scratch=tmp_path), expected=0)
    output: str = sink.getvalue()
    expect_in(member="same_process=True", container=output)
    expect_in(member="ping     ok", container=output)
    expect_in(member="index    '<!doctype html>'", container=output)
    expect_true(condition=(tmp_path / "server.log").exists())
    expect_none(value=local.reuse_server(path=run.Constants.site))


def _never_ready(**_options: object) -> bool:
    """Report an unavailable server.

    Args:
        **_options: Readiness arguments.

    Returns:
        False for the simulated startup failure.

    """
    return False


def _no_adoption(**_options: object) -> None:
    """Simulate unsuccessful server adoption.

    Args:
        **_options: Adoption arguments.

    """


def test_example_reports_unready_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exit ``1`` when the spawned server never accepts connections.

    Args:
        tmp_path: Per-test scratch directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=local, name="wait_ready", value=_never_ready)
    expect_equal(actual=run.main(scratch=tmp_path), expected=1)


def test_example_reports_adoption_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exit ``1`` when ``reuse_server`` cannot adopt the instance.

    Args:
        tmp_path: Per-test scratch directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=local, name="reuse_server", value=_no_adoption)
    expect_equal(actual=run.main(scratch=tmp_path), expected=1)
