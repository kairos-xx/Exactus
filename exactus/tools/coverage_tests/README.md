# `exactus/tools/coverage_tests/`

The `coverage-tests` exactus tool (aliases `coverage` and `tests`): a
standalone entry point (`main.py`) and its analysis core (`core.py`). One
pytest run (plus the `node:test` lane) produces both the coverage report
and the test reports. The inventory below documents every direct file.

## Output tree

```text
EXACTUS_RESULTS/COVERAGE_TESTS/
├── result.md, result.json, result_web/      unified root report
├── COVERAGE/result.md, result.json, result_web/
├── TESTS/result.md, result.json, result_web/
├── TESTS/<group>/result.md, result.json, result_web/
└── ARTIFACTS/
    ├── @activity.json, stderr.log, stdout.log
    ├── COVERAGE/coverage_raw_py.json, coverage_raw_js.json,
    │   import_graph.json, meaningful.json, completion.json, validation.json
    └── TESTS/pytest-shards/shard-NNN.log, js-tests.json
```

`js-tests.json` records the Node test run (`schema`, `command`, `cwd`,
`exit_code`, `tests`, `failed_tests`, `stdout_lines`, `stderr_lines`).

## Root report

The root `result.json` follows the normalized report contract and keeps
the legacy keys (`coverage`, `import_graph`, `javascript`,
`test_execution`, `gates`, `passed`, `root`). Its `gate` is composed of
two part gates, `gate.parts.tests` and `gate.parts.coverage` (each
`{status, reason, label, position}`); the global `gate.status` is `PASS`
only when both parts pass, and its reason names each failing part.

- Tests fail when any pytest or `node:test` test failed or errored, or
  when a test run itself failed (non-zero exit without a failed test).
- Coverage fails when `--fail-under`, `--per-file-minimum`,
  `--average-minimum`, the evidence check (`--minimum`, `--critical`), or
  the required Meaningful reachability policy is unmet.

## Meaningful unreached-source classification

After tests and coverage finalize the unreached Python set, Meaningful assigns
`TEST-0` through `TEST-3`. The default `--meaningful require` mode makes
`TEST-2+` actionable: each file remains in coverage.py as an unexecuted 0%
file and creates a blocking `coverage-meaningful` finding. `classify` records
levels without changing prior omission or gate behavior; `off` disables
analysis. `--meaningful-minimum-level` changes the boundary. Failed analyses
remain visible as `unclassified`; `--meaningful-unclassified` chooses
`filtered` (default), `actionable`, or `error` handling. `--include-unreached`
still counts every unreached source at 0%, while Meaningful controls only the
dedicated findings.

`ARTIFACTS/COVERAGE/meaningful.json` records resolved settings, selected paths,
classifications, failures, evidence, decision trees, metadata, and progress
stages. Worker count, evidence context, every threshold, feature weight, cap,
and promotion floor are available as `--meaningful-*` options and matching
kebab-case `[tool.exactus.coverage_tests]` keys. Explicit CLI values override
pyproject values, which override built-in defaults. Use `classify` to audit
without enforcement or `off` to preserve the legacy behavior.

`findings` holds one blocking error per failed test (rule
`test-failure`/`test-error`, the file and line of the failing assertion
or raise read from the pytest traceback, the exception's first line as
the message, an excerpt) and one per unmet coverage gate (rules
`coverage-total`, `coverage-per-file` with the uncovered ranges and an
excerpt of the first one, `coverage-average`, `coverage-evidence`).
`extension` holds the tests summary (outcomes, duration, groups linking
to `TESTS/<group>/`), the coverage summary (per-language totals, gate
rows, files below the per-file minimum) and the sub-report links.
`result.md` is rendered from `result.json` by `templates/markdown/`.

## Configuration

Settings live in `[tool.exactus.coverage_tests]`. Resolution order is
explicit command line, tool table, common/pipeline configuration, then built-in
defaults.

`shard-by = "node"` (CLI: `--shard-by node`) collects exact pytest node IDs
before execution and balances those IDs across `jobs`, allowing tests from one
large module to run in different coverage processes. Use `file` to retain
whole-file sharding and avoid the extra collection pass.

## Directory contents

### Directories

#### `templates/`

Report templates: the root `result.md` template and its mapping.

### Files

#### `__init__.py`

Coverage and tests exactus tool.

#### `core.py`

Run recursive tests with coverage derived from their local import graph. Public API: `CoverageCoreDefaults` — Immutable scalar configuration values.; `CoverageTestsLayout` — Locate every report and artifact directory of one tool run.; `CoverageCoreTables` — Shared lookup tables and compiled values.; `CoverageRunError` — Represent a combined-coverage discovery or execution failure.; `CliNamespace` — Describe the typed command-line parser namespace.; `CoverageConfig` — Store immutable combined-coverage execution settings.; `ModuleRecord` — Describe one local importable Python module.; `ImportRequest` — Describe one static import request found in a Python module.; `ImportGraph` — Store the recursively resolved local import graph.; `JsFileCoverage` — Store line-level coverage for one JavaScript source file.; `JsCoverageResult` — Store the outcome of the JavaScript coverage lane.; `TestFailure` — One failed or errored test reported by a pytest shard.; `TestWarning` — One warning reported by a pytest shard.; `ShardOutcome` — Captured outcome of one parallel pytest shard.; `TestExecution` — Aggregate pytest shard results with parsed test issues.; `ImportCollector` — Collect static ``import`` and ``from ... import ...`` statements.; `LocalModuleIndex` — Index import names that resolve to local project Python files.; `ImportGraphResolver` — Resolve the local import closure rooted at discovered tests.; `CombinedCoverageRunner` — Discover tests, resolve local targets, and render combined coverage.; `CommandLine` — Parse command-line arguments into a typed immutable configuration.; `main()` — Run the local-import combined coverage command-line application.

#### `report.py`

Build the normalized root report of the ``coverage-tests`` tool. Public API: `ReportTables` — Constants of the normalized root report.; `CoverageGates` — Coverage gates of one run.; `ReportInputs` — Everything the root report is built from.; `Values` — Typed reads of loosely shaped JSON values.; `Ranges` — Collapse line numbers into ranges.; `CoverageTestsReport` — Compose the normalized blocks of the root report.

#### `tracebacks.py`

Locate where and why each failing test failed. Public API: `FailureSite` — Where and why one test failed.; `NamedFailure` — One failing JavaScript test with its location and reason.; `ProjectPaths` — Map frame paths printed by test runners to project files.; `PytestTracebacks` — Read failing locations and reasons from pytest's terminal output.; `NodeTestFailures` — Read failing tests from the Node test runner's ``spec`` output.

#### `main.py`

Run the project's tests once for combined coverage and test reports. Public API: `create_parser()` — Create parser.; `parse_args()` — Parse args.; `main()` — Return main.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Coverage and tests exactus tool.
- [`arguments.py`](arguments.py) — Declare the coverage_tests CLI grammar.
- [`core.py`](core.py) — Run recursive tests with coverage derived from their local import graph.
- [`main.py`](main.py) — Run the project's tests once for combined coverage and test reports.
- [`meaningful.py`](meaningful.py) — Classify unreached and sub-minimum sources with Meaningful.
- [`report.py`](report.py) — Build the normalized root report of the ``coverage-tests`` tool.
- [`skip_plugin.py`](skip_plugin.py) — Preserve pytest skip identities and capture per-file execution timings.
- [`tracebacks.py`](tracebacks.py) — Locate where and why each failing test failed.

### Subdirectories

- [`templates/`](templates/README.md) — Report templates of the coverage-tests tool. The inventory below documents every direct file and child directory.

<!-- exactus:inventory:end -->

