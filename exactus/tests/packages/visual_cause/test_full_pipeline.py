# Copyright (c) 2026
"""End-to-end coverage for the bounded causal-analysis pipeline."""

from pathlib import Path

from exactus.packages.visual_cause import CssVisualCause, Settings
from exactus.tests.packages.visual_cause.support import expect_true


def test_tiny_full_pipeline(tmp_path: Path) -> None:
    """Exercise deep causal phases on a deliberately tiny search space.

    Args:
        tmp_path: Temporary test directory.

    """
    html: Path = tmp_path / "index.html"
    css_a: Path = tmp_path / "a.css"
    css_b: Path = tmp_path / "b.css"
    output: Path = tmp_path / "results"
    html.write_text(
        data="<!doctype html><html><body><main>"
        '<div id="box">A</div></main></body></html>',
        encoding="utf-8",
    )
    css_a.write_text(
        data=""":root { --x: 10px; } #box { width: 80px; height: 40px; }""",
        encoding="utf-8",
    )
    css_b.write_text(
        data=":root { --x: 10px; } #box { width: 80px; height: 40px; }"
        " #box { transform: translateX(calc(var(--x) + 10px)); }",
        encoding="utf-8",
    )
    CssVisualCause(
        settings=Settings(
            url=html.resolve().as_uri(),
            css_a=css_a,
            css_b=css_b,
            output=output,
            width=320,
            height=200,
            threshold=1,
            max_candidates=5,
            timeout_ms=3000,
            parallel_workers=1,
            recycle_after=8,
            analysis_budget_seconds=60.0,
        ),
    ).run()
    expect_true(condition=(output / "report.json").is_file())
    expect_true(condition=(output / "report.md").is_file())
    expect_true(condition=(output / "diff.png").is_file())
