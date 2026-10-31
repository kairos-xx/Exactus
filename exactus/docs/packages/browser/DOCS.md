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
| `examples/` | Run the bundled browser demo with Playwright Chromium: ```bash python -m browser.examples |
| `lifecycle.py` | Unified lifecycle monitoring for Playwright Chromium and native Chrome. |
| `session.py` | Open a URL in the managed browser and wait until the user closes it. |

Run it as a module: `python -m exactus.packages.browser`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `url` | Address to display in the browser window. |  |
| `--timeout` | Seconds to wait for the window (default: no limit). | default=None, type=float |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `cli.py`

Open a URL in the managed browser and wait until the user closes it.

- `main() -> int` — Open the given URL and wait for the browser window to close.

### `lifecycle.py`

Unified lifecycle monitoring for Playwright Chromium and native Chrome.

- `class ChromeLocator` — Resolve installed Chrome or Chromium executables portably.
  - `find(executable: Path | None=None) -> Path` — Resolve a usable Chrome or Chromium executable.
- `class BrowserBackend(StrEnum)` — Supported browser backends.
- `class BrowserEventType(StrEnum)` — Lifecycle events emitted by the controller.
- `class BrowserProcess(Protocol)` — Native process operations required by the controller.
  - `pid() -> int` — Return the process identifier.
  - `poll() -> int | None` — Return the exit status when available.
  - `wait() -> int` — Wait for process termination.
  - `terminate() -> None` — Request process termination.
- `class ProcessFactory(Protocol)` — Create native browser processes.
- `class NativeProcessFactory` — Create native browser subprocesses.
- `class PageState` — Last-known metadata for one Playwright page.
  - Fields: `identity: int`, `url: str`, `title: str`
- `class BrowserEvent` — Immutable snapshot describing a lifecycle event.
  - Fields: `event: BrowserEventType`, `backend: BrowserBackend`, `timestamp: datetime`, `pid: int | None`, `exit_code: int | None`, `browser: Browser | None`, `context: BrowserContext | None`, `page: Page | None`, `page_identity: int | None`, `url: str | None`, `title: str | None`
- `class BrowserCallback(Protocol)` — Handle one immutable browser lifecycle event.
- `class BrowserLifecycle` — Launch browsers and publish normalized lifecycle events.
  - `running() -> bool` — Return whether a background browser worker is active.
  - `ready() -> bool` — Return whether the background browser completed startup.
  - `error() -> PlaywrightError | None` — Return an exception raised by the background worker.
  - `browser() -> Browser | None` — Return the Playwright browser handle.
  - `process() -> BrowserProcess | None` — Return the native browser process.
  - `executable_path() -> Path | None` — Return the resolved native browser executable.
  - `pid() -> int | None` — Return the native process identifier when known.
  - `on(event: BrowserEventType, callback: BrowserCallback) -> None` — Register a callback for one event type.
  - `off(event: BrowserEventType, callback: BrowserCallback) -> None` — Remove a callback for one event type.
  - `on_all(callback: BrowserCallback) -> None` — Register a callback for every event.
  - `off_all(callback: BrowserCallback) -> None` — Remove a callback registered for every event.
  - `start_playwright(url: str, *, headless: bool=False, executable_path: Path | None=None, arguments: Sequence[str]=(), no_viewport: bool=False) -> None` — Start Playwright Chromium on a dedicated worker thread.
  - `wait_ready(*, timeout: float | None=None) -> bool` — Wait until asynchronous Playwright startup succeeds or ends.
  - `wait(*, timeout: float | None=None) -> bool` — Wait for a background browser worker to finish.
  - `launch_playwright(url: str, *, headless: bool=False, executable_path: Path | None=None, arguments: Sequence[str]=(), no_viewport: bool=False) -> Browser` — Launch Playwright Chromium.
  - `launch_chrome(url: str, *, executable: Path | None=None, arguments: Sequence[str]=()) -> BrowserProcess` — Launch and monitor an automatically resolved native browser.
  - `close() -> None` — Request shutdown and wait for owned resources to be released.

### `session.py`

Open a URL in the managed browser and wait until the user closes it.

- `class BrowserSession` — A visible browser window owned by the calling script.
  - `open(*, url: str) -> None` — Launch the managed browser on a URL.
  - `wait_closed(*, timeout: float | None=None) -> bool` — Wait for the independently running browser worker to finish.
  - `close() -> None` — Release the browser; safe after the user already closed it.

## Examples

Run the bundled browser demo with Playwright Chromium:

```bash
python -m browser.examples
```

With no URL, the example serves `web/` through the shared loopback server used
by `screenshot`. An existing server for that directory is reused; otherwise the
example starts one, waits until it is ready, and terminates it on exit.

The example starts Playwright on its non-blocking worker, waits five seconds by default, and then explicitly closes and joins that worker. Override
the lifetime with `--duration SECONDS`; use `--duration 0` to wait until the
browser is closed manually.

Open an explicit URL instead of starting the bundled server:

```bash
python -m browser.examples https://example.com
```

Run native Chrome on macOS:

```bash
python -m browser.examples \
  --backend chrome \
  --chrome "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

Every observed lifecycle event is written to stdout with timestamp, backend,
event type, PID, URL, title, and exit status where available.

Files: `__init__.py`, `__main__.py`, `run.py`, `web/code.js`, `web/index.html`, `web/style.css`

## Dependencies and consumers

- Third-party: `playwright`
- Used by: `../pyproject.toml`, `packages/actions/action_javascript/examples/run.py`, `packages/actions/action_rest/examples/run.py`, `packages/extended_selector/examples/run.py`, `packages/performance/api.py`, `packages/performance/session.py`, `packages/widgets/widget_clock/examples/run.py`, `packages/widgets/widget_console/examples/run.py`, `packages/widgets/widget_selector/examples/run.py`, `tools/record/studio/__main__.py`

## Tests

Tests live in `exactus/tests/packages/browser/`.

- `browser.test.mjs` — (3 tests)
  - browser lifecycle events carry independent close metadata
  - multiple lifecycle listeners receive the same event in order
  - removed lifecycle listeners are not called
- `test_browser.py` — Tests for the unified browser lifecycle API. (7 tests)
  - `test_darwin_locator_scans_application_roots`
  - `test_windows_locator_uses_program_files`
  - `test_linux_locator_uses_generic_names`
  - `test_find_rejects_missing_explicit_executable`
  - `test_find_reports_missing_installation`
  - `test_start_playwright_runs_worker_until_pages_close`
  - `test_start_playwright_rejects_a_running_worker`
- `test_examples.py` — Exercise the browser lifecycle example with recorded stubs. (11 tests)
  - `test_parser_defaults_to_the_playwright_backend`
  - `test_run_with_explicit_url_skips_the_demo_server`
  - `test_run_serves_the_bundled_demo_when_no_url`
  - `test_run_rejects_an_unsupported_backend`
  - `test_run_chrome_backend_uses_the_native_wait`
  - `test_event_renderer_prints_a_snapshot`
  - `test_start_demo_reuses_the_recorded_server`
  - `test_wait_native_polls_until_process_exit`
  - `test_main_module_runs_as_a_script`
  - `test_main_module_reports_an_unready_demo`
  - `test_run_ignores_keyboard_interrupt`

<!-- exactus:reference:end -->
