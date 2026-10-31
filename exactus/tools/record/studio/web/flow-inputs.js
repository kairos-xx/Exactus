/** The inputs a flow takes, edited as a list of rows in the flow settings. */
import { iconElement } from "./icons.js";
/**
 * @typedef {{name:string,value_type:string,required:boolean,default_value?:string|number|boolean|null}} FlowInput
 */
/** The value types an input can have, as `[stored, shown]` pairs.
 * @type {ReadonlyArray<readonly [string, string]>}
 */
export const INPUT_TYPES = [
  ["string", "Text"],
  ["integer", "Whole number"],
  ["float", "Decimal number"],
  ["boolean", "True or false"],
  ["json", "JSON"],
];
/** Build an element with optional class.
 * @template {keyof HTMLElementTagNameMap} K
 * @param {K} tag
 * @param {string} [className]
 * @returns {HTMLElementTagNameMap[K]}
 */
const make = (tag, className = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
};
/** One editable input row.
 * @param {FlowInput} input
 * @param {() => void} onRemove
 * @returns {HTMLElement}
 */
const inputRow = (input, onRemove) => {
  const row = make("div", "flow-input");
  const name = make("input");
  name.type = "text";
  name.value = input.name;
  name.placeholder = "Input name";
  name.setAttribute("aria-label", "Input name");
  name.setAttribute("data-part", "name");
  const type = make("select");
  type.setAttribute("aria-label", "Input type");
  type.setAttribute("data-part", "type");
  for (const [value, text] of INPUT_TYPES) {
    const option = make("option");
    option.value = value;
    option.textContent = text;
    type.append(option);
  }
  type.value = input.value_type;
  const required = make("input");
  required.type = "checkbox";
  required.checked = input.required;
  required.setAttribute("data-part", "required");
  const requiredLabel = make("label", "check");
  requiredLabel.append(required, "Required");
  const fallback = make("input");
  fallback.type = "text";
  fallback.value = input.required ? "" : String(input.default_value ?? "");
  fallback.placeholder = "Default value";
  fallback.setAttribute("aria-label", "Default value");
  fallback.setAttribute("data-part", "default");
  fallback.disabled = input.required;
  required.addEventListener("change", () => {
    fallback.disabled = required.checked;
    if (required.checked) fallback.value = "";
  });
  const remove = make("button");
  remove.type = "button";
  remove.title = "Remove input";
  remove.setAttribute("aria-label", "Remove input");
  remove.append(iconElement("trash"));
  remove.addEventListener("click", onRemove);
  const identity = make("div", "flow-input-line");
  identity.append(name, type, remove);
  const rule = make("div", "flow-input-line");
  rule.append(requiredLabel, fallback);
  row.append(identity, rule);
  return row;
};
/** One text or checkbox control of an input row.
 * @param {HTMLElement} row
 * @param {string} role Which control: name, required or default.
 * @returns {HTMLInputElement}
 */
const control = (row, role) =>
  /** @type {HTMLInputElement} */ (row.querySelector(`[data-part="${role}"]`));
/** The type menu of an input row.
 * @param {HTMLElement} row
 * @returns {HTMLSelectElement}
 */
const typeMenu = row =>
  /** @type {HTMLSelectElement} */ (row.querySelector('[data-part="type"]'));
/** An editable list of the inputs a flow takes.
 * @param {FlowInput[]} inputs The flow's saved inputs.
 * @returns {{element:HTMLElement,read:() => FlowInput[]}} The list and a reader
 *   for what it currently shows.
 */
export const flowInputsField = inputs => {
  const element = make("div", "flow-inputs");
  const list = make("div", "flow-inputs-list");
  const add = make("button", "flow-inputs-add");
  add.type = "button";
  add.append(iconElement("plus"), "Add input");
  /** Add one row.
   * @param {FlowInput} input
   * @returns {void}
   */
  const append = input => {
    const row = inputRow(input, () => {
      row.remove();
      list.dispatchEvent(new Event("input", { bubbles: true }));
    });
    list.append(row);
  };
  for (const input of inputs) append(input);
  add.addEventListener("click", () => {
    append({ name: "", value_type: "string", required: true });
    list.dispatchEvent(new Event("input", { bubbles: true }));
    const last = list.querySelector(".flow-input:last-child input");
    if (last instanceof HTMLInputElement) last.focus();
  });
  element.append(list, add);
  return {
    element,
    read: () =>
      [...list.children].filter(row => row instanceof HTMLElement).map(row => ({
        name: control(row, "name").value.trim(),
        value_type: typeMenu(row).value,
        required: control(row, "required").checked,
        default_value: control(row, "default").value,
      })),
  };
};
