/**
 * Demo harness for the ExtendedSelector structured editor.
 *
 * Binds an editor to a fixture page, runs expressions through the engine, and
 * exercises the element-registration API.
 *
 * @typedef {import("../../editor/extended-selector.js").SelectorDiagnostic} SelectorDiagnostic
 */
import ExtendedSelector from "../../editor/extended-selector.js";
import ExtendedSelectorEditor from "../../editor/extended-selector-editor.js";
const engine = new ExtendedSelector(document);
const area = /** @type {HTMLTextAreaElement | null} */ (
  document.querySelector("#expression")
);
const status = /** @type {HTMLElement | null} */ (
  document.querySelector("#status")
);
const cssResult = /** @type {HTMLElement | null} */ (
  document.querySelector("#css-result")
);
if (!area || !status || !cssResult) throw new Error("demo fixture incomplete");
const editor = new ExtendedSelectorEditor(area, {
  engine,
});
/**
 * Render the editor's current diagnostics into the status area.
 *
 * @returns {void}
 */
const update = () => {
  const diagnostics = editor.validate();
  status.textContent = diagnostics.length
    ? diagnostics
        .map(diagnostic => ExtendedSelector.formatDiagnostic(diagnostic))
        .join("\n\n")
    : "Valid";
};
editor.addEventListener("change", event => {
  const detail = /** @type {CustomEvent} */ (event).detail;
  const diagnostics = /** @type {SelectorDiagnostic[]} */ (
    detail.diagnostics ?? []
  );
  status.textContent = diagnostics.length
    ? diagnostics
        .map(diagnostic => ExtendedSelector.formatDiagnostic(diagnostic))
        .join("\n\n")
    : "Valid";
});
document.querySelector("#run")?.addEventListener("click", () => {
  try {
    const card = engine.queryOne(area.value);
    if (!card) throw new Error("No card matched.");
    ExtendedSelector.register(card, "card");
    if (!card.querySelector(":scope > svg"))
      card.insertAdjacentHTML(
        "beforeend",
        '<svg viewBox="0 0 16 16" aria-label="registered"><circle cx="8" cy="8" r="6" fill="currentColor"/></svg>',
      );
    const icons = document.querySelectorAll('[extended-selector="card"] > svg');
    cssResult.textContent = `card.register = ${JSON.stringify(
      ExtendedSelector.decorate(card).register,
    )}\n[extended-selector="card"] > svg → ${icons.length} match(es)`;
  } catch (error) {
    cssResult.textContent =
      error instanceof Error ? (error.stack ?? error.message) : String(error);
  }
});
document.querySelector("#clear")?.addEventListener("click", () => {
  document.querySelectorAll("[extended-selector]").forEach(element => {
    ExtendedSelector.unregister(element);
  });
  cssResult.textContent = "Registration cleared.";
});
update();
