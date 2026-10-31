# widget_selector/

The **selector expression widget**: a structured editor that edits an
ExtendedSelector expression as nested pills (the *Expression* view) or as plain
text (the *Text* view), with live validation, suggestions, a variable mention
menu and Pick / Highlight / match-statistics tools in its footer.

It is self-rendering and mounted on a text carrier that keeps the stored value,
so any form that already posts a `<textarea>` or `<input>` gains the widget
without changing its markup. The selector **engine** (parser, linter and query
evaluation) is *not* part of this package: it lives in
[`extended_selector/`](../../extended_selector/DOCS.md) and is handed to the
widget as an option.

```html
<link rel="stylesheet" href="/packages/widgets/widget_selector/style.css" />
<textarea name="selector"></textarea>
```

```js
import ExtendedSelector from "/packages/extended_selector/editor/extended-selector.js";
import { mountExpressionWidget } from "/packages/widgets/widget_selector/index.js";

const carrier = document.querySelector('textarea[name="selector"]');
const widget = mountExpressionWidget(carrier, {
  engine: new ExtendedSelector(document),
  label: "Expression",
  host: { /* pick(), highlight(), stats() against the page being tested */ },
});
widget.setMode("text");
```

Studio uses the widget through the compatibility wrapper
`extended-selector-editor.js`, whose contract its selector field already
relied on.

Run the demo with `python exactus/packages/widgets/widget_selector/examples` or
`python -m exactus.packages.widgets.widget_selector.examples`.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Package the selector expression widget for the Studio web server. |
| `examples/` | Demo harness for the selector expression widget. |
| `expression-view.js` | The Expression view: shapes plus one inline draft input at the caret. |
| `extended-selector-editor.js` | Compatibility wrapper with the contract Studio's field already uses. |
| `footer.js` | Footer: pick, highlight, stats chips, stats panel and the pick result. |
| `icons.js` | Inline SVG icons (one 24-unit grid, stroked). |
| `index.js` | Public entry of the expression widget. |
| `mention-menu.js` | A suggestion menu with expandable branches, like action_rest's `@` list. |
| `selector-tree.js` | Flat token model of an ExtendedSelector expression. |
| `shapes.js` | Pill shapes from the pills.svg design sheet at 20px: open, leaf, closing cap, slot. |
| `style.css` | Entry stylesheet that imports `../widget_styles/style.css`, `./styles/primary.css`, `./styles/base.css`, `./styles/catalog.css`, `./styles/semantic.css`, `./styles/components/widget.css`. |
| `styles/` | No direct files besides this README. |
| `suggest.js` | Context-aware suggestions for the selector language. |
| `text-view.js` | The Text view: a plain textarea with a colour overlay and problem underlines. |
| `validator.js` | Debounced validation with states, counts and problem stepping. |
| `widget.js` | The widget shell: header, semaphore, mode toggle, field, message row, footer slot. |

## JavaScript API reference

Exports of the package's ES modules, read from the source.

### `expression-view.js`

The Expression view: shapes plus one inline draft input at the caret.

- `const createExpressionView` — Create the view.

### `extended-selector-editor.js`

Compatibility wrapper with the contract Studio's field already uses.

- `class ExtendedSelectorEditor` — Compatibility wrapper with the contract Studio's field already uses.
  - `get value()`
  - `set value(next)`
  - `setEngine(engine)`

### `footer.js`

Footer: pick, highlight, stats chips, stats panel and the pick result.

- `const createFooter` — Build the footer row, stats panel and pick list.

### `icons.js`

Inline SVG icons (one 24-unit grid, stroked).

- `icon(name, always = false)` — Build an inline SVG icon.

### `index.js`

Public entry of the expression widget.

- `mountExpressionWidget(carrier, options)` — Mount the widget on a carrier element that keeps the stored value.

### `mention-menu.js`

A suggestion menu with expandable branches, like action_rest's `@` list.

- `const createMenu` — Create the suggestion menu bound to a host element.

### `selector-tree.js`

Flat token model of an ExtendedSelector expression.

- `const variableKind` — Which family a variable path belongs to.
- `const tokenize` — Cut an expression into tokens.
- `const serialize` — Rebuild the text a token sequence stands for.
- `matchingClose(tokens, index)` — Index of the close token matching the open token at `index`, or -1.
- `enclosing(tokens, caret)` — The open token enclosing a text offset and which argument the offset is in.
- `slotsOf(tokens, signatures)` — Required arguments still missing, to draw as dashed slots before the close.

### `shapes.js`

Pill shapes from the pills.svg design sheet at 20px: open, leaf, closing cap, slot.

- `const SHAPE` — The shape's fixed measures, mirrored by the geometry tokens in CSS.
- `const HORN_PATH` — Horns of an open shape: the concave notch is cut between them.
- `const CAP_PATH` — Closing cap: concave on the left, round on the right.
- `joinOf(prev, next)` — How two neighbours join.
- `const buildShape` — Build one shape.

### `suggest.js`

Context-aware suggestions for the selector language.

- `const ENVIRONMENT_VARIABLES` — Environment variables every selector may use (types only; values come from the host).
- `const createSampler` — Count page features under a scope, bounded by `cap` elements and cached.
- `const suggest` — Suggestions for the draft at the caret.

### `text-view.js`

The Text view: a plain textarea with a colour overlay and problem underlines.

- `const createTextView` — Create the plain-text view bound to a host element.

### `validator.js`

Debounced validation with states, counts and problem stepping.

- `const createValidator` — Create a debounced validator around an engine.

### `widget.js`

The widget shell: header, semaphore, mode toggle, field, message row, footer slot.

- `const createWidget` — Create a widget around a carrier element.

## Stylesheets

- `style.css` — Entry stylesheet: imports `../widget_styles/style.css`, `./styles/primary.css`, `./styles/base.css`, `./styles/catalog.css`, `./styles/semantic.css`, `./styles/components/widget.css`. (rules only)
- `styles/base.css` — BASE — derived values for the expression widget: theme-selected kind colors, geometry bridges and the runtime menu position. (56 custom properties)
- `styles/catalog.css` — CATALOG — generic design specifications for the expression-selector widget family. (65 custom properties)
- `styles/components/widget.css` — The expression widget: header, field, shapes, text mode, menu, footer. (2 custom properties)
- `styles/primary.css` — PRIMARY — literal inputs for the expression widget: the syntax kind palette (dark defaults with light variants) and the pill geometry from docs/todo/pills.svg at scale 1. (69 custom properties)
- `styles/semantic.css` — SEMANTIC — contextual aliases for the expression widget. (137 custom properties)

## Examples

Demo harness for the selector expression widget.

Run `python exactus/packages/widgets/widget_selector/examples` (or `python -m
exactus.packages.widgets.widget_selector.examples`) to serve the package over the shared
loopback server and open the demo in the system browser.

- `__init__.py` — package marker so the example can be imported as a module.
- `__main__.py` — run the demo via ``python -m exactus.packages.widgets.widget_selector.examples``.
- `run.py` — serve the demo via `exactus.packages.server` and open a browser.
- `web/` — the demo page and its harness scripts/styles: `index.html` mounts
  the expression widget on a sample page.

Files: `__init__.py`, `__main__.py`, `run.py`, `web/demo-host.js`, `web/demo.css`, `web/demo.js`, `web/index.html`

## Dependencies and consumers

- No dependencies outside the standard library.
- Used by: `tools/record/studio/web/editor.js`, `tools/record/studio/web/styles/style.css`

## Tests

Tests live in `exactus/tests/packages/widgets/widget_selector/`.

- `test_examples.py` — Exercise the bundled widget_selector demo launcher with stubs. (4 tests)
  - `test_start_demo_reuses_an_existing_server`
  - `test_start_demo_spawns_and_waits`
  - `test_start_demo_terminates_a_server_that_never_readies`
  - `test_main_serves_then_opens_and_closes_the_browser`

<!-- exactus:reference:end -->
