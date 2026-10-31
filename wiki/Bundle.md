[Home](Home.md) > [Bundle](Bundle.md) > bundle

# bundle/

Platform-specific offline tool bundles and packaged-executable freshness
checks. `python -m exactus.bundle` dispatches to the host's leaf, and
`from exactus.bundle import <module>` routes to the same leaf's module.

## Files

| File | Description |
|---|---|
| `__init__.py` | Host detection (`host_leaf()`), musl→glibc fallback, and `__getattr__` routing so `from exactus.bundle import partition_fs` resolves the host leaf's module. |
| `__main__.py` | Host dispatch: reuses `host_leaf()` and forwards to the matching leaf's `__main__.py`. |
| `content.py` | Render `CONTENT.md` inventories for staged bundle roots: reads each target leaf's `data/bundle.json` manifest and lists the operating systems, architectures and installed tool versions so a staged tree documents itself. |
| `CONTENT.md` | Generated inventory produced by `content.py` — OS/architecture/tool-version listing for the staged bundle tree. |
| `freshness.py` | Detect when a packaged `exactus` is older than its source tree; warns the user the bundle may be stale. |

## Layout

```
bundle/
├── linux/
│   ├── glibc/<arch>/   # glibc Linux bundles
│   └── musl/<arch>/    # musl (e.g. Alpine) bundles — no browser group
├── macos/<arch>/       # macOS bundles
└── windows/<arch>/     # Windows bundles
```

Each leaf is produced by `scripts/bundle_make` and contains a schema-5
partition launcher (`__main__.py`), the `data/parts/fs/catalog.json`
component catalog, content-addressed packs, and bundled
`zstd_portable/bin/` binaries.

## Host selection

- `linux` resolves glibc vs musl via `platform.libc_ver()` and
  `ld-musl-*.so*` loader probing; musl hosts get the musl leaf, everyone
  else the glibc leaf.
- `from exactus.bundle import <name>` resolves the host leaf through a
  package `__getattr__`: `partition_fs`, `partition_launcher`,
  `conflict_copies` and `zstd_portable` import from
  `exactus.bundle.<os>.<arch>` without callers naming the platform. The
  resolved module is cached on the package; unknown names raise
  `AttributeError`, and import failures *inside* a leaf module
  propagate rather than masquerading as missing attributes.
- The same ordered candidate list is used at runtime by
  `tools/common/cli.py::_host_bundle_dirs` when resolving tool bundles
  from `root/bundle`, `root/exactus/bundle` or the packaged
  `exactus/bundle` resource anchor.
- The `lints` tool binds every `all_lints` spec to this resolved host launcher
  when a standalone command is missing. This covers Ruff/Ruff-doc checks,
  BasedPyright, Pyrefly, ESLint, Stylelint, HTMLHint and TypeScript (`tsc`)
  without duplicating their execution or parsing logic in the lints tool.

## Notes

- `<leaf>.update/` siblings hold incremental update payloads (new packs
  + identities) emitted by `bundle_make --rebuild`.
- Bundle leaves ship their `data/` catalogs via `pyproject.toml`
  package-data globbing, so they survive wheel/zipapp packaging.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/bundle/`](../exactus/bundle/) | [`exactus/tests/bundle/`](../exactus/tests/bundle/) | [`DOCS.md`](../exactus/docs/bundle/DOCS.md) |

[Bundle index](Bundle.md)
