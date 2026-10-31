# `exactus/server/`

Loopback web-server lifecycle used by the screenshot shortcuts
(`--server` and `--entrypoint`) in `exactus/__main__.py`.

## Directory contents

### Files

#### `__init__.py`

Package marker documenting the server subpackage.

#### `diagnostics.py`

Server log parsing. Public API: `ServerDiagnostic` — One HTTP error
request parsed from captured server output.; `parse_server_log()` —
Parse Flask/Werkzeug, Uvicorn/FastAPI, and generic access logs into
4xx/5xx diagnostics.

#### `local.py`

Local server implementation. Public API: `accepts()` — Return whether a
host/port accepts TCP.; `free_port()` — Return an available loopback
port.; `probe_default_url()` — Poll loopback hosts on port 80.;
`wait_ready()` — Poll until a spawned server accepts connections.;
`server_state_path()` — Return the recorded server state file.;
`ping_server()` — Verify the `/_exactus_check_ping` identity token.;
`reuse_server()` — Return a surviving `--server` instance, if any.;
`serve()` — Reuse or spawn a `--server` instance for a directory.;
`start_entrypoint()` — Launch a custom server script.;
`clear_server_state()` — Remove a `--server` state file.

### Directories

#### `ports.py`

Safe fixed-port replacement for package servers. `replace_listener()`
verifies the listening process's package or explicitly permitted inline
factory before interrupting it. It reuses `local.accepts()` and
`process_control.terminate_tree()`; unrelated listeners are left alone.
Studio uses this shared lifecycle instead of its own port manager.

#### `examples/`

Runnable demonstration of the reuse contract: `run.py` serves the
bundled `web/` directory through `serve()`, verifies the identity ping
and a page fetch, shows `reuse_server()` adopting the same process, and
cleans up its `.scratch/` artifacts on exit.

## Reuse contract

`serve()` persists `{pid, port}` under
`~/.cache/exactus-tools/servers/<digest>.json`, where `digest` is the
SHA-256 of the resolved served path. A later invocation adopts the
recorded process only when the pid is alive and
`GET /_exactus_check_ping` returns the fixed `exactus-check-server`
token; otherwise a fresh server is spawned on a free port.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Loopback web-server lifecycle for the screenshot exactus shortcuts.
- [`__main__.py`](__main__.py) — Serve a directory over loopback (``python -m exactus.packages.server``).
- [`cli.py`](cli.py) — Serve a directory over loopback (``python -m exactus.packages.server``).
- [`diagnostics.py`](diagnostics.py) — Parse captured web-server output into screenshot diagnostics.
- [`json_types.py`](json_types.py) — JSON value types shared by the exactus tools.
- [`local.py`](local.py) — Loopback web-server lifecycle for the screenshot exactus shortcuts.
- [`ports.py`](ports.py) — Replace verified package servers without stopping unrelated listeners.
- [`process_control.py`](process_control.py) — Cross-invocation exactus ownership and process termination primitives.

### Subdirectories

- [`examples/`](examples/README.md) — `run.py` demonstrates the loopback-server lifecycle end to end: it serves the bundled `web/` directory through `exactus.packages.server.local.serve`, waits for readiness, verifies the `/_exactus_check_ping` identity token, fetches `index.html`, and shows `reuse_server` adopting the surviving process rather than spawning a second one. The server is terminated and its state file cleared when the demo exits.

<!-- exactus:inventory:end -->


