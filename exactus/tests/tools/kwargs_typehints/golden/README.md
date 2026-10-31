# Golden KWARGS_TYPEHINTS report

Golden normalized KWARGS_TYPEHINTS report used by `test_kwargs_report.py`.

- `result.json` — Normalized KWARGS_TYPEHINTS result (envelope, tool blocks and the legacy `summary`/`findings`/`bare_imports`/`type_hints`/`ambiguous`/`unresolved` keys) built by the exactus core from the tiny project of `test_kwargs_report.write_project`: eight findings in five categories (one missing keyword, a bare import, three missing hints, an ambiguous call, two unresolved callees), `extension` metrics and tables, and three-line-context source `excerpt`s; the envelope is the LINTS golden one with the tool renamed.
- `expected.md` — The `result.md` that `result.json` renders through `exactus/tools/kwargs_typehints/templates/markdown/`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`expected.md`](expected.md) — **Run time:** N/A
- [`result.json`](result.json) — Provide result json content.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


