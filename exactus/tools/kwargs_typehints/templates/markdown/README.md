# `exactus/tools/kwargs_typehints/templates/markdown/`

Markdown report template of the kwargs-typehints tool. The stamp stage
of `exactus/tools/common/execution.py` renders `result.md` from the normalized
`result.json` with these files. The inventory below documents every
direct file.

## Directory contents

### Files

#### `template.md`

Extends the common `result_template.md`. Overrides `tool_summary`: after
the common totals, `### Metrics` (files, call sites and how they
resolved, functions and parameters checked, signature hint coverage,
blocking findings) and `#### Findings by category` (every category with
its severity, whether it blocks and its count). Overrides
`tool_findings`: findings grouped by category, blocking categories
first (`### <category> — N findings`), each with its id and title,
severity, rule, `path:line:column`, a Blocking mark, the message and
the numbered source excerpt. Overrides `tool_extension` with
`## Unresolved callees` (callee, path, line, reason, call sites of the
callee, finding id), `## Ambiguous call sites`, `## Bare imports` and
`## Methodology and caveats`; every table states its empty state, and a
crash result renders `N/A`.

#### `mapping.json`

Tool mapping merged over the common base mapping (tool keys win):
`findings` keeps the report's category-then-path order, `source_label`
(`Category`) names the web findings filter, `extension.metrics` is
projected into `metrics` (metric/value rows) and `findings_by_category`,
and `extension` into `unresolved_callees`, `ambiguous_call_sites`,
`bare_imports` (rows carrying their `finding` id, which the web report
links to the finding and its snippet) and `methodology_and_caveats`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`mapping.json`](mapping.json) — Provide mapping json content.
- [`template.md`](template.md) — {% extends "result_template.md" %} {% from "partials/macros.md" import cell %} {% macro code(row, key) %}{% if row.get(key) is none %}N/A{% else %}{{ row.get(key) | md_code | md_cell }}{% endif %}{% endmacro %} {% block tool_summary %} {{ super() }} ### Metrics

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


