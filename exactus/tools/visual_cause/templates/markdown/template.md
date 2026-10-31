{% extends "result_template.md" %}
{% block tool_summary %}
{% if summary %}
**Result: {{ run.status }}** — {{ summary.targets }} targets, {{ summary.findings }} findings.

| Fail | Warning | Accept |
|---:|---:|---:|
| {{ summary.fail }} | {{ summary.warning }} | {{ summary.accept }} |
{% else %}
No visual-cause summary was recorded.
{% endif %}
{% endblock %}
{% block tool_extension %}
## Targets

{% if targets %}
{{ targets | md_table("Target:name", "Viewport:viewport", "Mode:mode", "Changed pixels:changed_pixels", "Changed elements:changed_element_count") }}
{% else %}
No target completed.
{% endif %}

## Level queries

{% if queries %}
{{ queries | md_table("Target:target", "Viewport:viewport", "Level:level", "Query:query", "Matched findings:matched_findings") }}
{% else %}
No level queries were configured.
{% endif %}

## Evidence

{% for target in targets %}
{% if target.a and target.b and target.diff %}
### {{ target.name | md_cell }} · {{ target.viewport | md_cell }}

| A — reference | B — changed | Pixel difference |
|---|---|---|
| ![]({{ target.a }}) | ![]({{ target.b }}) | ![]({{ target.diff }}) |

{% endif %}
{% if target.engine_markdown %}
[Full per-element evidence report]({{ target.engine_markdown }}){% if target.engine_report %} · [Engine JSON]({{ target.engine_report }}){% endif %}

{% endif %}
{% endfor %}
{% if not (targets | selectattr("a") | list) %}
No visual evidence was captured.
{% endif %}
{% endblock %}
