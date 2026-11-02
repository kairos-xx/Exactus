# README Exactus

**Run time:** 02 November 2026, 06:49:03 UTC

## Identity

| Field | Value |
|---|---|
| Tool | readme 0.6.1 |
| Run ID | 7906d1edd1a543c7894fd4387463792d:readme |
| Pipeline run | 7906d1edd1a543c7894fd4387463792d |
| Status | PASS |
| Exit code | 0 |
| Started | 02 November 2026, 06:49:03 UTC |
| Finished | 02 November 2026, 06:49:05 UTC |
| Duration | 1.9 s |
| Previous duration | 1.893s |

## What was checked

**Result: PASS** — 0 findings across 4 of 4 eligible targets.

| Severity | Count |
|---|---:|
| ERROR | 0 |

### Change since previous report

| Metric | Current | Previous | Delta |
|---|---:|---:|---:|
| Findings | 0 | 0 | 0 |
| Previous duration | 1.893s | | |

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

- `**/.agents/**`
- `**/.build-cache/**`
- `**/.cache/**`
- `**/.claude/**`
- `**/.cursor/**`
- `**/.devin/**`
- `**/.eggs/**`
- `**/.git/**`
- `**/.history/**`
- `**/.mypy_cache/**`
- `**/.pytest_cache/**`
- `**/.ruff_cache/**`
- `**/.tox/**`
- `**/.venv/**`
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
/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=59153 --orchestrator-control-token=[redacted] --orchestrator-worker-port=59141 --orchestrator-worker-token=[redacted] '--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"readme","module":"exactus.tools.readme.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/README","arguments":[],"run_id":"7906d1edd1a543c7894fd4387463792d:readme","pipeline_run_id":"7906d1edd1a543c7894fd4387463792d","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}'
~~~~

| Property | Value |
|---|---|
| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| Arguments | `exactus.tools.common.tool_worker` `ExactusTool` `--orchestrator-control-port=59153` `--orchestrator-control-token=[redacted]` `--orchestrator-worker-port=59141` `--orchestrator-worker-token=[redacted]` `--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"readme","module":"exactus.tools.readme.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/README","arguments":[],"run_id":"7906d1edd1a543c7894fd4387463792d:readme","pipeline_run_id":"7906d1edd1a543c7894fd4387463792d","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}` |

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
| EXACTUS_PIPELINE_RUN_ID | 7906d1edd1a543c7894fd4387463792d |
| EXACTUS_REGISTRY | [/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db](../.runtime/runs.db) |
| EXACTUS_ROOT | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| EXACTUS_RUN_ID | 7906d1edd1a543c7894fd4387463792d:readme |
| EXACTUS_TOOL | readme |
| LANG | C.UTF-8 |

## Gate

> **Gate: PASS** — No blocking findings

No blocking findings.

## Findings

No findings.

## Artifacts

| Artifact | Path | Bytes |
| --- | --- | --- |
| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 1796 |
| README.md | [ARTIFACTS/README.md](ARTIFACTS/README.md) | 451 |
| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |
| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 0 |
| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 1609 |

## Directory inventory

| Directory | README | README bytes | Entries | Documented | Missing |
| --- | --- | --- | --- | --- | --- |
| . | present | 1187 | 6 | 6 | 0 |
| python | present | 438 | 2 | 2 | 0 |
| tests | present | 579 | 3 | 3 | 0 |
| web | present | 465 | 3 | 3 | 0 |

## Documentation files

| Metric | Value |
| --- | --- |
| Markdown files | 4 |
| Markdown bytes | 2669 |
| Markdown lines | 80 |
| README files | 4 |

### README sizes

| README | Path | Bytes |
| --- | --- | --- |
| Largest | [README.md](../../README.md) | 1187 |
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

Exactus · readme 0.6.1 · Run 7906d1edd1a543c7894fd4387463792d:readme · Result PASS · Duration 1.9 s
