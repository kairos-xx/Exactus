# `model/`

Structural SQLite statement, schema, and execution model: production
application modules construct immutable schema, expression, and statement
objects and pass them through the SQLite execution boundary instead of
authoring SQL.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Structural SQLite statement, schema, and execution model.
- [`pipeline_queries.py`](pipeline_queries.py) — Typed pipeline schema and statements without handwritten SQL.
- [`registry_queries.py`](registry_queries.py) — Typed registry schema and statements without handwritten SQL.

### Subdirectories

- [`examples/`](examples/README.md) — `run.py` demonstrates the structural SQLite model end to end without touching the filesystem: a dataclass derives the `notes` table, every statement compiles to inspectable SQL first, and the `Database` execution boundary runs the same statements against an in-memory SQLite connection and prints the fetched row.
- [`sqlite_model/`](sqlite_model/README.md) — Typed, dependency-free SQLite AST, compiler, and execution layer.

<!-- exactus:inventory:end -->
