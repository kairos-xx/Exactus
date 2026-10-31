import "../../../packages/extended_selector/examples/web/editor.js";
/**
 * Unwrap a nullable demo lookup inside page evaluations.
 *
 * @param {any} value Lookup result.
 * @returns {any} The same value, asserted present.
 * @throws {Error} When the lookup is missing.
 */
const must = value => {
	if (value === null || value === undefined)
		throw new Error("missing required element");
	return value;
};
globalThis.must = must;
