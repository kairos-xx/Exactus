# tools/record/

The `record` tool: record, replay and audit browser sessions through the
`exactus.record` engine.

## Files

| File | Description |
|---|---|
| `arguments.py` | The record grammar, declared without importing the execution engine. |
| `core.py` | Record-tool core: session summaries and report data — emits the normalized `summary`/`scope`/`findings`/`extension` blocks. |
| `main.py` | Entry: record, replay and audit Record browser sessions. |
| `templates/` | Tool-specific Markdown template/mapping (session metrics, action and exported-event tables, rules, studio facts). |
| `studio/` | Studio frontend assets for the visual flow editor. |
| `examples/` | Runnable demonstrations of recording and replaying flows. |
| `py.typed` | PEP 561 marker — the tool ships inline type annotations. |
| **Recording and protocol** | |
| `action_recorder.py` | Record, normalize, compile, and replay interactive Playwright actions. |
| `action_recorder.js` | In-page injected recorder script producing `LocatorCandidate`-based action events. |
| `recorder_protocol.py` | Strict NDJSON protocol shared by GUI, recorder, and execution player. |
| `action_schema.py` | Typed action inputs, outputs and stable value-source bindings. |
| **Flow model and execution** | |
| `model.py` | Immutable models for viewports, flows, actions, and runtime artifacts. |
| `store.py` | Deterministic Flow workspace state and JSON persistence. |
| `execution.py` | Deterministic graph execution, typed variables, and run snapshots. |
| `flow_runner.py` | Execute Studio flows with assertions and durable browser evidence. |
| `flow_inventory.py` | Inventory the version-3 action surface that structured flows must keep. |
| `run.py` | Run saved Studio flows as unattended functional tests and captures. |
| `run_gate.py` | Pause, resume and single-step a flow run between its actions. |
| `live_run.py` | Incremental immutable execution-run telemetry for the desktop inspector. |
| `json_types.py` | JSON value types shared by the exactus tools. |
| `expressions.py` | Safe deterministic expression and template evaluation for Flow execution. |
| `assertions.py` | Generic assertion comparison shared by UI, protocol, and test runtime. |
| `expectations.py` | Deterministic network expectation matching for Flow observations. |
| `causality.py` | Deterministic causal attribution for recorded browser observations. |
| `workspace_actions.py` | Convert selector-based recorded actions into current workspace documents. |
| **Selectors** | |
| `selectors.py` | Reusable selectors, targeting modes and pacing for recorded actions. |
| `selector_engine.py` | Load the ExtendedSelector package engine as an injectable script. |
| `selector_resolver.py` | Resolve stored selector expressions to CSS in the target page. |
| `selector_targets.py` | Turn an action's selector reference into the targets it will act on. |
| `selector_probes.py` | Publish selector probes as variables for conditions. |
| `selector_snapshot.py` | Compare a matched element with the baseline recorded for a snapshot. |
| `selector_sandbox.py` | Run JavaScript actions in the isolated sandbox with run-wide streams. |
| `selector_usage.py` | Find where selectors are used, and keep references valid on rename. |
| `selector_resolve.js` | In-page resolution of ExtendedSelector expressions used by `selector_resolver.py`. |
| `selector_sandbox.js` | In-page sandbox runtime backing `selector_sandbox.py`. |
| `selector_scripts.d.ts` | Type declarations for the injected selector/sandbox page scripts. |
| **HTTP and assertions** | |
| `http_request.py` | Send one REST request; shared by flow runs and Studio's Send. |
| `response_paths.py` | Read one value from a REST response by a JSON or XML path. |
| **Capture and evidence** | |
| `capture_screen.py` | Capture screenshots with arbitrarily nested overflow fully exposed. |
| `similarity.py` | Multi-factor perceptual image similarity scoring. |
| `profile_emulation.py` | Apply a profile's device and media conditions to a real Chromium page. |
| `diagnostics.py` | Collect browser-visible diagnostics during click exploration. |
| **Discovery and crawling** | |
| `crawler.py` | Build a concrete visit plan covering every reachable app interface. |
| `visit.py` | Replay a crawler visit plan across parallel device and theme lanes. |
| `click_explorer.py` | Explore clickable states and capture visually distinctive screens. |
| `discovery.py` | Convert bounded crawler discoveries into editable flow documents. |
| **Project utilities** | |
| `rebase.py` | Carry recorded URLs to wherever the application under test runs now. |
| `conflict_copies.py` | Reconcile numbered sync copies without discarding unique project data. |
| `project_assets.py` | Embed and restore verified PNG assets in portable Studio projects. |
| `project_info.py` | Describe a project: its name, purpose, tags and authorship. |
| `sprint.py` | Shared flushed-writer printing helpers for scripts and examples. |

## Behavior

- Migrated to normalized reports: `core.py` no longer builds bespoke
  `RECORD.json/md/web` output — it emits canonical `result.*` through
  `ReportBundle` and the shared envelope.
- Session metrics, action counts, exported events and studio facts live
  in the `extension` block, rendered by the tool template.
- Drives the same `exactus.record` engine as Studio, so recorded
  sessions replay identically under the tool.
# record/recorder_protocol.py

Strict recorder and worker protocol used by Exactus Record, Flow Studio,
and the service-owned execution player. Browser clients communicate with
Studio through its authenticated HTTP/SSE command envelope;
`RecorderProtocol` validates the canonical internal payloads described
here.

Launch Flow Studio with
`python -m exactus.record.studio --project /path/to/project`. The
service binds to loopback on an operating-system-selected port and
prints the Studio URL.

## Model

-   Studio bootstraps `POST /api/session` with a per-launch bearer token
    carried in the URL fragment, never in the request URL. Authenticated
    requests then use the session cookie.
-   `POST /api/command` carries protocol version, request ID, client ID,
    current workspace revision, and command payload. The client ID is
    sent in `X-Studio-Client`.
-   `GET /api/snapshot?client=<id>` returns authoritative workspace and
    ownership state; `GET /events` streams ordered SSE events and
    snapshot recovery; `GET /api/export` downloads the canonical
    workspace.
-   Protected `/artifacts/` and `/reports/actions/` routes serve run
    evidence.
-   Command bodies are limited to 8 MiB. Request IDs are deduplicated;
    mutations require the controlling tab and current revision. After
    transport failure, refresh the snapshot before another mutation. A
    stale revision preserves current edits for review.
-   Internal recorder/worker messages are handled by `RecorderProtocol`.
    `play_flow` sends an immutable canonical flow to the service-owned
    worker.

## Targeting

DOM actions are selector-based. These event kinds require a non-empty
`selector` and must not contain `x`, `y`, `end_x`, or `end_y`:

``` text
click
double_click
right_click
hover
drag
scroll
gesture
input_text
```

There is no coordinate fallback when a selector stops resolving.
Timeline rollover highlighting uses the same selector.

Coordinates are valid only for `kind: "position_pointer"`. A positional
event requires `position_action`, `x`, and `y`, must not contain
`selector`, and may contain `end_x` and `end_y`. Allowed actions are
`click`, `double_click`, `right_click`, `hover`, `drag`, `scroll`, and
`gesture`.

The protocol boundary and domain model both enforce this invariant.

## Worker commands

  Command         Purpose
  --------------- ---------------------------------------------------------
  `record`        Start or resume recording for a Flow.
  `pause`         Pause recording.
  `wait`          Insert an explicit timed wait.
  `viewport`      Change logical viewport, preview scale, or device mode.
  `active_flow`   Change the active Flow.

Record/resume:

``` json
{"type":"command","name":"record","flow_id":"flow-a","milliseconds":null,"width":null,"height":null,"scale":null,"device_mode":"mobile","capture_images":true}
```

Pause and explicit wait:

``` json
{"type":"command","name":"pause","flow_id":"flow-a","milliseconds":null,"width":null,"height":null,"scale":null,"device_mode":null,"capture_images":null}
{"type":"command","name":"wait","flow_id":"flow-a","milliseconds":1000,"width":null,"height":null,"scale":null,"device_mode":null,"capture_images":null}
```

Viewport/device change:

``` json
{"type":"command","name":"viewport","flow_id":"flow-a","milliseconds":null,"width":390,"height":844,"scale":0.75,"device_mode":"mobile","capture_images":null}
```

`width` and `height` are logical CSS viewport dimensions; `scale` is the
browser preview fit factor. Device modes are `mobile`, `tablet`,
`desktop`, and `custom`. `capture_images` is the active Flow's
record-phase screenshot policy.

Active Flow change:

``` json
{"type":"command","name":"active_flow","flow_id":"flow-c","milliseconds":null,"width":null,"height":null,"scale":null,"device_mode":null,"capture_images":null}
```

## Play Flow

Play sends the complete canonical sequence to the service-owned player:

``` json
{
  "type": "play_flow",
  "flow_id": "flow-a",
  "name": "Search",
  "device_mode": "desktop",
  "capture_images": true,
  "task_description": "Search and open one result.",
  "expected_behavior": "The selected result is displayed.",
  "events": []
}
```

Events execute in sequence order. A Flow whose requested device mode
conflicts with its application-level scope is rejected or reported;
Exactus Record normally blocks the request before transmission.

## Events

Every inbound event contains:

``` json
{
  "type": "event",
  "event_id": "unique-event-id",
  "flow_id": "flow-a",
  "elapsed_ms": 1250,
  "layer": "interaction",
  "kind": "click",
  "label": "Click Save"
}
```

Required fields are `type`, `event_id`, `flow_id`, `elapsed_ms`,
`layer`, `kind`, and `label`. Optional fields are event-specific:

``` text
selector
url
method
status
payload
headers
share_session_cookies
caused_by_event_id
position_action
x / y / end_x / end_y
```

Headers are ordered:

``` json
[
  {"name":"Content-Type","value":"application/json"},
  {"name":"X-Client","value":"flow-studio"}
]
```

### Layers

``` text
interaction
navigation
network
websocket
console
timing
```

### Kinds

``` text
click
double_click
right_click
hover
drag
scroll
gesture
position_pointer
input_text
keystroke
wait
url_change
http_call
request
response
websocket_open
websocket_sent
websocket_received
websocket_close
websocket_error
console
note
```

## Interaction payloads

  ----------------------------------------------------------------------------------------------------------------------------
  Interaction                         Canonical payload
  ----------------------------------- ----------------------------------------------------------------------------------------
  Click                               `{"kind":"click","selector":"button[type='submit']"}`

  Double click                        `{"kind":"double_click","selector":"[data-row-id='42']"}`

  Right click                         `{"kind":"right_click","selector":"#asset-17"}`

  Hover                               `{"kind":"hover","selector":"[aria-label='Help']"}`

  Scroll                              `{"kind":"scroll","selector":".results","payload":"deltaX=0;deltaY=612"}`

  Drag                                `{"kind":"drag","selector":"[data-card='A']","payload":"target=[data-column='done']"}`

  Gesture                             `{"kind":"gesture","selector":"#canvas","payload":"gesture=pinch;scale=1.5"}`

  Input                               `{"kind":"input_text","selector":"input[type='email']","payload":"joao@example.test"}`

  Keystroke                           `{"kind":"keystroke","payload":"Control+Shift+S"}`
  ----------------------------------------------------------------------------------------------------------------------------

The table omits the common event envelope for compactness.

Explicit positional click:

``` json
{"type":"event","event_id":"p-1","flow_id":"flow-a","elapsed_ms":1950,"layer":"interaction","kind":"position_pointer","label":"Click canvas coordinate","position_action":"click","x":412,"y":278}
```

Explicit positional drag:

``` json
{"type":"event","event_id":"p-2","flow_id":"flow-a","elapsed_ms":2100,"layer":"interaction","kind":"position_pointer","label":"Drag freeform canvas point","position_action":"drag","x":300,"y":220,"end_x":650,"end_y":420}
```

Navigation:

``` json
{"type":"event","event_id":"n-1","flow_id":"flow-a","elapsed_ms":2400,"layer":"navigation","kind":"url_change","label":"Navigate to dashboard","url":"https://example.test/dashboard"}
```

## Network

An authored HTTP operation participates directly in the Flow sequence:

``` json
{
  "type": "event",
  "event_id": "http-1",
  "flow_id": "flow-a",
  "elapsed_ms": 2500,
  "layer": "network",
  "kind": "http_call",
  "label": "Create draft",
  "url": "https://example.test/api/drafts",
  "method": "POST",
  "headers": [
    {"name":"Content-Type","value":"application/json"},
    {"name":"X-Flow","value":"draft-create"}
  ],
  "payload": "{\"title\":\"Example\"}",
  "share_session_cookies": true
}
```

When `share_session_cookies` is true, the player executes with the same
Playwright browser-context/session identity as the visible page so
applicable authentication cookies are shared. The Flow records this
semantic requirement; the exact transport remains a player concern.

Observed request and response:

``` json
{"type":"event","event_id":"r-1","flow_id":"flow-a","elapsed_ms":2510,"layer":"network","kind":"request","label":"GET /api/search","url":"https://example.test/api/search?page=1","method":"GET","headers":[{"name":"Accept","value":"application/json"}],"caused_by_event_id":"e-search"}
{"type":"event","event_id":"r-2","flow_id":"flow-a","elapsed_ms":2665,"layer":"network","kind":"response","label":"GET /api/search -> 200","url":"https://example.test/api/search?page=1","method":"GET","status":200,"headers":[{"name":"Content-Type","value":"application/json"}],"payload":"{\"ok\":true,\"items\":[{\"id\":42}]}","caused_by_event_id":"e-search"}
```

`caused_by_event_id` binds passive observations to the action that
caused them, allowing Exactus Record to evaluate attached response
expectations locally.

## Expectations

Expectations are stored on their owning action and carried in that
event's `expectations` array during `play_flow`:

``` json
{
  "id": "expect-search",
  "label": "Search returns requested page",
  "method": "GET",
  "url_pattern": "/api/search",
  "url_match": "contains",
  "query_conditions": [
    {"name":"page","operator":"equals","value":"1"}
  ],
  "expected_status": 200,
  "expected_headers": [
    {"name":"Content-Type","value":"application/json"}
  ],
  "body_match": "json_contains",
  "expected_body": "{\"ok\":true}",
  "json_conditions": [
    {"path":"$.items[0].id","operator":"exists","value":null}
  ],
  "timeout_ms": 5000
}
```

  -----------------------------------------------------------------------
  Field                               Supported values
  ----------------------------------- -----------------------------------
  `url_match`                         `exact`, `contains`, `glob`,
                                      `regex`

  Query/JSON operator                 `exists`, `equals`, `not_equals`,
                                      `contains`, `regex`

  `body_match`                        `none`, `exact_text`, `json_exact`,
                                      `json_contains`
  -----------------------------------------------------------------------

Expected header names are compared case-insensitively. JSON conditions
use simple `$` paths such as `$.data.id` and `$.items[0].name`.

An expectation on `http_call` describes that call's response. The same
schema on a click or another browser action describes a network response
caused by that action.

A player may report its evaluation explicitly:

``` json
{
  "type": "expectation_result",
  "result_id": "result-17",
  "flow_id": "flow-a",
  "event_id": "e-search",
  "expectation_id": "expect-search",
  "outcome": "pass",
  "details": "Matched GET /api/search?page=1 with status 200.",
  "matched_url": "https://example.test/api/search?page=1",
  "actual_status": 200,
  "actual_body": "{\"ok\":true,\"items\":[{\"id\":42}]}"
}
```

`outcome` is `pass`, `fail`, or `timeout`. Exactus Record also evaluates
an observed `response` locally when it has `caused_by_event_id` and the
source action has expectations.

## Artifacts

When record/play image capture is enabled, the recorder or player may
report:

``` json
{
  "type": "screenshot",
  "artifact_id": "shot-001",
  "flow_id": "flow-a",
  "event_id": "e-search",
  "phase": "record",
  "path": "/absolute/or/player-managed/path/shot-001.png",
  "width": 1440,
  "height": 900,
  "sha256": "4ee3412d7f2b0f63c0a886f25728a09db22c939d132a8f719c0e5d26a0f88918"
}
```

`phase` is `record` or `play`. Exactus Record stores the metadata as a
run artifact; the recorder/player owns creation of the image itself.

## WebSocket and notes

WebSocket lifecycle events use the normal event envelope:

``` json
{"type":"event","event_id":"ws-1","flow_id":"flow-a","elapsed_ms":2800,"layer":"websocket","kind":"websocket_open","label":"WS open","url":"wss://example.test/live"}
{"type":"event","event_id":"ws-2","flow_id":"flow-a","elapsed_ms":2900,"layer":"websocket","kind":"websocket_sent","label":"WS send","url":"wss://example.test/live","payload":"{\"type\":\"subscribe\"}"}
{"type":"event","event_id":"ws-3","flow_id":"flow-a","elapsed_ms":3010,"layer":"websocket","kind":"websocket_received","label":"WS receive","url":"wss://example.test/live","payload":"{\"type\":\"ready\"}"}
```

Close and error use `websocket_close` and `websocket_error`.

Notes use the timing layer:

``` json
{"type":"event","event_id":"note-1","flow_id":"flow-a","elapsed_ms":3200,"layer":"timing","kind":"note","label":"Checkpoint","payload":"User is authenticated and dashboard data is visible."}
```

## Rollover highlighting

For selector-addressed events Exactus Record removes any previous
overlay, resolves `document.querySelector(selector)`, verifies that the
element is visible and intersects the viewport, draws a fixed
pointer-transparent overlay over its current bounding box, and removes
it when the pointer leaves the timeline item. It never attempts
`elementFromPoint` when selector resolution fails.

`position_pointer` uses the recorded point and a separate positional
overlay path. Normal selector events cannot reach that behavior.

# record/studio/

The local browser service behind Flow Studio
(`exactus.tools.record.studio` / `exactus.record.studio`). The editor
and the service-owned Playwright target run in separate browser
windows: the editor modifies flows while the target receives recorded
actions, discovery work and functional replay. Record CLI and Studio
use this service instead of the superseded Qt host, CDP attachment and
native bridge.

## Model

- The service binds only to `127.0.0.1`; port `0` selects an available
  local port. Commands use HTTP POST and ordered notifications use
  Server-Sent Events on the same origin — no web framework,
  development proxy, cross-origin cookie or WebChannel dependency.
- The editor opens at `/studio/#token=…`; the fragment never leaves the
  browser. It exchanges the bootstrap token at `/api/session` (Bearer +
  exact Origin) for an HttpOnly `SameSite=Strict` session cookie bound
  to the service instance.
- Each editor tab carries a distinct `X-Studio-Client` identity; one
  client owns mutation control with a 60-second idle lease, pinned
  while recording or execution is active. `control.release` requires
  the active recording or run to be paused or cancelled first.
- Commands carry a protocol version, unique request ID, command name,
  workspace revision and payload. Stale revisions are rejected rather
  than overwriting a newer workspace; identical retransmissions hit a
  bounded reply cache (256 client/request IDs), and reusing an ID with
  different data returns `ID_REUSED`.
- Routes: `GET /health`, `GET /studio/…`, `POST /api/session`,
  `GET /api/snapshot`, `POST /api/command`, `GET /events`,
  `GET /api/export`, `GET /artifacts/<id>[?download=1]` — bodies are
  bounded to 8 MiB, subscribers to 16, retained events to 256; path
  traversal and unknown assets are rejected.
- Command groups: `workspace.*`, `flow.*`, `event.*`, `edge.*`,
  `browser.*`, `recorder.*`, `run.*`, `crawl.*`, `screenshot.open`,
  `control.*`. Public error categories include `INVALID_INPUT`,
  `BAD_ORIGIN`, `UNAUTHORIZED`, `STALE_REVISION`, `CONTROL_OWNED`,
  `ID_REUSED`, `BUSY`, `WORKER_BUSY`, `PAYLOAD_TOO_LARGE`,
  `TOO_MANY_CLIENTS`, `NOT_FOUND`, `MISSING_ARTIFACT` and
  `PERSISTENCE_FAILED`.
- The worker owns its browser, context and target pages on one thread;
  HTTP handlers enqueue browser operations rather than driving
  Playwright from request threads. Stopping the service closes only its
  own worker — it never attaches to or terminates an unrelated browser.

## Storage

- Workspace saves and `.studio/recovery.pwflow.json` recovery writes
  are atomic; uploaded workspaces require schema version 3.
- Relative filenames must remain inside the selected project —
  absolute paths, traversal and symlink escapes are rejected — and
  saved-file hashes detect external modification, so a file changed by
  another process is never silently overwritten.

`exactus.record` owns discovery, recorded actions and functional
replay; `exactus.screenshot` owns image acquisition and similarity
comparison; `exactus.tools.frontend` combines those engines into the
FRONTEND exactus.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Own browser recording, crawling, diagnostics, and flow execution. |
| `action_recorder.js` | JavaScript module. |
| `action_recorder.py` | Record, normalize, compile, and replay interactive Playwright actions. |
| `action_schema.py` | Define typed action inputs, outputs and stable value-source bindings. |
| `arguments.py` | Declare the record grammar without importing its execution engine. |
| `assertions.py` | Generic assertion comparison shared by UI, protocol, and test runtime. |
| `capture_screen.py` | Capture screenshots with arbitrarily nested overflow fully exposed. |
| `causality.py` | Deterministic causal attribution for recorded browser observations. |
| `click_explorer.py` | Explore clickable states and capture visually distinctive screens. |
| `conflict_copies.py` | Reconcile numbered sync copies without discarding unique project data. |
| `core.py` | Record exactus core: session summaries and report rendering. |
| `crawler.py` | Build a concrete visit plan covering every reachable app interface. |
| `diagnostics.py` | Collect browser-visible diagnostics during click exploration. |
| `discovery.py` | Convert bounded crawler discoveries into editable flow documents. |
| `examples/` | Runnable demonstration for `exactus/tools/record/`. |
| `execution.py` | Deterministic graph execution, typed variables, and run snapshots. |
| `expectations.py` | Deterministic network expectation matching for Flow observations. |
| `expressions.py` | Safe deterministic expression and template evaluation for Flow execution. |
| `flow_inventory.py` | Inventory the version-3 action surface that structured flows must keep. |
| `flow_runner.py` | Execute Studio flows with assertions and durable browser evidence. |
| `http_request.py` | Send one REST request; shared by flow runs and Studio's Send. |
| `json_types.py` | JSON value types shared by the exactus tools. |
| `live_run.py` | Incremental immutable execution-run telemetry for the desktop inspector. |
| `main.py` | Record, replay, and Exactus Record browser sessions as an exactus. |
| `model.py` | Immutable models for viewports, flows, actions, and runtime artifacts. |
| `profile_emulation.py` | Apply a profile's device and media conditions to a real Chromium page. |
| `project_assets.py` | Embed and restore verified PNG assets in portable Studio projects. |
| `project_info.py` | Describe a project: its name, purpose, tags and authorship. |
| `py.typed` | PEP 561 marker declaring that the package ships inline type annotations. |
| `rebase.py` | Carry recorded URLs to wherever the application under test runs now. |
| `recorder_protocol.py` | Strict NDJSON protocol shared by GUI, recorder, and execution player. |
| `response_paths.py` | Read one value from a REST response by a JSON or XML path. |
| `run.py` | Run saved Studio flows as unattended functional tests and captures. |
| `run_gate.py` | Pause, resume and single-step a flow run between its actions. |
| `selector_engine.py` | Load the ExtendedSelector package engine as an injectable script. |
| `selector_probes.py` | Publish selector probes as variables for conditions. |
| `selector_resolve.js` | JavaScript module. |
| `selector_resolver.py` | Resolve stored selector expressions to CSS in the target page. |
| `selector_sandbox.js` | JavaScript module. |
| `selector_sandbox.py` | Run JavaScript actions in the isolated sandbox with run-wide streams. |
| `selector_scripts.d.ts` | JavaScript module. |
| `selector_snapshot.py` | Compare a matched element with the baseline recorded for a snapshot. |
| `selector_targets.py` | Turn an action's selector reference into the targets it will act on. |
| `selector_usage.py` | Find where selectors are used, and keep references valid on rename. |
| `selectors.py` | Reusable selectors, targeting modes and pacing for recorded actions. |
| `similarity.py` | Multi-factor perceptual image similarity scoring. |
| `sprint.py` | Shared flushed-writer printing helpers for scripts and examples. |
| `store.py` | Deterministic Flow workspace state and JSON persistence. |
| `studio/` | Subdirectory. |
| `templates/` | Subdirectory. |
| `visit.py` | Replay a crawler visit plan across parallel device and theme lanes. |
| `workspace_actions.py` | Convert selector-based recorded actions and current workspace documents. |

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--url` | Absolute URL to open in the recorder, replay against, or open in the managed Studio test browser. | default=None, type=str |
| `--width` | Viewport width in CSS pixels. | type=int, default=1440 |
| `--height` | Viewport height in CSS pixels. | type=int, default=1000 |
| `--timeout-ms` | Navigation and per-action timeout in milliseconds. | type=float, default=5000.0 |
| `--preserve-timing` | Emit recorded inter-action delays in generated programs. | action='store_true', default=False |
| `--replay` | Replay an actions.normalized.json program or a Exactus Record .pwflow.json workspace instead of recording. | type=Path, default=None |
| `--flow` | Flow id to replay from a workspace (default: the first Flow). | default=None |
| `--headless` | Run the managed test browser without a visible window. | action='store_true', default=False |
| `--port` | Loopback Studio service port; zero selects an available port. | type=int, default=0 |
| `--no-open` | Serve Studio without opening the editor browser. | action='store_true' |
| `--window` | Open the managed browser window with Studio and stop Studio when that window is closed. | action=BooleanOptionalAction, default=False |
| `--duration` | Optional Studio session duration in seconds. | type=float, default=None |
| `--flow-id` | Flow id used when exporting to a Exactus Record workspace. | default='exactus-recording' |
| `--flow-name` | Flow name used when exporting to a Exactus Record workspace. | default='Exactus recording' |
| `--workspace` | f'Extra destination for the exported workspace (always written as {Constants.workspace_name} in the output).' | type=Path, default=None |
| `--crawl` | Discover action sequences and export a Studio project. | action='store_true' |
| `--max-depth` |  | type=int, default=2 |
| `--max-states` |  | type=int, default=20 |
| `--include-selector` | Optional CSS selector limiting discovery targets. | default=None |
| `workspace` |  | type=Path |
| `--flow` | Entry flow ID; omit to test workflow entry points |  |
| `--url` | Optional initial page; recorded navigations still execute |  |
| `--output` |  | type=Path, default=Path('EXACTUS_RESULTS/FLOWS') |
| `--width` |  | type=int, default=1440 |
| `--height` |  | type=int, default=900 |
| `--headed` |  | action='store_true' |
| `--workers` |  | type=int, default=4 |
| `--screenshots` | Capture every executed step | action='store_true' |
| `--project` |  | type=Path, default=Path.cwd() |
| `--port` |  | type=int, default=0 |
| `--headed` | Also show the test browser in its own window, for debugging. | action='store_true' |
| `--headless` | SUPPRESS | action='store_true' |
| `--no-open` |  | action='store_true' |
| `--url` |  |  |
| `--duration` |  | type=float |
| `--window` | Open the managed browser window with Studio and stop Studio when that window is closed (default: [tool.exactus.record] window, else false). | action=BooleanOptionalAction, default=None |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Own browser recording, crawling, diagnostics, and flow execution.


### `action_recorder.py`

Record, normalize, compile, and replay interactive Playwright actions.

- `class RecorderOptions` — Configure one interactive recording session.
  - `width` = `1440`
  - `height` = `1000`
  - `timeout_ms` = `5000.0`
  - `preserve_timing` = `False`
  - Fields: `url: str`, `output: Path`
- `class ReplayOptions` — Configure one replay session.
  - `width` = `1440`
  - `height` = `1000`
  - `headless` = `False`
  - `timeout_ms` = `30000.0`
- `class LocatorCompiler` — Compile structured locator candidates into Playwright syntax.
  - `python(cls, *, target: Action) -> str` — Compile the strongest target locator to Python Playwright.
  - `javascript(cls, *, target: Action) -> str` — Compile the strongest target locator to JavaScript Playwright.
  - `candidate(*, target: Action) -> Action | None` — Return the strongest recorded locator candidate, if any.
- `class ActionNormalizer` — Collapse noisy raw browser events into semantic replay actions.
  - `normalize(cls, *, actions: Sequence[Action]) -> list[Action]` — Normalize, deduplicate, and collapse replaceable actions.
- `class ActionCompiler` — Compile normalized semantic actions into runnable source code.
  - `python(cls, *, action: Action) -> str | None` — Compile one semantic action to a Python Playwright statement.
  - `javascript(cls, *, action: Action) -> str | None` — Compile one semantic action to a JavaScript Playwright statement.
  - `write(cls, *, actions: Sequence[Action], output: Path, preserve_timing: bool=False) -> None` — Write normalized JSON and Python/JavaScript replay programs.
  - `target(*, action: Action, key: str='target') -> Action | None` — Return the dict-valued ``key`` entry of ``action``, if any.
  - `key(*, action: Action) -> str` — Render the action's keypress as a ``Mod+Key`` chord.
- `class ActionRecorder` — Own one headed Playwright recording session.
  - `__init__(self, *, options: RecorderOptions, on_action: Callable[[Action], None] | None=None) -> None` — Initialize the session around ``options``.
  - `actions(self) -> list[Action]` — Raw actions recorded so far.
  - `instrument(self, *, page: Page) -> None` — Attach the recorder hooks and script to an existing page.
  - `run(self) -> list[Action]` — Record until the browser closes, then normalize and compile.
- `class Constants` — Group module-level constants.
  - `python_emitters` = `{'wait': _emit_python_wait, 'position_pointer': _emit_python_position, 'c...`
  - `javascript_emitters` = `{'wait': _emit_javascript_wait, 'position_pointer': _emit_javascript_posi...`
  - `performers` = `{'wait': _replay_wait, 'position_pointer': _replay_position, 'click': _re...`
- `class ActionReplayer` — Replay normalized actions without evaluating generated source code.
  - `__init__(self, *, url: str, actions: Sequence[Action], options: ReplayOptions | None=None) -> None` — Initialize the replayer with a start URL and action program.
  - `locate(*, page: Page, target: Action) -> Locator` — Resolve a recorded target to a live ``Locator``.
  - `perform(self, *, page: Page, action: Action) -> None` — Replay one normalized action against ``page``.
  - `run(self) -> list[str]` — Replay the normalized action sequence, collecting failures.
- `load_actions(*, path: Path) -> list[Action]` — Load normalized JSON actions.

### `action_schema.py`

Define typed action inputs, outputs and stable value-source bindings.

- `class FlowValueType` — Name every value category accepted by an action contract.
  - `STRING` = `'string'`
  - `INTEGER` = `'integer'`
  - `FLOAT` = `'float'`
  - `NUMBER` = `'number'`
  - `BOOLEAN` = `'boolean'`
  - `JSON` = `'json'`
  - `URL` = `'url'`
  - `SELECTOR` = `'selector'`
  - `DURATION` = `'duration'`
  - `ARTIFACT` = `'artifact'`
  - `LIST` = `'list'`
  - `VOID` = `'void'`
  - `ENUM` = `'enum'`
  - `EXPRESSION` = `'expression'`
  - `VARIABLE_REF` = `'variable_ref'`
  - `VARIABLE_TYPE` = `'variable_type'`
  - `INFERRED` = `'inferred'`
  - `DEVICE_STATE` = `'device_state'`
  - `BROWSER_PAGE` = `'browser.page'`
  - `BROWSER_FRAME` = `'browser.frame'`
  - `BROWSER_DOWNLOAD` = `'browser.download'`
  - `BROWSER_DIALOG` = `'browser.dialog'`
- `class BindingKind` — Identify how an input obtains its value.
  - `LITERAL` = `'literal'`
  - `ACTION_OUTPUT` = `'action_output'`
  - `VARIABLE` = `'variable'`
  - `TEMPLATE` = `'template'`
  - `PROMPT` = `'prompt'`
- `class SlotSensitivity` — Describe which sensitivity an input slot accepts.
  - `PUBLIC` = `'public'`
  - `ACCEPTS_SENSITIVE` = `'accepts_secret'`
  - `SENSITIVE_ONLY` = `'secret_only'`
- `class PortSensitivity` — Describe the sensitivity an output publishes.
  - `PUBLIC` = `'public'`
  - `INHERITED` = `'inherited'`
  - `SENSITIVE` = `'secret'`
- `class ExposureDestination` — Name a destination to which an action can expose an input.
  - `PAGE` = `'page'`
  - `NETWORK` = `'network'`
  - `LOG` = `'log'`
  - `SCREENSHOT` = `'screenshot'`
  - `ERROR` = `'error'`
  - `EVIDENCE` = `'evidence'`
- `class EvaluationTiming` — Choose when an input binding is evaluated.
  - `COMPILE` = `'compile'`
  - `NODE_ENTRY` = `'node_entry'`
  - `EACH_ATTEMPT` = `'each_attempt'`
- `class LiteralBindingValue` — Wrap a literal so JSON null differs from an absent payload.
  - Fields: `value: JsonValue`
- `class ActionOutputReference` — Identify one published action result independently of its label.
  - `path` = `()`
  - `getter` = `None`
  - Fields: `producer_id: str`, `port_id: str`
  - `source_id(self) -> str` — Return the stable identity used by indexes and persisted links.
- `class ActionInputBinding` — Bind one input slot to exactly one kind-specific payload.
  - `literal` = `None`
  - `action_output` = `None`
  - `variable_id` = `None`
  - `template` = `None`
  - `prompt` = `None`
  - `timing` = `EvaluationTiming.NODE_ENTRY`
  - Fields: `kind: BindingKind`
  - `hard_dependency_id(self) -> str | None` — Return the producer action that must precede this binding.
- `class InputSlot` — Define one typed action input and its secret destination policy.
  - `many` = `False`
  - `item_type` = `None`
  - `sensitivity` = `SlotSensitivity.PUBLIC`
  - `exposes_to` = `frozenset()`
  - `allows_each_attempt` = `False`
  - Fields: `slot_id: str`, `value_type: FlowValueType`, `required: bool`
  - `accepts_secret(self, *, secret: bool) -> bool` — Return whether a value's sensitivity can enter this slot.
  - `accepts_timing(self, *, timing: EvaluationTiming) -> bool` — Return whether the slot permits the requested evaluation timing.
- `class OutputPort` — Define one stable result published by an action.
  - `nullable` = `False`
  - `primary` = `False`
  - `item_type` = `None`
  - `sensitivity` = `PortSensitivity.PUBLIC`
  - Fields: `port_id: str`, `value_type: FlowValueType`
- `class ActionSchema` — Define the complete input/output interface of one action kind.
  - `dynamic_inputs` = `False`
  - `dynamic_outputs` = `False`
  - Fields: `action_id: str`, `inputs: tuple[InputSlot, ...]`, `outputs: tuple[OutputPort, ...]`
- `hard_dependency_ids(*, bindings: tuple[ActionInputBinding, ...]) -> tuple[str, ...]` — Return producer IDs in first-use order without duplicates.

### `arguments.py`

Declare the record grammar without importing its execution engine.

- `class Constants` — Group module-level constants.
  - `workspace_name` = `'recording.pwflow.json'`
- `create_parser() -> ArgumentParser` — Create the recorder command-line parser.

### `assertions.py`

Generic assertion comparison shared by UI, protocol, and test runtime.

- `class AssertionEvaluationError` — Represent AssertionEvaluationError.
- `class AssertionEvaluator` — Represent AssertionEvaluator.
  - `evaluate(cls, *, assertion: AssertionSpec, actual: str | None, exists: bool) -> AssertionResult` — Return evaluate.

### `capture_screen.py`

Capture screenshots with arbitrarily nested overflow fully exposed.

- `class CaptureScreenDefaults` — Store immutable scalar configuration values.
  - `max_capture_height` = `8192`
  - `max_iterations` = `30`
  - `tolerance` = `1`
- `class Js` — Store browser-side JavaScript.
  - `EXPAND` = `dedent(text='\n        root => {\n            const state = window.__snap...`
  - `MEASURE` = `dedent(text='\n        root => {\n            const {top, bottom} = root....`
  - `SETTLE` = `dedent(text='\n        () => new Promise(resolve =>\n            requestA...`
  - `RESTORE` = `dedent(text='\n        () => {\n            const state = window.__snapsh...`
- `class Capture` — Represent a captured PNG.
  - Fields: `data: bytes`, `path: Path | None`, `truncated_height: bool`
  - `b64(self: Self) -> str` — Base64-encoded PNG data.
- `class CaptureSpec` — Describe capture-time options for the high-level API.
  - `path` = `None`
  - `width` = `1440`
  - `height` = `900`
  - `timeout_seconds` = `30.0`
  - `max_height` = `CaptureScreenDefaults.max_capture_height`
  - `target_only` = `False`
  - `image_type` = `'png'`
  - `quality` = `None`
  - `scale` = `'css'`
  - `user_agent` = `None`
  - `is_mobile` = `False`
  - `has_touch` = `False`
  - `color_scheme` = `None`
- `class SnapshotOptions` — Capture options for `SnapshotCapture`.
  - `max_height` = `CaptureScreenDefaults.max_capture_height`
  - `target_only` = `False`
  - `image_type` = `'png'`
  - `quality` = `None`
  - `scale` = `'css'`
- `class SnapshotCapture` — Capture a page with all nested target overflow exposed.
  - `__init__(self: Self, page: Page, target: str, *, options: SnapshotOptions | None=None) -> None` — Initialize the capture.
  - `capture(self: Self, path: Path | None=None) -> Capture` — Capture the expanded page and optionally save it.
- `class Screenshot` — Provide a high-level URL screenshot API.
  - `capture(url: str | None, target: str, spec: CaptureSpec | None=None, *, source: Browser | BrowserContext | Page | None=None) -> Capture` — Load a URL and capture its fully exposed target.

### `causality.py`

Deterministic causal attribution for recorded browser observations.

- `class Constants` — Group module-level constants.
  - `maximum_causal_window_ms` = `5000`
  - `minimum_confidence` = `0.35`
  - `minimum_winner_margin` = `0.08`
  - `temporal_weight` = `0.45`
  - `correlation_weight` = `0.4`
  - `initiator_weight` = `0.1`
  - `stack_weight` = `0.05`
  - `observation_kinds` = `frozenset({EventKind.REQUEST, EventKind.RESPONSE, EventKind.WEBSOCKET_OPE...`
- `class AttributionCandidate` — Represent AttributionCandidate.
  - Fields: `event_id: str`, `confidence: float`, `reasons: tuple[str, ...]`
- `class AttributionDecision` — Represent AttributionDecision.
  - Fields: `event: TimelineEvent`, `candidates: tuple[AttributionCandidate, ...]`, `inferred: bool`
- `class CausalAttributor` — Represent CausalAttributor.
  - `attribute(cls, *, observation: TimelineEvent, prior_events: tuple[TimelineEvent, ...]) -> AttributionDecision` — Return attribute.

### `click_explorer.py`

Explore clickable states and capture visually distinctive screens.

- `class ExplorerDefaults` — Store immutable exploratory-crawler defaults.
  - `CLICKABLE` = `"a[href],button,input[type=button],input[type=submit],input[type=reset],i...`
  - `DANGEROUS` = `re_compile(pattern='\\b(delete|remove|destroy|erase|wipe|format|purchase|...`
  - `MUTATING_METHODS` = `frozenset({'DELETE', 'PATCH', 'POST', 'PUT'})`
  - `TARGET` = `'body'`
  - `MAP_SHARE` = `0.3`
  - `PROBES_PER_STATE` = `2`
  - `DESCRIBE` = `dedent(text='    element => {\n      const step = (node) => {\n        if...`
  - `SETTLE_MS` = `500.0`
  - `TIMEOUT_MS` = `5000.0`
  - `PAGE_TIMEOUT_MS` = `30000.0`
  - `SIMILARITY` = `0.965`
  - `MAX_DEPTH` = `4`
  - `MAX_STATES` = `100`
  - `VIEWPORT_WIDTH` = `1440`
  - `VIEWPORT_HEIGHT` = `1000`
  - `TABLET_WIDTH` = `1024`
  - `TABLET_HEIGHT` = `1366`
  - `PHONE_WIDTH` = `390`
  - `PHONE_HEIGHT` = `844`
  - `DEVICE_SCALE_FACTOR` = `2.0`
- `class ClickTarget` — Describe a replayable clickable target.
  - `selector` = `''`
  - `url` = `''`
  - `x` = `0`
  - `y` = `0`
  - Fields: `index: int`, `label: str`, `tag: str`, `href: str`
  - `key(self) -> tuple[str, str, str, str, str]` — Identity used to tell whether a click unveiled this target.
- `class StateNode` — Describe one visually distinct interaction state.
  - Fields: `id: str`, `parent_id: str | None`, `path: tuple[ClickTarget, ...]`, `url: str`, `screenshot: str`, `similarity_to_parent: float | None`
- `class DiagnosticFinding` — Associate diagnostics with one tested interaction.
  - Fields: `variant: str`, `parent_id: str`, `action: ClickTarget`, `events: tuple[DiagnosticEvent, ...]`
- `class CaptureVariant` — Describe one responsive and color-scheme capture environment.
  - Fields: `name: str`, `width: int`, `height: int`, `color_scheme: Literal['dark', 'light']`, `is_mobile: bool`, `has_touch: bool`, `scale: float`
- `class LaneUpdate` — Describe one lane lifecycle transition.
  - `detail` = `''`
  - `share` = `None`
  - Fields: `name: str`, `state: str`, `completed: int`, `total: int`, `step: str`
- `class LaneReporter(Protocol)` — Publish live per-lane exploration progress.
  - `lane(self: Self, *, update: LaneUpdate) -> None` — Report one lane lifecycle transition.
  - `diagnostics(self: Self, *, events: tuple[DiagnosticEvent, ...]) -> None` — Report newly attributed diagnostic events.
- `class MatrixResult` — Carry everything one capture-matrix run observed.
  - Fields: `variants: tuple[CaptureVariant, ...]`, `results: dict[str, tuple[StateNode, ...]]`, `diagnostics: dict[str, tuple[DiagnosticEvent, ...]]`, `findings: dict[str, tuple[DiagnosticFinding, ...]]`, `blocked: dict[str, tuple[str, ...]]`, `candidates: dict[str, int]`
- `class ExplorerOptions` — Configure browser-state exploration.
  - `target` = `ExplorerDefaults.TARGET`
  - `similarity` = `ExplorerDefaults.SIMILARITY`
  - `max_depth` = `ExplorerDefaults.MAX_DEPTH`
  - `max_states` = `ExplorerDefaults.MAX_STATES`
  - `settle_ms` = `ExplorerDefaults.SETTLE_MS`
  - `timeout_ms` = `ExplorerDefaults.TIMEOUT_MS`
  - `width` = `ExplorerDefaults.VIEWPORT_WIDTH`
  - `height` = `ExplorerDefaults.VIEWPORT_HEIGHT`
  - `scale` = `ExplorerDefaults.DEVICE_SCALE_FACTOR`
  - `headless` = `True`
  - `unsafe` = `False`
  - `exhaustive` = `False`
  - `workers` = `4`
  - `only_get` = `False`
  - `capture_ui_changes` = `True`
  - `follow_links` = `True`
  - `click_controls` = `True`
  - `include_selector` = `None`
  - `variant` = `field(default_factory=lambda: CaptureVariant(name='desktop-light', width=...`
  - Fields: `url: str`, `output: Path`
- `class ClickExplorer` — Breadth-first explore and capture visually novel clickable states.
  - `__init__(self: Self, options: ExplorerOptions, reporter: LaneReporter | None=None, lane_name: str='', plan: tuple[Future[tuple[_Candidate, ...]], bool] | None=None) -> None` — Initialize the explorer.
  - `diagnostics(self: Self) -> tuple[DiagnosticEvent, ...]` — All diagnostics observed by this lane.
  - `planned(self: Self) -> int` — Click targets mapped so far (potential screenshots).
  - `findings(self: Self) -> tuple[DiagnosticFinding, ...]` — Interaction-attributed diagnostic findings.
  - `blocked(self: Self) -> tuple[str, ...]` — Mutating requests intercepted during safe exploration.
  - `run(self: Self) -> tuple[StateNode, ...]` — Run the browser exploration and return distinctive states.
- `class CaptureMatrix` — Run responsive light/dark explorations concurrently.
  - `__init__(self: Self, options: ExplorerOptions, reporter: LaneReporter | None=None) -> None` — Initialize the matrix runner.
  - `run(self: Self) -> MatrixResult` — Run all device and theme variants concurrently.

### `conflict_copies.py`

Reconcile numbered sync copies without discarding unique project data.

- `class Constants` — Group module-level constants.
  - `ignored` = `frozenset({'.history', 'node_modules', 'venv', '__pycache__', 'exactus/pa...`
- `class ClearResult` — Describe reconciled sync copies and recoverable conflicts.
  - `removed_directories` = `0`
  - `merged_entries` = `0`
  - `preserved_conflicts` = `0`
  - `errors` = `0`
- `clear_conflict_copies(*, root: Path) -> ClearResult` — Reconcile numbered directories with existing canonical counterparts.

### `core.py`

Record exactus core: session summaries and report rendering.

- `class RecordRules` — Stable identifiers of the findings the record exactus can raise.
  - `replay_failure` = `'REC001'`
  - `empty_recording` = `'REC002'`
  - `unexportable` = `'REC003'`
- `class RecordFinding` — One problem found while recording or replaying.
  - Fields: `rule: str`, `severity: str`, `message: str`
- `class RecordResult` — Outcome of one record, replay, or Exactus Record session.
  - `actions` = `()`
  - `exported_events` = `0`
  - `artifacts` = `()`
  - `workspace` = `''`
  - `failures` = `()`
  - `studio` = `field(default_factory=_no_facts)`
  - `elapsed_seconds` = `0.0`
  - Fields: `mode: str`, `url: str`
- `action_counts(*, actions: Sequence[Mapping[str, JsonValue]]) -> dict[str, int]` — Count recorded actions by type.
- `findings(*, result: RecordResult) -> tuple[RecordFinding, ...]` — Derive the exactus findings of one session.
- `passed(*, result: RecordResult) -> bool` — Report whether a session raised no error finding.
- `class Constants` — Group module-level constants.
  - `rule_titles` = `{RecordRules.replay_failure: 'Replay action failed', RecordRules.empty_re...`
  - `id_prefix` = `'RECORD'`
- `report_data(*, result: RecordResult) -> dict[str, JsonValue]` — Return the normalized JSON payload of one record session.

### `crawler.py`

Build a concrete visit plan covering every reachable app interface.

- `class CrawlerDefaults` — Store immutable crawler configuration values.
  - `app_url` = `'http://127.0.0.1:8000'`
  - `content` = `'#main-content'`
  - `nav_buttons` = `'.sv-navigation-rail button[data-value]'`
  - `nav_links` = `"a[href*='#/']"`
  - `button` = `'#main-content button:visible'`
  - `select` = `'#main-content select:visible'`
  - `toggle` = `'#main-content input[type=checkbox]:visible,#main-content input[type=radi...`
  - `setup_selector` = `'.vmim-setup'`
  - `mutating_methods` = `frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})`
  - `theme_key` = `'vmim.theme'`
  - `panel_key` = `'vmim.panel'`
  - `machine_key` = `'vmim.machine'`
  - `setup_seen_key` = `'vmim.setup.seen'`
  - `trigger_allow` = `re_compile(pattern='add|new|create|connect|publish|edit|config|download|p...`
  - `trigger_deny` = `re_compile(pattern='delete|remove|stop|kill|rollback|prune|restart|reboot...`
  - `theme_switch_prefix` = `'(?:switch to|follow the|toggle)\\s+(?:the\\s+)?'`
  - `theme_switch` = `re_compile(pattern=theme_switch_prefix + '(?:system\\s+|light\\s+|dark\\s...`
  - `settle_ms` = `700`
  - `navigate_settle_ms` = `900`
  - `dialog_settle_ms` = `400`
  - `action_timeout_ms` = `5000`
  - `page_timeout_ms` = `60000`
  - `content_timeout_ms` = `15000`
- `class VisitAction` — Describe one Playwright interaction within a visit.
  - `index` = `0`
  - `text` = `''`
  - `value` = `''`
  - Fields: `kind: ActionKind`, `selector: str`
- `class VisitStep` — Describe one interface visit: load ``url`` then apply ``actions``.
  - `actions` = `()`
  - `id` = `''`
  - Fields: `name: str`, `url: str`
- `class DeviceSpec` — Describe one emulated device lane for the visit matrix.
  - Fields: `name: str`, `width: int`, `height: int`, `scale_factor: float`, `mobile: bool`, `touch: bool`
  - `parse(cls, data: dict[str, JsonValue]) -> DeviceSpec | None` — Rebuild one device preset from a decoded plan entry.
- `class Constants` — Group module-level constants.
  - `devices` = `(DeviceSpec(name='desktop', width=1440, height=900, scale_factor=2.0, mob...`
  - `themes` = `('light', 'dark')`
- `class VisitPlan` — Describe every interface visit the application exposes.
  - `themes` = `Constants.themes`
  - `devices` = `Constants.devices`
  - `visits` = `()`
  - Fields: `base_url: str`
  - `parse(cls, data: dict[str, JsonValue]) -> VisitPlan` — Rebuild a plan from decoded JSON.
- `slug(value: str) -> str` — Convert arbitrary text to a filesystem-safe short slug.
- `visit_id(*, name: str) -> str` — Derive a short stable identifier from a visit name.
- `dismiss_wizard(page: Page) -> None` — Walk the first-run setup dialog until it closes.
- `route_mutations(context: BrowserContext, sink: list[str]) -> None` — Block mutating HTTP methods while recording their signatures.
- `storage_seed(theme: ThemeName, machine: str) -> str` — Return the init script seeding deterministic storage state.
- `settle_content(page: Page) -> None` — Wait for rendered content and the post-navigation settle.
- `panel_urls(page: Page, base_url: str, *, version: ConsoleVersion) -> list[str]` — Discover every hash-routed interface URL in visit order.
- `dialog_visits(page: Page, *, url: str, panel: str) -> list[VisitStep]` — Record visits opening every non-destructive panel trigger.
- `option_visits(page: Page, *, url: str, panel: str) -> list[VisitStep]` — Record visits selecting every option of every panel select.
- `toggle_visits(page: Page, *, url: str, panel: str) -> list[VisitStep]` — Record visits flipping every panel checkbox and radio.
- `panel_visits(page: Page, *, url: str, panel: str) -> list[VisitStep]` — Inventory one panel plus its dialog, option, and toggle visits.
- `resolve_devices(names: str) -> tuple[DeviceSpec, ...]` — Resolve a comma-separated device list against the presets.
- `resolve_themes(names: str) -> tuple[ThemeName, ...]` — Resolve a comma-separated theme list against the presets.
- `class CrawlOptions` — Optional crawl switches.
  - `version` = `'v1'`
  - `on_progress` = `None`
- `build_plan(*, base_url: str, devices: tuple[DeviceSpec, ...], themes: tuple[ThemeName, ...], machine: str, options: CrawlOptions | None=None) -> VisitPlan` — Discover every interface visit the running application exposes.

### `diagnostics.py`

Collect browser-visible diagnostics during click exploration.

- `class Constants` — Group module-level constants.
  - `self_inflicted` = `('ERR_BLOCKED_BY_CLIENT', 'ERR_ABORTED')`
  - `http_error_min` = `400`
  - `http_server_error_min` = `500`
  - `stack_frame` = `re_compile(pattern='^\\s*at\\s+(?:(?P<function>.*?)\\s+\\()?(?P<file>.+?)...`
- `class DiagnosticEvent` — Describe one browser-observable diagnostic event.
  - `method` = `''`
  - `status` = `None`
  - `timestamp` = `''`
  - `file` = `''`
  - `line` = `None`
  - `column` = `None`
  - `function` = `''`
  - `stack` = `''`
  - Fields: `category: DiagnosticCategory`, `severity: str`, `phase: DiagnosticPhase`, `variant: str`, `action: str`, `message: str`, `url: str`
- `class EventDraft` — Carry the caller-supplied fields of one diagnostic event.
  - `method` = `''`
  - `status` = `None`
  - `file` = `''`
  - `line` = `None`
  - `column` = `None`
  - `function` = `''`
  - `stack` = `''`
  - Fields: `category: DiagnosticCategory`, `severity: str`, `message: str`, `url: str`
- `class DiagnosticCollector` — Collect and deduplicate Playwright page diagnostics.
  - `__init__(self: Self, *, variant: str) -> None` — Initialize the collector for one device/theme lane.
  - `events(self: Self) -> tuple[DiagnosticEvent, ...]` — Collected events in observation order.
  - `stack_origin(*, stack: str) -> dict[str, str]` — Read the first source location from a JavaScript stack.
  - `serialize(event: DiagnosticEvent) -> dict[str, JsonValue]` — Serialize one diagnostic event for report artifacts.
  - `mark(self: Self) -> int` — Return a cursor suitable for retrieving newly observed events.
  - `since(self: Self, *, mark: int) -> tuple[DiagnosticEvent, ...]` — Return events observed after a previous cursor.
  - `phase(self: Self, *, phase: DiagnosticPhase, action: str='') -> None` — Set attribution for subsequently observed diagnostics.
  - `attach(self: Self, *, page: Page) -> None` — Attach diagnostic listeners to a Playwright page.
  - `attach_sync(self: Self, *, page: sync_api.Page) -> None` — Attach listeners and Chromium console stack capture.
  - `attach_async(self: Self, *, page: async_api.Page) -> None` — Attach async page listeners and Chromium console stacks.

### `discovery.py`

Convert bounded crawler discoveries into editable flow documents.

- `class CrawlRequest` — Configure target discovery and the resulting Studio project.
  - `max_depth` = `2`
  - `max_states` = `20`
  - `capture_ui_changes` = `True`
  - `follow_links` = `True`
  - `click_controls` = `True`
  - `include_selector` = `None`
  - Fields: `url: str`
- `discover(*, options: ExplorerOptions, cancelled: Callable[[], bool], emit: Callable[[Event], None]) -> None` — Explore a bounded target and publish replayable flows.
- `discovered_flow(*, state: StateNode, options: ExplorerOptions, prefixes: dict[tuple[ClickTarget, ...], StateNode], flow_number: int) -> tuple[Event, list[Event]]` — Build an editable action sequence with optional UI checkpoints.

### `examples/__init__.py`

Provide runnable Exactus Record workspace examples.


### `examples/__main__.py`

Inspect the bundled branching Record workspace.


### `examples/run.py`

Load and summarize the bundled branching Record workspace.

- `main() -> int` — Validate the example workspace and print its graph size.

### `execution.py`

Deterministic graph execution, typed variables, and run snapshots.

- `class Constants` — Group module-level constants.
  - `system_flow_succeeded` = `'flow_succeeded'`
  - `system_flow_failed` = `'flow_failed'`
- `class ExecutionError` — Represent ExecutionError.
- `class EdgeTraversalCount` — Represent EdgeTraversalCount.
  - Fields: `source_flow_id: str`, `target_flow_id: str`, `mode: TransitionMode`, `condition_expression: str | None`, `count: int`
- `class ExecutionState` — Represent ExecutionState.
  - `action_records` = `()`
  - `transitions` = `()`
  - `traversal_counts` = `()`
  - `follow_connections` = `True`
  - Fields: `run_id: str`, `initial_flow_id: str`, `current_flow_id: str`, `device_mode: str`, `started_at_utc: str`, `variables: tuple[RuntimeVariable, ...]`
- `class FlowDispatchRequest` — Represent FlowDispatchRequest.
  - `restore_checkpoint_artifact_id` = `None`
  - `origin` = `None`
  - `selectors` = `()`
  - `probes` = `()`
  - `project_id` = `''`
  - `project_name` = `''`
  - `project_revision` = `''`
  - `context_base_url` = `''`
  - Fields: `run_id: str`, `flow: Flow`, `device_mode: str`, `variables: tuple[RuntimeVariable, ...]`
- `class CheckpointCaptureRequest` — Represent CheckpointCaptureRequest.
  - Fields: `run_id: str`, `checkpoint_id: str`, `flow_id: str`, `event_id: str | None`
- `class ExecutionDecision` — Represent ExecutionDecision.
  - Fields: `state: ExecutionState | None`, `next_flow_id: str | None`, `completed_run: ExecutionRun | None`, `selected_edge: FlowEdge | None`
- `class VariableResolver` — Represent VariableResolver.
  - `initial_variables(cls, *, workspace: Workspace, supplied: tuple[RuntimeVariable, ...]) -> tuple[RuntimeVariable, ...]` — Return initial variables.
  - `validate_flow_parameters(cls, *, flow: Flow, variables: tuple[RuntimeVariable, ...]) -> tuple[RuntimeVariable, ...]` — Return validate flow parameters.
  - `merge(*, current: tuple[RuntimeVariable, ...], updates: tuple[RuntimeVariable, ...]) -> tuple[RuntimeVariable, ...]` — Return merge.
  - `redact(*, variables: tuple[RuntimeVariable, ...]) -> tuple[RuntimeVariable, ...]` — Return redact.
- `class ExecutionStartRequest` — Represent ExecutionStartRequest.
  - `supplied_variables` = `()`
  - `follow_connections` = `True`
  - Fields: `run_id: str`, `initial_flow_id: str`, `device_mode: str`, `started_at_utc: str`
- `class ExecutionEngine` — Represent ExecutionEngine.
  - `start(cls, *, workspace: Workspace, request: ExecutionStartRequest) -> ExecutionState` — Return start.
  - `complete_flow(cls, *, workspace: Workspace, state: ExecutionState, result: FlowExecutionResult, finished_at_utc: str) -> ExecutionDecision` — Return complete flow.

### `expectations.py`

Deterministic network expectation matching for Flow observations.

- `class ExpectationEvaluationError` — Represent ExpectationEvaluationError.
- `class NetworkExpectationEvaluator` — Represent NetworkExpectationEvaluator.
  - `evaluate(cls, *, expectation: NetworkExpectation, response: TimelineEvent) -> tuple[bool, str]` — Return evaluate.

### `expressions.py`

Safe deterministic expression and template evaluation for Flow execution.

- `class Constants` — Group module-level constants.
  - `template_pattern` = `re_compile(pattern='\\$\\{([A-Za-z_][\\w.-]*)\\}')`
  - `allowed_functions` = `frozenset({'contains', 'exists', 'matches'})`
  - `binary_argument_count` = `2`
- `class ExpressionError` — Represent ExpressionError.
- `class ValueCodec` — Represent ValueCodec.
  - `coerce(cls, *, value_type: ValueType, value: ScalarValue) -> ScalarValue` — Return coerce.
  - `render(*, variable: RuntimeVariable) -> str` — Return render.
- `class ExpressionEvaluator` — Represent ExpressionEvaluator.
  - `evaluate(cls, *, expression: str, variables: tuple[RuntimeVariable, ...]) -> bool` — Return evaluate.
  - `validate(*, expression: str) -> None` — Handle validate.
  - `interpolate(*, template: str, variables: tuple[RuntimeVariable, ...]) -> str` — Return interpolate.

### `flow_inventory.py`

Inventory the version-3 action surface that structured flows must keep.

- `class Constants` — Group module-level constants.
  - `catalog_pattern` = `'\\bid: "([a-z_]+)"'`
  - `command_pattern` = `'^\\s+"([a-z_]+\\.[a-z_.]+)": self\\._command'`
  - `runner_pattern` = `'event\\.kind is EventKind\\.([A-Z_]+)'`
  - `catalog_aliases` = `(('touch_tap', 'gesture'), ('touch_long_press', 'gesture'), ('touch_swipe...`
  - `catalog_multi` = `(('pointer', ('click', 'double_click', 'right_click', 'hover', 'drag', 's...`
  - `guard_ids` = `('if',)`
- `class ActionInventory` — Hold the four views of the action surface that must agree.
  - Fields: `event_kinds: tuple[str, ...]`, `catalog_ids: tuple[str, ...]`, `controller_commands: tuple[str, ...]`, `runner_special_kinds: tuple[str, ...]`
- `catalog_ids(*, source: str) -> tuple[str, ...]` — List the action ids declared in the JavaScript catalog.
- `controller_commands(*, source: str) -> tuple[str, ...]` — List the commands the Studio controller dispatches.
- `runner_special_kinds(*, source: str) -> tuple[str, ...]` — List the event kinds the runner executes through a special path.
- `kinds_for_catalog_id(*, catalog_id: str) -> tuple[str, ...]` — Resolve every event kind a catalog id can execute as.
- `kind_for_catalog_id(*, catalog_id: str) -> str | None` — Resolve the single event kind a catalog id executes as.
- `build_inventory(*, record: Path) -> ActionInventory` — Measure the action surface from the working tree.
- `render_matrix(*, inventory: ActionInventory) -> str` — Render the parity matrix as Markdown.
- `main() -> None` — Write the parity matrix for the working tree to standard output.

### `flow_runner.py`

Execute Studio flows with assertions and durable browser evidence.

- `class Constants` — Group module-level constants.
  - `path_token` = `compile_pattern(pattern='\\{\\{(?P<name>[^{}.\\[\\]|]+)(?P<path>(?:\\.[^{...`
  - `path_step` = `compile_pattern(pattern='\\.([^{}.\\[\\]|]+)|\\[(\\d+)\\]')`
- `class EvidenceRequest` — Describe what a screenshot belongs to and how to leave the page.
  - `after_capture` = `None`
  - Fields: `flow_id: str`, `event_id: str`, `phase: str`
- `capture_evidence(*, page: Page, output: Path, request: EvidenceRequest) -> Event` — Capture a PNG with dimensions and an integrity hash.
- `class FlowRunner` — Replay actions, check contracts, and report every attempted step.
  - `__init__(self, *, output: Path, timeout_ms: float=5000, emit: Callable[[Event], None] | None=None, cancelled: Callable[[], bool] | None=None, after_capture: Callable[[Page], None] | None=None) -> None` — Configure the artifact directory, timeout, and protocol sink.
  - `run(self, *, page: Page, message: Event) -> Event` — Execute one Flow and emit run and artifact messages.

### `http_request.py`

Send one REST request; shared by flow runs and Studio's Send.

- `class PreparedRequest` — A request whose variables are already expanded.
  - Fields: `method: str`, `url: str`, `headers: Mapping[str, str]`, `body: str`, `timeout_ms: float`
- `class HttpResult` — What a sent request returned.
  - Fields: `status: int`, `url: str`, `headers: dict[str, str]`, `body: str`, `json: JsonValue`, `elapsed_ms: int`
- `cookie_header(*, rows: JsonValue) -> str | None` — Join the enabled cookie rows of a request into a ``Cookie`` value.
- `send_request(*, context: APIRequestContext, request: PreparedRequest) -> HttpResult` — Send a prepared request and describe the response.

### `json_types.py`

JSON value types shared by the exactus tools.

- `class JsonDict` — Dictionary with a formatted JSON representation.
  - `tojson(self) -> str` — Formatted JSON serialization of this dictionary.

### `live_run.py`

Incremental immutable execution-run telemetry for the desktop inspector.

- `class RunProgress` — Represent RunProgress.
  - `flow_id` = `None`
  - `event_id` = `None`
  - `status` = `None`
  - `started_at_utc` = `None`
  - `finished_at_utc` = `None`
  - `action_record` = `None`
  - `transition` = `None`
  - `variables` = `()`
  - `error` = `None`
  - Fields: `message_type: str`, `run_id: str`
- `class LiveRunAccumulator` — Represent LiveRunAccumulator.
  - `__init__(self) -> None` — Handle init.
  - `get(self, *, run_id: str) -> ExecutionRun | None` — Return get.
  - `accept(self, *, progress: RunProgress, device_mode: str) -> ExecutionRun` — Return accept.
  - `finalize(self, *, run: ExecutionRun) -> ExecutionRun` — Return finalize.

### `main.py`

Record, replay, and Exactus Record browser sessions as an exactus.

- `class Constants` — Group module-level constants.
  - `max_crawl_depth` = `10`
  - `max_crawl_states` = `200`
- `create_parser() -> ArgumentParser` — Return the shared CLI grammar used by execution and completion.
- `parse_args(*, arguments: tuple[str, ...] | None=None) -> Namespace` — Parse the recorder command line.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Run the record exactus.

### `model.py`

Immutable models for viewports, flows, actions, and runtime artifacts.

- `class RecorderCommandName` — Represent RecorderCommandName.
  - `RECORD` = `'record'`
  - `PAUSE` = `'pause'`
  - `WAIT` = `'wait'`
  - `VIEWPORT` = `'viewport'`
  - `ACTIVE_FLOW` = `'active_flow'`
- `class TimelineLayer` — Represent TimelineLayer.
  - `INTERACTION` = `'interaction'`
  - `NAVIGATION` = `'navigation'`
  - `NETWORK` = `'network'`
  - `WEBSOCKET` = `'websocket'`
  - `CONSOLE` = `'console'`
  - `TIMING` = `'timing'`
- `class DeviceMode` — Represent DeviceMode.
  - `SHARED` = `'shared'`
  - `MOBILE` = `'mobile'`
  - `TABLET` = `'tablet'`
  - `DESKTOP` = `'desktop'`
  - `CUSTOM` = `'custom'`
- `class CapturePhase` — Represent CapturePhase.
  - `RECORD` = `'record'`
  - `PLAY` = `'play'`
- `class UrlMatchMode` — Represent UrlMatchMode.
  - `EXACT` = `'exact'`
  - `CONTAINS` = `'contains'`
  - `GLOB` = `'glob'`
  - `REGEX` = `'regex'`
- `class BodyMatchMode` — Represent BodyMatchMode.
  - `NONE` = `'none'`
  - `EXACT_TEXT` = `'exact_text'`
  - `JSON_EXACT` = `'json_exact'`
  - `JSON_CONTAINS` = `'json_contains'`
- `class ConditionOperator` — Represent ConditionOperator.
  - `EXISTS` = `'exists'`
  - `EQUALS` = `'equals'`
  - `NOT_EQUALS` = `'not_equals'`
  - `CONTAINS` = `'contains'`
  - `REGEX` = `'regex'`
- `class PositionPointerAction` — Represent PositionPointerAction.
  - `CLICK` = `'click'`
  - `DOUBLE_CLICK` = `'double_click'`
  - `RIGHT_CLICK` = `'right_click'`
  - `HOVER` = `'hover'`
  - `DRAG` = `'drag'`
  - `SCROLL` = `'scroll'`
  - `GESTURE` = `'gesture'`
- `class ExpectationOutcome` — Represent ExpectationOutcome.
  - `SUCCEEDED` = `'pass'`
  - `FAILED` = `'fail'`
  - `TIMED_OUT` = `'timeout'`
- `class ValueType` — Represent ValueType.
  - `STRING` = `'string'`
  - `INTEGER` = `'integer'`
  - `FLOAT` = `'float'`
  - `BOOLEAN` = `'boolean'`
  - `JSON` = `'json'`
  - `URL` = `'url'`
  - `SELECTOR` = `'selector'`
  - `DURATION` = `'duration'`
  - `ARTIFACT` = `'artifact'`
  - `LIST` = `'list'`
  - `VOID` = `'void'`
- `class VariableScope` — Represent VariableScope.
  - `FLOW` = `'flow'`
  - `RUN` = `'run'`
  - `WORKSPACE` = `'workspace'`
  - `ENVIRONMENT` = `'environment'`
  - `CREDENTIAL` = `'secret'`
- `class AssertionKind` — Represent AssertionKind.
  - `DOM_VISIBLE` = `'dom_visible'`
  - `DOM_HIDDEN` = `'dom_hidden'`
  - `DOM_TEXT` = `'dom_text'`
  - `DOM_ATTRIBUTE` = `'dom_attribute'`
  - `DOM_COUNT` = `'dom_count'`
  - `URL` = `'url'`
  - `TITLE` = `'title'`
  - `COOKIE` = `'cookie'`
  - `LOCAL_STORAGE` = `'local_storage'`
  - `SESSION_STORAGE` = `'session_storage'`
  - `CONSOLE` = `'console'`
  - `JAVASCRIPT` = `'javascript'`
- `class AssertionOperator` — Represent AssertionOperator.
  - `EXISTS` = `'exists'`
  - `NOT_EXISTS` = `'not_exists'`
  - `EQUALS` = `'equals'`
  - `NOT_EQUALS` = `'not_equals'`
  - `CONTAINS` = `'contains'`
  - `REGEX` = `'regex'`
  - `GREATER_THAN` = `'greater_than'`
  - `GREATER_THAN_OR_EQUAL` = `'greater_than_or_equal'`
  - `LESS_THAN` = `'less_than'`
  - `LESS_THAN_OR_EQUAL` = `'less_than_or_equal'`
- `class OutputSource` — Represent OutputSource.
  - `RESPONSE_JSON_PATH` = `'response_json_path'`
  - `DOM_TEXT` = `'dom_text'`
  - `DOM_ATTRIBUTE` = `'dom_attribute'`
  - `URL` = `'url'`
  - `TITLE` = `'title'`
  - `JAVASCRIPT` = `'javascript'`
  - `VARIABLE` = `'variable'`
- `class TransitionMode` — Represent TransitionMode.
  - `ALWAYS` = `'always'`
  - `CONDITION` = `'condition'`
  - `FALLBACK` = `'fallback'`
  - `RETRY` = `'retry'`
  - `FINALLY` = `'finally'`
- `class RunStatus` — Represent RunStatus.
  - `RUNNING` = `'running'`
  - `SUCCEEDED` = `'succeeded'`
  - `FAILED` = `'failed'`
  - `CANCELLED` = `'cancelled'`
- `class ActionRunStatus` — Represent ActionRunStatus.
  - `SUCCEEDED` = `'succeeded'`
  - `FAILED` = `'failed'`
  - `SKIPPED` = `'skipped'`
  - `WARNING` = `'warning'`
- `class AssertionOutcome` — Represent AssertionOutcome.
  - `SUCCEEDED` = `'pass'`
  - `FAILED` = `'fail'`
  - `TIMED_OUT` = `'timeout'`
- `class EventKind` — Represent EventKind.
  - `CLICK` = `'click'`
  - `DOUBLE_CLICK` = `'double_click'`
  - `RIGHT_CLICK` = `'right_click'`
  - `HOVER` = `'hover'`
  - `DRAG` = `'drag'`
  - `SCROLL` = `'scroll'`
  - `GESTURE` = `'gesture'`
  - `POSITION_POINTER` = `'position_pointer'`
  - `CHECK` = `'check'`
  - `UNCHECK` = `'uncheck'`
  - `SELECT_OPTION` = `'select_option'`
  - `INPUT_TEXT` = `'input_text'`
  - `KEYSTROKE` = `'keystroke'`
  - `WAIT` = `'wait'`
  - `URL_CHANGE` = `'url_change'`
  - `JAVASCRIPT` = `'javascript'`
  - `HTTP_CALL` = `'http_call'`
  - `WEBSOCKET_CALL` = `'websocket_call'`
  - `EXTRACT_VALUE` = `'extract_value'`
  - `SET_VARIABLE` = `'set_variable'`
  - `VIEWPORT` = `'viewport'`
  - `REQUEST` = `'request'`
  - `RESPONSE` = `'response'`
  - `WEBSOCKET_OPEN` = `'websocket_open'`
  - `WEBSOCKET_SENT` = `'websocket_sent'`
  - `WEBSOCKET_RECEIVED` = `'websocket_received'`
  - `WEBSOCKET_CLOSE` = `'websocket_close'`
  - `WEBSOCKET_ERROR` = `'websocket_error'`
  - `CONSOLE` = `'console'`
  - `NOTE` = `'note'`
  - `SNAPSHOT` = `'snapshot'`
- `class Constants` — Group module-level constants.
  - `minimum_viewport_edge` = `160`
  - `maximum_viewport_edge` = `8192`
  - `minimum_scale` = `0.5`
  - `maximum_scale` = `4.0`
  - `max_profile_name_length` = `40`
  - `profile_id_pattern` = `'[a-z0-9][a-z0-9_-]{0,31}'`
  - `supported_media` = `{'prefers-color-scheme': ('light', 'dark'), 'prefers-contrast': ('no-pref...`
  - `derived_media` = `{'width': 'viewport size', 'height': 'viewport size', 'aspect-ratio': 'vi...`
  - `max_command_args` = `64`
  - `max_command_chars` = `2000`
  - `max_url_chars` = `2048`
  - `unsupported_media` = `frozenset({'color', 'color-index', 'monochrome', 'grid', 'inverted-colors...`
  - `port_max` = `65535`
  - `printable` = `32`
  - `pointer_kinds` = `frozenset({EventKind.CLICK, EventKind.DOUBLE_CLICK, EventKind.RIGHT_CLICK...`
  - `parallel_kinds` = `frozenset({EventKind.JAVASCRIPT, EventKind.INPUT_TEXT, EventKind.SELECT_O...`
  - `selector_required_kinds` = `frozenset({EventKind.CLICK, EventKind.DOUBLE_CLICK, EventKind.RIGHT_CLICK...`
  - `expectation_owner_kinds` = `frozenset({EventKind.CLICK, EventKind.DOUBLE_CLICK, EventKind.RIGHT_CLICK...`
- `class ActionLane` — Say which input device an action occupies while it runs.
  - `POINTER` = `'pointer'`
  - `KEYBOARD` = `'keyboard'`
  - `FREE` = `'free'`
- `lane_of(*, kind: EventKind) -> ActionLane` — Return the lane an action kind runs in.
- `class ViewportSize` — Represent ViewportSize.
  - Fields: `width: int`, `height: int`
  - `is_horizontal(self) -> bool` — The is horizontal value.
  - `horizontal(self) -> Self` — Return horizontal.
  - `vertical(self) -> Self` — Return vertical.
- `class Profile` — A named browser condition a flow is recorded and tested under.
  - `scale` = `1.0`
  - `screen_width` = `None`
  - `screen_height` = `None`
  - `touch` = `False`
  - `mobile` = `False`
  - `media` = `()`
  - Fields: `profile_id: str`, `name: str`, `width: int`, `height: int`
  - `device_settings(self) -> tuple[float, bool, bool, int | None, int | None]` — Settings Chromium only accepts when a browser context is created.
  - `size(self) -> ViewportSize` — The viewport this profile applies.
  - `check_media(*, name: str, value: str) -> None` — Accept only media features the test browser really emulates.
- `default_profiles() -> tuple[Profile, ...]` — Return the profiles a new project starts with.
- `class TargetMode` — How the application under test is reached.
  - `URL` = `'url'`
  - `SERVICE` = `'service'`
- `class Target` — The application a project records and tests.
  - `mode` = `TargetMode.URL`
  - `url` = `''`
  - `port` = `None`
  - `command` = `()`
  - `cwd` = `''`
  - `service_port` = `None`
  - `path` = `'/'`
  - `default_port(self) -> int` — The port used when none is given: 443 for https, else 80.
  - `origin(self, *, service_url: str | None=None) -> str | None` — Return scheme, host and port of the target, when it has one.
  - `address(self, *, service_url: str | None=None) -> str` — Return the address the browser should open.
- `class HttpHeader` — Represent HttpHeader.
  - Fields: `name: str`, `value: str`
- `class QueryCondition` — Represent QueryCondition.
  - `value` = `None`
  - Fields: `name: str`, `operator: ConditionOperator`
- `class JsonCondition` — Represent JsonCondition.
  - `value` = `None`
  - Fields: `path: str`, `operator: ConditionOperator`
- `class NetworkExpectation` — Represent NetworkExpectation.
  - `method` = `None`
  - `url_pattern` = `None`
  - `url_match` = `UrlMatchMode.EXACT`
  - `query_conditions` = `()`
  - `expected_status` = `None`
  - `expected_headers` = `()`
  - `body_match` = `BodyMatchMode.NONE`
  - `expected_body` = `None`
  - `json_conditions` = `()`
  - `timeout_ms` = `5000`
  - Fields: `expectation_id: str`, `label: str`
- `class FlowParameter` — Represent FlowParameter.
  - `required` = `True`
  - `default_value` = `None`
  - Fields: `name: str`, `value_type: ValueType`
- `class FlowOutput` — Represent FlowOutput.
  - Fields: `name: str`, `value_type: ValueType`, `expression: str`
- `class VariableDefinition` — Represent VariableDefinition.
  - `flow_id` = `None`
  - `default_value` = `None`
  - `source_name` = `None`
  - Fields: `name: str`, `value_type: ValueType`, `scope: VariableScope`
- `class RuntimeVariable` — Represent RuntimeVariable.
  - `secret` = `False`
  - Fields: `name: str`, `value_type: ValueType`, `value: str | int | float | bool | None`
- `class AssertionSpec` — Represent AssertionSpec.
  - `target` = `''`
  - `selector_id` = `None`
  - `expected` = `None`
  - `attribute` = `None`
  - `timeout_ms` = `5000`
  - Fields: `assertion_id: str`, `label: str`, `kind: AssertionKind`, `operator: AssertionOperator`
- `class OutputBinding` — Represent OutputBinding.
  - `selector` = `None`
  - `attribute` = `None`
  - Fields: `name: str`, `value_type: ValueType`, `source: OutputSource`, `expression: str`
- `class ActionContract` — Represent ActionContract.
  - `preconditions` = `()`
  - `postconditions` = `()`
  - `outputs` = `()`
  - `retry_count` = `0`
  - `retry_delay_ms` = `0`
  - `continue_on_failure` = `False`
  - `pace` = `None`
- `class EventDraft` — Represent EventDraft.
  - `selector` = `None`
  - `url` = `None`
  - `method` = `None`
  - `status` = `None`
  - `payload` = `None`
  - `headers` = `()`
  - `share_session_cookies` = `False`
  - `caused_by_event_id` = `None`
  - `position_action` = `None`
  - `x` = `None`
  - `y` = `None`
  - `end_x` = `None`
  - `end_y` = `None`
  - Fields: `layer: TimelineLayer`, `kind: EventKind`, `label: str`
- `class TimelineEvent` — Represent TimelineEvent.
  - `recording_group_id` = `None`
  - `selector` = `None`
  - `url` = `None`
  - `method` = `None`
  - `status` = `None`
  - `payload` = `None`
  - `headers` = `()`
  - `share_session_cookies` = `False`
  - `caused_by_event_id` = `None`
  - `position_action` = `None`
  - `x` = `None`
  - `y` = `None`
  - `end_x` = `None`
  - `end_y` = `None`
  - `expectations` = `()`
  - `contract` = `field(default_factory=ActionContract)`
  - `request_id` = `None`
  - `initiator_url` = `None`
  - `initiator_stack` = `()`
  - `correlation_id` = `None`
  - `attribution_confidence` = `None`
  - `attribution_reasons` = `()`
  - `selector_id` = `None`
  - `targets` = `TargetScope.FIRST`
  - `run_mode` = `RunMode.SEQUENTIAL`
  - `pace_between` = `None`
  - `sandbox` = `False`
  - `output_variable` = `None`
  - `when_expression` = `None`
  - `incomplete` = `False`
  - Fields: `event_id: str`, `flow_id: str`, `sequence: int`, `elapsed_ms: int`, `layer: TimelineLayer`, `kind: EventKind`, `label: str`
  - `supports_network_expectations(self) -> bool` — The supports network expectations value.
  - `with_sequence(self, *, sequence: int) -> Self` — Return with sequence.
  - `with_expectations(self, *, expectations: tuple[NetworkExpectation, ...]) -> Self` — Return with expectations.
  - `with_contract(self, *, contract: ActionContract) -> Self` — Return with contract.
  - `with_attribution(self, *, caused_by_event_id: str, confidence: float, reasons: tuple[str, ...]) -> Self` — Return with attribution.
- `class FlowSettings` — Represent FlowSettings.
  - `parameters` = `None`
  - Fields: `name: str`, `task_description: str`, `expected_behavior: str`, `notes: str`, `device_modes: frozenset[str]`, `capture_record_images: bool`, `capture_play_images: bool`
- `class FlowRecording` — A non-executable parent task containing captured timeline actions.
  - Fields: `recording_id: str`, `label: str`, `start_ms: int`
- `class Flow` — Represent Flow.
  - `device_modes` = `field(default_factory=lambda: frozenset({DeviceMode.SHARED}))`
  - `capture_record_images` = `False`
  - `capture_play_images` = `False`
  - `parameters` = `()`
  - `outputs` = `()`
  - `events` = `()`
  - `recordings` = `()`
  - Fields: `flow_id: str`, `name: str`, `task_description: str`, `expected_behavior: str`, `notes: str`
  - `with_events(self, *, events: tuple[TimelineEvent, ...]) -> Self` — Return with events.
  - `with_settings(self, *, settings: FlowSettings) -> Self` — Return with settings.
  - `applies_to(self, *, device_mode: str) -> bool` — Return applies to.
- `class FlowEdge` — Represent FlowEdge.
  - `mode` = `TransitionMode.ALWAYS`
  - `condition_expression` = `None`
  - `priority` = `0`
  - `max_traversals` = `1`
  - Fields: `source_flow_id: str`, `target_flow_id: str`
- `class ScreenshotArtifact` — Represent ScreenshotArtifact.
  - Fields: `artifact_id: str`, `flow_id: str`, `event_id: str`, `phase: CapturePhase`, `path: str`, `width: int`, `height: int`, `sha256: str`
- `class ExpectationResult` — Represent ExpectationResult.
  - `matched_url` = `None`
  - `actual_status` = `None`
  - `actual_body` = `None`
  - Fields: `result_id: str`, `flow_id: str`, `event_id: str`, `expectation_id: str`, `outcome: ExpectationOutcome`, `details: str`
- `class CheckpointDefinition` — Represent CheckpointDefinition.
  - `event_id` = `None`
  - `include_cookies` = `True`
  - `include_local_storage` = `True`
  - `include_session_storage` = `True`
  - `include_indexed_db` = `False`
  - `include_variables` = `True`
  - Fields: `checkpoint_id: str`, `name: str`, `flow_id: str`
- `class CheckpointArtifact` — Represent CheckpointArtifact.
  - `cookies_json` = `None`
  - `local_storage_json` = `None`
  - `session_storage_json` = `None`
  - `indexed_db_json` = `None`
  - `variables` = `()`
  - Fields: `artifact_id: str`, `checkpoint_id: str`, `run_id: str`, `flow_id: str`, `event_id: str | None`, `url: str`
- `class AssertionResult` — Represent AssertionResult.
  - `actual` = `None`
  - Fields: `assertion_id: str`, `outcome: AssertionOutcome`, `details: str`
- `class ActionRunRecord` — Represent ActionRunRecord.
  - `assertions` = `()`
  - `observed_event_ids` = `()`
  - `screenshot_artifact_ids` = `()`
  - `outputs` = `()`
  - `error` = `None`
  - `response_json` = `None`
  - `cause_json` = `None`
  - `streams_json` = `None`
  - `unit_index` = `None`
  - `unit_count` = `None`
  - Fields: `event_id: str`, `flow_id: str`, `status: ActionRunStatus`, `attempt: int`, `started_ms: int`, `finished_ms: int`
- `class FlowExecutionResult` — Represent FlowExecutionResult.
  - `action_records` = `()`
  - `outputs` = `()`
  - `error` = `None`
  - Fields: `run_id: str`, `flow_id: str`, `status: RunStatus`
- `class RunTransition` — Represent RunTransition.
  - Fields: `source_flow_id: str`, `target_flow_id: str`, `mode: TransitionMode`, `reason: str`
- `class ExecutionRun` — Represent ExecutionRun.
  - `finished_at_utc` = `None`
  - `action_records` = `()`
  - `transitions` = `()`
  - `variables` = `()`
  - `failure_reason` = `None`
  - Fields: `run_id: str`, `initial_flow_id: str`, `current_flow_id: str | None`, `device_mode: str`, `status: RunStatus`, `started_at_utc: str`
- `class Workspace` — Represent Workspace.
  - `screenshots` = `()`
  - `variables` = `()`
  - `checkpoint_definitions` = `()`
  - `checkpoint_artifacts` = `()`
  - `runs` = `()`
  - `profiles` = `field(default_factory=default_profiles)`
  - `target` = `field(default_factory=Target)`
  - `selectors` = `()`
  - `project` = `field(default_factory=ProjectInfo)`
  - Fields: `flows: tuple[Flow, ...]`, `edges: tuple[FlowEdge, ...]`
- `class RecorderCommand` — Represent RecorderCommand.
  - `flow_id` = `None`
  - `milliseconds` = `None`
  - `width` = `None`
  - `height` = `None`
  - `scale` = `None`
  - `device_mode` = `None`
  - `capture_images` = `None`
  - `recording_group_id` = `None`
  - `recording_start_ms` = `0`
  - Fields: `name: RecorderCommandName`
  - `record(cls, *, flow_id: str, device_mode: str, capture_images: bool, recording_group_id: str | None=None, recording_start_ms: int=0) -> Self` — Return record.
  - `pause(cls, *, flow_id: str) -> Self` — Return pause.
  - `wait(cls, *, flow_id: str, milliseconds: int) -> Self` — Return wait.
  - `viewport(cls, *, flow_id: str, viewport: ViewportSize, device_mode: str) -> Self` — Return viewport.
  - `active_flow(cls, *, flow_id: str) -> Self` — Return active flow.

### `profile_emulation.py`

Apply a profile's device and media conditions to a real Chromium page.

- `class MediaSession(Protocol)` — Describe the typed subset of Chromium's protocol session in use.
  - `send(self, *, method: str, params: dict[str, JsonValue]) -> JsonValue` — Send a protocol method.
- `class ScreenSize` — Pixel dimensions of a viewport or device screen.
  - Fields: `width: int`, `height: int`
- `class ContextOptions` — Browser-context options a profile controls, named as Playwright does.
  - Fields: `viewport: ScreenSize`, `device_scale_factor: float`, `is_mobile: bool`, `has_touch: bool`, `screen: NotRequired[ScreenSize]`
- `context_options(*, profile: Profile) -> ContextOptions` — Return the browser-context options that realise a profile.
- `class ProfileEmulator` — Keep media emulation alive for every page it was applied to.
  - `__init__(self) -> None` — Start without any emulated pages.
  - `apply(self, *, page: Page, profile: Profile) -> None` — Emulate a profile's media features on a page.
  - `restore(self, *, page: Page, profile: Profile) -> None` — Put touch emulation back after a full-page screenshot.
  - `release(self) -> None` — Forget every session so a closed browser leaves nothing behind.

### `project_assets.py`

Embed and restore verified PNG assets in portable Studio projects.

- `class Constants` — Group module-level constants.
  - `sha256_length` = `64`
  - `max_asset_bytes` = `8 * 1024 * 1024`
  - `max_project_assets` = `32 * 1024 * 1024`
- `embed_assets(*, document: dict[str, JsonValue], resolve: Callable[[dict[str, JsonValue]], Path]) -> dict[str, JsonValue]` — Embed known PNG screenshots without depending on machine paths.
- `restore_assets(*, document: dict[str, JsonValue], root: Path) -> dict[str, JsonValue]` — Restore verified assets exclusively into the service artifact root.

### `project_info.py`

Describe a project: its name, purpose, tags and authorship.

- `class Constants` — Group module-level constants.
  - `max_name` = `80`
  - `max_text` = `2000`
  - `max_short` = `80`
  - `max_tag` = `32`
  - `max_tags` = `20`
- `class ProjectInfoError` — Raise when project details cannot be used.
- `class ProjectInfo` — Describe a project for people and for the project gallery.
  - `name` = `''`
  - `description` = `''`
  - `tags` = `()`
  - `author` = `''`
  - `version` = `''`
  - `created_at` = `''`
- `class ProjectInfoCodec` — Convert project details to and from JSON.
  - `from_json_value(cls, *, value: JsonValue) -> ProjectInfo` — Read details saved in a project file.
  - `from_form(cls, *, data: dict[str, JsonValue], base: ProjectInfo) -> ProjectInfo` — Apply an editor form to existing details.
  - `clean_tags(*, tags: JsonValue) -> tuple[str, ...]` — Normalize tags typed by a person or read from a file.
  - `to_json_value(*, info: ProjectInfo) -> dict[str, JsonValue]` — Return the details as saved in the project file.

### `rebase.py`

Carry recorded URLs to wherever the application under test runs now.

- `class Constants` — Hosts that mean "this computer", whose port changes between runs.
  - `local_hosts` = `frozenset({'localhost', '127.0.0.1', '::1', str(object=IPv4Address(addres...`
- `rebase_url(*, url: str, origin: str | None) -> str` — Move a local URL onto the target's origin, keeping path and query.

### `recorder_protocol.py`

Strict NDJSON protocol shared by GUI, recorder, and execution player.

- `class RecorderProtocolError` — Represent RecorderProtocolError.
- `class RecorderProtocol` — Represent RecorderProtocol.
  - `encode_command(cls, *, command: RecorderCommand) -> bytes` — Return encode command.
  - `encode_play_request(cls, *, flow: Flow, device_mode: str) -> bytes` — Return encode play request.
  - `encode_dispatch_request(cls, *, request: FlowDispatchRequest) -> bytes` — Return encode dispatch request.
  - `encode_checkpoint_capture(cls, *, request: CheckpointCaptureRequest, definition: CheckpointDefinition) -> bytes` — Return encode checkpoint capture.
  - `encode_checkpoint_restore(cls, *, run_id: str, artifact_id: str) -> bytes` — Return encode checkpoint restore.
  - `encode_cancel_run(cls, *, run_id: str) -> bytes` — Return encode cancel run.
  - `decode_message(cls, *, line: bytes) -> RecorderInbound` — Return decode message.
  - `decode_event(cls, *, line: bytes) -> TimelineEvent` — Return decode event.

### `response_paths.py`

Read one value from a REST response by a JSON or XML path.

- `class Constants` — Path grammar shared by the response readers.
  - `json_step` = `compile_pattern(pattern='\\.([^{}.\\[\\]|]+)|\\[(\\d+)\\]')`
  - `xml_step` = `compile_pattern(pattern='^([^\\[\\]/@]+)(?:\\[(\\d+)\\])?$')`
- `class XmlRejectedError` — An XML response that is unsafe or malformed to read.
- `read_json_path(*, value: JsonValue, path: str) -> JsonValue` — Read a dotted or indexed path from a JSON-compatible value.
- `read_xml_path(*, text: str, path: str) -> str | None` — Read element text or an attribute from an XML document.

### `run.py`

Run saved Studio flows as unattended functional tests and captures.

- `class Constants` — Group module-level constants.
  - `mobile_max_width` = `600`
  - `tablet_max_width` = `1100`
- `class BrowserOptions` — Browser viewport and capture options.
  - `width` = `1440`
  - `height` = `900`
  - `headless` = `True`
  - `screenshots` = `False`
  - `scale` = `1.0`
  - `timeout_ms` = `5000`
  - `color_scheme` = `'light'`
  - `is_mobile` = `False`
  - `has_touch` = `False`
  - `cancelled` = `None`
  - `emit` = `None`
  - `workers` = `4`
- `class ReplayProgress` — Count completed replay events without counting retry attempts twice.
  - `completed` = `0`
  - `seen` = `field(default_factory=set)`
  - `lock` = `field(default_factory=Lock, repr=False)`
  - Fields: `observer: Callable[[Event], None] | None`, `total: int`
- `class WorkflowProgress` — Aggregate independent workflow progress without premature completion.
  - `completed` = `field(default_factory=dict)`
  - `finished` = `field(default_factory=set)`
  - `active` = `field(default_factory=dict)`
  - `lock` = `field(default_factory=Lock, repr=False)`
  - Fields: `observer: Callable[[Event], None] | None`, `budgets: dict[str, int]`
- `class WorkflowCapture` — Group workflow artifact and browser settings.
  - `profile` = `None`
  - `emulator` = `None`
  - Fields: `output: Path`, `browser: BrowserOptions`, `evidence: list[JsonValue]`, `diagnostics: DiagnosticCollector`
- `scoped_profile(*, workspace: Workspace, flow: Flow) -> Profile | None` — Find the profile an entry flow is scoped to.
- `run_workspace(*, path: Path, output: Path, flow_id: str | None=None, url: str | None=None, browser: BrowserOptions | None=None) -> Event` — Run workflow entry points and their saved connections.
- `main() -> int` — Run Studio workspaces from the command line.

### `run_gate.py`

Pause, resume and single-step a flow run between its actions.

- `class Constants` — Group module-level constants.
  - `poll_seconds` = `0.05`
- `class RunGate` — Hold a run before an action until it is resumed or stepped.
  - `__init__(self) -> None` — Start open: a run proceeds until someone pauses it.
  - `paused(self) -> bool` — Report whether a pause was requested and not yet resumed.
  - `waiting(self) -> bool` — Report whether a runner is blocked at an action boundary.
  - `pause(self) -> None` — Hold the run before its next action.
  - `resume(self) -> None` — Let the run continue without stopping again.
  - `step(self) -> None` — Let exactly one more action run, then hold the run again.
  - `reset(self) -> None` — Open the gate and forget pending steps, for a new or ended run.
  - `wait_turn(self, *, cancelled: Callable[[], bool], on_hold: Callable[[], None], on_release: Callable[[], None]) -> None` — Block until the next action may run.

### `selector_engine.py`

Load the ExtendedSelector package engine as an injectable script.

- `class Constants` — Group module-level constants.
  - `package` = `'exactus.packages.extended_selector'`
  - `relative` = `'editor/extended-selector.js'`
  - `class_export` = `'export class ExtendedSelector '`
  - `default_export` = `'export default ExtendedSelector;'`
  - `global_name` = `'__EXACTUS_ES__'`
  - `world_name` = `'exactus'`
  - `worlds` = `WeakKeyDictionary()`
- `engine_source() -> str` — Return the ExtendedSelector package engine module source.
- `engine_script() -> str` — Return the engine as a plain script that defines one global.
- `class SelectorRuntimeError` — Report a script failure inside the engine world.
- `class EngineWorld` — Keep the engine in an isolated world of one page.
  - `__init__(self, *, page: Page) -> None` — Remember the page; nothing is created until first use.
  - `evaluate(self, *, expression: str) -> JsonValue` — Run a script in the world and return its JSON result.
  - `call(self, *, function: str, argument: JsonValue) -> JsonValue` — Call a JavaScript function with one JSON argument.
- `world_for(*, page: Page) -> EngineWorld` — Return the page's engine world, creating the handle once.

### `selector_probes.py`

Publish selector probes as variables for conditions.

- `class Constants` — Group module-level constants.
  - `system_flow_succeeded` = `'flow_succeeded'`
  - `system_flow_failed` = `'flow_failed'`
  - `probe_details` = `{'count': 'How many elements match', 'exists': 'Whether anything matches'...`
  - `probe_types` = `{'count': 'integer', 'exists': 'boolean', 'visible': 'boolean', 'text': '...`
  - `pattern` = `re_compile(pattern='\\bsel_([A-Za-z][A-Za-z0-9_]*?)_(count|exists|visible...`
- `class ProbeRef` — One probe variable a condition reads.
  - Fields: `variable: str`, `selector_name: str`, `probe: str`
- `probe_refs(*, conditions: Iterable[str]) -> tuple[ProbeRef, ...]` — Find the probe variables that conditions read.
- `edge_probe_names(*, workspace: Workspace, flow_id: str) -> tuple[str, ...]` — Name the probes the connections leaving a flow read.
- `condition_vocabulary(*, workspace: Workspace) -> list[dict[str, str]]` — List the names a condition can use, for the editor's suggestions.
- `probe_variables(*, resolver: SelectorResolver, selectors: tuple[SelectorDef, ...], refs: Iterable[ProbeRef]) -> tuple[RuntimeVariable, ...]` — Measure probes in the page.
- `validate_condition(*, expression: str, selectors: tuple[SelectorDef, ...]) -> None` — Check a condition before it is saved.

### `selector_resolver.py`

Resolve stored selector expressions to CSS in the target page.

- `resolve_function() -> str` — Return the script that evaluates one expression in the page.
- `class ResolvedMatch` — Describe one element a selector matched.
  - `failed_checks` = `()`
  - Fields: `index: int`, `css: str | None`, `css_error: str | None`, `rect: dict[str, float]`, `evidence: dict[str, JsonValue]`
- `class Resolution` — Describe the outcome of resolving one expression.
  - `error` = `None`
  - `definition_errors` = `()`
  - `elapsed_ms` = `0`
  - `polls` = `1`
  - Fields: `expression: str`, `expected_count: int | None`, `count: int`, `matches: tuple[ResolvedMatch, ...]`
  - `count_ok(self) -> bool` — Return whether the match count is acceptable.
  - `checks_ok(self) -> bool` — Return whether every match satisfied every check.
  - `css_ok(self) -> bool` — Return whether every match could be turned into CSS.
  - `ok(self) -> bool` — Return whether the selector resolved cleanly.
  - `cause(self) -> dict[str, JsonValue]` — Describe why the resolution failed.
- `class SelectorResolver` — Resolve expressions against one page, using the project's selectors.
  - `__init__(self, *, page: Page, selectors: tuple[SelectorDef, ...]=(), timeout_ms: int=5000, poll_ms: int=100) -> None` — Bind the resolver to a page and the stored selectors.
  - `sample(self, *, expression: str) -> Resolution` — Evaluate an expression once, without waiting or compiling CSS.
  - `resolve_selector(self, *, selector: SelectorDef) -> Resolution` — Resolve a stored selector with its own count and checks.
  - `resolve(self, *, expression: str, expected_count: int | None=1, checks: tuple[str, ...]=(), compile_css: bool=True) -> Resolution` — Resolve an expression, waiting for the expected result.

### `selector_sandbox.py`

Run JavaScript actions in the isolated sandbox with run-wide streams.

- `class Constants` — Group module-level constants.
  - `history_keys` = `{'log': 'logs', 'warn': 'warnings', 'error': 'errors'}`
- `sandbox_function() -> str` — Return the script that runs a snippet in the sandbox.
- `class StreamEntry` — One line written to the run streams.
  - `unit` = `None`
  - `cause` = `None`
  - `at` = `0`
  - Fields: `level: str`, `source: str`, `message: str`, `flow_id: str`, `action_id: str`
- `class RunStreams` — Logs, warnings, errors and variables shared by one run's actions.
  - `entries` = `field(default_factory=list)`
  - `vars` = `field(default_factory=dict)`
  - `add(self, *, entry: StreamEntry) -> dict[str, JsonValue]` — Append one entry.
  - `history(self) -> dict[str, JsonValue]` — Return the streams in the shape the sandbox reads them.
- `class SandboxCall` — Describe one snippet run.
  - `targets` = `()`
  - `indices` = `(0,)`
  - `count` = `None`
  - `flow_name` = `''`
  - `action_kind` = `''`
  - `action_label` = `''`
  - `project_id` = `''`
  - `project_name` = `''`
  - `project_revision` = `''`
  - `context_id` = `''`
  - `context_name` = `''`
  - `context_base_url` = `''`
  - `context_origin` = `''`
  - Fields: `script: str`, `flow_id: str`, `action_id: str`, `run_id: str`
- `class SandboxResult` — The outcome of a snippet on one target.
  - Fields: `index: int`, `value: JsonValue`, `error: str | None`, `entries: tuple[dict[str, JsonValue], ...]`
- `run_sandbox(*, page: Page, call: SandboxCall, streams: RunStreams, selectors: tuple[SelectorDef, ...]=()) -> tuple[SandboxResult, ...]` — Run a snippet in the page's isolated world.
- `merge(*, streams: RunStreams, result: SandboxResult, flow_id: str, action_id: str, unit: int | None) -> None` — Store the entries a snippet produced in the run's streams.

### `selector_snapshot.py`

Compare a matched element with the baseline recorded for a snapshot.

- `class Constants` — Group module-level constants.
  - `rect_tolerance` = `16.0`
  - `compared` = `('tag', 'role', 'text', 'attributes')`
- `parse_baseline(*, payload: str | None) -> dict[str, JsonValue] | None` — Read a snapshot action's stored baseline.
- `compare_evidence(*, baseline: dict[str, JsonValue], current: dict[str, JsonValue]) -> list[dict[str, JsonValue]]` — List how the current element differs from the baseline.

### `selector_targets.py`

Turn an action's selector reference into the targets it will act on.

- `class Constants` — Group module-level constants.
  - `inline_prefix` = `'ext='`
- `class Unit` — One target of an action: the action with a concrete CSS selector.
  - `index` = `None`
  - `count` = `None`
  - `cause` = `None`
  - `selector_id` = `None`
  - `targets` = `()`
  - `position` = `0`
  - `evidence` = `None`
  - Fields: `event: TimelineEvent`
- `needs_planning(*, event: TimelineEvent) -> bool` — Tell whether an action's selector must be resolved before running.
- `failure_cause(*, failure: Exception, unit: Unit, stage: str) -> dict[str, JsonValue]` — Describe why running a target failed.
- `class TargetPlanner` — Resolve each action's selector into the targets to run.
  - `__init__(self, *, page: Page, selectors: tuple[SelectorDef, ...], timeout_ms: int) -> None` — Bind the planner to a page and the project's selectors.
  - `plan(self, *, event: TimelineEvent) -> tuple[Unit, ...]` — Return the targets an action will run on.

### `selector_usage.py`

Find where selectors are used, and keep references valid on rename.

- `class Constants` — Group module-level constants.
  - `probes` = `('count', 'exists', 'visible', 'text', 'enabled')`
  - `name_reference` = `re_compile(pattern='\\[extended-selector=(["\'])([A-Za-z][A-Za-z0-9_]*)\\...`
  - `probe_reference` = `re_compile(pattern='\\bsel_([A-Za-z][A-Za-z0-9_]*?)_(?:count|exists|visib...`
- `class SelectorUsage` — Describe everything that depends on one selector.
  - `actions` = `()`
  - `selectors` = `()`
  - `conditions` = `0`
  - Fields: `selector_id: str`
  - `flow_count(self) -> int` — Return how many flows contain an action that targets it.
  - `in_use(self) -> bool` — Return whether anything depends on the selector.
- `referenced_names(*, expression: str) -> frozenset[str]` — Return the selector names an expression refers to.
- `probe_names(*, condition: str) -> frozenset[str]` — Return the selector names a condition reads probes from.
- `usage_index(*, workspace: Workspace) -> dict[str, SelectorUsage]` — Return what depends on each selector in a project.
- `dangling_references(*, workspace: Workspace) -> tuple[tuple[str, str, str], ...]` — Return actions that point at a selector that does not exist.
- `rename_references(*, workspace: Workspace, selector_id: str, name: str) -> tuple[Workspace, tuple[str, ...]]` — Rename a selector and every reference that can be rewritten safely.

### `selectors.py`

Reusable selectors, targeting modes and pacing for recorded actions.

- `class Constants` — Group module-level constants.
  - `file_name` = `'selectors.pwflow.json'`
  - `version` = `1`
  - `name_pattern` = `'[A-Za-z][A-Za-z0-9_]*'`
  - `max_name_length` = `48`
  - `minimum_poll_ms` = `10`
- `class SelectorError` — Report an invalid selector, pace or selectors document.
- `class TargetScope` — Say which of the matched elements an action applies to.
  - `FIRST` = `'first'`
  - `ALL` = `'all'`
- `class RunMode` — Say how an action treats several targets.
  - `SEQUENTIAL` = `'sequential'`
  - `PARALLEL` = `'parallel'`
- `class Pace` — Describe a pause: a fixed delay and/or a condition to wait for.
  - `delay_ms` = `0`
  - `until` = `None`
  - `poll_ms` = `100`
  - `timeout_ms` = `5000`
- `class ValidatedOn` — Record where a selector was last tested and what it found.
  - Fields: `url: str`, `at: str`, `matches: int`
- `class SelectorDef` — Describe one project-wide named selector.
  - `expected_count` = `1`
  - `checks` = `()`
  - `validated_on` = `()`
  - Fields: `selector_id: str`, `name: str`, `expression: str`
- `validate_selectors(*, selectors: tuple[SelectorDef, ...]) -> None` — Require unique identifiers and unique names.
- `class SelectorCodec` — Read and write ``selectors.pwflow.json`` and pace records.
  - `to_json_value(cls, *, selectors: tuple[SelectorDef, ...]) -> JsonValue` — Return the selectors document.
  - `from_json_value(cls, *, value: JsonValue) -> tuple[SelectorDef, ...]` — Parse a selectors document.
  - `selector_from_json(cls, *, value: JsonValue) -> SelectorDef` — Parse one selector.
  - `pace_from_json(cls, *, value: JsonValue) -> Pace | None` — Parse a pace.
  - `save(cls, *, path: Path, selectors: tuple[SelectorDef, ...]) -> None` — Write the selectors document atomically.
  - `load(cls, *, path: Path) -> tuple[SelectorDef, ...]` — Read a selectors document.
  - `selector_to_json(*, item: SelectorDef) -> JsonValue` — Return one selector as JSON.
  - `pace_to_json(*, pace: Pace | None) -> JsonValue` — Return a pace as JSON.

### `similarity.py`

Multi-factor perceptual image similarity scoring.

- `class SimilarityResult` — Contain the components of an image similarity comparison.
  - Fields: `similarity: float`, `appearance: float`, `structure: float`, `perceptual: float`, `color: float`, `geometry: float`
- `class CachedComparison` — Contain a comparison against one previously cached image.
  - Fields: `index: int`, `result: SimilarityResult`
- `class ImageSimilarity` — Compare images and cache fingerprints for repeated comparisons.
  - `__init__(self) -> None` — Initialize an empty comparison fingerprint cache.
  - `compare(cls, first: ImageSource, second: ImageSource) -> float` — Return perceptual similarity between two images.
  - `compare_detailed(cls, first: ImageSource, second: ImageSource) -> SimilarityResult` — Return the final score and individual similarity components.
  - `cache_size(self) -> int` — The number of cached image fingerprints.
  - `clear_cache(self) -> None` — Remove all cached image fingerprints.
  - `remember(self, source: ImageSource) -> int` — Fingerprint and cache an image without comparing it.
  - `compare_history(self, source: ImageSource, *, remember: bool=True) -> tuple[CachedComparison, ...]` — Compare a new image against every cached image fingerprint.

### `sprint.py`

Shared flushed-writer printing helpers for scripts and examples.

- `class SprintStyle` — Per-call output and capture policy for `sprint`.
  - `level` = `'info'`
  - `color` = `None`
  - `save` = `True`
- `class Constants` — Group module-level constants.
  - `default_style` = `SprintStyle()`
  - `debug_marker` = `'DEBUG.txt'`
  - `debug_directory` = `'debug'`
  - `debug_filename` = `'out.txt'`
  - `debug_default_age` = `86400.0`
  - `debug_stamp` = `'%d/%m/%Y %H:%M:%S'`
  - `debug_units` = `{'d': 86400, 'h': 3600, 'm': 60, 's': 1}`
  - `debug_selector` = `recompile(pattern='^(?P<file>[^\\[\\]]*)(?:\\[(?P<functions>[^\\[\\]]*)\\...`
  - `debug_stamp_pattern` = `recompile(pattern='^(?:STDOUT|STDERR) - (\\d{2}/\\d{2}/\\d{4} \\d{2}:\\d{...`
  - `module_file` = `Path(__file__).resolve()`
  - `project_root` = `Path.cwd()`
  - `error_style` = `SprintStyle(level='error')`
- `class Writer(Protocol)` — Writable text stream accepted by `sprint`.
  - `write(self, s: str) -> int` — Write `s` and return the characters written.
  - `flush(self) -> None` — Flush buffered output to the stream.
- `sprint(*args: _Printable, sep: str=' ', end: str='\n', file: Writer | None=None, flush: bool=True, style: SprintStyle=Constants.default_style) -> None` — Print a message and optionally flush the writer.
- `sprint_err(*args: _Printable, sep: str=' ', end: str='\n', flush: bool=True, style: SprintStyle=Constants.error_style) -> None` — Print a message to stderr and optionally flush.

### `store.py`

Deterministic Flow workspace state and JSON persistence.

- `class Constants` — Group module-level constants.
  - `workspace_version` = `3`
  - `previous_fields` = `('selector', 'url', 'payload', 'label', 'when_expression')`
- `class WorkspaceError` — Represent WorkspaceError.
- `class FlowStore` — Represent FlowStore.
  - `__init__(self, *, workspace: Workspace) -> None` — Handle init.
  - `workspace(self) -> Workspace` — The workspace value.
  - `get_flow(self, *, flow_id: str) -> Flow` — Return get flow.
  - `get_event(self, *, flow_id: str, event_id: str) -> TimelineEvent` — Return get event.
  - `add_flow(self, *, flow: Flow) -> None` — Handle add flow.
  - `update_flow(self, *, flow_id: str, settings: FlowSettings) -> None` — Handle update flow.
  - `delete_flow(self, *, flow_id: str) -> None` — Handle delete flow.
  - `add_recording(self, *, flow_id: str, recording: FlowRecording) -> None` — Persist an empty parent before the first captured action arrives.
  - `save_target(self, *, target: Target) -> None` — Replace the application under test.
  - `save_profile(self, *, profile: Profile) -> None` — Add a profile, or replace the one with the same identifier.
  - `delete_profile(self, *, profile_id: str) -> None` — Remove a profile that no flow depends on.
  - `rename_recording(self, *, flow_id: str, recording_id: str, label: str) -> None` — Rename a recording parent without touching its actions.
  - `shift_recording(self, *, flow_id: str, recording_id: str, delta_ms: int, limit_ms: int) -> None` — Move a recording parent and all its actions by one time delta.
  - `delete_recording(self, *, flow_id: str, recording_id: str) -> None` — Remove a recording parent, its actions and their evidence.
  - `append_event(self, *, event: TimelineEvent) -> TimelineEvent` — Return append event.
  - `update_event(self, *, event: TimelineEvent) -> None` — Replace an existing step without changing its identity or order.
  - `delete_event(self, *, flow_id: str, event_id: str) -> None` — Handle delete event.
  - `move_event(self, *, flow_id: str, event_id: str, offset: int) -> None` — Handle move event.
  - `place_event(self, *, flow_id: str, event_id: str, index: int) -> None` — Drop a step at an absolute replay position.
  - `retime_event(self, *, flow_id: str, event_id: str, elapsed_ms: int) -> None` — Move a step to a new timeline time and order the flow by time.
  - `add_expectation(self, *, flow_id: str, event_id: str, expectation: NetworkExpectation) -> None` — Handle add expectation.
  - `remove_expectation(self, *, flow_id: str, event_id: str, expectation_id: str) -> None` — Handle remove expectation.
  - `set_action_contract(self, *, flow_id: str, event_id: str, contract: ActionContract) -> None` — Handle set action contract.
  - `set_flow_interface(self, *, flow_id: str, parameters: tuple[FlowParameter, ...], outputs: tuple[FlowOutput, ...]) -> None` — Handle set flow interface.
  - `add_variable(self, *, definition: VariableDefinition) -> None` — Handle add variable.
  - `remove_variable(self, *, name: str) -> None` — Handle remove variable.
  - `add_checkpoint_definition(self, *, checkpoint: CheckpointDefinition) -> None` — Handle add checkpoint definition.
  - `remove_checkpoint_definition(self, *, checkpoint_id: str) -> None` — Handle remove checkpoint definition.
  - `add_checkpoint_artifact(self, *, artifact: CheckpointArtifact) -> None` — Handle add checkpoint artifact.
  - `upsert_run(self, *, run: ExecutionRun) -> None` — Handle upsert run.
  - `add_screenshot(self, *, artifact: ScreenshotArtifact) -> None` — Handle add screenshot.
  - `add_edge(self, *, edge: FlowEdge) -> None` — Handle add edge.
  - `replace_edge(self, *, index: int, edge: FlowEdge) -> None` — Redefine one saved transition in place, keeping its position.
  - `move_edge(self, *, index: int, to: int) -> None` — Move a saved transition to another position in the evaluation order.
  - `remove_edge(self, *, edge: FlowEdge) -> None` — Handle remove edge.
  - `get_selector(self, *, selector_id: str) -> SelectorDef` — Return one project selector.
  - `upsert_selector(self, *, selector: SelectorDef) -> None` — Add a selector, or replace the one with the same identifier.
  - `delete_selector(self, *, selector_id: str, force: bool=False) -> None` — Remove a selector unless something still depends on it.
  - `rename_selector(self, *, selector_id: str, name: str) -> tuple[str, ...]` — Rename a selector and rewrite the references that can be.
  - `replace_workspace(self, *, workspace: Workspace) -> None` — Handle replace workspace.
- `class WorkspaceCodec` — Represent WorkspaceCodec.
  - `save(cls, *, path: Path, workspace: Workspace) -> None` — Handle save.
  - `load(cls, *, path: Path) -> Workspace` — Return load.
  - `to_json_value(cls, *, workspace: Workspace) -> JsonValue` — Return to json value.
  - `parse_target(cls, *, value: JsonValue) -> Target` — Read and validate a persisted or submitted target.
  - `parse_profile(cls, *, value: JsonValue) -> Profile` — Read and validate one persisted or submitted profile.
  - `from_json_value(cls, *, value: JsonValue) -> Workspace` — Return from json value.
  - `runtime_variable_to_json_value(cls, *, variable: RuntimeVariable) -> JsonValue` — Return runtime variable to json value.
  - `runtime_variable_from_json_value(cls, *, value: JsonValue) -> RuntimeVariable` — Return runtime variable from json value.
  - `action_record_to_json_value(cls, *, record: ActionRunRecord) -> JsonValue` — Return action record to json value.
  - `action_record_from_json_value(cls, *, value: JsonValue) -> ActionRunRecord` — Return action record from json value.
  - `event_to_json_value(cls, *, event: TimelineEvent) -> JsonValue` — Return event to json value.
  - `target_to_json(*, target: Target) -> JsonValue` — Return the target as persisted and shown to the editor.
  - `profile_to_json(*, profile: Profile) -> JsonValue` — Return a profile as persisted and shown to the editor.
  - `profile_schema() -> JsonValue` — Describe every profile setting so the editor builds typed controls.

### `studio/__init__.py`

Host the browser Flow Studio UI and its local service.


### `studio/__main__.py`

Run browser Studio as a package with its automation worker.

- `class StudioLaunch` — Configure the single browser Studio host.
  - `port` = `0`
  - `headless` = `True`
  - `open_editor` = `True`
  - `window` = `False`
  - `target_url` = `None`
  - `duration_seconds` = `None`
  - Fields: `root: Path`
- `serve(*, options: StudioLaunch) -> StudioService` — Serve the chosen project until interrupted or its duration ends.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Start the sole supported browser Studio launch path.

### `studio/action_commands.py`

Reconfigure an authored action from the Properties panel.

- `class Constants` — Group module-level constants.
  - `screenshot_marker` = `'__screenshot__'`
- `class ActionFields` — The normalized settings an action is reconfigured with.
  - Fields: `label: str`, `payload: str | None`, `selector: str | None`, `selector_id: str | None`, `url: str | None`, `method: str | None`, `position_action: PositionPointerAction | None`, `x: int | None`, `y: int | None`, `incomplete: bool`
- `default_label(*, event: TimelineEvent) -> str` — Return the label the action's own settings would generate.
- `reconfigured_event(*, event: TimelineEvent, fields: ActionFields, data: dict[str, JsonValue], selectors: tuple[SelectorDef, ...]) -> TimelineEvent` — Apply a full set of action settings to an existing action.

### `studio/controller.py`

HTML-first Exactus Record host window.

- `class Constants` — Group module-level constants.
  - `max_wait_ms` = `60000`
  - `max_timeline_ms` = `3600000`
  - `max_label_length` = `80`
  - `max_crawl_depth` = `10`
  - `max_crawl_states` = `200`
  - `max_scroll_delta` = `2000`
  - `max_key_length` = `80`
  - `max_pointer_button` = `4`
  - `max_pointer_buttons` = `31`
  - `ask_token` = `compile_pattern(pattern='\\{\\{ask:([^{}]+)\\}\\}')`
- `class StudioController` — Own one workspace and immutable execution inputs for the service.
  - `__init__(self, *, worker: BrowserWorker, events: EventBus, persistence: WorkspaceFiles, targets: TargetService, library: ProjectLibrary) -> None` — Initialize workspace ownership independently of HTTP.
  - `persistence(self) -> WorkspaceFiles` — Files of the project that is open now.
  - `project_slug(self) -> str` — Identifier of the project that is open now.
  - `library(self) -> ProjectLibrary` — The Studio's projects.
  - `workspace(self) -> Workspace` — Immutable current workspace.
  - `dispatch(self, command: str, payload: JsonValue, revision: int) -> JsonValue` — Return dispatch command.
  - `stop_demo(self) -> None` — Stop the processes this Studio service started: demo and target.
  - `receive(self, *, message: dict[str, JsonValue]) -> None` — Accept a typed worker message on the service's serialized boundary.

### `studio/demo.py`

Create an editable demonstration using the ordinary Studio flow runtime.

- `demo_site() -> Path` — Locate the bundled target application.
- `demo_target() -> Target | None` — Suggest starting the bundled demo application's own server.
- `demo_workspace(*, url: str) -> Workspace` — Bind a replayable graph to the demo server's actual runtime URL.

### `studio/events.py`

Publish bounded, ordered service events with snapshot recovery.

- `class EventBus` — Retain a bounded event history independently of connected clients.
  - `__init__(self, *, capacity: int=256) -> None` — Create the service-local history.
  - `emit_event(self, *, name: str, payload: JsonValue) -> None` — Publish an immutable JSON message and wake waiting clients.
  - `read(self, *, after: int, timeout: float=15) -> tuple[bool, tuple[tuple[int, str], ...]]` — Read newer events or indicate that history needs a snapshot.
  - `close(self) -> None` — Wake subscribers during shutdown.

### `studio/persistence.py`

Restrict workspace and artifact access to the selected project root.

- `class WorkspaceFiles` — Keep recovery and project saves atomic and detect external changes.
  - `__init__(self, *, root: Path) -> None` — Create project-local recovery storage.
  - `public_document(cls, *, value: JsonValue, artifact_links: bool=True) -> JsonValue` — Redact runtime secrets and expose artifact IDs instead of paths.
  - `safe_path(self, *, name: str) -> Path` — Reject absolute paths, traversal, and symlink escape.
  - `recover(self) -> Workspace | None` — Load durable unsaved work without starting any browser operation.
  - `open(self, *, data: dict[str, JsonValue]) -> Workspace` — Validate an uploaded document or a project-local workspace file.
  - `save(self, *, workspace: Workspace, data: dict[str, JsonValue]) -> None` — Atomically save without silently overwriting external edits.
  - `project_document(self, *, workspace: Workspace, include_selectors: bool=True) -> dict[str, JsonValue]` — Export a portable project with owned screenshot assets.
  - `discard_recovery(self) -> None` — Forget unsaved changes; the next open starts from the saved file.
  - `persist_recovery(self, *, workspace: Workspace) -> None` — Persist unsaved changes independently of browser unload events.
  - `artifact(self, *, workspace: Workspace, artifact_id: str) -> Path` — Resolve a known screenshot without accepting a client path.

### `studio/project_commands.py`

Editor commands for projects, apart from the large controller.

- `project_view(*, library: ProjectLibrary, active: str, workspace: Workspace) -> dict[str, JsonValue]` — Describe the open project and the library for the editor.
- `new_info(*, data: dict[str, JsonValue]) -> ProjectInfo` — Read the details of a new project from a form.
- `updated_workspace(*, workspace: Workspace, library: ProjectLibrary, active: str, data: dict[str, JsonValue]) -> Workspace` — Apply an edit of the open project's details.

### `studio/projects.py`

Keep a library of projects, one folder each, under the Studio root.

- `class Constants` — Group module-level constants.
  - `root_id` = `'@root'`
  - `folder` = `'projects'`
  - `file_name` = `'flows.pwflow.json'`
  - `recents_file` = `'.exactus-library/recents.json'`
  - `recents_kept` = `10`
  - `slug_pattern` = `re_compile(pattern='^[a-z0-9][a-z0-9-]{0,63}$')`
  - `default_name` = `'Default project'`
- `class ProjectError` — Raise when a project action cannot be done.
- `target_from_address(*, address: str, base: Target | None=None) -> Target` — Turn an address a person typed into the project's target.
- `class ProjectSummary` — Describe one project for the gallery.
  - Fields: `slug: str`, `info: ProjectInfo`, `modified_at: str`, `last_run_at: str`, `flows: int`, `runs: int`, `base_url: str`, `legacy: bool`
  - `to_json_value(self) -> dict[str, JsonValue]` — Return the summary as the gallery shows it.
- `class ProjectLibrary` — Create, find and manage the projects under one Studio root.
  - `__init__(self, *, root: Path) -> None` — Remember the library root.
  - `folder(self, *, slug: str) -> Path` — Return the folder of a project.
  - `slug_of(self, *, folder: Path) -> str` — Return the identifier of the project in a folder.
  - `list(self) -> tuple[ProjectSummary, ...]` — Describe every project, newest changes first.
  - `get(self, *, slug: str) -> ProjectSummary` — Describe one project.
  - `name_taken(self, *, name: str, ignore: str='') -> bool` — Say whether another project already has a name.
  - `create(self, *, info: ProjectInfo, base_url: str='') -> ProjectSummary` — Create an empty project in its own folder.
  - `ensure(self, *, info: ProjectInfo, workspace: Workspace) -> str` — Return the project with a name, creating it when it is missing.
  - `duplicate(self, *, slug: str, name: str) -> ProjectSummary` — Copy a project's definition, without its runs or screenshots.
  - `delete(self, *, slug: str) -> None` — Delete a project's folder for good.
  - `import_document(self, *, document: dict[str, JsonValue], name: str='') -> ProjectSummary` — Add a project from an exported document.
  - `export_document(self, *, slug: str) -> dict[str, JsonValue]` — Return a project as one portable document.
  - `recents(self) -> tuple[str, ...]` — List recently opened projects that still exist.
  - `touch(self, *, slug: str) -> None` — Remember that a project was just opened.
- `tags_of(*, projects: tuple[ProjectSummary, ...]) -> list[str]` — Collect every tag used by any project.

### `studio/selector_commands.py`

Editor commands for selectors, apart from the large controller.

- `class Constants` — Group module-level constants.
  - `max_test_matches` = `200`
  - `stats_script` = `dedent(text='    \n    args => {\n      const Engine = globalThis.__EXACT...`
- `save_selector(*, store: FlowStore, data: dict[str, JsonValue]) -> None` — Create a selector, or edit one in place.
- `delete_selector(*, store: FlowStore, data: dict[str, JsonValue]) -> None` — Delete a selector, refusing when it is in use unless forced.
- `updated_event(*, event: TimelineEvent, data: dict[str, JsonValue], selectors: tuple[SelectorDef, ...], label: str) -> TimelineEvent` — Apply an ``event.update`` command to an action in one validated step.
- `selector_view(*, workspace: Workspace) -> dict[str, JsonValue]` — Describe the project's selectors for the editor.
- `test_message(*, data: dict[str, JsonValue], selectors: tuple[SelectorDef, ...]) -> dict[str, JsonValue]` — Build the worker message that tests an expression in the live page.
- `run_selector_test(*, page: Page, message: dict[str, JsonValue]) -> dict[str, JsonValue]` — Resolve an expression in the page and describe the result.
- `record_validation(*, store: FlowStore, result: dict[str, JsonValue]) -> bool` — Remember a successful test on the selector that was tested.

### `studio/service.py`

Serve the local editor, authenticated commands, events and artifacts.

- `class Constants` — Group module-level constants.
  - `max_body` = `8 * 1024 * 1024`
  - `max_id_length` = `128`
  - `max_replies` = `256`
  - `read_commands` = `frozenset({'workspace.snapshot', 'screenshot.open'})`
  - `busy_blocked` = `frozenset({'workspace.open', 'demo.open', 'flow.delete', 'browser.navigat...`
  - `package_suffixes` = `frozenset({'.js', '.css', '.html'})`
  - `recovery_page` = `b''.join((b'<!doctype html><html lang=en><meta charset=utf-8>', b"<meta n...`
- `class StudioError` — Carry a stable public error without exposing internal exceptions.
  - `status` = `400`
  - Fields: `code: str`, `message: str`
- `class StudioService` — Own one controller, target worker and authenticated service lifetime.
  - `__init__(self, *, root: Path, port: int=0, headless: bool=False) -> None` — Bind an available loopback port without opening browsers.
  - `persistence(self) -> WorkspaceFiles` — Files of the project that is open now.
  - `origin(self) -> str` — Exact permitted service origin.
  - `url(self) -> str` — Browser bootstrap URL with a non-logged fragment.
  - `start(self) -> None` — Start the HTTP listener and its single target worker.
  - `stop(self) -> None` — Stop the service without affecting unrelated browser processes.
  - `snapshot(self) -> dict[str, JsonValue]` — Return authoritative state for any connected Studio window.
  - `command(self, *, value: JsonValue, client: str) -> dict[str, JsonValue]` — Validate, deduplicate, authorize ownership and dispatch commands.
  - `export_document(self, *, slug: str='') -> JsonValue` — Serialize a project as the public export document.
  - `artifact_path(self, *, artifact_id: str) -> Path` — Resolve one owned artifact under the service lock.
  - `subscriber(self) -> Generator[None]` — Hold one bounded event-stream subscription slot.
- `class StudioHandler` — Serve explicit routes with origin, Host, cookie and payload checks.
  - `__init__(self, request: socket, client_address: tuple[str, int], server: BaseServer, *, service: StudioService) -> None` — Attach the service before processing an HTTP request.
  - `log_message(self, format: str, *args: JsonValue) -> None` — Avoid access logs that could expose bootstrap credentials.
  - `do_post(self) -> None` — Handle bootstrap authentication and protected JSON commands.
  - `do_get(self) -> None` — Serve assets, readiness, snapshots, events and owned artifacts.

### `studio/target_inspection.py`

Read target element identity without dispatching an interaction.

- `class Constants` — Group module-level constants.
  - `probe` = `dedent(text="    ({x, y}) => {\n            const element = document.elem...`
  - `frame_tags` = `{'iframe', 'frame'}`
  - `max_frame_depth` = `4`
- `inspect_target(*, page: Page, x: float, y: float) -> JsonValue` — Inspect a target CSS point without changing the target DOM.

### `studio/target_service.py`

Start, detect and stop the service a project's target refers to.

- `class Constants` — Group module-level constants.
  - `start_timeout` = `30.0`
  - `settle_seconds` = `0.5`
  - `probe_timeout` = `1.0`
  - `error_status` = `500`
- `best_server(servers: tuple[HttpServer, ...]) -> HttpServer` — Choose the server a person most likely means.
- `class TargetService` — Own at most one started service and report what is reachable.
  - `__init__(self, *, root: Path, emit: Callable[[Event], None]) -> None` — Prepare without starting anything.
  - `base_url(self) -> str | None` — Address of the running service, if one was detected.
  - `check(*, target: Target) -> dict[str, JsonValue]` — Probe the configured address without starting anything.
  - `snapshot(self) -> dict[str, JsonValue]` — Return the current state, noticing a service that exited.
  - `start(self, *, target: Target) -> None` — Start the configured service and detect its port in the background.
  - `set_root(self, *, root: Path) -> None` — Move to another project folder.
  - `stop(self, *, wait: bool=False) -> None` — Stop the service and everything it started.

### `studio/window.py`

Resolve the Studio browser-window setting from CLI and pyproject.

- `add_window_argument(*, parser: ArgumentParser) -> None` — Register ``--window`` / ``--no-window`` on a Studio parser.
- `resolve_window(*, flag: bool | None, start: Path) -> bool` — Combine the CLI flag with ``[tool.exactus.record] window``.

### `studio/worker.py`

Keep synchronous Playwright objects on one service-owned worker thread.

- `class Constants` — Group module-level constants.
  - `watch_seconds` = `5.0`
  - `refresh_seconds` = `1.5`
  - `refresh_timeout_ms` = `1500`
- `class ScreencastSession(Protocol)` — Describe the typed subset of Chromium's live-frame transport.
  - `send(self, *, method: str, params: dict[str, JsonValue]) -> JsonValue` — Send a screencast method.
  - `on(self, *, event: str, f: Callable[[dict[str, JsonValue]], None]) -> None` — Subscribe to screencast frames.
- `validate_target_url(*, url: str) -> str` — Allow web targets and the initial blank document.
- `class BrowserWorker(Protocol)` — Describe the controller's browser command boundary.
  - `actions(self, *, specification: dict[str, JsonValue], root: Path) -> None` — Run a declarative tool recipe.
  - `crawl(self, *, request: CrawlRequest) -> None` — Start bounded discovery of the target URL.
  - `broadcast(self, *, command: RecorderCommand) -> None` — Queue recording control.
  - `broadcast_dispatch(self, *, request: FlowDispatchRequest) -> None` — Queue flow execution.
  - `navigate(self, *, value: str) -> None` — Queue navigation.
  - `set_profile(self, *, profile: Profile) -> None` — Apply the browser conditions the target is shown under.
  - `open_target(self, *, url: str) -> None` — Open an owned browser.
  - `input_target(self, *, message: Event) -> None` — Queue validated input for the visible managed page.
  - `close_target(self) -> None` — Close the owned target context.
  - `set_output(self, *, output: Path) -> None` — Move evidence to another project's directory.
  - `select_target(self, *, page_id: str) -> None` — Choose an owned page.
  - `cancel(self) -> None` — Signal cancellation outside the Playwright thread.
  - `pause_run(self) -> None` — Hold the running flow before its next action.
  - `resume_run(self) -> None` — Let a held flow continue without stopping again.
  - `step_run(self) -> None` — Let a held flow run exactly one more action.
- `class ManagedBrowserWorker` — Own browser lifetime and process one bounded command queue.
  - `__init__(self, *, output: Path, headless: bool=False) -> None` — Configure a lazy target without launching a browser.
  - `preview(self) -> bytes` — Return the newest preview frame.
  - `preview(self, frame: bytes) -> None` — Retain a frame and remember when it arrived.
  - `preview_age_ms(self) -> int | None` — Return how old the preview frame is, or None without a frame.
  - `start(self) -> None` — Start the sole owning Playwright thread.
  - `stop(self) -> None` — Cancel operations and close only service-owned browser resources.
  - `cancel(self) -> None` — Signal cooperative cancellation; no cross-thread browser calls.
  - `pause_run(self) -> None` — Hold the running flow before its next action.
  - `resume_run(self) -> None` — Let a held flow continue without stopping again.
  - `step_run(self) -> None` — Let a held flow run exactly one more action.
  - `broadcast(self, *, command: RecorderCommand) -> None` — Queue an encoded domain recorder command.
  - `broadcast_dispatch(self, *, request: FlowDispatchRequest) -> None` — Queue immutable execution inputs.
  - `navigate(self, *, value: str) -> None` — Queue validated navigation without changing the editor page.
  - `set_profile(self, *, profile: Profile) -> None` — Queue a change of the conditions the target is shown under.
  - `open_target(self, *, url: str) -> None` — Queue a new isolated browser context.
  - `close_target(self) -> None` — Queue closure of the managed context.
  - `set_output(self, *, output: Path) -> None` — Move evidence to another project's directory.
  - `input_target(self, *, message: Event) -> None` — Forward a validated live-panel input on the browser owning thread.
  - `select_target(self, *, page_id: str) -> None` — Queue active-page selection within the managed context.
  - `actions(self, *, specification: dict[str, JsonValue], root: Path) -> None` — Execute an Actions recipe on the owned discovery thread.
  - `crawl(self, *, request: CrawlRequest) -> None` — Launch the existing explorer with cancellable progress.
  - `select_page_for_test(self, *, page: Page) -> None` — Mark a page active without launching a browser.
  - `accept_frame(self, *, page: Page, session: ScreencastSession, message: dict[str, JsonValue]) -> None` — Keep a frame only when it matches the active page and viewport.

### `visit.py`

Replay a crawler visit plan across parallel device and theme lanes.

- `class VisitDefaults` — Store immutable visit configuration values.
  - `root` = `Path(__file__).resolve().parents[2]`
  - `output` = `root / 'VISIT'`
  - `visit_attempts` = `2`
- `class VisitSkipError` — Signal that a recorded action has no control in this lane.
- `class CaptureSettings` — Bundle the capture and replay settings recorded in the manifest.
  - Fields: `selector: str`, `target_only: bool`, `image_type: Literal['png', 'jpeg']`, `quality: int | None`, `scale: Literal['css', 'device']`, `max_height: int`, `workers: int`, `similarity_threshold: float`
- `class ShotRecord` — Record the outcome of one replayed interface visit.
  - `skipped` = `''`
  - Fields: `id: str`, `index: int`, `name: str`, `url: str`, `device: str`, `theme: str`, `ok: bool`, `path: str`, `duration_ms: float`, `truncated_height: bool`, `duplicate: bool`, `similarity: float`, `error: str`
- `class VisitReport` — Aggregate everything the parallel replay observed.
  - Fields: `results: list[ShotRecord]`, `console: list[dict[str, JsonValue]]`, `server: list[dict[str, JsonValue]]`, `mutations: list[str]`
- `class LaneWork` — Describe one lane's replay assignment.
  - Fields: `device: DeviceSpec`, `theme: ThemeName`, `visits: list[tuple[int, VisitStep]]`, `directory: Path`
- `class LaneSinks` — Collect the shared report sinks lanes append into.
  - Fields: `results: list[ShotRecord]`, `console: list[dict[str, JsonValue]]`, `server: list[dict[str, JsonValue]]`, `mutations: list[str]`
- `class Progress` — Track shared replay progress for the single-line bar.
  - `done` = `0`
  - `total` = `0`
- `class VisitTask` — One plan step replayed inside a lane.
  - Fields: `step: VisitStep`, `index: int`, `number: int`
- `class VisitOptions` — Run-time replay switches shared by every lane.
  - `on_progress` = `None`
  - Fields: `machine: str`, `server_log: bool`, `dedup: bool`
- `class LaneMatrix` — Device/theme combinations fanned out into lanes.
  - Fields: `devices: tuple[DeviceSpec, ...]`, `themes: tuple[ThemeName, ...]`
- `class LaneOutputs` — Shared report sinks and progress a lane appends into.
  - Fields: `sinks: LaneSinks`, `progress: Progress`
- `class Constants` — Group module-level constants.
  - `sensitive_headers` = `frozenset({'authorization', 'cookie', 'proxy-authorization', 'set-cookie'...`
  - `post_limit` = `2048`
- `redact_headers(headers: dict[str, str]) -> dict[str, str]` — Mask credential-bearing headers in a serialized header set.
- `post_payload(request: Request) -> JsonValue` — Serialize a request body; truncate text and mark binary data.
- `store_sync(path: Path, data: bytes) -> None` — Write capture bytes to disk; called inside an executor.
- `progress_line(done: int, total: int, label: str) -> str` — Render the single-line progress bar.
- `serialize_arg(handle: JSHandle) -> JsonValue` — Expand one console argument into a JSON-serializable value.
- `console_entry(message: ConsoleMessage, *, visit: str, visit_id: str, device: str, theme: str) -> dict[str, JsonValue]` — Serialize one console message with expanded arguments.
- `server_entry(request: Request, *, visit: str, visit_id: str, device: str, theme: str) -> dict[str, JsonValue]` — Serialize one finished or failed HTTP exchange.
- `drain(queue: Queue[LaneItem | None], *, device: str, theme: str, console: list[dict[str, JsonValue]], server: list[dict[str, JsonValue]]) -> None` — Consume one lane's queued events until the ``None`` sentinel.
- `perform(page: Page, action: VisitAction) -> None` — Apply one plan action to the current page.
- `visit_step(page: Page, work: LaneWork, *, task: VisitTask, settings: CaptureSettings, similarity: ImageSimilarity | None) -> ShotRecord` — Replay one interface visit and capture the opened state.
- `run_lane(browser: Browser, *, work: LaneWork, settings: CaptureSettings, options: VisitOptions, outputs: LaneOutputs) -> None` — Replay every visit inside one device/theme Playwright window.
- `run_visits(plan: VisitPlan, *, shots: Path, settings: CaptureSettings, matrix: LaneMatrix, options: VisitOptions) -> VisitReport` — Replay every visit across parallel device/theme windows.

### `workspace_actions.py`

Convert selector-based recorded actions and current workspace documents.

- `class WorkspaceActionError` — Raised when a Exactus Record file or message violates its schema.
- `class ActionSchema` — Define selector requirements and the current interchange version.
  - `workspace_version` = `3`
  - `selector_kinds` = `frozenset({'click', 'double_click', 'right_click', 'hover', 'drag', 'scro...`
  - `pointer_kinds` = `{'click': 'click', 'double_click': 'double_click', 'right_click': 'right_...`
- `css_selector(*, target: Action | None) -> str | None` — Derive the CSS selector Exactus Record requires from a recorded target.
- `new_event(*, event_id: str, kind: str, layer: str, label: str, elapsed_ms: int=0) -> Event` — Build one workspace event with every schema field present.
- `action_event(*, action: Action, event_id: str) -> Event | None` — Convert one recorded action into a Exactus Record event.
- `class KeyChord` — Render and parse Playwright key chords such as ``Control+A``.
  - `render(*, action: Action) -> str` — Render a recorded keypress as a ``Mod+Key`` chord.
  - `parse(*, chord: str) -> Action` — Split a chord back into a ``key`` action.
- `actions_to_events(*, actions: Sequence[Action], flow_id: str) -> list[Event]` — Convert a recorded program into ordered Exactus Record events.
- `build_flow(*, flow_id: str, name: str, events: Sequence[Event], notes: str='') -> Event` — Assemble one workspace Flow around ``events``.
- `build_workspace(*, flows: Sequence[Event]) -> Event` — Assemble a current-version workspace holding ``flows``.
- `write_workspace(*, path: Path, workspace: Event) -> None` — Write a workspace as deterministic UTF-8 JSON.
- `event_action(*, event: Event) -> Action | None` — Convert a Exactus Record event back into a replayable action.
- `class Constants` — Group module-level constants.
  - `coordinate_keys` = `('x', 'y', 'end_x', 'end_y')`
  - `modifiers` = `(('control', 'Control'), ('alt', 'Alt'), ('shift', 'Shift'), ('meta', 'Me...`
  - `event_actions` = `{'click': _pointer_action, 'double_click': _pointer_action, 'right_click'...`
- `load_flow_actions(*, path: Path, flow_id: str | None=None) -> list[Action]` — Load a replayable program from a Studio workspace or action file.
- `validate_event(*, event: Event) -> None` — Enforce Exactus Record's targeting invariants on a bridge event.
- `encode_message(*, message: Event) -> bytes` — Encode one compact NDJSON line.
- `bridge_event(*, event: Event, flow_id: str) -> Event` — Adapt a workspace event to the bridge's inbound event envelope.

## JavaScript API reference

Top-level exports, read from the source.

### `studio/web/action-card.js`

- `cardSpec`
- `renderSentence`
- `guardParts`
- `buildCard`
- `producedVariables`
- `producersOf`

### `studio/web/action-library.js`

- `ACTION_DRAG_TYPE`
- `ACTION_GROUPS`
- `definitionForEvent`
- `editsInRow`
- `actionValues`
- `ACTION_PREFS_EVENT`
- `loadActionPrefs`
- `saveActionPrefs`
- `renderActionCatalog`
- `configureActionForm`
- `DEFAULT_GUARD`
- `actionCommand`
- `defaultActionCommand`

### `studio/web/ask-inputs.js`

- `askLabels`
- `askInputs`

### `studio/web/compare-pairs.js`

- `groupCaptures`
- `pairFor`

### `studio/web/condition-field.js`

- `tokenAt`
- `attachConditionField`

### `studio/web/condition-language.js`

- `OPERATORS`
- `FUNCTIONS`
- `LITERALS`
- `semanticOf`
- `tokenize`
- `analyse`
- `guide`
- `suggestNext`
- `insertionFor`

### `studio/web/condition-pills.js`

- `renderPills`

### `studio/web/dock-grid.js`

- `DockGrid`

### `studio/web/dock-model.js`

- `HEADER_SIZE`
- `MIN_NEW_TRACK`
- `DEFAULT_COLUMN`
- `DEFAULT_ROW`
- `LAYOUT_VERSION`
- `defaultLayout`
- `clone`
- `defaultGraphLayout`
- `layoutForMode`
- `stateOwner`
- `coverage`
- `isDocked`
- `validate`
- `collapseAxis`
- `collapseDirection`
- `effectiveTracks`
- `canCollapse`
- `setCollapsed`
- `undock`
- `dockBeside`
- `dockOuter`
- `swap`
- `float`
- `SHARED_PANEL`
- `describeShared`
- `sameShared`
- `adoptShared`
- `isResizable`
- `resizeRange`
- `resizeBoundary`
- `boundaries`

### `studio/web/editor.js`

- `EditorApp`

### `studio/web/flow-inputs.js`

- `INPUT_TYPES`
- `flowInputsField`

### `studio/web/flow-list.js`

- `renderFlowList`

### `studio/web/graph-surface.js`

- `graphSvg`
- `defaultGraphPositions`
- `graphNodes`
- `graphBounds`
- `graphLinks`
- `graphConnectionInspector`

### `studio/web/icon-set.js`

- `ICONS`

### `studio/web/icons.js`

- `iconMarkup`
- `paintIcon`
- `iconElement`
- `kindOf`
- `watchIcons`

### `studio/web/javascript-action-widget.js`

- `javascriptActionWidget`
- `conditionWidget`

### `studio/web/live-target.js`

- `LiveTarget`

### `studio/web/project-actions.js`

- `ProjectActions`

### `studio/web/project-bar.js`

- `ProjectBar`

### `studio/web/project-dialogs.js`

- `h`
- `icon`
- `ProjectDialogs`

### `studio/web/project-model.js`

- `emptyFilter`
- `isFiltered`
- `nameIssue`
- `parseTags`
- `filterProjects`
- `ago`
- `when`
- `recentProjects`

### `studio/web/project-section.js`

- `ProjectSection`

### `studio/web/request-action-widget.js`

- `requestActionWidget`
- `requestActionConfig`

### `studio/web/run-cause.js`

- `worstStatus`
- `causeSummary`
- `causeFacts`
- `renderLastRun`

### `studio/web/selector-expression-field.js`

- `widgetHost`
- `selectorExpressionField`

### `studio/web/selector-live-tools.js`

- `selectorLiveTools`

### `studio/web/selector-reference-field.js`

- `bindSelectorReference`
- `selectorExpression`

### `studio/web/selectors-panel.js`

- `usageSentence`
- `renderSelectorList`
- `renderTestResult`
- `renderSeen`
- `selectorInspector`

### `studio/web/settings.js`

- `gcd`
- `reduceRatio`
- `heightForRatio`
- `slugify`
- `parseNumber`
- `issuesFor`
- `summary`
- `splitCommand`
- `joinCommand`
- `describeCheck`
- `describeService`
- `parsePort`
- `SettingsSurface`

### `studio/web/token-editor.js`

- `openTokenEditor`
- `openFloatingPanel`

### `studio/web/transport.js`

- `StudioTransport`

### `studio/web/variable-inspector.js`

- `gettersFor`
- `variableInspector`

### `studio/web/variable-mention-field.js`

- `variableName`
- `variableMentionField`

### `studio/web/welcome.js`

- `DISMISSED_KEY`
- `shouldWelcome`
- `renderWelcome`

## Examples

Runnable demonstration for `exactus/tools/record/`.

Load and summarize the bundled branching Record workspace.

```bash
python -m exactus.tools.record.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/assets/README.md`, `examples/assets/branching-demo.pwflow.json`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`argument_parser`](../../packages/argument_parser/DOCS.md), [`browser`](../../packages/browser/DOCS.md), [`http_process`](../../packages/http_process/DOCS.md), [`project_python`](../../packages/project_python/DOCS.md), [`server`](../../packages/server/DOCS.md), [`steps`](../../packages/steps/DOCS.md), [`actions`](../actions/DOCS.md), [`common`](../common/DOCS.md), [`reports`](../reports/DOCS.md)
- Used by: `__main__.py`, `tests/packages/screenshot/test_capture_support.py`, `tests/tools/actions/test_actions.py`, `tests/tools/common/test_conflict_copies.py`, `tests/tools/frontend/test_frontend.py`, `tests/tools/frontend/test_frontend_progress.py`, `tests/tools/frontend/test_parallel_flows.py`, `tests/tools/record/selector_support.py`, `tests/tools/record/test_action_schema.py`, `tests/tools/record/test_assertions_causality.py`, `tests/tools/record/test_crawler_visit.py`, `tests/tools/record/test_diagnostic_sources.py`, `tests/tools/record/test_discovery_project.py`, `tests/tools/record/test_expectations.py`, `tests/tools/record/test_expressions_errors.py`, `tests/tools/record/test_expressions_execution.py`, `tests/tools/record/test_flow_contracts.py`, `tests/tools/record/test_flow_inventory.py`, `tests/tools/record/test_flow_runner.py`, `tests/tools/record/test_flow_runner_actions.py`, `tests/tools/record/test_flow_runner_selectors.py`, `tests/tools/record/test_flow_runner_variables.py`, `tests/tools/record/test_http_request.py`, `tests/tools/record/test_live_run.py`, `tests/tools/record/test_model.py`, `tests/tools/record/test_model_selectors.py`, `tests/tools/record/test_model_validation_extra.py`, `tests/tools/record/test_persistence_selectors.py`, `tests/tools/record/test_preview_frames.py`, `tests/tools/record/test_profiles.py`, `tests/tools/record/test_project_assets.py`, `tests/tools/record/test_rebase.py`, `tests/tools/record/test_record_core.py`, `tests/tools/record/test_record_report.py`, `tests/tools/record/test_recorder.py`, `tests/tools/record/test_recorder_protocol.py`, `tests/tools/record/test_recording_groups.py`, `tests/tools/record/test_response_paths.py`, `tests/tools/record/test_run_gate.py`, `tests/tools/record/test_selector_conditions.py`, `tests/tools/record/test_selector_engine.py`, `tests/tools/record/test_selector_resolver.py`, `tests/tools/record/test_selector_sandbox.py`, `tests/tools/record/test_selector_snapshot.py`, `tests/tools/record/test_selector_store.py`, `tests/tools/record/test_selectors.py`, `tests/tools/record/test_similarity.py`, `tests/tools/record/test_store.py`, `tests/tools/record/test_store_errors.py`, `tests/tools/record/test_store_selectors.py`, `tests/tools/record/test_studio_action_setup.py`, `tests/tools/record/test_studio_boundaries.py`, `tests/tools/record/test_studio_duplicate_step.py`, `tests/tools/record/test_studio_entrypoint.py`, `tests/tools/record/test_studio_http_contract.py`, `tests/tools/record/test_studio_projects.py`, `tests/tools/record/test_studio_selectors.py`, `tests/tools/record/test_studio_window.py`, `tests/tools/record/test_target.py`, `tests/tools/record/test_v3_execution.py`, `tests/tools/record/test_v3_fixture_builder.py`, `tests/tools/record/test_v3_fixtures.py`, `tests/tools/record/test_workspace_actions.py`, `tests/tools/record/v3_fixture_builder.py`, `tools/actions/__main__.py`, `tools/actions/examples/run.py`, `tools/actions/runner.py`

## Tests

Tests live in `exactus/tests/tools/record/`.

- `test_action_schema.py` — Verify typed action bindings and stable input/output identities. (13 tests)
  - `test_action_output_identity_ignores_paths_and_display_metadata`
  - `test_binding_accepts_json_null_as_a_real_literal`
  - `test_binding_rejects_blank_text_payloads`
  - `test_binding_rejects_multiple_or_mismatched_payloads`
  - `test_binding_reports_its_producer_dependency`
  - `test_dependency_ids_follow_first_use_order`
  - `test_output_reference_rejects_empty_identity_parts`
  - `test_port_rejects_inconsistent_definitions`
  - `test_schema_rejects_ambiguous_ports`
  - `test_schema_rejects_empty_and_duplicate_identities`
  - `test_slot_enforces_secret_and_retry_capabilities`
  - `test_slot_rejects_inconsistent_definitions`
  - `test_value_vocabulary_matches_the_locked_contract`
- `test_assertions_causality.py` — Coverage for assertion evaluation and causal attribution. (4 tests)
  - `test_assertion_errors`
  - `test_assertion_operators`
  - `test_causal_ambiguity_does_not_guess`
  - `test_causal_attribution_paths`
- `test_bridge_protocol.py` — HTML-editor architecture regression tests. (1 tests)
  - `test_editor_assets_are_local_and_iframe_free`
- `test_crawler_visit.py` — The visit-plan crawler and the parallel visit replayer. (11 tests)
  - `test_build_plan_discovers_interfaces`
  - `test_device_and_theme_resolution`
  - `test_dismiss_wizard_paths`
  - `test_drain_events`
  - `test_plan_parsing`
  - `test_run_visits_end_to_end`
  - `test_slug_and_ids`
  - `test_storage_seed_script`
  - `test_store_sync`
  - `test_visit_helpers`
  - `test_visit_step_failure_reports_error`
- `test_diagnostic_sources.py` — Browser diagnostics retain real script locations and function stacks. (2 tests)
  - `test_async_console_and_exception_sources`
  - `test_sync_console_and_exception_sources`
- `test_discovery_project.py` — Verify crawler projects open and replay in browser Studio. (1 tests)
  - `test_discovery_opens_a_replayable_studio_project`
- `test_expectations.py` — Tests for action-attributed network expectation matching. (5 tests)
  - `test_expectation_fails_on_unexpected_status`
  - `test_expectation_failure_dimensions_and_body_modes`
  - `test_expectation_helper_edge_paths`
  - `test_expectation_matches_query_status_headers_and_json`
  - `test_expectation_url_and_json_helpers_cover_variants`
- `test_expressions_errors.py` — Error handling and operator coverage of the expression evaluator. (5 tests)
  - `test_boolean_coercion_accepts_booleans_and_rejects_text`
  - `test_interpolation_rejects_unknown_and_secret_variables`
  - `test_invalid_expressions_raise`
  - `test_operators_evaluate`
  - `test_validate_rejects_empty_and_syntax_errors`
- `test_expressions_execution.py` — Behavioral coverage for expression and execution engines. (8 tests)
  - `test_execution_engine_selects_condition_and_completes`
  - `test_expression_failures_are_explicit`
  - `test_running_one_flow_does_not_follow_its_connections`
  - `test_value_codec_and_expression_language`
  - `test_value_codec_edge_cases`
  - `test_value_codec_none`
  - `test_variable_resolution_and_execution_errors`
  - `test_variable_resolver_parameter_guards_and_defaults`
- `test_flow_contracts.py` — Bind the locked v4 contract files to FLOW.md and the real v3 surface. (10 tests)
  - `test_actions_are_well_formed`
  - `test_contract_agrees_with_the_spec_table`
  - `test_contract_covers_exactly_the_v3_catalog`
  - `test_contract_has_the_spec_counts`
  - `test_decision_document_keeps_every_section_and_limit`
  - `test_interaction_actions_publish_nothing`
  - `test_javascript_contract_agrees_with_the_spec`
  - `test_receipt_contract_agrees_with_the_spec`
  - `test_secret_rules_are_destination_based`
  - `test_selector_contract_agrees_with_the_spec`
- `test_flow_inventory.py` — Keep the version-3 action inventory complete and current. (3 tests)
  - `test_every_catalog_id_resolves_to_a_kind_or_guard`
  - `test_every_event_kind_is_in_the_matrix`
  - `test_inventory_document_is_current`
- `test_flow_runner.py` — Real-browser coverage of Studio functional tests and screenshot evidence. (18 tests)
  - `test_browser_state_assertions`
  - `test_cancelled_flows_keep_state_distinct_in_json_and_junit`
  - `test_console_and_invalid_selector_assertions_fail`
  - `test_empty_test_is_rejected`
  - `test_failed_contract_retries_then_skips_and_captures`
  - `test_failed_workspace_writes_junit_and_selection_error`
  - `test_flow_cli_reports_failure_and_rejects_invalid_viewport`
  - `test_http_call_actions_share_or_isolate_cookies`
  - `test_http_response_capture_feeds_the_next_request`
  - `test_module_entrypoint_runs_main`
  - `test_navigation_and_ci_reports`
  - `test_network_expectation_timeout_is_reported`
  - `test_output_bindings_and_unsupported_steps_fail`
  - `test_screenshot_capture_failures_mark_the_step`
  - `test_semantic_replay_and_durable_evidence`
  - `test_ui_response_expectations_and_explicit_screenshot`
  - `test_unsupported_flow_configuration_is_rejected`
  - `test_websocket_response_capture_feeds_the_next_action`
- `test_flow_runner_actions.py` — Run data, viewport, touch and REST actions in a real Chromium page. (10 tests)
  - `test_binding_fails_when_the_extended_selector_matches_nothing`
  - `test_binding_reads_through_an_extended_selector`
  - `test_extract_and_set_variable_actions`
  - `test_flow_inputs_are_variables_from_the_first_action`
  - `test_rest_action_binds_validates_and_records`
  - `test_rest_action_fails_when_a_check_does_not_hold`
  - `test_touch_gestures_reach_the_page`
  - `test_viewport_actions_resize_and_rotate`
  - `test_wait_actions_fail_on_bad_conditions`
  - `test_wait_actions_resolve_every_condition`
- `test_flow_runner_selectors.py` — Run actions that use stored selectors, several targets and pacing. (10 tests)
  - `test_a_failed_target_skips_the_remaining_targets`
  - `test_all_targets_run_in_the_selectors_own_order`
  - `test_an_unresolvable_selector_fails_with_a_cause`
  - `test_first_target_only_acts_on_the_first_match`
  - `test_inline_expressions_and_plain_selectors_expand`
  - `test_pause_between_targets_and_after_the_action`
  - `test_record_payload_matches_the_json_contract`
  - `test_tolerated_failures_warn_and_the_flow_continues`
  - `test_tolerated_target_failures_keep_the_rest_running`
  - `test_unknown_selector_ids_are_reported`
- `test_flow_runner_variables.py` — Verify that run variables expand with key and index paths. (11 tests)
  - `test_ask_each_time_answers_fill_actions`
  - `test_fixed_capture_ignores_response`
  - `test_flow_inputs_are_saved_and_typed_per_run`
  - `test_getters_read_a_whole_list_or_dictionary`
  - `test_index_and_key_paths_expand`
  - `test_names_with_spaces_expand_whole`
  - `test_optional_path_missing_is_null`
  - `test_required_path_missing_names_variable`
  - `test_retired_receive_previous_becomes_a_variable`
  - `test_unresolved_paths_stay_untouched`
  - `test_xml_capture_reads_path`
- `test_http_request.py` — Verify the shared HTTP sender used by runs and by Studio's Send. (2 tests)
  - `test_explicit_cookie_rows_are_sent`
  - `test_send_request_returns_parsed_json`
- `test_live_run.py` — Tests for immutable live execution-run accumulation. (1 tests)
  - `test_live_run_starts_and_canonical_result_replaces_snapshot`
- `test_model.py` — Tests for deterministic viewport, targeting, and Flow models. (10 tests)
  - `test_explicit_position_pointer_accepts_coordinates`
  - `test_flow_device_scope_supports_shared_and_selected_modes`
  - `test_model_validation_rejects_invalid_contract_metadata`
  - `test_passive_response_cannot_own_network_expectation`
  - `test_selector_action_rejects_coordinates`
  - `test_selector_pointer_actions_require_css_selector`
  - `test_viewport_command_contains_mode_size_and_display_scale`
  - `test_viewport_orientation_swaps_only_when_needed`
  - `test_viewport_rejects_out_of_range_edge`
  - `test_wait_command_rejects_non_positive_duration`
- `test_model_selectors.py` — Verify selector references, targeting modes and lanes on actions. (10 tests)
  - `test_a_selector_reference_satisfies_the_selector_requirement`
  - `test_all_targets_need_a_selector_and_pace_needs_all`
  - `test_contract_pace_and_warning_status_exist`
  - `test_javascript_that_targets_elements_needs_the_sandbox`
  - `test_lane_of_follows_the_input_device`
  - `test_parallel_is_limited_to_free_lane_kinds`
  - `test_position_pointer_cannot_use_a_selector_id`
  - `test_sandbox_is_for_javascript_only`
  - `test_selector_and_selector_id_are_exclusive`
  - `test_snapshot_needs_a_selector`
- `test_model_validation_extra.py` — Validation-path coverage for immutable domain records. (3 tests)
  - `test_flow_edge_artifact_and_run_validation`
  - `test_small_record_validation_failures`
  - `test_variable_assertion_and_output_validation`
- `test_persistence_selectors.py` — Verify selectors persist beside the flows, selectors first. (7 tests)
  - `test_external_edits_to_selectors_are_not_overwritten`
  - `test_no_selectors_means_no_file_until_one_existed`
  - `test_project_round_trips_through_the_files`
  - `test_recovery_keeps_unsaved_selectors`
  - `test_save_writes_selectors_beside_the_flows`
  - `test_selectors_are_written_before_the_flows`
  - `test_uploaded_projects_and_exports_carry_selectors`
- `test_preview_frames.py` — Prove the live preview keeps only matching frames and acknowledges all. (1 tests)
  - `test_only_matching_frames_replace_the_preview_and_all_are_acknowledged`
- `test_profiles.py` — Validate profile settings and prove Chromium honours every accepted one. (8 tests)
  - `test_chromium_follows_viewport_density_and_touch_settings`
  - `test_chromium_honours_every_accepted_media_value`
  - `test_field_catalog_covers_every_editable_setting`
  - `test_profile_rejects_features_the_browser_cannot_set`
  - `test_profile_validates_values_ranges_and_identity`
  - `test_profiles_round_trip_and_legacy_files_get_defaults`
  - `test_runner_scopes_a_flow_to_exactly_one_saved_profile`
  - `test_touch_survives_full_page_screenshots_only_when_restored`
- `test_project_assets.py` — Verify portable screenshot projects and transactional asset imports. (2 tests)
  - `test_invalid_asset_does_not_replace_project`
  - `test_project_transfers_between_roots`
- `test_rebase.py` — Recorded local URLs follow the target; outside addresses never move. (2 tests)
  - `test_rebase_url_moves_only_local_addresses`
  - `test_target_origin_follows_mode_and_port`
- `test_record_core.py` — Record exactus findings and normalized report data. (6 tests)
  - `test_findings_by_mode`
  - `test_record_cli_crawls_and_replays_project`
  - `test_record_cli_exports_session_and_replays_program`
  - `test_record_cli_studio_and_invalid_setup`
  - `test_report_data_is_normalized`
  - `test_report_data_skipped_actions`
- `test_record_report.py` — RECORD renders result.md from its normalized result.json and template. (6 tests)
  - `test_crash_render_shows_error_and_na_blocks`
  - `test_crashed_exec_worker_renders_error_report`
  - `test_empty_session_state_why_nothing_is_listed`
  - `test_execute_exactus_renders_record_from_template`
  - `test_failing_exec_renders_error_report`
  - `test_golden_result_renders_expected_markdown`
- `test_recorder.py` — Action recording, normalization, compilation and replay. (14 tests)
  - `test_compile_all_actions_and_write`
  - `test_exactus_record_argument_errors`
  - `test_exactus_record_cli`
  - `test_exactus_record_replay_failures_fail`
  - `test_key_chords`
  - `test_load_actions`
  - `test_locator_compilers`
  - `test_normalizer_collapses_noise`
  - `test_recorder_form_session`
  - `test_recorder_hover_filters_inert`
  - `test_recorder_preserves_fast_submit_order`
  - `test_recorder_session`
  - `test_replay_session`
  - `test_replayer_locate_strategies`
- `test_recorder_protocol.py` — Tests for selector-first recorder NDJSON and playback protocol. (16 tests)
  - `test_command_encoder_includes_active_flow`
  - `test_dispatch_carries_the_projects_selectors`
  - `test_event_decoder_accepts_websocket_keyframe`
  - `test_event_decoder_rejects_unknown_kind`
  - `test_expectation_result_message_decodes`
  - `test_play_request_contains_flow_actions_and_capture_policy`
  - `test_play_request_serializes_http_post_session_and_expectation`
  - `test_position_pointer_event_accepts_explicit_coordinates`
  - `test_protocol_decodes_terminal_checkpoint_and_progress_variants`
  - `test_protocol_encodes_execution_control_messages`
  - `test_protocol_rejects_malformed_message_shapes`
  - `test_protocol_scalar_validation_helpers`
  - `test_run_started_progress_decodes`
  - `test_screenshot_message_decodes_record_artifact`
  - `test_selector_event_accepts_selector_without_coordinates`
  - `test_selector_event_rejects_coordinate_fallback`
- `test_recording_groups.py` — Persist recording parents and preserve capture ownership and cadence. (4 tests)
  - `test_capture_clock_pause_resume_and_owner`
  - `test_recorded_playback_waits_and_can_cancel`
  - `test_recording_parent_rename_shift_and_delete`
  - `test_recording_parent_round_trip`
- `test_response_paths.py` — Verify that response values are read by JSON and XML paths. (5 tests)
  - `test_json_path_missing_returns_none`
  - `test_json_path_reads_nested_index`
  - `test_xml_path_reads_attribute`
  - `test_xml_path_reads_text`
  - `test_xml_with_dtd_is_rejected`
- `test_run_gate.py` — Pause, resume and step a run between actions, in a real Chromium page. (3 tests)
  - `test_a_free_gate_never_blocks_the_runner`
  - `test_cancellation_releases_a_held_runner`
  - `test_pause_step_and_resume_hold_a_real_run`
- `test_selector_conditions.py` — Wait for conditions that read selector probes, and feed connections. (9 tests)
  - `test_a_condition_that_never_holds_fails_the_gate`
  - `test_a_pace_waits_for_a_condition_that_becomes_true`
  - `test_a_probe_for_a_missing_selector_is_an_error`
  - `test_a_tolerated_gate_failure_lets_the_flow_continue`
  - `test_an_invalid_condition_fails_at_once`
  - `test_connection_probes_come_back_as_flow_outputs`
  - `test_edge_probe_names_come_from_the_leaving_connections`
  - `test_probe_references_are_found_once_in_order`
  - `test_probes_measure_the_page`
- `test_selector_engine.py` — Verify the ExtendedSelector package engine and its loader. (2 tests)
  - `test_engine_script_is_a_plain_script`
  - `test_package_files_match_the_library`
- `test_selector_resolver.py` — Resolve stored selectors in a real browser page. (12 tests)
  - `test_a_wrong_count_is_reported_after_the_timeout`
  - `test_an_invalid_expression_fails_fast`
  - `test_broken_stored_selectors_do_not_break_others`
  - `test_every_match_gets_css_that_finds_only_it`
  - `test_failed_checks_name_the_element_and_the_check`
  - `test_pages_with_a_strict_csp_still_resolve`
  - `test_shadow_elements_resolve_to_chains`
  - `test_sort_order_survives_the_round_trip`
  - `test_stored_selectors_resolve_by_name`
  - `test_the_page_is_left_untouched`
  - `test_the_world_is_rebuilt_after_a_navigation`
  - `test_waits_for_elements_that_appear_late`
- `test_selector_sandbox.py` — Run snippets in the isolated sandbox, alone and from the flow runner. (11 tests)
  - `test_a_throwing_snippet_fails_with_a_cause_and_an_error_entry`
  - `test_both_snippet_styles_work_and_errors_are_reported`
  - `test_canonical_exactus_runtime_exposes_context_and_variables`
  - `test_document_resolves_stored_selector_names`
  - `test_parallel_targets_run_together_and_report_each`
  - `test_sequential_targets_each_run_the_snippet`
  - `test_snippets_get_the_flow_context`
  - `test_streams_and_vars_persist_between_snippets`
  - `test_streams_are_persisted_on_the_record`
  - `test_targets_run_at_the_same_time`
  - `test_the_sandbox_is_separate_from_the_page`
- `test_selector_snapshot.py` — Record matched elements as snapshots and warn when they drift. (7 tests)
  - `test_a_matching_baseline_is_quiet`
  - `test_a_snapshot_records_the_element`
  - `test_a_stored_baseline_is_read_leniently`
  - `test_drift_warns_without_failing_the_flow`
  - `test_evidence_comparison_tolerates_small_box_changes`
  - `test_snapshots_need_an_extended_selector_expression`
  - `test_snapshots_of_all_targets_make_one_record_each`
- `test_selector_store.py` — Verify selector usage, deletion guard, renaming and dangling references. (5 tests)
  - `test_delete_is_guarded_unless_forced`
  - `test_names_are_found_in_expressions_and_conditions`
  - `test_rename_rewrites_references_and_flags_scripts`
  - `test_upsert_replaces_by_identifier_and_keeps_names_unique`
  - `test_usage_counts_actions_selectors_and_conditions`
- `test_selectors.py` — Verify selector models, pacing and the selectors document codec. (7 tests)
  - `test_document_round_trip_is_atomic_and_stable`
  - `test_invalid_selectors_are_rejected`
  - `test_malformed_documents_are_rejected`
  - `test_pace_rejects_unwaitable_values`
  - `test_pace_round_trip_and_defaults`
  - `test_selector_set_needs_unique_ids_and_names`
  - `test_unreadable_files_are_selector_errors`
- `test_similarity.py` — Perceptual image similarity loading and cache contracts. (5 tests)
  - `test_compare_detailed_breakdown`
  - `test_compare_scores`
  - `test_history_and_cache`
  - `test_load_rejections`
  - `test_load_source_variants`
- `test_store.py` — Tests for Flow graph state and deterministic persistence. (11 tests)
  - `test_edges_redefine_in_place_and_reorder`
  - `test_event_append_move_and_delete_resequence`
  - `test_expectation_and_screenshot_round_trip`
  - `test_flow_graph_allows_branching_and_cycles`
  - `test_flow_graph_rejects_direct_self_loop`
  - `test_place_and_retime_keep_replay_order_and_time_aligned`
  - `test_store_mutation_surface_updates_canonical_workspace`
  - `test_store_rejects_duplicate_and_missing_references`
  - `test_update_flow_rejects_empty_name`
  - `test_workspace_rejects_unsupported_versions`
  - `test_workspace_v3_comprehensive_round_trip`
- `test_store_errors.py` — Workspace loading rejects unreadable, unsupported, and duplicated data. (5 tests)
  - `test_duplicate_flow_edges_are_rejected`
  - `test_duplicate_flow_ids_are_rejected`
  - `test_duplicate_variable_names_are_rejected`
  - `test_load_rejects_unreadable_files`
  - `test_unsupported_version_is_rejected`
- `test_store_selectors.py` — Verify the workspace codec keeps selector fields and run causes. (5 tests)
  - `test_a_half_described_unit_is_rejected`
  - `test_invalid_selector_fields_are_workspace_errors`
  - `test_old_documents_load_with_defaults`
  - `test_run_records_keep_cause_unit_and_warning_status`
  - `test_selector_fields_round_trip`
- `test_studio_action_setup.py` — Verify that an action can be added first and configured afterwards. (6 tests)
  - `test_a_click_without_a_target_is_added_as_incomplete`
  - `test_a_flow_with_an_unfinished_action_will_not_run`
  - `test_a_navigation_label_follows_its_address_until_renamed`
  - `test_a_value_that_is_wrong_not_blank_is_still_refused`
  - `test_configuring_an_incomplete_action_completes_it`
  - `test_only_an_unfinished_action_stores_the_incomplete_flag`
- `test_studio_boundaries.py` — Cover live-input validation and read-only target inspection boundaries. (13 tests)
  - `test_a_new_project_suggests_the_demo_server_and_start_opens_its_page`
  - `test_a_still_page_never_looks_stale_while_it_is_watched`
  - `test_command_guards_reject_invalid_and_busy_operations`
  - `test_input_backpressure_is_reported_and_leaves_document_unchanged`
  - `test_live_input_boundaries`
  - `test_preview_maps_input_after_full_page_screenshot`
  - `test_preview_survives_missing_screencast_frames`
  - `test_selected_profile_reaches_the_real_page_and_bad_ones_are_refused`
  - `test_shared_demo_server_survives_another_service_stop`
  - `test_target_inspection_is_read_only`
  - `test_target_inspection_names_frames_and_survives_detachment`
  - `test_target_is_configured_started_and_opened_through_studio`
  - `test_target_url_rejects_unsafe_destinations`
- `test_studio_duplicate_step.py` — Verify that a step can be duplicated in place. (1 tests)
  - `test_a_duplicate_follows_its_source_with_fresh_ids`
- `test_studio_entrypoint.py` — Launch the Studio package with a bounded real service lifetime. (7 tests)
  - `test_studio_cli_maps_launch_options`
  - `test_studio_editor_link_and_shutdown`
  - `test_studio_package_cli_stops_cleanly`
  - `test_studio_preserves_unrelated_listener`
  - `test_studio_rejects_invalid_duration`
  - `test_studio_replaces_previous_package_launcher`
  - `test_the_test_browser_has_no_window_unless_asked`
- `test_studio_http_contract.py` — Verify browser Studio's public HTTP security and mutation contracts. (26 tests)
  - `test_a_run_pauses_steps_and_resumes_in_a_real_browser`
  - `test_bootstrap_rejects_foreign_origins`
  - `test_bounded_history_requests_snapshot_after_eviction`
  - `test_bundled_demo_runs_real_graph_and_retains_evidence`
  - `test_clock_module_root_alias`
  - `test_clock_package_asset_allowlist`
  - `test_clock_package_assets`
  - `test_command_header_and_payload_boundaries`
  - `test_duplicate_commands_and_concurrent_tabs`
  - `test_editor_flow_steps_assertions_and_connections`
  - `test_editor_persists_websocket_request_configuration`
  - `test_editor_rejects_non_websocket_session_urls`
  - `test_editor_reorders_and_retimes_steps`
  - `test_event_stream_delivers_initial_snapshot`
  - `test_event_subscription_limit_releases_slots`
  - `test_every_imported_stylesheet_and_module_is_served`
  - `test_extended_selector_assets_are_served`
  - `test_import_save_conflict_and_path_boundaries`
  - `test_invalid_commands_preserve_workspace`
  - `test_invalid_editor_steps_leave_document_unchanged`
  - `test_managed_browser_record_replay_and_close`
  - `test_package_projects_are_served_from_the_root_package_folder`
  - `test_raw_tab_gets_a_recovery_page_without_weakening_authorization`
  - `test_readiness_assets_and_authorization`
  - `test_recording_parent_captures_real_demo_clicks`
  - `test_studio_discovers_and_verifies_target`
- `test_studio_projects.py` — Drive the project commands through a real Studio service. (4 tests)
  - `test_creating_a_project_opens_it_with_unique_names`
  - `test_details_can_be_edited_and_names_stay_unique`
  - `test_duplicate_delete_and_import`
  - `test_switching_projects_guards_unsaved_edits`
- `test_studio_selectors.py` — Drive the selector editor commands through a real Studio service. (6 tests)
  - `test_a_selector_in_use_cannot_be_deleted_without_force`
  - `test_an_action_can_use_a_selector_and_its_targeting`
  - `test_connection_conditions_are_checked_when_saved`
  - `test_names_and_expressions_are_validated`
  - `test_saving_creates_then_edits_a_selector`
  - `test_testing_a_selector_in_the_live_page`
- `test_studio_window.py` — Resolve the Studio window setting from CLI flag and pyproject. (2 tests)
  - `test_default_is_false`
  - `test_pyproject_enables_and_flag_overrides`
- `test_target.py` — Cover the application target: its rules, file format and running service. (8 tests)
  - `test_check_tells_reachable_closed_and_unknown_addresses_apart`
  - `test_port_detection_prefers_healthy_local_servers_then_lowest_port`
  - `test_service_honours_a_manually_set_port`
  - `test_service_reports_failures_a_person_can_act_on`
  - `test_service_starts_detects_its_port_and_stops`
  - `test_target_rejects_unusable_settings`
  - `test_target_round_trips_and_a_typed_port_moves_to_the_port_field`
  - `test_url_target_builds_its_address_from_url_and_port`
- `test_v3_execution.py` — Freeze what version-3 flows compute so v4 can prove equivalence. (2 tests)
  - `test_guarded_chain_results_are_frozen`
  - `test_javascript_paths_are_frozen`
- `test_v3_fixture_builder.py` — Exercise the version-3 fixture regeneration utility. (7 tests)
  - `test_build_chains_guarded_events`
  - `test_build_covers_every_edge_mode`
  - `test_build_covers_every_variable_scope`
  - `test_build_keeps_legacy_receive_previous_shape`
  - `test_build_returns_every_fixture`
  - `test_canonical_round_trips_through_the_codec`
  - `test_main_writes_the_committed_fixtures`
- `test_v3_fixtures.py` — Prove the frozen version-3 workspaces load, round-trip and migrate. (5 tests)
  - `test_canonical_fixture_round_trips`
  - `test_condition_edge_requires_an_expression`
  - `test_edge_modes_are_all_present`
  - `test_receive_previous_migrates_to_a_named_result`
  - `test_variable_scopes_are_all_present`
- `test_where.py` — Placeholder test module. (1 tests)
  - `test_where`
- `test_workspace_actions.py` — Verify current workspace interchange and selector-based actions. (6 tests)
  - `test_actions_become_valid_events`
  - `test_css_selector_candidates`
  - `test_events_roundtrip_to_actions`
  - `test_exports_load_in_real_flow_studio`
  - `test_invalid_events_rejected`
  - `test_workspace_files`

<!-- exactus:reference:end -->
