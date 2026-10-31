# Copyright (c) 2026
"""Image similarity and the high-level screenshot capture API."""

from __future__ import annotations

from asyncio import run
from base64 import b64encode
from importlib import import_module
from io import BytesIO
from re import compile as re_compile
from textwrap import dedent
from typing import TYPE_CHECKING, Final, NoReturn, Protocol, cast, final

import pytest
from PIL import Image
from playwright.async_api import async_playwright

from exactus.packages.screenshot import capture_screen as screenshot_capture
from exactus.packages.screenshot import similarity as screenshot_similarity
from exactus.packages.screenshot.capture_screen import (
    Capture,
    CaptureSpec,
    Screenshot,
    SnapshotCapture,
    SnapshotOptions,
)
from exactus.packages.screenshot.similarity import ImageSimilarity
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
    private_call,
    require,
)
from exactus.tools.record import capture_screen as recorder_capture
from exactus.tools.record import similarity as recorder_similarity
from exactus.tools.record.diagnostics import DiagnosticCollector

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from types import ModuleType

    from PIL.Image import Image as PilImage
    from playwright.async_api import Browser, BrowserContext, Page, WebSocket

    from exactus.packages.screenshot.similarity import (
        CachedComparison,
        ImageSource,
        SimilarityResult,
    )


@final
class Constants:
    """Group module-level constants.

    Attributes:
        max_distinct: Grouped module constant.
        page: Grouped module constant.

    """

    max_distinct: Final[float] = 0.95
    page: Final[str] = dedent(
        text=(
            '    <!doctype html><html><body style="margin:0">\n    <div id="t"'
            ' style="height:100px;overflow:auto;width:200px">\n    <div style='
            '"height:1200px;background:linear-gradient(red,blue)">\n    long</'
            'div></div>\n    <div style="height:5000px"></div></body></html>'
        ),
    )


def _png(
    color: tuple[int, int, int],
    size: tuple[int, int] = (64, 48),
) -> bytes:
    """Encode a solid-color PNG.

    Args:
        color: RGB color.
        size: Image size.

    Returns:
        PNG bytes.

    """
    buffer: BytesIO = BytesIO()
    Image.new(mode="RGB", size=size, color=color).save(fp=buffer, format="PNG")
    return buffer.getvalue()


def _striped(size: tuple[int, int] = (64, 48)) -> Image.Image:
    """Create a striped image.

    Args:
        size: Image size.

    Returns:
        The image.

    """
    image: PilImage = Image.new(mode="RGB", size=size, color=(255, 255, 255))
    for x in range(0, size[0], 8):
        for y in range(size[1]):
            image.putpixel(xy=(x, y), value=(0, 0, 0))
    return image


def _approx(*, expected: float) -> object:
    """Return a loose numeric equality matcher.

    ``pytest.approx`` ships without parameter annotations, so the call is
    routed through :func:`exactus.tests.common.support.private_call`.

    Args:
        expected: Required value.

    Returns:
        The matcher object.

    """
    return private_call(owner=pytest, name="approx", expected=expected)


def test_similarity_identical_and_different() -> None:
    """Identical images score one and different images score lower."""
    red: bytes = _png(color=(255, 0, 0))
    expect_equal(
        actual=ImageSimilarity.compare(first=red, second=red),
        expected=_approx(expected=1.0),
    )
    expect_true(
        condition=ImageSimilarity.compare(
            first=red,
            second=_png(color=(0, 0, 255)),
        )
        < Constants.max_distinct,
    )
    expect_true(
        condition=ImageSimilarity.compare(
            first=red,
            second=_png(color=(255, 0, 0), size=(640, 100)),
        )
        < 1.0,
    )
    detail: SimilarityResult = ImageSimilarity.compare_detailed(
        first=red,
        second=_png(color=(0, 255, 0)),
    )
    expect_true(condition=0.0 <= detail.similarity <= 1.0)


def test_similarity_sources(tmp_path: Path) -> None:
    """Paths, Base64 strings, data URLs, bytes, files and images load.

    Args:
        tmp_path: Per-test temporary directory.

    """
    data: bytes = _png(color=(10, 20, 30))
    path: Path = tmp_path / "a.png"
    path.write_bytes(data=data)
    encoded: str = b64encode(s=data).decode()
    sources: list[Path | str | bytes | BytesIO | PilImage] = [
        path,
        str(object=path),
        encoded,
        f"data:image/png;base64,{encoded}",
        data,
        b64encode(s=data),
        BytesIO(initial_bytes=data),
        Image.open(fp=BytesIO(initial_bytes=data)),
    ]
    for source in sources:
        expect_equal(
            actual=ImageSimilarity.compare(first=data, second=source),
            expected=_approx(expected=1.0),
        )
    stream: BytesIO = BytesIO(initial_bytes=data)
    _ = stream.read(3)
    with pytest.raises(expected_exception=ValueError, match="file object"):
        _ = ImageSimilarity.compare(first=stream, second=data)
    expect_equal(actual=stream.tell(), expected=3)


class Unseekable:
    """File-like object that cannot seek."""

    def __init__(self, data: bytes) -> None:
        """Store data.

        Args:
            data: Bytes to serve.

        """
        self.data = data

    @staticmethod
    def seekable() -> bool:
        """Report that seeking is unsupported.

        Returns:
            Always false.

        """
        return False

    def read(self) -> bytes:
        """Return all data.

        Returns:
            The stored bytes.

        """
        return self.data


class Broken:
    """File-like object whose reads fail."""

    @staticmethod
    def seekable() -> bool:
        """Report seekability.

        Returns:
            Always false.

        """
        return False

    @staticmethod
    def read() -> NoReturn:
        """Fail reads.

        Raises:
            OSError: Always.

        """
        raise OSError


def test_similarity_errors(tmp_path: Path) -> None:
    """Undecodable sources raise ``ValueError``.

    Args:
        tmp_path: Per-test temporary directory.

    """
    good: bytes = _png(color=(1, 2, 3))
    expect_equal(
        actual=ImageSimilarity.compare(
            first=cast(typ="ImageSource", val=Unseekable(data=good)),
            second=good,
        ),
        expected=_approx(expected=1.0),
    )
    bad_file: Path = tmp_path / "bad.png"
    bad_file.write_text(data="not an image")
    for source in (
        bad_file,
        "definitely not base64 or a path!",
        b"neither",
        b"!!!!",
        cast(typ="ImageSource", val=Broken()),
    ):
        with pytest.raises(
            expected_exception=ValueError,
            match=re_compile(pattern="Cannot|neither"),
        ):
            _ = ImageSimilarity.compare(first=source, second=good)


def test_similarity_history_cache() -> None:
    """History comparisons accumulate and can be cleared."""
    sim: ImageSimilarity = ImageSimilarity()
    expect_equal(
        actual=sim.compare_history(source=_png(color=(1, 1, 1))),
        expected=(),
    )
    expect_equal(actual=sim.cache_size, expected=1)
    expect_equal(actual=sim.remember(source=_png(color=(9, 9, 9))), expected=1)
    found: tuple[CachedComparison, ...] = sim.compare_history(
        source=_png(color=(1, 1, 1)),
        remember=False,
    )
    expect_equal(actual=[c.index for c in found], expected=[0, 1])
    expect_equal(actual=sim.cache_size, expected=2)
    sim.clear_cache()
    expect_equal(actual=sim.cache_size, expected=0)
    stripes: PilImage = _striped()
    expect_equal(
        actual=ImageSimilarity.compare(first=stripes, second=stripes),
        expected=_approx(expected=1.0),
    )
    expect_true(
        condition=ImageSimilarity.compare(
            first=stripes,
            second=stripes.rotate(angle=90),
        )
        <= 1.0,
    )


def test_snapshot_capture_options(tmp_path: Path) -> None:
    """Expanded captures honor caps, clipping, formats and scales.

    Args:
        tmp_path: Per-test temporary directory.

    """

    async def scenario() -> list[Capture]:
        """Capture a snapshot with every option in a live browser.

        Returns:
            The captured results.

        """
        async with async_playwright() as playwright:
            browser: Browser = await playwright.chromium.launch(headless=True)
            context: BrowserContext = await browser.new_context(
                viewport={"width": 400, "height": 300},
            )
            page: Page = await context.new_page()
            await page.set_content(html=Constants.page)
            results: list[Capture] = [
                await SnapshotCapture(page=page, target="#t").capture(
                    path=tmp_path / "a.png",
                ),
                await SnapshotCapture(
                    page=page,
                    target="#t",
                    options=SnapshotOptions(
                        max_height=500,
                        target_only=True,
                        scale="device",
                    ),
                ).capture(),
                await SnapshotCapture(
                    page=page,
                    target="body",
                    options=SnapshotOptions(
                        max_height=0,
                        image_type="jpeg",
                        quality=60,
                    ),
                ).capture(),
            ]
            await browser.close()
            return results

    captures: list[Capture] = run(main=scenario())
    first_path: Path = require(value=captures[0].path)
    expect_equal(actual=first_path, expected=tmp_path / "a.png")
    expect_true(condition=first_path.is_file())
    expect_true(
        condition=bool(captures[1].truncated_height or captures[1].data),
    )
    expect_equal(actual=captures[2].data[:2], expected=b"\xff\xd8")
    expect_true(condition=bool(captures[0].b64))


def test_screenshot_api_sources(tmp_path: Path, demo_url: str) -> None:
    """The URL API works standalone and over supplied browser objects.

    Args:
        tmp_path: Per-test temporary directory.
        demo_url: Base URL of the live demo server.

    """

    async def scenario() -> None:
        """Capture through the high-level API from each source kind."""
        spec: CaptureSpec = CaptureSpec(
            path=tmp_path / "s.png",
            color_scheme="dark",
            is_mobile=True,
            has_touch=True,
            user_agent="x",
        )
        standalone: Capture = await Screenshot.capture(
            url=demo_url,
            target="body",
            spec=spec,
        )
        expect_true(condition=bool(standalone.data))
        async with async_playwright() as playwright:
            browser: Browser = await playwright.chromium.launch(headless=True)
            expect_true(
                condition=bool(
                    (
                        await Screenshot.capture(
                            url=demo_url,
                            target="body",
                            source=browser,
                        )
                    ).data,
                ),
            )
            context: BrowserContext = await browser.new_context()
            expect_true(
                condition=bool(
                    (
                        await Screenshot.capture(
                            url=demo_url,
                            target="body",
                            source=context,
                        )
                    ).data,
                ),
            )
            page: Page = await context.new_page()
            _ = await page.goto(url=demo_url)
            expect_true(
                condition=bool(
                    (
                        await Screenshot.capture(
                            url=None,
                            target="body",
                            source=page,
                        )
                    ).data,
                ),
            )
            expect_true(
                condition=bool(
                    (
                        await Screenshot.capture(
                            url=demo_url,
                            target="body",
                            source=page,
                        )
                    ).data,
                ),
            )
            await browser.close()
        with pytest.raises(
            expected_exception=ValueError,
            match="url is required",
        ):
            _ = await Screenshot.capture(url=None, target="body")

    run(main=scenario())


class _SocketCallback(Protocol):
    """WebSocket listener accepting a positional event value."""

    def __call__(self, value: object, /) -> None:
        """Receive a simulated WebSocket event.

        Args:
            value: Error message or received frame.

        """
        ...


class _SocketStub:
    """Stand-in WebSocket recording listener callbacks."""

    def __init__(self) -> None:
        """Initialize with a fixed URL and an empty handler map."""
        self.url: str = "wss://example.invalid/socket"
        self.handlers: dict[str, Callable[[object], None]] = {}

    def on(self, event: str, f: Callable[[object], None]) -> None:
        """Record one event handler.

        Args:
            event: Event name the collector listens to.
            f: Callback registered for the event.

        """
        self.handlers[event] = f


def test_collector_records_websocket_diagnostics() -> None:
    """Socket errors and error-bearing frames become diagnostics."""
    collector: DiagnosticCollector = DiagnosticCollector(variant="desktop")
    socket: _SocketStub = _SocketStub()
    private_call(
        owner=collector,
        name="_websocket",
        socket=cast(typ="WebSocket", val=socket),
    )
    socket_error: _SocketCallback = socket.handlers["socketerror"]
    frame_received: _SocketCallback = socket.handlers["framereceived"]
    socket_error("boom")
    frame_received("plain frame")
    frame_received("error: exploded")
    messages: list[str] = [event.message for event in collector.events]
    expect_in(member="boom", container=messages)
    expect_in(member="error: exploded", container=messages)
    expect_not_in(member="plain frame", container=messages)


@pytest.fixture(autouse=True, params=("screenshot", "record"))
def capture_implementation(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify both public capture implementations against the same contract.

    Args:
        request: Selected public package.
        monkeypatch: Restore module bindings after each contract.

    """
    capture: ModuleType = (
        recorder_capture if request.param == "record" else screenshot_capture
    )
    similarity: ModuleType = (
        recorder_similarity
        if request.param == "record"
        else screenshot_similarity
    )
    module: ModuleType = import_module(name=__name__)
    name: str
    for name in (
        "Capture",
        "CaptureSpec",
        "Screenshot",
        "SnapshotCapture",
        "SnapshotOptions",
    ):
        monkeypatch.setattr(
            target=module,
            name=name,
            value=getattr(capture, name),
        )
    monkeypatch.setattr(
        target=module,
        name="ImageSimilarity",
        value=similarity.ImageSimilarity,
    )
