# `zstd_portable/`

Portable Zstandard compression bootstrap for the generated bundle.

- [__init__.py](__init__.py) — Python wrapper and payload loader.
- [bin/](bin/README.md) — Target-specific native CLI archive.

Keep this package and its native archive together. The runtime extracts the CLI into its user cache when compression is needed.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`.DS_Store`](.DS_Store) — Provide .DS Store project content.
- [`__init__.py`](__init__.py) — Portable Zstandard CLI wrapper with lazy zipped-binary extraction.
- [`directory_inventory.py`](directory_inventory.py) — Maintain a managed, bottom-up directory inventory in README documents.

### Subdirectories

- [`__pycache__/`](__pycache__/README.md) — Contain   pycache   resources and their directory inventory.
- [`bin/`](bin/README.md) — Native Zstandard payload for `darwin/arm64`.

<!-- exactus:inventory:end -->
