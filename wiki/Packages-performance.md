[Home](Home.md) > [Packages](Packages.md) > performance

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/performance/`](../exactus/packages/performance/) | [`exactus/tests/packages/performance/`](../exactus/tests/packages/performance/) | [`DOCS.md`](../exactus/docs/packages/performance/DOCS.md) |

[< Packages-patcher](Packages-patcher.md) · [Packages index](Packages.md) · [Packages-pmanager >](Packages-pmanager.md)
