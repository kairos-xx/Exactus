# `exactus/tools/kwargs_typehints/`

The `kwargs-typehints` exactus tool: a standalone entry point (`main.py`), its analysis
core (`core.py`), the normalized report data (`report.py`) and the report template
(`templates/`). A run writes `result.json`, `result.md` (rendered from
`templates/markdown/`), `result_web/` and `ARTIFACTS/heuristics.json` (argument types
observed by fuzzing builtin callables) next to the common `ARTIFACTS/stderr.log`
and `@activity.json`. The inventory below documents every direct file and
child directory.

Assignments declaring `TypeVar` from `typing` or `typing_extensions` do
not need a variable annotation. Direct imports, aliases and qualified
module calls are recognized in both normal and strict modes. Ordinary
variables still need annotations.

## Directory contents

### Files

#### `__init__.py`

Kwargs and type-hint exactus tool.

#### `core.py`

Exactus keyword-call policy, imports, and explicit typing. Public API: `FuzzValue` — One reusable runtime type-fuzzing value factory.; `BareImportExactusor` — Detect bare imports and derive collision-safe explicit-import fixes.; `TypeHintExactusor` — Detect missing variable, parameter, and return annotations by scope.; `python_files()` — Collect every non-hidden, non-excluded Python file under `root`.; `module_names()` — Compute every plausible import name for a file.; `annotation_name()` — Extract a usable class name from an annotation.; `value_type_name()` — Infer a class name for a literal or constructor value.; `param_kind_of()` — Map an `inspect` parameter kind to the exactus vocabulary.; `sig_from_inspect()` — Convert an `inspect.Signature` into an exactus signature.; `build_sig()` — Build a signature record from a definition node.; `method_kind_of()` — Classify a method's receiver binding from its decorators.; `is_dataclass()` — Report whether a class is a dataclass and whether it is kw-only.; `field_call_options()` — Read `init` and `kw_only` options from a `field(...)` call.; `dataclass_params()` — Synthesize constructor parameters for a dataclass.; `dataclass_field()` — Convert one class-body statement into a field parameter.; `namedtuple_params()` — Synthesize constructor parameters for a `NamedTuple` class.; `collect_self_attrs()` — Record `self.attr = Type()` assignments as attribute types.; `build_classinfo()` — Build a class record from a definition node.; `index_method()` — Index one method on a class record.; `index_class_item()` — Index one class-body statement onto the class record.; `relative_module()` — Resolve a relative import to an absolute dotted module path.; `index_module()` — Parse and index one module's top-level definitions.; `index_module_item()` — Index one module-level statement.; `index_import()` — Record an `import x` statement on the module record.; `index_import_from()` — Record a `from x import y` statement on the module record.; `index_assignment()` — Record a module-level typed assignment.; `stub_sig()` — Build a signature from a stub definition.; `build_stub_class()` — Build a stub class record from a `.pyi` class definition.; `stub_roots()` — Locate typeshed stub roots bundled with a type checker.; `StubIndex` — Lazily parsed typeshed signatures for external callables.; `Project` — Repository-wide index used to resolve call sites.; `UnresolvedCall` — Call site whose callee could not be resolved to a signature.; `CallExactusor` — Walk one module's AST resolving every call site.; `probe_module()` — Return the module that owns a live probe target.; `probeable()` — Decide whether a sentinel probe call on `obj` is side-effect safe.; `kwarg_verdict()` — Classify a probe `TypeError` as keyword rejection or acceptance.; `probe_value()` — Return a safe runtime value for a parameter name.; `receiver_for()` — Build a fresh instance of `owner` for method probing.; `bind_probe()` — Return a probe target and whether it carries a bound receiver.; `probe_call()` — Probe whether `params[index]` accepts a keyword on `obj`.; `BuiltinTypeFuzzer` — Build an empirical argument-type index for builtin callables.; `fuzz_trial()` — Execute one isolated-by-fresh-state candidate-type trial.; `merge_trials()` — Merge overload observations for one candidate type.; `parameter_to_json()` — Convert empirical parameter information to JSON-compatible data.; `arity_fits()` — Check whether a call arity can bind to a parameter tuple.; `parse_args()` — Parse args.; `collect_findings()` — Flatten per-module findings and ambiguous calls.; `main()` — Run the exactus and write the report bundle and heuristics.

#### `main.py`

Exactus keyword usage, imports, and explicit type hints. Public API: `PathScope` — Include/exclude glob filter applied to discovered source files.; `create_parser()` — Create parser.; `parse_args()` — Parse args.; `main()` — Return main.

#### `report.py`

Normalize the KWARGS_TYPEHINTS report: findings, metrics and tables. Public API: `ReportTables` — Constants of the normalized KWARGS_TYPEHINTS report.; `normalized_findings()` — Return every finding of the run in the normalized shape.; `report_data()` — Return the KWARGS_TYPEHINTS payload with the normalized blocks.

### Directories

#### `templates/`

The report template (`markdown/template.md` and `markdown/mapping.json`).

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Kwargs and type-hint exactus tool.
- [`arguments.py`](arguments.py) — Declare the kwargs_typehints CLI grammar.
- [`core.py`](core.py) — Exactus keyword-call policy, imports, and explicit typing.
- [`main.py`](main.py) — Exactus keyword usage, imports, and explicit type hints.
- [`report.py`](report.py) — Normalize the KWARGS_TYPEHINTS report: findings, metrics and tables.

### Subdirectories

- [`templates/`](templates/README.md) — Report templates of the kwargs-typehints tool. The inventory below documents every direct file and child directory.

<!-- exactus:inventory:end -->



Safe keyword-call and bare-import findings auto-heal by default. Use `--dry` or `--dry-run` to validate and report repairs without modifying source files. The shared Exactus configuration also accepts `dry = true` globally or in `[tool.exactus.kwargs_typehints]`.
