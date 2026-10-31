# server/

Loopback web-server lifecycle helpers for the screenshot shortcuts,
plus parsing of captured server output into reportable diagnostics.

## Behavior

- Loopback only: servers bind `127.0.0.1` and are stopped by the same
  process-control ownership rules as the orchestrator.
- `/_exactus_ping` is the readiness probe — renamed from the legacy
  `/_exactus_check_ping` name and matched at both ends by a single
  constant.
- `diagnostics.py` turns raw server logs into the same finding shape
  used across normalized reports.
- `ports.replace_listener(port=..., module=...)` uses the shared TCP probe
  and process-tree termination helpers. It requests graceful interruption
  first, then escalates only for the verified owner. It recognizes module
  launches and their project-interpreter `__main__.py` re-execution.
  Callers may also specify a qualified `factory` for legacy inline
  launchers; static AST inspection must find both its import and its call.
  Unrelated, ambiguous, or unverifiable listeners are left running.
  Port zero bypasses replacement; missing `lsof`/`ps` fails safely on a
  busy port. Studio uses this shared policy for fixed-port startup.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Loopback web-server lifecycle for the screenshot exactus shortcuts. |
| `__main__.py` | Serve a directory over loopback (``python -m exactus.packages.server``). |
| `cli.py` | Serve a directory over loopback (``python -m exactus.packages.server``). |
| `diagnostics.py` | Parse captured web-server output into screenshot diagnostics. |
| `examples/` | `run.py` demonstrates the loopback-server lifecycle end to end: it serves the bundled `web/` directory through `exactus.packages.server.local.serve`, waits for readiness, verifies the `/_exactus_check_ping` identity token, |
| `json_types.py` | JSON value types shared by the exactus tools. |
| `local.py` | Loopback web-server lifecycle for the screenshot exactus shortcuts. |
| `ports.py` | Replace verified package servers without stopping unrelated listeners. |
| `process_control.py` | Cross-invocation exactus ownership and process termination primitives. |

Run it as a module: `python -m exactus.packages.server`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `path` | Directory to serve. | type=Path |
| `--log` | Server output destination (default: .scratch/server.log). | default=Path('.scratch/server.log'), type=Path |
| `--stop` | Terminate the recorded server and clear its state. | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `cli.py`

Serve a directory over loopback (``python -m exactus.packages.server``).

- `main() -> int` — Start, adopt, or stop a detached loopback server.

### `diagnostics.py`

Parse captured web-server output into screenshot diagnostics.

- `class Constants` — Group module-level constants.
  - `access` = `re_compile(pattern='"(?P<method>[A-Z]+)\\s+(?P<url>\\S+)\\s+HTTP/[0...`
- `class ServerDiagnostic` — One HTTP error request parsed from captured server output.
  - Fields: `stream: str`, `line: str`, `method: str`, `url: str`, `status: int`, `severity: str`
- `parse_server_log(*, path: Path) -> tuple[ServerDiagnostic, ...]` — Parse Flask/Werkzeug, Uvicorn/FastAPI, and generic access logs.

### `json_types.py`

JSON value types shared by the exactus tools.

- `class JsonDict(dict[str, T])` — Dictionary with a formatted JSON representation.
  - `tojson() -> str` — Formatted JSON serialization of this dictionary.

### `local.py`

Loopback web-server lifecycle for the screenshot exactus shortcuts.

- `class Constants` — Group module-level constants.
  - `probe_hosts` = `('localhost', '127.0.0.1')`
  - `probe_port` = `80`
  - `ping_path` = `'/_exactus_ping'`
  - `server_token` = `b'exactus-check-server'`
  - `server_snippet` = `dedent(text=f'\n        """Loopback file server answering the exact...`
  - `log_lock` = `Lock()`
  - `serve_retries` = `4`
- `accepts(*, host: str, port: int, timeout: float=1.0) -> bool` — Return whether ``host:port`` accepts a TCP connection.
- `free_port() -> int` — Return an available loopback TCP port.
- `probe_default_url(*, pid: int, timeout: float=15.0) -> str | None` — Poll default loopback hosts on port 80 for a running server.
- `wait_ready(*, url: str, pid: int, timeout: float=15.0) -> bool` — Poll until the URL's host and port accept TCP connections.
- `server_state_path(*, path: Path) -> Path` — Return the state file recording a ``--server`` instance.
- `ping_server(*, port: int, timeout: float=1.5) -> bool` — Return whether ``port`` answers the ``--server`` identity probe.
- `reuse_server(*, path: Path) -> tuple[int, int] | None` — Return the pid and port of a surviving ``--server`` instance.
- `serve(*, path: Path, log: Path) -> tuple[int, str, bool]` — Reuse a surviving ``--server`` instance or spawn a new one.
- `start_entrypoint(*, path: Path, log: Path, port: int | None=None) -> tuple[int, int]` — Launch a custom server script before the screenshot exactus.
- `clear_server_state(*, path: Path) -> None` — Remove the recorded ``--server`` state file for ``path``.

### `ports.py`

Replace verified package servers without stopping unrelated listeners.

- `listening(*, port: int) -> bool` — Check whether a loopback listener is accepting connections.
- `inline_factory(*, command: str, factory: str | None) -> bool` — Recognize an explicitly permitted factory call in inline Python.
- `listener_owner(*, port: int, module: str, factory: str | None=None) -> int | None` — Verify the listening PID belongs to the requested package launcher.
- `replace_listener(*, port: int, module: str, factory: str | None=None) -> int | None` — Release a fixed port only for the permitted package server.

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

## Examples

`run.py` demonstrates the loopback-server lifecycle end to end: it
serves the bundled `web/` directory through `exactus.packages.server.local.serve`,
waits for readiness, verifies the `/_exactus_check_ping` identity token,
fetches `index.html`, and shows `reuse_server` adopting the surviving
process rather than spawning a second one. The server is terminated and
its state file cleared when the demo exits.

```bash
python exactus/packages/server/examples
```

Artifacts — `server.log` and the `XDG_CACHE_HOME` reuse state — are
written under the git-ignored `.scratch/` folder, so re-runs leave the
checkout clean. Tests override the scratch directory with a temporary
path.

### Directory contents

- `__init__.py` — File.
- `__main__.py` — File.
- `run.py` — File.
- `web/` — Subdirectory.

Files: `.scratch/server.log`, `__init__.py`, `__main__.py`, `run.py`, `web/index.html`

## Dependencies and consumers

- No dependencies outside the standard library.
- Used by: `../pyproject.toml`, `packages/__main__.py`, `packages/actions/action_javascript/examples/run.py`, `packages/actions/action_rest/examples/run.py`, `packages/browser/examples/run.py`, `packages/extended_selector/examples/run.py`, `packages/performance/api.py`, `packages/performance/session.py`, `packages/screenshot/examples/run.py`, `packages/visual_cause/examples/run.py`, `packages/widgets/widget_clock/examples/run.py`, `packages/widgets/widget_console/examples/run.py`, `packages/widgets/widget_selector/examples/run.py`, `tests/common/json_serializers/test_json_serializers.py` and 20 more

## Tests

Tests live in `exactus/tests/packages/server/`.

- `test_examples.py` — Coverage for the ``exactus/server/examples`` demonstration. (3 tests)
  - `test_example_serves_pings_and_reuses`
  - `test_example_reports_unready_server`
  - `test_example_reports_adoption_failure`
- `test_main.py` — Cover the ``exactus.packages.server`` command-line entry point. (5 tests)
  - `test_main_falls_back_to_the_unqualified_import`
  - `test_main_stop_reports_missing_server`
  - `test_main_stop_terminates_a_recorded_server`
  - `test_main_serve_reports_a_server_that_never_ready`
  - `test_main_serve_blocks_until_signaled`
- `test_ports.py` — Exercise ownership checks and safe fixed-port replacement failures. (4 tests)
  - `test_listener_identity`
  - `test_inline_factory_requires_import_and_call`
  - `test_owner_query_failure_and_current_process`
  - `test_replacement_paths`
- `test_server_lifecycle.py` — Loopback server helpers: logs, ports, probing and lifecycle. (9 tests)
  - `test_parse_server_log`
  - `test_accepts_free_port_and_state`
  - `test_probe_and_wait_for_dead_process`
  - `test_probe_default_url_finds_listener`
  - `test_serve_ping_reuse_and_cleanup`
  - `test_start_entrypoint_exports_port`
  - `test_serve_adopts_a_recorded_server`
  - `test_serve_retries_a_failed_spawn`
  - `test_serve_reports_persistent_spawn_failure`

<!-- exactus:reference:end -->
