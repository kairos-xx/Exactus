[Home](Home.md) > [Tools](Tools.md) > visual_cause

# tools/visual_cause/

Visual-comparison gate: renders configured page or stylesheet targets at
one or more viewports through the `exactus.packages.visual_cause` engine, classifies
every changed element with ExtendedSelector queries, decides per-finding
verdict levels, and writes the standard Exactus `result.json` /
`result.md` / `result_web` bundle. Exit status is `1` when any finding
meets the failure policy.

## Running

```bash
exactus visual_cause --help
exactus visual_cause --html site --css-b proposed.css --viewport 1440x900
exactus visual_cause --url https://a.test --url-b https://b.test
exactus visual_cause --target landing --target header   # named config targets
```

`--target NAME` selects `[[tool.exactus.visual_cause.targets]]` entries
(repeatable); ad-hoc source flags (`--url`, `--html`, `--url-b`,
`--html-b`, `--css-a`, `--css-b`) form a single `adhoc` target and must
not be mixed with `--target`.

## Comparison modes

`Target.mode` normalizes each target to one of three shapes:

- `page` — `url-b`/`html-b` set: two rendered pages diffed directly.
- `stylesheets` — `css-a` + `css-b` on one page: causal CSS comparison.
- `overlay` — single side with only `css-b`: proposed styles over the
  page's native styles.

Each target needs exactly one of `url`/`html` (A side), and exactly one
of (`url-b`/`html-b`) or `css-b` (B side); a B page cannot combine with
CSS sides.

## CLI flags

Common surface (`add_common_arguments`): optional `root` positional,
`-o/--output-dir` (default `EXACTUS_RESULTS/VISUAL_CAUSE`), repeatable
`--include`/`--exclude` globs, `--context-lines N`, `--dry/--dry-run`.

Tool flags (`arguments.py`):

| Flag | Default | Meaning |
|---|---|---|
| `--target` | `[]` (repeatable) | Named configured targets. |
| `--url` / `--html` / `--landing` | `index.html` | A-side page source; `html` folders serve `landing`. |
| `--url-b` / `--html-b` / `--landing-b` | `index.html` | B-side page source. |
| `--css-a` / `--css-b` | — | A/B stylesheet file or directory. |
| `--viewport` | `[]` (repeatable) | `WIDTHxHEIGHT`; config targets default to `1440x900`. |
| `--accept` / `--warning` / `--fail` | `[]` (repeatable) | ExtendedSelector queries assigning verdict levels to matched findings. |
| `--default-level` | `fail` | Level for findings no query matched: `accept`/`warning`/`fail`. |
| `--fail-on` | `findings` | Failure gate: `findings`, `pixels`, or `never`. |
| `--threshold` | `8` | Pixel difference threshold, 0–255. |
| `--max-candidates` | `200` | Causal candidates explored per target. |
| `--parallel-workers` | `4` | Worker processes rendering comparisons. |
| `--timeout-ms` | `30000` | Per-render timeout. |
| `--screenshot-scale` | `2.0` | Device-pixel ratio for screenshot evidence. |
| `--native-styles-a` / `--native-styles-b` | off | Keep each side's native styles under the target CSS. |

All keys are also writable under `[tool.exactus.visual_cause]` in
`pyproject.toml` (kebab-case or snake_case), and per-target inside
`[[tool.exactus.visual_cause.targets]]` — relative paths in a target
resolve against the config file's own directory, so targets survive being
declared in nested configs.

## Configured targets

```toml
[[tool.exactus.visual_cause.targets]]
name = "landing"
html = "site"                    # or url = "https://..."
css-a = "css/base.css"
css-b = "css/proposed.css"
viewports = ["1440x900", "390x844"]
warning = ["header .banner"]     # ExtendedSelector queries -> levels
fail = [".modal"]
fail-on = "findings"             # findings | pixels | never
threshold = 8
```

Per-target keys: `name`, `url`/`html`/`landing`, `url-b`/`html-b`/
`landing-b`, `css-a`/`css-b`, `viewports`, `accept`/`warning`/`fail`,
`default-level`, `fail-on`, `threshold`, `max-candidates`,
`parallel-workers`, `timeout-ms`, `screenshot-scale`,
`native-styles-a`/`native-styles-b`. Missing values fall back to the
CLI/table-level options.

## Verdict levels and queries

`levels.py` severity order is `accept` < `warning` < `fail`. For each
changed element every configured query is evaluated on the rendered B
page; `decide()` picks the most severe matched level, ties breaking
toward fewer matches then earlier configured order; unmatched findings
get `default-level`. `fail-on` then gates the run: `findings` fails when
any finding is `fail`-level, `pixels` fails on changed pixels, `never`
never fails.

`queries.py` runs each B-side page in a `QuerySession` (its own
Playwright browser), injects the `exactus/packages/extended_selector` engine so
configured queries support structural/spatial/predicate operators, and
produces each finding's best selector plus ranked `candidates`
(`QueryResult`). `QuerySyntaxError` surfaces as a parser error.

## Result and output

`core.run(request)` orchestrates per-target/per-viewport comparisons,
owns local HTTP serving for `html` sources (`service.py` →
`exactus.packages.server.local`, with `server_diagnostics` from
`parse_server_log`), and returns a `VisualCauseResult`:

- `targets` — per `name`/`mode`/`viewport`: `url_a`/`url_b`,
  `changed_pixels`, `changed_element_count`, per-level `counts`,
  report-relative `artifacts` (screenshots, engine reports),
  `server_diagnostics`.
- `findings` — one `Finding` per changed element: `id`, `rule`,
  `target`, `viewport`, `tag`, `css_path`, best `query` + `candidates`,
  `categories`/`origins`/`mechanisms`, `geometry`,
  `computed_style_changes`, `changed_pixels`, causal `causes`,
  decided `level`, `decided_by`, `matched`, `message`.
- `queries` — configured-query match summaries.
- `failed` — the gate verdict; `main()` returns it as the exit code.

`report.py` normalizes this to the shared bundle; `ReportBundle.write`
emits canonical `result.json` (semantic source), `result.md` (rendered
through `templates/markdown/template.md` + `mapping.json`), and the
offline `result_web/` bundle.

## Files

| File | Description |
|---|---|
| `arguments.py` | `create_parser()` — common + tool CLI grammar. |
| `targets.py` | `Target`/`Viewport`/`resolve()` — ad-hoc and `[[tool.exactus.visual_cause.targets]]` normalization/validation. |
| `service.py` | `LocalServices`/`ServedPage` — loopback HTTP serving for `html` sources. |
| `core.py` | `run(request)` — per-target engine runs, query classification, finding construction. |
| `queries.py` | `QuerySession`/`QueryConfig`/`QueryResult` — ExtendedSelector bridge on the rendered B page. |
| `levels.py` | `decide()` — most-severe level resolution with tie-breaking. |
| `report.py` | `data()`/`markdown()` — normalization for the shared report bundle. |
| `main.py` | `parse_args()`/`main()` — config+target resolution, run, bundle write, exit code. |
| `templates/markdown/` | `template.md` + `mapping.json` consumed by `tools/reports/render.py`. |

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/tools/visual_cause/`](../exactus/tools/visual_cause/) | [`exactus/tests/tools/visual_cause/`](../exactus/tests/tools/visual_cause/) | [`DOCS.md`](../exactus/docs/tools/visual_cause/DOCS.md) |

[< Tools-self_test](Tools-self_test.md) · [Tools index](Tools.md)
