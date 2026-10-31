# Copyright (c) 2026
"""Tests for dual URL and token CSS analysis."""

from pathlib import Path

from exactus.packages.visual_cause import Settings
from exactus.packages.visual_cause.causal import CssValueTokenizer
from exactus.tests.packages.visual_cause.support import (
    expect_equal,
    expect_true,
)


def test_dual_url(tmp_path: Path) -> None:
    """A and B may navigate to distinct URLs.

    Args:
    tmp_path: Value for tmp path.

    """
    settings: Settings = Settings(
        url="https://a.example/",
        url_b="https://b.example/",
        css_a=tmp_path / "a.css",
        css_b=tmp_path / "b.css",
        output=tmp_path / "out",
        width=800,
        height=600,
        threshold=12,
        max_candidates=10,
        timeout_ms=1000,
    )
    expect_equal(actual=settings.url_b, expected="https://b.example/")


def test_nested_tokens() -> None:
    """Nested CSS functions retain literal and function nodes."""
    value: str = "translate(calc(20px + var(--x)), 4px) scale(1.1)"
    texts: set[str] = {
        node.text
        for node in CssValueTokenizer.flatten(
            nodes=CssValueTokenizer.parse(value=value),
        )
    }
    expect_true(condition={"20px", "var(--x)", "4px", "scale(1.1)"} <= texts)
