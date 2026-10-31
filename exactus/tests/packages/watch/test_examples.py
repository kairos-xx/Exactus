# Copyright (c) 2026
"""Exercise the programmatic watch example and its fixtures."""

from __future__ import annotations

from runpy import run_path
from typing import TYPE_CHECKING, cast

import pytest

from exactus.packages.watch.examples import run
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
    private_call,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from types import ModuleType

    from exactus.packages.watch.core import FolderWatchCopy
sys: ModuleType = __import__("sys")


def test_main_runs_the_bundled_dual_watchers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The no-argument demo copies the fixture into both destinations.

    Args:
        tmp_path: Isolated source and destination roots.
        monkeypatch: Redirects the example constants and argv.

    """
    source: Path = tmp_path / "project"
    source.mkdir()
    (source / "marker.txt").write_text(data="demo", encoding="utf-8")
    results: Path = tmp_path / "results"
    monkeypatch.setattr(target=run.Constants, name="source", value=source)
    monkeypatch.setattr(target=run.Constants, name="results", value=results)
    monkeypatch.setattr(target=run.Constants, name="duration", value=0.2)
    monkeypatch.setattr(target=sys, name="argv", value=["run.py"])
    expect_equal(actual=run.main(), expected=0)
    expect_true(
        condition=(results / "project-watch-copy" / "marker.txt").is_file(),
    )
    expect_true(
        condition=(results / "project-mirror" / "marker.txt").is_file(),
    )


def test_main_runs_a_single_explicit_watcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit ``source destination`` pair runs one copy watcher.

    Args:
        tmp_path: Isolated source and destination roots.
        monkeypatch: Redirects the example duration and argv.

    """
    source: Path = tmp_path / "src"
    source.mkdir()
    (source / "seed.txt").write_text(data="demo", encoding="utf-8")
    destination: Path = tmp_path / "dest"
    monkeypatch.setattr(target=run.Constants, name="duration", value=0.2)
    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["run.py", str(object=source), str(object=destination)],
    )
    expect_equal(actual=run.main(), expected=0)
    expect_true(condition=(destination / "seed.txt").is_file())


def test_main_rejects_a_lone_source_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source without a destination is a parser error.

    Args:
        monkeypatch: Redirects the example argv.

    """
    monkeypatch.setattr(target=sys, name="argv", value=["run.py", "only-src"])
    with pytest.raises(expected_exception=SystemExit) as raised:
        run.main()
    expect_equal(actual=raised.value.code, expected=2)


def test_bundled_watchers_cover_copy_and_mirror_modes() -> None:
    """The bundled pair mirrors the two documented deletion policies."""
    watchers: tuple[FolderWatchCopy, ...] = cast(
        typ="tuple[FolderWatchCopy, ...]",
        val=private_call(owner=run, name="_bundled_watchers"),
    )
    expect_equal(actual=len(watchers), expected=2)
    copy_watcher: FolderWatchCopy
    mirror_watcher: FolderWatchCopy
    copy_watcher, mirror_watcher = watchers
    expect_false(condition=copy_watcher.mirror_deletes)
    expect_true(condition=mirror_watcher.mirror_deletes)


def test_stopper_expires_at_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_stopper`` fires once ``monotonic`` reaches the deadline.

    Args:
        monkeypatch: Supplies deterministic monotonic timestamps.

    """
    moments: list[float] = [5.0, 20.0]

    def clock() -> float:
        """Return the next scripted timestamp.

        Returns:
            The next ``moments`` entry.

        """
        return moments.pop(0)

    monkeypatch.setattr(target=run, name="monotonic", value=clock)
    stopper: Callable[[], bool] = cast(
        typ="Callable[[], bool]",
        val=private_call(owner=run, name="_stopper", deadline=10.0),
    )
    expect_false(condition=stopper())
    expect_true(condition=stopper())


def test_fixture_scripts_print_their_marker(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each bundled ``watched.py`` prints the documented marker.

    Args:
        capsys: Captured fixture output.

    """
    root: Path = run.Constants.here
    fixtures: tuple[Path, ...] = (
        root / "project" / "src" / "watched.py",
        root / "results" / "project-mirror" / "src" / "watched.py",
        root / "results" / "project-watch-copy" / "src" / "watched.py",
    )
    for fixture in fixtures:
        run_path(path_name=str(object=fixture), run_name="__main__")
    expect_in(
        member="watch example fixture",
        container=capsys.readouterr().out,
    )
