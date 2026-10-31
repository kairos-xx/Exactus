[Home](Home.md) > [Tools](Tools.md) > lints

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/tools/lints/`](../exactus/tools/lints/) | [`exactus/tests/tools/lints/`](../exactus/tests/tools/lints/) | [`DOCS.md`](../exactus/docs/tools/lints/DOCS.md) |

[< Tools-kwargs_typehints](Tools-kwargs_typehints.md) · [Tools index](Tools.md) · [Tools-performance >](Tools-performance.md)
