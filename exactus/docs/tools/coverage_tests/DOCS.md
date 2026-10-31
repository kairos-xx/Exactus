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

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Coverage and tests exactus tool. |
| `arguments.py` | Declare the coverage_tests CLI grammar. |
| `core.py` | Run recursive tests with coverage derived from their local import graph. |
| `main.py` | Run the project's tests once for combined coverage and test reports. |
| `meaningful.py` | Classify unreached and sub-minimum sources with Meaningful. |
| `report.py` | Build the normalized root report of the ``coverage-tests`` tool. |
| `skip_plugin.py` | Preserve pytest skip identities and capture per-file execution timings. |
| `templates/` | Subdirectory. |
| `tracebacks.py` | Locate where and why each failing test failed. |

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--source-root` |  | action='append', default=[] |
| `--no-branch` |  | action='store_true' |
| `--no-js-coverage` |  | action='store_true' |
| `--jobs` |  | type=_positive |
| `--shard-by` | Balance pytest workers by test file or by collected pytest node ID. Node sharding can split large test modules. | choices=('file', 'node'), default='file' |
| `--fail-under` | Fail when total coverage is below this percent. | type=float, default=Constants.default_fail_under |
| `--pytest-arg` |  | action='append', default=[] |
| `--include-unreached` |  | action='store_true' |
| `--average-minimum` |  | type=float |
| `--per-file-minimum` | Fail when any single source file is below this percent (0 disables the per-file gate). Files below the minimum are excused when Meaningful classifies them below the minimum test level and are then excluded from coverage. | type=float, default=Constants.default_per_file_minimum |
| `--minimum` | Required total coverage of the validated evidence. | type=float, default=80.0 |
| `--critical` | Path fragment of a control-plane module with a stricter floor; repeatable. | action='append', default=[] |
| `--critical-minimum` |  | type=float, default=80.0 |
| `--meaningful` | Meaningful classification of unreached and sub-minimum sources; 'off' disables both checks. | choices=('off', 'classify', 'require'), default='require' |
| `--meaningful-minimum-level` |  | choices=('TEST-0', 'TEST-1', 'TEST-2', 'TEST-3'), default='TEST-2' |
| `--meaningful-unclassified` |  | choices=('filtered', 'actionable', 'error'), default='filtered' |
| `--meaningful-workers` |  | type=_positive |
| `--meaningful-evidence-context` |  | type=_non_negative, default=policy.evidence_context |
| `root` | Project root to scan recursively (default: current directory). | nargs='?', type=Path, default=Path.cwd() |
| `-o, --output` | Report output directory (default: coverage_report). | type=Path, default=Path('coverage_report') |
| `--source-root` | Local import root allowed in coverage; repeat as needed. Defaults to ROOT/src when it exists, otherwise ROOT. | action='append', type=Path, default=[], metavar='PATH' |
| `--no-branch` | Disable branch coverage. | action='store_true' |
| `--fail-under` | Fail when total coverage is below PERCENT after all reports (default: %(default)s). | type=float, default=_GroupFinalConstants.default_fail_under, metavar='PERCENT' |
| `--exclude-dir` | Add a directory basename to recursive discovery exclusions. | action='append', default=[], metavar='NAME' |
| `--no-js-coverage` | Skip running discovered `node:test` suites under Node V8 coverage. | action='store_true' |
| `--jobs, -j` | Split the discovered tests across N parallel pytest processes (default: all CPU cores; use 1 to run serially). | type=int, default=None, metavar='N' |
| `--shard-by` | Balance workers by test files or exact collected pytest node IDs (default: %(default)s). | choices=('file', 'node'), default='file' |
| `--context-lines` | Source lines embedded around each uncovered run in the web report snippets (default: %(default)s). | type=int, default=3, metavar='N' |
| `--per-file-minimum` | Fail when any single source file is below PERCENT (default: %(default)s; 0 disables the gate). | type=float, default=80.0, metavar='PERCENT' |
| `pytest_args` | Extra pytest arguments; place them after '--'. | nargs='*' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Coverage and tests exactus tool.


### `arguments.py`

Declare the coverage_tests CLI grammar.

- `class Constants` — Group module-level constants.
  - `default_fail_under` = `90.0`
  - `default_per_file_minimum` = `80.0`
- `create_parser() -> ArgumentParser` — Create parser.

### `core.py`

Run recursive tests with coverage derived from their local import graph.

- `class Constants` — Group module-level constants.
  - `bmp_max` = `65535`
  - `expensive_call_names` = `frozenset({'Popen', 'browserTest', 'check_call', 'check_output', 'communi...`
  - `child_env_drop` = `frozenset({'EXACTUS_ORCHESTRATED', 'EXACTUS_PIPELINE_RUN_ID', 'EXACTUS_RE...`
- `class CoverageCoreDefaults` — Immutable scalar configuration values.
  - `raw_report_name` = `'coverage_raw_py.json'`
  - `raw_js_report_name` = `'coverage_raw_js.json'`
  - `import_graph_name` = `'import_graph.json'`
  - `meaningful_name` = `'meaningful.json'`
  - `completion_name` = `'completion.json'`
  - `validation_name` = `'validation.json'`
  - `js_tests_name` = `'js-tests.json'`
  - `js_tests_schema` = `'exactus.coverage-tests.js-tests/v1'`
  - `test_costs_name` = `'test-costs.json'`
  - `v8_coverage_dir` = `'v8-coverage'`
- `class CoverageTestsLayout` — Locate every report and artifact directory of one tool run.
  - Fields: `root: Path`
  - `coverage_report(self: Self) -> Path` — Directory of the coverage report.
  - `tests_report(self: Self) -> Path` — Directory of the combined tests report and its group reports.
  - `artifacts(self: Self) -> Path` — Directory shared by the run's artifacts.
  - `coverage_artifacts(self: Self) -> Path` — Directory of the raw coverage evidence.
  - `tests_artifacts(self: Self) -> Path` — Directory of the raw test-run evidence.
- `class CoverageCoreTables` — Shared lookup tables and compiled values.
  - `DEFAULT_EXCLUDED_DIRS` = `ExactusCommonTables.DEFAULT_EXCLUDED_DIRS | frozenset({'bundle'})`
  - `DEFAULT_SOURCE_DIR_NAMES` = `('src',)`
  - `TEST_DIR_NAMES` = `frozenset({'test', 'tests'})`
  - `JS_TEST_SUFFIXES` = `frozenset({'.js', '.mjs', '.cjs'})`
  - `JS_TEST_NAME` = `recompile(pattern='(?:\\.test|\\.spec|_test)\\.[cm]?js$')`
  - `JS_LOADER` = `'exactus/tests/loader.mjs'`
  - `JS_SOURCE_SUFFIXES` = `frozenset({'.js', '.mjs'})`
  - `SHARD_LOG_DIRECTORY` = `'pytest-shards'`
  - `PYTEST_SUMMARY_ENTRY` = `recompile(pattern='^(?P<kind>FAILED|ERROR)\\s+(?P<test>.+?)(?:\\s+-\\s+(?...`
  - `PYTEST_TEST_ENTRY` = `recompile(pattern='^(?P<test>.+::.+)\\s+(?P<outcome>PASSED|FAILED|ERROR|S...`
  - `PYTEST_COLLECTED_ENTRY` = `recompile(pattern='collected\\s+(?P<count>\\d+)\\s+items?\\b')`
  - `PYTEST_DURATION_ENTRY` = `recompile(pattern='^\\s*(?P<seconds>\\d+(?:\\.\\d+)?)s\\s+(?:setup|call|t...`
  - `PYTEST_WARNING_LOCATION` = `recompile(pattern='^\\s+(?P<location>\\S+?:\\d+):\\s+(?P<category>[A-Za-z...`
  - `JS_FAILURE_ENTRY` = `recompile(pattern='^\\s*not ok\\s+\\d+\\s+-\\s+(?P<name>.+?)\\s*$')`
  - `SNIPPET_LANGUAGES` = `{'.py': 'python', '.pyi': 'python', '.js': 'javascript', '.jsx': 'javascr...`
  - `SNIPPET_MAX_LINES` = `600`
- `class CoverageRunError` — Represent a combined-coverage discovery or execution failure.
- `class CliNamespace` — Describe the typed command-line parser namespace.
  - Fields: `root: Path`, `output: Path`, `source_root: list[Path]`, `no_branch: bool`, `fail_under: float | None`, `exclude_dir: list[str]`, `pytest_args: list[str]`, `no_js_coverage: bool`, `jobs: int | None`, `shard_by: str`, `context_lines: int`, `per_file_minimum: float | None`
  - `__init__(self: Self) -> None` — Initialize parser defaults before argparse overwrites them.
- `class CoverageConfig` — Store immutable combined-coverage execution settings.
  - `include_unreached` = `False`
  - `measure_js` = `True`
  - `jobs` = `1`
  - `shard_by` = `'file'`
  - `context_lines` = `3`
  - `per_file_minimum` = `None`
  - `test_includes` = `()`
  - `test_excludes` = `()`
  - `source_excludes` = `()`
  - `meaningful` = `field(default_factory=MeaningfulConfig)`
  - Fields: `root: Path`, `output: Path`, `source_roots: tuple[Path, ...]`, `branch: bool`, `fail_under: float | None`, `excluded_dirs: frozenset[str]`, `pytest_args: tuple[str, ...]`
- `class ModuleRecord` — Describe one local importable Python module.
  - Fields: `name: str`, `path: Path`, `source_root: Path`, `is_package: bool`
- `class ImportRequest` — Describe one static import request found in a Python module.
  - Fields: `module: str | None`, `names: tuple[str, ...]`, `level: int`
- `class ImportGraph` — Store the recursively resolved local import graph.
  - Fields: `tests: tuple[Path, ...]`, `targets: tuple[ModuleRecord, ...]`, `ignored_imports: tuple[str, ...]`
- `class JsFileCoverage` — Store line-level coverage for one JavaScript source file.
  - Fields: `covered: frozenset[int]`, `executable: frozenset[int]`
- `class JsCoverageResult` — Store the outcome of the JavaScript coverage lane.
  - `detail` = `''`
  - `failures` = `()`
  - `failure_sites` = `()`
  - Fields: `tests: tuple[str, ...]`, `files: dict[str, JsFileCoverage]`, `unreached: tuple[str, ...]`, `status: int`
- `class CoverageSnapshot` — Store the measured coverage state at one point in the run.
  - Fields: `report: dict[str, JsonValue]`, `js_result: JsCoverageResult | None`, `js_manifest: dict[str, JsonValue] | None`
- `class TestFailure` — One failed or errored test reported by a pytest shard.
  - `path` = `None`
  - `line` = `None`
  - `reason` = `''`
  - Fields: `shard: int`, `kind: str`, `test: str`, `detail: str`
- `class TestWarning` — One warning reported by a pytest shard.
  - Fields: `shard: int`, `test: str`, `location: str`, `category: str`, `message: str`
- `class ExecutedTest` — One executed test reported by a pytest shard.
  - Fields: `shard: int`, `test: str`, `outcome: str`
- `class ShardOutcome` — Captured outcome of one parallel pytest shard.
  - `skipped` = `()`
  - Fields: `index: int`, `returncode: int`, `log: str`, `collected: int | None`, `tests: tuple[ExecutedTest, ...]`, `failures: tuple[TestFailure, ...]`, `warnings: tuple[TestWarning, ...]`
- `class TestExecution` — Aggregate pytest shard results with parsed test issues.
  - `duration_seconds` = `0.0`
  - Fields: `shards: tuple[ShardOutcome, ...]`, `status: int`
- `class ImportCollector` — Collect static ``import`` and ``from ... import ...`` statements.
  - `__init__(self: Self) -> None` — Initialize an empty collector.
  - `generic_visit(self: Self, node: AST) -> None` — Route import nodes to their collectors and keep recursing.
- `class LocalModuleIndex` — Index import names that resolve to local project Python files.
  - `__init__(self: Self, root: Path, source_roots: tuple[Path, ...], excluded_dirs: frozenset[str], excludes: tuple[str, ...]=()) -> None` — Build the local module index.
  - `records(self: Self) -> tuple[ModuleRecord, ...]` — All indexed local modules.
  - `excluded(self: Self) -> tuple[Path, ...]` — Source files rejected by the configured exclude globs.
  - `record_for_name(self: Self, name: str) -> ModuleRecord | None` — Return the local record for an import name.
  - `record_for_path(self: Self, path: Path) -> ModuleRecord | None` — Return the indexed record for a source path.
  - `package_records(self: Self, name: str) -> tuple[ModuleRecord, ...]` — Return package initializers loaded before a module.
- `class ImportGraphResolver` — Resolve the local import closure rooted at discovered tests.
  - `__init__(self: Self, index: LocalModuleIndex) -> None` — Initialize the resolver.
  - `resolve(self: Self, tests: tuple[Path, ...]) -> ImportGraph` — Resolve all recursively reachable local modules from exactus.tests.
- `class CombinedCoverageRunner` — Discover tests, resolve local targets, and render combined coverage.
  - `__init__(self: Self, config: CoverageConfig, *, test_filter: Callable[[Path], bool] | None=None) -> None` — Initialize the runner.
  - `execute_program(cls: type[Self], *, program: str, arguments: tuple[str, ...], cwd: Path, environment: Mapping[str, str]) -> CompletedProcess[bytes]` — Execute one arbitrary program without a shell.
  - `execute_many(cls: type[Self], *, argument_sets: tuple[tuple[str, ...], ...], cwd: Path, program: str | None=None, concurrency: int | None=None, progress: tuple[str, tuple[float, float]]=('pytest shard', (0.2, 0.6))) -> tuple[CompletedProcess[bytes], ...]` — Execute several Python module commands in parallel.
  - `execute(cls: type[Self], arguments: tuple[str, ...], cwd: Path, program: str | None=None) -> CompletedProcess[bytes]` — Execute one Python module command without a shell.
  - `pytest_failures(*, text: str, shard: int, root: Path | None=None) -> tuple[TestFailure, ...]` — Extract FAILED/ERROR summary entries from pytest output.
  - `pytest_skips(*, text: str, shard: int) -> tuple[TestFailure, ...]` — Read the complete skip records emitted by the pytest plugin.
  - `pytest_tests(*, text: str, shard: int) -> tuple[ExecutedTest, ...]` — Extract per-test outcomes from verbose pytest output.
  - `pytest_collected(*, text: str) -> int | None` — Extract the collected test count from pytest output.
  - `pytest_warnings(*, text: str, shard: int) -> tuple[TestWarning, ...]` — Extract warnings-summary entries from pytest output.
  - `discover_tests(self: Self) -> tuple[Path, ...]` — Return deterministic recursive ``test_*.py`` paths.
  - `discover_js_tests(self: Self) -> tuple[Path, ...]` — Return deterministic ``node:test`` test files across the project.
  - `run(self: Self) -> int` — Run all tests once and report only their reachable local sources.
- `class CommandLine` — Parse command-line arguments into a typed immutable configuration.
  - `target_source_roots(cls: type[Self], *, requested: Path, root: Path) -> tuple[Path, ...]` — Choose the measured source roots for an exactus target.
  - `parse(cls: type[Self]) -> CoverageConfig` — Parse CLI arguments.
  - `project_root(root: Path) -> Path` — Widen a subdirectory root to the enclosing project root.
  - `default_source_roots(root: Path) -> tuple[Path, ...]` — Choose conventional local source roots.
- `main() -> None` — Run the local-import combined coverage command-line application.

### `main.py`

Run the project's tests once for combined coverage and test reports.

- `class CoverageValidator` — Reject partial/stale coverage evidence before release publication.
  - `validate(cls: type[Self], *, directory: Path, minimum_percent: float, critical_patterns: tuple[str, ...]=(), critical_minimum: float=0.0) -> dict[str, JsonValue]` — Validate completion marker, coverage JSON and minimum percentage.
  - `critical_shortfalls(*, data: dict[str, JsonValue], patterns: tuple[str, ...], minimum_percent: float) -> tuple[tuple[str, float], ...]` — Return control-plane files below their own coverage floor.
  - `evidence(*, directory: Path) -> Path` — Locate the directory holding the completion marker.
- `create_parser() -> ArgumentParser` — Return the shared CLI grammar used by execution and completion.
- `parse_args(*, arguments: tuple[str, ...] | None=None) -> Namespace` — Parse args.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Return main.

### `meaningful.py`

Classify unreached and sub-minimum sources with Meaningful.

- `class MeaningfulConfig` — Store Exactus controls and the complete Meaningful evaluation policy.
  - `mode` = `'require'`
  - `minimum_level` = `UnitTestLevel.TEST_2`
  - `unclassified` = `'filtered'`
  - `workers` = `None`
  - `policy` = `field(default_factory=EvaluationPolicy)`
- `class MeaningfulResult` — Retain canonical skipped rows and the complete artifact payload.
  - Fields: `rows: tuple[dict[str, JsonValue], ...]`, `artifact: dict[str, JsonValue]`
  - `actionable(self) -> tuple[str, ...]` — Return paths Exactus treats as requiring test reachability.
  - `analysis_errors(self) -> tuple[str, ...]` — Return failed paths whose configured policy is ``error``.
  - `excused(self) -> tuple[str, ...]` — Return paths neither requiring tests nor failing analysis.
- `policy_from_values(*, evidence_context: int, thresholds: tuple[float, float, float], weights: tuple[float, float, float, float, float, float, float, float, float], caps: tuple[int, int, int, int, int, int, int, int, int], floors: tuple[float, float, float, float, float]) -> EvaluationPolicy` — Build and validate a complete Meaningful evaluation policy.
- `analyze_unreached(*, root: Path, paths: tuple[Path, ...], config: MeaningfulConfig, origin: ClassificationOrigin='unreached') -> MeaningfulResult` — Classify every canonical candidate path without dropping failures.
- `merge_results(*, first: MeaningfulResult, second: MeaningfulResult) -> MeaningfulResult` — Merge two classification passes into one combined result.
- `write_artifact(*, path: Path, result: MeaningfulResult) -> None` — Write the complete Meaningful integration artifact.

### `report.py`

Build the normalized root report of the ``coverage-tests`` tool.

- `class ReportTables` — Constants of the normalized root report.
  - `title` = `'Coverage'`
  - `assertion_values` = `2`
  - `analyzer` = `'coverage_tests'`
  - `test_rules` = `{'FAILED': 'test-failure', 'ERROR': 'test-error', 'SKIPPED': 'test-skipped'}`
  - `tests_source` = `'Tests'`
  - `coverage_source` = `'Coverage'`
  - `python_tests` = `'**/test_*.py'`
  - `javascript_tests` = `('**/*.test.{js,mjs,cjs}', '**/*.spec.{js,mjs,cjs}', '**/*_test.{js,mjs,c...`
  - `outcomes` = `{'PASSED': 'passed', 'FAILED': 'failed', 'ERROR': 'errors', 'SKIPPED': 's...`
  - `levels` = `('error', 'warning', 'info')`
- `class CoverageGates` — Coverage gates of one run.
  - `average_minimum` = `None`
  - `validation` = `None`
  - Fields: `fail_under: float | None`, `per_file_minimum: float | None`
- `class ReportInputs` — Everything the root report is built from.
  - `excluded_dirs` = `()`
  - `includes` = `()`
  - `excludes` = `()`
  - Fields: `root: Path`, `context: int`, `coverage: Mapping[str, JsonValue]`, `graph: Mapping[str, JsonValue]`, `javascript: Mapping[str, JsonValue] | None`, `execution: Mapping[str, JsonValue] | None`, `groups: tuple[Mapping[str, JsonValue], ...]`, `gates: CoverageGates`
- `class Values` — Typed reads of loosely shaped JSON values.
  - `items(*, value: JsonValue | None) -> list[JsonValue]` — Return a JSON list, or an empty one.
  - `mapping(*, value: JsonValue | None) -> dict[str, JsonValue]` — Return a JSON object, or an empty one.
  - `number(*, value: JsonValue | None) -> float | None` — Return a JSON number as a float.
  - `count(*, value: JsonValue | None) -> int` — Return a JSON integer count.
  - `text(*, value: JsonValue | None) -> str` — Return a JSON string.
- `class Ranges` — Collapse line numbers into ranges.
  - `span_size` = `3`
  - `text(cls, *, ranges: Sequence[tuple[int, int]]) -> str` — Render ranges as ``3-5, 9, 12, 13``.
  - `collapse(*, lines: Sequence[int]) -> list[tuple[int, int]]` — Group sorted line numbers into contiguous ranges.
- `class CoverageTestsReport` — Compose the normalized blocks of the root report.
  - `test_findings(cls: type[Self], *, inputs: ReportInputs) -> list[dict[str, JsonValue]]` — Return details for failed, errored and skipped tests.
  - `coverage_findings(cls: type[Self], *, inputs: ReportInputs) -> list[dict[str, JsonValue]]` — Return one finding per unmet coverage gate.
  - `meaningful_findings(cls: type[Self], *, inputs: ReportInputs) -> list[dict[str, JsonValue]]` — Return blocking findings required by Meaningful enforcement.
  - `violation(cls: type[Self], *, rule: str, title: str, message: str, measured: float | None, required: float | None) -> dict[str, JsonValue]` — Return one project-wide coverage finding.
  - `per_file_findings(cls: type[Self], *, inputs: ReportInputs, files: Sequence[tuple[str, float, list[int]]]) -> list[dict[str, JsonValue]]` — Return one finding per file below the per-file minimum.
  - `tests_part(cls: type[Self], *, inputs: ReportInputs) -> dict[str, JsonValue]` — Return the tests part gate.
  - `coverage_part(cls: type[Self], *, inputs: ReportInputs, findings: Sequence[Mapping[str, JsonValue]]) -> dict[str, JsonValue]` — Return the coverage part gate.
  - `coverage_block(cls: type[Self], *, inputs: ReportInputs, part: Mapping[str, JsonValue], findings: Sequence[Mapping[str, JsonValue]]) -> dict[str, JsonValue]` — Return the coverage summary of ``extension``.
  - `tests_block(cls: type[Self], *, inputs: ReportInputs, part: Mapping[str, JsonValue]) -> dict[str, JsonValue]` — Return the tests summary of ``extension``.
  - `report_data(cls: type[Self], *, inputs: ReportInputs) -> dict[str, JsonValue]` — Return the normalized blocks of the root report.
  - `write(cls: type[Self], *, inputs: ReportInputs, output: Path, legacy: Mapping[str, JsonValue]) -> None` — Write the root report bundle.
  - `assertion_diff(*, message: str) -> dict[str, JsonValue] | None` — Decode quoted assertion values for readable report code blocks.
  - `stable_id(*, prefix: str, parts: Sequence[str]) -> str` — Return an identifier that is stable across runs.
  - `percent(*, value: float | None) -> str` — Format a percentage for reasons and messages.
  - `file_percents(*, coverage: Mapping[str, JsonValue]) -> list[tuple[str, float, list[int]]]` — List every measured Python file with its coverage.
  - `javascript_percents(*, javascript: Mapping[str, JsonValue]) -> list[tuple[str, float, list[int]]]` — List measured JavaScript files with their uncovered source lines.
  - `percent_key(item: tuple[str, float, list[int]]) -> tuple[float, str]` — Sort key: lowest coverage first, then path.
  - `outcomes(*, inputs: ReportInputs) -> dict[str, int]` — Count pytest outcomes.
  - `gate(*, coverage: Mapping[str, JsonValue], tests: Mapping[str, JsonValue]) -> dict[str, JsonValue]` — Combine the tests and coverage gates into the report gate.
  - `scope(*, inputs: ReportInputs) -> dict[str, JsonValue]` — Return the ``scope`` block.

### `skip_plugin.py`

Preserve pytest skip identities and capture per-file execution timings.

- `class Constants` — Group module-level constants.
  - `skip_fields` = `3`
- `pytest_addoption(parser: Parser) -> None` — Register Exactus-internal pytest options.
- `pytest_terminal_summary(terminalreporter: TerminalReporter) -> None` — Emit structured skip records and optional timing telemetry.

### `tracebacks.py`

Locate where and why each failing test failed.

- `class Constants` — Group module-level constants.
  - `foreign_parts` = `frozenset({'site-packages', 'dist-packages', 'node_modules', '.venv', 've...`
- `class FailureSite` — Where and why one test failed.
  - Fields: `path: str | None`, `line: int | None`, `reason: str`
- `class NamedFailure` — One failing JavaScript test with its location and reason.
  - Fields: `name: str`, `site: FailureSite`
- `class ProjectPaths` — Map frame paths printed by test runners to project files.
  - `relative(*, root: Path, path: str) -> str | None` — Return a frame path relative to the project root.
- `class PytestTracebacks` — Read failing locations and reasons from pytest's terminal output.
  - `BANNER` = `recompile(pattern='^={3,} (?P<name>.+?) ={3,}$')`
  - `SECTION` = `recompile(pattern='^_{2,} (?P<title>.+?) _{2,}$')`
  - `CAPTURE` = `recompile(pattern='^-{3,} .+ -{3,}$')`
  - `LOCATION` = `recompile(pattern='^(?P<path>[^\\s:>][^:]*?):(?P<line>\\d+):(?: (?P<rest>...`
  - `NATIVE` = `recompile(pattern='^\\s*File "(?P<path>[^"]+)", line (?P<line>\\d+)')`
  - `ERROR` = `recompile(pattern='^E(?:\\s+(?P<text>.*))?$')`
  - `EXCEPTION` = `recompile(pattern='^[A-Za-z_][\\w.]*$')`
  - `BLOCKS` = `{'FAILURES': 'FAILED', 'ERRORS': 'ERROR'}`
  - `sections(cls, *, text: str) -> list[tuple[str, str, list[str]]]` — Split pytest output into failure sections.
  - `site(cls, *, lines: Sequence[str], root: Path) -> FailureSite` — Read the location and reason of one failure section.
  - `sites(cls, *, text: str, root: Path, entries: Sequence[tuple[str, str]]) -> tuple[FailureSite | None, ...]` — Locate every short-summary entry in its traceback section.
  - `titles(*, kind: str, node: str) -> tuple[str, ...]` — Return the section titles pytest prints for one summary entry.
  - `reason(*, errors: Sequence[str], exception: str | None) -> str` — Compose the first-line reason of one failure.
- `class NodeTestFailures` — Read failing tests from the Node test runner's ``spec`` output.
  - `BANNER` = `'✖ failing tests:'`
  - `TEST_AT` = `recompile(pattern='^test at (?P<path>.+?):(?P<line>\\d+):\\d+$')`
  - `NAME` = `recompile(pattern='^✖ (?P<name>.+?)(?: \\([\\d.]+m?s\\))?$')`
  - `FRAME` = `recompile(pattern='^\\s+at (?:.*?\\()?(?P<path>[^()\\s]+?):(?P<line>\\d+)...`
  - `entry(cls, *, lines: Sequence[str], root: Path) -> NamedFailure | None` — Read one failing-test entry.
  - `parse(cls, *, text: str, root: Path) -> tuple[NamedFailure, ...]` — Read every failing test of one Node test-runner run.
  - `frame_path(*, root: Path, raw: str) -> str | None` — Map a printed frame or test path to a project file.

## Dependencies and consumers

- Other packages: [`meaningful`](../../packages/meaningful/DOCS.md), [`project_python`](../../packages/project_python/DOCS.md), [`steps`](../../packages/steps/DOCS.md), [`common`](../common/DOCS.md), [`reports`](../reports/DOCS.md)
- Used by: `__main__.py`, `tests/tools/common/test_config_integration.py`, `tests/tools/common/test_context_lines.py`, `tests/tools/coverage_tests/test_assertion_report.py`, `tests/tools/coverage_tests/test_core_boundaries.py`, `tests/tools/coverage_tests/test_coverage_tool.py`, `tests/tools/coverage_tests/test_coverage_validator.py`, `tests/tools/coverage_tests/test_javascript_gate.py`, `tests/tools/coverage_tests/test_meaningful.py`, `tests/tools/coverage_tests/test_report_layout.py`, `tests/tools/coverage_tests/test_skipped_report.py`, `tests/tools/coverage_tests/test_steps_trace.py`, `tests/tools/coverage_tests/test_test_group_name.py`, `tests/tools/coverage_tests/test_tracebacks.py`

## Tests

Tests live in `exactus/tests/tools/coverage_tests/`.

- `test_assertion_report.py` — Report quoted assertion values as readable multiline evidence. (3 tests)
  - `test_expected_actual_decodes_quotes_and_newlines`
  - `test_missing_content_decodes_actual_markdown`
  - `test_unstructured_assertion_is_preserved`
- `test_core_boundaries.py` — Exercise the standalone coverage CLI and malformed browser evidence. (15 tests)
  - `test_child_environment_drops_live_coordination`
  - `test_collection_progress_cannot_overtake_test_execution`
  - `test_discovery_prunes_outputs_but_keeps_nested_test_groups`
  - `test_empty_and_missing_javascript_sources`
  - `test_file_shards_are_balanced_without_duplicate_collection`
  - `test_invalid_v8_ranges_are_ignored`
  - `test_node_collection_uses_exact_pytest_ids`
  - `test_node_shards_isolate_standalone_packages`
  - `test_node_shards_split_large_test_modules`
  - `test_package_meta_tests_require_an_exclusive_shard`
  - `test_project_root_boundaries`
  - `test_source_excludes_drop_measured_javascript`
  - `test_source_excludes_drop_measured_python_files`
  - `test_standalone_cli_options`
  - `test_standalone_main_preserves_exit_status`
- `test_coverage_tool.py` — In-process coverage-tests runs over the demo and a tiny project. (21 tests)
  - `test_combined_tests_report_lists_failures_with_reasons`
  - `test_context_lines_option`
  - `test_demo_combined_coverage`
  - `test_demo_flag_variants`
  - `test_excuse_shortfalls_filters_javascript_below_minimum`
  - `test_file_snippets_embed_context`
  - `test_file_snippets_skips_unhighlightable`
  - `test_file_snippets_zero_and_negative_context`
  - `test_generated_skip_plugin_is_a_regular_package`
  - `test_group_reports_do_not_inherit_other_group_failures`
  - `test_owned_source_root_is_not_omitted_by_directory_name`
  - `test_package_does_not_shadow_third_party_coverage`
  - `test_parse_args_defaults`
  - `test_per_file_gates_fail`
  - `test_playwright_greenlet_body_is_measured`
  - `test_production_conftest_is_measured`
  - `test_project_without_tests`
  - `test_skip_plugin_preserves_project_imports`
  - `test_tiny_project_output_tree`
  - `test_unmet_gates_fail`
  - `test_v8_offsets_after_astral_unicode_keep_the_correct_line`
- `test_coverage_validator.py` — Coverage evidence validation and per-file floors. (6 tests)
  - `test_fail_raises`
  - `test_floors`
  - `test_invalid_evidence`
  - `test_missing_files_rejected`
  - `test_valid_evidence`
  - `test_validate_writes_verdict`
- `test_javascript_gate.py` — Gate JavaScript coverage while preserving passing test results. (4 tests)
  - `test_javascript_gates_are_reported_as_coverage_findings`
  - `test_javascript_only_project_runs_tests_and_fails_low_coverage`
  - `test_package_named_javascript_sources_are_measured`
  - `test_unavailable_javascript_runtime_keeps_distinct_reason`
- `test_meaningful.py` — Meaningful classification, configuration, and coverage integration. (16 tests)
  - `test_adapter_applies_unclassified_policy`
  - `test_adapter_preserves_successes_and_failures`
  - `test_adapter_respects_configured_level_boundary`
  - `test_include_unreached_counts_filtered_sources_without_findings`
  - `test_meaningful_detects_javascript_not_covered_by_tests`
  - `test_meaningful_parser_accepts_all_control_families`
  - `test_meaningful_parser_defaults_and_complete_policy`
  - `test_meaningful_parser_rejects_invalid_policy_values`
  - `test_meaningful_pyproject_and_cli_precedence`
  - `test_merge_results_combines_rows_and_counts`
  - `test_non_enforcing_modes_preserve_previous_omission`
  - `test_require_counts_unreached_source_at_zero`
  - `test_shortfall_actionable_keeps_per_file_finding`
  - `test_shortfall_excused_below_minimum_level`
  - `test_shortfall_gate_only_excused_when_meaningful_runs`
  - `test_shortfall_rows_carry_origin_and_reason`
- `test_report_layout.py` — Coverage reports distinguish branch measurements and focus on failures. (2 tests)
  - `test_coverage_report_keeps_failure_details_out_of_summary_tables`
  - `test_ranges_text_compacts_only_runs_of_three`
- `test_skipped_report.py` — Preserve skipped test evidence without turning skips into failures. (4 tests)
  - `test_skip_plugin_ignores_missing_timings_option`
  - `test_skip_plugin_preserves_parameter_ids_and_source`
  - `test_skip_plugin_records_real_pytest_summary`
  - `test_skip_plugin_skips_malformed_reports_and_writes_timings`
- `test_steps_trace.py` — Steps debug trace coverage for the coverage-tests tool chain. (6 tests)
  - `test_main_writes_steps_artifact`
  - `test_meaningful_bridge_traces`
  - `test_meaningful_mode_off_traces`
  - `test_packaged_meaningful_traces_lifecycle`
  - `test_progress_snapshots_are_traced`
  - `test_write_false_suppresses_steps_artifact`
- `test_test_group_name.py` — Test paths map to stable TESTS report group names. (1 tests)
  - `test_test_group_name`
- `test_tracebacks.py` — Tests for traceback and failure parsing helpers. (28 tests)
  - `test_entry_prefers_first_project_frame`
  - `test_entry_reads_name_reason_and_frame`
  - `test_entry_returns_none_without_test_at`
  - `test_entry_uses_test_location_when_no_project_frame`
  - `test_frame_path_handles_file_urls`
  - `test_frame_path_handles_plain_paths`
  - `test_parse_collects_multiple_failures`
  - `test_parse_returns_empty_when_no_banner`
  - `test_reason_falls_back_to_exception_only`
  - `test_reason_prefers_error_line`
  - `test_reason_prepends_exception_when_not_in_error`
  - `test_reason_returns_empty_when_nothing_is_known`
  - `test_relative_accepts_root_relative_path`
  - `test_relative_rejects_foreign_parts`
  - `test_relative_rejects_foreign_parts_for_existing_file`
  - `test_relative_rejects_non_file`
  - `test_relative_rejects_outside_root`
  - `test_relative_returns_none_for_unresolvable_path`
  - `test_relative_returns_posix_path_for_project_file`
  - `test_sections_split_failure_and_error_blocks`
  - `test_site_picks_deepest_project_frame`
  - `test_site_skips_unmatched_lines`
  - `test_site_stops_at_capture_heading`
  - `test_sites_matches_and_pops_sections_in_order`
  - `test_sites_returns_none_for_missing_section`
  - `test_titles_for_collection_error`
  - `test_titles_for_error_node`
  - `test_titles_for_failed_node`

<!-- exactus:reference:end -->
