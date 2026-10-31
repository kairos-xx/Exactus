# `exactus/tools/docs/`

Docs analyzes Python docstrings and JavaScript JSDoc. Its metrics describe analyzed source files, lines, symbols and documentation coverage. Markdown and README inventories and sizes are reported by readme.

The `docs` exactus tool: a standalone entry point (`main.py`) and its analysis
core (`core.py`), plus the report template (`templates/`). The
inventory below documents every direct file and child directory.

## Directory contents

### Files

#### `__init__.py`

Docs exactus tool.

#### `core.py`

Exactus Python docstrings and JavaScript JSDoc from one Python program. Public API: `empty_statistics()` — Return zeroed counters for every exactused language.; `empty_lines()` — Return a zeroed line counter for every exactused language.; `Text` — Pure text utilities shared by both analyzers.; `PythonAnalyzer` — Analyze Google-style Python documentation contracts.; `JavaScriptAnalyzer` — Analyze JSDoc using Python-only structural lexical recognition.; `report_data()` — Return the normalized JSON payload of one documentation exactus (`summary`, `scope`, `findings`, `extension` with `languages`, `rules` and `metrics`).; `DocumentationExactus` — Coordinate discovery, analysis, reporting, and exit status.; `parse_args()` — Parse command-line arguments.; `main()` — Run the documentation exactus.

#### `main.py`

Exactus Python docstrings and JavaScript JSDoc. Public API: `create_parser()` — Create parser.; `parse_args()` — Parse args.; `main()` — Return main.

### Directories

#### `templates/`

Report templates of the docs tool: `markdown/` holds the `result.md`
template and mapping.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Docs exactus tool.
- [`arguments.py`](arguments.py) — Declare the docs grammar without importing its execution engine.
- [`core.py`](core.py) — Exactus Python docstrings and JavaScript JSDoc from one Python program.
- [`main.py`](main.py) — Exactus Python docstrings and JavaScript JSDoc.

### Subdirectories

- [`templates/`](templates/README.md) — Report templates of the docs tool. The inventory below documents every direct child directory.

<!-- exactus:inventory:end -->


