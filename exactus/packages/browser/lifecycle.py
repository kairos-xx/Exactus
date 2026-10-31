# Copyright (c) 2026 João Lopes.
"""Unified lifecycle monitoring for Playwright Chromium and native Chrome."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from os import getenv
from pathlib import Path
from platform import system
from shutil import which
from subprocess import Popen
from threading import Event, Lock, Thread, current_thread
from typing import TYPE_CHECKING, Protocol

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)
from playwright.sync_api import Error as PlaywrightError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class ChromeLocator:
    """Resolve installed Chrome or Chromium executables portably."""

    @classmethod
    def find(cls, executable: Path | None = None) -> Path:
        """Resolve a usable Chrome or Chromium executable.

        Args:
            executable: Explicit executable override. When supplied, it must
                identify an existing file.

        Returns:
            Resolved executable path.

        Raises:
            FileNotFoundError: When an explicit path is invalid or no browser
                installation can be found.

        """
        if executable is not None:
            resolved: Path = executable.expanduser().resolve()
            if resolved.is_file():
                return resolved
            msg: str = f"Chrome executable does not exist: {resolved}"
            raise FileNotFoundError(msg)
        executable_name: str
        for executable_name in cls._path_candidates():
            if (located_path := which(cmd=executable_name)) is not None:
                return Path(located_path).resolve()
        candidate_path: Path
        for candidate_path in cls._installation_candidates():
            if candidate_path.is_file():
                return candidate_path.resolve()
        msg = (
            "Chrome or Chromium was not found. Install Chrome/Chromium, add "
            "it to PATH, or provide executable=Path(...)."
        )
        raise FileNotFoundError(msg)

    @staticmethod
    def _path_candidates() -> tuple[str, ...]:
        """Return executable names searched through ``PATH``.

        Returns:
            Platform-appropriate Chrome and Chromium executable names.

        """
        match system():
            case "Windows":
                return ("chrome.exe", "chromium.exe")
            case "Darwin":
                return ("google-chrome", "chromium", "chrome")
            case _:
                return (
                    "google-chrome-stable",
                    "google-chrome",
                    "chromium",
                    "chromium-browser",
                )

    @staticmethod
    def _installation_candidates() -> tuple[Path, ...]:
        """Return conventional browser installation paths.

        Returns:
            Existing and non-existing candidate paths in preference order.

        """
        platform: str = system()
        if platform == "Darwin":
            application_roots: tuple[Path, ...] = (
                Path("/Applications"),
                Path.home() / "Applications",
            )
            application_names: tuple[str, ...] = (
                "Google Chrome.app",
                "Google Chrome Beta.app",
                "Google Chrome Dev.app",
                "Google Chrome Canary.app",
                "Chromium.app",
            )
            return tuple(
                application_root
                / application_name
                / "Contents"
                / "MacOS"
                / application_name.removesuffix(".app")
                for application_root in application_roots
                for application_name in application_names
            )
        if platform == "Windows":
            installation_roots: tuple[Path, ...] = tuple(
                Path(environment_value)
                for environment_name in (
                    "PROGRAMFILES",
                    "PROGRAMFILES(X86)",
                    "LOCALAPPDATA",
                )
                if (environment_value := getenv(key=environment_name))
                is not None
            )
            relative_paths: tuple[Path, ...] = (
                Path("Google/Chrome/Application/chrome.exe"),
                Path("Google/Chrome Beta/Application/chrome.exe"),
                Path("Google/Chrome Dev/Application/chrome.exe"),
                Path("Google/Chrome SxS/Application/chrome.exe"),
                Path("Chromium/Application/chrome.exe"),
            )
            return tuple(
                installation_root / relative_path
                for installation_root in installation_roots
                for relative_path in relative_paths
            )
        return tuple(
            Path(candidate_path)
            for candidate_path in (
                "/usr/bin/google-chrome-stable",
                "/usr/bin/google-chrome",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium",
                "/var/lib/flatpak/exports/bin/com.google.Chrome",
                "/var/lib/flatpak/exports/bin/org.chromium.Chromium",
            )
        )


class BrowserBackend(StrEnum):
    """Supported browser backends.

    Attributes:
        PLAYWRIGHT: Drive the browser through Playwright.
        CHROME: Launch a native Chrome/Chromium executable.

    """

    PLAYWRIGHT = "playwright"
    CHROME = "chrome"


class BrowserEventType(StrEnum):
    """Lifecycle events emitted by the controller.

    Attributes:
        PROCESS_START: The native browser process started.
        PROCESS_EXIT: The native browser process exited.
        BROWSER_CONNECTED: A browser connection was established.
        BROWSER_DISCONNECTED: The browser connection was closed.
        CONTEXT_OPEN: A browser context opened.
        CONTEXT_CLOSE: A browser context closed.
        PAGE_OPEN: A page opened.
        PAGE_CLOSE: A page closed.
        PAGE_CRASH: A page crashed.

    """

    PROCESS_START = "process_start"
    PROCESS_EXIT = "process_exit"
    BROWSER_CONNECTED = "browser_connected"
    BROWSER_DISCONNECTED = "browser_disconnected"
    CONTEXT_OPEN = "context_open"
    CONTEXT_CLOSE = "context_close"
    PAGE_OPEN = "page_open"
    PAGE_CLOSE = "page_close"
    PAGE_CRASH = "page_crash"


class BrowserProcess(Protocol):
    """Native process operations required by the controller."""

    @property
    def pid(self) -> int:
        """Return the process identifier.

        Returns:
            The native process identifier.

        """
        ...

    def poll(self) -> int | None:
        """Return the exit status when available.

        Returns:
            The exit status, or None while the process runs.

        """
        ...

    def wait(self) -> int:
        """Wait for process termination.

        Returns:
            The process exit status.

        """
        ...

    def terminate(self) -> None:
        """Request process termination."""
        ...


class ProcessFactory(Protocol):
    """Create native browser processes."""

    def __call__(self, *, command: Sequence[str]) -> BrowserProcess:
        """Create a native browser process.

        Args:
            command: Executable and command-line arguments.

        Returns:
            Created native browser process.

        """
        ...


class NativeProcessFactory:
    """Create native browser subprocesses."""

    def __call__(self, *, command: Sequence[str]) -> BrowserProcess:
        """Create a native browser subprocess.

        Args:
            command: Executable and command-line arguments.

        Returns:
            Created subprocess.

        """
        return Popen(args=list(command))


@dataclass(frozen=True, slots=True)
class PageState:
    """Last-known metadata for one Playwright page.

    Attributes:
        identity: Stable identity derived from the page object.
        url: Last reported page URL.
        title: Last reported page title.

    """

    identity: int
    url: str
    title: str


@dataclass(frozen=True, slots=True)
class BrowserEvent:
    """Immutable snapshot describing a lifecycle event.

    Attributes:
        event: The kind of lifecycle transition.
        backend: Backend that produced the event.
        timestamp: UTC time the event was recorded.
        pid: Native process identifier when known.
        exit_code: Process exit status for exit events.
        browser: Playwright browser handle when connected.
        context: Playwright context tied to the event.
        page: Playwright page tied to the event.
        page_identity: Stable identity of the affected page.
        url: URL reported for the affected page.
        title: Title reported for the affected page.

    """

    event: BrowserEventType
    backend: BrowserBackend
    timestamp: datetime
    pid: int | None
    exit_code: int | None
    browser: Browser | None
    context: BrowserContext | None
    page: Page | None
    page_identity: int | None
    url: str | None
    title: str | None


class BrowserCallback(Protocol):
    """Handle one immutable browser lifecycle event."""

    def __call__(self, *, event: BrowserEvent) -> None:
        """Handle a browser lifecycle event.

        Args:
            event: Immutable browser lifecycle event snapshot.

        """
        ...


type Clock = Callable[[], datetime]


class BrowserLifecycle:
    """Launch browsers and publish normalized lifecycle events."""

    def __init__(
        self,
        callback: BrowserCallback | None = None,
        *,
        clock: Clock | None = None,
        process_factory: ProcessFactory | None = None,
    ) -> None:
        """Initialize an idle lifecycle controller.

        Args:
            callback: Optional callback registered for every event.
            clock: Optional UTC timestamp provider.
            process_factory: Optional native process constructor.

        """
        self._backend: BrowserBackend = BrowserBackend.PLAYWRIGHT
        self._clock: Clock = (
            (lambda: datetime.now(tz=UTC)) if clock is None else clock
        )
        self._process_factory: ProcessFactory = (
            NativeProcessFactory()
            if process_factory is None
            else process_factory
        )
        self._all_callbacks: list[BrowserCallback] = (
            [] if callback is None else [callback]
        )
        self._event_callbacks: dict[
            BrowserEventType,
            list[BrowserCallback],
        ] = {}
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._process: BrowserProcess | None = None
        self._pid: int | None = None
        self._executable_path: Path | None = None
        self._lock: Lock = Lock()
        self._known_contexts: set[int] = set()
        self._known_pages: set[int] = set()
        self._page_states: dict[int, PageState] = {}
        self._worker: Thread | None = None
        self._stop_requested: Event = Event()
        self._ready: Event = Event()
        self._done: Event = Event()
        self._worker_error: PlaywrightError | None = None

    @property
    def running(self) -> bool:
        """Return whether a background browser worker is active.

        Returns:
            True while a non-blocking browser worker is alive.

        """
        worker: Thread | None = self._worker
        return worker is not None and worker.is_alive()

    @property
    def ready(self) -> bool:
        """Return whether the background browser completed startup.

        Returns:
            True after startup succeeds.

        """
        return self._ready.is_set()

    @property
    def error(self) -> PlaywrightError | None:
        """Return an exception raised by the background worker.

        Returns:
            Worker exception, or None when no asynchronous failure occurred.

        """
        return self._worker_error

    @property
    def browser(self) -> Browser | None:
        """Return the Playwright browser handle.

        Returns:
            The connected browser, or None before launch.

        """
        return self._browser

    @property
    def process(self) -> BrowserProcess | None:
        """Return the native browser process.

        Returns:
            The native process, or None when none is tracked.

        """
        return self._process

    @property
    def executable_path(self) -> Path | None:
        """Return the resolved native browser executable.

        Returns:
            Resolved executable path, or None when not using native Chrome.

        """
        return self._executable_path

    @property
    def pid(self) -> int | None:
        """Return the native process identifier when known.

        Returns:
            The process identifier, or None before launch.

        """
        return self._pid

    def on(self, event: BrowserEventType, callback: BrowserCallback) -> None:
        """Register a callback for one event type.

        Args:
            event: Event type to observe.
            callback: Callback to register.

        """
        callbacks: list[BrowserCallback] = self._event_callbacks.setdefault(
            event,
            [],
        )
        if callback not in callbacks:
            callbacks.append(callback)

    def off(self, event: BrowserEventType, callback: BrowserCallback) -> None:
        """Remove a callback for one event type.

        Args:
            event: Event type whose callback should be removed.
            callback: Callback to remove.

        """
        callbacks: list[BrowserCallback] | None = self._event_callbacks.get(
            event,
        )
        if callbacks is not None and callback in callbacks:
            callbacks.remove(callback)
            if not callbacks:
                del self._event_callbacks[event]

    def on_all(self, callback: BrowserCallback) -> None:
        """Register a callback for every event.

        Args:
            callback: Callback to register.

        """
        if callback not in self._all_callbacks:
            self._all_callbacks.append(callback)

    def off_all(self, callback: BrowserCallback) -> None:
        """Remove a callback registered for every event.

        Args:
            callback: Callback to remove.

        """
        if callback in self._all_callbacks:
            self._all_callbacks.remove(callback)

    def start_playwright(
        self,
        url: str,
        *,
        headless: bool = False,
        executable_path: Path | None = None,
        arguments: Sequence[str] = (),
        no_viewport: bool = False,
    ) -> None:
        """Start Playwright Chromium on a dedicated worker thread.

        This method returns immediately. The worker owns the complete
        Playwright runtime, including event dispatch and shutdown.

        Args:
            url: Initial URL.
            headless: Whether to hide the browser UI.
            executable_path: Optional Chromium/Chrome executable.
            arguments: Extra browser arguments.
            no_viewport: Let pages fill the browser window.

        Raises:
            RuntimeError: When a background worker is already active.

        """
        if self.running:
            msg: str = "A browser worker is already running."
            raise RuntimeError(msg)
        self._stop_requested.clear()
        self._ready.clear()
        self._done.clear()
        self._worker_error = None
        self._worker = Thread(
            target=self._run_playwright_worker,
            kwargs={
                "url": url,
                "headless": headless,
                "executable_path": executable_path,
                "arguments": tuple(arguments),
                "no_viewport": no_viewport,
            },
            name="browser-playwright",
            daemon=True,
        )
        self._worker.start()

    def wait_ready(self, *, timeout: float | None = None) -> bool:
        """Wait until asynchronous Playwright startup succeeds or ends.

        Args:
            timeout: Maximum seconds to wait, or None for no limit.

        Returns:
            True when startup succeeded, otherwise False.

        """
        if self._ready.is_set():
            return True
        if self._done.wait(timeout=timeout):
            return self._ready.is_set()
        return self._ready.wait(timeout=0)

    def wait(self, *, timeout: float | None = None) -> bool:
        """Wait for a background browser worker to finish.

        Args:
            timeout: Maximum seconds to wait, or None for no limit.

        Returns:
            True when the worker finished before the timeout.

        """
        worker: Thread | None = self._worker
        return True if worker is None else self._done.wait(timeout=timeout)

    def launch_playwright(
        self,
        url: str,
        *,
        headless: bool = False,
        executable_path: Path | None = None,
        arguments: Sequence[str] = (),
        no_viewport: bool = False,
    ) -> Browser:
        """Launch Playwright Chromium.

        Args:
            url: Initial URL.
            headless: Whether to hide the browser UI.
            executable_path: Optional Chromium/Chrome executable.
            arguments: Extra browser arguments.
            no_viewport: Let pages fill the window instead of emulating a
                fixed viewport.

        Returns:
            Launched Playwright browser.

        """
        self._backend = BrowserBackend.PLAYWRIGHT
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=headless,
            executable_path=(
                None
                if executable_path is None
                else str(object=executable_path)
            ),
            args=list(arguments),
        )
        self._emit(
            event=BrowserEventType.BROWSER_CONNECTED,
            browser=self._browser,
        )
        self._browser.on(
            event="disconnected",
            f=lambda _: self._emit(
                event=BrowserEventType.BROWSER_DISCONNECTED,
                browser=self._browser,
            ),
        )
        context: BrowserContext = (
            self._browser.new_context(no_viewport=True)
            if no_viewport
            else self._browser.new_context()
        )
        self._register_context(context=context)
        page: Page = context.new_page()
        _ = page.goto(url=url)
        _ = self._update_page_state(page=page)
        return self._browser

    def launch_chrome(
        self,
        url: str,
        *,
        executable: Path | None = None,
        arguments: Sequence[str] = (),
    ) -> BrowserProcess:
        """Launch and monitor an automatically resolved native browser.

        Args:
            url: Initial URL.
            executable: Optional Chrome/Chromium executable override.
            arguments: Extra browser arguments.

        Returns:
            Native process handle.

        """
        self._backend = BrowserBackend.CHROME
        self._executable_path = ChromeLocator.find(executable=executable)
        process: BrowserProcess = self._process_factory(
            command=[str(object=self._executable_path), *arguments, url],
        )
        self._process = process
        self._pid = process.pid
        self._emit(event=BrowserEventType.PROCESS_START)
        Thread(
            target=self._watch_process,
            name=f"browser-{process.pid}",
            daemon=True,
        ).start()
        return process

    def close(self) -> None:
        """Request shutdown and wait for owned resources to be released."""
        worker: Thread | None = self._worker
        if worker is not None and worker.is_alive():
            self._stop_requested.set()
            if worker is not current_thread():
                worker.join()
            return
        self._close_owned_resources()

    def _update_page_state(self, page: Page) -> PageState:
        """Record metadata while a page is known to be alive.

        Args:
            page: Live page whose metadata should be captured.

        Returns:
            Newly recorded immutable page state.

        """
        state: PageState = PageState(
            identity=id(page),
            url=page.url,
            title=page.title(),
        )
        self._page_states[state.identity] = state
        return state

    def _page_state(self, page: Page | None) -> PageState | None:
        """Return the recorded state without touching the page.

        Args:
            page: Page whose state should be returned.

        Returns:
            Last-known state when one exists.

        """
        return None if page is None else self._page_states.get(id(page))

    def _emit(
        self,
        event: BrowserEventType,
        *,
        browser: Browser | None = None,
        context: BrowserContext | None = None,
        page: Page | None = None,
        exit_code: int | None = None,
    ) -> None:
        """Publish a lifecycle event from recorded state only.

        Args:
            event: Event kind.
            browser: Related browser.
            context: Related browser context.
            page: Related page.
            exit_code: Native process exit code.

        """
        state: PageState | None = self._page_state(page=page)
        snapshot: BrowserEvent = BrowserEvent(
            event=event,
            backend=self._backend,
            timestamp=self._clock(),
            pid=self._pid,
            exit_code=exit_code,
            browser=browser,
            context=context,
            page=page,
            page_identity=None if state is None else state.identity,
            url=None if state is None else state.url,
            title=None if state is None else state.title,
        )
        callbacks: tuple[BrowserCallback, ...] = (
            *tuple(self._event_callbacks.get(event, ())),
            *tuple(self._all_callbacks),
        )
        callback: BrowserCallback
        for callback in callbacks:
            callback(event=snapshot)

    def _register_page(self, page: Page, *, context: BrowserContext) -> None:
        """Register one live Playwright page.

        Args:
            page: Page to monitor.
            context: Owning context.

        """
        identity: int = id(page)
        with self._lock:
            if identity in self._known_pages:
                return
            self._known_pages.add(identity)
        _ = self._update_page_state(page=page)
        self._emit(
            event=BrowserEventType.PAGE_OPEN,
            browser=self._browser,
            context=context,
            page=page,
        )
        page.on(
            event="domcontentloaded",
            f=lambda _: self._refresh_page(page=page),
        )
        page.on(event="load", f=lambda _: self._refresh_page(page=page))
        page.on(
            event="framenavigated",
            f=lambda _: self._refresh_page(page=page),
        )
        page.on(
            event="close",
            f=lambda _: self._page_closed(page=page, context=context),
        )
        page.on(
            event="crash",
            f=lambda _: self._page_crashed(page=page, context=context),
        )

    def _refresh_page(self, *, page: Page) -> None:
        """Refresh metadata for a page known to still be alive.

        Args:
            page: Live page whose state should be refreshed.

        """
        _ = self._update_page_state(page=page)

    def _page_crashed(self, *, page: Page, context: BrowserContext) -> None:
        """Publish a crash using the last live metadata snapshot.

        Args:
            page: Crashed page.
            context: Owning context.

        """
        self._emit(
            event=BrowserEventType.PAGE_CRASH,
            browser=self._browser,
            context=context,
            page=page,
        )

    def _page_closed(self, *, page: Page, context: BrowserContext) -> None:
        """Handle closure without interrogating the dead page.

        Args:
            page: Closed page.
            context: Owning context.

        """
        with self._lock:
            self._known_pages.discard(id(page))
        self._emit(
            event=BrowserEventType.PAGE_CLOSE,
            browser=self._browser,
            context=context,
            page=page,
        )

    def _register_context(self, context: BrowserContext) -> None:
        """Register one Playwright browser context.

        Args:
            context: Context to monitor.

        """
        identity: int = id(context)
        with self._lock:
            if identity in self._known_contexts:
                return
            self._known_contexts.add(identity)
        self._emit(
            event=BrowserEventType.CONTEXT_OPEN,
            browser=self._browser,
            context=context,
        )
        context.on(
            event="page",
            f=lambda page: self._register_page(page=page, context=context),
        )
        context.on(
            event="close",
            f=lambda _: self._context_closed(context=context),
        )
        page: Page
        for page in context.pages:
            self._register_page(page=page, context=context)

    def _context_closed(self, *, context: BrowserContext) -> None:
        """Handle context closure.

        Args:
            context: Closed context.

        """
        with self._lock:
            self._known_contexts.discard(id(context))
        self._emit(
            event=BrowserEventType.CONTEXT_CLOSE,
            browser=self._browser,
            context=context,
        )

    def _run_playwright_worker(
        self,
        *,
        url: str,
        headless: bool,
        executable_path: Path | None,
        arguments: Sequence[str],
        no_viewport: bool,
    ) -> None:
        """Own and pump one asynchronous Playwright browser.

        Args:
            url: Initial URL.
            headless: Whether to hide the browser UI.
            executable_path: Optional Chromium/Chrome executable.
            arguments: Extra browser arguments.
            no_viewport: Let pages fill the browser window.

        Raises:
            Error: When the page pump fails while the browser is
                connected.

        """
        try:
            browser: Browser = self.launch_playwright(
                url=url,
                headless=headless,
                executable_path=executable_path,
                arguments=arguments,
                no_viewport=no_viewport,
            )
            self._ready.set()
            while not self._stop_requested.is_set() and browser.is_connected():
                pages: list[Page] = [
                    page
                    for context in browser.contexts
                    for page in context.pages
                    if not page.is_closed()
                ]
                if not pages:
                    break
                try:
                    pages[0].wait_for_timeout(timeout=100)
                except PlaywrightError:
                    if browser.is_connected():
                        raise
        except PlaywrightError as error:
            self._worker_error = error
        finally:
            self._close_owned_resources()
            self._done.set()

    def _watch_process(self) -> None:
        """Wait for native process termination and publish its exit."""
        process: BrowserProcess | None = self._process
        if process is not None:
            self._emit(
                event=BrowserEventType.PROCESS_EXIT,
                exit_code=process.wait(),
            )

    def _close_owned_resources(self) -> None:
        """Close resources from their owning thread."""
        if self._browser is not None:
            if self._browser.is_connected():
                self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
