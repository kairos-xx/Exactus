{% from "partials/macros.md" import cell %}
---

Exactus · {{ tool.name }}{% if tool.get("version") %} {{ tool.version }}{% endif %} · Run {{ cell(run, "id") }} · Result {{ run.status }} · Duration {{ cell(run, "duration_human") }}
