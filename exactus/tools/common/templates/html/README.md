# `exactus/tools/common/templates/html/`

Shared assets of the offline web report bundle consumed by
`exactus/tools/reports/bundle.py`. The inventory below documents every
direct file and child directory.

## Directory contents

### Files

#### `report.css`

Layout-only stylesheet for the offline web report bundle; colors,
type and components come from `exactus/packages/cerulean.css`.

#### `report.html`

HTML entry point of the offline web report bundle.

#### `report.js`

Client-side renderer of the offline web report bundle. A migrated
tool's data carries `view` (the mapped view model its `result.md` was
rendered from), `view_columns` and `view_order` (the mapping order of
the tool sections); the page then renders from the view model: section
navigation, gate banner, what was checked (totals, severity counts,
scope), findings filterable by text, source (a tool's `source_label`,
such as Linter or Category), rule and severity (each finding's
`excerpt` shown in a snippet viewer: numbered lines, the finding line
highlighted, "Fewer lines"/"More lines" buttons that narrow or widen
the context within the captured lines), generic sortable tables for
every tool extension block (a row naming a `finding` links to it: a
click anywhere on the row clears filters hiding the finding, selects
it, scrolls to it, focuses it and adds a link back to the row), note
lists for prose blocks, artifacts, identity and setup. Other tools keep the legacy views:
filterable findings grouped by file, coverage tables, the screenshot
gallery with before/after lightbox and click markers, and the pipeline
overview.

### Subdirectories

#### `vendor/`

Vendored third-party assets copied verbatim into every web bundle:
`cerulean.css`, the Cerulean design-system tokens (dark plus a derived
light theme) and `ds-*` components. Excluded from lint exactuss.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`report.css`](report.css) — Provide report css content.
- [`report.html`](report.html) — Provide report html content.
- [`report.js`](report.js) — Keys the report reads from exactus payloads. Listing them (instead of an index signature) keeps dot access valid for both TypeScript and ESLint and turns key typos into type errors.

### Subdirectories

- [`vendor/`](vendor/README.md) — Pinned browser assets used by generated HTML reports. Keep license notices and versioned filenames with their corresponding assets.

<!-- exactus:inventory:end -->


