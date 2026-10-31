# watch/

Project-local recursive filesystem watcher that mirrors source changes
into a destination tree and records destination activity.

## Behavior

- Changes under the watched root are copied to the destination; removed
  entries are pruned when `mirror-deletes` is enabled.
- Excluded entries count as stale and are deleted during pruning —
  rsync `--delete-excluded` semantics.
- Entries on the `include` list override exclusion, so OS-generated
  files such as `.DS_Store` are left alone instead of being pruned
  repeatedly.
- Activity records are always kept, regardless of pruning rules.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Project-local recursive filesystem watcher package. |
| `__main__.py` | Run the project-local recursive filesystem watcher. |
| `core.py` | Watch a directory tree, copy changes, and record destination activity. |
| `examples/` | These examples assume `exactus/packages/watch/` is installed inside the project. |

Run it as a module: `python -m exactus.packages.watch`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `source` | Directory to watch. | nargs='?', type=Path |
| `destination` | Directory receiving changed files and folders. | nargs='?', type=Path |
| `--pyproject` | Use an explicit pyproject.toml instead of upward discovery. | default=None, type=Path |
| `--interval` |  | default=None, type=float |
| `--settle-time` |  | default=None, type=float |
| `--workers` | Parallel worker count for bulk operations (0 = auto). | default=None, type=int |
| `--exclude` |  | default=None, action='append' |
| `--include` | Keep entries matching GLOB even when excluded. | default=None, action='append' |
| `--initial-sync` |  | default=None, action='store_true' |
| `--no-initial-sync` |  | action='store_false' |
| `--mirror-deletes` |  | default=None, action='store_true' |
| `--no-mirror-deletes` |  | action='store_false' |
| `--quiet` |  | default=None, action='store_true' |
| `--no-quiet` |  | action='store_false' |
| `--install-autostart` |  | action='store_true' |
| `--uninstall-autostart` |  | action='store_true' |
| `--autostart-status` |  | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `core.py`

Watch a directory tree, copy changes, and record destination activity.

- `class Constants` — Group module-level constants.
  - `activity_name` = `'@activity.json'`
  - `autostart_label` = `'com.folder-watch-copy'`
  - `pyproject_name` = `'pyproject.toml'`
  - `config_table` = `('tool', 'watch')`
  - `autostart_plist_name` = `f'{autostart_label}.plist'`
  - `metrics_ttl` = `1.0`
  - `parallel_threshold` = `8`
  - `prune_interval` = `5.0`
- `class EntryState` — Represent the observable state of one source filesystem entry.
  - Fields: `is_directory: bool`, `is_symlink: bool`, `size: int`, `modified_ns: int`, `link_target: str | None`
- `class TreeMetrics` — Describe an inventory of a filesystem snapshot.
  - Fields: `files: int`, `directories: int`, `symlinks: int`, `total_entries: int`, `total_size_bytes: int`
- `class ActivityDelta` — Describe one successfully applied destination operation.
  - Fields: `operation: str`, `relative_path: str`, `entry_type: str`, `size_delta_bytes: int`, `transferred_bytes: int`
- `class ActivityRecorder` — Maintain an atomic machine-readable activity record in a destination.
  - `record(*, delta: ActivityDelta, source_metrics: TreeMetrics, destination_metrics: TreeMetrics, autostart_installed: bool) -> None` — Record one successful filesystem operation.
  - `write_started(*, source_metrics: TreeMetrics, destination_metrics: TreeMetrics, autostart_installed: bool) -> None` — Create the activity file when a watcher starts.
- `class MacAutostart` — Install and manage the folder watcher as a macOS LaunchAgent.
  - `installed() -> bool` — Return whether the LaunchAgent property list exists.
  - `install(*, script: Path, arguments: CliArguments) -> None` — Install and immediately bootstrap the per-user LaunchAgent.
  - `install_package(*, settings: WatchSettings) -> None` — Install this package configuration as a per-user LaunchAgent.
  - `uninstall() -> bool` — Unload and remove the installed LaunchAgent.
  - `status() -> dict[str, bool | int | str | list[str]]` — Return installed and launchctl state plus persisted arguments.
  - `plist_path() -> Path` — Return the per-user LaunchAgent property-list path.
  - `require_macos() -> None` — Reject LaunchAgent operations outside macOS.
- `class FolderWatchCopy` — Poll one directory tree and copy changes into another tree.
  - Fields: `source: Path`, `destination: Path`, `interval: float`, `settle_time: float`, `exclusions: tuple[str, ...]`, `inclusions: tuple[str, ...]`, `mirror_deletes: bool`, `verbose: bool`, `workers: int`
  - `run(*, initial_sync: bool, should_stop: Callable[[], bool] | None=None) -> bool` — Watch until interrupted or the supervisor requests a restart.
- `class WatchSettings` — Represent the fully resolved watcher configuration.
  - Fields: `source: Path`, `destination: Path`, `interval: float`, `settle_time: float`, `exclude: tuple[str, ...]`, `include: tuple[str, ...]`, `initial_sync: bool`, `mirror_deletes: bool`, `quiet: bool`, `run: bool`, `project_root: Path | None`, `pyproject: Path | None`, `workers: int`
- `class PyprojectConfig` — Discover and load ``[tool.watch]`` project configuration.
  - `load(*, path: Path) -> dict[str, bool | float | int | str | list[str]]` — Load and validate the ``[tool.watch]`` table.
  - `fingerprint(*, path: Path | None) -> str` — Return a stable identity for the current ``[tool.watch]`` table.
  - `discover(*, start: Path) -> Path | None` — Find the nearest pyproject.toml at or above a starting path.
- `class CliArguments(Namespace)` — Provide precise types for command-line argument values.
- `class FolderWatchCopyCli` — Resolve project/CLI configuration and launch FolderWatchCopy.
  - `run() -> int` — Parse arguments, manage autostart, or run the watcher.
  - `parser() -> ArgumentParser` — Build the command-line parser.
- `main() -> int` — Run the folder watcher command.

## Examples

These examples assume `exactus/packages/watch/` is installed inside the project.

### Project configuration

Copy the `[tool.watch]` table from either TOML example in `assets/` into
the project's existing `pyproject.toml`, then run:

```bash
python -m exactus.packages.watch
```

- `assets/pyproject-basic.toml` copies changes to a sibling backup
  directory without deleting destination files when their source
  disappears.
- `assets/pyproject-mirror.toml` keeps the destination as a true mirror,
  including deletions, and demonstrates additional exclusions.

All relative paths are resolved from the directory containing `pyproject.toml`.
The running command observes the `[tool.watch]` table itself. Changing a
setting such as `destination`, `exclude`, or `interval` stops the active worker
and starts a new worker with the updated values. Set `run = false` to pause all
copying while leaving the supervisor alive; changing it back to `run = true`
starts a fresh watcher without restarting the command.

### Programmatic use

`run.py` shows direct construction of `FolderWatchCopy` when the
watcher is embedded in another Python tool:

```bash
python exactus/packages/watch/examples
```

Without arguments it watches the bundled [`project/`](project/README.md)
fixture and continuously copies it into `results/project-watch-copy`
and `results/project-mirror`, matching the two `assets/` configurations:
the copy destination keeps files whose source disappears while the mirror
destination propagates deletions. An explicit pair runs a single watcher
instead:

```bash
python exactus/packages/watch/examples ./source ./destination
```

The process runs until interrupted with Ctrl+C.

### macOS autostart

After adding `[tool.watch]` to the real project `pyproject.toml`, install the
current project configuration as a LaunchAgent with:

```bash
python -m exactus.packages.watch --install-autostart
```

Inspect or remove it with:

```bash
python -m exactus.packages.watch --autostart-status
python -m exactus.packages.watch --uninstall-autostart
```

Files: `__init__.py`, `__main__.py`, `assets/pyproject-basic.toml`, `assets/pyproject-mirror.toml`, `project/src/__init__.py`, `project/src/watched.py`, `results/project-mirror/@activity.json`, `results/project-mirror/src/__init__.py`, `results/project-mirror/src/watched.py`, `results/project-watch-copy/@activity.json`, `results/project-watch-copy/src/__init__.py`, `results/project-watch-copy/src/watched.py`, `run.py`

## Dependencies and consumers

- No dependencies outside the standard library.
- Used by: `tests/common/package/test_package_independence.py`

## Tests

Tests live in `exactus/tests/packages/watch/`.

- `test_examples.py` — Exercise the programmatic watch example and its fixtures. (6 tests)
  - `test_main_runs_the_bundled_dual_watchers`
  - `test_main_runs_a_single_explicit_watcher`
  - `test_main_rejects_a_lone_source_argument`
  - `test_bundled_watchers_cover_copy_and_mirror_modes`
  - `test_stopper_expires_at_the_deadline`
  - `test_fixture_scripts_print_their_marker`
- `test_watch.py` — Exercise the project-local filesystem watcher and its CLI. (18 tests)
  - `test_config_validation_and_helpers`
  - `test_snapshot_sync_activity_changes_and_delete`
  - `test_mirror_prune_removes_excluded_destination_entries`
  - `test_inclusions_override_exclusions`
  - `test_pending_change_reset_and_no_delete_mirroring`
  - `test_destination_type_replacement_and_entry_size`
  - `test_pyproject_discovery_loading_and_errors`
  - `test_settings_precedence_and_resolution`
  - `test_autostart_helpers`
  - `test_uid_bootstrap_failures`
  - `test_cli_management_paths`
  - `test_run_loop_and_output`
  - `test_autostart_legacy_install_and_success_uid`
  - `test_copy_delete_error_branches`
  - `test_cli_all_dispatches`
  - `test_supervisor_restarts_for_changed_watch_configuration`
  - `test_run_false_pauses_until_pyproject_enables_watcher`
  - `test_more_path_and_metrics_branches`

<!-- exactus:reference:end -->
