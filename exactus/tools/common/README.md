# `exactus/tools/common/`

Leaf primitives shared by every exactus tool. Modules here import only the
standard library and each other, never another part of the repository, so
any tool, script or test can depend on them without cycles.

## Directory contents

### Files

#### `activity.py`

Fixed `@activity.json` schema (`exactus/activity/v1`) combining
heartbeat, progress and recent activity, written by every tool run and
every pipeline run. Public API: `ActivityTables` (schema id, file name,
event limit, levels, phases), `ActivityEvent`, `ActivityHeartbeat`,
`ActivityProgress`, `ActivityDocument` (`payload()`/`from_payload()`),
`ActivityLog` (thread-safe bounded event list) and `ActivityFile`
(atomic `write()`/`write_json()` and `read()`).

#### `__init__.py`

Leaf primitives shared by every exactus tool.

#### `envelope.py`

Normalized report envelope built from facts the runner knows. Public
API: `Constants` — Envelope constants.; `RunFacts` — Facts about one tool
run known to the runner, not the tool.; `Redaction` — Hide credentials
in text a report shows.; `EnvironmentProbe` — Collect allowlisted,
redacted facts about the host.; `Envelope` — Assemble the
`tool`, `run`, `invocation`, `environment`, `gate` and `artifacts`
blocks.

#### `json_types.py`

JSON value types shared by the exactus tools. Public API: `JsonScalar`,
`JsonValue`, `JsonDict` (a dictionary with a formatted `tojson`
property) and `JsonObject`.

#### `process_control.py`

Cross-invocation exactus ownership and process termination primitives.
Public API: `new_run_id()`, `process_exists()`, `descendants()`,
`terminate_tree()`, `exit_if_replaced()`, `read_json()` and `write_json()`.
Conflicting runs use `terminate_tree(replaced=True)` so the previous
exactus prints a cancellation notice and exits normally with status 130.
The live pipeline table marks adopted report results with `PASS*` or
`FAIL*` and explains the marks below the table.

#### `stderr_capture.py`

Standard-error capture: the raw `stderr.log` transcript plus
line/level counting (`error`/`warning`/`info` per completed line).
Public API: `StderrTables`, `StderrRecorder` (chunks to bounded line
counts) and `StderrMirror` (records a process's `sys.stderr` while
forwarding it).

#### `snippets.py`

Numbered source excerpts around finding lines for normalized reports.
Reads are bounded (scan bytes, bytes and characters per line, context
depth capped at 50), binary files are skipped and paths resolving
outside the project root (`..`, absolute paths, escaping symlinks) are
refused. Public API: `SnippetLimits` (bounds and fence-language tables),
`ExcerptLine`, `Excerpt` (`payload()`), `SnippetSource` (`language()`,
`locate()`, `read()`), `excerpt()`, `finding_excerpt()` and
`with_excerpts()`.

#### `sprint.py`

Shared flushed-writer printing helpers for scripts and examples. Public
API: `SprintStyle`, `Writer` and `sprint()`. A `DEBUG.txt` marker at the
exactused project root makes `sprint` calls append capture records.


#### `cli.py`

Shared command-line and glob helpers for project exactuss. Public API: `map_lanes()` — Run ``work`` once per lane on pooled threads, preserving order.; `consume()` — Explicitly consume a return value used only for side effects.; `heartbeat_timestamp()` — Return the local wall-clock time for heartbeat payloads.; `ExactusCommonTables` — Shared lookup tables and compiled values.; `context_lines()` — Parse a ``--context-lines`` value.; `add_common_arguments()` — Add the common exactus CLI surface.; `parse_common_arguments()` — Parse the common standalone exactus CLI surface.; `resolve_report_output()` — Resolve an analyzer report directory for optional-output CLIs.; `resolve_output()` — Resolve an output directory, honoring cwd-relative paths.; `match_path()` — Return whether a path passes normalized glob filters.; `linter_platform_supported()` — Return whether the bundled linter toolchain can execute locally.; `resolve_linter_toolchain()` — Resolve the canonical bundled Ruff + BasedPyright executable.; `linter_command()` — Return the command prefix that invokes one linter.; `resolve_exactus_tool_bundle()` — Resolve the offline Linux AMD64 exactus tool bundle.; `exactus_bundle_cache()` — Materialize and return the offline bundle's payload cache.; `activate_exactus_tool_bundle()` — Expose bundled modules to the current interpreter.; `exactus_tool_prefix()` — Resolve an installed tool or the bundle, or ``None``.; `exactus_tool_command()` — Resolve an installed exactus tool or the offline Linux AMD64 bundle.; `expand_paths()` — Expand path/glob arguments relative to root deterministically.


#### `config.py`

Discover `[tool.exactus]` settings in `pyproject.toml` files and render them as tool arguments. Public API: `discover()` — Collect exactus configuration files, nearest first.; `argv_for()` — Render the configured arguments of one tool, lowest priority first.; `orchestrator_arguments()` — Render ``check``'s own settings for pipeline-style invocations.; `validate()` — Reject unknown tables and keys before any tool starts.; `effective()` — Report each option's final value and the layer that set it.; `resolve_arguments()` — Prefix a standalone tool's arguments with its configuration.


#### `progress.py`

Canonical `exactus-run/v1` progress and lifecycle envelope of the
internal surfaces — the per-tool `ARTIFACTS/.progress.json` channel,
the `PIPELINES/ARTIFACTS/pipeline.json` ownership file, and the Linux
AMD64 bundle builder's `parts/@activity.json`. (The user-facing
`<TOOL>/ARTIFACTS/@activity.json` and
`PIPELINES/<PIPELINE>/ARTIFACTS/@activity.json` use the fixed
`exactus/activity/v1` schema of `common/activity.py`.) All of them
serialize the same
dataclasses: `kind`/`name`/`run_id`/`pipeline_run_id`/`pid`, `status`
(`WAITING`/`RUNNING`/`DONE`/`FAIL`/`INTERRUPT`), fractional `progress`
(0.0–1.0) with `completed`/`total`/`step`/`detail`, ISO timestamps
(`started_at`/`updated_at`/`finished_at`), `elapsed_seconds`, nested
`items` (`RunItem` — pipeline tools or bundle build steps), and
`extra` for surface-specific metadata (build `target`, archive `parts`,
tool environment). Public API: `RunItem` — Serialize one child work
item.; `RunDocument` — Serialize one canonical run document.;
`utc_now()` — Return the current UTC instant in ISO 8601.


#### `digest.py`

Summarize tool reports into failure digests for aggregate reports. Public API: `digest_report()` — Summarize one tool report.; `render_failure()` — Render one failing tool as Markdown.; `digest_data()` — Convert a digest to JSON-ready data.; `ToolDigest` — A tool report summarized for an aggregate report.; `FindingLine` — One finding reduced to what a reader needs.


#### `terminal.py`

Responsive ANSI terminal presentation for exactus execution. Public API: `ResultRow` — Represent result row.; `ExactusTerminal` — Render the only user-facing exactus terminal protocol.; `dsr_reply()` — Return whether ``stdout`` accepts ANSI cursor positioning.; `dsr_cursor_moves()` — Verify one reversible cursor move against the output terminal.


#### `report_comparison.py`

Compare normalized findings between report generations without depending on
the report renderer. Provides capture, comparison, and lifecycle cleanup.
Baselines survive run cleanup and are inherited by tool workers. Comparisons
include finding occurrences, per-source/category/rule sections, numeric
summary and extension metrics, and per-tool snapshots in pipeline reports.

### Subdirectories

#### `templates/`

Shared data assets: the offline web report bundle (`html/`) and the core
Markdown report template, partials, base mapping and examples
(`markdown/`).
- `conflict_copies.py` — File.

- [`directory_docs.py`](directory_docs.py) — Portable folder READMEs for generated report artifacts.

- [`report_time.py`](report_time.py) — Readable UTC timestamps shared by all report formats.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Leaf primitives shared by every exactus tool.
- [`activity.py`](activity.py) — Fixed ``@activity.json`` schema: heartbeat, progress and activity.
- [`api.py`](api.py) — Process-isolated Python API for canonical exactus tools.
- [`catalog.py`](catalog.py) — Canonical exactus tool and pipeline catalog.
- [`cli.py`](cli.py) — Shared command-line and glob helpers for project exactuss.
- [`collect_files.py`](collect_files.py) — Bundle report finding files into a ``FILES`` evidence folder.
- [`config.py`](config.py) — Discover ``\[tool.exactus\]`` settings and render them as tool arguments.
- [`conflict_copies.py`](conflict_copies.py) — Reconcile numbered sync copies without discarding unique project data.
- [`digest.py`](digest.py) — Summarize tool reports into failure digests for aggregate reports.
- [`directory_docs.py`](directory_docs.py) — Document artifact folders from their innermost children outward.
- [`directory_inventory.py`](directory_inventory.py) — Maintain a managed, bottom-up directory inventory in README documents.
- [`envelope.py`](envelope.py) — Build the normalized report envelope from facts the runner knows.
- [`execution.py`](execution.py) — Shared standalone exactus entry-point reporting.
- [`json_types.py`](json_types.py) — JSON value types shared by the exactus tools.
- [`models.py`](models.py) — Shared exactus orchestration models.
- [`pipeline_supervisor.py`](pipeline_supervisor.py) — Provide transactional ownership and reset coordination for pipelines.
- [`process_control.py`](process_control.py) — Cross-invocation exactus ownership and process termination primitives.
- [`progress.py`](progress.py) — Uniform ``exactus-run/v1`` live-run progress document schema.
- [`registry.py`](registry.py) — Cross-process exactus run registry backed by an embedded database.
- [`report_comparison.py`](report_comparison.py) — Compare normalized exactus findings with the preceding report bundle.
- [`report_time.py`](report_time.py) — Format recorded report times without changing their machine values.
- [`runtime.py`](runtime.py) — Shared exactus runtime state, progress, and summary protocol.
- [`snippets.py`](snippets.py) — Capture numbered source excerpts around report findings.
- [`sprint.py`](sprint.py) — Shared flushed-writer printing helpers for scripts and examples.
- [`stderr_capture.py`](stderr_capture.py) — Standard-error capture: ``stderr.log`` transcripts with line counts.
- [`terminal.py`](terminal.py) — Responsive ANSI terminal presentation for exactus execution.
- [`terminal_progress.py`](terminal_progress.py) — Animated terminal progress bar with responsive determinate modes.
- [`toml.py`](toml.py) — Dependency-free TOML serializer compatible with tomllib.
- [`tool_worker.py`](tool_worker.py) — Run canonical exactus tools in detached pmanager workers.

### Subdirectories

- [`examples/`](examples/README.md) — `run.py` creates a disposable Python project and exercises the process coordination system with four overlapping Exactus invocations:
- [`process_layer/`](process_layer/README.md) — Authenticated Exactus process identification and termination.
- [`templates/`](templates/README.md) — Data assets shared by the exactus tools. The inventory below documents every direct file and child directory.

<!-- exactus:inventory:end -->
