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

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Kwargs and type-hint exactus tool. |
| `arguments.py` | Declare the kwargs_typehints CLI grammar. |
| `core.py` | Exactus keyword-call policy, imports, and explicit typing. |
| `main.py` | Exactus keyword usage, imports, and explicit type hints. |
| `report.py` | Normalize the KWARGS_TYPEHINTS report: findings, metrics and tables. |
| `templates/` | Subdirectory. |

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--allow-bare-import` |  | action='append', default=['pytest', 'lints'], metavar='MODULE' |
| `-s, --strict` | also report bindings that cannot carry an annotation (loop, with, except, match, and comprehension targets); without it only plain `name = value` assignments are reported | action='store_true' |
| `--python` | interpreter or virtual-environment directory whose version/platform steer inference; defaults to the project .venv, then requires-python probes, then self | default=None, metavar='INTERPRETER' |
| `--root` | repository root (default: directory containing exactus/) | type=Path, default=Path(__file__).resolve().parents[3] |
| `--output` | report path (default: <root>/POSITIONAL_ARGS_EXACTUS.md) | type=Path, default=None |
| `--allow-bare-import` | permit MODULE only as a standalone unaliased `import MODULE`; repeatable (default: pytest) | action='append', default=sorted(BareImportExactusor.DEFAULT_ALLOWED), metavar='MODULE' |
| `--python` | interpreter or virtual-environment directory whose version/platform steer inference; defaults to the project .venv, then requires-python probes, then self | default=None, metavar='INTERPRETER' |
| `--heuristics-output` | builtin type-fuzz heuristics JSON path (default: <root>/heuristics.json) | type=Path, default=None |
| `--context-lines` | source lines captured around each finding line (default: %(default)s) | type=context_lines, default=SnippetLimits.default_context, metavar='N' |
| `--capability-index` | canonical capability index to consume (default: CAPABILITY_INDEX.json beside this module when present) | type=Path, default=None |
| `--write-capability-index` | regenerate the canonical capability index at PATH from this interpreter; live resolution is used and any committed index is ignored | type=Path, default=None |
| `--dry, --dry-run` | report deterministic repairs without modifying sources | action='store_true', dest='dry' |
| `-s, --strict` | also report bindings that cannot carry an annotation (loop, with, except, match, and comprehension targets); without it only plain `name = value` assignments are reported | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Kwargs and type-hint exactus tool.


### `arguments.py`

Declare the kwargs_typehints CLI grammar.

- `create_parser() -> ArgumentParser` — Create parser.

### `core.py`

Exactus keyword-call policy, imports, and explicit typing.

- `class BoundedLaneProgress` — Publish bounded progress checkpoints for high-cardinality stages.
  - `checkpoints` = `32`
  - `__init__(self: Self, *, total: int, step: str, span: tuple[float, float]) -> None` — Initialize a thread-safe bounded progress lane.
  - `finish(self: Self, *, item: str, error: str | None=None) -> None` — Complete one item and publish only useful checkpoints.
- `class FuzzValue` — One reusable runtime type-fuzzing value factory.
  - Fields: `type_name: str`, `factories: tuple[Callable[[], LiveObject], ...]`
- `class Constants` — Static lookup tables and probe fixtures for the exactus.
  - `dataclass_markers` = `frozenset({'dataclass', 'dataclasses.dataclass'})`
  - `skip_dirs` = `ExactusCommonTables.DEFAULT_EXCLUDED_DIRS`
  - `file_openers` = `frozenset({'open', 'fdopen', 'popen'})`
  - `skip_calls` = `frozenset({'__import__', 'print', 'exec', 'eval', 'vars'})`
  - `dynamic_callee_prefixes` = `('pytest.mark.',)`
  - `positional_only_methods` = `frozenset({'bind', 'connect', 'count', 'emit', 'end', 'execute', 'execute...`
  - `foreign_binding_pattern` = `'^[a-z]+[A-Z]\\w*$'`
  - `receiver_names` = `frozenset({'self', 'cls'})`
  - `callable_kinds` = `frozenset({'function', 'class', 'instance', 'stubclass', 'stubinstance'})`
  - `probe_default` = `None`
  - `probe_values` = `{'base': 10, 'byteorder': 'big', 'count': 0, 'default': None, 'encoding':...`
  - `receiver_factories` = `{'bool': lambda: True, 'bytearray': partial(bytearray, b'x'), 'bytes': la...`
  - `probe_blocklist` = `frozenset({'__import__', 'breakpoint', 'compile', 'eval', 'exec', 'exit',...`
  - `probe_safe_modules` = `frozenset({'_bisect', '_heapq', '_operator', '_statistics', 'cmath', 'mat...`
  - `posonly_params` = `{'_contextvars.ContextVar': frozenset({'name'}), 'contextvars.ContextVar'...`
  - `max_depth` = `15`
  - `interpreter_candidates` = `(Path('.venv/bin/python'), Path('.venv/Scripts/python.exe'), Path('venv/b...`
  - `interpreter_probe` = `'import json, sys; print(json.dumps([list(sys.version_info), sys.platform...`
  - `interpreter_timeout` = `20.0`
  - `fixture_hints` = `{'monkeypatch': 'pytest.MonkeyPatch', 'tmp_path': 'pathlib.Path', 'capsys...`
  - `optional_wrappers` = `frozenset({'Annotated', 'ClassVar', 'Final', 'NotRequired', 'Optional', '...`
  - `container_names` = `frozenset({'Collection', 'Iterable', 'Iterator', 'KeysView', 'MutableSequ...`
  - `iterable_wrappers` = `frozenset({'copy', 'frozenset', 'iter', 'list', 'reversed', 'set', 'sorte...`
  - `type_fuzz_values` = `(FuzzValue(type_name='NoneType', factories=(lambda: None,)), FuzzValue(ty...`
- `class Param` — One parameter of a callable signature.
  - `has_default` = `False`
  - Fields: `name: str`, `kind: ParamKind`
- `class Sig` — Resolved signature for a callable.
  - `method` = `'function'`
  - `returns` = `None`
  - Fields: `name: str`, `params: tuple[Param, ...]`
- `class VerifyRecord` — Canonical ``verify_sets`` outcome for one external callable.
  - Fields: `sets: tuple[tuple[Param, ...], ...]`, `conclusive: bool`
- `class CapabilityIndex` — Canonical runtime capability snapshot for external callables.
  - Fields: `verify: dict[str, VerifyRecord]`, `sigs: dict[str, tuple[Param, ...] | None]`, `types: dict[str, str | None]`, `absent: frozenset[str]`, `python_version: str`, `executable: str`
  - `load(cls: type[Self], *, path: Path) -> Self` — Load a committed capability index snapshot.
  - `dump(self: Self, *, path: Path) -> None` — Write the canonical index snapshot.
- `class ClassInfo` — Indexed class definition.
  - `methods` = `field(default_factory=dict)`
  - `nested` = `field(default_factory=dict)`
  - `bases` = `field(default_factory=list)`
  - `fields` = `None`
  - `attr_types` = `field(default_factory=dict)`
  - `attr_calls` = `field(default_factory=dict)`
  - `attr_elems` = `field(default_factory=dict)`
  - `class_calls` = `field(default_factory=dict)`
  - Fields: `name: str`, `module: str`, `path: Path`
- `class ModuleInfo` — Indexed module.
  - `functions` = `field(default_factory=dict)`
  - `classes` = `field(default_factory=dict)`
  - `aliases` = `field(default_factory=dict)`
  - `module_aliases` = `field(default_factory=dict)`
  - `var_types` = `field(default_factory=dict)`
  - `var_calls` = `field(default_factory=dict)`
  - `call_exprs` = `field(default_factory=dict)`
  - `tree` = `None`
  - Fields: `name: str`, `path: Path`, `is_package: bool`
- `class StubModule` — Parsed typeshed stub module.
  - `functions` = `field(default_factory=dict)`
  - `classes` = `field(default_factory=dict)`
  - `reexports` = `field(default_factory=dict)`
  - `star_sources` = `field(default_factory=list)`
  - Fields: `name: str`
- `class StubClass` — Parsed typeshed stub class.
  - `methods` = `field(default_factory=dict)`
  - `nested` = `field(default_factory=dict)`
  - `bases` = `field(default_factory=list)`
  - `ctors` = `field(default_factory=list)`
  - Fields: `name: str`
- `class Resolved` — Outcome of resolving one expression.
  - `kind` = `'unknown'`
  - `sig` = `None`
  - `sigs` = `()`
  - `cls` = `None`
  - `module` = `None`
  - `bound` = `False`
  - `obj` = `None`
  - `ext_kind` = `'other'`
  - `stub` = `None`
  - `dotted` = `''`
- `class Finding` — One positional argument bound to a keyword-capable parameter.
  - Fields: `path: Path`, `line: int`, `callee: str`, `param: str`, `index: int`, `argument: str`, `confidence: str`, `suggestion: str`
- `class AmbiguousCall` — Call whose callee name maps to multiple disagreeing signatures.
  - Fields: `path: Path`, `line: int`, `callee: str`, `candidates: tuple[str, ...]`
- `class UnresolvedCall` — Call site whose callee could not be resolved to a signature.
  - Fields: `path: Path`, `line: int`, `column: int`, `callee: str`, `reason: str`
- `class Scope` — Lexical scope for name resolution.
  - `__init__(self: Self, *, parent: Scope | None, classinfo: ClassInfo | None, class_body: bool=False) -> None` — Initialize the scope.
  - `enclosing_class(self: Self) -> ClassInfo | None` — Return the nearest enclosing class record.
  - `visible_scopes(self: Self) -> Iterator[Scope]` — Yield scopes whose names are visible for bare-name lookup.
  - `lookup_def(self: Self, *, name: str) -> Sig | None` — Find a callable bound under `name` in this scope chain.
  - `lookup_class(self: Self, *, name: str) -> ClassInfo | None` — Find a class bound under `name` in this scope chain.
  - `lookup_var(self: Self, *, name: str) -> str | None` — Find the class name bound to variable `name`.
  - `lookup_elem(self: Self, *, name: str) -> str | None` — Find the iterated element type recorded for `name`.
  - `lookup_call(self: Self, *, name: str) -> Resolved | None` — Find a callable bound to variable `name` in this scope chain.
  - `lookup_alias(self: Self, *, name: str) -> str | None` — Find a function-local `from x import y` target.
  - `lookup_module_alias(self: Self, *, name: str) -> str | None` — Find a function-local `import x` target.
- `class ImportUse` — One module-qualified expression that can be rewritten safely.
  - Fields: `line: int`, `column: int`, `original: str`, `symbol: str`, `suffix: tuple[str, ...]`
- `class BareImportPlan` — Mutable analysis state for one analyzed bare import.
  - `nested_reserved` = `field(default_factory=set)`
  - `uses` = `field(default_factory=list)`
  - `value_uses` = `False`
  - `unsafe_reasons` = `field(default_factory=set)`
  - `generated_names` = `field(default_factory=dict)`
  - Fields: `path: Path`, `line: int`, `column: int`, `module: str`, `bound: str`, `prefix: tuple[str, ...]`, `scope_key: int`, `reserved: frozenset[str]`
  - `safe(self: Self) -> bool` — Return whether the entire import can be rewritten safely.
- `class BareImportFinding` — One forbidden bare import and its scope-aware proposed rewrite.
  - Fields: `path: Path`, `line: int`, `column: int`, `module: str`, `bound: str`, `safe: bool`, `suggestion: str`, `replacements: tuple[tuple[int, int, str, str], ...]`, `reason: str`
- `class BareImportExactusor` — Detect bare imports and derive collision-safe explicit-import fixes.
  - `DEFAULT_ALLOWED` = `frozenset({'pytest'})`
  - `__init__(self: Self, *, path: Path, allowed: frozenset[str], tree: Module | None=None) -> None` — Initialize one file exactus.
  - `target_names(cls: type[Self], *, node: AST) -> set[str]` — Return names bound by an assignment-style target.
  - `scope_bindings(cls: type[Self], *, body: list[stmt], parameters: arguments | None=None) -> set[str]` — Collect names statically bound in one lexical scope.
  - `collect_statement_bindings(cls: type[Self], *, node: AST, names: set[str], globals_: set[str], nonlocals: set[str]) -> None` — Collect bindings from one statement without entering child scopes.
  - `assignment_bindings(cls: type[Self], *, node: Assign | AnnAssign | AugAssign | NamedExpr | For | AsyncFor, names: set[str]) -> None` — Collect names bound by assignment-style statements.
  - `with_bindings(cls: type[Self], *, node: With | AsyncWith, names: set[str]) -> None` — Collect names bound by with-statement optional targets.
  - `comprehension_bindings(cls: type[Self], *, node: ListComp | SetComp | DictComp | GeneratorExp, names: set[str], globals_: set[str], nonlocals: set[str]) -> None` — Collect walrus bindings inside a comprehension's parts.
  - `child_bindings(cls: type[Self], *, node: AST, names: set[str], globals_: set[str], nonlocals: set[str]) -> None` — Collect bindings from child nodes, skipping lambda bodies.
  - `contains_attribute_use(cls: type[Self], *, node: AST, name: str) -> bool` — Return whether a subtree accesses attributes on a bare name.
  - `import_bindings(*, node: Import | ImportFrom, names: set[str]) -> None` — Collect names bound by one import statement.
  - `flatten_attribute(*, node: Attribute) -> tuple[str, tuple[str, ...]] | None` — Flatten an attribute chain to its root name and attributes.
  - `import_shape(*, imported: alias) -> tuple[str, tuple[str, ...]]` — Return the runtime binding name and module-prefix attributes.
  - `preserved_import(*, plan: BareImportPlan) -> str` — Rebuild the original bare import for retained module value uses.
  - `unique_name(*, preferred: str, module: str, reserved: set[str]) -> str` — Choose a collision-free imported symbol binding.
  - `external_declarations(*, body: list[stmt]) -> set[str]` — Return names declared ``global`` or ``nonlocal`` in a scope.
  - `contains_loaded_name(*, node: AST, name: str) -> bool` — Return whether a subtree loads a bare name outside deeper scopes.
  - `record_attribute_use(*, node: Attribute, attrs: tuple[str, ...], plan: BareImportPlan) -> None` — Record a safely rewritable module attribute expression.
  - `exactus(self: Self) -> tuple[BareImportFinding, ...]` — Exactus the file and return scope-aware bare-import findings.
  - `ensure_all_imports(self: Self, *, tree: Module) -> None` — Ensure imports in non-linear structures are still diagnosed.
  - `exactus_scope(self: Self, *, body: list[stmt], bindings: set[str], external_names: set[str], inherited: dict[str, BareImportPlan] | None=None) -> None` — Exactus one lexical scope in execution order.
  - `exactus_statement(self: Self, *, node: stmt, active: dict[str, BareImportPlan], bindings: set[str], external_names: set[str]) -> None` — Exactus one statement, updating sequential module bindings.
  - `exactus_function_statement(self: Self, *, node: FunctionDef | AsyncFunctionDef, active: dict[str, BareImportPlan]) -> None` — Exactus one function definition and its inner scope.
  - `exactus_class_statement(self: Self, *, node: ClassDef, active: dict[str, BareImportPlan]) -> None` — Exactus one class definition and its inner scope.
  - `exactus_assignment(self: Self, *, node: Assign | AnnAssign | AugAssign, active: dict[str, BareImportPlan]) -> None` — Exactus one assignment statement in evaluation order.
  - `exactus_other_statement(self: Self, *, node: stmt, active: dict[str, BareImportPlan]) -> None` — Exactus a generic statement's uses and rebound bindings.
  - `record_bare_import(self: Self, *, node: Import, active: dict[str, BareImportPlan], bindings: set[str], external_names: set[str]) -> None` — Record analysis plans from one bare import statement.
  - `scan_function_definition(self: Self, *, node: FunctionDef | AsyncFunctionDef, active: dict[str, BareImportPlan]) -> None` — Scan expressions evaluated while defining a function.
  - `scan_class_definition(self: Self, *, node: ClassDef, active: dict[str, BareImportPlan]) -> None` — Scan expressions evaluated before entering a class body.
  - `mark_nested_references(self: Self, *, body: list[stmt], active: dict[str, BareImportPlan], local_bindings: set[str]) -> None` — Classify ancestor module references inside a child lexical scope.
  - `mark_complex_flow(self: Self, *, node: stmt, active: dict[str, BareImportPlan]) -> None` — Conservatively handle loops/context managers with binding ambiguity.
  - `shadow_targets(self: Self, *, node: AST, active: dict[str, BareImportPlan]) -> None` — Apply a deterministic assignment target to active bindings.
  - `scan_node(self: Self, *, node: AST, active: dict[str, BareImportPlan]) -> None` — Scan an expression subtree for uses of active module bindings.
  - `scan_lambda(self: Self, *, node: Lambda, active: dict[str, BareImportPlan]) -> None` — Classify active bindings referenced from a lambda body.
  - `scan_comprehension(self: Self, *, node: ListComp | SetComp | DictComp | GeneratorExp, active: dict[str, BareImportPlan]) -> bool` — Flag active bindings shadowed by comprehension targets.
  - `scan_attribute(self: Self, *, node: Attribute, active: dict[str, BareImportPlan]) -> bool` — Record an attribute chain rooted at an active binding.
  - `finalize(self: Self) -> tuple[BareImportFinding, ...]` — Finalize aliases, replacements, and human-readable findings.
- `class TypeHintFinding` — One missing explicit type annotation.
  - Fields: `path: Path`, `line: int`, `column: int`, `kind: Literal['variable', 'attribute', 'parameter', 'return']`, `name: str`, `scope: str`, `suggestion: str`, `reason: str`
- `class TypeScope` — Lexical annotation state used by the type-hint exactus.
  - `imports` = `field(default_factory=dict)`
  - `reported` = `field(default_factory=set)`
  - Fields: `parent: TypeScope | None`, `kind: Literal['module', 'function', 'class', 'lambda', 'comprehension']`, `label: str`, `annotations: set[str]`, `bindings: set[str]`, `globals: set[str]`, `nonlocals: set[str]`
  - `module_scope(self: Self) -> TypeScope` — Return the root module scope.
  - `owner(self: Self, *, name: str) -> TypeScope` — Resolve the lexical scope owning a bound name.
- `class ClassAnnotationState` — Class-wide instance/class attribute annotation state.
  - `reported` = `field(default_factory=set)`
  - `enum_like` = `False`
  - Fields: `label: str`, `annotations: set[str]`
- `is_name_assign(node: AST) -> bool` — Return whether node assigns directly to at least one name.
- `class CheckTargetArgs` — Represent check target args.
  - Fields: `target: AST`, `scope: TypeScope`, `class_state: ClassAnnotationState | None`, `line: int`, `column: int`, `source: NotRequired[str]`, `syntax_permits_annotation: NotRequired[bool]`
- `class CheckNameArgs` — Represent check name args.
  - Fields: `name: str`, `scope: TypeScope`, `line: int`, `column: int`, `source: str`, `syntax_permits_annotation: NotRequired[bool]`
- `class TypeHintExactusor` — Detect missing variable, parameter, and return annotations by scope.
  - `RECEIVERS` = `frozenset({'self', 'cls'})`
  - `ENUM_BASES` = `frozenset({'Enum', 'IntEnum', 'Flag', 'IntFlag', 'StrEnum', 'ReprEnum'})`
  - `__init__(self: Self, *, path: Path, strict: bool, tree: Module | None=None) -> None` — Initialize one source-file type-hint exactus.
  - `make_scope(cls: type[Self], *, body: list[stmt], parent: TypeScope | None, kind: Literal['module', 'function', 'class', 'lambda', 'comprehension'], label: str, parameters: arguments | None=None) -> TypeScope` — Create a scope with whole-scope annotation/binding knowledge.
  - `collect_scope_metadata(cls: type[Self], *, body: list[stmt]) -> tuple[set[str], set[str], set[str], dict[str, str], set[str]]` — Collect direct-scope metadata and owned walrus bindings.
  - `class_annotations(cls: type[Self], *, node: ClassDef) -> set[str]` — Collect ``self.attr``/``cls.attr`` annotations class-wide.
  - `enum_like(cls: type[Self], *, node: ClassDef) -> bool` — Return whether a class derives from a standard enum base.
  - `check_annotated_attribute(cls: type[Self], *, target: Attribute, class_state: ClassAnnotationState | None) -> None` — Record a directly encountered owned attribute annotation.
  - `typevar_declaration(*, node: Assign, scope: TypeScope) -> bool` — Recognize TypeVar factories without exempting ordinary variables.
  - `collect_walrus_bindings(*, body: list[stmt]) -> set[str]` — Collect walrus-created names owned by one lexical scope.
  - `child_label(*, scope: TypeScope, name: str) -> str` — Build a qualified lexical-scope label.
  - `exactus(self: Self) -> tuple[TypeHintFinding, ...]` — Exactus the file for missing explicit type hints.
  - `walk_body(self: Self, *, body: list[stmt], scope: TypeScope, class_state: ClassAnnotationState | None) -> None` — Walk statements in one lexical annotation scope.
  - `walk_node(self: Self, *, node: AST, scope: TypeScope, class_state: ClassAnnotationState | None) -> None` — Inspect one AST node without crossing scope boundaries implicitly.
  - `walk_generic(self: Self, *, node: AST, scope: TypeScope, class_state: ClassAnnotationState | None) -> None` — Check pattern bindings and recurse into child nodes.
  - `walk_assignment(self: Self, *, node: Assign | AnnAssign | AugAssign, scope: TypeScope, class_state: ClassAnnotationState | None) -> None` — Check assignment targets and walk evaluated expressions.
  - `walk_for(self: Self, *, node: For | AsyncFor, scope: TypeScope, class_state: ClassAnnotationState | None) -> None` — Check a loop target and walk its iterable and body.
  - `walk_with(self: Self, *, node: With | AsyncWith, scope: TypeScope, class_state: ClassAnnotationState | None) -> None` — Check with-item targets and walk context expressions.
  - `walk_except(self: Self, *, node: ExceptHandler, scope: TypeScope, class_state: ClassAnnotationState | None) -> None` — Check an exception target and walk its type and body.
  - `exactus_function(self: Self, *, node: FunctionDef | AsyncFunctionDef, scope: TypeScope, class_state: ClassAnnotationState | None) -> None` — Check a function signature and recurse into its own scope.
  - `check_signature(self: Self, *, node: FunctionDef | AsyncFunctionDef, scope: TypeScope, label: str) -> None` — Report unannotated parameters and missing return annotations.
  - `exactus_class(self: Self, *, node: ClassDef, scope: TypeScope) -> None` — Exactus a class body in a fresh lexical/class-attribute scope.
  - `exactus_lambda(self: Self, *, node: Lambda, scope: TypeScope, class_state: ClassAnnotationState | None) -> None` — Exactus lambda-local bindings that cannot carry annotations.
  - `exactus_comprehension(self: Self, *, node: ListComp | SetComp | DictComp | GeneratorExp, scope: TypeScope, class_state: ClassAnnotationState | None) -> None` — Exactus comprehension bindings in their implicit child scope.
  - `walk_comprehension_expr(self: Self, *, node: AST, scope: TypeScope, walrus_scope: TypeScope, class_state: ClassAnnotationState | None) -> None` — Walk a comprehension expression with correct walrus ownership.
  - `check_target(self: Self, **kwargs: Unpack[CheckTargetArgs]) -> None` — Check target.
  - `check_name(self: Self, **kwargs: Unpack[CheckNameArgs]) -> None` — Check name.
  - `check_attribute(self: Self, *, target: Attribute, class_state: ClassAnnotationState | None, source: str, syntax_permits_annotation: bool) -> None` — Report an untyped ``self``/``cls`` attribute once per class.
- `python_files(*, root: Path, path_filter: Callable[[Path], bool] | None=None) -> list[Path]` — Collect every non-hidden, non-excluded Python file under `root`.
- `configured_source_roots(root: Path, modified_ns: int) -> tuple[Path, ...]` — Resolve explicitly configured import roots for a project revision.
- `module_names(*, path: Path, root: Path) -> list[str]` — Compute every plausible import name for a file.
- `annotation_name(*, node: expr | None) -> str | None` — Extract a usable class name from an annotation.
- `annotation_element(*, node: expr | None) -> str | None` — Extract the iterated element type from a container annotation.
- `value_type_name(*, node: expr | None) -> str | None` — Infer a class name for a literal or constructor value.
- `param_kind_of(*, parameter: Parameter) -> ParamKind` — Map an `inspect` parameter kind to the exactus vocabulary.
- `sig_from_inspect(*, name: str, resolved: Signature) -> Sig` — Convert an `inspect.Signature` into an exactus signature.
- `build_sig(*, node: FunctionDef | AsyncFunctionDef | Lambda, name: str, method: MethodKind) -> Sig` — Build a signature record from a definition node.
- `method_kind_of(*, node: FunctionDef | AsyncFunctionDef) -> MethodKind` — Classify a method's receiver binding from its decorators.
- `is_dataclass(*, node: ClassDef) -> tuple[bool, bool]` — Report whether a class is a dataclass and whether it is kw-only.
- `field_call_options(*, node: expr) -> tuple[bool, bool]` — Read `init` and `kw_only` options from a `field(...)` call.
- `dataclass_params(*, node: ClassDef, kw_only: bool) -> tuple[Param, ...]` — Synthesize constructor parameters for a dataclass.
- `dataclass_field(*, item: stmt, kw_rest: bool) -> tuple[Param | None, bool]` — Convert one class-body statement into a field parameter.
- `namedtuple_params(*, node: ClassDef) -> tuple[Param, ...]` — Synthesize constructor parameters for a `NamedTuple` class.
- `record_self_annotation(*, info: ClassInfo, attr: str, annotation: expr) -> bool` — Record an annotated `self.attr` type and container element.
- `collect_self_attrs(*, node: FunctionDef | AsyncFunctionDef, info: ClassInfo) -> None` — Record `self.attr = Type()` assignments as attribute types.
- `build_classinfo(*, node: ClassDef, module: str, path: Path, prefix: str) -> ClassInfo` — Build a class record from a definition node.
- `index_method(*, item: FunctionDef | AsyncFunctionDef, info: ClassInfo, qualified: str) -> None` — Index one method on a class record.
- `index_class_item(*, item: stmt, info: ClassInfo, module: str, path: Path, qualified: str) -> None` — Index one class-body statement onto the class record.
- `relative_module(*, module: ModuleInfo, level: int, body: str) -> str` — Resolve a relative import to an absolute dotted module path.
- `index_module(*, path: Path, root: Path) -> ModuleInfo | None` — Parse and index one module's top-level definitions.
- `index_module_item(*, item: stmt, module: ModuleInfo, path: Path) -> None` — Index one module-level statement.
- `index_import(*, node: Import, module: ModuleInfo) -> None` — Record an `import x` statement on the module record.
- `index_import_from(*, node: ImportFrom, module: ModuleInfo) -> None` — Record a `from x import y` statement on the module record.
- `index_assignment(*, node: Assign | AnnAssign, module: ModuleInfo) -> None` — Record a module-level typed assignment.
- `stub_sig(*, node: FunctionDef | AsyncFunctionDef, name: str, method: MethodKind) -> Sig` — Build a signature from a stub definition.
- `class TargetPython` — Interpreter facts the analyzed project is written for.
  - Fields: `executable: str`, `version_info: tuple[int | str, ...]`, `platform: str`
  - `release(self: Self) -> str` — Render the interpreter's ``major.minor.micro`` version.
- `current_python() -> TargetPython` — Describe the interpreter that is running the analyzer.
- `project_interpreter(*, root: Path) -> Path | None` — Locate the interpreter a project runs on.
- `target_python(*, root: Path, python: str | None=None) -> TargetPython` — Resolve the interpreter facts inference must run against.
- `live_stub_statements(*, body: list[stmt], target: TargetPython) -> list[stmt]` — Flatten stub ``if`` blocks to the statements live on the target.
- `build_stub_class(*, node: ClassDef, prefix: str, target: TargetPython) -> StubClass` — Build a stub class record from a `.pyi` class definition.
- `stub_roots() -> list[Path]` — Locate typeshed stub roots bundled with a type checker.
- `class StubClassLookupArgs` — Represent stub class lookup args.
  - Fields: `module: StubModule`, `info: StubClass`, `rest: list[str]`, `bound: bool`, `dotted: str`, `depth: int`
- `class StubIndex` — Lazily parsed typeshed signatures for external callables.
  - `__init__(self: Self, *, roots: list[Path], target: TargetPython) -> None` — Initialize the stub index.
  - `from_source(*, item: ImportFrom, dotted: str) -> str` — Resolve an `ImportFrom` node to its absolute source module.
  - `module(self: Self, *, dotted: str) -> StubModule | None` — Return the stub module for a dotted path, if any.
  - `parse_stub(self: Self, *, path: Path, dotted: str) -> StubModule | None` — Parse one stub file into a module record.
  - `module_prefix(self: Self, *, dotted: str) -> tuple[StubModule, list[str]] | None` — Return the longest stub-module prefix for a dotted path.
  - `lookup(self: Self, *, dotted: str, depth: int=0) -> Resolved` — Resolve a dotted path through the stub index.
  - `in_module(self: Self, *, module: StubModule, rest: list[str], dotted: str, depth: int) -> Resolved` — Resolve a name inside a stub module.
  - `in_module_class(self: Self, *, module: StubModule, info: StubClass, rest: list[str], dotted: str, depth: int) -> Resolved` — Resolve a class member path inside a stub module.
  - `in_stub_submodule(self: Self, *, module: StubModule, name: str, rest: list[str], dotted: str, depth: int) -> Resolved` — Resolve a path that descends into a stub submodule.
  - `in_class(self: Self, **kwargs: Unpack[StubClassLookupArgs]) -> Resolved` — Return in class.
  - `in_bases(self: Self, **kwargs: Unpack[StubClassLookupArgs]) -> Resolved` — Return in bases.
  - `base_method_sigs(self: Self, *, module: StubModule, info: StubClass, name: str, depth: int) -> list[Sig]` — Collect `name` signatures declared across the base classes.
- `class Project` — Repository-wide index used to resolve call sites.
  - `__init__(self: Self, *, root: Path, path_filter: Callable[[Path], bool] | None=None, capability: CapabilityIndex | None=None, source_paths: list[Path] | None=None, python: str | None=None) -> None` — Build the index for every Python file under `root`.
  - `external_via_prefix(*, parts: list[str], split: int) -> LiveObject` — Resolve a path through one importable module prefix.
  - `local_instance(*, local: Resolved) -> Resolved` — Convert a module-level resolution to an instance resolution.
  - `class_call(*, stored: Resolved, bound: bool) -> Resolved` — Resolve a class-body callable attribute for one access.
  - `register_class(self: Self, *, info: ClassInfo) -> None` — Register a class and its methods in the global indexes.
  - `class_named(self: Self, *, name: str) -> ClassInfo | None` — Resolve a class by qualified or short name.
  - `find_method(self: Self, *, info: ClassInfo, name: str, depth: int=0) -> Sig | None` — Find a method on a class, walking project base classes.
  - `external_object(self: Self, *, dotted: str) -> LiveObject` — Resolve a dotted path to a live external object.
  - `external_single(self: Self, *, name: str) -> LiveObject` — Resolve a bare name to a builtin or top-level module.
  - `external_dotted(self: Self, *, parts: list[str]) -> LiveObject` — Resolve a multi-segment path through importable prefixes.
  - `external_type(self: Self, *, name: str) -> tuple[type, str] | None` — Resolve an annotation type name to a live runtime class.
  - `external_sig(self: Self, *, dotted: str) -> Sig | None` — Return the runtime signature for an external callable.
  - `probe(self: Self, *, obj: LiveObject, params: tuple[Param, ...], index: int) -> bool | None` — Return a cached runtime keyword-acceptance probe verdict.
  - `verify_params(self: Self, *, obj: LiveObject, params: tuple[Param, ...]) -> tuple[tuple[Param, ...], bool]` — Demote stub parameters the runtime rejects as keywords.
  - `write_capability_index(self: Self, *, path: Path) -> None` — Commit the captured runtime capability snapshot to JSON.
  - `resolve_dotted(self: Self, *, dotted: str, depth: int=0) -> Resolved` — Resolve a dotted path through the project index or imports.
  - `resolve_in_module(self: Self, *, module: ModuleInfo, rest: list[str], depth: int=0) -> Resolved` — Resolve a name inside an indexed module.
  - `module_symbol(self: Self, *, module: ModuleInfo, name: str, rest: list[str], depth: int) -> Resolved | None` — Resolve `name` against a module's defined symbols.
  - `follow_alias(self: Self, *, target: str, rest: list[str], depth: int) -> Resolved` — Follow an import alias to a project or external target.
  - `module_call_expr(self: Self, *, module: ModuleInfo, name: str, rest: list[str], depth: int) -> Resolved` — Resolve a module-level `name = a.b` callable reference.
  - `module_instance(self: Self, *, module: ModuleInfo, name: str, rest: list[str]) -> Resolved` — Resolve a module-level variable holding a class instance.
  - `declared_instance(self: Self, *, module: ModuleInfo | None, name: str) -> Resolved` — Resolve an annotation type name in its declaring module's scope.
  - `instance_rest(self: Self, *, base: Resolved, rest: list[str]) -> Resolved` — Resolve remaining attribute segments on an instance.
  - `module_submodule(self: Self, *, module: ModuleInfo, name: str, rest: list[str], depth: int) -> Resolved | None` — Resolve `name` as a submodule of `module`.
  - `resolve_in_class(self: Self, *, info: ClassInfo, rest: list[str], bound: bool=False) -> Resolved` — Resolve an attribute path inside a class record.
  - `class_member(self: Self, *, info: ClassInfo, name: str, rest: list[str], bound: bool) -> Resolved | None` — Resolve `name` against a class's members.
  - `class_attr(self: Self, *, info: ClassInfo, name: str, rest: list[str]) -> Resolved` — Resolve a class attribute holding a typed instance.
  - `resolve_external(self: Self, *, dotted: str) -> Resolved` — Resolve a dotted path to a live external object.
- `class PositionalCheckArgs` — Represent positional check args.
  - Fields: `node: Call`, `index: int`, `argument: expr`, `compatible: list[tuple[Param, ...]]`, `keyword_names: set[str]`, `callee_text: str`, `confidence: str`, `positional_count: int`
- `class CallExactusor` — Walk one module's AST resolving every call site.
  - `__init__(self: Self, *, project: Project, module: ModuleInfo) -> None` — Initialize the exactusor for one module.
  - `unresolved_reason(*, node: Call) -> str` — Classify why a call's callee has no known signature.
  - `is_exempt(*, callee_text: str, node: Call) -> bool` — Return whether an unresolved call cannot take keyword arguments.
  - `branch_scope(*, scope: Scope) -> Scope` — Clone flow-sensitive bindings for one control-flow branch.
  - `merge_branch_maps(*, target: dict[str, T], left: dict[str, T], right: dict[str, T]) -> None` — Keep only bindings proven identical after both branches.
  - `record_import(*, node: Import, scope: Scope) -> None` — Record a function-local `import x` statement.
  - `seed_parameters(*, args: arguments, scope: Scope) -> None` — Bind parameter annotations in a fresh child scope.
  - `iter_element(*, node: expr, scope: Scope) -> str | None` — Return the recorded element type of an iterable expression.
  - `record_self_attr(*, target: Attribute, name: str, scope: Scope, element: str | None=None) -> None` — Record `self.attr` types on the enclosing class record.
  - `bind_callable_name(*, name: str, resolved: Resolved, scope: Scope) -> None` — Bind or clear a callable resolution for a plain name.
  - `bind_callable_attr(*, target: expr, resolved: Resolved, scope: Scope) -> None` — Bind or clear a callable resolution for `self.attr`.
  - `name_def(*, name: str, scope: Scope) -> Resolved | None` — Resolve `name` as a locally defined callable.
  - `name_class(*, name: str, scope: Scope) -> Resolved | None` — Resolve `name` as a locally defined class.
  - `name_var_call(*, name: str, scope: Scope) -> Resolved | None` — Resolve `name` as a variable bound to a callable reference.
  - `ready_params(sig: Sig, *, bound: bool) -> tuple[Param, ...]` — Return call-ready parameters with the receiver dropped.
  - `posonly_names(*, resolved: Resolved, obj: LiveObject) -> frozenset[str]` — Return runtime-verified positional-only parameter names.
  - `record_unresolved(self: Self, *, callee_text: str, node: Call) -> None` — Count an unresolved call, apart when it is not actionable.
  - `exactus(self: Self) -> None` — Parse and walk the module, collecting findings.
  - `walk_body(self: Self, *, stmts: list[stmt], scope: Scope) -> None` — Walk a statement list in order.
  - `seed_scope(self: Self, *, stmts: list[stmt], scope: Scope) -> None` — Pre-register only lexically available sibling definitions.
  - `walk_if(self: Self, *, node: If, scope: Scope) -> None` — Walk an ``if`` using independent flow-sensitive branch states.
  - `walk_node(self: Self, *, node: AST, scope: Scope) -> None` — Dispatch one node, tracking scope transitions.
  - `record_binding(self: Self, *, node: AST, scope: Scope) -> None` — Record names a statement binds before its children are walked.
  - `record_import_from(self: Self, *, node: ImportFrom, scope: Scope) -> None` — Record a function-local `from x import y` statement.
  - `enter_function(self: Self, *, node: FunctionDef | AsyncFunctionDef, scope: Scope) -> None` — Walk a function body inside a fresh child scope.
  - `enter_class(self: Self, *, node: ClassDef, scope: Scope) -> None` — Walk a class body with the class record as context.
  - `enter_lambda(self: Self, *, node: Lambda, scope: Scope) -> None` — Walk a lambda body inside a fresh child scope.
  - `resolved_assignment(self: Self, *, target: expr, resolved: Resolved, scope: Scope) -> bool` — Record an assignment from an inferred resolved value.
  - `record_assignment(self: Self, *, node: Assign | AnnAssign, scope: Scope) -> None` — Record the value type visible after an assignment executes.
  - `record_with(self: Self, *, node: With | AsyncWith, scope: Scope) -> None` — Type ``with open(...) as name`` targets as file objects.
  - `record_for(self: Self, *, node: For | AsyncFor, scope: Scope) -> None` — Type a `for` target from the iterated container's element.
  - `record_target(self: Self, *, target: expr, name: str, scope: Scope, element: str | None=None) -> None` — Bind a class name to a name or `self.attr` target.
  - `record_callable(self: Self, *, target: expr, value: Name | Attribute, scope: Scope) -> None` — Record a name or attribute bound to a callable reference.
  - `resolve_name(self: Self, *, name: str, scope: Scope) -> Resolved` — Resolve a bare name through scope, module, imports, builtins.
  - `name_var(self: Self, *, name: str, scope: Scope) -> Resolved | None` — Resolve `name` as a variable holding a class instance.
  - `name_scope_alias(self: Self, *, name: str, scope: Scope) -> Resolved | None` — Resolve `name` as a function-local `from x import y`.
  - `name_scope_module(self: Self, *, name: str, scope: Scope) -> Resolved | None` — Resolve `name` as a function-local `import x`.
  - `infer_literal(self: Self, *, node: expr) -> Resolved` — Infer a literal container or scalar expression.
  - `infer_expr(self: Self, *, node: expr, scope: Scope) -> Resolved` — Infer what an expression denotes for attribute resolution.
  - `infer_binop(self: Self, *, node: BinOp, scope: Scope) -> Resolved` — Infer a binary expression from its concrete left-hand object.
  - `infer_subscript(self: Self, *, node: Subscript, scope: Scope) -> Resolved` — Infer common sequence-subscript result types.
  - `fallback_external_member(self: Self, *, name: str) -> Resolved` — Resolve a last-resort standard-library method by method name.
  - `infer_name(self: Self, *, node: Name, scope: Scope) -> Resolved` — Infer what a bare name denotes, including `self` and `cls`.
  - `infer_special_attribute_call(self: Self, *, node: Call, scope: Scope) -> Resolved` — Infer known result-preserving attribute calls.
  - `infer_cast_call(self: Self, *, node: Call, scope: Scope) -> Resolved` — Infer a ``typing.cast`` result.
  - `infer_call(self: Self, *, node: Call, scope: Scope) -> Resolved` — Infer the result type of a call expression.
  - `known_external_result(self: Self, *, callee: Resolved) -> Resolved` — Infer selected standard-library return types by dotted identity.
  - `infer_super(self: Self, *, scope: Scope) -> Resolved` — Infer a `super()` proxy as the next project or external base.
  - `call_result(self: Self, *, callee: Resolved) -> Resolved` — Infer the result type produced by calling `callee`.
  - `attribute_of(self: Self, *, owner: Resolved, name: str) -> Resolved` — Resolve `owner.name` as an attribute access.
  - `attr_module(self: Self, *, owner: Resolved, name: str) -> Resolved | None` — Resolve an attribute on a project module.
  - `attr_class(self: Self, *, owner: Resolved, name: str) -> Resolved | None` — Resolve an attribute on a project class object.
  - `attr_instance(self: Self, *, owner: Resolved, name: str) -> Resolved | None` — Resolve an attribute on a project class instance.
  - `attr_external(self: Self, *, owner: Resolved, name: str) -> Resolved | None` — Resolve an attribute on a live external object.
  - `attr_stub(self: Self, *, owner: Resolved, name: str) -> Resolved | None` — Resolve an attribute on a stub module or class.
  - `external_base_attr(self: Self, *, bases: list[str], name: str) -> Resolved` — Resolve a method on an external base class.
  - `base_member(self: Self, *, dotted: str, name: str) -> Resolved | None` — Resolve `name` on one external base class.
  - `stub_member(self: Self, *, dotted: str, bound: bool) -> Resolved | None` — Resolve a member through the typeshed stub index.
  - `stub_member_via_type(self: Self, *, member: LiveObject, bound: bool) -> Resolved | None` — Resolve a bound method through its owner type's stub.
  - `expand_base(self: Self, *, name: str) -> str` — Expand a base-class name through the module's import table.
  - `external_attr(self: Self, *, owner: Resolved, name: str) -> Resolved` — Resolve an attribute on a live external object.
  - `external_member(self: Self, *, owner: Resolved, name: str, member: LiveObject) -> Resolved | None` — Resolve an attribute member on a live external object.
  - `external_member_callable(self: Self, *, owner: Resolved, member: LiveObject, dotted: str) -> Resolved | None` — Resolve a callable member on a live external object.
  - `check_call(self: Self, *, node: Call, scope: Scope) -> None` — Exactus one call site for positional keyword-capable args.
  - `receiver_is_external(self: Self, *, node: Attribute, scope: Scope) -> bool` — Return whether a method receiver has a known non-project type.
  - `inherited_external_attr(self: Self, *, node: expr, scope: Scope) -> bool` — Return whether ``self.attr`` comes from a non-project base class.
  - `annotated_receiver_type(self: Self, *, node: expr, scope: Scope) -> str | None` — Return the declared type name of a receiver expression.
  - `param_sets_of(self: Self, *, resolved: Resolved) -> tuple[list[tuple[Param, ...]], str]` — Convert a resolved callee into call-ready parameter sets.
  - `verify_sets(self: Self, *, resolved: Resolved, sets: list[tuple[Param, ...]], member: str | None) -> tuple[list[tuple[Param, ...]], str]` — Verify stub parameter kinds against the live runtime object.
  - `sets_function(self: Self, *, resolved: Resolved) -> tuple[list[tuple[Param, ...]], str] | None` — Parameter sets for a resolved function or method.
  - `sets_class(self: Self, *, resolved: Resolved) -> tuple[list[tuple[Param, ...]], str] | None` — Parameter sets for a project class constructor.
  - `sets_instance(self: Self, *, resolved: Resolved) -> tuple[list[tuple[Param, ...]], str] | None` — Parameter sets for calling a project class instance.
  - `sets_stubclass(self: Self, *, resolved: Resolved) -> tuple[list[tuple[Param, ...]], str] | None` — Parameter sets for a stub class constructor.
  - `sets_stubinstance(self: Self, *, resolved: Resolved) -> tuple[list[tuple[Param, ...]], str] | None` — Parameter sets for calling a stub class instance.
  - `sets_external(self: Self, *, resolved: Resolved) -> tuple[list[tuple[Param, ...]], str] | None` — Parameter sets for a live external callable.
  - `external_via_type(self: Self, *, resolved: Resolved) -> Resolved` — Resolve a bound method through its owner type's stub.
  - `constructor_sig(self: Self, *, info: ClassInfo) -> Sig` — Return the effective constructor signature for a class.
  - `external_callable_params(self: Self, *, resolved: Resolved) -> tuple[Param, ...] | None` — Return runtime signature parameters for an external callable.
  - `fallback_method(self: Self, *, name: str, node: Call) -> tuple[list[tuple[Param, ...]], str] | None` — Resolve a method by unique global name as a last resort.
  - `would_flag(self: Self, *, sig: Sig, node: Call) -> bool` — Report whether a candidate signature flags this call.
  - `apply_params(self: Self, *, node: Call, param_sets: list[tuple[Param, ...]], callee_text: str, confidence: str) -> None` — Bind call arguments to parameter sets and report findings.
  - `check_positional_arg(self: Self, **kwargs: Unpack[PositionalCheckArgs]) -> None` — Check positional arg.
- `probe_module(*, obj: LiveObject) -> str` — Return the module that owns a live probe target.
- `probeable(*, obj: LiveObject) -> bool` — Decide whether a sentinel probe call on `obj` is side-effect safe.
- `kwarg_verdict(*, message: str, param: str) -> bool | None` — Classify a probe `TypeError` as keyword rejection or acceptance.
- `probe_value(*, name: str) -> LiveObject` — Return a safe runtime value for a parameter name.
- `receiver_for(*, owner: type) -> LiveObject` — Build a fresh instance of `owner` for method probing.
- `bind_probe(*, obj: LiveObject) -> tuple[LiveObject, bool]` — Return a probe target and whether it carries a bound receiver.
- `probe_call(*, obj: LiveObject, params: tuple[Param, ...], index: int) -> bool | None` — Probe whether `params[index]` accepts a keyword on `obj`.
- `class TypeTrial` — Observed runtime result for one candidate argument type.
  - `exception_type` = `None`
  - `exception_message` = `None`
  - Fields: `type_name: str`, `observation: str`
- `class TypeParameter` — Empirical type information for one callable parameter.
  - Fields: `name: str`, `kind: ParamKind`, `advertised_kinds: tuple[ParamKind, ...]`, `has_default: bool`, `keyword_valid: bool | None`, `trials: tuple[TypeTrial, ...]`
- `class TypeCallable` — Empirical runtime type index entry for one builtin callable.
  - Fields: `method: str`, `signature_source: str`, `signature_variants: tuple[tuple[Param, ...], ...]`, `parameters: tuple[TypeParameter, ...]`
- `class BuiltinTypeFuzzer` — Build an empirical argument-type index for builtin callables.
  - `__init__(self: Self, *, project: Project) -> None` — Initialize the fuzzer.
  - `targets() -> tuple[tuple[str, LiveObject], ...]` — Return directly exposed builtin callables and builtin type methods.
  - `drop_receiver(*, params: tuple[Param, ...], bound: bool) -> tuple[Param, ...]` — Drop an already-bound self/cls parameter.
  - `record_json(record: TypeCallable) -> dict[str, LiveObject]` — Convert one callable record to JSON-compatible dictionaries.
  - `run(self: Self) -> dict[str, LiveObject]` — Fuzz every directly exposed builtin callable and type method.
  - `fuzz_callable(self: Self, *, method: str, obj: LiveObject) -> TypeCallable | None` — Fuzz one builtin callable.
  - `signature_sets(self: Self, *, method: str, obj: LiveObject) -> tuple[tuple[tuple[Param, ...], ...], str]` — Resolve runtime or typeshed parameter sets for one builtin.
  - `stub_signature_sets(self: Self, *, method: str) -> tuple[tuple[Param, ...], ...]` — Return call-ready parameter variants from typeshed.
  - `normalize_bound(self: Self, *, obj: LiveObject, params: tuple[Param, ...]) -> tuple[Param, ...]` — Normalize inspect parameters for a descriptor bound by probing.
  - `merge_parameters(self: Self, *, obj: LiveObject, advertised_sets: tuple[tuple[Param, ...], ...], param_sets: tuple[tuple[Param, ...], ...]) -> tuple[TypeParameter, ...]` — Merge per-overload fuzz results by parameter name.
  - `merge_parameter(self: Self, name: str, *, obj: LiveObject, advertised_sets: tuple[tuple[Param, ...], ...], param_sets: tuple[tuple[Param, ...], ...]) -> TypeParameter` — Fuzz and merge one named parameter across overload variants.
- `fuzz_trial(*, obj: LiveObject, params: tuple[Param, ...], index: int, value: LiveObject, type_name: str) -> TypeTrial` — Execute one isolated-by-fresh-state candidate-type trial.
- `merge_trials(*, type_name: str, trials: list[TypeTrial]) -> TypeTrial` — Merge overload observations for one candidate type.
- `parameter_to_json(*, parameter: TypeParameter) -> dict[str, LiveObject]` — Convert empirical parameter information to JSON-compatible data.
- `arity_fits(*, params: tuple[Param, ...], arity: int) -> bool` — Check whether a call arity can bind to a parameter tuple.
- `parse_args(*, arguments: tuple[str, ...] | None=None) -> Namespace` — Parse args.
- `collect_findings(*, exactusors: list[CallExactusor]) -> tuple[list[Finding], list[AmbiguousCall]]` — Flatten per-module findings and ambiguous calls.
- `class SourceEdit` — One validated source-text replacement used by auto-healing.
  - Fields: `start: int`, `end: int`, `replacement: str`, `kind: str`, `line: int`, `column: int`, `original: str`, `reported_replacement: str`
- `class AnalysisRun` — Stable kwargs/type-hints analysis snapshot.
  - Fields: `project: Project`, `exactusors: list[CallExactusor]`, `bare_imports: list[BareImportFinding]`, `type_hints: list[TypeHintFinding]`, `checked: tuple[int, int]`, `auto_fixes: list[JsonValue]`
- `class AnalysisRequest` — Inputs steering one kwargs/type-hints analysis run.
  - Fields: `root: Path`, `path_filter: Callable[[Path], bool] | None`, `source_paths: Sequence[Path] | None`, `capability: CapabilityIndex | None`, `allowed: frozenset[str]`, `strict: bool`, `dry_run: bool`, `python: str | None`
- `class AnalysisDestinations` — Report and artifact destinations for a completed analysis.
  - Fields: `output: Path`, `root: Path`, `context: int`, `heuristics_output: Path`, `write_index: Path | None`
- `main(*, arguments: tuple[str, ...] | None=None, path_filter: Callable[[Path], bool] | None=None, includes: tuple[str, ...]=(), excludes: tuple[str, ...]=(), source_paths: Sequence[Path] | None=None) -> int` — Run the exactus and write the report bundle and heuristics.

### `main.py`

Exactus keyword usage, imports, and explicit type hints.

- `class Constants` — Group module-level constants.
  - `heuristics` = `'heuristics.json'`
- `class PathScope` — Include/exclude glob filter applied to discovered source files.
  - Fields: `root: Path`, `includes: tuple[str, ...]`, `excludes: tuple[str, ...]`
- `create_parser() -> ArgumentParser` — Return the shared CLI grammar used by execution and completion.
- `parse_args(*, arguments: tuple[str, ...] | None=None) -> Namespace` — Parse args.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Return main.

### `report.py`

Normalize the KWARGS_TYPEHINTS report: findings, metrics and tables.

- `class ReportTables` — Constants of the normalized KWARGS_TYPEHINTS report.
  - `id_prefix` = `'KWARGS'`
  - `categories` = `('missing-kwargs', 'bare-import', 'missing-hint', 'parse-failure', 'ambig...`
  - `labels` = `{'missing-kwargs': 'Missing keyword arguments', 'bare-import': 'Bare impo...`
  - `severities` = `{'missing-kwargs': 'error', 'bare-import': 'error', 'missing-hint': 'erro...`
  - `blocking` = `frozenset({'missing-kwargs', 'bare-import', 'missing-hint', 'parse-failur...`
  - `levels` = `('error', 'warning', 'info')`
  - `reasons` = `{'unknown-name': ('name not defined', 'The name has no known definition')...`
  - `methodology` = `('Signatures come from a repository-wide AST index (functions, methods, d...`
- `normalized_findings(*, report: Mapping[str, JsonValue]) -> list[JsonValue]` — Return every finding of the run in the normalized shape.
- `report_data(*, report: Mapping[str, JsonValue]) -> dict[str, JsonValue]` — Return the KWARGS_TYPEHINTS payload with the normalized blocks.

## Dependencies and consumers

- Other packages: [`argument_parser`](../../packages/argument_parser/DOCS.md), [`project_python`](../../packages/project_python/DOCS.md), [`steps`](../../packages/steps/DOCS.md), [`common`](../common/DOCS.md), [`reports`](../reports/DOCS.md)
- Used by: `__main__.py`, `tests/tools/kwargs_typehints/test_kwargs_report.py`, `tests/tools/kwargs_typehints/test_kwargs_typehints.py`

## Tests

Tests live in `exactus/tests/tools/kwargs_typehints/`.

- `test_kwargs_report.py` — KWARGS_TYPEHINTS renders result.md and its web view from normalized data. (8 tests)
  - `test_clean_run_states_why_tables_are_empty`
  - `test_crash_render_shows_na_blocks`
  - `test_execute_exactus_writes_the_normalized_bundle`
  - `test_extension_rows_link_to_their_findings`
  - `test_findings_cover_every_category`
  - `test_golden_result_renders_expected_markdown`
  - `test_normalization_of_rare_categories`
  - `test_summary_scope_and_metrics`
- `test_kwargs_typehints.py` — The kwargs-typehints analyzer on projects, flags and its artifacts. (24 tests)
  - `test_bare_import_heal_keeps_module_value_uses`
  - `test_bare_imports_require_only_attribute_access`
  - `test_external_module_and_bound_classmethod_resolution`
  - `test_import_roots_and_annotated_factories`
  - `test_kwargs_auto_heals_safe_findings_and_converges`
  - `test_kwargs_default_root_is_repository_root`
  - `test_kwargs_dry_run_preserves_sources`
  - `test_kwargs_exempts_positional_only_and_dynamic_callees`
  - `test_kwargs_pyproject_dry_reports_without_writing`
  - `test_kwargs_strict_flag`
  - `test_kwargs_writes_heuristics_under_artifacts`
  - `test_pointer_keywords_follow_the_project_python`
  - `test_pointer_keywords_hold_on_a_real_python_313`
  - `test_python_option_is_part_of_the_cli_grammar`
  - `test_python_option_reaches_the_engine`
  - `test_requires_python_reads_the_declared_specifier`
  - `test_spec_clauses_and_version_ok_cover_common_operators`
  - `test_stub_guards_are_decided_by_the_target_interpreter`
  - `test_target_python_accepts_an_environment_directory`
  - `test_target_python_falls_back_to_the_running_interpreter`
  - `test_target_python_reads_the_project_interpreter`
  - `test_target_python_trusts_the_project_environment`
  - `test_target_python_uses_the_configured_interpreter`
  - `test_typevar_assignments_need_no_annotation`

<!-- exactus:reference:end -->
