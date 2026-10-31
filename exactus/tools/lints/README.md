# `exactus/tools/lints/`

Lints includes the CMP engineering rules for source parsing, diagnostic suppressions, typing escape hatches and lint/type-check configuration. These checks run as `custom_compliance` in the LINTS report, with finding excerpts, rule counts and deltas. There is no separate compliance command or report.

The `lints` exactus tool: a standalone entry point (`main.py`), its analysis
core (`core.py`), the normalized report builder (`report.py`) and the
report and linter-configuration templates (`templates/`). The inventory
below documents every direct file and child directory.

JavaScript type checking is a project-level step after the
`all_lints` package lane. It runs `tsc --noEmit --project` against the existing
`jsconfig.json` or `tsconfig.json`, preserving that project's compiler
options and file selection. Its diagnostics appear under `typescript` in
the LINTS report, including strict `checkJs` errors in `.js`, `.jsx`, `.mjs`
and `.cjs` files. Without a project config, a temporary strict config checks
the selected JavaScript files and is removed afterwards; native TypeScript
diagnostics from `all_lints` are retained alongside those results. ESLint
and TypeScript remain separate checks, so an ESLint pass is not a type-check
pass.

## CSS token architecture

The `custom_css` linter also audits the stylesheets as one custom-property
graph (`css_tokens.py`): five layers (`--primary-*` and `--dynamic-*` literal
inputs, `--base-*` derived from them, `--catalog-<component>-<domain>-<rule>`
derived from BASE, and unprefixed SEMANTIC tokens that are one plain CATALOG
reference), consumed in ordinary declarations through SEMANTIC variables only.
Definitions and references are resolved across every stylesheet in scope, so a
token may live in a different file from its users. Findings are `CSS100`-`CSS125`
(`CSS0xx` are the per-file value conventions); `--css-context-word` (repeatable,
or `css-context-word` in `[tool.exactus.lints]`) lists application words that
CATALOG names must not contain, and `components/<name>/` directory names are
added automatically as whole names (`condition-field` flags that name, not the
word `field`). Structural keywords (`display`, `place-items`, `flex-flow`, …)
may stay literal; their operands are still checked. A property set under
different selectors or at-rules is the cascade, not a conflict: `CSS101` fires
only when one scope gives it two values.

| Rule | Check |
| --- | --- |
| CSS100 | a stylesheet cannot be read (missing, unreadable, not UTF-8); the rest are still audited |
| CSS101 | a custom property has two values in the same scope |
| CSS102 | a referenced custom property is not defined (`--dynamic-*` excepted) |
| CSS103 | a token name encodes provenance, a hash, or a BASE numeric suffix |
| CSS104-CSS107 | PRIMARY keyword, percent, duration and font-weight scales |
| CSS108-CSS109 | PRIMARY/DYNAMIC value references a token or calls a function |
| CSS110 | BASE references something other than PRIMARY or DYNAMIC |
| CSS111-CSS113 | CATALOG references non-BASE, derives a color, or multiplies by BASE one/zero |
| CSS114-CSS118 | CATALOG name shape, domain order, domain, scale vocabulary, context words |
| CSS119-CSS120 | SEMANTIC is not exactly one plain CATALOG reference |
| CSS121 | terminal declaration reads a non-SEMANTIC variable |
| CSS122 | terminal declaration uses `calc`/`min`/`max`/`clamp`/`minmax`/`color-mix`/`repeat` |
| CSS123 | a design property is not exactly one SEMANTIC `var()` |
| CSS124 | a terminal declaration embeds a hardcoded measure, color or color function |
| CSS125 | a configurable numeric property holds a bare number |

## Directory contents

### Files

#### `__init__.py`

Lints exactus tool.

#### `core.py`

Lint exactus engine: clean, lint, and type-check sources with rollback. Public API: `NodeVisitorWalk` — Provide compact AST traversal helpers.; `JavaScriptScanner` — Provide lightweight lexical JavaScript helpers.; `SourceCleaner` — Remove blank lines, normalize whitespace, and format sources.; `LintExactus` — Lint, type-check, and guard ``pyrefly infer`` against regressions. `template_resource()` — Locate a bundled linter template in `exactus/tools/lints/templates`.

#### `css_tokens.py`

Audit the CSS custom-property architecture and terminal-layer policy. Public API: `Layer` — Custom-property architecture layers.; `CssTokenInput` — Carry the inputs of one CSS token audit.; `CssTokenFinding` — One token-architecture violation.; `CssTokenAudit` — Audit a stylesheet set against the token architecture.; `layer_of()` — Return the architecture layer a custom-property name belongs to.; `lex()` — Separate a stylesheet's structure from its comments and strings.; `parse_declarations()` — Parse the declarations of one stylesheet.; `scan_css_tokens()` — Audit a stylesheet set against the token architecture.

#### `js_delimiters.py`

Conservatively remove unnecessary JavaScript parentheses and braces. Runs as `custom_javascript_delimiters` in the LINTS report: in fix mode the scan rewrites each in-scope `.js`/`.mjs`/`.cjs` file (guarded by Node syntax validation) and reports the rewrite under `healed`; without fix each file carrying removable delimiters is a `DEL001` finding. Public API: `JavaScriptDelimiterSimplifier` — conservative text/file/path simplifier.; `scan_delimiters()` — audit-and-heal pass over a file list.; `DelimiterInput`, `DelimiterResult`, `DelimiterFinding`, `DelimiterHeal` — frozen scan models. See `exactus/docs/exactus/tools/lints/DOCS.md`.

#### `js_function_blocks.py`

Report JavaScript function and method blocks and modernization eligibility through Node/Espree. Runs as `custom_javascript_notation` in the LINTS report: in fix mode the scan rewrites each in-scope `.js`/`.mjs`/`.cjs`/`.jsx` file to compact arrow or static notation and reports the rewrite under `healed`; without fix each file carrying a modernizable callable is a `JSN001` finding. Instance methods are never auto-promoted to `static`. Public API: `JavaScriptBlockAnalyzer` — block analysis and conversions (`analyze`, `normalize`, `to_arrow`, `from_arrow`).; `scan_function_blocks()` — audit-and-heal pass over a file list.; `FunctionBlocksInput`, `FunctionBlocksResult`, `FunctionBlocksFinding`, `FunctionBlocksHeal` — frozen scan models. See `exactus/docs/exactus/tools/lints/DOCS.md`.

#### `long_lines.py`

Repair Python lines that remain too long after Ruff formatting. Public API: `LongLinesAPI` — Stable in-memory, file and batch facade.; `LongLineRepair` — Repair hook run inside the Ruff stabilization loop.; `LongLineFixer` — AST-validated repair engine.; `Settings`, `Result`, `TextResult`, `BatchResult`, `RepairSummary` — Frozen configuration and result models. See `exactus/docs/exactus/tools/lints/DOCS.md`.

#### `main.py`

Run the combined lint exactus and emit the LINTS report bundle. Public API: `create_parser()` — Create parser.; `parse_args()` — Parse args.; `main()` — Return main. The payload is `report.report_data` with source excerpts (`--context-lines`); the stamp stage renders `result.md` from `templates/markdown/`.

#### `report.py`

Normalize the LINTS report: summary, scope, findings and metrics. Public API: `ReportTables` — Constants of the normalized LINTS report.; `relative_path()` — Express a linter's file name relative to the project root.; `linter_status()` — Classify how one linter took part in the run.; `finding_title()` — Return the one-line title of a lint finding.; `normalized_findings()` — Return the findings in the normalized shape, keeping legacy fields.; `report_data()` — Return the LINTS payload with the normalized blocks added (`summary`, `scope`, `findings`, `extension.metrics`).

### Subdirectories

#### `templates/`

Fallback ESLint, Stylelint and JavaScript configurations materialized
when an exactused project carries none, and the `result.md` template and
mapping (`markdown/`). See `templates/README.md`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Lints exactus tool.
- [`arguments.py`](arguments.py) — Declare the lints grammar without importing its execution engine.
- [`compliance.py`](compliance.py) — Exactus suppression markers, escape-hatch annotations, and lint config.
- [`core.py`](core.py) — Lint exactus engine: clean, lint, and type-check sources with rollback.
- [`css_tokens.py`](css_tokens.py) — Audit the CSS custom-property architecture and terminal-layer policy.
- [`js_delimiters.py`](js_delimiters.py) — Conservatively remove unnecessary JavaScript parentheses and braces.
- [`js_function_blocks.py`](js_function_blocks.py) — Report JavaScript function and method blocks and modernization eligibility.
- [`long_lines.py`](long_lines.py) — Repair Python lines that remain too long after Ruff formatting.
- [`long_lines_engine.py`](long_lines_engine.py) — Repair Python lines that remain too long after Ruff formatting.
- [`main.py`](main.py) — Run the combined lint exactus and emit the LINTS report bundle.
- [`packages_pipeline.py`](packages_pipeline.py) — Bridge Exactus lints to packaged source-refactor and lint tools.
- [`report.py`](report.py) — Normalize the LINTS report: summary, scope, findings and metrics.
- [`shebang.py`](shebang.py) — Exactus Python executable permissions against shebang presence.
- [`string_transform.py`](string_transform.py) — Source-preserving string dedenting, splitting and f-string formatting.

### Subdirectories

- [`templates/`](templates/README.md) — Fallback tool configurations materialized temporarily by the lints exactus when an exactused project carries no linter configuration of its own, and the report template (`markdown/`). The inventory below documents every direct file and child directory.

<!-- exactus:inventory:end -->




Organizer debugging uses the shared `exactus.packages.steps` trace and records per-file `changed`/`would change`, `unchanged`, and `skipped: unparseable` states plus stage totals.

### JavaScript organization

The `organize` pre-stage also orders safe contiguous JavaScript class-method
runs. Its canonical order is constructor, public static accessors, public
static methods, public accessors, public instance methods, private static
accessors, private static methods, private accessors, then private instance
methods. Getter/setter pairs stay adjacent with the getter first. Class fields,
static blocks, computed method names, and other executable class elements are
hard barriers and are never moved. Steps tracing labels each input as
`organize[python]` or `organize[javascript]`.
