# project_python/

Shared interpreter bootstrap for repository scripts.

## Behavior

- `switch_to_project_venv()` replaces a non-project Python process with
  `.venv/bin/python` (or `.venv/Scripts/python.exe` on Windows),
  preserving the requested script and its arguments.
- It is a no-op when `.venv` is absent or already active.
- Re-execution is skipped inside `multiprocessing` spawn workers
  (`multiprocessing.parent_process()` non-`None`), so workers inheriting
  a test runner's `sys.argv` are never re-launched as the parent command.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Re-execute project scripts with the repository virtual environment. |
| `__main__.py` | Run a script under the project virtual environment. |
| `auto.py` | Activate the repository virtual environment when this module is imported. |
| `examples/` | Runnable examples for `exactus/packages/project_python/`. |

Run it as a module: `python -m exactus.packages.project_python`.

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Re-execute project scripts with the repository virtual environment.

- `class Constants` — Group module-level constants.
  - `project_root` = `_project_root()`
- `switch_to_project_venv() -> None` — Replace the current interpreter with ``.venv`` when available.

### `__main__.py`

Run a script under the project virtual environment.

- `main() -> int` — Run ``argv[1]`` as ``__main__`` under the project interpreter.

### `auto.py`

Activate the repository virtual environment when this module is imported.

- `class Constants` — Group module-level constants.
  - `activated` = `True`

## Examples

Runnable examples for `exactus/packages/project_python/`.

Files: `__init__.py`, `__main__.py`, `run.py`

## Dependencies and consumers

- No dependencies outside the standard library.
- Used by: `__main__.py`, `packages/actions/action_javascript/examples/__main__.py`, `packages/actions/action_javascript/examples/run.py`, `packages/actions/action_rest/examples/__main__.py`, `packages/actions/action_rest/examples/run.py`, `packages/all_lints/__main__.py`, `packages/all_lints/examples/__main__.py`, `packages/all_lints/examples/run.py`, `packages/browser/__main__.py`, `packages/browser/examples/__main__.py`, `packages/browser/examples/run.py`, `packages/completion/__main__.py`, `packages/completion/examples/__main__.py`, `packages/extended_selector/examples/__main__.py` and 90 more

## Tests

Tests live in `exactus/tests/packages/project_python/`.

- `test_examples.py` — Exercise the ``project_python`` re-exec example delegation chain. (2 tests)
  - `test_example_switches_venv_then_runs_the_tool`
  - `test_example_swaps_and_restores_build_constants`
- `test_venv.py` — Exercise the shared project virtual-environment bootstrap. (8 tests)
  - `test_switch_to_project_venv_reexecutes_with_original_arguments`
  - `test_switch_to_project_venv_is_safe_without_a_switch`
  - `test_switch_to_project_venv_skips_multiprocessing_children`
  - `test_executable_tools_and_scripts_use_project_python`
  - `test_project_root_falls_back_to_package_grandparent`
  - `test_switch_returns_when_argv_has_no_script`
  - `test_switch_resolves_program_through_path`
  - `test_main_module_runs_the_requested_script`

<!-- exactus:reference:end -->
