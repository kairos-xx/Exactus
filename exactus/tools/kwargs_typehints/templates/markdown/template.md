{% extends "result_template.md" %}
{% from "partials/macros.md" import cell %}
{% macro code(row, key) %}{% if row.get(key) is none %}N/A{% else %}{{ row.get(key) | md_code | md_cell }}{% endif %}{% endmacro %}
{% block tool_summary %}
{{ super() }}
### Metrics

{% if metrics %}
{{ metrics | md_table("Metric:metric", "Value:value") }}

#### Findings by category

| Category | Severity | Blocking | Findings |
|---|---|---|---:|
{% for row in findings_by_category %}
| {{ cell(row, "category") }} | {{ cell(row, "severity") }} | {{ "Yes" if row.blocking else "No" }} | {{ cell(row, "findings") }} |
{% endfor %}
{% else %}
N/A — the tool reported no metrics.
{% endif %}
{% endblock %}
{% block tool_findings %}
{% if findings is none %}
N/A — the tool reported no findings list.

{% elif not findings %}
No findings.

{% else %}
Grouped by category (blocking categories first), then ordered by path and line.

{% for finding in findings %}
{% set source = finding.get("source") or "Other" %}
{% if loop.first or source != (loop.previtem.get("source") or "Other") %}
{% set total = findings | selectattr("source", "equalto", finding.get("source")) | list | length %}
### {{ source }} — {{ total }} {{ "finding" if total == 1 else "findings" }}

{% endif %}
{% if finding.get("anchor") %}<a id="{{ finding.anchor }}"></a>

{% endif %}#### {{ finding.id }} — {{ finding.title }}

**Severity:** {{ finding.severity }} · **Rule:** {{ finding.rule or "N/A" }} · **Location:** {% if finding.path %}`{{ finding.path }}{% if finding.line %}:{{ finding.line }}{% if finding.get("column") %}:{{ finding.column }}{% endif %}{% endif %}`{% else %}N/A{% endif %}{% if finding.blocking %} · **Blocking**{% endif %}


{{ finding.message | trim }}

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

## Unresolved callees

{% if extension %}
Callees with no known signature, so positional use at these call sites was not checked. Most call sites first; the Finding column names the finding with the source excerpt.

{% if unresolved_callees %}
| Callee | Path | Line | Reason | Call sites | Finding |
|---|---|---:|---|---:|---|
{% for row in unresolved_callees %}
| {{ code(row, "callee") }} | {{ cell(row, "path") }} | {{ cell(row, "line") }} | {{ cell(row, "reason") }} | {{ cell(row, "call_sites") }} | {{ cell(row, "finding") }} |
{% endfor %}
{% else %}
No unresolved callees: every checked call site resolved to a signature or is exempt.
{% endif %}
{% else %}
N/A — the tool reported no unresolved callees.
{% endif %}

## Ambiguous call sites

{% if extension %}
{% if ambiguous_call_sites %}
Several classes define the method and their signatures disagree, so these calls need a manual review.

| Callee | Path | Line | Candidates | Finding |
|---|---|---:|---|---|
{% for row in ambiguous_call_sites %}
| {{ code(row, "callee") }} | {{ cell(row, "path") }} | {{ cell(row, "line") }} | {{ cell(row, "candidates") }} | {{ cell(row, "finding") }} |
{% endfor %}
{% else %}
No ambiguous call sites.
{% endif %}
{% else %}
N/A — the tool reported no ambiguous call sites.
{% endif %}

## Bare imports

{% if extension %}
{% if bare_imports %}
Bare `import module` statements outside the allowlist, with the explicit import that replaces each one when an automatic rewrite is safe.

| Module | Path | Line | Fix | Replacement | Finding |
|---|---|---:|---|---|---|
{% for row in bare_imports %}
| {{ code(row, "module") }} | {{ cell(row, "path") }} | {{ cell(row, "line") }} | {{ cell(row, "fix") }} | {{ code(row, "replacement") }} | {{ cell(row, "finding") }} |
{% endfor %}
{% else %}
No bare imports.
{% endif %}
{% else %}
N/A — the tool reported no bare imports.
{% endif %}

## Automatic fixes

{% if extension %}
{% if auto_fixes %}
Validated deterministic source edits. `fixed` means the edit was written; `would-fix` means dry-run mode validated it without modifying the file.

| Status | Kind | Path | Line | Column | Original | Replacement |
|---|---|---|---:|---:|---|---|
{% for row in auto_fixes %}
| {{ cell(row, "status") }} | {{ cell(row, "kind") }} | {{ cell(row, "file") }} | {{ cell(row, "line") }} | {{ cell(row, "column") }} | {{ code(row, "original") }} | {{ code(row, "replacement") }} |
{% endfor %}
{% else %}
No automatic source edits were applicable.
{% endif %}
{% else %}
N/A — the tool reported no automatic-fix data.
{% endif %}

## Methodology and caveats

{% if methodology_and_caveats %}
{% for note in methodology_and_caveats %}
- {{ note }}
{% endfor %}
{% else %}
N/A — the tool reported no methodology notes.
{% endif %}
{% endblock %}
