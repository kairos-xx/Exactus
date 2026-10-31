# Copyright (c) 2026 Project contributors
"""Keep the version-3 action inventory complete and current."""

from __future__ import annotations

from pathlib import Path
from typing import Final, final

from exactus.tests.common.support import expect_equal, expect_in
from exactus.tools.record.flow_inventory import (
    ActionInventory,
    build_inventory,
    kinds_for_catalog_id,
    render_matrix,
)
from exactus.tools.record.model import EventKind


@final
class Constants:
    """Group module-level constants.

    Attributes:
        record: Grouped module constant.
        document: Grouped module constant.

    """

    record: Final[Path] = (
        Path(__file__).resolve().parents[3] / "tools" / "record"
    )
    document: Final[Path] = (
        Path(__file__).resolve().parents[4]
        / "docs"
        / "todo"
        / "FLOW-INVENTORY.md"
    )


def test_every_event_kind_is_in_the_matrix() -> None:
    """List each event kind exactly once in the rendered matrix."""
    matrix: str = render_matrix(
        inventory=build_inventory(record=Constants.record),
    )
    for kind in EventKind:
        expect_in(member=f"| `{kind.value}` |", container=matrix)


def test_every_catalog_id_resolves_to_a_kind_or_guard() -> None:
    """Resolve each palette id to real event kinds, or to a guard."""
    inventory: ActionInventory = build_inventory(record=Constants.record)
    for catalog_id in inventory.catalog_ids:
        for kind in kinds_for_catalog_id(catalog_id=catalog_id):
            expect_in(member=kind, container=inventory.event_kinds)


def test_inventory_document_is_current() -> None:
    """Fail when the committed document no longer matches the tree."""
    expect_equal(
        actual=Constants.document.read_text(encoding="utf-8"),
        expected=render_matrix(
            inventory=build_inventory(record=Constants.record),
        ),
    )
