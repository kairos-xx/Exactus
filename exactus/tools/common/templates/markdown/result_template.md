{% from "partials/macros.md" import cell, bullets %}
# {{ tool.display_name }}

**Run time:** {{ cell(run, "at_human") }}

{% block identity %}
## Identity

| Field | Value |
|---|---|
| Tool | {{ tool.name | md_cell }}{% if tool.get("version") %} {{ tool.version | md_cell }}{% endif %} |
| Run ID | {{ cell(run, "id") }} |
| Pipeline run | {{ cell(run, "pipeline_id") }} |
| Status | {{ cell(run, "status") }} |
| Exit code | {{ cell(run, "exit_code") }} |
| Started | {{ cell(run, "started_at_human") }} |
| Finished | {{ cell(run, "finished_at_human") }} |
| Duration | {{ cell(run, "duration_human") }} |
{% if previous_duration_seconds is defined and previous_duration_seconds is not none %}| Previous duration | {{ "%.3fs" | format(previous_duration_seconds) }} |
{% endif %}
{% endblock %}

## What was checked

{% block tool_summary %}
{% if summary %}
**Result: {{ run.status }}** — {{ summary.findings_total }} {{ "finding" if summary.findings_total == 1 else "findings" }} across {{ summary.targets_analyzed }} of {{ summary.targets_eligible }} eligible targets.

| Severity | Count |
|---|---:|
{% for level in severity_levels %}
| {{ level | upper }} | {{ (summary.severity or {}).get(level, 0) }} |
{% endfor %}
{% else %}
**Result: {{ run.status }}** — N/A — the tool reported no summary.
{% endif %}
{% endblock %}

{% block comparison %}
### Change since previous report

{% if comparison and comparison.available %}
| Metric | Current | Previous | Delta |
|---|---:|---:|---:|
| Findings | {{ comparison.current_total }} | {{ comparison.previous_total }} | {% if comparison.delta > 0 %}+{% endif %}{{ comparison.delta }} |
{% if comparison.previous_duration_seconds is defined and comparison.previous_duration_seconds is not none %}
| Previous duration | {{ "%.3fs" | format(comparison.previous_duration_seconds) }} | | |
{% endif %}

| Finding change | Count |
|---|---:|
| Added | {{ cell(comparison, "added_count") }} |
| Resolved | {{ cell(comparison, "resolved_count") }} |
| Unchanged | {{ cell(comparison, "unchanged_count") }} |

{% if comparison.added %}
**Added findings**

{{ comparison.added | md_table("Rule:rule", "Path:path", "Line:line", "Title:title") }}

{% endif %}
{% if comparison.resolved %}
**Resolved findings**

{{ comparison.resolved | md_table("Rule:rule", "Path:path", "Line:line", "Title:title") }}

{% endif %}
{% if comparison.get("categories") %}
#### Category findings

{{ comparison.categories | md_table("Category:category", "Title:title", "Findings:current", "Previous:previous", "Delta:delta") }}

{% endif %}
{% else %}
No previous report exists; this run establishes the baseline.

{% endif %}
{% endblock %}
{% block scope %}
### Scope

{% if scope %}
**Included**

{{ bullets(scope.include, "no include rules") }}

**Excluded**

{{ bullets(scope.exclude, "no exclude rules") }}

**Skipped targets**

{% if scope.skipped %}
{{ scope.skipped | md_table("Target:target", "Reason:reason") }}
{% else %}
No skipped targets.
{% endif %}
{% else %}
N/A — the tool reported no scope.
{% endif %}
{% endblock %}

{% block setup %}
## Setup

### Invocation

{{ invocation.command | md_fence("shell") }}

| Property | Value |
|---|---|
| Working directory | {{ cell(invocation, "cwd") }} |
| Arguments | {% if invocation.arguments %}{% for argument in invocation.arguments %}{{ argument | md_code | md_cell }}{{ " " if not loop.last }}{% endfor %}{% else %}N/A{% endif %} |

### Environment

| Property | Value |
|---|---|
| OS | {{ cell(environment, "os") }} |
| Python | {{ cell(environment, "python") }} |
| Node | {{ cell(environment, "node") }} |
| CPU count | {{ cell(environment, "cpu_count") }} |

{% if environment.variables %}
{{ environment.variables | md_table("Variable:name", "Value:value") }}
{% else %}
No allowlisted environment variables are set.
{% endif %}
{% endblock %}

{% block gate %}
## Gate

> **Gate: {{ gate.status }}** — {{ gate.reason }}
{% if run.error is defined and run.error %}

The tool raised an error:

{{ run.error | md_fence("text") }}
{% endif %}

{% if blocking %}
Blocking findings:

{% for item in blocking %}
- {{ item.id }} — {{ item.title }}
{% endfor %}
{% elif findings is none %}
N/A — the tool reported no findings list.
{% else %}
No blocking findings.
{% endif %}
{% endblock %}

## Findings

{% if file_summary is defined and file_summary %}
### By file

{% for group in file_summary %}
#### `{{ group.path }}`

{{ group.count }} {{ "finding" if group.count == 1 else "findings" }}{{ " — " ~ group.severity_text if group.severity_text else "" }}

{% for issue in group.issues %}
- [{{ issue.id }}](#{{ issue.anchor }}) — {{ issue.severity }}{{ " · " ~ issue.rule if issue.rule else "" }}{{ " · line " ~ issue.line if issue.line is defined and issue.line is not none else "" }}
{% endfor %}

{% endfor %}
{% endif %}
{% block tool_findings %}
{% if findings is none %}
N/A — the tool reported no findings list.

{% else %}
{% for finding in findings %}
{% include "partials/finding.md" %}
{% else %}
No findings.

{% endfor %}
{% if findings %}
### Index

{{ findings | md_table("ID:id", "Severity:severity", "Rule:rule", "Path:path", "Line:line", "Title:title") }}

{% endif %}
{% endif %}
{% endblock %}
{% block artifacts %}
## Artifacts

{% if artifacts %}
{{ artifacts | md_table("Artifact:name", "Path:path", "Bytes:bytes") }}
{% else %}
No auxiliary artifacts.
{% endif %}
{% endblock %}
{% block tool_extension %}
{% endblock %}

{% include "partials/footer.md" %}
