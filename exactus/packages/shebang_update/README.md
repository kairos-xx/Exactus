# `shebang_update/`

Update Python virtual-environment shebangs to the current project path.

After a project directory is moved or renamed, the scripts it carries
still embed the old absolute interpreter path. The updater walks the
project root and rewrites any file whose first line is an absolute
`#!.../.venv/bin/python...` shebang so it points at this checkout's
environment instead. Files inside `.venv` are skipped, files whose
shebang is already correct are left untouched, and every rewrite is
printed.

```bash
python -m exactus.packages.shebang_update
```

`__main__.py` makes the directory itself runnable as well:
`python exactus/packages/shebang_update` puts the directory on `sys.path`,
switches to the project interpreter when one exists, and calls `main()`
from `core.py`, which scans the current working directory.
`examples/` holds a runnable demo that rebuilds a throwaway project
under `.scratch/` and repairs only its stale shebang.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Update Python virtual-environment shebangs to the current project path.
- [`__main__.py`](__main__.py) — Run the virtual-environment shebang updater.
- [`core.py`](core.py) — Update Python virtual-environment shebangs to the current project path.

### Subdirectories

- [`examples/`](examples/README.md) — Runnable demonstration for `exactus/packages/shebang_update/`.

<!-- exactus:inventory:end -->
