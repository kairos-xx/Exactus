import { iconMarkup } from "./icons.js";
/** Dock grid view: renders the layout from `dock-model.js` and handles the interactions around it (drag to dock, resize, collapse, float).  All panels are children of one CSS grid. Rows and columns are shared tracks, so splits line up across the whole workspace by construction.
 */
import * as Model from "./dock-model.js";
const STORAGE_KEY = "studio.dock-grid.v1";
const MOBILE_QUERY = "(max-width: 600px)";
/** Distance from the workspace edge that docks a panel along the whole edge.
 */
const OUTER_BAND = 28;
/** Share of a panel, measured from its edge, that docks beside it.
 */
const EDGE_SHARE = 0.28;
/** Pixel travel before a press on a header becomes a drag.
 */
const DRAG_THRESHOLD = 5;
const DEFAULT_MINIMUM = Object.freeze({
  width: 160,
  height: 96,
});
/** @typedef {import("./dock-model.js").Layout} Layout */
/** @typedef {import("./dock-model.js").Edge} Edge */
/** @typedef {{width:number,height:number}} Minimum */
/** @typedef {object} DockTarget @property {"edge"|"outer"|"swap"} kind What a drop would do. @property {Edge} [edge] Side of the target or of the window. @property {string} [target] Panel being docked against. @property {boolean} [blocked] The drop would leave a panel too small. @property {DOMRect} area Highlighted region in viewport coordinates.
 */
/** Icon element markup: a real inline SVG.
 */
const icon = (/** @type {string} */ name) => iconMarkup(name);
/** Render and manage the shared dock grid, its floating panels and resize boundaries. */
export class DockGrid {
  /** Edit's layout; Graph owns a separate layout using the same docking engine.
   * @type {Layout}
   */
  editLayout = Model.defaultLayout();
  graphLayout = Model.defaultGraphLayout();
  /** Read the layout that belongs to the active workspace.
   * @returns {Layout} Active workspace's independent layout.
   */
  get layout() {
    return this.mode === "graph" ? this.graphLayout : this.editLayout;
  }
  /** Replace the layout that belongs to the active workspace.
   * @param {Layout} value Layout to store for the active workspace.
   */
  set layout(value) {
    if (this.mode === "graph") this.graphLayout = value;
    else this.editLayout = value;
  }
  /** What the current mode shows, derived from that workspace's layout.
   * @returns {Layout|null}
   */
  get view() {
    return Model.layoutForMode(this.mode, this.layout);
  }
  /** Edit and Graph can both be rearranged without changing each other's layout.
   * @returns {boolean}
   */
  get editable() {
    return ["edit", "graph", "record"].includes(this.mode);
  }
  /** The panel that owns the saved state of a visible panel.
   * @param {string} id
   * @returns {string}
   */
  owner(id) {
    return Model.stateOwner(this.mode, id);
  }
  /** @type {string} */
  mode = "edit";
  /** @type {HTMLElement} */
  root;
  /** @type {Map<string,HTMLElement>} */
  panels = new Map();
  /** @type {Record<string,Minimum>} */
  minimums;
  /** @type {(message:string)=>void} */
  onStatus;
  /** Where a floating panel came from, so docking it back returns it.
   */
  /** @type {Record<string,{target:string,edge:Edge}>} */
  home = {};
  /** A drop ends with a click that must not activate the header.
   */
  suppressClickUntil = 0;
  /** @type {HTMLElement} */
  handles;
  /** @type {{handle:HTMLElement,axis:"c"|"r",line:{index:number,from:number,to:number,before:string[],after:string[]}}[]} */
  handleList = [];
  floatLayer = 60;
  /** function Object() { [native code] }
   * @param {{root:HTMLElement,minimums:Record<string,Minimum>,onStatus:(message:string)=>void}} options
   */
  constructor(options) {
    this.root = options.root;
    this.minimums = options.minimums;
    this.onStatus = options.onStatus;
    for (const node of this.root.querySelectorAll(
      ":scope > .panel[data-panel-id]",
    ))
      if (node instanceof HTMLElement)
        this.panels.set(node.getAttribute("data-panel-id") || "", node);
    this.layout = this.load();
    this.graphLayout = this.load(true);
    // The Flows panel is one component: both workspaces start in agreement,
    // and an older saved layout is moved to the full-height column.
    const shared = Model.describeShared(this.editLayout);
    this.editLayout = Model.adoptShared(this.editLayout, shared);
    if (!Model.sameShared(shared, Model.describeShared(this.graphLayout)))
      this.graphLayout = Model.adoptShared(this.graphLayout, shared);
    this.handles = document.createElement("div");
    this.handles.className = "dock-handles";
    this.root.append(this.handles);
    for (const [id, panel] of this.panels) this.mountPanel(id, panel);
    new ResizeObserver(() => this.placeHandles()).observe(this.root);
    window
      .matchMedia(MOBILE_QUERY)
      .addEventListener("change", () => this.render());
    document.addEventListener("click", event => {
      if (
        !(event.target instanceof Element) ||
        !event.target.closest(".panel-tools")
      )
        DockGrid.closeMenus();
    });
  }
  /** Check whether the compact one-panel workspace is active.
   * @returns {boolean} Whether the compact one-panel layout is active.
   */
  get mobile() {
    return window.matchMedia(MOBILE_QUERY).matches;
  }
  /** Read and validate the saved layout, falling back to the shipped layout.
   * @param {boolean} graph Whether to load the independent Graph layout.
   * @returns {Layout} The saved layout, or the shipped default.
   */
  load(graph = false) {
    try {
      const saved = Model.validate(
        JSON.parse(
          localStorage.getItem(graph ? `${STORAGE_KEY}.graph` : STORAGE_KEY) ||
            "null",
        ),
        new Set(
          [...this.panels.keys()].filter(id =>
            graph
              ? id === "workspace" ||
                id === "composition" ||
                id === "properties" ||
                id.startsWith("graph-")
              : id !== "composition" && !id.startsWith("graph-"),
          ),
        ),
      );
      if (saved) return saved;
    } catch {
      /* Fall through to the default layout. */
    }
    return graph ? Model.defaultGraphLayout() : Model.defaultLayout();
  }
  /** Persist the current dock layout when browser storage is available.
   * @returns {void}
   */
  save() {
    this.shareFlows();
    try {
      localStorage.setItem(
        this.mode === "graph" ? `${STORAGE_KEY}.graph` : STORAGE_KEY,
        JSON.stringify(this.layout),
      );
    } catch {
      /* Storage can be unavailable; the layout then lasts for this tab. */
    }
  }
  /** Make the other workspace show the Flows panel exactly as this one does.
   * @returns {void}
   */
  shareFlows() {
    if (!this.editable) return;
    const mine = Model.describeShared(this.layout);
    const graph = this.mode === "graph";
    const other = graph ? this.editLayout : this.graphLayout;
    if (Model.sameShared(mine, Model.describeShared(other))) return;
    const adopted = Model.adoptShared(other, mine);
    if (graph) this.editLayout = adopted;
    else this.graphLayout = adopted;
    try {
      localStorage.setItem(
        graph ? STORAGE_KEY : `${STORAGE_KEY}.graph`,
        JSON.stringify(adopted),
      );
    } catch {
      /* Storage can be unavailable; the layout then lasts for this tab. */
    }
  }
  /** Return the measured minimum size of a panel.
   * @param {string} id
   * @returns {Minimum}
   */
  minimumOf(id) {
    return this.minimums[id] ?? DEFAULT_MINIMUM;
  }
  /** Return the visible title of a panel, falling back to its id.
   * @param {string} id
   * @returns {string} Visible panel title.
   */
  nameOf(id) {
    const title = this.panels.get(id)?.querySelector(".panel-title-text");
    return title?.textContent?.trim() || id;
  }
  /** Measure the rendered grid tracks in CSS pixels.
   * @returns {{cols:number[],rows:number[]}} Rendered track sizes in pixels.
   */
  metrics() {
    const style = getComputedStyle(this.root);
    /** Parse computed grid track lengths into numeric CSS pixel sizes.
     * @param {string} value
     * @returns {number[]}
     */
    const parse = value =>
      value
        .split(" ")
        .map(item => Number.parseFloat(item))
        .filter(item => Number.isFinite(item));
    return {
      cols: parse(style.gridTemplateColumns),
      rows: parse(style.gridTemplateRows),
    };
  }
  /** Switch the visible set of panels and redraw.
   * @param {string} [mode]
   * @returns {void}
   */
  render(mode = this.mode) {
    this.mode = mode;
    const view = this.view;
    const edit = this.editable;
    const compact = this.mobile;
    this.root.toggleAttribute("data-static", !edit);
    for (const [id, panel] of this.panels) {
      const cell = view?.cells[id];
      const floating = view?.floating[id];
      panel.classList.toggle("is-floating", Boolean(floating) && !compact);
      panel.classList.toggle("is-unplaced", !cell && !floating && !compact);
      panel.classList.toggle("is-docked", Boolean(cell));
      const collapsed = view?.collapsed[id];
      const axis = view ? Model.collapseAxis(view, id) : null;
      const direction = view ? Model.collapseDirection(view, id) : null;
      panel.classList.toggle("is-collapsed", Boolean(collapsed) && !compact);
      if (collapsed && !compact) panel.setAttribute("data-collapse", collapsed);
      else panel.removeAttribute("data-collapse");
      if (direction) panel.setAttribute("data-collapse-dir", direction);
      else panel.removeAttribute("data-collapse-dir");
      /* The chevron points where the panel will go, and back when collapsed. */
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
      panel
        .querySelector(".panel-title")
        ?.setAttribute("title", this.nameOf(id));
      this.syncTools(
        id,
        panel,
        Boolean(collapsed),
        Boolean(view && axis && Model.canCollapse(view, id)),
      );
      if (floating && !compact) {
        panel.style.removeProperty("grid-column");
        panel.style.removeProperty("grid-row");
        panel.style.left = `${floating.x}px`;
        panel.style.top = `${floating.y}px`;
        panel.style.width = `${floating.w}px`;
        // A size container has no content height of its own, so a collapsed
        // window needs its header's height spelled out or it shrinks to a line.
        const header = panel.querySelector(":scope > header");
        const bar =
          header instanceof HTMLElement && header.offsetHeight
            ? header.offsetHeight
            : Model.HEADER_SIZE;
        panel.style.height = `${collapsed ? bar : floating.h}px`;
      } else {
        for (const property of ["left", "top", "width", "height"])
          panel.style.removeProperty(property);
        panel.style.gridColumn =
          cell && !compact ? `${cell.c + 1} / span ${cell.cs}` : "";
        panel.style.gridRow =
          cell && !compact ? `${cell.r + 1} / span ${cell.rs}` : "";
      }
      if (cell)
        panel.setAttribute(
          "data-grid",
          `${cell.c},${cell.r},${cell.cs},${cell.rs}`,
        );
      else panel.removeAttribute("data-grid");
    }
    this.applyTracks(view, compact);
    this.placeHandles();
  }
  /** Apply constrained track sizes and report whether the layout fits.
   * @param {Layout|null} view
   * @param {boolean} compact
   * @returns {void}
   */
  applyTracks(view, compact) {
    if (!view || compact) {
      this.root.style.removeProperty("grid-template-columns");
      this.root.style.removeProperty("grid-template-rows");
      return;
    }
    /** @param {"c"|"r"} axis
     * @returns {string}
     */
    const template = axis =>
      Model.effectiveTracks(view, axis)
        .map((item, index) => {
          if (item.collapsed) return `${Model.HEADER_SIZE}px`;
          if (item.flex)
            return `minmax(${this.trackMinimum(view, axis, index)}px, 1fr)`;
          return `minmax(0, ${Math.round(item.size)}px)`;
        })
        .join(" ");
    this.root.style.gridTemplateColumns = template("c");
    this.root.style.gridTemplateRows = template("r");
  }
  /** Smallest size a track may take: the largest minimum among the panels that live entirely inside it.
   * @param {Layout} view
   * @param {"c"|"r"} axis
   * @param {number} index
   * @returns {number}
   */
  trackMinimum(view, axis, index) {
    let need = 0;
    for (const [id, cell] of Object.entries(view.cells)) {
      const [first, count] =
        axis === "c" ? [cell.c, cell.cs] : [cell.r, cell.rs];
      if (count === 1 && first === index)
        need = Math.max(
          need,
          axis === "c" ? this.minimumOf(id).width : this.minimumOf(id).height,
        );
    }
    return need;
  }
  /** Remember rendered sizes so a restored panel returns to the size it had. A collapsed track keeps its saved size, and so does a neighbour that is only borrowing the flexible role while that panel is collapsed.
   * @returns {void}
   */
  syncSizes() {
    if (!this.editable || this.mobile) return;
    const { cols, rows } = this.metrics();
    for (const [
      axis,
      tracks,
      sizes,
    ] of /** @type {["c"|"r",Model.Track[],number[]][]} */ ([
      ["c", this.layout.cols, cols],
      ["r", this.layout.rows, rows],
    ])) {
      const effective = Model.effectiveTracks(this.layout, axis);
      tracks.forEach((item, index) => {
        const borrowed = effective[index]?.flex !== item.flex;
        if (!effective[index]?.collapsed && !borrowed && sizes[index])
          item.size = sizes[index];
      });
    }
  }
  /** Create one handle per shared track line that separates two panels.
   * @returns {void}
   */
  placeHandles() {
    this.handles.replaceChildren();
    this.handleList = [];
    const view = this.view;
    if (!view || !this.editable || this.mobile || !this.root.offsetParent)
      return;
    for (const axis of /** @type {("c"|"r")[]} */ (["c", "r"]))
      for (const line of Model.boundaries(view, axis)) {
        if (!Model.isResizable(view, axis, line.index)) continue;
        const handle = document.createElement("div");
        handle.className = "dock-handle";
        handle.setAttribute("data-axis", axis);
        handle.setAttribute("role", "separator");
        handle.setAttribute(
          "aria-orientation",
          axis === "c" ? "vertical" : "horizontal",
        );
        handle.tabIndex = 0;
        handle.setAttribute(
          "aria-label",
          `Resize ${this.nameOf(line.before[0] ?? "")} and ${this.nameOf(line.after[0] ?? "")}`,
        );
        this.bindHandle(handle, axis, line.index);
        this.handles.append(handle);
        this.handleList.push({
          handle,
          axis,
          line,
        });
      }
    this.layoutHandles();
  }
  /** Move the existing handles to the current track lines, without recreating them.
   * @returns {void}
   */
  layoutHandles() {
    const view = this.view;
    if (!view || this.handleList.length === 0) return;
    const { cols, rows } = this.metrics();
    const gap = Number.parseFloat(getComputedStyle(this.root).columnGap) || 0;
    /** @param {number[]} sizes
     * @param {number} count
     * @returns {number}
     */
    const offset = (sizes, count) =>
      sizes.slice(0, count).reduce((sum, item) => sum + item, 0) + gap * count;
    for (const { handle, axis, line } of this.handleList) {
      const column = axis === "c";
      const sizes = column ? cols : rows;
      const effective = Model.effectiveTracks(view, axis);
      const before = effective[line.index];
      const after = effective[line.index + 1];
      if (!before || !after) continue;
      const controlled =
        before.collapsed || !after.collapsed && before.flex
          ? line.index + 1
          : line.index;
      const from = offset(column ? rows : cols, line.from);
      handle.setAttribute(
        "aria-valuenow",
        String(Math.round(sizes[controlled] ?? 0)),
      );
      handle.style.setProperty(
        "--dynamic-along",
        `${offset(sizes, line.index + 1) - gap / 2}px`,
      );
      handle.style.setProperty("--dynamic-from", `${from}px`);
      handle.style.setProperty(
        "--dynamic-length",
        `${offset(column ? rows : cols, line.to) - from - gap}px`,
      );
    }
  }
  /** Bind pointer and keyboard resizing to a shared grid boundary.
   * @param {HTMLElement} handle
   * @param {"c"|"r"} axis
   * @param {number} index
   * @returns {void}
   */
  bindHandle(handle, axis, index) {
    /** @param {number} delta
     * @param {Layout} origin
     * @param {{cols:number[],rows:number[]}} sizes
     */
    const apply = (delta, origin, sizes) => {
      this.layout = Model.resizeBoundary(
        origin,
        axis,
        index,
        delta,
        id => this.minimumOf(id),
        sizes,
      );
      const view = this.view;
      this.applyTracks(view, false);
      this.layoutHandles();
    };
    handle.addEventListener("pointerdown", down => {
      if (down.button !== 0) return;
      down.preventDefault();
      const origin = Model.clone(this.layout);
      const sizes = this.metrics();
      const startAt = axis === "c" ? down.clientX : down.clientY;
      handle.setPointerCapture(down.pointerId);
      handle.classList.add("is-active");
      document.body.classList.add(
        axis === "c" ? "dock-resizing-x" : "dock-resizing-y",
      );
      const move = (/** @type {PointerEvent} */ event) =>
        apply(
          (axis === "c" ? event.clientX : event.clientY) - startAt,
          origin,
          sizes,
        );
      const finish = () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", finish);
        handle.removeEventListener("pointercancel", finish);
        handle.classList.remove("is-active");
        document.body.classList.remove("dock-resizing-x", "dock-resizing-y");
        this.syncSizes();
        this.save();
        this.placeHandles();
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", finish);
      handle.addEventListener("pointercancel", finish);
    });
    handle.addEventListener("keydown", event => {
      const back = axis === "c" ? "ArrowLeft" : "ArrowUp";
      const forward = axis === "c" ? "ArrowRight" : "ArrowDown";
      if (event.key !== back && event.key !== forward) return;
      event.preventDefault();
      const step = (event.shiftKey ? 64 : 16) * (event.key === back ? -1 : 1);
      apply(step, Model.clone(this.layout), this.metrics());
      this.syncSizes();
      this.save();
      this.placeHandles();
      const grew = event.key === forward;
      this.onStatus(
        axis === "c"
          ? `Column ${grew ? "widened" : "narrowed"}`
          : `Row ${grew ? "taller" : "shorter"}`,
      );
      const next = this.handles.querySelector(
        `[data-axis="${axis}"][aria-label="${CSS.escape(handle.getAttribute("aria-label") || "")}"]`,
      );
      if (next instanceof HTMLElement) next.focus();
    });
  }
  /* ---------- Panel tools and menu ---------- */
  /** Attach docking controls and drag behavior to a panel header.
   * @param {string} id
   * @param {HTMLElement} panel
   * @returns {void}
   */
  mountPanel(id, panel) {
    const header = panel.querySelector(":scope > header");
    if (!(header instanceof HTMLElement)) return;
    header.draggable = false;
    const others = [...this.panels.keys()]
      .filter(item => item !== id)
      .map(item => `<option value="${item}">${this.nameOf(item)}</option>`)
      .join("");
    const item = (
      /** @type {string} */
      attribute,
      /** @type {string} */
      value,
      /** @type {string} */
      glyph,
      /** @type {string} */
      label,
    ) =>
      `<button type="button" class="panel-menu-item" role="menuitem" ${attribute}="${value}">${icon(glyph)}<span>${label}</span></button>`;
    const tools = document.createElement("div");
    tools.className = "panel-tools";
    tools.innerHTML = `
      <button type="button" class="panel-tool panel-tool-always button-small" data-panel-action="collapse" title="Collapse panel (Alt+Shift+C)" aria-label="Collapse panel" aria-keyshortcuts="Alt+Shift+C" aria-expanded="true">${icon("chevron-down")}</button>
      <button type="button" class="panel-tool panel-tool-reveal button-small" data-panel-action="float" title="Detach panel" aria-label="Detach panel" aria-pressed="false">${icon("app-window")}</button>
      <button type="button" class="panel-tool panel-tool-reveal button-small" data-panel-action="dock-menu" title="Move panel" aria-label="Move panel" aria-expanded="false">${icon("dots")}</button>
      <div class="panel-dock-menu" role="menu" aria-hidden="true">
        <span class="panel-menu-caption">Dock to window edge</span>
        ${item("data-panel-dock", "left", "arrow-left", "Dock left")}
        ${item("data-panel-dock", "right", "arrow-right", "Dock right")}
        ${item("data-panel-dock", "top", "arrow-up", "Dock top")}
        ${item("data-panel-dock", "bottom", "arrow-down", "Dock bottom")}
        <span class="panel-menu-caption">Place beside</span>
        <select data-panel-beside-target aria-label="Panel to place beside">${others}</select>
        <div class="panel-split-edges">
          ${item("data-panel-edge", "left", "arrow-left", "Place left")}
          ${item("data-panel-edge", "right", "arrow-right", "Place right")}
          ${item("data-panel-edge", "top", "arrow-up", "Place above")}
          ${item("data-panel-edge", "bottom", "arrow-down", "Place below")}
        </div>
        <span class="panel-menu-caption">Window</span>
        ${item("data-panel-dock", "float", "app-window", "Float window")}
      </div>`;
    header.append(tools);
    const bind = (
      /** @type {string} */
      selector,
      /** @type {(button:HTMLElement)=>void} */
      handler,
    ) =>
      tools.querySelectorAll(selector).forEach(node => {
        if (node instanceof HTMLElement)
          node.addEventListener("click", () => handler(node));
      });
    bind('[data-panel-action="collapse"]', () => this.toggleCollapse(id));
    bind('[data-panel-action="float"]', () => this.toggleFloat(id));
    bind('[data-panel-action="dock-menu"]', button => {
      const menu = tools.querySelector(".panel-dock-menu");
      const open = !menu?.classList.contains("is-open");
      DockGrid.closeMenus();
      menu?.classList.toggle("is-open", open);
      menu?.setAttribute("aria-hidden", String(!open));
      button.setAttribute("aria-expanded", String(open));
      if (open) this.syncMenu(id, tools);
    });
    bind("[data-panel-dock]", button => {
      const where = button.getAttribute("data-panel-dock") || "";
      DockGrid.closeMenus();
      if (where === "float") this.toggleFloat(id);
      else this.dockOuter(id, /** @type {Edge} */ (where));
    });
    bind("[data-panel-edge]", button => {
      const select = tools.querySelector("[data-panel-beside-target]");
      if (!(select instanceof HTMLSelectElement) || !select.value) return;
      DockGrid.closeMenus();
      this.dockBeside(
        id,
        select.value,
        /** @type {Edge} */
        (button.getAttribute("data-panel-edge")),
      );
    });
    header.addEventListener("pointerdown", event =>
      this.beginDrag(id, panel, event),
    );
    header.addEventListener(
      "click",
      event => {
        if (performance.now() >= this.suppressClickUntil) return;
        event.preventDefault();
        event.stopImmediatePropagation();
      },
      true,
    );
    header.addEventListener("dblclick", event => {
      if (
        event.target instanceof Element &&
        event.target.closest("button, input, select, .panel-tools")
      )
        return;
      if (this.layout.floating[this.owner(id)] === undefined)
        this.toggleCollapse(id);
    });
    // Alt+Shift+arrow docks along that window edge, +C collapses, +F floats.
    panel.addEventListener("keydown", event => {
      if (!event.altKey || !event.shiftKey || !this.editable) return;
      const edges = /** @type {Record<string, Edge>} */ ({
        ArrowLeft: "left",
        ArrowRight: "right",
        ArrowUp: "top",
        ArrowDown: "bottom",
      });
      const edge = edges[event.key];
      if (edge) this.dockOuter(id, edge);
      else if (event.code === "KeyC") this.toggleCollapse(id);
      else if (event.code === "KeyF") this.toggleFloat(id);
      else return;
      event.preventDefault();
    });
    panel.addEventListener("pointerdown", () => {
      if (panel.classList.contains("is-floating"))
        panel.style.zIndex = String(this.floatLayer += 1);
    });
    new ResizeObserver(() => this.rememberFloat(id, panel)).observe(panel);
  }
  /** Keep the saved window size in step with the native resize grip.
   * @param {string} id
   * @param {HTMLElement} panel
   * @returns {void}
   */
  rememberFloat(id, panel) {
    const saved = this.layout.floating[this.owner(id)];
    if (
      !saved ||
      !panel.classList.contains("is-floating") ||
      panel.classList.contains("is-collapsed")
    )
      return;
    const box = panel.getBoundingClientRect();
    if (Math.abs(box.width - saved.w) < 2 && Math.abs(box.height - saved.h) < 2)
      return;
    saved.w = Math.round(box.width);
    saved.h = Math.round(box.height);
    this.save();
  }
  /** Update panel controls for its current collapsed and floating state.
   * @param {string} id
   * @param {HTMLElement} panel
   * @param {boolean} collapsed
   * @param {boolean} allowed
   * @returns {void}
   */
  syncTools(id, panel, collapsed, allowed) {
    const collapse = panel.querySelector('[data-panel-action="collapse"]');
    if (collapse instanceof HTMLButtonElement) {
      const label = collapsed ? "Expand panel" : "Collapse panel";
      collapse.title =
        allowed || collapsed
          ? label
          : "Dock this panel to its own row or column to collapse it";
      collapse.setAttribute("aria-label", label);
      collapse.setAttribute("aria-expanded", String(!collapsed));
      collapse.disabled = !allowed && !collapsed;
    }
    const detach = panel.querySelector('[data-panel-action="float"]');
    if (detach instanceof HTMLButtonElement) {
      const floating = Boolean(this.view && id in this.view.floating);
      detach.title = floating
        ? "Dock panel back into the workspace"
        : "Detach panel";
      detach.setAttribute("aria-label", detach.title);
      detach.setAttribute("aria-pressed", String(floating));
    }
  }
  /** Refresh docking menu choices for the current panel layout.
   * @param {string} id
   * @param {Element} tools
   * @returns {void}
   */
  syncMenu(id, tools) {
    const select = tools.querySelector("[data-panel-beside-target]");
    if (select instanceof HTMLSelectElement)
      for (const option of select.options) {
        const unavailable =
          !this.view ||
          !(option.value in this.view.cells) ||
          option.value === id;
        option.hidden = unavailable;
        option.disabled = unavailable;
      }
    if (
      select instanceof HTMLSelectElement &&
      select.selectedOptions[0]?.disabled
    )
      select.value =
        [...select.options].find(option => !option.disabled)?.value ?? "";
    const float = tools.querySelector(
      '[data-panel-dock="float"] span:not(.studio-icon)',
    );
    if (float)
      float.textContent =
        this.view && id in this.view.floating ? "Dock window" : "Float window";
  }
  /** @returns {void}
   */
  static closeMenus = () => {
    for (const menu of document.querySelectorAll(".panel-dock-menu.is-open")) {
      menu.classList.remove("is-open");
      menu.setAttribute("aria-hidden", "true");
    }
    for (const button of document.querySelectorAll(
      '[data-panel-action="dock-menu"]',
    ))
      button.setAttribute("aria-expanded", "false");
  };
  /* ---------- Operations ---------- */
  /** Persist and render a committed layout change.
   * @param {string} message
   * @returns {void}
   */
  commit(message) {
    this.save();
    this.render();
    this.syncSizes();
    this.placeHandles();
    this.onStatus(message);
  }
  /** Collapse a panel to its title bar; a collapsed panel stays collapsed.
   * @param {string} id
   * @returns {void}
   */
  collapse(id) {
    if (!this.editable || this.mobile) return;
    if (!this.layout.collapsed[this.owner(id)]) this.toggleCollapse(id);
  }
  /** Collapse or restore the panel along its available grid axis.
   * @param {string} id
   * @returns {void}
   */
  toggleCollapse(id) {
    if (!this.editable || this.mobile) return;
    const key = this.owner(id);
    const collapsed = Boolean(this.layout.collapsed[key]);
    this.syncSizes();
    this.layout = Model.setCollapsed(this.layout, key, !collapsed);
    if (Boolean(this.layout.collapsed[key]) === collapsed) return;
    this.commit(`${this.nameOf(id)} ${collapsed ? "expanded" : "collapsed"}`);
  }
  /** Detach a panel or restore its previous dock position.
   * @param {string} id
   * @returns {void}
   */
  toggleFloat(id) {
    if (!this.editable || this.mobile) return;
    const key = this.owner(id);
    if (key in this.layout.floating) {
      const home = this.home[key];
      if (home && home.target in this.layout.cells)
        this.dockBeside(id, home.target, home.edge);
      else this.dockOuter(id, "right");
      return;
    }
    const panel = this.panels.get(id);
    if (!panel) return;
    this.syncSizes();
    const box = panel.getBoundingClientRect();
    this.rememberHome(id);
    const minimum = this.minimumOf(id);
    this.floatAt(id, {
      x: Math.round(box.left + 24),
      y: Math.round(box.top + 24),
      w: Math.round(Math.max(box.width, minimum.width)),
      h: Math.round(Math.max(box.height, minimum.height)),
    });
  }
  /** Detach a panel at the requested viewport coordinates.
   * @param {string} id
   * @param {{x:number,y:number,w:number,h:number}} rect
   * @returns {void}
   */
  floatAt(id, rect) {
    this.layout = Model.float(this.layout, this.owner(id), rect);
    this.commit(`${this.nameOf(id)} detached`);
    const panel = this.panels.get(id);
    if (panel) panel.style.zIndex = String(this.floatLayer += 1);
  }
  /** Remember a neighbour so the panel can return beside it.
   * @param {string} id
   * @returns {void}
   */
  rememberHome(id) {
    const key = this.owner(id);
    const cell = this.layout.cells[key];
    if (!cell) return;
    /** @type {{target:string,edge:Edge}|null} */
    let best = null;
    let bestArea = 0;
    for (const [other, near] of Object.entries(this.layout.cells)) {
      if (other === key) continue;
      /** @type {Edge|null} */
      let edge = null;
      if (near.c + near.cs === cell.c) edge = "right";
      else if (near.c === cell.c + cell.cs) edge = "left";
      else if (near.r + near.rs === cell.r) edge = "bottom";
      else if (near.r === cell.r + cell.rs) edge = "top";
      if (!edge || near.cs * near.rs <= bestArea) continue;
      bestArea = near.cs * near.rs;
      best = {
        target: other,
        edge,
      };
    }
    if (best) this.home[key] = best;
  }
  /** Dock a panel at the outer edge of the workspace.
   * @param {string} id
   * @param {Edge} edge
   * @returns {void}
   */
  dockOuter(id, edge) {
    if (!this.editable) return;
    this.syncSizes();
    this.layout = Model.dockOuter(this.layout, this.owner(id), edge);
    this.commit(`${this.nameOf(id)} docked along the ${edge} edge`);
  }
  /** Dock a panel beside the selected panel or ancestor group.
   * @param {string} id
   * @param {string} target
   * @param {Edge} edge
   * @returns {void}
   */
  dockBeside(id, target, edge) {
    if (!this.editable || !(this.owner(target) in this.layout.cells)) return;
    this.syncSizes();
    this.layout = Model.dockBeside(
      this.layout,
      this.owner(id),
      this.owner(target),
      edge,
      this.metrics(),
    );
    const side = {
      left: "left of",
      right: "right of",
      top: "above",
      bottom: "below",
    }[edge];
    this.commit(`${this.nameOf(id)} docked ${side} ${this.nameOf(target)}`);
  }
  /** Restore the shipped workspace layout.
   * @returns {void}
   */
  reset() {
    this.layout =
      this.mode === "graph"
        ? Model.defaultGraphLayout()
        : Model.defaultLayout();
    this.home = {};
    this.shareFlows();
    try {
      localStorage.removeItem(
        this.mode === "graph" ? `${STORAGE_KEY}.graph` : STORAGE_KEY,
      );
    } catch {
      /* Nothing stored to remove. */
    }
    this.render();
    this.syncSizes();
    this.onStatus("Panel layout reset");
  }
  /** Show a panel that is not part of the workspace, such as the action library. Compact screens reveal it in place; wider ones float it.
   * @param {string} id
   * @param {{x:number,y:number,w:number,h:number}} rect
   * @returns {void}
   */
  openWindow(id, rect) {
    const panel = this.panels.get(id);
    if (!panel) return;
    if (this.mobile) {
      panel.setAttribute("data-open", "");
      return;
    }
    if (!this.editable) return;
    const key = this.owner(id);
    this.layout = Model.setCollapsed(this.layout, key, false);
    const placed = key in this.layout.cells || key in this.layout.floating;
    if (placed) {
      this.save();
      this.render();
    } else this.floatAt(id, rect);
  }
  /* ---------- Dragging a panel ---------- */
  /** Start a header drag while preserving its pointer offset.
   * @param {string} id
   * @param {HTMLElement} panel
   * @param {PointerEvent} down
   * @returns {void}
   */
  beginDrag(id, panel, down) {
    if (
      down.button !== 0 ||
      !this.editable ||
      this.mobile ||
      down.target instanceof Element &&
        down.target.closest("button, input, select, textarea, a, .panel-tools")
    )
      return;
    const floating = panel.classList.contains("is-floating");
    const origin = panel.getBoundingClientRect();
    let started = false;
    /** @type {DockTarget|null} */
    let target = null;
    /** @type {HTMLElement|null} */
    let ghost = null;
    /** @type {HTMLElement|null} */
    let overlay = null;
    const drag = {
      begin: () => {
        started = true;
        window.getSelection()?.removeAllRanges();
        document.body.classList.add("panel-dock-dragging");
        panel.classList.add("is-dragging");
        DockGrid.closeMenus();
        overlay = document.createElement("div");
        overlay.className = "dock-drop";
        overlay.hidden = true;
        this.root.append(overlay);
        if (!floating) {
          ghost = document.createElement("div");
          ghost.className = "dock-ghost";
          ghost.textContent = this.nameOf(id);
          document.body.append(ghost);
        }
      },
      /** @param {PointerEvent} event
       */
      move: event => {
        const dx = event.clientX - down.clientX;
        const dy = event.clientY - down.clientY;
        if (!started && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
        if (!started) drag.begin();
        if (floating) {
          panel.style.left = `${Math.min(window.innerWidth - 80, Math.max(-origin.width + 80, origin.left + dx))}px`;
          panel.style.top = `${Math.min(window.innerHeight - 40, Math.max(0, origin.top + dy))}px`;
        } else if (ghost)
          ghost.style.transform = `translate(${event.clientX + 14}px, ${event.clientY + 14}px)`;
        target = this.hit(id, event.clientX, event.clientY, floating);
        this.showDrop(overlay, target);
      },
      up: () => drag.finish(true),
      cancel: () => drag.finish(false),
      /** @param {KeyboardEvent} event
       */
      key: event => {
        if (event.key !== "Escape") return;
        event.stopPropagation();
        if (floating) {
          panel.style.left = `${origin.left}px`;
          panel.style.top = `${origin.top}px`;
        }
        drag.finish(false);
      },
      /** @param {boolean} commit
       */
      finish: commit => {
        window.removeEventListener("pointermove", drag.move);
        window.removeEventListener("pointerup", drag.up);
        window.removeEventListener("pointercancel", drag.cancel);
        document.removeEventListener("keydown", drag.key, true);
        ghost?.remove();
        overlay?.remove();
        document.body.classList.remove("panel-dock-dragging");
        panel.classList.remove("is-dragging");
        if (!started) return;
        this.suppressClickUntil = performance.now() + 300;
        if (commit && target && !target.blocked) this.drop(id, target);
        else if (floating) {
          const saved = this.layout.floating[this.owner(id)];
          const box = panel.getBoundingClientRect();
          if (saved) {
            saved.x = Math.round(box.left);
            saved.y = Math.round(box.top);
            this.save();
          }
        } else this.render();
      },
    };
    window.addEventListener("pointermove", drag.move);
    window.addEventListener("pointerup", drag.up);
    window.addEventListener("pointercancel", drag.cancel);
    document.addEventListener("keydown", drag.key, true);
  }
  /** What dropping at a pointer position would do.
   * @param {string} id Panel being dragged.
   * @param {number} x
   * @param {number} y
   * @param {boolean} floating Whether the dragged panel is a floating window.
   * @returns {DockTarget|null}
   */
  hit(id, x, y, floating) {
    const area = this.root.getBoundingClientRect();
    if (x < area.left || x > area.right || y < area.top || y > area.bottom)
      return null;
    /** @type {Record<Edge,number>} */
    const outer = {
      left: x - area.left,
      right: area.right - x,
      top: y - area.top,
      bottom: area.bottom - y,
    };
    const [nearest, gap] = /** @type {[Edge,number]} */ (
      Object.entries(outer).sort((a, b) => a[1] - b[1])[0]
    );
    if (gap <= OUTER_BAND) {
      const band = 96;
      const rect =
        nearest === "left"
          ? new DOMRect(area.left, area.top, band, area.height)
          : nearest === "right"
            ? new DOMRect(area.right - band, area.top, band, area.height)
            : nearest === "top"
              ? new DOMRect(area.left, area.top, area.width, band)
              : new DOMRect(area.left, area.bottom - band, area.width, band);
      return {
        kind: "outer",
        edge: nearest,
        area: rect,
      };
    }
    for (const other of Object.keys(this.view?.cells ?? {})) {
      if (other === id) continue;
      const panel = this.panels.get(other);
      if (!panel) continue;
      const box = panel.getBoundingClientRect();
      if (x < box.left || x > box.right || y < box.top || y > box.bottom)
        continue;
      const fx = (x - box.left) / box.width;
      const fy = (y - box.top) / box.height;
      /** @type {Record<Edge,number>} */
      const share = {
        left: fx,
        right: 1 - fx,
        top: fy,
        bottom: 1 - fy,
      };
      const [edge, value] = /** @type {[Edge,number]} */ (
        Object.entries(share).sort((a, b) => a[1] - b[1])[0]
      );
      if (value < EDGE_SHARE || floating) {
        const vertical = edge === "left" || edge === "right";
        const need = vertical
          ? this.minimumOf(other).width + this.minimumOf(id).width
          : this.minimumOf(other).height + this.minimumOf(id).height;
        const room = vertical ? box.width : box.height;
        const half = vertical
          ? new DOMRect(
              edge === "left" ? box.left : box.left + box.width / 2,
              box.top,
              box.width / 2,
              box.height,
            )
          : new DOMRect(
              box.left,
              edge === "top" ? box.top : box.top + box.height / 2,
              box.width,
              box.height / 2,
            );
        return {
          kind: "edge",
          edge,
          target: other,
          blocked: room < need,
          area: half,
        };
      }
      if (this.owner(id) in this.layout.cells && !this.view?.collapsed[other])
        return {
          kind: "swap",
          target: other,
          area: box,
        };
      return null;
    }
    return null;
  }
  /** Display the marker for the current valid docking target.
   * @param {HTMLElement|null} overlay
   * @param {DockTarget|null} target
   * @returns {void}
   */
  showDrop(overlay, target) {
    if (!overlay) return;
    overlay.hidden = !target;
    if (!target) return;
    const root = this.root.getBoundingClientRect();
    overlay.style.left = `${target.area.left - root.left}px`;
    overlay.style.top = `${target.area.top - root.top}px`;
    overlay.style.width = `${target.area.width}px`;
    overlay.style.height = `${target.area.height}px`;
    overlay.setAttribute("data-kind", target.kind);
    overlay.toggleAttribute("data-blocked", Boolean(target.blocked));
    if (target.blocked)
      this.onStatus("There is not enough room to place the panel there.");
  }
  /** Commit a valid drop or leave the existing layout unchanged.
   * @param {string} id
   * @param {DockTarget} target
   * @returns {void}
   */
  drop(id, target) {
    this.syncSizes();
    if (target.kind === "outer" && target.edge) {
      this.rememberHome(id);
      this.dockOuter(id, target.edge);
    } else if (target.kind === "edge" && target.target && target.edge) {
      this.rememberHome(id);
      this.dockBeside(id, target.target, target.edge);
    } else if (target.kind === "swap" && target.target) {
      this.layout = Model.swap(
        this.layout,
        this.owner(id),
        this.owner(target.target),
      );
      this.commit(
        `${this.nameOf(id)} swapped with ${this.nameOf(target.target)}`,
      );
    }
  }
}
