# `widget_selector/`

The **selector expression widget**: a structured editor that edits an
ExtendedSelector expression as nested pills (the *Expression* view) or as plain
text (the *Text* view), with live validation, suggestions, a variable mention
menu and Pick / Highlight / match-statistics tools in its footer.

It is self-rendering and mounted on a text carrier that keeps the stored value,
so any form that already posts a `<textarea>` or `<input>` gains the widget
without changing its markup. The selector **engine** (parser, linter and query
evaluation) is *not* part of this package: it lives in
[`extended_selector/`](../../extended_selector/README.md) and is handed to the
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

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Package the selector expression widget for the Studio web server.
- [`expression-view.js`](expression-view.js) — The Expression view: shapes plus one inline draft input at the caret.
- [`extended-selector-editor.js`](extended-selector-editor.js) — Compatibility wrapper with the contract Studio's field already uses.
- [`footer.js`](footer.js) — Footer: pick, highlight, stats chips, stats panel and the pick result.
- [`icons.js`](icons.js) — Inline SVG icons (one 24-unit grid, stroked).
- [`index.js`](index.js) — Public entry of the expression widget.
- [`mention-menu.js`](mention-menu.js) — A suggestion menu with expandable branches, like action_rest's `
- [`selector-tree.js`](selector-tree.js) — Flat token model of an ExtendedSelector expression.
- [`shapes.js`](shapes.js) — Pill shapes from the pills.svg design sheet at 20px: open, leaf, closing cap, slot.
- [`style.css`](style.css) — Provide style css content.
- [`suggest.js`](suggest.js) — Context-aware suggestions for the selector language.
- [`text-view.js`](text-view.js) — The Text view: a plain textarea with a colour overlay and problem underlines.
- [`validator.js`](validator.js) — Debounced validation with states, counts and problem stepping.
- [`widget.js`](widget.js) — The widget shell: header, semaphore, mode toggle, field, message row, footer slot.

### Subdirectories

- [`examples/`](examples/README.md) — Demo harness for the selector expression widget.
- [`styles/`](styles/README.md) — No direct files besides this README.

<!-- exactus:inventory:end -->
