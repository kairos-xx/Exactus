# `exactus/packages/argument_parser/` — dash/underscore option folding

`exactus.packages.argument_parser` provides `ExactusArgumentParser`, an
`ArgumentParser` subclass that folds `-` and `_` in long option names at parse
time, so `--dry-run` and `--dry_run` select the same option without duplicate
flags or help noise. Folded names claimed by two different options fall back
to exact matching, and folding stops after a bare `--`.

```python
from exactus.packages.argument_parser import ExactusArgumentParser, normalized_option
```

## Files

| File | Description |
|---|---|
| `parser.py` | Implementation of `ExactusArgumentParser` and `normalized_option`: folds `-`/`_` in long-option spellings at parse time, falls back to exact matching on collisions and stops folding after a bare `--`. |
| `__init__.py` | Public re-exports (`ExactusArgumentParser`, `normalized_option`). |

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Public API for the dash/underscore-folding argument parser. |
| `parser.py` | Shared argument parser accepting ``-`` and ``_`` interchangeably. |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Public API for the dash/underscore-folding argument parser.


### `parser.py`

Shared argument parser accepting ``-`` and ``_`` interchangeably.

- `normalized_option(*, argument: str) -> str` — Fold dashes to underscores in the name part of a long option.
- `class ExactusArgumentParser` — ``ArgumentParser`` accepting ``-``/``_`` long-option spellings.
  - `parse_known_args(self, args: Iterable[str] | None=None, namespace: None=None) -> tuple[Namespace, list[str]]`
  - `parse_known_args(self, args: Iterable[str] | None, namespace: _N) -> tuple[_N, list[str]]`
  - `parse_known_args(self, *, namespace: _N) -> tuple[_N, list[str]]`
  - `parse_known_args(self, args: Iterable[str] | None=None, namespace: _N | None=None) -> tuple[_N, list[str]]` — Rewrite alternative long-option spellings, then parse.

## Dependencies and consumers

- Used by: `__main__.py`, `packages/__main__.py`, `packages/all_lints/core.py`, `packages/browser/cli.py`, `packages/browser/examples/run.py`, `packages/completion/catalog.py`, `packages/completion/cli.py`, `packages/completion/engine.py`, `packages/completion/examples/run.py`, `packages/exactus_mcp/cli.py`, `packages/exactus_mcp/examples/client.py`, `packages/exactus_mcp/wakeup_cli.py`, `packages/group_final/core.py`, `packages/guard/cli.py`, `packages/http_process/cli.py`, `packages/markdown/main.py`, `packages/meaningful/cli.py`, `packages/organize/core.py`, `packages/package/bundle.py`, `packages/package/cli.py`, `packages/package/install.py`, `packages/package/inventory_cli.py`, `packages/patcher/cli.py`, `packages/patcher/runtime.py`, `packages/performance/cli.py`, `packages/rename_project/cli_help.py`, `packages/scene_description/cli.py`, `packages/screenshot/cli.py`, `packages/screenshot/examples/run.py`, `packages/server/cli.py`, `packages/todo_sync/cli.py`, `packages/tree/core.py`, `packages/visual_cause/analyzer.py`, `packages/visual_cause/dom_diff.py`, `packages/watch/core.py`, `packages/watch/examples/run.py`, `packages/zip_components/core.py`, `tests/packages/argument_parser/test_parser.py`, `tools/__main__.py`, `tools/actions/__main__.py`, `tools/actions/examples/run.py`, `tools/common/cli.py`, `tools/common/collect_files.py`, `tools/common/config.py`, `tools/common/examples/run.py`, `tools/completion/main.py`, `tools/docs/arguments.py`, `tools/docs/core.py`, `tools/frontend/arguments.py`, `tools/kwargs_typehints/arguments.py`, `tools/kwargs_typehints/core.py`, `tools/lints/arguments.py`, `tools/performance/arguments.py`, `tools/readme/arguments.py`, `tools/record/arguments.py`, `tools/record/run.py`, `tools/record/studio/__main__.py`, `tools/self_test/arguments.py`, `tools/visual_cause/arguments.py`

## Tests

Tests live in `exactus/tests/packages/argument_parser/`.

- `test_parser.py` — Dash/underscore folding in the shared ``ExactusArgumentParser``. (7 tests)
  - `test_abbrev_matching_still_works`
  - `test_colliding_spellings_fall_back_to_exact`
  - `test_dash_and_underscore_parse_identically`
  - `test_equal_form_and_separator`
  - `test_normalized_option_folds_long_names`
  - `test_subparsers_inherit_folding`
  - `test_unmatched_tokens_pass_through`

<!-- exactus:reference:end -->
