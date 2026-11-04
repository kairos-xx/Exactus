# Lint Exactus

**Run time:** 04 November 2026, 07:55:00 UTC

## Identity

| Field | Value |
|---|---|
| Tool | lints 0.7.1 |
| Run ID | 514ec66fc2624d32b23c563ae81bb010:lints |
| Pipeline run | 514ec66fc2624d32b23c563ae81bb010 |
| Status | PASS |
| Exit code | 0 |
| Started | 04 November 2026, 07:55:00 UTC |
| Finished | 04 November 2026, 07:55:16 UTC |
| Duration | 16.7 s |
| Previous duration | 4.262s |

## What was checked

**Result: PASS** — 0 findings across 10 of 10 eligible targets.

| Severity | Count |
|---|---:|
| ERROR | 0 |
| WARNING | 0 |
| INFORMATION | 0 |

### Change since previous report

| Metric | Current | Previous | Delta |
|---|---:|---:|---:|
| Findings | 0 | 0 | 0 |
| Previous duration | 4.262s | | |

| Finding change | Count |
|---|---:|
| Added | 0 |
| Resolved | 0 |
| Unchanged | 0 |

#### Category findings

| Category | Title | Findings | Previous | Delta |
| --- | --- | --- | --- | --- |
| CMP000 | Module does not parse | 0 | 0 | 0 |
| CMP001 | Suppression marker | 0 | 0 | 0 |
| CMP002 | typing.Any usage | 0 | 0 | 0 |
| CMP003 | object annotation | 0 | 0 | 0 |
| CMP004 | Lint ignore configuration | 0 | 0 | 0 |
| CMP005 | Type-check suppression | 0 | 0 | 0 |
| CMP006 | pyproject.toml missing | 0 | 0 | 0 |

### Scope

**Included**

- `.`

**Excluded**

- `.*/**`
- `**/.*/**`
- `**/__pycache__/**`
- `**/build/**`
- `**/coverage_report/**`
- `**/dist/**`
- `**/env/**`
- `**/htmlcov/**`
- `**/mutants/**`
- `**/node_modules/**`
- `**/site-packages/**`
- `**/venv/**`
- `*.egg-info/**`
- `*.dist-info/**`
- `EXACTUS_RESULTS/**`
- `**/EXACTUS_RESULTS/**`
- `EXACTUS_RESULTS`
- `EXACTUS_RESULTS/**`

**Skipped targets**

No skipped targets.

## Setup

### Invocation

~~~~shell
/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=52908 --orchestrator-control-token=[redacted] --orchestrator-worker-port=52902 --orchestrator-worker-token=[redacted] '--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"lints","module":"exactus.tools.lints.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS","arguments":[],"explicit_arguments":[],"run_id":"514ec66fc2624d32b23c563ae81bb010:lints","pipeline_run_id":"514ec66fc2624d32b23c563ae81bb010","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}'
~~~~

| Property | Value |
|---|---|
| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| Arguments | `exactus.tools.common.tool_worker` `ExactusTool` `--orchestrator-control-port=52908` `--orchestrator-control-token=[redacted]` `--orchestrator-worker-port=52902` `--orchestrator-worker-token=[redacted]` `--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"lints","module":"exactus.tools.lints.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS","arguments":[],"explicit_arguments":[],"run_id":"514ec66fc2624d32b23c563ae81bb010:lints","pipeline_run_id":"514ec66fc2624d32b23c563ae81bb010","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}` |

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
| EXACTUS_RUN_ID | 514ec66fc2624d32b23c563ae81bb010:lints |
| EXACTUS_TOOL | lints |
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
| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 2687 |
| README.md | [ARTIFACTS/README.md](ARTIFACTS/README.md) | 450 |
| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |
| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 433 |
| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 69873 |

## Integrated stages

### group_final

| Files scanned | Modules planned | Constants moved | Files changed | Dry run |
|---:|---:|---:|---:|---|
| 6 | 0 | 0 | 0 | True |

### all_lints

| Tools | Passed | Failed | Unavailable | File checks | Diagnostics |
|---:|---:|---:|---:|---:|---:|
| 9 | 8 | 0 | 1 | 40 | 0 |

## Rules

| Rule | Title | Category | Findings |
| --- | --- | --- | --- |
| CMP000 | Module does not parse | Parsing | 0 |
| CMP001 | Suppression marker | Suppression | 0 |
| CMP002 | typing.Any usage | Typing | 0 |
| CMP003 | object annotation | Typing | 0 |
| CMP004 | Lint ignore configuration | Configuration | 0 |
| CMP005 | Type-check suppression | Configuration | 0 |
| CMP006 | pyproject.toml missing | Configuration | 0 |


## Lint metrics

| Metric | Value |
| --- | --- |
| Linters run | 17 |
| Linters unavailable | 0 |
| Files analyzed | 10 |
| Files with findings | 0 |
| Rules triggered | 0 |
| Findings | 0 |

### Linters

| Linter | Status | Version | Files | Findings | Errors | Warnings | Information | Exit code | Duration (s) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| custom_compliance | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.001703375019133091 |
| custom_shebang | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.010653958015609533 |
| custom_python | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.006 |
| custom_python_long_lines | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.00015295797493308783 |
| custom_javascript | ran | built-in | 2 | 0 | 0 | 0 | 0 | 0 | 0.0 |
| custom_javascript_delimiters | ran | built-in | 2 | 0 | 0 | 0 | 0 | 0 | 0.00028266600565984845 |
| custom_javascript_notation | ran | built-in | 2 | 0 | 0 | 0 | 0 | 0 | 2.3042026441544294e-05 |
| custom_css | ran | built-in | 1 | 0 | 0 | 0 | 0 | 0 | 0.004 |
| custom_html | ran | built-in | 1 | 0 | 0 | 0 | 0 | 0 | 0.0 |
| ruff | ran | 0.15.22 | 6 | 0 | 0 | 0 | 0 | 0 | 0.093502 |
| ruff_docs | ran | 0.15.22 | 6 | 0 | 0 | 0 | 0 | 0 | 0.093502 |
| basedpyright | ran | 1.40.2 | 6 | 0 | 0 | 0 | 0 | 0 | 2.830421 |
| pyrefly | ran | 0.63.0 | 6 | 0 | 0 | 0 | 0 | 0 | 0.364 |
| eslint | ran | 10.14.0 | 2 | 0 | 0 | 0 | 0 | 0 | 1.834442 |
| typescript | ran | 6.0.3 | 2 | 0 | 0 | 0 | 0 | 0 | 3.560066 |
| stylelint | ran | 17.16.0 | 1 | 0 | 0 | 0 | 0 | 0 | 1.70532 |
| htmlhint | ran | 1.9.2 | 1 | 0 | 0 | 0 | 0 | 0 | 0.114452 |

### Top rules

N/A — no rule reported a finding.

### Files with the most findings

N/A — no file has a finding.

---

Exactus · lints 0.7.1 · Run 514ec66fc2624d32b23c563ae81bb010:lints · Result PASS · Duration 16.7 s
