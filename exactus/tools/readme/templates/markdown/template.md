{% extends "result_template.md" %}
{% from "partials/macros.md" import bullets %}
{% block tool_extension %}

## Directory inventory

{% if inventory %}
{{ inventory | md_table("Directory:directory", "README:readme", "README bytes:bytes", "Entries:entries", "Documented:documented", "Missing:missing") }}
{% else %}
N/A — the tool reported no directory inventory.
{% endif %}

## Documentation files

{% if documentation_files %}
{{ documentation_files | md_table("Metric:metric", "Value:value") }}

### README sizes

{% if readme_sizes %}
{{ readme_sizes | md_table("README:readme", "Path:path", "Bytes:bytes") }}
{% else %}
N/A — no README.md file was found.
{% endif %}

### Directories without a README

{{ bullets(directories_without_readme, "every directory with analyzed source files has a README") }}
{% else %}
N/A — the tool reported no metrics.
{% endif %}

## Rules

{% if rules %}
{{ rules | md_table("Rule:rule", "Title:title", "Findings:count") }}
{% else %}
N/A — the tool reported no rule counts.
{% endif %}
{% endblock %}
