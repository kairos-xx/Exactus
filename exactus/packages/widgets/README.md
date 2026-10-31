# `widgets/`

Self-rendering browser widgets that Studio and other pages mount (`widget_clock`, `widget_console`, `widget_selector`, `widget_styles`).

Each member keeps its own README, examples and tests; see `exactus/docs/packages/widgets/DOCS.md` for the full reference.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Self-rendering browser widgets that Studio and other pages mount.

### Subdirectories

- [`widget_clock/`](widget_clock/README.md) — Reusable browser widget: `widget_clock.js` contains the clock class and installs one shared `.sst-*` stylesheet automatically. No external widget CSS is needed. `index.js` is the named/default ES-module entry point. Methods use arrow class fields; pure helpers are static. Constructors and property accessors retain their required native syntax.
- [`widget_console/`](widget_console/README.md) — Reusable, self-rendering **console widget**: a filterable, searchable message list that shows values the way a developer console does — expandable objects, maps, sets, errors with stacks, `console.table`, groups, repeat counters, and per-level tinting — in the same visual language as `extended_selector` and `action_rest`.
- [`widget_selector/`](widget_selector/README.md) — The **selector expression widget**: a structured editor that edits an ExtendedSelector expression as nested pills (the *Expression* view) or as plain text (the *Text* view), with live validation, suggestions, a variable mention menu and Pick / Highlight / match-statistics tools in its footer.
- [`widget_styles/`](widget_styles/README.md) — Shared CSS kit for widgets. Prefix `--ws-`. Generic roles only: surfaces, text, borders, focus ring, status colours, control height, radii, spacing and type scales, motion durations, light and dark value sets (`\[data-theme\]` or the system preference) and a forced-colors mapping.

<!-- exactus:inventory:end -->
