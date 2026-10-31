# Copyright (c) 2026
"""Steps debug trace coverage for the coverage-tests tool chain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from exactus.packages.meaningful import Meaningful
from exactus.packages.steps import step_log
from exactus.tests.common.support import expect_false, expect_in, expect_true
from exactus.tools.common.runtime import emit_progress
from exactus.tools.coverage_tests.main import main
from exactus.tools.coverage_tests.meaningful import (
    MeaningfulConfig,
    analyze_unreached,
)

if TYPE_CHECKING:
    from pathlib import Path


def _steps_text(*, destination: Path) -> str:
    """Read the generated steps trace.

    Args:
        destination: Trace file.

    Returns:
        Trace file contents.

    """
    return destination.read_text(encoding="utf-8")


def test_progress_snapshots_are_traced(tmp_path: Path) -> None:
    """Published progress snapshots reach the active steps trace.

    Args:
        tmp_path: Pytest temporary directory.

    """
    destination: Path = tmp_path / "steps.txt"
    with step_log(path=destination):
        emit_progress(
            state="RUNNING",
            completed=1,
            total=3,
            step="combine coverage",
            detail="two shards",
        )
    text: str = _steps_text(destination=destination)
    expect_in(member="progress: combine coverage", container=text)
    expect_in(member="two shards", container=text)
    expect_in(member="(1/3)", container=text)


def test_meaningful_bridge_traces(tmp_path: Path) -> None:
    """The Exactus Meaningful bridge logs selection and row counts.

    Args:
        tmp_path: Pytest temporary directory.

    """
    source: Path = tmp_path / "mod.py"
    source.write_text(data="value = 1\n", encoding="utf-8")
    destination: Path = tmp_path / "steps.txt"
    with step_log(path=destination):
        analyze_unreached(
            root=tmp_path,
            paths=(source,),
            config=MeaningfulConfig(mode="classify"),
        )
    text: str = _steps_text(destination=destination)
    expect_in(member="meaningful: 1 source files selected", container=text)
    expect_in(member="meaningful: run complete", container=text)
    expect_in(member="meaningful: 1 rows", container=text)


def test_meaningful_mode_off_traces(tmp_path: Path) -> None:
    """A disabled Meaningful run records the skip instead of silence.

    Args:
        tmp_path: Pytest temporary directory.

    """
    source: Path = tmp_path / "mod.py"
    source.write_text(data="value = 1\n", encoding="utf-8")
    destination: Path = tmp_path / "steps.txt"
    with step_log(path=destination):
        analyze_unreached(
            root=tmp_path,
            paths=(source,),
            config=MeaningfulConfig(mode="off"),
        )
    text: str = _steps_text(destination=destination)
    expect_in(
        member="meaningful: mode off — classification skipped",
        container=text,
    )


def test_packaged_meaningful_traces_lifecycle(tmp_path: Path) -> None:
    """Packaged Meaningful workers record each per-file analysis stage.

    Args:
        tmp_path: Pytest temporary directory.

    """
    source: Path = tmp_path / "target.py"
    source.write_text(data="def run():\n    return 42\n", encoding="utf-8")
    destination: Path = tmp_path / "steps.txt"
    with step_log(path=destination):
        Meaningful().analyze(paths=(source,))
    text: str = _steps_text(destination=destination)
    expect_in(member="meaningful: resolved 1 candidates", container=text)
    expect_in(member="workers for 1 files", container=text)
    expect_in(member="target.py — fast scan", container=text)
    expect_in(member="target.py — ", container=text)
    expect_in(member="evidence items", container=text)
    expect_in(member="meaningful: 1 findings, 0 failures", container=text)


def test_main_writes_steps_artifact(tmp_path: Path) -> None:
    """The coverage-tests entry point writes ``ARTIFACTS/steps.txt``.

    Args:
        tmp_path: Pytest temporary directory.

    """
    project: Path = tmp_path / "empty"
    project.mkdir()
    (project / "a.py").write_text(data="x = 1\n", encoding="utf-8")
    out: Path = tmp_path / "out"
    _ = main(arguments=(str(object=project), "-o", str(object=out)))
    destination: Path = out / "ARTIFACTS" / "steps.txt"
    expect_true(condition=destination.is_file())
    text: str = _steps_text(destination=destination)
    expect_in(member="coverage tests: arguments", container=text)
    expect_in(member="coverage tests: run start", container=text)
    expect_in(member="vacuous pass", container=text)


def test_write_false_suppresses_steps_artifact(tmp_path: Path) -> None:
    """``[tool.steps] write = false`` leaves no trace file behind.

    Args:
        tmp_path: Pytest temporary directory.

    """
    _ = (tmp_path / "pyproject.toml").write_text(
        data="[tool.steps]\nwrite = false\n",
        encoding="utf-8",
    )
    project: Path = tmp_path / "empty"
    project.mkdir()
    (project / "a.py").write_text(data="x = 1\n", encoding="utf-8")
    out: Path = tmp_path / "out"
    _ = main(arguments=(str(object=project), "-o", str(object=out)))
    expect_false(condition=(out / "ARTIFACTS" / "steps.txt").exists())
