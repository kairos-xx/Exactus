# Tests

Tests of `exactus/tools/common` leaf primitives and shared templates.

- `__init__.py` — Tests of `exactus/tools/common` leaf primitives and shared templates.
- `test_activity.py` — The fixed ``@activity.json`` schema, its bounded log and atomic file.
- `test_common_package.py` — The common package is a leaf: it imports nothing else from the repo.
- `test_envelope.py` — The runner-owned envelope blocks of a normalized report.
- `test_process_control.py` — Process-tree control and JSON state primitives.
- `test_report_templates.py` — The shipped report templates render goldens and reach the bundle.
- `test_snippets.py` — Bounded, root-confined source excerpts around finding lines.
- `test_sprint.py` — Flushed printing helpers and the ``DEBUG.txt`` capture directives.
- `test_stderr_capture.py` — Standard-error capture: line counts and the mirror.

## Files

- `test_conflict_copies.py` — File.
- `test_common.py` — File.
- `test_config.py` — File.
- `test_config_integration.py` — File.
- `test_context_lines.py` — File.
- `test_digest.py` — File.
- `test_terminal.py` — File.
- `test_report_comparison.py` — File.



## Shared helper coverage

- [test_common.py](test_common.py)
- [test_config.py](test_config.py)
- [test_config_integration.py](test_config_integration.py)
- [test_context_lines.py](test_context_lines.py)
- [test_digest.py](test_digest.py)
- [test_terminal.py](test_terminal.py)

- [`test_report_time.py`](test_report_time.py) — Run timestamp precedence and timezone formatting.
- [test_report_comparison.py](test_report_comparison.py) — Baseline retention, worker inheritance, repeated findings, and subsection deltas.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests of `exactus/tools/common` leaf primitives and shared templates.
- [`test_activity.py`](test_activity.py) — The fixed ``@activity.json`` schema, its bounded log and atomic file.
- [`test_analyzers.py`](test_analyzers.py) — In-process runs of every static analyzer over the toolkit and a sample.
- [`test_catalog.py`](test_catalog.py) — Catalog validation, alias resolution, and pipeline wave planning.
- [`test_collect_files.py`](test_collect_files.py) — The ``FILES`` bundle written beside reports when collecting files.
- [`test_common.py`](test_common.py) — Shared helpers: output resolution, filtering, and bundle discovery.
- [`test_common_package.py`](test_common_package.py) — The common package is a leaf: it imports nothing else from the repo.
- [`test_config.py`](test_config.py) — Discovery, parsing, merging and rendering of ``\[tool.exactus\]`` settings.
- [`test_config_integration.py`](test_config_integration.py) — ``pyproject.toml`` settings reaching standalone tools and ``check``.
- [`test_conflict_copies.py`](test_conflict_copies.py) — Verify automatic sync cleanup preserves unique and conflicting data.
- [`test_context_lines.py`](test_context_lines.py) — The shared ``--context-lines`` option and its configuration layers.
- [`test_digest.py`](test_digest.py) — Tool reports are digested into failure summaries for aggregates.
- [`test_directory_inventory.py`](test_directory_inventory.py) — Verify semantic, bottom-up README inventories and idempotent repairs.
- [`test_envelope.py`](test_envelope.py) — The runner-owned envelope blocks of a normalized report.
- [`test_examples_run.py`](test_examples_run.py) — Cover the bundled ``common`` examples entry points.
- [`test_execution.py`](test_execution.py) — The shared exactus execution wrapper, fallbacks, and crash recording.
- [`test_models_api.py`](test_models_api.py) — Result models, progress documents, the process API, and runtime.
- [`test_output_tree.py`](test_output_tree.py) — Every tool run leaves ``@activity.json``, ``stderr.log``/``stdout.log``.
- [`test_pipeline_output.py`](test_pipeline_output.py) — Pipeline output lives under ``EXACTUS_RESULTS/PIPELINES/``.
- [`test_pipeline_supervisor.py`](test_pipeline_supervisor.py) — Verify transactional pipeline ownership and observer generations.
- [`test_process_control.py`](test_process_control.py) — Process-tree control and JSON state primitives.
- [`test_progress_ownership.py`](test_progress_ownership.py) — Keep terminal progress tied to the invocation being displayed.
- [`test_registry.py`](test_registry.py) — The cross-process run registry.
- [`test_report_comparison.py`](test_report_comparison.py) — Exercise baseline retention and per-section report comparisons.
- [`test_report_templates.py`](test_report_templates.py) — The shipped report templates render goldens and reach the bundle.
- [`test_report_time.py`](test_report_time.py) — Verify readable report timestamps and recorded-time precedence.
- [`test_snippets.py`](test_snippets.py) — Bounded, root-confined source excerpts around finding lines.
- [`test_sprint.py`](test_sprint.py) — Flushed printing helpers and the ``DEBUG.txt`` capture directives.
- [`test_stderr_capture.py`](test_stderr_capture.py) — Standard-error capture: line counts, levels and the mirror.
- [`test_terminal.py`](test_terminal.py) — ANSI terminal rendering, progress painting, and cursor probing.
- [`test_terminal_progress.py`](test_terminal_progress.py) — Determinate and indeterminate terminal progress rendering.
- [`test_toml.py`](test_toml.py) — Round-trip coverage for the dependency-free TOML serializer.
- [`test_tool_worker.py`](test_tool_worker.py) — Detached exactus worker specifications, results, and lifecycle hooks.
- [`test_toolkit.py`](test_toolkit.py) — Validate catalog, collection, and current partitioned tool dispatch.

### Subdirectories

- [`js/`](js/README.md) — `node:test` suites for the shared HTML report template at `exactus/tools/common/templates/html/report.js`. Browser assertions run through the shared \[`exactus/tests/common/browser.mjs`\](../../../common/browser.mjs) Playwright harness.
- [`process_layer/`](process_layer/README.md) — Test authenticated process-layer access and lifecycle helpers.

<!-- exactus:inventory:end -->

