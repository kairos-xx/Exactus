# steps/

Timestamped step tracing shared by the Exactus packages: one
`timestamp +elapsed step` line per event in a plain text file.

## Behavior

- `step_log(path=...)` creates missing parents, opens the file for
  writing and becomes the process-wide active log for the context.
- Nested `step_log` contexts reuse the already active log instead of
  truncating the file, so a caller may activate the same run's log
  inside an outer activation.
- `trace(step=..., depth=...)` is a no-op until a log is active, so
  packaged tools can instrument themselves unconditionally.
- Writes are serialized through a lock and flushed per line; a file
  that cannot be opened or written degrades to a silent no-op.
- The nearest `pyproject.toml` — found by walking up from the
  destination, then from the working directory — can disable tracing:
  `[tool.steps] write = false` discards every call and never creates
  the file.
- Depth levels mark nesting: `0` tool boundary, `1` stage, `2` substep,
  `3` detail and `4` per-file record.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Timestamped step tracing shared by the Exactus packages. |
| `__main__.py` | Run the step-trace demonstration. |
| `core.py` | Record a timestamped step trace of a tool run in a text file. |
| `examples/` | Runnable demonstration for `exactus/packages/steps/`. |
| `sampler.py` | Sample process-tree CPU, memory and disk I/O while a step log is open. |

Run it as a module: `python -m exactus.packages.steps`.

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Timestamped step tracing shared by the Exactus packages.


### `__main__.py`

Run the step-trace demonstration.


### `core.py`

Record a timestamped step trace of a tool run in a text file.

- `class Constants` — Group module-level constants.
  - `active` = `None`
- `class StepLog` — Append timestamped, depth-indented step lines to one file.
  - `__init__(self, *, path: Path) -> None` — Open ``path`` for writing, degrading to a no-op on failure.
  - `next_span(self) -> int` — Allocate a span identifier unique within this log.
  - `write(self, *, step: str, depth: int=0, duration: float | None=None, span: int | None=None) -> None` — Append one timestamped step line.
  - `write_sample(self, fields: str) -> None` — Append one ``~sample`` resource line without thread trailers.
  - `close(self) -> None` — Stop sampling, then flush and close the underlying stream.
- `step_log(*, path: Path) -> Generator[StepLog]` — Activate a step log for the duration of the context.
- `trace(*, step: str, depth: int=0, duration: float | None=None) -> None` — Forward one step line to the active log, when one exists.
- `span(*, step: str, depth: int=0) -> Generator[None]` — Record a step's begin line and a measured end line.
- `main(*, path: Path | None=None) -> int` — Write a small demonstration trace beside the package.

### `examples/__init__.py`

Runnable demonstration for the ``steps`` package.


### `examples/__main__.py`

Run the steps example with the project virtual environment.


### `examples/run.py`

Write a timestamped step trace for a small simulated tool run.

- `class Constants` — Collect shared example paths and the simulated stage map.
  - `here` = `Path(__file__).resolve().parent`
  - `work` = `here / '.scratch'`
  - `destination` = `work / 'ARTIFACTS' / 'steps.txt'`
  - `stages` = `(('collect', ('src/app.py', 'src/lib.py')), ('check', ('src/app.py', 'src...`
- `main() -> int` — Emit a simulated tool run and print the resulting trace.

### `sampler.py`

Sample process-tree CPU, memory and disk I/O while a step log is open.

- `class Constants` — Group module-level constants.
  - `mib` = `1024.0 * 1024.0`
- `class ResourceSampler` — Emit periodic resource usage fields for the process tree.
  - `__init__(self, *, emit: Callable[[str], None], interval: float) -> None` — Prepare a stopped sampler.
  - `start(self) -> None` — Begin sampling on a daemon thread.
  - `stop(self) -> None` — Stop sampling and wait for the thread to finish.

## Examples

Runnable demonstration for `exactus/packages/steps/`.

Write a timestamped step trace for a small simulated tool run.

```bash
python -m exactus.packages.steps.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`

## Dependencies and consumers

- Used by: `packages/all_lints/core.py`, `packages/group_final/core.py`, `packages/meaningful/api.py`, `packages/tree/core.py`, `packages/zip_components/core.py`, `tests/packages/steps/test_examples.py`, `tests/packages/steps/test_steps.py`, `tests/tools/coverage_tests/test_steps_trace.py`, `tests/tools/lints/test_lints.py`, `tools/common/runtime.py`, `tools/coverage_tests/core.py`, `tools/coverage_tests/main.py`, `tools/coverage_tests/meaningful.py`, `tools/coverage_tests/report.py`, `tools/coverage_tests/tracebacks.py`, `tools/docs/core.py`, `tools/docs/main.py`, `tools/frontend/main.py`, `tools/kwargs_typehints/core.py`, `tools/kwargs_typehints/main.py`, `tools/lints/compliance.py`, `tools/lints/core.py`, `tools/lints/css_tokens.py`, `tools/lints/js_delimiters.py`, `tools/lints/js_function_blocks.py`, `tools/lints/main.py`, `tools/lints/packages_pipeline.py`, `tools/lints/shebang.py`, `tools/performance/main.py`, `tools/readme/core.py`, `tools/readme/main.py`, `tools/record/main.py`, `tools/self_test/main.py`, `tools/visual_cause/main.py`

## Tests

Tests live in `exactus/tests/packages/steps/`.

- `test_examples.py` — Coverage for the ``exactus/packages/steps/examples`` demonstration. (4 tests)
  - `test_example_module_runs_as_a_script`
  - `test_example_writes_and_prints_the_trace`
  - `test_examples_main_module_runs_the_demo`
  - `test_package_main_module_runs_the_demo`
- `test_steps.py` — Exercise the reusable timestamped step trace. (15 tests)
  - `test_configured_sampling_writes_resource_lines`
  - `test_main_writes_a_demonstration_trace`
  - `test_nested_step_log_reuses_the_active_log`
  - `test_pyproject_without_steps_section_keeps_writing`
  - `test_sampling_is_off_without_configuration`
  - `test_span_without_an_active_log_only_runs_the_body`
  - `test_span_writes_begin_and_measured_end_lines`
  - `test_step_log_context_resets_active_and_closes`
  - `test_step_log_degrades_when_destination_cannot_open`
  - `test_step_log_writes_timestamped_depth_lines`
  - `test_trace_is_a_noop_without_an_active_log`
  - `test_worker_threads_are_tagged_and_main_is_not`
  - `test_write_failure_disables_the_stream`
  - `test_write_false_discards_every_step`
  - `test_write_true_records_steps`

<!-- exactus:reference:end -->
