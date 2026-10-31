[Home](Home.md) > [Packages](Packages.md) > browser

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/browser/`](../exactus/packages/browser/) | [`exactus/tests/packages/browser/`](../exactus/tests/packages/browser/) | [`DOCS.md`](../exactus/docs/packages/browser/DOCS.md) |

[< Packages-argument_parser](Packages-argument_parser.md) · [Packages index](Packages.md) · [Packages-completion >](Packages-completion.md)
