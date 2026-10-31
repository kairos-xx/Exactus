# `examples/`

`run.py` demonstrates the synchronizer end to end without risking a real
checklist: it copies `TODO.md` into the git-ignored `.scratch/` folder and
runs `synchronize` against the copy, which rewrites the managed dashboard
block and emits the standalone `TODO.html` dashboard beside it. The
bundled source stays pristine, so the demo can be re-run any number of
times.

```bash
python exactus/packages/todo_sync/examples
```

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`TODO.md`](TODO.md) — Provide TODO md content.
- [`__init__.py`](__init__.py) — Provide a runnable TODO synchronization example.
- [`__main__.py`](__main__.py) — Run the todo-sync example with the project virtual environment.
- [`run.py`](run.py) — Synchronize a throwaway copy of the bundled ``TODO.md`` example.

### Subdirectories

- [`assets/`](assets/README.md) — No direct files besides this README.

<!-- exactus:inventory:end -->
