# Golden LINTS report

Golden normalized LINTS report used by `test_lints_report.py`.

- `result.json` — Normalized LINTS result (envelope, tool blocks and legacy `tools`/`summary`/`findings` keys) built by `report_data` from the fake legacy result of `test_lints_report.fake_report`: eight findings from five linters (two failing), one ESLint-ignored file, a missing and a not-run linter, `extension.metrics`, and three-line-context source `excerpt`s.
- `expected.md` — The `result.md` that `result.json` renders through `exactus/tools/lints/templates/markdown/`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`expected.md`](expected.md) — **Run time:** N/A
- [`result.json`](result.json) — Provide result json content.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


