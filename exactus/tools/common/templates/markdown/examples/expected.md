# Lints

**Run time:** N/A

## Identity

| Field | Value |
|---|---|
| Tool | lints 0.5.0 |
| Run ID | run-001 |
| Pipeline run | N/A |
| Status | FAIL |
| Exit code | 1 |
| Started | N/A |
| Finished | N/A |
| Duration | 12.0 s |

## What was checked

**Result: FAIL** — 3 findings across 10 of 10 eligible targets.

| Severity | Count |
|---|---:|
| ERROR | 2 |
| WARNING | 1 |
| INFO | 0 |

### Change since previous report

No previous report exists; this run establishes the baseline.

### Scope

**Included**

- `exactus/**/*.py`

**Excluded**

- `build/**`
- `**/__pycache__/**`

**Skipped targets**

| Target | Reason |
| --- | --- |
| exactus/packages/x.js | excluded by config |

## Setup

### Invocation

~~~~shell
./check -t lints --root .
~~~~

| Property | Value |
|---|---|
| Working directory | /work/project |
| Arguments | `-t` `lints` `--root` `.` |

### Environment

| Property | Value |
|---|---|
| OS | Darwin 25.3.0 |
| Python | 3.13.1 |
| Node | v22.4.0 |
| CPU count | 8 |

| Variable | Value |
| --- | --- |
| EXACTUS_ORCHESTRATED | 1 |
| EXACTUS_TOKEN | [redacted] |

## Gate

> **Gate: FAIL** — 2 blocking findings

Blocking findings:

- F-001 — Bare except
- F-003 — Mutable default argument

## Findings

### F-001 — Bare except

**Severity:** error · **Rule:** E722 · **Location:** `pkg/a.py:3`

Do not use bare `except`

~~~python
    2 | try:
    3>| except:
    4 |     pass
~~~

### F-002 — Unused import

**Severity:** warning · **Rule:** F401 · **Location:** `pkg/b.py:1`

`os` imported but unused

### F-003 — Mutable default argument

**Severity:** error · **Rule:** B006 · **Location:** `pkg/c.py:7`

Do not use a mutable default argument

### Index

| ID | Severity | Rule | Path | Line | Title |
| --- | --- | --- | --- | --- | --- |
| F-001 | error | E722 | pkg/a.py | 3 | Bare except |
| F-002 | warning | F401 | pkg/b.py | 1 | Unused import |
| F-003 | error | B006 | pkg/c.py | 7 | Mutable default argument |

## Artifacts

| Artifact | Path | Bytes |
| --- | --- | --- |
| stderr.log | ARTIFACTS/stderr.log | 120 |

---

Exactus · lints 0.5.0 · Run run-001 · Result FAIL · Duration 12.0 s
