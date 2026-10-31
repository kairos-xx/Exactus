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

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Causal CSS visual-difference analysis. |
| `__main__.py` | Command-line entry point for visual_cause. |
| `analyzer.py` | Find CSS rules that causally change a page's rendered pixels. |
| `causal.py` | CSS expression trees, causal set minimization, and layout evidence. |
| `cli.py` | Command-line entry point for visual_cause. |
| `dom_diff.py` | Compare two web pages visually and map pixel differences to DOM elements. |
| `examples/` | Runnable demonstration for `exactus/packages/visual_cause/`. |
| `js/` | Subdirectory. |

Run it as a module: `python -m exactus.packages.visual_cause`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `url` |  |  |
| `css_a` |  | type=Path |
| `css_b` |  | type=Path |
| `-o, --output` |  | type=Path, default=Path('css-cause') |
| `--width` |  | type=int, default=Constants.default_width |
| `--height` |  | type=int, default=Constants.default_height |
| `--threshold` |  | type=int, default=Constants.default_threshold |
| `--max-candidates` |  | type=int, default=Constants.default_max_candidates |
| `--timeout-ms` |  | type=int, default=30000 |
| `--url-b` | Optional B URL. Omit to compare both CSS targets on the same URL. | default=None |
| `--native-styles-a` | Keep URL A's native author styles before applying target A. | action='store_true' |
| `--native-styles-b` | Keep URL B's native author styles before applying target B. | action='store_true' |
| `--parallel-workers` |  | type=int, default=4 |
| `--recycle-after` |  | type=int, default=24 |
| `--screenshot-scale` |  | type=float, default=2.0 |
| `--no-extended-selectors` | Do not install the packaged extended-selector engine; use only native querySelectorAll for selector queries. | action='store_false', dest='extended_selectors' |
| `url_a` |  |  |
| `url_b` |  |  |
| `-o, --output` |  | type=Path, default=Path('visual-diff') |
| `--width` |  | type=int, default=Constants.default_width |
| `--height` |  | type=int, default=Constants.default_height |
| `--threshold` |  | type=int, default=Constants.default_threshold |
| `--merge-gap` |  | type=int, default=Constants.default_merge_gap |
| `--min-area` |  | type=int, default=Constants.default_min_area |
| `--timeout-ms` |  | type=int, default=Constants.default_timeout_ms |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Causal CSS visual-difference analysis.


### `__main__.py`

Command-line entry point for visual_cause.


### `analyzer.py`

Find CSS rules that causally change a page's rendered pixels.

- `class Constants` — Group module-level constants.
  - `default_width` = `1440`
  - `default_height` = `900`
  - `default_threshold` = `12`
  - `default_max_candidates` = `80`
  - `max_threshold` = `255`
  - `max_relation_elements` = `8`
  - `min_region_pixels` = `2`
  - `geometry_delta_epsilon` = `0.005`
- `class Settings` — Runtime configuration.
  - `url_b` = `None`
  - `use_native_styles_a` = `False`
  - `use_native_styles_b` = `False`
  - `parallel_workers` = `4`
  - `recycle_after` = `24`
  - `analysis_budget_seconds` = `45.0`
  - `screenshot_scale` = `2.0`
  - `advanced_analysis` = `True`
  - `extended_selectors` = `True`
  - Fields: `url: str`, `css_a: Path | str | None`, `css_b: Path | str | None`, `output: Path`, `width: int`, `height: int`, `threshold: int`, `max_candidates: int`, `timeout_ms: int`
- `class CssTarget` — Normalized CSS comparison target.
  - Fields: `source: Path | None`, `files: tuple[Path, ...]`, `css: str`
  - `load(cls, source: Path | str | None) -> CssTarget` — Load one CSS file or recursively combine a directory of CSS files.
  - `manifest(self) -> dict[str, JsonValue]` — Return report metadata for this target.
- `class Rect` — Document-space rectangle.
  - Fields: `x: float`, `y: float`, `width: float`, `height: float`
  - `right(self) -> float` — Return the right edge.
  - `bottom(self) -> float` — Return the bottom edge.
  - `area(self) -> float` — Return the rectangle area.
  - `intersection_area(self, other: Rect) -> float` — Return the area shared with another rectangle.
  - `intersects(self, other: Rect) -> bool` — Return whether two rectangles overlap.
- `class ElementInfo` — DOM element relevant to a visual change.
  - Fields: `selector: str`, `dom_path: str`, `parent_path: str`, `tag: str`, `text: str`, `own_text: str`, `rect: Rect`, `position: str`, `z_index: str`, `computed: dict[str, str]`, `typed_computed: dict[str, JsonValue]`, `before_content: str`, `after_content: str`, `child_count: int`, `scroll_width: float`, `scroll_height: float`, `client_width: float`, `client_height: float`, `overflow_x: str`, `overflow_y: str`
- `class StyleChange` — One computed-style before/after change.
  - Fields: `a: str`, `b: str`
- `class ChangeNode` — One changed DOM element before tree serialization.
  - Fields: `selector: str`, `categories: tuple[str, ...]`, `origins: tuple[str, ...]`, `mechanisms: tuple[str, ...]`, `geometry: dict[str, dict[str, float]]`, `computed_style_changes: dict[str, dict[str, StyleChange]]`, `changed_pixels: int`
- `class RuleInfo` — Browser-parsed CSS style rule.
  - Fields: `index: int`, `selector: str`, `css_text: str`, `declarations: tuple[str, ...]`, `matched: tuple[str, ...]`
- `class Cause` — Counterfactual evidence for one CSS rule.
  - Fields: `index: int`, `selector: str`, `css_text: str`, `declarations: tuple[str, ...]`, `matched: tuple[str, ...]`, `relations: tuple[str, ...]`, `changed_pixels_without_rule: int`, `pixels_explained: int`, `explanation_ratio: float`
- `class InvalidBrowserPayloadError` — Raised when browser JSON does not match the expected schema.
- `class JsonPage(Protocol)` — Typed boundary for JavaScript evaluation.
  - `evaluate(self, expression: str, arg: str | None=None) -> str` — Evaluate JavaScript and return serialized JSON.
- `class CdpSender(Protocol)` — Typed boundary for Chrome DevTools Protocol commands.
- `class ProgressObserver(Protocol)` — Receive bounded analyzer progress updates.
- `class Intervention` — Counterfactual render interventions applied to one page.
  - `disabled_rule` = `None`
  - `element_override` = `None`
  - `disabled_declarations` = `()`
- `class ProvenanceMaps` — Per-selector causal provenance produced by the analysis phases.
  - Fields: `causal_edges: dict[str, list[dict[str, JsonValue]]]`, `declaration_provenance: dict[str, list[dict[str, JsonValue]]]`, `function_provenance: dict[str, list[dict[str, JsonValue]]]`, `cascade_provenance: dict[str, JsonValue]`, `interaction_provenance: dict[str, list[dict[str, JsonValue]]]`, `minimal_sets: dict[str, list[dict[str, JsonValue]]]`
- `class AnalysisResults` — Complete analyzer output bundle used for report generation.
  - Fields: `baseline: int`, `regions: tuple[Rect, ...]`, `affected: tuple[ElementInfo, ...]`, `nodes: tuple[ChangeNode, ...]`, `causes: tuple[Cause, ...]`, `elements_a: tuple[ElementInfo, ...]`, `rules_b: tuple[RuleInfo, ...]`, `evidence_image_a: Image.Image`, `evidence_image_b: Image.Image`, `analysis_image_a: Image.Image`, `analysis_image_b: Image.Image`, `provenance: ProvenanceMaps`
- `class ReportState` — Mutable per-report caches used while writing report.md.
  - Fields: `evidence: Path`, `crop_cache: dict[str, tuple[str, str, str]]`, `nodes_by_selector: dict[str, ChangeNode]`, `elements_b: dict[str, ElementInfo]`
- `class ProvenanceTrial` — Per-node counterfactual context for provenance experiments.
  - Fields: `browser: Browser`, `reference: ElementInfo`, `baseline: float`
- `class DeclarationContext` — Shared lookups for declaration-level counterfactual trials.
  - Fields: `selectors: tuple[str, ...]`, `a_by_selector: dict[str, ElementInfo]`, `b_by_selector: dict[str, ElementInfo]`, `causes_by_index: dict[int, Cause]`
- `browser_script(*, name: str) -> str` — Return one packaged browser script's source text.
- `class CssVisualCause` — Compare two stylesheets and experimentally identify visual causes.
  - `__init__(self, settings: Settings, progress: ProgressObserver | None=None) -> None` — Initialize the analyzer.
  - `run(self) -> AnalysisResults` — Run analysis and return the result used to write the artifacts.
- `analyze(*, settings: Settings, progress: ProgressObserver | None=None) -> AnalysisResults` — Run one visual-cause analysis and return its structured result.
- `main() -> None` — Run the command-line analyzer.

### `causal.py`

CSS expression trees, causal set minimization, and layout evidence.

- `class ValueNode` — One source-preserving CSS expression node.
  - `children` = `()`
  - Fields: `kind: str`, `text: str`, `start: int`, `end: int`
  - `to_json(self) -> dict[str, str | int | list[dict[str, str | int]]]` — Return a shallow JSON-safe node representation.
- `class CssValueParser` — Parse nested CSS functions, arguments, operators, and literal spans.
  - `parse(cls, value: str) -> ValueNode` — Return the expression tree preserving exact source offsets.
  - `walk(cls, node: ValueNode) -> tuple[ValueNode, ...]` — Return all descendants in depth-first order.
  - `replace(value: str, node: ValueNode, replacement: str) -> str` — Replace exactly one source span.
- `class CauseSet` — One experimentally supported minimal sufficient intervention set.
  - Fields: `members: tuple[tuple[int, str], ...]`, `improvement: float`, `confidence: float`, `evaluations: int`, `minimal_within_budget: bool`
- `class CausalMinimizer` — Find bounded minimal sufficient cause sets using group testing.
  - `__init__(self, evaluate: Callable[[tuple[tuple[int, str], ...]], float], budget: int=64, threshold: float=0.8) -> None` — Initialize a memoized counterfactual evaluator.
  - `score(self, members: tuple[tuple[int, str], ...]) -> float | None` — Evaluate a canonical cause set, or None if budget exhausted.
  - `minimize(self, candidates: tuple[tuple[int, str], ...]) -> CauseSet | None` — Reduce a sufficient set via partitions then one-by-one removal.
- `class LayoutEvidence` — Infer grid/flex/container layout explanations from snapshots.
  - `compare(a: dict[str, str], b: dict[str, str]) -> dict[str, dict[str, str]]` — Return changed layout properties and resolved track details.
- `class CssTokenNode` — Lossless token/expression node inside a CSS value.
  - `children` = `()`
  - Fields: `kind: str`, `text: str`, `start: int`, `end: int`
- `class CssValueTokenizer` — Lossless tokenizer for counterfactual CSS value interventions.
  - `parse(cls, value: str) -> tuple[CssTokenNode, ...]` — Tokenize literals, operators, functions, strings, and separators.
  - `flatten(cls, nodes: tuple[CssTokenNode, ...]) -> tuple[CssTokenNode, ...]` — Flatten a value tree while retaining exact source spans.

### `cli.py`

Command-line entry point for visual_cause.

- `main() -> None` — Dispatch between causal-CSS and generic DOM comparison modes.

### `dom_diff.py`

Compare two web pages visually and map pixel differences to DOM elements.

- `class Constants` — Group module-level constants.
  - `default_width` = `1440`
  - `default_height` = `900`
  - `default_threshold` = `12`
  - `default_merge_gap` = `3`
  - `default_min_area` = `4`
  - `default_timeout_ms` = `30000`
  - `max_threshold` = `255`
  - `max_elements_per_region` = `8`
- `class DomElement` — Describe a visible DOM element and its document-space bounds.
  - Fields: `selector: str`, `tag: str`, `element_id: str`, `classes: str`, `text: str`, `rect: Rect`
- `class ElementMatch` — Describe a DOM element associated with one visual-diff region.
  - Fields: `selector: str`, `tag: str`, `element_id: str`, `classes: str`, `text: str`, `bounds: Rect`, `overlap_pixels: float`, `overlap_ratio: float`
- `class DiffRegion` — Describe one connected visual-difference region.
  - Fields: `bounds: Rect`, `changed_pixels: int`, `elements_a: tuple[ElementMatch, ...]`, `elements_b: tuple[ElementMatch, ...]`
- `class ComparisonReport` — Describe the complete result of a visual DOM comparison.
  - Fields: `url_a: str`, `url_b: str`, `screenshot_a: str`, `screenshot_b: str`, `diff_image: str`, `image_width: int`, `image_height: int`, `changed_pixels: int`, `changed_ratio: float`, `regions: tuple[DiffRegion, ...]`
- `class Settings` — Hold immutable command-line settings.
  - Fields: `url_a: str`, `url_b: str`, `output: Path`, `width: int`, `height: int`, `threshold: int`, `merge_gap: int`, `min_area: int`, `timeout_ms: int`
- `class LocatorEvaluator(Protocol)` — Narrow the dynamically typed Playwright evaluation boundary.
  - `evaluate_all(self, expression: str) -> str` — Evaluate JavaScript against all located elements.
- `class VisualDomDiff` — Capture two URLs, compare pixels, and map changes to DOM elements.
  - `__init__(self, settings: Settings) -> None` — Run the comparison and write all artifacts.
  - `run(self) -> ComparisonReport` — Execute capture, image comparison, DOM mapping, and reporting.
- `main(*, arguments: Sequence[str] | None=None) -> int` — Run the command-line visual DOM comparison.

### `examples/__init__.py`

Runnable examples for visual_cause.


### `examples/__main__.py`

Run the visual-cause example with the project virtual environment.


### `examples/run.py`

Run the CSS visual-cause analyzer against its bundled demo.

- `start_demo(*, demo: Path, log: Path) -> tuple[int, str, bool]` — Serve the bundled demo page through the shared loopback server.
- `main() -> None` — Analyze the bundled demo served over loopback HTTP.

### `examples/validate_results.py`

Validate that the demo produced navigable human evidence.

- `class Constants` — Group module-level constants.
  - `evidence_triplet_size` = `3`
- `main() -> None` — Require a non-empty Markdown causal report and resolvable evidence.

## Examples

Runnable demonstration for `exactus/packages/visual_cause/`.

Run the CSS visual-cause analyzer against its bundled demo.

```bash
python -m exactus.packages.visual_cause.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/results/README.md`, `examples/results/a.png`, `examples/results/b.png`, `examples/results/diff.png`, `examples/results/evidence/README.md`, `examples/results/evidence/r0-element-html___body___main_demo-a.png`, `examples/results/evidence/r0-element-html___body___main_demo-b.png`, `examples/results/evidence/r0-element-html___body___main_demo-diff.png`, `examples/results/evidence/r0-element-html___body___main_demo___button_action-a.png`, `examples/results/evidence/r0-element-html___body___main_demo___button_action-b.png`, `examples/results/evidence/r0-element-html___body___main_demo___button_action-diff.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards-a.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards-b.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards-diff.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards___article_card_primary_nth-of-type_1_-a.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards___article_card_primary_nth-of-type_1_-b.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards___article_card_primary_nth-of-type_1_-diff.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards___article_card_primary_nth-of-type_1____h2-a.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards___article_card_primary_nth-of-type_1____h2-b.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards___article_card_primary_nth-of-type_1____h2-diff.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards___article_card_primary_nth-of-type_1____p-a.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards___article_card_primary_nth-of-type_1____p-b.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards___article_card_primary_nth-of-type_1____p-diff.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards___article_card_secondary_nth-of-type_2_-a.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards___article_card_secondary_nth-of-type_2_-b.png`, `examples/results/evidence/r0-element-html___body___main_demo___section_cards___article_card_secondary_nth-of-type_2_-diff.png`, `examples/results/progress.json`, `examples/results/report.json`, `examples/results/report.md`, `examples/run.py`, `examples/validate_results.py`, `examples/web/README.md`, `examples/web/a.css`, `examples/web/b.css`, `examples/web/index.html`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md), [`server`](../server/DOCS.md)
- Used by: `tests/packages/visual_cause/test_advanced.py`, `tests/packages/visual_cause/test_analyzer_helpers.py`, `tests/packages/visual_cause/test_cli_coverage.py`, `tests/packages/visual_cause/test_css_targets.py`, `tests/packages/visual_cause/test_dom_diff.py`, `tests/packages/visual_cause/test_dual_url_tokens.py`, `tests/packages/visual_cause/test_examples.py`, `tests/packages/visual_cause/test_full_pipeline.py`, `tests/packages/visual_cause/test_runtime_lifecycle.py`, `tests/packages/visual_cause/test_token_cascade.py`, `tests/packages/visual_cause/test_typed_parallel.py`, `tools/visual_cause/core.py`

## Tests

Tests live in `exactus/tests/packages/visual_cause/`.

- `test_advanced.py` — Tests for advanced CSS causal analysis primitives. (8 tests)
  - `test_budget_and_unsatisfied`
  - `test_layout_evidence`
  - `test_lossless_tokenizer_nested_strings_and_flatten`
  - `test_minimize_joint_only`
  - `test_minimizer_empty_reduction_and_cache`
  - `test_nested_function_ast`
  - `test_parser_comments_escapes_and_unclosed_constructs`
  - `test_quoted_function_content`
- `test_analyzer_helpers.py` — Focused behavioral coverage for analyzer helper logic. (20 tests)
  - `test_budget_navigation_and_side_url`
  - `test_candidate_order_provenance_and_numeric_helpers`
  - `test_cascade_provenance_cdp_success_and_error`
  - `test_change_forest_serializes_relations`
  - `test_human_summary_and_crops`
  - `test_interactions_minimal_sets_and_causal_edges`
  - `test_missing_target_and_trial_budget_break`
  - `test_pixel_regions_and_change_classification`
  - `test_rect_url_and_declaration_helpers`
  - `test_render_context_wrapper_and_browser_fallback`
  - `test_render_page_high_density_and_interventions`
  - `test_root_cause_paint_and_contributors`
  - `test_rule_and_element_payload_validation`
  - `test_run_analysis_orchestration_and_failure`
  - `test_run_failure_path_and_provenance_skips`
  - `test_serial_rule_trials_with_recyclable_page`
  - `test_structural_empty_and_content_delta_branches`
  - `test_structural_image_analysis_and_rich_report`
  - `test_structural_relationships_and_ranking`
  - `test_variable_chains_cycles_and_content_delta`
- `test_browser_js.py` — Validate every browser-side JavaScript source asset. (2 tests)
  - `test_all_browser_js_assets_are_discovered`
  - `test_browser_js_parses`
- `test_cli_coverage.py` — Coverage for command entry points. (4 tests)
  - `test_module_entrypoint_calls_analyzer_main`
  - `test_module_entrypoint_dispatches_dom_diff`
  - `test_settings_parses_valid_cli`
  - `test_settings_rejects_invalid_dimensions`
- `test_css_targets.py` — Tests for CSS file/directory comparison targets. (4 tests)
  - `test_directory_target_is_recursive_and_deterministic`
  - `test_directory_without_css_fails`
  - `test_file_target`
  - `test_non_css_file_fails`
- `test_dom_diff.py` — Coverage for generic two-URL visual DOM comparison. (6 tests)
  - `test_dom_diff_cli_settings_and_validation`
  - `test_dom_diff_helpers_normalize_threshold_and_merge_regions`
  - `test_dom_diff_main_writes_summary`
  - `test_dom_diff_parses_and_ranks_elements`
  - `test_dom_diff_run_writes_original_report_contract`
  - `test_dom_diff_settings_are_publicly_exported`
- `test_dual_url_tokens.py` — Tests for dual URL and token CSS analysis. (2 tests)
  - `test_dual_url`
  - `test_nested_tokens`
- `test_examples.py` — Coverage and behavior tests for bundled runnable examples. (9 tests)
  - `test_example_run_builds_demo_settings`
  - `test_example_run_module_executes_as_a_script`
  - `test_example_run_reports_a_server_that_never_ready`
  - `test_examples_run_module_executes_as_a_script`
  - `test_examples_run_module_reuses_the_recorded_server`
  - `test_validate_results_rejects_incomplete_evidence_triplet`
  - `test_validate_results_rejects_incomplete_markdown`
  - `test_validate_results_rejects_zero_missing_and_empty_evidence`
  - `test_validate_results_success_and_failures`
- `test_full_pipeline.py` — End-to-end coverage for the bounded causal-analysis pipeline. (1 tests)
  - `test_tiny_full_pipeline`
- `test_runtime_lifecycle.py` — Regression tests for bounded runtime and report lifecycle. (2 tests)
  - `test_failure_report_is_always_persisted`
  - `test_zero_candidates_is_explicit_quick_mode`
- `test_support.py` — Validate the shared visual_cause test helpers. (5 tests)
  - `test_constant_and_dig_helpers`
  - `test_expectation_helpers_accept_good_values`
  - `test_fail_and_expectation_failures`
  - `test_private_helpers_read_write_and_call`
  - `test_require_helpers_narrow_and_reject`
- `test_token_cascade.py` — Tests for exact CSS value nodes. (2 tests)
  - `test_exact_span_replacement`
  - `test_nested_value_nodes`
- `test_typed_parallel.py` — Tests for Typed OM and parallel settings surfaces. (1 tests)
  - `test_parallel_defaults`

<!-- exactus:reference:end -->
