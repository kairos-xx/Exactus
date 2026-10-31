# Copyright (c) 2026
"""Focused behavioral coverage for analyzer helper logic."""

from __future__ import annotations

from io import BytesIO
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import pytest
from PIL import Image

from exactus.packages.visual_cause import analyzer as analyzer_module
from exactus.packages.visual_cause.analyzer import (
    AnalysisResults,
    Cause,
    ChangeNode,
    CssTarget,
    CssVisualCause,
    ElementInfo,
    Intervention,
    InvalidBrowserPayloadError,
    JsonValue,
    ProvenanceMaps,
    Rect,
    RuleInfo,
    Settings,
    StyleChange,
)
from exactus.tests.packages.visual_cause.support import (
    Constant,
    dig,
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_in,
    expect_true,
    private,
    private_call,
    private_result,
    set_private,
)

if TYPE_CHECKING:
    from pathlib import Path
    from typing import ClassVar


def _element(
    selector: str,
    dom_path: str,
    parent: str,
    x: float = 0.0,
    z: str = "0",
) -> ElementInfo:
    """Create a compact rendered-element fixture.

    Args:
        selector: Test fixture or input value.
        dom_path: Test fixture or input value.
        parent: Test fixture or input value.
        x: Test fixture or input value.
        z: Test fixture or input value.

    Returns:
        Constructed test fixture.

    """
    return ElementInfo(
        selector=selector,
        dom_path=dom_path,
        parent_path=parent,
        tag="div",
        text="text",
        own_text="text",
        rect=Rect(x=x, y=0.0, width=20.0, height=20.0),
        position="relative",
        z_index=z,
        computed={"display": "block", "color": "rgb(0, 0, 0)"},
        typed_computed={},
        before_content="none",
        after_content="none",
        child_count=0,
        scroll_width=20.0,
        scroll_height=20.0,
        client_width=20.0,
        client_height=20.0,
        overflow_x="visible",
        overflow_y="visible",
    )


def _analyzer(tmp_path: Path) -> CssVisualCause:
    """Create an analyzer without launching a browser.

    Args:
        tmp_path: Test fixture or input value.

    Returns:
        Constructed test fixture.

    """
    a: Path = tmp_path / "a.css"
    b: Path = tmp_path / "b.css"
    a.write_text(data=".a { color: red; }", encoding="utf-8")
    b.write_text(data=".a { color: blue; }", encoding="utf-8")
    return CssVisualCause(
        settings=Settings(
            url="https://example.test/",
            css_a=a,
            css_b=b,
            output=tmp_path / "out",
            width=100,
            height=100,
            threshold=1,
            max_candidates=2,
            timeout_ms=1000,
        ),
    )


def test_rect_url_and_declaration_helpers() -> None:
    """Cover geometry, URL validation, declarations, and style groups."""
    rect: Rect = Rect(x=0, y=0, width=10, height=10)
    expect_equal(actual=rect.right, expected=10)
    expect_equal(actual=rect.bottom, expected=10)
    expect_equal(actual=rect.area, expected=100)
    expect_equal(
        actual=rect.intersection_area(
            other=Rect(x=5, y=5, width=10, height=10),
        ),
        expected=25,
    )
    expect_true(
        condition=rect.intersects(other=Rect(x=9, y=9, width=2, height=2)),
    )
    expect_false(
        condition=rect.intersects(other=Rect(x=10, y=10, width=2, height=2)),
    )
    expect_equal(
        actual=private_call(
            analyzer_module,
            "_validated_url",
            value="https://example.test/a",
        ),
        expected="https://example.test/a",
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="URL must use http",
    ):
        private_call(
            analyzer_module,
            "_validated_url",
            value="javascript:alert(1)",
        )
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_declaration_parts",
            declaration="color: red",
        ),
        expected=("color", "red"),
    )
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_declaration_parts",
            declaration="invalid",
        ),
        expected=("invalid", ""),
    )
    expect_equal(
        actual=private_call(CssVisualCause, "_style_group", name="display"),
        expected="layout",
    )
    expect_equal(
        actual=private_call(CssVisualCause, "_style_group", name="--custom"),
        expected="other",
    )


def test_structural_relationships_and_ranking(tmp_path: Path) -> None:
    """Cover ancestor, descendant, sibling, overlap, and ranking logic.

    Args:
        tmp_path: Test fixture or input value.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    parent: ElementInfo = _element(selector="main", dom_path="main", parent="")
    child: ElementInfo = _element(
        selector="main > div",
        dom_path="main/div",
        parent="main",
    )
    sibling: ElementInfo = _element(
        selector="main > span",
        dom_path="main/span",
        parent="main",
        x=30,
    )
    overlap: ElementInfo = _element(
        selector="aside",
        dom_path="aside",
        parent="",
        x=10,
    )
    elements: tuple[ElementInfo, ...] = (parent, child, sibling, overlap)
    expect_equal(
        actual=private_call(
            analyzer,
            "_relationship",
            source="main",
            target="main > div",
            elements=elements,
        ),
        expected="ancestor",
    )
    expect_equal(
        actual=private_call(
            analyzer,
            "_relationship",
            source="main > div",
            target="main",
            elements=elements,
        ),
        expected="descendant",
    )
    expect_equal(
        actual=private_call(
            analyzer,
            "_relationship",
            source="main > div",
            target="main > span",
            elements=elements,
        ),
        expected="sibling",
    )
    expect_equal(
        actual=private_call(
            analyzer,
            "_relationship",
            source="main > div",
            target="aside",
            elements=elements,
        ),
        expected="overlap",
    )
    expect_equal(
        actual=private_call(
            analyzer,
            "_relationship",
            source="missing",
            target="aside",
            elements=elements,
        ),
        expected="indirect",
    )
    rule: RuleInfo = RuleInfo(
        index=1,
        selector="main",
        css_text="main{}",
        declarations=(),
        matched=("main",),
    )
    relations: tuple[str, ...] = cast(
        typ="tuple[str, ...]",
        val=private_call(
            analyzer,
            "_relations",
            rule=rule,
            affected=(child,),
            elements=elements,
        ),
    )
    expect_in(member="ancestor:main", container=relations)
    expect_equal(
        actual=private_call(
            analyzer,
            "_rank_rules",
            rules=(rule,),
            affected=(child,),
            elements=elements,
        ),
        expected=(rule,),
    )
    expect_equal(
        actual=private_call(
            analyzer,
            "_element_by_selector",
            elements=elements,
            selector="main",
        ),
        expected=parent,
    )
    with pytest.raises(expected_exception=KeyError):
        private_call(
            analyzer,
            "_element_by_selector",
            elements=elements,
            selector="nope",
        )
    expect_equal(
        actual=private_call(
            analyzer,
            "_element_distance",
            reference=parent,
            candidate=child,
        ),
        expected=0.0,
    )


def test_root_cause_paint_and_contributors() -> None:
    """Cover root-cause selection, paint order, and interaction companions."""
    low: dict[str, object] = {"confidence": 0.2}
    high: dict[str, object] = {"confidence": 0.8}
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_strongest_root_cause",
            singles=[low],
            interactions=[high],
            fallback=[],
        ),
        expected=high,
    )
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_strongest_root_cause",
            singles=[high],
            interactions=[low],
            fallback=[],
        ),
        expected=high,
    )
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_strongest_root_cause",
            singles=[],
            interactions=[],
            fallback=[low],
        ),
        expected=low,
    )
    expect_none(
        value=private_call(
            CssVisualCause,
            "_strongest_root_cause",
            singles=[],
            interactions=[],
            fallback=[],
        ),
    )
    first: ElementInfo = _element(selector="a", dom_path="a", parent="", z="1")
    above: ElementInfo = _element(selector="b", dom_path="b", parent="", z="2")
    below: ElementInfo = _element(selector="c", dom_path="c", parent="", z="0")
    unknown: ElementInfo = _element(
        selector="d",
        dom_path="d",
        parent="",
        z="auto",
    )
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_paint_order",
            current=first,
            other=above,
        ),
        expected="other-above",
    )
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_paint_order",
            current=first,
            other=below,
        ),
        expected="other-below",
    )
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_paint_order",
            current=first,
            other=first,
        ),
        expected="same-z-index",
    )
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_paint_order",
            current=first,
            other=unknown,
        ),
        expected="unknown",
    )
    members: list[dict[str, object]] = [
        {"rule_index": 1, "property": "width"},
        {"rule_index": 2, "property": "gap"},
    ]
    interactions: dict[str, list[dict[str, object]]] = {
        "a": [{"members": members}],
    }
    minimal: dict[str, list[dict[str, object]]] = {"a": [{"members": members}]}
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_contributors_for",
            selector="a",
            rule_index=1,
            property_name="width",
            interactions=interactions,
            minimal_sets=minimal,
        ),
        expected=["gap"],
    )


def test_human_summary_and_crops(tmp_path: Path) -> None:
    """Cover human-readable summaries and evidence crop generation.

    Args:
        tmp_path: Test fixture or input value.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    node: ChangeNode = ChangeNode(
        selector="a",
        categories=("layout",),
        origins=("computed-style",),
        mechanisms=("geometry",),
        geometry={"x": {"a": 1.0, "b": 3.0}, "y": {"a": 1.0, "b": 1.0}},
        computed_style_changes={
            "layout": {"display": StyleChange(a="block", b="grid")},
        },
        changed_pixels=10,
    )
    summary: str = private_result(
        analyzer,
        "_human_change_summary",
        str,
        node=node,
    )
    expect_in(member="Geometry", container=summary)
    expect_in(member="display", container=summary)
    unchanged: ChangeNode = ChangeNode(
        selector="a",
        categories=(),
        origins=(),
        mechanisms=(),
        geometry={},
        computed_style_changes={},
        changed_pixels=1,
    )
    expect_in(
        member="pixel-level",
        container=private_result(
            analyzer,
            "_human_change_summary",
            str,
            node=unchanged,
        ),
    )
    image_a: Image.Image = Image.new(mode="RGB", size=(50, 50), color="white")
    image_b: Image.Image = Image.new(mode="RGB", size=(50, 50), color="black")
    evidence: Path = analyzer.settings.output / "evidence"
    evidence.mkdir(parents=True)
    paths: tuple[str, str, str] = cast(
        typ="tuple[str, str, str]",
        val=private_call(
            analyzer,
            "_save_element_crops",
            image_a=image_a,
            image_b=image_b,
            element=_element(selector="a", dom_path="a", parent="", x=5),
            evidence=evidence,
            stem="sample",
        ),
    )
    expect_true(
        condition=all(
            (analyzer.settings.output / path).is_file() for path in paths
        ),
    )
    expect_true(
        condition=private_call(
            CssVisualCause,
            "_safe_evidence_name",
            rule_index=1,
            property_name="grid/template",
            selector="a > b",
        ),
    )


def test_change_forest_serializes_relations(tmp_path: Path) -> None:
    """Cover recursive changed-node serialization and causal annotations.

    Args:
        tmp_path: Test fixture or input value.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    parent: ElementInfo = _element(selector="main", dom_path="main", parent="")
    child: ElementInfo = _element(
        selector="main > div",
        dom_path="main/div",
        parent="main",
    )
    nodes: tuple[ChangeNode, ...] = tuple(
        ChangeNode(
            selector=e.selector,
            categories=("layout",),
            origins=("computed-style",),
            mechanisms=("layout",),
            geometry={},
            computed_style_changes={},
            changed_pixels=2,
        )
        for e in (parent, child)
    )
    cause: Cause = Cause(
        index=0,
        selector="main",
        css_text="main { display: grid; }",
        declarations=("display: grid",),
        matched=("main",),
        relations=("ancestor:main > div",),
        changed_pixels_without_rule=0,
        pixels_explained=2,
        explanation_ratio=1.0,
    )
    forest: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=private_call(
            analyzer,
            "_change_forest",
            nodes=nodes,
            causes=(cause,),
            elements=(parent, child),
            elements_a=(parent, child),
            provenance=ProvenanceMaps(
                causal_edges={},
                declaration_provenance={},
                function_provenance={},
                cascade_provenance={},
                interaction_provenance={},
                minimal_sets={},
            ),
        ),
    )
    expect_equal(
        actual=dig(document=forest, path=(0, "selector")),
        expected="main",
    )
    expect_equal(
        actual=dig(
            document=forest,
            path=(0, "relations", "descendants", 0, "selector"),
        ),
        expected="main > div",
    )


def test_rule_and_element_payload_validation(tmp_path: Path) -> None:
    """Parse valid browser JSON and reject malformed browser payloads.

    Args:
        tmp_path: Test fixture or input value.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)

    class PageStub:
        @staticmethod
        def evaluate(expression: str, arg: str | None = None) -> str:
            expect_true(condition=expression)
            expect_none(value=arg)
            return (
                '[{"index":0,"selector":".a",'
                '"cssText":".a { color: red; }",'
                '"declarations":["color: red"],"matched":[".a"]}]'
            )

    rules: tuple[RuleInfo, ...] = cast(
        typ="tuple[RuleInfo, ...]",
        val=private_call(analyzer, "_read_rules", page=PageStub()),
    )
    expect_equal(actual=rules[0].selector, expected=".a")
    with pytest.raises(expected_exception=InvalidBrowserPayloadError):
        private_call(CssVisualCause, "_parse_elements", raw='{"bad": true}')
    raw: str = dedent(
        text=(
            '    [{\n            "selector":".a","domPath":"html/body/div","pa'
            'rentPath":"html/body",\n            "tag":"div","text":"A","ownTe'
            'xt":"A","x":1,"y":2,"width":3,\n            "height":4,"position"'
            ':"static","zIndex":"auto","computed":{"display":"block"},\n      '
            '      "typedComputed":{"width":{"type":"CSSUnitValue","text":"3px'
            '"}},\n            "beforeContent":"none","afterContent":"none","c'
            'hildCount":0,\n            "scrollWidth":3,"scrollHeight":4,"clie'
            'ntWidth":3,"clientHeight":4,\n            "overflowX":"visible","'
            'overflowY":"visible"\n        }]'
        ),
    )
    elements: tuple[ElementInfo, ...] = cast(
        typ="tuple[ElementInfo, ...]",
        val=private_call(CssVisualCause, "_parse_elements", raw=raw),
    )
    expect_equal(
        actual=elements[0].rect,
        expected=Rect(x=1.0, y=2.0, width=3.0, height=4.0),
    )


def test_variable_chains_cycles_and_content_delta() -> None:
    """Resolve custom-property chains, cycles, and rendered-content deltas."""
    records: list[dict[str, JsonValue]] = [
        {
            "defines": "--a",
            "selector": ":root",
            "references": ["--b"],
            "authored_value": "var(--b)",
        },
        {
            "defines": "--b",
            "selector": ":root",
            "references": ["--a"],
            "authored_value": "var(--a)",
        },
        {
            "selector": ".x",
            "property": "width",
            "references": ["--a"],
            "authored_value": "var(--a)",
        },
    ]
    chains: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=private_call(CssVisualCause, "_variable_chains", records=records),
    )
    expect_true(
        condition=any(
            dig(document=item, path=("consumer", "selector")) == ".x"
            for item in chains
        ),
    )
    before: ElementInfo = _element(selector="a", dom_path="a", parent="")
    after: ElementInfo = ElementInfo(
        selector=before.selector,
        dom_path=before.dom_path,
        parent_path=before.parent_path,
        tag=before.tag,
        text="changed",
        own_text="changed",
        rect=before.rect,
        position=before.position,
        z_index=before.z_index,
        computed=before.computed,
        typed_computed=before.typed_computed,
        before_content='"before"',
        after_content='"after"',
        child_count=1,
        scroll_width=30,
        scroll_height=25,
        client_width=20,
        client_height=20,
        overflow_x="auto",
        overflow_y="scroll",
    )
    delta: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=private_call(
            CssVisualCause,
            "_content_delta",
            before=before,
            after=after,
        ),
    )
    expect_equal(
        actual=dig(document=delta, path=("text", "b")),
        expected="changed",
    )
    expect_none(
        value=private_call(
            CssVisualCause,
            "_content_delta",
            before=before,
            after=before,
        ),
    )


def test_candidate_order_provenance_and_numeric_helpers(
    tmp_path: Path,
) -> None:
    """Cover changed-rule priority and single-declaration evidence.

    Args:
        tmp_path: Test fixture or input value.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    old: RuleInfo = RuleInfo(
        index=0,
        selector=".a",
        css_text=".a{color:red}",
        declarations=("color: red",),
        matched=("a",),
    )
    new: RuleInfo = RuleInfo(
        index=1,
        selector=".a",
        css_text=".a{color:blue}",
        declarations=("color: blue",),
        matched=("a",),
    )
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_changed_rule_candidates",
            rules_a=(old,),
            ranked=(old, new),
        ),
        expected=(new,),
    )
    before: ElementInfo = _element(selector="a", dom_path="a", parent="")
    after: ElementInfo = ElementInfo(
        selector=before.selector,
        dom_path=before.dom_path,
        parent_path=before.parent_path,
        tag=before.tag,
        text=before.text,
        own_text=before.own_text,
        rect=before.rect,
        position=before.position,
        z_index=before.z_index,
        computed={"color": "blue"},
        typed_computed={},
        before_content="none",
        after_content="none",
        child_count=0,
        scroll_width=20,
        scroll_height=20,
        client_width=20,
        client_height=20,
        overflow_x="visible",
        overflow_y="visible",
    )
    set_private(analyzer, "_last_elements_b", (after,))
    node: ChangeNode = ChangeNode(
        selector="a",
        categories=(),
        origins=(),
        mechanisms=(),
        geometry={},
        computed_style_changes={},
        changed_pixels=1,
    )
    cause: Cause = Cause(
        index=1,
        selector=".a",
        css_text=new.css_text,
        declarations=new.declarations,
        matched=("a",),
        relations=(),
        changed_pixels_without_rule=0,
        pixels_explained=5,
        explanation_ratio=0.5,
    )
    evidence: dict[str, list[dict[str, JsonValue]]] = cast(
        typ="dict[str, list[dict[str, JsonValue]]]",
        val=private_call(
            analyzer,
            "_single_declaration_provenance",
            nodes=(node,),
            causes=(cause,),
            elements_a=(before,),
        ),
    )
    expect_equal(
        actual=dig(document=evidence, path=("a", 0, "property")),
        expected="color",
    )
    expect_equal(
        actual=private_call(CssVisualCause, "_json_float", value=2),
        expected=2.0,
    )
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_json_float",
            value=True,
            default=3.0,
        ),
        expected=3.0,
    )
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_parent_selector",
            selector="a > b > c",
        ),
        expected="a > b",
    )
    expect_equal(
        actual=private_call(CssVisualCause, "_parent_selector", selector="a"),
        expected="",
    )


def test_budget_navigation_and_side_url(tmp_path: Path) -> None:
    """Cover bounded-budget expiration, navigation modes, and B URL selection.

    Args:
        tmp_path: Test fixture or input value.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    set_private(analyzer, "_deadline", 0.0)
    expect_false(condition=private_result(analyzer, "_budget_available", bool))
    expect_false(
        condition=private_result(
            analyzer,
            "_require_budget",
            bool,
            phase="test",
        ),
    )
    expect_true(
        condition=(analyzer.settings.output / "progress.json").is_file(),
    )
    set_private(analyzer, "_deadline", None)
    expect_true(
        condition=private_result(
            analyzer,
            "_require_budget",
            bool,
            phase="test",
        ),
    )

    class PageStub:
        def __init__(self) -> None:
            self.content: str = ""
            self.url: str = ""
            self.waited: int = 0

        def set_content(
            self,
            *,
            html: str,
            wait_until: str,
            timeout: int,
        ) -> None:
            self.content = html
            expect_equal(actual=wait_until, expected="domcontentloaded")
            expect_equal(actual=timeout, expected=1000)

        def goto(self, *, url: str, wait_until: str, timeout: int) -> None:
            self.url = url
            expect_equal(actual=wait_until, expected="domcontentloaded")
            expect_equal(actual=timeout, expected=1000)

        def wait_for_timeout(self, *, timeout: int) -> None:
            self.waited += timeout

    html: Path = tmp_path / "page.html"
    html.write_text(data="<p>ok</p>", encoding="utf-8")
    page: PageStub = PageStub()
    private_call(analyzer, "_navigate", page=page, url=html.as_uri())
    expect_equal(actual=page.content, expected="<p>ok</p>")
    private_call(analyzer, "_navigate", page=page, url="https://example.test/")
    expect_equal(actual=page.url, expected="https://example.test/")
    expect_equal(actual=page.waited, expected=100)


def test_pixel_regions_and_change_classification(tmp_path: Path) -> None:
    """Cover image-difference regions and propagated/computed classifications.

    Args:
        tmp_path: Test fixture or input value.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    image_a: Image.Image = Image.new(mode="RGB", size=(10, 10), color="white")
    image_b: Image.Image = Image.new(mode="RGB", size=(10, 10), color="white")
    for point in ((2, 2), (2, 3), (8, 8)):
        image_b.putpixel(xy=point, value=(0, 0, 0))
    expect_equal(
        actual=private_call(
            analyzer,
            "_changed_pixels",
            image_a=image_a,
            image_b=image_b,
        ),
        expected=3,
    )
    regions: tuple[Rect, ...] = cast(
        typ="tuple[Rect, ...]",
        val=private_call(
            analyzer,
            "_regions",
            image_a=image_a,
            image_b=image_b,
        ),
    )
    expect_equal(actual=len(regions), expected=1)
    expect_equal(actual=regions[0].height, expected=2.0)
    expect_equal(
        actual=private_call(
            CssVisualCause,
            "_pixels_in_rect",
            mask=private_call(
                analyzer,
                "_difference_mask",
                image_a=image_a,
                image_b=image_b,
            ),
            rect=Rect(x=50, y=50, width=1, height=1),
        ),
        expected=0,
    )
    before: ElementInfo = _element(selector="a", dom_path="a", parent="")
    after: ElementInfo = ElementInfo(
        selector=before.selector,
        dom_path=before.dom_path,
        parent_path=before.parent_path,
        tag=before.tag,
        text=before.text,
        own_text=before.own_text,
        rect=Rect(x=2, y=0, width=25, height=20),
        position=before.position,
        z_index=before.z_index,
        computed={
            "display": "grid",
            "color": "rgb(1, 2, 3)",
            "transform": "matrix(1,0,0,1,2,0)",
        },
        typed_computed={},
        before_content="none",
        after_content="none",
        child_count=0,
        scroll_width=25,
        scroll_height=20,
        client_width=25,
        client_height=20,
        overflow_x="visible",
        overflow_y="visible",
    )
    nodes: tuple[ChangeNode, ...] = cast(
        typ="tuple[ChangeNode, ...]",
        val=private_call(
            analyzer,
            "_change_nodes",
            image_a=image_a,
            image_b=image_b,
            elements_a=(before,),
            affected=(after,),
        ),
    )
    expect_equal(
        actual=nodes[0].categories,
        expected=("position", "size", "color", "style"),
    )
    expect_in(member="layout", container=nodes[0].mechanisms)
    expect_in(member="paint", container=nodes[0].mechanisms)
    expect_in(member="transform", container=nodes[0].mechanisms)


def test_run_failure_path_and_provenance_skips(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist diagnostics from ``run`` and cover provenance filtering.

    Args:
        tmp_path: Test fixture or input value.
        monkeypatch: Test fixture or input value.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)

    def fail() -> None:
        """Raise the synthetic analyzer failure.

        Raises:
            RuntimeError: Always, to exercise failure persistence.

        """
        msg: str = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(target=analyzer, name="_run_analysis", value=fail)
    with pytest.raises(expected_exception=RuntimeError, match="boom"):
        analyzer.run()
    expect_true(
        condition=(analyzer.settings.output / "failure.json").is_file(),
    )
    before: ElementInfo = _element(selector="a", dom_path="a", parent="")
    set_private(analyzer, "_last_elements_b", (before,))
    node: ChangeNode = ChangeNode(
        selector="a",
        categories=(),
        origins=(),
        mechanisms=(),
        geometry={},
        computed_style_changes={},
        changed_pixels=1,
    )
    multi: Cause = Cause(
        index=0,
        selector=".a",
        css_text="",
        declarations=("a: 1", "b: 2"),
        matched=("a",),
        relations=(),
        changed_pixels_without_rule=0,
        pixels_explained=1,
        explanation_ratio=1.0,
    )
    unmatched: Cause = Cause(
        index=1,
        selector=".b",
        css_text="",
        declarations=("a: 1",),
        matched=("b",),
        relations=(),
        changed_pixels_without_rule=0,
        pixels_explained=1,
        explanation_ratio=1.0,
    )
    expect_equal(
        actual=private_call(
            analyzer,
            "_single_declaration_provenance",
            nodes=(node,),
            causes=(multi, unmatched),
            elements_a=(before,),
        ),
        expected={"a": []},
    )


def test_serial_rule_trials_with_recyclable_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise bounded serial rule trials without launching Chromium.

    Args:
        tmp_path: Test fixture or input value.
        monkeypatch: Test fixture or input value.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    baseline_image: Image.Image = Image.new(
        mode="RGB",
        size=(4, 4),
        color="white",
    )
    trial_image: Image.Image = Image.new(
        mode="RGB",
        size=(4, 4),
        color="white",
    )
    trial_image.putpixel(xy=(0, 0), value=(0, 0, 0))

    class PageStub:
        pass

    class ContextStub:
        closed: bool = False

        @staticmethod
        def new_page() -> PageStub:
            return PageStub()

        def close(self) -> None:
            self.closed = True

    class BrowserStub:
        context: ContextStub = ContextStub()

        def new_context(self, **kwargs: object) -> ContextStub:
            expect_equal(actual=kwargs["device_scale_factor"], expected=1.0)
            return self.context

    monkeypatch.setattr(
        target=analyzer,
        name="_render_page",
        value=Constant(value=(trial_image, (), ())),
    )
    rule: RuleInfo = RuleInfo(
        index=0,
        selector=".a",
        css_text=".a{}",
        declarations=(),
        matched=("a",),
    )
    browser: BrowserStub = BrowserStub()
    results: list[tuple[RuleInfo, int, int]] = cast(
        typ="list[tuple[RuleInfo, int, int]]",
        val=private_call(
            analyzer,
            "_serial_rule_trials",
            browser=browser,
            rules=(rule,),
            image_a=baseline_image,
            baseline=2,
        ),
    )
    expect_equal(actual=results[0][1:], expected=(1, 1))
    expect_true(condition=browser.context.closed)


def test_missing_target_and_trial_budget_break(tmp_path: Path) -> None:
    """Cover missing CSS targets and pre-expired rule-trial budgets.

    Args:
        tmp_path: Test fixture or input value.

    """
    with pytest.raises(expected_exception=FileNotFoundError):
        CssTarget.load(source=tmp_path / "missing.css")
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    set_private(analyzer, "_deadline", 0.0)

    class ContextStub:
        @staticmethod
        def new_page() -> object:
            return object()

        @staticmethod
        def close() -> None:
            return None

    class BrowserStub:
        @staticmethod
        def new_context(**_: object) -> ContextStub:
            return ContextStub()

    rule: RuleInfo = RuleInfo(
        index=0,
        selector=".a",
        css_text=".a{}",
        declarations=(),
        matched=("a",),
    )
    results: list[tuple[RuleInfo, int, int]] = cast(
        typ="list[tuple[RuleInfo, int, int]]",
        val=private_call(
            analyzer,
            "_serial_rule_trials",
            browser=BrowserStub(),
            rules=(rule,),
            image_a=Image.new(mode="RGB", size=(1, 1)),
            baseline=1,
        ),
    )
    expect_equal(actual=results, expected=[])


def test_structural_image_analysis_and_rich_report(tmp_path: Path) -> None:
    """Cover structural image analysis and CSS-first Markdown evidence.

    Args:
        tmp_path: Temporary test directory.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    first: ElementInfo = _element(
        selector=".a",
        dom_path="html/body/a",
        parent="html/body",
        x=5,
    )
    second: ElementInfo = _element(
        selector=".b",
        dom_path="html/body/b",
        parent="html/body",
        x=5,
    )
    structure: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=private_call(
            analyzer,
            "_structural_analysis",
            image_a=Image.new(mode="RGB", size=(100, 100), color="white"),
            image_b=Image.new(mode="RGB", size=(100, 100), color="black"),
            regions=(
                Rect(x=0, y=0, width=20, height=10),
                Rect(x=30, y=20, width=20, height=10),
            ),
            elements=(first, second),
        ),
    )
    expect_equal(actual=structure["changed_region_count"], expected=2)
    expect_equal(actual=structure["changed_region_area_ratio"], expected=0.04)
    expect_equal(
        actual=dig(document=structure, path=("alignment_pairs", "left")),
        expected=1,
    )
    expect_equal(
        actual=structure["repeated_geometry_groups"],
        expected=[{"size": "20x20", "count": 2}],
    )
    node: ChangeNode = ChangeNode(
        selector=".a",
        categories=("layout",),
        origins=("computed-style",),
        mechanisms=("geometry",),
        geometry={"x": {"a": 0.0, "b": 5.0}},
        computed_style_changes={
            "layout": {"display": StyleChange(a="block", b="grid")},
        },
        changed_pixels=20,
    )
    rule: RuleInfo = RuleInfo(
        index=0,
        selector=".a",
        css_text=".a { display: grid; }",
        declarations=("display: grid",),
        matched=(".a",),
    )
    set_private(analyzer, "_last_elements_b", (first,))
    image_a: Image.Image = Image.new(
        mode="RGB",
        size=(200, 200),
        color="white",
    )
    image_b: Image.Image = Image.new(
        mode="RGB",
        size=(200, 200),
        color="black",
    )
    private_call(
        analyzer,
        "_write_human_report",
        results=AnalysisResults(
            baseline=10,
            regions=(),
            affected=(first,),
            nodes=(node,),
            causes=(),
            elements_a=(first,),
            rules_b=(rule,),
            evidence_image_a=image_a,
            evidence_image_b=image_b,
            analysis_image_a=image_a,
            analysis_image_b=image_b,
            provenance=ProvenanceMaps(
                causal_edges={},
                declaration_provenance={
                    ".a": [
                        {
                            "rule_index": 0,
                            "property": "display",
                            "authored_value": "grid",
                            "improvement": 20.0,
                            "confidence": 0.5,
                        },
                    ],
                },
                function_provenance={
                    ".a": [
                        {
                            "rule_index": 0,
                            "property": "display",
                            "a": "block",
                            "b": "grid",
                            "confidence": 0.5,
                        },
                    ],
                },
                cascade_provenance={},
                interaction_provenance={},
                minimal_sets={},
            ),
        ),
        structure=structure,
    )
    report: str = (analyzer.settings.output / "report.md").read_text(
        encoding="utf-8",
    )
    expect_in(member="## Executive summary", container=report)
    expect_in(member="## Structural image analysis", container=report)
    expect_in(member="## Visual overview", container=report)
    expect_in(member="Affected element `.a`", container=report)
    expect_in(member="Causal value fragments", container=report)
    expect_equal(
        actual=len(
            tuple(
                (analyzer.settings.output / "evidence").glob(pattern="*.png"),
            ),
        ),
        expected=3,
    )


def test_run_analysis_orchestration_and_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the full orchestration path with deterministic stubs.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    element: ElementInfo = _element(
        selector=".a",
        dom_path="html/body/a",
        parent="html/body",
    )
    rule: RuleInfo = RuleInfo(
        index=0,
        selector=".a",
        css_text=".a { color: blue; }",
        declarations=("color: blue",),
        matched=(".a",),
    )
    image_a: Image.Image = Image.new(mode="RGB", size=(20, 20), color="white")
    image_b: Image.Image = Image.new(mode="RGB", size=(20, 20), color="black")

    class BrowserStub:
        @staticmethod
        def close() -> None:
            """Record browser closure."""

    class ChromiumStub:
        @staticmethod
        def launch(**kwargs: object) -> BrowserStub:
            """Return the deterministic browser stub.

            Args:
                **kwargs: Ignored browser launch settings.

            Returns:
                Browser stub.

            """
            expect_true(condition=kwargs["headless"] is True)
            return BrowserStub()

    class PlaywrightStub:
        chromium: ChromiumStub = ChromiumStub()

    class ManagerStub:
        def __enter__(self) -> PlaywrightStub:
            """Enter the synthetic Playwright manager.

            Returns:
                Entered stub.

            """
            return PlaywrightStub()

        def __exit__(self, *args: object) -> None:
            """Exit the synthetic Playwright manager.

            Args:
                *args: Context-manager exception state.

            """

    monkeypatch.setattr(
        target="exactus.packages.visual_cause.analyzer.sync_playwright",
        name=Constant(value=ManagerStub()),
    )
    renders: list[Image.Image] = [image_a, image_b]

    def render_stub(
        **_kwargs: object,
    ) -> tuple[Image.Image, tuple[ElementInfo, ...], tuple[RuleInfo, ...]]:
        """Return successive renders for the two baselines.

        Args:
            **_kwargs: Ignored render arguments.

        Returns:
            Image, element, and rule triple for the next baseline.

        """
        return renders.pop(0), (element,), (rule,)

    monkeypatch.setattr(target=analyzer, name="_render", value=render_stub)
    monkeypatch.setattr(
        target=analyzer,
        name="_changed_pixels",
        value=Constant(value=10),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_regions",
        value=Constant(value=(Rect(x=0, y=0, width=20, height=20),)),
    )
    node: ChangeNode = ChangeNode(
        selector=".a",
        categories=("paint",),
        origins=("css",),
        mechanisms=("color",),
        geometry={},
        computed_style_changes={},
        changed_pixels=10,
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_change_nodes",
        value=Constant(value=(node,)),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_rank_rules",
        value=Constant(value=(rule,)),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_changed_rule_candidates",
        value=Constant(value=(rule,)),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_serial_rule_trials",
        value=Constant(value=[(rule, 0, 10)]),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_relations",
        value=Constant(value=("self:.a",)),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_causal_edges",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_declaration_trials",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_function_provenance",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_cascade_provenance",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_interaction_provenance",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_minimal_cause_sets",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    written: list[bool] = []

    def record_write(**_kwargs: object) -> None:
        """Record each synthesized report write.

        Args:
            **_kwargs: Ignored write arguments.

        """
        written.append(True)

    def fail_analysis() -> None:
        """Raise the synthetic analyzer failure.

        Raises:
            RuntimeError: Always, carrying ``boom``.

        """
        msg: str = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        target=analyzer,
        name="_write_outputs",
        value=record_write,
    )
    private_call(analyzer, "_run_analysis")
    expect_equal(actual=written, expected=[True])
    monkeypatch.setattr(
        target=analyzer,
        name="_run_analysis",
        value=fail_analysis,
    )
    with pytest.raises(expected_exception=RuntimeError, match="boom"):
        analyzer.run()
    expect_true(
        condition=(analyzer.settings.output / "failure.json").is_file(),
    )


class _CdpLocatorStub:
    """Stub the Playwright locator boundary."""

    @staticmethod
    def evaluate(**_kwargs: object) -> None:
        """Accept stylesheet injection.

        Args:
            **_kwargs: Playwright evaluation arguments.

        """


class _CdpPageStub:
    """Stub the Playwright page boundary."""

    @staticmethod
    def evaluate(**_kwargs: object) -> str:
        """Accept browser setup evaluations.

        Args:
            **_kwargs: Playwright evaluation arguments.

        Returns:
            Empty JSON payload.

        """
        return "{}"

    @staticmethod
    def locator(**_kwargs: object) -> _CdpLocatorStub:
        """Return a locator stub.

        Args:
            **_kwargs: Locator arguments.

        Returns:
            Locator stub.

        """
        return _CdpLocatorStub()


class _CdpSessionStub:
    """Stub the Playwright CDP session boundary."""

    @staticmethod
    def send(
        method: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Return deterministic CDP responses.

        Args:
            method: CDP method name.
            params: Optional CDP parameters.

        Returns:
            Synthetic CDP response.

        """
        if method == "DOM.getDocument":
            return {"root": {"nodeId": 1}}
        if method == "DOM.querySelector":
            expect_true(condition=params is not None)
            return {"nodeId": 2}
        if method == "CSS.getMatchedStylesForNode":
            return {
                "matchedCSSRules": [
                    {"rule": {"selectorList": {"text": ".a"}}},
                ],
            }
        if method == "CSS.getComputedStyleForNode":
            return {
                "computedStyle": [
                    {"name": "color", "value": "rgb(0, 0, 255)"},
                ],
            }
        return {}


class _CdpContextStub:
    """Stub the Playwright browser-context boundary.

    Attributes:
        page: Shared page stub returned by ``new_page``.

    """

    page: ClassVar[_CdpPageStub] = _CdpPageStub()

    @staticmethod
    def new_cdp_session(**_kwargs: object) -> _CdpSessionStub:
        """Return the CDP session stub.

        Args:
            **_kwargs: CDP-session arguments.

        Returns:
            Session stub.

        """
        return _CdpSessionStub()

    @staticmethod
    def close() -> None:
        """Close the context stub."""

    def new_page(self) -> _CdpPageStub:
        """Return the page stub.

        Returns:
            Shared page stub.

        """
        return self.page


class _CdpBrowserStub:
    """Stub the Playwright browser boundary."""

    @staticmethod
    def new_context(**kwargs: object) -> _CdpContextStub:
        """Return the context stub.

        Args:
            **kwargs: Browser-context arguments.

        Returns:
            Context stub.

        """
        expect_equal(actual=kwargs["device_scale_factor"], expected=2.0)
        return _CdpContextStub()


def test_cascade_provenance_cdp_success_and_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise Chromium CDP cascade provenance and per-node recovery.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    node: ChangeNode = ChangeNode(
        selector=".a",
        categories=(),
        origins=(),
        mechanisms=(),
        geometry={},
        computed_style_changes={},
        changed_pixels=1,
    )
    shadow: ChangeNode = ChangeNode(
        selector="#shadow-root .x",
        categories=(),
        origins=(),
        mechanisms=(),
        geometry={},
        computed_style_changes={},
        changed_pixels=1,
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_navigate",
        value=Constant(value=None),
    )
    output: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=private_call(
            analyzer,
            "_cascade_provenance",
            browser=_CdpBrowserStub(),
            nodes=(node, shadow),
        ),
    )
    expect_equal(
        actual=dig(document=output, path=(".a", "source")),
        expected="chromium-cdp",
    )
    expect_not_in(member="#shadow-root .x", container=output)


def test_render_page_high_density_and_interventions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture device-scale evidence while keeping CSS-pixel analysis geometry.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    analyzer.settings = Settings(
        url=analyzer.settings.url,
        css_a=analyzer.settings.css_a,
        css_b=analyzer.settings.css_b,
        output=analyzer.settings.output,
        width=100,
        height=100,
        threshold=1,
        max_candidates=2,
        timeout_ms=1000,
        screenshot_scale=2.0,
    )
    buffer: BytesIO = BytesIO()
    Image.new(mode="RGBA", size=(200, 100), color="white").save(
        fp=buffer,
        format="PNG",
    )
    png: bytes = buffer.getvalue()

    class LocatorStub:
        @staticmethod
        def evaluate(**_kwargs: object) -> None:
            """Accept stylesheet injection.

            Args:
                **_kwargs: Evaluation arguments.

            """

    class PageStub:
        calls: ClassVar[list[str]] = []

        def evaluate(
            self,
            *,
            expression: str,
            arg: object | None = None,
        ) -> str:
            """Return payloads for the requested browser program.

            Args:
                expression: Browser JavaScript expression.
                arg: Optional expression argument.

            Returns:
                JSON string when the browser program expects one.

            """
            del arg
            self.calls.append(expression)
            if expression == private(analyzer, "_RULES_JS"):
                return (
                    '[{"index":0,"selector":".a",'
                    '"cssText":".a { color: blue; }",'
                    '"declarations":["color: blue"],"matched":[".a"]}]'
                )
            if expression == private(analyzer, "_ELEMENTS_JS"):
                return "[]"
            if expression == private(analyzer, "_CONTAINER_RULES_JS"):
                return "[]"
            return "null"

        @staticmethod
        def locator(*, selector: str) -> LocatorStub:
            """Return the style locator.

            Args:
                selector: CSS selector.

            Returns:
                Locator stub.

            """
            expect_equal(actual=selector, expected="#__css_cause_style__")
            return LocatorStub()

        @staticmethod
        def screenshot(**kwargs: object) -> bytes:
            """Return a synthetic screenshot.

            Args:
                **kwargs: Screenshot settings.

            Returns:
                PNG bytes.

            """
            if kwargs["scale"] == "css":
                css_buffer: BytesIO = BytesIO()
                Image.new(mode="RGBA", size=(100, 50), color="white").save(
                    fp=css_buffer,
                    format="PNG",
                )
                return css_buffer.getvalue()
            return png

    page: PageStub = PageStub()
    monkeypatch.setattr(
        target=analyzer,
        name="_navigate",
        value=Constant(value=None),
    )
    image, elements, rules = cast(
        typ=(
            "tuple[Image.Image, tuple[ElementInfo, ...], tuple[RuleInfo, ...]]"
        ),
        val=private_call(
            analyzer,
            "_render_page",
            page=page,
            css=analyzer.css_b,
            intervention=Intervention(
                disabled_rule=0,
                element_override=(".a", {"color": "red"}),
                disabled_declarations=((0, "color"), (0, "width")),
            ),
        ),
    )
    expect_equal(actual=image.size, expected=(100, 50))
    expect_equal(actual=elements, expected=())
    expect_equal(actual=rules[0].selector, expected=".a")
    expect_in(
        member=private(analyzer, "_DISABLE_DECLARATIONS_JS"),
        container=page.calls,
    )
    expect_in(
        member=private(analyzer, "_OVERRIDE_ELEMENT_JS"),
        container=page.calls,
    )


def test_interactions_minimal_sets_and_causal_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise multi-property and cross-element causal experiments.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    reference: ElementInfo = _element(
        selector=".a",
        dom_path="html/body/a",
        parent="html/body",
        x=0,
    )
    baseline: ElementInfo = _element(
        selector=".a",
        dom_path="html/body/a",
        parent="html/body",
        x=10,
    )
    other_ref: ElementInfo = _element(
        selector=".b",
        dom_path="html/body/b",
        parent="html/body",
        x=30,
    )
    other_base: ElementInfo = _element(
        selector=".b",
        dom_path="html/body/b",
        parent="html/body",
        x=40,
    )
    set_private(analyzer, "_last_elements_b", (baseline, other_base))
    node: ChangeNode = ChangeNode(
        selector=".a",
        categories=("layout",),
        origins=("computed-style",),
        mechanisms=("geometry",),
        geometry={"x": {"a": 0.0, "b": 10.0}},
        computed_style_changes={
            "layout": {"width": StyleChange(a="10px", b="20px")},
        },
        changed_pixels=10,
    )
    other_node: ChangeNode = ChangeNode(
        selector=".b",
        categories=("layout",),
        origins=("computed-style",),
        mechanisms=("geometry",),
        geometry={"x": {"a": 30.0, "b": 40.0}},
        computed_style_changes={},
        changed_pixels=10,
    )
    rule: RuleInfo = RuleInfo(
        index=0,
        selector=".a",
        css_text=".a { width: 20px; gap: 5px; }",
        declarations=("width: 20px", "gap: 5px"),
        matched=(".a",),
    )

    def fake_render(
        **_kwargs: object,
    ) -> tuple[Image.Image, tuple[ElementInfo, ...], tuple[RuleInfo, ...]]:
        """Return reference geometry for every intervention.

        Args:
            **_kwargs: Counterfactual render arguments.

        Returns:
            Synthetic counterfactual render.

        """
        return (
            Image.new(mode="RGB", size=(10, 10)),
            (reference, other_ref),
            (rule,),
        )

    monkeypatch.setattr(target=analyzer, name="_render", value=fake_render)
    interactions: dict[str, list[dict[str, JsonValue]]] = cast(
        typ="dict[str, list[dict[str, JsonValue]]]",
        val=private_call(
            analyzer,
            "_interaction_provenance",
            browser=object(),
            nodes=(node,),
            rules=(rule,),
            elements_a=(reference,),
            singles={".a": []},
        ),
    )
    expect_equal(
        actual=dig(document=interactions, path=(".a", 0, "kind")),
        expected="interaction",
    )
    minimum: dict[str, list[dict[str, JsonValue]]] = cast(
        typ="dict[str, list[dict[str, JsonValue]]]",
        val=private_call(
            analyzer,
            "_minimal_cause_sets",
            browser=object(),
            nodes=(node,),
            rules=(rule,),
            elements_a=(reference,),
        ),
    )
    expect_equal(
        actual=dig(document=minimum, path=(".a", 0, "confidence")),
        expected=1.0,
    )
    edges: dict[str, list[dict[str, JsonValue]]] = cast(
        typ="dict[str, list[dict[str, JsonValue]]]",
        val=private_call(
            analyzer,
            "_causal_edges",
            browser=object(),
            nodes=(node, other_node),
            elements_a=(reference, other_ref),
        ),
    )
    expect_equal(
        actual=dig(document=edges, path=(".b", 0, "selector")),
        expected=".a",
    )


def test_render_context_wrapper_and_browser_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover render-context cleanup and system-Chromium fallback launch.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)

    class ContextStub:
        closed: bool = False

        @staticmethod
        def new_page() -> object:
            """Return a page sentinel.

            Returns:
                Page sentinel.

            """
            return object()

        def close(self) -> None:
            """Record context closure."""
            self.closed = True

    context: ContextStub = ContextStub()

    class BrowserStub:
        @staticmethod
        def new_context(**kwargs: object) -> ContextStub:
            """Return the synthetic context.

            Args:
                **kwargs: Context configuration.

            Returns:
                Context stub.

            """
            expect_equal(actual=kwargs["device_scale_factor"], expected=2.0)
            return context

    monkeypatch.setattr(
        target=analyzer,
        name="_render_page",
        value=Constant(value=(Image.new(mode="RGB", size=(1, 1)), (), ())),
    )
    private_call(
        analyzer,
        "_render",
        browser=BrowserStub(),
        css=analyzer.css_a,
        intervention=Intervention(),
    )
    expect_true(condition=context.closed)

    class LaunchedBrowser:
        @staticmethod
        def close() -> None:
            """Close the launched browser."""

    class ChromiumStub:
        calls: int = 0

        def launch(self, **kwargs: object) -> LaunchedBrowser:
            """Fail bundled Chromium then accept a system executable.

            Args:
                **kwargs: Browser launch configuration.

            Returns:
                Launched browser stub.

            Raises:
                RuntimeError: When bundled Chromium is unavailable.

            """
            self.calls += 1
            if "executable_path" not in kwargs:
                msg: str = "bundled browser unavailable"
                raise RuntimeError(msg)
            expect_equal(
                actual=kwargs["executable_path"],
                expected="/usr/bin/chromium",
            )
            return LaunchedBrowser()

    chromium: ChromiumStub = ChromiumStub()

    class PlaywrightStub:
        def __init__(self) -> None:
            self.chromium: ChromiumStub = chromium

    class ManagerStub:
        def __enter__(self) -> PlaywrightStub:
            """Enter the Playwright stub.

            Returns:
                Entered stub.

            """
            return PlaywrightStub()

        def __exit__(self, *args: object) -> None:
            """Exit the Playwright stub.

            Args:
                *args: Context-manager exception state.

            """

    monkeypatch.setattr(
        target="exactus.packages.visual_cause.analyzer.sync_playwright",
        name=Constant(value=ManagerStub()),
    )
    monkeypatch.setattr(
        target="exactus.packages.visual_cause.analyzer.which",
        name=Constant(value="/usr/bin/chromium"),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_progress",
        value=Constant(value=None),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_render",
        value=Constant(value=(Image.new(mode="RGB", size=(1, 1)), (), ())),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_changed_pixels",
        value=Constant(value=0),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_regions",
        value=Constant(value=()),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_change_nodes",
        value=Constant(value=()),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_rank_rules",
        value=Constant(value=()),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_changed_rule_candidates",
        value=Constant(value=()),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_serial_rule_trials",
        value=Constant[list[JsonValue]](value=[]),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_declaration_trials",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_complete_property_evidence",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_causal_edges",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_function_provenance",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_cascade_provenance",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_interaction_provenance",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_minimal_cause_sets",
        value=Constant[dict[str, JsonValue]](value={}),
    )
    monkeypatch.setattr(
        target=analyzer,
        name="_write_outputs",
        value=Constant(value=None),
    )
    private_call(analyzer, "_run_analysis")
    expect_equal(actual=chromium.calls, expected=2)


def test_structural_empty_and_content_delta_branches(tmp_path: Path) -> None:
    """Cover empty structural summaries and rich content deltas.

    Args:
        tmp_path: Temporary test directory.

    """
    analyzer: CssVisualCause = _analyzer(tmp_path=tmp_path)
    empty: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=private_call(
            analyzer,
            "_structural_analysis",
            image_a=Image.new(mode="RGB", size=(10, 10)),
            image_b=Image.new(mode="RGB", size=(10, 10)),
            regions=(),
            elements=(),
        ),
    )
    expect_equal(actual=empty["largest_region_area"], expected=0.0)
    before: ElementInfo = _element(selector="a", dom_path="a", parent="")
    after: ElementInfo = ElementInfo(
        selector=before.selector,
        dom_path=before.dom_path,
        parent_path=before.parent_path,
        tag=before.tag,
        text="changed",
        own_text="changed",
        rect=before.rect,
        position=before.position,
        z_index=before.z_index,
        computed=before.computed,
        typed_computed=before.typed_computed,
        before_content='"before"',
        after_content='"after"',
        child_count=1,
        scroll_width=30.0,
        scroll_height=31.0,
        client_width=19.0,
        client_height=18.0,
        overflow_x="hidden",
        overflow_y="scroll",
    )
    delta: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=private_call(
            analyzer,
            "_content_delta",
            before=before,
            after=after,
        ),
    )
    expect_in(member="intrinsic_geometry", container=delta)
    expect_in(member="overflow", container=delta)
