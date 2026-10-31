# `examples/`

Runnable demonstration for `exactus/packages/steps/`.

`run.py` recreates the git-ignored `.scratch/` folder on every run,
activates `step_log` on `steps.txt` and emits a simulated pipeline: a
tool boundary, stages, substeps and per-file records. A nested
`step_log` context demonstrates that inner tools reuse the already
active log instead of truncating it, and worker threads demonstrate
that writes are serialized safely. The finished trace is printed so the
timestamp, elapsed and depth columns are visible.

```bash
python -m exactus.packages.steps.examples
```

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Runnable demonstration for the ``steps`` package.
- [`__main__.py`](__main__.py) — Run the steps example with the project virtual environment.
- [`run.py`](run.py) — Write a timestamped step trace for a small simulated tool run.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
