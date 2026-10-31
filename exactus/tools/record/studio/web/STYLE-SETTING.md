# How JavaScript sets styles on elements

Audit of every mechanism this codebase uses to put styles on DOM elements from
JS, with the code at each site. Scope: `studio/web/*.js` plus the in-repo
`exactus/packages/` widgets. Generated bundles under `exactus/bundle/**` and result
artifacts under `EXACTUS_RESULTS/**` are excluded.

Mechanisms found, in order of frequency:

1. Direct property assignment (`el.style.left = …`)
2. `el.style.setProperty(name, value)` — custom properties and regular props
3. `Object.assign(el.style, {…})`
4. Inline `style="…"` inside generated HTML strings / `h()` attributes
5. Constructable stylesheets (`adoptedStyleSheets` + `replaceSync`)
6. `el.style.cssText` append
7. `setAttribute("style", …)` / `removeAttribute("style")` — save/restore
8. `el.style.removeProperty(name)` — cleanup counterparts

Not used anywhere in source: `insertRule`, `<style>` element injection,
`attributeStyleMap` / `styleMap`, `element.animate()` keyframes.

---

## 1. CSS custom properties set from JS

Every `--var` written from JS. Initial/default values for these live in
`styles/**/*.css`; JS only overrides at runtime.

### studio/web/editor.js

`--dynamic-graph-zoom` — graph zoom level (0.1–1.5), line 1246:

```js
EditorApp.element("graph").style.setProperty(
  "--dynamic-graph-zoom",
  String(this.graphZoom),
);
```

`--dynamic-timeline-duration` — timeline width in rem, line 2773:

```js
target.style.setProperty(
  "--dynamic-timeline-duration",
  `${(duration / interval) * scale}rem`,
);
```

`--dynamic-clip-top` — clip's lane row, line 2881:

```js
clip.style.setProperty(
  "--dynamic-clip-top",
  `calc(${row} * var(--dynamic-lane-h) + 0.25rem)`,
);
```

`--dynamic-screenshot-width` — screenshot zoom %, line 4122:

```js
EditorApp.element("screenshot-preview").style.setProperty(
  "--dynamic-screenshot-width",
  `${event.target.value}%`,
);
```

Reset when the screenshot dialog reopens, line 3533:

```js
image.style.removeProperty("--dynamic-screenshot-width");
```

`--dynamic-clip-top` is also written inline in generated markup — see §5.

### studio/web/dock-grid.js

`--dynamic-chevron-turn` — collapse-chevron rotation, line 259:

```js
const turn = {
  left: 90,
  right: -90,
  up: 180,
  down: 0,
}[direction ?? "down"];
panel.style.setProperty(
  "--dynamic-chevron-turn",
  `${turn + (collapsed ? 180 : 0)}deg`,
);
```

`--dynamic-along`, `--dynamic-from`, `--dynamic-length` — splitter handle position and length along a
grid line, lines 437–444:

```js
handle.style.setProperty(
  "--dynamic-along",
  `${offset(sizes, line.index + 1) - gap / 2}px`,
);
handle.style.setProperty("--dynamic-from", `${from}px`);
handle.style.setProperty(
  "--dynamic-length",
  `${offset(column ? rows : cols, line.to) - from - gap}px`,
);
```

### studio/web/condition-pills.js

`--dynamic-depth` — nesting depth for group/call pills, lines 209 and 245:

```js
wrap.style.setProperty("--dynamic-depth", String(depth));
```

### studio/web/welcome.js

Via `h()` → `setAttribute` (see §5), line 44:

```js
style: `--dynamic-at: ${(index / seconds) * 100}%`,
```

Line 53:

```js
style: `--dynamic-from: ${(step.start / seconds) * 100}%; --dynamic-span: ${(step.length / seconds) * 100}%; --dynamic-played-at: ${0.4 + step.start}s`,
```

### exactus/packages/extended_selector/extended-selector-editor.js

`--ese-depth` — nesting depth of expression call pills, line 302:

```js
call.style.setProperty("--ese-depth", String(depth));
```

### exactus/packages/widgets/widget_clock/widget_clock.js — two systems

**(a) Per-element `setProperty`.**

Per-group segment overrides on `.sst-group`, lines 686–724:

```js
group.style.setProperty(
  "column-gap",
  `${Number(item.digitGap ?? this.#settings.digitGap)}px`,
);
group.style.setProperty(
  "--sst-on",
  this.#settings.structure
    ? String(item.color ?? this.#settings.segmentOnColor)
    : this.cssValue("segmentOnColor"),
);
group.style.setProperty(
  "--sst-off",
  this.#settings.structure
    ? String(item.offColor ?? this.#settings.segmentOffColor)
    : this.cssValue("segmentOffColor"),
);
group.style.setProperty(
  "--sst-glow",
  String(item.glowColor ?? this.#settings.segmentGlowColor),
);
group.style.setProperty(
  "--sst-segment-glow",
  `0 0 ${Number(item.glowSize ?? this.#settings.segmentGlowSize)}px ${String(item.glowColor ?? this.#settings.segmentGlowColor)}`,
);
group.style.setProperty(
  "--sst-on-time",
  this.#settings.structure
    ? `${Number(item.onDuration ?? this.#settings.segmentOnDuration)}ms`
    : this.cssValue("segmentOnDuration", "ms"),
);
group.style.setProperty(
  "--sst-off-time",
  this.#settings.structure
    ? `${Number(item.offDuration ?? this.#settings.segmentOffDuration)}ms`
    : this.cssValue("segmentOffDuration", "ms"),
);
group.style.setProperty(
  "--sst-ease",
  String(item.easing ?? this.#settings.transitionEasing),
);
```

Marker variables on `.sst-custom-marker`, lines 760–786:

```js
marker.style.setProperty("--marker-size", `${size}px`);
marker.style.setProperty(
  "--marker-color",
  this.#settings.structure
    ? String(item.color ?? this.#settings.segmentOnColor)
    : this.cssValue("segmentOnColor"),
);
marker.style.setProperty(
  "--marker-off",
  String(item.offColor ?? this.#settings.segmentOffColor),
);
marker.style.setProperty(
  "--marker-glow-color",
  String(item.glowColor ?? item.color ?? this.#settings.segmentGlowColor),
);
marker.style.setProperty(
  "--marker-glow-size",
  `${Number(item.glowSize ?? 0)}px`,
);
marker.style.setProperty(
  "--marker-before",
  `${Number(item.gapBefore ?? 0)}px`,
);
marker.style.setProperty(
  "--marker-after",
  `${Number(item.gapAfter ?? 0)}px`,
);
```

`--dynamic-analog-clock-aspect` on the mount target, lines 1385–1389:

```js
if (naturalHeight > 0)
  this.target.style.setProperty(
    "--dynamic-analog-clock-aspect",
    String(naturalWidth / naturalHeight),
  );
```

**(b) Per-instance variables via a generated stylesheet** (see §6): the ~40
`--sst-*` keys in the `vars` object are *not* set with `setProperty`; they're
stored in `AnalogClock.#instances` and turned into a
`[data-seven-segment="<id>"]{ … }` rule by `refreshInstanceStyles()`.

Lines 1181–1226:

```js
const vars = {
  "--sst-matrix-cols": String(s.matrixColumns),
  "--sst-matrix-rows": String(s.matrixRows),
  "--sst-matrix-physical-cols": String(this.matrixTemplateWidth()),
  "--sst-matrix-physical-rows": String(s.matrixRows),
  "--sst-matrix-dot": `${s.matrixDotSize}px`,
  "--sst-matrix-gap": `${s.matrixDotGap}px`,
  "--sst-matrix-on": s.matrixOnColor,
  "--sst-matrix-off": s.matrixOffColor,
  "--sst-matrix-glow-size": `${s.matrixGlowSize}px`,
  "--sst-matrix-glow": `0 0 ${s.matrixGlowSize}px ${s.matrixOnColor}`,
  "--sst-digit-gap": `${s.digitGap}px`,
  "--sst-group-gap": `${s.groupGap}px`,
  "--sst-separator-width": `${s.separatorWidth}px`,
  "--sst-on": s.segmentOnColor,
  "--sst-off": s.segmentOffColor,
  "--sst-glow": s.segmentGlowColor,
  "--sst-glow-size": `${s.segmentGlowSize}px`,
  "--sst-segment-glow": `0 0 ${s.segmentGlowSize}px ${s.segmentGlowColor}`,
  "--sst-on-time": `${s.segmentOnDuration}ms`,
  "--sst-off-time": `${s.segmentOffDuration}ms`,
  "--sst-ease": s.transitionEasing,
  "--sst-dot-time": `${s.dotBlinkDuration}ms`,
  "--sst-rec-size": `${s.recLedSize}px`,
  "--sst-rec-on": s.recLedOnColor,
  "--sst-rec-off": s.recLedOffColor,
  "--sst-rec-glow": s.recLedGlowColor,
  "--sst-rec-glow-size": `${s.recLedGlowSize}px`,
  "--sst-rec-glow-effect": `0 0 ${s.recLedGlowSize}px ${s.recLedGlowColor}`,
  "--sst-rec-pulse": `${s.recPulseDuration}ms`,
  "--sst-rec-font": s.recFontFamily,
  "--sst-rec-font-size": `${s.recFontSize}px`,
  "--sst-rec-weight": String(s.recFontWeight),
  "--sst-rec-spacing": `${s.recLetterSpacing}px`,
  "--sst-rec-text": s.recTextColor,
  "--sst-rec-gap": `${s.recGap}px`,
  "--sst-widget-gap": `${s.recWidgetGap}px`,
  "--sst-bg": s.background,
  "--sst-padding": `${s.padding}px`,
  "--sst-scale": "1",
  "--sst-digit-width": `${s.segmentLength + s.segmentGap + s.segmentThickness}px`,
};
AnalogClock.#instances.set(this.id, {
  ...vars,
  "--sst-align": s.align,
});
```

Individual updates go through `setInstanceVariable(name, value)`, defined at
1403–1408:

```js
setInstanceVariable(name, value) {
  const variables = AnalogClock.#instances.get(this.id) ?? {};
  variables[name] = value;
  AnalogClock.#instances.set(this.id, variables);
  AnalogClock.refreshInstanceStyles();
}
```

Called at lines 808–809, 1288–1292, 1364, 1397:

```js
this.setInstanceVariable("--sst-matrix-physical-cols", String(columns));
this.setInstanceVariable("--sst-matrix-physical-rows", String(rows));
```

```js
this.setInstanceVariable("--sst-scale", "1");
```

```js
this.setInstanceVariable("--sst-scale", String(Math.max(0, scale)));
```

---

## 2. `el.style.setProperty` for regular (non-custom) properties

Same API, used with ordinary CSS property names — typically inside a loop so
the property name can be a variable.

studio/web/live-target.js, lines 171–177 (numbered match boxes) and 205–211
(inspect highlight):

```js
for (const [property, value] of Object.entries({
  left: offsetX + (match.rect.x / viewport.width) * page.width,
  top: offsetY + (match.rect.y / viewport.height) * page.height,
  width: (match.rect.width / viewport.width) * page.width,
  height: (match.rect.height / viewport.height) * page.height,
}))
  box.style.setProperty(property, `${value}px`);
```

```js
for (const [property, value] of Object.entries({
  left: offsetX + (element.rect.x / viewport.width) * page.width,
  top: offsetY + (element.rect.y / viewport.height) * page.height,
  width: (element.rect.width / viewport.width) * page.width,
  height: (element.rect.height / viewport.height) * page.height,
}))
  highlight.style.setProperty(property, `${value}px`);
```

widget_clock.js — `column-gap` via `setProperty` (line 686, shown in §1) and
logical-size props on matrix dots, lines 1036–1041:

```js
dot.style.setProperty("inline-size", `${markerSize}px`);
dot.style.setProperty("min-inline-size", `${markerSize}px`);
dot.style.setProperty("max-inline-size", `${markerSize}px`);
dot.style.setProperty("block-size", `${markerSize}px`);
dot.style.setProperty("min-block-size", `${markerSize}px`);
dot.style.setProperty("max-block-size", `${markerSize}px`);
```

---

## 3. Direct property assignment (`el.style.x = v`)

The dominant pattern for drag/position/layout updates — one camelCase property
at a time.

### studio/web/editor.js

`flowNode` while dragging on the graph, lines 1109–1110:

```js
flowNode.style.left = `${Math.max(8, startLeft + dx)}px`;
flowNode.style.top = `${Math.max(8, startTop + dy)}px`;
```

Context `menu` clamped to viewport, lines 1587–1588:

```js
menu.style.top = `${Math.min(box.bottom + 2, window.innerHeight - menu.offsetHeight - 4)}px`;
menu.style.left = `${Math.max(4, Math.min(box.right - menu.offsetWidth, window.innerWidth - menu.offsetWidth - 4))}px`;
```

Drag-preview transforms, lines 2012 and 2159–2160 (cleared at 2040, 2180 — see §9):

```js
row.style.transform = `translateY(${dy}px)`;
```

```js
item.style.transform = `translateX(${shift}px)`;
line.style.left = `${(target / this.timelineTick) * this.timelineScale}rem`;
```

Clip-group `band` on the timeline, lines 2853–2867:

```js
band.style.left = position(group.start_ms);
// …
band.style.width = position(end - group.start_ms);
// …
band.style.width = `${Math.max(Number.parseFloat(band.style.width), left + 5.75)}rem`;
```

`clip` left and `clips` minHeight, lines 2880–2887:

```js
clip.style.left = `${left}rem`;
// …
clips.style.minHeight = `calc(${Math.max(1, rowEnds.length)} * var(--dynamic-lane-h) + 0.5rem)`;
```

Timeline `cursor`, lines 2954–2961:

```js
cursor.style.left = `${left}px`;
cursor.style.height = `${Math.max(timeline.clientHeight, lastTrack instanceof HTMLElement ? lastTrack.offsetTop + lastTrack.offsetHeight : 0)}px`;
cursor.style.visibility =
  left - timeline.scrollLeft < labelRight ||
  left - timeline.scrollLeft > timeline.clientWidth
    ? "hidden"
    : "visible";
```

### studio/web/dock-grid.js

Floating `panel` geometry (and docked grid placement), lines 272–292:

```js
panel.style.removeProperty("grid-column");
panel.style.removeProperty("grid-row");
panel.style.left = `${floating.x}px`;
panel.style.top = `${floating.y}px`;
panel.style.width = `${floating.w}px`;
// …
panel.style.height = `${collapsed ? bar : floating.h}px`;
// else branch:
for (const property of ["left", "top", "width", "height"])
  panel.style.removeProperty(property);
panel.style.gridColumn =
  cell && !compact ? `${cell.c + 1} / span ${cell.cs}` : "";
panel.style.gridRow =
  cell && !compact ? `${cell.r + 1} / span ${cell.rs}` : "";
```

Grid track templates on `root`, lines 327–328:

```js
this.root.style.gridTemplateColumns = template("c");
this.root.style.gridTemplateRows = template("r");
```

Float-to-front `zIndex` counter, lines 651 and 806:

```js
panel.style.zIndex = String((this.floatLayer += 1));
```

Panel dragging and the drag ghost, lines 964–967:

```js
panel.style.left = `${Math.min(window.innerWidth - 80, Math.max(-origin.width + 80, origin.left + dx))}px`;
panel.style.top = `${Math.min(window.innerHeight - 40, Math.max(0, origin.top + dy))}px`;
// else if (ghost)
ghost.style.transform = `translate(${event.clientX + 14}px, ${event.clientY + 14}px)`;
```

Escape restores origin, lines 979–980:

```js
panel.style.left = `${origin.left}px`;
panel.style.top = `${origin.top}px`;
```

Drop-target `overlay`, lines 1117–1120:

```js
overlay.style.left = `${target.area.left - root.left}px`;
overlay.style.top = `${target.area.top - root.top}px`;
overlay.style.width = `${target.area.width}px`;
overlay.style.height = `${target.area.height}px`;
```

### studio/web/graph-surface.js

Graph `node` position, lines 127–128:

```js
node.style.left = `${Math.max(8, position.x)}px`;
node.style.top = `${Math.max(8, position.y)}px`;
```

`canvas` backing-store size, lines 200–201:

```js
canvas.style.width = `${width}px`;
canvas.style.height = `${height}px`;
```

### studio/web/project-bar.js

Project `menu` anchored to its button, lines 207–208:

```js
menu.style.top = `${box.bottom + 4}px`;
menu.style.right = `${Math.max(8, window.innerWidth - box.right)}px`;
```

### studio/web/condition-field.js

Highlight `paint` layer aligned to the input, lines 122–123:

```js
paint.style.lineHeight = `${input.getBoundingClientRect().height}px`;
paint.style.paddingLeft = `${Number.parseFloat(style.paddingLeft) + Number.parseFloat(style.borderLeftWidth)}px`;
```

Autocomplete `menu`, lines 217–220:

```js
menu.style.left = `${left}px`;
// …
menu.style.top = below ? `${at.bottom - box.top + 2}px` : `${at.top - box.top - menu.offsetHeight - 2}px`;
```

### exactus/packages/widgets/widget_clock/widget_clock.js

Matrix dot on/off paint, lines 1042–1059:

```js
dot.style.background = String(
  marker.matrixColor ?? marker.color ?? this.#settings.matrixOnColor,
);
dot.style.boxShadow = `0 0 ${Number(
  marker.matrixGlowSize ?? marker.glowSize ?? 0,
)}px ${String(marker.matrixGlowColor ?? marker.glowColor ?? marker.matrixColor ?? marker.color ?? this.#settings.matrixOnColor)}`;
```

Digit `svg` logical size, lines 1336–1337:

```js
svg.style.inlineSize = `${item.digitWidth ?? digitWidth}px`;
svg.style.blockSize = `${item.digitHeight ?? 192}px`;
```

### exactus/packages/widgets/widget_clock/examples/code.js

Container clamping, lines 68–69:

```js
target.style.inlineSize = `${Math.min(maxWidth, Math.max(Math.min(parseFloat(style.minWidth) || 0, maxWidth), width))}px`;
target.style.blockSize = `${Math.min(maxHeight, Math.max(Math.min(parseFloat(style.minHeight) || 0, maxHeight), height))}px`;
```

### exactus/packages/extended_selector/extended-selector.js

Color-validity probe — the browser drops invalid values, line 1006:

```js
const probe = document.createElement("span");
probe.style.color = value.trim();
if (!probe.style.color) return null;
document.body.append(probe);
const resolved = getComputedStyle(probe).color;
probe.remove();
```

---

## 4. `Object.assign(el.style, {…})` — multi-property batch

editor.js — marquee `band`, lines 1812–1817:

```js
Object.assign(band.style, {
  left: `${x}px`,
  top: `${y}px`,
  width: `${width}px`,
  height: `${height}px`,
});
```

extended-selector-editor.js — `popup`, lines 580–583:

```js
Object.assign(this.popup.style, {
  left: `${Math.min(rect.left, innerWidth - 320)}px`,
  top: `${Math.min(rect.bottom + 6, innerHeight - 220)}px`,
});
```

---

## 5. Inline `style="…"` in generated markup

### HTML template strings → `innerHTML` (editor.js)

Timeline marker, line 2807:

```js
`<span class="timeline-marker" style="left:${position(this.timelineMarker)}"><small>${EditorApp.timecode(this.timelineMarker)}</small></span>`;
```

Ruler tick, line 2811:

```js
`<span style="left:${index * scale}rem">${EditorApp.tickLabel(index * interval)}</span>`,
```

Clip button — `left` **and** `--dynamic-clip-top` defined inline, line 2830:

```js
`<button style="left:${left}rem;--dynamic-clip-top:calc(${row} * var(--dynamic-lane-h) + 0.25rem)" data-step="${EditorApp.escape(event.id)}" class="clip ${EditorApp.escape(layer)}" title="…">…</button>`;
```

`.clips` wrapper — `min-height` *consuming* `var(--dynamic-lane-h)` inline, line 2833:

```js
`<div class="track"><div class="track-label">…</div><div class="clips" style="min-height:calc(${Math.max(1, rowEnds.length)} * var(--dynamic-lane-h))">${clips}${playhead}</div></div>`;
```

### `h()` helper attribute → `setAttribute` (project-dialogs.js:42–52)

`h()` maps every attribute key other than `text`/`class` to
`node.setAttribute(key, value)`, so `style: "…"` lands as a `style` attribute:

```js
export const h = (tag, attributes = {}, children = []) => {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (key === "text") node.textContent = String(value);
    else if (key === "class") node.className = String(value);
    else if (value === true) node.setAttribute(key, "");
    else if (value !== false) node.setAttribute(key, String(value));
  }
  node.append(...children);
  return node;
};
```

Used by welcome.js (snippets in §1): `--dynamic-at` at line 44; `--dynamic-from`, `--dynamic-span`,
`--dynamic-played-at` at line 53.

---

## 6. Constructable stylesheets — `new CSSStyleSheet` + `adoptedStyleSheets`

Only in `exactus/packages/widgets/widget_clock/widget_clock.js`. Styles are never inline; two
shared sheets are installed on each document once (`installStyles`), so they
survive `innerHTML` rebuilds of the clock DOM.

Static component sheet — lines 6–12 (the CSS string is ~5 KB; first rule shown):

```js
static #sheet = (() => {
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(
    '.sst-root {\n  position: relative;\n  inline-size: 100%;\n  …var(--sst-*) consumers…'
  );
  return sheet;
})();
```

Instance sheet — line 119:

```js
static #instanceSheet = new CSSStyleSheet();
```

Installation onto the document — lines 396–404:

```js
static installStyles = (documentRef) => {
  if (AnalogClock.#installedDocuments.has(documentRef)) return;
  documentRef.adoptedStyleSheets = [
    ...documentRef.adoptedStyleSheets,
    AnalogClock.#sheet,
    AnalogClock.#instanceSheet,
  ];
  AnalogClock.#installedDocuments.add(documentRef);
};
```

Per-instance rule regeneration — lines 405–416:

```js
static refreshInstanceStyles = () => {
  AnalogClock.#instanceSheet.replaceSync(
    [...AnalogClock.#instances.entries()]
      .map(([id, variables]) => {
        const body = Object.entries(variables)
          .map(([name, value]) => `${name}:${value}`)
          .join(";");
        return `[data-seven-segment="${id}"]{${body}}`;
      })
      .join("\n"),
  );
};
```

Net effect: per-clock CSS variables (the `vars` object in §1b) are delivered
through a stylesheet rule scoped by `[data-seven-segment]` attribute, not
inline styles.

---

## 7. `el.style.cssText` — wholesale declaration block

js/capture_screen.js — force-expands scroll containers for full-page capture,
line 118:

```js
element.style.cssText +=
  ";height:auto!important;max-height:none!important;overflow-y:visible!important";
```

---

## 8. `setAttribute("style")` / `removeAttribute("style")` — save & restore

js/capture_screen.js — snapshot before §7 mutation, line 111; restore, lines
180–183:

```js
state.styles.push([element, element.getAttribute("style")]);
```

```js
for (const [element, style] of state.styles)
  style === null
    ? element.removeAttribute("style")
    : element.setAttribute("style", style);
```

This is also the mechanism `h()` (§5) uses under the hood.

---

## 9. `el.style.removeProperty(name)` — cleanup

editor.js — drag-preview transform cleanup, lines 2040 and 2180:

```js
row.style.removeProperty("transform");
// …
item.style.removeProperty("transform");
```

editor.js — screenshot-width reset, line 3533 (shown in §1).

dock-grid.js — grid placement cleanup, lines 273–274:

```js
panel.style.removeProperty("grid-column");
panel.style.removeProperty("grid-row");
```

dock-grid.js — floating geometry cleared on re-dock, lines 287–288:

```js
for (const property of ["left", "top", "width", "height"])
  panel.style.removeProperty(property);
```

dock-grid.js — root teardown, lines 311–312:

```js
this.root.style.removeProperty("grid-template-columns");
this.root.style.removeProperty("grid-template-rows");
```

widget_clock.js — per-dot sizing cleanup, lines 1062–1073:

```js
[
  "inline-size",
  "min-inline-size",
  "max-inline-size",
  "block-size",
  "min-block-size",
  "max-block-size",
  "background",
  "box-shadow",
].forEach((property) => {
  dot.style.removeProperty(property);
});
```

---

## Mechanism cheat-sheet vs. where it's used

```
el.style.prop = v          → drag/position updates everywhere (§3)
el.style.setProperty()     → CSS vars (§1) + looped standard props (§2)
Object.assign(el.style, …) → 2 batch updates (§4)
style="…" in markup        → innerHTML templates + h() helper (§5)
adoptedStyleSheets         → widget_clock only (§6)
el.style.cssText           → capture_screen expansion (§7)
setAttribute("style")      → capture_screen restore + h() (§8)
el.style.removeProperty()  → cleanup counterparts (§9)
```
