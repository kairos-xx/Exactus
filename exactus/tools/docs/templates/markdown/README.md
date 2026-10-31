# `exactus/tools/docs/templates/markdown/`

Markdown report template of the docs tool. The stamp stage of
`exactus/tools/common/execution.py` renders `result.md` from the normalized
`result.json` with these files. The inventory below documents every
direct file.

## Directory contents

### Files

#### `template.md`

Extends the common `result_template.md` and overrides the
`tool_extension` block with `## Documentation statistics` (per-language
files, parsed, failed, symbols, documented, coverage, findings),
`## Rules` and `## Suggested documentation` (signature, reason and the
suggested docstring of every finding), plus `## Analyzed code` (files and lines per language) from `extension.metrics`.

#### `mapping.json`

Tool mapping merged over the common base mapping (tool keys win):
projects `extension.languages` into the `languages` statistics rows (adding `N/A` coverage when a language has no symbols) exposes `extension.rules` as `rules` and projects `extension.metrics.languages` into `analyzed_code` with explicit column order.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`mapping.json`](mapping.json) — Provide mapping json content.
- [`template.md`](template.md) — {% extends "result_template.md" %} {% block tool_extension %}

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


