{% extends "result_template.md" %}
{% from "partials/macros.md" import bullets %}
{% block tool_extension %}

## Session

{% if session %}
{{ session | md_table("Fact:fact", "Value:value") }}
{% else %}
N/A — the tool reported no session facts.
{% endif %}

### Actions by type

{% if action_types %}
{{ action_types | md_table("Type:type", "Count:count") }}
{% else %}
N/A — no replayable actions were recorded.
{% endif %}

### Exactus Record session

{% if studio %}
{{ studio | md_table("Fact:fact", "Value:value") }}
{% else %}
N/A — no Exactus Record session facts were reported.
{% endif %}

### Produced files

{{ bullets(produced_files, "the session produced no files") }}

## Rules

{% if rules %}
{{ rules | md_table("Rule:rule", "Title:title", "Findings:count") }}
{% else %}
N/A — the tool reported no rule counts.
{% endif %}
{% endblock %}
