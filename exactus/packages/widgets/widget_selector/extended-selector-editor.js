/** Compatibility wrapper with the contract Studio's field already uses. */
import { mountExpressionWidget } from "./index.js";
/** Compatibility wrapper with the contract Studio's field already uses. */
export class ExtendedSelectorEditor extends EventTarget {
  /**
   * Mount the widget on a target textarea.
   * @param {HTMLTextAreaElement} target Target textarea.
   * @param {{engine?:any, selectors?:string[], label?:string, multiple?:boolean, startAsText?:boolean, theme?:string|null, variables?:()=>any[], saved?:()=>any[], expected?:()=>number|null, host?:object}} [options] Editor options.
   */
  constructor(target, options = {}) {
    super();
    this.target = target;
    this.options = options;
    this.controller = mountExpressionWidget(target, {
      engine: options.engine,
      label: options.label ?? "Expression",
      ...(options.multiple !== undefined ? { multiple: options.multiple } : {}),
      ...(options.startAsText !== undefined ? { startAsText: options.startAsText } : {}),
      ...(options.theme !== undefined ? { theme: options.theme } : {}),
      providers: {
        variables: options.variables ?? (() => []),
        saved: options.saved ?? (() => (options.selectors ?? []).map(name => ({ name }))),
        ...(options.expected ? { expected: options.expected } : {}),
      },
      ...(options.host ? { host: options.host } : {}),
    });
    this.surface = this.controller.surface;
    this.controller.on("change", () => this.dispatchEvent(new Event("change")));
  }
  /**
   * Read the expression text.
   * @returns {string} The expression text.
   */
  get value() {
    return this.controller.value;
  }
  /**
   * Replace the expression text.
   * @param {string} next New expression text.
   */
  set value(next) {
    this.controller.value = next;
  }
  /**
   * Replace the expression engine.
   * @param {any} engine New engine.
   * @returns {ExtendedSelectorEditor} This editor.
   */
  setEngine(engine) {
    this.options.engine = engine;
    return this;
  }
}
export default ExtendedSelectorEditor;
