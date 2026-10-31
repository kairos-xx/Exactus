/** Studio's binding to the expression widget: it maps Studio's data and
 * transport onto the widget's options and contains no widget UI. */
import { selectorLiveTools } from "./selector-live-tools.js";
/** @typedef {object} ExpressionFieldOptions
 * @property {string} label Visible field label.
 * @property {HTMLTextAreaElement|HTMLInputElement} textarea Stored form control (the value carrier).
 * @property {any} Editor Widget editor constructor.
 * @property {any} engine ExtendedSelector engine instance.
 * @property {string[]} selectors Saved selector names.
 * @property {number|null|undefined} [matchCount] Latest live-test match count.
 * @property {boolean} [multiple] One check per line.
 * @property {boolean} [startAsText] Start in Text mode.
 * @property {((apply:(element:{selector:string,matches?:number,alternatives?:Array<{strategy:string,selector:string,matches:number}>})=>void)=>void)|undefined} [onPick] Begin page picking.
 * @property {((value:string,done:(result:{count?:number})=>void)=>void)|undefined} [onHighlight] Highlight page matches.
 * @property {(()=>void)|undefined} [onClear] Remove the page highlight.
 * @property {((value:string)=>Promise<object>)|undefined} [onStats] Silent test returning widget stats.
 * @property {(()=>object[])|undefined} [variables] Variables the host offers.
 * @property {(()=>{name:string,count?:number|null}[])|undefined} [saved] Saved selectors with counts.
 * @property {(()=>number|null)|undefined} [expected] Expected match count.
 */
/** Build the widget `host` from Studio's callbacks.
 * Page actions stay in Studio's own live-tools row so the widget never draws a
 * second set of Pick/Highlight buttons inside Studio forms.
 * @param {ExpressionFieldOptions} options
 * @returns {object}
 */
export const widgetHost = options => ({
  ...(options.onStats ? { stats: options.onStats } : {}),
});
/** Mount the widget on a form control and keep the form contract.
 * @param {ExpressionFieldOptions} options
 * @returns {{field:HTMLElement, editor:any|null}}
 */
export const selectorExpressionField = options => {
  const field = document.createElement("div");
  field.className = "selector-field selector-expression-field";
  field.append(options.textarea);
  /** @type {any} */
  let editor = null;
  /** Write a value through the editor when present so its surface stays honest.
   * @param {string} value New expression text.
   * @returns {void}
   */
  const setValue = value => {
    if (editor) editor.value = value;
    else options.textarea.value = value;
    options.textarea.dispatchEvent(new Event("input", { bubbles: true }));
    options.textarea.dispatchEvent(new Event("change", { bubbles: true }));
  };
  if (options.onPick || options.onHighlight) {
    const live = selectorLiveTools({
      getValue: () => options.textarea.value,
      setValue,
      ...(options.onPick ? { onPick: options.onPick } : {}),
      ...(options.onHighlight ? { onHighlight: options.onHighlight } : {}),
      ...(options.onClear ? { onClear: options.onClear } : {}),
      matchCount: options.matchCount,
    });
    field.append(live.element);
  }
  if (!options.Editor || !options.engine) return { field, editor: null };
  editor = new options.Editor(options.textarea, {
    engine: options.engine,
    selectors: options.selectors,
    label: options.label,
    theme: "dark",
    ...(options.multiple !== undefined ? { multiple: options.multiple } : {}),
    ...(options.startAsText !== undefined ? { startAsText: options.startAsText } : {}),
    ...(options.variables ? { variables: options.variables } : {}),
    ...(options.saved ? { saved: options.saved } : {}),
    ...(options.expected ? { expected: options.expected } : {}),
    host: widgetHost(options),
  });
  const surface =
    options.textarea.nextElementSibling instanceof HTMLElement
      ? options.textarea.nextElementSibling
      : editor.surface instanceof HTMLElement
        ? editor.surface
        : null;
  const diagnostic = document.createElement("p");
  diagnostic.className = "selector-diagnostic";
  diagnostic.setAttribute("role", "status");
  diagnostic.hidden = true;
  /** Lint the carrier text into the diagnostic line.
   * @returns {void}
   */
  const lint = () => {
    const issues = options.engine.lint?.(options.textarea.value) ?? [];
    diagnostic.textContent = issues
      .map((/** @type {{message?:string}} */ issue) => issue.message ?? "")
      .filter(Boolean)
      .join("\n");
    diagnostic.hidden = issues.length === 0;
  };
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "selector-link";
  /** Swap between the visual expression view and the raw text area.
   * @param {boolean} text Show the raw textarea.
   * @returns {void}
   */
  const setMode = text => {
    options.textarea.hidden = !text;
    if (surface instanceof HTMLElement) surface.hidden = text;
    toggle.textContent = text ? "Edit as expression" : "Edit as text";
    toggle.setAttribute("aria-pressed", String(text));
    if (text) lint();
  };
  toggle.addEventListener("click", () => setMode(Boolean(options.textarea.hidden)));
  options.textarea.addEventListener("input", lint);
  editor.addEventListener?.("change", lint);
  if (surface instanceof HTMLElement)
    surface.addEventListener("click", event => {
      const hit = event.target;
      if (
        hit instanceof Element &&
        hit.closest("button, input, textarea, select, a, [contenteditable]")
      )
        return;
      /** @type {HTMLElement|null} */ (
        surface.querySelector(
          "[data-role='atom'], [contenteditable='true'], [tabindex]"
        )
      )?.focus();
    });
  field.append(toggle, diagnostic);
  setMode(!options.textarea.value.trim());
  return { field, editor };
};
