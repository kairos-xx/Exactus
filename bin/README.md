# `bin/`

Project executables and native tool archives.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Project executables and native tool archives.
- [`_bootstrap.py`](_bootstrap.py) — Put the repository root on ``sys.path`` and switch to the project venv.
- [`patcher.pyz`](patcher.pyz) — Provide patcher pyz content.
- [`studio.py`](studio.py) — Start Flow Studio on a port, replacing any listener.

### Subdirectories

- [`release/`](release/README.md) — Release executables for every supported OS, architecture, and libc target. Each directory holds the `exactus` zipapp plus a generated `MANIFEST.md` with the artifact checksum and bundled tool versions; `exactus_all/` embeds every target in a single binary.
- [`zstd_portable/`](zstd_portable/README.md) — No subdirectories.

<!-- exactus:inventory:end -->
