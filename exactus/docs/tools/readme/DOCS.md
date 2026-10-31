# tools/readme/

The `readme` tool: audits per-directory README documentation inventories.

## Files

| File | Description |
|---|---|
| `arguments.py` | The readme grammar, declared without importing the execution engine. |
| `core.py` | The audit engine: verifies each directory's README documents its files and subdirectories. |
| `main.py` | Entry point. |
| `metrics.py` | Measure Markdown files and README sizes for the README report. |
| `templates/` | Tool-specific Markdown template/mapping. |

## Behavior

- Walks the tree checking that every directory's README documents the
  files and subdirectories it actually contains.
- `metrics.py` produces Markdown file counts and README size metrics for
  the report's summary.
- Findings identify undocumented entries and stale inventory sections;
  emits the normalized envelope like every other tool.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Readme exactus tool. |
| `arguments.py` | Declare the readme grammar without importing its execution engine. |
| `core.py` | Exactus per-directory README documentation inventories. |
| `main.py` | Exactus per-directory README documentation inventories. |
| `metrics.py` | Measure Markdown files and README sizes for the README report. |
| `templates/` | Subdirectory. |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Readme exactus tool.


### `arguments.py`

Declare the readme grammar without importing its execution engine.

- `create_parser() -> ArgumentParser` — Create parser.

### `core.py`

Exactus per-directory README documentation inventories.

- `class Constants` — README exactus constants.
  - `documented_roots` = `('src', 'tests', 'examples', 'scripts', 'resources', 'docs')`
  - `skipped_dirs` = `ExactusCommonTables.DEFAULT_EXCLUDED_DIRS | frozenset({'DEBUG.txt', 'debu...`
  - `duplicate_copy` = `compile_pattern(pattern=' \\d+(?:\\.[^.]+)?$')`
  - `rule_titles` = `{'RDM001': 'Missing README.md', 'RDM002': 'Undocumented subdirectory', 'R...`
  - `id_prefix` = `'README'`
  - `excluded_reason` = `'excluded by include/exclude rules'`
  - `readme_name` = `'README.md'`
  - `suffix_excludes` = `('**/.*', '**/*.egg-info/**', '**/*.dist-info/**')`
  - `readme_glob` = `'**/README.md'`
- `class ReadmeFinding` — One documentation-inventory violation.
  - `severity` = `'error'`
  - Fields: `rule: str`, `file: str`, `message: str`
- `class ReadmeExactusInput` — Carry the inputs of one README exactus run.
  - `fix` = `False`
  - Fields: `root: Path`, `includes: tuple[str, ...]`, `excludes: tuple[str, ...]`
- `class ReadmeDirectory` — Inventory outcome of one exactused directory.
  - Fields: `path: str`, `has_readme: bool`, `readme_bytes: int`, `entries: int`, `documented: int`, `missing: int`
- `class ReadmeSkip` — One directory found under the root but not exactused.
  - Fields: `target: str`, `reason: str`
- `class ReadmeExactusResult` — Aggregate the README exactus outcome.
  - `inventories` = `()`
  - `includes` = `()`
  - `excludes` = `()`
  - `skipped` = `()`
  - `metrics` = `field(default_factory=dict)`
  - Fields: `directories: tuple[str, ...]`, `findings: tuple[ReadmeFinding, ...]`
- `skipped(*, name: str) -> bool` — Return whether a directory entry is excluded from inventories.
- `readme(*, inputs: ReadmeExactusInput) -> ReadmeExactusResult` — Exactus every documented directory's README inventory.
- `report_data(*, result: ReadmeExactusResult) -> dict[str, JsonValue]` — Build the normalized JSON report payload.

### `main.py`

Exactus per-directory README documentation inventories.

- `create_parser() -> ArgumentParser` — Return the shared CLI grammar used by execution and completion.
- `parse_args(*, arguments: tuple[str, ...] | None=None) -> Namespace` — Parse args.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Return main.

### `metrics.py`

Measure Markdown files and README sizes for the README report.

- `collect_metrics(*, root: Path, includes: tuple[str, ...], excludes: tuple[str, ...], excluded_dirs: frozenset[str]) -> dict[str, JsonValue]` — Measure scoped Markdown files and source directories without READMEs.

## Dependencies and consumers

- Other packages: [`argument_parser`](../../packages/argument_parser/DOCS.md), [`project_python`](../../packages/project_python/DOCS.md), [`steps`](../../packages/steps/DOCS.md), [`common`](../common/DOCS.md), [`reports`](../reports/DOCS.md)
- Used by: `__main__.py`, `tests/tools/common/test_context_lines.py`, `tests/tools/common/test_directory_inventory.py`, `tests/tools/readme/test_readme.py`, `tests/tools/readme/test_readme_metrics.py`, `tests/tools/readme/test_readme_report.py`, `tests/tools/reports/test_report_snippets.py`, `tests/tools/reports/test_report_web.py`

## Tests

Tests live in `exactus/tests/tools/readme/`.

- `test_readme.py` — The README analyzer flags undocumented directory entries. (3 tests)
  - `test_readme_directory_exactus_flags_undocumented_entries`
  - `test_readme_exactus_dry_leaves_files_unchanged`
  - `test_readme_exactus_repairs_missing_inventories`
- `test_readme_metrics.py` — README owns Markdown statistics, sizes and undocumented folders. (7 tests)
  - `test_directories_without_readme`
  - `test_exclusions_apply_to_markdown`
  - `test_markdown_and_readme_statistics`
  - `test_project_without_markdown_has_empty_readme_stats`
  - `test_readme_ties_resolve_to_the_first_path`
  - `test_root_without_readme_is_listed_as_dot`
  - `test_symlinked_markdown_is_ignored`
- `test_readme_report.py` — README renders result.md from its normalized result.json and template. (5 tests)
  - `test_clean_readme_run_states_no_findings`
  - `test_crash_render_shows_error_and_na_blocks`
  - `test_execute_exactus_renders_readme_from_template`
  - `test_golden_result_renders_expected_markdown`
  - `test_report_data_is_normalized`

<!-- exactus:reference:end -->
