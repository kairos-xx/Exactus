# `action_javascript/`

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

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Package the reusable JavaScript snippet runner and its browser demo.
- [`editor.js`](editor.js) — The code editor: a textarea over a highlighted mirror, with a line-number gutter. Ctrl/Cmd+Enter dispatches an `editor-run` event on `element`.
- [`executor.js`](executor.js) — Host side of snippet execution: one disposable Worker per run.
- [`highlight.js`](highlight.js) — A small JavaScript tokenizer for colouring the editor overlay.
- [`index.js`](index.js) — Public entry of the JavaScript runner widget.
- [`runner_view.js`](runner_view.js) — The runner widget: edit a snippet, run it in a sandbox, read the result and console.
- [`style.css`](style.css) — Provide style css content.
- [`variables_menu.js`](variables_menu.js) — A searchable popover that inserts earlier action values into the snippet.
- [`worker_source.js`](worker_source.js) — Source text of the sandbox worker that runs one snippet.

### Subdirectories

- [`examples/`](examples/README.md) — Runnable browser demonstration of the JavaScript runner widget.

<!-- exactus:inventory:end -->
