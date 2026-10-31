# Copyright (c) 2026
"""Enforce the runnable package contract for source-owned examples."""

from __future__ import annotations

from pathlib import Path
from stat import S_IXUSR
from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import expect_equal, expect_true

if TYPE_CHECKING:
    from collections.abc import Iterable


def _example_directories(*, root: Path) -> tuple[Path, ...]:
    """Discover supported source example directories.

    Args:
        root: Repository root.

    Returns:
        Sorted Exactus and package example directories. A grouping
        directory holding runnable example packages is replaced by them.

    """
    groups: tuple[Iterable[Path], ...] = (
        (root / "exactus" / "tools").glob(pattern="*/examples"),
        (root / "exactus" / "tools").glob(pattern="*/templates/*/examples"),
        (root / "exactus" / "packages").glob(pattern="*/examples"),
    )
    found: list[Path] = []
    path: Path
    for path in (p for group in groups for p in group if p.is_dir()):
        nested: list[Path] = sorted(
            child
            for child in path.iterdir()
            if child.is_dir() and (child / "run.py").is_file()
        )
        found.extend(
            nested if nested and not (path / "run.py").is_file() else [path],
        )
    return tuple(sorted(found))


@pytest.mark.parametrize("filename", ["__init__.py", "__main__.py", "run.py"])
def test_every_example_directory_is_a_runnable_package(filename: str) -> None:
    """Every source example exposes each standard package entry point.

    Args:
        filename: Required entry-point filename.

    """
    root: Path = Path(__file__).resolve().parents[4]
    directories: tuple[Path, ...] = _example_directories(root=root)
    expect_true(condition=bool(directories))
    missing: tuple[str, ...] = tuple(
        str(object=path.relative_to(root))
        for path in directories
        if not (path / filename).is_file()
    )
    expect_equal(actual=missing, expected=())


def test_every_example_run_script_is_executable() -> None:
    """Every source example supports direct executable invocation."""
    root: Path = Path(__file__).resolve().parents[4]
    failures: list[str] = []
    directory: Path
    for directory in _example_directories(root=root):
        script: Path = directory / "run.py"
        if not script.stat().st_mode & S_IXUSR:
            failures.append(str(object=directory.relative_to(root)))
            continue
        first_line: str = script.read_text(encoding="utf-8").partition("\n")[0]
        if first_line != "#!/usr/bin/env python3":
            failures.append(str(object=directory.relative_to(root)))
    expect_equal(actual=failures, expected=[])
