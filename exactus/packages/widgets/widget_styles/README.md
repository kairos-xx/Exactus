# `widget_styles/`

Shared CSS kit for widgets. Prefix `--ws-`. Generic roles only: surfaces, text, borders, focus ring, status colours, control height, radii, spacing and type scales, motion durations, light and dark value sets (`[data-theme]` or the system preference) and a forced-colors mapping.

Rules: no token names a widget; widgets add their own alias tier (for example `--ese-*`) built from single `var(--ws-…)` references and never redefine a `--ws-*` token.

Use: `<link rel="stylesheet" href="…/widget_styles/style.css">` then your widget stylesheet.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Package the shared ``--ws-*`` stylesheet kit for browser widgets.
- [`base.css`](base.css) — Provide base css content.
- [`catalog.css`](catalog.css) — Provide catalog css content.
- [`primary.css`](primary.css) — Provide primary css content.
- [`style.css`](style.css) — Provide style css content.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
