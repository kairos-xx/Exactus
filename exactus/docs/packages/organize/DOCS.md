# `exactus.packages.organize`

`exactus.packages.organize` reorders direct methods in Python classes into a deterministic
semantic layout while preserving the original method source text. It uses the
Python AST only to discover and classify definitions; it does **not** regenerate
methods with `ast.unparse()`.

## Canonical order

Every method is classified into one of eleven named categories. The default
category order is `DEFAULT_ORDER`:

1. `new` — `__new__`
2. `init` — `__init__`
3. `classmethod` — public `@classmethod` methods
4. `property` — public property families
5. `staticmethod` — public `@staticmethod` methods
6. `method` — public instance methods
7. `magic` — other magic/dunder methods
8. `private_classmethod` — private `@classmethod` methods
9. `private_property` — private property families
10. `private_staticmethod` — private `@staticmethod` methods
11. `private_method` — private instance methods

Ordering is stable inside a category. Property families retain their original
family order, while recognized accessors are ordered getter, setter, deleter.

### Custom order

Any complete permutation of the eleven category names is a valid order. It can
be supplied per call (`order=` on every API), on the CLI (`--order`), or through
`[tool.organize]` in the nearest `pyproject.toml`:

```toml
[tool.organize]
order = [
    "new",
    "init",
    "classmethod",
    "property",
    "staticmethod",
    "method",
    "magic",
    "private_classmethod",
    "private_property",
    "private_staticmethod",
    "private_method",
]
```

`configured_order()` walks up from a start path (default: the working
directory) and returns the first `pyproject.toml`'s `[tool.organize] order`,
or `DEFAULT_ORDER` when the section is absent. `validate_order()` rejects
incomplete or misspelled permutations with `ValueError`; the CLI surfaces the
same condition as a parser error.

## Preservation contract

The implementation moves original source slices instead of reconstructing
methods. Consequently it preserves:

- decorators, decorator ordering, arguments, and multiline formatting;
- `def` versus `async def`;
- positional-only and keyword-only signature markers;
- argument annotations, return annotations, defaults, and generic expressions;
- method docstrings and all method-body comments/formatting;
- comments directly adjacent to the first decorator or definition line.

A comment block directly touching a method is treated as documentation for that
method and moves with it. A comment separated from the method by a blank line is
left anchored at its original slot.

Module and class docstrings are non-method statements and are never moved.
Assignments, nested class declarations, conditionals, and other non-method
class-body statements are also left in their original slots.

## Decorator classification

Arbitrary decorators are preserved verbatim. The organizer only needs semantic
knowledge of decorators that determine method binding or property membership.
It recognizes simple and qualified terminal names such as:

```python
@classmethod
@builtins.classmethod
@staticmethod
@namespace.staticmethod
@property
@value.getter
@value.setter
@value.deleter
```

An arbitrary alias such as `@cm` cannot safely be inferred to mean
`@classmethod` without resolving imports, so it is preserved but treated as an
ordinary decorator.

## API

### File-backed operation

```python
from pathlib import Path

from exactus.packages.organize.core import PythonClassMethodReorderer

reorderer: PythonClassMethodReorderer = PythonClassMethodReorderer(
    path=Path("module.py"),
)

preview: str = reorderer.reorder()
changed: bool = reorderer.write()
```

`reorder()` returns transformed text without modifying the file. `write()`
rewrites the file only when the output differs and returns whether a change was
made. `measure()` returns a `ReorderResult` (reordered text plus metrics)
without writing.

### In-memory operation

```python
from exactus.packages.organize.core import PythonClassMethodReorderer

source: str = """class Example:\n    ...\n"""
result: str = PythonClassMethodReorderer.reorder_source(source=source)
```

Invalid Python raises `SyntaxError`; no partial rewrite is attempted.

### Metrics

`reorder_source_detailed()` returns a `ReorderResult` pairing the reordered
source with a `ReorderMetrics` snapshot:

```python
result = PythonClassMethodReorderer.reorder_source_detailed(source=source)
result.source                 # reordered text
result.changed                # whether any method moved
result.metrics.classes_seen
result.metrics.classes_reordered
result.metrics.methods_seen
result.metrics.methods_moved
result.metrics.lines_moved
```

The Exactus lints pipeline consumes these metrics: `run_organize` aggregates
them across the resolved Python scope and stores the totals under the
`"organize"` key of `LINTS.json` (`files`, `changed`, `skipped`,
`classes_seen`, `classes_reordered`, `methods_seen`, `methods_moved`,
`lines_moved`).

## CLI

```text
python -m exactus.packages.organize [options] <PATH> [PATH ...]
```

Each `PATH` may be a Python file, a directory (searched recursively for
`*.py`), or a glob pattern (`exactus/packages/**/*.py`). Options:

- `--include GLOB` — keep only sources matching the glob; repeatable.
- `--exclude GLOB` — skip sources matching the glob; repeatable.
- `--dry` / `--dry-run` — report `would update` lines without writing.
- `--order CATEGORIES` — comma-separated category list overriding
  `[tool.organize] order`.

Each file reports `updated`, `unchanged`, `would update`, or `error` with its
moved-method/class/line metrics, followed by an aggregate summary line. The
exit status is `0` on success and `1` when no paths resolved or a file failed;
an invalid `--order` or `[tool.organize] order` is a parser error (`2`).

## Example

All three forms execute the same example, which prints the before/after source
and the collected metrics:

```text
python exactus/packages/organize/examples/run.py
python exactus/packages/organize/examples
python -m exactus.packages.organize.examples
```

Run from the project root so `exactus` is importable.

## Safety and scope

Only direct methods in a class are candidates for reordering. Nested classes
that are direct class-body declarations are processed independently. Classes
defined inside functions or methods are intentionally not traversed, because
they are runtime-local implementation details rather than structural members of
the containing class/module.

Reordering method definitions can inherently change class-definition-time
behavior when decorators or class-body expressions depend on definition order.
The organizer preserves source exactly but cannot guarantee semantic equivalence
for code that intentionally relies on the original method-definition order.

## Idempotence

Canonical output is idempotent. Running the organizer repeatedly produces the
same bytes after the first successful organization.

## Tests and coverage

Run:

```text
PYTHONPATH=. python3.13 -m pytest -q \
    --cov=exactus.packages.organize.core \
    --cov-report=term-missing \
    --cov-fail-under=90
```

The suite covers every ordering category, source preservation, complex
decorators and type annotations, property families, qualified decorators,
comment ownership, nested classes, runtime-local classes, idempotence, file
writes, unchanged files, invalid syntax, reorder metrics, custom category
orders, `[tool.organize]` resolution, and the CLI (dry run, include/exclude
globs, glob expansion, order overrides, and usage errors).

## JavaScript organization

`exactus.packages.organize` also organizes JavaScript class methods in `.js`, `.jsx`,
`.mjs`, and `.cjs` files. JavaScript parsing uses Node.js and Espree. Espree is
resolved from the source project first, then an installed ESLint, then global
npm modules.

The canonical JavaScript method order is:

1. constructor;
2. public static getters/setters;
3. public static methods;
4. public getters/setters;
5. public instance methods;
6. private static getters/setters;
7. private static methods;
8. private getters/setters;
9. private instance methods.

Getter/setter families remain adjacent with the getter before the setter.
Ordering is stable within each category.

The shared Node.js script `exactus/packages/organize/js/class_organizer.js` reads a JSON
payload on stdin (`{file, espree, action}`) and dispatches on `action`:

- `organize` (default) — reorder class methods and report metrics.
- `analyze` — emit the function-block inventory used by
  `exactus.tools.lints.js_function_blocks`.
- `convert` — apply arrow/static transformations (`direction`:
  `to_arrow`, `from_arrow`, or `normalize`).

JavaScript class fields, static blocks, computed method names, and other
executable class members are barriers. Methods are only reordered inside
contiguous safe method runs. This preserves field-initializer and computed-key
evaluation order. Method source text and directly attached comments are moved
verbatim rather than regenerated.

The standalone API is `JavaScriptClassMethodReorderer(path=...)`, with
`measure()`, `reorder()`, and `write()` matching the file-backed Python API.
The normal CLI discovers both Python and JavaScript sources recursively.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Public API for Python and JavaScript class method organization. |
| `__main__.py` | Run Python and JavaScript class method organization. |
| `core.py` | Reorder Python class methods while preserving original source text. |
| `examples/` | Examples for the organize package. |
| `javascript.py` | Source-preserving JavaScript class-method organization. |
| `js/` | Parse the source as a module, falling back to script mode. |

Run it as a module: `python -m exactus.packages.organize`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `paths` | Python/JavaScript files, directories, or glob patterns to organize. | nargs='*' |
| `--include` | Only organize sources matching GLOB; repeatable. | default=[], action='append' |
| `--exclude` | Skip sources matching GLOB; repeatable. | default=[], action='append' |
| `--dry, --dry-run` | Report the changes organize would make without writing. | action='store_true' |
| `--order` | Comma-separated category order overriding [tool.organize] order in pyproject.toml. |  |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `core.py`

Reorder Python class methods while preserving original source text.

- `class Constants` — Group module-level constants.
  - `min_reorder_methods` = `2`
  - `min_dunder_name_length` = `5`
  - `supported_suffixes` = `frozenset({'.py', '.js', '.jsx', '.mjs', '.cjs'})`
  - `default_order` = `('new', 'init', 'classmethod', 'property', 'staticmethod', 'method'...`
- `class ReorderMetrics` — Metrics describing one reorder operation.
  - Fields: `classes_reordered: int`, `classes_seen: int`, `lines_moved: int`, `methods_moved: int`, `methods_seen: int`
- `class ReorderResult` — Outcome of reordering one Python source.
  - Fields: `metrics: ReorderMetrics`, `source: str`
  - `changed() -> bool` — Whether the reorder moved at least one method.
- `validate_order(*, order: Sequence[str]) -> tuple[str, ...]` — Validate and normalize a method-category order.
- `configured_order(*, start: Path | None=None) -> tuple[str, ...]` — Resolve ``[tool.organize] order`` from the nearest ``pyproject.toml``.
- `class PythonClassMethodReorderer` — Reorder direct class methods using a stable, source-preserving policy.
  - `reorder_source(*, source: str, order: Sequence[str]=Constants.default_order) -> str` — Reorder all classes in Python source.
  - `reorder_source_detailed(*, source: str, order: Sequence[str]=Constants.default_order) -> ReorderResult` — Reorder all classes in Python source and collect metrics.
  - `reorder() -> str` — Return reordered file content without writing it.
  - `measure() -> ReorderResult` — Return the reorder outcome with metrics, without writing.
  - `write() -> bool` — Reorder the file in place when a change is required.
- `main(*, arguments: Sequence[str] | None=None) -> int` — Organize class methods in Python and JavaScript files.

### `javascript.py`

Source-preserving JavaScript class-method organization.

- `class Constants` — Group module-level constants.
  - `resolve_local` = `"const{createRequire}=require('node:module');const r=createRequire(...`
  - `resolve_eslint` = `"const{createRequire}=require('node:module');const{realpathSync}=re...`
- `class JavaScriptReorderMetrics` — Metrics produced by JavaScript class-method organization.
  - Fields: `classes_reordered: int`, `classes_seen: int`, `lines_moved: int`, `methods_moved: int`, `methods_seen: int`
- `class JavaScriptReorderResult` — Outcome of reordering one JavaScript source file.
  - Fields: `metrics: JavaScriptReorderMetrics`, `source: str`
  - `changed() -> bool` — Return whether at least one method moved.
- `class JavaScriptClassMethodReorderer` — Reorder safe JavaScript class-method runs without regenerating code.
  - `measure() -> JavaScriptReorderResult` — Return reordered source and metrics without writing the file.
  - `reorder() -> str` — Return reordered source without writing the file.
  - `write() -> bool` — Reorder the file in place and return whether it changed.

## Examples

Examples for the organize package.

Files: `__init__.py`, `__main__.py`, `run.py`

## Dependencies and consumers

- Third-party: `psutil`
- Used by: `../pyproject.toml`, `tests/tools/lints/js/function_blocks.test.mjs`, `tests/tools/lints/js/function_blocks_torture.test.mjs`, `tests/tools/lints/test_lints.py`, `tools/lints/core.py`, `tools/lints/packages_pipeline.py`

## Tests

Tests live in `exactus/tests/packages/organize/`.

- `test_javascript.py` — Tests for standalone JavaScript class-method organization. (4 tests)
  - `test_javascript_reorders_and_is_idempotent`
  - `test_javascript_reports_organizer_failures`
  - `test_javascript_resolves_global_espree_or_fails`
  - `test_javascript_rejects_malformed_payloads`
- `test_organize.py` — Tests for source-preserving Python class method organization. (23 tests)
  - `test_reorders_every_category_stably`
  - `test_preserves_decorators_annotations_docstrings_and_comments`
  - `test_property_family_is_adjacent_and_accessor_order_is_normalized`
  - `test_qualified_binding_decorators_are_recognized`
  - `test_blank_line_separated_comment_remains_anchored`
  - `test_direct_comment_moves_with_method`
  - `test_nested_class_is_reordered_but_function_local_class_is_not`
  - `test_idempotent_and_already_ordered_source_is_byte_identical`
  - `test_single_method_and_empty_class_are_unchanged`
  - `test_file_api_reorders_and_reports_change`
  - `test_invalid_python_propagates_syntax_error`
  - `test_metrics_report_moved_methods_classes_and_lines`
  - `test_metrics_report_zero_moves_for_ordered_source`
  - `test_custom_order_reorders_by_given_categories`
  - `test_validate_order_rejects_incomplete_and_unknown`
  - `test_configured_order_reads_pyproject`
  - `test_configured_order_defaults_without_section`
  - `test_configured_order_rejects_invalid_pyproject`
  - `test_main_dry_run_reports_metrics_without_writing`
  - `test_main_expands_globs_and_applies_exclude`
  - `test_main_order_flag_overrides_pyproject`
  - `test_main_rejects_an_invalid_order_flag`
  - `test_main_without_paths_returns_one`

<!-- exactus:reference:end -->
