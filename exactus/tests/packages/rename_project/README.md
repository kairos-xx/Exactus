# Tests

Tests of the `exactus/packages/rename_project/` renamer.

- `__init__.py` — Tests of the `exactus/packages/rename_project/` renamer.
- `assertions.py` — Keyword-only assertion helpers shared by the suite.
- `test_adversarial_semantics.py` — Hostile inputs and semantic edge cases.
- `test_assertions.py` — The shared assertion helpers fail loudly when violated.
- `test_cli_behavior.py` — CLI-level behavior: plans, prompts, rollback.
- `test_example.py` — The `examples/` demo renames only a throwaway copy.
- `test_next_safety_batch.py` — Deferred safety checks for the rename plan.
- `test_roundtrip.py` — Rename round-trips across a synthetic project tree.
- `test_safety_metrics.py` — Safety-metric accounting of the renamer.
- `test_sqlite_semantics.py` — SQLite schema and trigger rewrite semantics.

## Files

- `test_cli_help.py` — File.
- `test_example.py` — File.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests of the `exactus/packages/rename_project/` renamer.
- [`assertions.py`](assertions.py) — Keyword-only assertion helpers for the rename_project tests.
- [`test_adversarial_semantics.py`](test_adversarial_semantics.py) — Adversarial semantic-safety tests for rename_project.
- [`test_assertions.py`](test_assertions.py) — Every assertion helper passes on good input and fails on bad input.
- [`test_cli_behavior.py`](test_cli_behavior.py) — CLI-level behavior of the project renamer: plans, prompts, rollback.
- [`test_cli_help.py`](test_cli_help.py) — ANSI-styled ``--help`` output of the ``cli_help`` module.
- [`test_example.py`](test_example.py) — The ``examples/run.py`` demo renames only a throwaway copy.
- [`test_main_bootstrap.py`](test_main_bootstrap.py) — Cover the rename_project package bootstrap entry points.
- [`test_next_safety_batch.py`](test_next_safety_batch.py) — Regression tests for SQL, Unicode geometry, golden projects, rollback.
- [`test_roundtrip.py`](test_roundtrip.py) — Renaming forth and back reproduces the original project exactly.
- [`test_safety_metrics.py`](test_safety_metrics.py) — Safety-oriented corpus metrics with asymmetric failure accounting.
- [`test_scanners.py`](test_scanners.py) — Exercise the language-aware safe-span scanners in the renamer.
- [`test_sqlite_semantics.py`](test_sqlite_semantics.py) — SQLite safety tests for the project renamer.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


