# `guard/`

Public API for process_guard.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Public API for process_guard.
- [`__main__.py`](__main__.py) — Execute process_guard as a Python module.
- [`cleanup.py`](cleanup.py) — Terminate processes previously observed by a process tracker.
- [`cli.py`](cli.py) — Command-line entry point for external process supervision.
- [`guard.py`](guard.py) — In-process descendant cleanup context manager.
- [`model.py`](model.py) — Typed value models for process supervision.
- [`supervisor.py`](supervisor.py) — External process supervisor that owns and cleans a target process tree.
- [`tracker.py`](tracker.py) — Continuously discover and retain descendant process identities.

### Subdirectories

- [`examples/`](examples/README.md) — Executable examples for exactus.packages.guard.

<!-- exactus:inventory:end -->
