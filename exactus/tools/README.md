# `exactus/tools/`

Exactus orchestration lives here: API, entrypoint, catalog, models, registry,
and runtime. Reusable leaf helpers live in [common/](common/README.md).
Report delivery and template rendering live in [reports/](reports/README.md).
Tool analysis and entrypoints remain in their respective packages.

## Directory contents

### Files

#### `__init__.py`

Exactus tool package marker.

#### `_entrypoint.py`

Shared standalone exactus entry-point reporting. Every run writes
`ARTIFACTS/@activity.json` (refreshed each second, finalized on success,
failure, signal and worker crash), `ARTIFACTS/stderr.log`
and `ARTIFACTS/stdout.log`. Public API: `ExactusEntrypointTables` — Store common standalone exactus CLI constants.; `ExactusRunIds` — Run identifiers injected by an orchestrating pipeline.; `FallbackResult` — Everything a fallback report needs to render the full run.; `execute_exactus()` — Return execute exactus.; `CrashDetails` — Facts describing a worker process that died before reporting.; `crashed_exactus()` — Record a run whose worker process ended before reporting.; `run_exactus()` — Return run exactus.

#### `api.py`

Process-isolated Python API for canonical exactus tools. Public API: `ExactusApi` — Represent exactus api.

#### `catalog.py`

Canonical exactus tool and pipeline catalog. Public API: `ToolSpec` — Describe one canonical executable exactus tool.; `PipelineSpec` — Describe one non-executable orchestration pipeline.; `Catalog` — Resolve canonical tools and pipelines without duplicate execution.; `validate_scripts()` — Validate scripts.

#### `models.py`

Shared exactus orchestration models. Public API: `ToolRequest` — Describe one tool execution requested by the orchestrator.; `ToolRunResult` — Describe the completed outcome of one tool execution.; `ToolActivity` — Describe live progress of one tool inside a pipeline run.; `PipelineActivity` — Describe live progress of one pipeline run.

#### `registry.py`

Cross-process exactus run registry backed by an embedded database. Public API: `RegistryTables` — Static schema and lookup values for the run registry.; `RunClaim` — Ownership facts registered by one starting run.; `RunBeat` — Optional progress fields refreshed by one heartbeat.; `RunRecord` — One registered exactus run row.; `RunRegistry` — Shared exactus-run registry persisted in an embedded database.

#### `runtime.py`

Shared exactus runtime state, progress, and summary protocol. Public API: `emit_progress()` — Publish progress for standalone and orchestrated execution.; `LaneProgress` — Run-wide completed-unit counter shared by parallel lanes.

### Subdirectories

#### `common/`

Leaf primitives shared by every tool (`sprint.py`, `process_control.py`,
`json_types.py`, `envelope.py`, the `@activity.json` schema in
`activity.py` and the `stderr.log` capture in `stderr_capture.py`) plus
the shared report assets in `templates/`. See `common/README.md`.

#### `coverage_tests/`

Run the project's tests once for combined coverage and test reports (tool `coverage-tests`, aliases `coverage` and `tests`). Holds `main.py` (CLI entry point), `core.py` (analysis) and `__init__.py`. See `coverage_tests/README.md`.

#### `docs/`

Exactus Python docstrings and JavaScript JSDoc. Holds `main.py` (CLI entry point), `core.py` (analysis), `__init__.py` and `templates/` (report template and mapping). See `exactus/docs/README.md`.

#### `kwargs_typehints/`

Exactus keyword usage, imports, and explicit type hints. Holds `main.py` (CLI entry point), `core.py` (analysis), `report.py` (normalized report data), `templates/` (the `result.md` template) and `__init__.py`. See `kwargs_typehints/README.md`.

#### `lints/`

Run the combined lint exactus and emit the LINTS report bundle. Holds `main.py` (CLI entry point), `core.py` (analysis) and `__init__.py`. See `lints/README.md`.

#### `record/`

Record interactive browser actions into a normalized Playwright program. Holds `main.py` (CLI entry point), `core.py` (analysis) and `__init__.py`. See `record/README.md`.

#### `readme/`

Exactus per-directory README documentation inventories. Holds `main.py` (CLI entry point), `core.py` (analysis), `__init__.py` and `templates/` (report template and mapping). See `readme/README.md`.

#### `screenshot/`

Exactus application screenshots across device and theme lanes. Holds `main.py` (CLI entry point), `core.py` (analysis) and `__init__.py`. See `screenshot/README.md`.
- `frontend/` — Subdirectory.



## Entry points

Every tool main is a standalone script and a package module:

```bash
python exactus/tools/lints/main.py --help
python -m exactus.tools.lints.main --help
python -m exactus --lints --help
```

#### `reports/`

Shared Markdown, JSON, and web report generation. See [reports/README.md](reports/README.md).

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Canonical exactus tools and shared runtime for project exactuss.
- [`__main__.py`](__main__.py) — Run every tool example and report each one's exit status.

### Subdirectories

- [`actions/`](actions/README.md) — Execute ordered discovery and exactus tools from JSON or TOML recipes, resolving named outputs without shell interpolation. Actions is an integration package: it composes recording, server startup, the exactus API, and report generation. Flow Studio may import this package.
- [`common/`](common/README.md) — Leaf primitives shared by every exactus tool. Modules here import only the standard library and each other, never another part of the repository, so any tool, script or test can depend on them without cycles.
- [`completion/`](completion/README.md) — Exactus-specific completion wiring on top of ``exactus.packages.completion``.
- [`coverage_tests/`](coverage_tests/README.md) — The `coverage-tests` exactus tool (aliases `coverage` and `tests`): a standalone entry point (`main.py`) and its analysis core (`core.py`). One pytest run (plus the `node:test` lane) produces both the coverage report and the test reports. The inventory below documents every direct file.
- [`docs/`](docs/README.md) — Docs analyzes Python docstrings and JavaScript JSDoc. Its metrics describe analyzed source files, lines, symbols and documentation coverage. Markdown and README inventories and sizes are reported by readme.
- [`frontend/`](frontend/README.md) — Execute a normal Studio project or an Actions recipe and organize its functional results, JavaScript responses, assertions and browser/server diagnostics. Screenshots are captured only when requested by the flow.
- [`kwargs_typehints/`](kwargs_typehints/README.md) — The `kwargs-typehints` exactus tool: a standalone entry point (`main.py`), its analysis core (`core.py`), the normalized report data (`report.py`) and the report template (`templates/`). A run writes `result.json`, `result.md` (rendered from `templates/markdown/`), `result_web/` and `ARTIFACTS/heuristics.json` (argument types observed by fuzzing builtin callables) next to the common `ARTIFACTS/stderr.log` and `@activity.json`. The inventory below documents every direct file and child directory.
- [`lints/`](lints/README.md) — Lints includes the CMP engineering rules for source parsing, diagnostic suppressions, typing escape hatches and lint/type-check configuration. These checks run as `custom_compliance` in the LINTS report, with finding excerpts, rule counts and deltas. There is no separate compliance command or report.
- [`performance/`](performance/README.md) — The `performance` exactus tool instruments the generic `exactus/packages/performance` analyzer against this project. It scans `EXACTUS_RESULTS` for the `steps.txt` traces each analyzer writes under `ARTIFACTS/`, prints a compact per-run bottleneck summary, writes the normalized report bundle (`result.md`, `result.json`, `result_web/`), and exports the interactive dashboard into `ARTIFACTS/`. `--no-serve` (the pipeline default) exports and exits; without it the run serves the dashboard and opens it in the managed browser.
- [`readme/`](readme/README.md) — README reports own Markdown file, byte and line totals, README counts and largest/smallest sizes, and source directories without a README. These metrics follow the README include/exclude rules.
- [`record/`](record/README.md) — Record owns action recording, replay, crawler discovery and functional execution. The browser editor and its HTTP service live in `studio/`. PNG capture and visual comparison live in `exactus.packages.screenshot`.
- [`reports/`](reports/README.md) — Shared report delivery and template rendering. This package may depend on `exactus.packages.markdown` and `exactus.tools.common`; the leaf `common` package must never import it. Shared templates remain in \[../common/templates/\](../common/templates/README.md).
- [`self_test/`](self_test/README.md) — The `exactus --self_test` self-diagnostic. Generates a seven-file fixture project in a temporary directory, probes every expected tool — the system-installed executable on `PATH` first, the pyz's bundled toolchain as fallback — then runs the `unified` pipeline against the fixture and verifies every `EXACTUS_RESULTS` report is fresh, PASS, and issue-free. Writes the standard `EXACTUS_RESULTS/SELF_TEST` report bundle and leaves nothing outside the temp tree.
- [`visual_cause/`](visual_cause/README.md) — Compare pages or stylesheet variants at one or more viewports, explain the changed elements, classify them with ExtendedSelector queries, and write the standard Exactus Markdown, JSON, web, and artifact bundle.

<!-- exactus:inventory:end -->


