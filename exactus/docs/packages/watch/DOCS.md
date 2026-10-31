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
| `examples/` | Runnable demonstration for `exactus/packages/watch/`. |

Run it as a module: `python -m exactus.packages.watch`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `source` | Directory to watch. | type=Path, nargs='?' |
| `destination` | Directory receiving changed files and folders. | type=Path, nargs='?' |
| `--pyproject` | Use an explicit pyproject.toml instead of upward discovery. | type=Path, default=None, metavar='PATH' |
| `--interval` |  | type=float, default=None, metavar='SECONDS' |
| `--settle-time` |  | type=float, default=None, metavar='SECONDS' |
| `--workers` | Parallel worker count for bulk operations (0 = auto). | type=int, default=None, metavar='COUNT' |
| `--exclude` |  | action='append', default=None, metavar='GLOB' |
| `--include` | Keep entries matching GLOB even when excluded. | action='append', default=None, metavar='GLOB' |
| `--initial-sync` |  | action='store_true', default=None |
| `--no-initial-sync` |  | action='store_false', dest='initial_sync' |
| `--mirror-deletes` |  | action='store_true', default=None |
| `--no-mirror-deletes` |  | action='store_false', dest='mirror_deletes' |
| `--quiet` |  | action='store_true', default=None |
| `--no-quiet` |  | action='store_false', dest='quiet' |
| `--install-autostart` |  | action='store_true' |
| `--uninstall-autostart` |  | action='store_true' |
| `--autostart-status` |  | action='store_true' |
| `source` | Directory to watch (default: the bundled project/ fixture). | nargs='?', type=Path, default=None |
| `destination` | Directory receiving changes. | nargs='?', type=Path, default=None |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Project-local recursive filesystem watcher package.


### `__main__.py`

Run the project-local recursive filesystem watcher.


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
  - `__init__(self, *, source: Path, destination: Path) -> None` — Initialize an activity recorder.
  - `record(self, *, delta: ActivityDelta, source_metrics: TreeMetrics, destination_metrics: TreeMetrics, autostart_installed: bool) -> None` — Record one successful filesystem operation.
  - `write_started(self, *, source_metrics: TreeMetrics, destination_metrics: TreeMetrics, autostart_installed: bool) -> None` — Create the activity file when a watcher starts.
- `class MacAutostart` — Install and manage the folder watcher as a macOS LaunchAgent.
  - `installed(cls) -> bool` — Return whether the LaunchAgent property list exists.
  - `install(cls, *, script: Path, arguments: CliArguments) -> None` — Install and immediately bootstrap the per-user LaunchAgent.
  - `install_package(cls, *, settings: WatchSettings) -> None` — Install this package configuration as a per-user LaunchAgent.
  - `uninstall(cls) -> bool` — Unload and remove the installed LaunchAgent.
  - `status(cls) -> dict[str, bool | int | str | list[str]]` — Return installed and launchctl state plus persisted arguments.
  - `plist_path() -> Path` — Return the per-user LaunchAgent property-list path.
  - `require_macos() -> None` — Reject LaunchAgent operations outside macOS.
- `class FolderWatchCopy` — Poll one directory tree and copy changes into another tree.
  - `workers` = `0`
  - Fields: `source: Path`, `destination: Path`, `interval: float`, `settle_time: float`, `exclusions: tuple[str, ...]`, `inclusions: tuple[str, ...]`, `mirror_deletes: bool`, `verbose: bool`
  - `run(self, *, initial_sync: bool, should_stop: Callable[[], bool] | None=None) -> bool` — Watch until interrupted or the supervisor requests a restart.
- `class WatchSettings` — Represent the fully resolved watcher configuration.
  - `workers` = `0`
  - Fields: `source: Path`, `destination: Path`, `interval: float`, `settle_time: float`, `exclude: tuple[str, ...]`, `include: tuple[str, ...]`, `initial_sync: bool`, `mirror_deletes: bool`, `quiet: bool`, `run: bool`, `project_root: Path | None`, `pyproject: Path | None`
- `class PyprojectConfig` — Discover and load ``[tool.watch]`` project configuration.
  - `load(cls, *, path: Path) -> dict[str, bool | float | int | str | list[str]]` — Load and validate the ``[tool.watch]`` table.
  - `fingerprint(cls, *, path: Path | None) -> str` — Return a stable identity for the current ``[tool.watch]`` table.
  - `discover(*, start: Path) -> Path | None` — Find the nearest pyproject.toml at or above a starting path.
- `class CliArguments` — Provide precise types for command-line argument values.
  - Fields: `source: Path | None`, `destination: Path | None`, `pyproject: Path | None`, `interval: float | None`, `settle_time: float | None`, `exclude: list[str] | None`, `include: list[str] | None`, `initial_sync: bool | None`, `mirror_deletes: bool | None`, `quiet: bool | None`, `workers: int | None`, `install_autostart: bool`, `uninstall_autostart: bool`, `autostart_status: bool`
- `class FolderWatchCopyCli` — Resolve project/CLI configuration and launch FolderWatchCopy.
  - `run(cls) -> int` — Parse arguments, manage autostart, or run the watcher.
  - `parser() -> ArgumentParser` — Build the command-line parser.
- `main() -> int` — Run the folder watcher command.

### `examples/__init__.py`

Runnable examples for the folder watcher package.


### `examples/__main__.py`

Run the watch example with the project virtual environment.


### `examples/project/src/__init__.py`

Runnable examples for the folder watcher package.


### `examples/project/src/watched.py`

Print a marker the watcher copies on every edit.


### `examples/results/project-mirror/src/__init__.py`

Runnable examples for the folder watcher package.


### `examples/results/project-mirror/src/watched.py`

Print a marker the watcher copies on every edit.


### `examples/results/project-watch-copy/src/__init__.py`

Runnable examples for the folder watcher package.


### `examples/results/project-watch-copy/src/watched.py`

Print a marker the watcher copies on every edit.


### `examples/run.py`

Run the folder watcher directly from Python code.

- `class Constants` — Group module-level constants.
  - `here` = `Path(__file__).resolve().parent`
  - `source` = `here / 'project'`
  - `results` = `here / 'results'`
  - `duration` = `5.0`
- `main() -> int` — Run the bundled dual-mode demo or one explicit watcher.

## Examples

Runnable demonstration for `exactus/packages/watch/`.

Run the folder watcher directly from Python code.

```bash
python -m exactus.packages.watch.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/assets/README.md`, `examples/assets/pyproject-basic.toml`, `examples/assets/pyproject-mirror.toml`, `examples/project/README.md`, `examples/project/src/README.md`, `examples/project/src/__init__.py`, `examples/project/src/watched.py`, `examples/results/README.md`, `examples/results/project-mirror/@activity.json`, `examples/results/project-mirror/README.md`, `examples/results/project-mirror/src/README.md`, `examples/results/project-mirror/src/__init__.py`, `examples/results/project-mirror/src/watched.py`, `examples/results/project-watch-copy/@activity.json`, `examples/results/project-watch-copy/README.md`, `examples/results/project-watch-copy/src/README.md`, `examples/results/project-watch-copy/src/__init__.py`, `examples/results/project-watch-copy/src/watched.py`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md)
- Used by: `tests/packages/watch/test_examples.py`, `tests/packages/watch/test_watch.py`

## Tests

Tests live in `exactus/tests/packages/watch/`.

- `test_examples.py` — Exercise the programmatic watch example and its fixtures. (6 tests)
  - `test_bundled_watchers_cover_copy_and_mirror_modes`
  - `test_fixture_scripts_print_their_marker`
  - `test_main_rejects_a_lone_source_argument`
  - `test_main_runs_a_single_explicit_watcher`
  - `test_main_runs_the_bundled_dual_watchers`
  - `test_stopper_expires_at_the_deadline`
- `test_watch.py` — Exercise the project-local filesystem watcher and its CLI. (18 tests)
  - `test_autostart_helpers`
  - `test_autostart_legacy_install_and_success_uid`
  - `test_cli_all_dispatches`
  - `test_cli_management_paths`
  - `test_config_validation_and_helpers`
  - `test_copy_delete_error_branches`
  - `test_destination_type_replacement_and_entry_size`
  - `test_inclusions_override_exclusions`
  - `test_mirror_prune_removes_excluded_destination_entries`
  - `test_more_path_and_metrics_branches`
  - `test_pending_change_reset_and_no_delete_mirroring`
  - `test_pyproject_discovery_loading_and_errors`
  - `test_run_false_pauses_until_pyproject_enables_watcher`
  - `test_run_loop_and_output`
  - `test_settings_precedence_and_resolution`
  - `test_snapshot_sync_activity_changes_and_delete`
  - `test_supervisor_restarts_for_changed_watch_configuration`
  - `test_uid_bootstrap_failures`

<!-- exactus:reference:end -->
