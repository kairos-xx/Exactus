# tools/common/

The shared leaf primitives every tool builds on: configuration,
normalized envelope, report rendering inputs, terminal UI, source
excerpts and the packaged utilities.

## Files

| File | Description |
|---|---|
| `cli.py` | Shared CLI and glob helpers; bundle-dir resolution (`_host_bundle_dirs`); orchestrator-key filtering; `is_reports_tree` fingerprints report trees by content (`.runtime/`, `result.json` + `result.md`, `ARTIFACTS/@activity.json`) so renamed results roots are pruned from source discovery. |
| `config.py` | `[tool.exactus]` discovery and rendering: upward `pyproject.toml` walk with `root=true`, `--config`/`--no-config`, layered precedence, per-option provenance, path resolution relative to the declaring file, `--show-config`. |
| `parser.py` | Shared `ExactusArgumentParser`: folds `-`/`_` in long-option names so every CLI accepts `--foo-bar` and `--foo_bar` identically; collisions degrade to exact matching. |
| `envelope.py` | Build the normalized report envelope — `tool`/`run`/`invocation`/`environment`/`gate`/`artifacts` — plus crash/cancel stamping. |
| `activity.py` | Fixed `@activity.json` schema: heartbeat, progress and activity. |
| `progress.py` | `exactus-run/v1` live-run progress document schema. |
| `terminal.py` | Responsive ANSI terminal presentation for executions; progress bars mark the cell where a tool failed with a red `x`, in the tool row and at its position inside the pipeline GLOBAL bar. |
| `digest.py` | Summarize tool reports into failure digests for aggregate reports. |
| `directory_docs.py` | Document artifact folders from their innermost children outward. |
| `directory_inventory.py` | Managed bottom-up README inventories. |
| `report_comparison.py` | Compare normalized findings with the preceding report bundle. |
| `report_time.py` | Format recorded report times without changing machine values. |
| `snippets.py` | Numbered source excerpts around findings, with root containment, symlink and byte/line bounds. |
| `stderr_capture.py` | `stderr.log` transcripts with line counts. |
| `sprint.py` | Flushed-writer printing helpers. |
| `process_control.py` | Cross-invocation ownership/termination primitives. |
| `conflict_copies.py` | Reconcile numbered sync copies without discarding unique data. |
| `json_types.py` | JSON value types. |
| `templates/` | Shared Markdown template/mapping for `result.md` and the error report. |
| `process_layer/` | Internal authenticated process control: loopback identity responder, registry-free `discover`/`identify`, verified `ProcessTerminator`/`terminate_tree`; consumed by the orchestrator only, never standalone. |

## Configuration precedence

Highest first: tool CLI/`--tool-arg` → common CLI → pipeline-scoped tool
table → tool table → common table → catalog preset → parser defaults.
Scalars/booleans override; lists combine with nearest configuration last.
`resolve_arguments` skips reapplying configuration when
`EXACTUS_ORCHESTRATED=1` so layers are never resolved twice.

## Report contract

`envelope.py` is the single place the normalized envelope is
constructed; tools supply `summary`/`scope`/`findings`/`extension`, and
the runner adds `tool`/`run`/`invocation`/`environment`/`gate`/
`artifacts`. `result.json` is the semantic source — Markdown and HTML
render from it, never the reverse.

## process_layer/

Internal authenticated process identification and termination —
consumed by the orchestrator and tool workers, never a standalone tool.
There is no registry, PID file, or discovery database: identity is
proven live over a private loopback listener.

- `access.py` provisions the shared secret (`.runtime/authkey`,
  `EXACTUS_AUTHKEY` override) and wires the `RunRegistry` over
  `.runtime/runs.db`.
- `process_control.py` provides `IdentityResponder` plus
  `identify()`/`discover()`: a nonce/HMAC handshake on `127.0.0.1`,
  listener-table enumeration that skips per-process `AccessDenied`, and
  identity validation bound to process creation time — so a reused PID
  impersonating a stale record is rejected.
- `process_termination.py` provides `ProcessTerminator` and
  `terminate_tree`: child-first teardown restricted to trees verified
  through `identify`, with PID-reuse and stale-record protection.

`exactus/__main__.py` wires the responder around every run and drives
`--kill`/`--kill-all`; `tools/common/tool_worker.py` uses the same
access layer for worker-side termination requests.
