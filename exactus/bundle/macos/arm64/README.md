# Offline partitioned tools

Run this package with `python -m exactus.bundle.macos.arm64` or `python exactus/bundle/macos/arm64`. Keep __init__.py, __main__.py, partition_fs.py, partition_launcher.py, conflict_copies.py, zstd_portable/, and data/ together. JSON metadata is in data/bundle.json and data/metrics.json; the catalog and packs are in data/parts/fs/. Runtime is offline.

Use `list-tools`, `--verify`, `--verify-deep`, or `TOOL [ARGS...]`. Components materialize lazily with their dependencies. Cache: EXACTUS_TOOLS_CACHE or ${XDG_CACHE_HOME:-~/.cache}/exactus-tools/<catalog-root>. Set EXACTUS_TOOLS_OBJECT_CACHE=discard to discard decoded objects after materialization.

Builds reuse unchanged staged recipes and packs. --only forces named selected components; --rebuild restages all. Incremental rebuilds emit a sibling `<leaf>.update/` directory holding the new catalog and only the changed packs. Apply with `--apply-update <dir>`; rollback with `--rollback`. Explicit GC is opt-in.

Catalog root: `f93a1527036704296d14411f7a1d56e7b1ef52212e71f2dd4b577452903682b3`
