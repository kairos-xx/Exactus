# `exactus.packages.external/`

Bundled-toolchain surface behind `exactus --external`: with no tool
name it renders the leaf manifest's OS/Python/Node version inventory;
with `TOOL [ARGS...]` it forwards the command line to the offline
partition launcher.

```shell
exactus --external                          # grouped tool inventory
exactus --external ruff check --select ALL  # run bundled ruff
exactus --external basedpyright tests       # run bundled basedpyright
exactus --external list-tools               # launcher tool names
```

Unknown tools fail before dispatch with
`ERROR: no bundled tool named "<name>"`; launcher subcommands
(`list-tools`, `--verify`, `--verify-deep`, `--version`, `--help`)
pass through untouched.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Bundled-toolchain inventory and dispatch for ``exactus --external``.
- [`__main__.py`](__main__.py) — Execute the external bundled-tool command-line interface.
- [`cli.py`](cli.py) — List and dispatch the tools bundled inside an exactus executable.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
