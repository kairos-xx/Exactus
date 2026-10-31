# action_rest/

Reusable browser request-studio controller with a standalone browser demo.
`request_studio.js` contains the `RequestStudio` class and `index.js` is the
named/default ES-module entry point. The package supports HTTP and WebSocket
request workflows, variables, query parameters, headers, cookies, body editing,
response inspection, and response-value capture.

## Studio import

Studio can import the package through its stable module facade:

```js
import { RequestStudio } from "./packages/actions/action_rest/index.js";

const studio = new RequestStudio({
  rows: {
    params: [],
    headers: [],
    cookies: [],
  },
  variables: [],
  url: "https://api.example.com/users",
  body: "",
});
```

`RequestStudio` controls the request-studio DOM contract used by the host page.
Unlike a self-rendering widget, it intentionally binds to the required element
IDs in the host document. The complete reference host markup and styling live
under `examples/web/`.

## Package layout

- `request_studio.js` — reusable request-studio controller.
- `index.js` — stable named/default ES-module facade.
- `examples/` — runnable demo launcher.
- `examples/web/index.html` — complete host DOM contract.
- `examples/web/style.css` — request-studio host/demo styling.
- `examples/web/code.js` — demo seed data and event wiring.

The old `js/` split is intentionally removed: reusable code belongs at package
root, while demo-only code belongs under `examples/web/`, matching the
`widget_clock` package layout.

## Demo

When installed inside Exactus, launch the standalone package server and managed
browser with any supported entry point:

```sh
python exactus/packages/actions/action_rest/examples/run.py
python -m exactus.packages.actions.action_rest.examples
./exactus/packages/actions/action_rest/examples/run.py
```

The launcher serves only this package, reuses an existing package server when
available, and leaves that reusable background server running after the managed
browser closes.

The demo page is:

```text
/packages/actions/action_rest/examples/web/index.html
```

## Directory contents

### Files

- `__init__.py` — Python package marker/documentation.
- `index.js` — JavaScript package facade.
- `request_studio.js` — reusable request-studio implementation.

### Subdirectories

- `examples/` — runnable browser demonstration.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Package the reusable JavaScript request studio and its browser demo. |
| `examples/` | Runnable demonstration for `exactus/actions/action_rest/`. |
| `index.js` | JavaScript module. |
| `request_studio.js` | JavaScript module. |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Package the reusable JavaScript request studio and its browser demo.


### `examples/__init__.py`

Runnable browser demonstration of the reusable request studio.


### `examples/__main__.py`

Run the request-studio example with the project virtual environment.


### `examples/run.py`

Start the loopback request-studio demo and open the managed browser.

- `start_demo(*, log: Path) -> str` — Serve this package only, including the demo's library import.
- `main() -> int` — Launch the demo; leave its reusable background server running.

## JavaScript API reference

Top-level exports, read from the source.

### `request_studio.js`

- `RequestStudio`

## Examples

Runnable demonstration for `exactus/actions/action_rest/`.

Start the loopback request-studio demo and open the managed browser.

```bash
python -m exactus.actions.action_rest.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`, `examples/web/README.md`, `examples/web/code.js`, `examples/web/index.html`, `examples/web/style.css`

## Dependencies and consumers

- Other packages: [`browser`](../../browser/DOCS.md), [`server`](../../server/DOCS.md)
- Used by: `tests/packages/actions/action_rest/test_examples.py`

## Tests

Tests live in `exactus/tests/packages/actions/action_rest/`.

- `test_examples.py` — Coverage for the mini postman demo server launcher. (4 tests)
  - `test_main_prints_url_and_opens_browser`
  - `test_module_entrypoint_invokes_main`
  - `test_start_demo_replaces_unready_server`
  - `test_start_demo_serves_assets_and_reuses`

<!-- exactus:reference:end -->
