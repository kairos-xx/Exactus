# Copyright (c) 2026 Project contributors
"""Verify selector models, pacing and the selectors document codec."""

from __future__ import annotations

from functools import partial
from json import dumps, loads
from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import expect_equal, expect_none
from exactus.tools.record.selectors import (
    Pace,
    SelectorCodec,
    SelectorDef,
    SelectorError,
    ValidatedOn,
    validate_selectors,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _selector(
    *,
    name: str = "card",
    selector_id: str = "sel-1",
) -> SelectorDef:
    """Build a valid selector.

    Args:
        name: Selector name.
        selector_id: Stable identifier.

    Returns:
        A selector with one check and one validation record.

    """
    return SelectorDef(
        selector_id=selector_id,
        name=name,
        expression="sort(.card, [data-priority])",
        expected_count=None,
        checks=('[aria-disabled!="true"]',),
        validated_on=(
            ValidatedOn(
                url="http://127.0.0.1:8000/",
                at="2026-10-09T00:00Z",
                matches=3,
            ),
        ),
    )


def _build(
    *,
    selector_id: str = "sel-1",
    name: str = "card",
    expression: str = ".card",
    expected_count: int | None = 1,
    checks: tuple[str, ...] = (),
) -> SelectorDef:
    """Build a selector from explicit fields.

    Args:
        selector_id: Stable identifier.
        name: Selector name.
        expression: ExtendedSelector expression.
        expected_count: Exact match count, or ``None``.
        checks: Predicates every match must satisfy.

    Returns:
        The selector, which validates itself on creation.

    """
    return SelectorDef(
        selector_id=selector_id,
        name=name,
        expression=expression,
        expected_count=expected_count,
        checks=checks,
    )


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (partial(_build, name="1bad"), "start with a letter"),
        (partial(_build, name="has-dash"), "start with a letter"),
        (partial(_build, name="x" * 49), "start with a letter"),
        (partial(_build, selector_id=" "), "identifier"),
        (partial(_build, expression="  "), "expression"),
        (partial(_build, expected_count=-1), "negative"),
        (partial(_build, checks=("  ",)), "blank"),
    ],
)
def test_invalid_selectors_are_rejected(
    factory: Callable[[], SelectorDef],
    message: str,
) -> None:
    """Reject names, identifiers and counts that cannot be used.

    Args:
        factory: Builder that supplies one invalid field.
        message: Text the error must contain.

    """
    with pytest.raises(expected_exception=SelectorError, match=message):
        _ = factory()


def test_pace_rejects_unwaitable_values() -> None:
    """Reject negative durations, tiny polls and blank conditions."""
    with pytest.raises(expected_exception=SelectorError, match="negative"):
        _ = Pace(delay_ms=-1)
    with pytest.raises(expected_exception=SelectorError, match="polling"):
        _ = Pace(poll_ms=1)
    with pytest.raises(expected_exception=SelectorError, match="blank"):
        _ = Pace(until="  ")
    expect_equal(actual=Pace().timeout_ms, expected=5000)


def test_selector_set_needs_unique_ids_and_names() -> None:
    """Refuse two selectors that share an identifier or a name."""
    with pytest.raises(expected_exception=SelectorError, match="identifiers"):
        validate_selectors(selectors=(_selector(), _selector(name="other")))
    with pytest.raises(expected_exception=SelectorError, match="names"):
        validate_selectors(
            selectors=(_selector(), _selector(selector_id="sel-2")),
        )


def test_document_round_trip_is_atomic_and_stable(tmp_path: Path) -> None:
    """Write sorted JSON next to the flows and read it back unchanged.

    Args:
        tmp_path: Disposable project folder.

    """
    path: Path = tmp_path / "selectors.pwflow.json"
    selectors: tuple[SelectorDef, ...] = (
        _selector(),
        _selector(name="other", selector_id="sel-2"),
    )
    SelectorCodec.save(path=path, selectors=selectors)
    expect_equal(actual=SelectorCodec.load(path=path), expected=selectors)
    document: dict[str, object] = loads(s=path.read_text(encoding="utf-8"))
    expect_equal(actual=document["version"], expected=1)
    expect_equal(
        actual=[item.name for item in tmp_path.iterdir()],
        expected=["selectors.pwflow.json"],
    )


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"version": 2, "selectors": []},
        {"version": 1},
        {"version": 1, "selectors": ["no"]},
        {"version": 1, "selectors": [{"selector_id": "a", "name": "n"}]},
        {
            "version": 1,
            "selectors": [
                {
                    "selector_id": "a",
                    "name": "n",
                    "expression": ".x",
                    "expected_count": "1",
                },
            ],
        },
    ],
)
def test_malformed_documents_are_rejected(document: object) -> None:
    """Report a clear error instead of loading half a project.

    Args:
        document: JSON value that is not a valid selectors document.

    """
    with pytest.raises(expected_exception=SelectorError):
        _ = SelectorCodec.from_json_value(value=loads(s=dumps(obj=document)))


def test_unreadable_files_are_selector_errors(tmp_path: Path) -> None:
    """Wrap missing and corrupt files in the selectors error type.

    Args:
        tmp_path: Disposable project folder.

    """
    with pytest.raises(expected_exception=SelectorError):
        _ = SelectorCodec.load(path=tmp_path / "missing.json")
    broken: Path = tmp_path / "broken.json"
    _ = broken.write_text(data="{", encoding="utf-8")
    with pytest.raises(expected_exception=SelectorError):
        _ = SelectorCodec.load(path=broken)


def test_pace_round_trip_and_defaults() -> None:
    """Keep every pace field and tolerate a missing pace."""
    expect_none(value=SelectorCodec.pace_from_json(value=None))
    expect_none(value=SelectorCodec.pace_to_json(pace=None))
    pace: Pace = Pace(
        delay_ms=50,
        until="sel_card_count >= 3",
        poll_ms=20,
        timeout_ms=900,
    )
    expect_equal(
        actual=SelectorCodec.pace_from_json(
            value=SelectorCodec.pace_to_json(pace=pace),
        ),
        expected=pace,
    )
    expect_equal(
        actual=SelectorCodec.pace_from_json(value={"delay_ms": 10}),
        expected=Pace(delay_ms=10),
    )
