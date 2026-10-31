# Actions

Execute ordered discovery and exactus tools from JSON or TOML recipes, resolving named outputs without shell interpolation. Actions is an integration package: it composes recording, server startup, the exactus API, and report generation. Flow Studio may import this package.

Try the [runnable example](examples/README.md).

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Run declarative sequences of tool calls with named output references.
- [`__main__.py`](__main__.py) — Execute a saved JSON or TOML Actions recipe.
- [`conflict_copies.py`](conflict_copies.py) — Reconcile numbered sync copies without discarding unique project data.
- [`json_types.py`](json_types.py) — JSON value types shared by the exactus tools.
- [`process_control.py`](process_control.py) — Cross-invocation exactus ownership and process termination primitives.
- [`runner.py`](runner.py) — Orchestrate discovery and functional exactuss from JSON or TOML actions.

### Subdirectories

- [`examples/`](examples/README.md) — Discover the bundled page at mobile and desktop sizes, then replay the generated projects using a named output reference.

<!-- exactus:inventory:end -->


