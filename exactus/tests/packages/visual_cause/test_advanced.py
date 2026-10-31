# Copyright (c) 2026
"""Tests for advanced CSS causal analysis primitives."""

from __future__ import annotations

from exactus.packages.visual_cause.causal import (
    CausalMinimizer,
    CauseSet,
    CssTokenNode,
    CssValueParser,
    CssValueTokenizer,
    LayoutEvidence,
    ValueNode,
)
from exactus.tests.packages.visual_cause.support import (
    Constant,
    expect_equal,
    expect_none,
    expect_true,
    private_call,
    require,
)


def test_nested_function_ast() -> None:
    """Nested expressions retain exact source spans."""
    value: str = "clamp(10px, calc(var(--base, 2px) * 3), 400px)"
    nodes: tuple[ValueNode, ...] = CssValueParser.walk(
        node=CssValueParser.parse(value=value),
    )
    functions: list[str] = [
        node.kind for node in nodes if node.kind.startswith("function:")
    ]
    expect_equal(
        actual=functions,
        expected=["function:clamp", "function:calc", "function:var"],
    )
    for node in nodes:
        expect_equal(actual=value[node.start : node.end], expected=node.text)
    var_node: ValueNode = next(
        node for node in nodes if node.kind == "function:var"
    )
    expect_equal(
        actual=CssValueParser.replace(
            value=value,
            node=var_node,
            replacement="4px",
        ),
        expected="clamp(10px, calc(4px * 3), 400px)",
    )


def test_quoted_function_content() -> None:
    """Parentheses and commas inside strings do not split arguments."""
    value: str = 'attr(data-label, "a,b (x)")'
    root: ValueNode = CssValueParser.parse(value=value)
    function: ValueNode = root.children[0]
    expect_equal(actual=function.kind, expected="function:attr")
    expect_equal(actual=len(function.children), expected=2)
    expect_equal(actual=function.children[1].text, expected=' "a,b (x)"')


def test_minimize_joint_only() -> None:
    """Joint-only effects are found without relying on single ablations."""

    def evaluate(items: tuple[tuple[int, str], ...]) -> float:
        """Return an effect only when both necessary members are present.

        Args:
        items: Value for items.

        Returns:
        Result produced by evaluate.

        """
        return float({"width", "box-sizing"} <= {name for _, name in items})

    search: CausalMinimizer = CausalMinimizer(
        evaluate=evaluate,
        budget=24,
        threshold=0.8,
    )
    result: CauseSet = require(
        value=search.minimize(
            candidates=((1, "width"), (2, "box-sizing"), (3, "color")),
        ),
    )
    expect_equal(
        actual={name for _, name in result.members},
        expected={"width", "box-sizing"},
    )
    expect_true(condition=result.minimal_within_budget)


def test_budget_and_unsatisfied() -> None:
    """Search correctly refuses unsupported causes and respects budgets."""
    search: CausalMinimizer = CausalMinimizer(
        evaluate=Constant(value=0.0),
        budget=2,
    )
    expect_none(value=search.minimize(candidates=((1, "width"),)))
    expect_equal(actual=search.score(members=((2, "height"),)), expected=0.0)
    expect_none(value=search.score(members=((3, "color"),)))


def test_layout_evidence() -> None:
    """Resolved grid tracks and container type changes are retained."""
    changes: dict[str, dict[str, str]] = LayoutEvidence.compare(
        a={"grid-template-columns": "100px 100px", "container-type": "normal"},
        b={
            "grid-template-columns": "150px 100px",
            "container-type": "inline-size",
        },
    )
    expect_equal(
        actual=changes["grid-template-columns"]["b"],
        expected="150px 100px",
    )
    expect_equal(actual=changes["container-type"]["a"], expected="normal")


def test_parser_comments_escapes_and_unclosed_constructs() -> None:
    """Exercise comment, escape, operator, and unclosed-parser branches."""
    commented: ValueNode = CssValueParser.parse(
        value="calc(1px /* gap */ + 2px)",
    )
    expect_true(
        condition=any(
            node.kind == "operator"
            for node in CssValueParser.walk(node=commented)
        ),
    )
    quoted: ValueNode = CssValueParser.parse(value='"a\\"b"')
    expect_equal(actual=quoted.children[0].kind, expected="string")
    unclosed: ValueNode = CssValueParser.parse(value="calc(1px /* open")
    expect_equal(actual=unclosed.text, expected="calc(1px /* open")
    expect_equal(
        actual=private_call(
            CssValueParser,
            "_closing_paren",
            value="func(",
            opening=4,
            end=5,
        ),
        expected=-1,
    )


def test_minimizer_empty_reduction_and_cache() -> None:
    """Exercise empty input, cache hits, and one-by-one minimal reduction."""
    calls: list[tuple[tuple[int, str], ...]] = []

    def evaluate(items: tuple[tuple[int, str], ...]) -> float:
        """Score sets containing width.

        Args:
            items: Candidate cause members.

        Returns:
            One for sets containing width, otherwise zero.

        """
        calls.append(items)
        return float(any(name == "width" for _, name in items))

    search: CausalMinimizer = CausalMinimizer(
        evaluate=evaluate,
        budget=20,
        threshold=0.5,
    )
    expect_none(value=search.minimize(candidates=()))
    result: CauseSet = require(
        value=search.minimize(
            candidates=((1, "width"), (2, "height"), (3, "color"), (4, "gap")),
        ),
    )
    expect_equal(actual=result.members, expected=((1, "width"),))
    before: int = len(calls)
    expect_equal(actual=search.score(members=((1, "width"),)), expected=1.0)
    expect_equal(actual=len(calls), expected=before)


def test_lossless_tokenizer_nested_strings_and_flatten() -> None:
    """Exercise the lossless tokenizer's recursive branches."""
    value: str = 'translate(calc(10px + var(--x)), "a\\"b") / 2'
    nodes: tuple[CssTokenNode, ...] = CssValueTokenizer.parse(value=value)
    flat: tuple[CssTokenNode, ...] = CssValueTokenizer.flatten(nodes=nodes)
    expect_true(condition=any(node.kind == "function" for node in flat))
    expect_true(condition=any(node.kind == "string" for node in flat))
    expect_true(
        condition=any(
            node.kind == "operator" and node.text == "/" for node in flat
        ),
    )
    expect_true(
        condition=all(
            value[node.start : node.end] == node.text for node in flat
        ),
    )
