# Copyright (c) 2026
"""Compare two web pages visually and map pixel differences to DOM elements."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from json import dumps, loads
from pathlib import Path
from sys import stdout
from textwrap import dedent
from typing import TYPE_CHECKING, Final, Protocol, cast, final

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.visual_cause.analyzer import (
    InvalidBrowserPayloadError,
    JsonValue,
    Rect,
    browser_script,
)

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from collections.abc import Sequence


@final
class Constants:
    """Group module-level constants.

    Attributes:
        default_width: Grouped module constant.
        default_height: Grouped module constant.
        default_threshold: Grouped module constant.
        default_merge_gap: Grouped module constant.
        default_min_area: Grouped module constant.
        default_timeout_ms: Grouped module constant.
        max_threshold: Grouped module constant.
        max_elements_per_region: Grouped module constant.

    """

    default_width: Final[int] = 1440
    default_height: Final[int] = 900
    default_threshold: Final[int] = 12
    default_merge_gap: Final[int] = 3
    default_min_area: Final[int] = 4
    default_timeout_ms: Final[int] = 30000
    max_threshold: Final[int] = 255
    max_elements_per_region: Final[int] = 8


@dataclass(frozen=True, slots=True)
class DomElement:
    """Describe a visible DOM element and its document-space bounds.

    Attributes:
        selector: Unique selector identifying the element.
        tag: Lowercase element tag name.
        element_id: Element ``id`` attribute, empty when absent.
        classes: Space-joined class list.
        text: Trimmed visible text content.
        rect: Document-space bounding rectangle.

    """

    selector: str
    tag: str
    element_id: str
    classes: str
    text: str
    rect: Rect


@dataclass(frozen=True, slots=True)
class ElementMatch:
    """Describe a DOM element associated with one visual-diff region.

    Attributes:
        selector: Unique selector identifying the element.
        tag: Lowercase element tag name.
        element_id: Element ``id`` attribute, empty when absent.
        classes: Space-joined class list.
        text: Trimmed visible text content.
        bounds: Document-space bounding rectangle.
        overlap_pixels: Pixels shared with the diff region.
        overlap_ratio: Region fraction covered by the element.

    """

    selector: str
    tag: str
    element_id: str
    classes: str
    text: str
    bounds: Rect
    overlap_pixels: float
    overlap_ratio: float


@dataclass(frozen=True, slots=True)
class DiffRegion:
    """Describe one connected visual-difference region.

    Attributes:
        bounds: Bounding box of the changed pixels.
        changed_pixels: Pixel count differing past the threshold.
        elements_a: Elements overlapping the region on side A.
        elements_b: Elements overlapping the region on side B.

    """

    bounds: Rect
    changed_pixels: int
    elements_a: tuple[ElementMatch, ...]
    elements_b: tuple[ElementMatch, ...]


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    """Describe the complete result of a visual DOM comparison.

    Attributes:
        url_a: Compared URL for side A.
        url_b: Compared URL for side B.
        screenshot_a: Side A screenshot artifact path.
        screenshot_b: Side B screenshot artifact path.
        diff_image: Highlighted difference image path.
        image_width: Screenshot width in pixels.
        image_height: Screenshot height in pixels.
        changed_pixels: Total pixels differing past the threshold.
        changed_ratio: Changed fraction of the full frame.
        regions: Connected difference regions.

    """

    url_a: str
    url_b: str
    screenshot_a: str
    screenshot_b: str
    diff_image: str
    image_width: int
    image_height: int
    changed_pixels: int
    changed_ratio: float
    regions: tuple[DiffRegion, ...]


@dataclass(frozen=True, slots=True)
class Settings:
    """Hold immutable command-line settings.

    Attributes:
        url_a: Compared URL for side A.
        url_b: Compared URL for side B.
        output: Directory receiving screenshots and reports.
        width: Viewport width in CSS pixels.
        height: Viewport height in CSS pixels.
        threshold: Per-channel difference threshold.
        merge_gap: Pixel gap bridged when merging regions.
        min_area: Smallest reported region in square pixels.
        timeout_ms: Navigation and capture timeout.

    """

    url_a: str
    url_b: str
    output: Path
    width: int
    height: int
    threshold: int
    merge_gap: int
    min_area: int
    timeout_ms: int


class LocatorEvaluator(Protocol):
    """Narrow the dynamically typed Playwright evaluation boundary."""

    def evaluate_all(self, expression: str) -> str:
        """Evaluate JavaScript against all located elements.

        Args:
            expression: JavaScript evaluated for each element.

        Returns:
            Serialized evaluation result.

        """
        ...


class VisualDomDiff:
    """Capture two URLs, compare pixels, and map changes to DOM elements."""

    _DOM_SCRIPT: Final[str] = browser_script(name="dom_elements.js")

    def __init__(self, settings: Settings) -> None:
        """Run the comparison and write all artifacts.

        Args:
            settings: Immutable comparison configuration.

        """
        self._settings: Settings = settings
        self._settings.output.mkdir(parents=True, exist_ok=True)

    def run(self) -> ComparisonReport:
        """Execute capture, image comparison, DOM mapping, and reporting.

        Returns:
            Completed comparison report.

        """
        with sync_playwright() as playwright:
            browser: Browser = playwright.chromium.launch(headless=True)
            try:
                context: BrowserContext = browser.new_context(
                    viewport={
                        "width": self._settings.width,
                        "height": self._settings.height,
                    },
                    device_scale_factor=1.0,
                    reduced_motion="reduce",
                )
                try:
                    page_a: Page = context.new_page()
                    page_b: Page = context.new_page()
                    image_a, elements_a = self._capture(
                        page=page_a,
                        url=self._settings.url_a,
                        name="a.png",
                    )
                    image_b, elements_b = self._capture(
                        page=page_b,
                        url=self._settings.url_b,
                        name="b.png",
                    )
                finally:
                    context.close()
            finally:
                browser.close()
        normalized_a, normalized_b = self._normalize_images(
            image_a=image_a,
            image_b=image_b,
        )
        mask: Image.Image = self._difference_mask(
            image_a=normalized_a,
            image_b=normalized_b,
        )
        boxes: tuple[Rect, ...] = self._regions(mask=mask)
        changed_pixels: int = sum(1 for value in mask.getdata() if value != 0)
        regions: tuple[DiffRegion, ...] = tuple(
            DiffRegion(
                bounds=box,
                changed_pixels=self._count_changed(mask=mask, bounds=box),
                elements_a=self._match_elements(
                    elements=elements_a,
                    region=box,
                ),
                elements_b=self._match_elements(
                    elements=elements_b,
                    region=box,
                ),
            )
            for box in boxes
        )
        diff_path: Path = self._settings.output / "diff.png"
        self._draw_diff(
            image=normalized_b,
            regions=regions,
            destination=diff_path,
        )
        report: ComparisonReport = ComparisonReport(
            url_a=self._settings.url_a,
            url_b=self._settings.url_b,
            screenshot_a=str(object=self._settings.output / "a.png"),
            screenshot_b=str(object=self._settings.output / "b.png"),
            diff_image=str(object=diff_path),
            image_width=normalized_a.width,
            image_height=normalized_a.height,
            changed_pixels=changed_pixels,
            changed_ratio=changed_pixels
            / (normalized_a.width * normalized_a.height),
            regions=regions,
        )
        (self._settings.output / "report.json").write_text(
            data=dumps(obj=asdict(obj=report), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return report

    @staticmethod
    def _parse_elements(*, raw: str) -> tuple[DomElement, ...]:
        """Validate and convert the lightweight browser DOM snapshot.

        Args:
            raw: Serialized DOM element snapshot.

        Returns:
            Visible elements and their document-space bounds.

        Raises:
            InvalidBrowserPayloadError: If the payload schema is invalid.

        """
        decoded: JsonValue = cast(typ="JsonValue", val=loads(s=raw))
        if not isinstance(decoded, list):
            raise InvalidBrowserPayloadError
        output: list[DomElement] = []
        for entry_value in decoded:
            if not isinstance(entry_value, dict):
                raise InvalidBrowserPayloadError
            entry: dict[str, JsonValue] = entry_value
            selector: JsonValue = entry.get("selector")
            tag: JsonValue = entry.get("tag")
            element_id: JsonValue = entry.get("element_id")
            classes: JsonValue = entry.get("classes")
            text: JsonValue = entry.get("text")
            numbers: tuple[JsonValue, ...] = tuple(
                entry.get(name) for name in ("x", "y", "width", "height")
            )
            if (
                not isinstance(selector, str)
                or not isinstance(tag, str)
                or not isinstance(element_id, str)
                or not isinstance(classes, str)
                or not isinstance(text, str)
                or not all(
                    isinstance(value, int | float)
                    and not isinstance(value, bool)
                    for value in numbers
                )
            ):
                raise InvalidBrowserPayloadError
            numeric_values: tuple[float, ...] = tuple(
                float(value)
                for value in numbers
                if isinstance(value, int | float)
            )
            output.append(
                DomElement(
                    selector=selector,
                    tag=tag,
                    element_id=element_id,
                    classes=classes,
                    text=text,
                    rect=Rect(
                        x=numeric_values[0],
                        y=numeric_values[1],
                        width=numeric_values[2],
                        height=numeric_values[3],
                    ),
                ),
            )
        return tuple(output)

    @staticmethod
    def _normalize_images(
        *,
        image_a: Image.Image,
        image_b: Image.Image,
    ) -> tuple[Image.Image, Image.Image]:
        """Pad screenshots to one common size.

        Args:
            image_a: First screenshot.
            image_b: Second screenshot.

        Returns:
            Equally sized RGBA images.

        """
        width: int = max(image_a.width, image_b.width)
        height: int = max(image_a.height, image_b.height)
        normalized: list[Image.Image] = []
        for image in (image_a, image_b):
            canvas: Image.Image = Image.new(
                mode="RGBA",
                size=(width, height),
                color=(0, 0, 0, 0),
            )
            canvas.paste(im=image, box=(0, 0))
            normalized.append(canvas)
        return (normalized[0], normalized[1])

    @staticmethod
    def _count_changed(*, mask: Image.Image, bounds: Rect) -> int:
        """Count changed source pixels inside a region.

        Args:
            mask: Original binary difference mask.
            bounds: Region to inspect.

        Returns:
            Number of changed pixels.

        """
        cropped: Image.Image = mask.crop(
            box=(
                int(bounds.x),
                int(bounds.y),
                int(bounds.right),
                int(bounds.bottom),
            ),
        )
        return sum(1 for value in cropped.getdata() if value != 0)

    @staticmethod
    def _match_elements(
        *,
        elements: tuple[DomElement, ...],
        region: Rect,
    ) -> tuple[ElementMatch, ...]:
        """Rank DOM elements that overlap a visual-difference region.

        Args:
            elements: Visible DOM snapshot.
            region: Difference region in document coordinates.

        Returns:
            Best matching elements, with descendants favored over ancestors.

        """
        matches: list[ElementMatch] = []
        for element in elements:
            overlap: float = element.rect.intersection_area(other=region)
            if overlap <= 0.0:
                continue
            denominator: float = min(region.area, element.rect.area)
            matches.append(
                ElementMatch(
                    selector=element.selector,
                    tag=element.tag,
                    element_id=element.element_id,
                    classes=element.classes,
                    text=element.text,
                    bounds=element.rect,
                    overlap_pixels=overlap,
                    overlap_ratio=overlap / denominator
                    if denominator
                    else 0.0,
                ),
            )
        matches.sort(
            key=lambda item: (
                -item.overlap_ratio,
                item.bounds.area,
                -item.overlap_pixels,
            ),
        )
        return tuple(matches[: Constants.max_elements_per_region])

    @staticmethod
    def _draw_diff(
        *,
        image: Image.Image,
        regions: tuple[DiffRegion, ...],
        destination: Path,
    ) -> None:
        """Write an annotated image showing every detected region.

        Args:
            image: Background screenshot.
            regions: Regions to annotate.
            destination: Output image path.

        """
        annotated: Image.Image = image.copy()
        drawing: ImageDraw.ImageDraw = ImageDraw.Draw(im=annotated)
        for index, region in enumerate(iterable=regions, start=1):
            bounds: Rect = region.bounds
            drawing.rectangle(
                xy=(bounds.x, bounds.y, bounds.right, bounds.bottom),
                outline="red",
                width=2,
            )
            drawing.text(
                xy=(bounds.x + 3, bounds.y + 3),
                text=str(object=index),
                fill="red",
            )
        annotated.save(fp=destination)

    def _capture(
        self,
        *,
        page: Page,
        url: str,
        name: str,
    ) -> tuple[Image.Image, tuple[DomElement, ...]]:
        """Capture one page and collect its visible DOM geometry.

        Args:
            page: Playwright page to use.
            url: URL to navigate to.
            name: Screenshot filename.

        Returns:
            Screenshot image and visible DOM element snapshot.

        """
        page.goto(
            url=url,
            wait_until="networkidle",
            timeout=self._settings.timeout_ms,
        )
        page.emulate_media(reduced_motion="reduce")
        page.evaluate(
            expression=(
                dedent(
                    text=(
                        "    () => {\n                    for (const eleme"
                        'nt of document.querySelectorAll("video"))\n      '
                        "                  element.pause();\n             "
                        "   }"
                    ),
                )
            ),
        )
        page.screenshot(
            path=self._settings.output / name,
            full_page=True,
            animations="disabled",
            caret="hide",
            scale="css",
        )
        raw: str = cast(
            typ="LocatorEvaluator",
            val=page.locator(selector="*"),
        ).evaluate_all(expression=self._DOM_SCRIPT)
        elements: tuple[DomElement, ...] = self._parse_elements(raw=raw)
        with Image.open(fp=self._settings.output / name) as screenshot:
            return screenshot.convert(mode="RGBA"), elements

    def _difference_mask(
        self,
        *,
        image_a: Image.Image,
        image_b: Image.Image,
    ) -> Image.Image:
        """Create a binary mask for pixels exceeding the channel threshold.

        Args:
            image_a: First normalized screenshot.
            image_b: Second normalized screenshot.

        Returns:
            Single-channel binary difference mask.

        """
        channels: tuple[Image.Image, ...] = ImageChops.difference(
            image1=image_a,
            image2=image_b,
        ).split()
        maximum: Image.Image = ImageChops.lighter(
            image1=ImageChops.lighter(image1=channels[0], image2=channels[1]),
            image2=ImageChops.lighter(image1=channels[2], image2=channels[3]),
        )
        threshold: int = self._settings.threshold

        def binarize(value: float) -> int:
            """Threshold one channel value to black or white.

            Args:
                value: Combined channel value to test.

            Returns:
                ``255`` above the threshold, ``0`` otherwise.

            """
            return 255 if value > threshold else 0

        return maximum.point(lut=binarize, mode="1").convert(mode="L")

    def _regions(self, *, mask: Image.Image) -> tuple[Rect, ...]:
        """Find connected visual-difference regions.

        Args:
            mask: Binary pixel-difference mask.

        Returns:
            Difference bounding boxes sorted top-to-bottom, left-to-right.

        """
        expanded: Image.Image = (
            mask.filter(
                filter=ImageFilter.MaxFilter(
                    size=self._settings.merge_gap * 2 + 1,
                ),
            )
            if self._settings.merge_gap > 0
            else mask
        )
        width: int = expanded.width
        pixels: bytes = expanded.tobytes()
        visited: bytearray = bytearray(len(pixels))
        regions: list[Rect] = []
        for index, value in enumerate(iterable=pixels):
            if value == 0 or visited[index] != 0:
                continue
            stack: list[int] = [index]
            visited[index] = 1
            min_x: int = index % width
            max_x: int = min_x
            min_y: int = index // width
            max_y: int = min_y
            while stack:
                current: int = stack.pop()
                x: int = current % width
                y: int = current // width
                min_x, max_x = (min(min_x, x), max(max_x, x))
                min_y, max_y = (min(min_y, y), max(max_y, y))
                for neighbor in (
                    current - 1 if x > 0 else -1,
                    current + 1 if x + 1 < width else -1,
                    current - width if y > 0 else -1,
                    current + width if y + 1 < expanded.height else -1,
                ):
                    if (
                        neighbor >= 0
                        and pixels[neighbor] != 0
                        and visited[neighbor] == 0
                    ):
                        visited[neighbor] = 1
                        stack.append(neighbor)
            region: Rect = Rect(
                x=float(min_x),
                y=float(min_y),
                width=float(max_x - min_x + 1),
                height=float(max_y - min_y + 1),
            )
            if region.area >= self._settings.min_area:
                regions.append(region)
        return tuple(sorted(regions, key=lambda item: (item.y, item.x)))


def _settings(*, arguments: Sequence[str] | None = None) -> Settings:
    """Parse command-line arguments into immutable settings.

    Args:
        arguments: Optional argument vector, excluding the executable name.

    Returns:
        Validated comparison settings.

    Raises:
        ValueError: If numeric settings fall outside their valid ranges.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description=(
            "Capture two URLs, compare their rendered pixels, and map visual "
            "differences to overlapping DOM elements."
        ),
    )
    parser.add_argument("url_a")
    parser.add_argument("url_b")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("visual-diff"),
    )
    parser.add_argument("--width", type=int, default=Constants.default_width)
    parser.add_argument("--height", type=int, default=Constants.default_height)
    parser.add_argument(
        "--threshold",
        type=int,
        default=Constants.default_threshold,
    )
    parser.add_argument(
        "--merge-gap",
        type=int,
        default=Constants.default_merge_gap,
    )
    parser.add_argument(
        "--min-area",
        type=int,
        default=Constants.default_min_area,
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=Constants.default_timeout_ms,
    )
    args: Namespace = parser.parse_args(args=arguments)
    settings: Settings = Settings(
        url_a=cast(typ="str", val=args.url_a),
        url_b=cast(typ="str", val=args.url_b),
        output=cast(typ="Path", val=args.output),
        width=cast(typ="int", val=args.width),
        height=cast(typ="int", val=args.height),
        threshold=cast(typ="int", val=args.threshold),
        merge_gap=cast(typ="int", val=args.merge_gap),
        min_area=cast(typ="int", val=args.min_area),
        timeout_ms=cast(typ="int", val=args.timeout_ms),
    )
    if settings.width <= 0 or settings.height <= 0:
        msg: str = "width and height must be positive"
        raise ValueError(msg)
    if not 0 <= settings.threshold <= Constants.max_threshold:
        msg = "threshold must be between 0 and 255"
        raise ValueError(msg)
    if settings.merge_gap < 0 or settings.min_area < 0:
        msg = "merge-gap and min-area must be non-negative"
        raise ValueError(msg)
    if settings.timeout_ms <= 0:
        msg = "timeout-ms must be positive"
        raise ValueError(msg)
    return settings


def main(*, arguments: Sequence[str] | None = None) -> int:
    """Run the command-line visual DOM comparison.

    Args:
        arguments: Optional argument vector, excluding the executable name.

    Returns:
        Process exit status.

    """
    report: ComparisonReport = VisualDomDiff(
        settings=_settings(arguments=arguments),
    ).run()
    stdout.write(
        f"Changed pixels: {report.changed_pixels} "
        f"({report.changed_ratio:.4%})\n"
        f"Regions: {len(report.regions)}\n"
        f"Report: {Path(report.diff_image).with_name(name='report.json')}\n",
    )
    return 0


if __name__ == "__main__":
    main()
