# watch examples

These examples assume `exactus/packages/watch/` is installed inside the project.

## Project configuration

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

## Programmatic use

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

## macOS autostart

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

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Runnable examples for the folder watcher package.
- [`__main__.py`](__main__.py) — Run the watch example with the project virtual environment.
- [`run.py`](run.py) — Run the folder watcher directly from Python code.

### Subdirectories

- [`assets/`](assets/README.md) — Provide pyproject basic toml content.
- [`project/`](project/README.md) — Tiny watched-source fixture for the `run.py` example: running the example watches this tree and continuously copies it to `../results/project-watch-copy` and `../results/project-mirror`. Edit any file here while the example runs to see both destinations update — deleting a file removes it only from `project-mirror`.
- [`results/`](results/README.md) — Tiny watched-source fixture for the `run.py` example: running the example watches this tree and continuously copies it to `project-watch-copy` and `project-mirror`. Edit any file here while the example runs to see both destinations update — deleting a file removes it only from `project-mirror`.

<!-- exactus:inventory:end -->
