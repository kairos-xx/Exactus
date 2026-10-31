# README Exactus

**Run time:** N/A

## Identity

| Field | Value |
|---|---|
| Tool | readme 0.5.0 |
| Run ID | 0123456789abcdef0123456789abcdef |
| Pipeline run | N/A |
| Status | FAIL |
| Exit code | 1 |
| Started | 03 October 2026, 09:00:00 UTC |
| Finished | 03 October 2026, 09:00:01 UTC |
| Duration | 0.8 s |

## What was checked

**Result: FAIL** — 3 findings across 4 of 5 eligible targets.

| Severity | Count |
|---|---:|
| ERROR | 3 |

### Change since previous report

No previous report exists; this run establishes the baseline.

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

- `exactus/docs/archive/**`
- `**/.git/**`
- `**/EXACTUS_RESULTS/**`
- `**/DEBUG.txt/**`
- `**/__pycache__/**`
- `**/build/**`
- `**/debug/**`
- `**/dist/**`
- `**/node_modules/**`
- `**/site-packages/**`
- `**/venv/**`
- `**/.*`
- `**/*.egg-info/**`
- `**/*.dist-info/**`

**Skipped targets**

| Target | Reason |
| --- | --- |
| exactus/docs/archive | excluded by include/exclude rules |

## Setup

### Invocation

~~~~shell
python exactus/tools/readme/main.py . --exclude 'exactus/docs/archive/**'
~~~~

| Property | Value |
|---|---|
| Working directory | /work/project |
| Arguments | `.` `--exclude` `exactus/docs/archive/**` |

### Environment

| Property | Value |
|---|---|
| OS | Linux 6.8.0 |
| Python | 3.13.1 |
| Node | v22.4.0 |
| CPU count | 8 |

| Variable | Value |
| --- | --- |
| EXACTUS_ORCHESTRATED | 1 |
| CI | true |

## Gate

> **Gate: FAIL** — 3 blocking findings

Blocking findings:

- README-001 — Missing README.md
- README-002 — Undocumented file
- README-003 — Undocumented subdirectory

## Findings

### By file

#### `exactus/docs/README.md`

1 finding — 1 error

- [README-002](#finding-readme-002) — error · RDM003 · line 0

#### `exactus/docs/guides`

1 finding — 1 error

- [README-001](#finding-readme-001) — error · RDM001 · line 0

#### `src/README.md`

1 finding — 1 error

- [README-003](#finding-readme-003) — error · RDM002 · line 0

<a id="finding-readme-001"></a>

### README-001 — Missing README.md

**Severity:** error · **Rule:** RDM001 · **Location:** `exactus/docs/guides`

missing README.md

<a id="finding-readme-002"></a>

### README-002 — Undocumented file

**Severity:** error · **Rule:** RDM003 · **Location:** `exactus/docs/README.md`

does not document file setup.md

<a id="finding-readme-003"></a>

### README-003 — Undocumented subdirectory

**Severity:** error · **Rule:** RDM002 · **Location:** `src/README.md`

does not document subdirectory pkg/

### Index

| ID | Severity | Rule | Path | Line | Title |
| --- | --- | --- | --- | --- | --- |
| README-001 | error | RDM001 | exactus/docs/guides | 0 | Missing README.md |
| README-002 | error | RDM003 | exactus/docs/README.md | 0 | Undocumented file |
| README-003 | error | RDM002 | src/README.md | 0 | Undocumented subdirectory |

## Artifacts

| Artifact | Path | Bytes |
| --- | --- | --- |
| stderr.log | ARTIFACTS/stderr.log | 0 |
| stdout.log | ARTIFACTS/stdout.log | 145 |

## Directory inventory

| Directory | README | README bytes | Entries | Documented | Missing |
| --- | --- | --- | --- | --- | --- |
| docs | present | 412 | 3 | 2 | 1 |
| exactus/docs/guides | missing | 0 | 2 | 0 | 2 |
| src | present | 230 | 2 | 1 | 1 |
| src/pkg | present | 98 | 1 | 1 | 0 |

## Documentation files

N/A — the tool reported no metrics.

## Rules

| Rule | Title | Findings |
| --- | --- | --- |
| RDM001 | Missing README.md | 1 |
| RDM002 | Undocumented subdirectory | 1 |
| RDM003 | Undocumented file | 1 |

---

Exactus · readme 0.5.0 · Run 0123456789abcdef0123456789abcdef · Result FAIL · Duration 0.8 s
