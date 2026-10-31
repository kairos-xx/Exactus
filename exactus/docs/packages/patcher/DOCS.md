# `exactus.packages.patcher`

`exactus.packages.patcher` builds deterministic executable `.pyz` filesystem deltas and
applies them transactionally.

## Sources

Either side of a delta may be a directory, ZIP archive, or a `.pyz` produced
by this package. Sources are normalized into a virtual project snapshot before
comparison.

## Basic API

```python
from exactus.packages.patcher import PyzProjectPatch

patch = PyzProjectPatch.delta(
    a="/tmp/project-before",
    b="/tmp/project-after.zip",
    project_root="/srv/project",
)
patch.build(output="update.pyz")
```

The resulting PYZ contains the changed/added content plus manifest operations
for removals, moves, directories, symlinks and metadata.

## Runtime root

Without `--root`, the embedded project root is used.

An explicit `--root` always overrides the embedded root. Absolute paths remain
absolute. Relative paths are resolved against the **process invocation working
directory**, not against the location of the `.pyz`.

For example, if the shell is currently in `/srv/project`:

```console
$ /home/me/Downloads/update.pyz --root .
```

the effective root is `/srv/project`.

The same is true for:

```console
$ python /home/me/Downloads/update.pyz --root .
```

This behavior deliberately follows normal command-line path semantics.

## Inspection and safety

```console
update.pyz --dry-run
update.pyz --verify
update.pyz --list
update.pyz --info
update.pyz --json
update.pyz --conflict abort
update.pyz --conflict overwrite
update.pyz --conflict skip
update.pyz --conflict backup
update.pyz --force
```

Application validates paths and hashes before mutation, stages changes,
commits them transactionally, verifies the resulting state, and rolls back
committed operations when application fails.

## Reversal

Reversible patches retain the required before-state blobs:

```python
rollback = patch.inverse()
rollback.build(output="rollback.pyz")
```

Set `reversible=False` at build time when minimizing archive size is more
important than standalone inversion.

## Composition

Compatible patches can be composed:

```python
ac = ab.compose(next_patch=bc)
ac.build(output="a-to-c.pyz")
```

## Filtering

Use the package include/exclude facilities when constructing snapshots to omit
cache/build/packages paths that are outside the desired patch scope.

## Example

The comprehensive example can be invoked equivalently as:

```console
exactus/packages/patcher/examples/run.py
python exactus/packages/patcher/examples
python -m exactus.packages.patcher.examples
```

Run those commands from the repository root so `exactus` is importable.

## Validation

The tests cover source normalization, delta generation/application,
reversibility, deterministic builds, and invocation-directory-relative
`--root .` behavior. Production coverage is intended to remain at or above
90%.

## Self-contained patcher CLI (`--bin`)

Build the patcher itself as a standalone executable PYZ:

```console
python -m exactus.packages.patcher --project-root . --bin
```

This creates `./bin/patcher.pyz`. `--bin-dir` defaults to `bin` under the
selected project root and may be overridden with either a project-root-relative
or absolute directory:

```console
python -m exactus.packages.patcher --project-root . --bin --bin-dir tools
python -m exactus.packages.patcher --project-root . --bin --bin-dir /opt/patch-tools
```

The generated binary exposes the same exhaustive builder CLI:

```console
./bin/patcher.pyz --help
./bin/patcher.pyz --a old --b new --project-root . --output update.pyz
```

The equivalent Python API is `PatcherCli.build_binary(...)`. Delta construction
is available through both `PatcherCli.build_delta(...)` and the lower-level
`PyzProjectPatch` API.

## No-argument behavior

Both builder entry points print the complete help text and return success when
called without arguments:

```console
python -m exactus.packages.patcher
./bin/patcher.pyz
```

`--bin` accepts an optional directory directly. Bare `--bin` creates
`PROJECT/bin/patcher.pyz`; `--bin tools` creates
`PROJECT/tools/patcher.pyz`. `--bin-dir tools` remains supported with bare
`--bin`.

## Diff preview

`--diff` is read-only. It renders everything that would change and exits
without creating or applying a patch.

Builder/source diff:

```console
python -m exactus.packages.patcher --a old --b new --diff
./bin/patcher.pyz --a old --b new --diff
```

Already-built update:

```console
./update.pyz --diff
```

Output follows conventional unified-diff structure (`diff --git`, `---`, `+++`,
`@@`, `-`, `+`). ANSI coloring distinguishes headers, hunks, removals,
additions and metadata. Builder diffs additionally apply lightweight syntax
highlighting for JavaScript, CSS, HTML, Python, JSON, TOML and XML.

Use `--no-color` for logs/CI or `--diff-context N` to change context size.
Neither diff mode mutates the destination.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Build and apply deterministic executable filesystem patches. |
| `__main__.py` | Run ``exactus.packages.patcher`` through the project's virtualenv. |
| `cli.py` | Command-line and programmatic orchestration for the patcher package. |
| `core.py` | Build deterministic and transactional executable filesystem deltas. |
| `diff.py` | Render read-only ANSI unified diffs for project snapshots. |
| `examples/` | Package marker. |
| `runtime.py` | Provide the transactional runtime embedded in project-delta PYZ files. |

Run it as a module: `python -m exactus.packages.patcher`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--a` | A/before source: directory, ZIP, or generated patch PYZ. |  |
| `--b` | B/after source: directory, ZIP, or generated patch PYZ. |  |
| `--project-root` | Project root embedded into an update or used as the base for relative --bin-dir. Relative paths use invocation CWD. Default: . | default=Defaults.project_root |
| `-o, --output` | Generated delta PYZ path. Default: update.pyz | default=Defaults.output |
| `--include` | Include glob. Repeat for multiple patterns. | default=[], action='append' |
| `--exclude` | Exclude glob. Repeat for multiple patterns. | default=[], action='append' |
| `--detect-moves` | Detect identical moved entries (default). | default=True, action='store_true' |
| `--no-detect-moves` | Represent moves as independent removal/addition operations. | action='store_false' |
| `--reversible` | Store before-state blobs so the patch can be inverted (default). | default=True, action='store_true' |
| `--forward-only` | Omit before-state blobs to reduce generated patch size. | action='store_false' |
| `--compression-threshold` | Store payload blobs smaller than this many bytes without DEFLATE. Default: 64. | default=Defaults.compression_threshold, type=int |
| `--diff` | Print a read-only unified diff from A to B and exit without creating or applying a patch. | action='store_true' |
| `--no-color` | Disable ANSI colors and syntax highlighting in --diff output. | action='store_true' |
| `--diff-context` | Number of unchanged context lines in --diff output. Default: 3. | default=Defaults.diff_context, type=int |
| `--bin` | Build a self-contained patcher.pyz CLI instead of an A-to-B delta. With no PATH, use bin (or --bin-dir when supplied). With PATH, write under that project-root-relative or absolute directory, e.g. --bin tools. | default=None, nargs='?' |
| `--bin-dir` | Directory for --bin output. Relative paths are resolved under --project-root; absolute paths are preserved. Used with bare --bin. Default when omitted: bin. | default=None |
| `--root` |  | type=Path |
| `--dry-run` |  | action='store_true' |
| `--force` |  | action='store_true' |
| `--conflict` |  | default='abort', choices=('abort', 'overwrite', 'skip', 'backup') |
| `--list` |  | action='store_true' |
| `--info` |  | action='store_true' |
| `--json` |  | action='store_true' |
| `--verify` |  | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `cli.py`

Command-line and programmatic orchestration for the patcher package.

- `class DeltaBuildOptions` — Configure executable delta generation.
  - Fields: `includes: tuple[str, ...]`, `excludes: tuple[str, ...]`, `detect_moves: bool`, `reversible: bool`, `compression_threshold: int`
- `class CliArguments` — Represent fully typed parsed CLI arguments.
  - Fields: `a: str | None`, `b: str | None`, `project_root: str`, `output: str`, `includes: tuple[str, ...]`, `excludes: tuple[str, ...]`, `detect_moves: bool`, `reversible: bool`, `compression_threshold: int`, `diff: bool`, `no_color: bool`, `diff_context: int`, `bin: str | None`, `bin_dir: str | None`
- `class Defaults` — Provide immutable-by-convention patcher defaults.
- `class PatcherCli` — Expose the complete patch-builder CLI as an equivalent Python API.
  - `run(*, arguments: Sequence[str] | None=None) -> int` — Parse CLI arguments and execute the requested builder operation.
  - `build_binary(*, project_root: Path | str, bin_dir: Path | str=Defaults.bin_directory, filename: str=Defaults.bin_filename) -> Path` — Build a self-contained CLI PYZ containing the patcher package.
  - `build_delta(*, a: Path | str, b: Path | str, project_root: Path | str, output: Path | str, options: DeltaBuildOptions=Defaults.delta_build_options) -> Path` — Build an executable A-to-B project delta.
  - `parser() -> ArgumentParser` — Return the exhaustive CLI parser.
- `main(*, arguments: Sequence[str] | None=None) -> int` — Run the patcher builder CLI.

### `core.py`

Build deterministic and transactional executable filesystem deltas.

- `class DeltaOptions(TypedDict)` — Describe optional controls accepted while calculating a delta.
- `class Defaults` — Provide immutable constants used by snapshot and archive processing.
- `resolve_invocation_root(*, root: str | Path, cwd: Path | None=None) -> Path` — Resolve an application root against the invocation directory.
- `class EntryKind(StrEnum)` — Identify filesystem entry kinds representable by a snapshot.
- `class ConflictPolicy(StrEnum)` — Identify supported destination-precondition conflict policies.
- `class SnapshotEntry` — Describe one normalized filesystem entry.
  - Fields: `path: PurePosixPath`, `kind: EntryKind`, `mode: int`, `digest: str`, `link_target: str`, `content: bytes`
  - `identity() -> tuple[EntryKind, int, str, str]` — Return metadata used to determine semantic entry equality.
- `class ProjectSnapshot` — Represent a complete normalized virtual project tree.
  - Fields: `entries: tuple[SnapshotEntry, ...]`
  - `by_path() -> dict[PurePosixPath, SnapshotEntry]` — Return snapshot entries indexed by project-relative path.
  - `fingerprint() -> str` — Return a deterministic metadata and content fingerprint.
- `class DeltaOperation` — Represent one path transition between two project snapshots.
  - Fields: `path: PurePosixPath`, `before: SnapshotEntry | None`, `after: SnapshotEntry | None`, `move_from: PurePosixPath | None`
- `class PatchResult` — Describe the observable outcome of applying a project patch.
  - Fields: `added: tuple[str, ...]`, `changed: tuple[str, ...]`, `removed: tuple[str, ...]`, `moved: tuple[str, ...]`, `skipped: tuple[str, ...]`, `conflicts: tuple[str, ...]`, `bytes_written: int`, `verified: bool`, `rolled_back: bool`
- `class ProjectDelta` — Represent a deterministic transition between two project snapshots.
  - Fields: `before_fingerprint: str`, `after_fingerprint: str`, `operations: tuple[DeltaOperation, ...]`
  - `between(*, before: ProjectSnapshot, after: ProjectSnapshot, detect_moves: bool=True) -> 'ProjectDelta'` — Calculate the minimal transition between two snapshots.
  - `inverse() -> 'ProjectDelta'` — Return the exact inverse transition.
  - `compose(*, next_delta: 'ProjectDelta') -> 'ProjectDelta'` — Compose this A-to-B delta with a compatible B-to-C delta.
- `class ProjectSource` — Load snapshots from directories, ZIP archives, or patch PYZ files.
  - `from_path(*, path: Path | str, includes: Iterable[str]=(), excludes: Iterable[str]=()) -> ProjectSnapshot` — Load a normalized snapshot from a supported source path.
- `safe_relative(*, value: str) -> PurePosixPath` — Validate and normalize a project-relative POSIX path.
- `class PyzProjectPatch` — Build deterministic executable project-delta archives.
  - `delta(*, a: Path | str, b: Path | str, project_root: Path | str, **options: Unpack[DeltaOptions]) -> 'PyzProjectPatch'` — Create a delta from independently supported A and B sources.
  - `from_delta(*, delta: ProjectDelta, project_root: Path | str, before_snapshot: ProjectSnapshot, after_snapshot: ProjectSnapshot) -> 'PyzProjectPatch'` — Create a patch builder around an existing delta model.
  - `relative(*, root: Path, path: Path | str) -> PurePosixPath` — Resolve a path and return its normalized project-relative form.
  - `build(*, output: Path | str, reversible: bool=True, compression_threshold: int=64) -> Path` — Write a deterministic executable PYZ containing this delta.
  - `inverse() -> 'PyzProjectPatch'` — Return a builder representing the exact reverse patch.
  - `compose(*, next_patch: 'PyzProjectPatch') -> 'PyzProjectPatch'` — Compose this patch with a compatible subsequent patch.

### `diff.py`

Render read-only ANSI unified diffs for project snapshots.

- `class Constants` — Group module-level constants.
  - `reset` = `'\x1b[0m'`
  - `red` = `'\x1b[31m'`
  - `green` = `'\x1b[32m'`
  - `cyan` = `'\x1b[36m'`
  - `yellow` = `'\x1b[33m'`
  - `magenta` = `'\x1b[35m'`
  - `blue` = `'\x1b[34m'`
  - `dim` = `'\x1b[2m'`
  - `token` = `compile_pattern(pattern='(\\"(?:\\\\.|[^\\"\\\\])*\\"|\'(?:\\\\.|[^...`
  - `highlight_suffixes` = `frozenset({'.js', '.mjs', '.cjs', '.css', '.html', '.htm', '.py', '...`
- `class DiffRenderer` — Render deterministic unified diffs without mutating either snapshot.
  - `render(*, before: ProjectSnapshot, after: ProjectSnapshot, color: bool=True, context: int=3) -> str` — Return a human-readable delta between two snapshots.
  - `write(*, before: ProjectSnapshot, after: ProjectSnapshot, color: bool | None=None, context: int=3) -> None` — Write a rendered project diff to standard output.

### `runtime.py`

Provide the transactional runtime embedded in project-delta PYZ files.

- `class Arguments(Namespace)` — Store fully typed command-line arguments for the patch runtime.
- `class ResultData(TypedDict)` — Describe the JSON result emitted after successful application.
- `safe(*, root: Path, relative: str) -> Path` — Resolve a manifest path while preventing project-root traversal.
- `digest(*, path: Path) -> str` — Calculate the SHA-256 digest of a filesystem file.
- `state(*, path: Path) -> EntryState` — Capture the comparable state of a destination filesystem entry.
- `expected(*, raw: EntryData | None) -> EntryState` — Convert manifest entry data into a comparable expected state.
- `remove(*, path: Path) -> None` — Remove a file, symlink, or directory tree when present.
- `restore(*, source: Path, target: Path) -> None` — Restore one transaction backup entry to its destination path.
- `arguments() -> Arguments` — Parse command-line controls accepted by an executable patch.
- `diff_blob(*, package: Traversable, raw: EntryData | None) -> bytes` — Read the embedded file bytes represented by a manifest entry.
- `paint(*, text: str, code: str, enabled: bool) -> str` — Wrap text in an ANSI color sequence when coloring is enabled.
- `syntax(*, text: str, path: str, enabled: bool, base: str) -> str` — Apply lightweight syntax highlighting to supported textual files.
- `render_diff(*, package: Traversable, manifest: ManifestData, color: bool, context: int) -> str` — Render the embedded delta as a read-only unified diff.
- `main() -> int` — Run patch inspection, verification, or transactional application.

## Examples

Package marker.

Files: `__init__.py`, `__main__.py`, `run.py`

## Dependencies and consumers

- No dependencies outside the standard library.
- Used by: no other module imports it; it is run directly or through the bundle.

## Tests

Tests live in `exactus/tests/packages/patcher/`.

- `test_diff.py` — Test read-only unified diff rendering and patcher diff CLI modes. (4 tests)
  - `test_highlighted_text_diff`
  - `test_builder_diff_is_read_only`
  - `test_generated_update_diff_is_read_only`
  - `test_binary_diff_summary`
- `test_example_run.py` — Cover the bundled ``patcher`` example entry point. (1 tests)
  - `test_example_module_runs_as_a_script`
- `test_patcher.py` — Test the deterministic executable project patcher. (28 tests)
  - `test_resolve_relative_root_from_invocation_directory`
  - `test_folder_delta_and_relative_runtime_root`
  - `test_zip_as_b_source`
  - `test_inverse_restores_before_state`
  - `test_deterministic_build`
  - `test_relative_root_variants`
  - `test_source_filter_symlink_empty_directory_and_unsupported`
  - `test_ordinary_zip_directory_file_and_symlink`
  - `test_pyz_is_semantic_after_snapshot_and_nonreversible_build`
  - `test_move_detection_disable_and_composition`
  - `test_direct_constructor_removal_relative_and_outside_rejection`
  - `test_safe_relative_rejects_unsafe_values`
  - `test_manifest_validation_errors_and_corrupt_blob`
  - `test_generated_pyz_inspection_commands`
  - `test_builder_help_is_exhaustive`
  - `test_bin_default_and_generated_cli`
  - `test_generated_patch_backs_up_overlapping_removals`
  - `test_generated_binary_builds_delta`
  - `test_bin_dir_is_relative_to_project_root`
  - `test_cli_api_run_builds_binary`
  - `test_cli_api_run_builds_delta`
  - `test_parser_defaults_and_switches`
  - `test_bin_accepts_inline_directory`
  - `test_module_without_arguments_prints_help`
  - `test_generated_binary_without_arguments_prints_help`
  - `test_inline_bin_and_bin_dir_conflict`
  - `test_main_module_switches_to_project_python`
  - `test_examples_module_switches_to_project_python`
- `test_runtime.py` — Test the standalone transactional patch runtime directly. (18 tests)
  - `test_safe_accepts_nested_path_and_rejects_unsafe_paths`
  - `test_digest_state_and_expected_cover_file_directory_and_absence`
  - `test_state_and_restore_cover_symbolic_links`
  - `test_restore_copies_directory_tree`
  - `test_diff_blob_handles_absent_nonfile_and_file_payloads`
  - `test_paint_and_syntax_respect_color_controls`
  - `test_render_diff_covers_text_move_metadata_and_binary`
  - `test_runtime_manifest_accessors_reject_invalid_data`
  - `test_main_lists_and_describes_operations`
  - `test_main_diff_modes_render_and_validate`
  - `test_main_verify_and_conflict_policies`
  - `test_main_apply_commits_full_delta`
  - `test_main_rolls_back_failed_postcondition`
  - `test_main_rejects_corrupt_payload`
  - `test_main_root_resolution_variants`
  - `test_main_rejects_malformed_manifest_members`
  - `test_module_guard_invokes_main`
  - `test_safe_rejects_symlink_parent_escape`

<!-- exactus:reference:end -->
