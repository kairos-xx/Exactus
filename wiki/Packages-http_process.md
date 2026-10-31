[Home](Home.md) > [Packages](Packages.md) > http_process

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/http_process/`](../exactus/packages/http_process/) | [`exactus/tests/packages/http_process/`](../exactus/tests/packages/http_process/) | [`DOCS.md`](../exactus/docs/packages/http_process/DOCS.md) |

[< Packages-guard](Packages-guard.md) · [Packages index](Packages.md) · [Packages-markdown >](Packages-markdown.md)
