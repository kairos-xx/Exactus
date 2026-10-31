/** The panel that explains one variable pill: where it comes from and how it is read. */
import { iconElement } from "./icons.js";
/**
 * @typedef {object} InspectorOptions
 * @property {string} token The text between the braces, such as `Order.items[0]|count`.
 * @property {string} type What the variable holds, or an empty string when unknown.
 * @property {string} icon Icon of the action that produces it.
 * @property {string} tone Colour family of that action.
 * @property {(token:string) => void} onChange Called with the rewritten token.
 * @property {() => void} onClear Called when the person clears the pill.
 * @property {(name:string) => void} onReveal Called with the variable's name to show its source.
 */
/** The ways a variable can be read, by what it holds.
 * @param {string} type A type label such as "Text" or "Dictionary".
 * @returns {Array<[string, string]>} `[getter, label]` pairs, value first.
 */
export const gettersFor = type => {
  const whole = /** @type {Array<[string, string]>} */ ([["", "Value"]]);
  if (type === "Number" || type === "Boolean") return whole;
  if (type === "Text") return [...whole, ["count", "Length"]];
  return [
    ...whole,
    ["keys", "Keys"],
    ["values", "Values"],
    ["count", "Count"],
  ];
};
/** Build an element with a class.
 * @template {keyof HTMLElementTagNameMap} K
 * @param {K} tag
 * @param {string} [className]
 * @param {string} [text]
 * @returns {HTMLElementTagNameMap[K]}
 */
const make = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  node.className = className;
  if (text) node.textContent = text;
  return node;
};
/** A labelled row of the panel.
 * @param {string} caption
 * @param {HTMLElement} control
 * @returns {HTMLLabelElement}
 */
const row = (caption, control) => {
  const label = make("label", "variable-inspector-row");
  label.append(make("span", "", caption), control);
  return label;
};
/** Build the panel for one variable.
 * @param {InspectorOptions} options
 * @returns {HTMLElement}
 */
export const variableInspector = options => {
  const split = /^([^.[|]+)([^|]*)(?:\|(\w+))?$/.exec(options.token);
  const base = split?.[1] ?? options.token;
  const path = split?.[2] ?? "";
  const getter = split?.[3] ?? "";
  const type = options.type || "Any";
  const panel = make("div", "variable-inspector");
  const head = make("div", "variable-inspector-head");
  const tile = make("span", "action-tile");
  tile.setAttribute("data-tone", options.tone);
  tile.append(iconElement(options.icon));
  head.append(tile, make("strong", "variable-inspector-name", base));
  const actions = make("div", "variable-inspector-actions");
  const clear = make("button");
  clear.type = "button";
  clear.append(iconElement("x"), "Clear");
  clear.addEventListener("click", options.onClear);
  const reveal = make("button");
  reveal.type = "button";
  reveal.append(iconElement("eye"), "Reveal");
  reveal.addEventListener("click", () => options.onReveal(base));
  actions.append(clear, reveal);
  const kind = make("span", "variable-inspector-type", type);
  const key = make("input");
  key.type = "text";
  key.placeholder = "e.g. url or [0].url";
  key.value = path.replace(/^\./, "");
  const how = make("select");
  for (const [value, text] of gettersFor(type)) {
    const option = make("option", "", text);
    option.value = value;
    how.append(option);
  }
  how.value = getter;
  /** Rewrite the token from the key and the way it is read.
   * @returns {void}
   */
  const rewrite = () => {
    const raw = key.value.trim();
    const suffix = raw === "" ? "" : raw.startsWith("[") ? raw : `.${raw}`;
    options.onChange(`${base}${suffix}${how.value ? `|${how.value}` : ""}`);
  };
  key.addEventListener("input", rewrite);
  how.addEventListener("change", rewrite);
  panel.append(
    head,
    actions,
    row("Type", kind),
    row("Read as", how),
    row("Get key or index", key),
  );
  return panel;
};
