# Tests

- `__init__.py` — package marker for the CSS visual cause analyzer tests.
- `support.py` — Test helpers mirroring `exactus/tests/common/support.py` conventions.
- `test_advanced.py` — Advanced analyzer helper coverage.
- `test_analyzer_helpers.py` — White-box coverage of analyzer internals.
- `test_browser_js.py` — Browser JavaScript asset inventory and behavior.
- `test_cli_coverage.py` — Command-line entry point checks.
- `test_css_targets.py` — CSS target parsing and resolution.
- `test_dom_diff.py` — Generic two-URL DOM-overlap diff coverage.
- `test_dual_url_tokens.py` — Dual-URL token handling.
- `test_examples.py` — Bundled examples render expected output.
- `test_full_pipeline.py` — End-to-end pipeline coverage.
- `test_runtime_lifecycle.py` — Browser runtime lifecycle management.
- `test_token_cascade.py` — Token cascade provenance.
- `test_typed_parallel.py` — Typed parallel worker coverage.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests of `exactus/packages/visual_cause`.
- [`browser_operations.test.mjs`](browser_operations.test.mjs) — Evaluate a visual-cause browser operation inside a fresh VM context.
- [`support.py`](support.py) — Typed assertion and reflection helpers shared by the test suite.
- [`test_advanced.py`](test_advanced.py) — Tests for advanced CSS causal analysis primitives.
- [`test_analyzer_helpers.py`](test_analyzer_helpers.py) — Focused behavioral coverage for analyzer helper logic.
- [`test_browser_js.py`](test_browser_js.py) — Validate every browser-side JavaScript source asset.
- [`test_cli_coverage.py`](test_cli_coverage.py) — Coverage for command entry points.
- [`test_css_targets.py`](test_css_targets.py) — Tests for CSS file/directory comparison targets.
- [`test_dom_diff.py`](test_dom_diff.py) — Coverage for generic two-URL visual DOM comparison.
- [`test_dual_url_tokens.py`](test_dual_url_tokens.py) — Tests for dual URL and token CSS analysis.
- [`test_examples.py`](test_examples.py) — Coverage and behavior tests for bundled runnable examples.
- [`test_full_pipeline.py`](test_full_pipeline.py) — End-to-end coverage for the bounded causal-analysis pipeline.
- [`test_runtime_lifecycle.py`](test_runtime_lifecycle.py) — Regression tests for bounded runtime and report lifecycle.
- [`test_support.py`](test_support.py) — Validate the shared visual_cause test helpers.
- [`test_token_cascade.py`](test_token_cascade.py) — Tests for exact CSS value nodes.
- [`test_typed_parallel.py`](test_typed_parallel.py) — Tests for Typed OM and parallel settings surfaces.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
