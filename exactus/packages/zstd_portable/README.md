# `zstd_portable/`

Portable Zstandard CLI wrapper with lazy zipped-binary extraction. Ships
compressed `zstd` binaries under `bin/` per platform and extracts the
matching one on first use, so callers get a real `zstd` executable
without a system install.

The platform payloads themselves live in the repository's
[`bin/zstd_portable/`](../../../bin/zstd_portable/README.md) directory and
are copied into every bundle target by `export_package`, so staged
packages find the archive beside `__init__.py` in `bin/`.

Run the example from the repository root:

```bash
python -m exactus.packages.zstd_portable.examples
```

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Portable Zstandard CLI wrapper with lazy zipped-binary extraction.
- [`__main__.py`](__main__.py) — Run the zstd_portable demo through the project virtualenv.
- [`py.typed`](py.typed) — Provide py typed content.

### Subdirectories

- [`examples/`](examples/README.md) — Run the streaming round-trip from the repository root:

<!-- exactus:inventory:end -->
