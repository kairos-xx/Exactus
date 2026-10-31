# tools/frontend/

The `frontend` tool: executes saved Studio workflows with the shared
functional test executor and reports durable browser evidence.

## Files

| File | Description |
|---|---|
| `arguments.py` | The frontend grammar, declared without importing the execution engine. |
| `core.py` | Executes Studio workflows through the shared functional test executor (the `exactus.record` engine). |
| `main.py` | Entry: run workflows and emit the FRONTEND report bundle. |
| `progress.py` | Publishes real frontend work into the shared tool heartbeat. |
| `report.py` | Normalize frontend execution evidence for Markdown and web reports. |
| `templates/` | Tool-specific Markdown template/mapping. |

## Behavior

- Runs `.exactus` Studio flows headlessly as functional tests, producing
  JUnit-style results, screenshots and browser diagnostics per flow.
- `progress.py` streams heartbeat/progress so the orchestrator and
  Studio see live state rather than a silent run.
- `report.py` normalizes per-flow status (passed/failed/cancelled/
  skipped) into the shared envelope so the FRONTEND report renders like
  every other tool.
- Orchestrator-only options (e.g. `clear`) are filtered out before the
  tool's argv reaches the executor.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Frontend exactus tool. |
| `arguments.py` | Declare the frontend grammar without importing its execution engine. |
| `core.py` | Exactus saved Studio workflows with the shared functional test executor. |
| `main.py` | Execute Studio workflows and report functional frontend evidence. |
| `progress.py` | Publish real frontend work into the shared tool heartbeat. |
| `report.py` | Normalize frontend execution evidence for Markdown and web reports. |
| `templates/` | Subdirectory. |

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--actions` | Actions recipe orchestrating discovery and replay. | type=Path |
| `--url` | Optional initial application URL. |  |
| `--workspace` | Studio project to execute. | type=Path |
| `--flow` | Optional workflow entry flow ID. |  |
| `--width` |  | type=int, default=1440 |
| `--height` |  | type=int, default=1000 |
| `--scale` |  | type=float, default=1.0 |
| `--timeout-ms` |  | type=float, default=5000 |
| `--headed` |  | action='store_true' |
| `--workers` | Concurrent workflow visits; use 1 for serial execution. | type=int, default=4 |
| `--server-log` |  | type=Path |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Frontend exactus tool.


### `arguments.py`

Declare the frontend grammar without importing its execution engine.

- `create_parser() -> ArgumentParser` — Create parser.

### `core.py`

Exactus saved Studio workflows with the shared functional test executor.

- `class FrontendFinding` — Describe an execution or browser diagnostic failure.
  - `severity` = `'error'`
  - `line` = `None`
  - `column` = `None`
  - `function` = `''`
  - `stack` = `''`
  - `flow` = `''`
  - `action` = `''`
  - `phase` = `''`
  - `category` = `''`
  - Fields: `rule: str`, `file: str`, `message: str`
- `class FrontendExactusInput` — Configure execution of a Studio project.
  - `url` = `None`
  - `workspace` = `None`
  - `flow_id` = `None`
  - `width` = `1440`
  - `height` = `1000`
  - `scale` = `1.0`
  - `timeout_ms` = `5000`
  - `color_scheme` = `'light'`
  - `is_mobile` = `False`
  - `has_touch` = `False`
  - `cancelled` = `None`
  - `emit` = `None`
  - `headless` = `True`
  - `server_log` = `None`
  - `workers` = `4`
  - Fields: `output: Path`
- `class FrontendExactusResult` — Collect workflow execution and exactus findings.
  - Fields: `findings: tuple[FrontendFinding, ...]`, `options: FrontendExactusInput`, `execution: dict[str, JsonValue]`, `server_diagnostics: tuple[JsonValue, ...]`, `elapsed_seconds: float`
- `frontend(*, inputs: FrontendExactusInput) -> FrontendExactusResult` — Execute saved flows and capture only their requested screenshots.
- `report_data(*, result: FrontendExactusResult) -> dict[str, JsonValue]` — Build dynamic report data from the shared execution evidence.
- `markdown_report(*, result: FrontendExactusResult) -> str` — Render execution results with JavaScript responses and assertions.

### `main.py`

Execute Studio workflows and report functional frontend evidence.

- `create_parser() -> ArgumentParser` — Return the shared CLI grammar used by execution and completion.
- `parse_args(*, arguments: tuple[str, ...] | None=None) -> Namespace` — Parse args.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Return main.

### `progress.py`

Publish real frontend work into the shared tool heartbeat.

- `class FrontendProgress` — Track Actions phases while reserving completion for report writing.
  - `actions` = `1`
  - `index` = `-1`

### `report.py`

Normalize frontend execution evidence for Markdown and web reports.

- `objects(*, value: JsonValue) -> list[dict[str, JsonValue]]` — Read object rows without interpreting missing evidence as success.
- `artifact_path(*, value: JsonValue, output: Path) -> str` — Resolve evidence after the runner moves auxiliary files to ARTIFACTS.
- `normalized_data(*, payload: Mapping[str, JsonValue], output: Path) -> dict[str, JsonValue]` — Add summary, findings, scope and execution tables to raw evidence.

## Dependencies and consumers

- Other packages: [`argument_parser`](../../packages/argument_parser/DOCS.md), [`project_python`](../../packages/project_python/DOCS.md), [`server`](../../packages/server/DOCS.md), [`steps`](../../packages/steps/DOCS.md), [`common`](../common/DOCS.md), [`reports`](../reports/DOCS.md)
- Used by: `__main__.py`, `tests/tools/frontend/test_frontend.py`, `tests/tools/frontend/test_frontend_progress.py`, `tests/tools/frontend/test_frontend_report.py`, `tools/actions/runner.py`

## Tests

Tests live in `exactus/tests/tools/frontend/`.

- `test_frontend.py` — Verify FRONTEND uses normal Studio projects and their capture policies. (6 tests)
  - `test_configured_recipe_and_explicit_project`
  - `test_flow_capture_policy_and_response`
  - `test_frontend_cli_runs_recipe_and_writes_report`
  - `test_frontend_legacy_markdown_retains_step_response`
  - `test_parser_accepts_workspace_without_url`
  - `test_url_only_has_no_implicit_screenshots`
- `test_frontend_progress.py` — Frontend progress uses completed work and ignores repeated attempts. (3 tests)
  - `test_parallel_progress_waits_for_all_workers_and_counts_retries_once`
  - `test_recipe_progress_advances_through_discovery_and_replay`
  - `test_replay_counts_retries_once`
- `test_frontend_report.py` — Frontend reports retain execution outcomes and readable evidence. (4 tests)
  - `test_artifact_paths_follow_organized_output`
  - `test_empty_frontend_execution_does_not_claim_success`
  - `test_findings_group_browser_failures_by_flow`
  - `test_frontend_report_explains_diagnostics_and_steps`
- `test_parallel_flows.py` — Verify concurrent real-browser replay and ordered workflow evidence. (2 tests)
  - `test_parallel_flows_overlap_and_preserve_isolation_and_order`
  - `test_workers_must_be_positive`

<!-- exactus:reference:end -->
