[Home](Home.md) > [Packages](Packages.md) > visual_cause

# `exactus/packages/visual_cause/` — causal CSS visual-difference analysis

`exactus.packages.visual_cause` renders one page under two CSS targets (or two whole
pages), performs counterfactual browser interventions — removing or
restoring individual rules, declarations and value subexpressions — and
reports which CSS actually *caused* each visual difference, with pixel
evidence. It runs on Playwright/Chromium and Pillow.

## Requirements

```bash
python -m pip install playwright pillow
playwright install chromium
```

## Running

Causal CSS mode — one URL, two CSS targets (each independently a `.css`
file or a directory scanned recursively and concatenated in deterministic
lexical order):

```bash
python -m exactus.packages.visual_cause URL A.css B.css -o css-cause
python -m exactus.packages.visual_cause https://app.test styles/a/ styles/b/
```

Generic DOM-diff mode — direct A/B visual comparison of two URLs without
CSS targets:

```bash
python -m exactus.packages.visual_cause dom-diff URL_A URL_B -o visual-diff
```

`cli.py` dispatches on the first argument: `dom-diff` selects the generic
comparator; anything else runs the causal analyzer.

### Causal-mode flags

| Flag | Default | Meaning |
|---|---|---|
| `url` `css_a` `css_b` | — | Page URL and the two CSS targets (files or directories). |
| `-o`/`--output` | `css-cause` | Output directory. |
| `--width` / `--height` | `1440` / `900` | Viewport in CSS pixels. |
| `--threshold` | `12` | Per-channel pixel difference threshold (0–255). |
| `--max-candidates` | `80` | Causal candidates explored (must be positive on the CLI; `Settings`-level `0` is a smoke mode). |
| `--timeout-ms` | `30000` | Navigation/capture timeout. |
| `--url-b` | `None` | Optional second URL; omit to A/B CSS on the same page. |
| `--native-styles-a` / `--native-styles-b` | off | Keep each side's native author styles under the target CSS. |
| `--parallel-workers` | `4` | Playwright worker count for first-order rule discovery. |
| `--recycle-after` | `24` | Jobs per reusable page before browser state is recycled. |
| `--screenshot-scale` | `2.0` | Device-pixel density for saved screenshot evidence. |
| `--no-extended-selectors` | off | Restrict selector queries to native `querySelectorAll`. |

### DOM-diff flags

`url_a` `url_b`, `-o/--output` (default `visual-diff`), `--width`/`--height`
(`1440`/`900`), `--threshold` (`12`, 0–255), `--merge-gap` (`3`, pixel gap
bridged when merging regions), `--min-area` (`4`, smallest reported region
in px²), `--timeout-ms` (`30000`). Prints `Changed pixels`, `Regions` and
the `report.json` path.

## Python API

```python
from exactus.packages.visual_cause import (
    CssVisualCause, Settings, analyze, CssTarget,
    VisualDomDiff, DomDiffSettings,
)

analyze(settings=Settings(
    url="https://example.test/",
    css_a=Path("baseline.css"),      # file, directory, or None
    css_b=Path("styles/candidate"),  # file, directory, or None
    output=Path("css-cause"),
    width=1440, height=900, threshold=8, max_candidates=200,
    timeout_ms=30000,
    url_b=None,                      # optional second page
    use_native_styles_a=False, use_native_styles_b=False,
    parallel_workers=4, recycle_after=24,
    analysis_budget_seconds=45.0,    # wall-clock bound for causal expansion
    screenshot_scale=2.0,
    advanced_analysis=True,          # higher-order causal phases
    extended_selectors=True,         # inject exactus/packages/extended_selector engine
))

VisualDomDiff(settings=DomDiffSettings(
    url_a="https://a.test/", url_b="https://b.test/",
    output=Path("visual-diff"),
    width=1440, height=900, threshold=8,
    merge_gap=12, min_area=25, timeout_ms=30000,
)).run()
```

- `analyze(settings=, progress=None) -> AnalysisResults` — the structured
  result also serialized into the report. `progress` is a
  `ProgressObserver` called for every phase update.
- `CssTarget.load(source)` — normalizes a file/directory/`None` target;
  directories inject `/* css-visual-cause source: <name> */` markers so
  rules map back to their original file.
- Exported names: `AnalysisResults`, `CssTarget`, `CssVisualCause`,
  `ProgressObserver`, `Settings`, `analyze`, `VisualDomDiff`,
  `DomDiffSettings`, `DomDiffComparisonReport`, `DiffRegion`,
  `DomElement`, `ElementMatch`.

## Outputs

Causal mode writes `a.png`, `b.png`, `diff.png`, `report.json`,
`report.md` plus an `evidence/` crop directory, `progress.json`
(written immediately on start), and `failure.json` + a failure
`report.md` if the run raises. DOM-diff mode writes `a.png`, `b.png`,
annotated `diff.png`, and `report.json` with `changed_pixels`,
`changed_ratio`, connected changed regions and the ranked visible DOM
elements overlapping each region on both sides.

## `report.json` model

- `target_a` / `target_b` — target kind (`native`/`file`/`directory`),
  source, ordered file list and count.
- `element_deltas` — per-element `position`, `size`, `color` and `style`
  before/after values using the complete `getComputedStyle()` result;
  an element can hold several categories.
- `change_trees` — deduplicated forest of changed nodes: `categories`,
  `change_origin` (computed-style and/or propagated), `mechanisms`
  (layout, layout-reflow, text-reflow, paint, transform, stacking,
  unknown), `geometry` (A/B/delta), grouped `computed_style_changes`,
  `causes`, `visual_impact.changed_pixels`, recursive
  `relations.descendants`, and deduplicated sibling/overlap references
  including z-index and estimated paint order.
- `caused_by` — experimental causal edges (not DOM-ancestry inference):
  each changed candidate source element's A-side computed properties are
  restored while rendering B; an edge is emitted only when the target
  measurably moves back toward A. `confidence` is the fraction of the
  measured A/B distance removed; `root_cause` exposes the strongest
  experimental cause.
- `css_provenance` — declaration-level cascade provenance: matched
  selector, rule index/source order, property, authored value
  (incl. `!important`), B-side computed value, improvement, confidence.
  Overridden declarations get no credit; several declarations can share
  credit when the render is genuinely composed.
- `content_change` — DOM text, child-count, `::before`/`::after` content
  differences that explain geometry even with identical CSS.
- `interaction_causes` — bounded pairwise interventions recording member
  improvements, joint improvement, positive synergy and confidence;
  catches threshold/composition effects (`width` + `box-sizing`,
  `display` + grid config, custom-property-driven combinations).
- `css_variables.usage` / `.chains` — transitive `var()` dependency
  chains to their definitions (cycles detected), recorded with source
  order, `!important`, grouping conditions, matched elements and resolved
  values — kept separate so an unchanged winning declaration can still be
  explained by an upstream custom-property change.
- `css_function_provenance` / `css_value_provenance` — nested CSS
  function/expression trees with exact source spans; counterfactual
  rewrites replace only the exact expression span (`calc()`, `min()`,
  `clamp()`, `var()`, transforms, gradients, `color-mix()`, shadows,
  nested expressions) and retain what measurably restores the target.
- `cascade_provenance` — Chromium DevTools CSS domain data: matched rules
  and selector indices, origins/source ranges, inline style, inherited
  chains, pseudo-element rules, keyframes.
- `typed_om_changes` — `computedStyleMap()` serialization
  (`CSSUnitValue`/`CSSKeywordValue`/`CSSUnparsedValue`/`CSSTransformValue`)
  alongside serialized `getComputedStyle()` values.
- `minimal_cause_sets`, `layout_evidence`, `container_queries` — from the
  bounded delta-debugging minimizer and grid/flex/container comparisons
  in `causal.py`.

Snapshots carry deterministic `dom_path`/`parent_path` (not selector
prefixes), traverse open shadow roots, and record intrinsic box signals
(`scrollWidth`/`scrollHeight`/`clientWidth`/`clientHeight`) plus overflow
state to separate CSS-driven geometry from content pressure.

## Runtime behavior

- First-order rule discovery runs on `parallel_workers` Playwright
  workers; each owns its own browser/context/page and pages are recycled
  after `recycle_after` jobs to bound memory. Playwright objects are
  never shared across threads.
- When `exactus/packages/extended_selector` exists on disk its `ExtendedSelector`
  engine is injected into every rendered page: selectors resolve through
  native `querySelectorAll` first, then the engine for structural,
  spatial and predicate operators. `--no-extended-selectors` disables it.
- The causal analyzer navigates with `domcontentloaded` (WebSockets/polling
  make `networkidle` unsuitable there); `dom-diff` waits for `networkidle`.
- `analysis_budget_seconds` bounds long causal searches;
  `max_candidates=0` is an explicit smoke mode that skips counterfactual
  expansion while keeping baseline screenshots, regions, changed DOM
  nodes and reports.

## Limits

The expression parser is structural, not a full CSS Values grammar;
function-subexpression counterfactuals are heuristic (replacing a nested
function with the whole property's computed A value can produce invalid
CSS or conflate operands) — treat their confidence accordingly.
`container_queries` reports query definitions/nesting, not the active
condition; grid/flex track output is resolved computed style, not the
layout engine's sizing algorithm.

## Browser-side assets (`js/`)

Real files (not Python string literals) so JS execution is attributable
in coverage: `prepare.js`, `install_helpers.js`, `rules.js`,
`container_rules.js`, `css_variables.js`, `elements.js`,
`dom_elements.js`, `disable_rule.js`, `disable_declaration.js`,
`disable_declarations.js`, `override_element.js`, `globals.d.ts`
(ambient `__cssCauseSelector`/`__cssCauseQuery(All)` types).

## Examples and tests

```bash
python -m exactus.packages.visual_cause.examples          # serve bundled demo + full analysis
python exactus/packages/visual_cause/examples/validate_results.py  # evidence completeness check
```

`examples/web/` holds the demo page and `a.css`/`b.css` covering direct,
ancestor/inheritance, parent-layout, sibling/layout, descendant,
absolute-overlap, custom-property, transform and non-causal differences.
Tests live in `exactus/tests/packages/visual_cause/`.

## Layout

```
exactus/packages/visual_cause/
├── __init__.py        # public API re-exports
├── __main__.py        # venv bootstrap -> python -m exactus.packages.visual_cause
├── cli.py             # dom-diff / causal dispatch
├── analyzer.py        # CssVisualCause engine, Settings, report writers
├── causal.py          # CSS expression trees, cause-set minimizer, layout evidence
├── dom_diff.py        # VisualDomDiff two-URL pixel/DOM comparison
├── js/                # injected browser scripts
└── examples/          # run.py + validate_results.py + web/ demo
```

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/visual_cause/`](../exactus/packages/visual_cause/) | [`exactus/tests/packages/visual_cause/`](../exactus/tests/packages/visual_cause/) | [`DOCS.md`](../exactus/docs/packages/visual_cause/DOCS.md) |

[< Packages-tree](Packages-tree.md) · [Packages index](Packages.md) · [Packages-watch >](Packages-watch.md)
