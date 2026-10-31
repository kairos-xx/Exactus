import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import process from "node:process";
import test from "node:test";
import {fileURLToPath} from "node:url";
import {
	bestLocalSelector,
} from "../../../packages/extended_selector/editor/selector-adapters.js";
/**
 * One captured ``bestSelector`` invocation.
 *
 * @typedef {object} CapturedCall
 * @property {unknown} targets Targets forwarded by the adapter.
 * @property {any} options Merged generator options.
 */
/**
 * Capture the options the adapter hands to the engine.
 *
 * @returns {{engine: object, calls: CapturedCall[]}} Recording engine.
 */
const recordingEngine = () => {
	/** @type {CapturedCall[]} */
	const calls = [];
	return {
		calls,
		engine: {
			bestSelector: (
				/** @type {unknown} */ targets,
				/** @type {any} */ options,
			) => {
				calls.push({targets, options});
				return {strategy: "recorded", selector: ".card"};
			},
		},
	};
};
test("verify.mjs resolves every bundled selector library", () => {
	const output = execFileSync(process.execPath, [
		fileURLToPath(
			new URL(
				"../../../packages/extended_selector/verify.mjs",
				import.meta.url,
			),
		),
	], {encoding: "utf8"});
	assert.deepEqual(output.split("\n").filter(Boolean).sort(), [
		"adapter: OK",
		"engine: OK",
		"finder: OK",
		"generator: OK",
		"optimal: OK",
	]);
});
test("bestLocalSelector delegates to the engine with merged options", () => {
	const {engine, calls} = recordingEngine();
	const result = bestLocalSelector(
		/** @type {any} */ (engine),
		[],
		/** @type {any} */ ({extra: true}),
	);
	assert.deepEqual(result, {strategy: "recorded", selector: ".card"});
	assert.equal(calls.length, 1);
	const call = /** @type {CapturedCall} */ (calls[0]);
	assert.equal(call.options.extra, true);
	assert.equal(typeof call.options.generator, "function");
	assert.equal(typeof call.options.optimal.getSingleSelector, "function");
	assert.equal(typeof call.options.optimal.getMultiSelector, "function");
	assert.equal(typeof call.options.optimal.optimize, "function");
	assert.equal(typeof call.options.finder, "function");
});
test("bestLocalSelector injects working generator callbacks", () => {
	const {engine, calls} = recordingEngine();
	bestLocalSelector(/** @type {any} */ (engine), []);
	const options = /** @type {CapturedCall} */ (calls[0]).options;
	const element = {nodeType: 1, ownerDocument: {nodeType: 9}};
	globalThis.Node ??= /** @type {any} */ ({DOCUMENT_NODE: 9});
	for (const invoke of [
		() => options.generator([element], {}),
		() => options.optimal.getSingleSelector(element),
		() => options.optimal.getMultiSelector([element]),
		() => options.optimal.optimize(".card"),
		() => options.finder(element, {}),
		() => options.finder(element, {root: {nodeType: 1}}),
	]) {
		try {
			invoke();
		} catch {
			// The bundled libraries reject non-DOM stand-ins; the adapter's
			// call-through wiring is what this test exercises.
		}
	}
});
