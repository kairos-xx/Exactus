# `examples/`

Runnable demo for the CSS visual cause analyzer.

- `__init__.py` — package marker so tests can import the example modules.
- `__main__.py` — run the demo via ``python -m exactus.packages.visual_cause.examples``.
- `run.py` — serve the bundled demo via `exactus.packages.server` and analyze it end to end.
- `validate_results.py` — check demo evidence and report completeness.
- `web/` — static demo page and its two candidate stylesheets.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Runnable examples for visual_cause.
- [`__main__.py`](__main__.py) — Run the visual-cause example with the project virtual environment.
- [`run.py`](run.py) — Run the CSS visual-cause analyzer against its bundled demo.
- [`validate_results.py`](validate_results.py) — Validate that the demo produced navigable human evidence.

### Subdirectories

- [`results/`](results/README.md) — Provide a png content.
- [`web/`](web/README.md) — Minimal static demo for the CSS visual-cause analyzer.

<!-- exactus:inventory:end -->
