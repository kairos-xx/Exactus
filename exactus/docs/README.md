# Exactus documentation

Implementation and acceptance work is tracked only in [TODO.md](todo/TODO.md).
These documents explain current interfaces and behavior.

## `exactus/` — the application

The Exactus application: user-facing tools, packaging scripts, and the
generated runtime-bundle namespaces that ship inside the executable.

| Directory | Description |
|---|---|
| `bundle/` | Generated per-platform tool-bundle namespaces staged by `build_make`. |
| `docs/` | This documentation mirror of the `exactus/` package tree. |
| `packages/` | First-party and extracted-utility packages: self-contained reusable libraries audited by the same lint pipeline as `exactus/` code. |
| `tests/` | Python and JavaScript test suites mirroring the packages and tools. |
| `tools/` | User-facing command implementations reached via `exactus <tool>`. |

- `exactus/__main__.py` lazily delegates `exactus <tool>` invocations to
  the matching `exactus.tools.<tool>` module.
- `bundle/` contents are generated artifacts — published catalogs and
  staged packs validated by `build_make`, not hand-edited sources.

<!-- exactus:inventory:start -->
## Directory contents

### Files

No direct files besides this README.

### Subdirectories

- [`bundle/`](bundle/README.md) — No subdirectories.
- [`packages/`](packages/README.md) — First-party and extracted-utility packages maintained in the repository. Each package is self-contained, ships its own README and tests, and is audited by the same lint pipeline as `exactus/` code.
- [`tests/`](tests/README.md) — The tests in `exactus/tests/bundle/` verify the small runtime layer that locates and exposes Exactus' generated platform bundle.
- [`tools/`](tools/README.md) — The canonical exactus tools and the shared runtime that orchestrates them. Everything a user runs via `exactus --tool`/`--pipeline` lives here.

<!-- exactus:inventory:end -->
