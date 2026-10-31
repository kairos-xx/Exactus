[Home](Home.md) > [Packages](Packages.md) > server

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/server/`](../exactus/packages/server/) | [`exactus/tests/packages/server/`](../exactus/tests/packages/server/) | [`DOCS.md`](../exactus/docs/packages/server/DOCS.md) |

[< Packages-screenshot](Packages-screenshot.md) · [Packages index](Packages.md) · [Packages-shebang_update >](Packages-shebang_update.md)
