# Meaningful

`exactus.packages.meaningful` is a Python-first semantic analyzer that estimates how
strongly each Python source file warrants dedicated tests. The CLI is a thin
adapter over the same object-oriented Python API and data model.

## Python API

The canonical entry point is `Meaningful`. It accepts one `str`/`Path`, a
sequence containing either type, directories, and recursive glob selectors.
`include` intersects the candidate set and `exclude` subtracts from it.

```python
from pathlib import Path
from exactus.packages.meaningful import Meaningful, ProgressSnapshot

updates: list[ProgressSnapshot] = []
analyzer: Meaningful = Meaningful(
    max_workers=8,
    on_progress=updates.append,
)
run = analyzer.analyze(
    paths=[Path("exactus/packages"), "scripts/**/*.py"],
    include=("**/*.py",),
    exclude=("**/generated/**", "**/fixtures/**"),
)
```

`analyze()` returns an immutable `AnalysisRun`, not an unstructured mapping.
Its `findings`, `failures`, and `metadata` fields are strongly typed frozen
slot dataclasses. `classify()` remains a convenience method that returns only
successful `FileFinding` objects and raises when a worker failed.

## Parallel execution

Independent files are analyzed by a bounded `ThreadPoolExecutor`. The default
worker count is `min(32, cpu_count + 4, file_count)`. Set `max_workers` on the
`Meaningful` instance or override it per `analyze()` call. `1` gives serial
execution. Final findings and failures are always path-sorted, so parallel
completion order never changes the final result.

The implementation parallelizes the unit that is actually independent: one
source file. Selector resolution and final aggregation remain deterministic
coordinator operations.

## Progress callback

Register `on_progress` on the analyzer or per run. It is invoked exactly once
after every finished worker, including failed workers:

```python
from exactus.packages.meaningful import ProgressSnapshot


def update(progress: ProgressSnapshot) -> None:
    # progress.percent is 0..100.
    # progress.completed == progress.succeeded + progress.failed.
    ...


run = Meaningful(on_progress=update).analyze(paths="exactus/packages")
```

`ProgressSnapshot` contains:

- `total`, `completed`, `succeeded`, `failed`, and `remaining`;
- `percent` completion;
- `current_path` and the completed file's `current_level` when successful;
- elapsed seconds;
- files per second;
- estimated remaining seconds when throughput is measurable.

Callback exceptions are isolated. A UI, logger, or telemetry observer cannot
abort or mutate the analysis run.

## Run and file metadata

`RunMetadata` records UTC start/end timestamps, total/resolution/analysis
execution times, requested and effective worker counts, file success/failure
counts, aggregate bytes and source lines, counts for TEST-0 through TEST-3,
Python version, platform, and working directory.

Every `FileFinding` includes `FileMetadata`: source byte/line counts, UTC
worker start/end timestamps, worker duration, and worker thread name.
`FileFailure` retains path, exception type/message, and worker-side duration.
Failures therefore remain visible in both progress and final accounting.

## Strong finding model

A `FileFinding` contains:

- `path`, `level`, and semantic `category`;
- all three normalized `PromotionScores`;
- unit-test, execution, and branch-coverage requirements;
- human-readable reasons;
- objective AST `Metrics`;
- final-level `FindingEvidence` records;
- per-file execution/source metadata.

Evidence is emitted only for the highest level reached. Each evidence record
contains category, reason, exact AST line range, context range, and structured
`SourceLine` records. Source lines identify whether each line is highlighted.
Context defaults to two lines before and after and is configurable with
`EvaluationPolicy(evidence_context=N)` or `analyze(evidence_context=N)`.

## Evaluation policy

Measurement and policy are separate. `EvaluationPolicy` contains immutable
`PromotionThresholds`, `FeatureWeights`, `FeatureCaps`, `PromotionFloors`, and
evidence context. This lets applications tune importance without replacing AST
measurement.

The default adjacent promotion thresholds are 0.25, 0.50, and 0.70 for
TEST-0→1, TEST-1→2, and TEST-2→3. Each value must be within 0..1. A threshold
of zero means promote on any *positive* evidence; zero-evidence structural
modules remain TEST-0.

Filename is not the primary signal. Large ordinary modules, public behavioral
surfaces, computations, branching, state mutation, side effects, exception
paths, import-time behavior, nesting, and source size can independently make a
normal module important enough for TEST-2 or TEST-3.

## CLI

```text
python -m exactus.packages.meaningful PATH [PATH ...]
    [--include PATH_OR_GLOB]
    [--exclude PATH_OR_GLOB]
    [--threshold-test-0-to-1 0..1]
    [--threshold-test-1-to-2 0..1]
    [--threshold-test-2-to-3 0..1]
    [--evidence-context N]
    [--workers N]
    [--output-file FILE]
```

Without `--output-file`, the complete `AnalysisRun` is serialized as JSON to
stdout. The output includes findings, failures, evidence, per-file metadata,
and aggregate run metadata.

## Executable examples

The API and CLI examples are available under
`exactus/packages/meaningful/examples/api` and `exactus/packages/meaningful/examples/cli`. Each can
run as its `run.py`, as an executable example directory where supported, or
through Python module execution. The API example demonstrates parallelism,
progress callbacks, metadata, selectors, and the policy model.

## Testing

The Python suite covers the semantic analyzer, policy engine, strong models,
parallel coordinator, progress accounting, failures, resolver, CLI, and
examples. The Node suite exercises the CLI as a black-box subprocess and
validates the serialized run contract.

## Exactus `coverage_tests` integration

`meaningful` is an unreached-source filter. Exactus discovers source files that
no test reaches and passes only that candidate set to `Meaningful.analyze()`.
The analyzer does not interpret line coverage, branch coverage, coverage
percentages, or test outcomes. Once a source has been reached by tests,
`meaningful` has no further responsibility for that source.

Each successful `FileFinding` exposes `should_be_visited`. `TEST-2` and
`TEST-3` decisions are retained as actionable unreached sources; `TEST-0` and
`TEST-1` decisions are available through `AnalysisRun.filtered` so the Exactus
report can explain why they were removed. `AnalysisRun.should_be_visited`
returns the retained set directly.

Every decision contains an ordered `decision_tree`. Its `DecisionNode` records
the stable rule, question, score, threshold, input/output levels, outcome, and
the IDs of the `FindingEvidence` records that support that promotion. The tree
is created by the same policy evaluation that produces the final level; it is
not reconstructed afterward. Evidence contains a stable ID, semantic category,
reason, exact source range, and source context (two surrounding lines by
default).

Live progress is delivered through `ProgressSnapshot`. Successful files emit
`FILE_STARTED`, `FAST_SCAN`, `EVIDENCE`, and `DECISION` stages. Snapshots expose
total/completed/remaining counts, kept/filtered/failed counts, completion
percentage, current file and level, evidence count, elapsed time, throughput,
and ETA. Exactus can throttle terminal rendering without losing the structured
progress stream.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Public API for meaningful Python test-necessity analysis. |
| `__main__.py` | Execute the meaningful command-line interface. |
| `analyzer.py` | Analyze Python source semantics to estimate test necessity. |
| `api.py` | Primary object-oriented Python API for meaningful analysis. |
| `cli.py` | Thin command-line adapter over the canonical Python API. |
| `engine.py` | Policy evaluation and source evidence for meaningful findings. |
| `examples/` | Runnable demonstration for `exactus/packages/meaningful/`. |
| `models.py` | Strong immutable data model for meaningful analysis runs. |

Run it as a module: `python -m exactus.packages.meaningful`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `paths` |  | nargs='+' |
| `--include` |  | action='append', default=[] |
| `--exclude` |  | action='append', default=[] |
| `--threshold-test-0-to-1` |  | type=float, default=0.25 |
| `--threshold-test-1-to-2` |  | type=float, default=0.5 |
| `--threshold-test-2-to-3` |  | type=float, default=0.7 |
| `--evidence-context` |  | type=int, default=2 |
| `--workers` |  | type=int |
| `--output-file` |  | type=Path |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Public API for meaningful Python test-necessity analysis.


### `__main__.py`

Execute the meaningful command-line interface.


### `analyzer.py`

Analyze Python source semantics to estimate test necessity.

- `class Constants` — Group module-level constants.
  - `side_effect_names` = `frozenset({'input', 'open', 'print', 'datetime.date.today', 'datetime.dat...`
  - `side_effect_attributes` = `frozenset({'chmod', 'commit', 'connect', 'execute', 'executemany', 'hardl...`
  - `side_effect_prefixes` = `frozenset({'httpx.', 'requests.', 'socket.', 'urllib.request.'})`
  - `external_state_names` = `frozenset({'os.environ', 'sys.argv'})`
  - `mutation_names` = `frozenset({'delattr', 'setattr'})`
  - `mutation_attributes` = `frozenset({'add', 'append', 'clear', 'discard', 'extend', 'insert', 'pop'...`
  - `static_declaration_calls` = `frozenset({'dataclasses.field', 'enum.auto', 'frozenset', 'pathlib.Path',...`
  - `computation_calls` = `frozenset({'abs', 'all', 'any', 'bool', 'bytes', 'dict', 'float', 'int',...`
  - `usage` = `'Usage: python_test_need.py FILE.py [--json]\n'`
  - `default_threshold` = `12`
  - `complex_cyclomatic_threshold` = `6`
  - `complex_nesting_threshold` = `3`
  - `complex_public_members_threshold` = `4`
  - `max_nesting_score` = `3`
  - `multi_call_behavior_threshold` = `2`
  - `multi_statement_behavior_threshold` = `2`
- `class UnitTestLevel` — Available test-necessity classifications.
  - `TEST_0` = `'TEST-0'`
  - `TEST_1` = `'TEST-1'`
  - `TEST_2` = `'TEST-2'`
  - `TEST_3` = `'TEST-3'`
- `class Category` — Semantic categories corresponding to the test levels.
  - `STRUCTURAL` = `'structural'`
  - `TRIVIAL` = `'trivial'`
  - `BEHAVIORAL` = `'behavioral'`
  - `COMPLEX` = `'complex'`
- `class MetricsJson` — JSON representation of classification metrics.
  - Fields: `cyclomatic_complexity: int`, `branches: int`, `loops: int`, `exception_handlers: int`, `raises: int`, `boolean_decisions: int`, `comprehension_decisions: int`, `computations: int`, `side_effects: int`, `mutations: int`, `behavioral_statements: int`, `runtime_calls: int`, `substantive_callables: int`, `trivial_callables: int`, `public_behavioral_members: int`, `module_runtime_statements: int`, `max_control_nesting: int`
- `class ClassificationJson` — JSON representation of a complete classification.
  - Fields: `path: str`, `level: str`, `category: str`, `score: int`, `requires_unit_tests: bool`, `requires_execution: bool`, `requires_branch_coverage: bool`, `reasons: list[str]`, `metrics: MetricsJson`
- `class Metrics` — Measured behavioral properties of one Python module.
  - Fields: `cyclomatic_complexity: int`, `branches: int`, `loops: int`, `exception_handlers: int`, `raises: int`, `boolean_decisions: int`, `comprehension_decisions: int`, `computations: int`, `side_effects: int`, `mutations: int`, `behavioral_statements: int`, `runtime_calls: int`, `substantive_callables: int`, `trivial_callables: int`, `public_behavioral_members: int`, `module_runtime_statements: int`, `max_control_nesting: int`
  - `to_json(self) -> MetricsJson` — Return a JSON-compatible metric mapping.
- `class Classification` — Test recommendation and evidence for one Python module.
  - Fields: `path: Path`, `level: UnitTestLevel`, `category: Category`, `score: int`, `requires_unit_tests: bool`, `requires_execution: bool`, `requires_branch_coverage: bool`, `reasons: tuple[str, ...]`, `metrics: Metrics`
  - `to_json(self) -> ClassificationJson` — Return the classification in a stable JSON-compatible shape.
  - `render(self) -> str` — Render a compact human-readable report.
- `class PythonTestNeedClassifier` — Classify one Python file from its syntax and observable behavior.
  - `__init__(self, *, path: Path, threshold: int=Constants.default_threshold) -> None` — Load and parse a Python source file.
  - `classify(self) -> Classification` — Measure the file and derive its test-necessity classification.

### `api.py`

Primary object-oriented Python API for meaningful analysis.

- `class AnalyzeOptions` — Optional controls accepted by :meth:`Meaningful.analyze`.
  - Fields: `include: NotRequired[Sequence[PathInput]]`, `exclude: NotRequired[Sequence[PathInput]]`, `policy: NotRequired[EvaluationPolicy | None]`, `max_workers: NotRequired[int | None]`, `on_progress: NotRequired[ProgressCallback | None]`, `evidence_context: NotRequired[int | None]`
- `class Meaningful` — Resolve and analyze Python and JavaScript sources in bounded workers.
  - `__init__(self, *, policy: EvaluationPolicy | None=None, max_workers: int | None=None, on_progress: ProgressCallback | None=None) -> None` — Configure a reusable analyzer.
  - `resolve(cls, *, paths: PathInputs, include: Sequence[PathInput]=(), exclude: Sequence[PathInput]=()) -> tuple[Path, ...]` — Resolve selectors into a unique sorted tuple of Python files.
  - `analyze(self, *, paths: PathInputs, **options: Unpack[AnalyzeOptions]) -> AnalysisRun` — Analyze selected files and return a complete immutable run model.
  - `classify(self, *, paths: PathInputs, include: Sequence[PathInput]=(), exclude: Sequence[PathInput]=(), policy: EvaluationPolicy | None=None) -> tuple[FileFinding, ...]` — Compatibility convenience returning successful findings only.
- `analyze(*, paths: PathInputs, **options: Unpack[AnalyzeOptions]) -> AnalysisRun` — Analyze sources through the functional convenience API.
- `classify(*, paths: PathInputs, include: Sequence[PathInput]=(), exclude: Sequence[PathInput]=(), policy: EvaluationPolicy | None=None) -> tuple[FileFinding, ...]` — Return successful findings through the compatibility API.

### `cli.py`

Thin command-line adapter over the canonical Python API.

- `class MeaningfulCli` — Parse CLI selectors and serialize the Python API run model.
  - `run(cls, *, arguments: Sequence[str] | None=None) -> int` — Run analysis and emit the complete run model as JSON.
  - `parser() -> ArgumentParser` — Build the command-line parser.
- `main(*, arguments: Sequence[str] | None=None) -> None` — Run the CLI and terminate with its exit status.

### `engine.py`

Policy evaluation and source evidence for meaningful findings.

- `class PolicyEvaluator` — Convert objective metrics into normalized promotion decisions.
  - `COMPLEXITY_FLOOR` = `6`
  - `NESTING_FLOOR` = `3`
  - `__init__(self, *, policy: EvaluationPolicy) -> None` — Store the immutable evaluation policy.
  - `category(*, level: UnitTestLevel) -> Category` — Map test level to semantic category.
  - `scores(self, *, metrics: Metrics, source_lines: int) -> PromotionScores` — Calculate independent normalized promotion evidence scores.
  - `level(self, *, scores: PromotionScores) -> UnitTestLevel` — Apply thresholds while preserving zero-evidence TEST-0.
  - `decisions(self, *, scores: PromotionScores, evidence: tuple[FindingEvidence, ...]) -> tuple[DecisionNode, ...]` — Return the exact adjacent-promotion decisions used by the policy.
- `class EvidenceCollector` — Collect representative source evidence for the final finding level.
  - `MAX_EVIDENCE` = `5`
  - `__init__(self, *, path: Path, context: int) -> None` — Read and parse the source once for evidence extraction.
  - `collect(self, *, level: UnitTestLevel) -> tuple[FindingEvidence, ...]` — Return evidence only for the highest level reached.
- `baseline_metrics(*, path: Path) -> Metrics` — Measure a source with the established AST analyzer.
- `javascript_metrics(*, path: Path) -> Metrics` — Measure conservative behavioral signals in JavaScript source.
- `javascript_evidence(*, path: Path, context: int, level: UnitTestLevel) -> tuple[FindingEvidence, ...]` — Collect source-backed evidence for a JavaScript classification.

### `examples/__init__.py`

Executable examples for meaningful.


### `examples/__main__.py`

Run the meaningful example with the project virtual environment.


### `examples/api/__init__.py`

Executable meaningful api example package.


### `examples/api/__main__.py`

Execute the meaningful Python API example package.


### `examples/api/run.py`

Comprehensive executable example of the meaningful Python API.

- `class ApiExample` — Demonstrate analysis, parallelism, metadata, and progress callbacks.
  - `run() -> None` — Analyze the package and print concise run information.

### `examples/cli/__init__.py`

Executable meaningful cli example package.


### `examples/cli/__main__.py`

Execute the meaningful CLI example package.


### `examples/cli/run.py`

Executable example of the thin meaningful CLI adapter.

- `class CliExample` — Demonstrate selectors, policy thresholds, and worker control.
  - `run() -> int` — Run a representative CLI request.

### `examples/run.py`

Run both public meaningful demonstrations.

- `main() -> int` — Execute the API example followed by the CLI example.

### `models.py`

Strong immutable data model for meaningful analysis runs.

- `class PromotionThresholds` — Thresholds required to cross each adjacent test level.
  - `test_0_to_1` = `0.25`
  - `test_1_to_2` = `0.5`
  - `test_2_to_3` = `0.7`
- `class FeatureWeights` — Relative importance of measured semantic features.
  - `behavior` = `1.0`
  - `public_surface` = `1.1`
  - `side_effects` = `1.4`
  - `mutations` = `1.3`
  - `decisions` = `1.2`
  - `errors` = `1.3`
  - `computations` = `0.8`
  - `size` = `0.9`
  - `nesting` = `1.0`
- `class FeatureCaps` — Saturation caps used to normalize raw measurements.
  - `behavioral_statements` = `30`
  - `public_members` = `10`
  - `side_effects` = `5`
  - `mutations` = `5`
  - `decisions` = `12`
  - `errors` = `5`
  - `computations` = `40`
  - `source_lines` = `300`
  - `nesting` = `5`
- `class PromotionFloors` — Minimum risk scores for semantically important behavior.
  - `side_effect_test_1_to_2` = `0.7`
  - `mutation_test_1_to_2` = `0.65`
  - `error_test_1_to_2` = `0.7`
  - `import_runtime_test_1_to_2` = `0.65`
  - `high_complexity_test_2_to_3` = `0.75`
- `class EvaluationPolicy` — Complete policy controlling semantic promotion decisions.
  - `thresholds` = `field(default_factory=PromotionThresholds)`
  - `weights` = `field(default_factory=FeatureWeights)`
  - `caps` = `field(default_factory=FeatureCaps)`
  - `floors` = `field(default_factory=PromotionFloors)`
  - `evidence_context` = `2`
- `class PromotionScores` — Normalized evidence available at each promotion boundary.
  - Fields: `test_0_to_1: float`, `test_1_to_2: float`, `test_2_to_3: float`
- `class SourceLine` — One source line included in evidence.
  - Fields: `line: int`, `text: str`, `highlighted: bool`
- `class FindingEvidence` — Source-backed evidence supporting the final classification level.
  - Fields: `id: str`, `category: str`, `reason: str`, `line: int`, `end_line: int`, `context_start_line: int`, `context_end_line: int`, `source: tuple[SourceLine, ...]`
- `class AnalysisStage` — Observable stages of one progressive file decision.
  - `FILE_STARTED` = `'file_started'`
  - `FAST_SCAN` = `'fast_scan'`
  - `EVIDENCE` = `'evidence'`
  - `DECISION` = `'decision'`
  - `FILE_FAILED` = `'file_failed'`
- `class DecisionNode` — One auditable rule application in the actual decision path.
  - Fields: `rule: str`, `question: str`, `outcome: bool`, `score: float`, `threshold: float`, `level_before: UnitTestLevel`, `level_after: UnitTestLevel`, `evidence_ids: tuple[str, ...]`
- `class FileMetadata` — Execution and source metadata for one analyzed file.
  - Fields: `size_bytes: int`, `source_lines: int`, `started_at: datetime`, `finished_at: datetime`, `duration_seconds: float`, `worker_name: str`
- `class FileFinding` — Complete strongly typed finding for one Python source file.
  - Fields: `path: Path`, `level: UnitTestLevel`, `category: Category`, `scores: PromotionScores`, `should_be_visited: bool`, `decision_tree: tuple[DecisionNode, ...]`, `reasons: tuple[str, ...]`, `metrics: Metrics`, `evidence: tuple[FindingEvidence, ...]`, `metadata: FileMetadata`
- `class FileFailure` — Failure produced by one completed analysis worker.
  - Fields: `path: Path`, `error_type: str`, `message: str`, `duration_seconds: float`
- `class ProgressSnapshot` — Immutable progress state emitted after every finished worker.
  - Fields: `total: int`, `completed: int`, `succeeded: int`, `kept: int`, `filtered: int`, `failed: int`, `remaining: int`, `percent: float`, `current_path: Path`, `current_level: UnitTestLevel | None`, `stage: AnalysisStage`, `evidence_count: int`, `elapsed_seconds: float`, `files_per_second: float`, `estimated_remaining_seconds: float | None`
- `class RunMetadata` — Aggregate metadata describing a complete analysis run.
  - Fields: `started_at: datetime`, `finished_at: datetime`, `duration_seconds: float`, `resolution_seconds: float`, `analysis_seconds: float`, `requested_workers: int | None`, `workers_used: int`, `total_files: int`, `succeeded: int`, `failed: int`, `kept: int`, `filtered: int`, `total_bytes: int`, `total_source_lines: int`, `test_0: int`, `test_1: int`, `test_2: int`, `test_3: int`, `python_version: str`, `platform: str`, `working_directory: Path`
- `class ProgressState` — Inputs required to derive one progress snapshot.
  - Fields: `total: int`, `completed: int`, `succeeded: int`, `kept: int`, `filtered: int`, `failed: int`, `current_path: Path`, `current_level: UnitTestLevel | None`, `stage: AnalysisStage`, `evidence_count: int`, `started: float`
- `class RunTiming` — Timing and worker inputs used to aggregate run metadata.
  - Fields: `started_at: datetime`, `finished_at: datetime`, `duration_seconds: float`, `resolution_seconds: float`, `analysis_seconds: float`, `requested_workers: int | None`, `workers_used: int`
- `class AnalysisRun` — Complete result of one Python API analysis invocation.
  - Fields: `findings: tuple[FileFinding, ...]`, `failures: tuple[FileFailure, ...]`, `metadata: RunMetadata`
  - `should_be_visited(self) -> tuple[FileFinding, ...]` — Return unreached sources that must remain actionable.
  - `filtered(self) -> tuple[FileFinding, ...]` — Return unreached sources safely filtered from coverage findings.

## Examples

Runnable demonstration for `exactus/packages/meaningful/`.

Run both public meaningful demonstrations.

```bash
python -m exactus.packages.meaningful.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/api/README.md`, `examples/api/__init__.py`, `examples/api/__main__.py`, `examples/api/run.py`, `examples/cli/README.md`, `examples/cli/__init__.py`, `examples/cli/__main__.py`, `examples/cli/run.py`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md), [`steps`](../steps/DOCS.md), [`common`](../../tools/common/DOCS.md)
- Used by: `tests/packages/meaningful/test_analyzer.py`, `tests/packages/meaningful/test_api_cli.py`, `tests/packages/meaningful/test_example_run.py`, `tests/tools/coverage_tests/test_coverage_tool.py`, `tests/tools/coverage_tests/test_meaningful.py`, `tests/tools/coverage_tests/test_steps_trace.py`, `tools/coverage_tests/arguments.py`, `tools/coverage_tests/main.py`, `tools/coverage_tests/meaningful.py`

## Tests

Tests live in `exactus/tests/packages/meaningful/`.

- `test_analyzer.py` — Behavioral tests for the single-file test-necessity classifier. (4 tests)
  - `test_classification_levels`
  - `test_metrics_json_and_render`
  - `test_non_python_file_is_rejected`
  - `test_syntax_error_is_preserved`
- `test_api_cli.py` — Tests for the object-oriented API, parallel runs, metadata, and CLI. (9 tests)
  - `test_cli_json_output_file_and_errors`
  - `test_examples_execute`
  - `test_failures_are_accounted_and_callback_isolated`
  - `test_functional_api_and_overrides`
  - `test_javascript_behavior_is_classified_as_needing_tests`
  - `test_parallel_run_metadata_and_progress`
  - `test_policy_thresholds_evidence_and_context`
  - `test_resolution_inputs_and_filters`
  - `test_validation_errors`
- `test_example_run.py` — Cover the bundled ``meaningful`` CLI example entry point. (1 tests)
  - `test_example_module_runs_as_a_script`
- `test_meaningful_sources.py` — Execute package entry points required by meaningful coverage policy. (3 tests)
  - `test_packages_cli_entrypoint`
  - `test_packages_support_module_executes`
  - `test_rename_project_entrypoint_bootstraps`

<!-- exactus:reference:end -->
