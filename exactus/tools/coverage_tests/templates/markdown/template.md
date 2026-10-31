{% extends "result_template.md" %}
{% from "partials/macros.md" import cell %}
{% macro report_link(row) %}{% if row.get("report") %}[{{ row.report }}/result.md]({{ row.report }}/result.md){% else %}N/A{% endif %}{% endmacro %}
{% block tool_summary %}
{% if summary %}
{% set tests = summary.tests or {} %}
**Result: {{ run.status }}** — {{ tests.get("total", 0) }} {{ "test" if tests.get("total", 0) == 1 else "tests" }} from {{ tests.get("files", 0) }} test {{ "file" if tests.get("files", 0) == 1 else "files" }} across {{ summary.targets_analyzed }} measured source {{ "file" if summary.targets_analyzed == 1 else "files" }}; Python coverage {% if summary.coverage_percent is none %}N/A{% else %}{{ "%.1f" | format(summary.coverage_percent) }}%{% endif %}{% if summary.coverage_required is not none %} (minimum {{ "%.1f" | format(summary.coverage_required) }}%){% endif %}; {{ summary.findings_total }} {{ "finding" if summary.findings_total == 1 else "findings" }}.

| Severity | Count |
|---|---:|
{% for level in severity_levels %}
| {{ level | upper }} | {{ (summary.severity or {}).get(level, 0) }} |
{% endfor %}
{% else %}
**Result: {{ run.status }}** — N/A — the tool reported no summary.
{% endif %}

### Tests

{% if tests_summary %}
{{ tests_summary | md_table("Metric:metric", "Value:value") }}
{% else %}
N/A — the tool reported no test summary.
{% endif %}

### Coverage

{% if coverage_summary %}
| Language | Coverage | Measurement | Files |
|---|---:|---|---:|
{% for row in coverage_summary %}
| {{ cell(row, "language") }} | {% if row.percent is none %}N/A{% else %}{{ cell(row, "percent") }}%{% endif %} | {{ row.get("basis") or ("Lines + branches" if row.get("lines") and row.get("covered") is not none and row.get("percent") is not none and ((row.percent - row.covered * 100 / row.lines) | abs) > 0.01 else "Lines") }} | {{ cell(row, "files") }} |
{% endfor %}

The Python gate includes branches when branch measurement is enabled. JavaScript measures executable lines.
{% else %}
N/A — the tool reported no coverage summary.
{% endif %}
{% endblock %}
{% block scope %}{% endblock %}
{% block gate %}
## Gate

> **Gate: {{ gate.status }}** — {{ gate.reason }}
{% if run.error is defined and run.error %}

The tool raised an error:

~~~~text
{{ run.error }}
~~~~
{% endif %}

{% if gate.get("parts") %}
| Part | Status | Reason |
|---|---|---|
{% for name in ["tests", "coverage"] %}
{% if gate.parts.get(name) %}
| {{ gate.parts[name].get("label") or name }} | {{ cell(gate.parts[name], "status") }} | {{ cell(gate.parts[name], "reason") }} |
{% endif %}
{% endfor %}
{% else %}
N/A — the tool reported no part gates.
{% endif %}

{% if coverage_gates %}
### Coverage requirements

{{ coverage_gates | md_table("Requirement:gate", "Minimum:required", "Measured:measured", "Result:status") }}
{% endif %}
{% if files_below_minimum %}

### Files below the minimum

| File | Coverage | Minimum | Shortfall |
|---|---:|---:|---:|
{% for row in files_below_minimum %}
| {{ cell(row, "path") }} | {{ "%.2f" | format(row.percent) }}% | {{ "%.2f" | format(row.required) }}% | {{ "%.2f" | format(row.required - row.percent) }} percentage points |
{% endfor %}
{% endif %}
{% endblock %}
{% block tool_findings %}
{% if findings is none %}
N/A — the tool reported no findings list.

{% else %}
{% for group in [("Tests", "Failed tests", "No failed or errored tests."), ("Coverage", "Coverage violations", "Every coverage gate is met.")] %}
{% set items = findings | selectattr("source", "equalto", group[0]) | list %}
### {{ group[1] }} — {{ items | length }}

{% for finding in items %}
{% if finding.get("anchor") %}<a id="{{ finding.anchor }}"></a>

{% endif %}#### {% if finding.rule == "coverage-per-file" %}{{ finding.path | md_code }}{% else %}{{ finding.title }}{% endif %}

{% if finding.rule == "coverage-per-file" %}
**Coverage:** {{ "%.2f" | format(finding.percent) }}% · **Minimum:** {{ "%.2f" | format(finding.required) }}% · {{ finding.id | md_code }}
{% else %}
**{{ finding.severity | upper }}** · {{ finding.rule | md_code }} · {% if finding.path %}{{ finding.path | md_code }}{% if finding.line %}:{{ finding.line }}{% endif %}{% endif %}
{% endif %}


{% if finding.get("assertion_diff") %}
AssertionError: the actual result differs from the expected result.

**Expected**

{{ finding.assertion_diff.expected | md_codeblock("text") }}

**Actual**

{{ finding.assertion_diff.actual | md_codeblock("text") }}
{% elif finding.rule == "coverage-per-file" %}
**Uncovered lines**

{{ finding.uncovered | wordwrap(78, break_long_words=false) | md_codeblock("text") }}
{% else %}
{{ finding.message | trim | md_codeblock("text") }}
{% endif %}
{% if finding.get("log") %}

Log: [Test output]({{ finding.log }}){% if finding.get("shard") is not none %} (shard {{ finding.shard }}){% endif %}

{% endif %}

{% if finding.get("excerpt") %}
~~~{{ finding.excerpt.language }}
{% for row in finding.excerpt.lines %}
{{ "%5d" | format(row.n) }}{{ ">" if row.target else " " }}|{{ " " ~ row.text if row.text else "" }}
{% endfor %}
~~~

{% endif %}
{% else %}
{{ group[2] }}

{% endfor %}
{% endfor %}
{% endif %}
{% endblock %}
{% block artifacts %}
## Evidence

| Artifact | Path | Bytes |
|---|---|---:|
{% for artifact in artifacts %}
{% if "/TESTS/" not in artifact.path and artifact.name != "README.md" %}
| {{ artifact.name | md_cell }} | [{{ artifact.path | md_cell }}]({{ artifact.path }}) | {{ artifact.bytes }} |
{% endif %}
{% endfor %}
{% endblock %}
{% block tool_extension %}

## Test groups

{% if test_groups %}
One report per group of Python test files.

| Group | Files | Tests | Passed | Failed | Skipped | Report |
|---|---:|---:|---:|---:|---:|---|
{% for row in test_groups %}
| {{ cell(row, "group") }} | {{ cell(row, "files") }} | {{ cell(row, "tests") }} | {{ cell(row, "passed") }} | {{ cell(row, "failed") }} | {{ cell(row, "skipped") }} | {{ report_link(row) }} |
{% endfor %}
{% else %}
No Python test groups.
{% endif %}

## Sub-reports

{% if sub_reports %}
| Report | Path | Contents |
|---|---|---|
{% for row in sub_reports %}
| {{ cell(row, "name") }} | {{ report_link(row) }} | {{ cell(row, "description") }} |
{% endfor %}
{% else %}
N/A — the tool reported no sub-reports.
{% endif %}
{% endblock %}
