# Offline partitioned tools

Run this package with `python -m exactus.bundle.linux.musl.arm64` or `python exactus/bundle/linux/musl/arm64`. Keep __init__.py, __main__.py, partition_fs.py, partition_launcher.py, conflict_copies.py, zstd_portable/, and data/ together. JSON metadata is in data/bundle.json and data/metrics.json; the catalog and packs are in data/parts/fs/. Runtime is offline.

Use `list-tools`, `--verify`, `--verify-deep`, or `TOOL [ARGS...]`. Components materialize lazily with their dependencies. Cache: EXACTUS_TOOLS_CACHE or ${XDG_CACHE_HOME:-~/.cache}/exactus-tools/<catalog-root>. Set EXACTUS_TOOLS_OBJECT_CACHE=discard to discard decoded objects after materialization.

Builds reuse unchanged staged recipes and packs. --only forces named selected components; --rebuild restages all. Incremental rebuilds emit a sibling `<leaf>.update/` directory holding the new catalog and only the changed packs. Apply with `--apply-update <dir>`; rollback with `--rollback`. Explicit GC is opt-in.

Catalog root: `47f75c4660b1ed3fe113f70baa01debe072c0fa0c28eefd4d8c066d1aa638723`

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`@activity.json`](%40activity.json) — Provide @activity json content.

### Subdirectories

- [`fs/`](fs/README.md) — Filesystem catalog, immutable packs, and retained catalogs.

<!-- exactus:inventory:end -->
