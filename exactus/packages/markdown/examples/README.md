# `exactus/markdown/examples/`

Small generic example for the Markdown engine, independent of any exactus
report. The inventory below documents every direct file and child
directory.

## Directory contents

### Files

- `__init__.py` — package marker so the example can be imported as a module.
- `__main__.py` — run the example via ``python -m exactus.packages.markdown.examples``.
- `run.py` — render `assets/` and compare with the checked-in golden file.

### `assets/`

Example inputs and golden output:

- `data.json` — source document with a `name` and an unsorted `items` list.
- `mapping.json` — mapping specification exposing `name` and the items
  sorted by `rank`.
- `template.md` — template greeting the name and listing the sorted items.
- `expected.md` — golden Markdown rendered from `data.json` through
  `mapping.json` and `template.md` with `python -m exactus.packages.markdown`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Examples for the markdown package.
- [`__main__.py`](__main__.py) — Run the markdown example with the project virtual environment.
- [`run.py`](run.py) — Render the bundled example and check it against the golden output.

### Subdirectories

- [`assets/`](assets/README.md) — Provide data json content.

<!-- exactus:inventory:end -->
