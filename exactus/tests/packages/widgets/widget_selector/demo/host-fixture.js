import ExtendedSelector from "../../../../../packages/extended_selector/editor/extended-selector.js";
import { createDemoHost } from "../../../../../packages/widgets/widget_selector/examples/web/demo-host.js";
/**
 * Unwrap a nullable fixture lookup or fail the page load.
 *
 * @param {any} value Lookup result.
 * @returns {any} The same value, asserted present.
 * @throws {Error} When the lookup is missing.
 */
const must = value => {
	if (value === null || value === undefined)
		throw new Error("demo host fixture incomplete");
	return value;
};
const stage = /** @type {HTMLElement} */ (must(document.getElementById("stage")));
const layer = /** @type {HTMLElement} */ (must(document.getElementById("layer")));
globalThis.hostReady = true;
globalThis.demoHost = createDemoHost({
	engine: new ExtendedSelector(document),
	stage,
	layer,
});
globalThis.must = must;
