# `action_pointer/`

Reusable pointer-action frontend for Flow Studio. One action selector configures mouse clicks, hover, drag, scrolling, viewport coordinates, taps, long presses, swipes, and pinch gestures while preserving the existing runtime event kinds.

```js
import { mountPointerStudio } from "./action_pointer/index.js";

const studio = mountPointerStudio(document.querySelector("#pointer-action"), {
  pointer_action: "touch_swipe",
  selector: "#carousel",
  direction: "left",
});
```

The generated controls use the command field names documented in `docs/ACTIONS.md`. `pointer_action` selects the concrete event; the host translates it to `click`, `drag`, `scroll`, `position_pointer`, or `gesture` before submission.

## Demo

```sh
python -m exactus.packages.actions.action_pointer.examples
```

The runnable example mounts the same frontend, previews the submitted form values, and provides live click, hover, drag, drop, scroll, and touch-oriented targets.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Package the shared pointer and touch action frontend.
- [`index.js`](index.js) — Provide index js content.
- [`pointer_studio.js`](pointer_studio.js) — Provide pointer studio js content.

### Subdirectories

- [`examples/`](examples/README.md) — Runnable browser demonstration of the shared pointer and touch action frontend.

<!-- exactus:inventory:end -->
