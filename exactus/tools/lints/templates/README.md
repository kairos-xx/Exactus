# `exactus/tools/lints/templates/`

Fallback tool configurations materialized temporarily by the lints exactus
when an exactused project carries no linter configuration of its own, and
the report template (`markdown/`). The inventory below documents every
direct file and child directory.

## Directory contents

### Files

#### `eslint.config.mjs`

Generic strict ESLint flat configuration copied into a project under
exactus when it lacks `eslint.config.js`/`eslint.config.mjs`/
`eslint.config.cjs`; also used as the `--config` fallback path.

#### `jsconfig.json`

Strict `checkJs` JavaScript configuration materialized in a project
under exactus when it lacks `jsconfig.json`/`tsconfig.json`.

#### `stylelint.config.mjs`

Generic strict Stylelint configuration materialized in a project under
exactus when it lacks any `.stylelintrc*`/`stylelint.config.*` file.

### Directories

#### `markdown/`

The lints `result.md` template (`template.md`) and its mapping
(`mapping.json`).

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`eslint.config.mjs`](eslint.config.mjs) — ", "*
- [`jsconfig.json`](jsconfig.json) — Provide jsconfig json content.
- [`pyproject.toml`](pyproject.toml) — Provide pyproject toml content.
- [`stylelint.config.mjs`](stylelint.config.mjs) — ", "*

### Subdirectories

- [`markdown/`](markdown/README.md) — Markdown report template of the lints tool. The stamp stage of `exactus/tools/common/execution.py` renders `result.md` from the normalized `result.json` with these files. The inventory below documents every direct file.

<!-- exactus:inventory:end -->


