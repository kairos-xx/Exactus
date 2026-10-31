# Tests

Tests of the lints tool.

- `__init__.py` — Tests of the lints tool.
- `test_lints.py` — In-process runs of the lints analyzer over generated projects.
- `test_lints_install.py` — Installer paths of the lints core, exercised with fake subprocesses.
- `test_lints_normalizers.py` — Diagnostic normalizers for every external tool's JSON output.
- `test_lints_report.py` — LINTS renders result.md and its web view from normalized data: `report_data` on a fake legacy result (summary, scope, findings order and blocking, metrics), excerpts, titles, paths, linter versions and durations, the golden rendering, crash and empty states, and an `execute_exactus` run with every external linter resolved to nothing.
- `test_long_lines.py` — The long-line repair preserves the AST, converges, honors Ruff's exemptions and its Python API, and runs as the stabilization hook.
- `test_shebang.py` — The lints shebang check reports and heals permission mismatches.
- `test_shebang_metrics.py` — The lints shebang check counts executables, shebangs and interpreters.
- `golden/` — Golden normalized LINTS `result.json` and the `result.md` it renders.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests of the lints tool.
- [`test_compliance.py`](test_compliance.py) — LINTS includes the canonical engineering rules and their source evidence.
- [`test_css_tokens.py`](test_css_tokens.py) — The lints CSS token audit resolves one token graph across stylesheets.
- [`test_js_delimiters.py`](test_js_delimiters.py) — Behavioral tests for the JavaScript delimiter simplifier.
- [`test_js_function_blocks.py`](test_js_function_blocks.py) — Behavioral tests for the Python JavaScript block analyzer API.
- [`test_lints.py`](test_lints.py) — In-process runs of the lints analyzer over generated projects.
- [`test_lints_install.py`](test_lints_install.py) — Installer paths of the lints core, exercised with fake subprocesses.
- [`test_lints_normalizers.py`](test_lints_normalizers.py) — Diagnostic normalizers for every external tool's JSON output.
- [`test_lints_report.py`](test_lints_report.py) — LINTS renders result.md and its web view from normalized data.
- [`test_long_lines.py`](test_long_lines.py) — The lints long-line repair keeps behavior and converges to a fixpoint.
- [`test_method_contracts.py`](test_method_contracts.py) — Protect externally inherited instance methods from binding changes.
- [`test_shebang.py`](test_shebang.py) — The lints shebang check reports and heals permission mismatches.
- [`test_shebang_metrics.py`](test_shebang_metrics.py) — The lints shebang check counts executables, shebangs and interpreters.
- [`test_source_cleaner.py`](test_source_cleaner.py) — Behavioral tests for the lints source cleaner.
- [`test_string_transform.py`](test_string_transform.py) — Behavioral tests for source-preserving string conversion.

### Subdirectories

- [`golden/`](golden/README.md) — Golden normalized LINTS report used by `test_lints_report.py`.
- [`js/`](js/README.md) — `node:test` suites verifying lint configuration contracts and the JavaScript function-block analyzer (including its differential torture suite).

<!-- exactus:inventory:end -->


