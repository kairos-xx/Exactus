# `exactus/markdown/`

Jinja2 Markdown template engine: renders Markdown reports from JSON
through templates and mappings. The inventory below documents every
direct file and child directory.

The package is exactus-agnostic: it imports nothing from the exactus report
machinery. The exactus report templates live in
`exactus/tools/common/templates/markdown/`.

## Directory contents

### Files

#### `__init__.py`

Package entry point that re-exports the public API. Public API:
`MappingError` — Raised when a mapping specification is invalid.;
`MarkdownEngine` — Sandboxed Jinja2 engine rendering Markdown templates.;
`TemplateEngineError` — Base error for template loading, rendering, and
validation.; `render_report` — Render Markdown from a result document.

#### `errors.py`

Exceptions raised by the Markdown template engine, rooted at
`TemplateEngineError` so callers can catch every engine failure with one
clause. Public API: `TemplateEngineError` — Base error for template
loading, rendering, and validation.; `MappingError` — Raised when a
mapping specification is invalid.

#### `paths.py`

Resolve JSON path expressions against nested documents. Supports dotted
keys, list indexes, and anchoring at the document root. Public API:
`Lookup` — Frozen dataclass outcome of resolving a path.; `PathResolver`
— Static resolver walking dict keys and list indexes described by a path
string.

#### `operators.py`

Comparison operators for mapping predicates, keyed by their
mapping-spec name. Public API: `Operator` — Protocol for keyword-only
comparison callables.; `Constants` — Operator constants.; `Operators` —
Comparison operators keyed by their mapping-spec name.

#### `predicates.py`

Evaluate mapping predicates against JSON values: boolean literals,
`$and`/`$or`/`$not` combinators, `$path`/`$op`/`$value` comparisons, and
equality shorthand objects. Public API: `Constants` — Predicate
constants.; `Predicates` — Evaluate predicate specifications.

#### `directives.py`

Base types for mapping directives. Public API: `MappingHost` — Protocol
for services a directive step needs from the mapper.; `Step` — Abstract
base of one mapping directive applied to a resolved value.

#### `steps.py`

Concrete mapping directive steps. Public API: `WhereStep` — `$where`
filter.; `SortStep` — `$sort_by`/`$reverse` ordering, numbers first.;
`UniqueStep` — `$unique`/`$unique_by` deduplication.; `SliceStep` —
`$offset`/`$limit` window.; `EachStep` — `$each` projection.;
`FlattenStep` — `$flatten` one level.; `PickStep` — `$pick` keys.;
`OmitStep` — `$omit` keys.; `JoinStep` — `$join` into a string.;
`TemplateStep` — `$template` rendering.

#### `pipeline.py`

Apply mapping directive steps in their fixed order. Public API:
`Pipeline` — Run every activated directive step, in order.

#### `mapping.py`

Reshape a source document into a template context. Public API:
`Renderer` — Protocol rendering a named template with a context.;
`Mapper` — Evaluate mapping specifications.

#### `filters.py`

Markdown formatting filters for Jinja2 templates; filter callbacks take
positional arguments because Jinja2 calls them positionally. Public API:
`Constants` — Filter constants.; `MarkdownFilters` — Filters exposed to
templates (`text`, `escape`, `code`, `codeblock`, `bullets`, `numbered`,
`cell`, `table`, `render_table`, `to_json`, `compact_json`, `register`).

#### `engine.py`

Sandboxed Jinja2 rendering of Markdown templates: template roots, strict
or lenient undefined handling, and every Jinja2 failure wrapped in
`TemplateEngineError`. Public API: `MarkdownEngine` — Render Markdown
templates with JSON mapping, loops and includes.

#### `loader.py`

Template loader confined to the configured roots: files whose resolved
path leaves every root (for example through a symlink) are refused as
missing. Public API: `RootBoundLoader` — File-system loader that
refuses symlinks leaving the roots.

#### `api.py`

Public entry points for rendering reports. Public API: `load_json` —
Read JSON from a path, or pass a value through.; `render_report` —
Render `result.md` from `result.json` with an optional mapping.

#### `main.py`

Command-line interface for the Markdown template engine
(`python -m exactus.packages.markdown TEMPLATE DATA [-m MAPPING] [-o OUTPUT]`).
Exit code 2 with `error: <message>` on the error stream (stderr, resolved
at call time) for load or render failures; output and error streams are
injectable for tests. Public API: `Arguments` — Typed command-line arguments.;
`Cli` — Run the template engine from the command line.; `main` — Run
the command-line interface.

#### `__main__.py`

Module entry point for `python -m exactus.packages.markdown`; exits with the code
returned by `main.main`.

### Directories

#### `examples/`

Small generic example: data, mapping, template and golden output.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Render Markdown reports from JSON through templates and mappings.
- [`__main__.py`](__main__.py) — Run ``python -m exactus.packages.markdown``.
- [`api.py`](api.py) — Public entry points for rendering reports.
- [`directives.py`](directives.py) — Base types for mapping directives.
- [`engine.py`](engine.py) — Sandboxed Jinja2 rendering of Markdown templates.
- [`errors.py`](errors.py) — Exceptions raised by the Markdown template engine.
- [`filters.py`](filters.py) — Markdown formatting filters for Jinja2 templates.
- [`json_types.py`](json_types.py) — JSON value types shared by the exactus tools.
- [`loader.py`](loader.py) — Template loader that never reads files outside its roots.
- [`main.py`](main.py) — Command-line interface for the Markdown template engine.
- [`mapping.py`](mapping.py) — Reshape a source document into a template context.
- [`operators.py`](operators.py) — Comparison operators for mapping predicates.
- [`paths.py`](paths.py) — Resolve JSON path expressions against nested documents.
- [`pipeline.py`](pipeline.py) — Apply mapping directive steps in their fixed order.
- [`predicates.py`](predicates.py) — Evaluate mapping predicates against JSON values.
- [`steps.py`](steps.py) — Concrete mapping directive steps.

### Subdirectories

- [`examples/`](examples/README.md) — Small generic example for the Markdown engine, independent of any exactus report. The inventory below documents every direct file and child directory.

<!-- exactus:inventory:end -->


