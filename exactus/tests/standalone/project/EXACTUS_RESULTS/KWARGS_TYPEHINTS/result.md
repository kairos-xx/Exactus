# Python Call, Import, and Typing Exactus

**Run time:** 31 October 2026, 05:10:45 UTC

## Identity

| Field | Value |
|---|---|
| Tool | kwargs_typehints |
| Run ID | 2c65e21142f34f8db22b09b30d9044d1:kwargs_typehints |
| Pipeline run | 2c65e21142f34f8db22b09b30d9044d1 |
| Status | PASS |
| Exit code | 0 |
| Started | 31 October 2026, 05:10:45 UTC |
| Finished | 31 October 2026, 05:10:47 UTC |
| Duration | 2.1 s |
| Previous duration | 1.523s |

## What was checked

**Result: PASS** — 0 findings across 6 of 6 eligible targets.

| Severity | Count |
|---|---:|
| ERROR | 0 |
| WARNING | 0 |
| INFO | 0 |

### Metrics

| Metric | Value |
| --- | --- |
| Python files analyzed | 6 |
| Files that failed to parse | 0 |
| Call sites with positional arguments | 3 |
| Call sites resolved to a signature | 3 |
| Resolved (%) | 100.0 |
| Exempt call sites (positional-only or dynamic APIs) | 0 |
| Unresolved call sites | 0 |
| Other unchecked call sites | 0 |
| Functions checked | 5 |
| Parameters checked | 5 |
| Signature hint coverage (%) | 100.0 |
| Missing variable and attribute hints | 0 |
| Blocking findings | 0 |

#### Findings by category

| Category | Severity | Blocking | Findings |
|---|---|---|---:|
| Missing keyword arguments | error | Yes | 0 |
| Bare imports | error | Yes | 0 |
| Missing type hints | error | Yes | 0 |
| Parse failures | error | Yes | 0 |
| Ambiguous calls | warning | No | 0 |
| Unresolved callees | info | No | 0 |

### Change since previous report

| Metric | Current | Previous | Delta |
|---|---:|---:|---:|
| Findings | 0 | 0 | 0 |
| Previous duration | 1.523s | | |

| Finding change | Count |
|---|---:|
| Added | 0 |
| Resolved | 0 |
| Unchanged | 0 |

#### Category findings

| Category | Title | Findings | Previous | Delta |
| --- | --- | --- | --- | --- |
| ambiguous-call | Ambiguous calls | 0 | 0 | 0 |
| bare-import | Bare imports | 0 | 0 | 0 |
| missing-hint | Missing type hints | 0 | 0 | 0 |
| missing-kwargs | Missing keyword arguments | 0 | 0 | 0 |
| parse-failure | Parse failures | 0 | 0 | 0 |
| unresolved-callee | Unresolved callees | 0 | 0 | 0 |

### Scope

**Included**

- `**/*.py`

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
- `**/build/**`
- `**/coverage_report/**`
- `**/dist/**`
- `**/env/**`
- `**/htmlcov/**`
- `**/mutants/**`
- `**/node_modules/**`
- `**/site-packages/**`
- `**/venv/**`

**Skipped targets**

No skipped targets.

## Setup

### Invocation

~~~~shell
/usr/local/bin/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=62458 --orchestrator-control-token=[redacted] --orchestrator-worker-port=62429 --orchestrator-worker-token=[redacted] '--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"kwargs_typehints","module":"exactus.tools.kwargs_typehints.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/KWARGS_TYPEHINTS","arguments":[],"run_id":"2c65e21142f34f8db22b09b30d9044d1:kwargs_typehints","pipeline_run_id":"2c65e21142f34f8db22b09b30d9044d1","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}'
~~~~

| Property | Value |
|---|---|
| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |
| Arguments | `exactus.tools.common.tool_worker` `ExactusTool` `--orchestrator-control-port=62458` `--orchestrator-control-token=[redacted]` `--orchestrator-worker-port=62429` `--orchestrator-worker-token=[redacted]` `--orchestrator-call={"args":[],"kwargs":{"request":{"identifier":"kwargs_typehints","module":"exactus.tools.kwargs_typehints.main","output":"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/KWARGS_TYPEHINTS","arguments":[],"run_id":"2c65e21142f34f8db22b09b30d9044d1:kwargs_typehints","pipeline_run_id":"2c65e21142f34f8db22b09b30d9044d1","project_root":"/Users/joaolopes/Exactus/exactus/tests/standalone/project"}}}` |

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
| EXACTUS_RUN_ID | 2c65e21142f34f8db22b09b30d9044d1:kwargs_typehints |
| EXACTUS_TOOL | kwargs_typehints |
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
| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 1867 |
| README.md | [ARTIFACTS/README.md](ARTIFACTS/README.md) | 460 |
| heuristics.json | [ARTIFACTS/heuristics.json](ARTIFACTS/heuristics.json) | 3915706 |
| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |
| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 0 |
| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 4275 |

## Unresolved callees

Callees with no known signature, so positional use at these call sites was not checked. Most call sites first; the Finding column names the finding with the source excerpt.

No unresolved callees: every checked call site resolved to a signature or is exempt.

## Ambiguous call sites

No ambiguous call sites.

## Bare imports

No bare imports.

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
- [`ARTIFACTS/heuristics.json`](ARTIFACTS/heuristics.json) holds the argument types observed by fuzzing builtin callables.

---

Exactus · kwargs_typehints · Run 2c65e21142f34f8db22b09b30d9044d1:kwargs_typehints · Result PASS · Duration 2.1 s
