# Screenshot examples

[run.py](run.py) captures a served page at 390, 1440, and
1728 pixels wide using [Screenshot.capture](../capture_screen.py).

With no arguments it serves the bundled [demo page](web/README.md) through
`exactus.packages.server` — the page's clamped feed element forces the capture engine
to expand the hidden browser window beyond the 900px viewport — and saves
each PNG under `results/` (override with `--output`):

```sh
python -m exactus.packages.screenshot.examples
```

A URL may also be supplied to capture any other served page:

```sh
python -m exactus.packages.screenshot.examples http://127.0.0.1:8000
```

Install the Playwright Chromium browser first if needed:
`python -m playwright install chromium`. The example prints each saved PNG
path and closes the browser after each capture.

## Files

- `__init__.py` — File.
- `__main__.py` — File.
- `run.py` — File.
- `web/` — bundled demo page served by the example.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Provide runnable screenshot capture examples.
- [`__main__.py`](__main__.py) — Run the screenshot example with the project virtual environment.
- [`run.py`](run.py) — Capture a served page at mobile and desktop viewport sizes.

### Subdirectories

- [`results/`](results/README.md) — Provide page 1440 png content.
- [`web/`](web/README.md) — Static demo page served by `../run.py` through `exactus.packages.server` — includes a clamped feed that forces the capture engine to expand the hidden browser window for a full-height screenshot.

<!-- exactus:inventory:end -->
