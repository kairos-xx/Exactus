# project/

Minimal mixed-language project audited by the installed `exactus`
executable. `python/` holds a small Python package, `web/` a tiny web
page, and `tests/` the tests covering both. Running `exactus` with
`--root` pointing here writes `EXACTUS_RESULTS/` inside this directory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Standalone fixture project root marker.
- [`conftest.py`](conftest.py) — Make the fixture project's ``python`` package importable in tests.
- [`pyproject.toml`](pyproject.toml) — Provide pyproject toml content.

### Subdirectories

- [`python/`](python/README.md) — A toy Python package (`calc.py`: `add`, `is_even`) exercised by the fixture's tests and by the standalone `exactus` run.
- [`tests/`](tests/README.md) — Fixture-project tests: `test_calc.py` covers `python/calc.py` and `code.test.mjs` covers `web/code.js`. They run both inside the repository suite and inside the standalone `exactus` audit.
- [`web/`](web/README.md) — A one-page fixture (`index.html`, `code.js`, `style.css`) loaded by the standalone `exactus` run's HTML/CSS/JS checks.

<!-- exactus:inventory:end -->
