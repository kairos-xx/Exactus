# Documentation Exactus

**Run time:** 31 October 2026, 02:56:19 UTC

## Identity

| Field | Value |
|---|---|
| Tool | docs 0.5.0 |
| Run ID | f9656595c8b74d23b2b6aec3bd0db7de:docs |
| Pipeline run | f9656595c8b74d23b2b6aec3bd0db7de |
| Status | PASS |
| Exit code | 0 |
| Started | 31 October 2026, 02:56:19 UTC |
| Finished | 31 October 2026, 02:56:20 UTC |
| Duration | 0.7 s |
| Previous duration | 0.647s |

## What was checked

**Result: PASS** — 0 findings across 8 of 8 eligible targets.

| Severity | Count |
|---|---:|
| ERROR | 0 |
| WARNING | 0 |
| INFO | 0 |

### Change since previous report

| Metric | Current | Previous | Delta |
|---|---:|---:|---:|
| Findings | 0 | 0 | 0 |
| Previous duration | 0.647s | | |

| Finding change | Count |
|---|---:|
| Added | 0 |
| Resolved | 0 |
| Unchanged | 0 |

#### Category findings

| Category | Title | Findings | Previous | Delta |
| --- | --- | --- | --- | --- |
| DOC001 | Missing documentation | 0 | 0 | 0 |
| DOC002 | Missing parameter documentation | 0 | 0 | 0 |
| DOC003 | Stale parameter documentation | 0 | 0 | 0 |
| DOC004 | Missing return documentation | 0 | 0 | 0 |
| DOC005 | Return and yield mismatch | 0 | 0 | 0 |
| DOC006 | Missing exception documentation | 0 | 0 | 0 |
| DOC007 | Missing attribute documentation | 0 | 0 | 0 |
| DOC008 | Malformed documentation | 0 | 0 | 0 |
| DOC009 | Analysis failure | 0 | 0 | 0 |
| DOC010 | Missing description | 0 | 0 | 0 |
| DOC011 | Stale exception documentation | 0 | 0 | 0 |
| DOC012 | Stale attribute documentation | 0 | 0 | 0 |

### Scope

**Included**

- `**/*.js`
- `**/*.mjs`
- `**/*.cjs`
- `**/*.py`

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
- `**/EXACTUS_RESULTS/**`
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
- `**/.*/**`
- `**/*.min.js`

**Skipped targets**

No skipped targets.

## Setup

### Invocation

~~~~shell
/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=60223 --orchestrator-control-token=[redacted] --orchestrator-worker-port=60194 --orchestrator-worker-token=[redacted] '--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"docs","module":"exactus.tools.docs.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/DOCS","arguments":[],"run_id":"f9656595c8b74d23b2b6aec3bd0db7de:docs","pipeline_run_id":"f9656595c8b74d23b2b6aec3bd0db7de","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}'
~~~~

| Property | Value |
|---|---|
| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| Arguments | `exactus.tools.common.tool_worker` `ExactusTool` `--orchestrator-control-port=60223` `--orchestrator-control-token=[redacted]` `--orchestrator-worker-port=60194` `--orchestrator-worker-token=[redacted]` `--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"docs","module":"exactus.tools.docs.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/DOCS","arguments":[],"run_id":"f9656595c8b74d23b2b6aec3bd0db7de:docs","pipeline_run_id":"f9656595c8b74d23b2b6aec3bd0db7de","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}` |

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
| EXACTUS_RUN_ID | f9656595c8b74d23b2b6aec3bd0db7de:docs |
| EXACTUS_TOOL | docs |
| LANG | C.UTF-8 |

## Gate

> **Gate: PASS** — No blocking findings

No blocking findings.

## Findings

No findings.

## Artifacts

| Artifact | Path | Bytes |
| --- | --- | --- |
| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 1648 |
| README.md | [ARTIFACTS/README.md](ARTIFACTS/README.md) | 448 |
| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |
| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 0 |
| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 1754 |

## Documentation statistics

| Language | Files | Parsed | Failed | Symbols | Documented | Coverage % | Findings |
| --- | --- | --- | --- | --- | --- | --- | --- |
| javascript | 2 | 2 | 0 | 3 | 3 | 100.0 | 0 |
| python | 6 | 6 | 0 | 12 | 12 | 100.0 | 0 |

## Analyzed code

| Language | Files | Lines |
| --- | --- | --- |
| javascript | 2 | 35 |
| python | 6 | 91 |

## Rules

| Rule | Title | Findings |
| --- | --- | --- |
| DOC001 | Missing documentation | 0 |
| DOC002 | Missing parameter documentation | 0 |
| DOC003 | Stale parameter documentation | 0 |
| DOC004 | Missing return documentation | 0 |
| DOC005 | Return and yield mismatch | 0 |
| DOC006 | Missing exception documentation | 0 |
| DOC007 | Missing attribute documentation | 0 |
| DOC008 | Malformed documentation | 0 |
| DOC009 | Analysis failure | 0 |
| DOC010 | Missing description | 0 |
| DOC011 | Stale exception documentation | 0 |
| DOC012 | Stale attribute documentation | 0 |

## Suggested documentation

No suggestions.

---

Exactus · docs 0.5.0 · Run f9656595c8b74d23b2b6aec3bd0db7de:docs · Result PASS · Duration 0.7 s
