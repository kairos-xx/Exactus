[Home](Home.md) > [Packages](Packages.md) > organize

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/organize/`](../exactus/packages/organize/) | [`exactus/tests/packages/organize/`](../exactus/tests/packages/organize/) | [`DOCS.md`](../exactus/docs/packages/organize/DOCS.md) |

[< Packages-model](Packages-model.md) · [Packages index](Packages.md) · [Packages-package >](Packages-package.md)
