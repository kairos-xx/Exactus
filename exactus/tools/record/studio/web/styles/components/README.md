# Components

Each component directory owns exactly `semantic.css`, `style.css`, and `README.md`. Load semantic before style for a component. `../style.css` preserves interleaved cascade phases by importing separately named semantic components at their original positions.

`../style.css` lists every file in canonical load order, after `tokens/primary.css`, `tokens/base.css` and `tokens/catalog.css`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

No direct files besides this README.

### Subdirectories

- [`action-cards/`](action-cards/README.md) — The Shortcuts-style card of an action: a coloured icon tile, one sentence with editable tokens and variable pills, a code block, If / End If branch cards and the small editor a token opens.
- [`action-workbench/`](action-workbench/README.md) — The shared action-authoring shell and the JavaScript Code, Values, Outputs and Latest result subviews. REST and WebSocket retain their transport-specific editors inside this shell.
- [`actions/`](actions/README.md) — Action controls and status treatments.
- [`chrome/`](chrome/README.md) — Identity row, workspace sections, transport and status bar.
- [`command-palette/`](command-palette/README.md) — Command palette and workspace surface shell.
- [`composition/`](composition/README.md) — Flow composition details.
- [`condition-field/`](condition-field/README.md) — The condition field: token colours, pills, suggestions and issues.
- [`connections/`](connections/README.md) — Connection and target controls.
- [`controls/`](controls/README.md) — Profile, comparison, and assertion controls. Control specimens and dock-zone foundations.
- [`data-tables/`](data-tables/README.md) — Tables and tabular panels.
- [`density/`](density/README.md) — Aliases and rules of the density component.
- [`dialogs/`](dialogs/README.md) — Dialog and preview surfaces.
- [`dock-chrome/`](dock-chrome/README.md) — No subdirectories.
- [`dock-grid/`](dock-grid/README.md) — No subdirectories.
- [`dock-groups/`](dock-groups/README.md) — No subdirectories.
- [`docks/`](docks/README.md) — Dock sizing controls.
- [`edit-workspace/`](edit-workspace/README.md) — No subdirectories.
- [`flow/`](flow/README.md) — Flow graph nodes and connectors.
- [`flow-bar/`](flow-bar/README.md) — No subdirectories.
- [`flow-inputs/`](flow-inputs/README.md) — The inputs a flow takes: one bordered row per input (name, type, required, default) in the flow settings.
- [`forms/`](forms/README.md) — Forms, fields, and action editors.
- [`foundation/`](foundation/README.md) — Element-level control defaults and icon masks (layered).
- [`graph-workspace/`](graph-workspace/README.md) — No subdirectories.
- [`icon-buttons/`](icon-buttons/README.md) — Aliases and rules of the icon buttons component.
- [`inspector/`](inspector/README.md) — Inspector content and code displays.
- [`live-target/`](live-target/README.md) — Aliases and rules of the live target component.
- [`mock-fidelity/`](mock-fidelity/README.md) — Aliases and rules of the mock fidelity component.
- [`panel-chrome/`](panel-chrome/README.md) — No subdirectories.
- [`panel-docking/`](panel-docking/README.md) — No subdirectories.
- [`panel-modes/`](panel-modes/README.md) — No subdirectories.
- [`panels/`](panels/README.md) — Workspace and panel foundations.
- [`project-bar/`](project-bar/README.md) — The top bar's project controls and their three responsive tiers.
- [`project-dialogs/`](project-dialogs/README.md) — New project, name, unsaved-changes and gallery dialogs.
- [`request-actions/`](request-actions/README.md) — The compact REST and WebSocket request composer used by Studio action forms. It adapts REST action's request line and tabs to Studio's action-card shell and adds variable mentions, response checks, and typed response-to-variable maps.
- [`responsive/`](responsive/README.md) — Base responsive adaptations.
- [`responsive-docks/`](responsive-docks/README.md) — No subdirectories.
- [`responsive-layout/`](responsive-layout/README.md) — No subdirectories.
- [`run-status/`](run-status/README.md) — The latest run on a step: row badge and the "Last run" section.
- [`screenshots/`](screenshots/README.md) — Screenshot and action-library surfaces.
- [`section-row/`](section-row/README.md) — Aliases and rules of the section row component.
- [`selectors/`](selectors/README.md) — Selectors list, selector inspector and the numbered live match boxes.
- [`settings/`](settings/README.md) — Aliases and rules of the settings component.
- [`shell/`](shell/README.md) — Application shell and global controls.
- [`sidebars/`](sidebars/README.md) — Test browser, disclosure rows and the Properties form.
- [`steps/`](steps/README.md) — Step rows with drag grip and drop line, tabs and empty state.
- [`theme/`](theme/README.md) — Shared Studio design tokens.
- [`timeline/`](timeline/README.md) — Timeline tracks and clips.
- [`timeline-clock/`](timeline-clock/README.md) — No subdirectories.
- [`timeline-editor/`](timeline-editor/README.md) — No subdirectories.
- [`tonal-theme/`](tonal-theme/README.md) — No subdirectories.
- [`welcome/`](welcome/README.md) — Aliases and rules of the welcome component.
- [`workspace/`](workspace/README.md) — Workspace view layouts.
- [`workspace-surfaces/`](workspace-surfaces/README.md) — No subdirectories.

<!-- exactus:inventory:end -->
