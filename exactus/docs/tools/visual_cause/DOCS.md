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

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Compare rendered pages and classify causal visual changes. |
| `arguments.py` | Declare the visual-cause command-line grammar. |
| `core.py` | Orchestrate visual-cause targets, engines, queries, and verdicts. |
| `levels.py` | Resolve visual-cause finding levels from selector matches. |
| `main.py` | Run the visual-cause exactus and write its report bundle. |
| `queries.py` | Bridge visual-cause findings to the ExtendedSelector page engine. |
| `report.py` | Normalize visual-cause results for the shared report bundle. |
| `service.py` | Own local HTTP services used by visual-cause targets. |
| `targets.py` | Normalize and validate configured visual-cause targets. |
| `templates/` | Subdirectory. |

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--target` |  | action='append', default=[] |
| `--url` |  |  |
| `--html` |  | type=Path |
| `--landing` |  | default='index.html' |
| `--url-b` |  |  |
| `--html-b` |  | type=Path |
| `--landing-b` |  | default='index.html' |
| `--css-a` |  | type=Path |
| `--css-b` |  | type=Path |
| `--viewport` |  | action='append', default=[] |
| `--accept` |  | action='append', default=[] |
| `--warning` |  | action='append', default=[] |
| `--fail` |  | action='append', default=[] |
| `--default-level` |  | choices=('accept', 'warning', 'fail'), default='fail' |
| `--fail-on` |  | choices=('findings', 'pixels', 'never'), default='findings' |
| `--threshold` |  | type=int, default=8 |
| `--max-candidates` |  | type=int, default=200 |
| `--parallel-workers` |  | type=int, default=4 |
| `--timeout-ms` |  | type=int, default=30000 |
| `--screenshot-scale` |  | type=float, default=2.0 |
| `--native-styles-a` |  | action='store_true' |
| `--native-styles-b` |  | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Compare rendered pages and classify causal visual changes.


### `arguments.py`

Declare the visual-cause command-line grammar.

- `create_parser() -> ArgumentParser` — Return the visual-cause parser.

### `core.py`

Orchestrate visual-cause targets, engines, queries, and verdicts.

- `class VisualCauseRequest` — One public visual-cause run request.
  - Fields: `targets: tuple[Target, ...]`, `output: Path`
- `class Finding` — One changed element or target-level failure.
  - Fields: `id: str`, `rule: str`, `target: str`, `viewport: str`, `tag: str`, `css_path: str`, `query: str`, `candidates: tuple[dict[str, JsonValue], ...]`, `categories: tuple[str, ...]`, `origins: tuple[str, ...]`, `mechanisms: tuple[str, ...]`, `geometry: dict[str, dict[str, float]]`, `computed_style_changes: dict[str, JsonValue]`, `changed_pixels: int`, `causes: tuple[dict[str, JsonValue], ...]`, `level: Level`, `decided_by: str | None`, `matched: tuple[dict[str, JsonValue], ...]`, `message: str`
- `class TargetResult` — One target and viewport result.
  - Fields: `name: str`, `mode: str`, `viewport: str`, `url_a: str`, `url_b: str`, `changed_pixels: int`, `changed_element_count: int`, `counts: dict[str, int]`, `artifacts: dict[str, str]`, `server_diagnostics: tuple[dict[str, JsonValue], ...]`
- `class VisualCauseResult` — Complete normalized tool result.
  - Fields: `targets: tuple[TargetResult, ...]`, `findings: tuple[Finding, ...]`, `queries: tuple[dict[str, JsonValue], ...]`, `failed: bool`
- `run(*, request: VisualCauseRequest) -> VisualCauseResult` — Run every target and viewport, continuing after target failures.

### `levels.py`

Resolve visual-cause finding levels from selector matches.

- `class QueryMatch` — One configured query and its match cardinality.
  - Fields: `level: Level`, `query: str`, `match_count: int`, `order: int`
- `class LevelDecision` — The winning level and the evidence explaining it.
  - Fields: `level: Level`, `decided_by: str | None`, `matched: tuple[QueryMatch, ...]`
- `class Constants` — Store severity ordering.
  - `severity` = `{'accept': 0, 'warning': 1, 'fail': 2}`
- `decide(*, matches: tuple[QueryMatch, ...], default: Level) -> LevelDecision` — Choose the most severe match and its narrowest winning query.

### `main.py`

Run the visual-cause exactus and write its report bundle.

- `create_parser() -> ArgumentParser` — Return the shared CLI grammar.
- `parse_args(*, arguments: tuple[str, ...] | None=None) -> Namespace` — Resolve configuration, parse arguments, and validate targets.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Run configured visual comparisons and return their gate status.

### `queries.py`

Bridge visual-cause findings to the ExtendedSelector page engine.

- `class QuerySyntaxError` — Report one invalid configured ExtendedSelector query.
- `class QueryResult` — Optimal selector and ranked exact candidates for one element.
  - Fields: `query: str`, `candidates: tuple[dict[str, JsonValue], ...]`
- `class QueryConfig` — Configure one B-side selector query session.
  - Fields: `url: str`, `width: int`, `height: int`, `timeout_ms: int`, `css: str`, `native_styles: bool`
- `class QuerySession` — Own one B-side browser render used for queries and best selectors.
  - `__init__(self, *, config: QueryConfig) -> None` — Initialize a closed query session.
  - `page(self) -> Page` — Return the initialized page.
  - `lint(self, *, query: str) -> tuple[dict[str, JsonValue], ...]` — Return ExtendedSelector diagnostics for one expression.
  - `matching(self, *, css_path: str, query: str) -> tuple[bool, int]` — Return whether the finding element matches and total query count.
  - `best(self, *, css_path: str) -> QueryResult` — Return an exact optimal selector for the finding element.

### `report.py`

Normalize visual-cause results for the shared report bundle.

- `data(*, result: VisualCauseResult, project_root: str) -> dict[str, JsonValue]` — Return the normalized JSON payload.
- `markdown(*, result: VisualCauseResult) -> str` — Render one concise report with target and finding detail.

### `service.py`

Own local HTTP services used by visual-cause targets.

- `class ServedPage` — Resolved browser URL and its optional server log.
  - Fields: `url: str`, `log: Path | None`
- `class LocalServices` — Share servers by directory and terminate only owned processes.
  - `__init__(self, *, artifacts: Path, timeout_ms: int) -> None` — Initialize an empty per-target service registry.
  - `page(self, *, url: str | None, html: Path | None, landing: str, label: str) -> ServedPage` — Return an unchanged remote URL or serve one local source.

### `targets.py`

Normalize and validate configured visual-cause targets.

- `class TargetOptions(Protocol)` — Typed options consumed while resolving targets.
  - Fields: `root: Path`, `target: list[str]`, `url: str | None`, `html: Path | None`, `landing: str`, `url_b: str | None`, `html_b: Path | None`, `landing_b: str`, `css_a: Path | None`, `css_b: Path | None`, `viewport: list[str]`, `accept: list[str]`, `warning: list[str]`, `fail: list[str]`, `default_level: str`, `fail_on: str`, `threshold: int`, `max_candidates: int`, `parallel_workers: int`, `timeout_ms: int`, `screenshot_scale: float`, `native_styles_a: bool`, `native_styles_b: bool`
- `class SourceValues` — Normalized A/B page and stylesheet sources.
  - Fields: `url: str | None`, `html: Path | None`, `url_b: str | None`, `html_b: Path | None`, `css_a: Path | None`, `css_b: Path | None`
- `class Constants` — Store closed target limits.
  - `viewport_parts` = `2`
  - `max_threshold` = `255`
- `class Viewport` — One CSS-pixel viewport.
  - Fields: `width: int`, `height: int`
  - `parse(cls, *, value: str) -> Viewport` — Parse ``WIDTHxHEIGHT`` and reject non-positive dimensions.
  - `label(self) -> str` — Return the stable viewport label.
- `class Target` — One validated page comparison across one or more viewports.
  - Fields: `name: str`, `url: str | None`, `html: Path | None`, `landing: str`, `url_b: str | None`, `html_b: Path | None`, `landing_b: str`, `css_a: Path | None`, `css_b: Path | None`, `viewports: tuple[Viewport, ...]`, `accept: tuple[str, ...]`, `warning: tuple[str, ...]`, `fail: tuple[str, ...]`, `default_level: str`, `fail_on: str`, `threshold: int`, `max_candidates: int`, `parallel_workers: int`, `timeout_ms: int`, `screenshot_scale: float`, `native_styles_a: bool`, `native_styles_b: bool`
  - `mode(self) -> str` — Return the normalized comparison mode.
- `configured(*, start: Path) -> tuple[dict[str, JsonValue], ...]` — Load named target tables with nearest-file name overrides.
- `resolve(*, options: TargetOptions) -> tuple[Target, ...]` — Resolve ad-hoc or named configured targets.

## Dependencies and consumers

- Other packages: [`argument_parser`](../../packages/argument_parser/DOCS.md), [`project_python`](../../packages/project_python/DOCS.md), [`server`](../../packages/server/DOCS.md), [`steps`](../../packages/steps/DOCS.md), [`visual_cause`](../../packages/visual_cause/DOCS.md), [`common`](../common/DOCS.md), [`reports`](../reports/DOCS.md)
- Used by: `__main__.py`, `tests/tools/visual_cause/test_levels.py`, `tests/tools/visual_cause/test_pipeline.py`, `tests/tools/visual_cause/test_report.py`, `tests/tools/visual_cause/test_service.py`, `tests/tools/visual_cause/test_targets.py`

## Tests

Tests live in `exactus/tests/tools/visual_cause/`.

- `test_levels.py` — The most severe matching query decides a finding's level. (3 tests)
  - `test_default_level_applies_without_matches`
  - `test_most_severe_level_wins`
  - `test_narrowest_then_earliest_query_breaks_ties`
- `test_pipeline.py` — Visual-cause runs against real pages through Chromium. (8 tests)
  - `test_invalid_level_query_raises`
  - `test_main_rejects_bad_arguments_and_queries`
  - `test_main_writes_the_report_bundle`
  - `test_run_overlay_directory_css_and_pixel_gate`
  - `test_run_reports_changed_elements_by_level`
  - `test_run_reports_unreadable_sources_as_target_errors`
  - `test_session_can_drop_native_styles`
  - `test_session_queries_and_best_selectors`
- `test_report.py` — The visual-cause report renders findings, counts and evidence. (3 tests)
  - `test_data_counts_findings_by_level`
  - `test_markdown_handles_empty_runs`
  - `test_markdown_lists_findings_and_evidence`
- `test_service.py` — Local page services reuse remote URLs and own the servers they start. (5 tests)
  - `test_adopted_servers_are_never_terminated`
  - `test_missing_and_absent_sources_are_errors`
  - `test_remote_url_is_used_directly`
  - `test_server_that_never_becomes_ready_is_stopped`
  - `test_servers_are_shared_per_directory_and_terminated`
- `test_targets.py` — Visual-cause targets resolve from flags and configuration. (9 tests)
  - `test_ad_hoc_stylesheet_target`
  - `test_configured_targets_resolve_by_name`
  - `test_default_viewport_and_modes`
  - `test_invalid_ad_hoc_options_are_rejected`
  - `test_invalid_configured_targets_are_rejected`
  - `test_missing_source_without_configuration`
  - `test_unnamed_configured_target_is_rejected`
  - `test_viewport_parses_and_labels`
  - `test_viewport_rejects_malformed_values`

<!-- exactus:reference:end -->
