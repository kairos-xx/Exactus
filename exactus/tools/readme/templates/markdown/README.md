# `exactus/tools/readme/templates/markdown/`

Markdown report template of the readme tool. The stamp stage of
`exactus/tools/common/execution.py` renders `result.md` from the normalized
`result.json` with these files. The inventory below documents every
direct file.

## Directory contents

### Files

#### `template.md`

Extends the common `result_template.md` and overrides the
`tool_extension` block with a `## Directory inventory` table (one row
per exactused directory) and a `## Rules` table (rule, title, finding
count; `N/A` when the tool reported none).

#### `mapping.json`

Tool mapping merged over the common base mapping (tool keys win):
limits the severity table to `error`, projects `extension.directories` into the `inventory` table rows (directory, README present/missing, README bytes, entries, documented, missing) and exposes `extension.rules` as `rules`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`mapping.json`](mapping.json) — Provide mapping json content.
- [`template.md`](template.md) — {% extends "result_template.md" %} {% from "partials/macros.md" import bullets %} {% block tool_extension %}

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->



README owns the Markdown totals, README size extremes and directories without
a README projected from `extension.metrics`. Docs reports only docstrings
and JSDoc.
