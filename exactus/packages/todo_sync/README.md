# TODO synchronization

Adapted from the supplied `sync_todo.py`: a reusable, standard-library-only package
with no dependency on `vm_image_manager`, Exactus runtime, npm, or the network.
It never infers completion or changes checkboxes.

Normalized task headers use `**ID** **Priority** **Category** — Description`.
Run `--normalize` once to migrate legacy headers, or `--normalize --check` for
a read-only audit. Existing IDs, states and detail text are preserved; missing
IDs are allocated without collisions. Missing priorities remain `Untriaged`.
Category suggestions are written explicitly for review; already-normalized
headers are never reclassified. Definitions live in the source Markdown.
Normalization is one-shot only; the watcher reads explicit fields. Legacy
category glyphs remain supported for other documents.

Runtime: Python 3.13 or newer, matching this repository. Importing the package
requires no installed Exactus dependencies. Permission guarantees refer to POSIX
file modes; Windows ACL/detachment qualification remains tracked in `exactus/docs/todo/TODO.md`.

## Run

From the repository root:

```sh
python -m exactus.packages.todo_sync --path exactus/docs/todo/TODO.md
python -m exactus.packages.todo_sync --path exactus/docs/todo/TODO.md --check
python exactus/packages/todo_sync --path exactus/docs/todo/TODO.md --no-html
```

The first command updates the managed Markdown block and writes `exactus/docs/todo/TODO.html`.
Other basenames work: `Roadmap.md` produces `Roadmap.html`. Existing content outside
the marker pair is retained. Without markers, the dashboard is inserted after the
document title, or at the start. Documents with no tasks get no Markdown dashboard.
Missing, duplicated or reversed marker pairs fail closed.

`--check` is read-only and checks **both** outputs by default. Exit codes: `0`
current/success, `1` stale or watcher not running, `2` invalid arguments/I/O.
`--no-html` checks/synchronizes Markdown alone. Atomic replacements prevent torn
files; unchanged files retain their modification times. Markdown and HTML are
separate replacements, not one transaction; rerun after an interrupted second write.
Existing permissions are preserved; newly generated files are owner-only.

## API

```python
from pathlib import Path
from exactus.packages.todo_sync import (
    completion,
    parse,
    render_html,
    synchronize,
    update,
)

text = "# Plan\n- [ ] **R01 — Implement** P0\n"
updated = update(text=text)
sections, priorities = parse(text=text)
percent = completion(text=text)
html = render_html(text=updated)
changed = synchronize(path=Path("exactus/docs/todo/TODO.md"), check=True)
```

## Counting contract

- `-`, `*`, and `+` checkbox items count; `x` and `X` mean complete.
- Fenced examples, HTML comments and the managed block never count.
- Each checkbox has equal weight, including parent and child items. Progress is
  **not** release readiness, estimated effort or elapsed time. The checklist and
  acceptance evidence remain authoritative.
- ATX headings own tasks; workstream totals include descendant headings.
- `P0`–`P3` classify priority. Normalization makes missing priorities explicit
  as `Untriaged`; the Markdown matrix shows an Untriaged column.
- Bold IDs include `DIS-001`, `R01`, `H21`, `PQ06`, and `UI-O03`.
- Explicit bold labels: `Frontend`, `Backend`, `Documentation`, `Testing / QA`,
  `DevOps / Release`, `Uncategorized`. Legacy glyphs remain accepted: `□`, `◆`,
  `¶`, `✓`, `▲` respectively. Unmarked tasks are not assumed backend.
- `ONGOING` identifies ongoing work; unchecked ongoing tasks remain open.
- This is a checklist parser, not complete CommonMark: ATX headings and fenced
  blocks are supported; indented code is not treated as fence syntax.

## Offline dashboard

The supplied stylesheet and static shell remain readable assets; the compressed
base64 blob is gone. Direct DOM construction replaces runtime HTML-string parsing.
Task labels and source text never execute as HTML.

Styles and behavior are maintained in `web/dashboard.css` and `web/dashboard.js`.
The HTML template references these assets; generation embeds them as data URLs
so the resulting dashboard remains a single offline file without inline
executable script or style blocks in the source template.

Search uses exact-token/subsequence matching; all query tokens must match. Filters
compose across status, category, priority, workstream, ID prefix and ongoing state.
Grouping, sorting, light/dark mode, filtered JSON export, source-line links, mobile
filters and URL-fragment restoration require no server.

Intentional adaptations: Source displays the complete Markdown verbatim, including
code/comments/evidence, instead of attempting full Markdown rendering; workstream
filters are flat, rather than the original expandable tree; fuzzy search uses
deterministic subsequences instead of the original ranking engine. Reset clears
all filters. All tasks show initially, including completed tasks. No edits write
back from HTML, and the page does not poll the watcher: regenerate and reload.

## Watch

```sh
python -m exactus.packages.todo_sync --path exactus/docs/todo/TODO.md --watch
python -m exactus.packages.todo_sync --path exactus/docs/todo/TODO.md --watch-status
python -m exactus.packages.todo_sync --path exactus/docs/todo/TODO.md --watch-stop
python -m exactus.packages.todo_sync --path exactus/docs/todo/TODO.md --watch-child --interval 0.5
```

Importing or synchronizing never starts a watcher. `--watch` explicitly detaches
one; `--watch-child` runs foreground until Ctrl-C. Intervals must be finite and
positive. An exclusive `.TODO.md.todo-sync/` directory contains `state.json`:
PID (diagnostic only), canonical path, ownership token, heartbeat, last update,
completion, percentage-point delta, and last error. A token-matched stop request
ends the loop. **A PID read from disk is never signaled.** Startup waits for
readiness; retained logs live in `.TODO.md.todo-sync.log`.

Stale/malformed locks prevent another watcher. Inspect state/log and confirm the
actual owner exited before manually removing ownership files and the empty lock
directory. Never remove an active lock. A forcibly killed process may leave a lock;
this safety trade-off avoids terminating an unrelated PID. Heartbeats indicate
liveness, not cryptographic identity.

Stable reads detect edits during rendering but cannot guarantee compare-and-swap
against arbitrary external editors between the final check and rename. Use one
watcher and coordinate other formatters.

## Ownership and tests

- `core.py`: parsing, totals, marker replacement and embedded dashboard data.
- `sync.py`: read/check/write orchestration and concurrent-edit preflight.
- `watch.py`: exclusive ownership, readiness, heartbeat and cooperative stop.
- `cli.py`, `__main__.py`, `__init__.py`: CLI and public API boundaries.
- `web/dashboard.html`, `web/dashboard.css`, `web/dashboard.js`: readable
  assets included in wheels. Generated HTML embeds its styles/scripts as
  data URLs for offline use.
- `exactus/tests/packages/todo_sync/test_sync.py`: parser, output, CLI and real watcher tests.

```sh
python -m pytest exactus/tests/packages/todo_sync -q
python -m ruff check exactus/packages/todo_sync exactus/tests/packages/todo_sync
basedpyright exactus/packages/todo_sync exactus/tests/packages/todo_sync
```

For a safe demo, copy `examples/TODO.md` to a temporary directory and run the
CLI against that copy. No background watcher is started by the example.

Local checks do not imply public HTTPS visual-review approval. Do not publish
private TODO content merely to obtain a dashboard-review receipt.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Dependency-free Markdown checklist dashboards and synchronization.
- [`__main__.py`](__main__.py) — Execute the todo_sync package as a module or directory.
- [`cli.py`](cli.py) — Command-line entry point for the reusable TODO synchronizer.
- [`core.py`](core.py) — Synchronize the managed progress dashboard in TODO.md.
- [`normalize.py`](normalize.py) — Normalize checklist headers without changing task states or obligations.
- [`sync.py`](sync.py) — File synchronization with stable reads and atomic replacement.
- [`watch.py`](watch.py) — Exclusive, cooperative watchers: a persisted PID never authorizes a kill.

### Subdirectories

- [`examples/`](examples/README.md) — `run.py` demonstrates the synchronizer end to end without risking a real checklist: it copies `TODO.md` into the git-ignored `.scratch/` folder and runs `synchronize` against the copy, which rewrites the managed dashboard block and emits the standalone `TODO.html` dashboard beside it. The bundled source stays pristine, so the demo can be re-run any number of times.
- [`web/`](web/README.md) — Contain web resources and their directory inventory.

<!-- exactus:inventory:end -->
