# widget_styles/

Shared CSS kit for widgets. Prefix `--ws-`. Generic roles only: surfaces, text, borders, focus ring, status colours, control height, radii, spacing and type scales, motion durations, light and dark value sets (`[data-theme]` or the system preference) and a forced-colors mapping.

Rules: no token names a widget; widgets add their own alias tier (for example `--ese-*`) built from single `var(--ws-…)` references and never redefine a `--ws-*` token.

Use: `<link rel="stylesheet" href="…/widget_styles/style.css">` then your widget stylesheet.

## How the kit is organised

The kit is the shared token hierarchy for widgets, split into three tiers that are imported in order by `style.css`:

1. **PRIMARY** (`primary.css`) — literal inputs only: units, keywords, named colours and the widget palette. No `var()` and no functions.
2. **BASE** (`base.css`) — reusable derived values built from PRIMARY: theme role colours, measures, typography units and keyword bridges. Both theme value sets (light and dark) are declared here.
3. **CATALOG** (`catalog.css`) — generic design specifications assembled from BASE, such as control, field and surface treatments. They name no concrete widget.

A consuming widget adds a fourth, **alias** tier of its own: custom properties that each resolve to exactly one `var(--ws-…)` reference, and component rules that read only those aliases. A widget never redefines a `--ws-*` token, and the kit never names a widget.

## Theming and accessibility

- Dark is the default theme. Light applies for `[data-theme="light"]` or, when the document sets no `data-theme`, for `prefers-color-scheme: light`; `[data-theme="dark"]` forces dark.
- Under `forced-colors: active`, the role colours map onto system colours so controls, focus rings and borders stay visible.
- The themes are value sets declared in `base.css`, so a widget switches theme by changing one attribute and never by redefining tokens.

## Using the kit

```html
<link rel="stylesheet" href="/packages/widgets/widget_styles/style.css" />
<link rel="stylesheet" href="/packages/widgets/widget_selector/style.css" />
```

`widget_selector/style.css` itself imports the kit, so a page that mounts that widget needs only its own stylesheet. A page that builds another widget imports `style.css` first and then its own alias tier.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `base.css` | BASE — reusable derived values: theme role colors, measures, typography units and keyword bridges. |
| `catalog.css` | CATALOG — generic design specifications shared by widget consumers. |
| `primary.css` | PRIMARY — literal inputs: units, keywords, named colors and the widget palette. |
| `style.css` | Entry stylesheet that imports `./primary.css`, `./base.css`, `./catalog.css`. |

## Stylesheets

- `base.css` — BASE — reusable derived values: theme role colors, measures, typography units and keyword bridges. (81 custom properties)
- `catalog.css` — CATALOG — generic design specifications shared by widget consumers. (95 custom properties)
- `primary.css` — PRIMARY — literal inputs: units, keywords, named colors and the widget palette. (61 custom properties)
- `style.css` — Entry stylesheet: imports `./primary.css`, `./base.css`, `./catalog.css`. (rules only)

## Dependencies and consumers

- No dependencies outside the standard library.
- Used by: `packages/widgets/widget_selector/examples/web/index.html`, `packages/widgets/widget_selector/style.css`

<!-- exactus:reference:end -->
