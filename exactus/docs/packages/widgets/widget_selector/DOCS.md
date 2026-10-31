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
| `examples/` | Runnable demonstration for `exactus/widgets/widget_selector/`. |
| `expression-view.js` | JavaScript module. |
| `extended-selector-editor.js` | JavaScript module. |
| `footer.js` | JavaScript module. |
| `icons.js` | JavaScript module. |
| `index.js` | JavaScript module. |
| `mention-menu.js` | JavaScript module. |
| `selector-tree.js` | JavaScript module. |
| `shapes.js` | JavaScript module. |
| `style.css` | — |
| `styles/` | Subdirectory. |
| `suggest.js` | JavaScript module. |
| `text-view.js` | JavaScript module. |
| `validator.js` | JavaScript module. |
| `widget.js` | JavaScript module. |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Package the selector expression widget for the Studio web server.


### `examples/__init__.py`

Runnable demonstration for the selector expression widget.


### `examples/__main__.py`

Run the widget_selector example with the project virtual environment.


### `examples/run.py`

Serve the expression-widget demo and open the browser.

- `start_demo(*, log: Path) -> str` — Serve ``packages/`` so the demo can reach ``widget_styles/`` too.
- `main() -> int` — Launch the demo; leave its reusable background server running.

## JavaScript API reference

Top-level exports, read from the source.

### `examples/web/demo-host.js`

- `createDemoHost`

### `expression-view.js`

- `createExpressionView`

### `extended-selector-editor.js`

- `ExtendedSelectorEditor`

### `footer.js`

- `createFooter`

### `icons.js`

- `icon`

### `index.js`

- `mountExpressionWidget`

### `mention-menu.js`

- `createMenu`

### `selector-tree.js`

- `variableKind`
- `tokenize`
- `serialize`
- `matchingClose`
- `enclosing`
- `slotsOf`

### `shapes.js`

- `SHAPE`
- `HORN_PATH`
- `CAP_PATH`
- `joinOf`
- `buildShape`

### `suggest.js`

- `ENVIRONMENT_VARIABLES`
- `createSampler`
- `suggest`

### `text-view.js`

- `createTextView`

### `validator.js`

- `createValidator`

### `widget.js`

- `createWidget`

## Examples

Runnable demonstration for `exactus/widgets/widget_selector/`.

Serve the expression-widget demo and open the browser.

```bash
python -m exactus.widgets.widget_selector.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`, `examples/web/README.md`, `examples/web/demo-host.js`, `examples/web/demo.css`, `examples/web/demo.js`, `examples/web/index.html`

## Dependencies and consumers

- Other packages: [`browser`](../../browser/DOCS.md), [`server`](../../server/DOCS.md)
- Used by: `tests/packages/widgets/widget_selector/test_examples.py`

## Tests

Tests live in `exactus/tests/packages/widgets/widget_selector/`.

- `test_examples.py` — Exercise the bundled widget_selector demo launcher with stubs. (4 tests)
  - `test_main_serves_then_opens_and_closes_the_browser`
  - `test_start_demo_reuses_an_existing_server`
  - `test_start_demo_spawns_and_waits`
  - `test_start_demo_terminates_a_server_that_never_readies`

<!-- exactus:reference:end -->
