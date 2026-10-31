# `examples/`

`run.py` demonstrates the renamer end to end without risking a real
checkout: it duplicates `project/` into the git-ignored
`.scratch/` folder and renames the copy to `demo_app` with
`--yes --no-git --diff --boundary loose` (loose also renames inside
identifiers, so `PROJECT_VERSION` becomes `DEMO_APP_VERSION`).
Because only the copy is touched, the checked-in example project stays
pristine and the demo can be re-run any number of times.

```bash
python exactus/packages/rename_project/examples
```

The template exercises every casing convention: `project`
(identifiers, module folder), `project` (distribution name in
`pyproject.toml`), `Project` (a class), `project`
(camelCase prose), `PROJECT_*` (constants), and `Project`
(headings).

## Directory contents

- `__init__.py` — File.
- `__main__.py` — File.
- `run.py` — File.
- `project/` — Subdirectory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Runnable demonstration for the ``rename_project`` script.
- [`__main__.py`](__main__.py) — Run the rename-project example with the project virtual environment.
- [`run.py`](run.py) — Rename a throwaway copy of ``project`` with ``rename_project``.

### Subdirectories

- [`project/`](project/README.md) — `project` is a tiny package that exists only to be renamed by the `rename_project` example. Every casing of the name appears somewhere so the restyling rules can be watched live: `project` in imports, `project` as the distribution name, `Project` as a class, `project` in camelCase prose, and `PROJECT_VERSION` as a constant.

<!-- exactus:inventory:end -->
