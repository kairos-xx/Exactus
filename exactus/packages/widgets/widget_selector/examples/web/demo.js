/** Demo page: the widget on a sample page, with width, theme and mode controls. */
import ExtendedSelector from "../../../../extended_selector/editor/extended-selector.js";
import { createDemoHost } from "./demo-host.js";
import { mountExpressionWidget } from "../../index.js";
const stage = /** @type {HTMLElement} */ (document.getElementById("stage"));
const layer = /** @type {HTMLElement} */ (document.getElementById("layer"));
const engine = new ExtendedSelector(document);
const host = createDemoHost({ engine, stage, layer });
const carrier = /** @type {HTMLTextAreaElement} */ (document.getElementById("expression"));
carrier.value = 'and(.card, has(.card, button[innerText^="Save"]), not(:disabled))';
const widget = mountExpressionWidget(carrier, {
  engine,
  label: "Expression",
  root: stage,
  providers: {
    saved: () => [
      { name: "save-button", count: 2 },
      { name: "group/sidebar.save", count: 1 },
    ],
    variables: () => [{ path: "orders/total", scope: "flow", type: "num", value: 3 }],
    expected: () => null,
  },
  host,
});
const second = /** @type {HTMLTextAreaElement} */ (document.getElementById("checks"));
second.value = "button\n:hovr\na::before";
mountExpressionWidget(second, { engine, label: "Every match must satisfy", multiple: true, startAsText: true, root: stage, providers: {}, host: {} });
const panel = /** @type {HTMLElement} */ (document.getElementById("panel"));
const range = /** @type {HTMLInputElement} */ (document.getElementById("width"));
const readout = /** @type {HTMLElement} */ (document.getElementById("readout"));
range.addEventListener("input", () => {
  panel.style.setProperty("--dynamic-esd-panel-w", `${range.value}px`);
  readout.textContent = `${range.value}px`;
});
panel.style.setProperty("--dynamic-esd-panel-w", `${range.value}px`);
for (const button of document.querySelectorAll("[data-theme-choice]"))
  button.addEventListener("click", () => {
    const value = /** @type {HTMLElement} */ (button).getAttribute("data-theme-choice") ?? "dark";
    document.documentElement.setAttribute("data-theme", value);
    widget.setTheme(value);
  });
document.documentElement.setAttribute("data-theme", "dark");
