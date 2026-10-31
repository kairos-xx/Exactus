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
| `examples/` | `run.py` demonstrates the synchronizer end to end without risking a real checklist: it copies `TODO.md` into the git-ignored `.scratch/` folder and runs `synchronize` against the copy, which rewrites the managed dashboard |
| `normalize.py` | Normalize checklist headers without changing task states or obligations. |
| `sync.py` | File synchronization with stable reads and atomic replacement. |
| `watch.py` | Exclusive, cooperative watchers: a persisted PID never authorizes a kill. |
| `web/` | Contain web resources and their directory inventory. |

Run it as a module: `python -m exactus.packages.todo_sync`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--path` |  | default=Path('exactus/docs/todo/TODO.md'), type=Path |
| `--check` |  | action='store_true' |
| `--watch-stop` |  | action='store_true' |
| `--watch-status` |  | action='store_true' |
| `--no-html` | Only synchronize Markdown. | action='store_true' |
| `--interval` |  | default=0.5, type=float |
| `--normalize` | Normalize task headers once; combine with --check to audit. | action='store_true' |
| `--watch` |  | action='store_true' |
| `--watch-child` |  | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `cli.py`

Command-line entry point for the reusable TODO synchronizer.

- `class ModeGroup(Protocol)` — Public structural interface for mutually exclusive CLI switches.
  - `add_argument(: Self, *name_or_flags: str, action: str) -> Action` — Register a mutually exclusive command-line switch.
- `class Args(Namespace)` — Concrete command-line types shared with argparse.
- `main(argv: Sequence[str] | None=None) -> int` — Run one-shot synchronization, freshness checking or watcher control.

### `core.py`

Synchronize the managed progress dashboard in TODO.md.

- `class SyncTodoDefaults` — Immutable scalar configuration values.
  - Fields: `start: str`, `end: str`, `summary_start: str`, `summary_end: str`
- `class SyncTodoTables` — Shared lookup tables and compiled values.
- `class Task` — One tagged checklist item.
  - Fields: `ident: str`, `priority: str`, `category: str`, `done: bool`
- `class Counts` — Store checkbox totals for one roadmap section.
  - Fields: `title: str`, `level: int`, `anchor: str`, `done: int`, `open: int`, `ongoing: int`, `tasks: list[Task]`
  - `total() -> int` — Return total checklist items.
- `visible_lines(text: str) -> Iterator[str]` — Yield lines outside fences, comments and the managed dashboard.
- `task_priority(label: str) -> str` — Read explicit header priority before legacy description annotations.
- `parse(text: str) -> tuple[list[Counts], dict[str, tuple[int, int]]]` — Count real checkboxes and priority annotations.
- `render_html(text: str) -> str` — Render the self-contained interactive TODO.html dashboard.
- `completion(text: str) -> float` — Return overall checkbox completion for one document.
- `atomic_write(path: Path, text: str) -> None` — Write `text` to `path` atomically via a sibling temp file.
- `update(text: str) -> str` — Insert or replace the managed dashboard idempotently.

### `normalize.py`

Normalize checklist headers without changing task states or obligations.

- `class Patterns` — Shared normalized task syntax and metadata detection.
- `category(*, label: str, ident: str, fallback: str='Uncategorized') -> str` — Suggest a category without overriding an explicit source category.
- `class Constants` — Group module-level constants.
  - `category_rules` = `(('verify|qualify|tests?|testing|coverage|regressions?|lint|pyright...`
  - `family_categories` = `{'W': 'Frontend', 'H': 'Frontend', 'S': 'Frontend', 'LT': 'Frontend...`
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

## Stylesheets

- `web/dashboard.css` — (1097 custom properties)

## Examples

`run.py` demonstrates the synchronizer end to end without risking a real
checklist: it copies `TODO.md` into the git-ignored `.scratch/` folder and
runs `synchronize` against the copy, which rewrites the managed dashboard
block and emits the standalone `TODO.html` dashboard beside it. The
bundled source stays pristine, so the demo can be re-run any number of
times.

```bash
python exactus/packages/todo_sync/examples
```

Files: `.scratch/TODO.html`, `.scratch/TODO.md`, `TODO.md`, `__init__.py`, `__main__.py`, `run.py`

## Dependencies and consumers

- No dependencies outside the standard library.
- Used by: `../pyproject.toml`

## Tests

Tests live in `exactus/tests/packages/todo_sync/`.

- `dashboard.test.mjs` — Exercise the real checklist dashboard and retain browser V8 coverage. (1 tests)
  - dashboard controls and saved state at ${width}px
- `test_dashboard.py` — Exercise the actual offline dashboard at desktop and mobile widths. (1 tests)
  - `test_dashboard_controls`
- `test_default_path.py` — The default CLI source and report live under ``exactus/docs/todo``. (1 tests)
  - `test_default_workspace`
- `test_examples.py` — Exercise the bundled ``todo_sync`` synchronization example. (1 tests)
  - `test_example_synchronizes_a_scratch_copy`
- `test_normalize.py` — Uniform headers preserve obligations and expose source metadata. (6 tests)
  - `test_canonical_queue_schema`
  - `test_headers_and_idempotence`
  - `test_explicit_metadata_wins`
  - `test_crlf_and_unknown_priority`
  - `test_normalization_check_is_read_only`
  - `test_normalization_cannot_be_silently_ignored`
- `test_permissions.py` — Preserve private Markdown permissions and keep new HTML owner-only. (1 tests)
  - `test_private_output`
- `test_sync.py` — Validate parsing, atomic output, CLI and safe watcher lifecycle. (14 tests)
  - `test_excluded_examples_and_parent_rollup`
  - `test_identifiers`
  - `test_malformed_markers`
  - `test_preserve_outside_managed_block`
  - `test_top_summary_updates_without_moving_detailed_tables`
  - `test_duplicate_heading_anchor`
  - `test_html_escaping`
  - `test_check_and_html_repair`
  - `test_concurrent_edit`
  - `test_symlink_preflight`
  - `test_cli`
  - `test_bad_intervals`
  - `test_stale_state`
  - `test_real_watcher`
- `test_watch.py` — Cover the exclusive todo_sync watcher lifecycle. (15 tests)
  - `test_watch_exits_on_the_token_matched_stop_request`
  - `test_watch_exits_on_keyboard_interrupt`
  - `test_watch_records_stat_failures_and_recovers`
  - `test_watch_rejects_a_nonpositive_interval`
  - `test_detached_child_reads_environment_configuration`
  - `test_start_rejects_a_nonpositive_interval`
  - `test_start_returns_when_a_watcher_is_live`
  - `test_start_rejects_a_stale_lock`
  - `test_start_returns_once_the_child_publishes_a_heartbeat`
  - `test_start_fails_when_the_child_exits_early`
  - `test_start_fails_when_the_heartbeat_never_arrives`
  - `test_stop_returns_when_no_lock_exists`
  - `test_stop_rejects_a_stale_lock`
  - `test_stop_writes_the_token_and_returns_when_the_lock_closes`
  - `test_stop_fails_when_the_watcher_ignores_the_request`

<!-- exactus:reference:end -->
