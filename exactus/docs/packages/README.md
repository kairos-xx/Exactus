# `exactus/packages/`

First-party and extracted-utility packages maintained in the repository. Each package is self-contained, ships its own README and tests, and is audited by the same lint pipeline as `exactus/` code.

<!-- exactus:inventory:start -->
## Directory contents

### Files

No direct files besides this README.

### Subdirectories

- [`actions/`](actions/README.md) — Action packages hold the interactive editors behind authored flow actions: a shared pointer and touch frontend, a JavaScript snippet runner, and a REST/WebSocket request studio. `action_javascript` is self-rendering and mounts on a carrier element; `action_rest` binds to the DOM contract of its host page.
- [`all_lints/`](all_lints/README.md) — Run project linters and merge their diagnostics into one JSON report.
- [`argument_parser/`](argument_parser/README.md) — Documentation for \[`exactus/packages/argument_parser/`\](../../../packages/argument_parser).
- [`browser/`](browser/README.md) — `BrowserLifecycle` owns lifecycle observation and callback dispatch.
- [`completion/`](completion/README.md) — No subdirectories.
- [`exactus_mcp/`](exactus_mcp/README.md) — Exactus MCP exposes the constrained Exactus report tools to ChatGPT through a stable Cloudflare Worker while the actual service remains bound to loopback on the local machine.
- [`extended_selector/`](extended_selector/README.md) — `ExtendedSelector` is a browser-native, dependency-free DOM and visual query engine that extends ordinary CSS selection with predicates, boolean algebra, structural relations, geometry, viewport state, scrolling, stacking order, Shadow DOM, slots, pseudo-element style inspection, extensibility hooks, diagnostics, compilation, and a structured formula-style frontend editor.
- [`external/`](external/README.md) — Bundled-toolchain listing and dispatch, exposed as `exactus --external`.
- [`group_final/`](group_final/README.md) — AST-based refactoring that groups safely movable module-level `Final` constants into a `Constants` class and updates references across the source tree.
- [`guard/`](guard/README.md) — `exactus.packages.guard` is a Python 3.13 process-tree supervisor for code that must not leave subprocesses running after the owning operation finishes.
- [`http_process/`](http_process/README.md) — Start processes, discover TCP listeners owned by their process trees, verify HTTP endpoints, and resolve local listener ownership.
- [`markdown/`](markdown/README.md) — No subdirectories.
- [`meaningful/`](meaningful/README.md) — `exactus.packages.meaningful` is a Python-first semantic analyzer that estimates how strongly each Python source file warrants dedicated tests. The CLI is a thin adapter over the same object-oriented Python API and data model.
- [`model/`](model/README.md) — This project uses a dependency-free structural SQLite layer instead of handwritten application SQL.
- [`organize/`](organize/README.md) — `exactus.packages.organize` reorders direct methods in Python classes into a deterministic semantic layout while preserving the original method source text. It uses the Python AST only to discover and classify definitions; it does **not** regenerate methods with `ast.unparse()`.
- [`package/`](package/README.md) — `exactus.packages.package` is the unified release pipeline for the existing Exactus build, bundle and package operations. It exposes the same three stages through Python, CLI and `pyproject.toml` and always executes selected stages in this order:
- [`patcher/`](patcher/README.md) — `exactus.packages.patcher` builds deterministic executable `.pyz` filesystem deltas and applies them transactionally.
- [`performance/`](performance/README.md) — `exactus.packages.performance` turns timestamped `exactus.packages.steps` traces into an immutable performance model and an interactive browser profiler. It is designed for Exactus result trees but also accepts individual `steps.txt` files.
- [`pmanager/`](pmanager/README.md) — Python 3.13 process manager with a symmetric typed configuration model, object-reference process graph API, detached cross-platform workers, lifecycle hooks, structured Python arguments, live status enrichment, and context/global broadcasts.
- [`project_python/`](project_python/README.md) — Shared interpreter bootstrap for repository scripts.
- [`rename_project/`](rename_project/README.md) — Renames a project in one safe, reviewable step: the root directory, the files and folders named after it, and every mention of its name inside text files — each restyled to match how the name was written (lower, upper, snake, kebab, camel and title variants). Optionally renames the GitHub repository too.
- [`scene_description/`](scene_description/README.md) — Rendered semantic scene descriptions and Visual Cause integration: captures a semantic scene graph from a rendered page, describes deterministic A/B differences between two scenes in human-readable language, and enriches an existing Visual Cause report with those descriptions.
- [`screenshot/`](screenshot/README.md) — No subdirectories.
- [`server/`](server/README.md) — No subdirectories.
- [`shebang_update/`](shebang_update/README.md) — Update Python virtual-environment shebangs to the current project path.
- [`steps/`](steps/README.md) — Timestamped step tracing shared by the Exactus packages: one `timestamp +elapsed step` line per event in a plain text file.
- [`todo_sync/`](todo_sync/README.md) — Reusable, standard-library-only TODO-list synchronizer with no dependency on the Exactus runtime, npm, or the network. It never infers completion or changes checkboxes.
- [`tree/`](tree/README.md) — Documentation for \[`exactus/packages/tree/`\](../../../packages/tree).
- [`visual_cause/`](visual_cause/README.md) — Documentation for \[`exactus/packages/visual_cause/`\](../../../packages/visual_cause).
- [`watch/`](watch/README.md) — Project-local recursive filesystem watcher that mirrors source changes into a destination tree and records destination activity.
- [`widgets/`](widgets/README.md) — Widgets are self-rendering browser components that Studio and ordinary pages mount. Each ships its own ES modules, a token-driven stylesheet and a runnable demo, and none depends on Studio.
- [`zip_components/`](zip_components/README.md) — `exactus.packages.zip_components` creates source-bundle archives of exactus tools and packages packages: each component's sources, tests and docs plus the shared skeleton files, unzippable back onto a repository root.
- [`zstd_portable/`](zstd_portable/README.md) — Portable Zstandard CLI wrapper with lazy zipped-binary extraction. Ships compressed `zstd` binaries under `bin/` per platform and extracts the matching one on first use, so callers get a real `zstd` executable without a system install.

<!-- exactus:inventory:end -->

## Package index

Every package has `exactus/docs/packages/<name>/DOCS.md`; the `actions` and `widgets` groups hold their members in subfolders.

| Package | Description |
|---|---|
| [`actions/action_javascript`](actions/action_javascript/DOCS.md) | Reusable, self-rendering JavaScript snippet runner |
| [`actions/action_rest`](actions/action_rest/DOCS.md) | Reusable browser request-studio controller with a standalone browser demo. |
| [`all_lints`](all_lints/DOCS.md) | Run project linters and merge their diagnostics into one JSON report. |
| [`browser`](browser/DOCS.md) | A Python 3.13 package that normalizes browser lifecycle notifications across Playwright-managed Chromium and a native Chrome/Chromium subprocess. |
| [`completion`](completion/DOCS.md) | Grammar-aware shell autocomplete for exactus |
| [`exactus_mcp`](exactus_mcp/DOCS.md) | Bearer-protected Streamable HTTP Exactus MCP service with an ngrok public connection page. |
| [`extended_selector`](extended_selector/DOCS.md) | The selector engine and its structured formula editor. |
| [`group_final`](group_final/DOCS.md) | AST-based refactoring that groups safely movable module-level Final constants into a Constants class and updates references across the source tree. |
| [`guard`](guard/DOCS.md) | exactus.packages.guard is a Python 3.13 process-tree supervisor for code that must not leave subprocesses running after the owning operation finishes. |
| [`http_process`](http_process/DOCS.md) | Start processes, discover TCP listeners owned by their process trees, verify HTTP endpoints, and resolve local listener ownership. |
| [`markdown`](markdown/DOCS.md) | The generic Markdown report engine |
| [`meaningful`](meaningful/DOCS.md) | exactus.packages.meaningful is a Python-first semantic analyzer that estimates how strongly each Python source file warrants dedicated tests. |
| [`model`](model/DOCS.md) | This project uses a dependency-free structural SQLite layer instead of handwritten application SQL. |
| [`organize`](organize/DOCS.md) | exactus.packages.organize reorders direct methods in Python classes into a deterministic semantic layout while preserving the original method source text. |
| [`package`](package/DOCS.md) | exactus.packages.package is the unified release pipeline for the existing Exactus build, bundle and package operations. |
| [`patcher`](patcher/DOCS.md) | exactus.packages.patcher builds deterministic executable .pyz filesystem deltas and applies them transactionally. |
| [`performance`](performance/DOCS.md) | exactus.packages.performance turns timestamped exactus.packages.steps traces into an immutable performance model and an interactive browser profiler. |
| [`pmanager`](pmanager/DOCS.md) | pmanager is a Python 3.13 process manager with a symmetric typed configuration model, object-reference process graph API, detached cross-platform workers, lifecycle hooks, structured Python arguments, live status enrichment, and context/global broadcasts. |
| [`project_python`](project_python/DOCS.md) | Shared interpreter bootstrap for repository scripts. |
| [`rename_project`](rename_project/DOCS.md) | Renames a project in one safe, reviewable step |
| [`scene_description`](scene_description/DOCS.md) | Rendered semantic scene descriptions and Visual Cause integration |
| [`screenshot`](screenshot/DOCS.md) | Screenshot capture script package: capture pages with arbitrarily nested overflow fully exposed, and score image similarity perceptually. |
| [`server`](server/DOCS.md) | Loopback web-server lifecycle helpers for the screenshot shortcuts, plus parsing of captured server output into reportable diagnostics. |
| [`shebang_update`](shebang_update/DOCS.md) | Update Python virtual-environment shebangs to the current project path. |
| [`steps`](steps/DOCS.md) | Timestamped step tracing shared by the Exactus packages: one timestamp +elapsed step line per event in a plain text file. |
| [`todo_sync`](todo_sync/DOCS.md) | Reusable, standard-library-only TODO-list synchronizer with no dependency on the Exactus runtime, npm, or the network. |
| [`tree`](tree/DOCS.md) | exactus.packages.tree renders directories, .zip archives and explicit path lists as the same tree format exactus/scripts/inventory writes to TREE.txt |
| [`visual_cause`](visual_cause/DOCS.md) | exactus.packages.visual_cause renders one page under two CSS targets (or two whole pages), performs counterfactual browser interventions — removing or restoring individual rules, declarations and value subexpressions — and reports which CSS actually caused each visual difference, with pixel evidence. |
| [`watch`](watch/DOCS.md) | Project-local recursive filesystem watcher that mirrors source changes into a destination tree and records destination activity. |
| [`widgets/widget_clock`](widgets/widget_clock/DOCS.md) | exactus.packages.widgets.widget_clock is a reusable browser widget package. |
| [`widgets/widget_console`](widgets/widget_console/DOCS.md) | Reusable, self-rendering console widget |
| [`widgets/widget_selector`](widgets/widget_selector/DOCS.md) | The selector expression widget |
| [`widgets/widget_styles`](widgets/widget_styles/DOCS.md) | Shared CSS kit for widgets. |
| [`zip_components`](zip_components/DOCS.md) | exactus.packages.zip_components packages one or more exactus tools and/or packages packages into a single .zip whose members keep their repository-relative paths. |
| [`zstd_portable`](zstd_portable/DOCS.md) | Portable Zstandard CLI wrapper with lazy zipped-binary extraction. |

## Behavior

- Packages are checked in-tree; `exactus/packages/**` is never excluded from audits.
- Import roots that need resolution live on the checkers' `search-path` / `extraPaths` / `pythonpath` lists in `pyproject.toml`.
