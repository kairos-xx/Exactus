# `performance/`

Analyze Exactus step traces and expose an interactive profiler.

Beyond stalls and stages, the profiler attributes time: each step owns
the time until the next step on its thread, grouped by actor and by
repeated operation (paths and numbers abstracted). It reads the optional
`@thread=`, `@span=` and `@dur=` trailers written by
`exactus.packages.steps` (`span()` and `trace(duration=...)`), plus
`in 1.2s`-style phrases already present in messages. The dashboard adds
Hotspots (time by actor/operation, slowest steps, a stacked time-share
chart) and Workers (per-thread Gantt and load) next to Bottlenecks.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Analyze Exactus step traces and expose an interactive profiler.
- [`__main__.py`](__main__.py) — Run ``exactus.packages.performance`` through the project's virtualenv.
- [`analyzer.py`](analyzer.py) — Analyze step traces for execution bottlenecks.
- [`api.py`](api.py) — Public high-level API for performance analysis.
- [`cli.py`](cli.py) — Command-line interface for performance trace analysis.
- [`config.py`](config.py) — Resolve performance settings from defaults, pyproject, and overrides.
- [`dashboard.py`](dashboard.py) — Export and serve the interactive performance dashboard.
- [`model.py`](model.py) — Typed models for step-trace performance analysis.
- [`parser.py`](parser.py) — Parse and discover Exactus step traces.
- [`report.py`](report.py) — Build the machine-readable performance report.
- [`session.py`](session.py) — Shared server and browser lifecycle for exported performance dashboards.

### Subdirectories

- [`examples/`](examples/README.md) — Executable examples for :mod:`exactus.packages.performance`.
- [`web/`](web/README.md) — Packaged static assets for the interactive performance profiler.

<!-- exactus:inventory:end -->

## Machine-readable report

Every run writes `report.json` (schema `exactus.performance-report/v1`)
next to the dashboard — no web server or browser is needed. It holds, per
tool: stages, bottlenecks, actors, operations, slowest steps, threads,
resource summary and samples, the execution tree and the parsed events.

- CLI: `--report PATH` chooses the location; the default is
  `<output>/report.json`, also written with `--summary`.
- API: `Performance.report(paths, destination=None)` returns the same
  object and optionally writes it.
- Dashboard: the **⭳ JSON report** button downloads the exported file.
