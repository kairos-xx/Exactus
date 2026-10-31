# Record Exactus

**Run time:** 05 October 2026, 06:00:00 UTC

## Identity

| Field | Value |
|---|---|
| Tool | record 0.5.0 |
| Run ID | eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee |
| Pipeline run | ffffffffffffffffffffffffffffffff |
| Status | FAIL |
| Exit code | 1 |
| Started | 05 October 2026, 06:00:00 UTC |
| Finished | 05 October 2026, 06:00:01 UTC |
| Duration | 1.2 s |

## What was checked

**Result: FAIL** — 2 findings across 3 of 3 eligible targets.

| Severity | Count |
|---|---:|
| ERROR | 1 |
| WARNING | 1 |

### Change since previous report

No previous report exists; this run establishes the baseline.

### Scope

**Included**

- `http://127.0.0.1:8000`
- `recording.pwflow.json`

**Excluded**

N/A — no exclude rules.

**Skipped targets**

| Target | Reason |
| --- | --- |
| 1 action(s) | no selector-addressable Exactus Record equivalent |

## Setup

### Invocation

~~~~shell
python exactus/tools/record/main.py --url http://127.0.0.1:8000
~~~~

| Property | Value |
|---|---|
| Working directory | /work/project |
| Arguments | `--url` `http://127.0.0.1:8000` |

### Environment

| Property | Value |
|---|---|
| OS | Linux 6.8.0 |
| Python | 3.13.1 |
| Node | v22.4.0 |
| CPU count | 8 |

| Variable | Value |
| --- | --- |
| AUDIT_ORCHESTRATED | 1 |
| CI | true |

## Gate

> **Gate: FAIL** — 1 blocking finding

Blocking findings:

- RECORD-001 — Replay action failed

## Findings

### By file

#### `recording.pwflow.json`

2 findings — 1 error · 1 warning

- [RECORD-001](#finding-record-001) — error · REC001
- [RECORD-002](#finding-record-002) — warning · REC003

<a id="finding-record-001"></a>

### RECORD-001 — Replay action failed

**Severity:** error · **Rule:** REC001 · **Location:** `recording.pwflow.json`

1 click: boom

<a id="finding-record-002"></a>

### RECORD-002 — Actions without Exactus Record equivalent

**Severity:** warning · **Rule:** REC003 · **Location:** `recording.pwflow.json`

1 action(s) have no selector-addressable Exactus Record equivalent and were not exported

### Index

| ID | Severity | Rule | Path | Line | Title |
| --- | --- | --- | --- | --- | --- |
| RECORD-001 | error | REC001 | recording.pwflow.json |  | Replay action failed |
| RECORD-002 | warning | REC003 | recording.pwflow.json |  | Actions without Exactus Record equivalent |

## Artifacts

| Artifact | Path | Bytes |
| --- | --- | --- |
| stdout.log | ARTIFACTS/stdout.log | 21 |
| stderr.log | ARTIFACTS/stderr.log | 0 |

## Session

| Fact | Value |
| --- | --- |
| Mode | replay |
| URL | http://127.0.0.1:8000 |
| Actions | 3 |
| Exactus Record events exported | 3 |
| Replay failures | 1 |
| Duration (seconds) | 1.234 |
| Workspace | recording.pwflow.json |

### Actions by type

| Type | Count |
| --- | --- |
| click | 2 |
| key | 1 |

### Exactus Record session

N/A — no Exactus Record session facts were reported.

### Produced files

- `replay.py`

## Rules

| Rule | Title | Findings |
| --- | --- | --- |
| REC001 | Replay action failed | 1 |
| REC002 | Empty recording | 0 |
| REC003 | Actions without Exactus Record equivalent | 0 |

---

Exactus · record 0.5.0 · Run eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee · Result FAIL · Duration 1.2 s
