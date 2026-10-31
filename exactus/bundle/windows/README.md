# `windows/`

Provide the generated tool-bundle namespace.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Provide the generated tool-bundle namespace.

### Subdirectories

- [`amd64/`](amd64/README.md) — Run this package with `python -m exactus.bundle.windows.amd64` or `python exactus/bundle/windows/amd64`. Keep __init__.py, __main__.py, partition_fs.py, partition_launcher.py, conflict_copies.py, zstd_portable/, and data/ together. JSON metadata is in data/bundle.json and data/metrics.json; the catalog and packs are in data/parts/fs/. Runtime is offline.
- [`amd64.update/`](amd64.update/README.md) — Filesystem catalog, immutable packs, and retained catalogs.
- [`arm64/`](arm64/README.md) — Run this package with `python -m exactus.bundle.windows.arm64` or `python exactus/bundle/windows/arm64`. Keep __init__.py, __main__.py, partition_fs.py, partition_launcher.py, conflict_copies.py, zstd_portable/, and data/ together. JSON metadata is in data/bundle.json and data/metrics.json; the catalog and packs are in data/parts/fs/. Runtime is offline.
- [`arm64.update/`](arm64.update/README.md) — Filesystem catalog, immutable packs, and retained catalogs.

<!-- exactus:inventory:end -->
