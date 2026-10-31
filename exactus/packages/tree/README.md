# `exactus/packages/tree/`

Render directories, `.zip` archives and explicit path lists as
`TREE.txt`-style listings (name + aligned size + modified date).

## Usage

```bash
python exactus/packages/tree exactus/packages/steps                 # a directory
python exactus/packages/tree packages_steps.zip             # a zip archive
python exactus/packages/tree 'exactus/packages/**/*.py' -o TREE.txt # glob expansion
python exactus/packages/tree docs --include '*.md' --exclude '*/node_modules/*'
```

Python API:

```python
from exactus.packages.tree import render_tree

text = render_tree(source=Path("exactus/packages/steps"))
text = render_tree(source=Path("packages_steps.zip"))
text = render_tree(
    source=["exactus/packages/steps/core.py", "pyproject.toml"],
    root=Path.cwd(),
    name="bundle",
)
```

## Layout

- `core.py` — rendering, member collection, filtering and the CLI.
- `examples/` — runnable demo (`python -m exactus.packages.tree.examples`).
- `tests/` — `exactus/tests/packages/tree/`; docs live in `exactus/docs/packages/tree/`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Public API for ``TREE.txt``-style listings.
- [`__main__.py`](__main__.py) — Run ``exactus.packages.tree`` through the project's virtualenv.
- [`core.py`](core.py) — Render directories, zip archives and path lists as ``TREE.txt`` text.

### Subdirectories

- [`examples/`](examples/README.md) — Runnable demos for `exactus.packages.tree`.

<!-- exactus:inventory:end -->
