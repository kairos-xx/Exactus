# group_final

AST-based Python refactoring utility that groups safely movable module-level
`Final` constants into a `Constants` class and updates Python references across
the source tree.

## Run

The module and example entry points automatically re-execute with the
repository `.venv` through `exactus.packages.project_python` when it is available.

Apply changes:

```bash
python -m group_final /path/to/project
```

Dry run (analyze without writing):

```bash
python -m group_final /path/to/project --dry-run
```

## Example

```bash
python -m group_final.examples
```

The tool excludes common generated/cache/environment directories and replaces
one contiguous block of module-level declarations at its original execution
boundary. Generated members retain their `Final` annotations and the generated
`Constants` class is decorated with `@final`.

Local and imported references are rewritten with lexical-scope awareness.
Absolute and package-relative imports are supported, and generated imports use
private aliases when `Constants` or `final` would collide with an existing
binding. Providers consumed through a star import or an ambiguously rebound
module-level import are left unchanged rather than producing an unsafe rewrite.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Group safe module-level Final constants into Constants classes.
- [`__main__.py`](__main__.py) — Run the Final constants refactoring tool.
- [`core.py`](core.py) — Group safely movable module-level Final constants into Constants classes.

### Subdirectories

- [`examples/`](examples/README.md) — Examples for the group_final package.

<!-- exactus:inventory:end -->
