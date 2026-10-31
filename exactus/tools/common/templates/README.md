# `exactus/tools/common/templates/`

Data assets shared by the exactus tools. The inventory below documents
every direct file and child directory.

## Directory contents

### Subdirectories

#### `html/`

Offline web report bundle assets: stylesheet, entry page, client script
and the vendored design-system kit.

#### `markdown/`

Core Markdown report template, its partials and golden examples for the
`exactus.packages.markdown` engine.

<!-- exactus:inventory:start -->
## Directory contents

### Files

No direct files besides this README.

### Subdirectories

- [`html/`](html/README.md) — Shared assets of the offline web report bundle consumed by `exactus/tools/reports/bundle.py`. The inventory below documents every direct file and child directory.
- [`markdown/`](markdown/README.md) — Core Markdown report template for the Jinja2 engine. A migrated tool's `templates/markdown/template.md` extends `result_template.md` and its `mapping.json` is merged over `mapping.json` here (`{**base, **tool}`). The inventory below documents every direct file and child directory.

<!-- exactus:inventory:end -->


