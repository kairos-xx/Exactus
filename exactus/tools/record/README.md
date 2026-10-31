# Record

Record owns action recording, replay, crawler discovery and functional execution.
The browser editor and its HTTP service live in `studio/`. PNG capture and visual
comparison live in `exactus.packages.screenshot`.

```sh
python -m exactus.tools.record.studio --project . --headless
python -m exactus.tools.record.run flows.pwflow.json --output EXACTUS_RESULTS/FLOWS
python -m exactus.tools.actions demo/actions/frontend.json
```

Studio serves the editor over an authenticated loopback HTTP service and owns a
separate Playwright browser for the application under test. Recording and replay
use the same action schema. There is no Qt, WebChannel or CDP host.

The editor provides flows, connected transitions, a continuous timeline,
editable actions and JavaScript calls, assertions, screenshot checkpoints,
recording scopes, viewport presets, orientation and custom responsive sizes.
Crawler discovery generates ordinary current-version Studio projects.

See [Flow Studio service](../../docs/FLOW_STUDIO_SERVICE.md),
[Actions recipes](../../docs/ACTIONS.md) and
[FRONTEND exactus](../../docs/FRONTEND_EXACTUS.md) for execution and report contracts.

## Files

- `__init__.py` — File.
- `action_recorder.js` — File.
- `action_recorder.py` — File.
- `assertions.py` — File.
- `causality.py` — File.
- `click_explorer.py` — File.
- `crawler.py` — File.
- `diagnostics.py` — File.
- `discovery.py` — File.
- `execution.py` — File.
- `expectations.py` — File.
- `expressions.py` — File.
- `flow_runner.py` — File.
- `live_run.py` — File.
- `model.py` — File.
- `project_assets.py` — File.
- `py.typed` — File.
- `recorder_protocol.py` — File.
- `run.py` — File.
- `store.py` — File.
- `visit.py` — File.
- `workspace_actions.py` — File.

## Subdirectories

- `examples/` — Subdirectory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Own browser recording, crawling, diagnostics, and flow execution.
- [`action_recorder.js`](action_recorder.js) — One recorded locator strategy, strongest first.
- [`action_recorder.py`](action_recorder.py) — Record, normalize, compile, and replay interactive Playwright actions.
- [`action_schema.py`](action_schema.py) — Define typed action inputs, outputs and stable value-source bindings.
- [`arguments.py`](arguments.py) — Declare the record grammar without importing its execution engine.
- [`assertions.py`](assertions.py) — Generic assertion comparison shared by UI, protocol, and test runtime.
- [`capture_screen.py`](capture_screen.py) — Capture screenshots with arbitrarily nested overflow fully exposed.
- [`causality.py`](causality.py) — Deterministic causal attribution for recorded browser observations.
- [`click_explorer.py`](click_explorer.py) — Explore clickable states and capture visually distinctive screens.
- [`conflict_copies.py`](conflict_copies.py) — Reconcile numbered sync copies without discarding unique project data.
- [`core.py`](core.py) — Record exactus core: session summaries and report rendering.
- [`crawler.py`](crawler.py) — Build a concrete visit plan covering every reachable app interface.
- [`diagnostics.py`](diagnostics.py) — Collect browser-visible diagnostics during click exploration.
- [`discovery.py`](discovery.py) — Convert bounded crawler discoveries into editable flow documents.
- [`execution.py`](execution.py) — Deterministic graph execution, typed variables, and run snapshots.
- [`expectations.py`](expectations.py) — Deterministic network expectation matching for Flow observations.
- [`expressions.py`](expressions.py) — Safe deterministic expression and template evaluation for Flow execution.
- [`flow_inventory.py`](flow_inventory.py) — Inventory the version-3 action surface that structured flows must keep.
- [`flow_runner.py`](flow_runner.py) — Execute Studio flows with assertions and durable browser evidence.
- [`http_request.py`](http_request.py) — Send one REST request; shared by flow runs and Studio's Send.
- [`json_types.py`](json_types.py) — JSON value types shared by the exactus tools.
- [`live_run.py`](live_run.py) — Incremental immutable execution-run telemetry for the desktop inspector.
- [`main.py`](main.py) — Record, replay, and Exactus Record browser sessions as an exactus.
- [`model.py`](model.py) — Immutable models for viewports, flows, actions, and runtime artifacts.
- [`profile_emulation.py`](profile_emulation.py) — Apply a profile's device and media conditions to a real Chromium page.
- [`project_assets.py`](project_assets.py) — Embed and restore verified PNG assets in portable Studio projects.
- [`project_info.py`](project_info.py) — Describe a project: its name, purpose, tags and authorship.
- [`py.typed`](py.typed) — Provide py typed content.
- [`rebase.py`](rebase.py) — Carry recorded URLs to wherever the application under test runs now.
- [`recorder_protocol.py`](recorder_protocol.py) — Strict NDJSON protocol shared by GUI, recorder, and execution player.
- [`response_paths.py`](response_paths.py) — Read one value from a REST response by a JSON or XML path.
- [`run.py`](run.py) — Run saved Studio flows as unattended functional tests and captures.
- [`run_gate.py`](run_gate.py) — Pause, resume and single-step a flow run between its actions.
- [`selector_engine.py`](selector_engine.py) — Load the ExtendedSelector package engine as an injectable script.
- [`selector_probes.py`](selector_probes.py) — Publish selector probes as variables for conditions.
- [`selector_resolve.js`](selector_resolve.js) — Resolve one ExtendedSelector expression inside the engine's isolated world.
- [`selector_resolver.py`](selector_resolver.py) — Resolve stored selector expressions to CSS in the target page.
- [`selector_sandbox.js`](selector_sandbox.js) — Run a JavaScript action in the engine's isolated world.
- [`selector_sandbox.py`](selector_sandbox.py) — Run JavaScript actions in the isolated sandbox with run-wide streams.
- [`selector_scripts.d.ts`](selector_scripts.d.ts) — Provide selector scripts.d ts content.
- [`selector_snapshot.py`](selector_snapshot.py) — Compare a matched element with the baseline recorded for a snapshot.
- [`selector_targets.py`](selector_targets.py) — Turn an action's selector reference into the targets it will act on.
- [`selector_usage.py`](selector_usage.py) — Find where selectors are used, and keep references valid on rename.
- [`selectors.py`](selectors.py) — Reusable selectors, targeting modes and pacing for recorded actions.
- [`similarity.py`](similarity.py) — Multi-factor perceptual image similarity scoring.
- [`sprint.py`](sprint.py) — Shared flushed-writer printing helpers for scripts and examples.
- [`store.py`](store.py) — Deterministic Flow workspace state and JSON persistence.
- [`visit.py`](visit.py) — Replay a crawler visit plan across parallel device and theme lanes.
- [`workspace_actions.py`](workspace_actions.py) — Convert selector-based recorded actions and current workspace documents.

### Subdirectories

- [`examples/`](examples/README.md) — Load and validate the branching workspace without starting a browser:
- [`studio/`](studio/README.md) — Studio owns the browser editor, authenticated local HTTP service, recovery, command transport, and the separate Playwright target worker.
- [`templates/`](templates/README.md) — Provide mapping json content.

<!-- exactus:inventory:end -->


