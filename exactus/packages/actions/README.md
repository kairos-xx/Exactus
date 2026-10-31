# `actions/`

Action editors behind authored flow actions: the shared pointer and touch frontend (`action_pointer`), JavaScript snippet runner (`action_javascript`), and REST/WebSocket request studio (`action_rest`).

Each member keeps its own README, examples and tests; see `exactus/docs/packages/actions/DOCS.md` for the full reference.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Action editors for pointer, JavaScript, REST, and WebSocket actions.

### Subdirectories

- [`action_javascript/`](action_javascript/README.md) — Reusable, self-rendering **JavaScript snippet runner**: write a snippet, run it in a sandbox, and read what it **returned**, what it **logged**, and **where it failed** — without leaving the action form. It embeds `widget_console` for output and shares its visual language.
- [`action_pointer/`](action_pointer/README.md) — Reusable pointer-action frontend for Flow Studio. One action selector configures mouse clicks, hover, drag, scrolling, viewport coordinates, taps, long presses, swipes, and pinch gestures while preserving the existing runtime event kinds.
- [`action_rest/`](action_rest/README.md) — Reusable browser request-studio controller with a standalone browser demo. `request_studio.js` contains the `RequestStudio` class and `index.js` is the named/default ES-module entry point. The package supports HTTP and WebSocket request workflows, variables, query parameters, headers, cookies, body editing, response inspection, and response-value capture.

<!-- exactus:inventory:end -->
