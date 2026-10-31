# `exactus/packages/`

Vendored multi-use tools: self-contained packages reused by exactus.

[`todo_sync/`](todo_sync/README.md) synchronizes Markdown checklist progress,
generates an offline dashboard and provides an explicitly started watcher.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Package marker.
- [`__main__.py`](__main__.py) — Run every packages example and report each one's exit status.

### Subdirectories

- [`actions/`](actions/README.md) — Action editors behind authored flow actions: the shared pointer and touch frontend (`action_pointer`), JavaScript snippet runner (`action_javascript`), and REST/WebSocket request studio (`action_rest`).
- [`all_lints/`](all_lints/README.md) — Run project linters and merge their diagnostics into one JSON report.
- [`argument_parser/`](argument_parser/README.md) — `ExactusArgumentParser`: an `ArgumentParser` whose long options accept dashes and underscores interchangeably (`--dry-run` = `--dry_run`). Standalone, so any package can depend on it.
- [`browser/`](browser/README.md) — A Python 3.13 package that normalizes browser lifecycle notifications across Playwright-managed Chromium and a native Chrome/Chromium subprocess.
- [`completion/`](completion/README.md) — Shell completion for the `check` CLI: a grammar-aware Python engine behind a thin, generated shell adapter per supported shell.
- [`exactus_mcp/`](exactus_mcp/README.md) — Exactus MCP exposes the constrained Exactus report tools to ChatGPT through a stable Cloudflare Worker while the actual service remains bound to loopback on the local machine.
- [`extended_selector/`](extended_selector/README.md) — The selector **engine** and its structured formula editor. The expression widget that edits selectors in Studio lives in its own package, \[`widget_selector/`\](../widgets/widget_selector/README.md).
- [`external/`](external/README.md) — Bundled-toolchain surface behind `exactus --external`: with no tool name it renders the leaf manifest's OS/Python/Node version inventory; with `TOOL \[ARGS...\]` it forwards the command line to the offline partition launcher.
- [`group_final/`](group_final/README.md) — AST-based Python refactoring utility that groups safely movable module-level `Final` constants into a `Constants` class and updates Python references across the source tree.
- [`guard/`](guard/README.md) — Public API for process_guard.
- [`http_process/`](http_process/README.md) — A Python 3.13 package for starting processes, discovering TCP listeners owned by their process trees, verifying HTTP endpoints, and resolving local listener ownership.
- [`markdown/`](markdown/README.md) — Jinja2 Markdown template engine: renders Markdown reports from JSON through templates and mappings. The inventory below documents every direct file and child directory.
- [`meaningful/`](meaningful/README.md) — Public API for meaningful Python test-necessity analysis.
- [`model/`](model/README.md) — Structural SQLite statement, schema, and execution model: production application modules construct immutable schema, expression, and statement objects and pass them through the SQLite execution boundary instead of authoring SQL.
- [`organize/`](organize/README.md) — Public API for source-preserving Python and JavaScript class method organization.
- [`package/`](package/README.md) — Unified project build, bundle, and package pipeline.
- [`patcher/`](patcher/README.md) — Build and apply deterministic executable filesystem patches.
- [`performance/`](performance/README.md) — Analyze Exactus step traces and expose an interactive profiler.
- [`pmanager/`](pmanager/README.md) — `pmanager` is a Python 3.13 process manager with a symmetric typed configuration model, object-reference process graph API, detached cross-platform workers, lifecycle hooks, structured Python arguments, live status enrichment, and context/global broadcasts.
- [`project_python/`](project_python/README.md) — Shared interpreter bootstrap for repository scripts. Calling `switch_to_project_venv()` replaces a non-project Python process with `.venv/bin/python` (or `.venv/Scripts/python.exe` on Windows), while preserving the requested script and its arguments. It is a no-op when `.venv` is absent or already active. The top-level Exactus dispatcher, standalone tool modules, build/package scripts, `all_lints`, `group_final`, their examples, `rename_project`, and `watch` invoke it at their executable boundaries before loading command implementations, so manual activation is not required:
- [`rename_project/`](rename_project/README.md) — Rename a project in one safe, reviewable step: the root directory, the files and folders named after it, and every mention of its name inside text files, each restyled to match how it was written. Optionally renames the GitHub repository too.
- [`scene_description/`](scene_description/README.md) — Rendered semantic scene descriptions and Visual Cause integration.
- [`screenshot/`](screenshot/README.md) — This package owns screenshot acquisition and image similarity comparison. Browser recording, crawling, diagnostics, and replay live in `exactus.tools.record`. The `exactus.tools.frontend` exactus combines both engines in device/theme lanes.
- [`server/`](server/README.md) — Loopback web-server lifecycle used by the screenshot shortcuts (`--server` and `--entrypoint`) in `exactus/__main__.py`.
- [`shebang_update/`](shebang_update/README.md) — Update Python virtual-environment shebangs to the current project path.
- [`steps/`](steps/README.md) — Timestamped step tracing shared by the Exactus packages.
- [`todo_sync/`](todo_sync/README.md) — Adapted from the supplied `sync_todo.py`: a reusable, standard-library-only package with no dependency on `vm_image_manager`, Exactus runtime, npm, or the network. It never infers completion or changes checkboxes.
- [`tree/`](tree/README.md) — Render directories, `.zip` archives and explicit path lists as `TREE.txt`-style listings (name + aligned size + modified date).
- [`visual_cause/`](visual_cause/README.md) — A causal visual CSS differential analyzer.
- [`watch/`](watch/README.md) — Provide init py content.
- [`widgets/`](widgets/README.md) — Self-rendering browser widgets that Studio and other pages mount (`widget_clock`, `widget_console`, `widget_selector`, `widget_styles`).
- [`zip_components/`](zip_components/README.md) — Create source-bundle archives of exactus tools and packages packages.
- [`zstd_portable/`](zstd_portable/README.md) — Portable Zstandard CLI wrapper with lazy zipped-binary extraction. Ships compressed `zstd` binaries under `bin/` per platform and extracts the matching one on first use, so callers get a real `zstd` executable without a system install.

<!-- exactus:inventory:end -->
