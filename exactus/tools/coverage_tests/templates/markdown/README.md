# `exactus/tools/coverage_tests/templates/markdown/`

Markdown template of the coverage-tests root report
(`COVERAGE_TESTS/result.md`). The stamp stage of
`exactus/tools/common/execution.py` renders it from the normalized
`result.json`. The `COVERAGE/` and `TESTS/` sub-reports are not rendered
from it. The inventory below documents every direct file.

## Directory contents

### Files

#### `template.md`

Extends the common `result_template.md`. Overrides `tool_summary`: a
lead sentence (tests run, test files, Python coverage against its
minimum, findings), the severity counts, `### Tests` (outcome counts,
duration, test files, shards, JavaScript files and failures) and
`### Coverage` (per-language totals and one row per configured coverage
gate with its required and measured value and status). Overrides `scope` to
show every skipped target's Meaningful level, category, status, and test
requirement. Overrides `gate`:
the global gate and reason, then a Part/Status/Reason table for
`gate.parts.tests` and `gate.parts.coverage`, then the blocking
findings. Overrides `tool_findings`: `### Failed tests — N` and
`### Coverage violations — N`, each finding with its id, title,
severity, rule, `path:line`, the reason, the shard log and the numbered
source excerpt. Overrides `tool_extension` with `## Test groups` (one
row per group linking to `TESTS/<group>/result.md`),
`## Files below the per-file minimum` and `## Sub-reports`. Every block
states its empty state, and a crash result renders `N/A`.

#### `mapping.json`

Tool mapping merged over the common base mapping (tool keys win):
`findings` keeps the report order (failed tests, then coverage
violations), `source_label` (`Gate`) names the web findings filter
(`Tests`/`Coverage`), and `extension` is projected into
`tests_summary` (metric/value rows), `test_groups` (rows carrying their
`report` directory, which the web report links), `coverage_summary`,
`coverage_gates`, `files_below_minimum` (rows carrying their `finding`
id) and `sub_reports`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`mapping.json`](mapping.json) — Provide mapping json content.
- [`template.md`](template.md) — {% extends "result_template.md" %} {% from "partials/macros.md" import cell %} {% macro report_link(row) %}{% if row.get("report") %}\[{{ row.report }}/result.md\]({{ row.report }}/result.md){% else %}N/A{% endif %}{% endmacro %} {% block tool_summary %} {% if summary %} {% set tests = summary.tests or {} %} **Result: {{ run.status }}** — {{ tests.get("total", 0) }} {{ "test" if tests.get("total", 0) == 1 else "tests" }} from {{ tests.get("files", 0) }} test {{ "file" if tests.get("files", 0) == 1 else "files" }} across {{ summary.targets_analyzed }} measured source {{ "file" if summary.targets_analyzed == 1 else "files" }}; Python coverage {% if summary.coverage_percent is none %}N/A{% else %}{{ "%.1f" | format(summary.coverage_percent) }}%{% endif %}{% if summary.coverage_required is not none %} (minimum {{ "%.1f" | format(summary.coverage_required) }}%){% endif %}; {{ summary.findings_total }} {{ "finding" if summary.findings_total == 1 else "findings" }}.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


