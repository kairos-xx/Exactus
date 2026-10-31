[Home](Home.md) > [Tools](Tools.md) > coverage_tests

# tools/coverage_tests/

The `coverage-tests` tool: runs the project's tests once, producing
combined coverage and test reports with per-group nested reports.

## Files

| File | Description |
|---|---|
| `arguments.py` | The coverage-tests CLI grammar, declared without importing the execution engine. |
| `core.py` | Recursive test execution with coverage derived from each shard's local import graph. |
| `main.py` | Entry: run tests once for the combined coverage + test report bundle. |
| `meaningful.py` | Classify unreached and sub-minimum sources with `exactus/packages/meaningful`: drives the `coverage-meaningful` gate, which requires meaningful sources below the thresholds to have an associated test or an explicit excuse. |
| `report.py` | Build the normalized root report (independent test/coverage/aggregate gates). |
| `skip_plugin.py` | Pytest plugin preserving complete skip identities and reasons in shard output. |
| `tracebacks.py` | Locate where and why each failing test failed. |
| `templates/` | Tool-specific Markdown template/mapping composed on the shared engine. |

## Report shape

- Root `EXACTUS_RESULTS/COVERAGE_TESTS/` holds the aggregate report with
  three independent gates: tests, coverage threshold, aggregate.
- Nested `TESTS/<group>/` folders carry each shard's own normalized
  report; `COVERAGE/` carries the coverage report — each independently
  gated and stamped.
- Shards are split by the local import graph so coverage measurement is
  accurate per group rather than global.
- `--shard-by node` distributes collected pytest node IDs across `--jobs`, so
  one large test module no longer determines a worker's critical path;
  `--shard-by file` retains whole-file scheduling.
- Skipped tests keep their full node id and reason via `skip_plugin`;
  failures get tracebacks mapped to files/lines via `tracebacks.py`.

## Gates and filtering

- `--fail-under` (or `fail-under`) is the total coverage floor and
  defaults to `90`; the run fails when measured coverage lands below it.
- `--per-file-minimum` (or `per-file-minimum`) is the per-source-file
  floor and defaults to `80` — every measured file below it is reported
  under "Files below the per-file gate" and fails the run. `0` disables
  the per-file gate.
- `--exclude` (or `exclude = [...]`) filters by root-relative glob in
  both directions: matching test files are not collected, and matching
  Python/JavaScript source files are excluded from coverage measurement
  and meaningful findings. Excluded sources still appear in
  `import_graph.json` under `omitted_sources` for transparency.
- `--include` (or `include = [...]`) restricts test discovery to
  matching paths.
- `--critical` / `--critical-minimum` apply a stricter floor to
  control-plane modules matched by path fragment.
- Uncovered-line lists render as compact spans: runs of three or more
  contiguous lines become `first-last` (`5-9`), while two-line runs stay
  comma-separated (`5, 6`) since `5-6` is no clearer. The structured
  `uncovered_ranges` data keeps the raw ranges; the same rule applies in
  the web report's missing-lines column.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/tools/coverage_tests/`](../exactus/tools/coverage_tests/) | [`exactus/tests/tools/coverage_tests/`](../exactus/tests/tools/coverage_tests/) | [`DOCS.md`](../exactus/docs/tools/coverage_tests/DOCS.md) |

[< Tools-completion](Tools-completion.md) · [Tools index](Tools.md) · [Tools-docs >](Tools-docs.md)
