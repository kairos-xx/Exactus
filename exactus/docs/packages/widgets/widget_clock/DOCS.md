# `exactus/packages/widgets/widget_clock/` — seven-segment & matrix timecode widget

`exactus.packages.widgets.widget_clock` is a reusable browser widget package. `widget_clock.js`
defines the `AnalogClock` class (seven-segment and dot-matrix rendering
modes) and installs one shared `.sst-*` stylesheet automatically via
`adoptedStyleSheets` — no external widget CSS is needed. `index.js` is the
named/default ES-module facade; the plain script also supports being loaded
as a classic script so the demo works when opened as a local file.
Methods use arrow class fields; pure helpers are static.

## Embedding

```js
import { AnalogClock } from "./packages/widgets/widget_clock/index.js";

const clock = new AnalogClock(target, {
  live: false,          // externally driven (timeline) mode
  fps: 30,
  recording: false,
  recVisible: "hidden",
});
clock.setTime(1234);    // elapsed milliseconds -> 00:00:01.07
clock.setFrame(1800);   // integer frame index   -> 00:01:00.00
clock.destroy();        // disconnects observers, cancels pending callbacks
```

The host provides a sized `HTMLElement` (`target`) in the current document;
only one clock can occupy a target. In externally driven mode the widget
never starts its own playback timer — the host drives `setTime`/`setFrame`
from its playback or scrub state. Studio serves this package from its
resources with a fixed asset allowlist and uses it as the timeline header
segment renderer with millisecond precision; playback ownership stays in
Studio.

## Instance API

- `new AnalogClock(target, settings?)` — validates `settings` before
  applying; unknown keys, wrong types and invalid values throw.
- `setTime(milliseconds)` — chainable; floors milliseconds to the frame
  boundary, displays elapsed time.
- `setFrame(index)` — chainable; frame timecode is non-drop-frame,
  integer `fps` in `1–100`, below 100 hours. Requires four two-digit
  groups (`dd:dd:dd.dd`), i.e. no millisecond template.
- `value = "12:34:56.07"` / `groupValues = ["12","34","56","07"]` — manual
  display; the `value` getter returns a defensive group array.
- `timecode` — the rendered label. `timeMilliseconds` — the externally
  supplied position, or `null` after manual/live changes.
- `clear()` — blanks the display. `resume()` — explicitly starts
  wall-clock (`live`) mode.
- `set(options)` / `getSettings()` — validated update; `getSettings()`
  returns a defensive serializable snapshot including CSS bindings.
- `settings` — proxy whose assignments go through the same
  validation/update path as `set()`; assigning a `"--var-name"` string
  binds the setting to that CSS variable.
- `destroyed` — destruction state. `destroy()` is idempotent; updates on a
  destroyed instance throw.

## Statics

- `AnalogClock.formatTime(milliseconds, {fps})` and
  `AnalogClock.formatFrame(index, {fps})` — pure formatting helpers.
- `AnalogClock.DEFAULTS` — the frozen full option table (below).
- `AnalogClock.CSS_SETTINGS` — setting → `[css-variable, unit]` map.
- `AnalogClock.validateSettings(settings)` / `validateFps(fps)` —
  the validators the constructor applies.
- `AnalogClock.installStyles(documentRef)` /
  `refreshInstanceStyles()` — shared/per-document stylesheet plumbing.

## Options (`DEFAULTS`)

Timecode & renderer:

| Option | Default | Meaning |
|---|---|---|
| `value`, `groupValues` | `null` | Manual display content. |
| `live` | `true` | Wall-clock mode when not externally driven. |
| `fps` | `30` | Frames per second for `setFrame`/`formatFrame` (1–100). |
| `mode` | `"segment"` | `"segment"` or `"matrix"` renderer. |
| `template` | `"dd:dd:dd.dd"` | Group template; `"dd:dd:dd.ddd"` gives ms precision. |
| `structure` | `null` | Explicit segment structure; `null` derives it from `template`. |

Matrix renderer:

| Option | Default |
|---|---|
| `matrixLayout` | `"content"` |
| `matrixRows` / `matrixColumns` | `7` / `5` |
| `matrixDotSize` / `matrixDotGap` | `7` / `4` |
| `matrixOnColor` / `matrixOffColor` | `"#ff3b30"` / `"#251514"` |
| `matrixGlowSize` | `5` |

Segment renderer:

| Option | Default |
|---|---|
| `digitWidth` / `digitHeight` / `digitInset` | `120` / `192` / `14` |
| `segmentLength` / `segmentThickness` | `76` / `14` |
| `segmentGap` / `digitGap` / `groupGap` / `separatorWidth` | `4` / `0` / `0` / `24` |
| `dotSize` | `10` |
| `blinkSeparatorsOnSecond` / `dotBlinkDuration` | `true` / `160` |
| `segmentOnColor` / `segmentOffColor` | `"#ff3b30"` / `"#251514"` |
| `segmentGlowColor` / `segmentGlowSize` | `"#ff3b30"` / `5` |
| `segmentOnDuration` / `segmentOffDuration` | `120` / `300` |
| `transitionEasing` | `"cubic-bezier(.2,.8,.2,1)"` |

REC badge & frame:

| Option | Default |
|---|---|
| `recVisible` / `recEnabled` / `recording` / `recPulse` | `"visible"` / `true` / `true` / `true` |
| `recLedSize` | `12` |
| `recLedOnColor` / `recLedOffColor` / `recLedGlowColor` / `recLedGlowSize` | `"#ff2d2d"` / `"#3b1818"` / `"#ff2d2d"` / `12` |
| `recPulseDuration` | `1000` |
| `recLabel` | `"REC"` |
| `recFontFamily` / `recFontSize` / `recFontWeight` / `recLetterSpacing` / `recTextColor` | mono stack / `15` / `700` / `2` / `"#aeb3ba"` |
| `recGap` / `recWidgetGap` | `10` / `20` |
| `background` / `align` / `padding` | `"transparent"` / `"center"` / `0` |

## Reactive CSS-variable settings

Any setting can be bound to a CSS custom property by assigning the
variable name as a string:

```js
target.style.setProperty("--segment-off-duration", "300ms");
clock.settings.segmentOffDuration = "--segment-off-duration";
target.style.setProperty("--segment-off-duration", "0.5s"); // live update

clock.settings.matrixRows = "--matrix-rows";                // runtime binding
clock.settings.matrixRows = 7;                              // removes binding
```

- Variables are read on the target, including inherited values.
- Native-CSS settings (durations, colors, font dimensions — the
  `CSS_SETTINGS` map) keep `var(--sst-*)` in the stylesheet and need no
  polling: `segmentOnDuration`/`OffDuration`, `dotBlinkDuration`,
  `transitionEasing`, `segmentOnColor`/`OffColor`, `recPulseDuration`,
  `recTextColor`, `recLedOnColor`/`OffColor`, `recFontSize`/`Weight`/
  `Family`/`LetterSpacing`, `background`, `align` map to `--sst-*`.
- Runtime-only settings (e.g. `matrixRows`) use one shared
  animation-frame watcher per instance while bindings exist; only changed
  valid values rebuild the renderer.
- Invalid runtime CSS keeps the last valid value; initially invalid
  configured values throw. Undefined variables fall back to the last
  valid value.
- Units: runtime numeric variables are unitless numbers; CSS durations
  use `ms`/`s`; font dimensions use `px`.
- Nested structures (`structure`) are snapshots — update with
  `set({structure})`, not mutation.

## Demo and tests

`examples/web/{index.html,style.css,code.js}` is a demo-specific harness
(slider+spinbox controls, mouse/touch/keyboard resize grip); its CSS only
styles the demo. Studio demo URL:
`/studio/packages/widgets/widget_clock/examples/web/index.html`.

Launch a standalone mini-server and open the managed browser (the
launcher exits when the browser closes; the background server is reused
by later launches and serves only this package; access logs go to the
system temp directory):

```bash
python -m exactus.packages.widgets.widget_clock.examples
```

Tests:

```bash
node --test exactus/tests/packages/widgets/widget_clock/widget_clock.test.mjs
```

## Layout

```
exactus/packages/widgets/widget_clock/
├── index.js           # ES-module facade (named + default export)
├── widget_clock.js    # AnalogClock class, .sst-* stylesheet install
├── README.md
└── examples/
    ├── __main__.py    # venv bootstrap -> demo launcher
    ├── run.py         # exactus.packages.server + managed-browser demo runner
    └── web/           # demo page: index.html + style.css + code.js
```

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Package the reusable JavaScript timeline clock and its browser demo. |
| `examples/` | Runnable demonstration for `exactus/widgets/widget_clock/`. |
| `index.js` | JavaScript module. |
| `widget_clock.js` | JavaScript module. |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Package the reusable JavaScript timeline clock and its browser demo.


### `examples/__init__.py`

Runnable browser demonstration of the reusable timeline clock.


### `examples/__main__.py`

Run the analog-clock example with the project virtual environment.


### `examples/run.py`

Start the loopback demo server and open the managed browser.

- `start_demo(*, log: Path) -> str` — Serve this package only, including the demo's relative library import.
- `main() -> int` — Launch the demo; leave its reusable background server running.

## JavaScript API reference

Top-level exports, read from the source.

### `index.js`

- `AnalogClock`

## Examples

Runnable demonstration for `exactus/widgets/widget_clock/`.

Start the loopback demo server and open the managed browser.

```bash
python -m exactus.widgets.widget_clock.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`, `examples/web/README.md`, `examples/web/code.js`, `examples/web/index.html`, `examples/web/style.css`

## Dependencies and consumers

- Other packages: [`browser`](../../browser/DOCS.md), [`server`](../../server/DOCS.md)
- Used by: `tests/packages/widgets/widget_clock/test_examples.py`

## Tests

Tests live in `exactus/tests/packages/widgets/widget_clock/`.

- `test_examples.py` — Coverage for the widget_clock demo server launcher. (4 tests)
  - `test_main_prints_url_and_opens_browser`
  - `test_module_entrypoint_invokes_main`
  - `test_start_demo_replaces_unready_server`
  - `test_start_demo_serves_assets_and_reuses`

<!-- exactus:reference:end -->
