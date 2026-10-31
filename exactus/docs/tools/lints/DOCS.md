# tools/lints/

The `lints` tool: clean, lint and type-check sources with rollback.

## Files

| File | Description |
|---|---|
| `arguments.py` | The lints grammar, declared without importing the execution engine. |
| `compliance.py` | Suppression markers, escape-hatch annotations and lint-config handling. |
| `core.py` | The lint engine: orchestrates group-final → all-lints → guarded inference and reporting. |
| `css_tokens.py` | Audit the CSS custom-property token graph as `custom_css`: the five-layer `PRIMARY`/`DYNAMIC`/`BASE`/`CATALOG`/terminal architecture and its consumption rules. |
| `js_delimiters.py` | Simplify removable JavaScript delimiters as `custom_javascript_delimiters` in fix mode; see [JavaScript delimiter simplifier](#javascript-delimiter-simplifier). |
| `js_function_blocks.py` | Modernize JavaScript callables to arrow/static notation as `custom_javascript_notation` in fix mode; see [JavaScript function blocks](#javascript-function-blocks). |
| `exactus/packages/organize/js/class_organizer.js` | Node/Espree script driving `js_function_blocks.py` (actions `analyze`/`convert`) and `exactus.packages.organize` (`organize`). |
| `long_lines.py` | Repair lines left over-long by Ruff inside the stabilization loop; see [Long-line repair](#long-line-repair). |
| `long_lines_engine.py` | Engine behind `long_lines.py`: `LongLinesAPI` (in-memory and batch facade) and `LongLineRepair` (the `FileRepair` hook plugged into the Ruff stabilization loop). |
| `main.py` | Entry: run the combined lint audit and emit the LINTS report bundle. |
| `report.py` | Normalize the LINTS report: summary, scope, findings and metrics. |
| `packages_pipeline.py` | Adapt `exactus/packages/group_final`, `exactus/packages/organize`, and `exactus/packages/all_lints` results to the Exactus report contract. |
| `shebang.py` | Shebang/executable-bit policy as `custom_shebang`, mirroring Ruff `EXE001`/`EXE002`; heals mismatches per `ShebangSettings`. |
| `string_transform.py` | Source-preserving string rewriting applied inside the Python-conventions pass: `dedent(...)` conversion, width-limited literal splitting and f-string call expansion over the caller's parsed AST. |
| `templates/` | Tool-specific Markdown template/mapping. |

## Behavior

- Runs `exactus/packages/group_final` first, unless `--no-group-final` (or
  `no-group-final = true`) is configured.
- Runs source-preserving `exactus/packages/organize` on the resolved Python lint scope
  before formatter/linter stages, unless `--no-organize` (or
  `no-organize = true`) is configured. Dry runs report planned changes without
  writing files. The shared steps trace records each organizer file as `changed`/`would change`, `unchanged`, or `skipped: unparseable`, plus stage totals.
- Delegates external discovery, execution and diagnostic normalization to
  `exactus/packages/all_lints`; independent analyzers share its worker pool.
  `--workers N` (or `workers = N`) bounds simultaneous external lint
  processes, and `1` provides deterministic serial execution.
- The Python API exposes the same controls as `LintExactusConfig.group_final` and `LintExactusConfig.organize`,
  `LintExactusConfig.simple` and `LintExactusConfig.unsafe_fixes`.
- `compliance.py` understands suppression markers and escape-hatch
  annotations so legitimate suppressions aren't reported as violations.
- Repairs lines Ruff cannot wrap through the stabilization hook of
  `exactus/packages/all_lints`; `--no-long-lines` (or `no-long-lines = true`) disables
  only that repair and `LintExactusConfig.long_lines` is the Python form.
  Details: [Long-line repair](#long-line-repair).
- Scans JavaScript for removable delimiters and rewrites them under
  `--fix`; `--no-delimiters` (or `no-delimiters = true`) disables the
  scan and `LintExactusConfig.delimiters` is the Python form.
  Details: [JavaScript delimiter simplifier](#javascript-delimiter-simplifier).
- Scans JavaScript for function blocks that can move to compact arrow or
  static notation and rewrites them under `--fix`; `--no-notation` (or
  `no-notation = true`) disables the scan and
  `LintExactusConfig.notation` is the Python form.
  Details: [JavaScript function blocks](#javascript-function-blocks).
- The Python-conventions pass applies `string_transform` rewrites over the
  tree already parsed by `core`: `dedent(...)` calls holding plain string
  literals are folded into dedented literals, over-width literals split
  within the effective Ruff line length, and f-string calls expand where
  safe — each rewrite is AST-validated so behavior is preserved. Findings
  surface as `custom_python`.
- Audits stylesheet custom properties against the five-layer token graph
  (`PRIMARY`/`DYNAMIC`/`BASE`/`CATALOG`/terminal): literal-only layers,
  derivation order and terminal-layer consumption are enforced and reported
  as `custom_css`.
- Checks shebang/executable-bit agreement as `custom_shebang`, mirroring
  Ruff `EXE001`/`EXE002`; `shebang.heal` repairs mismatches —
  `exec_no_shebang` chooses `add-shebang`/`drop-exec` for executable files
  without a shebang, `shebang_no_exec` chooses `add-exec`/`drop-shebang`
  for shebang files without the executable bit (`--no-shebang-heal`,
  `--exec-no-shebang`).
- Rollback: if the clean/lint phase mutates files and later fails, the
  tree is restored to its pre-run state.
- Findings carry file/line/rule into the normalized envelope; the report keeps
  the raw `all_lints` summary plus `group_final` and `organize` metrics alongside the existing
  per-linter insights.
- `--simple` (or `simple = true`) runs only the `all_lints` audit:
  group-final, organize, source cleaning, conventions, long-line repair,
  compliance and inference are skipped, and the standard `LINTS` bundle
  carries only `all_lints` findings. It composes with `--no-fix`/`--dry`
  and works both standalone and inside pipelines with its own progress
  spans.
- Audit-only runs (`--no-fix`, `--dry`) disable every mutation phase:
  `all_lints` is invoked with `stabilize=False` (no Ruff format/fix
  cycles, no long-line repair) and the inference stage degrades to an
  audit-only `pyrefly` check published as `pyrefly`, never `infer`.
- The shared `EXACTUS_RESULTS/.runtime` registry is bounded:
  `--runtime-max-runs N` (or `runtime_max_runs = N`) keeps only the
  newest N finished runs, and `--runtime-max-size SIZE` (or
  `runtime_max_size`) caps the database file size — `SIZE` is a plain
  byte count (`33554432`) or a unit size (`"64MB"`), and `0` disables
  the cap. The oldest finished runs are pruned after each run; live
  runs are never deleted.

## Long-line repair
`exactus/tools/lints/long_lines.py` repairs physical Python lines that stay
over the configured width after Ruff has formatted a file. It is part of the
`lints` autofix: the stabilization loop calls it for every file, and the
module also exposes a stable Python API.

A repair never changes behavior. Every candidate is checked against the
Python AST, scored against Ruff's own E501 diagnostics and accepted only when
it strictly improves the file. Anything that cannot be repaired safely is
reported, never silently dropped.

### How `lints` runs it

```
ruff format → ruff check --fix → long-line repair → (changed? repeat)
```

1. `exactus/packages/all_lints` stabilizes every Python file with Ruff.
2. After each format/fix cycle the stabilizer calls the `FileRepair` hook
   installed by `lints` (`LongLineRepair`).
3. The hook asks Ruff for the file's E501 rows, resolves the file's line
   length from its own Ruff configuration, and repairs the file in place.
4. A file the hook changed gets another complete Ruff cycle, so the output is
   always Ruff-formatted and Ruff-fixed.
5. The linters then run on the final files, so the LINTS report reflects the
   repaired tree, not the pre-repair one.

| Control | Effect |
|---|---|
| `--no-long-lines` / `no-long-lines = true` | Skip only the long-line repair. |
| `--no-fix` / `--dry` | Skip the whole stabilization loop, so no repair runs. |
| `LintExactusConfig.long_lines` | Python API form of `--no-long-lines`. |

The repair is skipped when Ruff cannot be resolved. A run that repaired files
prints `Repaired long lines in N file(s).`; unreadable files are counted and
left to the Ruff syntax diagnostics.

When `long_lines` is enabled the LINTS report carries a
`custom_python_long_lines` tool entry: its `findings` mirror the residual
Ruff `E501` diagnostics (the exact rows the repair could not clear), `healed`
lists every file the stabilization loop repaired, and `skipped_files` lists
sources that could not be read or decoded.

### What it repairs

Repairs are tried in a fixed order and the first strictly improving one wins:

| Order | Repair | Example |
|---|---|---|
| 1 | Expand top-level semicolon statements | `a = 1; b = 2` |
| 2 | Hoist a trailing comment above its statement | `x = f()  # why` |
| 3 | Wrap a standalone comment | long `# …` line |
| 4 | Reflow a docstring (Google, NumPy, Sphinx) | summary kept whole |
| 5 | Split a multiline string or bytes literal | `"""…"""` |
| 6 | Split a plain string literal | `"…long…"` |
| 7 | Parenthesize `from` imports, `with`, conditions, `for`, `case` guards | |
| 8 | Parenthesize assignments, `return`/`yield`/`assert`/`raise` | |
| 9 | Parenthesize annotations and decorators | |
| 10 | Split static text of an f-string | `f"text {x} text"` |
| 11 | Parenthesize the widest long AST expression | |
| 12 | Break a dotted call chain | `a.b().c().d()` |
| 13 | Explicit `\` continuation (last resort) | |

Directive comments (`# type:`, `# noqa`, `# pyright:`, `# fmt:`, `# pragma:`,
…) are never moved or wrapped, because their meaning depends on the line they
sit on.

### What it leaves alone

The repair mirrors Ruff's E501 exemptions, so it never reports a line Ruff
does not:

- a line that is a single unbroken word;
- a line ending in a URL that starts inside the width;
- a line whose trailing pragma comment starts inside the width;
- SPDX identifiers.

Regions delimited by `# fmt: off` / `# fmt: on` are protected by default and
reported through `protected_lines`. A long line dominated by one indivisible
name or string is reported as `unfixable_lines`.

### Python API

```python
from pathlib import Path

from exactus.tools.lints.long_lines import (
    LongLineRepair,
    LongLinesAPI,
    Settings,
)
```

#### `Settings`

Frozen configuration shared by every operation.

| Field | Default | Meaning |
|---|---|---|
| `line_length` | `79` | Maximum physical width, tabs expanded to four. |
| `run_ruff` | `True` | Format candidates and score E501 through Ruff. |
| `check_only` | `False` | Compute results without writing files. |
| `verbose` | `False` | Reserved for presentation layers. |
| `respect_fmt_off` | `True` | Protect `# fmt: off` regions. |
| `show_diff` | `False` | Attach a unified diff to changed results. |
| `backup` | `False` | Save the original bytes as `<name>.py.bak`. |
| `reported_e501_lines` | `frozenset()` | Rows from an earlier Ruff report that seed the first pass. |
| `ruff_command` | `("ruff",)` | Launcher prefix, e.g. a bundled toolchain. |

#### Results

All results are frozen dataclasses.

- `TextResult` — `source`, `changed`, `passes`, `unresolved_lines`,
  `protected_lines`, `unfixable_lines`, `diff`.
- `Result` — the same fields for a file, with `path` instead of `source`.
- `BatchResult` — `results`, plus `changed`, `clean` and `unresolved_count`.

`changed` means the transformed output differs from the input, not that a
write happened (`check_only` suppresses writes).

#### `LongLinesAPI`

| Method | Purpose |
|---|---|
| `transform(source, settings, path)` | Repair a string without touching the filesystem. `path` only selects the Ruff configuration. |
| `fix_file(path, settings)` | Repair one file; writes unless `check_only`. |
| `fix(paths, settings, ruff_report, resolve_line_length=)` | Repair files and directories deterministically. |
| `discover(paths)` | Expand inputs into sorted Python files; skips hidden, build and bundle trees. |
| `parse_ruff_report(path)` | Read E501 rows from a broad Ruff JSON report. Raises `ValueError` for invalid JSON and `TypeError` when the JSON is not an array. |
| `ruff_e501_rows(path, ruff_command)` | Ask Ruff for one file's E501 rows; empty when Ruff is unavailable. |
| `resolve_line_length(file_path, ruff_command)` | Effective width: Ruff's resolved settings, then `pyproject.toml`, then `79`. |
| `find_pyproject(file_path)` | Nearest enclosing `pyproject.toml`. |
| `has_long_lines(path, line_length)` | Cheap pre-scan for over-width lines. |

`fix(..., resolve_line_length=True)` resolves the width once per project
configuration, not once per file.

#### `LongLineRepair`

The `FileRepair` implementation used by `lints`. Calling
`repair(path=path)` repairs one stabilized file; `repair.summary()` returns a
`RepairSummary` of repaired, unresolved and skipped paths. It is safe to call
from worker threads.

### Guarantees

- **Semantics.** Candidates must parse to an identical AST. Docstring text is
  the only value allowed to change, and only through the docstring repair.
- **Convergence.** Passes stop at a fixpoint or when a source repeats; a
  second run on the output is a no-op.
- **Atomic writes.** Files are written through a temporary file in the same
  directory and replaced atomically, preserving mode and encoding.
- **Encoding.** The source encoding cookie or BOM is honored and restored.
- **Determinism.** Repairs run in a fixed order with no randomness.
## JavaScript delimiter simplifier

`JavaScriptDelimiterSimplifier` is a dependency-free Python 3.13 library for
conservatively removing unnecessary JavaScript parentheses and braces while
preserving JavaScript syntax and the semantics of the constructs it knows how
to transform.

It is deliberately **not a minifier** and has no CLI layer. The public API is
Python-only and returns immutable dataclass-based results and metrics instead
of printing output or encoding results in process exit codes. The `lints`
fix mode runs it as `custom_javascript_delimiters`: `scan_delimiters`
audits every in-scope `.js`/`.mjs`/`.cjs` file and
`JavaScriptDelimiterSimplifier` rewrites the ones carrying removable
delimiters, guarded by Node syntax validation.

### Files

- `exactus/tools/lints/js_delimiters.py` — production library and scan
  API.
- `exactus/tests/exactus/tools/lints/test_js_delimiters.py` — pytest
  behavioral/regression suite.
- `exactus/docs/exactus/tools/lints/DOCS.md` — this document.

### Design goals

The library is designed around five requirements:

1. Remove delimiters only when the transformation is known to be safe.
2. Preserve precedence, associativity, lexical scope, optional-chain
   boundaries, arrow/object grammar, comments, strings, templates and regexes.
3. Iterate transformations until the source reaches a stable representation.
4. Validate changed file source with Node when validation is enabled and Node
   is available.
5. Return detailed immutable metadata for text, file and multi-file execution.

Correctness takes priority over compactness. A pair of parentheses or braces
is retained whenever the implementation cannot prove that removing it is safe.

### Requirements

- Python 3.13 or newer.
- Node.js is optional but strongly recommended when `validate=True`.
- `pytest` and `coverage` are required only for running the supplied tests and
  measuring coverage.

There are no runtime Python package dependencies outside the standard library.

### Supported JavaScript files

Directory discovery processes:

- `.js`
- `.mjs`
- `.cjs`

JSX is intentionally not processed. JSX requires a JSX-aware parser and must
not be treated as ordinary ECMAScript by a conservative source transformer.

### Default exclusions

`JavaScriptDelimiterSimplifier.DEFAULT_EXCLUDES` contains:

```text
node_modules
__pycache__
.git
.hg
.svn
dist
build
.build-cache
coverage
exactus/bundle
```

`JavaScriptFiles` applies these exclusions during recursive discovery.
Callers may supply a different exclusion tuple to `simplify_paths()`.

## Public data model

All result/metric dataclasses are frozen and use slots. Results can therefore
be passed between application layers without exposing mutable execution state.

### `Replacement`

Describes one accepted source replacement.

Fields:

- `start: int` — inclusive source offset.
- `end: int` — exclusive source offset.
- `text: str` — replacement text.
- `kind: str` — transformation category.

Property:

- `characters_removed` — net characters removed by the replacement, never
  below zero.

`Replacement` is primarily transformation metadata. Higher-level callers
normally consume the aggregated `TransformationMetrics`.

### `TransformationMetrics`

Summarizes all accepted transformations for one source.

Fields:

- `total: int` — total accepted transformations.
- `by_kind: tuple[tuple[str, int], ...]` — deterministic sorted counts.
- `characters_removed: int` — sum of net characters removed by accepted
  replacements.
- `parentheses_removed: int` — number of parenthesis delimiter characters
  removed.
- `braces_removed: int` — number of brace delimiter characters removed.

Methods:

#### `TransformationMetrics.from_replacements(*, replacements)`

Constructs metrics from the complete accepted replacement history.

#### `TransformationMetrics.count(*, kind)`

Returns the count for one transformation kind, or `0` when absent.

Example:

```python
count: int = result.transformations.count(
    kind="arrow-parameter-parentheses",
)
```

### `SourceMetrics`

Describes physical source-size differences.

Fields:

- `bytes_before`
- `bytes_after`
- `characters_before`
- `characters_after`
- `lines_before`
- `lines_after`
- `blank_lines_before`
- `blank_lines_after`

Derived properties:

- `bytes_removed`
- `characters_removed`
- `lines_removed`
- `blank_lines_removed`

These values are **net source deltas**. They are intentionally distinct from
transformation counts. For example, several transformations may occur on one
line without removing the line.

#### `SourceMetrics.compare(*, before, after)`

Builds source metrics for two strings.

Byte counts use UTF-8 encoding. Line counts use `str.splitlines()`.

### `ValidationMetrics`

Describes JavaScript syntax validation for a file result.

Fields:

- `requested: bool` — validation was enabled on the simplifier.
- `available: bool` — a Node executable was available.
- `performed: bool` — validation was actually run.
- `passed: bool | None` — result when performed; otherwise `None`.
- `engine: str | None` — validation engine description when applicable.

Validation is relevant to changed file candidates. It is a syntax gate, not a
claim that Node can prove semantic equivalence.

### `TextResult`

Returned by `simplify_text()`.

Fields:

- `source: str` — final simplified source.
- `changed: bool`
- `transformations: TransformationMetrics`
- `source_metrics: SourceMetrics`
- `elapsed_seconds: float`

### `FileResult`

Returned by `simplify_file()` and stored in `ExecutionMetrics.files`.

Fields:

- `path: Path`
- `changed: bool`
- `written: bool`
- `backup_path: Path | None`
- `transformations: TransformationMetrics`
- `source_metrics: SourceMetrics`
- `validation: ValidationMetrics`
- `elapsed_seconds: float`

`changed` and `written` are deliberately separate. With `write=False`, a file
may be reported as changed while `written` remains false.

### `ExecutionMetrics`

Returned by `simplify_paths()`.

Fields:

- `files: tuple[FileResult, ...]`
- `elapsed_seconds: float`

Aggregate properties:

- `files_total`
- `files_changed`
- `files_written`
- `transformations`
- `transformations_by_kind`
- `bytes_removed`
- `characters_removed`
- `lines_removed`
- `blank_lines_removed`

Aggregates are derived from immutable per-file results rather than maintained
through mutable counters.

## Public classes

### `JavaScriptDelimiterSimplifier`

Main transformation API.

#### Constructor

```python
JavaScriptDelimiterSimplifier(
    *,
    validate: bool = True,
    remove_control_braces: bool = True,
)
```

`validate` enables Node syntax validation when Node is available.

`remove_control_braces` controls transformations such as:

```javascript
if (ready) {
    run();
}
```

to:

```javascript
if (ready) run();
```

It does not disable parenthesis or arrow-body transformations.

#### `simplify_text(*, source)`

Transforms an in-memory JavaScript string.

It never writes files and does not require a `Path`.

```python
from exactus.tools.lints.js_delimiters import JavaScriptDelimiterSimplifier, TextResult

simplifier: JavaScriptDelimiterSimplifier = (
    JavaScriptDelimiterSimplifier(validate=False)
)
result: TextResult = simplifier.simplify_text(
    source="const fn = (x) => { return x * 2; };",
)

assert result.source == "const fn = x => x * 2;"
assert result.changed
```

#### `simplify_file(*, path, write=True, backup=False)`

Transforms one file.

When `write=True`, changed source replaces the original file. When
`backup=True`, the original is first written beside it as `<filename>.bak`.

Use `write=False` for analysis/dry-run behavior.

```python
from pathlib import Path

from exactus.tools.lints.js_delimiters import FileResult, JavaScriptDelimiterSimplifier

simplifier: JavaScriptDelimiterSimplifier = JavaScriptDelimiterSimplifier()
result: FileResult = simplifier.simplify_file(
    path=Path("src/app.js"),
    write=False,
)

if result.changed:
    print(result.transformations.total)
```

#### `simplify_paths(*, roots, excludes=..., write=True, backup=False)`

Discovers supported JavaScript files under one or more roots, processes each
file and returns aggregate metrics.

A root may be a JavaScript file or a directory.

```python
from pathlib import Path

from exactus.tools.lints.js_delimiters import (
    ExecutionMetrics,
    JavaScriptDelimiterSimplifier,
)

simplifier: JavaScriptDelimiterSimplifier = JavaScriptDelimiterSimplifier()

metrics: ExecutionMetrics = simplifier.simplify_paths(
    roots=(Path("src"), Path("exactus/tests/browser")),
    write=False,
)

print(metrics.files_total)
print(metrics.files_changed)
print(metrics.transformations)
print(metrics.lines_removed)
print(metrics.bytes_removed)
print(metrics.transformations_by_kind)
```

To write changes:

```python
metrics: ExecutionMetrics = simplifier.simplify_paths(
    roots=(Path("."),),
    write=True,
    backup=False,
)
```

### `JavaScriptFiles`

Filesystem discovery helper.

Constructor:

```python
JavaScriptFiles(
    *,
    roots: tuple[Path, ...],
    excludes: tuple[str, ...],
)
```

#### `collect()`

Returns a deterministic sorted tuple of unique resolved JavaScript paths.

Direct file roots are accepted when their extension is supported. Directory
roots are recursively traversed.

## Transformation model

The transformer works iteratively. On each pass it lexically protects source
regions that must not be interpreted as structural JavaScript delimiters,
collects candidate replacements, selects deterministic non-overlapping
replacements, applies them, and repeats until no additional accepted
replacement exists.

The complete accepted replacement history is retained for metrics.

### Protected lexical regions

The scanner protects:

- single-quoted strings;
- double-quoted strings;
- template literals;
- line comments;
- block comments;
- probable regular-expression literals.

This prevents delimiters inside lexical content from being treated as source
structure.

Template literals are conservatively protected as a whole. The transformer
does not attempt to rewrite expressions embedded inside `${...}`.

## Supported transformations

The exact accepted transformation depends on context. The following examples
illustrate the supported families rather than defining a textual regex.

### Single arrow parameters

```javascript
(x) => x
```

becomes:

```javascript
x => x
```

Async single parameters are also supported:

```javascript
async (x) => x
```

becomes:

```javascript
async x => x
```

Parentheses remain required for multiple parameters, defaults, rest parameters
and destructuring.

### Arrow return blocks

```javascript
x => {
    return x * 2;
}
```

becomes:

```javascript
x => x * 2
```

Array/string/call and other expression returns can likewise become expression
bodies when safe.

#### Object-literal returns

Object literals require grouping in expression-bodied arrows:

```javascript
x => {
    return { value: x };
}
```

becomes:

```javascript
x => ({ value: x })
```

It must **not** become:

```javascript
x => { value: x }
```

because the latter is parsed as a block containing a labelled statement and
returns `undefined`.

This rule also protects object-expression arrows already written as:

```javascript
items.map(index => ({
    index,
    value: null,
}))
```

The outer object-expression parentheses are retained.

### Redundant grouping

Examples of removable grouping include contexts such as:

```javascript
const value = ((item));
foo((item));
array[(index)];
```

which can reduce to:

```javascript
const value = item;
foo(item);
array[index];
```

### Precedence-aware grouping

Parentheses are removed only when surrounding precedence and associativity make
them unnecessary.

```javascript
const x = (a * b) + c;
const y = a + (b * c);
```

can become:

```javascript
const x = a * b + c;
const y = a + b * c;
```

while:

```javascript
const x = (a + b) * c;
```

must retain its parentheses.

The implementation accounts for operator families including assignment,
conditional, nullish coalescing, logical operators, bitwise operators,
equality/relational/shift operators, additive/multiplicative operators and
exponentiation.

### Control-flow braces

When enabled, a block containing one safe statement can be reduced:

```javascript
if (ready) {
    run();
}

while (ready) {
    run();
}

for (const item of items) {
    use(item);
}

do {
    run();
} while (ready);
```

to the corresponding legal single-statement forms.

`else` blocks are also eligible when safe.

## Delimiters intentionally retained

The transformer is designed to retain delimiters whenever they carry grammar,
precedence, scope or runtime semantics.

### Lexical declarations

This is valid:

```javascript
if (ready) {
    const x = 1;
}
```

but this is invalid JavaScript:

```javascript
if (ready) const x = 1;
```

Therefore blocks containing `const` or `let` declarations are retained.

Class/function declarations and other unsafe single-statement block forms are
also retained.

### Precedence and associativity

Examples that require grouping include:

```javascript
(a + b) * c
a - (b - c)
a / (b / c)
(a ** b) ** c
```

Exponentiation has additional JavaScript grammar restrictions and is treated
accordingly.

### Nullish/logical grammar boundaries

JavaScript restricts unparenthesized mixing of `??` with `&&`/`||`.
Parentheses needed by those grammar boundaries remain.

### Optional-chain boundaries

This distinction is semantically important:

```javascript
(obj?.a).b
```

is not blindly changed to:

```javascript
obj?.a.b
```

Parentheses can terminate an optional chain. Removing them may change whether
a subsequent access throws or short-circuits.

The same caution applies around calls/member/index continuation where grouping
changes optional-chain behavior.

### Object-expression arrow bodies

As described above, the grouping in:

```javascript
x => ({ value: x })
```

is required.

### Comments and ambiguous constructs

Blocks or expressions involving comments or lexical forms that cannot be
safely classified are retained rather than rewritten.

## Safety and validation

### Conservative transformation

The library does not use a “remove everything and see whether it parses”
strategy. Syntax validity alone cannot establish semantic equivalence.

It first applies structural and precedence rules to decide whether a
transformation is safe.

### Node syntax validation

When:

- the simplifier was constructed with `validate=True`;
- source changed; and
- Node is available;

the changed file source is checked using Node before it is written.

If transformed source fails validation, the operation raises `ValueError` and
the invalid candidate is not written.

Validation metadata is returned in `FileResult.validation`.

Node validation is a final syntax gate. It does not replace the transformer's
semantic safety checks.

### Idempotence

The simplifier iterates internally until stable. Running it again on its own
output should therefore produce no further transformations.

A useful integration invariant is:

```python
first = simplifier.simplify_text(source=source)
second = simplifier.simplify_text(source=first.source)

assert not second.changed
assert second.transformations.total == 0
```

## Metrics semantics

There are two distinct metric layers.

### Transformation activity

`TransformationMetrics` answers questions such as:

- How many transformations occurred?
- Which transformation categories occurred?
- How many delimiter characters were removed?
- How many characters did accepted replacements remove?

### Final source delta

`SourceMetrics` answers:

- How much smaller is the final UTF-8 source?
- How many characters disappeared?
- How many physical lines disappeared?
- How many blank lines disappeared?

These values should not be conflated.

For example, five parenthesis transformations on one line may report five
transformations but zero lines removed.

## Analysis-only execution

For project auditing without changing files:

```python
from pathlib import Path

from exactus.tools.lints.js_delimiters import JavaScriptDelimiterSimplifier

simplifier: JavaScriptDelimiterSimplifier = JavaScriptDelimiterSimplifier()

metrics = simplifier.simplify_paths(
    roots=(Path("."),),
    write=False,
)

for result in metrics.files:
    if result.changed:
        print(
            result.path,
            result.transformations.total,
            result.source_metrics.bytes_removed,
        )
```

No CLI is required and the library itself writes nothing to stdout/stderr.

## Backup execution

```python
metrics = simplifier.simplify_paths(
    roots=(Path("src"),),
    write=True,
    backup=True,
)
```

Every changed file receives a sibling `.bak` containing its original source.
`FileResult.backup_path` identifies the backup.

## Disabling control-block removal

If only expression/parenthesis/arrow transformations are desired:

```python
simplifier = JavaScriptDelimiterSimplifier(
    remove_control_braces=False,
)
```

This leaves eligible `if`/`else`/`for`/`while`/`do` braces untouched.

## Custom exclusions

```python
from pathlib import Path

from exactus.tools.lints.js_delimiters import JavaScriptDelimiterSimplifier

simplifier = JavaScriptDelimiterSimplifier()

metrics = simplifier.simplify_paths(
    roots=(Path("."),),
    excludes=(
        "node_modules",
        "vendor",
        "packages",
        "generated",
        "dist",
    ),
    write=False,
)
```

## Error behavior

The API intentionally uses exceptions instead of CLI exit codes.

Typical failures include:

- filesystem read/write errors from `Path`;
- Unicode decoding/encoding failures;
- `ValueError` when transformed JavaScript fails Node syntax validation.

Callers decide whether to fail fast, aggregate failures or wrap them in their
own application-specific result model.

## Testing

The supplied suite is written with pytest and tests the public API rather than
depending on private implementation helpers.

It covers transformation families, preservation cases, lexical content,
precedence behavior, metrics, file discovery, exclusions, dry runs, writes,
backups, validation, idempotence and regression cases discovered against a
real JavaScript project.

Run:

```bash
pytest -q test_js_delimiters.py
```

Coverage:

```bash
coverage run -m pytest -q test_js_delimiters.py
coverage report -m exactus/tools/lints/js_delimiters.py
```

At packaging time the validated suite contained 69 passing tests and the
production module had 92% statement coverage.

The production module and tests also passed the project's combined lint
orchestrator with zero issues across Ruff, Ruff documentation checks,
BasedPyright and Pyrefly.

## Transformation metrics example

```python
from pathlib import Path

from exactus.tools.lints.js_delimiters import ExecutionMetrics, JavaScriptDelimiterSimplifier

simplifier: JavaScriptDelimiterSimplifier = JavaScriptDelimiterSimplifier()

metrics: ExecutionMetrics = simplifier.simplify_paths(
    roots=(Path("."),),
    write=False,
)

summary: dict[str, int | float | tuple[tuple[str, int], ...]] = {
    "files_total": metrics.files_total,
    "files_changed": metrics.files_changed,
    "files_written": metrics.files_written,
    "transformations": metrics.transformations,
    "transformations_by_kind": metrics.transformations_by_kind,
    "bytes_removed": metrics.bytes_removed,
    "characters_removed": metrics.characters_removed,
    "lines_removed": metrics.lines_removed,
    "blank_lines_removed": metrics.blank_lines_removed,
    "elapsed_seconds": metrics.elapsed_seconds,
}
```

## Known limitations

The library intentionally has a narrower contract than a complete ECMAScript
AST parser/printer.

- JSX is not supported.
- TypeScript syntax is not supported.
- Template literals are protected conservatively as complete lexical regions,
  so JavaScript inside `${...}` is not rewritten.
- Regex-literal recognition is lexical/heuristic rather than a full parser.
- The tool does not promise to remove every theoretically redundant delimiter
  in ECMAScript.
- It does not reorder, rename, fold constants, rewrite expressions, format
  source globally or perform general minification.
- Node validation verifies syntax, not semantic equivalence.

These limitations are deliberate. A construct outside the proven
transformation model should remain unchanged rather than be compressed
speculatively.

## Recommended integration

For automated repository cleanup:

1. Instantiate with validation enabled.
2. Run `simplify_paths(..., write=False)` and inspect metrics when introducing
   the tool to a repository.
3. Run the project's JavaScript tests on representative transformed output.
4. Apply with `write=True`.
5. Run the simplifier again and require `files_changed == 0`.
6. Run JavaScript syntax/lint/tests and the Python exactus/tests/lint gates.

The second-run zero-change condition provides a simple mechanical idempotence
check.

## API summary

```text
Replacement
  characters_removed

TransformationMetrics
  from_replacements(...)
  count(...)

SourceMetrics
  compare(...)
  bytes_removed
  characters_removed
  lines_removed
  blank_lines_removed

ValidationMetrics

TextResult

FileResult

ExecutionMetrics
  files_total
  files_changed
  files_written
  transformations
  transformations_by_kind
  bytes_removed
  characters_removed
  lines_removed
  blank_lines_removed

JavaScriptDelimiterSimplifier
  simplify_text(...)
  simplify_file(...)
  simplify_paths(...)

JavaScriptFiles
  collect()
```

The intended high-level entry point is `JavaScriptDelimiterSimplifier`.
## JavaScript function blocks

### Purpose

This package analyzes JavaScript function-like blocks from Python and can
convert eligible callables **to** compact arrow notation or **from** arrow
notation while preserving semantics conservatively.

The Python module is API-only. It has no CLI layer. JavaScript parsing and
source transformation live in `exactus/packages/organize/js/class_organizer.js`
under the `analyze` and `convert` actions.

### Lints integration

Inside `lints`, the module runs as the `custom_javascript_notation`
tool. `scan_function_blocks()` audits every in-scope
`.js`/`.mjs`/`.cjs`/`.jsx` file (except `*.min.js`) on a worker pool with a
shared Espree resolution:

- Without `--fix` each file `normalize()` would rewrite produces one
  `JSN001` warning positioned at the first change; unreadable files report
  `JSN002` and failed analyses `JSN003`, both as errors. When Espree cannot
  be resolved at all, a single `JSN003` finding reports the scan-level
  failure.
- With `--fix` each accepted normalization is applied and reported under
  `healed` with action `normalize` and the transformation count.
- `--no-notation` (or `no-notation = true`) skips the scan;
  `LintExactusConfig.notation` is the Python form.
- Normalization never promotes an instance method to `static`: relocation
  can break instance, inherited, reflective, extracted, or external usage
  that local analysis cannot see. Only arrow conversions that preserve
  semantics are applied.

### Files

- `exactus/tools/lints/js_function_blocks.py` — typed Python 3.13 API and
  data model.
- `exactus/packages/organize/js/class_organizer.js` — Espree AST analyzer,
  transformer, and class-method organizer used through `exactus.packages.organize.javascript`.
- `exactus/tests/exactus/tools/lints/test_js_function_blocks.py` — Python API,
  validation, resolution, process, malformed-output, and scan tests.
- `exactus/tests/exactus/tools/lints/js/function_blocks.test.mjs` — direct
  JavaScript analyzer/transformation tests.
- `exactus/tests/exactus/tools/lints/js/function_blocks_torture.test.mjs` —
  differential runtime torture suite.
- `exactus/tests/exactus/tools/lints/js/fake_espree.cjs` — deterministic ESTree
  fixture parser used only by the JavaScript unit tests; production never
  imports it.

### Requirements

Production use requires:

1. Python 3.13 or newer.
2. Node.js.
3. Espree available to the target JavaScript project, through ESLint, or as a
   global npm package.

The Python resolver checks Espree in this order:

1. Node resolution relative to the target JavaScript file.
2. Espree bundled with an available ESLint executable.
3. `espree/dist/espree.cjs` under the global npm module root.

If none can be resolved, the API raises `RuntimeError` rather than silently
falling back to a weaker parser.

### Python API

#### `JavaScriptBlockAnalyzer`

Create an analyzer with a JavaScript path:

```python
from pathlib import Path

from exactus.tools.lints.js_function_blocks import JavaScriptBlockAnalyzer

analyzer: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(
    path=Path("src/app.js"),
)
```

Accepted suffixes are `.js`, `.mjs`, `.cjs`, and `.jsx`.

Construction raises:

- `FileNotFoundError` when the source file does not exist.
- `ValueError` when the file extension is unsupported.

#### `analyze()`

```python
blocks: tuple[FunctionBlock, ...] = analyzer.analyze()
```

Returns source-ordered immutable `FunctionBlock` values for:

- function declarations;
- function expressions;
- arrow functions;
- class methods;
- callable class fields;
- object shorthand methods.

Each `FunctionBlock` contains:

| Field | Meaning |
| --- | --- |
| `name` | Declared or inferred callable/member name. |
| `kind` | Syntactic callable category. |
| `class_name` | Containing class, when applicable. |
| `method_kind` | Method subtype such as `method`, `constructor`, `get`, `set`, or `field`. |
| `line_start` / `line_end` | One-based source lines. |
| `column_start` / `column_end` | One-based source columns. |
| `static_current` | Whether the class member is currently static. |
| `static_eligible` | Whether an instance member can safely become static under the analyzer's receiver checks. |
| `arrow_current` | Whether the callable currently uses arrow syntax. |
| `arrow_eligible` | Whether the conservative body checks permit arrow conversion. |
| `uses_this_or_super` | Direct receiver dependency detected. |
| `uses_arguments` | Direct use of `arguments` detected. |
| `uses_new_target` | Direct use of `new.target` detected. |
| `is_async` | Async callable state. |
| `arrow_blockers` | Semantic/syntactic reasons preventing conversion. |
| `recommendation` | Suggested modernization action. |
| `source` | Exact source slice represented by the block. |

Possible recommendations include `keep`, `make static arrow`, `make static`,
`use static arrow`, and `use arrow`.

### Conversion API

#### Convert to arrows

```python
result: ConversionResult = analyzer.to_arrow()
```

Equivalent generic call:

```python
result: ConversionResult = analyzer.convert(direction="to_arrow")
```

The converter applies the compact arrow convention when semantics permit.

#### Single identifier parameter

```javascript
function double(x) {
    return x * 2;
}
```

becomes:

```javascript
const double = x => x * 2;
```

The unnecessary parameter parentheses are removed.

#### Multiple or zero parameters

Parentheses remain required:

```javascript
(a, b) => a + b
() => value
```

#### Single return expression

A block containing only a value-returning `return` becomes an expression body:

```javascript
x => x * 2
```

rather than:

```javascript
x => {
    return x * 2;
}
```

#### Object-expression return

Object literals are parenthesized because removing both the block and the
parentheses would change JavaScript parsing:

```javascript
x => ({ value: x })
```

#### Multi-statement bodies

Braces remain when the body cannot be represented as one expression without
changing behavior:

```javascript
x => {
    const value = normalize(x);
    return value;
}
```

#### Class methods

Receiver-independent class methods are converted to the project's preferred
static arrow-field form:

```javascript
class MathTools {
    double(x) {
        return x * 2;
    }
}
```

becomes:

```javascript
class MathTools {
    static double = x => x * 2;
}
```

Already-static eligible methods remain static and are converted to arrow
fields.

#### Object methods

Eligible shorthand methods become arrow-valued properties:

```javascript
const tools = {
    double(x) {
        return x * 2;
    },
};
```

becomes:

```javascript
const tools = {
    double: x => x * 2,
};
```

#### Function expressions

Eligible function expressions are replaced in place:

```javascript
const double = function(x) {
    return x * 2;
};
```

becomes:

```javascript
const double = x => x * 2;
```

### Convert from arrows

```python
result: ConversionResult = analyzer.from_arrow()
```

Equivalent generic call:

```python
result: ConversionResult = analyzer.convert(direction="from_arrow")
```

Standalone arrow expressions become ordinary function expressions. Class
arrow fields become ordinary methods while retaining `static` and `async`
where applicable.

Example:

```javascript
const double = x => x * 2;
```

becomes:

```javascript
const double = function(x) { return x * 2; };
```

A static class arrow field:

```javascript
static double = x => x * 2;
```

becomes:

```javascript
static double(x) { return x * 2; }
```

### Semantic safety rules

Conversion is intentionally conservative. `to_arrow()` refuses conversions
that would alter dynamic callable semantics detected inside the callable.
Important blockers include:

- constructors;
- getters;
- setters;
- generators or `yield`;
- dynamic `this` or `super`;
- `arguments`;
- `new.target`.

`from_arrow()` likewise refuses lexical-arrow conversions when receiver or
other lexical semantics would be changed.

Nested ordinary functions and nested classes are semantic boundaries when the
analyzer checks a callable. Their receiver usage does not incorrectly make the
outer callable receiver-dependent.

This is source-local semantic analysis. It does not attempt whole-program proof
of external constructability or reflective uses such as callers relying on a
function's `.prototype`.

### `ConversionResult`

Every conversion returns an immutable value with:

- `source`: the complete converted JavaScript source;
- `changed`: whether output differs from input;
- `transformations`: number of callable transformations applied.

The API does **not** overwrite the source file. The caller decides whether and
where to persist `result.source`.

### Error model

The Python layer raises:

- `FileNotFoundError` for missing source paths;
- `ValueError` for unsupported extensions or malformed analyzer JSON;
- `RuntimeError` when Node.js/Espree cannot be resolved or the JavaScript
  analyzer process fails.

JavaScript syntax errors from Espree are surfaced through `RuntimeError` by the
Python API.

The JS analyzer first parses as an ECMAScript module and retries as a script.
If both fail, the original module parse error is preserved.

### Testing

#### Python

The Python suite uses `pytest` and `coverage.py`:

```bash
coverage erase
coverage run --branch -m pytest -q exactus/tests/exactus/tools/lints/test_js_function_blocks.py
coverage report -m --include='*/js_function_blocks.py'
```

Current measured result:

- `js_function_blocks.py`: **98%** coverage.
- 27 tests passing.

#### JavaScript

The JavaScript suite uses the Node.js native test runner and native coverage:

```bash
node \
  --experimental-test-coverage \
  --test-coverage-lines=90 \
  --test-coverage-include='*class_organizer.js' \
  --test exactus/tests/exactus/tools/lints/js/function_blocks.test.mjs
```

Current measured result:

- `exactus/packages/organize/js/class_organizer.js` (`analyze`/`convert` actions): **96.92% line coverage**.
- **100% function coverage**.
- 26 tests passing.

`exactus/tests/exactus/tools/lints/js/fake_espree.cjs` supplies deterministic
ESTree fixtures to the JS unit
suite. This keeps unit tests independent of an npm/network installation while
still exercising the actual production analyzer and transformer code. It is
not part of production parser resolution.

### Syntax validation

```bash
python -m py_compile exactus/tools/lints/js_function_blocks.py exactus/tests/exactus/tools/lints/test_js_function_blocks.py
node --check exactus/packages/organize/js/class_organizer.js
```

Both validations pass for the packaged version.

### Full validation

From the repository root:

```bash
coverage erase && \
coverage run --branch -m pytest -q exactus/tests/exactus/tools/lints/test_js_function_blocks.py && \
coverage report --fail-under=90 --include='*/js_function_blocks.py' && \
node --experimental-test-coverage \
    --test-coverage-lines=90 \
    --test-coverage-include='*class_organizer.js' \
    --test exactus/tests/exactus/tools/lints/js/function_blocks.test.mjs && \
python -m py_compile exactus/tools/lints/js_function_blocks.py exactus/tests/exactus/tools/lints/test_js_function_blocks.py && \
node --check exactus/packages/organize/js/class_organizer.js
```

The two coverage thresholds are enforced separately, so high coverage in one
language cannot hide insufficient coverage in the other.

### Semantic arrow-conversion blockers

Automatic normalization treats static eligibility and arrow eligibility as
separate decisions. A receiver-free class method can therefore be promoted to
`static` while deliberately retaining ordinary method syntax when arrow
semantics are not equivalent.

In addition to `this`/`super`, `arguments`, `new.target`, generators/yield,
constructors, getters, and setters, standalone ordinary functions are preserved
when ordinary-function identity is observably required. This includes detected
construction with `new`, `.prototype` access, declaration use before the
function declaration (hoisting), and named function expressions. Reverse
conversion likewise preserves arrows that lexically capture `this`,
`arguments`, or `new.target`.

### Differential torture suite

`exactus/tests/exactus/tools/lints/js/function_blocks_torture.test.mjs` uses real
Espree rather than the deterministic fake
parser used by the focused unit tests. It generates families of executable
programs, normalizes them, executes both original and transformed programs in
Node.js, and requires identical exit status, standard output, and standard
error. It covers safe standalone conversion, parameter forms, constructibility,
prototype/reflection, aliases, hoisting, dynamic and lexical receiver semantics,
`arguments`, `new.target`, generators, nested callable scope ownership,
accessors, inheritance/`super`, and normalization idempotency.

Automatic normalization is intentionally more conservative than forced
`to_arrow`: an instance method can be `static_eligible` based on its body while
still being preserved automatically because moving it to the static side can
break existing instance, inherited, reflective, extracted, or external usage.
Unknown usage therefore means no automatic relocation.
### JavaScript method organization

The `organize` pre-stage includes `.js`, `.jsx`, `.mjs`, and `.cjs` files from
the resolved ESLint scope. It reorders only safe contiguous, non-computed class
method/accessor runs. Fields, static blocks, computed names, and other class
members remain fixed barriers. The order is constructor; public static
accessors; public static methods; public accessors; public methods; private
static accessors; private static methods; private accessors; private methods.
Getter/setter pairs remain adjacent with the getter first. Step traces identify
the language with `organize[python]` and `organize[javascript]` prefixes.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Lints exactus tool. |
| `arguments.py` | Declare the lints grammar without importing its execution engine. |
| `compliance.py` | Exactus suppression markers, escape-hatch annotations, and lint config. |
| `core.py` | Lint exactus engine: clean, lint, and type-check sources with rollback. |
| `css_tokens.py` | Audit the CSS custom-property architecture and terminal-layer policy. |
| `js_delimiters.py` | Conservatively remove unnecessary JavaScript parentheses and braces. |
| `js_function_blocks.py` | Report JavaScript function and method blocks and modernization eligibility. |
| `long_lines.py` | Repair Python lines that remain too long after Ruff formatting. |
| `long_lines_engine.py` | Repair Python lines that remain too long after Ruff formatting. |
| `main.py` | Run the combined lint exactus and emit the LINTS report bundle. |
| `packages_pipeline.py` | Bridge Exactus lints to packaged source-refactor and lint tools. |
| `report.py` | Normalize the LINTS report: summary, scope, findings and metrics. |
| `shebang.py` | Exactus Python executable permissions against shebang presence. |
| `string_transform.py` | Source-preserving string dedenting, splitting and f-string formatting. |
| `templates/` | Subdirectory. |

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--workers` | Maximum independent external lint processes; defaults to min(16, CPU count). Use 1 for serial execution. | type=_positive, default=None, metavar='N' |
| `--no-clean` | Skip source cleaning and formatter passes. | action='store_true' |
| `--no-fix` | Audit only: report without healing. Skips the Ruff format/check --fix convergence loop along with source cleaning, convention rewrites, refactors, shebang repair and guarded inference. | action='store_true' |
| `--simple` | Run only the all_lints package audit and report its findings alone: skips source cleaning, convention scans, refactors, compliance and guarded inference. | action='store_true' |
| `--no-long-lines` | Skip the long-line repair that runs inside the Ruff --fix convergence loop. | action='store_true' |
| `--no-delimiters` | Skip the JavaScript delimiter scan and the delimiter simplification it applies under --fix. | action='store_true' |
| `--no-notation` | Skip the JavaScript function-block scan and the arrow or static normalization it applies under --fix. | action='store_true' |
| `--no-infer` | Skip guarded pyrefly infer. | action='store_true' |
| `--no-group-final` | Skip the group_final refactor that normally runs first. | action='store_true' |
| `--no-organize` | Skip the organize class-method reorder that normally runs after scope collection. | action='store_true' |
| `--unsafe-fixes` | Allow Ruff unsafe fixes during all_lints stabilization. | action='store_true' |
| `--no-shebang-heal` | Report shebang/executable mismatches without repairing them. | action='store_true' |
| `--exec-no-shebang` | Heal executable files lacking a shebang by inserting the interpreter line for their suffix (default) or by clearing their executable bits. | choices=('add-shebang', 'drop-exec'), default='add-shebang' |
| `--shebang-no-exec` | Heal shebang files lacking the executable bit by marking them executable (default) or by removing the shebang line. | choices=('add-exec', 'drop-shebang'), default='add-exec' |
| `--no-install-tools` | Do not install missing external tools. | action='store_true' |
| `--runtime-max-runs` | Finished runs kept in the shared EXACTUS_RESULTS/.runtime registry; the oldest are pruned after each run (default: 500). | type=_positive, default=None, metavar='N' |
| `--runtime-max-size` | Byte cap on the shared EXACTUS_RESULTS/.runtime registry database as raw bytes or a size (for example 33554432 or 64MB); the oldest finished runs are deleted when it is exceeded. 0 disables the cap (default: 64MB). | type=_byte_size, default=None, metavar='SIZE' |
| `--bare-import-exception` | Allow a Python bare import. Repeat for multiple modules; defaults to pytest. | action='append', default=list(Constants.default_bare_import_exceptions), metavar='MODULE' |
| `--css-context-word` | Application or component word that CSS CATALOG token names must not contain (CSS118). Repeat for multiple words; components/<name>/ directories are added automatically. | action='append', default=[], metavar='WORD' |
| `--toolchain` | Explicit exactus toolchain executable path. | type=Path, default=None |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Lints exactus tool.


### `arguments.py`

Declare the lints grammar without importing its execution engine.

- `class Constants` — Group module-level constants.
  - `default_bare_import_exceptions` = `('pytest', 'sys')`
  - `size_units` = `{'': 1, 'b': 1, 'byte': 1, 'bytes': 1, 'k': 1 << 10, 'kb': 1 << 10, 'kib'...`
- `create_parser() -> ArgumentParser` — Create parser.

### `compliance.py`

Exactus suppression markers, escape-hatch annotations, and lint config.

- `class Constants` — Compliance exactus constants.
  - `suppression_names` = `('noqa', 'type: ignore', 'pyright: ignore', 'ruff: noqa', 'basedpyright:...`
  - `skipped_dirs` = `ExactusCommonTables.DEFAULT_EXCLUDED_DIRS`
  - `duplicate_copy` = `compile_pattern(pattern=' \\d+(?:\\.[^.]+)?$')`
  - `lint_ignore_prefixes` = `('per-file-ignores', 'extend-ignore')`
  - `allowed_lint_ignores` = `frozenset({'COM812', 'D203', 'D213'})`
  - `typecheck_suffixes` = `('false', '"none"', "'none'")`
  - `environment_table` = `compile_pattern(pattern='\\[\\[\\s*tool\\.(?:based)?pyright\\.executionEn...`
  - `suppressions` = `tuple((f'# {name}' for name in suppression_names))`
  - `ignore_list` = `compile_pattern(pattern='^ignore\\s*=\\s*\\[(?P<codes>[^\\]]*)\\]')`
  - `quoted_code` = `compile_pattern(pattern='["\\\'](?P<code>[^"\\\']+)["\\\']')`
  - `rules` = `{'CMP000': ('Module does not parse', 'Parsing'), 'CMP001': ('Suppression...`
  - `excluded_reason` = `'excluded by include/exclude rules'`
  - `builtin_excludes` = `('**/.*', '**/__pycache__/**', '**/build/**', '**/dist/**', '**/*.egg-inf...`
  - `default_include` = `'**/*.py'`
- `class ComplianceFinding` — One compliance violation located in a scanned file.
  - `severity` = `'error'`
  - Fields: `rule: str`, `file: str`, `line: int`, `message: str`
- `class ComplianceInput` — Carry the inputs of one compliance exactus run.
  - `source_files` = `None`
  - Fields: `root: Path`, `includes: tuple[str, ...]`, `excludes: tuple[str, ...]`
- `class ComplianceSkip` — One Python file found under the root but not exactused.
  - Fields: `target: str`, `reason: str`
- `class ComplianceResult` — Outcome of one compliance exactus run.
  - `includes` = `()`
  - `excludes` = `()`
  - `skipped` = `()`
  - Fields: `files: int`, `findings: tuple[ComplianceFinding, ...]`
- `skipped(*, name: str) -> bool` — Report whether a path segment is excluded from the exactus.
- `scan(*, inputs: ComplianceInput) -> tuple[list[Path], list[ComplianceSkip]]` — Collect owned Python sources and the files left out.
- `python_files(*, inputs: ComplianceInput) -> list[Path]` — Collect owned Python sources under the exactus root.
- `suppression_findings(*, path: Path, root: Path) -> list[ComplianceFinding]` — Reject diagnostic-suppression comment markers in one file.
- `annotation_findings(*, path: Path, root: Path) -> list[ComplianceFinding]` — Reject ``typing.Any`` and flag ``object`` escape-hatch annotations.
- `configuration_findings(*, root: Path) -> list[ComplianceFinding]` — Reject lint and type-check suppression configuration.
- `scan_compliance(*, inputs: ComplianceInput) -> ComplianceResult` — Exactus owned Python sources and lint configuration.

### `core.py`

Lint exactus engine: clean, lint, and type-check sources with rollback.

- `template_resource(*, name: str) -> Traversable` — Locate a bundled linter template.
- `class Constants` — Hold the report schema and tool-matching defaults.
  - `report_version` = `1`
  - `python_suffixes` = `frozenset({'.py', '.pyi'})`
  - `eslint_suffixes` = `frozenset({'.js', '.jsx', '.mjs', '.cjs'})`
  - `stylelint_suffixes` = `frozenset({'.css'})`
  - `htmlhint_suffixes` = `frozenset({'.htm', '.html'})`
  - `tool_names` = `('custom_compliance', 'custom_shebang', 'custom_python', 'custom_python_l...`
  - `default_bare_import_exceptions` = `('pytest', 'sys')`
  - `python_packages` = `(('ruff', 'ruff'), ('basedpyright', 'basedpyright'), ('pyrefly', 'pyrefly'))`
  - `node_packages` = `(('eslint', 'eslint'), ('tsc', 'typescript'), ('stylelint', 'stylelint'),...`
  - `node_path_extras` = `('/opt/homebrew/bin', '/usr/local/bin', '/usr/bin')`
  - `ruff_extend_ignores` = `('--extend-ignore', 'D203', '--extend-ignore', 'D213')`
  - `ruff_config_names` = `('ruff.toml', '.ruff.toml')`
  - `eslint_config_names` = `('eslint.config.js', 'eslint.config.mjs', 'eslint.config.cjs')`
  - `jsconfig_names` = `('jsconfig.json', 'tsconfig.json')`
  - `stylelint_config_names` = `('.stylelintrc', '.stylelintrc.json', '.stylelintrc.yaml', '.stylelintrc....`
  - `upper_global_pattern` = `compile_regex(pattern='^_*[A-Z][A-Z0-9_]*$')`
  - `upper_global_exempt_calls` = `frozenset(('TypeVar', 'ParamSpec', 'TypeVarTuple', 'TypeAliasType', 'NewT...`
  - `js_class_pattern` = `compile_regex(pattern='^[ \\t]*(?:export\\s+(?:default\\s+)?)?class\\s+(?...`
  - `js_method_pattern` = `compile_regex(pattern='(?m)^[ \\t]*(?P<static>static\\s+)?(?:async\\s+)?(...`
  - `js_arrow_field_pattern` = `compile_regex(pattern='(?m)^[ \\t]*(?P<static>static\\s+)?(?:async\\s+)?(...`
  - `js_function_pattern` = `compile_regex(pattern='(?m)^[ \\t]*(?:async\\s+)?function\\s+(?P<name>[A-...`
  - `css_measure_pattern` = `compile_regex(pattern='(?i)(?<![-\\w.])(?:\\d+(?:\\.\\d+)?|\\.\\d+)(?:px|...`
  - `css_numeric_literal_pattern` = `compile_regex(pattern='(?i)(?<![#\\w.-])(?P<number>[-+]?(?:\\d+(?:\\.\\d+...`
  - `css_gradient_pattern` = `compile_regex(pattern='(?i)\\b(?:repeating-)?(?:linear|radial|conic)-grad...`
  - `css_color_pattern` = `compile_regex(pattern='(?i)(?:#[0-9a-f]{3,8}\\b|\\b(?:rgb|rgba|hsl|hsla|h...`
  - `css_time_pattern` = `compile_regex(pattern='(?<![-\\w.])(?:\\d+(?:\\.\\d+)?|\\.\\d+)(?:ms|s)\\b')`
  - `css_easing_pattern` = `compile_regex(pattern='(?i)\\b(?:linear|ease|ease-in|ease-out|ease-in-out...`
  - `css_font_text_properties` = `frozenset({'font', 'font-family', 'font-size', 'font-size-adjust', 'font-...`
  - `css_allowed_literals` = `frozenset({'0', '1', '0%', '100%'})`
  - `js_style_assignment_pattern` = `compile_regex(pattern='(?m)(?P<target>[A-Za-z_$][\\w$]*(?:\\.[A-Za-z_$][\...`
  - `js_style_set_property_pattern` = `compile_regex(pattern='(?m)(?P<target>[A-Za-z_$][\\w$]*(?:\\.[A-Za-z_$][\...`
  - `js_object_assign_style_pattern` = `compile_regex(pattern='(?s)Object\\.assign\\(\\s*(?P<target>[A-Za-z_$][\\...`
  - `js_object_property_pattern` = `compile_regex(pattern='(?m)(?P<property>[A-Za-z_$][\\w$]*|[\'\\"][^\'\\"]...`
  - `js_identifier_pattern` = `compile_regex(pattern='[A-Za-z_$][\\w$]*')`
  - `js_masked_region_pattern` = `compile_regex(pattern='\'(?:\\\\.|[^\'\\\\])*\'|"(?:\\\\.|[^"\\\\])*"|`(?...`
  - `js_quoted_value_pattern` = `compile_regex(pattern='^([\'\\"])(?:\\\\.|(?!\\1).)*\\1$')`
  - `js_static_value_pattern` = `compile_regex(pattern='^(?:[-+]?(?:\\d+(?:\\.\\d+)?|\\.\\d+)|true|false|n...`
  - `css_reference_pattern` = `compile_regex(pattern='(?i)\\b(?:var|url)\\s*\\(')`
  - `css_descriptor_pattern` = `compile_regex(pattern='(?i)@(?:font-face|property|counter-style)\\b[^{}]*...`
  - `css_priority_pattern` = `compile_regex(pattern='(?i)\\s*!\\s*important\\s*$')`
  - `css_comment_pattern` = `compile_regex(pattern='(?s)/\\*.*?\\*/')`
  - `comment_body_pattern` = `compile_regex(pattern='[^\\n]')`
  - `css_declaration_pattern` = `compile_regex(pattern='(?m)(?:^|[{;])\\s*(?P<property>-{0,2}[\\w][\\w-]*)...`
  - `html_comment_pattern` = `compile_regex(pattern='(?s)<!--.*?-->')`
  - `html_style_tag_pattern` = `compile_regex(pattern='(?is)<style(?:\\s[^>]*)?>')`
  - `html_style_block_pattern` = `compile_regex(pattern='(?is)<style\\b[^>]*>.*?</style\\s*>')`
  - `html_inline_script_pattern` = `compile_regex(pattern='(?is)<script\\b(?P<attrs>[^>]*)>(?P<body>.*?)</scr...`
  - `html_script_src_pattern` = `compile_regex(pattern='(?i)(?<![\\w-])src\\s*=')`
  - `html_type_attribute_pattern` = `compile_regex(pattern='(?i)(?<![\\w-])type\\s*=\\s*[\\"\']?(?P<type>[\\w....`
  - `html_style_attribute_pattern` = `compile_regex(pattern='(?i)(?<![\\w-])style\\s*=\\s*(?P<value>\\"[^\\"]+\...`
  - `html_event_attribute_pattern` = `compile_regex(pattern='(?i)(?<![\\w-])(?P<name>on[a-z]+)\\s*=')`
  - `html_javascript_url_pattern` = `compile_regex(pattern='(?i)(?<![\\w-])(?:href|src|action|formaction|xlink...`
  - `html_data_script_types` = `frozenset({'application/json', 'application/ld+json', 'importmap', 'specu...`
  - `stylelint_default_config` = `{'ignoreFiles': ['**/node_modules/**', '**/*.min.css', '**/dist/**', '**/...`
  - `empty_methods` = `frozenset()`
  - `version_commands` = `{'ruff': 'ruff', 'ruff_docs': 'ruff', 'basedpyright': 'basedpyright', 'py...`
  - `version_pattern` = `compile_regex(pattern='\\d+(?:\\.\\d+)+[\\w.+-]*')`
  - `version_timeout` = `30.0`
  - `stage_spans` = `{'toolchain': (0.02, 0.06), 'clean': (0.06, 0.12), 'conventions': (0.12,...`
  - `simple_stage_spans` = `{'toolchain': (0.02, 0.08), 'all lints': (0.08, 0.95), 'compliance and re...`
  - `total_stages` = `8`
  - `simple_total_stages` = `4`
  - `ruff_config_text(cls, *, cwd: Path) -> str` — Return the project's own Ruff configuration text, if any.
  - `ruff_policy(cls, *, cwd: Path) -> tuple[str, ...]` — Return Ruff rule-selection flags for the exactused project.
- `class CommandResult` — Store one subprocess result.
  - `duration_seconds` = `0.0`
  - Fields: `command: tuple[str, ...]`, `returncode: int`, `stdout: str`, `stderr: str`
- `class Snapshot` — Describe the pre-inference Python source snapshot.
  - Fields: `root: Path`, `files: Mapping[Path, Path]`, `existing: frozenset[Path]`
- `class SummaryInput` — Carry report-summary construction inputs.
  - Fields: `started_at: datetime`, `finished_at: datetime`, `duration_seconds: float`, `cwd: Path`, `report_path: Path | None`, `targets: Sequence[str]`, `ignores: Sequence[str]`, `tools: Mapping[str, JsonValue]`, `all_findings: Sequence[JsonValue]`, `python_args: Sequence[str]`, `eslint_args: Sequence[str]`, `stylelint_args: Sequence[str]`, `htmlhint_args: Sequence[str]`
- `class LintProgress` — Publish ordered lint-exactus stages to the shared progress channel.
  - `completed` = `0`
  - `total` = `Constants.total_stages`
  - `span` = `(0.0, 0.02)`
  - `share` = `0.0`
  - `simple` = `False`
  - `stage(self, *, name: str) -> None` — Mark the previous stage finished and publish ``name``.
  - `note(self, *, step: str, detail: str='', share: float | None=None, completed: int | None=None, total: int | None=None) -> None` — Publish a progress snapshot without advancing the stage.
- `class LintExactusInput` — Carry guarded-inference inputs.
  - `progress` = `field(default_factory=LintProgress)`
  - Fields: `cwd: Path`, `targets: Sequence[str]`, `ignores: Sequence[str]`, `python_args: Sequence[str]`, `python_files: frozenset[Path]`, `bare_import_exceptions: Sequence[str]`, `baselines: tuple[frozenset[IssueKey], frozenset[IssueKey]]`, `tools: dict[str, JsonValue]`, `commands: ToolCommands`, `arguments: ToolArguments`, `writer: Writer`
- `class CleanStats` — Accumulated metrics from a cleaning run.
  - `scanned` = `0`
  - `changed` = `0`
  - `lines_removed` = `0`
  - `bytes_delta` = `0`
- `class LintExactusConfig` — Toggle the mutating and tool-management stages of the exactus.
  - `clean` = `True`
  - `fix` = `True`
  - `long_lines` = `True`
  - `delimiters` = `True`
  - `notation` = `True`
  - `infer` = `True`
  - `install_tools` = `True`
  - `group_final` = `True`
  - `organize` = `True`
  - `unsafe_fixes` = `False`
  - `workers` = `None`
  - `shebang` = `field(default_factory=ShebangSettings)`
  - `simple` = `False`
- `class LintExactusRequest` — Carry the inputs of one guarded lint-exactus run.
  - `css_context_words` = `()`
  - Fields: `cwd: Path`, `targets: Sequence[str]`, `report_path: Path | None`, `ignores: Sequence[str]`, `bare_import_exceptions: Sequence[str]`, `config: LintExactusConfig`, `writer: Writer`, `toolchain: Path | None`, `tool_args: ToolArguments`
- `class PythonReportInput` — Carry inputs for the Python analyzer stage.
  - `progress` = `field(default_factory=LintProgress)`
  - Fields: `tools: dict[str, JsonValue]`, `cwd: Path`, `python_args: Sequence[str]`, `commands: ToolCommands`, `arguments: ToolArguments`, `fix: bool`
- `class CustomToolsInput` — Carry inputs for the built-in convention scans.
  - `css_context_words` = `()`
  - `shebang` = `field(default_factory=ShebangSettings)`
  - `progress` = `field(default_factory=LintProgress)`
  - `fix` = `True`
  - `ruff_command` = `None`
  - `delimiters` = `True`
  - `notation` = `True`
  - Fields: `cwd: Path`, `python_files: frozenset[Path]`, `eslint_args: Sequence[str]`, `stylelint_args: Sequence[str]`, `htmlhint_args: Sequence[str]`, `bare_import_exceptions: Sequence[str]`, `targets: Sequence[str]`, `ignores: Sequence[str]`
- `class AllLintsStageInput` — Carry inputs for the all-lints package stage.
  - `progress` = `field(default_factory=LintProgress)`
  - `repair` = `None`
  - Fields: `cwd: Path`, `targets: Sequence[str]`, `ignores: Sequence[str]`, `commands: ToolCommands`, `tool_args: ToolArguments`, `config: LintExactusConfig`, `tools: dict[str, JsonValue]`
- `class FinishToolsInput` — Carry inputs for the compliance and report stage.
  - `simple` = `False`
  - Fields: `cwd: Path`, `targets: Sequence[str]`, `ignores: Sequence[str]`, `python_files: frozenset[Path]`, `tools: dict[str, JsonValue]`, `commands: Mapping[str, tuple[str, ...] | None]`
- `class FrontendReportInput` — Carry inputs for the frontend analyzer stage.
  - `progress` = `field(default_factory=LintProgress)`
  - Fields: `tools: dict[str, JsonValue]`, `cwd: Path`, `eslint_args: Sequence[str]`, `stylelint_args: Sequence[str]`, `htmlhint_args: Sequence[str]`, `commands: ToolCommands`, `arguments: ToolArguments`
- `class NodeVisitorWalk` — Provide compact AST traversal helpers.
  - `walk(tree: AST) -> list[AST]` — Return descendants including the supplied AST node.
  - `children(node: AST) -> list[AST]` — Return direct AST children.
- `class JavaScriptScanner` — Provide lightweight lexical JavaScript helpers.
  - `block_end(source: str, start: int, opening: str='{', closing: str='}') -> int` — Find the matching delimiter while respecting quoted strings.
  - `tokens(source: str) -> frozenset[str]` — Return identifier-like tokens outside strings and comments.
- `class SourceCleaner` — Normalize safe whitespace and format without formatter conflicts.
  - `py` = `frozenset({'.py', '.pyi'})`
  - `js` = `frozenset({'.js', '.jsx', '.mjs', '.cjs'})`
  - `css` = `frozenset({'.css'})`
  - `html` = `frozenset({'.html', '.htm'})`
  - `prettier` = `css | html`
  - `suffixes` = `py | js | prettier`
  - `markup_raw_tags` = `('pre', 'textarea', 'script', 'xmp', 'listing')`
  - `default_excludes` = `ExactusCommonTables.DEFAULT_EXCLUDED_DIRS | frozenset({'exec'})`
  - `normalize(cls: type[Self], path: Path, source: str) -> str` — Clean source and ensure exactly one final newline.
  - `collect(cls: type[Self], cwd: Path, targets: Sequence[str], excludes: Sequence[str], on_file: Callable[[Path], None] | None=None) -> list[Path]` — Expand and filter source paths for cleaning.
  - `run(cls: type[Self], files: Sequence[Path], cwd: Path, writer: Writer, commands: ToolCommands) -> CleanStats` — Clean source files and run formatters.
- `class LintExactus` — Lint, type-check, and guard ``pyrefly infer`` against regressions.
  - `run(cls: type[Self], request: LintExactusRequest) -> tuple[dict[str, JsonValue], int]` — Run the complete guarded lint workflow.
  - `run_command(command: Sequence[str], cwd: Path) -> CommandResult` — Run one command without raising for diagnostics.
  - `parse_json_output(result: CommandResult) -> JsonValue` — Parse JSON output from a command.

### `css_tokens.py`

Audit the CSS custom-property architecture and terminal-layer policy.

- `class Layer` — Custom-property architecture layers.
  - `PRIMARY` = `'primary'`
  - `DYNAMIC` = `'dynamic'`
  - `BASE` = `'base'`
  - `CATALOG` = `'catalog'`
  - `SEMANTIC` = `'semantic'`
- `class Constants` — CSS token audit constants.
  - `rules` = `{'CSS100': 'unreadable-stylesheet', 'CSS101': 'duplicate-definition', 'CS...`
  - `var_reference` = `compile_pattern(pattern='var\\(\\s*(--[^\\s,)]+)', flags=IGNORECASE)`
  - `design_function` = `compile_pattern(pattern='(?<![-\\w])(calc|min|max|clamp|minmax|color-mix|...`
  - `design_literal` = `compile_pattern(pattern='(?<![\\w.-])[+-]?(?:\\d*\\.\\d+|\\d+)(?:e[+-]?\\...`
  - `provenance` = `compile_pattern(pattern='(?:^|-)(?:derived|generated|autogenerated|auto-g...`
  - `numeric_suffix` = `compile_pattern(pattern='-\\d+$')`
  - `special` = `compile_pattern(pattern='/\\*|[\\"\'\\\\]|(?<![\\w-])url\\(', flags=IGNOR...`
  - `important` = `compile_pattern(pattern='\\s*!\\s*important\\s*$', flags=IGNORECASE)`
  - `property_name` = `compile_pattern(pattern='[*_]?[^\\s{};()\\"\'@:,<>=!/&#.\\[\\]+~]+')`
  - `var_open` = `compile_pattern(pattern='(?<![\\w-])var\\(', flags=IGNORECASE)`
  - `analysis_limit` = `16384`
  - `message_limit` = `120`
  - `blanks` = `' \t\r\n\x0c'`
  - `function_call` = `compile_pattern(pattern='[A-Za-z_-][A-Za-z0-9_-]*\\s*\\(')`
  - `color_mix` = `compile_pattern(pattern='\\bcolor-mix\\s*\\(', flags=IGNORECASE)`
  - `identity_calc` = `compile_pattern(pattern='calc\\([^)]*(?:\\*\\s*var\\(\\s*--base-number-(?...`
  - `noncanonical_scale` = `compile_pattern(pattern='(?:^|-)(?:[2-9]xl|[2-9]xs|sm|md|lg)(?:-|$)', fla...`
  - `plain_reference` = `compile_pattern(pattern='var\\(\\s*(--[^\\s,)]+)\\s*\\)', flags=IGNORECASE)`
  - `catalog_reference` = `compile_pattern(pattern='var\\(\\s*--catalog-[^\\s,)]+\\s*\\)', flags=IGN...`
  - `bare_number` = `compile_pattern(pattern='(?<![\\w.-])[+-]?(?:\\d*\\.\\d+|\\d+)(?![\\w.%-])')`
  - `design_properties` = `frozenset({'-webkit-border-before', '-webkit-box-reflect', '-webkit-mask-...`
  - `grammar_properties` = `frozenset({'-moz-float-edge', '-moz-force-broken-image-icon', '-moz-orien...`
  - `configurable_numeric` = `frozenset({'column-count', 'columns', 'fill-opacity', 'flex-grow', 'flex-...`
  - `catalog_domains` = `frozenset({'measure', 'typography', 'color', 'border', 'cursor', 'effect'...`
  - `allowed_base_references` = `frozenset({Layer.PRIMARY, Layer.DYNAMIC})`
  - `min_catalog_segments` = `3`
  - `css_wide_keywords` = `frozenset({'inherit', 'initial', 'unset', 'revert', 'revert-layer'})`
- `class CssTokenInput` — Carry the inputs of one CSS token audit.
  - `context_words` = `frozenset()`
  - Fields: `root: Path`, `files: Sequence[Path]`
- `class CssTokenFinding` — One token-architecture violation.
  - Fields: `rule: str`, `file: Path`, `line: int`, `message: str`
- `class CssDeclaration` — One parsed CSS declaration.
  - `scope` = `''`
  - Fields: `name: str`, `value: str`, `masked: str`, `file: Path`, `line: int`
  - `is_custom(self) -> bool` — Report whether the declaration defines a custom property.
- `class CssSource` — One stylesheet after lexing.
  - Fields: `clean: str`, `masked: str`, `newlines: tuple[int, ...]`
  - `line(self, *, offset: int) -> int` — Return the one-based line holding an offset.
- `layer_of(*, name: str) -> Layer` — Return the architecture layer a custom-property name belongs to.
- `lex(*, text: str) -> CssSource` — Separate a stylesheet's structure from its comments and strings.
- `parse_declarations(*, text: str, file: Path) -> list[CssDeclaration]` — Parse the declarations of one stylesheet.
- `class CssTokenAudit` — Audit a stylesheet set against the token architecture.
  - `__init__(self, *, inputs: CssTokenInput) -> None` — Parse the stylesheet set and audit it immediately.
- `scan_css_tokens(*, inputs: CssTokenInput) -> tuple[CssTokenFinding, ...]` — Audit a stylesheet set against the token architecture.

### `js_delimiters.py`

Conservatively remove unnecessary JavaScript parentheses and braces.

- `class Constants` — Describe Constants.
  - `delimiter_pair_length` = `2`
  - `exponent_precedence` = `14`
- `class Replacement` — Describe Replacement.
  - Fields: `start: int`, `end: int`, `text: str`, `kind: str`
  - `characters_removed(self) -> int` — Characters removed.
- `class TransformationMetrics` — Summarize transformations accepted for one source.
  - Fields: `total: int`, `by_kind: tuple[tuple[str, int], ...]`, `characters_removed: int`, `parentheses_removed: int`, `braces_removed: int`
  - `from_replacements(cls, *, replacements: tuple[Replacement, ...]) -> Self` — From replacements.
  - `count(self, *, kind: str) -> int` — Count.
- `class SourceMetrics` — Describe measurable source-size changes.
  - Fields: `bytes_before: int`, `bytes_after: int`, `characters_before: int`, `characters_after: int`, `lines_before: int`, `lines_after: int`, `blank_lines_before: int`, `blank_lines_after: int`
  - `compare(cls, *, before: str, after: str) -> Self` — Compare.
  - `bytes_removed(self) -> int` — Bytes removed.
  - `characters_removed(self) -> int` — Characters removed.
  - `lines_removed(self) -> int` — Lines removed.
  - `blank_lines_removed(self) -> int` — Blank lines removed.
- `class ValidationMetrics` — Describe JavaScript syntax validation for one result.
  - Fields: `requested: bool`, `available: bool`, `performed: bool`, `passed: bool | None`, `engine: str | None`
- `class TextResult` — Describe one in-memory simplification.
  - `replacements` = `()`
  - Fields: `source: str`, `changed: bool`, `transformations: TransformationMetrics`, `source_metrics: SourceMetrics`, `elapsed_seconds: float`
- `class FileResult` — Describe simplification and metadata for one JavaScript file.
  - `replacements` = `()`
  - Fields: `path: Path`, `changed: bool`, `written: bool`, `backup_path: Path | None`, `transformations: TransformationMetrics`, `source_metrics: SourceMetrics`, `validation: ValidationMetrics`, `elapsed_seconds: float`
- `class ExecutionMetrics` — Aggregate immutable metrics for a multi-file execution.
  - Fields: `files: tuple[FileResult, ...]`, `elapsed_seconds: float`
  - `files_total(self) -> int` — Files total.
  - `files_changed(self) -> int` — Files changed.
  - `files_written(self) -> int` — Files written.
  - `transformations(self) -> int` — Transformations.
  - `transformations_by_kind(self) -> tuple[tuple[str, int], ...]` — Transformations by kind.
  - `bytes_removed(self) -> int` — Bytes removed.
  - `characters_removed(self) -> int` — Characters removed.
  - `lines_removed(self) -> int` — Lines removed.
  - `blank_lines_removed(self) -> int` — Blank lines removed.
- `class JavaScriptDelimiterSimplifier` — Remove conservative subsets of unnecessary JavaScript delimiters.
  - `EXTENSIONS` = `frozenset({'.js', '.mjs', '.cjs'})`
  - `DEFAULT_EXCLUDES` = `('node_modules', '__pycache__', '.git', '.hg', '.svn', 'EXACTUS_RESULTS',...`
  - `IDENTIFIER` = `'[A-Za-z_$][\\w$]*'`
  - `ARROW_PARAMETER` = `compile_pattern(pattern=f'(?:(async)\\s+)?\\(\\s*({IDENTIFIER})\\s*\\)(\\...`
  - `SIMPLE_PAREN` = `compile_pattern(pattern=''.join(('\\(\\s*(', f'(?:{IDENTIFIER}(?:\\s*(?:\...`
  - `CONTROL_HEADER` = `compile_pattern(pattern='\\b(if|for|while|with)\\s*\\(')`
  - `DO_BLOCK` = `compile_pattern(pattern='\\bdo\\s*\\{')`
  - `ELSE_BLOCK` = `compile_pattern(pattern='\\belse\\s*\\{')`
  - `UNSAFE_SINGLE_STATEMENT` = `compile_pattern(pattern='^\\s*(?:(?:const|let|class|function)\\b|if\\b|(?...`
  - `__init__(self, *, validate: bool=True, remove_control_braces: bool=True) -> None` — Init  .
  - `protected_spans(cls, *, source: str) -> tuple[Span, ...]` — Return string, comment, template, and regular-expression spans.
  - `inside_protected(cls, *, index: int, protected: tuple[Span, ...]) -> bool` — Return whether an offset belongs to protected lexical content.
  - `simplify_text(self, *, source: str) -> TextResult` — Simplify text.
  - `simplify_file(self, *, path: Path, write: bool=True, backup: bool=False) -> FileResult` — Simplify file.
  - `simplify_paths(self, *, roots: tuple[Path, ...], excludes: tuple[str, ...]=DEFAULT_EXCLUDES, write: bool=True, backup: bool=False) -> ExecutionMetrics` — Simplify paths.
- `class JavaScriptFiles` — Discover JavaScript files from files and directories.
  - `__init__(self, *, roots: tuple[Path, ...], excludes: tuple[str, ...]) -> None` — Init  .
  - `collect(self) -> tuple[Path, ...]` — Collect.
- `class DelimiterFinding` — Describe DelimiterFinding.
  - `severity` = `'warning'`
  - Fields: `rule: str`, `file: str`, `line: int`, `column: int`, `message: str`
- `class DelimiterHeal` — Describe DelimiterHeal.
  - Fields: `rule: str`, `file: str`, `action: str`, `transformations: int`, `characters_removed: int`
- `class DelimiterInput` — Describe DelimiterInput.
  - `validate` = `True`
  - Fields: `root: Path`, `files: tuple[Path, ...]`, `fix: bool`
- `class DelimiterResult` — Describe DelimiterResult.
  - Fields: `files: int`, `findings: tuple[DelimiterFinding, ...]`, `healed: tuple[DelimiterHeal, ...]`
- `scan_delimiters(*, inputs: DelimiterInput, progress_span: tuple[float, float]=(0.0, 1.0)) -> DelimiterResult` — Scan delimiters.

### `js_function_blocks.py`

Report JavaScript function and method blocks and modernization eligibility.

- `class FunctionBlock` — Describe FunctionBlock.
  - Fields: `name: str`, `kind: BlockKind`, `class_name: str | None`, `method_kind: str | None`, `line_start: int`, `column_start: int`, `line_end: int`, `column_end: int`, `static_current: bool`, `static_eligible: bool`, `arrow_current: bool`, `arrow_eligible: bool`, `uses_this_or_super: bool`, `uses_arguments: bool`, `uses_new_target: bool`, `is_async: bool`, `arrow_blockers: tuple[str, ...]`, `recommendation: str`, `source: str`
- `class ConversionResult` — Describe ConversionResult.
  - Fields: `source: str`, `changed: bool`, `transformations: int`
- `class JavaScriptBlockAnalyzer` — Parse and classify function-like blocks in one JavaScript file.
  - `__init__(self, *, path: Path, espree: str | None=None) -> None` — Init  .
  - `resolve_espree(self) -> str` — Resolve espree.
  - `analyze(self) -> tuple[FunctionBlock, ...]` — Analyze.
  - `convert(self, *, direction: ArrowDirection | None=None) -> ConversionResult` — Convert.
  - `normalize(self) -> ConversionResult` — Normalize.
  - `to_arrow(self) -> ConversionResult` — To arrow.
  - `from_arrow(self) -> ConversionResult` — From arrow.
- `class FunctionBlocksFinding` — Describe FunctionBlocksFinding.
  - `severity` = `'warning'`
  - Fields: `rule: str`, `file: str`, `line: int`, `column: int`, `message: str`
- `class FunctionBlocksHeal` — Describe FunctionBlocksHeal.
  - Fields: `rule: str`, `file: str`, `action: str`, `transformations: int`
- `class FunctionBlocksInput` — Describe FunctionBlocksInput.
  - Fields: `root: Path`, `files: tuple[Path, ...]`, `fix: bool`
- `class FunctionBlocksResult` — Describe FunctionBlocksResult.
  - Fields: `files: int`, `findings: tuple[FunctionBlocksFinding, ...]`, `healed: tuple[FunctionBlocksHeal, ...]`
- `scan_function_blocks(*, inputs: FunctionBlocksInput, progress_span: tuple[float, float]=(0.0, 1.0)) -> FunctionBlocksResult` — Scan function blocks.

### `long_lines.py`

Repair Python lines that remain too long after Ruff formatting.

- `class LongLinesAPI` — Stable Python API for long-line repair integration.
  - `resolve_line_length(cls, file_path: Path, ruff_command: tuple[str, ...]=('ruff',)) -> int` — Resolve effective Ruff line length for one Python file.
  - `fix(cls, paths: tuple[Path, ...], settings: Settings | None=None, ruff_report: Path | None=None, *, resolve_line_length: bool=False) -> BatchResult` — Process a deterministic batch for pipeline integration.
  - `parse_ruff_report(path: Path) -> dict[Path, frozenset[int]]` — Load E501 rows from a broad Ruff JSON report.
  - `find_pyproject(file_path: Path) -> Path | None` — Find the nearest applicable ``pyproject.toml``.
  - `discover(paths: tuple[Path, ...]) -> tuple[Path, ...]` — Expand file/directory inputs into deterministic Python paths.
  - `ruff_e501_rows(path: Path, ruff_command: tuple[str, ...]=('ruff',)) -> frozenset[int]` — Collect the rows Ruff reports as E501 for one file.
  - `ruff_e501_rows_many(paths: tuple[Path, ...], ruff_command: tuple[str, ...]=('ruff',)) -> dict[Path, frozenset[int]]` — Collect Ruff E501 rows for many files with one subprocess.
  - `has_long_lines(path: Path, line_length: int) -> bool` — Cheaply test whether a file has a physical line over the width.
  - `transform(source: str, settings: Settings | None=None, path: Path | None=None) -> TextResult` — Transform source without filesystem mutation.
  - `fix_file(path: Path, settings: Settings | None=None) -> Result` — Process one Python file.
- `class RepairSummary` — Totals gathered by one :class:`LongLineRepair` over a lint run.
  - Fields: `repaired: tuple[Path, ...]`, `unresolved: tuple[Path, ...]`, `skipped: tuple[Path, ...]`
- `class LongLineRepair` — Repair residual long lines inside the Ruff stabilization loop.
  - `__init__(self, *, ruff_command: tuple[str, ...]=('ruff',)) -> None` — Create a repair bound to one Ruff launcher.
  - `repair_many(self, *, paths: tuple[Path, ...]) -> None` — Repair Ruff-reported E501 rows across a batch.
  - `summary(self) -> RepairSummary` — Return the totals gathered so far.

### `long_lines_engine.py`

Repair Python lines that remain too long after Ruff formatting.

- `class Constants` — Group module-level constants.
  - `default_line_length` = `79`
  - `max_passes` = `256`
  - `string_prefix_pattern` = `compile_pattern(pattern='(?i)^([rubf]*)([\'\\"]{1,3})')`
  - `word_pattern` = `compile_pattern(pattern='[A-Za-z_]\\w*|"[^"\\n]*"?|\'[^\'\\n]*\'?')`
  - `pragma_pattern` = `compile_pattern(pattern='#\\s*(?:noqa|type:|pyright:|pylint:|flake8:|ruff...`
  - `expression_prefixes` = `('return ', 'yield ', 'assert ', 'raise ')`
  - `condition_prefixes` = `('if ', 'elif ', 'while ')`
  - `directive_names` = `('SPDX-', 'type:', 'pyright:', 'noqa', 'fmt:', 'isort:', 'pragma:', 'nose...`
  - `excluded_parts` = `ExactusCommonTables.DEFAULT_EXCLUDED_DIRS`
  - `triple_quote_length` = `3`
  - `min_split_parts` = `2`
  - `min_docstring_width` = `24`
  - `docstring_block_indent` = `8`
  - `docstring_field_indent` = `4`
  - `min_section_underline` = `3`
  - `min_fstring_text` = `12`
  - `min_chain_dots` = `2`
  - `field_sections` = `frozenset({'Args:', 'Arguments:', 'Parameters:', 'Keyword Args:', 'Other...`
  - `tab_size` = `4`
  - `pyproject_name` = `'pyproject.toml'`
- `class Settings` — Configuration for long-line repair.
  - `line_length` = `Constants.default_line_length`
  - `run_ruff` = `True`
  - `check_only` = `False`
  - `verbose` = `False`
  - `respect_fmt_off` = `True`
  - `show_diff` = `False`
  - `backup` = `False`
  - `reported_e501_lines` = `frozenset()`
  - `ruff_command` = `('ruff',)`
- `class Edit` — One source edit using absolute character offsets.
  - Fields: `start: int`, `end: int`, `replacement: str`, `reason: str`
- `class Result` — Outcome for one processed Python file.
  - `diff` = `''`
  - Fields: `path: Path`, `changed: bool`, `passes: int`, `unresolved_lines: tuple[int, ...]`, `protected_lines: tuple[int, ...]`, `unfixable_lines: tuple[int, ...]`
- `class TextResult` — Outcome for one in-memory Python source transformation.
  - `diff` = `''`
  - Fields: `source: str`, `changed: bool`, `passes: int`, `unresolved_lines: tuple[int, ...]`, `protected_lines: tuple[int, ...]`, `unfixable_lines: tuple[int, ...]`
- `class BatchResult` — Aggregate outcome for a deterministic batch transformation.
  - Fields: `results: tuple[Result, ...]`
  - `changed(self) -> bool` — Return whether at least one file would change.
  - `clean(self) -> bool` — Return whether every processed file has no unresolved lines.
  - `unresolved_count(self) -> int` — Return the total unresolved-line count across the batch.
- `class CandidateScore` — Lexicographic quality score for one candidate source.
  - Fields: `syntax_error: int`, `semantic_change: int`, `protected_change: int`, `e501_count: int`, `overflow: int`, `explicit_continuations: int`, `changed_characters: int`
- `class RuffDiagnostic` — One residual Ruff E501 diagnostic.
  - Fields: `row: int`, `column: int`, `message: str`
- `class ReflowState` — Mutable traversal state while reflowing docstring lines.
  - `section` = `''`
  - `fenced` = `False`
  - `literal_block` = `False`
- `class TokenScan` — Shared token-stream state for f-string split repairs.
  - Fields: `source: str`, `tokens: tuple[TokenInfo, ...]`, `offsets: tuple[int, ...]`, `long_lines: frozenset[int]`
- `class LongLineFixer` — Repair residual E501-style Python lines conservatively.
  - `__init__(self, settings: Settings) -> None` — Initialize the fixer.
  - `transform_text(self, source: str, path: Path | None=None) -> TextResult` — Transform Python source in memory without writing a file.
  - `fix_path(self, path: Path) -> Result` — Fix one Python file using the same in-memory API as callers.
- `class LineTransformer(Protocol)` — Transform one indentation-free physical Python line.

### `main.py`

Run the combined lint exactus and emit the LINTS report bundle.

- `create_parser() -> ArgumentParser` — Return the shared CLI grammar used by execution and completion.
- `parse_args(*, arguments: tuple[str, ...] | None=None) -> Namespace` — Parse args.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Return main.

### `packages_pipeline.py`

Bridge Exactus lints to packaged source-refactor and lint tools.

- `class AllLintsRequest` — Inputs for one all-lints execution from the Exactus tool.
  - `workers` = `None`
  - `progress` = `None`
  - `repair` = `None`
  - `batch_repair` = `None`
  - Fields: `root: Path`, `targets: Sequence[str]`, `excludes: Sequence[str]`, `commands: Mapping[str, tuple[str, ...] | None]`, `arguments: Mapping[str, Sequence[str]]`, `stabilize: bool`, `unsafe_fixes: bool`
- `run_group_final(*, root: Path, dry_run: bool) -> dict[str, JsonValue]` — Run group-final and return its report as JSON-ready data.
- `run_organize(*, paths: Sequence[Path], dry_run: bool, order: Sequence[str]=Constants.default_order) -> dict[str, JsonValue]` — Organize Python and JavaScript class methods in the resolved scope.
- `run_all_lints(*, request: AllLintsRequest) -> tuple[dict[str, JsonValue], list[ToolResult]]` — Run all-lints with Exactus scope, tool arguments and bundle commands.
- `legacy_tools(*, results: Sequence[ToolResult]) -> dict[str, JsonValue]` — Adapt all-lints results to the established Exactus report schema.
- `issue_baselines(*, results: Sequence[ToolResult]) -> tuple[frozenset[tuple[str, int, int, str, str]], frozenset[tuple[str, int, int, str, str]]]` — Return Ruff and BasedPyright issue identities for guarded inference.

### `report.py`

Normalize the LINTS report: summary, scope, findings and metrics.

- `class ReportTables` — Constants of the normalized LINTS report.
  - `id_prefix` = `'LINTS'`
  - `top_limit` = `20`
  - `title_chars` = `120`
  - `ellipsis` = `'…'`
  - `severities` = `('error', 'warning', 'information')`
  - `builtin` = `'built-in'`
  - `custom_prefix` = `'custom_'`
  - `missing` = `'is not installed.'`
  - `file_groups` = `{'custom_compliance': 'python', 'custom_shebang': 'python', 'custom_pytho...`
  - `ranks` = `{name: index for index, name in enumerate(iterable=LintConstants.tool_nam...`
- `relative_path(*, value: str, root: Path) -> str` — Express a linter's file name relative to the project root.
- `linter_status(*, entry: JsonValue) -> str` — Classify how one linter took part in the run.
- `finding_title(*, message: str, rule: str, source: str) -> str` — Return the one-line title of a lint finding.
- `normalized_findings(*, report: Mapping[str, JsonValue], root: Path) -> list[JsonValue]` — Return the findings in the normalized shape, keeping legacy fields.
- `report_data(*, report: Mapping[str, JsonValue], root: Path) -> dict[str, JsonValue]` — Return the LINTS payload with the normalized blocks added.

### `shebang.py`

Exactus Python executable permissions against shebang presence.

- `class Constants` — Executable-permission exactus constants.
  - `executable_bits` = `S_IXUSR | S_IXGRP | S_IXOTH`
  - `readable_bits` = `S_IRUSR | S_IRGRP | S_IROTH`
  - `skipped_dirs` = `ExactusCommonTables.DEFAULT_EXCLUDED_DIRS | frozenset({'bundle'})`
  - `duplicate_copy` = `compile_pattern(pattern=' \\d+(?:\\.[^.]+)?$')`
  - `excluded_reason` = `'excluded by include/exclude rules'`
  - `symlink_reason` = `'symbolic link'`
  - `shebang_limit` = `512`
  - `env_program` = `'env'`
  - `env_value_options` = `frozenset({'-u', '--unset', '-C', '--chdir'})`
  - `env_split_option` = `'-S'`
  - `unknown_interpreter` = `'unknown'`
  - `no_extension` = `'(none)'`
  - `shebangs` = `{'.py': '#!/usr/bin/env python3', '.sh': '#!/bin/sh', '.bash': '#!/usr/bi...`
- `class ShebangSettings` — Auto-heal toggle and the two mismatch heal policies.
  - `heal` = `False`
  - `exec_no_shebang` = `'add-shebang'`
  - `shebang_no_exec` = `'add-exec'`
- `class ShebangFinding` — One executable-permission violation located in a scanned file.
  - `severity` = `'error'`
  - Fields: `rule: str`, `file: str`, `line: int`, `message: str`
- `class ShebangHeal` — One permission/shebang repair applied to a scanned file.
  - Fields: `rule: str`, `file: str`, `action: str`
- `class ShebangInput` — Carry the inputs of one executable-permission exactus run.
  - `settings` = `field(default_factory=ShebangSettings)`
  - `source_files` = `None`
  - Fields: `root: Path`, `includes: tuple[str, ...]`, `excludes: tuple[str, ...]`
- `class ShebangSkip` — One Python file found under the root but not audited.
  - Fields: `target: str`, `reason: str`
- `class FileFacts` — What one inspection learned about a scanned file.
  - `executable` = `False`
  - `interpreter` = `None`
  - `error` = `None`
  - Fields: `file: str`, `extension: str`
- `class ShebangMetrics` — Counters gathered from the files the exactus walked.
  - `files_scanned` = `0`
  - `executable_files` = `0`
  - `files_with_shebang` = `0`
  - `interpreters` = `()`
  - `executable_without_shebang` = `()`
  - `shebang_without_executable` = `()`
  - `extensions` = `()`
- `class ShebangResult` — Outcome of one executable-permission exactus run.
  - `healed` = `()`
  - `includes` = `()`
  - `excludes` = `()`
  - `skipped` = `()`
  - `metrics` = `field(default_factory=ShebangMetrics)`
  - Fields: `files: int`, `findings: tuple[ShebangFinding, ...]`
- `skipped(*, name: str) -> bool` — Report whether a path segment is excluded from the exactus.
- `scan(*, inputs: ShebangInput) -> tuple[list[Path], list[ShebangSkip]]` — Collect owned Python sources and the files left out.
- `python_files(*, inputs: ShebangInput) -> list[Path]` — Collect owned Python sources under the exactus root.
- `first_line(*, path: Path) -> bytes` — Read the start of a file's first line.
- `has_shebang(*, path: Path) -> bool` — Report whether a file's first line is a shebang.
- `interpreter_of(*, line: bytes) -> str | None` — Normalize the interpreter named by a shebang line.
- `inspect_file(*, path: Path, root: Path) -> FileFacts` — Read one file's permission bits and shebang in a single visit.
- `findings_for(*, facts: FileFacts) -> list[ShebangFinding]` — Check one file's executable bits against its shebang.
- `check_file(*, path: Path, root: Path) -> list[ShebangFinding]` — Check one file's executable bits against its shebang.
- `heal_file(*, path: Path, facts: FileFacts, settings: ShebangSettings) -> ShebangHeal | None` — Repair one file's permission/shebang mismatch.
- `collect_metrics(*, facts: list[FileFacts]) -> ShebangMetrics` — Summarize the facts of every scanned file.
- `scan_shebang(*, inputs: ShebangInput, progress_span: tuple[float, float]=(0.0, 1.0)) -> ShebangResult` — Exactus executable permissions for every owned Python source.
- `metrics_data(*, metrics: ShebangMetrics) -> dict[str, JsonValue]` — Return the executable/shebang counters as JSON.

### `string_transform.py`

Source-preserving string dedenting, splitting and f-string formatting.

- `class Constants` — Group module-level constants.
  - `implicit_strings` = `2`
  - `min_split_parts` = `2`
  - `min_line_width` = `20`
  - `max_line_width` = `320`
  - `min_fragment_width` = `4`
  - `strategies` = `('preserve', 'split', 'smart')`
- `class ConversionResult` — Transformed source, syntax tree, number of replacements, and status.
  - Fields: `source: str`, `tree: Module`, `count: int`, `changed: bool`
- `class CallFormatOptions` — Options controlling call expansion inside f-string expressions.
  - `enabled` = `True`
  - `minimum_arguments` = `3`
  - `ruff_executable` = `None`
  - `line_length` = `88`
- `class SplitOptions` — Width discovery and policy settings for literal splitting.
  - `max_line_size` = `None`
  - `line_length` = `None`
  - `ruff_executable` = `None`
  - `ruff_args` = `()`
  - `multiline_strategy` = `'smart'`
  - `split_fstrings` = `True`
  - `split_raw_strings` = `True`
  - `split_bytes` = `True`
  - `preserve_docstrings` = `True`
  - `preserve_comments` = `True`
  - `format_interpolations` = `False`
  - `verify_semantics` = `True`
- `class TransformOptions` — Split options plus call formatting for the combined transform.
  - `format_interpolations` = `True`
  - `call_format` = `None`
- `offsets(*, lines: list[str]) -> list[int]` — Return the cumulative character offset at each line start.
- `position(*, offsets: list[int], point: tuple[int, int]) -> int` — Map a ``(row, column)`` token position to a character offset.
- `flatten(node: expr) -> list[Constant | FormattedValue] | None` — Flatten literals and f-string expressions in evaluation order.
- `signature(*, values: Sequence[expr]) -> tuple[str, list[str]]` — Separate literal text from interpolation syntax in a string body.
- `escape(*, parts: list[Constant | FormattedValue], is_fstring: bool, quote: str) -> list[str] | None` — Escape literal parts and unparse interpolations for one quote style.
- `verified(*, candidate: str, parts: list[Constant | FormattedValue], is_fstring: bool) -> bool` — Check a rendered candidate reproduces the original literal.
- `render(*, parts: list[Constant | FormattedValue]) -> str | None` — Render strings with verified interpolation and literal semantics.
- `implicit_tokens(*, tokens: list[TokenInfo], start: int, end: int, offsets: list[int]) -> bool` — Return whether the span covers multiple adjacent string tokens.
- `select(*, patches: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]` — Keep non-overlapping patches, preferring outer spans first.
- `apply(*, source: str, selected: list[tuple[int, int, str]]) -> str` — Apply patches from last to first so offsets stay valid.
- `merge_dedent(*, result: str, compatible: ImportFrom, offsets: list[int]) -> str` — Extend an existing textwrap import with ``dedent``.
- `insertion_offset(*, updated: Module, updated_lines: list[str]) -> int` — Return the offset after the docstring and future imports.
- `with_dedent_import(*, result: str, updated: Module | None=None) -> str` — Ensure ``from textwrap import dedent`` in transformed source.
- `ruff_call(*, call: str, executable: str, line_length: int) -> str | None` — Format a temporary f-string call using Ruff without editing its source.
- `convert_strings(file: str | Path, tree: Module | None=None, *, write: bool=True, dry_run: bool=False, call_format: CallFormatOptions | None=None) -> ConversionResult` — Rewrite implicit and explicit string concatenations in source.
- `class Skipped` — Location and reason for a conservatively rejected expression.
  - Fields: `line: int`, `column: int`, `reason: str`
- `class SplitResult` — Source and diagnostics after attempting safe literal splits.
  - `skipped` = `()`
  - Fields: `source: str`, `count: int`, `changed: bool`
- `literal_parts(value: str | bytes, width: int) -> list[str] | None` — Split at code-point boundaries, retaining exact escape semantics.
- `offset(lines: list[str], starts: list[int], line: int, column: int) -> int` — Convert UTF-8 AST byte column to a source character offset.
- `atomic_write(path: Path, content: str | bytes) -> None` — Replace a source file atomically, retaining its permission bits.
- `resolve_line_length(*, file: str | Path, line_length: int | None=None, ruff_executable: str | None=None, ruff_args: tuple[str, ...]=()) -> int` — Read Ruff's effective formatter width for the target file.
- `split_strings(file: str | Path, *, tree: Module | None=None, write: bool=True, dry_run: bool=False, options: SplitOptions | None=None) -> SplitResult` — Split provably equivalent oversized literals; report unsafe cases.
- `class TransformResult` — Combined transformation result and rejected-split diagnostics.
  - Fields: `source: str`, `tree: Module`, `count: int`, `changed: bool`, `skipped: tuple[Skipped, ...]`
- `transform_strings(file: str | Path, *, tree: Module | None=None, write: bool=True, dry_run: bool=False, options: TransformOptions | None=None) -> TransformResult` — Run dedent conversion followed by width-limited splitting.

## Dependencies and consumers

- Other packages: [`all_lints`](../../packages/all_lints/DOCS.md), [`argument_parser`](../../packages/argument_parser/DOCS.md), [`group_final`](../../packages/group_final/DOCS.md), [`organize`](../../packages/organize/DOCS.md), [`project_python`](../../packages/project_python/DOCS.md), [`steps`](../../packages/steps/DOCS.md), [`common`](../common/DOCS.md), [`reports`](../reports/DOCS.md)
- Used by: `__main__.py`, `tests/tools/common/test_context_lines.py`, `tests/tools/lints/test_compliance.py`, `tests/tools/lints/test_css_tokens.py`, `tests/tools/lints/test_js_delimiters.py`, `tests/tools/lints/test_js_function_blocks.py`, `tests/tools/lints/test_lints.py`, `tests/tools/lints/test_lints_install.py`, `tests/tools/lints/test_lints_normalizers.py`, `tests/tools/lints/test_lints_report.py`, `tests/tools/lints/test_long_lines.py`, `tests/tools/lints/test_method_contracts.py`, `tests/tools/lints/test_shebang.py`, `tests/tools/lints/test_shebang_metrics.py`, `tests/tools/lints/test_source_cleaner.py`, `tests/tools/lints/test_string_transform.py`, `tests/tools/reports/test_report_snippets.py`

## Tests

Tests live in `exactus/tests/tools/lints/`.

- `test_compliance.py` — LINTS includes the canonical engineering rules and their source evidence. (3 tests)
  - `test_configuration_rules_preserve_findings`
  - `test_engineering_findings_are_part_of_lints`
  - `test_source_rules_preserve_findings`
- `test_css_tokens.py` — The lints CSS token audit resolves one token graph across stylesheets. (25 tests)
  - `test_byte_order_mark_and_crlf`
  - `test_comments_and_strings_hide_nothing`
  - `test_component_directories_are_matched_whole`
  - `test_conforming_layers_pass`
  - `test_context_words_match_case_insensitively`
  - `test_css_wide_keywords_need_no_token`
  - `test_dynamic_references_need_no_definition`
  - `test_each_rule_reports`
  - `test_every_prefix_of_a_sheet_audits`
  - `test_every_rule_has_a_name`
  - `test_finding_locates_declaration`
  - `test_grammar_keywords_stay_literal`
  - `test_important_does_not_hide_a_plain_reference`
  - `test_layer_prefixes`
  - `test_lexer_keeps_text_length_and_lines`
  - `test_long_values_are_clipped_in_messages`
  - `test_malformed_input_degrades_locally`
  - `test_negative_numbers_are_literals`
  - `test_one_line_files_scale`
  - `test_scoped_overrides_are_not_conflicts`
  - `test_strings_are_not_references_or_literals`
  - `test_studio_component_directories_have_one_uniform_contract`
  - `test_token_findings_are_part_of_lints`
  - `test_tokens_resolve_across_files`
  - `test_unreadable_files_are_findings_not_crashes`
- `test_js_delimiters.py` — Behavioral tests for the JavaScript delimiter simplifier. (13 tests)
  - `test_embedded_delimiters_progress_stays_in_its_phase`
  - `test_file_discovery_and_exclusions`
  - `test_file_processing_write_backup_and_unchanged`
  - `test_preserves_object_expression_arrow_inside_call`
  - `test_preserves_required_delimiters`
  - `test_public_stability_corpus`
  - `test_real_node_validation_when_available`
  - `test_rich_metrics_and_execution`
  - `test_scan_heals_files_with_fix`
  - `test_scan_reports_findings_without_writing`
  - `test_scan_reports_unreadable_files`
  - `test_simplifies_supported_constructs`
  - `test_source_and_empty_transformation_metrics`
- `test_js_function_blocks.py` — Behavioral tests for the Python JavaScript block analyzer API. (15 tests)
  - `test_analyze_failures`
  - `test_analyze_public_contract`
  - `test_automatic_normalization_public_api`
  - `test_constructor_validation`
  - `test_conversion_failures`
  - `test_conversion_public_wrappers`
  - `test_embedded_function_blocks_progress_stays_in_its_phase`
  - `test_end_to_end_analysis_and_conversion`
  - `test_end_to_end_parse_failure`
  - `test_end_to_end_reverse_and_parser_fallback`
  - `test_public_block_field_validation`
  - `test_public_espree_resolution_fallbacks`
  - `test_public_node_unavailable_for_analyzer`
  - `test_scan_heals_files_with_fix`
  - `test_scan_reports_findings_without_writing`
- `test_lints.py` — In-process runs of the lints analyzer over generated projects. (24 tests)
  - `test_conventions_progress_is_uniform_and_monotonic`
  - `test_defect_project_lints`
  - `test_fixing_pass_runs_on_copy`
  - `test_inline_style_scan_lints_generated_code_not_embedded_source`
  - `test_javascript_organizer_orders_safe_method_runs`
  - `test_lints_repairs_lines_ruff_cannot_wrap`
  - `test_long_line_repair_needs_fixing_ruff_and_its_switch`
  - `test_long_line_summary_is_written_to_the_status_stream`
  - `test_parse_args_defaults`
  - `test_parse_args_integrated_stage_controls`
  - `test_parse_args_long_line_repair_control`
  - `test_parse_args_rejects_bad_runtime_limits`
  - `test_parse_args_simple_and_runtime_limits`
  - `test_pyproject_configures_integrated_stages`
  - `test_pyproject_configures_simple_and_runtime_limits`
  - `test_pyrefly_stage_span_replaces_infer_label`
  - `test_repo_lints_dry`
  - `test_run_organize_respects_dry_run_and_writes`
  - `test_run_organize_traces_each_file_state`
  - `test_sample_project_lints`
  - `test_simple_progress_budgets_only_all_lints`
  - `test_template_resource_found`
  - `test_uppercase_globals_exempt_generic_binders`
  - `test_weighted_progress_keeps_activity_monotonic`
- `test_lints_install.py` — Installer paths of the lints core, exercised with fake subprocesses. (8 tests)
  - `test_ensure_node_noop_when_npm_present`
  - `test_ensure_node_unsupported_host`
  - `test_ensure_tools_installs_missing`
  - `test_ensure_tools_skips_when_bundle_present`
  - `test_install_failure_raises`
  - `test_node_installer_without_manager`
  - `test_node_installers_run_expected_commands`
  - `test_sudo_prefix_and_refresh_path`
- `test_lints_normalizers.py` — Diagnostic normalizers for every external tool's JSON output. (3 tests)
  - `test_helper_conversions`
  - `test_malformed_payloads_raise`
  - `test_valid_payloads`
- `test_lints_report.py` — LINTS renders result.md and its web view from normalized data. (12 tests)
  - `test_crash_render_shows_na_blocks`
  - `test_empty_findings_state_why_nothing_is_listed`
  - `test_execute_exactus_dry_reports_pyrefly_not_infer`
  - `test_execute_exactus_renders_lints_from_template`
  - `test_execute_exactus_simple_reports_only_all_lints`
  - `test_finding_title`
  - `test_findings_carry_excerpts`
  - `test_golden_result_renders_expected_markdown`
  - `test_paths_and_statuses`
  - `test_report_data_metrics`
  - `test_report_data_normalizes_a_fake_result`
  - `test_versions_and_durations_are_recorded`
- `test_long_lines.py` — The lints long-line repair keeps behavior and converges to a fixpoint. (27 tests)
  - `test_batch_fix_resolves_width_once_per_configuration`
  - `test_batched_e501_rows_report_only_long_files`
  - `test_batched_e501_rows_tolerate_bad_ruff_output`
  - `test_check_only_never_writes`
  - `test_clean_crlf_file_is_untouched`
  - `test_commit_preserves_mode_and_writes_backup`
  - `test_diff_is_attached_when_requested`
  - `test_directive_comments_stay_on_their_line`
  - `test_discover_skips_hidden_and_build_directories`
  - `test_docstring_reflow_keeps_summary_and_fields`
  - `test_encoding_cookie_is_preserved`
  - `test_every_repair_family_preserves_the_ast`
  - `test_fmt_off_regions_are_protected`
  - `test_line_length_falls_back_to_pyproject`
  - `test_line_length_reads_ruff_show_settings`
  - `test_module_source_is_a_fixpoint`
  - `test_parse_ruff_report_keeps_only_e501_rows`
  - `test_parse_ruff_report_rejects_malformed_json`
  - `test_repair_hook_fixes_files_and_summarizes`
  - `test_repair_many_rewrites_long_files_only`
  - `test_ruff_e501_rows_come_from_the_ruff_report`
  - `test_ruff_exempt_lines_are_not_reported`
  - `test_single_file_repair_records_changes_and_skips`
  - `test_split_literals_stay_parenthesized_and_multiline`
  - `test_standalone_comment_wraps`
  - `test_trailing_comment_is_hoisted_above_the_statement`
  - `test_unbreakable_line_is_reported`
- `test_method_contracts.py` — Protect externally inherited instance methods from binding changes. (1 tests)
  - `test_external_override_keeps_instance_binding`
- `test_shebang.py` — The lints shebang check reports and heals permission mismatches. (8 tests)
  - `test_check_file_permission_mismatches`
  - `test_embedded_shebang_progress_stays_in_its_phase`
  - `test_heal_adds_executable_bit_to_shebang_file`
  - `test_heal_drops_exec_bit_instead_of_shebang`
  - `test_heal_drops_shebang_from_non_executable`
  - `test_heal_inserts_shebang_into_executable`
  - `test_heal_is_idempotent`
  - `test_report_only_keeps_findings_and_files`
- `test_shebang_metrics.py` — The lints shebang check counts executables, shebangs and interpreters. (7 tests)
  - `test_interpreter_is_normalized`
  - `test_metrics_ignore_skipped_files`
  - `test_metrics_of_a_mixed_project`
  - `test_metrics_of_an_empty_project`
  - `test_metrics_payload_shape`
  - `test_non_shebang_line_has_no_interpreter`
  - `test_unreadable_file_is_counted_but_not_classified`
- `test_source_cleaner.py` — Behavioral tests for the lints source cleaner. (11 tests)
  - `test_clean_writes_normalized_javascript`
  - `test_collect_excludes_only_root_packages`
  - `test_collect_includes_all_source_suffixes`
  - `test_normalize_covers_jsx_and_cjs`
  - `test_normalize_drops_javascript_blank_lines`
  - `test_normalize_drops_markup_blank_lines`
  - `test_normalize_drops_python_blank_lines_outside_strings`
  - `test_normalize_drops_stylesheet_blank_lines`
  - `test_normalize_keeps_preformatted_markup_blanks`
  - `test_normalize_keeps_template_literal_blank_lines`
  - `test_normalize_python_pyi_and_final_newline`
- `test_string_transform.py` — Behavioral tests for source-preserving string conversion. (35 tests)
  - `test_ast_helpers_and_rejections`
  - `test_combined_dry_run`
  - `test_combined_transform`
  - `test_complex_literals`
  - `test_controls_and_error_paths`
  - `test_docstring`
  - `test_explicit_and_fstrings`
  - `test_format_interpolation_and_idempotence`
  - `test_fstring_call_formatting`
  - `test_fstring_nested_call_formatting`
  - `test_fstring_ruff_staging_with_fake`
  - `test_implicit`
  - `test_import_variations`
  - `test_indented_budget_and_empty_literals`
  - `test_interpolation_already_short_and_already_multiline`
  - `test_interpolation_comment_protection`
  - `test_interpolation_keyword_and_single_argument`
  - `test_interpolation_rejection`
  - `test_literal_helpers_and_atomic_failure`
  - `test_long_fstring`
  - `test_long_literal`
  - `test_more_skip_and_conversion_branches`
  - `test_multiline_bytes_raw_and_docstrings`
  - `test_nested_and_comment_preservation`
  - `test_nested_fstrings_and_debug_are_safe`
  - `test_options_and_error_cases`
  - `test_rejected_candidate_paths`
  - `test_rejections_and_settings`
  - `test_ruff_failure_paths`
  - `test_ruff_line_length_discovery`
  - `test_ruff_unavailable_fallback`
  - `test_source_encoding_and_crlf_roundtrip`
  - `test_unicode_escapes_and_crlf`
  - `test_varied_literal_boundaries`
  - `test_write_failure_and_source_preservation`

<!-- exactus:reference:end -->
