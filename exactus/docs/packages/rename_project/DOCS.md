# rename_project/

Renames a project in one safe, reviewable step: the root directory, the
files and folders named after it, and every mention of its name inside
text files — each restyled to match how the name was written (lower,
upper, snake, kebab, camel and title variants). Optionally renames the
GitHub repository too.

Run as a directory: `python scripts/rename_project`.

## What it changes

- The project root directory name.
- Files and folders whose names contain the project name.
- Occurrences inside text files, restyled to each occurrence's writing
  style (`name`, `NAME`, `Name`, `name_x`, `name-x`, `nameX`).

## Safety properties

- Rename operations are ordered deepest-first so parent renames never
  invalidate pending child paths.
- Binary files and excluded directories are left untouched.
- The plan is reviewable before any mutation is applied.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Rename a project: root directory, files, and its name inside text. |
| `__main__.py` | Rename a project: root directory, files, and its name inside text. |
| `cli_help.py` | ANSI-styled ``--help``/``-h`` output shared by the root scripts. |
| `examples/` | Runnable demonstration for `exactus/packages/rename_project/`. |
| `pyproject.toml` | Standalone package metadata. |
| `pytest.ini` | Configuration file. |
| `rename_project.py` | Rename a project: its root directory, its files, and its name in text. |

Run it as a module: `python -m exactus.packages.rename_project`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `root` | repository root; located from the working directory, then the script's parent, when omitted | nargs='?' |
| `--name` | target project name in any casing; also the new root directory name (default: %(default)s) | default=Constants.default_name, metavar='NAME' |
| `--from, --alias` | extra old name to replace (repeatable); the root directory and pyproject [project] name are detected already | dest='old_names', action='append', default=[], metavar='NAME' |
| `--abbrev` | also rename an exact, case-sensitive abbreviation, e.g. AT=FB; a bare AT becomes the new name's initials in the same case (repeatable, one per spelling) | action='append', default=[], metavar='OLD[=NEW]' |
| `--allow-short-lowercase` | allow lowercase abbreviations of up to three letters, which also match words like 'at' and suffixes like '_at | action='store_true' |
| `--dotted` | also rename the dotted spelling (abc.cde); off by default because in code it is usually attribute access or an import path, such as obj.attr or package.module | action='store_true' |
| `--dotted-code` | also rewrite dotted spellings in executable code; high-risk override for intentional package/member renames; implies --dotted | action='store_true' |
| `--boundary` | word' matches a name only when it does not touch letters, digits or '_'; 'loose' also renames inside identifiers such as old_name_core (default: %(default)s) | choices=sorted(Constants.boundaries), default='word' |
| `--include` | only touch paths matching GLOB (relative, POSIX); repeatable | action='append', default=[], metavar='GLOB' |
| `--exclude` | never touch paths matching GLOB; repeatable | action='append', default=[], metavar='GLOB' |
| `--no-git` | walk the tree instead of using git ls-files (which honors .gitignore) | action='store_true' |
| `--no-rename-root` | rewrite files but keep the root directory name | action='store_true' |
| `--keep-absolute` | leave absolute paths inside the project untouched instead of making them relative | action='store_true' |
| `--no-sqlite` | do not inspect or update SQLite .db/.sqlite/.sqlite3 files | action='store_true' |
| `--sqlite-schema` | also rename SQLite table/column identifiers using ALTER TABLE | action='store_true' |
| `--max-size` | skip files larger than this (default: %(default)s) | type=int, default=Constants.default_max_size, metavar='BYTES' |
| `--github` | rename the GitHub repository behind the git remote with gh and repoint the remote, without asking; rolled back if the local rename fails. Without a flag, a discovered repository is offered interactively | dest='github', action='store_const', const=True, default=None |
| `--no-github` | never rename or offer to rename the GitHub repository | dest='github', action='store_const', const=False |
| `--remote` | git remote used for GitHub (default: %(default)s) | default='origin', metavar='NAME' |
| `--dry-run` | report changes without renaming or writing | action='store_true' |
| `--diff` | show a unified diff of every rewrite | action='store_true' |
| `--quiet` | print only the summary line | action='store_true' |
| `--yes` | apply without the confirmation question; never renames a GitHub repository by itself (use --github) | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Rename a project: root directory, files, and its name inside text.


### `__main__.py`

Rename a project: root directory, files, and its name inside text.


### `cli_help.py`

ANSI-styled ``--help``/``-h`` output shared by the root scripts.

- `class Constants` — Group module-level constants.
  - `reset` = `'\x1b[0m'`
  - `bold` = `'\x1b[1m'`
  - `dim` = `'\x1b[2m'`
  - `green` = `'\x1b[32m'`
  - `yellow` = `'\x1b[33m'`
  - `cyan` = `'\x1b[36m'`
- `styled() -> bool` — Return whether ANSI styling may be emitted on stdout.
- `paint(*, code: str, text: str) -> str` — Wrap ``text`` in an ANSI ``code`` when styling is enabled.
- `class PrettyHelpFormatter` — argparse formatter adding ANSI color to the help layout.
  - `format_help(self) -> str` — Return the full help with a styled leading usage line.
  - `start_section(self, heading: str | None) -> None` — Begin a help section with a bold heading.
- `pretty_parser(*, prog: str, description: str, epilog: str='') -> ArgumentParser` — Create an ``ArgumentParser`` with the ANSI help formatter.

### `examples/__init__.py`

Runnable demonstration for the ``rename_project`` script.


### `examples/__main__.py`

Run the rename-project example with the project virtual environment.


### `examples/project/src/project/__init__.py`

Project demo package renamed by ``examples/run.py``.

- `class Constants` — Group module-level constants.
  - `project_version` = `'0.1.0'`
- `class Project` — Tiny greeter demonstrating class-name restyling.
  - `greet(*, name: str) -> str` — Return the Project greeting.

### `examples/project/src/project/cli.py`

Command line entry point for ``project``.

- `main() -> int` — Print the Project banner.

### `examples/run.py`

Rename a throwaway copy of ``project`` with ``rename_project``.

- `class Constants` — Group module-level constants.
  - `here` = `Path(__file__).resolve().parent`
  - `template` = `here / 'project'`
  - `work` = `here / '.scratch'`
  - `new_name` = `'demo_app'`
- `main() -> int` — Copy ``project`` and rename the copy to ``demo_app``.

### `rename_project.py`

Rename a project: its root directory, its files, and its name in text.

- `class Constants` — Group module-level constants.
  - `prose` = `frozenset(('.md', '.markdown', '.rst', '.txt', '.adoc'))`
  - `data` = `frozenset(('.toml', '.yaml', '.yml', '.json', '.cfg', '.ini', '.csv', '.x...`
  - `doc_suffixes` = `frozenset(('.md', '.markdown'))`
  - `min_attribute_parts` = `2`
  - `quoted_length` = `2`
  - `line_comment` = `compile_pattern(pattern='(?:^|(?<=\\s))(?:#|//)')`
  - `code_suffixes` = `frozenset(('.c', '.cc', '.cpp', '.cs', '.css', '.go', '.h', '.hpp', '.htm...`
  - `dotted_guard_suffixes` = `code_suffixes | frozenset(('.md', '.markdown'))`
  - `styles` = `('snake', 'screaming', 'kebab', 'dot', 'flat', 'lower', 'upper', 'title',...`
  - `preference` = `{'code': ('snake', 'pascal', 'screaming', 'camel', 'kebab', 'flat', 'dot'...`
  - `boundaries` = `{'word': ('(?<!\\w)', '(?!\\w)'), 'loose': ('(?<![A-Za-z0-9])', '(?![A-Za...`
  - `path_token` = `compile_pattern(pattern='(?<![\\w/])/(?!/)(?:[\\w.@%+=~,:-]+/)*[\\w.@%+=~...`
  - `name_line` = `compile_pattern(pattern='\\s*name\\s*=')`
  - `max_leftovers` = `3`
  - `ask_attempts` = `3`
  - `github_url` = `compile_pattern(pattern='(?P<head>(?:https?://|ssh://git@|git@)github\\.c...`
  - `short_limit` = `3`
  - `valid_name` = `compile_pattern(pattern='[A-Za-z][\\w.\\- ]*')`
  - `web_attribute` = `compile_pattern(pattern='\\b(?P<name>id|class)\\s*=\\s*(?P<q>[\'\\"])(?P<...`
  - `css_symbol` = `compile_pattern(pattern='(?<![\\w-])(?P<prefix>[.#])(?P<name>[A-Za-z_][\\...`
  - `js_id` = `compile_pattern(pattern='\\bgetElementById\\s*\\(\\s*([\'\\"])(?P<name>[^...`
  - `js_selector` = `compile_pattern(pattern='\\b(?:querySelector(?:All)?|matches|closest)\\s*...`
  - `js_class` = `compile_pattern(pattern='\\.classList\\.(?:add|remove|toggle|contains|rep...`
  - `web_suffixes` = `frozenset(('.html', '.css', '.js', '.mjs'))`
  - `default_name` = `'exactus'`
  - `default_max_size` = `5 * 1024 * 1024`
  - `pruned_dirs` = `frozenset(('.git', '.hg', '.svn', '.venv', 'venv', 'node_modules', '__pyc...`
  - `module_suffixes` = `('.py', '.pyi', '.js', '.mjs', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs')`
  - `sqlite_suffixes` = `frozenset(('.db', '.db3', '.sqlite', '.sqlite3'))`
  - `sqlite_header` = `b'SQLite format 3\x00'`
- `class RenameError` — Report a problem that stops the rename before or during apply.
- `class Options` — User-controlled behavior of one rename.
  - `old_names` = `()`
  - `boundary` = `'word'`
  - `keep_absolute` = `False`
  - `rename_root` = `True`
  - `use_git` = `True`
  - `includes` = `()`
  - `excludes` = `()`
  - `max_size` = `Constants.default_max_size`
  - `abbreviations` = `()`
  - `allow_short_lowercase` = `False`
  - `dotted` = `False`
  - `dotted_code` = `False`
  - `sqlite` = `True`
  - `sqlite_schema` = `False`
  - `github` = `None`
  - `remote` = `'origin'`
  - Fields: `new_name: str`
- `class RemoteRename` — A planned GitHub repository rename.
  - Fields: `remote: str`, `owner: str`, `old: str`, `new: str`, `old_url: str`, `new_url: str`
- `class RenameRules` — Everything needed to restyle the old name into the new one.
  - Fields: `names: Pattern[str]`, `styles: dict[str, tuple[str, ...]]`, `words: tuple[str, ...]`
- `class FileEdit` — One planned content rewrite.
  - Fields: `path: Path`, `before: bytes`, `after: bytes`, `matches: int`
- `class SqliteSchemaEdit` — One SQLite table or column rename performed through ALTER TABLE.
  - Fields: `database: Path`, `kind: str`, `table: str`, `old: str`, `new: str`
- `class SqlApplicationReference` — One static application SQL reference to a renamed schema symbol.
  - Fields: `path: Path`, `line: int`, `symbol: str`, `kind: str`
- `class SqliteCellEdit` — One SQLite TEXT-cell update identified by a stable row locator.
  - Fields: `database: Path`, `table: str`, `column: str`, `locator_columns: tuple[str, ...]`, `locator_values: tuple[int | float | str | bytes | None, ...]`, `before: str`, `after: str`
- `class Plan` — Every change a rename would make.
  - `edits` = `field(default_factory=list)`
  - `sqlite_edits` = `field(default_factory=list)`
  - `sqlite_schema_edits` = `field(default_factory=list)`
  - `sql_references` = `field(default_factory=list)`
  - `renames` = `field(default_factory=list)`
  - `root_target` = `None`
  - `skipped` = `field(default_factory=list)`
  - `leftovers` = `field(default_factory=list)`
  - `guarded` = `field(default_factory=list)`
  - `web_links` = `field(default_factory=list)`
  - `remote` = `None`
  - `candidate` = `None`
  - Fields: `root: Path`
- `dotted_path_exists(*, dotted: str, roots: tuple[Path, ...]) -> bool` — Report whether a dotted name addresses an existing module or package.
- `sql_safe_dotted_spans(*, text: str) -> dict[int, tuple[tuple[int, int], ...]]` — Return SQL regions where dotted identifiers may be rewritten.
- `python_safe_dotted_spans(*, text: str) -> dict[int, tuple[tuple[int, int], ...]]` — Find Python documentation, literal-string, and comment regions.
- `byte_boundaries(*, text: str) -> tuple[int, ...]` — Return UTF-8 byte offsets for every Python character boundary.
- `byte_to_character(*, boundaries: tuple[int, ...], offset: int) -> int` — Translate an exact Tree-sitter UTF-8 byte boundary to a character index.
- `parse_tree(*, text: str, language: str) -> tuple[bytes, Node] | None` — Parse text with a Python-hosted Tree-sitter grammar, failing closed.
- `safe_dotted_spans(*, text: str, suffix: str) -> dict[int, tuple[tuple[int, int], ...]]` — Return syntax-proven regions where dotted text may be rewritten.
- `span_contained(*, span: tuple[int, int], containers: tuple[tuple[int, int], ...]) -> bool` — Return whether ``span`` is fully inside one allowed container.
- `structurally_valid_rewrite(*, text: str, suffix: str) -> bool` — Validate rewritten structured text before accepting an edit.
- `build_plan(*, root: Path, options: Options) -> Plan` — Compute every change without touching the disk.
- `move(*, source: Path, destination: Path) -> None` — Rename a path, handling case-only changes on case-folding disks.
- `apply_plan(*, plan: Plan) -> None` — Apply a plan as one transaction, rolling back on failure.
- `ask(*, question: str, details: tuple[str, ...]=(), default: bool=False) -> bool` — Ask a yes/no question with an ANSI-styled prompt.
- `main(*, arguments: Sequence[str] | None=None) -> int` — Plan, show, and apply a project rename.

## Examples

Runnable demonstration for `exactus/packages/rename_project/`.

Rename a throwaway copy of ``project`` with ``rename_project``.

```bash
python -m exactus.packages.rename_project.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/project/README.md`, `examples/project/docs/README.md`, `examples/project/docs/usage.md`, `examples/project/pyproject.toml`, `examples/project/src/README.md`, `examples/project/src/project/README.md`, `examples/project/src/project/__init__.py`, `examples/project/src/project/cli.py`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md), [`model`](../model/DOCS.md)
- Used by: `tests/packages/rename_project/test_example.py`

## Tests

Tests live in `exactus/tests/packages/rename_project/`.

- `test_adversarial_semantics.py` — Adversarial semantic-safety tests for rename_project. (6 tests)
  - `test_adversarial_classification`
  - `test_corpus_has_safety_weight`
  - `test_parser_contracts`
  - `test_source_file_exists`
  - `test_structural_validation_rejects_invalid_source`
  - `test_utf8_byte_character_round_trip`
- `test_assertions.py` — Every assertion helper passes on good input and fails on bad input. (2 tests)
  - `test_helpers_accept_valid_expectations`
  - `test_helpers_raise_on_violated_expectations`
- `test_cli_behavior.py` — CLI-level behavior of the project renamer: plans, prompts, rollback. (32 tests)
  - `test_abbreviations_are_exact_and_opt_in`
  - `test_absolute_paths`
  - `test_collisions_stop_before_any_change`
  - `test_declining_the_github_question_keeps_the_repository`
  - `test_discovered_repository_is_offered_and_renamed_on_yes`
  - `test_dotted_import_paths_that_exist_are_kept`
  - `test_dotted_javascript_and_css`
  - `test_dotted_markdown_and_chains`
  - `test_dotted_modes_override_detection`
  - `test_dotted_python_attribute_vs_string`
  - `test_dry_run_and_confirmation`
  - `test_existing_root_target_is_refused`
  - `test_github_failure_rolls_back_local_changes`
  - `test_github_needs_a_github_remote`
  - `test_github_rename_is_undone_when_repointing_fails`
  - `test_github_rename_updates_repo_remote_and_urls`
  - `test_gitignored_files_are_left_alone`
  - `test_invalid_and_identical_names`
  - `test_loose_boundary_reaches_inside_identifiers`
  - `test_markdown_heading_and_inline_code`
  - `test_mixed_case_spellings_are_reported`
  - `test_no_github_flag_never_asks`
  - `test_preserves_crlf_bom_and_mode`
  - `test_prompt_formatting_and_retry`
  - `test_pyproject_name_is_detected`
  - `test_renames_files_and_directories`
  - `test_restyles_every_casing`
  - `test_rolls_back_when_a_step_fails`
  - `test_shebang_binary_and_symlink_untouched`
  - `test_short_lowercase_abbreviation_needs_consent`
  - `test_single_word_name_follows_file_kind`
  - `test_yes_flag_never_renames_a_discovered_repository`
- `test_cli_help.py` — ANSI-styled ``--help`` output of the ``cli_help`` module. (1 tests)
  - `test_cli_help_styling`
- `test_example.py` — The ``examples/run.py`` demo renames only a throwaway copy. (2 tests)
  - `test_example_renames_only_the_copy`
  - `test_template_cli_prints_the_project_banner`
- `test_main_bootstrap.py` — Cover the rename_project package bootstrap entry points. (5 tests)
  - `test_cli_example_runs_as_a_script`
  - `test_getattr_rejects_unknown_attributes`
  - `test_main_attribute_imports_the_cli_entry_point`
  - `test_main_module_survives_without_project_python`
  - `test_main_module_uses_the_secondary_import_candidate`
- `test_next_safety_batch.py` — Regression tests for SQL, Unicode geometry, golden projects, rollback. (6 tests)
  - `test_application_sql_reference_inventory`
  - `test_failure_after_database_mutation_restores_everything`
  - `test_golden_project_updates_files_and_sqlite`
  - `test_python_ast_utf8_columns_are_character_columns`
  - `test_sql_dotted_identifier_excludes_literal_and_comments`
  - `test_sql_file_rewrites_identifier_not_dotted_literal`
- `test_roundtrip.py` — Renaming forth and back reproduces the original project exactly. (1 tests)
  - `test_rename_there_and_back_is_lossless`
- `test_safety_metrics.py` — Safety-oriented corpus metrics with asymmetric failure accounting. (1 tests)
  - `test_metric_distinguishes_error_severity`
- `test_scanners.py` — Exercise the language-aware safe-span scanners in the renamer. (12 tests)
  - `test_css_safe_offsets_mark_strings_and_comments`
  - `test_html_safe_offsets_mark_prose_and_attributes`
  - `test_javascript_safe_offsets_marks_literals`
  - `test_markdown_safe_offsets_mark_prose`
  - `test_non_ascii_text_maps_byte_offsets_to_characters`
  - `test_python_safe_spans_cover_strings_and_comments`
  - `test_python_safe_spans_exclude_fstring_bodies`
  - `test_python_safe_spans_fail_closed_on_syntax_error`
  - `test_sql_safe_spans_skip_strings_and_comments`
  - `test_typescript_safe_offsets_parse_ts_and_tsx`
  - `test_unknown_suffix_falls_back_to_comment_spans`
  - `test_web_symbol_scanner_indexes_cross_references`
- `test_sqlite_semantics.py` — SQLite safety tests for the project renamer. (12 tests)
  - `test_sqlite_ambiguous_column_rename_rolls_back`
  - `test_sqlite_generated_column_is_not_written`
  - `test_sqlite_is_restored_when_later_filesystem_step_fails`
  - `test_sqlite_named_index_is_recreated_with_new_name`
  - `test_sqlite_schema_collision_is_guarded`
  - `test_sqlite_schema_is_opt_in`
  - `test_sqlite_schema_match_is_guarded_not_rewritten`
  - `test_sqlite_schema_restored_after_later_failure`
  - `test_sqlite_schema_table_column_dependencies_are_propagated`
  - `test_sqlite_text_updates_and_blob_is_untouched`
  - `test_sqlite_wal_database_is_updated_consistently`
  - `test_sqlite_without_rowid_composite_primary_key`

<!-- exactus:reference:end -->
