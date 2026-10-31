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
| `console_view.js` | JavaScript module. |
| `describe.js` | JavaScript module. |
| `examples/` | Runnable demonstration for `exactus/widgets/widget_console/`. |
| `format.js` | JavaScript module. |
| `icons.js` | JavaScript module. |
| `index.js` | JavaScript module. |
| `inspect.js` | JavaScript module. |
| `recorder.js` | JavaScript module. |
| `style.css` | — |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Package the reusable JavaScript console widget and its browser demo.


### `examples/__init__.py`

Runnable browser demonstration of the console widget.


### `examples/__main__.py`

Run the console widget example with the project virtual environment.


### `examples/run.py`

Start the loopback console widget demo and open the managed browser.

- `start_demo(*, log: Path) -> str` — Serve ``packages/`` so the demo can reach sibling widget packages.
- `main() -> int` — Launch the demo; leave its reusable background server running.

## JavaScript API reference

Top-level exports, read from the source.

### `console_view.js`

- `mountConsole`

### `describe.js`

- `Describer`
- `describe`

### `format.js`

- `formatNumber`
- `formatFunction`
- `formatValue`
- `partsText`
- `applyFormat`

### `icons.js`

- `icon`

### `index.js`

- `Describer`
- `describe`
- `applyFormat`
- `formatValue`
- `partsText`
- `icon`
- `renderTable`
- `renderValue`
- `ConsoleRecorder`
- `mountConsole`

### `inspect.js`

- `Inspector`
- `renderValue`
- `renderTable`

### `recorder.js`

- `ConsoleRecorder`

## Examples

Runnable demonstration for `exactus/widgets/widget_console/`.

Start the loopback console widget demo and open the managed browser.

```bash
python -m exactus.widgets.widget_console.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`, `examples/web/README.md`, `examples/web/code.js`, `examples/web/demo.css`, `examples/web/index.html`

## Dependencies and consumers

- Other packages: [`browser`](../../browser/DOCS.md), [`server`](../../server/DOCS.md)
- Used by: `tests/packages/widgets/widget_console/test_examples.py`

## Tests

Tests live in `exactus/tests/packages/widgets/widget_console/`.

- `test_examples.py` — Coverage for the console widget demo server launcher. (6 tests)
  - `test_demo_assets_exist`
  - `test_main_prints_url_and_opens_browser`
  - `test_module_entrypoint_invokes_main`
  - `test_start_demo_replaces_unready_server`
  - `test_start_demo_reuses_a_recorded_server`
  - `test_start_demo_spawns_and_waits`

<!-- exactus:reference:end -->
