# Copyright (c) 2026 Project contributors
"""Verify selector usage, deletion guard, renaming and dangling references."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tests.tools.record.selector_support import project
from exactus.tools.record.selector_usage import (
    SelectorUsage,
    dangling_references,
    probe_names,
    referenced_names,
    usage_index,
)
from exactus.tools.record.selectors import Pace, SelectorDef, SelectorError
from exactus.tools.record.store import FlowStore, WorkspaceError

if TYPE_CHECKING:
    from exactus.tools.record.model import Workspace


def test_names_are_found_in_expressions_and_conditions() -> None:
    """Read selector names from expressions and from probe variables."""
    expect_equal(
        actual=referenced_names(
            expression=(
                "and([extended-selector=\"a\"], [extended-selector='b_1'])"
            ),
        ),
        expected=frozenset({"a", "b_1"}),
    )
    expect_equal(
        actual=probe_names(
            condition="sel_a_b_count > 1 and sel_c_text == 'x'",
        ),
        expected=frozenset({"a_b", "c"}),
    )
    expect_equal(
        actual=probe_names(condition="sel_a_other == 1"),
        expected=frozenset(),
    )


def test_usage_counts_actions_selectors_and_conditions() -> None:
    """Report who depends on each selector."""
    index: dict[str, SelectorUsage] = usage_index(workspace=project())
    card: SelectorUsage = index["sel-card"]
    expect_equal(
        actual=card.actions,
        expected=(("f1", card.actions[0][1]), ("f2", card.actions[1][1])),
    )
    expect_equal(actual=card.flow_count, expected=2)
    expect_equal(actual=card.selectors, expected=("sel-title",))
    expect_equal(actual=card.conditions, expected=2)
    expect_true(condition=card.in_use)
    expect_true(condition=not index["sel-title"].in_use)


def test_delete_is_guarded_unless_forced() -> None:
    """Refuse to remove a selector that is still in use."""
    store: FlowStore = FlowStore(workspace=project())
    with pytest.raises(expected_exception=WorkspaceError, match="2 action"):
        store.delete_selector(selector_id="sel-card")
    store.delete_selector(selector_id="sel-title")
    expect_equal(
        actual=[item.name for item in store.workspace.selectors],
        expected=["card"],
    )
    store.delete_selector(selector_id="sel-card", force=True)
    expect_equal(actual=store.workspace.selectors, expected=())
    expect_equal(
        actual=[
            (f, s)
            for f, _, s in dangling_references(workspace=store.workspace)
        ],
        expected=[("f1", "sel-card"), ("f2", "sel-card")],
    )
    with pytest.raises(expected_exception=WorkspaceError, match="Unknown"):
        store.delete_selector(selector_id="sel-card")


def test_upsert_replaces_by_identifier_and_keeps_names_unique() -> None:
    """Edit in place by id, and reject a name another selector holds."""
    store: FlowStore = FlowStore(workspace=project())
    store.upsert_selector(
        selector=replace(
            store.get_selector(selector_id="sel-card"),
            expression=".panel",
        ),
    )
    expect_equal(
        actual=store.get_selector(selector_id="sel-card").expression,
        expected=".panel",
    )
    expect_equal(actual=len(store.workspace.selectors), expected=2)
    with pytest.raises(expected_exception=SelectorError, match="names"):
        store.upsert_selector(
            selector=SelectorDef(
                selector_id="sel-new",
                name="card",
                expression=".x",
            ),
        )
    expect_equal(actual=len(store.workspace.selectors), expected=2)


def test_rename_rewrites_references_and_flags_scripts() -> None:
    """Rewrite what can be rewritten and report snippets that mention it."""
    store: FlowStore = FlowStore(workspace=project())
    flagged: tuple[str, ...] = store.rename_selector(
        selector_id="sel-card",
        name="panel",
    )
    workspace: Workspace = store.workspace
    expect_equal(actual=flagged, expected=("f1-js",))
    expect_equal(
        actual=store.get_selector(selector_id="sel-title").expression,
        expected='children([extended-selector="panel"], .title)',
    )
    expect_equal(
        actual=workspace.flows[1].events[0].pace_between,
        expected=Pace(until="sel_panel_count >= 3"),
    )
    expect_equal(
        actual=workspace.edges[0].condition_expression,
        expected="flow_succeeded and sel_panel_exists",
    )
    expect_equal(
        actual=workspace.flows[0].events[1].payload,
        expected="document.querySelector('[extended-selector=\"card\"]')",
    )
    with pytest.raises(expected_exception=SelectorError, match="names"):
        _ = store.rename_selector(selector_id="sel-title", name="panel")
    with pytest.raises(expected_exception=SelectorError, match="start with"):
        _ = store.rename_selector(selector_id="sel-title", name="1x")
