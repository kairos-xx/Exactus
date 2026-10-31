# Copyright (c) 2026
"""Tests for the deterministic SceneChangeDescriber."""

from exactus.packages.scene_description.changes import (
    ElementChange,
    SceneChangeDescriber,
)
from exactus.packages.scene_description.models import JsonValue
from exactus.tests.common.support import require
from exactus.tests.packages.scene_description.conftest import element, scene
from exactus.tests.packages.scene_description.support import (
    expect_equal,
    expect_false,
    expect_none,
    expect_true,
)


def _describer() -> SceneChangeDescriber:
    """Return a fresh describer instance.

    Returns:
        New ``SceneChangeDescriber``.

    """
    return SceneChangeDescriber()


def test_describe_element_missing_in_both_scenes() -> None:
    """An unmatched selector yields no change."""
    change: ElementChange | None = _describer().describe_element(
        selector="#missing",
        scene_a=scene(),
        scene_b=scene(),
    )
    expect_none(value=change)


def test_describe_element_appeared() -> None:
    """An element present only in B reports as appeared."""
    change: ElementChange = require(
        value=_describer().describe_element(
            selector="#cta",
            scene_a=scene(),
            scene_b=scene(
                elements={"e1": element(selector="#cta", name="Buy now")},
            ),
        ),
    )
    expect_equal(actual=change.selector, expected="#cta")
    expect_equal(actual=change.summary, expected="button “Buy now” appeared.")
    expect_equal(
        actual=change.details,
        expected=("The element is present in B but not in A.",),
    )


def test_describe_element_disappeared() -> None:
    """An element present only in A reports as disappeared."""
    change: ElementChange = require(
        value=_describer().describe_element(
            selector="#cta",
            scene_a=scene(
                elements={"e1": element(selector="#cta", name="Buy now")},
            ),
            scene_b=scene(),
        ),
    )
    expect_equal(
        actual=change.summary,
        expected="button “Buy now” disappeared.",
    )
    expect_equal(
        actual=change.details,
        expected=("The element is present in A but not in B.",),
    )


def test_describe_element_identical() -> None:
    """Identical elements produce no change."""
    shared: dict[str, dict[str, JsonValue]] = {
        "e1": element(selector="#cta", name="Buy now"),
    }
    change: ElementChange | None = _describer().describe_element(
        selector="#cta",
        scene_a=scene(elements=shared),
        scene_b=scene(elements=shared),
    )
    expect_none(value=change)


def test_describe_element_movement() -> None:
    """Translation deltas describe direction and distance."""
    before: dict[str, JsonValue] = element(
        selector="#cta",
        frame={"x": 0.0, "y": 0.0, "width": 100.0, "height": 40.0},
    )
    after: dict[str, JsonValue] = element(
        selector="#cta",
        frame={"x": 24.0, "y": -12.5, "width": 100.0, "height": 40.0},
    )
    change: ElementChange = require(
        value=_describer().describe_element(
            selector="#cta",
            scene_a=scene(elements={"e1": before}),
            scene_b=scene(elements={"e1": after}),
        ),
    )
    expect_equal(
        actual=change.details,
        expected=("moved 24px right and 12.5px up",),
    )
    expect_true(condition=change.summary.endswith("."), message=change.summary)


def test_describe_element_resize() -> None:
    """Geometry deltas describe width and height transitions."""
    before: dict[str, JsonValue] = element(
        selector="#cta",
        frame={"x": 0.0, "y": 0.0, "width": 100.0, "height": 40.0},
    )
    after: dict[str, JsonValue] = element(
        selector="#cta",
        frame={"x": 0.0, "y": 0.0, "width": 120.0, "height": 30.0},
    )
    change: ElementChange = require(
        value=_describer().describe_element(
            selector="#cta",
            scene_a=scene(elements={"e1": before}),
            scene_b=scene(elements={"e1": after}),
        ),
    )
    expect_equal(
        actual=change.details,
        expected=("resized (width 100→120px, height 40→30px)",),
    )


def test_describe_element_below_tolerance() -> None:
    """Sub-tolerance geometry deltas are ignored."""
    before: dict[str, JsonValue] = element(
        selector="#cta",
        frame={"x": 0.0, "y": 0.0, "width": 100.0, "height": 40.0},
    )
    after: dict[str, JsonValue] = element(
        selector="#cta",
        frame={"x": 0.005, "y": 0.0, "width": 100.0, "height": 40.0},
    )
    change: ElementChange | None = _describer().describe_element(
        selector="#cta",
        scene_a=scene(elements={"e1": before}),
        scene_b=scene(elements={"e1": after}),
    )
    expect_none(value=change)


def test_describe_element_missing_frames() -> None:
    """Elements without usable frames skip geometry entirely."""
    before: dict[str, JsonValue] = element(
        selector="#cta",
        frame={"x": 0.0, "y": 0.0, "width": 100.0, "height": 40.0},
    )
    after: dict[str, JsonValue] = element(selector="#cta", text="other")
    change: ElementChange = require(
        value=_describer().describe_element(
            selector="#cta",
            scene_a=scene(elements={"e1": before}),
            scene_b=scene(elements={"e1": after}),
        ),
    )
    expect_equal(
        actual=change.details,
        expected=("text changed from None to 'other'",),
    )


def test_describe_element_identity_fields() -> None:
    """Text, name, and role changes each produce a detail line."""
    before: dict[str, JsonValue] = element(
        selector="#cta",
        name="Old",
        text="old text",
        role="button",
    )
    after: dict[str, JsonValue] = element(
        selector="#cta",
        name="New",
        text="new text",
        role="link",
    )
    change: ElementChange = require(
        value=_describer().describe_element(
            selector="#cta",
            scene_a=scene(elements={"e1": before}),
            scene_b=scene(elements={"e1": after}),
        ),
    )
    expect_equal(
        actual=change.details,
        expected=(
            "text changed from 'old text' to 'new text'",
            "accessible name changed from 'Old' to 'New'",
            "role changed from 'button' to 'link'",
        ),
    )
    expect_true(
        condition=change.summary.startswith("button “New”:"),
        message=change.summary,
    )


def test_element_matches_visual_cause_selector() -> None:
    """``visualCauseSelector`` aliases resolve elements too."""
    target: dict[str, JsonValue] = element(
        selector="#internal",
        visual_cause_selector="main > div:nth-of-type(2)",
        name="Panel",
    )
    change: ElementChange = require(
        value=_describer().describe_element(
            selector="main > div:nth-of-type(2)",
            scene_a=scene(),
            scene_b=scene(elements={"e1": target}),
        ),
    )
    expect_equal(actual=change.summary, expected="button “Panel” appeared.")


def test_elements_requires_dict_container() -> None:
    """Non-dict ``elements`` payloads yield no matches."""
    describer: SceneChangeDescriber = _describer()
    expect_equal(
        actual=describer.describe_scene(
            scene_a={"elements": ["not", "a", "dict"]},
            scene_b=scene(),
        ),
        expected=(),
    )


def test_elements_skips_non_dict_entries() -> None:
    """Malformed element entries are ignored."""
    describer: SceneChangeDescriber = _describer()
    expect_equal(
        actual=describer.describe_scene(
            scene_a={"elements": {"bad1": 42, "bad2": None}},
            scene_b=scene(),
        ),
        expected=(),
    )


def test_selectors_requires_string() -> None:
    """Non-string selectors never join the candidate set."""
    describer: SceneChangeDescriber = _describer()
    expect_equal(
        actual=describer.describe_scene(
            scene_a={"elements": {"e1": {"selector": 7}}},
            scene_b=scene(),
        ),
        expected=(),
    )


def test_describe_scene_sorted_union() -> None:
    """Default candidates are the sorted union of both scenes."""
    scene_a: dict[str, JsonValue] = scene(
        elements={
            "b": element(selector="#b", name="Bee"),
            "a": element(selector="#a", name="Ay"),
        },
    )
    scene_b: dict[str, JsonValue] = scene(
        elements={
            "c": element(selector="#c", name="Cee"),
            "a": element(selector="#a", name="Ay"),
        },
    )
    changes: tuple[ElementChange, ...] = _describer().describe_scene(
        scene_a=scene_a,
        scene_b=scene_b,
    )
    expect_equal(
        actual=[change.selector for change in changes],
        expected=["#b", "#c"],
    )


def test_describe_scene_explicit_selectors() -> None:
    """Callers can restrict description to specific selectors."""
    scene_a: dict[str, JsonValue] = scene(
        elements={"a": element(selector="#a", name="Ay")},
    )
    changes: tuple[ElementChange, ...] = _describer().describe_scene(
        scene_a=scene_a,
        scene_b=scene(),
        selectors=("#a", "#missing"),
    )
    expect_equal(
        actual=[change.selector for change in changes],
        expected=["#a"],
    )


def test_label_falls_back_to_text() -> None:
    """Text evidence labels elements lacking a name."""
    target: dict[str, JsonValue] = element(
        selector="#note",
        name="   ",
        tag="p",
        text="  Hello   world  ",
    )
    change: ElementChange = require(
        value=_describer().describe_element(
            selector="#note",
            scene_a=scene(),
            scene_b=scene(elements={"e": target}),
        ),
    )
    expect_equal(actual=change.summary, expected="p “Hello world” appeared.")


def test_label_falls_back_to_tag_and_selector() -> None:
    """Tag, then the raw selector, label anonymous elements."""
    describer: SceneChangeDescriber = _describer()
    tagged: dict[str, JsonValue] = element(
        selector="#t",
        name=None,
        text=None,
        tag="img",
    )
    change: ElementChange = require(
        value=describer.describe_element(
            selector="#t",
            scene_a=scene(),
            scene_b=scene(elements={"e": tagged}),
        ),
    )
    expect_equal(actual=change.summary, expected="img appeared.")
    tagless: dict[str, JsonValue] = element(
        selector="#t2",
        name=None,
        text=None,
        tag=None,
    )
    change = require(
        value=describer.describe_element(
            selector="#t2",
            scene_a=scene(),
            scene_b=scene(elements={"e": tagless}),
        ),
    )
    expect_equal(actual=change.summary, expected="#t2 appeared.")


def test_label_long_text_truncates() -> None:
    """Long text labels collapse whitespace and truncate at 80 chars."""
    long_text: str = "word " * 30
    target: dict[str, JsonValue] = element(
        selector="#t",
        tag="p",
        text=long_text,
    )
    change: ElementChange = require(
        value=_describer().describe_element(
            selector="#t",
            scene_a=scene(),
            scene_b=scene(elements={"e": target}),
        ),
    )
    compact: str = " ".join(long_text.split())[:80]
    expect_equal(actual=change.summary, expected=f"p “{compact}” appeared.")


def test_frame_requires_visual_and_numeric() -> None:
    """Frame extraction ignores missing or non-numeric geometry."""

    def frame(value: dict[str, JsonValue]) -> dict[str, float]:
        """Return frame.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return SceneChangeDescriber.frame(element=value)

    expect_equal(actual=frame(value={}), expected={})
    expect_equal(actual=frame(value={"visual": "no"}), expected={})
    expect_equal(
        actual=frame(value={"visual": {"viewportFrame": "no"}}),
        expected={},
    )
    expect_equal(
        actual=frame(
            value={
                "visual": {
                    "viewportFrame": {
                        "x": "bad",
                        "y": 1,
                        "width": 2.5,
                        "height": True,
                    },
                },
            },
        ),
        expected={"y": 1.0, "width": 2.5, "height": 1.0},
    )


def test_element_change_as_json() -> None:
    """ElementChange serializes selector, summary, and details list."""
    change: ElementChange = ElementChange(
        selector="#a",
        summary="summary.",
        details=("one", "two"),
    )
    expect_equal(
        actual=change.as_json(),
        expected={
            "selector": "#a",
            "summary": "summary.",
            "details": ["one", "two"],
        },
    )


def test_geometry_without_any_frame_keys() -> None:
    """A present-but-empty viewportFrame skips geometry output."""
    before: dict[str, JsonValue] = element(
        selector="#x",
        visual_cause_selector=None,
        text="a",
    )
    before["visual"] = {"viewportFrame": {"x": "n/a"}}
    after: dict[str, JsonValue] = element(
        selector="#x",
        frame={"x": 1.0, "y": 1.0, "width": 2.0, "height": 2.0},
        text="a",
    )
    change: ElementChange | None = _describer().describe_element(
        selector="#x",
        scene_a=scene(elements={"e": before}),
        scene_b=scene(elements={"e": after}),
    )
    expect_none(value=change)


def test_scene_b_and_a_empty_details() -> None:
    """describe_scene filters selectors producing no change."""
    same: dict[str, JsonValue] = element(selector="#same", name="Same")
    changes: tuple[ElementChange, ...] = _describer().describe_scene(
        scene_a=scene(elements={"e": same}),
        scene_b=scene(elements={"e": same}),
    )
    expect_false(condition=changes)
