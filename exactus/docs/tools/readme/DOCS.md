# tools/readme/

The `readme` tool: audits per-directory README documentation inventories.

## Files

| File | Description |
|---|---|
| `arguments.py` | The readme grammar, declared without importing the execution engine. |
| `core.py` | The audit engine: verifies each directory's README documents its files and subdirectories. |
| `main.py` | Entry point. |
| `metrics.py` | Measure Markdown files and README sizes for the README report. |
| `templates/` | Tool-specific Markdown template/mapping. |

## Behavior

- Walks the tree checking that every directory's README documents the
  files and subdirectories it actually contains.
- `metrics.py` produces Markdown file counts and README size metrics for
  the report's summary.
- Findings identify undocumented entries and stale inventory sections;
  emits the normalized envelope like every other tool.
