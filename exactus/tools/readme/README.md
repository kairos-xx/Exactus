# `exactus/tools/readme/`

README reports own Markdown file, byte and line totals, README counts and largest/smallest sizes, and source directories without a README. These metrics follow the README include/exclude rules.

The `readme` exactus tool: a standalone entry point (`main.py`) and its analysis
core (`core.py`), plus the report template (`templates/`). The
inventory below documents every direct file and child directory.

## Directory contents

### Files

#### `__init__.py`

Readme exactus tool.

#### `core.py`

Exactus per-directory README documentation inventories. Public API: `ReadmeFinding` — One documentation-inventory violation.; `ReadmeExactusInput` — Carry the inputs of one README exactus run.; `ReadmeDirectory` — Inventory outcome of one exactused directory.; `ReadmeSkip` — One directory found under the root but not exactused.; `ReadmeExactusResult` — Aggregate the README exactus outcome.; `skipped()` — Return whether a directory entry is excluded from inventories.; `readme()` — Exactus every documented directory's README inventory.; `report_data()` — Build the normalized JSON report payload (`summary`, `scope`, `findings`, `extension`).

#### `main.py`

Exactus per-directory README documentation inventories. Public API: `create_parser()` — Create parser.; `parse_args()` — Parse args.; `main()` — Return main.

### Directories

#### `templates/`

Report templates of the readme tool: `markdown/` holds the `result.md`
template and mapping.

## Automatic inventory healing

Run `exec/exactus --readme` to refresh the managed `Directory contents` section.
Every eligible directory is processed from the deepest child to the project
root. File summaries come from Python module docstrings or JavaScript/CSS
JSDoc comments; folder summaries come from the introduction in the child
README. Missing descriptions use a filename-based fallback. The managed
section contains relative links, separate file and subdirectory lists, and
one summary per entry. Repairs preserve authored prose outside the inventory
markers and avoid rewriting unchanged files.

The default `python exactus --readme` run repairs inventories. Complete legacy
`audit:inventory` blocks and duplicate `exactus:inventory` blocks are consolidated
into one current inventory, removing generated references to deleted or renamed
entries. Authored text outside those markers is preserved; `--dry` checks without
writing repairs.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Readme exactus tool.
- [`arguments.py`](arguments.py) — Declare the readme grammar without importing its execution engine.
- [`core.py`](core.py) — Exactus per-directory README documentation inventories.
- [`main.py`](main.py) — Exactus per-directory README documentation inventories.
- [`metrics.py`](metrics.py) — Measure Markdown files and README sizes for the README report.

### Subdirectories

- [`templates/`](templates/README.md) — Report templates of the readme tool. The inventory below documents every direct child directory.

<!-- exactus:inventory:end -->
