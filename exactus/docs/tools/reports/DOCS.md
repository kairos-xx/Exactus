# tools/reports/

Report bundle writing and normalized-report rendering — the bridge
between each tool's `result.json` and the shipped `result.md`/offline
web bundle.

## Files

| File | Description |
|---|---|
| `bundle.py` | `ReportBundle`: writes consistent `result.json`, `result.md` and the offline web bundle (`report.css`/`report.js`/`data.js`) for every tool — canonical names regardless of what the tool requested. |
| `render.py` | Render normalized `result.json` through each tool's template/mapping via the `exactus.markdown` engine. |

## Behavior

- Canonical naming: any `ReportPaths` a tool passes is rewritten to
  `result.*`, so `result.json` is always the semantic source.
- `render.py` composes tool-specific templates/mappings on the generic
  engine — the engine itself stays report-independent.
- Before rendering, `render.py` assigns every mapped finding a stable
  `finding-…` anchor id and builds `file_summary`: findings grouped per
  file with concise issue rows. The common template emits a "By file"
  resume that links each issue to its anchored finding section; the web
  renderer passes the `<a id>` markers through so `#finding-…` links
  work there too. `file_summary` is template-only and is excluded from
  the mapped web `view`.
- The web bundle is fully offline: no CDN, one `data.js` carries the
  model and `report.js` renders it client-side.
- Applies the shared stamp (`NormalizedStamp`) so every report carries
  the same envelope blocks before rendering.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Shared exactus report rendering and delivery. |
| `bundle.py` | Write consistent Markdown, JSON, and offline web exactus reports. |
| `render.py` | Render normalized reports from ``result.json`` through tool templates. |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Shared exactus report rendering and delivery.


### `bundle.py`

Write consistent Markdown, JSON, and offline web exactus reports.

- `class Constants` — Store shared report rendering constants.
  - `schema` = `'project-exactus-report/v1'`
  - `max_path_chars` = `4096`
  - `css_name` = `'report.css'`
  - `code_span` = `re_compile(pattern='(?<!\\[)`(?P<path>[^`:\\n]+?)(?::(?P<line>\\d+)(?::\\...`
  - `kit_css_name` = `'cerulean.css'`
  - `kit_template` = `'vendor/cerulean.css'`
  - `js_name` = `'report.js'`
  - `html_name` = `'index.html'`
  - `data_name` = `'data.json'`
  - `data_js_name` = `'data.js'`
  - `required_payload_keys` = `frozenset({'schema', 'title', 'analyzer', 'generated_at', 'fingerprint',...`
  - `object_blocks` = `frozenset({'tool', 'run', 'invocation', 'environment', 'gate', 'summary',...`
  - `list_blocks` = `frozenset({'artifacts', 'findings'})`
  - `envelope_blocks` = `frozenset({'tool', 'run', 'invocation', 'environment', 'gate', 'artifacts'})`
  - `normalized_blocks` = `envelope_blocks | frozenset({'summary', 'scope', 'findings', 'extension'})`
  - `finding_keys` = `frozenset({'id', 'title', 'severity', 'rule', 'path', 'line', 'message',...`
  - `irregular_whitespace` = `frozenset((chr(point) for point in (11, 12, 133, 160, 5760, 6158, *range(...`
- `command_output(*, args: tuple[str, ...]) -> str` — Return a trimmed command's stdout, or an empty string on failure.
- `fingerprint() -> JsonObject` — Return the tree and toolchain identity of this exactus run.
- `class ReportPaths` — Represent the three public report deliverables.
  - Fields: `markdown: Path`, `json: Path`, `web: Path`
- `class ReportBundle` — Render one analyzer result in identical Markdown/JSON/web formats.
  - `sections(cls: type[Self], *, markdown: str) -> list[JsonValue]` — Extract a flat heading index preserving Markdown organization.
  - `write_web_data(cls: type[Self], *, web: Path, payload: JsonObject) -> None` — Write the ``data.json`` and ``data.js`` payload files.
  - `local_links(cls: type[Self], *, value: JsonValue, base: Path, root: Path) -> dict[str, JsonValue]` — Index existing report file references for web-rendered cells.
  - `link_paths(cls: type[Self], *, markdown: str, base: Path, root: Path) -> str` — Turn backticked project paths into relative Markdown links.
  - `relative_href(cls, *, href: str, base: Path, root: Path) -> str` — Return a URL-encoded local link relative to its report.
  - `validate_payload(cls: type[Self], *, payload: Mapping[str, JsonValue], markdown: str, required_blocks: frozenset[str]=frozenset()) -> None` — Validate the common cross-format report contract.
  - `write(cls: type[Self], *, paths: ReportPaths, analyzer: str, title: str, markdown: str, data: Mapping[str, JsonValue] | None=None) -> JsonObject` — Write matching Markdown, JSON, and static-web reports.
  - `web_data_js(*, payload: JsonObject) -> str` — Render the report payload as a script-includable JS document.
  - `validate_blocks(*, payload: Mapping[str, JsonValue], required: frozenset[str]) -> None` — Validate the normalized blocks of a migrated report.
  - `validate_paths(*, paths: ReportPaths) -> None` — Validate that all three report representations were written.

### `render.py`

Render normalized reports from ``result.json`` through tool templates.

- `class Constants` — Template layout constants.
  - `tools` = `_template_tools_root()`
  - `common` = `tools / 'common' / 'templates' / 'markdown'`
  - `relative` = `('templates', 'markdown')`
  - `template` = `'template.md'`
  - `mapping` = `'mapping.json'`
  - `logger` = `getLogger(name=__name__)`
  - `anchor_noise` = `compile_pattern(pattern='[^a-z0-9]+')`
- `class RenderedReport` — Markdown and the mapped view model it was rendered from.
  - Fields: `markdown: str`, `view: dict[str, JsonValue]`
- `class ReportTemplates` — Locate, merge and render the Markdown templates of a tool.
  - `migrated(cls: type[Self], *, analyzer: str) -> bool` — Report whether a tool renders through a template.
  - `mapping(cls: type[Self], *, tool_dir: Path, common_dir: Path=Constants.common) -> dict[str, JsonValue]` — Merge a tool mapping over the common base mapping.
  - `render(cls: type[Self], *, model: JsonValue, tool_dir: Path, common_dir: Path=Constants.common) -> RenderedReport` — Map ``model`` and render the tool template.
  - `tool_dir(*, analyzer: str) -> Path` — Return a tool's Markdown template directory.
  - `load_mapping(*, path: Path) -> dict[str, JsonValue]` — Read one mapping file.
  - `columns(*, view: Mapping[str, JsonValue]) -> dict[str, JsonValue]` — Record the column order of every list-of-objects view block.
- `class NormalizedStamp` — Add the envelope to a written report and re-render it.
  - `apply(cls: type[Self], *, facts: RunFacts, required: frozenset[str]) -> bool` — Stamp ``result.json``, ``result.md`` and the web data.

## Dependencies and consumers

- Other packages: [`markdown`](../../packages/markdown/DOCS.md), [`common`](../common/DOCS.md)
- Used by: `__main__.py`, `tests/common/support.py`, `tests/tools/common/test_report_templates.py`, `tests/tools/coverage_tests/test_report_layout.py`, `tests/tools/docs/test_docs_metrics.py`, `tests/tools/docs/test_docs_report.py`, `tests/tools/frontend/test_frontend_report.py`, `tests/tools/kwargs_typehints/test_kwargs_report.py`, `tests/tools/lints/test_lints_report.py`, `tests/tools/readme/test_readme_report.py`, `tests/tools/record/test_record_report.py`, `tests/tools/reports/test_report_bundle.py`, `tests/tools/reports/test_report_render.py`, `tests/tools/reports/test_report_web.py`, `tools/actions/runner.py`, `tools/common/execution.py`, `tools/coverage_tests/core.py`, `tools/coverage_tests/report.py`, `tools/docs/core.py`, `tools/frontend/main.py`, `tools/kwargs_typehints/core.py`, `tools/lints/main.py`, `tools/performance/main.py`, `tools/readme/main.py`, `tools/record/main.py`, `tools/self_test/main.py`, `tools/visual_cause/main.py`

## Tests

Tests live in `exactus/tests/tools/reports/`.

- `test_report_bundle.py` — Report-bundle validation helpers and fingerprint command plumbing. (26 tests)
  - `test_artifact_names_stay_plain_and_paths_are_linked`
  - `test_command_output_failure_paths`
  - `test_command_output_missing_program`
  - `test_fingerprint_reports_environment`
  - `test_large_markdown_stays_in_one_file`
  - `test_link_paths_leaves_non_paths`
  - `test_link_paths_leaves_oversized_paths`
  - `test_link_paths_links_existing_files`
  - `test_link_paths_node_fallbacks`
  - `test_normalize_markdown_adds_title`
  - `test_normalize_markdown_variants`
  - `test_portable_links_cover_artifacts_and_existing_links`
  - `test_table_dunder_file_is_one_literal_link`
  - `test_validate_blocks_finding_keys`
  - `test_validate_blocks_missing_block`
  - `test_validate_blocks_wrong_types`
  - `test_validate_paths_missing_artifacts`
  - `test_validate_payload_empty_sections`
  - `test_validate_payload_markdown_heading`
  - `test_validate_payload_missing_keys`
  - `test_validate_payload_web_keys`
  - `test_web_data_js_escapes_template_sequences`
  - `test_web_link_index_uses_report_base`
  - `test_write_compares_findings_with_previous_report`
  - `test_write_emits_web_data_files`
  - `test_write_records_previous_duration`
- `test_report_js_renderer.py` — The web report's Markdown renderer escapes code and refuses bad links. (19 tests)
  - `test_anchor_lines_pass_through_unescaped`
  - `test_backtick_fence_and_longer_closer`
  - `test_category_filter_pluralizes_its_label`
  - `test_code_label_links_remain_clickable`
  - `test_code_span_has_no_inline_markup`
  - `test_diagnostic_callouts_have_distinct_colors`
  - `test_file_links_encode_reserved_characters`
  - `test_finding_rows_link_to_their_findings`
  - `test_findings_filter_and_group_by_source`
  - `test_javascript_links_stay_text`
  - `test_markdown_paragraph_link_is_text`
  - `test_prose_lists_render_as_notes`
  - `test_ranges_compacts_only_runs_of_three`
  - `test_safe_links_render`
  - `test_severity_badge_escapes_label`
  - `test_single_source_keeps_a_flat_list`
  - `test_tilde_fence_renders_escaped_code`
  - `test_tool_sections_follow_the_mapping_order`
  - `test_unclosed_fence_is_closed`
- `test_report_render.py` — Tool templates extend the common template; mappings merge over base. (12 tests)
  - `test_bad_mapping_is_rejected`
  - `test_fence_markers_in_content_cannot_close_the_fence`
  - `test_identity_renders_previous_duration`
  - `test_migrated_tools`
  - `test_missing_tool_mapping_uses_base`
  - `test_packaged_templates_remain_renderable`
  - `test_render_adds_a_linked_per_file_resume`
  - `test_render_groups_pathless_findings_as_general`
  - `test_tool_mapping_wins_over_base`
  - `test_tool_template_extends_common_template`
  - `test_unmigrated_tool_keeps_legacy_markdown`
  - `test_validate_blocks`
- `test_report_snippets.py` — Migrated tools store finding excerpts in result.json, Markdown and web. (5 tests)
  - `test_context_zero_keeps_the_target_line`
  - `test_exec_excerpt_follows_context_lines`
  - `test_lints_and_docs_excerpts_use_default_context`
  - `test_readme_findings_without_lines_get_no_excerpt`
  - `test_web_bundle_ships_the_snippet_viewer`
- `test_report_web.py` — The web bundle carries the view model that renders ``result.md``. (5 tests)
  - `test_columns_follow_first_seen_row_keys`
  - `test_error_after_report_is_kept`
  - `test_migrated_web_data_carries_the_markdown_view`
  - `test_unmigrated_web_data_has_no_view`
  - `test_web_write_failure_keeps_the_normalized_markdown`

<!-- exactus:reference:end -->
