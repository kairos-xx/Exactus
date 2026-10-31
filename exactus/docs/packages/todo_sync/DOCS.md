# todo_sync/

Reusable, standard-library-only TODO-list synchronizer with no
dependency on the Exactus runtime, npm, or the network. It never infers
completion or changes checkboxes.

## Behavior

- Normalized task headers use
  `**ID** **Priority** **Category** — Description`.
- `--normalize` migrates legacy headers; `--normalize --check` validates
  without writing.
- Watchers refuse to kill processes they did not start.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Dependency-free Markdown checklist dashboards and synchronization. |
| `__main__.py` | Execute the todo_sync package as a module or directory. |
| `cli.py` | Command-line entry point for the reusable TODO synchronizer. |
| `core.py` | Synchronize the managed progress dashboard in TODO.md. |
| `examples/` | Runnable demonstration for `exactus/packages/todo_sync/`. |
| `normalize.py` | Normalize checklist headers without changing task states or obligations. |
| `sync.py` | File synchronization with stable reads and atomic replacement. |
| `watch.py` | Exclusive, cooperative watchers: a persisted PID never authorizes a kill. |
| `web/` | Subdirectory. |

Run it as a module: `python -m exactus.packages.todo_sync`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--path` |  | type=Path, default=Path('exactus/docs/todo/TODO.md') |
| `--check` |  | action='store_true' |
| `--watch-stop` |  | action='store_true' |
| `--watch-status` |  | action='store_true' |
| `--no-html` | Only synchronize Markdown. | action='store_true' |
| `--interval` |  | type=float, default=0.5 |
| `--normalize` | Normalize task headers once; combine with --check to audit. | action='store_true' |
| `--watch` |  | action='store_true' |
| `--watch-child` |  | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Dependency-free Markdown checklist dashboards and synchronization.


### `__main__.py`

Execute the todo_sync package as a module or directory.


### `cli.py`

Command-line entry point for the reusable TODO synchronizer.

- `class ModeGroup(Protocol)` — Public structural interface for mutually exclusive CLI switches.
  - `add_argument(self: Self, *name_or_flags: str, action: str) -> Action` — Register a mutually exclusive command-line switch.
- `class Args` — Concrete command-line types shared with argparse.
  - `path` = `Path('exactus/docs/todo/TODO.md')`
  - `check` = `False`
  - `watch` = `False`
  - `watch_child` = `False`
  - `watch_stop` = `False`
  - `watch_status` = `False`
  - `no_html` = `False`
  - `interval` = `0.5`
  - `normalize` = `False`
- `main(argv: Sequence[str] | None=None) -> int` — Run one-shot synchronization, freshness checking or watcher control.

### `core.py`

Synchronize the managed progress dashboard in TODO.md.

- `class SyncTodoDefaults` — Immutable scalar configuration values.
  - `start` = `'<!-- ROADMAP_PROGRESS_DASHBOARD_START -->'`
  - `end` = `'<!-- ROADMAP_PROGRESS_DASHBOARD_END -->'`
  - `summary_start` = `'<!-- ROADMAP_PROGRESS_SUMMARY_START -->'`
  - `summary_end` = `'<!-- ROADMAP_PROGRESS_SUMMARY_END -->'`
- `class SyncTodoTables` — Shared lookup tables and compiled values.
  - `WORKSTREAM_LEVEL` = `2`
  - `DETAIL_LEVEL` = `5`
  - `DEFAULT_PATH` = `Path('exactus/docs/todo/TODO.md')`
  - `CHECKBOX` = `re_compile(pattern='^\\s*[-*+]\\s+\\[([xX ])\\]\\s+(.*)$')`
  - `LIST_ITEM` = `re_compile(pattern='^\\s*(?:[-*+]|\\d{1,9}[.)])\\s')`
  - `TEXT_PREFIX` = `re_compile(pattern='^(?:P[0-3]|Untriaged)\\s+(?:Frontend|Backend|Document...`
  - `FENCE` = `re_compile(pattern='^ {0,3}(`{3,}|~{3,})(.*)$')`
  - `HEADING` = `re_compile(pattern='^(#{1,6})\\s+(.+?)\\s*#*\\s*$')`
  - `ONGOING` = `re_compile(pattern='\\bONGOING\\b', flags=0)`
  - `PRIORITY` = `re_compile(pattern='\\bP([0-3])\\b')`
  - `TASK` = `re_compile(pattern='^\\*\\*([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\\d+)\\b')`
  - `CATEGORY` = `re_compile(pattern='(?P<frontend>□|\\*\\*Frontend\\*\\*)|(?P<backend>◆|\\...`
  - `CATEGORY_ORDER` = `('frontend', 'backend', 'documentation', 'testing', 'devops', 'uncategori...`
  - `CATEGORY_LABELS` = `{'frontend': 'Frontend', 'backend': 'Backend', 'documentation': 'Document...`
  - `WATCH_INTERVAL` = `0.5`
  - `HEARTBEAT_INTERVAL` = `2.0`
  - `HEARTBEAT_STALE` = `10.0`
  - `PID_SUFFIX` = `'.sync-todo.pid'`
  - `STAMP_FORMAT` = `'%d/%m/%Y %H:%M:%S'`
- `class Task` — One tagged checklist item.
  - Fields: `ident: str`, `priority: str`, `category: str`, `done: bool`
- `class Counts` — Store checkbox totals for one roadmap section.
  - `anchor` = `''`
  - `done` = `0`
  - `open` = `0`
  - `ongoing` = `0`
  - `tasks` = `field(default_factory=list)`
  - Fields: `title: str`, `level: int`
  - `total(self) -> int` — Return total checklist items.
- `visible_lines(text: str) -> Iterator[str]` — Yield lines outside fences, comments and the managed dashboard.
- `task_priority(label: str) -> str` — Read explicit header priority before legacy description annotations.
- `parse(text: str) -> tuple[list[Counts], dict[str, tuple[int, int]]]` — Count real checkboxes and priority annotations.
- `render_html(text: str) -> str` — Render the self-contained interactive TODO.html dashboard.
- `completion(text: str) -> float` — Return overall checkbox completion for one document.
- `atomic_write(path: Path, text: str) -> None` — Write `text` to `path` atomically via a sibling temp file.
- `update(text: str) -> str` — Insert or replace the managed dashboard idempotently.

### `examples/__init__.py`

Provide a runnable TODO synchronization example.


### `examples/__main__.py`

Run the todo-sync example with the project virtual environment.


### `examples/run.py`

Synchronize a throwaway copy of the bundled ``TODO.md`` example.

- `class Constants` — Group module-level constants.
  - `here` = `Path(__file__).resolve().parent`
  - `source` = `here / 'TODO.md'`
  - `scratch` = `here / '.scratch'`
- `main(*, scratch: Path | None=None) -> int` — Copy the example checklist and synchronize the copy.

### `normalize.py`

Normalize checklist headers without changing task states or obligations.

- `class Patterns` — Shared normalized task syntax and metadata detection.
  - `NORMAL` = `re_compile(pattern=''.join(_NORMAL_PARTS))`
  - `BOX` = `re_compile(pattern='^(\\s*)[-*+]\\s+\\[([xX ])\\]\\s+(.*)$')`
  - `BOLD` = `re_compile(pattern='^\\*\\*([^*]+)\\*\\*(.*)$')`
  - `PRIORITY` = `re_compile(pattern='\\bP[0-3]\\b')`
  - `META` = `re_compile(pattern=''.join(_META_PARTS))`
  - `START_PRIORITY` = `re_compile(pattern='^P[0-3]\\s*[·:—-]\\s*')`
  - `SEPARATOR` = `re_compile(pattern='^\\s*(?:—|---|--|-|:)\\s*')`
- `category(*, label: str, ident: str, fallback: str='Uncategorized') -> str` — Suggest a category without overriding an explicit source category.
- `class Constants` — Group module-level constants.
  - `category_rules` = `(('verify|qualify|tests?|testing|coverage|regressions?|lint|pyright|ruff'...`
  - `family_categories` = `{'W': 'Frontend', 'H': 'Frontend', 'S': 'Frontend', 'LT': 'Frontend', 'EV...`
- `identity(*, label: str, used: set[str], parent: str | None) -> str` — Retain IDs or allocate a collision-free root/child identifier.
- `priority_for(*, label: str, parent: str | None, headings: dict[int, str]) -> str` — Keep ambiguity explicit instead of assigning invented urgency.
- `description(*, label: str, ident: str) -> str` — Remove legacy header fields but retain description text and emphasis.
- `normalize(*, text: str) -> str` — Write uniform headers, preserving states, descriptions and existing IDs.

### `sync.py`

File synchronization with stable reads and atomic replacement.

- `synchronize(*, path: Path, check: bool=False, html: bool=True, normalize_tasks: bool=False) -> bool` — Update managed Markdown and sibling HTML; return whether either differs.

### `watch.py`

Exclusive, cooperative watchers: a persisted PID never authorizes a kill.

- `class Constants` — Watcher timing policy.
  - `STALE_SECONDS` = `10`
- `lock_path(*, path: Path) -> Path` — Return the atomic ownership directory associated with one source.
- `read_state(*, path: Path) -> dict[str, StateValue]` — Read diagnostic watcher state without trusting a stored PID.
- `running(*, path: Path) -> bool` — Require a fresh heartbeat, positive PID and matching source.
- `watch(*, path: Path, interval: float=0.5, html: bool=True) -> int` — Synchronize in the foreground until Ctrl-C or an owned stop request.
- `detached_child() -> int` — Run the fixed child entry point with environment-carried configuration.
- `start(*, path: Path, interval: float=0.5, html: bool=True) -> int` — Detach a watcher, waiting for its ready heartbeat or startup failure.
- `stop(*, path: Path) -> int` — Request token-matched shutdown; never signal a PID read from disk.

## Examples

Runnable demonstration for `exactus/packages/todo_sync/`.

Synchronize a throwaway copy of the bundled ``TODO.md`` example.

```bash
python -m exactus.packages.todo_sync.examples
```

Files: `examples/README.md`, `examples/TODO.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/assets/README.md`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md)
- Used by: `tests/packages/todo_sync/test_dashboard.py`, `tests/packages/todo_sync/test_default_path.py`, `tests/packages/todo_sync/test_examples.py`, `tests/packages/todo_sync/test_normalize.py`, `tests/packages/todo_sync/test_permissions.py`, `tests/packages/todo_sync/test_sync.py`, `tests/packages/todo_sync/test_watch.py`

## Tests

Tests live in `exactus/tests/packages/todo_sync/`.

- `test_dashboard.py` — Exercise the actual offline dashboard at desktop and mobile widths. (1 tests)
  - `test_dashboard_controls`
- `test_default_path.py` — The default CLI source and report live under ``exactus/docs/todo``. (1 tests)
  - `test_default_workspace`
- `test_examples.py` — Exercise the bundled ``todo_sync`` synchronization example. (1 tests)
  - `test_example_synchronizes_a_scratch_copy`
- `test_normalize.py` — Uniform headers preserve obligations and expose source metadata. (6 tests)
  - `test_canonical_queue_schema`
  - `test_crlf_and_unknown_priority`
  - `test_explicit_metadata_wins`
  - `test_headers_and_idempotence`
  - `test_normalization_cannot_be_silently_ignored`
  - `test_normalization_check_is_read_only`
- `test_permissions.py` — Preserve private Markdown permissions and keep new HTML owner-only. (1 tests)
  - `test_private_output`
- `test_sync.py` — Validate parsing, atomic output, CLI and safe watcher lifecycle. (14 tests)
  - `test_bad_intervals`
  - `test_check_and_html_repair`
  - `test_cli`
  - `test_concurrent_edit`
  - `test_duplicate_heading_anchor`
  - `test_excluded_examples_and_parent_rollup`
  - `test_html_escaping`
  - `test_identifiers`
  - `test_malformed_markers`
  - `test_preserve_outside_managed_block`
  - `test_real_watcher`
  - `test_stale_state`
  - `test_symlink_preflight`
  - `test_top_summary_updates_without_moving_detailed_tables`
- `test_watch.py` — Cover the exclusive todo_sync watcher lifecycle. (15 tests)
  - `test_detached_child_reads_environment_configuration`
  - `test_start_fails_when_the_child_exits_early`
  - `test_start_fails_when_the_heartbeat_never_arrives`
  - `test_start_rejects_a_nonpositive_interval`
  - `test_start_rejects_a_stale_lock`
  - `test_start_returns_once_the_child_publishes_a_heartbeat`
  - `test_start_returns_when_a_watcher_is_live`
  - `test_stop_fails_when_the_watcher_ignores_the_request`
  - `test_stop_rejects_a_stale_lock`
  - `test_stop_returns_when_no_lock_exists`
  - `test_stop_writes_the_token_and_returns_when_the_lock_closes`
  - `test_watch_exits_on_keyboard_interrupt`
  - `test_watch_exits_on_the_token_matched_stop_request`
  - `test_watch_records_stat_failures_and_recovers`
  - `test_watch_rejects_a_nonpositive_interval`

<!-- exactus:reference:end -->
