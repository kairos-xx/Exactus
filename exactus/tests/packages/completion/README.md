# Tests

Tests of `exactus/completion`.

- `__init__.py` — Tests of `exactus/completion`.
- `test_catalog.py` — `spec_from_parser` introspection: cardinalities, choices, mutex groups, repeatable and suppressed actions, positionals, provider inference, spec merging.
- `test_engine.py` — The scanner and decision tree on a synthetic grammar: option/value/positional/subcommand contexts, used-option and mutex suppression, repeat-value filtering, `--` handling, inline `=`, short clusters, negative numbers.
- `test_integration.py` — End-to-end runs against the real `check` catalog: dispatch flags, tool/pipeline values, shortcut merge, the `completion` command, plus install/uninstall/diagnose lifecycle in a fake home.
- `test_protocol.py` — `__complete` argument validation, record encoding, size limits, exit codes, and stdout purity.
- `test_providers.py` — Path/directory listing, hidden files, prefix splitting, static and scoped-argument providers, and the default registry.
- `test_shells.py` — Deterministic script shape for all four shells, plus `bash -n`/`zsh -n`/`fish --no-execute` syntax validation where available.
- `README.md` — This file.

- `test_startup.py` — Automatic portable registration, OS profile layouts, catalog refresh, idempotence, and preservation of user content.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests of ``exactus/completion``.
- [`test_catalog.py`](test_catalog.py) — Coverage for parser introspection in ``exactus/completion/catalog``.
- [`test_engine.py`](test_engine.py) — Decision-tree coverage for :class:`CompletionEngine`.
- [`test_examples.py`](test_examples.py) — Run the public completion example against the standalone grammar.
- [`test_main.py`](test_main.py) — Cover the ``exactus.packages.completion`` command-line entry point.
- [`test_protocol.py`](test_protocol.py) — Wire-protocol coverage for ``__complete`` parsing and records.
- [`test_providers.py`](test_providers.py) — Coverage for the dynamic completion providers.
- [`test_shells.py`](test_shells.py) — Coverage for the shell registration-script renderers.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


