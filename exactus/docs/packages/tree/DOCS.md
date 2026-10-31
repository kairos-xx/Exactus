# `exactus/packages/tree/` — TREE.txt-style listings

`exactus.packages.tree` renders directories, `.zip` archives and explicit path
lists as the same tree format `exactus/scripts/inventory` writes to
`TREE.txt`: `├──`/`└──` branches with aligned human-readable sizes and
`dd Mon yyyy HH:MM` dates; directories aggregate descendant size and
the latest descendant mtime.

## Running

```bash
python exactus/packages/tree exactus/packages/steps                  # a directory
python exactus/packages/tree packages_steps.zip              # a zip archive
python exactus/packages/tree 'exactus/packages/**/*.py'              # glob expansion
python exactus/packages/tree docs --include '*.md'         # whitelist members
python exactus/packages/tree docs --exclude '*/build/*'    # drop members
python exactus/packages/tree . -o TREE.txt                 # write to a file
```

Positional arguments may be directories, `.zip` files or glob
patterns (expanded with `Path.glob` semantics). `--include`/`-i` and
`--exclude`/`-e` are repeatable and match posix member labels via
`fnmatch`; an empty include list keeps everything. `-o/--output`
writes the listing to a file instead of stdout. With no resolvable
source the CLI prints usage and returns `1`.

## Python API

```python
from exactus.packages.tree import render_tree, members_for, human_size

render_tree(source=Path("exactus/packages/steps"))
render_tree(source=Path("packages_steps.zip"))
render_tree(
    source=["exactus/packages/steps/core.py", Path("pyproject.toml")],
    root=Path.cwd(),          # stats + label relativization
    name="bundle",            # root row label
    include=(), exclude=(),   # fnmatch globs on member labels
)
```

- `render_tree(source=, include=, exclude=, name=, root=) -> str` —
  the listing text.
- `members_for(source=, root=) -> dict[str, tuple[int, float]]` —
  `label -> (size, mtime)` resolution shared with `render_tree`.
- `human_size(size=) -> str` — `512B`/`23KB`/`4.6MB` formatting.
- `main(arguments=None) -> int` — the CLI entry point.

`str` members keep their labels verbatim and are stat'ed under
`root`; `Path` members are stat'ed directly and relativized when
possible. Members that don't exist render with `0B` and the epoch
date. Zip `date_time` stamps are treated as UTC.

## Layout

```
exactus/packages/tree/
├── core.py            # rendering, member collection, CLI
├── __main__.py        # venv bootstrap → python exactus/packages/tree
└── examples/          # python -m exactus.packages.tree.examples
```

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Public API for ``TREE.txt``-style listings. |
| `__main__.py` | Run ``exactus.packages.tree`` through the project's virtualenv. |
| `core.py` | Render directories, zip archives and path lists as ``TREE.txt`` text. |
| `examples/` | Runnable demonstration for `exactus/packages/tree/`. |

Run it as a module: `python -m exactus.packages.tree`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `sources` | Directories, .zip archives or glob patterns. | nargs='*', metavar='PATH' |
| `--include, -i` | Keep only member paths matching this glob (repeatable). | dest='include', action='append', metavar='GLOB' |
| `--exclude, -e` | Drop member paths matching this glob (repeatable). | dest='exclude', action='append', metavar='GLOB' |
| `--output, -o` | Write the listing to FILE instead of stdout. | dest='output', type=Path, default=None, metavar='FILE' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Public API for ``TREE.txt``-style listings.


### `__main__.py`

Run ``exactus.packages.tree`` through the project's virtualenv.


### `core.py`

Render directories, zip archives and path lists as ``TREE.txt`` text.

- `class Constants` — Group module-level constants.
  - `skipped_names` = `frozenset({'.DS_Store'})`
  - `skipped_directories` = `frozenset({'__pycache__'})`
  - `magic` = `frozenset('*?[')`
- `human_size(*, size: int) -> str` — Format a byte count compactly, e.g. ``512B``/``23KB``/``4.6MB``.
- `members_for(*, source: Path | Sequence[str | Path] | Members, root: Path | None=None) -> dict[str, tuple[int, float] | None]` — Resolve any supported source into member entries.
- `render_tree(*, source: Path | Sequence[str | Path] | Members, include: Sequence[str]=(), exclude: Sequence[str]=(), name: str | None=None, root: Path | None=None) -> str` — Render ``source`` as a ``TREE.txt``-style listing.
- `main(*, arguments: Sequence[str] | None=None) -> int` — Render trees for directories, zips and glob expansions.

### `examples/__init__.py`

Runnable examples for ``exactus.packages.tree``.


### `examples/__main__.py`

Run the tree package example through the project virtualenv.


### `examples/run.py`

Render a small temporary tree and a zip member listing.

- `main() -> int` — Render one directory tree and one zip member listing.

## Examples

Runnable demonstration for `exactus/packages/tree/`.

Render a small temporary tree and a zip member listing.

```bash
python -m exactus.packages.tree.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md), [`steps`](../steps/DOCS.md)
- Used by: `packages/all_lints/core.py`, `packages/package/inventory.py`, `packages/zip_components/core.py`, `tests/packages/tree/test_tree.py`, `tools/common/collect_files.py`

## Tests

Tests live in `exactus/tests/packages/tree/`.

- `test_example_run.py` — Cover the bundled ``tree`` example entry point. (1 tests)
  - `test_example_module_runs_as_a_script`
- `test_tree.py` — Tests for TREE.txt-style directory and archive listings. (9 tests)
  - `test_human_size_scales_units`
  - `test_main_renders_sources_and_writes_output`
  - `test_main_usage_without_sources`
  - `test_members_for_single_file`
  - `test_render_tree_accepts_member_lists`
  - `test_render_tree_include_exclude_globs`
  - `test_render_tree_lists_directory_recursively`
  - `test_render_tree_lists_zip_members`
  - `test_render_tree_marks_missing_members`

<!-- exactus:reference:end -->
