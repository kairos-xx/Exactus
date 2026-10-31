{% extends "result_template.md" %}
{% block tool_summary %}
{% if summary %}
**Result: {{ run.status }}** — {{ summary.workflows }} workflows, {{ summary.steps }} steps, {{ summary.findings_total }} findings.

| Outcome | Workflows | Steps |
|---|---:|---:|
{% for status in ["succeeded", "failed", "cancelled", "skipped", "unknown"] %}
| {{ status | title }} | {{ summary.workflow_outcomes.get(status, 0) }} | {{ summary.step_outcomes.get(status, 0) }} |
{% endfor %}

Screenshots: **{{ summary.screenshots }}**. Captures follow the policy saved in each workflow.
{% else %}
No execution summary was recorded.
{% endif %}
{% endblock %}
{% block gate %}
## Gate

> **Gate: {{ gate.status }}** — {{ gate.reason }}
{% if run.get("error") %}

{{ run.error | md_codeblock("text") }}
{% endif %}
{% endblock %}
{% block tool_findings %}
{% if findings %}
{% for group in findings | groupby("group") %}
### {{ "Server" if group.grouper == "Server" else "Flow: " ~ group.grouper | md_cell }}

{% for stage in group.list | groupby("stage") %}
{% if group.grouper != "Server" %}
#### {{ stage.grouper | title | md_cell }}

{% endif %}
{% for finding in stage.list %}
{% if finding.get("anchor") %}<a id="{{ finding.anchor }}"></a>

{% endif %}{% if finding.category in ["console", "pageerror", "server"] %}
> [!{{ "CAUTION" if finding.category == "server" else "WARNING" }}]
> **{{ finding.title | md_cell }}** · {{ finding.severity | upper }} · {{ finding.id | md_code }}
{% else %}
**{{ finding.title | md_cell }}** · {{ finding.severity | upper }} · {{ finding.id | md_code }}
{% endif %}

{% if finding.get("line") %}
Source: {{ finding.path | md_code }}:{{ finding.line }}{% if finding.get("column") %}:{{ finding.column }}{% endif %}

{% endif %}
{% if finding.get("function") %}
Function: {{ finding.function | md_code }}

{% endif %}
{{ finding.message | md_codeblock("text") }}{{ "\n" }}
{% if finding.get("stack") %}

**Stack trace**

{{ finding.stack | md_codeblock("text") }}{{ "\n" }}
{% endif %}
{% endfor %}
{% endfor %}
{% endfor %}
{% else %}
No findings.
{% endif %}
{% endblock %}
{% block tool_extension %}
## Actions recipe

{% if recipe_actions %}
{{ recipe_actions | md_table("Action:id", "Tool:tool", "Status:status", "Error:error") }}
{% else %}
This run executed a workspace or URL directly.
{% endif %}

## Workflows

{% if workflow_rows %}
{{ workflow_rows | md_table("Name:name", "Workflow:flow_id", "Status:status", "Width (px):width", "Height (px):height", "Theme:theme", "Steps:steps", "Failed steps:failed_steps") }}

{% for flow in workflow_rows %}
{% if flow.get("action_id") and (loop.first or flow.get("action_id") != loop.previtem.get("action_id")) %}
### Action: {{ flow.action_id | md_cell }}

{% endif %}
#### {{ flow.name | md_cell }} — {{ flow.status | md_cell }}

Run: {{ flow.run_id | md_code }}. Workflow: {{ flow.flow_id | md_code }}.
{% if flow.get("error") %}

**Failure reason**

{{ flow.get("error") | md_codeblock("text") }}
{% endif %}

{% if flow.get("action_records") %}
{{ flow.get("action_records") | md_table("Step:label", "Type:kind", "Status:status", "Attempt:attempt", "Started (ms):started_ms", "Finished (ms):finished_ms", "Error:error") }}

{% for record in flow.get("action_records") %}
{% if record.get("error") or record.get("script") or record.response is not none or record.get("assertions") or record.get("screenshot_artifact_ids") %}
##### {{ record.label | default(record.event_id, true) | md_cell }}

Event: {{ record.event_id | md_code }} · Status: **{{ record.status | md_cell }}**
{% if record.get("error") %}

**Error**

{{ record.get("error") | md_codeblock("text") }}
{% endif %}
{% if record.get("script") %}

**JavaScript**

{{ record.get("script") | md_codeblock("javascript") }}
{% endif %}
{% if record.kind == "javascript" or record.response is not none %}

**Response**

{{ record.response | json | md_codeblock("json") }}
{% endif %}
{% if record.get("assertions") %}

**Assertions**

{{ record.get("assertions") | json | md_codeblock("json") }}
{% endif %}
{% if record.get("screenshot_artifact_ids") %}

Screenshot IDs: {% for id in record.get("screenshot_artifact_ids") %}{{ id | md_code }}{{ ", " if not loop.last }}{% endfor %}.
{% endif %}
{% endif %}
{% endfor %}
{% else %}
No steps were recorded for this workflow.
{% endif %}
{% endfor %}
{% else %}
No workflows were recorded. Check the gate and findings for the execution failure.
{% endif %}

## Browser and discovery diagnostics

{% if browser_diagnostics %}
{% for diagnostic in browser_diagnostics %}
### {{ diagnostic.get("category", "Browser issue") | title }} — {{ diagnostic.get("severity", "unknown") | upper }}

Workflow: {{ diagnostic.get("flow", "Unknown") | md_code }} · Phase: {{ diagnostic.get("phase", "Unknown") | md_code }}{% if diagnostic.get("action") %} · Action: {{ diagnostic.action | md_code }}{% endif %}

{% if diagnostic.get("file") or diagnostic.get("url") %}
Source: {{ (diagnostic.get("file") or diagnostic.get("url")) | md_code }}{% if diagnostic.get("line") %}:{{ diagnostic.line }}{% if diagnostic.get("column") %}:{{ diagnostic.column }}{% endif %}{% endif %}

{% endif %}
{% if diagnostic.get("category") in ["console", "pageerror"] %}
Function: {{ (diagnostic.get("function") or "Not provided by the browser") | md_code }}

{% endif %}
{% if diagnostic.get("method") or diagnostic.get("status") %}
Request: {{ diagnostic.get("method", "") | md_code }}{% if diagnostic.get("status") %} · HTTP status: **{{ diagnostic.status }}**{% endif %}

{% endif %}
{{ diagnostic.get("message", "") | md_codeblock("text") }}
{% if diagnostic.get("stack") %}

**Stack trace**

{{ diagnostic.stack | md_codeblock("text") }}
{% endif %}
{% endfor %}
{% else %}
No browser or discovery diagnostics were recorded.
{% endif %}

## Server diagnostics

{% if server_diagnostics %}
{% for diagnostic in server_diagnostics %}
### Server issue — {{ diagnostic.get("severity", "unknown") | upper }}{% if diagnostic.get("status") %} · HTTP {{ diagnostic.status }}{% endif %}

{% if diagnostic.get("method") or diagnostic.get("url") %}
Request: {{ diagnostic.get("method", "") | md_code }} {{ diagnostic.get("url", "") | md_code }}

{% endif %}
{% if diagnostic.get("stream") %}
Stream: {{ diagnostic.stream | md_code }}

{% endif %}
{{ (diagnostic.get("message") or diagnostic.get("line", "")) | md_codeblock("text") }}
{% endfor %}
{% else %}
No server diagnostics were recorded.
{% endif %}

## Screenshots

{% if screenshots %}
{% for image in screenshots %}
- [{{ image.artifact_id | md_cell }}]({{ image.path }}) — {{ image.width }} × {{ image.height }} px; workflow {{ image.flow_id | md_code }}, event {{ image.event_id | md_code }}.
{% endfor %}
{% else %}
No screenshots were recorded.
{% endif %}
{% endblock %}
