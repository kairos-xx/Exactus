# Studio editor

The framework-free editor uses `index.html`, `editor.css`, `editor.js`,
`transport.js` and the dock modules. `editor.css` imports `styles/style.css`,
which loads the token hierarchy and each component in cascade order. HTTP
commands and Server-Sent Events connect it to the service. Tabler outline icons and shared CSS tokens keep the dark editor
consistent. The application under test runs in a separate owned Chromium that
Studio drives with Playwright. It has no window of its own (headless is the
default, `--headed` opts out): the Browser panel streams its pixels and sends
clicks and keys back, so it behaves like an embedded frame without an iframe's
limits (framing restrictions, no emulation, a different engine).

## Workspaces

Five tabs, each one phase of the job. Older view names still resolve to them
(`EditorApp.VIEW_ALIASES`).

| Tab | What it holds |
| --- | --- |
| Flow editor | Flows, Steps, the always-visible Browser, Properties and the Timeline. Record, Pause, Stop, Crawl, Pick element and Maximize live in the Browser panel. |
| Graph | The same Flows and Properties panels around the flow network. |
| Play | Run flow (this flow only), Run with connections and Stop; the run's actions, evidence and console. |
| Compare | Screenshot comparison and baseline review. |
| Settings | Target (an address and port, or a service Studio starts), browser profiles, and recovery. |

There is no global command bar: each command sits where it is used. Crawl opens
a page of discovery options inside the Flow editor tab.

Every concept is one component, not lookalikes per tab. The Flows panel
(`flow-list.js`) and Properties panel (flow settings, or the connection editor
when a Graph connection is selected) are single elements the dock moves between
layouts. Flows also shares its *state* between Flow editor and Graph: its edge,
size, collapse and detach state follow wherever you change it
(`describeShared` / `adoptShared` in `dock-model.js`). A flow is created with
the “+” in the Flows panel and removed from a row's “…” menu or from Flow
settings, in both tabs.

## Settings

`settings.js` renders the page from the backend's `profile_schema`, so a profile
can only be edited in ways the test browser can honour: lengths in px,
resolution in dppx, the aspect ratio as two numbers linked to width and height,
and each supported media feature as a choice. Features Chromium ignores are
listed, never offered. The Target section either takes an address and a port
(empty means 80 or 443) or a service command, working folder, page and port
(detected automatically unless set). A project with no target is offered the
bundled demo server as a suggestion; nothing runs until **Start service**, and
the exact command is shown next to the button.

## Docking

Every panel is a cell range of one shared CSS grid, so rows and columns line up
across the whole workspace by construction.

- `dock-model.js` is the pure layout model: tracks, panel cells, docking beside
  a panel or along a window edge, swapping, floating, collapsing and resizing.
  It has no DOM access and is covered by `dock-model.test.mjs`.
- `dock-grid.js` renders that model, draws the resize handles on the shared
  track lines, and handles dragging, the panel menu and persistence under the
  `studio.dock-grid.v1` key.
- A panel collapses along the axis where it has no sibling: sideways into a
  vertical bar, or vertically into a horizontal bar. Only the chevron and the
  panel icon remain, and restoring returns every track to its earlier size.
- Keyboard: Alt+Shift+arrow docks the focused panel along that window edge,
  Alt+Shift+C collapses or expands it and Alt+Shift+F floats or re-docks it;
  arrow keys on a focused separator resize it (Shift for larger steps). Every
  change is announced in the status line, and `prefers-reduced-motion` removes
  panel transitions.
- Below 600px the panels become tabs (Flows, Steps, Browser, Properties, Runs)
  and the dock tools are hidden.
- Reset layout restores the shipped arrangement and clears `studio.dock-grid.v1`.
- Panel content answers to the width of its panel through container queries in
  `styles/components/responsive-layout/style.css`, not to the window.

## Subdirectories

- `icons/` — Subdirectory.
- `styles/` — Ordered Studio layout and component styles.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`STYLE-SETTING.md`](STYLE-SETTING.md) — Audit of every mechanism this codebase uses to put styles on DOM elements from JS, with the code at each site. Scope: `studio/web/*.js` plus the in-repo `exactus/packages/` widgets. Generated bundles under `exactus/bundle/**` and result artifacts under `EXACTUS_RESULTS/**` are excluded.
- [`ab-new.html`](ab-new.html) — Provide ab new html content.
- [`action-card.js`](action-card.js) — Shortcuts-style action cards: an icon tile and one sentence with tokens.
- [`action-library.js`](action-library.js) — Action catalog and schema-driven insertion form for Flow Studio.
- [`ask-inputs.js`](ask-inputs.js) — Per-run answers for "Ask Each Time" variables.
- [`compare-pairs.js`](compare-pairs.js) — Pair screenshots of the same step across runs, so Compare shows a baseline and a latest capture.
- [`condition-field.js`](condition-field.js) — A text field for conditions that colours, checks and completes them.
- [`condition-language.js`](condition-language.js) — The token system of the condition language.
- [`condition-pills.js`](condition-pills.js) — Pills for the condition language.
- [`condition-types.d.ts`](condition-types.d.ts) — Provide condition types.d ts content.
- [`dock-grid.js`](dock-grid.js) — Dock grid view: renders the layout from `dock-model.js` and handles the interactions around it (drag to dock, resize, collapse, float). All panels are children of one CSS grid. Rows and columns are shared tracks, so splits line up across the whole workspace by construction.
- [`dock-model.js`](dock-model.js) — Pure layout model for the Studio dock grid. Every panel occupies a rectangle of cells in one shared grid. Rows and columns are tracks common to all panels, so panels in different rows can never end up with misaligned columns. The model has no DOM access: the view in `dock-grid.js` renders it and feeds back measured pixel sizes.
- [`editor.css`](editor.css) — Provide editor css content.
- [`editor.js`](editor.js) — Provide editor js content.
- [`flow-inputs.js`](flow-inputs.js) — The inputs a flow takes, edited as a list of rows in the flow settings.
- [`flow-list.js`](flow-list.js) — The one Flows list: every place that shows saved flows renders it here.
- [`graph-surface.js`](graph-surface.js) — Explicit DOM rendering for the flow graph. Positions never change execution order.
- [`icon-set.js`](icon-set.js) — The Studio's icons, as the shapes inside a 24 by 24 `<svg>`.
- [`icons.js`](icons.js) — Icons as real `<svg>` elements.
- [`index.html`](index.html) — Provide index html content.
- [`javascript-action-widget.js`](javascript-action-widget.js) — JavaScript authoring workbench: a runnable snippet editor plus a runtime-value catalog.
- [`live-target.js`](live-target.js) — Present the real Playwright page, forwarding input in target CSS pixels.
- [`project-actions.js`](project-actions.js) — What a person can do with projects: create, open, save, import, export.
- [`project-bar.js`](project-bar.js) — The top bar's project controls: name, saved state, actions and menus.
- [`project-dialogs.js`](project-dialogs.js) — The project dialogs: new project, ask for a name, unsaved changes, and the gallery.
- [`project-model.js`](project-model.js) — Pure rules for projects: names, tags, filtering, sorting and dates.
- [`project-section.js`](project-section.js) — The Project section of the Settings tab: name, details and the gallery.
- [`project-types.d.ts`](project-types.d.ts) — Provide project types.d ts content.
- [`request-action-widget.js`](request-action-widget.js) — Request-action editor shared by REST and WebSocket flow actions.
- [`run-cause.js`](run-cause.js) — How a run explains a failed or tolerated action.
- [`run-types.d.ts`](run-types.d.ts) — Provide run types.d ts content.
- [`selector-expression-field.js`](selector-expression-field.js) — Studio's binding to the expression widget: it maps Studio's data and transport onto the widget's options and contains no widget UI.
- [`selector-live-tools.js`](selector-live-tools.js) — Page-aware controls shared by every ExtendedSelector editing surface.
- [`selector-reference-field.js`](selector-reference-field.js) — Reusable saved-selector chooser with an inline-expression escape hatch.
- [`selectors-panel.js`](selectors-panel.js) — The Selectors list and the selector inspector.
- [`settings.js`](settings.js) — Settings: browser profiles and project recovery, rendered from the backend's field catalog.
- [`styles.zip`](styles.zip) — Provide styles zip content.
- [`token-editor.js`](token-editor.js) — The small editor that opens when a card token is clicked.
- [`transport.js`](transport.js) — Connect one editor tab to the authenticated loopback service.
- [`variable-inspector.js`](variable-inspector.js) — The panel that explains one variable pill: where it comes from and how it is read.
- [`variable-mention-field.js`](variable-mention-field.js) — Variable-aware form controls with mention suggestions and token pills.
- [`welcome.js`](welcome.js) — The first-run screen: what a new person sees before any project exists.

### Subdirectories

- [`icons/`](icons/README.md) — Owned SVGs from \[Tabler Icons\](https://tabler.io/icons), outline variant. Better Design resolved the names and supplied the initial files. Additional verified names came from the same official Tabler repository after Iconify rate-limited downloads. The original license is included in `LICENSE`.
- [`styles/`](styles/README.md) — `style.css` is the only stylesheet entry point; `../editor.css` imports it. It loads the token pipeline (`tokens/`) and then every component (`components/<name>/`) in canonical cascade order.

<!-- exactus:inventory:end -->



## Recording parent tasks

Record immediately persists a `FlowRecording` under the active flow. Captured
actions refer to its `recording_group_id`; the parent is not an executable
browser action. Steps renders a collapsible parent containing its children;
Timeline renders a recording lane with child clips inside its time band.
Children remain normal editable actions, with sequence and automatically
captured unique CSS selectors.

The worker pins the recording to its original flow, starts a fresh clock for
each group and uses browser event timestamps rather than service startup time.
Pause flushes pending text edits; resume continues the same group without the
paused interval or a second initial navigation. Stop then Record creates another
group. JSON persistence accepts older workspaces without recording parents.
Replay honors captured cadence with cancellation checks every 50 ms. Slow
browser actions may exceed the recorded cadence; playback never skips them.
Group rename, bulk retiming, reparenting and group-level deletion are not yet
implemented; tracked in the canonical TODO.

## Graph workspace

Flow editor composes actions within a selected flow using its steps and
timeline. Graph connects whole flows, with no action previews, action timeline
or connections table. Both tabs use the same Flows and Properties components and
workspace data. Selecting a flow is global; adding one creates its list entry and graph
node from the same saved snapshot. Node positions do not determine execution order.

- Drag node titles to reposition flows; drag empty canvas to pan.
- Drag an output port to an input, or use Enter on both ports. Escape
  cancels a pending connection.
- Fit includes all node positions. Zoom is available through the graph's “…” menu.
- Select an arrow with the mouse or Enter to edit its condition, execution
  rule, priority and traversal limit in the dockable connection inspector.
  Apply saves atomically through `edge.update`; rejected saves retain the draft.
- The connection inspector removes the exact saved transition, including
  its condition, priority and traversal limit.
- On compact screens, Flows, Graph and Properties use the panel switcher.

Graph and the Flow editor share docking controls and the Flows panel's state;
every other panel keeps its own arrangement per tab. Graph saves
`studio.dock-grid.v1.graph`; the Flow editor saves `studio.dock-grid.v1`. A
saved layout from before Flows became shared is migrated to the full-height
column when it loads.

A minimap, fit-selection and
project-scoped node positions remain tracked under S31 in `exactus/docs/todo/TODO.md`.
