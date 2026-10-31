# Copyright (c) 2026
"""The performance tool wraps the generic analyzer for this project."""

from __future__ import annotations

from json import loads
from textwrap import dedent
from typing import TYPE_CHECKING

from exactus.tests.common.support import (
    dig,
    expect_equal,
    expect_in,
    expect_true,
)
from exactus.tools.performance import main as performance_main

if TYPE_CHECKING:
    from argparse import Namespace
    from pathlib import Path


def trace_text() -> str:
    """Return a deterministic two-step trace.

    Returns:
        Representative trace content.

    """
    return dedent(
        text=(
            "    2026-01-01T00:00:00.000+00:00 +    0.000s tool: start\n    20"
            "26-01-01T00:00:00.010+00:00 +    0.010s   collect\n    2026-01-01"
            "T00:00:02.000+00:00 +    2.000s tool: done\n    "
        ),
    )


def write_trace(*, root: Path, tool: str = "LINTS") -> Path:
    """Write one Exactus-shaped trace fixture.

    Args:
        root: Temporary project root.
        tool: Tool directory name.

    Returns:
        Written trace path.

    """
    path: Path = root / "EXACTUS_RESULTS" / tool / "ARTIFACTS" / "steps.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(data=trace_text(), encoding="utf-8")
    return path


def test_main_reports_missing_traces(tmp_path: Path) -> None:
    """An empty scan root returns status 2 and a FAIL report.

    Args:
        tmp_path: Per-test temporary directory.

    """
    status: int = performance_main.main(
        arguments=(str(object=tmp_path), "--source", "EMPTY", "--no-serve"),
    )
    expect_equal(actual=status, expected=2)
    report: Path = tmp_path / "EXACTUS_RESULTS" / "PERFORMANCE" / "result.json"
    expect_true(condition=report.is_file())
    payload: object = loads(s=report.read_text(encoding="utf-8"))
    expect_equal(
        actual=dig(document=payload, path=("status",)),
        expected="FAIL",
    )
    expect_equal(
        actual=dig(document=payload, path=("resume",)),
        expected="No steps.txt traces found.",
    )


def test_main_analyzes_and_exports(tmp_path: Path) -> None:
    """A trace produces the report bundle plus the exported dashboard.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = write_trace(root=tmp_path)
    status: int = performance_main.main(
        arguments=(str(object=tmp_path), "--no-serve"),
    )
    expect_equal(actual=status, expected=0)
    output: Path = tmp_path / "EXACTUS_RESULTS" / "PERFORMANCE"
    expect_true(condition=(output / "result.md").is_file())
    expect_true(condition=(output / "result.json").is_file())
    expect_true(condition=(output / "result_web").is_dir())
    expect_true(condition=(output / "index.html").is_file())
    expect_true(condition=(output / "ARTIFACTS" / "steps.txt").is_file())
    payload: object = loads(
        s=(output / "result.json").read_text(encoding="utf-8"),
    )
    expect_in(
        member="slowest lints",
        container=str(object=dig(document=payload, path=("resume",))),
    )


def test_parse_args_reads_repeatable_sources(tmp_path: Path) -> None:
    """``--source`` accumulates into a list replacing the default scan root.

    Args:
        tmp_path: Per-test temporary directory.

    """
    options: Namespace = performance_main.parse_args(
        arguments=(str(object=tmp_path), "--source", "a", "--source", "b"),
    )
    expect_equal(actual=options.sources, expected=["a", "b"])
