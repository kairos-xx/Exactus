# Copyright (c) 2026
"""Coverage for generic two-URL visual DOM comparison."""

from __future__ import annotations

from io import StringIO
from json import dumps, loads
from typing import TYPE_CHECKING, cast

import pytest
from PIL import Image

from exactus.packages.visual_cause import (
    DiffRegion,
    DomDiffComparisonReport,
    DomDiffSettings,
    DomElement,
    ElementMatch,
    VisualDomDiff,
)
from exactus.packages.visual_cause import dom_diff as dom_diff_module
from exactus.packages.visual_cause.analyzer import (
    InvalidBrowserPayloadError,
    JsonValue,
    Rect,
)
from exactus.tests.packages.visual_cause.support import (
    dig,
    expect_equal,
    expect_in,
    expect_true,
    private_call,
    private_result,
    require_type,
)

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType


def _settings(
    *,
    output: Path,
    threshold: int = 1,
    merge_gap: int = 0,
    min_area: int = 1,
) -> DomDiffSettings:
    """Build compact comparison settings for deterministic image fixtures.

    Args:
        output: Temporary output directory.
        threshold: Pixel difference threshold.
        merge_gap: Gap to bridge while finding regions.
        min_area: Minimum reported region area.

    Returns:
        Immutable comparison settings.

    """
    return DomDiffSettings(
        url_a="https://a.example/",
        url_b="https://b.example/",
        output=output,
        width=16,
        height=16,
        threshold=threshold,
        merge_gap=merge_gap,
        min_area=min_area,
        timeout_ms=1000,
    )


def _element_payload(*, selector: str, rect: Rect) -> dict[str, JsonValue]:
    """Build one browser DOM snapshot entry.

    Args:
        selector: Element selector.
        rect: Element bounds.

    Returns:
        Serialized payload entry.

    """
    return {
        "selector": selector,
        "tag": "div",
        "element_id": selector.removeprefix("#"),
        "classes": "fixture",
        "text": f"text for {selector}",
        "x": rect.x,
        "y": rect.y,
        "width": rect.width,
        "height": rect.height,
    }


class FakeLocator:
    """Return a predetermined DOM payload for ``evaluate_all``."""

    def __init__(self, *, payload: str) -> None:
        """Store the serialized payload.

        Args:
            payload: JSON returned by the fake locator.

        """
        self._payload: str = payload

    def evaluate_all(self, expression: str) -> str:
        """Return the serialized DOM snapshot.

        Args:
            expression: JavaScript evaluated for each element.

        Returns:
            Serialized evaluation result.

        """
        expect_in(member="flatMap", container=expression)
        return self._payload


class FakePage:
    """Implement the narrow page surface used by ``VisualDomDiff``."""

    def __init__(
        self,
        *,
        image: Image.Image,
        elements: list[dict[str, JsonValue]],
    ) -> None:
        """Store screenshot and DOM fixture data.

        Args:
            image: Image written by the fake screenshot operation.
            elements: Serialized DOM snapshot entries.

        """
        self._image: Image.Image = image
        self._payload: str = dumps(obj=elements)
        self.url: str = ""

    @staticmethod
    def emulate_media(*, reduced_motion: str) -> None:
        """Validate the deterministic media setting.

        Args:
            reduced_motion: Requested reduced-motion behavior.

        """
        expect_equal(actual=reduced_motion, expected="reduce")

    @staticmethod
    def evaluate(*, expression: str) -> None:
        """Validate that video playback is paused for deterministic captures.

        Args:
            expression: JavaScript executed in the page.

        """
        expect_in(member="pause", container=expression)

    def goto(self, *, url: str, wait_until: str, timeout: int) -> None:
        """Record the navigation request.

        Args:
            url: URL to navigate to.
            wait_until: Navigation lifecycle condition.
            timeout: Navigation timeout in milliseconds.

        """
        expect_equal(actual=wait_until, expected="networkidle")
        expect_true(condition=timeout > 0)
        self.url = url

    def screenshot(
        self,
        *,
        path: Path,
        full_page: bool,
        animations: str,
        caret: str,
        scale: str,
    ) -> None:
        """Write the predetermined screenshot image.

        Args:
            path: Destination screenshot path.
            full_page: Whether the capture covers the page.
            animations: Animation handling mode.
            caret: Caret handling mode.
            scale: Screenshot scale mode.

        """
        expect_true(condition=full_page)
        expect_equal(actual=animations, expected="disabled")
        expect_equal(actual=caret, expected="hide")
        expect_equal(actual=scale, expected="css")
        self._image.save(fp=path)

    def locator(self, *, selector: str) -> FakeLocator:
        """Return a locator for the predetermined DOM payload.

        Args:
            selector: Element selector.

        Returns:
            Fake element locator.

        """
        expect_equal(actual=selector, expected="*")
        return FakeLocator(payload=self._payload)


class FakeContext:
    """Return predetermined A/B pages and record closure."""

    def __init__(self, *, pages: tuple[FakePage, FakePage]) -> None:
        """Store the fake pages.

        Args:
            pages: Side-A and side-B pages.

        """
        self._pages: tuple[FakePage, FakePage] = pages
        self._next_page: int = 0
        self.closed: bool = False

    def new_page(self) -> FakePage:
        """Return the next fake page.

        Returns:
            Fake page fixture.

        """
        page: FakePage = self._pages[min(self._next_page, 1)]
        self._next_page += 1
        return page

    def close(self) -> None:
        """Record context cleanup."""
        self.closed = True


class FakeBrowser:
    """Create one fake browser context and record closure."""

    def __init__(self, *, pages: tuple[FakePage, FakePage]) -> None:
        """Store the pages used by the context.

        Args:
            pages: Side-A and side-B pages.

        """
        self._pages: tuple[FakePage, FakePage] = pages
        self.closed: bool = False

    def new_context(
        self,
        *,
        viewport: dict[str, int],
        device_scale_factor: float,
        reduced_motion: str,
    ) -> FakeContext:
        """Validate context settings and return a fake context.

        Args:
            viewport: Viewport dimensions.
            device_scale_factor: Device scale factor.
            reduced_motion: Requested reduced-motion behavior.

        Returns:
            Fake browser context.

        """
        expect_equal(actual=viewport, expected={"width": 16, "height": 16})
        expect_equal(actual=device_scale_factor, expected=1.0)
        expect_equal(actual=reduced_motion, expected="reduce")
        return FakeContext(pages=self._pages)

    def close(self) -> None:
        """Record browser cleanup."""
        self.closed = True


class FakeChromium:
    """Launch the predetermined fake browser."""

    def __init__(self, *, pages: tuple[FakePage, FakePage]) -> None:
        """Store browser fixture pages.

        Args:
            pages: Side-A and side-B pages.

        """
        self._pages: tuple[FakePage, FakePage] = pages
        self.headless: bool = False

    def launch(self, *, headless: bool) -> FakeBrowser:
        """Return the fake browser.

        Args:
            headless: Whether Chromium is headless.

        Returns:
            Fake browser.

        """
        self.headless = headless
        return FakeBrowser(pages=self._pages)


class FakePlaywright:
    """Expose a fake Chromium launcher."""

    def __init__(self, *, pages: tuple[FakePage, FakePage]) -> None:
        """Store browser fixture pages.

        Args:
            pages: Side-A and side-B pages.

        """
        self.chromium: FakeChromium = FakeChromium(pages=pages)


class FakePlaywrightManager:
    """Implement the synchronous Playwright context-manager boundary."""

    def __init__(self, *, pages: tuple[FakePage, FakePage]) -> None:
        """Store browser fixture pages.

        Args:
            pages: Side-A and side-B pages.

        """
        self.playwright: FakePlaywright = FakePlaywright(pages=pages)

    def __enter__(self) -> FakePlaywright:
        """Enter the fake Playwright context.

        Returns:
            Fake Playwright facade.

        """
        return self.playwright

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Leave the fake Playwright context.

        Args:
            exc_type: Exception type, if raised.
            exc_value: Exception value, if raised.
            traceback: Exception traceback, if raised.

        """
        del exc_type, exc_value, traceback


def test_dom_diff_helpers_normalize_threshold_and_merge_regions(
    tmp_path: Path,
) -> None:
    """Cover padding, thresholding, merge-gap, min-area, and pixel counts.

    Args:
        tmp_path: Temporary test directory.

    """
    diff: VisualDomDiff = VisualDomDiff(
        settings=_settings(output=tmp_path, merge_gap=3),
    )
    image_a: Image.Image = Image.new(
        mode="RGBA",
        size=(10, 10),
        color=(255, 255, 255, 255),
    )
    image_b: Image.Image = image_a.copy()
    image_b.putpixel(xy=(1, 1), value=(255, 0, 0, 255))
    image_b.putpixel(xy=(6, 1), value=(255, 0, 0, 255))
    normalized: tuple[Image.Image, Image.Image] = cast(
        typ="tuple[Image.Image, Image.Image]",
        val=private_result(
            diff,
            "_normalize_images",
            tuple,
            image_a=Image.new(mode="RGBA", size=(3, 2), color=(1, 2, 3, 255)),
            image_b=Image.new(mode="RGBA", size=(2, 4), color=(1, 2, 3, 255)),
        ),
    )
    expect_equal(
        actual=(normalized[0].width, normalized[0].height),
        expected=(3, 4),
    )
    expect_equal(
        actual=normalized[0].getpixel(xy=(2, 3)),
        expected=(0, 0, 0, 0),
    )
    mask: Image.Image = private_result(
        diff,
        "_difference_mask",
        Image.Image,
        image_a=image_a,
        image_b=image_b,
    )
    regions: tuple[Rect, ...] = cast(
        typ="tuple[Rect, ...]",
        val=private_result(diff, "_regions", tuple, mask=mask),
    )
    expect_equal(actual=len(regions), expected=1)
    expect_equal(
        actual=regions[0],
        expected=Rect(x=0.0, y=0.0, width=10.0, height=5.0),
    )
    expect_equal(
        actual=private_call(
            diff,
            "_count_changed",
            mask=mask,
            bounds=regions[0],
        ),
        expected=2,
    )
    filtered: VisualDomDiff = VisualDomDiff(
        settings=_settings(
            output=tmp_path / "filtered",
            merge_gap=0,
            min_area=2,
        ),
    )
    expect_equal(
        actual=cast(
            typ="tuple[Rect, ...]",
            val=private_result(filtered, "_regions", tuple, mask=mask),
        ),
        expected=(),
    )


def test_dom_diff_parses_and_ranks_elements() -> None:
    """Cover lightweight DOM payload validation and overlap ranking."""
    payload: str = dumps(
        obj=[
            _element_payload(
                selector="#parent",
                rect=Rect(x=0.0, y=0.0, width=10.0, height=10.0),
            ),
            _element_payload(
                selector="#child",
                rect=Rect(x=2.0, y=2.0, width=4.0, height=4.0),
            ),
            _element_payload(
                selector="#outside",
                rect=Rect(x=20.0, y=20.0, width=3.0, height=3.0),
            ),
        ],
    )
    elements: tuple[DomElement, ...] = cast(
        typ="tuple[DomElement, ...]",
        val=private_result(
            VisualDomDiff,
            "_parse_elements",
            tuple,
            raw=payload,
        ),
    )
    expect_equal(actual=len(elements), expected=3)
    expect_equal(actual=elements[1].element_id, expected="child")
    region: Rect = Rect(x=2.0, y=2.0, width=4.0, height=4.0)
    matches: tuple[ElementMatch, ...] = cast(
        typ="tuple[ElementMatch, ...]",
        val=private_result(
            VisualDomDiff,
            "_match_elements",
            tuple,
            elements=elements,
            region=region,
        ),
    )
    expect_equal(
        actual=[match.selector for match in matches],
        expected=["#child", "#parent"],
    )
    expect_equal(actual=matches[0].overlap_pixels, expected=16.0)
    expect_equal(actual=matches[0].overlap_ratio, expected=1.0)
    with pytest.raises(expected_exception=InvalidBrowserPayloadError):
        private_call(VisualDomDiff, "_parse_elements", raw="{}")


def test_dom_diff_cli_settings_and_validation(tmp_path: Path) -> None:
    """Parse generic-diff options and reject invalid numeric ranges.

    Args:
        tmp_path: Temporary test directory.

    """
    settings: DomDiffSettings = private_result(
        dom_diff_module,
        "_settings",
        DomDiffSettings,
        arguments=[
            "https://a.example/",
            "https://b.example/",
            "-o",
            str(object=tmp_path),
            "--width",
            "320",
            "--height",
            "200",
            "--threshold",
            "5",
            "--merge-gap",
            "2",
            "--min-area",
            "9",
            "--timeout-ms",
            "700",
        ],
    )
    expect_equal(actual=settings.output, expected=tmp_path)
    expect_equal(actual=settings.width, expected=320)
    expect_equal(actual=settings.merge_gap, expected=2)
    expect_equal(actual=settings.min_area, expected=9)
    invalid_arguments: tuple[tuple[str, ...], ...] = (
        ("a", "b", "--width", "0"),
        ("a", "b", "--threshold", "256"),
        ("a", "b", "--merge-gap", "-1"),
        ("a", "b", "--timeout-ms", "0"),
    )
    for arguments in invalid_arguments:
        with pytest.raises(expected_exception=ValueError, match="must"):
            private_call(
                dom_diff_module,
                "_settings",
                arguments=list(arguments),
            )


def test_dom_diff_run_writes_original_report_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the whole comparison through a fake Playwright boundary.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    image_a: Image.Image = Image.new(
        mode="RGBA",
        size=(8, 8),
        color=(255, 255, 255, 255),
    )
    image_b: Image.Image = image_a.copy()
    for x in range(2, 6):
        for y in range(2, 6):
            image_b.putpixel(xy=(x, y), value=(255, 0, 0, 255))
    region_rect: Rect = Rect(x=2.0, y=2.0, width=4.0, height=4.0)
    parent_rect: Rect = Rect(x=0.0, y=0.0, width=8.0, height=8.0)
    elements: list[dict[str, JsonValue]] = [
        _element_payload(selector="#parent", rect=parent_rect),
        _element_payload(selector="#child", rect=region_rect),
    ]
    pages: tuple[FakePage, FakePage] = (
        FakePage(image=image_a, elements=elements),
        FakePage(image=image_b, elements=elements),
    )
    manager: FakePlaywrightManager = FakePlaywrightManager(pages=pages)
    monkeypatch.setattr(
        target=dom_diff_module,
        name="sync_playwright",
        value=lambda: manager,
    )
    output: Path = tmp_path / "out"
    report: DomDiffComparisonReport = VisualDomDiff(
        settings=_settings(
            output=output,
            threshold=1,
            merge_gap=0,
            min_area=1,
        ),
    ).run()
    expect_true(condition=manager.playwright.chromium.headless)
    expect_equal(actual=report.changed_pixels, expected=16)
    expect_equal(actual=report.changed_ratio, expected=0.25)
    expect_equal(actual=len(report.regions), expected=1)
    first: DiffRegion = report.regions[0]
    expect_equal(actual=first.changed_pixels, expected=16)
    expect_equal(
        actual=[match.selector for match in first.elements_a],
        expected=["#child", "#parent"],
    )
    expect_true(condition=(output / "a.png").is_file())
    expect_true(condition=(output / "b.png").is_file())
    expect_true(condition=(output / "diff.png").is_file())
    decoded: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=require_type(
            value=loads(
                s=(output / "report.json").read_text(encoding="utf-8"),
            ),
            kind=dict,
        ),
    )
    expect_equal(actual=decoded["changed_pixels"], expected=16)
    expect_equal(actual=decoded["changed_ratio"], expected=0.25)
    expect_equal(
        actual=dig(
            document=decoded,
            path=("regions", 0, "elements_a", 0, "selector"),
        ),
        expected="#child",
    )
    expect_equal(actual=pages[0].url, expected="https://a.example/")
    expect_equal(actual=pages[1].url, expected="https://b.example/")


def test_dom_diff_main_writes_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the standalone CLI summary path without a browser.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    report: DomDiffComparisonReport = DomDiffComparisonReport(
        url_a="https://a.example/",
        url_b="https://b.example/",
        screenshot_a=str(object=tmp_path / "a.png"),
        screenshot_b=str(object=tmp_path / "b.png"),
        diff_image=str(object=tmp_path / "diff.png"),
        image_width=1,
        image_height=1,
        changed_pixels=1,
        changed_ratio=1.0,
        regions=(),
    )

    def fake_run(self: VisualDomDiff) -> DomDiffComparisonReport:
        """Return the predetermined report.

        Args:
            self: Diff instance under test.

        Returns:
            Predetermined comparison report.

        """
        del self
        return report

    monkeypatch.setattr(target=VisualDomDiff, name="run", value=fake_run)
    stream: StringIO = StringIO()
    monkeypatch.setattr(target=dom_diff_module, name="stdout", value=stream)
    status: int = dom_diff_module.main(
        arguments=[
            "https://a.example/",
            "https://b.example/",
            "-o",
            str(object=tmp_path),
        ],
    )
    expect_equal(actual=status, expected=0)
    captured: str = stream.getvalue()
    expect_in(member="Changed pixels: 1 (100.0000%)", container=captured)
    expect_in(member="Regions: 0", container=captured)
    expect_in(member="Report:", container=captured)


def test_dom_diff_settings_are_publicly_exported(tmp_path: Path) -> None:
    """Require package-level access to the migrated standalone API.

    Args:
        tmp_path: Temporary test directory.

    """
    settings: DomDiffSettings = _settings(output=tmp_path)
    diff: VisualDomDiff = VisualDomDiff(settings=settings)
    expect_equal(actual=type(diff), expected=VisualDomDiff)
    expect_equal(actual=settings.output, expected=tmp_path)
