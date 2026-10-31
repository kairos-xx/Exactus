# Copyright (c) 2026
"""Tests for the VisualCauseDescriber report enrichment."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from exactus.packages.scene_description.visual_cause import (
    VisualCauseDescriber,
)
from exactus.tests.common.support import dig
from exactus.tests.packages.scene_description.conftest import (
    element,
    report,
    scene,
)
from exactus.tests.packages.scene_description.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
    require_json_dict,
    require_json_list,
)

if TYPE_CHECKING:
    from exactus.packages.scene_description.models import JsonValue


def _describer() -> VisualCauseDescriber:
    """Return a fresh describer instance.

    Returns:
        New ``VisualCauseDescriber``.

    """
    return VisualCauseDescriber()


def test_enrich_adds_change_description() -> None:
    """Enrichment always attaches the change_description block."""
    describer: VisualCauseDescriber = _describer()
    enriched: dict[str, JsonValue] = describer.enrich(
        report=report(),
        scene_a=scene(metadata={"viewport": "a"}),
        scene_b=scene(metadata={"viewport": "b"}),
    )
    block: dict[str, JsonValue] = require_json_dict(
        value=enriched["change_description"],
    )
    expect_equal(
        actual=block["schema"],
        expected="scene-description/visual-cause/v1",
    )
    expect_equal(actual=block["elements"], expected=[])
    expect_equal(
        actual=block["summary"],
        expected=(
            "No changed Visual Cause nodes could be matched "
            "to rendered scene elements."
        ),
    )
    expect_equal(
        actual=dig(document=block, path=("scene_a", "metadata", "viewport")),
        expected="a",
    )


def test_enrich_does_not_mutate_report() -> None:
    """The input report object is left untouched."""
    original: dict[str, JsonValue] = report(
        trees=[{"selector": "#x", "categories": ["layout"]}],
    )
    describer: VisualCauseDescriber = _describer()
    enriched: dict[str, JsonValue] = describer.enrich(
        report=original,
        scene_a=scene(),
        scene_b=scene(
            elements={"e": element(selector="#x", name="X", tag="div")},
        ),
    )
    expect_false(
        condition="visual_description"
        in require_json_dict(
            value=dig(document=original, path=("change_trees", 0)),
        ),
    )
    expect_in(
        member="visual_description",
        container=require_json_dict(
            value=dig(document=enriched, path=("change_trees", 0)),
        ),
    )


def test_enrich_non_list_trees() -> None:
    """Non-list change_trees produce an empty description set."""
    enriched: dict[str, JsonValue] = _describer().enrich(
        report=report(trees={"not": "a list"}),
        scene_a=scene(),
        scene_b=scene(),
    )
    expect_equal(
        actual=dig(document=enriched, path=("change_description", "elements")),
        expected=[],
    )


def test_enrich_skips_non_dict_nodes() -> None:
    """Malformed change-tree entries are ignored."""
    enriched: dict[str, JsonValue] = _describer().enrich(
        report=report(trees=[42, "node", None]),
        scene_a=scene(),
        scene_b=scene(),
    )
    expect_equal(
        actual=dig(document=enriched, path=("change_description", "elements")),
        expected=[],
    )


def test_enrich_node_without_selector() -> None:
    """Nodes without a string selector receive no description."""
    enriched: dict[str, JsonValue] = _describer().enrich(
        report=report(trees=[{"categories": ["paint"]}]),
        scene_a=scene(),
        scene_b=scene(),
    )
    node: dict[str, JsonValue] = require_json_dict(
        value=dig(document=enriched, path=("change_trees", 0)),
    )
    expect_false(condition="visual_description" in node)


def test_enrich_matched_node_serializes_context() -> None:
    """Matched nodes carry categories, mechanisms, and root_cause."""
    tree: dict[str, JsonValue] = {
        "selector": "#cta",
        "categories": ["layout", 7, None],
        "mechanisms": ["geometry"],
        "root_cause": {"rule": "color"},
        "relations": {"descendants": []},
    }
    enriched: dict[str, JsonValue] = _describer().enrich(
        report=report(trees=[tree]),
        scene_a=scene(),
        scene_b=scene(
            elements={"e": element(selector="#cta", name="Call", tag="a")},
        ),
    )
    description: dict[str, JsonValue] = require_json_dict(
        value=dig(
            document=enriched,
            path=("change_trees", 0, "visual_description"),
        ),
    )
    expect_equal(actual=description["categories"], expected=["layout"])
    expect_equal(actual=description["mechanisms"], expected=["geometry"])
    expect_equal(actual=description["root_cause"], expected={"rule": "color"})
    expect_equal(actual=description["summary"], expected="a “Call” appeared.")
    expect_equal(
        actual=dig(document=enriched, path=("change_description", "elements")),
        expected=[description],
    )
    expect_equal(
        actual=dig(document=enriched, path=("change_description", "summary")),
        expected="1 changed rendered element described from A to B.",
    )


def test_enrich_recurses_descendants() -> None:
    """Descriptions propagate through relations.descendants chains."""
    tree: dict[str, JsonValue] = {
        "selector": "#outer",
        "relations": {
            "descendants": [
                {"selector": "#inner"},
                {"relations": {"descendants": [{"selector": "#leaf"}]}},
                "malformed",
            ],
        },
    }
    enriched: dict[str, JsonValue] = _describer().enrich(
        report=report(trees=[tree]),
        scene_a=scene(),
        scene_b=scene(
            elements={
                "o": element(selector="#outer", name="Outer", tag="div"),
                "i": element(selector="#inner", name="Inner", tag="div"),
                "l": element(selector="#leaf", name="Leaf", tag="div"),
            },
        ),
    )
    descriptions: list[JsonValue] = require_json_list(
        value=dig(document=enriched, path=("change_description", "elements")),
    )
    expect_equal(actual=len(descriptions), expected=3)
    expect_equal(
        actual=dig(document=enriched, path=("change_description", "summary")),
        expected="3 changed rendered elements described from A to B.",
    )


def test_enrich_missing_relations_or_descendants() -> None:
    """Nodes lacking relations or a descendant list stop recursion."""
    enriched: dict[str, JsonValue] = _describer().enrich(
        report=report(
            trees=[
                {"relations": "not-a-dict"},
                {"relations": {"descendants": "not-a-list"}},
            ],
        ),
        scene_a=scene(),
        scene_b=scene(),
    )
    expect_equal(
        actual=dig(document=enriched, path=("change_description", "elements")),
        expected=[],
    )


def test_strings_filters_members() -> None:
    """``strings`` keeps only string members of a list."""
    expect_equal(
        actual=VisualCauseDescriber.strings(value=["a", 1, "b", None]),
        expected=["a", "b"],
    )
    expect_equal(
        actual=VisualCauseDescriber.strings(value="not-list"),
        expected=[],
    )


def test_scene_metadata_fallbacks() -> None:
    """Missing or malformed metadata/reference default to empty dicts."""
    expect_equal(
        actual=VisualCauseDescriber.scene_metadata(
            scene={"metadata": "bad", "reference": None},
        ),
        expected={"metadata": {}, "reference": {}},
    )
    expect_equal(
        actual=VisualCauseDescriber.scene_metadata(
            scene={"metadata": {"a": 1}, "reference": {"b": 2}},
        ),
        expected={"metadata": {"a": 1}, "reference": {"b": 2}},
    )


def test_markdown_missing_block() -> None:
    """A report without change_description renders the fallback."""
    expect_equal(
        actual=_describer().markdown(report=report()),
        expected=(
            dedent(
                text=(
                    "    ## Rendered change description\n    \n    No scen"
                    "e description is available.\n    "
                ),
            )
        ),
    )
    expect_equal(
        actual=_describer().markdown(
            report={"change_description": "not-a-dict"},
        ),
        expected=(
            dedent(
                text=(
                    "    ## Rendered change description\n    \n    No scen"
                    "e description is available.\n    "
                ),
            )
        ),
    )


def test_markdown_renders_summary_and_elements() -> None:
    """Markdown lists the summary plus each element summary."""
    document: dict[str, JsonValue] = {
        "change_description": {
            "summary": "2 changed rendered elements described from A to B.",
            "elements": [
                {"summary": "a “Call” appeared."},
                {"summary": "p “Note” disappeared."},
                {"summary": None},
                "malformed",
            ],
        },
    }
    markdown: str = _describer().markdown(report=document)
    expect_true(
        condition=markdown.startswith("## Rendered change description\n"),
        message=markdown,
    )
    expect_in(
        member="2 changed rendered elements described from A to B.",
        container=markdown,
    )
    expect_in(member="- a “Call” appeared.", container=markdown)
    expect_in(member="- p “Note” disappeared.", container=markdown)
    expect_false(condition="- None" in markdown)


def test_markdown_without_elements_list() -> None:
    """A missing or malformed elements list renders just the summary."""
    document: dict[str, JsonValue] = {
        "change_description": {
            "summary": "Custom summary.",
            "elements": "not-a-list",
        },
    }
    markdown: str = _describer().markdown(report=document)
    expect_in(member="Custom summary.", container=markdown)
    expect_false(condition="-" in markdown)


def test_markdown_missing_summary_fallback() -> None:
    """A missing summary falls back to the default sentence."""
    document: dict[str, JsonValue] = {"change_description": {}}
    markdown: str = _describer().markdown(report=document)
    expect_in(member="No rendered changes were described.", container=markdown)
