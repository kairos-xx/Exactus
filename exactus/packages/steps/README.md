# `steps/`

Timestamped step tracing shared by the Exactus packages.

`step_log(path=...)` opens a destination text file for one run and makes
it the process-wide active log; `trace(step=..., depth=...)` appends one
`timestamp +elapsed step` line through that active log, so instrumented
helpers need no plumbing of their own. Nested `step_log` contexts reuse
the already active log instead of truncating the file, writes are
serialized through a lock so parallel workers can emit lines safely, and
a file that cannot be opened degrades to a silent no-op.

Depth levels mark nesting: `0` tool boundary, `1` stage, `2` substep,
`3` detail and `4` per-file record.

Lines may end with `@key=value` trailers that carry machine-readable
facts: `@thread=NAME` (worker threads only), `@span=N` and `@dur=1.234s`.
`span(step=..., depth=...)` writes the begin line, then a ` — done` line
with the measured duration, and `trace(duration=...)` attaches a known
duration to one line. The performance profiler reads these trailers.

The nearest `pyproject.toml` (searched from the destination's ancestors,
then the working directory) can disable tracing entirely:
`[tool.steps] write = false` leaves the file uncreated and discards
every step call.

## Usage

```python
from exactus.packages.steps import step_log, trace

with step_log(path=output_dir / "ARTIFACTS" / "steps.txt"):
    trace(step="stage: collect", depth=1)
    ...
```

`__main__.py` makes the directory itself runnable as well:
`python exactus/packages/steps` or `python -m exactus.packages.steps` switches to the
project interpreter when one exists and writes a short demonstration
trace to `.scratch/steps.txt`. `examples/` holds a runnable demo that
simulates a staged tool run — including nested `step_log` reuse and
worker-thread writes — and prints the resulting trace.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Timestamped step tracing shared by the Exactus packages.
- [`__main__.py`](__main__.py) — Run the step-trace demonstration.
- [`core.py`](core.py) — Record a timestamped step trace of a tool run in a text file.
- [`sampler.py`](sampler.py) — Sample process-tree CPU, memory and disk I/O while a step log is open.

### Subdirectories

- [`examples/`](examples/README.md) — Runnable demonstration for `exactus/packages/steps/`.

<!-- exactus:inventory:end -->
