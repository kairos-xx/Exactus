{% extends "result_template.md" %}
{% block tool_extension %}

## Documentation statistics

{% if languages %}
{{ languages | md_table("Language:language", "Files:discovered", "Parsed:parsed", "Failed:failed", "Symbols:symbols", "Documented:documented", "Coverage %:coverage", "Findings:findings") }}
{% else %}
N/A — the tool reported no documentation statistics.
{% endif %}

## Analyzed code

{% if analyzed_code %}
{{ analyzed_code | md_table("Language:language", "Files:files", "Lines:lines") }}
{% else %}
N/A — the tool reported no per-language metrics.
{% endif %}

## Rules

{% if rules %}
{{ rules | md_table("Rule:rule", "Title:title", "Findings:count") }}
{% else %}
N/A — the tool reported no rule counts.
{% endif %}

## Suggested documentation

{% if findings is none %}
N/A — the tool reported no findings list.
{% else %}
{% for finding in findings %}
### {{ finding.id }} — `{{ finding.qualname }}`

{% if finding.signature %}
Signature: `{{ finding.signature }}`

{% endif %}
Reason: {{ finding.reason }}

~~~{{ "python" if finding.language == "python" else "js" }}
{{ finding.suggestion }}
~~~
{% if not loop.last %}

{% endif %}
{% else %}
No suggestions.
{% endfor %}
{% endif %}
{% endblock %}
