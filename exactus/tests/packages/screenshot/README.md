# Tests

Tests of `exactus/screenshot`.

- `__init__.py` — Tests of `exactus/screenshot`.
- `test_capture_support.py` — Image similarity and the high-level screenshot capture API.
- `test_crawler_visit.py` — The visit-plan crawler and the parallel visit replayer.
- `test_flow_studio.py` — Exactus Record interchange, bridge client and live session.
- `test_recorder.py` — Action recording, normalization, compilation and replay.

## Files

- `test_flow_runner.py` — File.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests of `exactus/screenshot`.
- [`test_capture_support.py`](test_capture_support.py) — Image similarity and the high-level screenshot capture API.
- [`test_examples.py`](test_examples.py) — Run the public screenshot example against a live demonstration site.
- [`test_main.py`](test_main.py) — Cover the ``exactus.packages.screenshot`` command-line entry point.

### Subdirectories

- [`js/`](js/README.md) — `node:test` suite for `exactus/packages/screenshot/js/capture_screen.js` viewport expansion and restoration. Browser assertions run through the shared \[`exactus/tests/common/browser.mjs`\](../../../common/browser.mjs) Playwright harness.

<!-- exactus:inventory:end -->

