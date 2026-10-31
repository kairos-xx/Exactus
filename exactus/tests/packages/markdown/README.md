# Tests

- `__init__.py` — package marker for the Markdown template engine tests.
- `test_errors.py` — The engine exposes one exception tree rooted at TemplateEngineError.
- `test_paths.py` — JSON paths resolve against a current value or the document root.
- `test_predicates.py` — Predicate specs filter list items and drive conditional mapping.
- `test_operators.py` — Operator edge cases for non-matching operand types.
- `test_mapping.py` — Mapping specs reshape a source document into a template context.
- `test_filters.py` — Markdown filters format values for templates.
- `test_engine.py` — The engine renders sandboxed Jinja2 templates from mapped JSON, confines includes to its roots and wraps every failure.
- `test_cli.py` — The command line renders templates and reports failures with exit 2.
- `test_examples.py` — The generic engine example renders to its checked-in expected output.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests for the Markdown template engine.
- [`test_cli.py`](test_cli.py) — The command line renders templates and reports failures with exit 2.
- [`test_engine.py`](test_engine.py) — The engine renders sandboxed Jinja2 templates from mapped JSON.
- [`test_errors.py`](test_errors.py) — The engine exposes one exception tree rooted at TemplateEngineError.
- [`test_example_run.py`](test_example_run.py) — Cover the bundled ``markdown`` example entry point.
- [`test_examples.py`](test_examples.py) — The generic engine example renders to its checked-in expected output.
- [`test_filters.py`](test_filters.py) — Markdown filters format values for templates.
- [`test_mapping.py`](test_mapping.py) — Mapping specs reshape a source document into a template context.
- [`test_operators.py`](test_operators.py) — Operator edge cases for non-matching operand types.
- [`test_paths.py`](test_paths.py) — JSON paths resolve against a current value or the document root.
- [`test_predicates.py`](test_predicates.py) — Predicate specs filter list items and drive conditional mapping.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


