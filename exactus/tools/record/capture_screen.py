# Copyright (c) 2026
"""Capture screenshots with arbitrarily nested overflow fully exposed."""

from __future__ import annotations

from base64 import b64encode
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from textwrap import dedent
from typing import TYPE_CHECKING, ClassVar, Literal, Self, cast

if TYPE_CHECKING:
    from pathlib import Path
from playwright.async_api import (
    Browser,
    BrowserContext,
    ElementHandle,
    Error,
    FloatRect,
    Page,
    ViewportSize,
    async_playwright,
)


class CaptureScreenDefaults:
    """Store immutable scalar configuration values.

    Attributes:
        max_capture_height: Max capture height.
        max_iterations: Max iterations.
        tolerance: Tolerance.

    """

    max_capture_height: ClassVar[int] = 8192
    max_iterations: ClassVar[int] = 30
    tolerance: ClassVar[int] = 1


class Js(StrEnum):
    """Store browser-side JavaScript.

    Attributes:
        EXPAND: Expand.
        MEASURE: Measure.
        RESTORE: Restore.
        SETTLE: Settle.

    """

    EXPAND = dedent(
        text=(
            """\

        root => {
            const state = window.__snapshotCapture ??= {
                styles: [], scrolls: [], expanded: new Set(),
                winX: scrollX, winY: scrollY,
            };
            let changed = false;
            for (const element of [root, ...root.querySelectorAll("*")]) {
                if (
                    !(
                        element instanceof HTMLElement
                        || element instanceof SVGElement
                    )
                    || element.scrollHeight <= element.clientHeight + 1
                    || state.expanded.has(element)
                )
                    continue;
                state.expanded.add(element);
                state.styles.push([element, element.getAttribute("style")]);
                if (element instanceof HTMLElement)
                    state.scrolls.push([
                        element, element.scrollLeft, element.scrollTop,
                    ]);
                for (const [property, value] of [
                    ["height", "auto"],
                    ["max-height", "none"],
                    ["overflow-y", "visible"],
                ])
                    element.style.setProperty(property, value, "important");
                changed = true;
            }
            return changed;
        }
        """
        ),
    ).strip()
    MEASURE = dedent(
        text=(
            """\

        root => {
            const {top, bottom} = root.getBoundingClientRect();
            return {
                height: Math.ceil(
                    top
                    + root.scrollHeight
                    + Math.max(
                        document.documentElement.scrollHeight,
                        document.body?.scrollHeight ?? 0,
                    )
                    - bottom
                ),
                width: Math.max(
                    document.documentElement.scrollWidth,
                    document.body?.scrollWidth ?? 0,
                ),
                innerHeight,
                signature: [root, ...root.querySelectorAll("*")].map(
                    element => {
                    const {top, height} = element.getBoundingClientRect();
                    return `${Math.round(top)}:${Math.round(height)}:`
                        + `${element.scrollHeight ?? 0}:`
                        + `${element.clientHeight ?? 0}`;
                    },
                ).join("|"),
            };
        }
        """
        ),
    ).strip()
    SETTLE = dedent(
        text=(
            """\

        () => new Promise(resolve =>
            requestAnimationFrame(() => requestAnimationFrame(resolve))
        )
        """
        ),
    ).strip()
    RESTORE = dedent(
        text=(
            """\

        () => {
            const state = window.__snapshotCapture;
            if (!state)
                return;
            for (const [element, style] of state.styles)
                style === null
                    ? element.removeAttribute("style")
                    : element.setAttribute("style", style);
            for (const [element, left, top] of state.scrolls)
                Object.assign(element, {scrollLeft: left, scrollTop: top});
            if (state.winX !== undefined)
                scrollTo(state.winX, state.winY);
            delete window.__snapshotCapture;
        }
        """
        ),
    ).strip()


@dataclass(frozen=True, slots=True)
class Capture:
    """Represent a captured PNG.

    Attributes:
        data: Raw PNG bytes.
        path: Saved PNG path, if requested.
        truncated_height: Whether capture hit the height cap.

    """

    data: bytes
    path: Path | None
    truncated_height: bool

    @property
    def b64(self: Self) -> str:
        """Base64-encoded PNG data.

        Returns:
            Base64-encoded PNG.

        """
        return b64encode(s=self.data).decode(encoding="ascii")


@dataclass(frozen=True, slots=True)
class CaptureSpec:
    """Describe capture-time options for the high-level API.

    Attributes:
        path: Optional PNG destination.
        width: Viewport width when this call creates the context.
        height: Viewport height when this call creates the context.
        timeout_seconds: Playwright timeout in seconds.
        max_height: Maximum captured image height; non-positive
            disables the cap.
        target_only: Capture only the target element's region.
        image_type: Image encoding format.
        quality: JPEG quality, 0-100; ignored for PNG output.
        scale: ``css`` for CSS pixels or ``device`` for device pixels.
        user_agent: Optional browser user agent for created contexts.
        is_mobile: Whether created contexts emulate mobile layout.
        has_touch: Whether created contexts expose touch input.
        color_scheme: Optional emulated light or dark color scheme.

    """

    path: Path | None = None
    width: int = 1440
    height: int = 900
    timeout_seconds: float = 30.0
    max_height: int = CaptureScreenDefaults.max_capture_height
    target_only: bool = False
    image_type: Literal["png", "jpeg"] = "png"
    quality: int | None = None
    scale: Literal["css", "device"] = "css"
    user_agent: str | None = None
    is_mobile: bool = False
    has_touch: bool = False
    color_scheme: Literal["light", "dark"] | None = None


@dataclass(frozen=True, slots=True)
class SnapshotOptions:
    """Capture options for `SnapshotCapture`.

    Attributes:
        max_height: Maximum captured image height; non-positive
            disables the cap.
        target_only: Capture only the target element's region.
        image_type: Image encoding format.
        quality: JPEG quality, 0-100; ignored for PNG output.
        scale: ``css`` for CSS pixels or ``device`` for device pixels.

    """

    max_height: int = CaptureScreenDefaults.max_capture_height
    target_only: bool = False
    image_type: Literal["png", "jpeg"] = "png"
    quality: int | None = None
    scale: Literal["css", "device"] = "css"


class SnapshotCapture:
    """Capture a page with all nested target overflow exposed.

    Run one capture per page at a time: expansion state is page-global.
    """

    def __init__(
        self: Self,
        page: Page,
        target: str,
        *,
        options: SnapshotOptions | None = None,
    ) -> None:
        """Initialize the capture.

        Args:
            page: Playwright page.
            target: Target CSS selector.
            options: Optional capture tuning overrides.

        """
        resolved: SnapshotOptions = (
            options if options is not None else SnapshotOptions()
        )
        self.page: Page = page
        self.target: str = target
        self.max_height: int = resolved.max_height
        self.target_only: bool = resolved.target_only
        self.image_type: Literal["png", "jpeg"] = resolved.image_type
        self.quality: int | None = resolved.quality
        self.scale: Literal["css", "device"] = resolved.scale

    async def capture(self: Self, path: Path | None = None) -> Capture:
        """Capture the expanded page and optionally save it.

        Args:
            path: Optional PNG destination.

        Returns:
            Capture containing PNG bytes, path, and Base64 access.

        Raises:
            RuntimeError: If no viewport exists or the target is absent.

        """
        viewport: ViewportSize | None
        root: ElementHandle | None
        if (viewport := self.page.viewport_size) is None:
            msg: str = "Playwright page must have a configured viewport."
            raise RuntimeError(msg)
        if (
            root := await self.page.query_selector(selector=self.target)
        ) is None:
            msg = f"Target element not found: {self.target}"
            raise RuntimeError(msg)
        try:
            truncated: bool
            applied: int
            doc_width: int
            truncated, applied, doc_width = await self._stabilize(
                root=root,
                width=viewport["width"],
            )
            await self.page.evaluate(expression=Js.SETTLE)
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
            if self.target_only:
                await root.scroll_into_view_if_needed()
                await self.page.evaluate(expression=Js.SETTLE)
                if (box := await root.bounding_box()) is None:
                    msg = f"Target element is not visible: {self.target}"
                    raise RuntimeError(msg)
                clip: FloatRect = {
                    "x": box["x"],
                    "y": box["y"],
                    "width": box["width"],
                    "height": min(
                        box["height"],
                        (
                            float(self.max_height)
                            if self.max_height > 0
                            else box["height"]
                        ),
                    ),
                }
                truncated = clip["height"] < box["height"]
            else:
                clip = {"x": 0, "y": 0, "width": doc_width, "height": applied}
            return Capture(
                data=await self.page.screenshot(
                    path=path,
                    clip=clip,
                    type=self.image_type,
                    quality=(
                        self.quality if self.image_type == "jpeg" else None
                    ),
                    scale=self.scale,
                    animations="disabled",
                    caret="hide",
                ),
                path=path,
                truncated_height=truncated,
            )
        finally:
            with suppress(Error):
                await root.evaluate(expression=Js.RESTORE)
            await self.page.set_viewport_size(viewport_size=viewport)

    async def _stabilize(
        self: Self,
        root: ElementHandle,
        width: int,
    ) -> tuple[bool, int, int]:
        """Resize until DOM geometry and viewport height converge.

        Args:
            root: Target root element.
            width: Original viewport width.

        Returns:
            Truncation flag, applied capture height, and document width.

        """
        previous: str = ""
        truncated: bool = False
        applied: int = self.max_height
        doc_width: int = width
        for _ in range(CaptureScreenDefaults.max_iterations):
            changed: bool = cast(
                typ="bool",
                val=await root.evaluate(expression=Js.EXPAND),
            )
            await self.page.evaluate(expression=Js.SETTLE)
            truncated = (
                needed := int(
                    (
                        measurement := cast(
                            typ="dict[str, int | str]",
                            val=await root.evaluate(expression=Js.MEASURE),
                        )
                    )["height"],
                )
            ) > (
                target := (
                    min(needed, self.max_height)
                    if self.max_height > 0
                    else needed
                )
            )
            applied = target
            doc_width = int(measurement["width"])
            delta: int = abs(target - int(measurement["innerHeight"]))
            if (
                (current := f"{needed}|{measurement['signature']}") == previous
                and not changed
                and delta <= CaptureScreenDefaults.tolerance
            ):
                break
            previous = current
            if delta > CaptureScreenDefaults.tolerance:
                await self.page.set_viewport_size(
                    viewport_size={"width": width, "height": target},
                )
        return truncated, applied, doc_width


class Screenshot:
    """Provide a high-level URL screenshot API."""

    @staticmethod
    async def capture(
        url: str | None,
        target: str,
        spec: CaptureSpec | None = None,
        *,
        source: Browser | BrowserContext | Page | None = None,
    ) -> Capture:
        """Load a URL and capture its fully exposed target.

        An optional ``source`` supplies an existing browser, context, or
        page to reuse. Supplied objects are never closed; only objects
        created by this call are cleaned up — a page opened inside a
        supplied context, or a context opened inside a supplied browser.
        A supplied page is navigated to ``url`` when one is given;
        passing ``None`` captures its current state as-is. A supplied
        page keeps its own viewport and default timeout; spec viewport
        dimensions apply only when this call creates the context.

        Args:
            url: URL to load; required unless ``source`` is a page.
            target: CSS selector identifying the target.
            spec: Capture-time options; defaults apply when omitted.
            source: Optional browser, context, or page to reuse.

        Returns:
            Captured screenshot.

        Raises:
            ValueError: If ``url`` is omitted without a page source.

        """
        spec = spec or CaptureSpec()
        if url is None and not isinstance(source, Page):
            msg: str = "url is required unless an existing page is supplied."
            raise ValueError(msg)

        async def in_page(page: Page) -> Capture:
            """Navigate a page to the URL when given and capture it.

            Args:
                page: Page receiving the optional navigation.

            Returns:
                Captured screenshot.

            """
            if spec.color_scheme is not None:
                await page.emulate_media(color_scheme=spec.color_scheme)
            if url is not None:
                _ = await page.goto(
                    url=url,
                    wait_until="networkidle",
                    timeout=spec.timeout_seconds * 1000,
                )
            return await SnapshotCapture(
                page=page,
                target=target,
                options=SnapshotOptions(
                    max_height=spec.max_height,
                    target_only=spec.target_only,
                    image_type=spec.image_type,
                    quality=spec.quality,
                    scale=spec.scale,
                ),
            ).capture(path=spec.path)

        async def in_context(context: BrowserContext) -> Capture:
            """Open, capture, and close a temporary page.

            Args:
                context: Context owning the temporary page.

            Returns:
                Captured screenshot.

            """
            (page := await context.new_page()).set_default_timeout(
                timeout=spec.timeout_seconds * 1000,
            )
            try:
                return await in_page(page=page)
            finally:
                await page.close()

        async def in_browser(browser: Browser) -> Capture:
            """Open, capture, and close a temporary context.

            Args:
                browser: Browser owning the temporary context.

            Returns:
                Captured screenshot.

            """
            context: BrowserContext = await browser.new_context(
                viewport={"width": spec.width, "height": spec.height},
                user_agent=spec.user_agent,
                is_mobile=spec.is_mobile,
                has_touch=spec.has_touch,
            )
            try:
                return await in_context(context=context)
            finally:
                await context.close()

        if isinstance(source, Page):
            return await in_page(page=source)
        if isinstance(source, BrowserContext):
            return await in_context(context=source)
        if isinstance(source, Browser):
            return await in_browser(browser=source)
        async with async_playwright() as playwright:
            browser: Browser = await playwright.chromium.launch(headless=True)
            try:
                return await in_browser(browser=browser)
            finally:
                await browser.close()
