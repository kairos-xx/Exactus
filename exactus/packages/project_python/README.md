# `project_python/`

Shared interpreter bootstrap for repository scripts. Calling
`switch_to_project_venv()` replaces a non-project Python process with
`.venv/bin/python` (or `.venv/Scripts/python.exe` on Windows), while
preserving the requested script and its arguments. It is a no-op when
`.venv` is absent or already active. The top-level Exactus dispatcher,
standalone tool modules, build/package scripts, `all_lints`, `group_final`,
their examples, `rename_project`, and `watch` invoke it at their executable
boundaries before loading command implementations, so manual activation is
not required:

```python
from exactus.packages.project_python import switch_to_project_venv

switch_to_project_venv()
```

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Re-execute project scripts with the repository virtual environment.
- [`__main__.py`](__main__.py) — Run a script under the project virtual environment.
- [`auto.py`](auto.py) — Activate the repository virtual environment when this module is imported.

### Subdirectories

- [`examples/`](examples/README.md) — Runnable examples for `exactus/packages/project_python/`.

<!-- exactus:inventory:end -->
