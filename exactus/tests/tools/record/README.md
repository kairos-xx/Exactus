# Tests

- `__init__.py` — package marker for the record test suite.
- `conftest.py` — shared Qt bootstrap and session fixtures.
- `test_assertions_causality.py` — assertion evaluation and causal attribution.
- `test_bridge_protocol.py` — HTML editor and bridge architecture invariants.
- `test_expectations.py` — network expectation matching.
- `test_expressions_execution.py` — safe expression and graph execution behavior.
- `test_expressions_errors.py` — Error handling and operator coverage of the expression evaluator.
- `test_live_run.py` — incremental immutable run telemetry.
- `test_model.py` — domain-model validation and selector invariants.
- `test_model_validation_extra.py` — extra domain-model validation coverage.
- `test_qt_runtime.py` — real PyQt6/WebEngine runtime coverage.
- `test_recorder_protocol.py` — recorder/player protocol serialization and decoding.
- `test_store.py` — workspace mutation, migration, and persistence.
- `test_store_errors.py` — Workspace loading rejects unreadable, unsupported, and duplicated data.
- `test_where.py` — placeholder test module.
- `test_window_runtime.py` — host-window command and persistence coverage.

## Files

- `test_crawler_visit.py` — File.
- `test_flow_runner.py` — File.
- `test_flow_studio.py` — File.
- `test_recorder.py` — File.
- `test_studio_http_contract.py` — File.
- `test_discovery_project.py` — File.
- `test_project_assets.py` — File.
- `test_workspace_actions.py` — File.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests for the Exactus Record studio.
- [`selector_support.py`](selector_support.py) — Build small projects that use selectors, for the selector tests.
- [`test_action_schema.py`](test_action_schema.py) — Verify typed action bindings and stable input/output identities.
- [`test_assertions_causality.py`](test_assertions_causality.py) — Coverage for assertion evaluation and causal attribution.
- [`test_bridge_protocol.py`](test_bridge_protocol.py) — HTML-editor architecture regression tests.
- [`test_crawler_visit.py`](test_crawler_visit.py) — The visit-plan crawler and the parallel visit replayer.
- [`test_diagnostic_sources.py`](test_diagnostic_sources.py) — Browser diagnostics retain real script locations and function stacks.
- [`test_discovery_project.py`](test_discovery_project.py) — Verify crawler projects open and replay in browser Studio.
- [`test_expectations.py`](test_expectations.py) — Tests for action-attributed network expectation matching.
- [`test_expressions_errors.py`](test_expressions_errors.py) — Error handling and operator coverage of the expression evaluator.
- [`test_expressions_execution.py`](test_expressions_execution.py) — Behavioral coverage for expression and execution engines.
- [`test_flow_contracts.py`](test_flow_contracts.py) — Bind the locked v4 contract files to FLOW.md and the real v3 surface.
- [`test_flow_inventory.py`](test_flow_inventory.py) — Keep the version-3 action inventory complete and current.
- [`test_flow_runner.py`](test_flow_runner.py) — Real-browser coverage of Studio functional tests and screenshot evidence.
- [`test_flow_runner_actions.py`](test_flow_runner_actions.py) — Run data, viewport, touch and REST actions in a real Chromium page.
- [`test_flow_runner_selectors.py`](test_flow_runner_selectors.py) — Run actions that use stored selectors, several targets and pacing.
- [`test_flow_runner_variables.py`](test_flow_runner_variables.py) — Verify that run variables expand with key and index paths.
- [`test_http_request.py`](test_http_request.py) — Verify the shared HTTP sender used by runs and by Studio's Send.
- [`test_live_run.py`](test_live_run.py) — Tests for immutable live execution-run accumulation.
- [`test_model.py`](test_model.py) — Tests for deterministic viewport, targeting, and Flow models.
- [`test_model_selectors.py`](test_model_selectors.py) — Verify selector references, targeting modes and lanes on actions.
- [`test_model_validation_extra.py`](test_model_validation_extra.py) — Validation-path coverage for immutable domain records.
- [`test_persistence_selectors.py`](test_persistence_selectors.py) — Verify selectors persist beside the flows, selectors first.
- [`test_preview_frames.py`](test_preview_frames.py) — Prove the live preview keeps only matching frames and acknowledges all.
- [`test_profiles.py`](test_profiles.py) — Validate profile settings and prove Chromium honours every accepted one.
- [`test_project_assets.py`](test_project_assets.py) — Verify portable screenshot projects and transactional asset imports.
- [`test_rebase.py`](test_rebase.py) — Recorded local URLs follow the target; outside addresses never move.
- [`test_record_core.py`](test_record_core.py) — Record exactus findings and normalized report data.
- [`test_record_report.py`](test_record_report.py) — RECORD renders result.md from its normalized result.json and template.
- [`test_recorder.py`](test_recorder.py) — Action recording, normalization, compilation and replay.
- [`test_recorder_protocol.py`](test_recorder_protocol.py) — Tests for selector-first recorder NDJSON and playback protocol.
- [`test_recording_groups.py`](test_recording_groups.py) — Persist recording parents and preserve capture ownership and cadence.
- [`test_response_paths.py`](test_response_paths.py) — Verify that response values are read by JSON and XML paths.
- [`test_run_gate.py`](test_run_gate.py) — Pause, resume and step a run between actions, in a real Chromium page.
- [`test_selector_conditions.py`](test_selector_conditions.py) — Wait for conditions that read selector probes, and feed connections.
- [`test_selector_engine.py`](test_selector_engine.py) — Verify the ExtendedSelector package engine and its loader.
- [`test_selector_resolver.py`](test_selector_resolver.py) — Resolve stored selectors in a real browser page.
- [`test_selector_sandbox.py`](test_selector_sandbox.py) — Run snippets in the isolated sandbox, alone and from the flow runner.
- [`test_selector_snapshot.py`](test_selector_snapshot.py) — Record matched elements as snapshots and warn when they drift.
- [`test_selector_store.py`](test_selector_store.py) — Verify selector usage, deletion guard, renaming and dangling references.
- [`test_selectors.py`](test_selectors.py) — Verify selector models, pacing and the selectors document codec.
- [`test_similarity.py`](test_similarity.py) — Perceptual image similarity loading and cache contracts.
- [`test_store.py`](test_store.py) — Tests for Flow graph state and deterministic persistence.
- [`test_store_errors.py`](test_store_errors.py) — Workspace loading rejects unreadable, unsupported, and duplicated data.
- [`test_store_selectors.py`](test_store_selectors.py) — Verify the workspace codec keeps selector fields and run causes.
- [`test_studio_action_setup.py`](test_studio_action_setup.py) — Verify that an action can be added first and configured afterwards.
- [`test_studio_boundaries.py`](test_studio_boundaries.py) — Cover live-input validation and read-only target inspection boundaries.
- [`test_studio_duplicate_step.py`](test_studio_duplicate_step.py) — Verify that a step can be duplicated in place.
- [`test_studio_entrypoint.py`](test_studio_entrypoint.py) — Launch the Studio package with a bounded real service lifetime.
- [`test_studio_http_contract.py`](test_studio_http_contract.py) — Verify browser Studio's public HTTP security and mutation contracts.
- [`test_studio_projects.py`](test_studio_projects.py) — Drive the project commands through a real Studio service.
- [`test_studio_selectors.py`](test_studio_selectors.py) — Drive the selector editor commands through a real Studio service.
- [`test_studio_window.py`](test_studio_window.py) — Resolve the Studio window setting from CLI flag and pyproject.
- [`test_target.py`](test_target.py) — Cover the application target: its rules, file format and running service.
- [`test_v3_execution.py`](test_v3_execution.py) — Freeze what version-3 flows compute so v4 can prove equivalence.
- [`test_v3_fixture_builder.py`](test_v3_fixture_builder.py) — Exercise the version-3 fixture regeneration utility.
- [`test_v3_fixtures.py`](test_v3_fixtures.py) — Prove the frozen version-3 workspaces load, round-trip and migrate.
- [`test_where.py`](test_where.py) — Placeholder test module.
- [`test_workspace_actions.py`](test_workspace_actions.py) — Verify current workspace interchange and selector-based actions.
- [`v3_fixture_builder.py`](v3_fixture_builder.py) — Write the frozen version-3 workspace fixtures used by migration tests.

### Subdirectories

- [`fixtures/`](fixtures/README.md) — Provide action contract json content.
- [`golden_tool/`](golden_tool/README.md) — **Run time:** 05 October 2026, 06:00:00 UTC
- [`js/`](js/README.md) — `node:test` suites for `exactus/record` browser components: the action recorder, the Flow Studio web UI and its transport. Browser assertions run through the shared \[`exactus/tests/common/browser.mjs`\](../../../common/browser.mjs) Playwright harness.
- [`web_selector/`](web_selector/README.md) — Standalone web page used by the selector tests: the harness serves it through \[`selector_support.py`\](../selector_support.py) and every element declares its geometry through `data-*` attributes.

<!-- exactus:inventory:end -->


