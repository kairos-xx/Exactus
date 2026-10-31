# standalone/

End-to-end verification that the installed `exactus` executable audits a
plain project: `test_standalone.py` runs the system `exactus` (or the
built `bin/release/exactus_<system>_<arch>` release binary) over `project/` and
checks that `project/EXACTUS_RESULTS/` reports are produced.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Standalone end-to-end fixture tests.
- [`test_standalone.py`](test_standalone.py) — Run the system ``exactus`` executable over the standalone project.

### Subdirectories

- [`project/`](project/README.md) — Minimal mixed-language project audited by the installed `exactus` executable. `python/` holds a small Python package, `web/` a tiny web page, and `tests/` the tests covering both. Running `exactus` with `--root` pointing here writes `EXACTUS_RESULTS/` inside this directory.

<!-- exactus:inventory:end -->
