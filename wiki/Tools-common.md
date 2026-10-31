[Home](Home.md) > [Tools](Tools.md) > common

# tools/common/

The shared leaf primitives every tool builds on: configuration,
normalized envelope, report rendering inputs, terminal UI, source
excerpts and the packaged utilities.

## Files

| File | Description |
|---|---|
| `cli.py` | Shared CLI and glob helpers; bundle-dir resolution (`_host_bundle_dirs`); orchestrator-key filtering; `is_reports_tree` fingerprints report trees by content (`.runtime/`, `result.json` + `result.md`, `ARTIFACTS/@activity.json`) so renamed results roots are pruned from source discovery. |
| `api.py` | Process-isolated Python API for canonical tools: invokes each tool's module entry point in a detached worker, parses its `result.json` back and returns typed run results without sharing the caller's process state. |
| `catalog.py` | Canonical tool/pipeline catalog: tools are executable leaves, pipelines hold only references to tool ids or other pipelines; resolution flattens nested pipelines in declaration order and de-duplicates by canonical id. |
| `config.py` | `[tool.exactus]` discovery and rendering: upward `pyproject.toml` walk with `root=true`, `--config`/`--no-config`, layered precedence, per-option provenance, path resolution relative to the declaring file, `--show-config`. |
| `parser.py` | Shared `ExactusArgumentParser`: folds `-`/`_` in long-option names so every CLI accepts `--foo-bar` and `--foo_bar` identically; collisions degrade to exact matching. |
| `envelope.py` | Build the normalized report envelope — `tool`/`run`/`invocation`/`environment`/`gate`/`artifacts` — plus crash/cancel stamping. |
| `execution.py` | Shared standalone entry-point reporting: wraps a tool's main() with the envelope, artifact directory layout, activity heartbeat and exit-status contract used by every `exactus --<tool>` run. |
| `models.py` | Shared orchestration dataclasses and records exchanged between the runner, workers and supervisors — run/item states, findings counters and lifecycle payloads. |
| `activity.py` | Fixed `@activity.json` schema: heartbeat, progress and activity. |
| `progress.py` | `exactus-run/v1` live-run progress document schema. |
| `runtime.py` | Shared runtime state, progress and summary protocol: per-run mutable state guards, progress event emission and the summary contract tools fill at the end of a run. |
| `terminal.py` | Responsive ANSI terminal presentation for executions; progress bars mark the cell where a tool failed with a red `x`, in the tool row and at its position inside the pipeline GLOBAL bar. |
| `terminal_progress.py` | Animated determinate progress bar primitives: responsive width/ETA rendering driven by `terminal.py` for long-running stages. |
| `digest.py` | Summarize tool reports into failure digests for aggregate reports. |
| `directory_docs.py` | Document artifact folders from their innermost children outward. |
| `directory_inventory.py` | Managed bottom-up README inventories. |
| `report_comparison.py` | Compare normalized findings with the preceding report bundle. |
| `report_time.py` | Format recorded report times without changing machine values. |
| `snippets.py` | Numbered source excerpts around findings, with root containment, symlink and byte/line bounds. |
| `collect_files.py` | `--collect-files` evidence bundling: every file `result.json` lists findings for is copied into `<report>/FILES/` — `files.zip` keeps the project-relative layout, `TREE.txt` renders the archive through `exactus.packages.tree`, `README.md` describes it. |
| `stderr_capture.py` | `stderr.log` transcripts with line counts. |
| `sprint.py` | Flushed-writer printing helpers. |
| `process_control.py` | Cross-invocation ownership/termination primitives. |
| `pipeline_supervisor.py` | Transactional pipeline ownership and reset coordination over the model queries: claims a pipeline run, records stage transitions and aborts competing writers safely. |
| `registry.py` | Cross-process run registry in `EXACTUS_RESULTS/.runtime/runs.db` (SQLite WAL): each run claims a row and terminates live rows writing the same output directory or intersecting targets, so reruns never race a stale writer; bounded by `runtime-max-runs`/`runtime-max-size`. |
| `conflict_copies.py` | Reconcile numbered sync copies without discarding unique data. |
| `json_types.py` | JSON value types. |
| `toml.py` | Dependency-free TOML serializer compatible with `tomllib` output — scalar/table emission used for rendered configuration and manifests. |
| `templates/` | Shared Markdown template/mapping for `result.md` and the error report. |
| `process_layer/` | Internal authenticated process control: loopback identity responder, registry-free `discover`/`identify`, verified `ProcessTerminator`/`terminate_tree`; consumed by the orchestrator only, never standalone. |
| `tool_worker.py` | Detached `pmanager` tool workers: spawns a canonical tool module in its own process with the orchestrator control-channel environment, applies worker-side termination requests through the `process_layer` access layer, and streams progress back to the runner. |

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/tools/common/`](../exactus/tools/common/) | [`exactus/tests/tools/common/`](../exactus/tests/tools/common/) | [`DOCS.md`](../exactus/docs/tools/common/DOCS.md) |

[< Tools-actions](Tools-actions.md) · [Tools index](Tools.md) · [Tools-completion >](Tools-completion.md)
