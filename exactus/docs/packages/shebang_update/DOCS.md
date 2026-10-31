# shebang_update/

Update Python virtual-environment shebangs to the current project path.

## Behavior

- After a project directory is moved or renamed, carried scripts still
  embed the old absolute interpreter path.
- The updater walks the project root and rewrites any file whose first
  line is an absolute `#!.../.venv/bin/python...` shebang so it points
  at this checkout's interpreter.
- Non-shebang files and relative shebangs are left untouched.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Update Python virtual-environment shebangs to the current project path. |
| `__main__.py` | Run the virtual-environment shebang updater. |
| `core.py` | Update Python virtual-environment shebangs to the current project path. |
| `examples/` | Runnable demonstration for `exactus/packages/shebang_update/`. |

Run it as a module: `python -m exactus.packages.shebang_update`.

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Update Python virtual-environment shebangs to the current project path.


### `__main__.py`

Run the virtual-environment shebang updater.


### `core.py`

Update Python virtual-environment shebangs to the current project path.

- `class Settings` — Configure recursive shebang replacement.
  - `virtual_environment` = `'.venv'`
  - `python_executable` = `'bin/python'`
  - Fields: `root: Path`
  - `shebang(self) -> bytes` — Return the expected project-local Python shebang.
- `class ShebangUpdater` — Recursively replace stale virtual-environment Python shebangs.
  - `__init__(self, *, settings: Settings) -> None` — Initialize the updater.
  - `run(self) -> int` — Update matching shebangs below the project root.
- `main() -> None` — Update stale shebangs using the current working directory.

### `examples/__init__.py`

Runnable demonstration for the ``shebang_update`` tool.


### `examples/__main__.py`

Run the shebang-update example with the project virtual environment.


### `examples/run.py`

Fix stale virtual-environment shebangs in a throwaway demo project.

- `class Constants` — Collect shared example paths and the stale shebang prefix.
  - `here` = `Path(__file__).resolve().parent`
  - `work` = `here / '.scratch' / 'demo_project'`
  - `stale` = `'/previous/checkout/demo_project'`
- `main() -> int` — Rebuild the demo project and repair its stale shebangs.

## Examples

Runnable demonstration for `exactus/packages/shebang_update/`.

Fix stale virtual-environment shebangs in a throwaway demo project.

```bash
python -m exactus.packages.shebang_update.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`

## Dependencies and consumers

- Used by: `tests/packages/shebang_update/test_examples.py`, `tests/packages/shebang_update/test_shebang_update.py`

## Tests

Tests live in `exactus/tests/packages/shebang_update/`.

- `test_examples.py` — Cover the shebang_update examples demonstration. (3 tests)
  - `test_example_module_runs_as_a_script`
  - `test_example_repairs_only_the_stale_script`
  - `test_examples_main_module_runs_the_demo`
- `test_shebang_update.py` — Exercise the packaged virtual-environment shebang updater. (11 tests)
  - `test_core_module_runs_main_as_a_script`
  - `test_main_module_runs_without_a_bootstrap_candidate`
  - `test_main_module_switches_interpreter_and_invokes_main`
  - `test_main_updates_the_working_directory`
  - `test_run_ignores_non_matching_first_lines`
  - `test_run_leaves_current_shebangs_unchanged`
  - `test_run_reports_zero_for_an_empty_project`
  - `test_run_rewrites_a_stale_shebang`
  - `test_run_skips_files_inside_the_environment`
  - `test_run_survives_unwritable_files`
  - `test_settings_builds_the_project_interpreter_shebang`

<!-- exactus:reference:end -->
