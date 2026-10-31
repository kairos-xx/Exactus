# Local selector libraries

The selector **engine** and its structured formula editor. The expression widget that edits selectors in Studio lives in its own package, [`widget_selector/`](../widgets/widget_selector/README.md).

This bundle contains the integration files and a pinned `package.json`. **Third-party package code is not bundled** because downloading the npm tarballs was unavailable in the packaging environment.

Run in this folder:

```bash
npm install
npm run verify
```

This downloads the three packages into `node_modules` locally. To run offline afterward, retain the whole folder including `node_modules`. For a deployable browser bundle, use your existing bundler (Vite/esbuild/Rollup) on `selector-adapters.js`; npm bare imports cannot be loaded directly by an ordinary browser without bundling or an import map.

```js
import { ExtendedSelector } from "./editor/extended-selector.js";
import { bestLocalSelector } from "./editor/selector-adapters.js";

const engine = new ExtendedSelector(document);
const element = document.querySelector("button");
const result = bestLocalSelector(engine, element);
console.log(result.selector, result.candidates);
```

**Libraries and versions:** css-selector-generator 3.9.4; optimal-select 4.0.1; @medv/finder 4.0.2. `optimal-select.optimize()` is a function in the same optimal-select package; it is not a fourth dependency.

**Caveats:** The engine's current specificity/fragility scores are heuristics, not a full CSS Selectors Level 4 specificity parser. Exact-target matching is checked before ranking. The browser integration has not been executed in this environment.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Package the ExtendedSelector engine and editor for the Studio web server.
- [`package.json`](package.json) — Provide package json content.
- [`verify.mjs`](verify.mjs) — Provide verify mjs content.

### Subdirectories

- [`editor/`](editor/README.md) — Provide extended selector editor css content.
- [`examples/`](examples/README.md) — Demo harness for the ExtendedSelector structured editor.

<!-- exactus:inventory:end -->
