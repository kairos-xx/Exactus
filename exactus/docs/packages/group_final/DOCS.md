# group_final/

AST-based refactoring that groups safely movable module-level `Final`
constants into a `Constants` class and updates references across the
source tree.

## Behavior

- Only provably safe constants move: values and references are resolved
  through AST analysis rather than text rewriting.
- Generated `Constants` classes follow the repository's grouped-constant
  convention; surviving references are rewritten to `Constants.<name>`.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Group safe module-level Final constants into Constants classes. |
| `__main__.py` | Run the Final constants refactoring tool. |
| `core.py` | Group safely movable module-level Final constants into Constants classes. |
| `examples/` | Runnable demonstration for `exactus/packages/group_final/`. |

Run it as a module: `python -m exactus.packages.group_final`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `root` | Python source-tree root. Defaults to the current directory. | nargs='?', type=Path, default=Path.cwd() |
| `--dry-run` | Analyze without writing. Omit to apply the changes. | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Group safe module-level Final constants into Constants classes.


### `__main__.py`

Run the Final constants refactoring tool.


### `core.py`

Group safely movable module-level Final constants into Constants classes.

- `class ConstantBinding` — Describe a module-level Final constant candidate.
  - Fields: `name: str`, `statement_index: int`, `statement: AnnAssign`
- `class ModulePlan` — Describe a safe constants-class transformation for one module.
  - `merge` = `False`
  - Fields: `path: Path`, `module_name: str`, `names: frozenset[str]`, `insertion_index: int`
- `class TransformRequest` — Collect the project context needed to transform one module.
  - Fields: `plan: ModulePlan | None`, `moved_by_module: dict[str, frozenset[str]]`, `members_by_module: dict[str, dict[str, str]]`, `current_module: str`, `current_is_package: bool`
- `class ScanReport` — Summarize one refactoring run.
  - Fields: `files: int`, `planned: int`, `constants: int`, `changed: int`, `dry_run: bool`
- `class Palette` — Collect ANSI styling constants.
  - `reset` = `'\x1b[0m'`
  - `bold` = `'\x1b[1m'`
  - `dim` = `'\x1b[2m'`
  - `red` = `'\x1b[31m'`
  - `green` = `'\x1b[32m'`
  - `yellow` = `'\x1b[33m'`
  - `cyan` = `'\x1b[36m'`
- `class ProgressDisplay` — Render a live single-row file-processing progress bar.
  - `__init__(self, *, label: str, total: int) -> None` — Initialize the display.
  - `render(self) -> None` — Draw the initial progress line.
  - `finish(self) -> None` — Record one processed file and refresh the line.
  - `close(self) -> None` — Terminate the progress line with a newline.
- `class NameCollector` — Collect loaded names from an AST subtree.
  - `__init__(self) -> None` — Initialize an empty name set.
  - `visit(self, node: AST) -> None` — Record a loaded name and recurse into the subtree.
- `class BindingCollector` — Collect every identifier bound below an AST subtree.
  - `__init__(self, *, nested: bool=True) -> None` — Initialize the collector.
  - `visit(self, node: AST) -> None` — Collect bindings while optionally stopping at nested scopes.
- `class ScopedReferenceTransformer` — Base transformer that respects function-local shadowing.
  - `__init__(self, *, tracked: frozenset[str]) -> None` — Initialize tracked identifiers.
  - `visit(self, node: AST) -> AST` — Visit a node through generic, scope-aware dispatch.
- `class LocalReferenceTransformer` — Rewrite references to moved constants inside their defining module.
  - `__init__(self, *, names: frozenset[str]) -> None` — Initialize the transformer.
- `class QualifiedReferenceTransformer` — Rewrite module-qualified constant references.
  - `__init__(self, *, module_aliases: dict[str, frozenset[str]]) -> None` — Initialize the transformer.
- `class MemberReferenceTransformer` — Rename references between members moved into ``Constants``.
  - `__init__(self, *, replacements: dict[str, str]) -> None` — Initialize member-name replacements.
  - `visit(self, node: AST) -> AST` — Rename one loaded member reference after visiting its children.
- `class ConstantsMemberTransformer` — Normalize references to members of generated Constants classes.
  - `__init__(self, *, current: dict[str, str], class_aliases: dict[str, dict[str, str]], module_aliases: dict[str, dict[str, str]]) -> None` — Initialize generated member reference mappings.
- `class FinalConstantsRefactor` — Refactor safely movable module-level Final constants project-wide.
  - `excludes` = `('**/node_modules', '**/__pycache__', '**/.*', '**/EXACTUS_RESULTS', 'mut...`
  - `__init__(self, *, root: Path, dry_run: bool) -> None` — Initialize the refactoring operation.
  - `run(self) -> ScanReport` — Analyze the source tree and rewrite it unless dry-running.
- `class DirectImportReferenceTransformer` — Rewrite names imported directly from transformed modules.
  - `__init__(self, *, replacements: dict[str, str | tuple[str, str]]) -> None` — Initialize direct-import replacements.
- `class Arguments` — Typed command-line arguments.
  - Fields: `root: Path`, `dry_run: bool`
- `class Cli` — Command-line interface.
  - `main(cls) -> int` — Run the command-line interface.
  - `parser() -> ArgumentParser` — Build the argument parser.
- `main() -> int` — Run the constants refactoring CLI.

### `examples/__init__.py`

Examples for the group_final package.


### `examples/__main__.py`

Run the group-final example with the project virtual environment.


### `examples/run.py`

Generate a demonstration project and run group_final against it.

- `class Constants` — Group module-level constants.
  - `sources` = `{'__init__.py': '"""Demonstration package for group_final."""\n', 'app.py...`
- `main() -> int` — Generate the demo project and run a dry-run demonstration.

## Examples

Runnable demonstration for `exactus/packages/group_final/`.

Generate a demonstration project and run group_final against it.

```bash
python -m exactus.packages.group_final.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md), [`steps`](../steps/DOCS.md), [`common`](../../tools/common/DOCS.md)
- Used by: `tests/packages/group_final/test_group_final.py`, `tools/lints/packages_pipeline.py`

## Tests

Tests live in `exactus/tests/packages/group_final/`.

- `test_group_final.py` — Exercise the group_final refactoring: discovery, plans and rewrites. (57 tests)
  - `test_candidate_accepts_uppercase_final`
  - `test_candidate_rejects_unsupported_statements`
  - `test_cli_main_runs`
  - `test_cli_parser_defaults_and_dry_run`
  - `test_direct_import_reference_transformer`
  - `test_example_dry_run_completes`
  - `test_examples_main_module_executes`
  - `test_is_excluded_matches_default_patterns`
  - `test_is_final_annotations`
  - `test_local_reference_transformer`
  - `test_main_delegates_to_cli`
  - `test_main_module_executes`
  - `test_module_aliases_for_import_forms`
  - `test_module_name_resolution`
  - `test_name_collector_loads_only`
  - `test_paint_wraps_or_passes_through`
  - `test_parse_trees_skips_vanished_files`
  - `test_plan_does_not_move_across_intervening_statements`
  - `test_plan_groups_movable_constants`
  - `test_plan_none_without_candidates`
  - `test_plan_uses_first_safe_contiguous_group`
  - `test_print_writes_and_flushes`
  - `test_progress_disabled_without_terminal`
  - `test_progress_no_color_keeps_plain_bar`
  - `test_progress_renders_on_terminal`
  - `test_python_files_prunes_excluded_trees`
  - `test_python_files_prunes_renamed_report_trees`
  - `test_qualified_reference_transformer`
  - `test_required_insertion_index_follows_dependencies`
  - `test_rewrite_imports_splits_moved_names`
  - `test_run_apply_rewrites_cross_module_references`
  - `test_run_apply_rewrites_local_references`
  - `test_run_avoids_constants_and_final_name_collisions`
  - `test_run_dry_run_reports_without_writing`
  - `test_run_empty_directory`
  - `test_run_inserts_typing_import_when_absent`
  - `test_run_keeps_final_import_when_still_used`
  - `test_run_leaves_partial_and_excluded_files_alone`
  - `test_run_leaves_star_import_provider_unchanged`
  - `test_run_merges_constants_into_existing_class`
  - `test_run_merges_typing_imports_in_member_order`
  - `test_run_places_class_after_docstring_and_imports`
  - `test_run_preserves_statement_order_and_annotation_dependencies`
  - `test_run_renames_private_references_between_members`
  - `test_run_rewrites_legacy_reference_to_snake_case_member`
  - `test_run_rewrites_relative_direct_imports`
  - `test_run_skips_locally_shadowed_candidate`
  - `test_run_skips_member_name_collision_on_merge`
  - `test_run_skips_merging_into_unrelated_constants`
  - `test_run_skips_provider_when_import_name_is_rebound`
  - `test_run_skips_underscore_member_collisions`
  - `test_run_strips_private_prefix_from_member_names`
  - `test_summary_colored_on_terminal`
  - `test_summary_table_labels_modes`
  - `test_top_level_definitions`
  - `test_uppercase_convention`
  - `test_used_before_detects_early_reference`

<!-- exactus:reference:end -->
