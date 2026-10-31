# `exactus/tools/performance/`

The `performance` exactus tool instruments the generic
`exactus/packages/performance` analyzer against this project. It scans
`EXACTUS_RESULTS` for the `steps.txt` traces each analyzer writes under
`ARTIFACTS/`, prints a compact per-run bottleneck summary, writes the
normalized report bundle (`result.md`, `result.json`, `result_web/`), and
exports the interactive dashboard into `ARTIFACTS/`. `--no-serve` (the
pipeline default) exports and exits; without it the run serves the
dashboard and opens it in the managed browser.

Configuration lives under `[tool.exactus.performance]` (via
`resolve_arguments`); the generic package keeps its own
`[tool.performance]` table for standalone use.

## Automatic inventory healing

Run `exec/exactus --readme` to refresh the managed `Directory contents`
section.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Performance exactus tool.
- [`arguments.py`](arguments.py) — Declare the performance grammar without importing its engine.
- [`main.py`](main.py) — Instrument the generic performance package against this project.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
