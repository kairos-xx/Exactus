# `js/`

`node:test` suites for `exactus/record` browser components: the action recorder,
the Flow Studio web UI and its transport. Browser assertions run through the
shared [`exactus/tests/common/browser.mjs`](../../../common/browser.mjs) Playwright harness.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`action-cards.test.mjs`](action-cards.test.mjs) — Action cards: one sentence per action, tokens, pills, branch cards and in-place edits.
- [`blank.html`](blank.html) — Provide blank html content.
- [`condition-language.test.mjs`](condition-language.test.mjs) — The condition language's tokens, type checks and next-step suggestions.
- [`condition-pills.test.mjs`](condition-pills.test.mjs) — Condition pills: each node kind draws, opens its menu and edits the text.
- [`debug-cursor.test.mjs`](debug-cursor.test.mjs) — Log the timeline and playhead geometry under a phase label.
- [`dock-model.test.mjs`](dock-model.test.mjs) — Exercise the pure dock grid model: alignment, docking, gaps and collapse.
- [`graph-surface.test.mjs`](graph-surface.test.mjs) — Graph layout stays deterministic and terminates for cyclic workspaces.
- [`icons.test.mjs`](icons.test.mjs) — The icon set: generated from icons/*.svg and drawn as real inline SVG.
- [`module-page.mjs`](module-page.mjs) — Run browser assertions against Studio modules on a blank page, with no editor.
- [`project-actions.test.mjs`](project-actions.test.mjs) — Project actions and the dialogs they open: save, leave, create, import and the gallery.
- [`project-bar.test.mjs`](project-bar.test.mjs) — The top bar: control routing, menus, keyboard, fit tiers and the saved pill.
- [`project-gallery.test.mjs`](project-gallery.test.mjs) — The project gallery: search, advanced filters, selection, details and deletion.
- [`project-harness.js`](project-harness.js) — A fake editor host and sample library for the project modules, run in a page.
- [`project-model.test.mjs`](project-model.test.mjs) — Project names, tags, filtering and dates.
- [`project-section.test.mjs`](project-section.test.mjs) — The Project section of Settings: draft, validation, apply, revert and gallery.
- [`recorder.test.mjs`](recorder.test.mjs) — Verify recorded browser interactions and semantic target metadata.
- [`run-cause.test.mjs`](run-cause.test.mjs) — Last-run causes: worst status, summaries, fact rows and the rendered list.
- [`selector-live-tools.test.mjs`](selector-live-tools.test.mjs) — The shared Pick/Highlight/strategy row every selector editing surface mounts.
- [`selector-scripts.test.mjs`](selector-scripts.test.mjs) — Exercise the selector resolver and sandbox page scripts directly.
- [`selectors-panel.test.mjs`](selectors-panel.test.mjs) — The selectors list, test result, tested-on pages and the selector inspector.
- [`settings.test.mjs`](settings.test.mjs) — Exercise the pure rules behind the Settings page: commands, ports, ratios, IDs and validation.
- [`studio-mock.mjs`](studio-mock.mjs) — Deterministic Flow Studio service for browser tests: one workspace, two flows and a command log.
- [`studio.test.mjs`](studio.test.mjs) — Exercise Flow Studio editing, recording, Actions recipes and keyboard dialogs.
- [`transport.test.mjs`](transport.test.mjs) — Verify authenticated Studio transport and interrupted command responses.
- [`variables.test.mjs`](variables.test.mjs) — Variables: picking, pills, the inspector, Ask Each Time and action forms.
- [`welcome.test.mjs`](welcome.test.mjs) — The first-run screen: when it covers the editor and what its buttons do.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->

