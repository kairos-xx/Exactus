[Home](Home.md) › Guides › Reports

# Reports

Every tool emits the same normalized bundle under
`EXACTUS_RESULTS/<TOOL>/` at the project root (override via
`--output-dir` or `[tool.exactus] reports-dir`).

## Bundle layout

```text
EXACTUS_RESULTS/
├── .runtime/          shared run registry (SQLite, capped by
│                      --runtime-max-runs / --runtime-max-size)
├── LINTS/
│   ├── result.md      human-readable findings report
│   ├── result.json    machine-readable report (same findings)
│   ├── index.html     rendered web report
│   ├── ARTIFACTS/     stdout.log, stderr.log, stderr.json,
│   │                  @activity.json live-progress file
│   └── FILES/         optional archive of flagged sources
│                      (--collect-files: README, TREE.txt, files.zip)
├── COVERAGE_TESTS/    COVERAGE/, TESTS/, TESTS/<group>/, ARTIFACTS/
└── <TOOL>/            one tree per tool
```

## Normalized sections

Each `result.json` carries the same top-level contract:
`summary` (status, counts, timing, host), `scope` (files/tools/roots),
`findings` (normalized diagnostics: file, line, code, severity,
message), and `extension` (tool-specific payload). `group_final` merges
per-tool results into aggregate pipeline reports.

## Comparisons

Reports diff against the previous report even after a clean rerun:
added / resolved / unchanged findings, deltas by source, category and
rule, numeric subsection metrics, and per-tool detail in pipeline
reports. Deltas use each metric's units; coverage changes are reported
in percentage points. The first run establishes the baseline; missing
history renders `N/A`.

## Gates

| Gate | Default | Override |
|---|---|---|
| Total coverage | 90% | `--fail-under PERCENT` |
| Per-file coverage | 80% | `--per-file-minimum PERCENT` |
| Findings | any `error` severity fails | per-tool config |

---

[Installation](Installation.md) · [CLI](CLI.md) · [Architecture](Architecture.md) · [Reports](Reports.md) · [Testing](Testing.md) · [Releasing](Releasing.md) · [Conventions](Conventions.md)
