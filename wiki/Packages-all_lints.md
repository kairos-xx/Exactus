[Home](Home.md) > [Packages](Packages.md) > all_lints

# all_lints/

Run project linters and merge their diagnostics into one JSON report.

## Behavior

- `basedpyright` and `pyrefly` run once per batch over all Python files;
  diagnostics are bucketed back to their owning files.
- `tsc` runs as a project tool: one `tsc --project <jsconfig|tsconfig>`
  invocation covers every discovered JS/TS file (via `checkJs`).
- Ruff (code + docstring lanes), ESLint, Stylelint and the HTML linter run
  per file through a shared worker pool.
- A file carrying diagnostics reports `failed` regardless of the tool's
  exit-code convention, so warn-level findings (e.g. pyrefly
  `--min-severity info`) fail the audit deterministically.
- Optional `stabilize` runs Ruff format/fix cycles before the lint passes.
- `AuditRunner.use_repair()` installs a `FileRepair` called for each file
  after every Ruff cycle; a change triggers another cycle, so repairs end up
  formatted and fixed.
- Output is written to `LINTS_REPORT.json` with per-file commands,
  statuses, durations and diagnostics.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/all_lints/`](../exactus/packages/all_lints/) | [`exactus/tests/packages/all_lints/`](../exactus/tests/packages/all_lints/) | [`DOCS.md`](../exactus/docs/packages/all_lints/DOCS.md) |

[< Packages-actions-action_rest](Packages-actions-action_rest.md) · [Packages index](Packages.md) · [Packages-argument_parser >](Packages-argument_parser.md)
