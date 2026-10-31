# `exactus/tools/reports/`

Shared report delivery and template rendering. This package may depend on
`exactus.packages.markdown` and `exactus.tools.common`; the leaf `common` package must
never import it. Shared templates remain in
[../common/templates/](../common/templates/README.md).

## Files

### `__init__.py`

Package marker; no compatibility re-exports.

#### `bundle.py`

Write consistent Markdown, JSON, and offline web exactus reports. Public API: `Constants` — Store shared report rendering constants.; `command_output()` — Return a trimmed command's stdout, or an empty string on failure.; `fingerprint()` — Return the tree and toolchain identity of this exactus run.; `ReportPaths` — Represent the three public report deliverables.; `ReportBundle` — Render one analyzer result in identical Markdown/JSON/web formats.


#### `render.py`

Render normalized reports from `result.json` through tool templates. Public API: `Constants` — Template layout constants.; `RenderedReport` — Markdown and the mapped view model it was rendered from.; `ReportTemplates` — Locate, merge (`{**base, **tool}`) and render the Markdown templates of a tool, and record the column order of the view model's table blocks for the web report.; `NormalizedStamp` — Add the envelope to a written report and re-render it.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Shared exactus report rendering and delivery.
- [`bundle.py`](bundle.py) — Write consistent Markdown, JSON, and offline web exactus reports.
- [`render.py`](render.py) — Render normalized reports from ``result.json`` through tool templates.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


