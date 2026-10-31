# Copyright (c) 2026
"""Tests for exact CSS value nodes."""

from exactus.packages.visual_cause.causal import CssValueParser, ValueNode
from exactus.tests.packages.visual_cause.support import (
    expect_equal,
    expect_true,
)


def test_nested_value_nodes() -> None:
    """Run test nested value nodes."""
    value: str = "translate(calc(20px + var(--x)), 4px) scale(1.1)"
    texts: set[str] = {
        node.text.strip()
        for node in CssValueParser.walk(node=CssValueParser.parse(value=value))
    }
    expect_true(
        condition={
            "calc(20px + var(--x))",
            "20px",
            "+",
            "var(--x)",
            "4px",
            "scale(1.1)",
        }
        <= texts,
    )


def test_exact_span_replacement() -> None:
    """Run test exact span replacement."""
    value: str = "calc(20px + var(--x))"
    node: ValueNode = next(
        item
        for item in CssValueParser.walk(node=CssValueParser.parse(value=value))
        if item.text == "20px"
    )
    expect_equal(
        actual=CssValueParser.replace(
            value=value,
            node=node,
            replacement="30px",
        ),
        expected="calc(30px + var(--x))",
    )
