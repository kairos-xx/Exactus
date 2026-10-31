# Coordination collision example

`run.py` creates a disposable Python project and exercises
the process coordination system with four overlapping Exactus invocations:

1. a `unified` pipeline running lints, streaming kwargs/type-hints, and README;
2. a second identical pipeline invocation, which joins the first owner and
   resets its shared work graph without killing the owner process;
3. another identical pipeline invocation arriving during the reset; and
4. a standalone kwargs/type-hints request arriving while lints is active.

Every invocation resolves the same project-root hash. The pipeline callers
mirror one execution and one progress model instead of creating competing
pipeline contexts. The owner records the join and reset in its event timeline,
restarts worker generations in place, requeues completed tasks, and lets
GLOBAL move backward as the shared total changes. The run also demonstrates
dependency priority, tool adoption, file-level releases, source reader/writer
barriers, and normalized terminal results when analyzers report findings.

## Automated run

Run from the repository root:

```bash
python -m exactus.tools.common.examples
```

The driver prefixes lifecycle snapshots and writes each invocation's untouched
terminal transcript under `<demo-project>/.demo-logs/`. It intentionally leaves
the temporary project in place and prints its path, allowing inspection of:

```text
EXACTUS_RESULTS/.runtime/runs.db
EXACTUS_RESULTS/.runtime/pipeline_requests/<run-id>/*.json
EXACTUS_RESULTS/PIPELINES/UNIFIED/ARTIFACTS/@activity.json
EXACTUS_RESULTS/<TOOL>/ARTIFACTS/@activity.json
EXACTUS_RESULTS/<TOOL>/result.json
```

The generated source deliberately omits annotations so analyzers have real
work. A configured analyzer may therefore pass or report findings; a worker
crash or “exited before reporting” is never an expected outcome.

## Four-terminal run

To see every native progress display separately, prepare the project without
starting processes:

```bash
python -m exactus.tools.common.examples \
  --prepare-only
```

The script prints four quoted commands. Run each in a separate terminal in the
displayed order, waiting roughly one second between commands. Watch for:

- the second pipeline terminal joining and mirroring the first owner process;
- a `shared pipeline reset requested ...` event in the pipeline timeline;
- the original pipeline PID remaining alive while progress resets;
- kwargs waiting at a file boundary while lints owns a mutating activity;
- released files contributing to kwargs before every lint activity settles;
- resets and tool reruns causing GLOBAL to move backward and resynchronize;
- child errors coloring task and GLOBAL progress; and
- every invocation producing its own normalized report instead of disappearing.

## Files

- `run.py` — Prepare and run the overlapping-process demo.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Provide runnable process-coordination examples.
- [`__main__.py`](__main__.py) — Run the process-coordination collision example.
- [`run.py`](run.py) — Run overlapping Exactus processes against one disposable workspace.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
