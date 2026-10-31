import { iconElement } from "./icons.js";
/** Explicit DOM rendering for the flow graph. Positions never change execution order.
 */
/** @typedef {import('./editor.js').EditorFlow} Flow */
/** @typedef {import('./editor.js').EditorEdge} Edge */
/** @typedef {{x:number,y:number}} Position */
const svgNamespace = "http://www.w3.org/2000/svg";
/** Create a text-only HTML element with the requested class.
 * @param {string} tag
 * @param {string} className
 * @param {string} [text]
 * @returns {HTMLElement}
 */
const element = (tag, className, text = "") => {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
};
/** Create an accessible decorative Studio icon.
 * @param {string} name
 * @returns {SVGSVGElement}
 */
const icon = name => iconElement(name);
/** Create an SVG element and assign its supplied attributes.
 * @param {string} tag
 * @param {Record<string,string>} attributes
 * @returns {SVGElement}
 */
export const graphSvg = (tag, attributes) => {
  const node = document.createElementNS(svgNamespace, tag);
  for (const [key, value] of Object.entries(attributes))
    node.setAttribute(key, value);
  return node;
};
/** Render a compact summary of named graph input or output fields.
 * @param {unknown[]} values
 * @param {string} label
 * @returns {HTMLElement}
 */
const fields = (values, label) => {
  const row = element("div", "graph-node-fields");
  row.append(element("span", "graph-field-label", label));
  const names = values
    .map(value => {
      if (!value || typeof value !== "object" || !("name" in value)) return "";
      return String(value.name);
    })
    .filter(Boolean);
  const content = element(
    "span",
    "graph-field-values",
    names.join(", ") || "None",
  );
  content.title = content.textContent || "";
  row.append(content);
  return row;
};
/** Place branches in downstream columns without treating positions as execution order. Cyclic components retain a finite grid fallback; retry edges do not advance columns.
 * @param {Flow[]} flows
 * @param {Edge[]} edges
 * @returns {Record<string,Position>}
 */
export const defaultGraphPositions = (flows, edges) => {
  const ids = new Set(flows.map(flow => flow.id));
  const links = edges.filter(
    edge =>
      ids.has(edge.source) &&
      ids.has(edge.target) &&
      edge.source !== edge.target &&
      edge.mode !== "retry",
  );
  const degree = new Map(flows.map(flow => [flow.id, 0]));
  const level = new Map(flows.map(flow => [flow.id, 0]));
  for (const edge of links)
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  const ready = flows
    .filter(flow => !degree.get(flow.id))
    .map(flow => flow.id);
  const visited = new Set();
  while (ready.length) {
    const source = ready.shift();
    if (!source || visited.has(source)) continue;
    visited.add(source);
    for (const edge of links.filter(item => item.source === source)) {
      level.set(
        edge.target,
        Math.max(level.get(edge.target) ?? 0, (level.get(source) ?? 0) + 1),
      );
      degree.set(edge.target, (degree.get(edge.target) ?? 1) - 1);
      if (!degree.get(edge.target)) ready.push(edge.target);
    }
  }
  /** @type {Record<string,Position>} */
  const positions = {};
  const rows = new Map();
  for (const [index, flow] of flows.entries()) {
    const column =
      links.length && visited.has(flow.id)
        ? (level.get(flow.id) ?? 0)
        : index % 3;
    const row = rows.get(column) ?? 0;
    rows.set(column, row + 1);
    positions[flow.id] = { x: 32 + column * 296, y: 32 + row * 240 };
  }
  return positions;
};
/** Render editable flow nodes at their saved graph positions.
 * @param {Flow[]} flows
 * @param {string|null} active
 * @param {Record<string,Position>} positions
 * @param {Edge[]} edges
 * @returns {HTMLElement}
 */
export const graphNodes = (flows, active, positions, edges) => {
  const canvas = element("div", "composition-nodes");
  const defaults = defaultGraphPositions(flows, edges);
  for (const [index, flow] of flows.entries()) {
    const saved = positions[flow.id];
    const position =
      saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)
        ? saved
        : (defaults[flow.id] ?? { x: 32, y: 32 });
    const node = element("article", "flow-node");
    node.setAttribute("data-node-flow", flow.id);
    node.classList.toggle("active", flow.id === active);
    node.style.left = `${Math.max(8, position.x)}px`;
    node.style.top = `${Math.max(8, position.y)}px`;
    const title = element("button", "flow-node-title");
    title.setAttribute("type", "button");
    title.setAttribute("data-select-flow", flow.id);
    title.title = flow.name;
    title.setAttribute("aria-pressed", String(flow.id === active));
    title.append(
      icon("arrows-join"),
      element("span", "graph-node-name", flow.name),
      element("small", "graph-node-index", String(index + 1).padStart(2, "0")),
    );
    node.append(
      title,
      fields(flow.parameters ?? [], "Inputs"),
      fields(flow.outputs ?? [], "Outputs"),
    );
    for (const direction of ["input", "output"]) {
      const port = element(
        "button",
        `flow-node-port flow-node-port-${direction}`,
      );
      port.setAttribute("type", "button");
      port.setAttribute(`data-graph-${direction}`, flow.id);
      const label = `Connect ${direction === "input" ? "into" : "from"} ${flow.name}`;
      port.setAttribute("aria-label", label);
      port.title = `${label} · Drag or press Enter`;
      node.append(port);
    }
    canvas.append(node);
  }
  if (!flows.length) {
    const empty = element("div", "graph-empty");
    empty.append(
      icon("arrows-join"),
      element("h2", "", "Connect your flows"),
      element("p", "", "Add a flow to start building your graph."),
    );
    canvas.append(empty);
  }
  return canvas;
};
/** Calculate the bounding rectangle of all positioned flow nodes.
 * @param {HTMLElement} canvas
 * @returns {{width:number,height:number}}
 */
export const graphBounds = canvas => {
  let width = 0;
  let height = 0;
  canvas.querySelectorAll(".flow-node").forEach(node => {
    if (!(node instanceof HTMLElement)) return;
    width = Math.max(width, node.offsetLeft + node.offsetWidth + 32);
    height = Math.max(height, node.offsetTop + node.offsetHeight + 32);
  });
  return { width, height };
};
/** Render transition paths and their selection handlers.
 * @param {HTMLElement} canvas
 * @param {Edge[]} edges
 * @param {Flow[]} flows
 * @param {number} zoom
 * @param {string} selected
 * @param {(edge:Edge)=>void} select
 * @returns {void}
 */
export const graphLinks = (canvas, edges, flows, zoom, selected, select) => {
  canvas
    .querySelector(".composition-links:not(.composition-preview-links)")
    ?.remove();
  const bounds = graphBounds(canvas);
  const parent = canvas.parentElement;
  const width = Math.max(bounds.width, (parent?.clientWidth ?? 0) / zoom, 1);
  const height = Math.max(bounds.height, (parent?.clientHeight ?? 0) / zoom, 1);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const svg = graphSvg("svg", {
    class: "composition-links",
    width: String(width),
    height: String(height),
    viewBox: `0 0 ${width} ${height}`,
    "aria-label": "Flow connections",
  });
  const defs = graphSvg("defs", {});
  const marker = graphSvg("marker", {
    id: "composition-arrow",
    viewBox: "0 0 8 8",
    refX: "7",
    refY: "4",
    markerWidth: "6",
    markerHeight: "6",
    orient: "auto",
  });
  marker.append(graphSvg("path", { d: "M 0 0 L 8 4 L 0 8 Z" }));
  defs.append(marker);
  svg.append(defs);
  for (const edge of edges) {
    const source = canvas.querySelector(
      `[data-graph-output="${CSS.escape(edge.source)}"]`,
    );
    const target = canvas.querySelector(
      `[data-graph-input="${CSS.escape(edge.target)}"]`,
    );
    if (!(source instanceof HTMLElement) || !(target instanceof HTMLElement))
      continue;
    const rect = canvas.getBoundingClientRect();
    const a = source.getBoundingClientRect();
    const b = target.getBoundingClientRect();
    const x1 = (a.left + a.width / 2 - rect.left) / zoom;
    const y1 = (a.top + a.height / 2 - rect.top) / zoom;
    const x2 = (b.left + b.width / 2 - rect.left) / zoom;
    const y2 = (b.top + b.height / 2 - rect.top) / zoom;
    const bend = Math.max(44, Math.abs(x2 - x1) / 2);
    const path = `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`;
    const key = `${edge.source}:${edge.target}`;
    const label =
      edge.condition_expression ||
      (edge.mode === "retry"
        ? `retry · limit ${edge.max_traversals || 1}`
        : edge.mode || "always");
    const from =
      flows.find(flow => flow.id === edge.source)?.name || edge.source;
    const to =
      flows.find(flow => flow.id === edge.target)?.name || edge.target;
    const group = graphSvg("g", {
      class: `composition-link${key === selected ? " is-selected" : ""}`,
      "data-edge": key,
      tabindex: "0",
      role: "button",
      "aria-label": `${from} to ${to}: ${label}`,
      "aria-pressed": String(key === selected),
    });
    group.append(
      graphSvg("path", {
        d: path,
        class: "graph-edge-line",
        "marker-end": "url(#composition-arrow)",
      }),
      graphSvg("path", { d: path, class: "graph-edge-hit" }),
    );
    const text = graphSvg("text", {
      x: String((x1 + x2) / 2),
      y: String((y1 + y2) / 2 - 10),
    });
    text.textContent = label.length > 32 ? `${label.slice(0, 31)}…` : label;
    group.append(text);
    group.addEventListener("click", event => {
      event.stopPropagation();
      select(edge);
    });
    group.addEventListener("keydown", event => {
      if (
        event instanceof KeyboardEvent &&
        ["Enter", " "].includes(event.key)
      ) {
        event.preventDefault();
        select(edge);
      }
    });
    svg.append(group);
  }
  canvas.prepend(svg);
};
/** Render editable settings for the selected transition.
 * @param {Edge} edge
 * @param {Flow[]} flows
 * @param {()=>void} remove
 * @param {(value:Edge)=>Promise<void>} update
 * @returns {HTMLElement}
 */
export const graphConnectionInspector = (edge, flows, remove, update) => {
  const section = element("section", "graph-connection-inspector");
  const heading = element("div", "graph-inspector-heading");
  heading.append(icon("arrows-join"), element("h2", "", "Connection"));
  section.append(
    heading,
    element("p", "graph-inspector-help", "Controls which flow runs next."),
  );
  const list = element("dl", "graph-connection-details");
  for (const [label, value] of [
    [
      "From",
      flows.find(flow => flow.id === edge.source)?.name || edge.source,
    ],
    ["To", flows.find(flow => flow.id === edge.target)?.name || edge.target],
  ])
    list.append(element("dt", "", label), element("dd", "", value));
  const button = element(
    "button",
    "graph-remove-connection",
    "Remove connection",
  );
  button.setAttribute("type", "button");
  button.addEventListener("click", remove);
  const form = document.createElement("form");
  form.className = "graph-connection-form";
  const mode = document.createElement("select");
  mode.name = "mode";
  for (const [value, label] of [
    ["always", "On success"],
    ["fallback", "Fallback"],
    ["finally", "Always finish"],
    ["retry", "Retry on failure"],
    ["condition", "If condition matches"],
  ]) {
    const option = document.createElement("option");
    option.value = value || "";
    option.textContent = label || "";
    mode.append(option);
  }
  mode.value = edge.mode || "always";
  const condition = document.createElement("input");
  condition.name = "condition_expression";
  condition.value = edge.condition_expression || "";
  const priority = document.createElement("input");
  priority.name = "priority";
  priority.type = "number";
  priority.step = "1";
  priority.value = String(edge.priority ?? 0);
  const limit = document.createElement("input");
  limit.name = "max_traversals";
  limit.type = "number";
  limit.min = "1";
  limit.step = "1";
  limit.value = String(edge.max_traversals ?? 1);
  for (const [name, control] of /** @type {[string,HTMLElement][]} */ ([
    ["Run when", mode],
    ["Condition", condition],
    ["Priority", priority],
    ["Traversal limit", limit],
  ])) {
    const label = document.createElement("label");
    label.append(document.createTextNode(name), control);
    form.append(label);
  }
  /** Show the condition field only for condition-based transitions.
   * @returns {void}
   */
  const sync = () => {
    condition.disabled = mode.value !== "condition";
    condition.required = mode.value === "condition";
  };
  mode.addEventListener("change", sync);
  sync();
  const save = document.createElement("button");
  save.type = "submit";
  save.textContent = "Apply connection";
  const status = document.createElement("p");
  status.setAttribute("role", "status");
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    save.disabled = true;
    status.textContent = "Saving connection…";
    try {
      await update({
        ...edge,
        mode: mode.value,
        condition_expression: mode.value === "condition" ? condition.value : "",
        priority: Number(priority.value),
        max_traversals: Number(limit.value),
      });
      status.textContent = "Connection updated";
    } catch (error) {
      status.textContent =
        error instanceof Error ? error.message : String(error);
    } finally {
      save.disabled = false;
    }
  });
  form.append(save, status);
  section.append(list, form, button);
  return section;
};
