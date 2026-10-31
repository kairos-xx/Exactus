# `package/`

Unified project build, bundle, and package pipeline.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Unified project build, bundle, and package pipeline.
- [`__main__.py`](__main__.py) — Execute process_guard as a Python module.
- [`api.py`](api.py) — Python API for deterministic build, bundle, package orchestration.
- [`build.py`](build.py) — Build the distributable artifacts of the exactus.
- [`bundle.py`](bundle.py) — Build incremental partitioned offline tool bundles and catalogs.
- [`cli.py`](cli.py) — Command-line interface for :mod:`exactus.packages.package`.
- [`config.py`](config.py) — Typed configuration for the build, bundle, and package pipeline.
- [`install.py`](install.py) — Install the built ``exactus`` executable system-wide.
- [`inventory.py`](inventory.py) — Share project-tree filtering between package and build_make scripts.
- [`inventory_cli.py`](inventory_cli.py) — ANSI-styled ``--help``/``-h`` output shared by the root scripts.
- [`partition_fs.py`](partition_fs.py) — Deterministic, streaming content-addressed filesystem bundles.
- [`partition_launcher.py`](partition_launcher.py) — Offline dependency-aware runtime for partitioned filesystem tools.
- [`process_control.py`](process_control.py) — Cross-invocation exactus ownership and process termination primitives.
- [`progress.py`](progress.py) — Uniform ``exactus-run/v1`` live-run progress document schema.
- [`readmes.py`](readmes.py) — Generate directory documentation for offline distribution assets.
- [`shims.py`](shims.py) — Generate ``exactus.vendor.<name>`` shims for bundled distributions.

### Subdirectories

- [`examples/`](examples/README.md) — Python API examples for the unified package pipeline.
- [`templates/`](templates/README.md) — Standalone Exactus package executable. Run from the project you want to check:

<!-- exactus:inventory:end -->
