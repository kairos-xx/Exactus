# all_lints/

Run project linters and merge their diagnostics into one JSON report.

## Behavior

- `basedpyright` and `pyrefly` run once per batch over all Python files;
  diagnostics are bucketed back to their owning files.
- `tsc` runs as a project tool: one `tsc --project <jsconfig|tsconfig>`
  invocation covers every discovered JS/TS file (via `checkJs`).
- Ruff (code + docstring lanes), ESLint, Stylelint and the HTML linter run
  per file through a shared worker pool.
- A file carrying diagnostics reports `failed` regardless of the tool's
  exit-code convention, so warn-level findings (e.g. pyrefly
  `--min-severity info`) fail the audit deterministically.
- Optional `stabilize` runs Ruff format/fix cycles before the lint passes.
  Every Ruff subprocess is checked: launch failures, timeouts, signal
  termination and exit codes above `1` raise `RuffExecutionError`,
  while exit code `1` from `check` or `format --check` reports
  findings without failing execution. Formatter and fixer fixed
  points are verified independently — byte-identical cycle output is
  not enough; read-only `format --check` must also pass. Repeated
  per-file source states abort with an oscillation diagnostic, except
  files with a proven format-then-revert signature (a fix or repair
  provably undoes the formatter's output): those are format-locked —
  the formatter's canonical output is kept, the file leaves the loop,
  `metrics.format_locked` counts them and the unsatisfiable lint rule
  surfaces as a normal diagnostic. Any other failure restores every
  owned file's original bytes and permissions (external edits detected
  during rollback are preserved and reported). `time_limit_seconds`
  bounds the whole run and `subprocess_timeout` bounds each process.
- `AuditRunner.use_repair()` installs a `FileRepair` called for each file
  after every Ruff cycle; a change triggers another cycle, so repairs end up
  formatted and fixed.
- Output is written to `LINTS_REPORT.json` with per-file commands,
  statuses, durations and diagnostics.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Run project linters and merge their diagnostics into one JSON report. |
| `__main__.py` | Run the merged linter audit. |
| `core.py` | Run project linters in parallel and merge diagnostics into one report. |
| `examples/` | Runnable demonstration for `exactus/packages/all_lints/`. |

Run it as a module: `python -m exactus.packages.all_lints`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `root` |  | nargs='?', type=Path, default=Constants.project_root |
| `-o, --output` | _join(parts=('Report destination; defaults to result.json inside', 'the configured output directory.'), separator=' ') | type=Path, default=None |
| `-j, --workers` | Maximum simultaneous linter processes. | type=int, default=max(1, min(16, cpu_count() or 4)) |
| `--unsafe-fixes` | Allow Ruff's unsafe fixes during source stabilization. | action='store_true' |
| `--collect-files` | Bundle the FILES archive of flagged source files. | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Run project linters and merge their diagnostics into one JSON report.


### `__main__.py`

Run the merged linter audit.


### `core.py`

Run project linters in parallel and merge diagnostics into one report.

- `class Constants` — Group module-level constants.
  - `output` = `'ALL_LINTS_RESULTS/result.json'`
  - `report_directory` = `'ALL_LINTS_RESULTS'`
  - `artifacts_directory` = `'ARTIFACTS'`
  - `files_directory` = `'FILES'`
  - `files_archive` = `'files.zip'`
  - `files_tree` = `'TREE.txt'`
  - `activity_name` = `'@activity.json'`
  - `activity_schema` = `'exactus/activity/v1'`
  - `activity_interval_seconds` = `1.0`
  - `activity_event_limit` = `50`
  - `log_escape_pattern` = `compile_regex(pattern='\\x1b\\[[0-9;?]*[A-Za-z]')`
  - `report_readme` = `dedent(text='            # `ALL_LINTS_RESULTS/`\n\n            Standalone...`
  - `artifacts_readme` = `dedent(text='    # `ARTIFACTS/`\n    \n    Execution evidence of the stan...`
  - `files_readme` = `dedent(text='    # `FILES/`\n    \n    Every file that produced diagnosti...`
  - `project_root` = `Path(__file__).resolve().parents[3]`
  - `pyproject` = `'pyproject.toml'`
  - `excludes` = `('**/node_modules', '**/__pycache__', '**/.*', 'mutants', '**/mutants', '...`
  - `python_suffixes` = `frozenset({'.py', '.pyi'})`
  - `javascript_suffixes` = `frozenset({'.js', '.jsx', '.mjs', '.cjs'})`
  - `typescript_suffixes` = `frozenset({'.ts', '.tsx', '.mts', '.cts'})`
  - `typescript_config_names` = `('jsconfig.json', 'tsconfig.json')`
  - `style_suffixes` = `frozenset({'.css', '.scss', '.sass', '.less'})`
  - `html_suffixes` = `frozenset({'.html', '.htm'})`
  - `eslint_severity_error` = `2`
  - `ruff_conflict_ignores` = `'D203,D213'`
  - `batch_pace_seconds` = `0.15`
  - `batch_pace_floor_seconds` = `0.005`
  - `tsc_pattern` = `compile_regex(pattern=_join(parts=('^(?P<file>.+?)\\((?P<line>\\d+),(?P<c...`
  - `html_pattern` = `compile_regex(pattern=_join(parts=('^(?P<file>.+?): line (?P<line>\\d+),...`
  - `ansi_pattern` = `compile_regex(pattern='\\x1b\\[[0-9;]*m')`
  - `ansi_reset` = `'\x1b[0m'`
  - `ansi_bold` = `'\x1b[1m'`
  - `ansi_dim` = `'\x1b[2m'`
  - `ansi_red` = `'\x1b[31m'`
  - `ansi_green` = `'\x1b[32m'`
  - `ansi_yellow` = `'\x1b[33m'`
  - `ansi_cyan` = `'\x1b[36m'`
- `class PreviousReport` — Counts recovered from the earlier aggregate report.
  - Fields: `durations: dict[str, float]`, `tool_issues: dict[str, int]`, `tool_files: dict[str, int]`, `total_issues: int`, `total_files: int`, `generated_at: str`
- `load_previous(*, output: Path) -> PreviousReport | None` — Read counts and durations from a previous aggregate report.
- `previous_durations(*, output: Path) -> dict[str, float]` — Return reusable tool durations from the previous aggregate report.
- `class Diagnostic` — Represent one normalized diagnostic.
  - Fields: `tool: str`, `file: str | None`, `line: int | None`, `column: int | None`, `end_line: int | None`, `end_column: int | None`, `severity: str`, `code: str | None`, `message: str`
- `class FileResult` — Represent one single-file linter or stabilizer result.
  - `format_calls` = `0`
  - `fix_calls` = `0`
  - `start_size` = `0`
  - `end_size` = `0`
  - `size_delta` = `0`
  - `start_datetime` = `None`
  - `end_datetime` = `None`
  - `total` = `0`
  - `current` = `0`
  - `started_monotonic` = `0.0`
  - Fields: `file: str`, `command: list[str]`, `status: str`, `exit_code: int | None`, `duration_seconds: float`, `diagnostics: list[Diagnostic]`, `stdout: str`, `stderr: str`
- `class StabilizationStart` — Capture the moment one file's stabilization began.
  - Fields: `size: int`, `datetime: datetime`, `time: float`
- `class ToolResult` — Represent the aggregate result of one tool's file tasks.
  - `optional` = `False`
  - Fields: `name: str`, `status: str`, `duration_seconds: float`, `total_files: int`, `completed_files: int`, `diagnostics: list[Diagnostic]`, `files: list[FileResult]`
- `class ToolSpec` — Describe a linter and the files it accepts.
  - `file_before_arguments` = `False`
  - `command_prefix` = `()`
  - `project` = `False`
  - `batch` = `False`
  - `batch_chunks` = `None`
  - `derived_from` = `None`
  - `derived_prefix` = `''`
  - `derived_exclude` = `()`
  - `optional` = `False`
  - Fields: `name: str`, `executable: str`, `parser: str`, `suffixes: frozenset[str]`, `arguments: tuple[str, ...]`
  - `command(self, *, file: Path) -> list[str]` — Build the command for exactly one source file.
  - `available(self) -> bool` — Return whether the command prefix can be launched.
- `class ProgressState` — Store mutable counters for one progress row.
  - `completed` = `0`
  - `issues` = `field(default_factory=set)`
  - Fields: `total: int`
- `class FinishCallback(Protocol)` — Define the callback invoked after processing each file.
- `class FileRepair(Protocol)` — Define a per-file repair applied inside the stabilization loop.
- `class BatchFileRepair(Protocol)` — Define a batch repair applied inside the stabilization loop.
  - `repair_many(self, *, paths: tuple[Path, ...]) -> None` — Repair stabilized Python files in one batch.
- `class ProgressListener(Protocol)` — Define the sink notified when audit progress changes.
- `class RuffStabilizerOptions` — Configure Ruff stabilization without widening its constructor.
  - `command_prefix` = `('ruff',)`
  - `unsafe_fixes` = `False`
  - `repair` = `None`
  - `batch_repair` = `None`
  - `subprocess_timeout` = `None`
  - `time_limit_seconds` = `None`
  - `project_root` = `None`
  - `capture_version` = `False`
  - `isolated` = `False`
  - `verify` = `True`
- `class ResolvedRuffPolicy` — Ruff policy resolved once and shared by every stage.
  - `command_prefix` = `('ruff',)`
  - `rule_flags` = `('--select', 'ALL', '--ignore', 'D203,D213')`
  - `unsafe_fixes` = `False`
  - `compact_config` = compact ``format`` ``--config`` overrides
  - `fallback_config` = `('--config', 'target-version = "py313"')` emitted only when the effective carrier leaves `target-version` unset
  - `isolated` = `False`
  - `ruff_version` = captured `ruff --version` output recorded by the stabilizer
  - `carrier` = root-level native carrier (`ruff.toml`, `.ruff.toml`, or `pyproject.toml` declaring `[tool.ruff]`), else `None`
  - `settings` = sorted flattened keys the carrier declares (`format.quote-style`, `line-length`, `extend-exclude`, ...)
  - `target_version` = carrier value, or `py313` when supplied as the fallback
  - `line_length` = carrier `line-length`, when configured
  - `preview` = carrier `preview` flag, when configured
  - `exclusions` = carrier `exclude` and `extend-exclude` patterns
  - `fingerprint` — short stable digest over the executable vector, emitted flags, captured carrier settings and probed version
  - `resolve(cls, *, options: RuffStabilizerOptions) -> ResolvedRuffPolicy` — Resolve the effective policy for one invocation.
  - `rule_flags_for(cls, *, root: Path | None) -> tuple[str, ...]` — Return rule-selection flags honoring project configuration.
  - `native_carrier(cls, *, root: Path) -> Path | None` — Return the root-level native Ruff carrier, when present.
  - `carrier_settings(cls, *, path: Path | None) -> dict[str, JsonValue]` — Return one carrier's explicit Ruff settings, merging bounded `extend` bases.
  - `explicit_keys(cls, *, settings: dict[str, JsonValue]) -> frozenset[str]` — Flatten a carrier table to explicit option keys.
  - `suppressed(cls, *, overrides: tuple[str, ...], explicit: frozenset[str]) -> tuple[str, ...]` — Drop `--config` pairs whose key a carrier explicitly sets.
  - `verify_argv(self, *, path: Path) -> tuple[str, ...]` — Build the capability probe exercising every emitted override.
  - `format_argv(self, *, paths: tuple[Path, ...], compact: bool=False, check: bool=False) -> tuple[str, ...]` — Build one ``ruff format`` argument vector.
  - `fix_argv(self, *, paths: tuple[Path, ...]) -> tuple[str, ...]` — Build one ``ruff check --fix`` argument vector.
  - `check_argv(self, *, paths: tuple[Path, ...]) -> tuple[str, ...]` — Build one read-only JSON ``ruff check`` argument vector.
- `class RuffRunResult` — Outcome of one registered Ruff subprocess.
  - Fields: `argv: tuple[str, ...]`, `returncode: int`, `stdout: bytes`, `stderr: bytes`, `duration_seconds: float`
- `class RuffExecutionError(RuntimeError)` — Ruff subprocess execution failure; lint findings reported via exit code 1 are not execution errors.
- `class RuffPolicyError(RuntimeError)` — Resolved Ruff policy rejected by the executable; raised by the capability probe before stabilization work starts.
- `class StabilizationMetrics` — Structured outcome of one stabilization run.
  - Fields: `files: int`, `invocations: int`, `iterations: int`, `per_step_changes: dict[str, int]`, `oscillated: bool`, `format_locked: int`, `converged: bool`, `rolled_back: bool`, `restored: int`, `conflicts: int`, `duration_seconds: float`, `diagnostics: int`, `policy_fingerprint: str`, `ruff_version: str | None`
- `class RuffStabilizer` — Format and fix Python files with Ruff in parallel until stable.
  - `__init__(self, *, paths: list[Path], callback: FinishCallback | None=None, max_workers: int | None=None, max_iterations: int=20, options: RuffStabilizerOptions | None=None) -> None` — Stabilize multiple Python files concurrently.
  - `metrics` — Snapshot the structured outcome of the completed run.
  - `ruff_format_until_stable(self, *, path: Path) -> int` — Run Ruff format until a file stops changing.
  - `ruff_fix_until_stable(self, *, path: Path) -> int` — Run Ruff check --fix until a file stops changing.
- `class ProgressDisplay` — Render one global and one per-tool live progress bar.
  - `__init__(self, *, totals: dict[str, int], listener: ProgressListener | None=None, draw: bool=True) -> None` — Initialize progress state.
  - `render(self) -> None` — Render or refresh the complete progress block.
  - `update(self, *, tool: str, files: list[Path]) -> None` — Set one tool's discovered file list and refresh the display.
  - `finish(self, *, tool: str, file: str, issues: bool=False) -> None` — Record one completed file task and refresh the display.
  - `flag_issue(self, *, tool: str, file: str) -> None` — Mark an already-completed file task as having issues.
  - `heartbeat(self) -> None` — Publish activity without inventing completed work.
- `class IgnoreMatcher` — Match project-relative paths against merged ignore patterns.
  - `__init__(self, *, patterns: Iterable[str]) -> None` — Initialize the matcher.
  - `matches(self, *, path: Path) -> bool` — Return whether a relative path is ignored.
- `class Configuration` — Load merged default and pyproject exclusion rules.
  - `__init__(self, *, root: Path) -> None` — Initialize project configuration.
  - `excludes(self, *, tool: str) -> list[str]` — Return merged exclusions for one tool.
  - `output_dir(self) -> str` — Return the configured report directory name.
  - `collect_files(self) -> bool` — Return whether the ``FILES`` bundle is enabled.
- `class AuditRunner` — Batch type checkers and run remaining checks per discovered file.
  - `__init__(self, *, root: Path, workers: int, targets: tuple[str, ...]=('.',), excludes: tuple[str, ...]=(), pace_estimates: Mapping[str, float] | None=None) -> None` — Initialize the runner.
  - `use_repair(self, *, repair: FileRepair | None) -> None` — Install the repair applied while files are stabilized.
  - `use_batch_repair(self, *, repair: BatchFileRepair | None) -> None` — Install the batch repair applied while files are stabilized.
  - `discover(self, *, spec: ToolSpec) -> list[Path]` — Discover nonignored files accepted by one tool.
  - `run_file(self, *, spec: ToolSpec, file: Path) -> FileResult` — Run exactly one linter process against one source file.
  - `run_all(self, *, specs: list[ToolSpec], stabilize: bool=False, unsafe_fixes: bool=False, listener: ProgressListener | None=None, draw: bool=True) -> list[ToolResult]` — Run every file task through one parallel worker pool.
- `class ReportBuilder` — Build the aggregate JSON document.
  - `build(cls, *, root: Path, started_at: datetime, duration_seconds: float, results: list[ToolResult], previous: PreviousReport | None=None) -> JsonObject` — Build the normalized report.
- `class Arguments` — Provide typed CLI storage.
  - Fields: `root: Path`, `output: Path | None`, `workers: int`, `unsafe_fixes: bool`, `collect_files: bool`
- `class Cli` — Provide the command-line interface.
  - `main(cls) -> int` — Run the audit CLI.
  - `parser() -> ArgumentParser` — Build the CLI parser.
  - `specs() -> list[ToolSpec]` — Return canonical single-file linter specifications.
- `main() -> int` — Run the merged linter audit.

### `examples/__init__.py`

Runnable demonstration for the ``all_lints`` tool.


### `examples/__main__.py`

Run the all-lints example with the project virtual environment.


### `examples/run.py`

Demonstrate ignore merging and report building on a scratch project.

- `class Constants` — Collect shared example paths and the scratch pyproject text.
  - `here` = `Path(__file__).resolve().parent`
  - `work` = `here / '.scratch' / 'demo_project'`
  - `pyproject` = `dedent(text='    [tool.ruff]\n    extend-exclude = ["fixtures", "generate...`
- `main() -> int` — Print merged excludes, tool commands, and a sample report.

## Examples

Runnable demonstration for `exactus/packages/all_lints/`.

Demonstrate ignore merging and report building on a scratch project.

```bash
python -m exactus.packages.all_lints.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md), [`steps`](../steps/DOCS.md), [`tree`](../tree/DOCS.md)
- Used by: `tests/packages/all_lints/test_all_lints.py`, `tests/packages/all_lints/test_refurb_optional.py`, `tools/lints/core.py`, `tools/lints/packages_pipeline.py`

## Tests

Tests live in `exactus/tests/packages/all_lints/`.

- `test_all_lints.py` — Exercise the merged linter audit: parsers, excludes, specs and report. (75 tests)
  - `test_batch_stabilizer_rejects_oscillation`
  - `test_batched_tool_paces_progress_against_the_estimated_duration`
  - `test_batched_tool_paces_progress_during_the_run`
  - `test_batched_warning_diagnostic_fails_its_file`
  - `test_cli_activity_beats_and_drops_events`
  - `test_cli_activity_lifecycle_and_interrupt`
  - `test_cli_activity_tolerates_unwritable_path`
  - `test_cli_defaults`
  - `test_configuration_all_lints_defaults`
  - `test_embedded_run_writes_no_lint_report`
  - `test_eslint_parser`
  - `test_examples_module_switches_to_project_python`
  - `test_excludes_default_without_pyproject`
  - `test_excludes_merge_pyproject`
  - `test_file_result_stabilizer_defaults`
  - `test_final_compact_pass_retries_after_final_fix`
  - `test_final_compact_pass_uses_expected_ruff_settings`
  - `test_main_collect_files_writes_files_bundle`
  - `test_main_custom_output_also_writes_canonical_result`
  - `test_main_fail_report_records_fail_activity`
  - `test_main_files_bundle_archives_flagged_files`
  - `test_main_function_delegates_to_cli`
  - `test_main_keyboard_interrupt_returns_130`
  - `test_main_module_switches_to_project_python`
  - `test_main_writes_lint_report_tree`
  - `test_missing_file_falls_back`
  - `test_parse_dispatches_to_tool_parser`
  - `test_parse_pyrefly_diagnostics`
  - `test_previous_durations_reads_the_last_report`
  - `test_progress_counts_checks_not_fully_checked_files`
  - `test_progress_display_disabled_is_silent`
  - `test_progress_display_tracks_and_renders`
  - `test_pyproject_configures_report_dir_and_collect_files`
  - `test_report_builder_shape`
  - `test_report_files_list_only_files_with_issues`
  - `test_ruff_parser`
  - `test_run_all_forwards_progress_to_listener`
  - `test_run_all_parallel`
  - `test_run_all_stabilize_lets_other_tools_start`
  - `test_run_all_stabilize_runs_ruff_on_discovered_files`
  - `test_run_all_stabilize_skips_without_ruff`
  - `test_run_all_stabilize_without_python_files`
  - `test_run_all_stabilize_without_ruff_spec`
  - `test_run_all_tool_durations_reflect_process_spans`
  - `test_run_kills_timed_out_process`
  - `test_run_raises_on_fatal_exit`
  - `test_run_raises_on_launch_failure`
  - `test_run_raises_on_signal_termination`
  - `test_run_rejects_findings_exit_for_format`
  - `test_run_returns_findings_result`
  - `test_runner_exposes_the_repair_installer`
  - `test_severity_normalization`
  - `test_shared_discovery_preserves_each_tool_scope`
  - `test_specs_build_single_file_commands`
  - `test_stabilizer_enforces_time_budget`
  - `test_stabilizer_fails_when_never_stable`
  - `test_stabilizer_forwards_unsafe_fixes`
  - `test_stabilizer_preserves_external_edits_on_rollback`
  - `test_stabilizer_rechecks_after_mutation`
  - `test_stabilizer_rejects_missing_files`
  - `test_stabilizer_rejects_oscillation`
  - `test_stabilizer_reports_remaining_diagnostics`
  - `test_stabilizer_reports_stable_file`
  - `test_stabilizer_reruns_ruff_after_a_repair`
  - `test_stabilizer_rolls_back_owned_changes`
  - `test_stabilizer_tracks_batch_progress`
  - `test_stream_tee_mirrors_and_strips_escapes`
  - `test_summary_table`
  - `test_summary_table_reports_unique_file_totals`
  - `test_terminate_processes_kills_registered_children`
  - `test_tool_spec_uses_command_prefix`
  - `test_typechecker_batches_keep_diagnostics`
  - `test_typescript_parser`
  - `test_typescript_project_run_attributes_findings`
  - `test_typescript_skips_without_project_config`
- `test_example_run.py` — Cover the bundled ``all_lints`` example entry point. (1 tests)
  - `test_example_module_runs_as_a_script`
- `test_refurb_optional.py` — Verify Refurb diagnostics and optional offline tool behavior. (3 tests)
  - `test_optional_unavailable_is_reported_without_failure`
  - `test_refurb_cli_registered_optional`
  - `test_refurb_output_parses`

<!-- exactus:reference:end -->

## Native subtree configuration

Audits group files by the nearest native carrier and effective argument vector.
Ruff uses `.ruff.toml`, `ruff.toml`, or `[tool.ruff]`; nested formatter settings
are preserved during compact stabilization. BasedPyright recognizes
basedpyrightconfig.json, pyrightconfig.json and both supported pyproject tables;
TypeScript uses the nearest tsconfig.json/jsconfig.json. Pyrefly is explicitly
grouped with `-c`, without relying on implicit per-file discovery. ESLint and
Stylelint retain their native cascades. Nested Exactus `*-arg` options are
forwarded only to their owning analyzer. Native includes/excludes are scoped to
their declaring folders. Analysis starts after Python mutations settle.

### Resolved Ruff policy reconciliation

`ResolvedRuffPolicy.resolve` captures the root carrier, its flattened explicit
settings (`settings`, `target_version`, `line_length`, `preview`, `exclusions`),
the `isolated` flag and a provenance `fingerprint`, then reconciles Exactus
defaults against them:

- **Per-key precedence at the root carrier**: compact `format.*` `--config`
  pairs are suppressed individually when the root carrier sets the same key —
  `format.quote-style` in `[tool.ruff.format]` drops only the matching compact
  pair while the remaining overrides still apply.
- **Nested carriers keep their own style wholesale**: files grouped under a
  non-root `ruff.toml`/`.ruff.toml`/`[tool.ruff]` receive no compact overrides
  and no `target-version` fallback at all; the nested project owns every
  setting, matching its own cascade.
- **`target-version` fallback**: `py313` is emitted via `--config` for
  unconfigured files and for the root carrier group only when the carrier does
  not set `target-version`; a carrier-set value removes the pair entirely.
- **`isolated`**: emits `--isolated`, drops the carrier (settings, rule flags
  and grouping revert to the strict `--select ALL --ignore D203,D213`
  defaults) and still applies the fallback where no explicit key survives.
- **Capability probe**: before any file work, the stabilizer runs
  `verify_argv` (`ruff check --exit-zero` carrying every emitted `--config`
  pair through the patched-`_run` seam) once per instance; an executable that
  rejects a resolved option fails fast with `RuffPolicyError`. `verify=False`
  opts out for hermetic argv tests; the probe is counted in
  `metrics.invocations`, and `metrics.policy_fingerprint`/`ruff_version`
  record the resolved identity.
- **`format.skip-magic-trailing-comma = false`**: the compact policy lets the
  formatter honor the magic trailing comma — expanding calls that carry one
  and leaving compact calls alone — so the format/fix fixed point is
  deterministic and `COM812` stays satisfied; carriers that explicitly set the
  key keep their own value.

### PYS capability map

Python simplification splits by owner rather than by convenience:

- `python_simplify` (the `PYS` lane) owns `PYS000`–`PYS006`: one-use-local
  inlining, adjacent walrus folding, provably-pure dead-store removal and the
  shared safety guard.
- The resolved Ruff policy owns the overlapping territory via `--select ALL`:
  `SIM`, `C4` and `UP` already cover nested control flow, comprehension
  intermediates, redundant temporaries and opt-in rewrites, so `PYS007`–`PYS010`
  stay reserved rather than duplicating rules the policy runs natively.

Ordinary formatting checks revisit touched files and externally changed files;
unchanged files that already reached a fixed point need no duplicate check.
Persistent Ruff LSP processing remains a future architecture option.
