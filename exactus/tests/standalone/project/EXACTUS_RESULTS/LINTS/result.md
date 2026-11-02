# Lint Exactus

**Run time:** 02 November 2026, 05:29:11 UTC

## Identity

| Field | Value |
|---|---|
| Tool | lints 0.6.1 |
| Run ID | a02e863bdc214c449643475edb79e655:lints |
| Pipeline run | a02e863bdc214c449643475edb79e655 |
| Status | PASS |
| Exit code | 0 |
| Started | 02 November 2026, 05:29:11 UTC |
| Finished | 02 November 2026, 05:29:19 UTC |
| Duration | 7.7 s |
| Previous duration | 9.757s |

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
| Previous duration | 9.757s | | |

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
/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=57866 --orchestrator-control-token=[redacted] --orchestrator-worker-port=57852 --orchestrator-worker-token=[redacted] '--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"lints","module":"exactus.tools.lints.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS","arguments":[],"run_id":"a02e863bdc214c449643475edb79e655:lints","pipeline_run_id":"a02e863bdc214c449643475edb79e655","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}'
~~~~

| Property | Value |
|---|---|
| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| Arguments | `exactus.tools.common.tool_worker` `ExactusTool` `--orchestrator-control-port=57866` `--orchestrator-control-token=[redacted]` `--orchestrator-worker-port=57852` `--orchestrator-worker-token=[redacted]` `--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"lints","module":"exactus.tools.lints.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS","arguments":[],"run_id":"a02e863bdc214c449643475edb79e655:lints","pipeline_run_id":"a02e863bdc214c449643475edb79e655","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}` |

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
| EXACTUS_PIPELINE_RUN_ID | a02e863bdc214c449643475edb79e655 |
| EXACTUS_REGISTRY | [/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db](../.runtime/runs.db) |
| EXACTUS_ROOT | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| EXACTUS_RUN_ID | a02e863bdc214c449643475edb79e655:lints |
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
| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 2336 |
| README.md | [ARTIFACTS/README.md](ARTIFACTS/README.md) | 450 |
| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |
| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 343 |
| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 38146 |

## Integrated stages

### group_final

| Files scanned | Modules planned | Constants moved | Files changed | Dry run |
|---:|---:|---:|---:|---|
| 6 | 0 | 0 | 0 | False |

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
| custom_compliance | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.0017717910232022405 |
| custom_shebang | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.002251582976896316 |
| custom_python | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.036 |
| custom_python_long_lines | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 7.774995174258947e-05 |
| custom_javascript | ran | built-in | 2 | 0 | 0 | 0 | 0 | 0 | 0.001 |
| custom_javascript_delimiters | ran | built-in | 2 | 0 | 0 | 0 | 0 | 0 | 0.045731999969575554 |
| custom_javascript_notation | ran | built-in | 2 | 0 | 0 | 0 | 0 | 0 | 0.19839616701938212 |
| custom_css | ran | built-in | 1 | 0 | 0 | 0 | 0 | 0 | 0.002 |
| custom_html | ran | built-in | 1 | 0 | 0 | 0 | 0 | 0 | 0.0 |
| ruff | ran | 0.12.0 | 6 | 0 | 0 | 0 | 0 | 0 | 0.233572 |
| ruff_docs | ran | 0.12.0 | 6 | 0 | 0 | 0 | 0 | 0 | 0.233572 |
| basedpyright | ran | 1.40.2 | 6 | 0 | 0 | 0 | 0 | 0 | 1.290921 |
| pyrefly | ran | 0.63.0 | 6 | 0 | 0 | 0 | 0 | 0 | 0.299 |
| eslint | ran | 10.14.0 | 2 | 0 | 0 | 0 | 0 | 0 | 0.667758 |
| typescript | ran | 6.0.3 | 2 | 0 | 0 | 0 | 0 | 0 | 2.986645 |
| stylelint | ran | 17.16.0 | 1 | 0 | 0 | 0 | 0 | 0 | 0.735674 |
| htmlhint | ran | 1.9.2 | 1 | 0 | 0 | 0 | 0 | 0 | 0.165826 |

### Top rules

N/A — no rule reported a finding.

### Files with the most findings

N/A — no file has a finding.

---

Exactus · lints 0.6.1 · Run a02e863bdc214c449643475edb79e655:lints · Result PASS · Duration 7.7 s
