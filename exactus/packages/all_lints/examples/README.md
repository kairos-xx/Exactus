# `examples/`

Runnable demonstration for `exactus/packages/all_lints/`.

`run.py` rebuilds a throwaway project under the git-ignored
`.scratch/` folder on every run: a `pyproject.toml` carrying
`[tool.ruff]` and `[tool.basedpyright]` ignore settings and one Python
file. It prints the merged exclude patterns, shows the command lines
the audit would launch, and writes a synthetic aggregate report — no
real linters are invoked, so it runs offline every time.

```bash
python -m exactus.packages.all_lints.examples
```

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Runnable demonstration for the ``all_lints`` tool.
- [`__main__.py`](__main__.py) — Run the all-lints example with the project virtual environment.
- [`run.py`](run.py) — Demonstrate ignore merging and report building on a scratch project.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
