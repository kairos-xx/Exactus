# Tests

Tests of the kwargs-typehints tool.

- `__init__.py` — Tests of the kwargs-typehints tool.
- `test_kwargs_typehints.py` — The kwargs-typehints analyzer on projects, flags and its artifacts: strict mode, exempt positional-only and dynamic callees, the core's default root, and `ARTIFACTS/heuristics.json`.
- `test_kwargs_report.py` — KWARGS_TYPEHINTS renders result.md and its web view from normalized data: a tiny project with a missing keyword, a bare import, missing hints, an ambiguous call and unresolved callees (findings per category, order, ids, blocking, excerpts; summary, scope and metrics; extension rows linked to their findings), rare categories, the golden rendering, crash and empty states, and an `execute_exactus` run (heuristics under its new name, linkable unresolved-callee rows in the web view).
- `golden/` — Golden normalized KWARGS_TYPEHINTS `result.json` and the `result.md` it renders.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests of the kwargs-typehints tool.
- [`test_kwargs_report.py`](test_kwargs_report.py) — KWARGS_TYPEHINTS renders result.md and its web view from normalized data.
- [`test_kwargs_typehints.py`](test_kwargs_typehints.py) — The kwargs-typehints analyzer on projects, flags and its artifacts.

### Subdirectories

- [`golden/`](golden/README.md) — Golden normalized KWARGS_TYPEHINTS report used by `test_kwargs_report.py`.

<!-- exactus:inventory:end -->


