# Coverage

**Run time:** 31 October 2026, 02:56:18 UTC

## Identity

| Field | Value |
|---|---|
| Tool | coverage_tests 0.5.0 |
| Run ID | f9656595c8b74d23b2b6aec3bd0db7de:coverage_tests |
| Pipeline run | f9656595c8b74d23b2b6aec3bd0db7de |
| Status | PASS |
| Exit code | 0 |
| Started | 31 October 2026, 02:56:18 UTC |
| Finished | 31 October 2026, 02:56:36 UTC |
| Duration | 17.8 s |
| Previous duration | 6.893s |

## What was checked

**Result: PASS** — 2 tests from 1 test file across 5 measured source files; Python coverage 100.0% (minimum 90.0%); 0 findings.

| Severity | Count |
|---|---:|
| ERROR | 0 |
| WARNING | 0 |
| INFO | 0 |

### Tests

| Metric | Value |
| --- | --- |
| Tests run | 2 |
| Passed | 2 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Expected failures (xfail) | 0 |
| Unexpected passes (xpass) | 0 |
| Duration (s) | 1.511 |
| Python test files | 1 |
| JavaScript test files | 1 |
| JavaScript failed tests | 0 |

### Coverage

| Language | Coverage | Measurement | Files |
|---|---:|---|---:|
| Python | 100.0% | Lines | 4 |
| JavaScript | 100.0% | Lines | 1 |

The Python gate includes branches when branch measurement is enabled. JavaScript measures executable lines.

### Change since previous report

| Metric | Current | Previous | Delta |
|---|---:|---:|---:|
| Findings | 0 | 0 | 0 |
| Previous duration | 6.893s | | |

| Finding change | Count |
|---|---:|
| Added | 0 |
| Resolved | 0 |
| Unchanged | 0 |

#### Category findings

| Category | Title | Findings | Previous | Delta |
| --- | --- | --- | --- | --- |
| coverage-average | Average file coverage | 0 | 0 | 0 |
| coverage-evidence | Coverage evidence validation | 0 | 0 | 0 |
| coverage-javascript-total | Overall JavaScript coverage | 0 | 0 | 0 |
| coverage-meaningful | Untested meaningful sources | 0 | 0 | 0 |
| coverage-meaningful-analysis | Meaningful analysis failures | 0 | 0 | 0 |
| coverage-per-file | Per-file coverage minimum | 0 | 0 | 0 |
| coverage-shortfall-excused | Excused sub-gate sources | 0 | 0 | 0 |
| coverage-total | Overall Python coverage | 0 | 0 | 0 |
| test-error | Errored tests | 0 | 0 | 0 |
| test-failure | Failed tests | 0 | 0 | 0 |


## Setup

### Invocation

~~~~shell
/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=60166 --orchestrator-control-token=[redacted] --orchestrator-worker-port=60128 --orchestrator-worker-token=[redacted] '--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"coverage_tests","module":"exactus.tools.coverage_tests.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/COVERAGE_TESTS","arguments":[],"run_id":"f9656595c8b74d23b2b6aec3bd0db7de:coverage_tests","pipeline_run_id":"f9656595c8b74d23b2b6aec3bd0db7de","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}'
~~~~

| Property | Value |
|---|---|
| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| Arguments | `exactus.tools.common.tool_worker` `ExactusTool` `--orchestrator-control-port=60166` `--orchestrator-control-token=[redacted]` `--orchestrator-worker-port=60128` `--orchestrator-worker-token=[redacted]` `--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"coverage_tests","module":"exactus.tools.coverage_tests.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/COVERAGE_TESTS","arguments":[],"run_id":"f9656595c8b74d23b2b6aec3bd0db7de:coverage_tests","pipeline_run_id":"f9656595c8b74d23b2b6aec3bd0db7de","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}` |

### Environment

| Property | Value |
|---|---|
| OS | Darwin 25.3.0 |
| Python | 3.13.9 |
| Node | v22.21.1 |
| CPU count | 18 |

| Variable | Value |
| --- | --- |
| EXACTUS_ORCHESTRATED | 1 |
| EXACTUS_PIPELINE_RUN_ID | f9656595c8b74d23b2b6aec3bd0db7de |
| EXACTUS_REGISTRY | [/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db](../.runtime/runs.db) |
| EXACTUS_ROOT | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| EXACTUS_RUN_ID | f9656595c8b74d23b2b6aec3bd0db7de:coverage_tests |
| EXACTUS_TOOL | coverage_tests |
| LANG | C.UTF-8 |

## Gate

> **Gate: PASS** — 2 of 2 tests passed; 1 JavaScript test file passed; Total 100.0% meets the 90.0% minimum; every file meets 80.0%

| Part | Status | Reason |
|---|---|---|
| Tests | PASS | 2 of 2 tests passed; 1 JavaScript test file passed |
| Coverage | PASS | Total 100.0% meets the 90.0% minimum; every file meets 80.0% |

### Coverage requirements

| Requirement | Minimum | Measured | Result |
| --- | --- | --- | --- |
| Total coverage | 90.0% | 100.0% | PASS |
| JavaScript total coverage | 90.0% | 100.0% | PASS |
| Per-file minimum | 80.0% | 0 of 5 files below | PASS |
| Untested meaningful sources | >= TEST-2 | 0 actionable, 0 analysis errors | PASS |
| Evidence check | complete, unchanged evidence | valid | PASS |

## Findings

### Failed tests — 0

No failed or errored tests.

### Coverage violations — 0

Every coverage gate is met.

## Evidence

| Artifact | Path | Bytes |
|---|---|---:|
| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 2287 |
| completion.json | [ARTIFACTS/COVERAGE/completion.json](ARTIFACTS/COVERAGE/completion.json) | 1505 |
| coverage_raw_js.json | [ARTIFACTS/COVERAGE/coverage_raw_js.json](ARTIFACTS/COVERAGE/coverage_raw_js.json) | 688 |
| coverage_raw_py.json | [ARTIFACTS/COVERAGE/coverage_raw_py.json](ARTIFACTS/COVERAGE/coverage_raw_py.json) | 8328 |
| import_graph.json | [ARTIFACTS/COVERAGE/import_graph.json](ARTIFACTS/COVERAGE/import_graph.json) | 2789 |
| meaningful.json | [ARTIFACTS/COVERAGE/meaningful.json](ARTIFACTS/COVERAGE/meaningful.json) | 7273 |
| test-costs.json | [ARTIFACTS/COVERAGE/test-costs.json](ARTIFACTS/COVERAGE/test-costs.json) | 117 |
| validation.json | [ARTIFACTS/COVERAGE/validation.json](ARTIFACTS/COVERAGE/validation.json) | 234 |
| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |
| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 0 |
| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 6652 |

## Test groups

One report per group of Python test files.

| Group | Files | Tests | Passed | Failed | Skipped | Report |
|---|---:|---:|---:|---:|---:|---|
| tests | 1 | 2 | 2 | 0 | 0 | [TESTS/tests/result.md](TESTS/tests/result.md) |

## Sub-reports

| Report | Path | Contents |
|---|---|---|
| Tests | [TESTS/result.md](TESTS/result.md) | Every test result, failed tests with reasons, shards and warnings |
| Coverage | [COVERAGE/result.md](COVERAGE/result.md) | Coverage per file with uncovered lines, the import graph and the JavaScript lane |

---

Exactus · coverage_tests 0.5.0 · Run f9656595c8b74d23b2b6aec3bd0db7de:coverage_tests · Result PASS · Duration 17.8 s
