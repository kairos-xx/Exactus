# `examples/`

Demo harness for the selector expression widget.

Run `python exactus/packages/widgets/widget_selector/examples` (or `python -m
exactus.packages.widgets.widget_selector.examples`) to serve the package over the shared
loopback server and open the demo in the system browser.

- `__init__.py` — package marker so the example can be imported as a module.
- `__main__.py` — run the demo via ``python -m exactus.packages.widgets.widget_selector.examples``.
- `run.py` — serve the demo via `exactus.packages.server` and open a browser.
- `web/` — the demo page and its harness scripts/styles: `index.html` mounts
  the expression widget on a sample page.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Runnable demonstration for the selector expression widget.
- [`__main__.py`](__main__.py) — Run the widget_selector example with the project virtual environment.
- [`run.py`](run.py) — Serve the expression-widget demo and open the browser.

### Subdirectories

- [`web/`](web/README.md) — Demo page for the selector expression widget: `index.html` mounts the widget on a sample page with width, theme and mode controls. `demo-host.js` implements Pick, Highlight and match statistics against the page itself.

<!-- exactus:inventory:end -->
