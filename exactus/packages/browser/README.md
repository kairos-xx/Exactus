# browser

A Python 3.13 package that normalizes browser lifecycle notifications across
Playwright-managed Chromium and a native Chrome/Chromium subprocess.

## Events

`PROCESS_START`, `PROCESS_EXIT`, `BROWSER_CONNECTED`,
`BROWSER_DISCONNECTED`, `CONTEXT_OPEN`, `CONTEXT_CLOSE`, `PAGE_OPEN`,
`PAGE_CLOSE`, and `PAGE_CRASH`.

## Install

```bash
python -m pip install playwright pytest pytest-cov
playwright install chromium
```

## Non-blocking launch

`BrowserLifecycle.start_playwright()` and `BrowserSession.open()` return
immediately. Playwright is created, pumped, and destroyed on one dedicated
worker thread, so the calling script can continue doing unrelated work.

```python
from exactus.packages.browser.lifecycle import BrowserLifecycle

lifecycle = BrowserLifecycle()
lifecycle.start_playwright(url="https://example.com")
# The calling thread continues immediately.
# ...other work...
lifecycle.close()
```

Use `wait_ready(timeout=...)` when work depends on successful startup, `wait()`
when a caller intentionally wants to join the browser lifetime, and `error` to
inspect asynchronous startup/runtime failures. `launch_playwright()` remains
the explicit synchronous API for callers that need direct Playwright handles.

## Example

```bash
python -m browser.examples --backend playwright --url https://example.com
python -m browser.examples --backend chrome --chrome "/path/to/chrome"
```

See [DOCS.md](DOCS.md) for the API and `examples/README.md` for demonstrations.

## Tests and coverage

```bash
pytest browser/tests/test_browser.py --cov=browser --cov-report=term-missing --cov-fail-under=90
node --experimental-test-coverage --test browser/tests/browser.test.mjs
```

The JavaScript suite is intentionally dependency-free and exercises the
browser-side example logic with Node's built-in test runner.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Unified browser lifecycle monitoring.
- [`__main__.py`](__main__.py) — Open a URL in the managed browser and wait until the user closes it.
- [`cli.py`](cli.py) — Open a URL in the managed browser and wait until the user closes it.
- [`lifecycle.py`](lifecycle.py) — Unified lifecycle monitoring for Playwright Chromium and native Chrome.
- [`session.py`](session.py) — Open a URL in the managed browser and wait until the user closes it.

### Subdirectories

- [`examples/`](examples/README.md) — Run the bundled browser demo with Playwright Chromium:

<!-- exactus:inventory:end -->

## Native Chrome discovery

The native Chrome backend does not require a hard-coded executable path.
`BrowserLifecycle.launch_chrome(url=...)` resolves Chrome or Chromium from
`PATH` and conventional installation locations on Windows, macOS, and Linux.
An explicit `executable=Path(...)` remains available as a deterministic
override and is validated before launch. The resolved path is available from
`BrowserLifecycle.executable_path`.

The example therefore works without `--chrome` on machines with a standard
Chrome/Chromium installation. `--chrome PATH` only overrides discovery.
