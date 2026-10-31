# Browser lifecycle API

A Python 3.13 package that normalizes browser lifecycle notifications across
Playwright-managed Chromium and a native Chrome/Chromium subprocess.

## `BrowserLifecycle`

`BrowserLifecycle` owns lifecycle observation and callback dispatch.

### Construction

```python
lifecycle = BrowserLifecycle(callback)
```

`callback` receives a frozen `BrowserEvent`. More callbacks may be added with
`on_all(callback)` and removed with `off_all(callback)`.

### `launch_playwright(...)`

Launches Playwright Chromium, registers browser/context/page listeners, creates
one context and one initial page, and navigates to the supplied URL.

The callback can receive browser connection/disconnection, context
open/close, and page open/close/crash events.

### `launch_chrome(...)`

Launches the supplied Chrome/Chromium executable as a native subprocess.
This backend reports `PROCESS_START` and `PROCESS_EXIT` and exposes the PID,
process handle, exit code, and timestamps.

Native Chrome does not expose individual tabs merely because Python owns its
process. For page-level native Chrome observation, launch Chrome with a remote
debugging endpoint and attach a CDP client/Playwright connection.

### `close()`

Closes a connected Playwright browser, stops Playwright, and terminates a
still-running native process.

## `BrowserEvent`

Immutable fields:

- `event`: normalized `BrowserEventType`.
- `backend`: `PLAYWRIGHT` or `CHROME`.
- `timestamp`: timezone-aware UTC event time.
- `pid`: native PID when known.
- `exit_code`: process exit code when applicable.
- `browser`: Playwright browser reference when applicable.
- `context`: Playwright context reference when applicable.
- `page`: Playwright page reference when applicable.
- `url`: safe last-known page URL.
- `title`: safe last-known page title.

## Event semantics

`PAGE_CLOSE` means a Playwright `Page` closed. `CONTEXT_CLOSE` means its
`BrowserContext` closed. `BROWSER_DISCONNECTED` means the Playwright browser
transport disconnected and can cover normal closure, external termination, or
a crash. `PROCESS_EXIT` is an OS-process observation and includes the exit
status.

## Event-specific subscriptions

Callbacks are not limited to the constructor. Multiple callbacks can subscribe
to individual event kinds or to every event:

```python
lifecycle.on(BrowserEventType.PAGE_CLOSE, on_page_close)
lifecycle.on(BrowserEventType.PAGE_CRASH, on_page_crash)
lifecycle.on(BrowserEventType.PROCESS_EXIT, on_process_exit)
lifecycle.on_all(on_every_event)

lifecycle.off(BrowserEventType.PAGE_CLOSE, on_page_close)
lifecycle.off_all(on_every_event)
```

Duplicate registrations in the same subscription group are ignored.
Event-specific callbacks run in registration order before global callbacks.

## Last-known page state

`BrowserLifecycle` maintains an immutable `PageState` snapshot for every
registered Playwright page. Metadata is refreshed while the page is alive on
registration, navigation, DOM-content-loaded, and load events.

Close and crash callbacks read only the registry. They never query a dead page.
Consequently `PAGE_CLOSE` and `PAGE_CRASH` retain the last-known page identity,
URL, and title without broad exception handling around Playwright calls.

`BrowserEvent.page_identity` identifies the recorded page even when its
Playwright handle is no longer usable.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Unified browser lifecycle monitoring. |
| `__main__.py` | Open a URL in the managed browser and wait until the user closes it. |
| `cli.py` | Open a URL in the managed browser and wait until the user closes it. |
| `examples/` | Runnable demonstration for `exactus/packages/browser/`. |
| `lifecycle.py` | Unified lifecycle monitoring for Playwright Chromium and native Chrome. |
| `session.py` | Open a URL in the managed browser and wait until the user closes it. |

Run it as a module: `python -m exactus.packages.browser`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `url` | Address to display in the browser window. |  |
| `--timeout` | Seconds to wait for the window (default: no limit). | type=float, default=None |
| `url` | Page to open (default: the bundled web/ demo). | nargs='?', default=None |
| `--backend` |  | choices=tuple(map(attrgetter('value'), BrowserBackend)), default=BrowserBackend.PLAYWRIGHT.value |
| `--chrome` |  | type=Path |
| `--headless` |  | action='store_true' |
| `--duration` | Seconds to keep the browser alive (default: %(default)s; 0 waits until exit). | type=float, default=Constants.duration |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Unified browser lifecycle monitoring.


### `__main__.py`

Open a URL in the managed browser and wait until the user closes it.


### `cli.py`

Open a URL in the managed browser and wait until the user closes it.

- `main() -> int` — Open the given URL and wait for the browser window to close.

### `examples/__init__.py`

Runnable examples for the browser lifecycle package.


### `examples/__main__.py`

Run the browser example with the project virtual environment.


### `examples/run.py`

Interactive browser lifecycle demonstration.

- `class Constants` — Group module-level constants.
  - `duration` = `5.0`
- `class Example` — Run the lifecycle demonstration.
  - `run(cls, arguments: Namespace) -> None` — Run the browser example and release every owned resource.
  - `parser() -> ArgumentParser` — Build the example argument parser.
- `main() -> None` — Run the command-line example.

### `lifecycle.py`

Unified lifecycle monitoring for Playwright Chromium and native Chrome.

- `class ChromeLocator` — Resolve installed Chrome or Chromium executables portably.
  - `find(cls, executable: Path | None=None) -> Path` — Resolve a usable Chrome or Chromium executable.
- `class BrowserBackend` — Supported browser backends.
  - `PLAYWRIGHT` = `'playwright'`
  - `CHROME` = `'chrome'`
- `class BrowserEventType` — Lifecycle events emitted by the controller.
  - `PROCESS_START` = `'process_start'`
  - `PROCESS_EXIT` = `'process_exit'`
  - `BROWSER_CONNECTED` = `'browser_connected'`
  - `BROWSER_DISCONNECTED` = `'browser_disconnected'`
  - `CONTEXT_OPEN` = `'context_open'`
  - `CONTEXT_CLOSE` = `'context_close'`
  - `PAGE_OPEN` = `'page_open'`
  - `PAGE_CLOSE` = `'page_close'`
  - `PAGE_CRASH` = `'page_crash'`
- `class BrowserProcess(Protocol)` — Native process operations required by the controller.
  - `pid(self) -> int` — Return the process identifier.
  - `poll(self) -> int | None` — Return the exit status when available.
  - `wait(self) -> int` — Wait for process termination.
  - `terminate(self) -> None` — Request process termination.
- `class ProcessFactory(Protocol)` — Create native browser processes.
- `class NativeProcessFactory` — Create native browser subprocesses.
- `class PageState` — Last-known metadata for one Playwright page.
  - Fields: `identity: int`, `url: str`, `title: str`
- `class BrowserEvent` — Immutable snapshot describing a lifecycle event.
  - Fields: `event: BrowserEventType`, `backend: BrowserBackend`, `timestamp: datetime`, `pid: int | None`, `exit_code: int | None`, `browser: Browser | None`, `context: BrowserContext | None`, `page: Page | None`, `page_identity: int | None`, `url: str | None`, `title: str | None`
- `class BrowserCallback(Protocol)` — Handle one immutable browser lifecycle event.
- `class BrowserLifecycle` — Launch browsers and publish normalized lifecycle events.
  - `__init__(self, callback: BrowserCallback | None=None, *, clock: Clock | None=None, process_factory: ProcessFactory | None=None) -> None` — Initialize an idle lifecycle controller.
  - `running(self) -> bool` — Return whether a background browser worker is active.
  - `ready(self) -> bool` — Return whether the background browser completed startup.
  - `error(self) -> PlaywrightError | None` — Return an exception raised by the background worker.
  - `browser(self) -> Browser | None` — Return the Playwright browser handle.
  - `process(self) -> BrowserProcess | None` — Return the native browser process.
  - `executable_path(self) -> Path | None` — Return the resolved native browser executable.
  - `pid(self) -> int | None` — Return the native process identifier when known.
  - `on(self, event: BrowserEventType, callback: BrowserCallback) -> None` — Register a callback for one event type.
  - `off(self, event: BrowserEventType, callback: BrowserCallback) -> None` — Remove a callback for one event type.
  - `on_all(self, callback: BrowserCallback) -> None` — Register a callback for every event.
  - `off_all(self, callback: BrowserCallback) -> None` — Remove a callback registered for every event.
  - `start_playwright(self, url: str, *, headless: bool=False, executable_path: Path | None=None, arguments: Sequence[str]=(), no_viewport: bool=False) -> None` — Start Playwright Chromium on a dedicated worker thread.
  - `wait_ready(self, *, timeout: float | None=None) -> bool` — Wait until asynchronous Playwright startup succeeds or ends.
  - `wait(self, *, timeout: float | None=None) -> bool` — Wait for a background browser worker to finish.
  - `launch_playwright(self, url: str, *, headless: bool=False, executable_path: Path | None=None, arguments: Sequence[str]=(), no_viewport: bool=False) -> Browser` — Launch Playwright Chromium.
  - `launch_chrome(self, url: str, *, executable: Path | None=None, arguments: Sequence[str]=()) -> BrowserProcess` — Launch and monitor an automatically resolved native browser.
  - `close(self) -> None` — Request shutdown and wait for owned resources to be released.

### `session.py`

Open a URL in the managed browser and wait until the user closes it.

- `class BrowserSession` — A visible browser window owned by the calling script.
  - `__init__(self) -> None` — Create an idle session; no browser exists until ``open``.
  - `open(self, *, url: str) -> None` — Launch the managed browser on a URL.
  - `wait_closed(self, *, timeout: float | None=None) -> bool` — Wait for the independently running browser worker to finish.
  - `close(self) -> None` — Release the browser; safe after the user already closed it.

## Examples

Runnable demonstration for `exactus/packages/browser/`.

Interactive browser lifecycle demonstration.

```bash
python -m exactus.packages.browser.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`, `examples/web/README.md`, `examples/web/code.js`, `examples/web/index.html`, `examples/web/style.css`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md), [`server`](../server/DOCS.md)
- Used by: `packages/actions/action_javascript/examples/run.py`, `packages/actions/action_pointer/examples/run.py`, `packages/actions/action_rest/examples/run.py`, `packages/extended_selector/examples/run.py`, `packages/performance/session.py`, `packages/widgets/widget_clock/examples/run.py`, `packages/widgets/widget_console/examples/run.py`, `packages/widgets/widget_selector/examples/run.py`, `tests/packages/browser/test_browser.py`, `tests/packages/browser/test_examples.py`, `tools/record/studio/__main__.py`

## Tests

Tests live in `exactus/tests/packages/browser/`.

- `test_browser.py` — Tests for the unified browser lifecycle API. (11 tests)
  - `test_darwin_locator_scans_application_roots`
  - `test_find_rejects_missing_explicit_executable`
  - `test_find_reports_missing_installation`
  - `test_idle_properties_and_native_termination`
  - `test_linux_locator_uses_generic_names`
  - `test_native_process_events_include_pid_and_exit_code`
  - `test_playwright_events_use_last_live_page_state`
  - `test_start_playwright_rejects_a_running_worker`
  - `test_start_playwright_runs_worker_until_pages_close`
  - `test_subscriptions_are_ordered_and_removable`
  - `test_windows_locator_uses_program_files`
- `test_examples.py` — Exercise the browser lifecycle example with recorded stubs. (11 tests)
  - `test_event_renderer_prints_a_snapshot`
  - `test_main_module_reports_an_unready_demo`
  - `test_main_module_runs_as_a_script`
  - `test_parser_defaults_to_the_playwright_backend`
  - `test_run_chrome_backend_uses_the_native_wait`
  - `test_run_ignores_keyboard_interrupt`
  - `test_run_rejects_an_unsupported_backend`
  - `test_run_serves_the_bundled_demo_when_no_url`
  - `test_run_with_explicit_url_skips_the_demo_server`
  - `test_start_demo_reuses_the_recorded_server`
  - `test_wait_native_polls_until_process_exit`

<!-- exactus:reference:end -->
