# Kwargs Typehints Exactus

**Run time:** N/A

## Identity

| Field | Value |
|---|---|
| Tool | kwargs-typehints 0.5.0 |
| Run ID | 0123456789abcdef0123456789abcdef |
| Pipeline run | N/A |
| Status | FAIL |
| Exit code | 1 |
| Started | N/A |
| Finished | N/A |
| Duration | 4.2 s |

## What was checked

**Result: FAIL** — 8 findings across 2 of 2 eligible targets.

| Severity | Count |
|---|---:|
| ERROR | 5 |
| WARNING | 1 |
| INFO | 2 |

### Metrics

| Metric | Value |
| --- | --- |
| Python files analyzed | 2 |
| Files that failed to parse | 0 |
| Call sites with positional arguments | 4 |
| Call sites resolved to a signature | 2 |
| Resolved (%) | 50 |
| Exempt call sites (positional-only or dynamic APIs) | 0 |
| Unresolved call sites | 2 |
| Other unchecked call sites | 0 |
| Functions checked | 5 |
| Parameters checked | 6 |
| Signature hint coverage (%) | 81.8 |
| Missing variable and attribute hints | 1 |
| Blocking findings | 5 |

#### Findings by category

| Category | Severity | Blocking | Findings |
|---|---|---|---:|
| Missing keyword arguments | error | Yes | 1 |
| Bare imports | error | Yes | 1 |
| Missing type hints | error | Yes | 3 |
| Parse failures | error | Yes | 0 |
| Ambiguous calls | warning | No | 1 |
| Unresolved callees | info | No | 2 |

### Change since previous report

No previous report exists; this run establishes the baseline.

### Scope

**Included**

- `**/*.py`

**Excluded**

- `exactus/packages/**`
- `**/__pycache__/**`
- `**/build/**`
- `**/dist/**`
- `**/mutants/**`
- `**/node_modules/**`
- `**/packages/**`

**Skipped targets**

No skipped targets.

## Setup

### Invocation

~~~~shell
python exactus/tools/kwargs_typehints/main.py .
~~~~

| Property | Value |
|---|---|
| Working directory | /work/project |
| Arguments | `.` |

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

> **Gate: FAIL** — 5 blocking findings

Blocking findings:

- KWARGS-001 — Pass `value` by keyword to `scale`
- KWARGS-002 — Bare `import json`
- KWARGS-003 — Missing return type hint for `total`
- KWARGS-004 — Missing parameter type hint for `items`
- KWARGS-005 — Missing variable type hint for `found`

## Findings

### By file

#### `pkg/mod.py`

8 findings — 5 error · 1 warning · 2 info

- [KWARGS-001](#finding-kwargs-001) — error · positional-argument · line 37
- [KWARGS-002](#finding-kwargs-002) — error · bare-import-manual · line 3
- [KWARGS-003](#finding-kwargs-003) — error · missing-return-hint · line 11
- [KWARGS-004](#finding-kwargs-004) — error · missing-parameter-hint · line 11
- [KWARGS-005](#finding-kwargs-005) — error · missing-variable-hint · line 35
- [KWARGS-006](#finding-kwargs-006) — warning · disagreeing-signatures · line 36
- [KWARGS-007](#finding-kwargs-007) — info · subscript-lookup · line 34
- [KWARGS-008](#finding-kwargs-008) — info · unknown-receiver · line 36

Grouped by category (blocking categories first), then ordered by path and line.

### Missing keyword arguments — 1 finding

<a id="finding-kwargs-001"></a>

#### KWARGS-001 — Pass `value` by keyword to `scale`

**Severity:** error · **Rule:** positional-argument · **Location:** `pkg/mod.py:37` · **Blocking**

`scale(…)` passes `3` positionally to the keyword-capable parameter `value` (signature: resolved). Write `value=3`.

~~~python
   34 |     registry["go"](7)
   35 |     found = registry["w"]
   36 |     found.walk(3)
   37>|     return json.dumps(obj=scale(3))
~~~

### Bare imports — 1 finding

<a id="finding-kwargs-002"></a>

#### KWARGS-002 — Bare `import json`

**Severity:** error · **Rule:** bare-import-manual · **Location:** `pkg/mod.py:3:1` · **Blocking**

No complete automatic rewrite is proposed because `json` is referenced from a nested lexical scope.

~~~python
    1 | """Demo module."""
    2 |
    3>| import json
    4 |
    5 |
    6 | def scale(value: int, factor: int = 2) -> int:
~~~

### Missing type hints — 3 findings

<a id="finding-kwargs-003"></a>

#### KWARGS-003 — Missing return type hint for `total`

**Severity:** error · **Rule:** missing-return-hint · **Location:** `pkg/mod.py:11:1` · **Blocking**

Callable has no explicit return annotation. Scope: `total`. Add `-> <return_type>`.

~~~python
    8 |     return value * factor
    9 |
   10 |
   11>| def total(items):
   12 |     """Sum items."""
   13 |     return sum(items)
   14 |
~~~

<a id="finding-kwargs-004"></a>

#### KWARGS-004 — Missing parameter type hint for `items`

**Severity:** error · **Rule:** missing-parameter-hint · **Location:** `pkg/mod.py:11:11` · **Blocking**

Function parameter has no explicit annotation. Scope: `total`. Add `items: <type>`.

~~~python
    8 |     return value * factor
    9 |
   10 |
   11>| def total(items):
   12 |     """Sum items."""
   13 |     return sum(items)
   14 |
~~~

<a id="finding-kwargs-005"></a>

#### KWARGS-005 — Missing variable type hint for `found`

**Severity:** error · **Rule:** missing-variable-hint · **Location:** `pkg/mod.py:35:5` · **Blocking**

Variable binding has no explicit annotation anywhere in its owning scope `dispatch`. Add `found: <type>`.

~~~python
   32 | def dispatch(registry: dict[str, object]) -> str:
   33 |     """Dispatch dynamically."""
   34 |     registry["go"](7)
   35>|     found = registry["w"]
   36 |     found.walk(3)
   37 |     return json.dumps(obj=scale(3))
~~~

### Ambiguous calls — 1 finding

<a id="finding-kwargs-006"></a>

#### KWARGS-006 — Ambiguous call `found.walk`

**Severity:** warning · **Rule:** disagreeing-signatures · **Location:** `pkg/mod.py:36`

2 candidate definitions disagree on the signature: `Gamma.walk`, `Delta.walk`. Review the call by hand.

~~~python
   33 |     """Dispatch dynamically."""
   34 |     registry["go"](7)
   35 |     found = registry["w"]
   36>|     found.walk(3)
   37 |     return json.dumps(obj=scale(3))
~~~

### Unresolved callees — 2 findings

<a id="finding-kwargs-007"></a>

#### KWARGS-007 — Unresolved callee `registry['go']`

**Severity:** info · **Rule:** subscript-lookup · **Location:** `pkg/mod.py:34:5`

The callee is a subscript lookup, so its positional arguments were not checked.

~~~python
   31 |
   32 | def dispatch(registry: dict[str, object]) -> str:
   33 |     """Dispatch dynamically."""
   34>|     registry["go"](7)
   35 |     found = registry["w"]
   36 |     found.walk(3)
   37 |     return json.dumps(obj=scale(3))
~~~

<a id="finding-kwargs-008"></a>

#### KWARGS-008 — Unresolved callee `found.walk`

**Severity:** info · **Rule:** unknown-receiver · **Location:** `pkg/mod.py:36:5`

The receiver's type is unknown, so its positional arguments were not checked.

~~~python
   33 |     """Dispatch dynamically."""
   34 |     registry["go"](7)
   35 |     found = registry["w"]
   36>|     found.walk(3)
   37 |     return json.dumps(obj=scale(3))
~~~

## Artifacts

| Artifact | Path | Bytes |
| --- | --- | --- |
| stderr.log | ARTIFACTS/stderr.log | 0 |
| heuristics.json | ARTIFACTS/heuristics.json | 3915729 |

## Unresolved callees

Callees with no known signature, so positional use at these call sites was not checked. Most call sites first; the Finding column names the finding with the source excerpt.

| Callee | Path | Line | Reason | Call sites | Finding |
|---|---|---:|---|---:|---|
| `found.walk` | pkg/mod.py | 36 | receiver type unknown | 1 | KWARGS-008 |
| `registry['go']` | pkg/mod.py | 34 | subscript lookup | 1 | KWARGS-007 |

## Ambiguous call sites

Several classes define the method and their signatures disagree, so these calls need a manual review.

| Callee | Path | Line | Candidates | Finding |
|---|---|---:|---|---|
| `found.walk` | pkg/mod.py | 36 | Gamma.walk, Delta.walk | KWARGS-006 |

## Bare imports

Bare `import module` statements outside the allowlist, with the explicit import that replaces each one when an automatic rewrite is safe.

| Module | Path | Line | Fix | Replacement | Finding |
|---|---|---:|---|---|---|
| `json` | pkg/mod.py | 3 | manual | N/A | KWARGS-002 |

## Automatic fixes

No automatic source edits were applicable.

## Methodology and caveats

- Signatures come from a repository-wide AST index (functions, methods, dataclass and `NamedTuple` fields, imports, `self.attr` assignments, annotations), `inspect.signature` for external callables and the typeshed stubs bundled with basedpyright.
- Confidence of a missing-keyword finding: `resolved` (project index), `constructor` (project class constructor), `external` (`inspect.signature`), `stub` (typeshed), `stub-rt` (typeshed checked by a runtime probe), `unique-name` (one class defines the method), `ambiguous-all-flag` (every candidate flags it).
- Arguments after a `*unpack`, beyond the named parameters of a `*args` signature, or already passed by keyword are not reported.
- Calls to `pytest.mark.*`, standard-library positional-only methods and Qt-style `lowerCamelCase` methods are counted as exempt, not as unresolved.
- A variable needs one annotation per lexical scope; parameters own their type, walrus bindings, TypeVar declarations and Enum members are exempt, `self`/`cls` need none, and lambdas cannot be annotated.
- Hint coverage counts the parameters (receivers excluded) and return annotations of every function; variables are not part of the ratio.
- Unresolved callees (dynamic objects, `*args` wrappers, mocks, higher-order results) are listed so they can be checked by hand; they never fail the run.
- `ARTIFACTS/heuristics.json` holds the argument types observed by fuzzing builtin callables.

---

Exactus · kwargs-typehints 0.5.0 · Run 0123456789abcdef0123456789abcdef · Result FAIL · Duration 4.2 s
