# tools/common/

The shared leaf primitives every tool builds on: configuration,
normalized envelope, report rendering inputs, terminal UI, source
excerpts and the packaged utilities.

## Files

| File | Description |
|---|---|
| `cli.py` | Shared CLI and glob helpers; bundle-dir resolution (`_host_bundle_dirs`); orchestrator-key filtering; `is_reports_tree` fingerprints report trees by content (`.runtime/`, `result.json` + `result.md`, `ARTIFACTS/@activity.json`) so renamed results roots are pruned from source discovery. |
| `api.py` | Process-isolated Python API for canonical tools: invokes each tool's module entry point in a detached worker, parses its `result.json` back and returns typed run results without sharing the caller's process state. |
| `catalog.py` | Canonical tool/pipeline catalog: tools are executable leaves, pipelines hold only references to tool ids or other pipelines; resolution flattens nested pipelines in declaration order and de-duplicates by canonical id. |
| `config.py` | `[tool.exactus]` discovery and rendering: upward `pyproject.toml` walk with `root=true`, `--config`/`--no-config`, layered precedence, per-option provenance, path resolution relative to the declaring file, `--show-config`. |
| `parser.py` | Shared `ExactusArgumentParser`: folds `-`/`_` in long-option names so every CLI accepts `--foo-bar` and `--foo_bar` identically; collisions degrade to exact matching. |
| `envelope.py` | Build the normalized report envelope — `tool`/`run`/`invocation`/`environment`/`gate`/`artifacts` — plus crash/cancel stamping. |
| `execution.py` | Shared standalone entry-point reporting: wraps a tool's main() with the envelope, artifact directory layout, activity heartbeat and exit-status contract used by every `exactus --<tool>` run. |
| `models.py` | Shared orchestration dataclasses and records exchanged between the runner, workers and supervisors — run/item states, findings counters and lifecycle payloads. |
| `activity.py` | Fixed `@activity.json` schema: heartbeat, progress and activity. |
| `progress.py` | `exactus-run/v1` live-run progress document schema. |
| `runtime.py` | Shared runtime state, progress and summary protocol: per-run mutable state guards, progress event emission and the summary contract tools fill at the end of a run. |
| `terminal.py` | Responsive ANSI terminal presentation for executions; progress bars mark the cell where a tool failed with a red `x`, in the tool row and at its position inside the pipeline GLOBAL bar. |
| `terminal_progress.py` | Animated determinate progress bar primitives: responsive width/ETA rendering driven by `terminal.py` for long-running stages. |
| `digest.py` | Summarize tool reports into failure digests for aggregate reports. |
| `directory_docs.py` | Document artifact folders from their innermost children outward. |
| `directory_inventory.py` | Managed bottom-up README inventories. |
| `report_comparison.py` | Compare normalized findings with the preceding report bundle. |
| `report_time.py` | Format recorded report times without changing machine values. |
| `snippets.py` | Numbered source excerpts around findings, with root containment, symlink and byte/line bounds. |
| `collect_files.py` | `--collect-files` evidence bundling: every file `result.json` lists findings for is copied into `<report>/FILES/` — `files.zip` keeps the project-relative layout, `TREE.txt` renders the archive through `exactus.packages.tree`, `README.md` describes it. |
| `stderr_capture.py` | `stderr.log` transcripts with line counts. |
| `sprint.py` | Flushed-writer printing helpers. |
| `process_control.py` | Cross-invocation ownership/termination primitives. |
| `pipeline_supervisor.py` | Transactional pipeline ownership and reset coordination over the model queries: claims a pipeline run, records stage transitions and aborts competing writers safely. |
| `registry.py` | Cross-process run registry in `EXACTUS_RESULTS/.runtime/runs.db` (SQLite WAL): each run claims a row and terminates live rows writing the same output directory or intersecting targets, so reruns never race a stale writer; bounded by `runtime-max-runs`/`runtime-max-size`. |
| `conflict_copies.py` | Reconcile numbered sync copies without discarding unique data. |
| `json_types.py` | JSON value types. |
| `toml.py` | Dependency-free TOML serializer compatible with `tomllib` output — scalar/table emission used for rendered configuration and manifests. |
| `templates/` | Shared Markdown template/mapping for `result.md` and the error report. |
| `process_layer/` | Internal authenticated process control: loopback identity responder, registry-free `discover`/`identify`, verified `ProcessTerminator`/`terminate_tree`; consumed by the orchestrator only, never standalone. |
| `tool_worker.py` | Detached `pmanager` tool workers: spawns a canonical tool module in its own process with the orchestrator control-channel environment, applies worker-side termination requests through the `process_layer` access layer, and streams progress back to the runner. |

## Configuration precedence

Highest first: tool CLI/`--tool-arg` → common CLI → pipeline-scoped tool
table → tool table → common table → catalog preset → parser defaults.
Scalars/booleans override; lists combine with nearest configuration last.
`resolve_arguments` skips reapplying configuration when
`EXACTUS_ORCHESTRATED=1` so layers are never resolved twice.

## Report contract

`envelope.py` is the single place the normalized envelope is
constructed; tools supply `summary`/`scope`/`findings`/`extension`, and
the runner adds `tool`/`run`/`invocation`/`environment`/`gate`/
`artifacts`. `result.json` is the semantic source — Markdown and HTML
render from it, never the reverse.

## process_layer/

Internal authenticated process identification and termination —
consumed by the orchestrator and tool workers, never a standalone tool.
There is no registry, PID file, or discovery database: identity is
proven live over a private loopback listener.

- `access.py` provisions the shared secret (`.runtime/authkey`,
  `EXACTUS_AUTHKEY` override) and wires the `RunRegistry` over
  `.runtime/runs.db`.
- `process_control.py` provides `IdentityResponder` plus
  `identify()`/`discover()`: a nonce/HMAC handshake on `127.0.0.1`,
  listener-table enumeration that skips per-process `AccessDenied`, and
  identity validation bound to process creation time — so a reused PID
  impersonating a stale record is rejected.
- `process_termination.py` provides `ProcessTerminator` and
  `terminate_tree`: child-first teardown restricted to trees verified
  through `identify`, with PID-reuse and stale-record protection.

`exactus/__main__.py` wires the responder around every run and drives
`--kill`/`--kill-all`; `tools/common/tool_worker.py` uses the same
access layer for worker-side termination requests.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Leaf primitives shared by every exactus tool. |
| `activity.py` | Fixed ``@activity.json`` schema: heartbeat, progress and activity. |
| `api.py` | Process-isolated Python API for canonical exactus tools. |
| `catalog.py` | Canonical exactus tool and pipeline catalog. |
| `cli.py` | Shared command-line and glob helpers for project exactuss. |
| `collect_files.py` | Bundle report finding files into a ``FILES`` evidence folder. |
| `config.py` | Discover ``[tool.exactus]`` settings and render them as tool arguments. |
| `conflict_copies.py` | Reconcile numbered sync copies without discarding unique project data. |
| `digest.py` | Summarize tool reports into failure digests for aggregate reports. |
| `directory_docs.py` | Document artifact folders from their innermost children outward. |
| `directory_inventory.py` | Maintain a managed, bottom-up directory inventory in README documents. |
| `envelope.py` | Build the normalized report envelope from facts the runner knows. |
| `examples/` | Runnable demonstration for `exactus/tools/common/`. |
| `execution.py` | Shared standalone exactus entry-point reporting. |
| `json_types.py` | JSON value types shared by the exactus tools. |
| `models.py` | Shared exactus orchestration models. |
| `pipeline_supervisor.py` | Provide transactional ownership and reset coordination for pipelines. |
| `process_control.py` | Cross-invocation exactus ownership and process termination primitives. |
| `process_layer/` | Subdirectory. |
| `progress.py` | Uniform ``exactus-run/v1`` live-run progress document schema. |
| `registry.py` | Cross-process exactus run registry backed by an embedded database. |
| `report_comparison.py` | Compare normalized exactus findings with the preceding report bundle. |
| `report_time.py` | Format recorded report times without changing their machine values. |
| `runtime.py` | Shared exactus runtime state, progress, and summary protocol. |
| `snippets.py` | Capture numbered source excerpts around report findings. |
| `sprint.py` | Shared flushed-writer printing helpers for scripts and examples. |
| `stderr_capture.py` | Standard-error capture: ``stderr.log`` transcripts with line counts. |
| `templates/` | Subdirectory. |
| `terminal.py` | Responsive ANSI terminal presentation for exactus execution. |
| `terminal_progress.py` | Animated terminal progress bar with responsive determinate modes. |
| `toml.py` | Dependency-free TOML serializer compatible with tomllib. |
| `tool_worker.py` | Run canonical exactus tools in detached pmanager workers. |

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `root` | Project root (default: current directory). | nargs='?', type=Path, default=Path.cwd() |
| `-o, --output-dir` | f'Output directory (default: EXACTUS_RESULTS/{default_output}).' | type=Path, default=Path('EXACTUS_RESULTS') / default_output |
| `--include` | Include relative paths matching GLOB; repeatable. | action='append', default=[], metavar='GLOB' |
| `--exclude` | Exclude relative paths matching GLOB; repeatable. | action='append', default=[], metavar='GLOB' |
| `--context-lines` | Source lines shown around each reported line in report excerpts and snippets (default: %(default)s). | type=context_lines, default=SnippetLimits.default_context, metavar='N' |
| `--dry, --dry-run` | Analyze and report without modifying project files; honored by tools that fix or write sources. | action='store_true', dest='dry' |
| `--collect-files` | Bundle every file the report lists findings for into a FILES folder beside the report (README.md, TREE.txt and files.zip keeping the project folder structure). | action='store_true', dest='collect_files' |
| `--files` | number of generated Python files | type=int, default=Constants.default_files |
| `--prepare-only` | create the project and print commands without launching them | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Leaf primitives shared by every exactus tool.


### `activity.py`

Fixed ``@activity.json`` schema: heartbeat, progress and activity.

- `class ActivityTables` — Constants of the ``@activity.json`` contract.
  - `schema` = `'exactus/activity/v1'`
  - `file_name` = `'@activity.json'`
  - `event_limit` = `50`
  - `levels` = `('debug', 'info', 'warning', 'error')`
  - `phases` = `('starting', 'running', 'finished', 'interrupted', 'crashed')`
  - `interval_seconds` = `1.0`
  - `now() -> str` — Return the current UTC time as an ISO-8601 string.
- `class ActivityEvent` — One timestamped entry of the activity list.
  - Fields: `at: str`, `level: str`, `message: str`
  - `from_payload(cls: type[Self], *, payload: JsonValue) -> Self | None` — Decode one serialized event.
  - `payload(self: Self) -> dict[str, JsonValue]` — Serialize the event.
- `class ActivityHeartbeat` — Liveness block of the document.
  - `pid` = `None`
  - `alive` = `False`
  - `last_beat` = `None`
  - `phase` = `'starting'`
  - `interval_seconds` = `ActivityTables.interval_seconds`
  - `from_payload(cls: type[Self], *, payload: JsonValue) -> Self` — Decode a heartbeat block, defaulting missing fields.
  - `payload(self: Self) -> dict[str, JsonValue]` — Serialize the heartbeat block.
- `class ActivityProgress` — Progress block of the document.
  - `completed` = `0`
  - `total` = `0`
  - `fraction` = `0.0`
  - `step` = `''`
  - `current` = `''`
  - `workers` = `None`
  - `hierarchy` = `None`
  - `from_payload(cls: type[Self], *, payload: JsonValue) -> Self` — Decode a progress block, defaulting missing fields.
  - `payload(self: Self) -> dict[str, JsonValue]` — Serialize the progress block.
- `class ActivityDocument` — One complete ``exactus/activity/v1`` document.
  - `run_id` = `None`
  - `pipeline_run_id` = `None`
  - `started_at` = `None`
  - `updated_at` = `None`
  - `finished_at` = `None`
  - `elapsed_seconds` = `0.0`
  - `heartbeat` = `field(default_factory=ActivityHeartbeat)`
  - `progress` = `field(default_factory=ActivityProgress)`
  - `events` = `()`
  - `events_dropped` = `0`
  - `event_limit` = `ActivityTables.event_limit`
  - `items` = `()`
  - `extra` = `field(default_factory=dict)`
  - Fields: `kind: str`, `name: str`, `status: str`
  - `from_payload(cls: type[Self], *, payload: JsonValue) -> Self | None` — Decode a document written by ``payload``.
  - `payload(self: Self) -> dict[str, JsonValue]` — Serialize the document with its fixed key set.
- `class ActivityLog` — Thread-safe bounded list of recent activity events.
  - `__init__(self: Self, *, limit: int=ActivityTables.event_limit) -> None` — Start an empty log.
  - `record(self: Self, *, message: str, level: str='info', at: str | None=None) -> None` — Append one event, evicting the oldest when full.
  - `extend(self: Self, *, events: tuple[ActivityEvent, ...], dropped: int=0) -> None` — Adopt events recorded elsewhere, such as a previous document.
  - `events(self: Self) -> tuple[ActivityEvent, ...]` — Return the kept events, oldest first.
  - `dropped(self: Self) -> int` — Return how many recorded events were evicted.
- `class ActivityFile` — Atomic reader and writer of ``@activity.json`` documents.
  - `write(cls: type[Self], *, path: Path, document: ActivityDocument) -> None` — Atomically write one activity document.
  - `write_json(*, path: Path, payload: dict[str, JsonValue]) -> None` — Replace one JSON file atomically.
  - `read(*, path: Path) -> ActivityDocument | None` — Read one activity document.

### `api.py`

Process-isolated Python API for canonical exactus tools.

- `class ExactusApi` — Represent exactus api.
  - `poll_seconds` = `0.1`
  - `run_tool(cls, *, request: ToolRequest, spec: ToolSpec) -> ToolRunResult` — Return run tool.
  - `reconcile(*, result: ToolRunResult) -> ToolRunResult` — Return reconcile.

### `catalog.py`

Canonical exactus tool and pipeline catalog.

- `class ToolSpec` — Describe one canonical executable exactus tool.
  - `aliases` = `()`
  - `dependencies` = `()`
  - `streaming_dependencies` = `False`
  - `whole_source_activity` = `False`
  - `file_census` = `True`
  - Fields: `identifier: str`, `module: str`, `script: str`, `output: str`
- `class PipelineSpec` — Describe one non-executable orchestration pipeline.
  - `aliases` = `()`
  - `tool_arguments` = `field(default_factory=lambda: MappingProxyType(mapping={}))`
  - `clear` = `False`
  - Fields: `identifier: str`, `stages: tuple[tuple[str, ...], ...]`
- `class Catalog` — Resolve canonical tools and pipelines without duplicate execution.
  - `__init__(self, *, tools: tuple[ToolSpec, ...], pipelines: tuple[PipelineSpec, ...]) -> None` — Create and validate a catalog.
  - `normalize(*, identifier: str) -> str` — Normalize a public catalog identifier.
  - `canonical(self, *, identifier: str) -> str` — Resolve an id or alias to its canonical identifier.
  - `tool(self, *, identifier: str) -> ToolSpec | None` — Return a canonical tool, or ``None`` for a pipeline.
  - `pipeline(self, *, identifier: str) -> PipelineSpec | None` — Return a canonical pipeline, or ``None`` for a tool.
  - `tools(self) -> tuple[ToolSpec, ...]` — Return tools.
  - `pipelines(self) -> tuple[PipelineSpec, ...]` — Return pipelines.
  - `waves(self, *, identifier: str) -> tuple[tuple[ToolSpec, ...], ...]` — Return waves.
  - `resolve(self, *, selections: tuple[str, ...]) -> tuple[ToolSpec, ...]` — Flatten tool/pipeline selections and de-duplicate canonical tools.
- `class Constants` — Group module-level constants.
  - `tools` = `(_tool(identifier='lints'), _tool(identifier='coverage_tests', dependenci...`
  - `url_gated` = `frozenset({'frontend', 'record', 'visual_cause'})`
  - `pipelines` = `(PipelineSpec(identifier='self', stages=(('coverage_tests', 'docs', 'kwar...`
  - `exactus_catalog` = `Catalog(tools=tools, pipelines=pipelines)`
- `validate_scripts(*, root: Path) -> tuple[str, ...]` — Validate scripts.

### `cli.py`

Shared command-line and glob helpers for project exactuss.

- `class Constants` — Group module-level constants.
  - `heartbeat_timestamp_format` = `'%d/%m/%Y %H:%M:%S'`
- `map_lanes(*, lanes: Sequence[T], work: Callable[[T], R]) -> list[R]` — Run ``work`` once per lane on pooled threads, preserving order.
- `consume(value: T) -> T` — Explicitly consume a return value used only for side effects.
- `heartbeat_timestamp() -> str` — Return the local wall-clock time for heartbeat payloads.
- `class ExactusCommonTables` — Shared lookup tables and compiled values.
  - `DEFAULT_EXCLUDES` = `('.*/**', '**/.*/**', 'EXACTUS_RESULTS/**', '**/EXACTUS_RESULTS/**', 'nod...`
  - `DEFAULT_EXCLUDED_DIRS` = `frozenset({'.agents', '.build-cache', '.cache', '.claude', '.cursor', '.d...`
  - `LINTER_TOOLCHAIN` = `'linters-linux-amd64'`
  - `LINTER_TOOLCHAIN_ENV` = `'EXACTUS_LINTER_TOOLCHAIN'`
  - `LINTER_TOOLCHAIN_ARCHES` = `frozenset({'x86_64', 'amd64'})`
  - `BUNDLE_IMPORTS` = `('PIL', 'coverage', 'playwright')`
- `context_lines(text: str) -> int` — Parse a ``--context-lines`` value.
- `add_common_arguments(*, parser: ArgumentParser, default_output: str) -> None` — Add the common exactus CLI surface.
- `parse_common_arguments(*, default_output: str, arguments: tuple[str, ...] | None=None) -> Namespace` — Parse the common standalone exactus CLI surface.
- `resolve_report_output(*, requested: Path | None, default: str) -> Path` — Resolve an analyzer report directory for optional-output CLIs.
- `resolve_output(*, root: Path, output: Path) -> Path` — Resolve an output directory, honoring cwd-relative paths.
- `is_reports_tree(directory: Path) -> bool` — Return whether ``directory`` holds exactus report output.
- `match_path(*, path: Path, root: Path, includes: tuple[str, ...], excludes: tuple[str, ...], defaults: bool=True) -> bool` — Return whether a path passes normalized glob filters.
- `linter_platform_supported() -> bool` — Return whether the bundled linter toolchain can execute locally.
- `resolve_linter_toolchain(*, root: Path, option: Path | None=None) -> Path | None` — Resolve the canonical bundled Ruff + BasedPyright executable.
- `linter_command(*, tool: str, root: Path, toolchain: Path | None=None, search: str | None=None) -> tuple[str, ...]` — Return the command prefix that invokes one linter.
- `resolve_exactus_tool_bundle(*, root: Path) -> Path | None` — Resolve the offline exactus tool bundle for this host.
- `exactus_bundle_cache(*, root: Path) -> Path | None` — Materialize catalog components needed for Python/browser activation.
- `exactus_bundle_python_paths(*, root: Path) -> tuple[Path, ...] | None` — Materialize every host bundle component and list its Python dirs.
- `activate_exactus_tool_bundle(*, root: Path) -> bool` — Expose selected offline Python modules and version-matched Chromium.
- `exactus_tool_prefix(*, tool: str, root: Path) -> tuple[str, ...] | None` — Resolve an installed tool or the bundle, or ``None``.
- `exactus_tool_command(*, tool: str, root: Path) -> tuple[str, ...]` — Resolve an installed exactus tool or the offline Linux AMD64 bundle.
- `resolve_source_scope(*, path: Path) -> tuple[Path, tuple[Path, ...] | None]` — Resolve a user-supplied scan root into root plus explicit files.
- `expand_paths(*, root: Path, patterns: tuple[str, ...]) -> tuple[Path, ...]` — Expand path/glob arguments relative to root deterministically.

### `collect_files.py`

Bundle report finding files into a ``FILES`` evidence folder.

- `class Constants` — Group module-level constants.
  - `flag` = `'--collect-files'`
  - `folded_flag` = `'--collect_files'`
  - `variable` = `'EXACTUS_COLLECT_FILES'`
  - `directory` = `'FILES'`
  - `archive` = `'files.zip'`
  - `tree` = `'TREE.txt'`
  - `readme` = `'README.md'`
  - `finding_keys` = `('file', 'path', 'target')`
  - `logger` = `getLogger(name=__name__)`
- `requested(*, tokens: Sequence[str]) -> bool` — Report whether finding-file collection is enabled for this run.
- `mark(*, tokens: tuple[str, ...]) -> tuple[str, ...]` — Export collection intent when the flag reached the tool.
- `collect_report_files(*, output: Path) -> bool` — Bundle the files a report lists findings for into ``FILES``.

### `config.py`

Discover ``[tool.exactus]`` settings and render them as tool arguments.

- `class Constants` — Group module-level constants.
  - `environment_variable` = `'EXACTUS_CONFIG'`
  - `orchestrated_variable` = `'EXACTUS_ORCHESTRATED'`
  - `orchestrator_keys` = `frozenset(('clear', 'pipeline', 'exclude-tools', 'include', 'exclude', 'r...`
  - `disabled` = `'off'`
  - `file_name` = `'pyproject.toml'`
  - `reserved` = `frozenset(('root', 'reports-dir'))`
  - `path_keys` = `('actions', 'workspace')`
  - `select_flags` = `frozenset(('-t', '--tools', '--tool'))`
  - `info_flags` = `frozenset(('-h', '--help', '--list-tools', '--list-pipelines', '--show-co...`
  - `repeat_actions` = `frozenset(('_AppendAction',))`
  - `multi_actions` = `frozenset(('_ExtendAction',))`
  - `extension_sections` = `frozenset(('mcp',))`
- `class ConfigError` — Report an invalid exactus configuration, naming file and key.
- `class ConfigFile` — One loaded ``pyproject.toml`` carrying a ``[tool.exactus]`` table.
  - Fields: `path: Path`, `table: dict[str, JsonValue]`
- `reports_directory(*, files: tuple[ConfigFile, ...]) -> Path` — Resolve the configured project-relative exactus reports directory.
- `reports_anchor(*, files: tuple[ConfigFile, ...], start: Path) -> Path` — Resolve the directory a relative ``reports-dir`` anchors at.
- `discover(*, start: Path, explicit: Path | None=None, disabled: bool=False, boundary: Path | None=None) -> tuple[ConfigFile, ...]` — Collect exactus configuration files, nearest first.
- `discovery_from_environment(*, start: Path) -> tuple[ConfigFile, ...]` — Discover files honoring the ``EXACTUS_CONFIG`` variable.
- `stacked(*, files: tuple[ConfigFile, ...], path: tuple[str, ...]) -> dict[str, JsonValue]` — Merge the non-table values of one table across all files.
- `render(*, values: dict[str, JsonValue], parser: ArgumentParser, source: str, strict: bool) -> list[str]` — Render config values into argv tokens for one parser.
- `section_tool(*, section: str) -> str` — Return the tool a ``[tool.exactus.<section>]`` table configures.
- `layered_argv(*, files: tuple[ConfigFile, ...], tool: str, parser: ArgumentParser, pipeline: str | None=None, standalone: bool=False) -> list[tuple[str, tuple[str, ...]]]` — Render the configured arguments of one tool per layer.
- `argv_for(*, files: tuple[ConfigFile, ...], tool: str, parser: ArgumentParser, pipeline: str | None=None, standalone: bool=False) -> tuple[str, ...]` — Render the configured arguments of one tool, lowest priority first.
- `class EffectiveRequest` — Describe one tool whose effective options are reported.
  - `preset` = `()`
  - `cli` = `()`
  - `pipeline` = `None`
  - Fields: `tool: str`, `module: str`
- `effective(*, files: tuple[ConfigFile, ...], request: EffectiveRequest) -> list[tuple[str, str, str]]` — Report each option's final value and the layer that set it.
- `validate(*, files: tuple[ConfigFile, ...], parsers: dict[str, ArgumentParser], pipelines: Collection[str]) -> None` — Reject unknown tables and keys before any tool starts.
- `orchestrator_arguments(*, files: tuple[ConfigFile, ...], parser: ArgumentParser, arguments: Sequence[str], pipeline: str | None, tool_flags: Collection[str]=()) -> tuple[str, ...]` — Render ``check``'s own settings for pipeline-style invocations.
- `tool_parser(*, module: str) -> ArgumentParser` — Build a tool's parser from its module name.
- `resolve_arguments(*, tool: str, parser: ArgumentParser, arguments: Sequence[str] | None) -> tuple[str, ...]` — Prefix a standalone tool's arguments with its configuration.

### `conflict_copies.py`

Reconcile numbered sync copies without discarding unique project data.

- `class Constants` — Group module-level constants.
  - `ignored` = `frozenset({'.history', 'node_modules', 'venv', '__pycache__', 'exactus/pa...`
- `class ClearResult` — Describe reconciled sync copies and recoverable conflicts.
  - `removed_directories` = `0`
  - `merged_entries` = `0`
  - `preserved_conflicts` = `0`
  - `errors` = `0`
- `clear_conflict_copies(*, root: Path) -> ClearResult` — Reconcile numbered directories with existing canonical counterparts.

### `digest.py`

Summarize tool reports into failure digests for aggregate reports.

- `class Constants` — Group module-level constants.
  - `top_rules` = `8`
  - `top_files` = `8`
  - `top_findings` = `12`
  - `top_tests` = `15`
  - `top_distinct` = `8`
  - `origin_pattern` = `'https?://[\\w.\\-]+(?::\\d+)?'`
  - `rule_keys` = `('rule', 'code', 'kind', 'category')`
  - `message_keys` = `('message', 'reason', 'detail', 'suggestion')`
  - `extra_lists` = `(('bare_imports', 'bare-import'), ('type_hints', 'missing-type-hint'), ('...`
  - `message_limit` = `160`
- `class FindingLine` — One finding reduced to what a reader needs.
  - Fields: `rule: str`, `location: str`, `message: str`
- `class ToolDigest` — A tool report summarized for an aggregate report.
  - Fields: `tool: str`, `status: str`, `resume: str`, `findings: int`, `rules: tuple[tuple[str, int], ...]`, `files: tuple[tuple[str, int], ...]`, `top: tuple[FindingLine, ...]`, `distinct: tuple[tuple[str, str, int, str], ...]`, `notes: tuple[str, ...]`, `failed_tests: tuple[tuple[str, str], ...]`
- `digest_report(*, tool: str, fields: Mapping[str, JsonValue], status: str, resume: str) -> ToolDigest` — Summarize one tool report.
- `render_failure(*, digest: ToolDigest) -> list[str]` — Render one failing tool as Markdown.
- `digest_data(*, digest: ToolDigest) -> dict[str, JsonValue]` — Convert a digest to JSON-ready data.

### `directory_docs.py`

Document artifact folders from their innermost children outward.

- `write_directory_docs(*, root: Path) -> None` — Refresh standard artifact inventories without changing authored prose.

### `directory_inventory.py`

Maintain a managed, bottom-up directory inventory in README documents.

- `class Constants` — Group module-level constants.
  - `start` = `'<!-- exactus:inventory:start -->'`
  - `end` = `'<!-- exactus:inventory:end -->'`
  - `max_text_bytes` = `1 << 20`
  - `inventory_blocks` = `compile_pattern(pattern='<!-- (?P<owner>exactus|audit):inventory:start --...`
- `description(*, path: Path) -> str` — Summarize a file's docstring or a child directory's README introduction.
- `entry_line(*, entry: Path) -> str` — Render one relative link and description in the standard list format.
- `heal_directory(*, directory: Path, entries: list[Path]) -> None` — Consolidate generated inventories while preserving authored prose.

### `envelope.py`

Build the normalized report envelope from facts the runner knows.

- `class Constants` — Envelope constants.
  - `distribution` = `'exactus'`
  - `variables` = `frozenset({'EXACTUS_COLLECT_FILES', 'EXACTUS_CONFIG', 'EXACTUS_HOST', 'EX...`
  - `sensitive_keys` = `'(?:passw(?:or)?d|passphrase|pass(?![a-z])|pwd|secret|token|api[_-]?key|a...`
  - `url` = `compile_pattern(pattern='(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)(?P<rest>\...`
  - `assignment` = `compile_pattern(pattern=f"""(?P<key>[\\w.-]*{sensitive_keys}[\\w.-]*)(?P<...`
  - `flag` = `compile_pattern(pattern=f'(?P<key>(?<![\\w-])--?[\\w.-]*{sensitive_keys}[...`
  - `flag_only` = `compile_pattern(pattern=f'--?[\\w.-]*{sensitive_keys}[\\w.-]*', flags=IGN...`
  - `scheme_secret` = `compile_pattern(pattern='\\b(?P<key>bearer|basic)(?P<sep>\\s+)(?P<value>\...`
  - `authority_end` = `'/?#'`
  - `redacted` = `'[redacted]'`
  - `node_timeout` = `5.0`
  - `minute` = `60.0`
  - `blocks` = `('tool', 'run', 'invocation', 'environment', 'gate', 'artifacts')`
- `class RunFacts` — Facts about one tool run known to the runner, not the tool.
  - Fields: `analyzer: str`, `title: str`, `status: str`, `exit_code: int | None`, `error: str | None`, `started_at: str | None`, `finished_at: str`, `duration_seconds: float`, `run_id: str | None`, `pipeline_run_id: str | None`, `command: str`, `cwd: str`, `arguments: tuple[str, ...]`, `output: Path`
- `class Redaction` — Hide credentials in text a report shows.
  - `text(cls, *, value: str) -> str` — Hide every credential found in one text.
  - `arguments(cls, *, values: Sequence[str]) -> list[str]` — Hide credentials in an argument vector.
  - `userinfo(found: Match[str]) -> str` — Hide the userinfo of one matched URL.
  - `keyed(found: Match[str]) -> str` — Hide the value of one matched ``key``/``value`` secret.
- `class EnvironmentProbe` — Collect allowlisted, redacted facts about the host.
  - `facts(cls, *, source: Mapping[str, str]) -> dict[str, JsonValue]` — Return the ``environment`` block.
  - `node_version() -> str | None` — Return the installed Node.js version.
  - `variables(*, source: Mapping[str, str]) -> list[JsonValue]` — Select and redact the reported environment variables.
- `class Envelope` — Assemble the runner-owned blocks of a normalized result.
  - `gate(cls, *, facts: RunFacts, payload: Mapping[str, JsonValue]) -> dict[str, JsonValue]` — Return the ``gate`` block.
  - `build(cls, *, facts: RunFacts, payload: Mapping[str, JsonValue]) -> dict[str, JsonValue]` — Return every runner-owned block.
  - `duration_human(*, seconds: float) -> str` — Format a duration for people.
  - `tool_version() -> str | None` — Return the installed toolkit version.
  - `blocking(*, payload: Mapping[str, JsonValue]) -> int | None` — Count blocking findings in a tool payload.
  - `artifacts(*, output: Path) -> list[JsonValue]` — Return the ``artifacts`` block.

### `examples/__init__.py`

Provide runnable process-coordination examples.


### `examples/__main__.py`

Run the process-coordination collision example.


### `examples/run.py`

Run overlapping Exactus processes against one disposable workspace.

- `class Constants` — Store fixed demo settings.
  - `default_files` = `80`
  - `poll_seconds` = `0.2`
  - `launch_grace_seconds` = `0.25`
  - `unexpected_markers` = `('Traceback (most recent call last)', 'exited before reporting', 'externa...`
- `class Invocation` — Describe one independently launched Exactus process.
  - Fields: `label: str`, `delay_seconds: float`, `command: tuple[str, ...]`
- `class RunningInvocation` — Track one live child process and its transcript.
  - Fields: `invocation: Invocation`, `process: Popen[bytes]`, `transcript: BinaryIO`
  - `close(self: Self) -> None` — Close the transcript after the process has stopped.
- `emit(*, message: str) -> None` — Write one immediately visible demo line.
- `parser() -> ArgumentParser` — Build the collision-demo command-line parser.
- `prepare_project(*, file_count: int) -> Path` — Create a disposable project containing deliberate analyzer findings.
- `invocations(*, root: Path) -> tuple[Invocation, ...]` — Build overlapping commands sharing one project-root context.
- `print_commands(*, plans: tuple[Invocation, ...]) -> None` — Print copyable commands for the four-terminal demonstration.
- `registry_row(record: RunRecord) -> str` — Render one normalized registry record for the demo timeline.
- `registry_snapshot(*, root: Path) -> tuple[str, ...]` — Return normalized live process rows from the workspace registry.
- `launch(*, root: Path, invocation: Invocation) -> RunningInvocation` — Launch one Exactus invocation with an isolated transcript.
- `transcript_failed(*, root: Path, invocation: Invocation) -> bool` — Return whether one transcript contains a coordination failure.
- `run_demo(*, root: Path, plans: tuple[Invocation, ...]) -> int` — Run every collision and monitor the shared registry until settled.
- `main() -> int` — Prepare and optionally execute the coordination collision demo.

### `execution.py`

Shared standalone exactus entry-point reporting.

- `class Constants` — Group module-level constants.
  - `logger` = `getLogger(name=__name__)`
- `class ExactusEntrypointTables` — Store common standalone exactus CLI constants.
  - `report_output` = `'--report-output'`
  - `heartbeat_seconds` = `1.0`
  - `checkpoint_timeout_seconds` = `5.0`
  - `terminate_signals` = `tuple((Signals.__members__[name] for name in ('SIGINT', 'SIGTERM', 'SIGHU...`
  - `capture_limit` = `262144`
  - `artifact_embed_limit` = `65536`
  - `runner_files` = `frozenset({ActivityTables.file_name, StderrTables.log_name, 'stdout.log'})`
- `class ExactusRunIds` — Run identifiers injected by an orchestrating pipeline.
  - `run_id` = `None`
  - `pipeline_run_id` = `None`
- `class FallbackResult` — Everything a fallback report needs to render the full run.
  - Fields: `output: Path`, `analyzer: str`, `title: str`, `status: int`, `command: str`, `elapsed_seconds: float`, `stdout_tail: str`, `stderr_tail: str`, `error: str | None`
- `release_dependency_workers(*, analyzer: str, run_id: str, output: Path) -> None` — Release checkpointed downstream workers after prerequisite analysis.
- `execute_exactus(*, analyzer: str, title: str, main: Callable[[], int], output: Path | None=None, run_ids: ExactusRunIds | None=None) -> ToolRunResult` — Return execute exactus.
- `class CrashDetails` — Facts describing a worker process that died before reporting.
  - Fields: `pid: int | None`, `exit_code: int`, `elapsed_seconds: float`
- `crashed_exactus(*, request: ToolRequest, title: str, crash: CrashDetails) -> ToolRunResult` — Record a run whose worker process ended before reporting.
- `run_exactus(*, analyzer: str, title: str, main: Callable[[], int]) -> int` — Return run exactus.

### `json_types.py`

JSON value types shared by the exactus tools.

- `class JsonDict` — Dictionary with a formatted JSON representation.
  - `tojson(self) -> str` — Formatted JSON serialization of this dictionary.

### `models.py`

Shared exactus orchestration models.

- `result_stats(*, report_json: Path) -> str` — Summarize a tool report's file coverage and finding severities.
- `class ToolRequest` — Describe one tool execution requested by the orchestrator.
  - `pipeline_run_id` = `None`
  - `project_root` = `None`
  - Fields: `identifier: str`, `output: Path`, `arguments: tuple[str, ...]`, `run_id: str`
- `class ToolRunResult` — Describe the completed outcome of one tool execution.
  - `replaced_after_execution` = `False`
  - Fields: `tool: str`, `run_id: str`, `pipeline_run_id: str | None`, `status: str`, `passed: bool`, `exit_code: int`, `duration_seconds: float`, `resume: str`, `report: Path`, `report_json: Path`, `report_web: Path`
  - `from_report(cls: type[Self], *, payload: JsonValue, output: Path, fallback: ToolRunResult) -> ToolRunResult` — Reconstruct a result from a superseding run's report payload.
  - `replaced(self: Self) -> ToolRunResult` — Mark this result as superseded by a different run's report.
- `class ToolActivity` — Describe live progress of one tool inside a pipeline run.
  - `report_updated` = `False`
  - `issues` = `0`
  - `hierarchy` = `None`
  - Fields: `name: str`, `run_id: str`, `group: int`, `position: int`, `status: str`, `progress: float`, `step: str`, `started_at: str | None`, `finished_at: str | None`, `elapsed_seconds: float`
  - `payload(self: Self) -> dict[str, JsonValue]` — Serialize the record as one ``exactus-run/v1`` items entry.
- `class PipelineActivity` — Describe live progress of one pipeline run.
  - `events` = `()`
  - `events_dropped` = `0`
  - `previous_duration_seconds` = `None`
  - Fields: `name: str`, `run_id: str`, `status: str`, `progress: float`, `completed: int`, `total: int`, `step: str`, `detail: str`, `current_group: int | None`, `group_count: int`, `started_at: str`, `finished_at: str | None`, `elapsed_seconds: float`, `updated_at: str`, `pid: int`, `items: tuple[ToolActivity, ...]`
  - `document(self: Self) -> ActivityDocument` — Build the fixed ``@activity.json`` document of the pipeline.
  - `payload(self: Self) -> dict[str, JsonValue]` — Serialize the activity record for ``@activity.json``.

### `pipeline_supervisor.py`

Provide transactional ownership and reset coordination for pipelines.

- `class Constants` — Store coordination protocol constants.
  - `database` = `'pipelines.db'`
  - `directory` = `'pipeline_requests'`
  - `running` = `'RUNNING'`
  - `sealed` = `'SEALED'`
  - `pending` = `'PENDING'`
  - `applied` = `'APPLIED'`
  - `failed` = `'FAILED'`
  - `complete` = `'COMPLETE'`
  - `detached` = `'DETACHED'`
  - `retention_days` = `7`
- `class PipelineOwner` — Describe one named pipeline owner.
  - Fields: `pipeline: str`, `run_id: str`, `pid: int`, `fingerprint: str`, `state: str`, `generation: int`, `started_at: str`, `updated_at: str`
- `class PipelineRequest` — Describe one invocation observing a pipeline owner.
  - `error` = `None`
  - Fields: `request_id: str`, `pipeline: str`, `pipeline_run_id: str`, `fingerprint: str`, `pid: int`, `tty: str | None`, `state: str`, `generation: int | None`, `requested_at: str`, `updated_at: str`, `detail: str`
  - `payload(self: Self) -> dict[str, JsonValue]` — Return an inspectable JSON request document.
- `class PipelineClaim` — Describe one transactional pipeline admission decision.
  - Fields: `mode: ClaimMode`, `owner: PipelineOwner`, `request: PipelineRequest | None`, `detail: str`
- `class PipelineCoordinator` — Serialize pipeline claims and finalization through SQLite.
  - `__init__(self: Self, *, runtime: Path) -> None` — Bind the supervisor to a shared runtime directory.
  - `claim(self: Self, *, pipeline: str, run_id: str, pid: int, fingerprint: str, tty: str | None) -> PipelineClaim` — Atomically elect an owner, admit an observer, or require waiting.
  - `owner(self: Self, *, pipeline: str) -> PipelineOwner | None` — Return the stored owner of a named pipeline.
  - `requests(self: Self, *, pipeline_run_id: str, state: str) -> tuple[PipelineRequest, ...]` — Return one owner's requests in deterministic order.
  - `get(self: Self, *, request_id: str) -> PipelineRequest | None` — Return one observer request.
  - `acknowledge(self: Self, *, requests: tuple[PipelineRequest, ...], generation: int, detail: str) -> None` — Commit a coalesced request batch to a work generation.
  - `fail_requests(self: Self, *, requests: tuple[PipelineRequest, ...], error: str) -> None` — Publish a reset delivery failure.
  - `settle_observer(self: Self, *, request_id: str, state: str, detail: str) -> None` — Record how an observer stopped waiting.
  - `seal(self: Self, *, pipeline: str, run_id: str) -> bool` — Seal an idle owner when no observer request is pending.
  - `finish(self: Self, *, pipeline: str, run_id: str, state: str) -> None` — Publish a terminal owner state and prune old evidence.
  - `prune(self: Self) -> None` — Remove terminal observer evidence after the retention period.

### `process_control.py`

Cross-invocation exactus ownership and process termination primitives.

- `class Constants` — Group module-level constants.
  - `term_wait_seconds` = `3.0`
  - `poll_seconds` = `0.05`
  - `notice_lifetime_seconds` = `30.0`
- `new_run_id() -> str` — Return new run id.
- `process_exists(*, pid: int) -> bool` — Return process exists.
- `descendants(*, pid: int) -> tuple[int, ...]` — Return descendants.
- `exit_if_replaced(*, output_fd: int=2) -> None` — Exit normally with a notice when another exactus replaced this run.
- `terminate_tree(*, pid: int, include_root: bool=True, replaced: bool=False) -> None` — Handle terminate tree.
- `pause_tree(*, pid: int, exclude: Iterable[int]=()) -> None` — Suspend a process tree until ``resume_tree`` releases it.
- `resume_tree(*, pid: int) -> None` — Release a process tree suspended by ``pause_tree``.
- `read_json(*, path: Path) -> dict[str, JsonValue] | None` — Read json.
- `write_json(*, path: Path, payload: dict[str, JsonValue]) -> None` — Write json.

### `process_layer/__init__.py`

Authenticated Exactus process identification and termination.


### `process_layer/access.py`

Shared-secret provisioning and responder wiring for exactus runs.

- `class Constants` — Group module-level constants.
  - `directory` = `'.runtime'`
  - `filename` = `'authkey'`
  - `environment` = `'EXACTUS_AUTHKEY'`
  - `reports` = `'EXACTUS_REPORTS_ROOT'`
  - `default_reports` = `'EXACTUS_RESULTS'`
  - `secret_bytes` = `32`
  - `close_timeout` = `2.0`
- `runtime_dir(*, output: Path | None=None) -> Path` — Resolve the shared ``.runtime`` directory for this process.
- `authkey(*, runtime: Path) -> bytes` — Return the shared process-layer secret, creating it when absent.
- `start_responder(*, run_id: str, runtime: Path) -> IdentityResponder | None` — Start a best-effort authenticated responder for the run.
- `stop_responder(*, responder: IdentityResponder | None) -> None` — Stop a responder started by ``start_responder``.

### `process_layer/process_control.py`

Registry-free process identification for Exactus.

- `class ProcessConstants` — Immutable process-control configuration.
  - `application` = `'exactus'`
  - `protocol` = `1`
  - `host` = `'127.0.0.1'`
  - `timeout` = `0.3`
  - `workers` = `32`
  - `max_workers` = `128`
  - `max_message` = `65536`
  - `min_authkey` = `32`
  - `backlog` = `16`
  - `accept_timeout` = `0.2`
  - `shutdown_timeout` = `2.0`
  - `nonce_bytes` = `32`
  - `header_bytes` = `4`
  - `buffer_bytes` = `4096`
  - `instance_bytes` = `16`
- `class RunIdentity` — Immutable identity of an Exactus root process.
  - `application` = `'exactus'`
  - `protocol_version` = `1`
  - Fields: `root_pid: int`, `run_id: str`, `runs_db: str`, `created_at: float`, `instance_id: str`
- `class IdentityResponder` — Expose Exactus process metadata without a centralized registry.
  - `constants` = `ProcessConstants()`
  - `__init__(self, *, run_id: str, runs_db: Path, authkey: bytes, timeout: float=0.3) -> None` — Initialize an authenticated identity responder.
  - `running(self) -> bool` — Return whether the responder is accepting requests.
  - `port(self) -> int | None` — Return the active private loopback port.
  - `start(self) -> None` — Start the background responder.
  - `close(self, *, timeout: float=2.0) -> None` — Stop the responder and release its listener.
- `identify(*, pid: int, authkey: bytes, timeout: float=0.3, port: int | None=None) -> RunIdentity | None` — Interrogate a candidate Exactus process.
- `discover(*, authkey: bytes, timeout: float=0.3, workers: int=32, full_scan: bool=True) -> list[RunIdentity]` — Discover running Exactus processes without a registry.

### `process_layer/process_termination.py`

Cross-platform termination of verified Exactus process trees.

- `class TerminationResult` — Represent the outcome of terminating an Exactus run.
  - Fields: `root_pid: int`, `run_id: str`, `runs_db: str`, `discovered: tuple[int, ...]`, `terminated: tuple[int, ...]`, `killed: tuple[int, ...]`, `already_exited: tuple[int, ...]`, `failed: tuple[int, ...]`, `skipped: tuple[int, ...]`, `duration: float`
  - `success(self) -> bool` — Return whether all verified processes were terminated.
  - `count(self) -> int` — Return the number of successfully terminated processes.
- `class ProcessTerminator` — Terminate Exactus process trees using verified runtime identities.
  - `__init__(self, *, grace_period: float=2.0, kill_timeout: float=2.0) -> None` — Initialize process termination settings.
  - `terminate(self, *, identity: RunIdentity, force: bool=True) -> TerminationResult` — Terminate one verified Exactus run and its process tree.

### `progress.py`

Uniform ``exactus-run/v1`` live-run progress document schema.

- `class Constants` — Group module-level constants.
  - `progress_schema` = `'exactus-run/v1'`
- `utc_now() -> str` — Return the current UTC wall-clock time as an ISO-8601 string.
- `class RunItem` — Describe one sub-entity record inside a uniform run document.
  - `progress` = `0.0`
  - `step` = `''`
  - `detail` = `''`
  - `run_id` = `None`
  - `started_at` = `None`
  - `finished_at` = `None`
  - `elapsed_seconds` = `0.0`
  - `extra` = `field(default_factory=dict)`
  - Fields: `name: str`, `status: str`
  - `payload(self: Self) -> dict[str, JsonValue]` — Serialize the record as one ``exactus-run/v1`` items entry.
- `class RunDocument` — Describe one uniform ``exactus-run/v1`` live-run document.
  - `progress` = `0.0`
  - `completed` = `0`
  - `total` = `0`
  - `step` = `''`
  - `detail` = `''`
  - `run_id` = `None`
  - `pipeline_run_id` = `None`
  - `pid` = `None`
  - `started_at` = `None`
  - `updated_at` = `None`
  - `finished_at` = `None`
  - `elapsed_seconds` = `0.0`
  - `items` = `()`
  - `extra` = `field(default_factory=dict)`
  - Fields: `kind: str`, `name: str`, `status: str`
  - `payload(self: Self) -> dict[str, JsonValue]` — Serialize the document for a progress artifact file.

### `registry.py`

Cross-process exactus run registry backed by an embedded database.

- `class RegistryTables` — Static schema and lookup values for the run registry.
  - `database_name` = `'runs.db'`
  - `env_path` = `'EXACTUS_REGISTRY'`
  - `project_root_env` = `'EXACTUS_PROJECT_ROOT'`
  - `exactus_root_name` = `'EXACTUS_RESULTS'`
  - `busy_timeout_seconds` = `10.0`
  - `retention` = `timedelta(days=7)`
  - `max_finished` = `500`
  - `max_size_bytes` = `67108864`
  - `size_trim_batch` = `50`
  - `max_text` = `512`
  - `journal_limit_bytes` = `1048576`
  - `max_runs_env` = `'EXACTUS_RUNTIME_MAX_RUNS'`
  - `max_size_env` = `'EXACTUS_RUNTIME_MAX_SIZE'`
  - `live_status` = `'RUNNING'`
  - `columns` = `('run_id', 'kind', 'identifier', 'pipeline_run_id', 'pid', 'output', 'tar...`
- `workspace_context(*, root: Path) -> str` — Return the deterministic pmanager context for one project root.
- `run_context(*, root: Path, owner: str) -> str` — Return one invocation child context inside a workspace context.
- `class RunClaim` — Ownership facts registered by one starting run.
  - Fields: `kind: str`, `identifier: str`, `run_id: str`, `pipeline_run_id: str | None`, `pid: int`, `output: Path`, `targets: tuple[str, ...]`
- `class RunBeat` — Optional progress fields refreshed by one heartbeat.
  - `status` = `None`
  - `progress` = `None`
  - `step` = `None`
  - `detail` = `None`
  - `elapsed_seconds` = `None`
  - Fields: `run_id: str`
- `class RunRecord` — One registered exactus run row.
  - Fields: `run_id: str`, `kind: str`, `identifier: str`, `pipeline_run_id: str | None`, `pid: int`, `output: str`, `targets: tuple[str, ...]`, `status: str`, `progress: float`, `step: str`, `detail: str`, `created_at: str`, `updated_at: str`, `elapsed_seconds: float`
- `class RunRegistry` — Shared exactus-run registry persisted in an embedded database.
  - `__init__(self, *, path: Path) -> None` — Bind the registry to one database path.
  - `for_output(cls: type[Self], *, output: Path) -> Self` — Resolve the registry governing one analyzer output directory.
  - `acquire_resource(self, *, lease_id: str, run_id: str, tool: str, resource: str, mode: str) -> bool | None` — Try to acquire one cross-process reader/writer resource lease.
  - `release_resource(self, *, lease_id: str) -> None` — Release one reader/writer resource lease.
  - `publish_activity(self, *, run_id: str, tool: str, item: str, state: str, error: str='') -> None` — Publish one file/activity boundary for cross-process consumers.
  - `activity_state(self, *, run_id: str, item: str) -> str | None` — Return the latest state of one run's file/activity.
  - `claim(self, *, request: RunClaim) -> tuple[RunRecord, ...] | None` — Register one run and return every live run it conflicts with.
  - `sanitize(self) -> int` — Prune stale rows and shrink the database file.
  - `beat(self, *, pulse: RunBeat) -> None` — Refresh one run's progress fields and liveness timestamp.
  - `finish(self, *, run_id: str, status: str, elapsed_seconds: float) -> None` — Stamp one run's terminal lifecycle status.
  - `live(self) -> tuple[RunRecord, ...]` — Return every registered run whose process is still alive.

### `report_comparison.py`

Compare normalized exactus findings with the preceding report bundle.

- `capture(*, output: Path) -> None` — Capture report documents before an output tree is replaced.
- `clear() -> None` — Discard reports captured for the current execution.
- `previous_duration(*, path: Path) -> float | None` — Return the duration of the report that preceded ``path``.
- `markdown(*, comparison: JsonValue) -> str` — Render global and subsection deltas for any Markdown report.
- `apply(*, payload: JsonObject, path: Path) -> None` — Attach finding-level comparison data to a current report payload.

### `report_time.py`

Format recorded report times without changing their machine values.

- `readable_time(*, value: JsonValue) -> str | None` — Format an ISO timestamp with an explicit timezone.
- `report_times(*, payload: Mapping[str, JsonValue]) -> dict[str, JsonValue]` — Select the recorded run time and supply readable display fields.

### `runtime.py`

Shared exactus runtime state, progress, and summary protocol.

- `class Constants` — Group module-level constants.
  - `tool_env` = `'EXACTUS_TOOL'`
  - `run_id_env` = `'EXACTUS_RUN_ID'`
  - `source_resource` = `'workspace:source-tree'`
- `request_checkpoint_pause(*, owner: str='*') -> None` — Pause worker threads when they next complete an activity.
- `release_checkpoint_pause(*, owner: str='*') -> None` — Release one owner's activity-boundary checkpoint lease.
- `checkpoint_status() -> dict[str, JsonValue]` — Return the cooperative activity-boundary state.
- `wait_for_dependencies() -> None` — Wait until every live prerequisite process reaches a terminal state.
- `source_activity(*, mode: str, identity: str, enabled: bool=True) -> Generator[None]` — Protect a file or whole logical subtask with a source-tree lease.
- `run_source_activity(*, mode: str, identity: str, action: Callable[[], ResultT], enabled: bool=True) -> ResultT` — Run one operation under a source-tree reader/writer lease.
- `class Progress` — Represent progress.
  - `detail` = `''`
  - `span` = `(0.0, 1.0)`
  - `share` = `None`
  - `workers` = `None`
  - `error` = `''`
  - Fields: `state: str`, `completed: int`, `total: int`, `step: str`
  - `fraction(self) -> float` — Completion fraction clamped to the ``[0, 1]`` range.
- `class ProgressNode` — Represent one normalized hierarchical progress node.
  - `error` = `None`
  - `children` = `()`
  - Fields: `level: str`, `identifier: str`, `state: str`, `completed: int`, `total: int`, `fraction: float`, `step: str`, `current: str`
  - `payload(self) -> dict[str, JsonValue]` — Serialize this node.
- `emit_progress(*, state: str, completed: int, total: int, step: str, detail: str='') -> None` — Publish whole-tool progress for standalone and orchestrated runs.
- `publish_progress(*, progress: Progress) -> None` — Publish one progress snapshot to the tool's progress channel.
- `current_progress() -> dict[str, JsonValue]` — Return the latest in-process progress snapshot.
- `clear_progress() -> None` — Clear progress retained from an earlier run in this process.
- `release_activities(*, items: list[Path] | frozenset[Path], stable: bool=True) -> None` — Publish available file activities for dependent processes.
- `class LaneProgress` — Run-wide completed-unit counter shared by parallel lanes.
  - `__init__(self, *, total: int, step: str='parallel work', span: tuple[float, float]=(0.0, 1.0)) -> None` — Store the run-wide work-unit total.
  - `completed(self) -> int` — Number of units completed so far.
  - `advance(self) -> int` — Mark one work unit complete and return the new count.
  - `begin(self, *, item: str) -> None` — Publish one thread starting a work item.
  - `finish(self, *, item: str, error: str | None=None) -> int` — Publish one thread completing or failing a work item.

### `snippets.py`

Capture numbered source excerpts around report findings.

- `class SnippetLimits` — Bounds and lookup tables of the excerpt reader.
  - `default_context` = `3`
  - `max_context` = `50`
  - `max_scan_bytes` = `16 * 1024 * 1024`
  - `max_line_bytes` = `4096`
  - `max_line_chars` = `400`
  - `sniff_bytes` = `8192`
  - `ellipsis` = `' …'`
  - `languages` = `{'.py': 'python', '.pyi': 'python', '.js': 'javascript', '.jsx': 'javascr...`
  - `names` = `{'Dockerfile': 'dockerfile', 'Makefile': 'makefile'}`
  - `fallback` = `'text'`
- `class ExcerptLine` — One numbered source line of an excerpt.
  - Fields: `n: int`, `text: str`, `target: bool`
  - `payload(self: Self) -> dict[str, JsonValue]` — Return the JSON form of this line.
- `class Excerpt` — Numbered lines around one finding line.
  - Fields: `line: int`, `context: int`, `language: str`, `lines: tuple[ExcerptLine, ...]`, `clipped: bool`
  - `payload(self: Self) -> dict[str, JsonValue]` — Return the JSON form stored on a finding.
- `class SnippetSource` — Locate and read project files for excerpts.
  - `read(cls, *, path: Path, first: int, last: int) -> list[tuple[int, str, bool]] | None` — Read the numbered lines ``first`` to ``last`` of a text file.
  - `language(*, path: Path) -> str` — Return the fenced-code language of a file.
  - `locate(*, root: Path, path: str | Path) -> Path | None` — Resolve a project path, refusing anything outside the root.
- `excerpt(*, root: Path, path: str | Path, line: int, context: int) -> Excerpt | None` — Capture the numbered lines around one line of a project file.
- `finding_excerpt(*, finding: JsonValue, root: Path, context: int) -> JsonValue` — Return a finding with its ``excerpt`` added when one is available.
- `with_excerpts(*, payload: dict[str, JsonValue], root: Path, context: int) -> dict[str, JsonValue]` — Add excerpts to every finding of a normalized report payload.

### `sprint.py`

Shared flushed-writer printing helpers for scripts and examples.

- `class SprintStyle` — Per-call output and capture policy for `sprint`.
  - `level` = `'info'`
  - `color` = `None`
  - `save` = `True`
- `class Constants` — Group module-level constants.
  - `default_style` = `SprintStyle()`
  - `debug_marker` = `'DEBUG.txt'`
  - `debug_directory` = `'debug'`
  - `debug_filename` = `'out.txt'`
  - `debug_default_age` = `86400.0`
  - `debug_stamp` = `'%d/%m/%Y %H:%M:%S'`
  - `debug_units` = `{'d': 86400, 'h': 3600, 'm': 60, 's': 1}`
  - `debug_selector` = `recompile(pattern='^(?P<file>[^\\[\\]]*)(?:\\[(?P<functions>[^\\[\\]]*)\\...`
  - `debug_stamp_pattern` = `recompile(pattern='^(?:STDOUT|STDERR) - (\\d{2}/\\d{2}/\\d{4} \\d{2}:\\d{...`
  - `module_file` = `Path(__file__).resolve()`
  - `project_root` = `Path.cwd()`
  - `error_style` = `SprintStyle(level='error')`
- `class Writer(Protocol)` — Writable text stream accepted by `sprint`.
  - `write(self, s: str) -> int` — Write `s` and return the characters written.
  - `flush(self) -> None` — Flush buffered output to the stream.
- `sprint(*args: _Printable, sep: str=' ', end: str='\n', file: Writer | None=None, flush: bool=True, style: SprintStyle=Constants.default_style) -> None` — Print a message and optionally flush the writer.
- `sprint_err(*args: _Printable, sep: str=' ', end: str='\n', flush: bool=True, style: SprintStyle=Constants.error_style) -> None` — Print a message to stderr and optionally flush.

### `stderr_capture.py`

Standard-error capture: ``stderr.log`` transcripts with line counts.

- `class StderrTables` — Constants of the ``stderr.log`` contract.
  - `log_name` = `'stderr.log'`
  - `line_chars` = `2000`
  - `char_bytes` = `4`
  - `error` = `compile_pattern(pattern='\\b(error|exception|traceback|fatal|critical)\\b...`
  - `warning` = `compile_pattern(pattern='\\b(warn|warning|warnings|deprecated|deprecation...`
  - `level(cls: type[Self], *, text: str) -> str` — Classify one line of standard error.
- `class StderrRecorder` — Count stream bytes and classify each completed line.
  - `__init__(self: Self, *, line_chars: int=StderrTables.line_chars) -> None` — Start an empty recording.
  - `feed(self: Self, *, chunk: bytes) -> None` — Consume one chunk of the stream.
  - `finish(self: Self) -> None` — Classify a trailing line that has no newline.
- `current_stderr() -> TextIO` — Return the interpreter's current ``sys.stderr`` stream.
- `class StderrMirror` — Record ``sys.stderr`` into a directory while forwarding it.
  - `__init__(self: Self, *, directory: Path) -> None` — Choose where ``stderr.log`` lands.

### `templates/markdown/examples/__init__.py`

Provide runnable Markdown report-template fixtures.


### `templates/markdown/examples/__main__.py`

Validate the Markdown report-template fixture set.


### `templates/markdown/examples/run.py`

Validate bundled Markdown report input and expected-output fixtures.

- `main() -> int` — Parse every JSON fixture and verify each expected report exists.

### `terminal.py`

Responsive ANSI terminal presentation for exactus execution.

- `class Constants` — Group module-level constants.
  - `reset` = `'\x1b[0m'`
  - `bold` = `'\x1b[1m'`
  - `dim` = `'\x1b[2m'`
  - `green` = `'\x1b[32m'`
  - `red` = `'\x1b[31m'`
  - `cyan` = `'\x1b[36m'`
  - `yellow` = `'\x1b[33m'`
  - `clear` = `'\x1b[2K'`
  - `up` = `'\x1b[1A'`
  - `erase_screen` = `'\x1b[2J\x1b[3J\x1b[H'`
  - `erase_below` = `'\x1b[J'`
  - `hide_cursor` = `'\x1b[?25l'`
  - `show_cursor` = `'\x1b[?25h'`
  - `sync_begin` = `'\x1b[?2026h'`
  - `sync_end` = `'\x1b[?2026l'`
  - `ansi` = `re_compile(pattern='\\033\\[[0-9;?]*[A-Za-z]')`
  - `live_lock` = `RLock()`
  - `dsr_pattern` = `re_compile(pattern=b'\\x1b\\[(\\d+);(\\d+)R')`
  - `dsr_timeout` = `0.4`
  - `o_noctty` = `getattr(import_module(name='os'), 'O_NOCTTY', 0)`
  - `o_nonblock` = `getattr(import_module(name='os'), 'O_NONBLOCK', 0)`
  - `failed` = `frozenset({'FAIL', 'INTERRUPT', 'TIMEOUT'})`
- `class ResultRow` — Represent result row.
  - `report` = `''`
  - `stats` = `''`
  - Fields: `tool: str`, `status: str`, `duration_seconds: float`, `resume: str`
- `class ExactusTerminal` — Render the only user-facing exactus terminal protocol.
  - `clear_screen(cls) -> None` — Erase the interactive screen and scrollback before a run.
  - `emit(cls, *, text: str, stream: TextIO | None=None) -> None` — Print log text without corrupting a live progress block.
  - `progress(cls, *, title: str, global_fraction: float, stage: str, tools: tuple[tuple[str, str, float, str, float | None], ...], previous_lines: int) -> int` — Repaint the live pipeline block in place.
  - `clear_progress(cls, *, lines: int) -> None` — Remove the live block and restore the cursor.
  - `standalone_progress(cls, *, tool: str, fraction: float, step: str) -> None` — Repaint the single standalone progress row in place.
  - `finish_standalone_progress(cls, *, failed: bool=False) -> None` — Clear the standalone progress row before final results.
  - `mirror_tty(cls, *, path: str) -> bool` — Attach a replaced run's terminal as a live-progress mirror.
  - `detach_mirrors(cls, *, note: str='') -> None` — Detach every mirrored terminal, restoring its cursor.
  - `results(cls, *, title: str, rows: tuple[ResultRow, ...]) -> None` — Handle results.
  - `restore_cursor() -> None` — Make the cursor visible again (safe to call at any time).
  - `tty_name() -> str | None` — Return the device path of the terminal behind ``stdout``.
- `dsr_reply() -> bool` — Return whether ``stdout`` accepts ANSI cursor positioning.
- `dsr_cursor_moves(*, descriptor: int, output: int) -> bool` — Verify one reversible cursor move against the output terminal.

### `terminal_progress.py`

Animated terminal progress bar with responsive determinate modes.

- `class Constants` — Group module-level constants.
  - `ansi_red` = `'\x1b[31m'`
  - `ansi_reset` = `'\x1b[0m'`
- `class ProgressMode` — Available progress rendering modes.
  - `DETERMINATE` = `auto()`
  - `INDETERMINATE` = `auto()`
- `class Settings` — Configure progress animation and rendering.
  - `fill` = `'█'`
  - `empty` = `'░'`
  - `head` = `'▓'`
  - `pulse` = `'█'`
  - `fps` = `30.0`
  - `smoothing_seconds` = `0.35`
  - `min` = `0.0005`
  - `max` = `100.0`
  - `pulse_width` = `4`
  - `hide_cursor` = `True`
- `class TerminalProgress` — Render a smoothly animated, resize-aware progress bar on one line.
  - `__init__(self, *, width: int | str=36, label: str='', settings: Settings | None=None, stream: TextIO=stdout) -> None` — Initialize a terminal progress renderer.
  - `progress(self) -> float` — Current target progress in the inclusive range 0..1.
  - `mode(self) -> ProgressMode` — Current rendering mode.
  - `start(self, *, indeterminate: bool=False) -> Self` — Start background rendering.
  - `set_progress(self, value: float, *, message: str | None=None) -> Self` — Set a determinate target and animate smoothly toward it.
  - `set_percent(self, percent: float, *, message: str | None=None) -> Self` — Set determinate progress using a percentage.
  - `set_indeterminate(self, *, message: str | None=None) -> Self` — Switch to the continuously animated indeterminate state.
  - `flag_issue(self, *, at: float | None=None) -> Self` — Mark the frontier cell red where an issue was found.
  - `set_message(self, message: str) -> Self` — Update the trailing status message without changing progress.
  - `finish(self, *, message: str | None=None) -> None` — Animate to exactly 100 percent and close the progress renderer.
  - `close(self) -> None` — Stop rendering, restore the cursor, and preserve the final frame.

### `toml.py`

Dependency-free TOML serializer compatible with tomllib.

- `class TomlSerializer` — Serialize Python values into TOML accepted by tomllib.
  - `bare_key_pattern` = `'[A-Za-z0-9_-]+'`
  - `dumps(cls, *, value: TomlDocument) -> str` — Serialize a TOML document.

### `tool_worker.py`

Run canonical exactus tools in detached pmanager workers.

- `class Constants` — Group module-level constants.
  - `repo_root` = `Path(__file__).resolve().parents[3]`
  - `terminal` = `frozenset({State.COMPLETED, State.FAILED, State.KILLED, State.CANCELLED})`
- `class WorkerRequest` — Describe the JSON-compatible arguments passed to a tool worker.
  - Fields: `identifier: str`, `module: str`, `output: str`, `arguments: list[str]`, `run_id: str`, `pipeline_run_id: str | None`, `project_root: str | None`
- `ensure_worker_path() -> None` — Expose this checkout to detached pmanager runtime processes.
- `tool_context(*, root: Path, owner: str) -> str` — Return a run context nested under the project-root hash.
- `build_spec(*, tools: Iterable[ToolSpec], root: Path) -> Spec` — Build the detached worker specification for participating tools.
- `worker_arguments(*, request: ToolRequest, spec: ToolSpec) -> tuple[tuple[JsonValue, ...], dict[str, JsonValue]]` — Encode one exactus request as structured ProcessClass arguments.
- `live_status(*, descriptors: Iterable[Descriptor], name: str, context: str) -> ProcessStatus | None` — Return live worker status without treating IPC timeouts as death.
- `result_from_status(*, request: ToolRequest, spec: ToolSpec, process_status: ProcessStatus | None, started: float) -> ToolRunResult` — Resolve a worker outcome from its terminal state and report.
- `kill_context(*, context: str) -> int` — Gracefully stop and then reap every worker in a context.
- `pause_worker(*, descriptor: Descriptor, owner: str) -> bool` — Acquire an owner-scoped pause lease on one worker.
- `resume_worker(*, descriptor: Descriptor, owner: str) -> bool` — Release one owner's pause lease on a worker.
- `reset_worker(*, descriptor: Descriptor) -> bool` — Restart one worker generation without replacing its owner process.
- `external_descriptors(*, records: Mapping[str, RunRecord], descriptors: Iterable[Descriptor], root: Path) -> dict[str, Descriptor]` — Join live registry records to discovered pmanager workers.
- `class ExactusTool` — Execute every catalog tool with a uniform lifecycle surface.
  - `kill_timeout` = `5.0`
  - `__init__(self) -> None` — Initialize worker lifecycle state.
  - `on_pause(self) -> None` — Publish the paused lifecycle before the runner stops.
  - `on_resume(self) -> None` — Publish the resumed lifecycle after the runner continues.
  - `on_reset(self) -> None` — Clear generation-scoped progress before a restart.
  - `on_cancel(self) -> None` — Mark cooperative cancellation before the runner exits.
  - `on_kill(self) -> None` — Reap tool-spawned descendants before the bounded hard kill.
  - `current_status(self) -> dict[str, JsonValue]` — Return live exactus progress and lifecycle details.
  - `control(self, payload: JsonValue) -> None` — Handle cooperative control broadcasts.
  - `run(self, *, request: WorkerRequest) -> int` — Execute one catalog tool through the canonical exactus boundary.

## Examples

Runnable demonstration for `exactus/tools/common/`.

Run overlapping Exactus processes against one disposable workspace.

```bash
python -m exactus.tools.common.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`argument_parser`](../../packages/argument_parser/DOCS.md), [`markdown`](../../packages/markdown/DOCS.md), [`model`](../../packages/model/DOCS.md), [`pmanager`](../../packages/pmanager/DOCS.md), [`project_python`](../../packages/project_python/DOCS.md), [`steps`](../../packages/steps/DOCS.md), [`tree`](../../packages/tree/DOCS.md), [`reports`](../reports/DOCS.md)
- Used by: `__init__.py`, `__main__.py`, `bundle/linux/glibc/amd64/partition_launcher.py`, `bundle/linux/glibc/amd64/zstd_portable/__init__.py`, `bundle/linux/glibc/arm64/partition_launcher.py`, `bundle/linux/glibc/arm64/zstd_portable/__init__.py`, `bundle/linux/musl/amd64/partition_launcher.py`, `bundle/linux/musl/amd64/zstd_portable/__init__.py`, `bundle/linux/musl/arm64/partition_launcher.py`, `bundle/linux/musl/arm64/zstd_portable/__init__.py`, `bundle/macos/amd64/partition_launcher.py`, `bundle/macos/amd64/zstd_portable/__init__.py`, `bundle/macos/arm64/partition_launcher.py`, `bundle/macos/arm64/zstd_portable/__init__.py`, `bundle/windows/amd64/partition_launcher.py`, `bundle/windows/amd64/zstd_portable/__init__.py`, `bundle/windows/arm64/partition_launcher.py`, `bundle/windows/arm64/zstd_portable/__init__.py`, `packages/exactus_mcp/runner.py`, `packages/external/cli.py`, `packages/group_final/core.py`, `packages/meaningful/api.py`, `packages/package/api.py`, `packages/package/build.py`, `packages/package/bundle.py`, `packages/package/install.py`, `packages/package/partition_launcher.py`, `packages/package/readmes.py`, `packages/zip_components/core.py`, `packages/zstd_portable/__init__.py`, `tests/common/check/test_check_extra.py`, `tests/common/check/test_public_api.py`, `tests/common/json_serializers/test_json_serializers.py`, `tests/common/support.py`, `tests/packages/external/test_cli.py`, `tests/packages/markdown/test_engine.py`, `tests/packages/markdown/test_filters.py`, `tests/packages/markdown/test_mapping.py`, `tests/packages/markdown/test_paths.py`, `tests/packages/markdown/test_predicates.py`, `tests/packages/server/test_server_lifecycle.py`, `tests/packages/zstd_portable/test_directory_inventory.py`, `tests/tools/actions/test_actions.py`, `tests/tools/common/process_layer/test_access.py`, `tests/tools/common/process_layer/test_control.py`, `tests/tools/common/process_layer/test_termination.py`, `tests/tools/common/test_activity.py`, `tests/tools/common/test_analyzers.py`, `tests/tools/common/test_catalog.py`, `tests/tools/common/test_collect_files.py`, `tests/tools/common/test_common.py`, `tests/tools/common/test_config.py`, `tests/tools/common/test_conflict_copies.py`, `tests/tools/common/test_context_lines.py`, `tests/tools/common/test_digest.py`, `tests/tools/common/test_envelope.py`, `tests/tools/common/test_examples_run.py`, `tests/tools/common/test_execution.py`, `tests/tools/common/test_models_api.py`, `tests/tools/common/test_output_tree.py`, `tests/tools/common/test_pipeline_output.py`, `tests/tools/common/test_pipeline_supervisor.py`, `tests/tools/common/test_process_control.py`, `tests/tools/common/test_progress_ownership.py`, `tests/tools/common/test_registry.py`, `tests/tools/common/test_report_comparison.py`, `tests/tools/common/test_report_templates.py`, `tests/tools/common/test_report_time.py`, `tests/tools/common/test_snippets.py`, `tests/tools/common/test_sprint.py`, `tests/tools/common/test_stderr_capture.py`, `tests/tools/common/test_terminal.py`, `tests/tools/common/test_terminal_progress.py`, `tests/tools/common/test_toml.py`, `tests/tools/common/test_tool_worker.py`, `tests/tools/common/test_toolkit.py`, `tests/tools/completion/test_integration.py`, `tests/tools/coverage_tests/test_core_boundaries.py`, `tests/tools/coverage_tests/test_coverage_tool.py`, `tests/tools/coverage_tests/test_coverage_validator.py`, `tests/tools/coverage_tests/test_javascript_gate.py`, `tests/tools/coverage_tests/test_meaningful.py`, `tests/tools/coverage_tests/test_report_layout.py`, `tests/tools/coverage_tests/test_skipped_report.py`, `tests/tools/coverage_tests/test_steps_trace.py`, `tests/tools/docs/test_docs_metrics.py`, `tests/tools/docs/test_docs_report.py`, `tests/tools/frontend/test_frontend.py`, `tests/tools/frontend/test_frontend_progress.py`, `tests/tools/frontend/test_frontend_report.py`, `tests/tools/frontend/test_parallel_flows.py`, `tests/tools/kwargs_typehints/test_kwargs_report.py`, `tests/tools/kwargs_typehints/test_kwargs_typehints.py`, `tests/tools/lints/test_compliance.py`, `tests/tools/lints/test_css_tokens.py`, `tests/tools/lints/test_js_delimiters.py`, `tests/tools/lints/test_js_function_blocks.py`, `tests/tools/lints/test_lints.py`, `tests/tools/lints/test_lints_normalizers.py`, `tests/tools/lints/test_lints_report.py`, `tests/tools/lints/test_method_contracts.py`, `tests/tools/lints/test_shebang_metrics.py`, `tests/tools/readme/test_readme_report.py`, `tests/tools/record/selector_support.py`, `tests/tools/record/test_action_schema.py`, `tests/tools/record/test_discovery_project.py`, `tests/tools/record/test_flow_contracts.py`, `tests/tools/record/test_flow_runner.py`, `tests/tools/record/test_flow_runner_actions.py`, `tests/tools/record/test_flow_runner_selectors.py`, `tests/tools/record/test_flow_runner_variables.py`, `tests/tools/record/test_persistence_selectors.py`, `tests/tools/record/test_project_assets.py`, `tests/tools/record/test_record_core.py`, `tests/tools/record/test_record_report.py`, `tests/tools/record/test_run_gate.py`, `tests/tools/record/test_selector_resolver.py`, `tests/tools/record/test_selector_sandbox.py`, `tests/tools/record/test_selector_snapshot.py`, `tests/tools/record/test_store_selectors.py`, `tests/tools/record/test_studio_action_setup.py`, `tests/tools/record/test_studio_duplicate_step.py`, `tests/tools/record/test_studio_projects.py`, `tests/tools/record/test_studio_selectors.py`, `tests/tools/record/test_v3_execution.py`, `tests/tools/record/test_v3_fixture_builder.py`, `tests/tools/record/test_v3_fixtures.py`, `tests/tools/record/v3_fixture_builder.py`, `tests/tools/reports/test_report_bundle.py`, `tests/tools/reports/test_report_render.py`, `tests/tools/reports/test_report_snippets.py`, `tests/tools/reports/test_report_web.py`, `tests/tools/test_self_test.py`, `tests/tools/visual_cause/test_report.py`, `tests/tools/visual_cause/test_targets.py`, `tools/actions/runner.py`, `tools/coverage_tests/arguments.py`, `tools/coverage_tests/core.py`, `tools/coverage_tests/main.py`, `tools/coverage_tests/meaningful.py`, `tools/coverage_tests/report.py`, `tools/docs/arguments.py`, `tools/docs/core.py`, `tools/docs/main.py`, `tools/frontend/arguments.py`, `tools/frontend/core.py`, `tools/frontend/main.py`, `tools/frontend/progress.py`, `tools/frontend/report.py`, `tools/kwargs_typehints/arguments.py`, `tools/kwargs_typehints/core.py`, `tools/kwargs_typehints/main.py`, `tools/kwargs_typehints/report.py`, `tools/lints/arguments.py`, `tools/lints/compliance.py`, `tools/lints/core.py`, `tools/lints/js_delimiters.py`, `tools/lints/js_function_blocks.py`, `tools/lints/long_lines_engine.py`, `tools/lints/main.py`, `tools/lints/report.py`, `tools/lints/shebang.py`, `tools/performance/arguments.py`, `tools/performance/main.py`, `tools/readme/arguments.py`, `tools/readme/core.py`, `tools/readme/main.py`, `tools/readme/metrics.py`, `tools/record/action_schema.py`, `tools/record/arguments.py`, `tools/record/core.py`, `tools/record/http_request.py`, `tools/record/main.py`, `tools/record/project_info.py`, `tools/record/response_paths.py`, `tools/record/selector_engine.py`, `tools/record/selector_resolver.py`, `tools/record/selector_sandbox.py`, `tools/record/selector_snapshot.py`, `tools/record/selector_targets.py`, `tools/record/selectors.py`, `tools/record/studio/action_commands.py`, `tools/record/studio/project_commands.py`, `tools/record/studio/projects.py`, `tools/record/studio/selector_commands.py`, `tools/record/studio/service.py`, `tools/record/studio/window.py`, `tools/reports/bundle.py`, `tools/reports/render.py`, `tools/self_test/arguments.py`, `tools/self_test/main.py`, `tools/visual_cause/arguments.py`, `tools/visual_cause/core.py`, `tools/visual_cause/main.py`, `tools/visual_cause/queries.py`, `tools/visual_cause/report.py`, `tools/visual_cause/service.py`, `tools/visual_cause/targets.py`

## Tests

Tests live in `exactus/tests/tools/common/`.

- `process_layer/test_access.py` — Shared-secret provisioning and responder lifecycle. (10 tests)
  - `test_authkey_env_override`
  - `test_authkey_env_override_rejects_short_keys`
  - `test_authkey_generates_and_reuses_file`
  - `test_authkey_honours_access_module`
  - `test_authkey_regenerates_short_files`
  - `test_runtime_dir_defaults_to_cwd_reports`
  - `test_runtime_dir_prefers_reports_env`
  - `test_runtime_dir_uses_output_parent`
  - `test_start_responder_starts_or_degrades`
  - `test_stop_responder_accepts_none`
- `process_layer/test_control.py` — Authenticated loopback identity discovery behavior. (11 tests)
  - `test_discover_finds_responder`
  - `test_discover_validates_workers`
  - `test_exactus_candidates_filters_by_process_identity`
  - `test_identify_rejects_bad_inputs`
  - `test_identify_rejects_wrong_authkey`
  - `test_identify_verifies_live_responder`
  - `test_listen_table_reports_own_responder_port`
  - `test_receive_none_on_early_close`
  - `test_receive_reads_exact_bytes`
  - `test_responder_rejects_invalid_configuration`
  - `test_responder_start_close_lifecycle`
- `process_layer/test_termination.py` — Verified-tree process termination behavior. (7 tests)
  - `test_database_pids_outside_tree_are_skipped`
  - `test_missing_database_yields_empty_pid_set`
  - `test_result_properties`
  - `test_terminate_absent_root_marks_exited`
  - `test_terminate_kills_verified_tree`
  - `test_terminate_refuses_self`
  - `test_terminator_rejects_nonfinite_timeouts`
- `test_activity.py` — The fixed ``@activity.json`` schema, its bounded log and atomic file. (12 tests)
  - `test_concurrent_readers_never_see_partial_documents`
  - `test_document_bounds_the_written_events`
  - `test_document_round_trips_through_json`
  - `test_failed_replace_keeps_the_previous_file`
  - `test_file_write_is_atomic_and_leaves_no_temporaries`
  - `test_foreign_payloads_are_rejected`
  - `test_log_keeps_only_the_newest_events`
  - `test_log_records_from_a_signal_handler_holding_the_lock`
  - `test_malformed_blocks_fall_back_to_defaults`
  - `test_payload_has_the_fixed_key_set`
  - `test_progress_fraction_is_clamped`
  - `test_worker_progress_survives_activity_file_roundtrip`
- `test_analyzers.py` — In-process runs of every static analyzer over the toolkit and a sample. (3 tests)
  - `test_real_world_corpus`
  - `test_sample_project_exactus`
  - `test_self_exactus_writes_reports`
- `test_catalog.py` — Catalog validation, alias resolution, and pipeline wave planning. (12 tests)
  - `test_alias_collisions_rejected`
  - `test_coverage_tests_aliases`
  - `test_duplicate_identifiers_rejected`
  - `test_identifier_lookup_accepts_dash_spellings`
  - `test_lookup_helpers`
  - `test_nested_pipelines_and_waves`
  - `test_packaged_tool_layout`
  - `test_pipeline_cycle_rejected`
  - `test_resolve_deduplicates`
  - `test_resolve_pipeline_unknown_member`
  - `test_unified_pipeline_audits_readmes_after_every_other_tool`
  - `test_unknown_references_rejected`
- `test_collect_files.py` — The ``FILES`` bundle written beside reports when collecting files. (8 tests)
  - `test_collect_report_files_bundles_findings`
  - `test_collect_report_files_lists_missing`
  - `test_collect_report_files_reads_snapshots`
  - `test_collect_report_files_without_report`
  - `test_common_parser_accepts_collect_files`
  - `test_mark_exports_collection`
  - `test_requested_and_mark_accept_underscore_flag`
  - `test_requested_flag_or_environment`
- `test_common.py` — Shared helpers: output resolution, filtering, and bundle discovery. (20 tests)
  - `test_activate_exposes_chromium_browsers`
  - `test_activate_requires_python_dir`
  - `test_bundle_cache_failures`
  - `test_bundle_resolution_and_cache`
  - `test_embedded_bundle_dir`
  - `test_embedded_bundle_dir_absent`
  - `test_executable_candidate`
  - `test_expand_paths`
  - `test_host_bundle_dirs`
  - `test_is_reports_tree`
  - `test_linter_command_order`
  - `test_map_lanes_and_misc`
  - `test_match_path`
  - `test_materialize_bundle`
  - `test_parse_common_arguments`
  - `test_platform_support`
  - `test_resolve_bundle_via_embedded`
  - `test_resolve_output`
  - `test_resolve_report_output`
  - `test_toolchain_resolution`
- `test_common_package.py` — The common package is a leaf: it imports nothing else from the repo. (3 tests)
  - `test_common_imports_only_itself`
  - `test_common_init_has_no_imports`
  - `test_common_modules_exist`
- `test_config.py` — Discovery, parsing, merging and rendering of ``[tool.exactus]`` settings. (27 tests)
  - `test_canonical_section_precedence`
  - `test_canonical_tool_list_extends_common_list`
  - `test_common_key_unknown_to_a_tool_is_skipped`
  - `test_common_keys_standalone_only`
  - `test_discover_boundary_contains_the_walk`
  - `test_discover_boundary_relocates_outside_start`
  - `test_discover_skips_files_without_exactus_table`
  - `test_discover_stops_at_root_marker`
  - `test_discover_walks_upward_nearest_first`
  - `test_effective_reports_the_winning_layer`
  - `test_environment_variable_controls_discovery`
  - `test_exactus_root_bounds_discovery`
  - `test_explicit_and_disabled`
  - `test_invalid_toml_names_the_file`
  - `test_negative_values_survive`
  - `test_nested_files_merge`
  - `test_orchestrator_injection_rules`
  - `test_path_keys_resolve_against_declaring_file`
  - `test_pipeline_table_overrides_tool_table`
  - `test_render_kinds`
  - `test_reports_directory_rejects_project_escape`
  - `test_reports_directory_setting`
  - `test_standalone_reports_directory_and_cli_override`
  - `test_unknown_key_and_wrong_type`
  - `test_validate_accepts_package_owned_mcp_configuration`
  - `test_validate_rejects_legacy_sections`
  - `test_validate_rejects_unknown_table_and_common_key`
- `test_config_integration.py` — ``pyproject.toml`` settings reaching standalone tools and ``check``. (9 tests)
  - `test_check_reports_config_errors`
  - `test_check_single_tool_uses_pyproject_gate`
  - `test_context_lines_from_pyproject`
  - `test_no_config_and_explicit_config`
  - `test_orchestrated_tool_skips_config`
  - `test_orchestrator_settings_apply_to_pipeline_style_runs`
  - `test_show_config_exits_cleanly`
  - `test_standalone_config_error_exits_two`
  - `test_standalone_tool_reads_pyproject`
- `test_conflict_copies.py` — Verify automatic sync cleanup preserves unique and conflicting data. (5 tests)
  - `test_history_backups_are_never_reconciled`
  - `test_sync_compares_links_and_retries_busy_folders`
  - `test_sync_ignores_unmatched_hidden_and_symlink_directories`
  - `test_sync_merges_numbered_hidden_directories`
  - `test_sync_merges_unique_entries_and_preserves_conflicts`
- `test_context_lines.py` — The shared ``--context-lines`` option and its configuration layers. (6 tests)
  - `test_common_table_sets_every_tool`
  - `test_context_lines_type`
  - `test_default_is_three_for_every_tool`
  - `test_negative_values_are_rejected`
  - `test_pipeline_table_sits_between_tool_table_and_cli`
  - `test_tool_table_overrides_common_and_cli_wins`
- `test_digest.py` — Tool reports are digested into failure summaries for aggregates. (5 tests)
  - `test_digest_counts_rules_files_and_extras`
  - `test_distinct_groups_ignore_origin_and_port`
  - `test_empty_report_yields_an_empty_digest`
  - `test_normalized_findings_skip_the_legacy_lists`
  - `test_render_failure_lists_tables_and_escapes_pipes`
- `test_directory_inventory.py` — Verify semantic, bottom-up README inventories and idempotent repairs. (2 tests)
  - `test_bottom_up_docstrings_child_summaries_and_updates`
  - `test_repair_removes_obsolete_and_duplicate_generated_blocks`
- `test_envelope.py` — The runner-owned envelope blocks of a normalized report. (12 tests)
  - `test_artifacts_list_visible_files`
  - `test_build_returns_every_envelope_block`
  - `test_duration_human`
  - `test_environment_facts`
  - `test_gate`
  - `test_invocation_is_redacted`
  - `test_node_version_reads_the_installed_node`
  - `test_redaction_arguments`
  - `test_redaction_text`
  - `test_tool_version_without_distribution`
  - `test_unlisted_variables_never_leak`
  - `test_variables_are_allowlisted_and_redacted`
- `test_examples_run.py` — Cover the bundled ``common`` examples entry points. (8 tests)
  - `test_invocations_plan_overlapping_collisions`
  - `test_main_prepare_only_prints_commands`
  - `test_markdown_template_example_validates_fixtures`
  - `test_prepare_project_builds_an_intentionally_imperfect_fixture`
  - `test_prepare_project_rejects_an_empty_fixture`
  - `test_registry_snapshot_handles_missing_and_live_databases`
  - `test_run_demo_monitors_stubbed_processes_until_settled`
  - `test_transcript_failed_detects_coordinator_markers`
- `test_execution.py` — The shared exactus execution wrapper, fallbacks, and crash recording. (25 tests)
  - `test_analyzer_written_reports_are_kept`
  - `test_conflicting_run_is_terminated`
  - `test_crashed_exactus_records_failure`
  - `test_crashed_exactus_respects_reclaimed_output`
  - `test_exceptions_become_failed_reports`
  - `test_exited_dependent_is_reset_without_checkpoint_wait`
  - `test_failed_analyzer_stamps_existing_reports`
  - `test_fallback_markdown_truncates_and_lists`
  - `test_help_preserves_existing_exactus_evidence`
  - `test_output_reclaimed_detection`
  - `test_output_streams_are_captured`
  - `test_prepare_output_cleans_and_preserves`
  - `test_prepare_output_moves_aside_when_locked`
  - `test_previous_duration_propagates_to_reports_and_activity`
  - `test_progress_helpers`
  - `test_registry_unavailable_falls_back_to_activity`
  - `test_report_output_argument`
  - `test_report_snapshot_and_emitted`
  - `test_run_exactus_returns_exit_code`
  - `test_signal_during_run_records_interrupt`
  - `test_stream_capture_failure_is_tolerated`
  - `test_success_without_report_gets_fallback`
  - `test_terminal_summary_and_ids`
  - `test_terminate_live_run_ignores_missing_or_finished`
  - `test_web_data_payload_is_stamped`
- `test_models_api.py` — Result models, progress documents, the process API, and runtime. (12 tests)
  - `test_activity_payloads`
  - `test_detached_worker_owns_its_file_threads`
  - `test_from_report_reads_fields_and_falls_back`
  - `test_lane_progress_counts`
  - `test_progress_is_current_and_spanned`
  - `test_progress_without_run_identity`
  - `test_provisional_release_opens_dependent_file_lane`
  - `test_reconcile_variants`
  - `test_result_stats_summarizes_files_and_severities`
  - `test_run_tool_reports_crashed_worker`
  - `test_run_tool_spawns_isolated_worker`
  - `test_worker_runs_tool_and_writes_result`
- `test_output_tree.py` — Every tool run leaves ``@activity.json``, ``stderr.log``/``stdout.log``. (4 tests)
  - `test_crash_finalizes_activity_and_stderr`
  - `test_nested_reports_stay_out_of_artifacts`
  - `test_tool_run_writes_the_three_artifacts`
  - `test_uncaptured_streams_still_get_stderr_files`
- `test_pipeline_output.py` — Pipeline output lives under ``EXACTUS_RESULTS/PIPELINES/``. (21 tests)
  - `test_adopted_progress_resets_on_superseding_run`
  - `test_claim_pipeline_joins_owner_without_terminating_it`
  - `test_failed_analysis_does_not_block_ready_tool`
  - `test_gate_blocks_until_the_pipeline_reaches_the_tool_group`
  - `test_global_fraction_normalizes_each_task_before_aggregation`
  - `test_heal_reads_pipeline_activity_files`
  - `test_legacy_pipeline_output_is_removed`
  - `test_live_pipeline_marks_replaced_reports`
  - `test_pause_tree_exclude_leaves_target_running`
  - `test_pause_tree_suspends_then_resume_tree_continues`
  - `test_pipeline_activity_and_ownership`
  - `test_pipeline_does_not_wait_without_reruns`
  - `test_pipeline_paths`
  - `test_pipeline_pauses_and_releases_prelaunched_tools`
  - `test_pipeline_report_links_tool_web_reports`
  - `test_pipeline_waits_for_same_tool_reruns`
  - `test_progress_rows_overlay_external_run_progress`
  - `test_release_group_keeps_paused_run_while_lease_is_held`
  - `test_standalone_run_waits_at_the_group_gate`
  - `test_unified_refresh_completes_the_progress_block`
  - `test_wave_adopts_and_drains_an_external_run`
- `test_pipeline_supervisor.py` — Verify transactional pipeline ownership and observer generations. (5 tests)
  - `test_claims_are_isolated_by_pipeline`
  - `test_compatible_claim_requests_a_shared_generation`
  - `test_connection_recreates_schema_after_runtime_reset`
  - `test_incompatible_and_sealed_claims_wait`
  - `test_terminal_owner_is_observable_and_replaceable`
- `test_process_control.py` — Process-tree control and JSON state primitives. (7 tests)
  - `test_parent_map_from_proc`
  - `test_parent_map_without_ps`
  - `test_process_exists_and_parent_map`
  - `test_process_json_roundtrip`
  - `test_replaced_exactus_exits_with_notice`
  - `test_terminate_tree_escalates_to_kill`
  - `test_terminate_tree_kills_children`
- `test_progress_ownership.py` — Keep terminal progress tied to the invocation being displayed. (1 tests)
  - `test_progress_ignores_previous_run_until_current_heartbeat`
- `test_registry.py` — The cross-process run registry. (10 tests)
  - `test_activity_ledger_and_source_resource_leases`
  - `test_claim_beat_finish_live`
  - `test_concurrent_connection_lifecycles_do_not_deadlock`
  - `test_conflicts_and_reaping`
  - `test_for_output_resolution`
  - `test_prune_old_and_trim_finished`
  - `test_record_decoding_is_defensive`
  - `test_runtime_env_limits_bound_finished_runs`
  - `test_sanitize_bounds_rows_and_text`
  - `test_unavailable_registry_degrades`
- `test_report_comparison.py` — Exercise baseline retention and per-section report comparisons. (16 tests)
  - `test_aggregate_deltas_use_previous_tool_snapshots`
  - `test_aggregate_with_counts_but_no_finding_history`
  - `test_apply_includes_previous_duration`
  - `test_baseline_survives_cleanup_and_reaches_worker`
  - `test_capture_records_previous_duration`
  - `test_coverage_metrics_exclude_file_details`
  - `test_coverage_remains_unresolved_when_measurements_change`
  - `test_equal_totals_still_detect_different_endpoints`
  - `test_first_run_comparison_duration_is_none`
  - `test_first_run_marks_delta_unavailable`
  - `test_local_server_findings_ignore_run_time_and_ephemeral_port`
  - `test_markdown_omits_missing_previous_duration`
  - `test_markdown_renders_previous_duration`
  - `test_rule_categories_include_zero_counts_and_real_deltas`
  - `test_sparse_count_maps_compare_missing_members_as_zero`
  - `test_subsections_metrics_and_repeated_findings`
- `test_report_templates.py` — The shipped report templates render goldens and reach the bundle. (5 tests)
  - `test_bundle_ships_the_common_web_assets`
  - `test_empty_example_keeps_every_section`
  - `test_error_example_renders_missing_blocks_as_na`
  - `test_example_matches_golden`
  - `test_pipes_in_cells_and_globs_survive`
- `test_report_time.py` — Verify readable report timestamps and recorded-time precedence. (2 tests)
  - `test_readable_timezone_conversion`
  - `test_run_time_precedence`
- `test_snippets.py` — Bounded, root-confined source excerpts around finding lines. (18 tests)
  - `test_binary_file_is_skipped`
  - `test_context_depth_is_capped`
  - `test_context_zero_and_negative_keep_only_the_target`
  - `test_cr_at_a_buffer_boundary_pairs_with_its_lf`
  - `test_finding_excerpt_needs_a_path_and_a_positive_line`
  - `test_huge_lines_are_clipped_without_breaking_numbering`
  - `test_invalid_utf8_is_replaced`
  - `test_language_from_file_name`
  - `test_last_line_without_newline_is_read`
  - `test_line_endings_follow_universal_newlines`
  - `test_middle_of_file_has_context_on_both_sides`
  - `test_paths_outside_the_root_are_refused`
  - `test_scan_limit_gives_up`
  - `test_start_and_end_of_file_are_clipped`
  - `test_symlink_inside_the_root_is_followed`
  - `test_unreadable_file_gives_nothing`
  - `test_unusable_lines_and_files_give_nothing`
  - `test_with_excerpts_annotates_every_finding`
- `test_sprint.py` — Flushed printing helpers and the ``DEBUG.txt`` capture directives. (12 tests)
  - `test_clear_drops_old_records`
  - `test_color_follows_terminal_detection`
  - `test_debug_site_skips_module_frames`
  - `test_default_streams`
  - `test_levels_prefix_output`
  - `test_max_age_parsing`
  - `test_record_is_written_and_filtered`
  - `test_record_survives_unwritable_target`
  - `test_save_target_resolution`
  - `test_selector_matching`
  - `test_selector_parsing`
  - `test_spec_parsing`
- `test_stderr_capture.py` — Standard-error capture: line counts, levels and the mirror. (4 tests)
  - `test_mirror_records_and_forwards_sys_stderr`
  - `test_pending_line_buffer_is_capped`
  - `test_recorder_lock_is_reentrant`
  - `test_recorder_splits_chunks_into_lines`
- `test_terminal.py` — ANSI terminal rendering, progress painting, and cursor probing. (19 tests)
  - `test_bar_is_contiguous_and_marks_issues_red`
  - `test_clear_screen_on_windows`
  - `test_dsr_cursor_moves`
  - `test_dsr_cursor_moves_bad_descriptor`
  - `test_dsr_cursor_moves_without_termios`
  - `test_dsr_reply_without_descriptor`
  - `test_helpers`
  - `test_mirror_tty_attaches_and_detaches`
  - `test_mirror_tty_skips_own_terminal`
  - `test_plain_progress_logs_transitions`
  - `test_probe_cursor_branches`
  - `test_probe_without_tty`
  - `test_progress_marks_failure_cells`
  - `test_progress_paints_and_repaints`
  - `test_progress_requires_tty`
  - `test_refreshed_report_status_and_legend`
  - `test_results_table`
  - `test_standalone_progress_and_cursor`
  - `test_tty_name_requires_real_terminal`
- `test_terminal_progress.py` — Determinate and indeterminate terminal progress rendering. (5 tests)
  - `test_context_manager_closes`
  - `test_determinate_lifecycle`
  - `test_indeterminate_mode_and_auto_start`
  - `test_settings_validation`
  - `test_width_expressions_and_rejections`
- `test_toml.py` — Round-trip coverage for the dependency-free TOML serializer. (14 tests)
  - `test_array_of_tables_roundtrip`
  - `test_array_of_tables_with_nested_array_of_tables`
  - `test_array_of_tables_with_nested_tables`
  - `test_empty_table_keeps_header`
  - `test_generated_pyproject_shape`
  - `test_mixed_array_rejects_tables`
  - `test_nested_tables_emit_dotted_headers`
  - `test_non_bare_key_is_quoted`
  - `test_non_finite_float_rejected`
  - `test_scalar_arrays_roundtrip`
  - `test_scalars_roundtrip`
  - `test_string_escaping`
  - `test_temporal_scalars_roundtrip`
  - `test_unsupported_type_rejected`
- `test_tool_worker.py` — Detached exactus worker specifications, results, and lifecycle hooks. (6 tests)
  - `test_build_spec_leaves_dependency_ordering_to_the_supervisor`
  - `test_context_and_worker_arguments_round_trip`
  - `test_control_broadcast_and_external_descriptor_join`
  - `test_lifecycle_hooks_publish_state_cleanup_and_reap`
  - `test_live_status_distinguishes_gone_from_ipc_timeout`
  - `test_result_from_status_prefers_report_and_crashes_when_missing`
- `test_toolkit.py` — Validate catalog, collection, and current partitioned tool dispatch. (5 tests)
  - `test_all_listed_tools_have_a_command`
  - `test_collect_files_skips_generated_output`
  - `test_every_script_exists`
  - `test_excluded_dir_rules`
  - `test_normalize_strips_decoration`

<!-- exactus:reference:end -->
