# Screenshot engine

This package owns screenshot acquisition and image similarity comparison.
Browser recording, crawling, diagnostics, and replay live in `exactus.tools.record`.
The `exactus.tools.frontend` exactus combines both engines in device/theme lanes.

## Files

- [examples](examples/README.md) — Capture a served page at three viewport sizes.

- `capture_screen.py` — Capture a URL or existing page, exposing nested overflow.
- `js/capture_screen.js` — Browser-side overflow measurement and expansion.
- `similarity.py` — Perceptual comparison, cached fingerprints, and deduplication.
- `__init__.py` — Public screenshot APIs.
- `__main__.py` — URL screenshot CLI.
- `README.md` — Package inventory.

## Subdirectories

- `examples/` — Subdirectory.
- `js/` — Subdirectory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Capture script package.
- [`__main__.py`](__main__.py) — Capture a URL screenshot (``python -m exactus.packages.screenshot``).
- [`capture_screen.py`](capture_screen.py) — Capture screenshots with arbitrarily nested overflow fully exposed.
- [`cli.py`](cli.py) — Capture a URL screenshot (``python -m exactus.packages.screenshot``).
- [`similarity.py`](similarity.py) — Multi-factor perceptual image similarity scoring.

### Subdirectories

- [`examples/`](examples/README.md) — \[run.py\](run.py) captures a served page at 390, 1440, and 1728 pixels wide using \[Screenshot.capture\](../capture_screen.py).
- [`js/`](js/README.md) — Provide capture screen js content.

<!-- exactus:inventory:end -->


