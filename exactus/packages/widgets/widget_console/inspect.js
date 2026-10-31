/** DOM rendering of value descriptors as inline, expandable inspector trees. */
import { formatFunction, formatValue } from "./format.js";
/** @typedef {import("./describe.js").Descriptor} Descriptor */
/** @typedef {import("./describe.js").Entry} Entry */
/** @typedef {import("./describe.js").ObjectDescriptor} ObjectDescriptor */
/**
 * Create an element with an optional class and text.
 * @template {keyof HTMLElementTagNameMap} K
 * @param {K} tag Tag name.
 * @param {string} [className] Class list.
 * @param {string} [text] Text content.
 * @returns {HTMLElementTagNameMap[K]} The new element.
 */
const make = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
/** Render value descriptors as inline, expandable inspector trees. */
export class Inspector {
  /**
   * Render a primitive or marker as a typed leaf.
   * @param {string} type Descriptor type used for colouring.
   * @param {string} text Display text.
   * @returns {HTMLElement} The leaf element.
   */
  static leaf = (type, text) => {
    const node = make("span", "jc-v", text);
    node.setAttribute("data-type", type);
    return node;
  };
  /**
   * Make a disclosure button for an expandable node.
   * @param {string} label Accessible name.
   * @returns {HTMLButtonElement} The twisty button.
   */
  static twisty = label => {
    const button = make("button", "jc-twisty");
    button.type = "button";
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-label", label);
    return button;
  };
  /**
   * Wire a head and twisty so either toggles a lazily built body.
   * @param {HTMLElement} box Outer node element.
   * @param {HTMLElement} head Head element.
   * @param {HTMLButtonElement} button Disclosure button.
   * @param {()=>HTMLElement} build Body factory, called once on first open.
   * @returns {void}
   */
  static wire = (box, head, button, build) => {
    /** @type {HTMLElement|null} */
    let body = null;
    const toggle = () => {
      const open = box.getAttribute("data-open") !== "true";
      if (open && !body) {
        body = build();
        box.append(body);
      }
      box.setAttribute("data-open", String(open));
      button.setAttribute("aria-expanded", String(open));
      if (body) body.hidden = !open;
    };
    button.addEventListener("click", event => {
      event.stopPropagation();
      toggle();
    });
    head.addEventListener("click", () => {
      if (window.getSelection()?.isCollapsed ?? true) toggle();
    });
  };
  /**
   * Render one container member.
   * @param {Entry} entry Member descriptor.
   * @param {string} kind Container kind.
   * @returns {HTMLElement} The member row.
   */
  static member = (entry, kind) => {
    const row = make("div", "jc-prop");
    if (entry.kd)
      row.append(Inspector.value(entry.kd, true), make("span", "jc-sep", " ⇒ "));
     else if (entry.k !== undefined) {
      const key = make("span", "jc-key", entry.k);
      if (kind === "array" || kind === "typed") key.setAttribute("data-index", "");
      row.append(key, make("span", "jc-sep", ": "));
    }
    row.append(Inspector.value(entry.v, true));
    return row;
  };
  /**
   * Render the expanded body of an object.
   * @param {ObjectDescriptor} descriptor Object descriptor.
   * @returns {HTMLElement} The children container.
   */
  static children = descriptor => {
    const list = make("div", "jc-children");
    list.setAttribute("role", "group");
    const stack = descriptor.error?.stack ?? "";
    if (stack) list.append(make("pre", "jc-stack", stack));
    for (const entry of descriptor.entries ?? []) list.append(Inspector.member(entry, descriptor.kind));
    if (descriptor.more) list.append(make("div", "jc-more", `… ${descriptor.more} more`));
    return list;
  };
  /**
   * Render an object, collection or error.
   * @param {ObjectDescriptor} descriptor Object descriptor.
   * @param {boolean} nested Whether the value sits inside a container.
   * @returns {HTMLElement} The inspector node.
   */
  static object = (descriptor, nested) => {
    const box = make("span", "jc-object");
    box.setAttribute("data-kind", descriptor.kind);
    const expandable = Boolean(descriptor.entries?.length || descriptor.more || descriptor.error?.stack);
    if (descriptor.circular || !expandable) {
      box.append(Inspector.leaf(descriptor.kind, formatValue(descriptor, { nested })));
      return box;
    }
    const head = make("span", "jc-object-head");
    const button = Inspector.twisty(`Expand ${descriptor.preview}`);
    const title = descriptor.kind === "error" && !nested ? descriptor.preview : formatValue(descriptor, { nested: true, depth: 1 });
    head.append(button, Inspector.leaf(descriptor.kind === "error" ? "error" : "object", title));
    box.append(head);
    Inspector.wire(box, head, button, () => Inspector.children(descriptor));
    return box;
  };
  /**
   * Render a function with its source on demand.
   * @param {Extract<Descriptor, {t:"function"}>} descriptor Function descriptor.
   * @returns {HTMLElement} The inspector node.
   */
  static func = descriptor => {
    const box = make("span", "jc-object");
    box.setAttribute("data-kind", "function");
    const head = make("span", "jc-object-head");
    const button = Inspector.twisty(`Show source of ${descriptor.name || "function"}`);
    head.append(button, Inspector.leaf("function", formatFunction(descriptor)));
    box.append(head);
    Inspector.wire(box, head, button, () => make("pre", "jc-stack", descriptor.src));
    return box;
  };
  /**
   * Render any descriptor as an inspector node.
   * @param {Descriptor} descriptor Value descriptor.
   * @param {boolean} [nested] Whether the value sits inside a container.
   * @returns {HTMLElement} The inspector node.
   */
  static value = (descriptor, nested = false) => {
    switch (descriptor.t) {
      case "function":
        return Inspector.func(descriptor);
      case "object":
        return Inspector.object(descriptor, nested);
      case "string":
        return Inspector.leaf("string", formatValue(descriptor, { nested }));
      default:
        return Inspector.leaf(descriptor.t, formatValue(descriptor, { nested }));
    }
  };
  /**
   * Render `console.table` output, or fall back to the plain value.
   * @param {Descriptor} data Tabular data descriptor.
   * @returns {HTMLElement} A table, or the inspector node when not tabular.
   */
  static table = data => {
    if (data.t !== "object" || !data.entries?.length) return Inspector.value(data);
    /** @type {string[]} */
    const columns = [];
    let hasValues = false;
    for (const entry of data.entries) {
      if (entry.v.t === "object" && entry.v.entries)
        for (const cell of entry.v.entries) {
          const name = cell.k ?? "";
          if (!columns.includes(name) && columns.length < 10) columns.push(name);
        }
       else
        hasValues = true;
    }
    const table = make("table", "jc-table");
    const head = make("tr");
    head.append(make("th", "", data.kind === "map" ? "(key)" : "(index)"), ...columns.map(name => make("th", "", name)));
    if (hasValues) head.append(make("th", "", "Value"));
    table.append(head);
    data.entries.forEach((entry, index) => {
      const row = make("tr");
      const label = entry.kd ? formatValue(entry.kd, { nested: true }) : (entry.k ?? String(index));
      row.append(make("th", "", label));
      const cells = entry.v.t === "object" ? (entry.v.entries ?? []) : [];
      for (const name of columns) {
        const cell = make("td");
        const found = cells.find(candidate => candidate.k === name);
        if (found) cell.append(Inspector.value(found.v, true));
        row.append(cell);
      }
      if (hasValues) {
        const cell = make("td");
        if (entry.v.t !== "object" || !entry.v.entries) cell.append(Inspector.value(entry.v, true));
        row.append(cell);
      }
      table.append(row);
    });
    return table;
  };
}
/**
 * Render any descriptor as an inspector node.
 * @type {typeof Inspector.value}
 */
export const renderValue = Inspector.value;
/**
 * Render `console.table` output, or fall back to the plain value.
 * @type {typeof Inspector.table}
 */
export const renderTable = Inspector.table;
