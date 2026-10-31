# `exactus/tools/lints/templates/markdown/`

Markdown report template of the lints tool. The stamp stage of
`exactus/tools/common/execution.py` renders `result.md` from the normalized
`result.json` with these files. The inventory below documents every
direct file.

## Directory contents

### Files

#### `template.md`

Extends the common `result_template.md`. Overrides `tool_findings`: the
findings are grouped by linter (`### <linter> — N findings`, report
order) and ordered by path and line; each one shows its id and title,
severity, rule, `path:line:column`, a Blocking mark, the full message
when it says more than the title (a text fence when multi-line) and the
numbered source excerpt. Overrides `tool_extension` with
`## Rules` lists engineering rules and rules reported by the other linters,
including zero findings for the engineering checks. `## Lint metrics` contains an overview table, `### Linters` (status, version,
files, findings by severity, exit code, duration; `N/A` when unknown),
`### Top rules` and `### Files with the most findings` (`N/A` with a
reason when empty; `N/A — the tool reported no metrics.` for a crash).

#### `mapping.json`

Tool mapping merged over the common base mapping (tool keys win): the
severity table uses the lint levels (`error`, `warning`, `information`),
`findings` keeps the report's linter-then-path order, `source_label`
(`Linter`) names the web findings filter by `source`, and
`extension.metrics` is projected into `lint_overview` (metric/value
rows), `linters`, `top_rules` and `top_files` with explicit column
order.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`mapping.json`](mapping.json) — Provide mapping json content.
- [`template.md`](template.md) — {% extends "result_template.md" %} {% from "partials/macros.md" import cell %} {% block tool_findings %} {% if findings is none %} N/A — the tool reported no findings list.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


