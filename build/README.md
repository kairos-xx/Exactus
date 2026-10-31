# `build/`

Generated dist directory produced by `python exactus.packages.package --build --build`.

The `bin/release/exactus_all/exactus` zipapp unzipped — the `exactus/` package plus
the `__main__.py` entry stub, runnable without bundling:

- `python build/` — same CLI as the `bin/release` pyz.
- `python -m exactus` — works from inside this directory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`.DS_Store`](.DS_Store) — Provide .DS Store project content.
- [`__main__.py`](__main__.py) — Pyz entry point dispatching to the exactus.

### Subdirectories

- [`exactus/`](exactus/README.md) — Self-contained exactus package. The inventory below documents every direct file and child directory.

<!-- exactus:inventory:end -->
