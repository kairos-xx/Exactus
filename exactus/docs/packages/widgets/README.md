# `widgets/`

Widgets are self-rendering browser components that Studio and ordinary pages mount. Each ships its own ES modules, a token-driven stylesheet and a runnable demo, and none depends on Studio.

<!-- exactus:inventory:start -->
## Directory contents

### Files

No direct files besides this README.

### Subdirectories

- [`widget_clock/`](widget_clock/README.md) — Documentation for \[`exactus/packages/widgets/widget_clock/`\](../../../packages/widgets/widget_clock).
- [`widget_console/`](widget_console/README.md) — Reusable, self-rendering **console widget**: a filterable, searchable message list that shows values the way a developer console does — expandable objects, maps, sets, errors with stacks, `console.table`, groups, repeat counters, and per-level tinting — in the same visual language as `extended_selector` and `action_rest`.
- [`widget_selector/`](widget_selector/README.md) — The **selector expression widget**: a structured editor that edits an ExtendedSelector expression as nested pills (the *Expression* view) or as plain text (the *Text* view), with live validation, suggestions, a variable mention menu and Pick / Highlight / match-statistics tools in its footer.
- [`widget_styles/`](widget_styles/README.md) — Shared CSS kit for widgets. Prefix `--ws-`. Generic roles only: surfaces, text, borders, focus ring, status colours, control height, radii, spacing and type scales, motion durations, light and dark value sets (`\[data-theme\]` or the system preference) and a forced-colors mapping.

<!-- exactus:inventory:end -->

## Packages

| Package | Description |
|---|---|
| [`widget_clock`](widget_clock/DOCS.md) | exactus.packages.widgets.widget_clock is a reusable browser widget package. |
| [`widget_console`](widget_console/DOCS.md) | Reusable, self-rendering console widget |
| [`widget_selector`](widget_selector/DOCS.md) | The selector expression widget |
| [`widget_styles`](widget_styles/DOCS.md) | Shared CSS kit for widgets. |

## How they fit together

- `widget_styles` is the shared token kit. `widget_selector` builds its alias tier on top of it and never redefines a `--ws-*` token.
- `widget_selector` edits ExtendedSelector expressions; the engine itself stays in [`extended_selector`](../extended_selector/DOCS.md) and is passed to the widget as an option.
- `widget_console` and `widget_clock` are standalone; `widget_console` is also embedded by [`action_javascript`](../actions/action_javascript/DOCS.md).

## Conventions

- Source lives in `exactus/packages/widgets/<name>/`, tests in `exactus/tests/packages/widgets/<name>/` and documentation in `exactus/docs/packages/widgets/<name>/DOCS.md`.
- Python import path is `exactus.packages.widgets.<name>`; browser path is `/packages/widgets/<name>/`.
- Each package has a runnable demo: `python -m exactus.packages.widgets.<name>.examples`, or run every demo with `python -m exactus.packages`.
