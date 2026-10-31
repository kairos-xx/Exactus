# scene_description/

Rendered semantic scene descriptions and Visual Cause integration: captures
a semantic scene graph from a rendered page, describes deterministic A/B
differences between two scenes in human-readable language, and enriches an
existing Visual Cause report with those descriptions. Report-independent —
nothing here imports `exactus.tools`.

Run standalone with `python -m exactus.packages.scene_description <report> <scene-a> <scene-b> -o <output>`.

## Boundaries

`SceneDescriptor` talks to the browser only through the narrow `PageLike`
protocol (`add_script_tag`, `evaluate`), so tests drive it with in-memory
fakes and Playwright covers it end to end. `describe()` installs the runtime
on demand and returns the manifest verbatim.

`SceneChangeDescriber` matches elements across scenes by `selector` (or the
`visualCauseSelector` alias) and applies a geometry tolerance so sub-pixel
noise produces no output. All comparisons are deterministic: selector order
is sorted and every detail line is derived from stable fields.

`VisualCauseDescriber.enrich()` never mutates the input report — it returns a
deep copy with a `change_description` block, per-node `visual_description`
entries for matched change trees, and a summary sentence.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Rendered semantic scene descriptions and Visual Cause integration. |
| `__main__.py` | Command-line enrichment of an existing Visual Cause report. |
| `capture.py` | Playwright bridge for the rendered semantic scene descriptor. |
| `changes.py` | Deterministically describe visual changes between semantic scene graphs. |
| `cli.py` | Command-line enrichment of an existing Visual Cause report. |
| `examples/` | Examples for scene_description. |
| `js/` | Provide unified evidence js content. |
| `models.py` | Typed data models for rendered-scene change descriptions. |
| `visual_cause.py` | Adapters enriching Visual Cause reports with rendered scenes. |

Run it as a module: `python -m exactus.packages.scene_description`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `report` |  | type=Path |
| `scene_a` |  | type=Path |
| `scene_b` |  | type=Path |
| `-o, --output` |  | required=True, type=Path |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `capture.py`

Playwright bridge for the rendered semantic scene descriptor.

- `class PageLike(Protocol)` — Narrow synchronous Playwright page boundary used by the descriptor.
  - `add_script_tag(*, content: str) -> JsonValue` — Inject JavaScript into the current document.
  - `evaluate(*, expression: str, arg: JsonValue=None) -> JsonValue` — Evaluate JavaScript in the current document.
- `class SceneDescriptor` — Capture a semantic scene graph from a rendered Playwright page.
  - `install(*, page: PageLike) -> None` — Install the descriptor runtime into the current document.
  - `describe(*, page: PageLike, selector: str='html', options: DescriptionOptions | None=None) -> dict[str, JsonValue]` — Describe one rendered DOM subtree.

### `changes.py`

Deterministically describe visual changes between semantic scene graphs.

- `class Constants` — Group module-level constants.
  - `geometry_tolerance` = `0.01`
- `class ElementChange` — Machine and human description for one matched rendered element.
  - Fields: `selector: str`, `summary: str`, `details: tuple[str, ...]`
  - `as_json() -> dict[str, JsonValue]` — Serialize the description for report enrichment.
- `class SceneChangeDescriber` — Compare descriptor manifests using stable element selectors.
  - `frame(element: dict[str, JsonValue]) -> dict[str, float]` — Extract numeric viewport-frame geometry from one element.
  - `describe_element(*, selector: str, scene_a: dict[str, JsonValue], scene_b: dict[str, JsonValue]) -> ElementChange | None` — Describe one selector's visible A/B change.
  - `describe_scene(*, scene_a: dict[str, JsonValue], scene_b: dict[str, JsonValue], selectors: tuple[str, ...] | None=None) -> tuple[ElementChange, ...]` — Describe changed elements, optionally restricted by selector.

### `cli.py`

Command-line enrichment of an existing Visual Cause report.

- `main() -> None` — Enrich a Visual Cause report from two captured scene manifests.

### `models.py`

Typed data models for rendered-scene change descriptions.

- `class DescriptionOptions` — Configure browser-side scene capture.
  - Fields: `include_computed_style: bool`, `include_relationships: bool`, `infer_spatial_layouts: bool`, `include_binary: bool`, `include_element_screenshots: bool`
  - `browser_options() -> dict[str, JsonValue]` — Return options using the browser runtime's camelCase API.

### `visual_cause.py`

Adapters enriching Visual Cause reports with rendered scenes.

- `class VisualCauseDescriber` — Attach semantic A/B descriptions to Visual Cause change trees.
  - `markdown(*, report: dict[str, JsonValue]) -> str` — Render the enriched change description as Markdown.
  - `strings(value: JsonValue) -> list[JsonValue]` — Return only the string members of a JSON list.
  - `scene_metadata(scene: dict[str, JsonValue]) -> dict[str, JsonValue]` — Return the scene's metadata and reference blocks.
  - `enrich(*, report: dict[str, JsonValue], scene_a: dict[str, JsonValue], scene_b: dict[str, JsonValue]) -> dict[str, JsonValue]` — Return a copy of the report with description fields added.

## JavaScript API reference

Exports of the package's ES modules, read from the source.

### `js/unified_evidence.js`

@file Rendered scene inspection and binary export.

## Examples

Examples for scene_description.

Files: `.scratch/results/description.md`, `.scratch/results/report-described.json`, `.scratch/results/report.json`, `.scratch/results/scene-a.json`, `.scratch/results/scene-b.json`, `__init__.py`, `__main__.py`, `run.py`

## Dependencies and consumers

- No dependencies outside the standard library.
- Used by: no other module imports it; it is run directly or through the bundle.

## Tests

Tests live in `exactus/tests/packages/scene_description/`.

- `test_capture.py` — Tests for the SceneDescriptor Playwright bridge. (8 tests)
  - `test_init_uses_bundled_runtime`
  - `test_init_accepts_custom_script_path`
  - `test_install_injects_when_missing`
  - `test_install_skips_when_available`
  - `test_describe_builds_browser_payload`
  - `test_describe_defaults`
  - `test_describe_rejects_non_dict_result`
  - `test_describe_installs_before_evaluate`
- `test_changes.py` — Tests for the deterministic SceneChangeDescriber. (22 tests)
  - `test_describe_element_missing_in_both_scenes`
  - `test_describe_element_appeared`
  - `test_describe_element_disappeared`
  - `test_describe_element_identical`
  - `test_describe_element_movement`
  - `test_describe_element_resize`
  - `test_describe_element_below_tolerance`
  - `test_describe_element_missing_frames`
  - `test_describe_element_identity_fields`
  - `test_element_matches_visual_cause_selector`
  - `test_elements_requires_dict_container`
  - `test_elements_skips_non_dict_entries`
  - `test_selectors_requires_string`
  - `test_describe_scene_sorted_union`
  - `test_describe_scene_explicit_selectors`
  - `test_label_falls_back_to_text`
  - `test_label_falls_back_to_tag_and_selector`
  - `test_label_long_text_truncates`
  - `test_frame_requires_visual_and_numeric`
  - `test_element_change_as_json`
  - `test_geometry_without_any_frame_keys`
  - `test_scene_b_and_a_empty_details`
- `test_examples.py` — Tests for the runnable scene_description examples. (3 tests)
  - `test_example_main_writes_enriched_outputs`
  - `test_example_main_seeds_inputs_when_results_are_missing`
  - `test_examples_module_entrypoint`
- `test_js_runtime.py` — Run the browser test suite and enforce JavaScript coverage. (3 tests)
  - `test_runtime_js_parses`
  - `test_browser_test_js_parses`
  - `test_browser_suite_and_coverage`
- `test_main.py` — Tests for the scene_description command-line entry point. (3 tests)
  - `test_load_returns_dict`
  - `test_load_rejects_non_object`
  - `test_main_enriches_report`
- `test_models.py` — Tests for the DescriptionOptions model and JSON aliases. (4 tests)
  - `test_browser_options_defaults`
  - `test_browser_options_reflects_overrides`
  - `test_options_are_frozen`
  - `test_package_exports`
- `test_visual_cause.py` — Tests for the VisualCauseDescriber report enrichment. (14 tests)
  - `test_enrich_adds_change_description`
  - `test_enrich_does_not_mutate_report`
  - `test_enrich_non_list_trees`
  - `test_enrich_skips_non_dict_nodes`
  - `test_enrich_node_without_selector`
  - `test_enrich_matched_node_serializes_context`
  - `test_enrich_recurses_descendants`
  - `test_enrich_missing_relations_or_descendants`
  - `test_strings_filters_members`
  - `test_scene_metadata_fallbacks`
  - `test_markdown_missing_block`
  - `test_markdown_renders_summary_and_elements`
  - `test_markdown_without_elements_list`
  - `test_markdown_missing_summary_fallback`

<!-- exactus:reference:end -->
