# `exactus/`

Self-contained exactus package. The inventory below documents
every direct file and child directory.

## Directory contents

### Files

#### `__main__.py`

Canonical CLI and orchestrator: tool dispatch, frontend shortcuts,
aggregated help, and staged pipelines. Public API: `Check` —
Coordinate canonical exactus tools and named pipelines.; `Tool` —
Describe a bundled command-line tool.; `ArgumentInfo` — Represent an
argument extracted from an ArgumentParser.; `Terminal` — Render
dependency-free terminal output.; `HelpRenderer` — Extract and render
help from child ArgumentParser instances.; `Application` — Dispatch
bundled command-line tools.; `tool_main` — Adapt a keyword-only tool
`main` to the dispatcher contract.; `main` — Run the bundled CLI
dispatcher.

### Directories

#### `tools/`

The exactus package: shared runtime plus one folder per tool (`main.py`
entrypoint, `core.py` analysis core, `__init__.py`, `README.md`), and the
shared leaf primitives and report templates under `common/`.

#### `screenshot/`

Screenshot acquisition, nested overflow expansion, and perceptual image
comparison. Browser exploration and diagnostics belong to `record/`.

#### `server/`

Loopback web-server lifecycle for the frontend shortcuts: the
embedded `--server` HTTP snippet with its identity ping, server
state files, free-port selection, readiness probing, and the
`--entrypoint` launcher.

#### `record/`

Browser action recording, crawling, diagnostics, reusable flow models, and
functional replay. `studio/` isolates the browser editor and local service.
The `frontend` exactus combines Record discovery with Screenshot image capture.


#### `bundle/`

Packaged-source fingerprints and executable freshness, plus generated
offline per-platform tool bundles under `bundle/<os>/<arch>/` used
automatically when the host lacks the exactus tools.

#### `markdown/`

Jinja2 Markdown template engine: renders Markdown reports from JSON
through templates and mappings, with its own exception tree.

#### `completion/`

Shell completion for the `check` CLI: a grammar-aware engine that
introspects the real argparse parsers, the hidden `__complete`
endpoint, per-shell registration-script renderers, and user-level
install/diagnose for Bash, Zsh, Fish, and PowerShell.
- `screenshot/` — Subdirectory.
- `bundle/` — Packaged executable fingerprints and freshness checks.
- `actions/` — Subdirectory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Exactus tooling, recording, and report generation.
- [`__main__.py`](__main__.py) — Run canonical exactus tools and staged pipelines through the Python API.

### Subdirectories

- [`bundle/`](bundle/README.md) — Runtime support for the packaged `exactus` executable.
- [`docs/`](docs/README.md) — Implementation and acceptance work is tracked only in \[TODO.md\](todo/TODO.md). These documents explain current interfaces and behavior.
- [`packages/`](packages/README.md) — Vendored multi-use tools: self-contained packages reused by exactus.
- [`tests/`](tests/README.md) — Repository-level tests for the toolkit itself. Top-level folders separate shared infrastructure, tools, reusable packages, bundle behavior, and demos.
- [`tools/`](tools/README.md) — Exactus orchestration lives here: API, entrypoint, catalog, models, registry, and runtime. Reusable leaf helpers live in \[common/\](common/README.md). Report delivery and template rendering live in \[reports/\](reports/README.md). Tool analysis and entrypoints remain in their respective packages.

<!-- exactus:inventory:end -->


