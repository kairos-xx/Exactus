# action_javascript/

Reusable, self-rendering **JavaScript snippet runner**: write a snippet, run it in a sandbox, and
read what it **returned**, what it **logged**, and **where it failed** — without leaving the
action form. It embeds `widget_console` for output and shares its visual language.

```html
<link rel="stylesheet" href="/packages/actions/action_javascript/style.css" />   <!-- imports widget_console/style.css -->
<textarea name="payload" hidden></textarea>
```

```js
import { mountRunner } from "./packages/actions/action_javascript/index.js";

const runner = mountRunner(document.querySelector("textarea[name=payload]"), {
  source: "return exactus.vars.get('user/id');",
  outputName: "result",
  variables: [{ name: "user/id", value: "usr_1" }],
});
runner.on("result", ({ status, json, saveAs }) => { /* publish json under saveAs */ });
```

The carrier element keeps the stored snippet (it is hidden, updated on every edit and receives
`input` events), so the widget drops into an ordinary form.

## What a run does

- The snippet runs in a **fresh Worker** per run. `worker.terminate()` ends it at the time limit (1 s – 60 s) or on **Stop**, so endless loops cannot freeze the page. The worker has **no DOM**.
- A single expression is returned automatically (`1 + 2`); a snippet whose last line is an expression returns it (REPL style); otherwise use `return`. Top-level `await` works.
- The sandbox mirrors Studio's runtime contract: `exactus.vars.get/has/set/metadata`, `exactus.project/context/flow/run/action/inputs`, `exactus.log/warn/error/assert`, and the `__EXACTUS_FLOW__` facade (`vars` as a plain object, `id`, `actionId`, `runId`, `log/warn/error/assert`). Page-only members (`exactus.page`, `frame`, `device`, `selectors`, `target`, `targets`, `graph`) throw a clear *only available during playback* error. Reading an unknown value logs a warning.
- The full `console` API is available (`log warn error table group count time assert …`); messages stream into the console with call-site links (`3:9`) that jump to the editor line.
- Results are pinned above the console: the value as an inspectable tree plus its type, a **JSON-safe** flag and the `saved as` name; failures show `Name: message`, a stack, the failing line (highlighted in the gutter) and a jump link.
- Run, Stop, timeout and cancellation are distinct states (`ok | error | timeout | cancelled`).

## Editor

Syntax colouring, line numbers, `Tab` / `Shift+Tab` block indent, auto-indent and brace splitting on `Enter`, `Ctrl/Cmd+/` comment toggle, `Ctrl/Cmd+Enter` to run, native undo, and a values picker that inserts `exactus.vars.get("name")` (secret values are masked).

## Options

| Option | Default | Meaning |
|---|---|---|
| `source` | `""` | Snippet used when the carrier is empty. |
| `label` | `"JavaScript"` | Title and accessible name. |
| `theme` | `null` | `"light"`, `"dark"` or inherit. |
| `timeoutMs` | `5000` | Default time limit (a custom value is added to the dropdown). |
| `mode` | `"auto"` | `"auto"` (REPL-style: the last expression is returned), `"playback"` (compile like a Studio run: one expression, else a function body that must `return`; a returned function is called), `"expression"` or `"statements"`. |
| `variables` | `[]` | `{name, value, secret?, type?}` values for `exactus.vars` (`type` is shown while the value is unknown). |
| `context` | `{}` | Sections `project`, `context`, `flow`, `run`, `action` and `inputs` of `exactus`. |
| `outputName` | unset | Shows the *Save as* field (`name="output_variable"`) when set. |
| `clearOnRun` | `true` | Clear the console before each run. |
| `readOnly` | `false` | Disable editing. |
| `runnable` | `true` | `false` makes an editor-only widget (no Run, result or console) for code that runs in the live page. |
| `name` / `required` | unset | Give the visible editor a form field name and `required`, so it submits with its form without relying on the hidden carrier. |
| `execute` | worker executor | Replacement executor `(request, handlers) => {promise, cancel}`; this is where a host runs the snippet in the real page world instead. |

## API

`mountRunner(carrier, options)` returns `run()`, `stop()`, `getValue()`, `setValue()`, `setVariables()`, `lastResult()`, `outputName()`, `on("run" | "result" | "change", listener)`, `setTheme()`, `destroy()`, plus `editor` and `console` (the embedded `widget_console` API).

## Limits

The default executor is a **preview**: it cannot touch the page, so selector-targeting values such as `exactus.target` belong to the host's `execute` replacement. Un-awaited timers still pending when a run settles are discarded with the worker.

## Demo

```sh
python exactus/packages/actions/action_javascript/examples/run.py
```

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Package the reusable JavaScript snippet runner and its browser demo. |
| `editor.js` | JavaScript module. |
| `examples/` | Runnable demonstration for `exactus/actions/action_javascript/`. |
| `executor.js` | JavaScript module. |
| `highlight.js` | JavaScript module. |
| `index.js` | JavaScript module. |
| `runner_view.js` | JavaScript module. |
| `style.css` | — |
| `variables_menu.js` | JavaScript module. |
| `worker_source.js` | JavaScript module. |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Package the reusable JavaScript snippet runner and its browser demo.


### `examples/__init__.py`

Runnable browser demonstration of the JavaScript runner widget.


### `examples/__main__.py`

Run the runner example with the project virtual environment.


### `examples/run.py`

Start the loopback runner demo and open the managed browser.

- `start_demo(*, log: Path) -> str` — Serve ``packages/`` so the demo can reach sibling widget packages.
- `main() -> int` — Launch the demo; leave its reusable background server running.

## JavaScript API reference

Top-level exports, read from the source.

### `editor.js`

- `createEditor`

### `executor.js`

- `WorkerExecutor`

### `highlight.js`

- `tokenize`
- `tokenizeLines`

### `index.js`

- `createEditor`
- `WorkerExecutor`
- `tokenize`
- `tokenizeLines`
- `buildWorkerSource`
- `mountRunner`

### `runner_view.js`

- `mountRunner`

### `variables_menu.js`

- `createVariablesMenu`

### `worker_source.js`

- `buildWorkerSource`
- `workerMain`

## Examples

Runnable demonstration for `exactus/actions/action_javascript/`.

Start the loopback runner demo and open the managed browser.

```bash
python -m exactus.actions.action_javascript.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`, `examples/web/README.md`, `examples/web/code.js`, `examples/web/demo.css`, `examples/web/index.html`

## Dependencies and consumers

- Other packages: [`browser`](../../browser/DOCS.md), [`server`](../../server/DOCS.md)
- Used by: `tests/packages/actions/action_javascript/test_examples.py`

## Tests

Tests live in `exactus/tests/packages/actions/action_javascript/`.

- `test_examples.py` — Coverage for the JavaScript runner widget demo server launcher. (6 tests)
  - `test_demo_assets_exist`
  - `test_main_prints_url_and_opens_browser`
  - `test_module_entrypoint_invokes_main`
  - `test_start_demo_replaces_unready_server`
  - `test_start_demo_reuses_a_recorded_server`
  - `test_start_demo_spawns_and_waits`

<!-- exactus:reference:end -->
