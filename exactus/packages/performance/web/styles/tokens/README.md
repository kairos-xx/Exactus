# Tokens

The design-token hierarchy of the performance dashboard: each tier references only the tiers above it.

Load order:

1. `primary.css` — irreducible literal inputs: the dimension unit (`1rem`) and the density multiplier.
2. `dynamic.css` — theme literals; `:root.light` rewrites them.
3. `base.css` — derived values: lengths are `unit × step × density`, typography is `unit × step`.
4. `catalog.css` — generic specifications composed from BASE.
5. `semantic.css` — shared roles; component-specific aliases live in `components/<name>/semantic.css`.

Set `--primary-density-unit` to scale every spacing, size and radius together; text sizes follow the root font size only.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`base.css`](base.css) — BASE — exact derived values. Built from PRIMARY and DYNAMIC only. Lengths are the dimension unit times a step times the density.
- [`catalog.css`](catalog.css) — CATALOG — generic specifications. Assembled from BASE values.
- [`dynamic.css`](dynamic.css) — DYNAMIC — theme literals. Dark defaults; `:root.light` supplies the light values. Written only by the theme toggle class.
- [`primary.css`](primary.css) — PRIMARY — literal inputs. Units and authored literals. No references, no functions.
- [`semantic.css`](semantic.css) — Shared semantic roles used across component boundaries. Each role is exactly one plain CATALOG reference.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
