# `exactus/tools/common/templates/markdown/`

Core Markdown report template for the Jinja2 engine. A migrated tool's
`templates/markdown/template.md` extends `result_template.md` and its
`mapping.json` is merged over `mapping.json` here (`{**base, **tool}`).
The inventory below documents every direct file and child directory.

## Directory contents

### Files

#### `result_template.md`

Core report template rendering, from the mapped normalized result, the
title and the sections Identity, What was checked (summary and scope),
Setup (invocation and environment), Gate, Findings (with an index) and
Artifacts, then tool-specific content and the footer. Overridable blocks:
`identity`, `tool_summary`, `scope`, `setup`, `gate`, `tool_findings`,
`artifacts` and `tool_extension` (empty by default). A block the tool did
not report (`summary`, `scope`, `findings`) renders `N/A`, as in a crash
report.

#### `mapping.json`

Base mapping every tool mapping extends: passes the envelope and tool
blocks through, sorts `findings` by path, projects the `blocking`
findings and sets `severity_levels` (`error`, `warning`, `info`).

### Directories

#### `examples/`

Example normalized results and golden Markdown for the core template.

#### `partials/`

Macros and includes shared by the core template.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`mapping.json`](mapping.json) — Provide mapping json content.
- [`result_template.md`](result_template.md) — {% from "partials/macros.md" import cell, bullets %} # {{ tool.display_name }}

### Subdirectories

- [`examples/`](examples/README.md) — Example normalized results and golden outputs for the core report template rendered alone with the base `mapping.json`. The inventory below documents every direct file and child directory.
- [`partials/`](partials/README.md) — Macros and includes used by `result_template.md`. The inventory below documents every direct file and child directory.

<!-- exactus:inventory:end -->


