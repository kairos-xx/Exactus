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
| `examples/` | Runnable demonstration for `exactus/packages/project_python/`. |

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

### `examples/__init__.py`

Runnable examples for the project interpreter bootstrap.


### `examples/__main__.py`

Run the project-python example with the project virtual environment.


### `examples/run.py`

Re-execute a repository script under the project virtual environment.

- `main() -> int` — Re-exec under ``.venv`` when needed, then run the tool.

## Examples

Runnable demonstration for `exactus/packages/project_python/`.

Re-execute a repository script under the project virtual environment.

```bash
python -m exactus.packages.project_python.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`

## Dependencies and consumers

- Used by: `__main__.py`, `tests/packages/project_python/test_examples.py`, `tools/actions/__main__.py`, `tools/actions/examples/__main__.py`, `tools/common/examples/__main__.py`, `tools/coverage_tests/main.py`, `tools/docs/main.py`, `tools/frontend/main.py`, `tools/kwargs_typehints/main.py`, `tools/lints/main.py`, `tools/performance/main.py`, `tools/readme/main.py`, `tools/record/examples/__main__.py`, `tools/record/main.py`, `tools/record/studio/__main__.py`, `tools/self_test/main.py`, `tools/visual_cause/main.py`

## Tests

Tests live in `exactus/tests/packages/project_python/`.

- `test_examples.py` — Exercise the ``project_python`` re-exec example delegation chain. (2 tests)
  - `test_example_swaps_and_restores_build_constants`
  - `test_example_switches_venv_then_runs_the_tool`
- `test_venv.py` — Exercise the shared project virtual-environment bootstrap. (8 tests)
  - `test_executable_tools_and_scripts_use_project_python`
  - `test_main_module_runs_the_requested_script`
  - `test_project_root_falls_back_to_package_grandparent`
  - `test_switch_resolves_program_through_path`
  - `test_switch_returns_when_argv_has_no_script`
  - `test_switch_to_project_venv_is_safe_without_a_switch`
  - `test_switch_to_project_venv_reexecutes_with_original_arguments`
  - `test_switch_to_project_venv_skips_multiprocessing_children`

<!-- exactus:reference:end -->
