import ExtendedSelector from "../../../packages/extended_selector/editor/extended-selector.js";
import ExtendedSelectorEditor from "../../../packages/extended_selector/editor/extended-selector-editor.js";
/**
 * Unwrap a nullable fixture lookup or fail the page load.
 *
 * @param {any} value Lookup result.
 * @returns {any} The same value, asserted present.
 * @throws {Error} When the lookup is missing.
 */
const must = value => {
	if (value === null || value === undefined)
		throw new Error("editor fixture incomplete");
	return value;
};
const target = /** @type {HTMLTextAreaElement} */ (
	must(document.getElementById("target"))
);
globalThis.engine = new ExtendedSelector(document);
globalThis.editor = new ExtendedSelectorEditor(target, {
	engine: globalThis.engine,
	selectors: ["saved-one", "saved-two"],
});
globalThis.Editor = ExtendedSelectorEditor;
globalThis.editorReady = true;
globalThis.must = must;
