# Studio styles

`style.css` is the only stylesheet entry point; `../editor.css` imports it. It loads the token pipeline (`tokens/`) and then every component (`components/<name>/`) in canonical cascade order.

Rules consume only SEMANTIC aliases, aliases select exactly one CATALOG specification, CATALOG consumes BASE, BASE derives from PRIMARY and DYNAMIC inputs. See `tokens/README.md` for the hierarchy and `components/README.md` for the load order.

Every component directory has exactly `semantic.css`, `style.css`, and `README.md`. Components that must enter the cascade later use a separate semantic directory name; `style.css` remains the explicit order manifest. A server test checks that every imported stylesheet is served and none is orphaned.

Native CSS nesting is used where a selector extends an adjacent parent rule, and `:where(...)` marks deliberately low-specificity shared scopes.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`style.css`](style.css) — Studio stylesheet entry point. Tokens, then each component's aliases (order-independent), then its rule files in cascade order.

### Subdirectories

- [`components/`](components/README.md) — Each component directory owns exactly `semantic.css`, `style.css`, and `README.md`. Load semantic before style for a component. `../style.css` preserves interleaved cascade phases by importing separately named semantic components at their original positions.
- [`tokens/`](tokens/README.md) — The design-token hierarchy of the Studio: each tier references only the tiers above it.

<!-- exactus:inventory:end -->
