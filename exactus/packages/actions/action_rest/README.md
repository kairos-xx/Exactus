# REST action / Request Studio

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

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Package the reusable JavaScript request studio and its browser demo.
- [`index.js`](index.js) — Provide index js content.
- [`request_studio.js`](request_studio.js) — Provide request studio js content.

### Subdirectories

- [`examples/`](examples/README.md) — Runnable browser demonstration of the reusable request studio.

<!-- exactus:inventory:end -->
