# widget_console/

Reusable, self-rendering **console widget**: a filterable, searchable message list that
shows values the way a developer console does — expandable objects, maps, sets, errors with
stacks, `console.table`, groups, repeat counters, and per-level tinting — in the same visual
language as `extended_selector` and `action_rest`.

```html
<link rel="stylesheet" href="/packages/widgets/widget_console/style.css" />
```

```js
import { mountConsole } from "./packages/widgets/widget_console/index.js";

const view = mountConsole(document.querySelector("#host"), { label: "Console" });
view.log("info", "ready", { user: { id: 7 } });   // describes live values
view.console.table([{ a: 1 }, { a: 2 }]);          // a console-like object feeding the widget
const release = view.capture();                    // mirror the page console + uncaught errors
```

The widget fills its host (`block-size: 100%`, bounded by `--size-console-max`), so give the
host a height when you want the list to scroll inside a fixed area.

## Options

| Option | Default | Meaning |
|---|---|---|
| `label` | `"Console"` | Title and accessible name. |
| `theme` | `null` | `"light"`, `"dark"`, or `null` to inherit `data-theme` / the system preference. |
| `maxEntries` | `1000` | Rows kept; older rows are dropped and a notice appears. |
| `timestamps` | `false` | Show a `HH:MM:SS.mmm` column. |
| `search` | `true` | Show the filter row (text search and level dropdown). |
| `emptyText` | `"No messages yet."` | Text shown while there are no rows. |

## API

`mountConsole(host, options)` returns:

- `append(entry)` — add an entry (`{level, kind, parts, time, depth, source}`); consecutive identical messages fold into a `×n` badge.
- `log(level, ...values)` — describe live values and append them.
- `console` — console-like methods (`log info warn error debug trace assert count time group table dir clear …`) backed by `ConsoleRecorder`.
- `capture(source?, window?)` — mirror a console and uncaught errors / unhandled rejections; returns a restore function.
- `clear()`, `setFilter(level)`, `setQuery(text)`, `setTimestamps(on)`, `text()`, `counts()`, `entries()`, `setTheme(value)`, `destroy()`.
- `on("change" | "source" | "copy", listener)` — `source` fires with `{line, column}` when a message's call-site link is clicked.

## Data contracts

- **Descriptor** — a structured-clone-safe tree produced by `Describer.describe(value)`: primitives, functions, accessors (never invoked), and objects classified as `object | array | map | set | date | regexp | error | typed | buffer | promise | node | boxed | weak`, with cycle markers and depth / entry / text / node limits. Descriptors cross `postMessage`, which is how the sandbox runner sends values back.
- **`Describer` and `ConsoleRecorder` are self-contained** — their source is embedded verbatim in sandbox workers, so they reference nothing outside themselves.

## Styling

`style.css` follows the project token hierarchy (PRIMARY → BASE → CATALOG → SEMANTIC); components
consume only semantic aliases. It carries dark and light value sets and responds to
`[data-theme]`, `prefers-color-scheme`, `pointer: coarse` (44 px targets), reduced motion and
forced colors. The widget is a size container, so it adapts to its own width.

## Demo

```sh
python exactus/packages/widgets/widget_console/examples/run.py
```

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Package the reusable JavaScript console widget and its browser demo. |
| `console_view.js` | The console widget: a filterable, searchable message list with inspectable values. |
| `describe.js` | Describe any JavaScript value as a structured-clone-safe tree. |
| `examples/` | Runnable browser demonstration of the console widget. |
| `format.js` | Text rendering of value descriptors: previews, plain text and printf-style substitution. |
| `icons.js` | Inline SVG icons (one 24-unit grid, stroked), shared by the console and runner widgets. |
| `index.js` | Public entry of the console widget. |
| `inspect.js` | DOM rendering of value descriptors as inline, expandable inspector trees. |
| `recorder.js` | Console method semantics (groups, counters, timers, tables) feeding any entry sink. |
| `style.css` | widget_console: PRIMARY literals -> BASE derivations -> CATALOG specifications -> SEMANTIC aliases (single reference each), then components. |

## JavaScript API reference

Exports of the package's ES modules, read from the source.

### `console_view.js`

The console widget: a filterable, searchable message list with inspectable values.

- `const mountConsole` — Mount a console widget in a host element.

### `describe.js`

Describe any JavaScript value as a structured-clone-safe tree.

- `class Describer` — Describe JavaScript values as structured-clone-safe descriptor trees.
  - `static describe(value, limits = {})`
  - `static walk(value, depth, path, limits)`
  - `static summary(value, kind, cls, size)`
  - `static object(value, depth, path, limits)`
  - `static members(value, kind, depth, path, limits)`
- `const describe`

### `format.js`

Text rendering of value descriptors: previews, plain text and printf-style substitution.

- `const formatNumber` — Format a number with its sign of zero preserved.
- `const formatFunction` — Format a function descriptor.
- `const formatValue` — Format any descriptor as one line of text.
- `const partsText` — Format descriptors the way a console line reads in plain text.
- `const applyFormat` — Apply printf-style substitutions to the first message part.

### `icons.js`

Inline SVG icons (one 24-unit grid, stroked), shared by the console and runner widgets.

- `const icon` — Build an inline SVG icon.

### `index.js`

Public entry of the console widget.

### `inspect.js`

DOM rendering of value descriptors as inline, expandable inspector trees.

- `class Inspector` — Render value descriptors as inline, expandable inspector trees.
  - `static leaf(type, text)`
  - `static wire(box, head, button, build)`
  - `static member(entry, kind)`
  - `static object(descriptor, nested)`
  - `static value(descriptor, nested = false)`
- `const renderValue` — Render any descriptor as an inspector node.
- `const renderTable` — Render `console.table` output, or fall back to the plain value.

### `recorder.js`

Console method semantics (groups, counters, timers, tables) feeding any entry sink.

- `class ConsoleRecorder` — Record console calls as console entries for a sink.
  - `emit(level, kind, args)`
  - `methods()`
  - `open(labels)`
  - `stamp(label, finish, extra)`

## Stylesheets

- `style.css` — widget_console: PRIMARY literals -> BASE derivations -> CATALOG specifications -> SEMANTIC aliases (single reference each), then components. (276 custom properties)

## Examples

Runnable browser demonstration of the console widget.

Files: `__init__.py`, `__main__.py`, `run.py`, `web/code.js`, `web/demo.css`, `web/index.html`

## Dependencies and consumers

- No dependencies outside the standard library.
- Used by: `packages/actions/action_javascript/executor.js`, `packages/actions/action_javascript/runner_view.js`, `packages/actions/action_javascript/style.css`, `packages/actions/action_javascript/variables_menu.js`, `packages/actions/action_javascript/worker_source.js`, `tests/packages/actions/action_javascript/action_javascript.test.mjs`

## Tests

Tests live in `exactus/tests/packages/widgets/widget_console/`.

- `test_examples.py` — Coverage for the console widget demo server launcher. (6 tests)
  - `test_demo_assets_exist`
  - `test_start_demo_reuses_a_recorded_server`
  - `test_start_demo_spawns_and_waits`
  - `test_start_demo_replaces_unready_server`
  - `test_main_prints_url_and_opens_browser`
  - `test_module_entrypoint_invokes_main`
- `widget_console.test.mjs` — (7 tests)
  - describer, formatter and recorder keep their contracts
  - console widget filters, folds repeats, trims and exposes its text
  - inspector trees expand lazily with accessible toggles
  - capture mirrors the page console and uncaught errors, then restores it
  - demo actions render tables, groups, repeats and keyboard-reachable controls
  - themes and compact widths keep the widget inside its container
  - the theme option recolours one widget without touching the page

<!-- exactus:reference:end -->
