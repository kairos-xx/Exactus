[Home](Home.md) > [Tools](Tools.md) > kwargs_typehints

# tools/kwargs_typehints/

The `kwargs_typehints` tool: enforce the keyword-call policy, the
explicit-import policy, and the explicit-typing policy across every Python
file in the project — and repair provably safe violations automatically.

Where a linter flags style, this tool enforces three project-wide contracts:

1. **Keyword calls** — every positional argument that binds to a
   keyword-capable parameter must be written as `name=value`.
2. **Explicit imports** — bare `import pkg.mod` statements are forbidden;
   code must use `from pkg.mod import Symbol` so every dependency is a
   named symbol.
3. **Explicit typing** — every variable, attribute, parameter, and return
   must carry an annotation anywhere Python syntax permits one.

The engine is a full semantic analyzer, not a regex pass: it builds a
repository-wide index of modules, classes, signatures, and imports, layers
typeshed stubs and live `inspect.signature` resolution on top, and only
reports a finding when the resolved signature *proves* the violation.
Anything it cannot prove is listed separately (ambiguous or unresolved)
instead of being guessed.

## Files

| File | Description |
|---|---|
| `arguments.py` | The kwargs_typehints CLI grammar, declared without importing the execution engine. |
| `core.py` | The analysis engine (~12k lines): project index, signature resolution, the three policy analyzers, the auto-heal pipeline, and report payload assembly. |
| `main.py` | Entry point: resolve config/CLI, invoke `core.main`, emit the `KWARGS_TYPEHINTS` report bundle. |
| `report.py` | Normalize the legacy payload into the standard envelope: `summary`, `scope`, `findings`, `extension` with categories and metrics. |
| `templates/` | `markdown/template.md` + `markdown/mapping.json` that render `result.md` from the normalized payload. |

`main.py` also defines `PathScope`, the include/exclude glob predicate
passed down as `path_filter`.

## Pipeline

Every run follows the same sequence (`core.main` →
`_analyze_until_stable` → `_finalize_analysis`):

1. **Discover** — `python_files()` walks `root` top-down, skipping hidden
   directories, `__pycache__`, `build`, `dist`, `mutants`,
   `node_modules`, `*.egg-info`, `*.dist-info`, hidden filenames, and any
   path rejected by `path_filter` (the `--include`/`--exclude` globs plus
   the shared `DEFAULT_EXCLUDES`).
2. **Index** — `Project` parses every discovered module into a
   repository-wide index: top-level functions and classes
   (`index_module`), class members (`index_class_item`), dataclass and
   `NamedTuple` constructor parameters, `self.attr` typed assignments,
   imports and aliases. Typeshed stubs bundled with basedpyright/pyright
   (`_typeshed_fallback_candidates`) and an optional `CapabilityIndex`
   extend the index to external callables.
3. **Scan** — `_scan_sources` runs `BareImportExactusor` and
   `TypeHintExactusor` over each module and counts functions/parameters
   checked.
4. **Resolve calls** — `_resolve_module_lane` runs `CallExactusor` per
   module, binding every call site to candidate signatures.
5. **Heal** — `_heal_sources` validates deterministic repairs and, unless
   `--dry`, applies them. Healed files are reparsed before writing.
6. **Stabilize** — if any file changed on disk (by healing or externally),
   the loop repeats from step 2 until the source inventory and content
   fingerprints are stable, so the report always describes post-repair
   sources.
7. **Report** — `_legacy_payload` + `report.py` write
   `KWARGS_TYPEHINTS.md`, `.json`, and `_web/`; `BuiltinTypeFuzzer`
   writes `ARTIFACTS/heuristics.json`; `--write-capability-index`
   optionally regenerates `CAPABILITY_INDEX.json`.

## Policy 1: keyword-call enforcement

A **finding** (`Finding`, category `missing-kwargs`) is one positional
argument that provably binds to a keyword-capable (`poskw`) parameter.

### Resolution

`CallExactusor` resolves each call's callee through a `Scope` chain that
models Python visibility (function bodies nested in a class do **not**
close over the class namespace). Resolution sources, in order:

- **Project index** — module/class/function records from the repo AST,
  including dataclass/`NamedTuple` synthesized constructors.
- **Live objects** — `inspect.signature` on imported external callables;
  results can be committed to `CAPABILITY_INDEX.json` so analysis runs
  identically on hosts where the callable resolves differently.
- **Typeshed** — the basedpyright `typeshed-fallback` stubs; each stub
  parameter kind is verified against the live runtime object
  (`verify_sets`) because stubs sometimes advertise keyword parameters
  that C functions reject at runtime.
- **Target interpreter** — typeshed gates definitions behind
  `sys.version_info`/`sys.platform` guards, so every guard is decided with
  the facts of the interpreter the *project* runs on (`--python`, else the
  project `.venv`/`venv`, else a `requires-python`-compatible `PATH`
  interpreter, else the running one), never the one hosting the analyzer.
  Example: `ctypes.POINTER` is `POINTER(cls)` on Python 3.14 but
  `POINTER(type, /)` on 3.13, so `POINTER(wintypes.DWORD)` is flagged for
  `cls=` only on a 3.14 project and is never rewritten on a 3.13 `.venv`.
  Regression tests: `test_pointer_keywords_follow_the_project_python` and
  `test_pointer_keywords_hold_on_a_real_python_313`.
- **`self.attr` / annotation tracking** — variable types inferred from
  annotations, `self.attr = Type()` assignments, container element types,
  and `with open(...) as f` receivers.

### Confidence labels

Every positional finding records how its signature was obtained:

| Confidence | Source |
|---|---|
| `resolved` | Project AST index |
| `constructor` | Project class constructor |
| `external` | `inspect.signature` on a live object |
| `stub` | Typeshed stub, unverified |
| `stub-rt` | Typeshed stub verified by a runtime probe |
| `typeshed` | Builtin method resolved straight from typeshed |
| `inspect` | Builtin method resolved by `inspect.signature` |
| `unique-name` | The method name exists on exactly one known class |
| `ambiguous-all-flag` | Multiple candidates, but every one flags the argument |

### Flagging rules (`apply_params`/`check_positional_arg`)

- Overloads: only arity-compatible parameter sets vote. An argument is
  flagged only when **every** compatible candidate binds it to a
  keyword-capable parameter; a mix of `poskw`/`posonly` verdicts produces
  an `ambiguous-call` finding instead.
- All-or-nothing per call: if any *later* positional argument would bind
  to a `posonly` parameter (or binds to nothing), the whole call is
  skipped — a partial keyword rewrite would be misleading.
- Starred arguments end positional analysis; the call is skipped when a
  `*unpack` is present.
- Arguments whose target parameter is already passed by keyword are not
  reported (it would be a duplicate binding).
- `stream.read/seek/truncate/write` calls on `n`/`offset`/`s`/`size` are
  carved out — the standard file-object convention.
- Builtin calls that never take keywords (`__import__`, `print`, `exec`,
  `eval`, `vars`) are skipped entirely.
- Exempt call sites are counted separately, not listed: `pytest.mark.*`
  dynamic factories, known stdlib positional-only method names (`write`,
  `update`, `joinpath`, `execute`, …), and `lowerCamelCase` names (Qt/JS
  foreign bindings, positional-only by convention).

### Unresolved and ambiguous calls

Calls that cannot be resolved are listed, never guessed — and never fail
the run:

- **`unresolved-callee`** (severity `info`) — one row per call site with a
  reason code: `unknown-name`, `unknown-receiver`, `call-result`,
  `subscript-lookup`, or `dynamic-expression`. Dynamic objects, `*args`
  wrappers, mocks, and higher-order results land here so they can be
  reviewed by hand.
- **`ambiguous-call`** (severity `warning`) — the callee name maps to
  multiple candidate signatures that disagree on whether the argument may
  be a keyword.

## Policy 2: explicit-import enforcement

`BareImportExactusor` flags every `import` statement — plain `import a`
or dotted `import a.b.c`, aliased or not — that is not on the allowlist
(category `bare-import`). The required style is `from a.b.c import
Symbol`, so each finding carries a scope-aware proposed rewrite: the
replacement import statement plus every use-site replacement
(`a.b.c.Symbol` → `Symbol`).

- `--allow-bare-import MODULE` permits `MODULE` only as a standalone,
  unaliased `import MODULE`. Tool-level default: `pytest`, `lints`
  (core default: `pytest`). Multi-name or aliased imports of an allowed
  module are still findings.
- A rewrite is **safe** only when the analyzer observed at least one use
  and collected zero `unsafe_reasons`. Reasons include: the bound name is
  rebound by a later bare import, declared `global`/`nonlocal`, shadowed
  by other bindings, used through complex control flow, referenced from
  nested class scopes, or has uses that cannot be located statically.
- `generated_names` picks collision-free symbol names (aliasing when the
  direct name is already bound in the scope).
- Unsafe findings keep `safe: false` with a `reason` — they are reported
  but never auto-healed.

## Policy 3: explicit-typing enforcement

`TypeHintExactusor` walks each file through `TypeScope` records (module,
function, class, lambda, comprehension) and reports missing annotations
(category `missing-hint`) in four kinds:

| Kind | What is flagged |
|---|---|
| `parameter` | Any `def` parameter without an annotation — positional, keyword-only, `*args`, `**kwargs`. The method receiver `self`/`cls` (non-`@staticmethod`) is exempt. |
| `return` | Any function without a return annotation (`-> None` is suggested for `__init__`). |
| `variable` | A `name = value` binding whose name has no annotation anywhere in its owning scope. Tuple/starred destructuring is unwrapped; `_` is ignored. |
| `attribute` | `self.x = …`/`cls.x = …` with no annotation anywhere in the class (reported once per attribute). |

Scope semantics:

- One annotation per **owning scope** suffices — `scope.owner(name)`
  routes `global`/`nonlocal` names to the scope that actually owns them,
  and each name is reported at most once per scope.
- **Exempt**: walrus `:=` bindings (the exemption covers the name for the
  whole scope), `TypeVar` declarations via `typing`/`typing_extensions`
  (direct, aliased, or qualified import recognized), members of
  Enum-family classes (`Enum`, `IntEnum`, `Flag`, `IntFlag`, `StrEnum`,
  `ReprEnum`), and lambda signatures — Python gives them no annotation
  syntax.
- **`--strict`/`-s`** additionally reports bindings whose syntax cannot
  carry an annotation: `for`/`with ... as`/`except ... as`/`match`
  capture/comprehension targets. The suggestion then reads "declare
  `name: <type>` in `scope` before this binding or refactor the
  construct" — the fix is a pre-declared annotation, not an inline one.
- Type-hint findings are **never** auto-healed: the tool reports the
  location and a `name: <type>` template but does not guess concrete
  types.

## Auto-healing

Healing is **on by default**; `--dry`/`--dry-run` makes it report-only.

| Repair | How it works |
|---|---|
| `keyword-argument` | Re-locate the exact `Call` node (unique match on line, callee text, argument text at the recorded index), then insert only `param=` before the argument — a pure insertion that preserves formatting. |
| `bare-import` | Replace the whole `import` statement with the proven `from … import …` suggestion, and apply every recorded use-site replacement in the same pass. |
| `bare-import-use` | One use-site expression replacement belonging to a bare-import fix; reported individually for review. |

Safety boundaries:

- A keyword edit is only generated when the call site matches **exactly
  once**; ambiguous or shifted matches are skipped.
- A bare-import fix is only generated when `safe` is true; each planned
  replacement is verified against the actual source text before it is
  included.
- Every candidate file is reparsed before writing; if the healed source
  fails to parse or equals the original, nothing is written.
- Import and use-site edits within a file apply **atomically** — a file
  is written once with all validated edits.
- The stabilization loop rescans after any write, so follow-on effects
  (a healed import changing resolution) are re-audited before the report
  is produced.

Each applied or proposed edit is recorded in `auto_fixes` with
`file`/`line`/`column`/`kind`/`original`/`replacement` and
`status: "fixed"` (applied) or `"would-fix"` (dry run).

## CLI and configuration

Tool-level (`main.py`, shared grammar from `arguments.py`):

```bash
python -m exactus.tools.kwargs_typehints.main [ROOT] [options]
```

| Option | Effect |
|---|---|
| `root` (positional) | Project root (default: current directory). |
| `-o`, `--output-dir PATH` | Report bundle directory (default: `EXACTUS_RESULTS/KWARGS_TYPEHINTS`). |
| `--include GLOB` / `--exclude GLOB` | Restrict scope; repeatable. The fixed `DEFAULT_EXCLUDES` always apply. |
| `--context-lines N` | Source lines embedded around each finding excerpt. |
| `--allow-bare-import MODULE` | Permit `MODULE` as a bare `import MODULE`; repeatable (default: `pytest`, `lints`). |
| `-s`, `--strict` | Also report bindings that cannot carry an inline annotation. |
| `--dry`, `--dry-run` | Report validated repairs without writing sources. |
| `--collect-files` | Bundle every file with findings into a `FILES/` folder beside the report. |
| `--python INTERPRETER` | Interpreter whose version/platform steer inference — an executable path, a `PATH` name, or a virtual-environment directory. |

The core engine's own parser (`core.parse_args`) additionally accepts
`--root`, `--output`, `--heuristics-output`, `--capability-index`, and
`--write-capability-index` for direct invocation and index regeneration.

Every long option accepts `-` and `_` interchangeably: `--collect_files`
and `--collect-files`, `--allow_bare_import` and `--allow-bare-import`
are the same flag.

Configuration (`resolve_arguments`): `pyproject.toml` `[tool.exactus]`
and `[tool.exactus.kwargs_typehints]` accept the same options —
e.g. `dry = true`, `strict = true`, `include`/`exclude` lists. Explicit
CLI arguments take precedence over configuration.

Interpreter selection: a configured `python` wins outright; otherwise a
project `.venv`/`venv` is used unconditionally — even when its version
violates `requires-python`, because the environment the project runs on
is the truth inference should model. Only with no project interpreter
does the analyzer probe `python3`/`python` on `PATH` against
`requires-python`, falling back to the running interpreter last.

## Report

`report.py` normalizes the run into the standard Exactus envelope.

### Categories

| Category | Severity | Blocking | Content |
|---|---|---|---|
| `missing-kwargs` | error | yes | Positional args that must be keywords |
| `bare-import` | error | yes | Forbidden bare imports |
| `missing-hint` | error | yes | Missing variable/attribute/parameter/return annotations |
| `parse-failure` | error | yes | Files that could not be parsed |
| `ambiguous-call` | warning | no | Calls with disagreeing candidate signatures |
| `unresolved-callee` | info | no | Call sites with no resolvable signature |

Findings are numbered `KWARGS-001`… ordered by category, path, line,
column; each keeps its legacy fields (`callee`, `parameter`, `argument`,
`confidence`, `suggestion`, `kind`, `safe`, `reason`, …) plus the
normalized `id`/`title`/`severity`/`rule`/`category`/`source`/`blocking`
envelope.

### Metrics (`extension.metrics.overview`)

`files_scanned`, `files_analyzed`, `parse_failures`, `call_sites`,
`resolved_call_sites`, `resolution_percent`, `exempt_call_sites`,
`unresolved_call_sites`, `skipped_call_sites`, `functions_checked`,
`parameters_checked`, `missing_parameter_hints`,
`missing_return_hints`, `missing_variable_hints`,
`hint_coverage_percent`, `findings`, `blocking_findings`, `auto_fixes`.
Hint coverage counts parameter and return annotations only; variables
are not part of the ratio.

### Artifacts

- `KWARGS_TYPEHINTS.md` / `KWARGS_TYPEHINTS.json` /
  `KWARGS_TYPEHINTS_web/` — the report bundle, inside `--output-dir`.
- `ARTIFACTS/heuristics.json` — argument types observed by
  `BuiltinTypeFuzzer` probing builtin callables.
- `ARTIFACTS/steps.txt` — the run trace; `stderr.log` and `@activity.json`
  come from the shared execution wrapper.
- `CAPABILITY_INDEX.json` — signature truth for external callables;
  consumed when present, regenerated with `--write-capability-index`.

### Exit status

`1` when any blocking category is non-empty (`missing-kwargs`,
`bare-import`, `missing-hint`, `parse-failure`); `0` otherwise.
Ambiguous and unresolved listings never fail the run.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/tools/kwargs_typehints/`](../exactus/tools/kwargs_typehints/) | [`exactus/tests/tools/kwargs_typehints/`](../exactus/tests/tools/kwargs_typehints/) | [`DOCS.md`](../exactus/docs/tools/kwargs_typehints/DOCS.md) |

[< Tools-frontend](Tools-frontend.md) · [Tools index](Tools.md) · [Tools-lints >](Tools-lints.md)
