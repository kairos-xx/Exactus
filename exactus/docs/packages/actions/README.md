# `actions/`

Action packages hold the interactive editors behind authored flow actions: a shared pointer and touch frontend, a JavaScript snippet runner, and a REST/WebSocket request studio. `action_javascript` is self-rendering and mounts on a carrier element; `action_rest` binds to the DOM contract of its host page.

<!-- exactus:inventory:start -->
## Directory contents

### Files

No direct files besides this README.

### Subdirectories

- [`action_javascript/`](action_javascript/README.md) — Reusable, self-rendering **JavaScript snippet runner**: write a snippet, run it in a sandbox, and read what it **returned**, what it **logged**, and **where it failed** — without leaving the action form. It embeds `widget_console` for output and shares its visual language.
- [`action_pointer/`](action_pointer/README.md) — Documentation for the shared mouse, coordinate-pointer, and touch action frontend.
- [`action_rest/`](action_rest/README.md) — Reusable browser request-studio controller with a standalone browser demo. `request_studio.js` contains the `RequestStudio` class and `index.js` is the named/default ES-module entry point. The package supports HTTP and WebSocket request workflows, variables, query parameters, headers, cookies, body editing, response inspection, and response-value capture.

<!-- exactus:inventory:end -->

## Packages

| Package | Description |
|---|---|
| [`action_pointer`](action_pointer/DOCS.md) | Shared mouse, coordinate-pointer, and touch action frontend |
| [`action_javascript`](action_javascript/DOCS.md) | Reusable, self-rendering JavaScript snippet runner |
| [`action_rest`](action_rest/DOCS.md) | Reusable browser request-studio controller with a standalone browser demo. |

## How they fit together

- `action_javascript` mounts [`widget_console`](../widgets/widget_console/DOCS.md) for its output and shares its visual language; Studio mounts it through `mountRunner` for the JavaScript action.
- `action_rest` is a standalone request studio for HTTP and WebSocket requests (the `RequestStudio` controller). Studio's own REST and WebSocket action settings adapt its request line and tabs in `request-action-widget.js`.

## Conventions

- Source lives in `exactus/packages/actions/<name>/`, tests in `exactus/tests/packages/actions/<name>/` and documentation in `exactus/docs/packages/actions/<name>/DOCS.md`.
- Python import path is `exactus.packages.actions.<name>`; browser path is `/packages/actions/<name>/`.
- Each package has a runnable demo: `python -m exactus.packages.actions.<name>.examples`, or run every demo with `python -m exactus.packages`.
