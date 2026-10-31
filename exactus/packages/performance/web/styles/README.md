# Styles

Entry point `style.css` imports `tokens/` then every component's `semantic.css` and `style.css`.
Rules live in the `perf-base` cascade layer.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`style.css`](style.css) — Performance dashboard stylesheet entry point. Tokens, then each component's aliases (order-independent), then its rule files in cascade order.

### Subdirectories

- [`components/`](components/README.md) — Top bar, search and global actions.
- [`tokens/`](tokens/README.md) — The design-token hierarchy of the performance dashboard: each tier references only the tiers above it.

<!-- exactus:inventory:end -->
