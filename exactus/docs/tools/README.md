# `tools/`

The canonical exactus tools and the shared runtime that orchestrates
them. Everything a user runs via `exactus --tool`/`--pipeline` lives
here.

## Shared runtime modules

| File | Description |
|---|---|
| `execution.py` | Shared standalone entry-point reporting used by tool `main()` functions. |
| `api.py` | Process-isolated Python API for invoking the canonical tools programmatically. |
| `catalog.py` | The canonical tool and pipeline catalog — tool identities, pipelines (`self`, `all-fast`, `unified`) and recipe wiring. |
| `models.py` | Shared orchestration models: tool specs, pipeline plans, run manifests. |
| `registry.py` | Cross-process run registry backed by an embedded database (`EXACTUS_RESULTS/.runtime/runs.db`), bounded by `runtime_max_runs`/`runtime_max_size`. |
| `runtime.py` | Shared runtime state, progress and the summary protocol. |

## Tool subpackages

| Folder | Tool | Purpose |
|---|---|---|
| [`actions/`](actions/README.md) | — | Action-recipe orchestration shared by record, frontend and Studio discovery/replay. |
| [`common/`](common/DOCS.md) | — | Shared leaf primitives, config, envelope, templates, terminal, snippets — imported by every tool. |
| [`completion/`](completion/README.md) | — | Shell-completion wiring on top of `exactus/packages/completion`. |
| [`coverage_tests/`](coverage_tests/DOCS.md) | `coverage-tests` | Run the project's tests once for combined coverage and test reports. |
| [`docs/`](docs/DOCS.md) | `docs` | Audit Python docstrings and JavaScript JSDoc coverage. |
| [`frontend/`](frontend/DOCS.md) | `frontend` | Execute saved Studio workflows and report functional frontend evidence. |
| [`kwargs_typehints/`](kwargs_typehints/DOCS.md) | `kwargs-typehints` | Enforce keyword-call policy, import style and explicit typing. |
| [`lints/`](lints/DOCS.md) | `lints` | Clean, lint and type-check sources with rollback. |
| [`performance/`](performance/DOCS.md) | `performance` | Profile the step traces recorded by earlier waves and export the performance dashboard. |
| [`readme/`](readme/DOCS.md) | `readme` | Audit per-directory README documentation inventories. |
| [`record/`](record/DOCS.md) | `record` | Record, replay and audit browser sessions. |
| [`reports/`](reports/DOCS.md) | — | Write consistent Markdown/JSON/offline-web report bundles and render normalized `result.json` through tool templates. |
| [`self_test/`](self_test/DOCS.md) | `self_test` | Probe every tool reachable by the executable and report which source answered. |
| [`visual_cause/`](visual_cause/DOCS.md) | `visual-cause` | Rank the DOM/CSS changes most likely responsible for a visual difference. |

The `performance` tool wraps the generic
[`exactus/packages/performance`](../../packages/performance/DOCS.md)
package; pipelines run it last with `--no-serve` so it exports
`EXACTUS_RESULTS/PERFORMANCE` from the step traces collected by the
earlier waves.

## Invariants

- Every tool produces the normalized envelope
  (`tool`/`run`/`invocation`/`environment`/`gate`/`artifacts`/`summary`/
  `scope`/`findings`/`extension`) via `common/envelope.py`.
- All tools accept the same orchestration interface; `catalog.py` is the
  single source of truth for what exists and how it is invoked.
- Catalog dependencies are scheduled only by the pipeline supervisor —
  a tool starts once its dependencies settle, whether they passed or
  failed with findings. Worker specifications never declare pmanager
  `depends_on` refs, because pmanager would abort a dependent when a
  dependency process exits nonzero (a normal lint `FAIL`).
- Pipeline GLOBAL progress is the mean of per-tool fractions. A settled
  tool re-run externally is requeued and its share drops to the new
  run's live progress (finished dependents are invalidated too); an
  adopted run superseded by a newer `run_id` resets the same way, so
  GLOBAL regresses and refills with the newest run.
- Source discovery never relies on the results-root name: report trees
  are pruned by fingerprint (`is_reports_tree` in `common/cli.py`), so
  renamed `output_dir` roots and nested fixture outputs are skipped.
- Generic packages elsewhere in `exactus` must not import from here —
  the dependency direction is always `tools` → generic.

<!-- exactus:inventory:start -->
## Directory contents

### Files

No direct files besides this README.

### Subdirectories

- [`actions/`](actions/README.md) — No subdirectories.
- [`common/`](common/README.md) — No subdirectories.
- [`completion/`](completion/README.md) — Exactus-specific shell-completion wiring on top of `exactus/packages/completion`.
- [`coverage_tests/`](coverage_tests/README.md) — No subdirectories.
- [`docs/`](docs/README.md) — No subdirectories.
- [`frontend/`](frontend/README.md) — No subdirectories.
- [`kwargs_typehints/`](kwargs_typehints/README.md) — No subdirectories.
- [`lints/`](lints/README.md) — No subdirectories.
- [`performance/`](performance/README.md) — Documentation for the `performance` exactus tool, which wraps the generic `exactus/packages/performance` analyzer with project-measured defaults, step tracing, and the normalized report bundle.
- [`readme/`](readme/README.md) — No subdirectories.
- [`record/`](record/README.md) — No subdirectories.
- [`reports/`](reports/README.md) — No subdirectories.
- [`self_test/`](self_test/README.md) — The executable's self-diagnostic catalog tool, exposed as `exactus --self_test`. The flag is hidden on normal builds; only executables built with `--build-self-test` carry the marker that enables it.
- [`visual_cause/`](visual_cause/README.md) — Documentation for \[`exactus/tools/visual_cause/`\](../../../../tools/visual_cause).

<!-- exactus:inventory:end -->
