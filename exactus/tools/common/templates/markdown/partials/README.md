# `exactus/tools/common/templates/markdown/partials/`

Macros and includes used by `result_template.md`. The inventory below
documents every direct file and child directory.

## Directory contents

### Files

#### `macros.md`

Jinja2 macros: `cell` (a block field, or `N/A` when missing or null) and `bullets` (a
bullet list or `N/A — <reason>.`).

#### `finding.md`

Include rendering one finding: heading, severity, rule, location,
message, and the optional `excerpt` as a numbered fenced block in the
file's language with the finding line marked by `>`.

#### `footer.md`

Include rendering the closing rule and the tool, run, result and
duration line.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`finding.md`](finding.md) — {% if finding.get("anchor") %}<a id="{{ finding.anchor }}"></a>
- [`footer.md`](footer.md) — {% from "partials/macros.md" import cell %} ---
- [`macros.md`](macros.md) — {% macro cell(block, key) %}{% if block.get(key) is none %}N/A{% else %}{{ block.get(key) | md_cell }}{% endif %}{% endmacro %} {% macro bullets(items, reason) %}{% if items %}{% for item in (items if items is sequence and items is not string else \[items\]) %}- {{ item | md_code }}{{ "\n" if not loop.last }}{% endfor %}{% else %}N/A — {{ reason }}.{% endif %}{% endmacro %}

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


