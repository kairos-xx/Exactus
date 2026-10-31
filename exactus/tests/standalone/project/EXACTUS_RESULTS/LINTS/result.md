# Lint Exactus

**Run time:** 31 October 2026, 05:10:25 UTC

## Identity

| Field | Value |
|---|---|
| Tool | lints |
| Run ID | 2c65e21142f34f8db22b09b30d9044d1:lints |
| Pipeline run | 2c65e21142f34f8db22b09b30d9044d1 |
| Status | PASS |
| Exit code | 0 |
| Started | 31 October 2026, 05:10:25 UTC |
| Finished | 31 October 2026, 05:10:35 UTC |
| Duration | 9.4 s |
| Previous duration | 6.627s |

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
| Previous duration | 6.627s | | |

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
- `EXACTUS_RESULTS/**`
- `**/EXACTUS_RESULTS/**`
- `node_modules/**`
- `build/**`
- `dist/**`
- `*.egg-info/**`
- `**/__pycache__/**`
- `EXACTUS_RESULTS`
- `EXACTUS_RESULTS/**`

**Skipped targets**

No skipped targets.

## Setup

### Invocation

~~~~shell
/usr/local/bin/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=60293 --orchestrator-control-token=[redacted] --orchestrator-worker-port=60241 --orchestrator-worker-token=[redacted] '--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"lints","module":"exactus.tools.lints.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS","arguments":[],"run_id":"2c65e21142f34f8db22b09b30d9044d1:lints","pipeline_run_id":"2c65e21142f34f8db22b09b30d9044d1","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}'
~~~~

| Property | Value |
|---|---|
| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| Arguments | `exactus.tools.common.tool_worker` `ExactusTool` `--orchestrator-control-port=60293` `--orchestrator-control-token=[redacted]` `--orchestrator-worker-port=60241` `--orchestrator-worker-token=[redacted]` `--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"lints","module":"exactus.tools.lints.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS","arguments":[],"run_id":"2c65e21142f34f8db22b09b30d9044d1:lints","pipeline_run_id":"2c65e21142f34f8db22b09b30d9044d1","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}` |

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
| EXACTUS_RUN_ID | 2c65e21142f34f8db22b09b30d9044d1:lints |
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
| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 2095 |
| README.md | [ARTIFACTS/README.md](ARTIFACTS/README.md) | 449 |
| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |
| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 343 |
| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 37771 |

## Integrated stages

### group_final

| Files scanned | Modules planned | Constants moved | Files changed | Dry run |
|---:|---:|---:|---:|---|
| 6 | 0 | 0 | 0 | False |

### all_lints

| Tools | Passed | Failed | Unavailable | File checks | Diagnostics |
|---:|---:|---:|---:|---:|---:|
| 8 | 8 | 0 | 0 | 34 | 0 |

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
| custom_compliance | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.0022991250007180497 |
| custom_shebang | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.0011241669999435544 |
| custom_python | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.031 |
| custom_python_long_lines | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.0015804580034455284 |
| custom_javascript | ran | built-in | 2 | 0 | 0 | 0 | 0 | 0 | 0.001 |
| custom_javascript_delimiters | ran | built-in | 2 | 0 | 0 | 0 | 0 | 0 | 0.01899174999562092 |
| custom_javascript_notation | ran | built-in | 2 | 0 | 0 | 0 | 0 | 0 | 0.1644098329998087 |
| custom_css | ran | built-in | 1 | 0 | 0 | 0 | 0 | 0 | 0.001 |
| custom_html | ran | built-in | 1 | 0 | 0 | 0 | 0 | 0 | 0.0 |
| ruff | ran | 0.12.0 | 6 | 0 | 0 | 0 | 0 | 0 | 0.284287 |
| ruff_docs | ran | 0.12.0 | 6 | 0 | 0 | 0 | 0 | 0 | 0.284287 |
| basedpyright | ran | 1.40.2 | 6 | 0 | 0 | 0 | 0 | 0 | 1.830926 |
| pyrefly | ran | 0.63.0 | 6 | 0 | 0 | 0 | 0 | 0 | 0.232 |
| eslint | ran | 10.13.0 | 2 | 0 | 0 | 0 | 0 | 0 | 0.899025 |
| typescript | ran | 6.0.3 | 2 | 0 | 0 | 0 | 0 | 0 | 4.57235 |
| stylelint | ran | 17.16.0 | 1 | 0 | 0 | 0 | 0 | 0 | 1.478769 |
| htmlhint | ran | 1.9.2 | 1 | 0 | 0 | 0 | 0 | 0 | 0.152769 |

### Top rules

N/A — no rule reported a finding.

### Files with the most findings

N/A — no file has a finding.

---

Exactus · lints · Run 2c65e21142f34f8db22b09b30d9044d1:lints · Result PASS · Duration 9.4 s
