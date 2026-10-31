# `examples/`

`run.py` demonstrates the structural SQLite model end to end without
touching the filesystem: a dataclass derives the `notes` table, every
statement compiles to inspectable SQL first, and the `Database`
execution boundary runs the same statements against an in-memory
SQLite connection and prints the fetched row.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Runnable demonstration for the ``model`` package.
- [`__main__.py`](__main__.py) — Run the model example with the project virtual environment.
- [`run.py`](run.py) — Demonstrate the structural SQLite model against an in-memory database.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
