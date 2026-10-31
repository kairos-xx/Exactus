# `action_pointer` — shared pointer and touch frontend

## Purpose

`action_pointer` provides one configuration surface for every interaction listed in `docs/ACTIONS.md` §2.1 and §2.2. It groups Click, Double click, Right click, Hover, Drag to, Scroll, Viewport position, Tap, Long press, Swipe, and Pinch / zoom in one **Interaction** chooser.

## Files

| File | Description |
|---|---|
| `index.js` | Public module surface: re-exports `PointerStudio` and `mountPointerStudio` (also as default) so hosts import everything through `./action_pointer/index.js`. |
| `pointer_studio.js` | Implementation: the eleven-operation interaction chooser, per-operation field visibility, value preservation across switches, `studio.value()`, and the Flow Studio adapter (`actionCommand`/`definitionForEvent`) mapping GUI state to the runtime event schema. |

Only fields relevant to the selected operation remain visible. Switching operations preserves values already entered during the current editing session.

## Browser API

```js
import { mountPointerStudio } from "./action_pointer/index.js";

const studio = mountPointerStudio(host, {
  pointer_action: "touch_swipe",
  selector: "#carousel",
  direction: "left",
  distance: "240",
  duration_ms: "350",
});
```

`mountPointerStudio(host, seed)` replaces `host` contents and returns a `PointerStudio`. `studio.value()` returns the selected operation. The generated native controls participate in the surrounding form.

## Field contract

| Operation | Submitted fields |
|---|---|
| Click, Double click, Right click, Hover, Tap | `pointer_action`, `selector` |
| Drag to | `pointer_action`, `selector`, `destination` |
| Scroll | `pointer_action`, `selector`, `scroll_x`, `scroll_y` |
| Viewport position | `pointer_action`, `position_action`, `x`, `y` |
| Long press | `pointer_action`, `selector`, `duration_ms` |
| Swipe | `pointer_action`, `selector`, `direction`, `distance`, `duration_ms` |
| Pinch / zoom | `pointer_action`, `selector`, `scale`, `duration_ms` |

## Flow Studio adapter

The palette exposes one `pointer` definition. `actionCommand()` translates its selected operation into the established runtime schema:

- mouse and coordinate operations use their concrete `EventKind`;
- drag stores `destination` as its payload;
- scroll stores `{x, y}` as JSON payload;
- touch operations use `kind: "gesture"` and store the gesture discriminator and parameters as JSON payload.

Existing runtime events map back to the `pointer` definition through `definitionForEvent()`, so the common GUI also edits previously saved flows without changing playback semantics.

## Runnable example

Launch the standalone package demonstration with:

```sh
python -m exactus.packages.actions.action_pointer.examples
```

The launcher starts a reusable loopback server and opens a managed browser. The page mounts the production `PointerStudio`, previews the native form document, offers all eleven operations, and supplies live targets for pointer, drag-and-drop, scroll, and touch-oriented configurations.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Package the shared pointer and touch action frontend. |
| `examples/` | Runnable demonstration for `exactus/actions/action_pointer/`. |
| `index.js` | JavaScript module. |
| `pointer_studio.js` | JavaScript module. |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Package the shared pointer and touch action frontend.


### `examples/__init__.py`

Runnable browser demonstration of the pointer action frontend.


### `examples/__main__.py`

Run the pointer-action example with the project virtual environment.


### `examples/run.py`

Start the loopback pointer-action demo and open the managed browser.

- `start_demo(*, log: Path) -> str` — Serve this package and return its browser-demo URL.
- `main() -> int` — Launch the demo and leave its reusable server running.

## JavaScript API reference

Top-level exports, read from the source.

### `pointer_studio.js`

- `PointerStudio`
- `mountPointerStudio`

## Examples

Runnable demonstration for `exactus/actions/action_pointer/`.

Start the loopback pointer-action demo and open the managed browser.

```bash
python -m exactus.actions.action_pointer.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`, `examples/web/README.md`, `examples/web/code.js`, `examples/web/demo.css`, `examples/web/index.html`

## Dependencies and consumers

- Other packages: [`browser`](../../browser/DOCS.md), [`server`](../../server/DOCS.md)
- Used by: `tests/packages/actions/action_pointer/test_examples.py`

## Tests

Tests live in `exactus/tests/packages/actions/action_pointer/`.

- `test_examples.py` — Coverage for the pointer-action demo launcher. (4 tests)
  - `test_main_prints_url_and_opens_browser`
  - `test_module_entrypoint_invokes_main`
  - `test_start_demo_reports_unready_server_and_cleans_up`
  - `test_start_demo_serves_assets_and_reuses`

<!-- exactus:reference:end -->
