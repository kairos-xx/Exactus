/** The small editor that opens when a card token is clicked. */
import { variableMentionField } from "./variable-mention-field.js";
/**
 * @typedef {object} TokenEditorOptions
 * @property {HTMLElement} anchor The token the editor opens under.
 * @property {string} value Current value.
 * @property {boolean} code Edit several lines of code instead of one value.
 * @property {import("./variable-mention-field.js").VariableSource[]} variables Results offered by the picker.
 * @property {(value:string) => void} onCommit Called with the new value.
 */
/** Build an element with a class.
 * @template {keyof HTMLElementTagNameMap} K
 * @param {K} tag
 * @param {string} [className]
 * @returns {HTMLElementTagNameMap[K]}
 */
const make = (tag, className = "") => {
  const node = document.createElement(tag);
  node.className = className;
  return node;
};
/** Open the editor for one token and close it again on commit or cancel.
 * @param {TokenEditorOptions} options
 * @returns {void}
 */
export const openTokenEditor = options => {
  const { anchor, value, code, variables, onCommit } = options;
  document.querySelector(".token-editor")?.remove();
  const panel = make("div", "token-editor");
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Edit value");
  const input = code ? make("textarea") : make("input");
  input.value = value;
  if (input instanceof HTMLInputElement) input.type = "text";
  input.setAttribute("aria-label", "Value");
  if (code) {
    input.spellcheck = false;
    input.className = "token-editor-code";
    if (input instanceof HTMLTextAreaElement) input.rows = 8;
    panel.append(input);
  } else panel.append(input);
  const field = code ? input : variableMentionField(input, variables);
  if (!code) panel.replaceChildren(field);
  let finished = false;
  const lifetime = new AbortController();
  /** Close the editor, committing the value when it changed.
   * @param {boolean} save
   * @returns {void}
   */
  const finish = save => {
    if (finished) return;
    finished = true;
    lifetime.abort();
    panel.remove();
    if (save && input.value !== value) onCommit(input.value);
  };
  panel.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      event.preventDefault();
      finish(false);
    } else if (event.key === "Enter" && (!code || event.metaKey || event.ctrlKey)) {
      const menu = panel.querySelector(".variable-menu");
      if (menu instanceof HTMLElement && !menu.hidden) return;
      event.preventDefault();
      finish(true);
    }
  });
  document.body.append(panel);
  const box = anchor.getBoundingClientRect();
  const width = Math.min(window.innerWidth - 16, code ? 480 : 360);
  panel.style.left = `${Math.max(8, Math.min(box.left, window.innerWidth - width - 8))}px`;
  panel.style.top = `${box.bottom + 6}px`;
  panel.style.width = `${width}px`;
  // Clicking anywhere outside the editor commits the value.
  document.addEventListener(
    "pointerdown",
    event => {
      if (event.target instanceof Node && !panel.contains(event.target))
        finish(true);
    },
    { capture: true, signal: lifetime.signal },
  );
  const target = code ? input : panel.querySelector(".variable-editor");
  if (target instanceof HTMLElement) target.focus();
};
/** Show ready-made content in a floating panel under an anchor; it closes on
 * Escape or a click outside.
 * @param {HTMLElement} anchor The element the panel opens under.
 * @param {HTMLElement} content What the panel shows.
 * @returns {() => void} Closes the panel.
 */
export const openFloatingPanel = (anchor, content) => {
  document.querySelector(".token-editor")?.remove();
  const panel = make("div", "token-editor");
  panel.setAttribute("role", "dialog");
  panel.append(content);
  const lifetime = new AbortController();
  /** Close the panel.
   * @returns {void}
   */
  const close = () => {
    lifetime.abort();
    panel.remove();
  };
  document.body.append(panel);
  const box = anchor.getBoundingClientRect();
  const width = Math.min(window.innerWidth - 16, 340);
  panel.style.left = `${Math.max(8, Math.min(box.left, window.innerWidth - width - 8))}px`;
  panel.style.top = `${box.bottom + 6}px`;
  panel.style.width = `${width}px`;
  document.addEventListener(
    "pointerdown",
    event => {
      if (event.target instanceof Node && !panel.contains(event.target)) close();
    },
    { capture: true, signal: lifetime.signal },
  );
  panel.addEventListener("keydown", event => {
    if (event.key === "Escape") close();
  });
  return close;
};
