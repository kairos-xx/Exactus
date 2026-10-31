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
