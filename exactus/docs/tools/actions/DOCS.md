# actions/

Executes declarative sequences of Exactus tool calls with named output
references. Recipes are JSON or TOML documents containing ordered calls;
each call may consume outputs produced by an earlier call.

Run a recipe with `python -m exactus.actions <recipe>`, through
`./exec/exactus --frontend --actions <recipe>`, or from Studio under
**Target & viewport → Actions recipe**.

## Files

  -----------------------------------------------------------------------
  File / path                         Description
  ----------------------------------- -----------------------------------
  `__init__.py`                       Package surface.

  `__main__.py`                       CLI entry: load a JSON/TOML recipe,
                                      orchestrate it, and report
                                      progress.

  `runner.py`                         Recipe parsing, validation, ordered
                                      execution, named output references,
                                      per-call output directories, and
                                      failure semantics.

  `process_control.py`                Vendored cross-invocation ownership
                                      and termination primitives.

  `conflict_copies.py`                Reconciles numbered synchronization
                                      copies without discarding unique
                                      data.

  `json_types.py`                     JSON value types used by recipe
                                      documents.

  `examples/`                         Shipped recipes, including crawler
                                      → record → frontend chains.
  -----------------------------------------------------------------------

## Model

-   Actions are orchestration data, not Studio projects. A recipe calls
    tools; a Studio project contains editable flows, timeline steps,
    assertions, and screenshot requests.
-   Recipes support JSON and TOML schema version `1`.
-   Calls execute in declaration order and IDs must be unique.
-   A call may reference outputs from an earlier completed call, for
    example `$discover.projects` or `$discover.server_log`.
-   References are resolved as data without shell interpolation. Invalid
    tools and forward references are rejected before execution.
-   Concrete arguments are validated before any call starts. Booleans
    are strict; crawl depth is 1--10, state count is 1--200, ports are
    0--65535, and viewport dimensions are integer pixels from 1--16384.
    Unknown arguments fail validation.
-   Each tool receives the selected root and its own output directory.
-   Ordinary recipes execute only the declared calls; pipeline
    dependencies are not expanded implicitly.
-   Setup failures stop the sequence while preserving failure evidence.
    A failed tool retains its result and report.
-   The runner uses the same process-control ownership rules as the
    orchestrator, so canonical termination interrupts recipe execution
    cleanly.
-   Recipes can live in a project and run independently of the recipe
    author's environment.

## Configuration

Frontend configuration selects an Actions recipe rather than an
application entrypoint:

``` toml
[tool.exactus.frontend]
actions = "demo/actions/frontend.json"
```

Configured paths resolve beside their `pyproject.toml`. An explicit
`--workspace` or `--url` replaces the configured recipe for that
invocation. Application entrypoint and port configuration belong to the
recipe's crawl call.

Run the same recipe directly or through the frontend orchestrator:

``` sh
python -m exactus.actions demo/actions/frontend.json \
  --output EXACTUS_RESULTS/ACTIONS

./exec/exactus --frontend --actions demo/actions/frontend.json
```

Studio can edit, import, export, and run the same JSON recipe. **Open
Actions report** opens its protected local report. The service owns an
application process launched by the recipe and stops it when execution
finishes.

## Recipe

A crawler-to-frontend recipe:

``` json
{
  "version": 1,
  "actions": [
    {
      "id": "discover",
      "tool": "record.crawl",
      "arguments": {
        "entrypoint": "server.py",
        "url": "http://127.0.0.1/",
        "port": 0,
        "screenshots": true,
        "server_errors": true,
        "javascript": ["() => document.title"],
        "max_depth": 2,
        "max_states": 20,
        "environments": [
          {"width": 390, "height": 844, "theme": "light"},
          {"width": 1440, "height": 900, "theme": "dark"}
        ]
      }
    },
    {
      "id": "verify",
      "tool": "frontend.run",
      "arguments": {
        "projects": "$discover.projects",
        "server_log": "$discover.server_log"
      }
    }
  ]
}
```

Entrypoints resolve relative to the recipe file when using the CLI and
relative to the selected project root in Studio. Port `0` selects an
available loopback port. Discovery and replay share the launched server.
Server stdout/stderr is retained in `server.log`; `server_errors`
controls promotion of server error diagnostics.

## Tools

### `record.crawl`

Discovers browser states and produces ordinary `.pwflow.json` Studio
projects. Supported controls include UI snapshots, `follow_links`,
`click_controls`, `include_selector`, depth/state limits, viewport/theme
`environments`, and explicit `javascript` expressions added to generated
flows.

UI snapshots are enabled by default. Each environment produces a project
at its configured viewport and theme with PNG assets stored inline. The
generated projects open directly in Studio and can be transferred as
single files. PNG imports verify SHA256, dimensions, and format before
writing.

### `frontend.run`

Replays generated projects at their respective viewport sizes and
themes. Its report contains workflow runs, action outcomes, JavaScript
responses, assertion evaluations, browser/server diagnostics, and
requested screenshots.

Discovery diagnostics remain separate from replay diagnostics. Aggregate
reporting groups repeated diagnostic causes while preserving independent
failed workflows.

### Catalog tools

Canonical Exactus tools can be called by catalog ID with an `argv` list:

``` json
{
  "id": "lint",
  "tool": "lints",
  "arguments": {
    "argv": ["--dry"]
  }
}
```

Catalog calls follow the same ordering, output-directory, validation,
failure, and process-control semantics as other recipe calls.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Run declarative sequences of tool calls with named output references. |
| `__main__.py` | Execute a saved JSON or TOML Actions recipe. |
| `conflict_copies.py` | Reconcile numbered sync copies without discarding unique project data. |
| `examples/` | Runnable demonstration for `exactus/tools/actions/`. |
| `json_types.py` | JSON value types shared by the exactus tools. |
| `process_control.py` | Cross-invocation exactus ownership and process termination primitives. |
| `runner.py` | Orchestrate discovery and functional exactuss from JSON or TOML actions. |

Run it as a module: `python -m exactus.tools.actions`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `specification` |  | type=Path |
| `--root` |  | type=Path |
| `--output` |  | type=Path, default=Path('EXACTUS_RESULTS/ACTIONS') |
| `--output` |  | type=Path, default=Path('.scratch/actions-example') |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Run declarative sequences of tool calls with named output references.


### `__main__.py`

Execute a saved JSON or TOML Actions recipe.

- `main() -> int` — Execute ordered tool calls and return their aggregate status.

### `conflict_copies.py`

Reconcile numbered sync copies without discarding unique project data.

- `class Constants` — Group module-level constants.
  - `ignored` = `frozenset({'.history', 'node_modules', 'venv', '__pycache__', 'exactus/pa...`
- `class ClearResult` — Describe reconciled sync copies and recoverable conflicts.
  - `removed_directories` = `0`
  - `merged_entries` = `0`
  - `preserved_conflicts` = `0`
  - `errors` = `0`
- `clear_conflict_copies(*, root: Path) -> ClearResult` — Reconcile numbered directories with existing canonical counterparts.

### `examples/__init__.py`

Demonstrate discovery followed by functional verification.


### `examples/__main__.py`

Run the Actions example.


### `examples/run.py`

Discover and verify a bundled page using a named-output Actions recipe.

- `main() -> int` — Serve the example page, run its recipe, and stop the owned server.

### `json_types.py`

JSON value types shared by the exactus tools.

- `class JsonDict` — Dictionary with a formatted JSON representation.
  - `tojson(self) -> str` — Formatted JSON serialization of this dictionary.

### `process_control.py`

Cross-invocation exactus ownership and process termination primitives.

- `class Constants` — Group module-level constants.
  - `term_wait_seconds` = `3.0`
  - `poll_seconds` = `0.05`
  - `notice_lifetime_seconds` = `30.0`
- `new_run_id() -> str` — Return new run id.
- `process_exists(*, pid: int) -> bool` — Return process exists.
- `descendants(*, pid: int) -> tuple[int, ...]` — Return descendants.
- `exit_if_replaced(*, output_fd: int=2) -> None` — Exit normally with a notice when another exactus replaced this run.
- `terminate_tree(*, pid: int, include_root: bool=True, replaced: bool=False) -> None` — Handle terminate tree.
- `read_json(*, path: Path) -> dict[str, JsonValue] | None` — Read json.
- `write_json(*, path: Path, payload: dict[str, JsonValue]) -> None` — Write json.

### `runner.py`

Orchestrate discovery and functional exactuss from JSON or TOML actions.

- `load_actions(*, path: Path) -> dict[str, JsonValue]` — Read a JSON or TOML tool recipe.
- `validate_actions(*, value: JsonValue) -> dict[str, JsonValue]` — Validate all tool calls and references before launching anything.
- `class Constants` — Group module-level constants.
  - `mobile_max_width` = `600`
- `run_actions(*, specification: dict[str, JsonValue], root: Path, output: Path, cancelled: Callable[[], bool] | None=None, emit: Callable[[dict[str, JsonValue]], None] | None=None) -> dict[str, JsonValue]` — Run ordered tools, retain their evidence and stop owned servers.

## Examples

Runnable demonstration for `exactus/tools/actions/`.

Discover and verify a bundled page using a named-output Actions recipe.

```bash
python -m exactus.tools.actions.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/assets/README.md`, `examples/assets/actions.json`, `examples/run.py`, `examples/web/README.md`, `examples/web/code.js`, `examples/web/index.html`

## Dependencies and consumers

- Other packages: [`argument_parser`](../../packages/argument_parser/DOCS.md), [`project_python`](../../packages/project_python/DOCS.md), [`server`](../../packages/server/DOCS.md), [`common`](../common/DOCS.md), [`frontend`](../frontend/DOCS.md), [`record`](../record/DOCS.md), [`reports`](../reports/DOCS.md)
- Used by: `packages/package/process_control.py`, `tests/tools/actions/test_actions.py`, `tests/tools/actions/test_examples.py`, `tools/record/studio/worker.py`

## Tests

Tests live in `exactus/tests/tools/actions/`.

- `test_actions.py` — Verify declarative tool orchestration through real discovery and replay. (8 tests)
  - `test_actions_entrypoint_defaults_and_status`
  - `test_demo_discovery_replay_and_report`
  - `test_evaluations_follow_captured_timestamps`
  - `test_frontend_findings_can_be_report_only`
  - `test_invalid_later_call_never_starts_server`
  - `test_rejects_unknown_tools_and_forward_references`
  - `test_setup_failure_retains_report_and_stops_server`
  - `test_toml_named_output_reference`
- `test_examples.py` — Run the public actions example against its bundled recipe. (1 tests)
  - `test_actions_example`

<!-- exactus:reference:end -->
