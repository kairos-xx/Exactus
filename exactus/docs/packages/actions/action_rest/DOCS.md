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
| `examples/` | Runnable browser demonstration of the reusable request studio. |
| `index.js` | — |
| `request_studio.js` | @typedef {"params" \| "headers" \| "cookies"} RowKind |

## JavaScript API reference

Exports of the package's ES modules, read from the source.

### `request_studio.js`

@typedef {"params" | "headers" | "cookies"} RowKind

- `class RequestStudio` — Interactive request studio: token editors, variables and HTTP/WebSocket transports.

## Examples

Runnable browser demonstration of the reusable request studio.

### Directory contents

### Files

- `__init__.py` — example package marker.
- `__main__.py` — run the example through the project virtual environment.
- `run.py` — start the loopback demo server and open the managed browser.

### Subdirectories

- `web/` — standalone request-studio host page, styles, and demo wiring.

Files: `__init__.py`, `__main__.py`, `run.py`, `web/code.js`, `web/index.html`, `web/style.css`

## Dependencies and consumers

- No dependencies outside the standard library.
- Used by: no other module imports it; it is run directly or through the bundle.

## Tests

Tests live in `exactus/tests/packages/actions/action_rest/`.

- `action_rest.test.mjs` — (5 tests)
  - request API resolves variables, params, headers and package exports
  - request rows, variables, tabs and body modes remain interactive
  - HTTP send builds the request and renders success, error and network responses
  - WebSocket mode maps protocols, logs frames and restores HTTP controls
  - JSON capture saves response values as variables and demo is responsive
- `test_examples.py` — Coverage for the mini postman demo server launcher. (4 tests)
  - `test_start_demo_serves_assets_and_reuses`
  - `test_start_demo_replaces_unready_server`
  - `test_main_prints_url_and_opens_browser`
  - `test_module_entrypoint_invokes_main`

<!-- exactus:reference:end -->
