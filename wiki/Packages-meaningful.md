[Home](Home.md) > [Packages](Packages.md) > meaningful

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/meaningful/`](../exactus/packages/meaningful/) | [`exactus/tests/packages/meaningful/`](../exactus/tests/packages/meaningful/) | [`DOCS.md`](../exactus/docs/packages/meaningful/DOCS.md) |

[< Packages-markdown](Packages-markdown.md) · [Packages index](Packages.md) · [Packages-model >](Packages-model.md)
