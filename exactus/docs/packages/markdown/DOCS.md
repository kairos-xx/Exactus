# markdown/

The generic Markdown report engine: renders normalized `result.json`
documents through sandboxed Jinja2 templates driven by declarative
mapping files. Report-independent — nothing here imports `exactus.tools`.

Run standalone with `python -m exactus.markdown`.

## Mapping pipeline

A mapping file declares ordered steps applied in a fixed order:

`resolve → where → sort → unique → slice → each → flatten → pick/omit → join → template`

- Sorting is numeric first, then case-folded text — deterministic.
- Path expressions support nested keys, indices and `$` root anchors.
- Predicates compose the comparison operators with boolean logic.

## Security model

- Jinja2 runs sandboxed — no attribute access outside the data model.
- Templates resolve only inside declared allowed roots; `../` traversal
  and symlink escapes are rejected.
- Undefined access is configurable: strict mode raises typed errors,
  lenient mode renders empty.
- `md_fence` sizes every code fence beyond the longest backtick/tilde
  run inside the fenced content, preventing fence injection.

## Packaging

Templates, mapping data and examples ship via `importlib.resources`, so
the engine renders from inside the zipapp without unpacking.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Render Markdown reports from JSON through templates and mappings. |
| `__main__.py` | Run ``python -m exactus.packages.markdown``. |
| `api.py` | Public entry points for rendering reports. |
| `directives.py` | Base types for mapping directives. |
| `engine.py` | Sandboxed Jinja2 rendering of Markdown templates. |
| `errors.py` | Exceptions raised by the Markdown template engine. |
| `examples/` | Runnable demonstration for `exactus/packages/markdown/`. |
| `filters.py` | Markdown formatting filters for Jinja2 templates. |
| `json_types.py` | JSON value types shared by the exactus tools. |
| `loader.py` | Template loader that never reads files outside its roots. |
| `main.py` | Command-line interface for the Markdown template engine. |
| `mapping.py` | Reshape a source document into a template context. |
| `operators.py` | Comparison operators for mapping predicates. |
| `paths.py` | Resolve JSON path expressions against nested documents. |
| `pipeline.py` | Apply mapping directive steps in their fixed order. |
| `predicates.py` | Evaluate mapping predicates against JSON values. |
| `steps.py` | Concrete mapping directive steps. |

Run it as a module: `python -m exactus.packages.markdown`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `template` |  | type=Path |
| `data` |  | type=Path |
| `-m, --mapping` |  | type=Path |
| `-o, --output` |  | type=Path |
| `--template-root` |  | action='append', type=Path, default=[] |
| `--context-output` |  | type=Path |
| `--lenient` |  | action='store_true' |
| `--validate-only` |  | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Render Markdown reports from JSON through templates and mappings.


### `__main__.py`

Run ``python -m exactus.packages.markdown``.


### `api.py`

Public entry points for rendering reports.

- `load_json(*, value: Path | JsonValue) -> JsonValue` — Read JSON from a path, or pass a value through.
- `render_report(*, result: Path | JsonValue, template: Path, mapping: Path | JsonValue | None=None, extra_roots: tuple[Path, ...]=(), strict: bool=True) -> str` — Render ``result.md`` from ``result.json``.

### `directives.py`

Base types for mapping directives.

- `class MappingHost(Protocol)` — Services a directive step needs from the mapper.
  - `map_value(self, *, spec: JsonValue, current: JsonValue, root: JsonValue) -> JsonValue` — Map a nested specification.
  - `render_name(self, *, name: str, context: dict[str, JsonValue]) -> str` — Render a named template.
- `class Step` — One mapping directive applied to a resolved value.
  - `keys` = `()`
  - `items(*, value: JsonValue, directive: str) -> list[JsonValue]` — Require a list.
  - `members(*, value: JsonValue, directive: str) -> dict[str, JsonValue]` — Require an object.
  - `integer(*, value: JsonValue, directive: str, default: int) -> int` — Require an integer, or return ``default`` for ``None``.
  - `applies(self, *, spec: dict[str, JsonValue]) -> bool` — Report whether the specification activates this step.
  - `apply(self, *, value: JsonValue, spec: dict[str, JsonValue], root: JsonValue, host: MappingHost) -> JsonValue` — Transform ``value`` according to ``spec``.

### `engine.py`

Sandboxed Jinja2 rendering of Markdown templates.

- `class MarkdownEngine` — Render Markdown templates with JSON mapping, loops and includes.
  - `__init__(self, *, roots: tuple[Path, ...], strict: bool=True) -> None` — Configure the sandbox.
  - `context(self, *, source: JsonValue, mapping: dict[str, JsonValue] | None) -> dict[str, JsonValue]` — Build the template context.
  - `render_name(self, *, name: str, context: dict[str, JsonValue]) -> str` — Render a template found under the roots.
  - `render_context(self, *, template: Path, context: dict[str, JsonValue]) -> str` — Render a template file with a prepared context.
  - `render(self, *, template: Path, source: JsonValue, mapping: dict[str, JsonValue] | None) -> str` — Map ``source`` and render ``template``.

### `errors.py`

Exceptions raised by the Markdown template engine.

- `class TemplateEngineError` — Base error for template loading, rendering, and validation.
- `class MappingError` — Raised when a mapping specification is invalid.

### `examples/__init__.py`

Examples for the markdown package.


### `examples/__main__.py`

Run the markdown example with the project virtual environment.


### `examples/run.py`

Render the bundled example and check it against the golden output.

- `main() -> int` — Render ``template.md`` and compare it with ``expected.md``.

### `filters.py`

Markdown formatting filters for Jinja2 templates.

- `class Constants` — Filter constants.
  - `escape` = `compile_pattern(pattern='([\\\\`*_{}\\[\\]<>#+.!|])')`
  - `newline` = `compile_pattern(pattern='\\r\\n|\\r|\\n')`
  - `fence_marker` = `compile_pattern(pattern='^[ \\t]*(?P<marker>~{3,}|`{3,})', flags=MULTILINE)`
- `class MarkdownFilters` — Filters exposed to templates.
  - `escape(cls, value: JsonValue) -> str` — Backslash-escape Markdown control characters.
  - `cell(cls, value: JsonValue) -> str` — Escape a value for one single-line table cell.
  - `code(cls, value: JsonValue) -> str` — Wrap a value in an inline code span.
  - `codeblock(cls, value: JsonValue, language: str='') -> str` — Wrap a value in a fenced code block.
  - `fence(cls, value: JsonValue, language: str='') -> str` — Wrap a value in a fence longer than any marker inside it.
  - `bullets(cls, value: JsonValue, path: str | None=None) -> str` — Render a bullet list.
  - `numbered(cls, value: JsonValue, path: str | None=None) -> str` — Render a numbered list.
  - `table(cls, value: JsonValue, *columns: str) -> str` — Render a Markdown table (Jinja2 positional entry point).
  - `render_table(cls, *, value: JsonValue, columns: tuple[str, ...]) -> str` — Render a Markdown table.
  - `register(cls, *, env: Environment) -> None` — Install every filter on a Jinja2 environment.
  - `text(value: JsonValue) -> str` — Stringify a value for inclusion in Markdown.
  - `to_json(value: JsonValue, indent: int=2) -> str` — Serialize to indented JSON.
  - `compact_json(value: JsonValue) -> str` — Serialize to compact JSON.

### `json_types.py`

JSON value types shared by the exactus tools.

- `class JsonDict` — Dictionary with a formatted JSON representation.
  - `tojson(self) -> str` — Formatted JSON serialization of this dictionary.

### `loader.py`

Template loader that never reads files outside its roots.

- `class RootBoundLoader` — File-system loader that refuses symlinks leaving the roots.
  - `__init__(self, *, roots: tuple[Path, ...]) -> None` — Remember the resolved roots.
  - `get_source(self, environment: Environment, template: str) -> tuple[str, str, Callable[[], bool]]` — Load a template, rejecting files that resolve outside a root.

### `main.py`

Command-line interface for the Markdown template engine.

- `class Arguments` — Typed command-line arguments.
  - Fields: `template: Path`, `data: Path`, `mapping: Path | None`, `output: Path | None`, `template_root: list[Path]`, `context_output: Path | None`, `lenient: bool`, `validate_only: bool`
- `class Streams` — Resolve the process streams when they are used, not at import.
  - `stdout() -> TextIO` — Return the current standard output stream.
  - `stderr() -> TextIO` — Return the current standard error stream.
- `class Cli` — Run the template engine from the command line.
  - `run(cls, *, argv: Sequence[str] | None=None, out: TextIO | None=None, err: TextIO | None=None) -> int` — Render according to ``argv``.
  - `parser() -> ArgumentParser` — Build the argument parser.
- `main(*, argv: Sequence[str] | None=None, out: TextIO | None=None, err: TextIO | None=None) -> int` — Run the command-line interface.

### `mapping.py`

Reshape a source document into a template context.

- `class Renderer(Protocol)` — Render a named template with a context.
- `class Mapper` — Evaluate mapping specifications.
  - `__init__(self, *, renderer: Renderer) -> None` — Store the template renderer.
  - `render_name(self, *, name: str, context: dict[str, JsonValue]) -> str` — Render a named template through the configured renderer.
  - `context(self, *, source: JsonValue, mapping: dict[str, JsonValue] | None) -> dict[str, JsonValue]` — Build the template context.
  - `map_value(self, *, spec: JsonValue, current: JsonValue, root: JsonValue) -> JsonValue` — Map ``spec`` and discard the found flag.
  - `map(self, *, spec: JsonValue, current: JsonValue, root: JsonValue) -> Lookup` — Evaluate one mapping specification.

### `operators.py`

Comparison operators for mapping predicates.

- `class Operator(Protocol)` — Keyword-only comparison between a resolved value and an operand.
- `class Constants` — Predicate constants.
  - `empty_values` = `(None, '', [], {})`
  - `type_names` = `{'str': (str,), 'int': (int,), 'float': (float,), 'bool': (bool,), 'list'...`
- `class Operators` — Comparison operators keyed by their mapping-spec name.
  - `not_empty(cls, *, actual: JsonValue, expected: JsonValue) -> bool` — Negate :meth:`empty`.
  - `not_in(cls, *, actual: JsonValue, expected: JsonValue) -> bool` — Negate :meth:`in_` for container operands.
  - `gt(cls, *, actual: JsonValue, expected: JsonValue) -> bool` — Test ``actual > expected`` for numbers or strings.
  - `gte(cls, *, actual: JsonValue, expected: JsonValue) -> bool` — Test ``actual >= expected`` for numbers or strings.
  - `lt(cls, *, actual: JsonValue, expected: JsonValue) -> bool` — Test ``actual < expected`` for numbers or strings.
  - `lte(cls, *, actual: JsonValue, expected: JsonValue) -> bool` — Test ``actual <= expected`` for numbers or strings.
  - `table(cls) -> dict[str, Operator]` — Map specification names to operator callables.
  - `truthy(*, actual: JsonValue, expected: JsonValue) -> bool` — Test ``bool(actual)``.
  - `falsy(*, actual: JsonValue, expected: JsonValue) -> bool` — Test ``not actual``.
  - `empty(*, actual: JsonValue, expected: JsonValue) -> bool` — Test for null, empty string, empty list or empty dict.
  - `eq(*, actual: JsonValue, expected: JsonValue) -> bool` — Test equality.
  - `ne(*, actual: JsonValue, expected: JsonValue) -> bool` — Test inequality.
  - `contains(*, actual: JsonValue, expected: JsonValue) -> bool` — Test that a container holds ``expected``.
  - `in_(*, actual: JsonValue, expected: JsonValue) -> bool` — Test that ``actual`` is a member of ``expected``.
  - `starts_with(*, actual: JsonValue, expected: JsonValue) -> bool` — Test a string prefix.
  - `ends_with(*, actual: JsonValue, expected: JsonValue) -> bool` — Test a string suffix.
  - `regex(*, actual: JsonValue, expected: JsonValue) -> bool` — Test a regular-expression search.
  - `type_is(*, actual: JsonValue, expected: JsonValue) -> bool` — Test the JSON type name of the value.

### `paths.py`

Resolve JSON path expressions against nested documents.

- `class Constants` — Path grammar constants.
  - `root_marker` = `'$'`
  - `root_anchor` = `'$.'`
  - `current_paths` = `frozenset({'', '.'})`
  - `token` = `compile_pattern(pattern='([^.\\[\\]]+)|\\[(\\d+)\\]')`
- `class Lookup` — Outcome of resolving a path.
  - `value` = `None`
  - Fields: `found: bool`
  - `hit(cls: type[Self], *, value: JsonValue) -> Self` — Build a successful lookup.
  - `miss(cls: type[Self]) -> Self` — Build a failed lookup.
- `class PathResolver` — Walk dict keys and list indexes described by a path string.
  - `resolve(cls, *, current: JsonValue, path: str, root: JsonValue) -> Lookup` — Resolve ``path`` from ``current`` or from ``root``.

### `pipeline.py`

Apply mapping directive steps in their fixed order.

- `class Pipeline` — Run every activated directive step, in order.
  - `__init__(self) -> None` — Build the ordered step list.
  - `run(self, *, value: JsonValue, spec: dict[str, JsonValue], root: JsonValue, host: MappingHost) -> JsonValue` — Apply the steps that ``spec`` activates.

### `predicates.py`

Evaluate mapping predicates against JSON values.

- `class Constants` — Predicate constants.
  - `presence_ops` = `frozenset({'exists', 'missing'})`
- `class Predicates` — Evaluate predicate specifications.
  - `evaluate(cls, *, spec: JsonValue, current: JsonValue, root: JsonValue) -> bool` — Evaluate one predicate specification.

### `steps.py`

Concrete mapping directive steps.

- `class WhereStep` — ``$where``: keep list items matching a predicate.
  - `keys` = `('$where',)`
  - `apply(self, *, value: JsonValue, spec: dict[str, JsonValue], root: JsonValue, host: MappingHost) -> JsonValue` — Filter a list.
- `class SortStep` — ``$sort_by`` / ``$reverse``: order a list by a path.
  - `keys` = `('$sort_by',)`
  - `apply(self, *, value: JsonValue, spec: dict[str, JsonValue], root: JsonValue, host: MappingHost) -> JsonValue` — Sort a list.
- `class UniqueStep` — ``$unique`` / ``$unique_by``: drop duplicate list items.
  - `keys` = `('$unique', '$unique_by')`
  - `applies(self, *, spec: dict[str, JsonValue]) -> bool` — Report whether deduplication was requested.
  - `apply(self, *, value: JsonValue, spec: dict[str, JsonValue], root: JsonValue, host: MappingHost) -> JsonValue` — Deduplicate a list, keeping first occurrences.
- `class SliceStep` — ``$offset`` / ``$limit``: window a list.
  - `keys` = `('$offset', '$limit')`
  - `apply(self, *, value: JsonValue, spec: dict[str, JsonValue], root: JsonValue, host: MappingHost) -> JsonValue` — Slice a list.
- `class EachStep` — ``$each``: map every list item through a nested specification.
  - `keys` = `('$each',)`
  - `apply(self, *, value: JsonValue, spec: dict[str, JsonValue], root: JsonValue, host: MappingHost) -> JsonValue` — Project each item.
- `class FlattenStep` — ``$flatten``: splice nested lists one level.
  - `keys` = `('$flatten',)`
  - `applies(self, *, spec: dict[str, JsonValue]) -> bool` — Report whether flattening was requested.
  - `apply(self, *, value: JsonValue, spec: dict[str, JsonValue], root: JsonValue, host: MappingHost) -> JsonValue` — Flatten one level.
- `class PickStep` — ``$pick``: keep only the named keys of an object.
  - `keys` = `('$pick',)`
  - `apply(self, *, value: JsonValue, spec: dict[str, JsonValue], root: JsonValue, host: MappingHost) -> JsonValue` — Select keys.
- `class OmitStep` — ``$omit``: drop the named keys of an object.
  - `keys` = `('$omit',)`
  - `apply(self, *, value: JsonValue, spec: dict[str, JsonValue], root: JsonValue, host: MappingHost) -> JsonValue` — Remove keys.
- `class JoinStep` — ``$join``: join list items into one string.
  - `keys` = `('$join',)`
  - `apply(self, *, value: JsonValue, spec: dict[str, JsonValue], root: JsonValue, host: MappingHost) -> JsonValue` — Join items.
- `class TemplateStep` — ``$template``: render a named template with the value.
  - `keys` = `('$template',)`
  - `apply(self, *, value: JsonValue, spec: dict[str, JsonValue], root: JsonValue, host: MappingHost) -> JsonValue` — Render the template once, or once per list item.

## Examples

Runnable demonstration for `exactus/packages/markdown/`.

Render the bundled example and check it against the golden output.

```bash
python -m exactus.packages.markdown.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/assets/README.md`, `examples/assets/data.json`, `examples/assets/expected.md`, `examples/assets/mapping.json`, `examples/assets/template.md`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md)
- Used by: `tests/packages/markdown/test_cli.py`, `tests/packages/markdown/test_engine.py`, `tests/packages/markdown/test_errors.py`, `tests/packages/markdown/test_examples.py`, `tests/packages/markdown/test_filters.py`, `tests/packages/markdown/test_mapping.py`, `tests/packages/markdown/test_operators.py`, `tests/packages/markdown/test_paths.py`, `tests/packages/markdown/test_predicates.py`, `tests/tools/common/test_report_templates.py`, `tests/tools/reports/test_report_render.py`, `tools/common/execution.py`, `tools/reports/render.py`

## Tests

Tests live in `exactus/tests/packages/markdown/`.

- `test_cli.py` — The command line renders templates and reports failures with exit 2. (7 tests)
  - `test_bad_json_and_non_object_mapping_exit_two`
  - `test_default_streams_are_resolved_at_call_time`
  - `test_errors_exit_two`
  - `test_prints_to_stdout_by_default`
  - `test_template_root_allows_includes_from_other_directories`
  - `test_validate_only_and_context_output`
  - `test_writes_output_file`
- `test_engine.py` — The engine renders sandboxed Jinja2 templates from mapped JSON. (15 tests)
  - `test_bad_json_files_are_wrapped`
  - `test_inheritance_includes_and_filters`
  - `test_load_json_passes_values_through`
  - `test_mapping_feeds_the_template`
  - `test_render_report_accepts_paths_and_objects`
  - `test_render_report_extra_roots`
  - `test_render_report_rejects_non_object_mapping`
  - `test_render_report_rejects_non_object_mapping_file`
  - `test_runtime_errors_are_wrapped`
  - `test_same_named_template_in_second_root_is_rendered`
  - `test_sandbox_blocks_unsafe_attribute_access`
  - `test_strict_undefined_raises_and_lenient_renders`
  - `test_symlink_include_outside_roots_is_refused`
  - `test_syntax_errors_are_wrapped`
  - `test_template_outside_roots_is_rejected`
- `test_errors.py` — The engine exposes one exception tree rooted at TemplateEngineError. (1 tests)
  - `test_mapping_error_is_a_template_engine_error`
- `test_example_run.py` — Cover the bundled ``markdown`` example entry point. (2 tests)
  - `test_example_module_reports_a_golden_mismatch`
  - `test_example_module_runs_as_a_script`
- `test_examples.py` — The generic engine example renders to its checked-in expected output. (2 tests)
  - `test_generic_example_matches_golden`
  - `test_run_script_returns_zero`
- `test_filters.py` — Markdown filters format values for templates. (9 tests)
  - `test_cell_escapes_pipes_and_every_line_break`
  - `test_codeblock_bullets_numbered`
  - `test_json_filters_and_registration`
  - `test_table_defaults_and_empty`
  - `test_table_filter_accepts_positional_columns_from_templates`
  - `test_table_normalizes_crlf_cells_and_pipe_headers`
  - `test_table_preserves_dunder_paths_and_titles`
  - `test_table_with_columns_escapes_cells`
  - `test_text_escape_and_code`
- `test_mapping.py` — Mapping specs reshape a source document into a template context. (9 tests)
  - `test_context_exposes_source_and_data`
  - `test_default_required_and_default_on_null`
  - `test_paths_literals_and_structures`
  - `test_sort_is_numeric_and_text_is_case_insensitive`
  - `test_template_and_template_each`
  - `test_unique_slice_flatten_pick_omit_join`
  - `test_when_coalesce_and_merge`
  - `test_where_sort_each_pipeline`
  - `test_wrong_value_kinds_name_the_directive`
- `test_operators.py` — Operator edge cases for non-matching operand types. (5 tests)
  - `test_contains_on_strings_and_scalars`
  - `test_in_on_strings_and_scalars`
  - `test_ordering_rejects_bool_and_mixed_types`
  - `test_regex_requires_strings`
  - `test_type_is_distinguishes_bool_from_int`
- `test_paths.py` — JSON paths resolve against a current value or the document root. (5 tests)
  - `test_dollar_returns_root_and_anchor_leaves_current`
  - `test_empty_and_dot_return_current`
  - `test_missing_key_index_and_type_mismatch_are_misses`
  - `test_nested_and_indexed_path`
  - `test_null_value_is_found`
- `test_predicates.py` — Predicate specs filter list items and drive conditional mapping. (6 tests)
  - `test_comparison_operators`
  - `test_invalid_specs_raise_mapping_error`
  - `test_logic_and_shorthand`
  - `test_membership_and_string_operators`
  - `test_presence_operators_and_missing_paths`
  - `test_truthiness_and_type_operators`

<!-- exactus:reference:end -->
