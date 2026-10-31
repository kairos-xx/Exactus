[Home](Home.md) > [Packages](Packages.md) > widget_selector

# widget_selector/

The **selector expression widget**: a structured editor that edits an
ExtendedSelector expression as nested pills (the *Expression* view) or as plain
text (the *Text* view), with live validation, suggestions, a variable mention
menu and Pick / Highlight / match-statistics tools in its footer.

It is self-rendering and mounted on a text carrier that keeps the stored value,
so any form that already posts a `<textarea>` or `<input>` gains the widget
without changing its markup. The selector **engine** (parser, linter and query
evaluation) is *not* part of this package: it lives in
[`extended_selector/`](Packages-extended_selector.md) and is handed to the
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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/widgets/widget_selector/`](../exactus/packages/widgets/widget_selector/) | [`exactus/tests/packages/widgets/widget_selector/`](../exactus/tests/packages/widgets/widget_selector/) | [`DOCS.md`](../exactus/docs/packages/widgets/widget_selector/DOCS.md) |

[< Packages-widgets-widget_console](Packages-widgets-widget_console.md) · [Packages index](Packages.md) · [Packages-widgets-widget_styles >](Packages-widgets-widget_styles.md)
