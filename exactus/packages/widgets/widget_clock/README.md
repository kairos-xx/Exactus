# Analog clock / timeline timecode

Reusable browser widget: `widget_clock.js` contains the clock class and installs
one shared `.sst-*` stylesheet automatically. No external widget CSS is needed.
`index.js` is the named/default
ES-module entry point. Methods use arrow class fields; pure helpers are static.
Constructors and property accessors retain their required native syntax.

## Studio import

Studio serves this package from its resources, with a fixed asset allowlist.
The same files are included in distributions; nothing is copied into `web/`.

```js
import { AnalogClock } from "./packages/widgets/widget_clock/index.js";

const clock = new AnalogClock(target, {
  live: false,
  fps: 30,
  recording: false,
  recVisible: "hidden",
});
clock.setTime(1234); // elapsed milliseconds -> 00:00:01.07
clock.setFrame(1800); // integer frame index -> 00:01:00.00
// Drive setTime from the existing timeline playback/scrub state.
// The widget does not start a playback timer in externally driven mode.
clock.destroy(); // disconnects observers and cancels pending callbacks
```

Studio's timeline header uses this segment renderer with millisecond precision;
playback ownership stays in Studio. Hosts provide a sized target element in
the current document. Only one clock can occupy a target.

## Values and lifecycle

- `setTime(milliseconds)` is chainable: use four two-digit groups for frames,
  or `template: "dd:dd:dd.ddd"` for millisecond precision, as in Studio's header.
  `setFrame(index)` requires four two-digit groups. Frame timecode is
  non-drop-frame, 1–100 integer FPS, below 100 hours.
- `AnalogClock.formatTime(milliseconds, {fps})` and `formatFrame(index, {fps})`
  are pure formatting helpers. Milliseconds are floored to the frame boundary.
- `value = "12:34:56.07"` or `groupValues = ["12", "34", "56", "07"]`
  sets a manual display. The legacy `value` getter returns a defensive group array.
- `timecode` returns the rendered label; `timeMilliseconds` is the externally
  supplied position, or null after manual/live changes.
- `clear()` blanks the display; `resume()` explicitly starts wall-clock mode.
- `set(options)` validates configuration before applying it. `getSettings()`
  returns a defensive, serializable snapshot, including CSS bindings.
- `destroy()` is idempotent. Updates on a destroyed instance throw an error.

## Reactive CSS-variable settings

```js
target.style.setProperty("--segment-off-duration", "300ms");
clock.settings.segmentOffDuration = "--segment-off-duration";
target.style.setProperty("--segment-off-duration", "0.5s");

target.style.setProperty("--matrix-rows", "9");
clock.settings.matrixRows = "--matrix-rows";
target.style.setProperty("--matrix-rows", "12");

clock.settings.matrixRows = 7; // numeric assignment removes the binding
```

Variables are read on the target, including inherited variables. Native CSS
settings, including segment/dot/record durations and colors, retain `var(...)`
in the stylesheet and need no polling. Runtime settings such as matrix rows
use one shared-per-instance animation-frame watcher while bindings exist;
only changed valid values rebuild the renderer. Invalid runtime CSS keeps the
last valid value; initially invalid configured values throw. Undefined variables
use the last valid value as fallback. Runtime numeric variables use unitless
numbers; native CSS durations use `ms`/`s`, native font dimensions use `px`.
Direct settings assignment goes through the same validation/update path as set().
Nested structures are snapshots: update them with `set({structure})`, not mutation.

## Demo and tests

`examples/web/index.html`, `examples/web/style.css`, and `examples/web/code.js` are all
demo-specific; its CSS only styles the demo controls and layout. The demo loads the library as a classic script, so it also works
when opened directly as a local file. Numeric controls pair a slider with a
spinbox and update the renderer on input. The resize grip supports mouse/touch
dragging and arrow keys (Shift increases the increment).

Studio demo URL: `/studio/packages/widgets/widget_clock/examples/web/index.html`.

Launch a standalone mini-server and open the managed browser (the launcher exits when it is closed):

```sh
python exactus/packages/widgets/widget_clock/examples/serve.py
# or: python -m exactus.packages.widgets.widget_clock.examples
# or: ./packages/widgets/widget_clock/examples/serve.py
```

It uses `exactus.packages.server`, binds a free loopback port, waits for readiness, and
reuses an already-running demo server. It serves only this package (the demo
and its library), not the repository. The background server remains running
after the launcher exits. Access logs go to the system temporary directory.

```sh
node --test exactus/tests/packages/widgets/widget_clock/widget_clock.test.mjs
```

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Package the reusable JavaScript timeline clock and its browser demo.
- [`index.js`](index.js) — Named ES-module facade; the underlying script also supports local file demos.
- [`widget_clock.js`](widget_clock.js) — Provide widget clock js content.

### Subdirectories

- [`examples/`](examples/README.md) — Runnable browser demonstration of the reusable timeline clock.

<!-- exactus:inventory:end -->
