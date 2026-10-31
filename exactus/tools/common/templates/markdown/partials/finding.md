{% if finding.get("anchor") %}<a id="{{ finding.anchor }}"></a>

{% endif %}### {{ finding.id }} — {{ finding.title }}

**Severity:** {{ finding.severity }} · **Rule:** {{ finding.rule }} · **Location:** {% if finding.get("path") %}`{{ finding.path }}{% if finding.line %}:{{ finding.line }}{% endif %}`{% else %}N/A{% endif %}


{% if finding.get("change") == "added" %}
**Change:** Added since the previous report.

{% endif %}
{{ finding.message }}

{% if finding.get("excerpt") %}
~~~{{ finding.excerpt.language }}
{% for row in finding.excerpt.lines %}
{{ "%5d" | format(row.n) }}{{ ">" if row.target else " " }}|{{ " " ~ row.text if row.text else "" }}
{% endfor %}
~~~

{% endif %}
