# pmanager

`pmanager` is a Python 3.13 process manager with a symmetric typed
configuration model, object-reference process graph API, detached
cross-platform workers, lifecycle hooks, structured Python arguments,
live status enrichment, and context/global broadcasts.

## Entry points

```bash
python -m exactus.packages.pmanager --help
python -m exactus.packages.pmanager --spec exactus/packages/pmanager/examples/cli/processes.json --tree example
python -m exactus.packages.pmanager.examples
python -m exactus.packages.pmanager.examples.api
python -m exactus.packages.pmanager.examples.cli
```

See `exactus/docs/packages/pmanager/DOCS.md` for the full API and
`examples/README.md` for runnable examples.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Public Python API for the process orchestrator.
- [`__main__.py`](__main__.py) — Run the pmanager command-line interface.
- [`_platform.py`](_platform.py) — Cross-platform process primitives used by the orchestrator.
- [`api.py`](api.py) — Stable Python-first API for the context-aware process orchestrator.
- [`builder.py`](builder.py) — Object-first orchestration graph builder.
- [`class_runner.py`](class_runner.py) — Detached runner for Python ProcessClass executors.
- [`lifecycle.py`](lifecycle.py) — Python process classes and lifecycle-hook decorators.
- [`model.py`](model.py) — Validated mutable configuration model for orchestration specifications.
- [`processes.json`](processes.json) — Provide processes json content.
- [`py.typed`](py.typed) — Provide py typed content.
- [`runtime.py`](runtime.py) — Context-aware process orchestrator.

### Subdirectories

- [`examples/`](examples/README.md) — Run the comprehensive API example with any of:

<!-- exactus:inventory:end -->
