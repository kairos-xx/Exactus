[Home](Home.md) > [Packages](Packages.md) > tree

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/tree/`](../exactus/packages/tree/) | [`exactus/tests/packages/tree/`](../exactus/tests/packages/tree/) | [`DOCS.md`](../exactus/docs/packages/tree/DOCS.md) |

[< Packages-todo_sync](Packages-todo_sync.md) · [Packages index](Packages.md) · [Packages-visual_cause >](Packages-visual_cause.md)
