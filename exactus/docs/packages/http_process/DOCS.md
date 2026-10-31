# http_process/

Start processes, discover TCP listeners owned by their process trees,
verify HTTP endpoints, and resolve local listener ownership.

## Layout

| Path | Description |
|---|---|
| `http_process/process.py` | `HttpProcess` orchestrator, `Listener`/`HttpServer`/`ProcessInfo` dataclasses, bind-scope and IP-family classification. |
| `http_process/__main__.py` | `http-process` CLI: inspect an IP/port or run a process and discover HTTP. |
| `http_process/examples/` | Runnable example servers. |
| `pyproject.toml` | Standalone package metadata; declares `psutil>=7.0`. |

## Behavior

- Process trees are walked with `psutil`; listeners are classified as
  `loopback`, `wildcard` or `specific`, and IPv4/IPv6.
- Wildcard binds are probed via their loopback equivalent
  (`0.0.0.0` → `127.0.0.1`, `::` → `::1`).
- `wait_for_http`/`wait_for_listener`/`wait_for` poll a started process
  until its HTTP endpoint answers or a timeout fires.
- The package root lives on the checkers' `search-path`/`extraPaths` so
  `import http_process` resolves inside the repository.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `.ruff_cache/` | Subdirectory. |
| `README.md` | Package readme. |
| `__init__.py` | Public API for HTTP process discovery and inspection. |
| `__main__.py` | Command-line interface for HTTP process inspection. |
| `cli.py` | Command-line interface for HTTP process inspection. |
| `examples/` | Examples for the http_process package. |
| `process.py` | Run processes and inspect HTTP servers and their owning processes. |
| `pyproject.toml` | — |

Run it as a module: `python -m exactus.packages.http_process`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--host` |  | default='127.0.0.1' |
| `--port` |  | type=int |
| `--timeout` |  | default=30.0, type=float |
| `--http-timeout` |  | default=0.5, type=float |
| `command` | Optional command to run and inspect. | nargs='*' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `cli.py`

Command-line interface for HTTP process inspection.

- `class Cli` — Expose HTTP process inspection through a command-line interface.
  - `run() -> int` — Run the command-line interface.
  - `parser() -> ArgumentParser` — Build the command-line parser.
- `main() -> int` — Run the package CLI.

### `process.py`

Run processes and inspect HTTP servers and their owning processes.

- `class Constants` — Group module-level constants.
  - `port_max` = `65535`
- `class BindScope(StrEnum)` — Network scope represented by a socket bind address.
- `class IpFamily(StrEnum)` — IP address family used by a listener.
- `class ProcessInfo` — Describe a process owning a network listener.
  - Fields: `pid: int`, `ppid: int`, `name: str`, `executable: Path | None`, `command: tuple[str, ...]`, `username: str | None`, `create_time: float | None`
- `class Listener` — Describe a TCP listener owned by a process.
  - Fields: `pid: int`, `bind_host: str`, `port: int`, `scope: BindScope`, `family: IpFamily`
- `class HttpServer` — Describe a verified HTTP server.
  - Fields: `bind_host: str`, `probe_host: str`, `port: int`, `scope: BindScope`, `family: IpFamily`, `url: str`, `status: int`, `reason: str`, `process: ProcessInfo | None`
  - `pid() -> int | None` — Return the owning process identifier when available.
  - `localhost_only() -> bool` — Return whether the server is restricted to loopback.
  - `all_interfaces() -> bool` — Return whether the server listens on wildcard interfaces.
  - `specific_ip() -> bool` — Return whether the server is bound to one non-loopback IP.
- `class HttpInspection` — Describe the result of inspecting an IP address and TCP port.
  - Fields: `host: str`, `port: int`, `tcp_open: bool`, `http: bool`, `url: str`, `status: int | None`, `reason: str | None`, `process: ProcessInfo | None`
  - `pid() -> int | None` — Return the owning process identifier when available.
- `class HttpProcess` — Run processes and inspect HTTP network listeners.
  - `pid() -> int | None` — Return the managed root process identifier.
  - `running() -> bool` — Return whether the managed root process is running.
  - `listeners() -> tuple[Listener, ...]` — Return TCP listeners owned by the managed process tree.
  - `http_servers() -> tuple[HttpServer, ...]` — Return verified HTTP servers owned by the process tree.
  - `ports() -> tuple[int, ...]` — Return unique TCP listening ports owned by the process tree.
  - `http_ports() -> tuple[int, ...]` — Return unique verified HTTP ports.
  - `bound_addresses() -> tuple[str, ...]` — Return unique addresses used by owned TCP listeners.
  - `urls() -> tuple[str, ...]` — Return URLs belonging to verified HTTP servers.
  - `localhost_servers() -> tuple[HttpServer, ...]` — Return HTTP servers restricted to loopback.
  - `wildcard_servers() -> tuple[HttpServer, ...]` — Return HTTP servers bound to wildcard addresses.
  - `specific_ip_servers() -> tuple[HttpServer, ...]` — Return servers bound to specific non-loopback addresses.
  - `start() -> Popen[bytes]` — Start the configured process.
  - `inspect(*, host: str, port: int) -> HttpInspection` — Inspect an address for an HTTP server and local process owner.
  - `is_http(*, host: str, port: int) -> bool` — Return whether an address is serving HTTP.
  - `process_at(*, host: str, port: int) -> ProcessInfo | None` — Return the local process owning an address and port.
  - `wait_for_http() -> tuple[HttpServer, ...]` — Wait until at least one owned HTTP server is detected.
  - `wait_for_listener() -> tuple[Listener, ...]` — Wait until at least one owned TCP listener is detected.
  - `wait_for(*, host: str, port: int) -> HttpInspection` — Wait until an address starts serving HTTP.
  - `stop(*, timeout: float=5.0) -> None` — Terminate the managed process tree.

## Examples

Examples for the http_process package.

Files: `__init__.py`, `__main__.py`, `inspect_existing.py`, `run.py`

## Dependencies and consumers

- Third-party: `psutil`
- Used by: `tests/packages/meaningful/test_meaningful_sources.py`, `tests/tools/record/test_target.py`, `tools/record/studio/target_service.py`

## Tests

Tests live in `exactus/tests/packages/http_process/`.

- `test_example_run.py` — Cover the bundled ``http_process`` example entry point. (1 tests)
  - `test_example_module_runs_as_a_script`
- `test_examples.py` — Exercise the bundled ``http_process`` examples end to end. (2 tests)
  - `test_example_run_starts_discovers_and_stops_a_server`
  - `test_inspect_existing_reports_the_endpoint`
- `test_http_process.py` — Smoke tests for the http_process package. (2 tests)
  - `test_address_helpers`
  - `test_started_process_uses_the_requested_working_directory`
- `test_main.py` — Cover the ``exactus.packages.http_process`` CLI and process wait paths. (16 tests)
  - `test_cli_inspect_reports_closed_port`
  - `test_cli_inspect_reports_live_server`
  - `test_cli_run_discovers_spawned_http_server`
  - `test_main_delegates_to_cli_run`
  - `test_wait_for_http_requires_a_started_process`
  - `test_wait_for_listener_requires_a_started_process`
  - `test_wait_for_http_reports_early_process_exit`
  - `test_wait_for_listener_times_out_without_a_socket`
  - `test_wait_for_times_out_on_a_closed_port`
  - `test_stop_terminates_a_managed_process`
  - `test_stop_is_safe_without_a_process`
  - `test_inspect_reports_process_ownership`
  - `test_wait_for_http_discovers_and_describes_a_spawned_server`
  - `test_constructor_rejects_empty_command`
  - `test_start_requires_a_command_and_single_use`
  - `test_inspect_rejects_an_invalid_port`

<!-- exactus:reference:end -->
