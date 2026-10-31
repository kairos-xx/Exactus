# `web/`

Minimal static demo for the CSS visual-cause analyzer.

`a.css` is the baseline and `b.css` contains exactly four intentional declaration changes:

1. `.primary` background: `#202529` → `#29343d`.
2. `.primary` padding: `24px` → `32px`.
3. `.secondary` border radius: `12px` → `28px`.
4. `.action` transform: `translateX(0)` → `translateX(20px)`.

The small change set keeps the generated causal report easy to inspect while exercising color, geometry, shape, and position changes.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`a.css`](a.css) — Provide a css content.
- [`b.css`](b.css) — Provide b css content.
- [`index.html`](index.html) — Provide index html content.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
