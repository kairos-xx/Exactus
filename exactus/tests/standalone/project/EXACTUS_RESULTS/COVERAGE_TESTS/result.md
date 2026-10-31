# Coverage

**Run time:** 31 October 2026, 05:10:41 UTC

## Identity

| Field | Value |
|---|---|
| Tool | coverage_tests |
| Run ID | 2c65e21142f34f8db22b09b30d9044d1:coverage_tests |
| Pipeline run | 2c65e21142f34f8db22b09b30d9044d1 |
| Status | PASS |
| Exit code | 0 |
| Started | 31 October 2026, 05:10:41 UTC |
| Finished | 31 October 2026, 05:10:52 UTC |
| Duration | 10.8 s |
| Previous duration | 17.845s |

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
| Duration (s) | 4.073 |
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
| Previous duration | 17.845s | | |

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
/usr/local/bin/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=62347 --orchestrator-control-token=[redacted] --orchestrator-worker-port=62325 --orchestrator-worker-token=[redacted] '--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"coverage_tests","module":"exactus.tools.coverage_tests.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/COVERAGE_TESTS","arguments":[],"run_id":"2c65e21142f34f8db22b09b30d9044d1:coverage_tests","pipeline_run_id":"2c65e21142f34f8db22b09b30d9044d1","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}'
~~~~

| Property | Value |
|---|---|
| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| Arguments | `exactus.tools.common.tool_worker` `ExactusTool` `--orchestrator-control-port=62347` `--orchestrator-control-token=[redacted]` `--orchestrator-worker-port=62325` `--orchestrator-worker-token=[redacted]` `--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"coverage_tests","module":"exactus.tools.coverage_tests.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/COVERAGE_TESTS","arguments":[],"run_id":"2c65e21142f34f8db22b09b30d9044d1:coverage_tests","pipeline_run_id":"2c65e21142f34f8db22b09b30d9044d1","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}` |

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
| EXACTUS_PIPELINE_RUN_ID | 2c65e21142f34f8db22b09b30d9044d1 |
| EXACTUS_REGISTRY | [/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db](../.runtime/runs.db) |
| EXACTUS_ROOT | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| EXACTUS_RUN_ID | 2c65e21142f34f8db22b09b30d9044d1:coverage_tests |
| EXACTUS_TOOL | coverage_tests |
| LANG | en_US.UTF-8 |
| TERM | xterm-256color |

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
| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 2288 |
| completion.json | [ARTIFACTS/COVERAGE/completion.json](ARTIFACTS/COVERAGE/completion.json) | 1505 |
| coverage_raw_js.json | [ARTIFACTS/COVERAGE/coverage_raw_js.json](ARTIFACTS/COVERAGE/coverage_raw_js.json) | 688 |
| coverage_raw_py.json | [ARTIFACTS/COVERAGE/coverage_raw_py.json](ARTIFACTS/COVERAGE/coverage_raw_py.json) | 8328 |
| import_graph.json | [ARTIFACTS/COVERAGE/import_graph.json](ARTIFACTS/COVERAGE/import_graph.json) | 2788 |
| meaningful.json | [ARTIFACTS/COVERAGE/meaningful.json](ARTIFACTS/COVERAGE/meaningful.json) | 7269 |
| test-costs.json | [ARTIFACTS/COVERAGE/test-costs.json](ARTIFACTS/COVERAGE/test-costs.json) | 117 |
| validation.json | [ARTIFACTS/COVERAGE/validation.json](ARTIFACTS/COVERAGE/validation.json) | 234 |
| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |
| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 0 |
| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 6658 |

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

Exactus · coverage_tests · Run 2c65e21142f34f8db22b09b30d9044d1:coverage_tests · Result PASS · Duration 10.8 s
