# README Exactus

**Run time:** 04 November 2026, 07:55:49 UTC

## Identity

| Field | Value |
|---|---|
| Tool | readme 0.7.1 |
| Run ID | 514ec66fc2624d32b23c563ae81bb010:readme |
| Pipeline run | 514ec66fc2624d32b23c563ae81bb010 |
| Status | PASS |
| Exit code | 0 |
| Started | 04 November 2026, 07:55:49 UTC |
| Finished | 04 November 2026, 07:55:50 UTC |
| Duration | 0.8 s |
| Previous duration | 0.742s |

## What was checked

**Result: PASS** — 0 findings across 4 of 4 eligible targets.

| Severity | Count |
|---|---:|
| ERROR | 0 |

### Change since previous report

| Metric | Current | Previous | Delta |
|---|---:|---:|---:|
| Findings | 0 | 0 | 0 |
| Previous duration | 0.742s | | |

| Finding change | Count |
|---|---:|
| Added | 0 |
| Resolved | 0 |
| Unchanged | 0 |

#### Category findings

| Category | Title | Findings | Previous | Delta |
| --- | --- | --- | --- | --- |
| RDM001 | Missing README.md | 0 | 0 | 0 |
| RDM002 | Undocumented subdirectory | 0 | 0 | 0 |
| RDM003 | Undocumented file | 0 | 0 | 0 |

### Scope

**Included**

- `src/**`
- `tests/**`
- `examples/**`
- `scripts/**`
- `resources/**`
- `docs/**`
- `**/README.md`

**Excluded**

- `**/DEBUG.txt/**`
- `**/EXACTUS_RESULTS/**`
- `**/__pycache__/**`
- `**/build/**`
- `**/coverage_report/**`
- `**/debug/**`
- `**/dist/**`
- `**/env/**`
- `**/htmlcov/**`
- `**/mutants/**`
- `**/node_modules/**`
- `**/site-packages/**`
- `**/venv/**`
- `**/.*`
- `**/*.egg-info/**`
- `**/*.dist-info/**`

**Skipped targets**

No skipped targets.

## Setup

### Invocation

~~~~shell
/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=56798 --orchestrator-control-token=[redacted] --orchestrator-worker-port=56770 --orchestrator-worker-token=[redacted] '--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"readme","module":"exactus.tools.readme.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/README","arguments":[],"explicit_arguments":[],"run_id":"514ec66fc2624d32b23c563ae81bb010:readme","pipeline_run_id":"514ec66fc2624d32b23c563ae81bb010","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}'
~~~~

| Property | Value |
|---|---|
| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| Arguments | `exactus.tools.common.tool_worker` `ExactusTool` `--orchestrator-control-port=56798` `--orchestrator-control-token=[redacted]` `--orchestrator-worker-port=56770` `--orchestrator-worker-token=[redacted]` `--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"readme","module":"exactus.tools.readme.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/README","arguments":[],"explicit_arguments":[],"run_id":"514ec66fc2624d32b23c563ae81bb010:readme","pipeline_run_id":"514ec66fc2624d32b23c563ae81bb010","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}` |

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
| EXACTUS_PIPELINE_RUN_ID | 514ec66fc2624d32b23c563ae81bb010 |
| EXACTUS_REGISTRY | [/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db](../.runtime/runs.db) |
| EXACTUS_ROOT | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| EXACTUS_RUN_ID | 514ec66fc2624d32b23c563ae81bb010:readme |
| EXACTUS_TOOL | readme |
| LANG | en_US.UTF-8 |
| TERM | xterm-256color |

## Gate

> **Gate: PASS** — No blocking findings

No blocking findings.

## Findings

No findings.

## Artifacts

| Artifact | Path | Bytes |
| --- | --- | --- |
| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 1664 |
| README.md | [ARTIFACTS/README.md](ARTIFACTS/README.md) | 451 |
| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |
| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 0 |
| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 1609 |

## Directory inventory

| Directory | README | README bytes | Entries | Documented | Missing |
| --- | --- | --- | --- | --- | --- |
| . | present | 1280 | 6 | 6 | 0 |
| python | present | 438 | 2 | 2 | 0 |
| tests | present | 703 | 3 | 3 | 0 |
| web | present | 465 | 3 | 3 | 0 |

## Documentation files

| Metric | Value |
| --- | --- |
| Markdown files | 4 |
| Markdown bytes | 2886 |
| Markdown lines | 81 |
| README files | 4 |

### README sizes

| README | Path | Bytes |
| --- | --- | --- |
| Largest | [README.md](../../README.md) | 1280 |
| Smallest | [python/README.md](../../python/README.md) | 438 |

### Directories without a README

N/A — every directory with analyzed source files has a README.

## Rules

| Rule | Title | Findings |
| --- | --- | --- |
| RDM001 | Missing README.md | 0 |
| RDM002 | Undocumented subdirectory | 0 |
| RDM003 | Undocumented file | 0 |

---

Exactus · readme 0.7.1 · Run 514ec66fc2624d32b23c563ae81bb010:readme · Result PASS · Duration 0.8 s
