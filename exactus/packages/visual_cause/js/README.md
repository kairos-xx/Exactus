# `js/`

Browser-side JavaScript assets injected by the analyzer during rendering and
intervention runs.

- `prepare.js` — prepare a page for deterministic rendering.
- `install_helpers.js` — install shared helper functions in the page.
- `rules.js` — enumerate CSS rules in the document.
- `container_rules.js` — inspect container and at-rule structure.
- `css_variables.js` — resolve custom property values.
- `elements.js` — locate target elements for interventions.
- `dom_elements.js` — collect lightweight visible-element geometry for
  generic two-URL visual diffs.
- `disable_rule.js` — disable a single CSS rule.
- `disable_declaration.js` — disable a single declaration.
- `disable_declarations.js` — disable a batch of declarations.
- `override_element.js` — apply a style override to one element.
- `globals.d.ts` — ambient types for the `__cssCauseSelector` and
  `__cssCauseQuery(All)` page globals.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`container_rules.js`](container_rules.js) — Execute the browser-side CSS analysis operation.
- [`css_variables.js`](css_variables.js) — Execute the browser-side CSS analysis operation.
- [`disable_declaration.js`](disable_declaration.js) — Execute the browser-side CSS analysis operation.
- [`disable_declarations.js`](disable_declarations.js) — Execute the browser-side CSS analysis operation.
- [`disable_rule.js`](disable_rule.js) — Execute the browser-side CSS analysis operation.
- [`dom_elements.js`](dom_elements.js) — Provide dom elements js content.
- [`elements.js`](elements.js) — Serialize a Typed OM value.
- [`globals.d.ts`](globals.d.ts) — Provide globals.d ts content.
- [`install_helpers.js`](install_helpers.js) — Provide install helpers js content.
- [`override_element.js`](override_element.js) — Execute the browser-side CSS analysis operation.
- [`prepare.js`](prepare.js) — Provide prepare js content.
- [`rules.js`](rules.js) — Execute the browser-side CSS analysis operation.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
