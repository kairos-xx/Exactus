# Copyright (c) 2026
"""Regression tests for bounded runtime and report lifecycle."""

from pathlib import Path

from exactus.packages.visual_cause import CssVisualCause, Settings
from exactus.tests.packages.visual_cause.support import (
    expect_equal,
    expect_in,
    expect_true,
    private_call,
)


def _settings(tmp_path: Path) -> Settings:
    """Build minimal runtime settings.

    Args:
        tmp_path: Temporary test directory.

    Returns:
        Minimal analyzer settings.

    """
    css_a: Path = tmp_path / "a.css"
    css_b: Path = tmp_path / "b.css"
    css_a.write_text(data="body { color: black; }", encoding="utf-8")
    css_b.write_text(data="body { color: white; }", encoding="utf-8")
    return Settings(
        url="https://example.invalid/",
        css_a=css_a,
        css_b=css_b,
        output=tmp_path / "out",
        width=320,
        height=240,
        threshold=8,
        max_candidates=0,
        timeout_ms=1000,
        analysis_budget_seconds=1.0,
    )


def test_failure_report_is_always_persisted(tmp_path: Path) -> None:
    """A failed run must leave human and machine-readable diagnostics.

    Args:
        tmp_path: Temporary test directory.

    """
    analyzer: CssVisualCause = CssVisualCause(
        settings=_settings(tmp_path=tmp_path),
    )
    error: RuntimeError = RuntimeError("synthetic failure")
    private_call(analyzer, "_write_failure", error=error)
    expect_true(
        condition=(analyzer.settings.output / "failure.json").is_file(),
    )
    expect_true(condition=(analyzer.settings.output / "report.md").is_file())
    expect_in(
        member='"status": "failed"',
        container=(analyzer.settings.output / "progress.json").read_text(
            encoding="utf-8",
        ),
    )


def test_zero_candidates_is_explicit_quick_mode(tmp_path: Path) -> None:
    """Zero candidates must remain valid for deterministic demo smoke runs.

    Args:
        tmp_path: Temporary test directory.

    """
    analyzer: CssVisualCause = CssVisualCause(
        settings=_settings(tmp_path=tmp_path),
    )
    expect_equal(actual=analyzer.settings.max_candidates, expected=0)
    expect_equal(
        actual=analyzer.settings.analysis_budget_seconds,
        expected=1.0,
    )
