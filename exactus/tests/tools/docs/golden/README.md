# Golden DOCS report

Golden normalized DOCS report used by `test_docs_report.py`.

- `result.json` — Normalized DOCS result (envelope, tool blocks and legacy keys) with findings and one skipped target and the `extension.metrics` block; every finding carries a three-line-context source `excerpt`.
- `expected.md` — The `result.md` that `result.json` renders through `exactus/tools/docs/templates/markdown/`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`expected.md`](expected.md) — **Run time:** N/A
- [`result.json`](result.json) — Provide result json content.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


