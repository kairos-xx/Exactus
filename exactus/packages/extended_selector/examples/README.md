# `examples/`

Demo harness for the ExtendedSelector structured editor.

Run `python exactus/packages/extended_selector/examples` (or `python -m
exactus.packages.extended_selector.examples`) to serve the package over the shared
loopback server and open the demo in the system browser.

- `__init__.py` — package marker so the example can be imported as a module.
- `__main__.py` — run the demo via ``python -m exactus.packages.extended_selector.examples``.
- `run.py` — serve the demo via `exactus.packages.server` and open a browser.
- `web/` — the demo page and its harness script/styles: `editor.html` exercises
  the structured editor and the element-registration API. The expression-widget
  demo is in `widget_selector/examples/`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Runnable demonstration for the ExtendedSelector structured editor.
- [`__main__.py`](__main__.py) — Run the extended-selector example with the project virtual environment.
- [`run.py`](run.py) — Serve the ExtendedSelector structured-editor demo and open the browser.

### Subdirectories

- [`web/`](web/README.md) — Demo page for the ExtendedSelector structured editor: `editor.html` exercises the editor and the element-registration API. The expression-widget demo moved to `widget_selector/examples/web/`.

<!-- exactus:inventory:end -->
