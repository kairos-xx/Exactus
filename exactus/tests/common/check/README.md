# `check/`

Test the top-level exactus check CLI.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Test the top-level exactus check CLI.
- [`test_check_cli.py`](test_check_cli.py) — The ``check`` orchestrator driven in-process with isolated global state.
- [`test_check_extra.py`](test_check_extra.py) — Orchestrator internals: signals, clearing, registry and unified refresh.
- [`test_check_more.py`](test_check_more.py) — Venv discovery, shortcut servers, and unified pipeline runs.
- [`test_check_units.py`](test_check_units.py) — Focused unit coverage for the bundled CLI model and presentation helpers.
- [`test_misc_entrypoints.py`](test_misc_entrypoints.py) — Thin dispatch modules and path-plumbing files.
- [`test_public_api.py`](test_public_api.py) — The package facade is the controlled public API surface.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
