# tools/performance/

The `performance` tool: instruments the generic
`exactus/packages/performance` analyzer against this project.

## Files

| File | Description |
|---|---|
| `arguments.py` | The performance grammar, declared without importing the execution engine. |
| `main.py` | Entry point: resolves Exactus arguments/config, records `steps.txt`, runs the generic API, and writes the report bundle. |

## Behavior

- Scans `EXACTUS_RESULTS` (configurable via repeated `--source`) for the
  `steps.txt` traces each analyzer writes under `ARTIFACTS/`.
- Prints a compact per-run bottleneck summary, writes the normalized
  report bundle (`result.md`, `result.json`, `result_web/`) under
  `EXACTUS_RESULTS/PERFORMANCE`, and exports the interactive dashboard
  into `ARTIFACTS/`.
- `--no-serve` exports and exits; without it the run serves the
  dashboard and opens the managed browser. Pipeline presets pass
  `--no-serve` so the final wave never blocks.
- Configuration lives under `[tool.exactus.performance]`; the package's
  own `[tool.performance]` table only applies to the standalone
  `python exactus/packages/performance` CLI.
