# Copyright (c) 2026 João Lopes.
"""Tests for the unified browser lifecycle API."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from operator import attrgetter
from pathlib import Path
from threading import Event
from typing import cast

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright

from exactus.packages.browser import lifecycle as lifecycle_module
from exactus.packages.browser.lifecycle import (
    BrowserBackend,
    BrowserEvent,
    BrowserEventType,
    BrowserLifecycle,
    BrowserProcess,
    ChromeLocator,
)
from exactus.tests.common.support import private_result, set_private


def expect(*, condition: bool, message: str) -> None:
    """Fail the test when a condition is false.

    Args:
        condition: Condition expected to be true.
        message: Failure explanation.

    """
    if not condition:
        pytest.fail(reason=message)


class FakePage:
    """Minimal runtime page double."""

    def __init__(self) -> None:
        """Initialize page state and handlers."""
        self.url: str = "https://example.com"
        self.closed: bool = False
        self.handlers: dict[str, Callable[[Page], None]] = {}
        self.visited: str | None = None

    @staticmethod
    def wait_for_timeout(timeout: float) -> None:
        """Accept the worker's keep-alive wait without blocking.

        Args:
            timeout: Requested wait in milliseconds (unused).

        """
        _ = timeout

    def is_closed(self) -> bool:
        """Return whether the page is closed.

        Returns:
            Whether the page is closed.

        """
        return self.closed

    def title(self) -> str:
        """Return the title while the page is alive.

        Returns:
            The fixed page title.

        Raises:
            AssertionError: When dead page metadata was queried.

        """
        if self.closed:
            msg: str = "dead page metadata was queried"
            raise AssertionError(msg)
        return "Example"

    def on(self, event: str, f: Callable[[Page], None]) -> None:
        """Record one event callback.

        Args:
            event: Event name.
            f: Callback to invoke.

        """
        self.handlers[event] = f

    def goto(self, url: str) -> None:
        """Record navigation.

        Args:
            url: Navigated URL.

        """
        self.url = url
        self.visited = url

    def fire(self, event: str) -> None:
        """Invoke a recorded callback.

        Args:
            event: Event name to dispatch.

        """
        handler: Callable[[Page], None] = self.handlers[event]
        handler(cast(typ="Page", val=self))


class FakeContext:
    """Minimal runtime context double."""

    def __init__(self) -> None:
        """Initialize context state."""
        self.pages: list[Page] = []
        self.handlers: dict[str, Callable[[Page], None]] = {}
        self.created: FakePage | None = None

    def on(self, event: str, f: Callable[[Page], None]) -> None:
        """Record one event callback.

        Args:
            event: Event name.
            f: Callback to invoke.

        """
        self.handlers[event] = f

    def new_page(self) -> Page:
        """Create and publish a fake page.

        Returns:
            The created fake page.

        """
        page: FakePage = FakePage()
        self.created = page
        self.pages.append(cast(typ="Page", val=page))
        handler: Callable[[Page], None] = self.handlers["page"]
        handler(cast(typ="Page", val=page))
        return cast(typ="Page", val=page)

    def fire(self, event: str) -> None:
        """Invoke a recorded callback.

        Args:
            event: Event name to dispatch.

        """
        handler: Callable[[Page], None] = self.handlers[event]
        handler(cast(typ="Page", val=self))


class FakeBrowser:
    """Minimal runtime browser double."""

    def __init__(self) -> None:
        """Initialize browser state."""
        self.connected: bool = True
        self.handlers: dict[str, Callable[[Page], None]] = {}
        self.context: FakeContext = FakeContext()

    @property
    def contexts(self) -> list[BrowserContext]:
        """Return the single fake context as the context list.

        Returns:
            List containing the fake context.

        """
        return [cast(typ="BrowserContext", val=self.context)]

    def on(self, event: str, f: Callable[[Page], None]) -> None:
        """Record one event callback.

        Args:
            event: Event name.
            f: Callback to invoke.

        """
        self.handlers[event] = f

    def new_context(self) -> BrowserContext:
        """Return the fake context.

        Returns:
            The shared fake context.

        """
        return cast(typ="BrowserContext", val=self.context)

    def is_connected(self) -> bool:
        """Return the connection state.

        Returns:
            Whether the browser is connected.

        """
        return self.connected

    def close(self) -> None:
        """Close and publish disconnection."""
        self.connected = False
        callback: Callable[[Page], None] | None = self.handlers.get(
            "disconnected",
        )
        if callback is not None:
            callback(cast(typ="Page", val=self))


class FakeChromium:
    """Minimal Chromium launcher double."""

    def __init__(self, browser: FakeBrowser) -> None:
        """Store the browser returned by launch.

        Args:
            browser: Browser returned by ``launch``.

        """
        self.browser: FakeBrowser = browser

    def launch(self, **_kwargs: str | bool | list[str] | None) -> Browser:
        """Return the configured browser.

        Args:
            _kwargs: Ignored launch options.

        Returns:
            The configured fake browser.

        """
        return cast(typ="Browser", val=self.browser)


class FakePlaywright:
    """Minimal Playwright runtime double."""

    def __init__(self, browser: FakeBrowser) -> None:
        """Initialize the Chromium launcher.

        Args:
            browser: Browser returned by ``chromium.launch``.

        """
        self.chromium: FakeChromium = FakeChromium(browser=browser)
        self.stopped: bool = False

    def stop(self) -> None:
        """Record shutdown."""
        self.stopped = True


class FakeStarter:
    """Minimal sync_playwright context double."""

    def __init__(self, playwright: FakePlaywright) -> None:
        """Store the runtime returned by start.

        Args:
            playwright: Runtime returned by ``start``.

        """
        self.playwright: FakePlaywright = playwright

    def start(self) -> Playwright:
        """Return the configured Playwright runtime.

        Returns:
            The configured fake runtime.

        """
        return cast(typ="Playwright", val=self.playwright)


class FakeProcess:
    """Deterministic native process double.

    Attributes:
        pid: Fake process identifier reported to the controller.

    """

    pid: int = 42

    def __init__(self) -> None:
        """Initialize process state."""
        self.code: int | None = None
        self.waited: Event = Event()

    def poll(self) -> int | None:
        """Return the current exit code.

        Returns:
            The recorded exit code, or ``None`` while running.

        """
        return self.code

    def wait(self) -> int:
        """Return a deterministic exit code and signal completion.

        Returns:
            The recorded exit code.

        """
        self.code = 0
        self.waited.set()
        return self.code

    def terminate(self) -> None:
        """Record termination."""
        self.code = -15


class FakeProcessFactory:
    """Return a configured native process double."""

    def __init__(self, process: FakeProcess) -> None:
        """Initialize the process factory.

        Args:
            process: Process returned for every launch.

        """
        self.process: FakeProcess = process
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, *, command: Sequence[str]) -> BrowserProcess:
        """Record a launch command and return the configured process.

        Args:
            command: Native browser launch command.

        Returns:
            Configured fake process.

        """
        self.commands.append(tuple(command))
        return self.process


class FakeChromeLocator:
    """Provide deterministic Chrome executable discovery.

    Attributes:
        executable: Deterministic fake Chrome executable path.

    """

    executable: Path = Path("/fake/chrome")

    @classmethod
    def find(cls, executable: Path | None = None) -> Path:
        """Return a deterministic executable path.

        Args:
            executable: Optional explicit executable override.

        Returns:
            Explicit executable or deterministic fake executable.

        """
        return cls.executable if executable is None else executable


class TestBrowserLifecycle:
    """Exercise public lifecycle behavior."""

    @staticmethod
    def test_subscriptions_are_ordered_and_removable(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Specific listeners precede global listeners without duplicates.

        Args:
            monkeypatch: Fixture replacing Chrome executable discovery.

        """
        monkeypatch.setattr(
            target=lifecycle_module,
            name="ChromeLocator",
            value=FakeChromeLocator,
        )
        calls: list[str] = []
        lifecycle: BrowserLifecycle = BrowserLifecycle()

        def specific(*, event: BrowserEvent) -> None:
            """Record the specific callback.

            Args:
                event: Emitted browser lifecycle event.

            """
            _ = event
            calls.append("specific")

        def global_callback(*, event: BrowserEvent) -> None:
            """Record the global callback.

            Args:
                event: Emitted browser lifecycle event.

            """
            _ = event
            calls.append("global")

        lifecycle.on(event=BrowserEventType.PROCESS_START, callback=specific)
        lifecycle.on(event=BrowserEventType.PROCESS_START, callback=specific)
        lifecycle.on_all(callback=specific)
        lifecycle.off_all(callback=specific)
        lifecycle.on_all(callback=global_callback)
        lifecycle.on_all(callback=global_callback)
        process: FakeProcess = FakeProcess()
        process_factory: FakeProcessFactory = FakeProcessFactory(
            process=process,
        )
        native: BrowserLifecycle = BrowserLifecycle(
            clock=lambda: datetime(year=2026, month=1, day=1, tzinfo=UTC),
            process_factory=process_factory,
        )
        native.on(event=BrowserEventType.PROCESS_START, callback=specific)
        native.on_all(callback=global_callback)
        _ = native.launch_chrome(url="about:blank")
        expect(
            condition=calls[:2] == ["specific", "global"],
            message="callback order differs",
        )
        expect(
            condition=process_factory.commands
            == [(str(object=FakeChromeLocator.executable), "about:blank")],
            message="native browser command differs",
        )
        native.off(event=BrowserEventType.PROCESS_START, callback=specific)
        native.off_all(callback=global_callback)
        lifecycle.off(event=BrowserEventType.PROCESS_START, callback=specific)
        lifecycle.off_all(callback=global_callback)

    @staticmethod
    def test_playwright_events_use_last_live_page_state(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Close and crash events never query a dead page.

        Args:
            monkeypatch: Fixture replacing ``sync_playwright``.

        """
        browser: FakeBrowser = FakeBrowser()
        runtime: FakePlaywright = FakePlaywright(browser=browser)
        monkeypatch.setattr(
            target=lifecycle_module,
            name="sync_playwright",
            value=lambda: FakeStarter(playwright=runtime),
        )
        events: list[BrowserEvent] = []

        def record_event(*, event: BrowserEvent) -> None:
            """Record an emitted browser lifecycle event.

            Args:
                event: Emitted browser lifecycle event.

            """
            events.append(event)

        lifecycle: BrowserLifecycle = BrowserLifecycle(callback=record_event)
        launched: Browser = lifecycle.launch_playwright(
            url="https://example.com/start",
            headless=True,
        )
        expect(
            condition=launched is cast(typ="Browser", val=browser),
            message="unexpected browser",
        )
        page: FakePage = cast(typ="FakePage", val=browser.context.created)
        page.url = "https://example.com/final"
        page.fire(event="framenavigated")
        page.fire(event="crash")
        page.closed = True
        page.fire(event="close")
        event: BrowserEvent
        crash: BrowserEvent | None = None
        for event in events:
            if event.event is BrowserEventType.PAGE_CRASH:
                crash = event
                break
        close: BrowserEvent | None = None
        for event in events:
            if event.event is BrowserEventType.PAGE_CLOSE:
                close = event
                break
        if crash is None:
            pytest.fail(reason="crash event missing")
        if close is None:
            pytest.fail(reason="close event missing")
        expect(
            condition=crash.url == "https://example.com/final",
            message="crash URL differs",
        )
        expect(
            condition=close.url == "https://example.com/final",
            message="close URL differs",
        )
        expect(
            condition=close.title == "Example",
            message="close title differs",
        )
        expect(
            condition=close.page_identity == id(page),
            message="page identity differs",
        )
        browser.context.fire(event="close")
        lifecycle.close()
        expect(condition=runtime.stopped, message="runtime did not stop")
        kinds: list[BrowserEventType] = list(map(attrgetter("event"), events))
        expect(
            condition=BrowserEventType.BROWSER_DISCONNECTED in kinds,
            message="disconnect event missing",
        )
        expect(
            condition=BrowserEventType.CONTEXT_CLOSE in kinds,
            message="context close event missing",
        )

    @staticmethod
    def test_native_process_events_include_pid_and_exit_code(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Native process lifecycle carries backend process information.

        Args:
            monkeypatch: Fixture replacing Chrome executable discovery.

        """
        monkeypatch.setattr(
            target=lifecycle_module,
            name="ChromeLocator",
            value=FakeChromeLocator,
        )
        process: FakeProcess = FakeProcess()
        process_factory: FakeProcessFactory = FakeProcessFactory(
            process=process,
        )
        events: list[BrowserEvent] = []

        def record_event(*, event: BrowserEvent) -> None:
            """Record an emitted browser lifecycle event.

            Args:
                event: Emitted browser lifecycle event.

            """
            events.append(event)

        lifecycle: BrowserLifecycle = BrowserLifecycle(
            callback=record_event,
            process_factory=process_factory,
        )
        returned: BrowserProcess = lifecycle.launch_chrome(url="about:blank")
        expect(condition=returned is process, message="unexpected process")
        expect(
            condition=process_factory.commands
            == [(str(object=FakeChromeLocator.executable), "about:blank")],
            message="native browser command differs",
        )
        expect(
            condition=process.waited.wait(timeout=1.0),
            message="process watcher did not finish",
        )
        starts: list[BrowserEvent] = list(
            filter(
                lambda item: item.event is BrowserEventType.PROCESS_START,
                events,
            ),
        )
        exits: list[BrowserEvent] = list(
            filter(
                lambda item: item.event is BrowserEventType.PROCESS_EXIT,
                events,
            ),
        )
        expect(
            condition=starts[0].backend is BrowserBackend.CHROME,
            message="backend differs",
        )
        expect(
            condition=starts[0].pid == FakeProcess.pid,
            message="PID differs",
        )
        expect(condition=exits[0].exit_code == 0, message="exit code differs")
        lifecycle.close()

    @staticmethod
    def test_idle_properties_and_native_termination() -> None:
        """Idle state is empty and close terminates a running process."""
        lifecycle: BrowserLifecycle = BrowserLifecycle()
        expect(
            condition=lifecycle.browser is None,
            message="browser should be absent",
        )
        expect(
            condition=lifecycle.process is None,
            message="process should be absent",
        )
        expect(condition=lifecycle.pid is None, message="PID should be absent")


def _chrome_locator_platform(
    *,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> tuple[tuple[str, ...], tuple[Path, ...]]:
    """Return locator candidates for a simulated operating system.

    Args:
        monkeypatch: Pytest patching helper.
        platform: ``platform.system`` value to simulate.

    Returns:
        Executable name and installation directory candidates.

    """
    monkeypatch.setattr(
        target=lifecycle_module,
        name="system",
        value=lambda: platform,
    )
    names: tuple[str, ...] = cast(
        typ="tuple[str, ...]",
        val=private_result(
            owner=ChromeLocator,
            name="_path_candidates",
            kind=tuple,
        ),
    )
    roots: tuple[Path, ...] = cast(
        typ="tuple[Path, ...]",
        val=private_result(
            owner=ChromeLocator,
            name="_installation_candidates",
            kind=tuple,
        ),
    )
    return (names, roots)


def test_darwin_locator_scans_application_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MacOS discovery scans the usual ``.app`` installation roots.

    Args:
        monkeypatch: Pytest patching helper.

    """
    names, roots = _chrome_locator_platform(
        monkeypatch=monkeypatch,
        platform="Darwin",
    )
    expect(condition="google-chrome" in names, message="PATH names missing")
    expect(
        condition=any("Chrome.app" in str(object=path) for path in roots),
        message="installation candidates missing",
    )


def test_windows_locator_uses_program_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows discovery derives paths from ``PROGRAMFILES`` values.

    Args:
        monkeypatch: Pytest patching helper.

    """

    def _getenv(*, key: str) -> str:
        """Return a synthetic Program Files or AppData location.

        Args:
            key: Environment variable name.

        Returns:
            The synthetic Windows directory.

        """
        return (
            "C:\\Program Files"
            if "PROGRAM" in key
            else "C:\\Users\\x\\AppData\\Local"
        )

    monkeypatch.setattr(target=lifecycle_module, name="getenv", value=_getenv)
    names, roots = _chrome_locator_platform(
        monkeypatch=monkeypatch,
        platform="Windows",
    )
    expect(condition="chrome.exe" in names, message="PATH names missing")
    expect(
        condition=any("chrome.exe" in str(object=path) for path in roots),
        message="installation candidates missing",
    )


def test_linux_locator_uses_generic_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Other platforms fall back to the generic binary names.

    Args:
        monkeypatch: Pytest patching helper.

    """
    names, roots = _chrome_locator_platform(
        monkeypatch=monkeypatch,
        platform="Linux",
    )
    expect(condition=len(names) >= 1, message="empty PATH candidates")
    expect(condition=len(roots) >= 1, message="empty install candidates")


def test_find_rejects_missing_explicit_executable() -> None:
    """An explicit missing executable raises ``FileNotFoundError``."""
    with pytest.raises(expected_exception=FileNotFoundError):
        ChromeLocator.find(executable=Path("/nonexistent/chrome"))


def test_find_reports_missing_installation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exhausting every discovery strategy raises ``FileNotFoundError``.

    Args:
        monkeypatch: Pytest patching helper.

    """

    def _not_found(*_ignored: object, **_named: object) -> None:
        """Report that no executable exists on ``PATH``.

        Args:
            _ignored: Positional arguments (unused).
            _named: Keyword arguments (unused).

        """
        return

    monkeypatch.setattr(
        target=lifecycle_module,
        name="which",
        value=_not_found,
    )

    def _no_roots(_cls: type[ChromeLocator]) -> tuple[()]:
        """Return no installation roots.

        Args:
            _cls: Locator class (unused).

        Returns:
            An empty tuple.

        """
        return ()

    monkeypatch.setattr(
        target=ChromeLocator,
        name="_installation_candidates",
        value=classmethod(_no_roots),
    )
    with pytest.raises(expected_exception=FileNotFoundError):
        ChromeLocator.find()


def test_start_playwright_runs_worker_until_pages_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The worker publishes readiness and exits when pages vanish.

    Args:
        monkeypatch: Pytest patching helper.

    """
    lifecycle: BrowserLifecycle = BrowserLifecycle()
    browser: FakeBrowser = FakeBrowser()

    def launch(
        self: BrowserLifecycle,
        url: str,
        **_options: object,
    ) -> Browser:
        """Return the fake browser and mark the worker ready.

        Args:
            self: Lifecycle instance owning the worker.
            url: Initial URL (unused).
            _options: Ignored launch options.

        Returns:
            The configured fake browser.

        """
        _ = url
        set_private(
            owner=self,
            name="_browser",
            value=cast(typ="Browser", val=browser),
        )
        return cast(typ="Browser", val=browser)

    monkeypatch.setattr(
        target=BrowserLifecycle,
        name="launch_playwright",
        value=launch,
    )
    try:
        lifecycle.start_playwright(url="https://example.com")
        expect(
            condition=lifecycle.wait_ready(timeout=5.0),
            message="worker never became ready",
        )
        expect(
            condition=lifecycle.wait(timeout=5.0),
            message="worker never finished",
        )
    finally:
        lifecycle.close()


def test_start_playwright_rejects_a_running_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second ``start_playwright`` call raises ``RuntimeError``.

    Args:
        monkeypatch: Pytest patching helper.

    """
    lifecycle: BrowserLifecycle = BrowserLifecycle()
    browser: FakeBrowser = FakeBrowser()

    def launch(
        self: BrowserLifecycle,
        url: str,
        **_options: object,
    ) -> Browser:
        """Return a fake browser whose page never closes.

        Args:
            self: Lifecycle instance owning the worker.
            url: Initial URL (unused).
            _options: Ignored launch options.

        Returns:
            The configured fake browser.

        """
        _ = url
        set_private(
            owner=self,
            name="_browser",
            value=cast(typ="Browser", val=browser),
        )
        return cast(typ="Browser", val=browser)

    monkeypatch.setattr(
        target=BrowserLifecycle,
        name="launch_playwright",
        value=launch,
    )
    page: FakePage = FakePage()
    browser.context.pages.append(cast(typ="Page", val=page))
    try:
        lifecycle.start_playwright(url="https://example.com")
        expect(
            condition=lifecycle.wait_ready(timeout=5.0),
            message="worker never became ready",
        )
        with pytest.raises(expected_exception=RuntimeError):
            lifecycle.start_playwright(url="https://example.com")
        lifecycle.close()
        expect(
            condition=lifecycle.wait(timeout=5.0),
            message="worker never finished",
        )
    finally:
        lifecycle.close()
