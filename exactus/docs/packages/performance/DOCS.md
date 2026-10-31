# `exactus.packages.performance`

`exactus.packages.performance` turns timestamped `exactus.packages.steps` traces into an immutable
performance model and an interactive browser profiler. It is
project-agnostic: it accepts any mix of `steps.txt` files, directories,
or glob expressions, and the `exactus` tool layer
(`exactus/tools/performance`) supplies the Exactus-specific
`EXACTUS_RESULTS` scan root and report destination.

## Input

The canonical trace format is the format emitted by `exactus.packages.steps.StepLog`:

```text
2026-10-14T16:11:32.372+00:00 +    0.002s tool: arguments
2026-10-14T16:11:32.390+00:00 +    0.020s   discover
2026-10-14T16:11:32.410+00:00 +    0.040s     scan file
```

Two leading spaces represent one nesting level. Depth `1` is treated as a
stage boundary; deeper events remain associated with that stage. The parser
ignores malformed lines rather than invalidating an otherwise useful run.

When a trace is located at
`EXACTUS_RESULTS/LINTS/ARTIFACTS/steps.txt`, the inferred tool name is
`lints`. Directory input is recursively searched for every `steps.txt`.

## API

```python
from pathlib import Path

from exactus.packages.performance import Performance
from exactus.packages.performance.config import PerformanceConfig

runs = Performance.analyze(paths=(Path("EXACTUS_RESULTS"),))
for run in runs:
    print(run.tool, run.duration, run.largest_gap)

index = Performance.export(
    paths=(Path("EXACTUS_RESULTS"),),
    destination=Path("performance-dashboard"),
)

session = Performance.serve(
    paths=(Path("EXACTUS_RESULTS"),),
    destination=Path("performance-dashboard"),
)
```

`Performance.summarize(runs=...)` renders the compact per-run text the
CLI prints. `Performance.execute(config=...)` is the complete flow —
analyze (or reuse caller-supplied `runs`), print the summary, write the
JSON report, export the dashboard, and optionally serve it until
Ctrl+C — used by both the standalone CLI and the `exactus` tool
wrapper:

```python
status = Performance.execute(
    config=PerformanceConfig(
        sources=("EXACTUS_RESULTS",),
        output=Path("performance-dashboard"),
        serve=False,
    ),
)
```

`Performance.analyze` returns immutable `PerformanceRun` values containing:

- raw parsed `StepEvent` values;
- inferred `Stage` intervals;
- ranked `Bottleneck` values;
- total duration;
- average event rate;
- largest adjacent-event silence.

### Bottlenecks

The analyzer currently produces two complementary bottleneck classes.

**Gap bottlenecks** measure silence between adjacent trace events. They are
useful for locating subprocess waits, blocking I/O, serialization, test
shards, browser waits, and other work that emits no intermediate trace event.
The score is the gap duration divided by total run duration.

**Repeat bottlenecks** identify messages occurring at least three times. They
highlight hot loops, per-file work, repeated repair passes, repeated progress
updates, and other high-cardinality operations. Their score is occurrence
count divided by total event count.

These are diagnostics, not proof of CPU cost: a silent gap can represent
useful external work, and a high-frequency event can be inexpensive. The
interactive timeline is intended for drilling into that context.

## Dashboard

`Performance.export` writes:

```text
index.html
style.css
code.js
data.js
steps.json
```

`steps.json` intentionally preserves the simple raw representation:

```json
{
  "lints": ["raw line 1", "raw line 2"],
  "coverage_tests": ["raw line 1"]
}
```

The browser derives its interactive model from those raw lines. `data.js`
carries the same payload as `window.__PERFORMANCE_STEPS__` so `index.html`
also works when opened through `file://`, where `fetch("steps.json")` is
blocked; the embedded payload wins and the fetch remains the fallback when
`data.js` is absent. The profiler
contains stage bands, event density, event raster marks, stall regions,
scrubbing, nearest-event inspection, zoom, drill-down, and synchronized raw
trace navigation. CSS and JavaScript remain external to `index.html`.

`Performance.serve` exports first and delegates serving to
`exactus.packages.server.local.serve`. Server readiness, identity pings, process reuse,
state caching, and process-tree termination therefore use the same lifecycle
as the rest of Exactus. Browser launch and shutdown are delegated to
`exactus.packages.browser.lifecycle.BrowserLifecycle`; no `http.server`, `webbrowser`,
or bespoke browser process management exists in this package.

The returned `DashboardSession` records the URL, server PID, reuse state, and
optional browser lifecycle. Call `session.close()` when finished. It closes
the browser and terminates only a server created by that session; an adopted
shared server remains alive.

The module and example entry points import `exactus.packages.project_python.auto` before
loading the implementation so repository execution automatically re-execs
under the project `.venv`, matching the other Exactus tools.

## CLI

Analyze and export:

```bash
python -m exactus.packages.performance EXACTUS_RESULTS
```

Summary only:

```bash
python -m exactus.packages.performance EXACTUS_RESULTS --summary
```

Export and serve interactively:

```bash
python -m exactus.packages.performance EXACTUS_RESULTS --serve
```

Suppress browser opening:

```bash
python -m exactus.packages.performance EXACTUS_RESULTS --serve --no-browser
```

Choose the export directory:

```bash
python -m exactus.packages.performance EXACTUS_RESULTS -o build/performance
```

## Example

All three forms execute the same comprehensive example:

```bash
exactus/packages/performance/examples/run.py
python exactus/packages/performance/examples
python -m exactus.packages.performance.examples
```

The example creates three representative Exactus-shaped traces, analyzes
stages and bottlenecks, prints the strongest findings, and exports the
interactive dashboard into a temporary workspace.

## Architecture

- `model.py` — immutable event, stage, bottleneck, and run models.
- `parser.py` — trace discovery, tool-name inference, and line parsing.
- `analyzer.py` — stage inference and bottleneck ranking.
- `dashboard.py` — static dashboard asset export.
- `session.py` — `exactus.packages.server` + `exactus.packages.browser` lifecycle integration.
- `api.py` — high-level `Performance` facade.
- `cli.py` — command-line interface.
- `web/` — external HTML/CSS/JavaScript profiler assets.
- `examples/` — executable end-to-end example.

The analytical core remains independent of browser/server lifecycle code; only
interactive serving crosses into `exactus.packages.server` and `exactus.packages.browser`.

## Project configuration

Configuration resolution is deterministic: explicit API or CLI values override
`[tool.performance]`; project configuration overrides package defaults. The
generic defaults scan `.` and export to `performance/`; a project opts into
concrete roots through `[tool.performance]` in its own `pyproject.toml`. With no
arguments, `python exactus/packages/performance` and `python -m exactus.packages.performance` use
that resolved configuration.

The `exactus` catalog tool (`exactus/tools/performance`) does not read
`[tool.performance]` — it reads `[tool.exactus.performance]` through the
standard `resolve_arguments` merge, scans `EXACTUS_RESULTS`, and writes the
normalized report bundle under `EXACTUS_RESULTS/PERFORMANCE`.

The complete merge-ready configuration surface is shipped as
`pyproject.performance.toml`. The package intentionally does not ship a root
`pyproject.toml` replacement because doing so would overwrite unrelated project
configuration when this archive is extracted over an existing repository.

The browser convention matches Exactus Studio: opening is enabled by default
and `--no-open` suppresses it. Serving is delegated to `exactus.packages.server`, browser
lifecycle to `exactus.packages.browser`, and direct entry points activate
`exactus.packages.project_python.auto` before loading the implementation.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Analyze Exactus step traces and expose an interactive profiler. |
| `__main__.py` | Run ``exactus.packages.performance`` through the project's virtualenv. |
| `analyzer.py` | Analyze step traces for execution bottlenecks. |
| `api.py` | Public high-level API for performance analysis. |
| `cli.py` | Command-line interface for performance trace analysis. |
| `config.py` | Resolve performance settings from defaults, pyproject, and overrides. |
| `dashboard.py` | Export and serve the interactive performance dashboard. |
| `examples/` | Runnable demonstration for `exactus/packages/performance/`. |
| `model.py` | Typed models for step-trace performance analysis. |
| `parser.py` | Parse and discover Exactus step traces. |
| `report.py` | Build the machine-readable performance report. |
| `session.py` | Shared server and browser lifecycle for exported performance dashboards. |
| `web/` | Subdirectory. |

Run it as a module: `python -m exactus.packages.performance`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `sources` | files, directories, or globs; defaults to tool.performance | nargs='*' |
| `--project` |  | type=Path |
| `-o, --output` |  | type=Path |
| `--report` | write the full JSON report here (default: <output>/report.json); no browser or server is needed | type=Path |
| `--serve` |  | action=BooleanOptionalAction, default=None |
| `--open` |  | action=BooleanOptionalAction, default=None |
| `--no-browser` | SUPPRESS | action='store_false', dest='open' |
| `--chrome` |  | type=Path |
| `--gap-threshold` |  | type=float |
| `--repetition-threshold` |  | type=int |
| `--server-timeout` |  | type=float |
| `--summary` | print analysis only; do not export or serve | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Analyze Exactus step traces and expose an interactive profiler.


### `__main__.py`

Run ``exactus.packages.performance`` through the project's virtualenv.


### `analyzer.py`

Analyze step traces for execution bottlenecks.

- `class PerformanceAnalyzer` — Convert timestamped step traces into performance diagnostics.
  - `analyze_events(cls, *, tool: str, source: Path, events: tuple[StepEvent, ...], gap_threshold: float=0.25, repetition_threshold: int=10) -> PerformanceRun` — Analyze already parsed events.
  - `analyze_file(cls, *, path: Path, gap_threshold: float=0.25, repetition_threshold: int=10) -> PerformanceRun` — Parse and analyze one trace file.
  - `analyze_paths(cls, *, paths: tuple[Path, ...], gap_threshold: float=0.25, repetition_threshold: int=10) -> tuple[PerformanceRun, ...]` — Discover and analyze every trace below the supplied paths.
  - `tree(*, events: tuple[StepEvent, ...], duration: float) -> tuple[TreeNode, ...]` — Build every thread's execution tree from depth and spans.
  - `integrate(*, samples: tuple[ResourceSample, ...], start: float, end: float) -> tuple[float, float, float, float] | None` — Integrate resource samples over an interval.
  - `summarize(*, samples: tuple[ResourceSample, ...]) -> ResourceSummary | None` — Aggregate resource samples.
  - `inferred(*, events: tuple[StepEvent, ...]) -> tuple[float, ...]` — Attribute each event the time until its thread's next event.

### `api.py`

Public high-level API for performance analysis.

- `class Performance` — Expose the performance analyzer as a compact application API.
  - `execute(cls, *, config: PerformanceConfig, runs: tuple[PerformanceRun, ...] | None=None, summary: bool=False, report: Path | None=None, writer: TextIO=stdout) -> int` — Run the complete analyze, report, export and serve flow.
  - `summarize(cls, *, runs: tuple[PerformanceRun, ...]) -> str` — Render a compact textual run summary.
  - `export(cls, *, paths: tuple[Path, ...], destination: Path) -> Path` — Analyze traces and export the interactive dashboard.
  - `serve(cls, *, paths: tuple[Path, ...], destination: Path, open_browser_window: bool=True, executable: Path | None=None, server_timeout: float=10.0) -> DashboardSession` — Analyze, export, serve, and optionally open the dashboard.
  - `report(cls, *, paths: tuple[Path, ...], destination: Path | None=None, gap_threshold: float=0.25, repetition_threshold: int=10) -> JsonObject` — Build the machine-readable report, optionally writing it.
  - `analyze(*, paths: tuple[Path, ...], gap_threshold: float=0.25, repetition_threshold: int=10) -> tuple[PerformanceRun, ...]` — Analyze traces below the supplied paths.

### `cli.py`

Command-line interface for performance trace analysis.

- `class Arguments` — Store typed command-line arguments.
  - Fields: `sources: list[str] | None`, `project: Path | None`, `output: Path | None`, `report: Path | None`, `serve: bool | None`, `open: bool | None`, `chrome: Path | None`, `gap_threshold: float | None`, `repetition_threshold: int | None`, `server_timeout: float | None`, `summary: bool`
- `class PerformanceCli` — Parse CLI arguments and dispatch performance analysis.
  - `run(cls, *, arguments: tuple[str, ...] | None=None) -> int` — Execute the CLI using CLI, pyproject, then package defaults.
  - `parser() -> ArgumentParser` — Build the argument parser.

### `config.py`

Resolve performance settings from defaults, pyproject, and overrides.

- `class Constants` — Group module-level constants.
  - `default_sources` = `('.',)`
  - `default_output` = `'performance'`
- `class PerformanceConfigOverrides` — Explicit overrides accepted by ``PerformanceConfig.load``.
  - Fields: `sources: tuple[str, ...] | None`, `output: Path | None`, `serve: bool | None`, `open_browser: bool | None`, `chrome: Path | None`, `gap_threshold: float | None`, `repetition_threshold: int | None`, `server_timeout: float | None`
- `class PerformanceConfig` — Store resolved performance analyzer settings.
  - Fields: `project: Path`, `sources: tuple[str, ...]`, `output: Path`, `serve: bool`, `open: bool`, `chrome: Path | None`, `gap_threshold: float`, `repetition_threshold: int`, `server_timeout: float`
  - `load(cls, *, project: Path | None=None, **overrides: Unpack[PerformanceConfigOverrides]) -> Self` — Resolve settings with explicit values taking highest precedence.
  - `paths(self) -> tuple[Path, ...]` — Expand configured source expressions relative to the project.
  - `validate(self) -> None` — Validate resolved settings.

### `dashboard.py`

Export and serve the interactive performance dashboard.

- `class DashboardExporter` — Write profiler assets and trace data to a destination directory.
  - `assets` = `('index.html', 'code.js')`
  - `styles` = `'styles'`
  - `export(cls, *, runs: tuple[PerformanceRun, ...], destination: Path) -> Path` — Export dashboard assets and raw trace data.
  - `raw_lines(*, run: PerformanceRun) -> list[str]` — Return a run's event and resource lines in time order.
  - `steps_data_js(*, data: dict[str, list[str]]) -> str` — Render trace data as a script-includable JavaScript document.

### `examples/__init__.py`

Executable examples for :mod:`exactus.packages.performance`.


### `examples/__main__.py`

Run the performance package example through the project virtualenv.


### `examples/run.py`

Build representative traces, analyze them, and export the dashboard.

- `main() -> int` — Exercise discovery, analysis, export, and reporting.

### `model.py`

Typed models for step-trace performance analysis.

- `class StepEvent` — Represent one parsed step event.
  - `thread` = `'main'`
  - `span` = `None`
  - `measured` = `None`
  - `phase` = `'point'`
  - `actor` = `''`
  - `template` = `''`
  - Fields: `index: int`, `timestamp: str`, `elapsed: float`, `depth: int`, `message: str`, `raw: str`
- `class Stage` — Represent a contiguous top-level execution stage.
  - Fields: `name: str`, `start: float`, `end: float`, `event_start: int`, `event_end: int`, `events: int`, `duration: float`
- `class Bottleneck` — Describe a suspicious interval or repeated operation.
  - Fields: `kind: str`, `label: str`, `start: float`, `end: float`, `duration: float`, `count: int`, `score: float`
- `class ActorStat` — Aggregate the time attributed to one step actor.
  - Fields: `name: str`, `count: int`, `inferred: float`, `measured: float`, `share: float`, `longest: float`, `p95: float`
- `class TemplateStat` — Aggregate one repeated operation after path/number abstraction.
  - Fields: `template: str`, `count: int`, `inferred: float`, `measured: float`, `longest: float`, `example: str`
- `class SlowStep` — Describe one individually slow step.
  - Fields: `index: int`, `label: str`, `start: float`, `duration: float`, `source: str`, `thread: str`
- `class ThreadStat` — Summarize one worker thread's activity.
  - Fields: `name: str`, `count: int`, `first: float`, `last: float`, `busy: float`
- `class ResourceSample` — Describe one process-tree resource sample.
  - `raw` = `''`
  - Fields: `elapsed: float`, `cpu: float`, `rss: float`, `threads: int`, `procs: int`, `read: float`, `write: float`, `scope: str`
- `class ResourceSummary` — Summarize every sample of a run.
  - Fields: `samples: int`, `mean_cpu: float`, `peak_cpu: float`, `peak_rss: float`, `read: float`, `write: float`, `peak_procs: int`
- `class TreeNode` — Describe one node of a thread's execution tree.
  - Fields: `id: int`, `event: int`, `parent: int | None`, `children: tuple[int, ...]`, `thread: str`, `level: int`, `start: float`, `end: float`, `total: float`, `self_time: float`
- `class PerformanceRun` — Contain a fully analyzed tool execution.
  - `actors` = `()`
  - `templates` = `()`
  - `slowest` = `()`
  - `threads` = `()`
  - `silent` = `0.0`
  - `samples` = `()`
  - `resources` = `None`
  - `nodes` = `()`
  - Fields: `tool: str`, `source: Path`, `events: tuple[StepEvent, ...]`, `stages: tuple[Stage, ...]`, `bottlenecks: tuple[Bottleneck, ...]`, `duration: float`, `event_rate: float`, `largest_gap: float`
- `class Constants` — Group module-level constants.
  - `step_file` = `'steps.txt'`

### `parser.py`

Parse and discover Exactus step traces.

- `class Constants` — Group module-level constants.
  - `line` = `compile_pattern(pattern='^(?P<stamp>\\S+)\\s+\\+\\s*(?P<elapsed>\\d+(?:\\...`
  - `trailer` = `compile_pattern(pattern='\\s@(?P<key>[a-z_]+)=(?P<value>\\S+)\\s*$')`
  - `embedded` = `compile_pattern(pattern='(?:\\bin |, |\\()(?P<value>\\d+(?:\\.\\d+)?)(?P<...`
  - `separator` = `compile_pattern(pattern=':| — ')`
  - `path` = `compile_pattern(pattern='(?:[A-Za-z]:)?(?:\\.{0,2}/)?[\\w.@+-]+(?:/[\\w.@...`
  - `number` = `compile_pattern(pattern='\\d+(?:\\.\\d+)?')`
- `class StepParser` — Discover and parse ``exactus.packages.steps`` trace files.
  - `parse_file(cls, *, path: Path) -> tuple[StepEvent, ...]` — Parse one trace file.
  - `parse_lines(cls, *, lines: tuple[str, ...]) -> tuple[StepEvent, ...]` — Parse raw trace lines.
  - `discover(*, paths: tuple[Path, ...]) -> tuple[Path, ...]` — Discover step traces from files and directories.
  - `tool_name(*, path: Path) -> str` — Infer the tool identifier from a trace path.
  - `parse_samples(*, lines: tuple[str, ...]) -> tuple[ResourceSample, ...]` — Parse ``~sample`` resource lines.
  - `template(*, message: str) -> str` — Abstract paths and numbers so repeated operations group.

### `report.py`

Build the machine-readable performance report.

- `class Constants` — Group module-level constants.
  - `schema` = `'exactus.performance-report/v1'`
  - `digits` = `6`
  - `file_name` = `'report.json'`
- `class PerformanceReport` — Serialize analyzed runs into one complete JSON document.
  - `build(cls, *, runs: tuple[PerformanceRun, ...]) -> JsonObject` — Build the report document.
  - `write(cls, *, runs: tuple[PerformanceRun, ...], path: Path) -> Path` — Write the report as UTF-8 JSON.

### `session.py`

Shared server and browser lifecycle for exported performance dashboards.

- `class DashboardSession` — Own or adopt the server and browser used by one dashboard.
  - `browser` = `None`
  - Fields: `directory: Path`, `pid: int`, `url: str`, `reused: bool`
  - `close(self) -> None` — Close owned resources without killing an adopted server.
- `class DashboardLauncher` — Launch exported dashboards through shared package infrastructure.
  - `serve(*, directory: Path, open_browser_window: bool=True, executable: Path | None=None, server_timeout: float=10.0) -> DashboardSession` — Serve a dashboard and optionally open it with the browser package.

### `web/__init__.py`

Packaged static assets for the interactive performance profiler.


## Examples

Runnable demonstration for `exactus/packages/performance/`.

Build representative traces, analyze them, and export the dashboard.

```bash
python -m exactus.packages.performance.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md), [`browser`](../browser/DOCS.md), [`server`](../server/DOCS.md)
- Used by: `tests/packages/performance/test_performance.py`, `tools/performance/main.py`

## Tests

Tests live in `exactus/tests/packages/performance/`.

- `test_performance.py` — Tests for parsing, analysis, dashboard export, serving, and CLI behavior. (25 tests)
  - `test_analyzer_attributes_time_per_actor_template_and_thread`
  - `test_analyzer_builds_stages_and_bottlenecks`
  - `test_cli_serve_shutdown_path`
  - `test_cli_summary_export_and_missing`
  - `test_config_defaults_without_pyproject`
  - `test_config_handles_non_table_tool_sections`
  - `test_config_reads_pyproject_and_cli_precedence`
  - `test_config_rejects_invalid_table_values`
  - `test_config_rejects_out_of_range_values`
  - `test_config_root_and_paths_expansion`
  - `test_dashboard_launcher_uses_package_lifecycles`
  - `test_empty_analysis_is_safe`
  - `test_example_runs`
  - `test_export_writes_assets_and_raw_lines`
  - `test_exporter_accepts_preanalyzed_runs`
  - `test_launcher_cleans_up_when_browser_launch_fails`
  - `test_launcher_fails_when_server_never_ready`
  - `test_launcher_keeps_reused_server_when_not_ready`
  - `test_parser_discovers_and_parses`
  - `test_parser_ignores_malformed_lines`
  - `test_parser_reads_trailers_and_embedded_durations`
  - `test_report_is_machine_readable_and_written_without_a_server`
  - `test_reused_dashboard_server_is_not_terminated`
  - `test_samples_are_parsed_and_summarized`
  - `test_server_serves_exported_index`

<!-- exactus:reference:end -->
