# CSS Visual Cause Demo

A causal visual CSS differential analyzer.

## Install

```bash
python -m pip install playwright pillow
playwright install chromium
```

## Run the bundled demo

```bash
python run_demo.py
```

The runner starts a local server on an ephemeral port, renders the same HTML
with `demo/a.css` and `demo/b.css`, performs causal rule interventions, writes
the results to `demo-results/`, and shuts the server down.

The demo deliberately contains direct, ancestor/inheritance, parent-layout,
sibling/layout, descendant, absolute-overlap, custom-property, transform, and
non-causal/unmatched CSS differences.

## Analyze your own page

```bash
python -m exactus.packages.visual_cause URL A.css B.css -o css-cause
```

Outputs: `a.png`, `b.png`, `diff.png`, and `report.json`.

`report.json` ranks rules by counterfactual evidence: each candidate B rule is
removed in a fresh render and the tool measures how many baseline-different
pixels disappear.

## Compare two rendered pages without CSS targets

For a direct A/B visual comparison of two URLs, use the generic DOM-diff mode:

```bash
python -m exactus.packages.visual_cause dom-diff URL_A URL_B -o visual-diff
```

The command writes `a.png`, `b.png`, an annotated `diff.png`, and a
`report.json` containing `changed_pixels`, `changed_ratio`, connected changed
regions, and the ranked visible DOM elements overlapping each region on both
sides. `--merge-gap` controls how close changed pixels must be to merge into
one region, and `--min-area` filters small regions. The same workflow is
available through `VisualDomDiff` and `DomDiffSettings` in the Python API.

## Element delta classification

`report.json` also contains `element_deltas`. For every visually affected DOM
element that exists in both renders it reports:

- `position`: exact `x` / `y` movement.
- `size`: exact width / height delta.
- `color`: before/after values for computed color-related properties.
- `style`: before/after values for every other changed computed-style property.

An element can belong to several categories simultaneously. The computed-style
comparison uses Chromium's complete `getComputedStyle()` result rather than a
fixed hand-picked property list.

## Causal change forest

The primary report structure is now `change_trees`: an array of isolated,
deduplicated trees. The analyzer keeps relationship information internally as
a graph, then chooses DOM changed-ancestor ownership for recursive tree
serialization so each changed element appears exactly once.

Each node contains:

- `categories`: position, size, color, style.
- `change_origin`: computed-style and/or propagated.
- `mechanisms`: layout, layout-reflow, text-reflow, paint, transform, stacking,
  or unknown.
- `geometry`: A/B/delta position and size.
- `computed_style_changes`: layout, box_model, typography, color, paint,
  transform, visibility, stacking, and other.
- `causes`: experimentally supported CSS rules associated with the node.
- `visual_impact.changed_pixels`: changed pixels inside the element rectangle.
- recursive `relations.descendants`.
- deduplicated sibling and overlap references, including overlap positioning,
  z-index, and estimated paint order.

Ancestors are represented by tree nesting instead of being recursively repeated,
which prevents cyclic JSON.

## Experimental causal chains

The report now includes `caused_by` on every change-tree node. These edges are
not inferred only from DOM ancestry. For each changed candidate source element,
the analyzer restores its changed A-side computed properties while rendering B,
then measures every other changed element against its A-side state.

A `caused_by` edge is emitted only when neutralizing the source measurably moves
the target back toward A. This applies to geometry, layout/reflow, typography,
color/paint, transforms, visibility, stacking, and arbitrary computed-style
changes. Edges may therefore point ancestor-to-descendant, descendant-to-
ancestor, sibling-to-sibling, overlap-to-covered-element, or indirect.

`confidence` is the fraction of the target's measured A/B state distance
removed by that intervention. `root_cause` exposes the strongest experimentally
supported CSS rule associated with a node when one is available.

## Cascade provenance and content causality

Each changed node now contains `css_provenance`. Candidate declarations are
taken from rules that actually match the element in Chromium, then each
declaration is independently removed from stylesheet B and the element is
remeasured against A. A declaration is reported only when removing it restores
the target toward A. This means overridden/lower-precedence declarations do not
receive causal credit, while multiple declarations can be retained when the
rendered result is genuinely composed from several CSS inputs.

The provenance record contains the matched selector, rule index/source order,
property, authored value (including `!important` when present), B-side computed
value, measured improvement and confidence. `root_cause` prefers the strongest
declaration-level experimental result.

`content_change` independently records DOM text, child-count, `::before`
content, and `::after` content changes. Consequently, geometry/reflow can be
explained by intrinsic content changes even when the CSS declarations and
computed styles are otherwise identical.

## Interaction causes

The analyzer no longer assumes that causes are independent. After single
declaration ablation it performs bounded pairwise interventions among the most
relevant declarations for each changed element. `interaction_causes` records a
pair only when removing/restoring the pair together explains more of the A/B
difference than either member explains independently.

Each interaction contains its members, each member's individual improvement,
joint improvement, positive synergy, and confidence. This detects threshold and
composition effects such as width + box-sizing, display + grid configuration,
parent constraints + child sizing, and combinations of custom-property-driven
declarations. `root_cause` can therefore be either a single declaration or a
synergistic cause-set.

## Advanced DOM and structural snapshotting

Element snapshots now carry a deterministic structural `dom_path` and
`parent_path` in addition to a human-readable selector. Structural relation
classification uses these paths rather than selector-string prefix heuristics.
The snapshot walker traverses the document and open shadow roots, so visible
elements inside web components can participate in geometry/style/content
analysis.

Content analysis now separates aggregate descendant text from direct text-node
content and records intrinsic box signals (`scrollWidth`, `scrollHeight`,
`clientWidth`, `clientHeight`) plus overflow state. This makes it possible to
distinguish CSS-driven geometry from intrinsic-content pressure, clipping, and
text/content expansion much more accurately.

## CSS custom-property provenance

Every changed element now reports `css_variables.usage` and
`css_variables.chains`. The browser-side collector walks nested stylesheet
rules, records custom-property definitions and every declaration containing
`var(...)`, preserves source order, `!important`, active grouping conditions,
matched elements, and the computed value resolved on each element.

Dependency chains are expanded transitively, so a consumer such as
`width: var(--component-width)` can be traced through
`--component-width -> --layout-width -> --density-width` to the definitions
that feed it. Cycles are detected explicitly. This provenance is kept separate
from ordinary declaration provenance so an unchanged winning declaration can
still be explained by an upstream custom-property change.

## CSS function/subexpression provenance

Changed nodes now include `css_function_provenance`. Nested CSS functions are
parsed with exact source spans and argument boundaries. The analyzer performs
counterfactual rewrites of individual function expressions and rerenders the
page, retaining only expressions whose replacement measurably restores the
target toward A.

This works recursively for nested value expressions such as `calc()`, `min()`,
`max()`, `clamp()`, `var()`, transforms, filters, gradients, `color-mix()`,
shadows, and other CSS function syntax. Results include the exact function,
source expression, arguments, nesting depth, source span, counterfactual value,
measured improvement, and confidence. Nested positive results therefore narrow
a causal declaration to the smallest tested function expression that explains
the visual change.

## Advanced causal search (current scope)

`causal_advanced.py` adds a source-span-preserving CSS expression tree (nested
functions, arguments, literals and operators), a memoized bounded delta-debugging
minimizer for *joint* declaration causes, and grid/flex/container computed-style
comparisons. `report.json` now includes `minimal_cause_sets`, `layout_evidence`,
and `container_queries` (query metadata and nesting, not a proof of the active
container condition). The minimizer searches across rules with matched elements,
not only declarations directly matching the affected node, and reports whether
minimality was established within the evaluation budget.

**Important limits:** the expression parser is structural, not a complete CSS
Values grammar; CSS Typed OM can supplement numeric evaluation in Chromium.
The existing function-subexpression counterfactual is heuristic, because
replacing a nested function with the *entire property*'s computed A value can
produce invalid CSS or conflate multiple operands. Its confidence must not be
interpreted as exact token-level proof. The container query collector reports
query definitions; evaluating active conditions requires tracking the actual
query container and query features. Grid/flex track output is resolved computed
style, not a reconstruction of the layout engine's sizing algorithm. Browser
navigation is environment-dependent; browser unit smoke tests can use
`page.set_content()` where navigation is blocked.

## A/B target API: CSS file or CSS folder

A comparison always uses one page URL and two CSS targets: target A and target
B. Each target may independently be either a single `.css` file or a directory.

Directories are scanned recursively for `.css` files. Files are concatenated in
deterministic lexical order by relative POSIX path, so the resulting cascade is
stable and reproducible. Non-CSS files are ignored. An empty CSS directory is
rejected.

Existing Python API calls remain valid:

```python
CssVisualCause(
    settings=Settings(
        url="https://example.test/",
        css_a=Path("baseline.css"),
        css_b=Path("candidate.css"),
        ...
    )
).run()
```

Folder comparison uses the same API:

```python
CssVisualCause(
    settings=Settings(
        url="https://example.test/",
        css_a=Path("styles/version-a"),
        css_b=Path("styles/version-b"),
        ...
    )
).run()
```

A file and a folder may also be mixed. The CLI has identical semantics:

```text
python -m exactus.packages.visual_cause URL TARGET_A TARGET_B
```

`report.json` contains `target_a` and `target_b` manifests with target kind,
source path, ordered CSS files, and file count.

## CSS Typed OM semantic values

The element snapshot now records both serialized `getComputedStyle()` values and
the browser's `computedStyleMap()` representation. `CSSUnitValue`,
`CSSKeywordValue`, `CSSUnparsedValue`, iterable typed values, and
`CSSTransformValue` components are serialized into `typed_om_changes`.

Typed OM is used as the semantic browser grammar where Chromium exposes typed
values. CSS syntax that the platform intentionally exposes as
`CSSUnparsedValue` remains losslessly represented by the source-preserving
parser; this is necessary for custom properties and unsupported grammar rather
than pretending Typed OM exposes an AST it does not provide.

## Parallel recyclable Playwright workers

First-order rule discovery now runs concurrently across `parallel_workers`
(default 4). Each worker owns its own Playwright instance, Chromium browser,
context, and reusable page; Playwright objects are never shared across threads.
The page is navigated and reused for multiple counterfactual interventions and
is recycled after `recycle_after` jobs (default 24) to bound browser state and
memory accumulation.

CLI controls:

```text
--parallel-workers N
--recycle-after N
--no-extended-selectors
```

## Extended selector engine

When `exactus/packages/extended_selector` exists on disk, the analyzer injects its
`ExtendedSelector` engine into every rendered page. CSS selector queries
resolve through native `querySelectorAll` first and fall back to the engine
for extended syntax (structural, spatial, and predicate operators). The
engine is enabled by default whenever the packaged path is found;
`--no-extended-selectors` restricts queries to native `querySelectorAll`.

## Chromium cascade provenance

Changed nodes now include `cascade_provenance` from Chromium's DevTools CSS
domain: matched rules and matching selector indices, origins/source ranges,
inline style, inherited chains, pseudo-element rules, keyframes, and computed
properties.

## Exact value-node interventions

`css_value_provenance` replaces the coarse whole-computed-value function
experiment. Functions, arguments, literals, operators, and nested expressions
are aligned to structurally compatible A-side authored nodes and only the exact
source span is replaced. Incompatible trees are skipped.

## Human-readable CSS-first report

Every run now also writes `report.md` and an `evidence/` directory. Unlike the
element-first causal tree in `report.json`, this view is inverted:

```text
CSS file
  rule
    causal property
      affected element
        what changed
        A / B / difference crops
        other contributing properties
        causal value fragments
```

Only declarations with positive counterfactual evidence are included.
Interaction partners come from experimentally detected interaction sets and
minimal sufficient cause sets.

For recursive CSS targets, rules are mapped back to the original file using the
source markers inserted while the target is assembled, so the report remains
organized by the user's actual CSS files rather than by the combined temporary
stylesheet.

## Mandatory coverage gate

Coverage is a release gate, not an informational metric:

- every source file must have at least **80%** coverage;
- aggregate project coverage must be at least **90%**;
- JavaScript coverage must remain enabled;
- every file under `browser_js/` is explicitly discovered by the test suite,
  so adding an untested browser program cannot silently pass because Python
  coverage is high.

The browser programs were moved out of Python string literals into
`browser_js/*.js`. This is important for Playwright testing: Exactus can now
attribute JavaScript execution to real source files instead of the browser code
being invisible inside Python constants. Playwright functional tests therefore
contribute evidence to the JS side of the combined coverage report.

## Runtime/lifecycle guarantees

The bundled `run_demo.py` is intentionally a fast smoke test. It uses the demo
HTML directly rather than starting a temporary HTTP server, so browser policy
or server teardown cannot make the demo appear to hang. It performs the A/B
baseline, visual/DOM change analysis and writes the complete baseline report.

Long causal searches are bounded by `Settings.analysis_budget_seconds`.
Navigation waits for `domcontentloaded`, not `networkidle`, because WebSockets,
polling and long-lived requests make `networkidle` unsuitable for arbitrary
applications.

Every run immediately writes `progress.json` and emits phase messages. A
runtime exception writes both `failure.json` and a human-readable failure
`report.md` before it is re-raised. Thus a failed browser launch/navigation is
diagnosable instead of silently leaving an empty output directory.

`max_candidates=0` is an explicit quick/smoke mode: it skips counterfactual
causal expansion while retaining baseline screenshots, visual regions, changed
DOM nodes and reports.

## Package layout

```text
exactus/packages/visual_cause/
  __init__.py
  __main__.py
  analyzer.py
  causal.py
  dom_diff.py
  js/
  examples/
    run.py
    validate_results.py
    web/
      index.html
      a.css
      b.css
    results/
exactus/tests/packages/visual_cause/
```

Run the module with `python -m exactus.packages.visual_cause`. Run the bundled evidence
example with `python -m exactus.packages.visual_cause.examples.run`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Causal CSS visual-difference analysis.
- [`__main__.py`](__main__.py) — Command-line entry point for visual_cause.
- [`analyzer.py`](analyzer.py) — Find CSS rules that causally change a page's rendered pixels.
- [`causal.py`](causal.py) — CSS expression trees, causal set minimization, and layout evidence.
- [`cli.py`](cli.py) — Command-line entry point for visual_cause.
- [`dom_diff.py`](dom_diff.py) — Compare two web pages visually and map pixel differences to DOM elements.

### Subdirectories

- [`examples/`](examples/README.md) — Runnable demo for the CSS visual cause analyzer.
- [`js/`](js/README.md) — Browser-side JavaScript assets injected by the analyzer during rendering and intervention runs.

<!-- exactus:inventory:end -->
