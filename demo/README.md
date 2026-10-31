# Exactus toolkit demo

This fixture exercises the relocatable `exec/exactus` artifact with Python,
JavaScript, CSS, HTML, Python tests, JavaScript tests, browser diagnostics and
server diagnostics.

## Source

- `__init__.py` — makes `demo` a package so tests import `demo.server`.
- `pyproject.toml` — demo-local Ruff/BasedPyright/Pyrefly settings.
- `demo_app/` — the Python package under test.
- `demo_app/logic.py` — local Python source exercised by pytest/coverage.
- `static/` — responsive browser application with two links to the same second
  URL, allowing navigation-URL deduplication to be exercised.
- `server.py` — custom dependency-free entrypoint honoring `EXACTUS_HOST` and
  `EXACTUS_PORT`; `/api/error` intentionally returns HTTP 500.

The Python and JavaScript test suites live in `exactus/tests/demo/`:

- `exactus/tests/demo/test_server.py` — Python tests for the demo logic and every server path (including the 500 endpoint and `main()`).
- `exactus/tests/demo/js/app.test.mjs` — Node `node:test` suite for every `app.js` path, run against a small fake DOM and measured with V8 coverage.

The first `/api/error` request in each server process returns HTTP 500;
subsequent requests return HTTP 200. A lock prevents parallel capture lanes
from emitting the same failure again. That single response produces one HTTP
finding, one browser console error from Chromium, and one captured server
error. Other tools should pass with zero
findings. Restart the demo server to reset the examples.

## Lints and tests through the built executable

From the toolkit project root:

```sh
./exec/exactus --lints demo --read-only --no-install-tools
./exec/exactus --coverage demo
```

## Embedded static server

```sh
./exec/exactus --server demo/static
```

The embedded server is owned by `check`. Its stdout/stderr are captured into
the frontend exactus artifacts. The demo API request is a 404 in this static
mode and is retained as a server warning.

## Custom server entrypoint

```sh
./exec/exactus --entrypoint demo/server.py
```

This runs every exactus tool against the project root while the server is up; add `--frontend-only` for just
the browser capture. `check` assigns a free loopback port through `EXACTUS_HOST`, `EXACTUS_PORT`, `HOST`
and `PORT`, starts the process, continuously captures both stdout and stderr,
and correlates Flask/Werkzeug-, Uvicorn/FastAPI-, and generic quoted HTTP
access-log 4xx/5xx lines into the frontend report. The demo returns HTTP 500,
which participates in FAIL.

## Existing URL

```sh
./exec/exactus --url http://127.0.0.1:8000/
```

No server process is owned in this mode, so only browser console, page,
request, response and WebSocket diagnostics are available.

Every screenshot mode automatically runs desktop, tablet and phone in both
light and dark schemes. Exploration is generic: no project-specific route or
element names are required. Navigations to an already visited URL are skipped,
while visually distinct same-URL UI states remain eligible for capture.

## Subdirectories

- `actions/` — Subdirectory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Exactus toolkit demonstration fixture.
- [`server.py`](server.py) — Serve the demo and expose an intentional HTTP 500 test endpoint.

### Subdirectories

- [`actions/`](actions/README.md) — Provide frontend json content.
- [`demo_app/`](demo_app/README.md) — Local application used by recording, replay, and screenshot demonstrations. See the \[demo guide\](../README.md) for launch instructions.
- [`static/`](static/README.md) — HTML, styles, and scripts served by the demo application. See the \[demo guide\](../README.md).

<!-- exactus:inventory:end -->
