# Lint Exactus

**Run time:** N/A

## Identity

| Field | Value |
|---|---|
| Tool | lints 0.5.0 |
| Run ID | 0123456789abcdef0123456789abcdef |
| Pipeline run | N/A |
| Status | FAIL |
| Exit code | 1 |
| Started | N/A |
| Finished | N/A |
| Duration | 4.2 s |

## What was checked

**Result: FAIL** — 8 findings across 3 of 3 eligible targets.

| Severity | Count |
|---|---:|
| ERROR | 1 |
| WARNING | 7 |
| INFORMATION | 0 |

### Change since previous report

No previous report exists; this run establishes the baseline.

### Scope

**Included**

- `.`

**Excluded**

- `exactus/packages/**`
- `**/__pycache__/**`

**Skipped targets**

| Target | Reason |
| --- | --- |
| web/exactus.packages.min.js | eslint: File ignored because of a matching ignore pattern. |

## Setup

### Invocation

~~~~shell
python exactus/tools/lints/main.py . --dry
~~~~

| Property | Value |
|---|---|
| Working directory | /work/project |
| Arguments | `.` `--dry` |

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

> **Gate: FAIL** — 4 blocking findings

Blocking findings:

- LINTS-003 — Missing type annotation for function argument `path`
- LINTS-004 — `open()` should be replaced by `Path.open()`
- LINTS-005 — Use a context manager for opening files
- LINTS-006 — Type annotation is missing for parameter "path"

## Findings

### By file

#### `pkg/app.py`

6 findings — 1 error · 5 warning

- [LINTS-001](#finding-lints-001) — warning · PY002 · line 4
- [LINTS-003](#finding-lints-003) — warning · ANN001 · line 7
- [LINTS-004](#finding-lints-004) — warning · PTH123 · line 9
- [LINTS-005](#finding-lints-005) — warning · SIM115 · line 9
- [LINTS-006](#finding-lints-006) — error · reportMissingParameterType · line 7
- [LINTS-007](#finding-lints-007) — warning · reportUnusedCallResult · line 12

#### `web/app.js`

2 findings — 2 warning

- [LINTS-002](#finding-lints-002) — warning · JS005 · line 2
- [LINTS-008](#finding-lints-008) — warning · prefer-const · line 1

Grouped by linter, then ordered by path and line.

### custom_python — 1 finding

<a id="finding-lints-001"></a>

#### LINTS-001 — Module global `LIMIT` is uppercase but is not declared Final.

**Severity:** warning · **Rule:** PY002 · **Location:** `pkg/app.py:4:1`

Module global `LIMIT` is uppercase but is not declared Final. Use an immutable constant or move mutable state to an explicit instance dependency.

~~~python
    1 | """Demo application."""
    2 |
    3 | import os
    4>| LIMIT = 3
    5 |
    6 |
    7 | def load(path):
~~~

### custom_javascript — 1 finding

<a id="finding-lints-002"></a>

#### LINTS-002 — Static inline style `color` is assigned directly.

**Severity:** warning · **Rule:** JS005 · **Location:** `web/app.js:2:1`

~~~javascript
    1 | const box = document.querySelector("#box");
    2>| box.style.color = "red";
~~~

### ruff — 3 findings

<a id="finding-lints-003"></a>

#### LINTS-003 — Missing type annotation for function argument `path`

**Severity:** warning · **Rule:** ANN001 · **Location:** `pkg/app.py:7:10` · **Blocking**

~~~python
    4 | LIMIT = 3
    5 |
    6 |
    7>| def load(path):
    8 |     """Load one file."""
    9 |     return open(path).read()
   10 |
~~~

<a id="finding-lints-004"></a>

#### LINTS-004 — `open()` should be replaced by `Path.open()`

**Severity:** warning · **Rule:** PTH123 · **Location:** `pkg/app.py:9:12` · **Blocking**

~~~python
    6 |
    7 | def load(path):
    8 |     """Load one file."""
    9>|     return open(path).read()
   10 |
   11 |
   12 | print(os.sep, LIMIT)
~~~

<a id="finding-lints-005"></a>

#### LINTS-005 — Use a context manager for opening files

**Severity:** warning · **Rule:** SIM115 · **Location:** `pkg/app.py:9:12` · **Blocking**

~~~python
    6 |
    7 | def load(path):
    8 |     """Load one file."""
    9>|     return open(path).read()
   10 |
   11 |
   12 | print(os.sep, LIMIT)
~~~

### basedpyright — 2 findings

<a id="finding-lints-006"></a>

#### LINTS-006 — Type annotation is missing for parameter "path"

**Severity:** error · **Rule:** reportMissingParameterType · **Location:** `pkg/app.py:7:10` · **Blocking**

~~~~text
Type annotation is missing for parameter "path"
  Parameter "path" is unannotated
~~~~

~~~python
    4 | LIMIT = 3
    5 |
    6 |
    7>| def load(path):
    8 |     """Load one file."""
    9 |     return open(path).read()
   10 |
~~~

<a id="finding-lints-007"></a>

#### LINTS-007 — Result of call expression is of type "None"

**Severity:** warning · **Rule:** reportUnusedCallResult · **Location:** `pkg/app.py:12:1`

~~~python
    9 |     return open(path).read()
   10 |
   11 |
   12>| print(os.sep, LIMIT)
~~~

### eslint — 1 finding

<a id="finding-lints-008"></a>

#### LINTS-008 — 'box' is never reassigned.

**Severity:** warning · **Rule:** prefer-const · **Location:** `web/app.js:1:7`

'box' is never reassigned. Use 'const' instead.

~~~javascript
    1>| const box = document.querySelector("#box");
    2 | box.style.color = "red";
~~~

## Artifacts

| Artifact | Path | Bytes |
| --- | --- | --- |
| stderr.log | ARTIFACTS/stderr.log | 0 |
| stdout.log | ARTIFACTS/stdout.log | 145 |

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
| PY002 | Module global `LIMIT` is uppercase but is not declared Final. | custom_python | 1 |
| JS005 | Static inline style `color` is assigned directly. | custom_javascript | 1 |
| ANN001 | Missing type annotation for function argument `path` | ruff | 1 |
| PTH123 | `open()` should be replaced by `Path.open()` | ruff | 1 |
| SIM115 | Use a context manager for opening files | ruff | 1 |
| reportMissingParameterType | Type annotation is missing for parameter "path" | basedpyright | 1 |
| reportUnusedCallResult | Result of call expression is of type "None" | basedpyright | 1 |
| prefer-const | 'box' is never reassigned. | eslint | 1 |


## Lint metrics

| Metric | Value |
| --- | --- |
| Linters run | 10 |
| Linters unavailable | 1 |
| Files analyzed | 3 |
| Files with findings | 2 |
| Rules triggered | 8 |
| Findings | 8 |

### Linters

| Linter | Status | Version | Files | Findings | Errors | Warnings | Information | Exit code | Duration (s) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| custom_python | ran | built-in | 1 | 1 | 0 | 1 | 0 | 0 | 0.25 |
| custom_javascript | ran | built-in | 2 | 1 | 0 | 1 | 0 | 0 | 0.25 |
| custom_css | ran | built-in | 0 | 0 | 0 | 0 | 0 | 0 | 0.25 |
| custom_html | ran | built-in | 0 | 0 | 0 | 0 | 0 | 0 | 0.25 |
| ruff | ran | 0.12.0 | 1 | 3 | 0 | 3 | 0 | 1 | 0.25 |
| ruff_docs | ran | 0.12.0 | 1 | 0 | 0 | 0 | 0 | 0 | 0.25 |
| basedpyright | ran | 1.39.0 | 1 | 2 | 1 | 1 | 0 | 1 | 0.25 |
| pyrefly | ran | 0.40.0 | 1 | 0 | 0 | 0 | 0 | 0 | 0.25 |
| eslint | ran | 9.12.0 | 2 | 1 | 0 | 1 | 0 | 0 | 0.25 |
| typescript | ran | 5.9.3 | 2 | 0 | 0 | 0 | 0 | 0 | 0.25 |
| stylelint | missing | N/A | 0 | 0 | 0 | 0 | 0 | N/A | N/A |
| htmlhint | not run | N/A | 0 | 0 | 0 | 0 | 0 | N/A | N/A |

### Top rules

| Rule | Linter | Findings |
| --- | --- | --- |
| PY002 | custom_python | 1 |
| JS005 | custom_javascript | 1 |
| ANN001 | ruff | 1 |
| PTH123 | ruff | 1 |
| SIM115 | ruff | 1 |
| reportMissingParameterType | basedpyright | 1 |
| reportUnusedCallResult | basedpyright | 1 |
| prefer-const | eslint | 1 |

### Files with the most findings

| Path | Findings |
| --- | --- |
| pkg/app.py | 6 |
| web/app.js | 2 |

---

Exactus · lints 0.5.0 · Run 0123456789abcdef0123456789abcdef · Result FAIL · Duration 4.2 s
