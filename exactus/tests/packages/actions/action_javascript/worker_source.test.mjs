import assert from "node:assert/strict";
import test from "node:test";
import {
	buildWorkerSource,
	workerMain,
} from "../../../../packages/actions/action_javascript/worker_source.js";
/**
 * @typedef {object} DoneResult
 * @property {string} status Completion status.
 * @property {boolean} [jsonSafe] JSON-safety flag.
 * @property {string | null} [json] Serialized result.
 * @property {{name: string, message: string}} [error] Error payload.
 * @property {unknown} [value] Raw result value.
 */
/**
 * @typedef {object} WorkerMessage
 * @property {string} type Message kind.
 * @property {any} [entry] Console entry payload.
 * @property {DoneResult} [result] Done result payload.
 */
/**
 * Install a fake worker scope and return its posted messages.
 *
 * @returns {{messages: WorkerMessage[],
 *   listeners: Map<string, ((event?: any) => void)[]>,
 *   run: (data: object) => unknown}} Scope harness.
 */
const harness = () => {
	/** @type {WorkerMessage[]} */
	const messages = [];
	/** @type {Map<string, ((event?: any) => void)[]>} */
	const listeners = new Map();
	const scope = {
		postMessage: (/** @type {WorkerMessage} */ message) => {
			messages.push(message);
		},
		/** @type {null | ((event: {data: object}) => unknown)} */
		onmessage: null,
		addEventListener: (
			/** @type {string} */ type,
			/** @type {(event?: any) => void} */ listener,
		) => {
			const list = listeners.get(type) ?? [];
			list.push(listener);
			listeners.set(type, list);
		},
	};
	globalThis.self = /** @type {typeof globalThis.self} */ (
		/** @type {unknown} */ (scope)
	);
	workerMain();
	return {
		messages,
		listeners,
		run: data => scope.onmessage?.({ data }),
	};
};
/**
 * Extract the single done message from a run.
 *
 * @param {WorkerMessage[]} messages Posted messages.
 * @returns {DoneResult} The done message result.
 */
const done = messages => {
	const message = messages.find(entry => entry.type === "done");
	assert.ok(message?.result, "expected a done message");
	return message.result;
};
/**
 * Extract console entry payloads from posted messages.
 *
 * @param {WorkerMessage[]} messages Posted messages.
 * @returns {any[]} Console entry payloads.
 */
const entries = messages =>
	messages.filter(entry => entry.type === "entry").map(entry => entry.entry);
test("buildWorkerSource emits the stringified runtime", () => {
	const source = buildWorkerSource();
	assert.equal(source.startsWith('"use strict";'), true);
	assert.equal(source.includes("AsyncFunction"), true);
	assert.equal(source.includes("workerMain") || source.includes("onmessage"), true);
});
test("auto mode returns the final expression", async () => {
	const { messages, run } = harness();
	await run({ code: "1 + 1", mode: "auto" });
	const result = done(messages);
	assert.equal(result.status, "ok");
	assert.equal(result.jsonSafe, true);
	assert.equal(JSON.parse(result.json ?? "null"), 2);
});
test("auto mode splits head statements from the tail", async () => {
	const { messages, run } = harness();
	await run({ code: "const a = 4;\nconst b = 5;\na * b", mode: "auto" });
	assert.equal(JSON.parse(done(messages).json ?? "null"), 20);
});
test("auto mode splits the tail after a semicolon", async () => {
	const { messages, run } = harness();
	await run({ code: "let a = 2; a * 3", mode: "auto" });
	assert.equal(JSON.parse(done(messages).json ?? "null"), 6);
});
test("expression mode evaluates a single expression", async () => {
	const { messages, run } = harness();
	await run({ code: "({ nested: [1, 2] })", mode: "expression" });
	const result = done(messages);
	assert.deepEqual(JSON.parse(result.json ?? "null"), { nested: [1, 2] });
});
test("statements mode reports an undefined result", async () => {
	const { messages, run } = harness();
	await run({ code: "const a = 1; a + 1", mode: "statements" });
	const result = done(messages);
	assert.equal(result.status, "ok");
	assert.equal(result.jsonSafe, false);
});
test("playback mode awaits a produced function and compiles bodies", async () => {
	const { messages, run } = harness();
	await run({ code: "async () => 42", mode: "playback" });
	assert.equal(JSON.parse(done(messages).json ?? "null"), 42);
	const second = harness();
	await second.run({ code: "return 7", mode: "playback" });
	assert.equal(JSON.parse(done(second.messages).json ?? "null"), 7);
});
test("console methods post entries and clear forwards", async () => {
	const { messages, run } = harness();
	await run({
		code: "console.log('hello'); console.warn('careful'); console.clear(); 1",
		mode: "auto",
	});
	const logged = entries(messages);
	assert.equal(logged.length, 2);
	assert.equal(logged[0].level, "log");
	assert.equal(logged[1].level, "warn");
	assert.equal(
		messages.some(message => message.type === "clear"),
		true,
	);
});
test("flow and exactus expose context ids and variable accessors", async () => {
	const { messages, run } = harness();
	await run({
		code: [
			"const seen = [",
			"  __EXACTUS_FLOW__.id, __EXACTUS_FLOW__.flowId,",
			"  __EXACTUS_FLOW__.actionId, __EXACTUS_FLOW__.runId,",
			"  exactus.vars.get('x'), exactus.vars.has('x'),",
			"  exactus.vars.set('y', 3), exactus.vars.get('y'),",
			"  exactus.vars.metadata('x').type, __EXACTUS_FLOW__.vars.x,",
			"]",
			"seen",
		].join("\n"),
		mode: "auto",
		variables: { x: 9 },
		context: {
			flow: { id: "f1" },
			action: { id: "a1" },
			run: { id: "r1" },
			project: { name: "p" },
		},
	});
	assert.deepEqual(
		JSON.parse(done(messages).json ?? "null"),
		["f1", "f1", "a1", "r1", 9, true, 3, 3, "number", 9],
	);
});
test("missing variables warn and assert throws AssertionError", async () => {
	const { messages, run } = harness();
	await run({ code: "exactus.vars.get('nope'); 1", mode: "auto" });
	const warned = entries(messages).find(entry => entry.level === "warn");
	assert.ok(warned.parts[0].text?.includes("nope") || JSON.stringify(warned.parts).includes("nope"));
	const second = harness();
	await second.run({ code: "exactus.assert(false, 'custom fail')", mode: "auto" });
	const result = done(second.messages);
	assert.equal(result.status, "error");
	assert.equal(result.error?.name, "AssertionError");
	assert.equal(result.error?.message, "custom fail");
});
test("page-only exactus members reject in the preview", async () => {
	const { messages, run } = harness();
	await run({ code: "exactus.page", mode: "auto" });
	const result = done(messages);
	assert.equal(result.status, "error");
	assert.equal(
		result.error?.message.includes("only available during playback"),
		true,
	);
});
test("thrown errors map to done.error with a value", async () => {
	const { messages, run } = harness();
	await run({ code: "throw new Error('boom')", mode: "auto" });
	const result = done(messages);
	assert.equal(result.status, "error");
	assert.equal(result.error?.name, "Error");
	assert.equal(result.error?.message, "boom");
	assert.ok(result.value);
	const second = harness();
	await second.run({ code: "throw 'raw string'", mode: "auto" });
	assert.equal(done(second.messages).error?.name, "Uncaught");
});
test("unhandled rejections log an error entry", async () => {
	const { messages, listeners, run } = harness();
	await run({ code: "1", mode: "auto" });
	const handlers = listeners.get("unhandledrejection");
	assert.ok(handlers?.length);
	handlers?.[0]?.({ reason: new Error("late failure") });
	const logged = entries(messages).find(entry => entry.level === "error");
	assert.ok(logged);
});
test("output truncates after the entry cap", async () => {
	const { messages, run } = harness();
	await run({
		code: "for (let i = 0; i < 1005; i += 1) console.log(i); 1",
		mode: "auto",
	});
	const posted = entries(messages);
	assert.equal(posted.length, 1001);
	const last = posted.at(-1);
	assert.equal(
		JSON.stringify(last?.parts).includes("truncated"),
		true,
	);
});
test("non-serializable results are reported as not json-safe", async () => {
	const { messages, run } = harness();
	await run({ code: "const a = {}; a.self = a; a", mode: "auto" });
	const result = done(messages);
	assert.equal(result.status, "ok");
	assert.equal(result.jsonSafe, false);
});
test("oversized json payloads are nulled", async () => {
	const { messages, run } = harness();
	await run({ code: "'x'.repeat(1000001)", mode: "auto" });
	const result = done(messages);
	assert.equal(result.jsonSafe, true);
	assert.equal(result.json, null);
});
test("compile failures report an error result", async () => {
	const { messages, run } = harness();
	await run({ code: "this is (((not js", mode: "expression" });
	const result = done(messages);
	assert.equal(result.status, "error");
	assert.ok((result.error?.message.length ?? 0) > 0);
});
