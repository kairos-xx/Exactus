{% extends "result_template.md" %}
{% from "partials/macros.md" import cell %}
{% block tool_findings %}
{% if findings is none %}
N/A — the tool reported no findings list.

{% elif not findings %}
No findings.

{% else %}
Grouped by linter, then ordered by path and line.

{% for finding in findings %}
{% set source = finding.get("source") or "unknown" %}
{% if loop.first or source != (loop.previtem.get("source") or "unknown") %}
{% set total = findings | selectattr("source", "equalto", finding.get("source")) | list | length %}
### {{ source }} — {{ total }} {{ "finding" if total == 1 else "findings" }}

{% endif %}
{% if finding.get("anchor") %}<a id="{{ finding.anchor }}"></a>

{% endif %}#### {{ finding.id }} — {{ finding.title }}

**Severity:** {{ finding.severity }} · **Rule:** {{ finding.rule or "N/A" }} · **Location:** {% if finding.path %}`{{ finding.path }}{% if finding.line %}:{{ finding.line }}{% if finding.get("column") %}:{{ finding.column }}{% endif %}{% endif %}`{% else %}N/A{% endif %}{% if finding.blocking %} · **Blocking**{% endif %}


{% set message = finding.message | trim %}
{% if message != finding.title %}
{% if "\n" in message %}
~~~~text
{{ message }}
~~~~
{% else %}
{{ message }}
{% endif %}

{% endif %}
{% if finding.get("excerpt") %}
~~~{{ finding.excerpt.language }}
{% for row in finding.excerpt.lines %}
{{ "%5d" | format(row.n) }}{{ ">" if row.target else " " }}|{{ " " ~ row.text if row.text else "" }}
{% endfor %}
~~~

{% endif %}
{% endfor %}
{% endif %}
{% endblock %}
{% block tool_extension %}
{% if group_final_summary or all_lints_summary %}

## Integrated stages

### group_final

{% if group_final_summary.get("status") == "skipped" %}
Skipped: {{ group_final_summary.get("reason", "source could not be parsed") }}.
{% elif group_final_summary and group_final_summary.get("enabled") is not sameas false %}
| Files scanned | Modules planned | Constants moved | Files changed | Dry run |
|---:|---:|---:|---:|---|
| {{ group_final_summary.get("files", 0) }} | {{ group_final_summary.get("planned", 0) }} | {{ group_final_summary.get("constants", 0) }} | {{ group_final_summary.get("changed", 0) }} | {{ group_final_summary.get("dry_run", false) }} |
{% else %}
Skipped by configuration.
{% endif %}

### all_lints

{% if all_lints_summary %}
| Tools | Passed | Failed | Unavailable | File checks | Diagnostics |
|---:|---:|---:|---:|---:|---:|
| {{ all_lints_summary.get("tools", 0) }} | {{ all_lints_summary.get("passed", 0) }} | {{ all_lints_summary.get("failed", 0) }} | {{ all_lints_summary.get("unavailable", 0) }} | {{ all_lints_summary.get("files", 0) }} | {{ all_lints_summary.get("diagnostics", 0) }} |
{% else %}
N/A — all_lints did not return a summary.
{% endif %}
{% endif %}

## Rules

{% if rules %}
{{ rules | md_table("Rule:rule", "Title:title", "Category:category", "Findings:count") }}
{% else %}
N/A — the tool reported no rule counts.
{% endif %}


## Lint metrics

{% if lint_overview %}
{{ lint_overview | md_table("Metric:metric", "Value:value") }}

### Linters

| Linter | Status | Version | Files | Findings | Errors | Warnings | Information | Exit code | Duration (s) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
{% for row in linters %}
| {{ cell(row, "linter") }} | {{ cell(row, "status") }} | {{ cell(row, "version") }} | {{ cell(row, "files") }} | {{ cell(row, "findings") }} | {{ cell(row, "errors") }} | {{ cell(row, "warnings") }} | {{ cell(row, "information") }} | {{ cell(row, "exit_code") }} | {{ cell(row, "duration_seconds") }} |
{% endfor %}

### Top rules

{% if top_rules %}
{{ top_rules | md_table("Rule:rule", "Linter:linter", "Findings:count") }}
{% else %}
N/A — no rule reported a finding.
{% endif %}

### Files with the most findings

{% if top_files %}
{{ top_files | md_table("Path:path", "Findings:count") }}
{% else %}
N/A — no file has a finding.
{% endif %}
{% else %}
N/A — the tool reported no metrics.
{% endif %}
{% endblock %}
