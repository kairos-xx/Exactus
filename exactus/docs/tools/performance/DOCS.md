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

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Performance exactus tool. |
| `arguments.py` | Declare the performance grammar without importing its engine. |
| `main.py` | Instrument the generic performance package against this project. |

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--source` | trace file, directory, or glob to scan; repeatable (default: EXACTUS_RESULTS) | action='append', dest='sources', metavar='PATH' |
| `--serve` | serve the exported dashboard (default: on) | action=BooleanOptionalAction, default=None |
| `--open` | open the dashboard in the managed browser (default: on) | action=BooleanOptionalAction, default=None |
| `--no-browser` | SUPPRESS | action='store_false', dest='open' |
| `--chrome` | Chrome or Chromium executable used to open the dashboard | type=Path |
| `--report` | write the full JSON report here (default: <output>/report.json) | type=Path |
| `--gap-threshold` | silent-gap threshold in seconds | type=float |
| `--repetition-threshold` | repeated-step count treated as a bottleneck | type=int |
| `--server-timeout` | seconds to wait for the dashboard server | type=float |
| `--summary` | print analysis only; do not export or serve | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Performance exactus tool.


### `arguments.py`

Declare the performance grammar without importing its engine.

- `create_parser() -> ArgumentParser` — Create parser.

### `main.py`

Instrument the generic performance package against this project.

- `class Constants` — Hold the Exactus-specific performance defaults.
  - `default_sources` = `('EXACTUS_RESULTS',)`
  - `default_gap_threshold` = `0.25`
  - `default_repetition_threshold` = `10`
  - `default_server_timeout` = `10.0`
- `create_parser() -> ArgumentParser` — Return the shared CLI grammar used by execution and completion.
- `parse_args(*, arguments: tuple[str, ...] | None=None) -> Namespace` — Parse args.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Return main.

## Dependencies and consumers

- Other packages: [`argument_parser`](../../packages/argument_parser/DOCS.md), [`performance`](../../packages/performance/DOCS.md), [`project_python`](../../packages/project_python/DOCS.md), [`steps`](../../packages/steps/DOCS.md), [`common`](../common/DOCS.md), [`reports`](../reports/DOCS.md)
- Used by: `tests/tools/performance/test_main.py`

## Tests

Tests live in `exactus/tests/tools/performance/`.

- `test_main.py` — The performance tool wraps the generic analyzer for this project. (3 tests)
  - `test_main_analyzes_and_exports`
  - `test_main_reports_missing_traces`
  - `test_parse_args_reads_repeatable_sources`

<!-- exactus:reference:end -->
