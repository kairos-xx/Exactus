/** A searchable popover that inserts earlier action values into the snippet. */
import { Describer } from "../../widgets/widget_console/describe.js";
import { formatValue } from "../../widgets/widget_console/format.js";
/**
 * @typedef {object} Variable
 * @property {string} name Value name, such as `user/id`.
 * @property {unknown} value Value read by `exactus.vars.get`.
 * @property {boolean} [secret] Whether previews are masked.
 * @property {string} [type] Type shown while the value is not known.
 */
/**
 * @typedef {object} MenuOptions
 * @property {HTMLButtonElement} anchor Button that toggles the menu.
 * @property {()=>Variable[]} variables Current values.
 * @property {(name:string)=>void} onPick Called with the chosen name.
 */
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
/**
 * Preview a value for the list.
 * @param {Variable} variable Variable to preview.
 * @returns {string} Short preview text.
 */
const preview = variable => {
  if (variable.secret) return "••••••••";
  if (variable.value === undefined && variable.type) return variable.type;
  return formatValue(Describer.describe(variable.value), { nested: true, depth: 0 });
};
/**
 * Create the menu element and wire it to its anchor.
 * @param {MenuOptions} options Menu options.
 * @returns The menu API.
 */
export const createVariablesMenu = options => {
  const { anchor } = options;
  const menu = make("div", "jr-menu");
  menu.hidden = true;
  menu.setAttribute("role", "dialog");
  menu.setAttribute("aria-label", "Insert a value");
  const search = make("input", "jr-menu-search");
  search.type = "search";
  search.placeholder = "Search values";
  search.setAttribute("aria-label", "Search values");
  search.autocomplete = "off";
  const list = make("div", "jr-menu-list");
  list.setAttribute("role", "listbox");
  list.setAttribute("aria-label", "Values");
  menu.append(search, list);
  anchor.setAttribute("aria-haspopup", "dialog");
  anchor.setAttribute("aria-expanded", "false");
  let active = 0;
  /**
   * List the current option elements.
   * @returns {HTMLElement[]} The current option elements.
   */
  const items = () => [...list.querySelectorAll(".jr-menu-item")].filter(node => node instanceof HTMLElement);
  /** Mark the active option and keep it visible. */
  const markActive = () => {
    const nodes = items();
    active = Math.min(Math.max(active, 0), Math.max(nodes.length - 1, 0));
    nodes.forEach((node, index) => {
      node.setAttribute("aria-selected", String(index === active));
      if (index === active) node.scrollIntoView({ block: "nearest" });
    });
  };
  /** Hide the menu and reset the anchor state. */
  const close = () => {
    if (menu.hidden) return;
    menu.hidden = true;
    anchor.setAttribute("aria-expanded", "false");
  };
  /** Rebuild the options for the current query. */
  const render = () => {
    const query = search.value.trim().toLowerCase();
    const shown = options.variables().filter(variable => variable.name.toLowerCase().includes(query));
    list.replaceChildren(
      ...shown.map(variable => {
        const item = make("button", "jr-menu-item");
        item.type = "button";
        item.setAttribute("role", "option");
        item.append(make("span", "jr-menu-name", variable.name), make("span", "jr-menu-preview", preview(variable)));
        item.addEventListener("click", () => {
          close();
          options.onPick(variable.name);
        });
        return item;
      }),
    );
    if (shown.length === 0) list.append(make("p", "jr-menu-empty", "No matching values."));
    active = 0;
    markActive();
  };
  /** Show the menu, rebuild the options and focus the search. */
  const open = () => {
    search.value = "";
    render();
    menu.hidden = false;
    anchor.setAttribute("aria-expanded", "true");
    search.focus();
  };
  /** Toggle the menu open or closed. */
  const toggle = () => menu.hidden ? open() : close();
  anchor.addEventListener("click", toggle);
  search.addEventListener("input", render);
  menu.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      anchor.focus();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      active += event.key === "ArrowDown" ? 1 : -1;
      markActive();
    } else if (event.key === "Enter") {
      event.preventDefault();
      items()[active]?.click();
    }
  });
  /**
   * Close the menu when a press lands outside it and its anchor.
   * @param {PointerEvent} event Pointer press anywhere.
   */
  const outside = event => {
    if (!menu.hidden && event.target instanceof Node && !menu.contains(event.target) && !anchor.contains(event.target)) close();
  };
  document.addEventListener("pointerdown", outside);
  return {
    element: menu,
    toggle,
    close,
    destroy: () => {
      document.removeEventListener("pointerdown", outside);
      menu.remove();
    },
  };
};
