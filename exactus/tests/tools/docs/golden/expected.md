# Documentation Exactus

**Run time:** N/A

## Identity

| Field | Value |
|---|---|
| Tool | docs 0.5.0 |
| Run ID | 0123456789abcdef0123456789abcdef |
| Pipeline run | N/A |
| Status | FAIL |
| Exit code | 1 |
| Started | N/A |
| Finished | N/A |
| Duration | 0.8 s |

## What was checked

**Result: FAIL** — 2 findings across 3 of 4 eligible targets.

| Severity | Count |
|---|---:|
| ERROR | 0 |
| WARNING | 1 |
| INFO | 1 |

### Change since previous report

No previous report exists; this run establishes the baseline.

### Scope

**Included**

- `**/*.js`
- `**/*.mjs`
- `**/*.cjs`
- `**/*.py`

**Excluded**

- `exactus/packages/**`
- `**/build/**`
- `**/node_modules/**`
- `**/.*/**`
- `**/*.min.js`

**Skipped targets**

| Target | Reason |
| --- | --- |
| exactus/packages/lib.py | excluded by include/exclude rules |

## Setup

### Invocation

~~~~shell
python exactus/tools/docs/main.py . --exclude 'exactus/packages/**'
~~~~

| Property | Value |
|---|---|
| Working directory | /work/project |
| Arguments | `.` `--exclude` `exactus/packages/**` |

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

> **Gate: FAIL** — 1 blocking finding

Blocking findings:

- DOCS-001 — Missing parameter documentation: load

## Findings

### By file

#### `pkg/util.py`

2 findings — 1 warning · 1 info

- [DOCS-001](#finding-docs-001) — warning · DOC002 · line 9
- [DOCS-002](#finding-docs-002) — info · DOC001 · line 20

<a id="finding-docs-001"></a>

### DOCS-001 — Missing parameter documentation: load

**Severity:** warning · **Rule:** DOC002 · **Location:** `pkg/util.py:9`

Parameter `path` is undocumented.

~~~python
    6 | ENCODING = "utf-8"
    7 |
    8 |
    9>| def load(path: str) -> str:
   10 |     """Load a file.
   11 |
   12 |     Returns:
~~~

<a id="finding-docs-002"></a>

### DOCS-002 — Missing documentation: helper

**Severity:** info · **Rule:** DOC001 · **Location:** `pkg/util.py:20`

Missing docstring.

~~~python
   17 |
   18 | # Called by the CLI entry point.
   19 | @lru_cache(maxsize=1)
   20>| def helper() -> None:
   21 |     print(load(path="README.md"))
~~~

### Index

| ID | Severity | Rule | Path | Line | Title |
| --- | --- | --- | --- | --- | --- |
| DOCS-001 | warning | DOC002 | pkg/util.py | 9 | Missing parameter documentation: load |
| DOCS-002 | info | DOC001 | pkg/util.py | 20 | Missing documentation: helper |

## Artifacts

| Artifact | Path | Bytes |
| --- | --- | --- |
| stderr.log | ARTIFACTS/stderr.log | 0 |
| stdout.log | ARTIFACTS/stdout.log | 145 |

## Documentation statistics

| Language | Files | Parsed | Failed | Symbols | Documented | Coverage % | Findings |
| --- | --- | --- | --- | --- | --- | --- | --- |
| javascript | 1 | 1 | 0 | 0 | 0 | N/A | 0 |
| python | 2 | 2 | 0 | 5 | 3 | 60 | 2 |

## Analyzed code

| Language | Files | Lines |
| --- | --- | --- |
| javascript | 1 | 14 |
| python | 2 | 46 |

## Rules

| Rule | Title | Findings |
| --- | --- | --- |
| DOC001 | Missing documentation | 1 |
| DOC002 | Missing parameter documentation | 1 |
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

### DOCS-001 — `load`

Signature: `load(path: str) -> str`

Reason: The parameter exists in the callable signature but not in Args.

~~~python
"""Load a file.

Args:
    path: Path to read.

Returns:
    The file text.
"""
~~~

### DOCS-002 — `helper`

Signature: `helper() -> None`

Reason: The callable has no runtime docstring.

~~~python
"""Describe helper."""
~~~

---

Exactus · docs 0.5.0 · Run 0123456789abcdef0123456789abcdef · Result FAIL · Duration 0.8 s
