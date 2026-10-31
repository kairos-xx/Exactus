# `examples/`

Runnable demonstration for `exactus/packages/shebang_update/`.

`example.py` rebuilds a throwaway project under the git-ignored
`.scratch/` folder on every run: a `.venv` directory, a script whose
shebang still points at the project's previous location, a script whose
shebang is already correct, a plain text file, and a stale-looking file
inside the environment itself. The updater repairs only the stale
script — the environment's own files are excluded by design — and prints
each rewrite it makes.

```bash
python -m exactus.packages.shebang_update.examples
```

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Runnable demonstration for the ``shebang_update`` tool.
- [`__main__.py`](__main__.py) — Run the shebang-update example with the project virtual environment.
- [`run.py`](run.py) — Fix stale virtual-environment shebangs in a throwaway demo project.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
