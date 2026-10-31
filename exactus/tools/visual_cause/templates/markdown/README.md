# Visual cause Markdown template

`template.md` renders normalized visual-cause targets, findings, selector
queries, and image evidence. `mapping.json` exposes the tool extension blocks
to the shared report renderer.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`mapping.json`](mapping.json) — Provide mapping json content.
- [`template.md`](template.md) — {% extends "result_template.md" %} {% block tool_summary %} {% if summary %} **Result: {{ run.status }}** — {{ summary.targets }} targets, {{ summary.findings }} findings.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
