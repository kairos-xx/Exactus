# Bundle runtime

Runtime support for the packaged `exactus` executable.

- [`__init__.py`](__init__.py) — Package description.
- [`freshness.py`](freshness.py) — Fingerprint packaged sources and warn when a development executable is outdated.

The signature remains at the package root as `_signature.json`, so existing build stamps retain their format.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`CONTENT.md`](CONTENT.md) — Generated inventory of the offline tool payloads staged in this directory. Regenerate with `python exactus/scripts/bundle_make` (full source bundle) or `python exactus/scripts/build_make` (staged subset).
- [`__init__.py`](__init__.py) — Packaged executable fingerprints, freshness checks, and host routing.
- [`__main__.py`](__main__.py) — Dispatch ``python -m exactus.bundle`` to the host platform bundle.
- [`content.py`](content.py) — Render ``CONTENT.md`` inventories for staged bundle roots.
- [`freshness.py`](freshness.py) — Detect a packaged ``exactus`` that is older than its source tree.

### Subdirectories

- [`linux/`](linux/README.md) — Provide the generated tool-bundle namespace.
- [`macos/`](macos/README.md) — Provide @activity json content.
- [`windows/`](windows/README.md) — Provide the generated tool-bundle namespace.

<!-- exactus:inventory:end -->
