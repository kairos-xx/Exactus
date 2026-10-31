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
| `root` |  | default=Constants.project_root, nargs='?', type=Path |
| `-o, --output` | _join(parts=('Report destination; defaults to result.json inside', 'the configured output directory.'), separator=' ') | default=None, type=Path |
| `-j, --workers` | Maximum simultaneous linter processes. | default=max(1, min(16, cpu_count() or 4)), type=int |
| `--unsafe-fixes` | Allow Ruff's unsafe fixes during source stabilization. | action='store_true' |
| `--collect-files` | Bundle the FILES archive of flagged source files. | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

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
  - `report_readme` = `'# `ALL_LINTS_RESULTS/`\n\nStandalone `exactus/packages/all_lints` ...`
  - `artifacts_readme` = `'# `ARTIFACTS/`\n\nExecution evidence of the standalone `exactus/pa...`
  - `files_readme` = `'# `FILES/`\n\nEvery file that produced diagnostics in `../result.j...`
  - `project_root` = `Path(__file__).resolve().parents[3]`
  - `pyproject` = `'pyproject.toml'`
  - `excludes` = `('**/node_modules', '**/__pycache__', '**/.*', 'mutants', '**/mutan...`
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
  - `tsc_pattern` = `compile_regex(pattern=_join(parts=('^(?P<file>.+?)\\((?P<line>\\d+)...`
  - `html_pattern` = `compile_regex(pattern=_join(parts=('^(?P<file>.+?): line (?P<line>\...`
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
  - Fields: `file: str`, `command: list[str]`, `status: str`, `exit_code: int | None`, `duration_seconds: float`, `diagnostics: list[Diagnostic]`, `stdout: str`, `stderr: str`, `format_calls: int`, `fix_calls: int`, `start_size: int`, `end_size: int`, `size_delta: int`, `start_datetime: datetime | None`, `end_datetime: datetime | None`, `total: int`, `current: int`, `started_monotonic: float`
- `class StabilizationStart` — Capture the moment one file's stabilization began.
  - Fields: `size: int`, `datetime: datetime`, `time: float`
- `class ToolResult` — Represent the aggregate result of one tool's file tasks.
  - Fields: `name: str`, `status: str`, `duration_seconds: float`, `total_files: int`, `completed_files: int`, `diagnostics: list[Diagnostic]`, `files: list[FileResult]`
- `class ToolSpec` — Describe a linter and the files it accepts.
  - Fields: `name: str`, `executable: str`, `parser: str`, `suffixes: frozenset[str]`, `arguments: tuple[str, ...]`, `file_before_arguments: bool`, `command_prefix: tuple[str, ...]`, `project: bool`, `batch: bool`, `batch_chunks: int | None`, `derived_from: str | None`, `derived_prefix: str`, `derived_exclude: tuple[str, ...]`
  - `command(*, file: Path) -> list[str]` — Build the command for exactly one source file.
  - `available() -> bool` — Return whether the command prefix can be launched.
- `class ProgressState` — Store mutable counters for one progress row.
  - Fields: `total: int`, `completed: int`, `issues: set[int]`
- `class FinishCallback(Protocol)` — Define the callback invoked after processing each file.
- `class FileRepair(Protocol)` — Define a per-file repair applied inside the stabilization loop.
- `class BatchFileRepair(Protocol)` — Define a batch repair applied inside the stabilization loop.
  - `repair_many(*, paths: tuple[Path, ...]) -> None` — Repair stabilized Python files in one batch.
- `class ProgressListener(Protocol)` — Define the sink notified when audit progress changes.
- `class RuffStabilizerOptions` — Configure Ruff stabilization without widening its constructor.
  - Fields: `command_prefix: tuple[str, ...]`, `unsafe_fixes: bool`, `repair: FileRepair | None`, `batch_repair: BatchFileRepair | None`
- `class RuffStabilizer` — Format and fix Python files with Ruff in parallel until stable.
  - `ruff_format_until_stable(*, path: Path) -> int` — Run Ruff format until a file stops changing.
  - `ruff_fix_until_stable(*, path: Path) -> int` — Run Ruff check --fix until a file stops changing.
- `class ProgressDisplay` — Render one global and one per-tool live progress bar.
  - `render() -> None` — Render or refresh the complete progress block.
  - `update(*, tool: str, files: list[Path]) -> None` — Set one tool's discovered file list and refresh the display.
  - `finish(*, tool: str, file: str, issues: bool=False) -> None` — Record one completed file task and refresh the display.
  - `flag_issue(*, tool: str, file: str) -> None` — Mark an already-completed file task as having issues.
  - `heartbeat() -> None` — Publish activity without inventing completed work.
- `class IgnoreMatcher` — Match project-relative paths against merged ignore patterns.
  - `matches(*, path: Path) -> bool` — Return whether a relative path is ignored.
- `class Configuration` — Load merged default and pyproject exclusion rules.
  - `excludes(*, tool: str) -> list[str]` — Return merged exclusions for one tool.
  - `output_dir() -> str` — Return the configured report directory name.
  - `collect_files() -> bool` — Return whether the ``FILES`` bundle is enabled.
- `class AuditRunner` — Batch type checkers and run remaining checks per discovered file.
  - `use_repair(*, repair: FileRepair | None) -> None` — Install the repair applied while files are stabilized.
  - `use_batch_repair(*, repair: BatchFileRepair | None) -> None` — Install the batch repair applied while files are stabilized.
  - `discover(*, spec: ToolSpec) -> list[Path]` — Discover nonignored files accepted by one tool.
  - `run_file(*, spec: ToolSpec, file: Path) -> FileResult` — Run exactly one linter process against one source file.
  - `run_all(*, specs: list[ToolSpec], stabilize: bool=False, unsafe_fixes: bool=False, listener: ProgressListener | None=None, draw: bool=True) -> list[ToolResult]` — Run every file task through one parallel worker pool.
- `class ReportBuilder` — Build the aggregate JSON document.
  - `build(*, root: Path, started_at: datetime, duration_seconds: float, results: list[ToolResult], previous: PreviousReport | None=None) -> JsonObject` — Build the normalized report.
- `class Arguments(Namespace)` — Provide typed CLI storage.
- `class Cli` — Provide the command-line interface.
  - `main() -> int` — Run the audit CLI.
  - `parser() -> ArgumentParser` — Build the CLI parser.
  - `specs() -> list[ToolSpec]` — Return canonical single-file linter specifications.
- `main() -> int` — Run the merged linter audit.

## Examples

Runnable demonstration for `exactus/packages/all_lints/`.

`run.py` rebuilds a throwaway project under the git-ignored
`.scratch/` folder on every run: a `pyproject.toml` carrying
`[tool.ruff]` and `[tool.basedpyright]` ignore settings and one Python
file. It prints the merged exclude patterns, shows the command lines
the audit would launch, and writes a synthetic aggregate report — no
real linters are invoked, so it runs offline every time.

```bash
python -m exactus.packages.all_lints.examples
```

Files: `.scratch/demo_project/app.py`, `.scratch/demo_project/pyproject.toml`, `__init__.py`, `__main__.py`, `run.py`

## Dependencies and consumers

- Other packages: [`steps`](../steps/DOCS.md), [`tree`](../tree/DOCS.md)
- Used by: `tools/lints/core.py`, `tools/lints/long_lines.py`, `tools/lints/packages_pipeline.py`

## Tests

Tests live in `exactus/tests/packages/all_lints/`.

- `test_all_lints.py` — Exercise the merged linter audit: parsers, excludes, specs and report. (61 tests)
  - `test_severity_normalization`
  - `test_ruff_parser`
  - `test_eslint_parser`
  - `test_typescript_parser`
  - `test_excludes_default_without_pyproject`
  - `test_excludes_merge_pyproject`
  - `test_specs_build_single_file_commands`
  - `test_report_builder_shape`
  - `test_report_files_list_only_files_with_issues`
  - `test_parse_pyrefly_diagnostics`
  - `test_parse_dispatches_to_tool_parser`
  - `test_summary_table`
  - `test_summary_table_reports_unique_file_totals`
  - `test_run_all_parallel`
  - `test_run_all_tool_durations_reflect_process_spans`
  - `test_run_all_forwards_progress_to_listener`
  - `test_shared_discovery_preserves_each_tool_scope`
  - `test_cli_defaults`
  - `test_progress_counts_checks_not_fully_checked_files`
  - `test_typechecker_batches_keep_diagnostics`
  - `test_batched_tool_paces_progress_during_the_run`
  - `test_batched_tool_paces_progress_against_the_estimated_duration`
  - `test_previous_durations_reads_the_last_report`
  - `test_batched_warning_diagnostic_fails_its_file`
  - `test_typescript_project_run_attributes_findings`
  - `test_typescript_skips_without_project_config`
  - `test_tool_spec_uses_command_prefix`
  - `test_missing_file_falls_back`
  - `test_file_result_stabilizer_defaults`
  - `test_stabilizer_rejects_missing_files`
  - `test_stabilizer_reports_stable_file`
  - `test_stabilizer_reruns_ruff_after_a_repair`
  - `test_runner_exposes_the_repair_installer`
  - `test_stabilizer_tracks_batch_progress`
  - `test_stabilizer_rechecks_after_mutation`
  - `test_stabilizer_forwards_unsafe_fixes`
  - `test_stabilizer_fails_when_never_stable`
  - `test_run_all_stabilize_skips_without_ruff`
  - `test_run_all_stabilize_without_ruff_spec`
  - `test_run_all_stabilize_without_python_files`
  - `test_run_all_stabilize_runs_ruff_on_discovered_files`
  - `test_run_all_stabilize_lets_other_tools_start`
  - `test_terminate_processes_kills_registered_children`
  - `test_main_keyboard_interrupt_returns_130`
  - `test_main_writes_lint_report_tree`
  - `test_embedded_run_writes_no_lint_report`
  - `test_main_fail_report_records_fail_activity`
  - `test_main_custom_output_also_writes_canonical_result`
  - `test_main_collect_files_writes_files_bundle`
  - `test_main_files_bundle_archives_flagged_files`
  - `test_pyproject_configures_report_dir_and_collect_files`
  - `test_configuration_all_lints_defaults`
  - `test_main_function_delegates_to_cli`
  - `test_stream_tee_mirrors_and_strips_escapes`
  - `test_cli_activity_lifecycle_and_interrupt`
  - `test_cli_activity_beats_and_drops_events`
  - `test_cli_activity_tolerates_unwritable_path`
  - `test_progress_display_tracks_and_renders`
  - `test_progress_display_disabled_is_silent`
  - `test_main_module_switches_to_project_python`
  - `test_examples_module_switches_to_project_python`
- `test_example_run.py` — Cover the bundled ``all_lints`` example entry point. (1 tests)
  - `test_example_module_runs_as_a_script`

<!-- exactus:reference:end -->
