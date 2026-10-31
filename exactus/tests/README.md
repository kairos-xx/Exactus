# tests

Repository-level tests for the toolkit itself. Top-level folders separate
shared infrastructure, tools, reusable packages, bundle behavior, and demos.

Tests follow the toolkit's own strict rules: no bare `assert`, no `Any`,
no suppression comments, keyword-only calls. Outcomes are checked through
the helpers in `support.py`.

JavaScript `node:test` suites live in a `js/` folder beside the Python tests
of the area they exercise (for example `exactus/tests/tools/record/js/`). Browser
assertions share the Playwright harness in `browser.mjs`, which serves the
repository over HTTP and retains Chromium V8 coverage for the exactus gate.
A `loader.mjs` at this level, when present, is the Node import hook the
coverage exactus uses to resolve browser imports. Run them with
`node --test`, after `python -m playwright install chromium`.

- `__init__.py` — makes `tests` a package.
- `browser.mjs` — Shared Playwright harness for browser assertions.
- `conftest.py` — Shared pytest fixtures for the toolkit tests.
- `support.py` — Typed assertion, reflection and fixture helpers shared
  by the test suite.
- `test_support.py` — The shared assertion and reflection helpers fail loudly when violated.
- `tools/` — the `exactus.tools` runtime and one directory per tool.
- `packages/` — independently reusable packages.
- `common/` — shared helpers plus common check and contract suites.
- `bundle/` — packaged-executable freshness and host dispatch.
- `demo/` — the root `demo/` fixture (`test_server.py`, `js/app.test.mjs`).

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Package marker.
- [`conftest.py`](conftest.py) — Shared pytest fixtures for the toolkit tests.

### Subdirectories

- [`bundle/`](bundle/README.md) — Test bundle freshness and packaging helpers.
- [`common/`](common/README.md) — Shared test helpers, pytest fixtures and the Playwright harness.
- [`demo/`](demo/README.md) — Executable tests for the `demo/` fixture, run by the `coverage` exactus.
- [`packages/`](packages/README.md) — Tests for the package multi-use tools.
- [`standalone/`](standalone/README.md) — End-to-end verification that the installed `exactus` executable audits a plain project: `test_standalone.py` runs the system `exactus` (or the built `bin/release/exactus_<system>_<arch>` release binary) over `project/` and checks that `project/EXACTUS_RESULTS/` reports are produced.
- [`tools/`](tools/README.md) — Tests of `exactus/tools`: shared runtime and every tool.

<!-- exactus:inventory:end -->

