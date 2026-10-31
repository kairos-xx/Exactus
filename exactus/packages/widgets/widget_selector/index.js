/** Public entry of the expression widget. */
import { createWidget } from "./widget.js";
/**
 * Mount the widget on a carrier element that keeps the stored value.
 * @param {HTMLTextAreaElement|HTMLInputElement} carrier Carrier element.
 * @param {{language?:"selector", engine:any, label?:string, multiple?:boolean, startAsText?:boolean, theme?:string|null, providers?:object, host?:object, root?:Document|Element}} options Widget options.
 * @returns {ReturnType<typeof createWidget>} The widget API.
 * @throws {Error} When the language is unsupported.
 */
export const mountExpressionWidget = (carrier, options) => {
  if ((options.language ?? "selector") !== "selector")
    throw new Error(`Unsupported language: ${options.language}`);
  return createWidget({ carrier, label: options.label ?? "Expression", ...options });
};
export default mountExpressionWidget;
