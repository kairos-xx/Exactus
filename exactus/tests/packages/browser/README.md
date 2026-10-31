# Tests

Python:

```bash
pytest browser/tests/test_browser.py --cov=browser.lifecycle   --cov-report=term-missing --cov-fail-under=90
```

JavaScript:

```bash
node --experimental-test-coverage --test   browser/tests/browser.test.mjs
```

`test_browser.py` tests lifecycle state and event dispatch without launching a
real GUI. The two JavaScript suites test `examples/web/code.js` without third
party packages.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests for browser lifecycle monitoring.
- [`browser.test.mjs`](browser.test.mjs) — Immutable metadata associated with a browser page lifecycle event.
- [`example-broken.html`](example-broken.html) — Provide example broken html content.
- [`example-fixture.html`](example-fixture.html) — Provide example fixture html content.
- [`example-web.test.mjs`](example-web.test.mjs) — Provide example web.test mjs content.
- [`globals.d.ts`](globals.d.ts) — Provide globals.d ts content.
- [`test_browser.py`](test_browser.py) — Tests for the unified browser lifecycle API.
- [`test_examples.py`](test_examples.py) — Exercise the browser lifecycle example with recorded stubs.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
