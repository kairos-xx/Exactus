# Copyright (c) 2026
"""Tests for Typed OM and parallel settings surfaces."""

from pathlib import Path

from exactus.packages.visual_cause import Settings
from exactus.tests.packages.visual_cause.support import expect_equal


def test_parallel_defaults(tmp_path: Path) -> None:
    """Settings expose bounded reusable-render worker defaults.

    Args:
    tmp_path: Value for tmp path.

    """
    settings: Settings = Settings(
        url="https://example.test/",
        css_a=tmp_path / "a.css",
        css_b=tmp_path / "b.css",
        output=tmp_path / "out",
        width=800,
        height=600,
        threshold=12,
        max_candidates=20,
        timeout_ms=1000,
    )
    expect_equal(actual=settings.parallel_workers, expected=4)
    expect_equal(actual=settings.recycle_after, expected=24)
