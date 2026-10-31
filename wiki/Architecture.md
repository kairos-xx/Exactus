[Home](Home.md) › Guides › Architecture

# Architecture

Exactus is a self-contained auditing executable. The whole application
is one Python package (`exactus/`) that can also be frozen into a
single-file zipapp carrying its own toolchain.

## Layers

```text
exactus/
├── __main__.py        dispatcher: tool flags, pipelines, orchestrator,
│                      EXACTUS_RESULTS tree, run registry, kill scripts,
│                      live progress, signal-safe cleanup
├── tools/             user-facing tools — per-tool main.py/arguments.py/
│                      core.py plus the shared runtime (api, catalog,
│                      models, registry, report_bundle, runtime, …) and
│                      the common/ leaf package
├── packages/          self-contained vendored libraries (browser,
│                      markdown, pmanager, project_python, server, …)
├── bundle/            generated per-platform offline tool bundles:
│                      bundle/<os>/<arch>/data/parts + content-addressed
│                      packs, lazily materialized on demand
├── docs/              DOCS.md mirror of this tree (one doc per leaf)
└── tests/             test suites mirroring packages/ and tools/
```

## Runtime model

- **Dispatch** — `exactus --lints` lazily maps to
  `exactus.tools.lints`. `python exactus`, `./bin/exactus` and
  `python build/` are equivalent entry points.
- **Shared runtime** — `exactus.tools.common` provides the process
  layer, pipeline supervisor, tool registry, report envelope
  (`summary`/`scope`/`findings`/`extension`), terminal progress and
  configuration precedence (defaults → `pyproject.toml` → env → CLI).
- **Vendored packages** — `exactus.packages.*` are reusable libraries
  audited by the same lint pipeline; `project_python` re-`exec`s into a
  project's `.venv` when invoked under a foreign interpreter.
- **Offline bundle** — when the host lacks a tool (ruff, node,
  playwright…), the partition launcher materializes it from
  `bundle/<os>/<arch>/` content-addressed packs and runs it under the
  executable's own interpreter.
- **Loopback server** — `exactus.server` hosts local pages for the
  browser-facing tools (record, frontend, visual_cause); nothing
  external is contacted.

## Report contract

Every tool writes the same normalized bundle under
`EXACTUS_RESULTS/<TOOL>/` — `result.md` + `result.json` + a rendered web
report, raw evidence under `ARTIFACTS/`, and an optional `FILES/`
archive of flagged sources. Reports diff against the previous run
(added / resolved / unchanged findings). See [Reports](Reports.md).

## Gate

A bare `exactus` is the single repository gate: it runs every enabled
tool and the pipelines and fails on the first blocking finding. The
repository rule — *never substitute separate ruff/basedpyright runs for
the gate* — is enforced by [AGENTS.md](../AGENTS.md).

---

[Installation](Installation.md) · [CLI](CLI.md) · [Architecture](Architecture.md) · [Reports](Reports.md) · [Testing](Testing.md) · [Releasing](Releasing.md) · [Conventions](Conventions.md)
