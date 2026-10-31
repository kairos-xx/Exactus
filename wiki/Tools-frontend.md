[Home](Home.md) > [Tools](Tools.md) > frontend

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/tools/frontend/`](../exactus/tools/frontend/) | [`exactus/tests/tools/frontend/`](../exactus/tests/tools/frontend/) | [`DOCS.md`](../exactus/docs/tools/frontend/DOCS.md) |

[< Tools-docs](Tools-docs.md) · [Tools index](Tools.md) · [Tools-kwargs_typehints >](Tools-kwargs_typehints.md)
