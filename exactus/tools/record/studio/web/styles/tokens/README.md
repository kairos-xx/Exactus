# Tokens

The design-token hierarchy of the Studio: each tier references only the tiers above it.

Load order:

1. `primary.css` — irreducible literal primitives.
2. `base.css` — context-free calculations from PRIMARY / proven DYNAMIC inputs.
3. `catalog.css` — generic reusable UI concepts from BASE.
4. `semantic.css` — shared roles used across component boundaries; each is exactly one plain CATALOG reference.

Component-specific semantic aliases live beside each component in `components/<name>/semantic.css` and are named from their owner, for example `--project-bar-studio-project-name-max-width`.

## Runtime inputs

`--dynamic-*` is the interface between the stylesheet and JavaScript; it has no file because CSS never declares a design default for it. Every name in it has a real writer:

| Name | Writer |
|---|---|
| `--dynamic-graph-zoom`, `--dynamic-timeline-duration`, `--dynamic-clip-top`, `--dynamic-screenshot-width` | `editor.js` |
| `--dynamic-chevron-turn`, `--dynamic-along`, `--dynamic-from`, `--dynamic-length` | `dock-grid.js` |
| `--dynamic-depth` | `condition-pills.js` (the rule for `.pill-call` holds the default) |
| `--dynamic-at`, `--dynamic-span`, `--dynamic-played-at` | `welcome.js` |
| `--dynamic-analog-clock-aspect` | `exactus/packages/widgets/widget_clock/widget_clock.js` |
| `--dynamic-lane-h` | set per density by `components/panel-modes/style.css`, read by `editor.js` |

A variable that nothing writes is a literal input and belongs in PRIMARY. BASE may reference `--dynamic-*`; component rules never read it directly.

## CSS grammar values

Generic CSS grammar values such as `flex`, `absolute`, `center`, `auto` and `pointer` are not design tokens and remain literal CSS, except for font and text properties, which are always tokenized.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`base.css`](base.css) — BASE — exact derived values. Built from PRIMARY and DYNAMIC only. Lengths use the named scale: a name is a step (`tiny`, `large`) or a step plus or minus another (`large-plus-tiny`).
- [`catalog.css`](catalog.css) — CATALOG — generic specifications. Named <property group>-<domain>-<scale steps>. Assembled from BASE values.
- [`primary.css`](primary.css) — PRIMARY — literal inputs. Units and authored literals. No references, no functions. Colours are named by family and OKLCH lightness (tenths of a percent) and alpha.
- [`semantic.css`](semantic.css) — Shared semantic roles used across component boundaries. Each role is exactly one plain CATALOG reference.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
