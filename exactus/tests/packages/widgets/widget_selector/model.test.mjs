import assert from "node:assert/strict";
import test from "node:test";
import {
	enclosing,
	matchingClose,
	serialize,
	slotsOf,
	tokenize,
	variableKind,
} from "../../../../packages/widgets/widget_selector/selector-tree.js";
import {
	createValidator
} from "../../../../packages/widgets/widget_selector/validator.js";
for (const text of ["", " div.card#main > * + a:hover ~ span::before || section, footer ", "has(div, child(.item, 2))", "{{device/width}} {{count = 3}} {{unfinished", '[data-value="quoted ] and \\" text"]', "[data-value='quoted ] text']", '[extended-selector="saved"] [width={{device/width}}] [text="{{literal}}"]', "[unfinished", ":not(.item) ::part(button) : :: . # 123$", ])
	test(`selector token spans round-trip ${JSON.stringify(text)}`, () => {
		const tokens = tokenize(text);
		assert.equal(serialize(tokens), text);
		for (const token of tokens) assert.equal(text.slice(token.start, token.end), token.text);
	});
test("variable and attribute tokens preserve their semantic families", () => {
	assert.equal(variableKind("device/width"), "env");
	assert.equal(variableKind("env/locale"), "env");
	assert.equal(variableKind("target/url"), "env");
	assert.equal(variableKind("flow/count"), "flow");
	const tokens = tokenize('[extended-selector="saved"] [width={{device/width}}] {{count = 3}}');
	assert.equal(tokens[0]?.kind, "saved");
	assert.equal(tokens[0]?.name, "saved");
	assert.deepEqual(tokens.filter(token => token.type === "leaf").map(token => token.kind), ["saved", "env", "flow"]);
	assert.equal(tokens.at(-1)?.label, "count = 3");
});
test("enclosing frames and required slots track nested arguments", () => {
	const text = "has(div, child(.item, ))";
	const tokens = tokenize(text);
	assert.equal(matchingClose(tokens, 0), tokens.length - 1);
	assert.equal(matchingClose(tokenize("has(div"), 0), -1);
	assert.equal(enclosing(tokens, 0), null);
	const frame = enclosing(tokens, text.indexOf("))"));
	assert.equal(frame?.open.name, "child");
	assert.equal(frame?.arg, 1);
	assert.equal(enclosing(tokens, text.length), null);
	const signatures = {
		has: {
			min: 2,
			roles: ["base", "condition"]
		},
		child: {
			min: 3,
			roles: ["base", "index", "condition"]
		},
	};
	assert.deepEqual(slotsOf(tokens, signatures).map(slot => slot.role), ["index", "condition"]);
	assert.deepEqual(slotsOf(tokenize("has( "), signatures).map(slot => slot.role), ["base", "condition"]);
	assert.deepEqual(slotsOf(tokenize("unknown()"), signatures), []);
	assert.equal(slotsOf(tokenize(") ,"), signatures).length, 0);
	assert.equal(slotsOf(tokenize("empty("), {
		empty: {
			min: 1,
			roles: []
		}
	})[0]?.role, "argument");
});
test("validator distinguishes idle, valid, warning and error and steps problems", () => {
	const results = new Set();
	const warning = {
		code: "warning",
		message: "warning",
		offset: 0,
		length: 1,
		line: 1,
		column: 1,
		severity: "warning"
	};
	const error = {
		...warning,
		code: "error",
		severity: "error"
	};
	const validator = createValidator({
		engine: {
			lint: (text = "") => new Map([["warning", [warning]], ["error", [error, warning]]]).get(text) ?? []
		},
		onResult: result => results.add(result.state),
	});
	assert.equal(validator.current().state, "idle");
	assert.equal(validator.step(1), null);
	assert.equal(validator.flush(" ").state, "idle");
	assert.equal(validator.flush("div").state, "valid");
	assert.equal(validator.flush("warning").warnings, 1);
	assert.equal(validator.current().state, "warning");
	assert.equal(validator.flush("error").errors, 1);
	assert.equal(validator.current().state, "error");
	assert.equal(validator.step(1)?.code, "warning");
	assert.equal(validator.step(1)?.code, "error");
	assert.equal(validator.step(-1)?.code, "warning");
	assert.deepEqual([...results], ["idle", "valid", "warning", "error"]);
	validator.destroy();
	const withoutEngine = createValidator({
		engine: null,
		onResult: () => {}
	});
	assert.equal(withoutEngine.flush("div").state, "valid");
	withoutEngine.destroy();
});
test("multiline validator rebases diagnostics and fixes across blank lines", () => {
	const validator = createValidator({
		engine: {
			lint: () => [{
				code: "bad",
				message: "bad",
				severity: "error",
				offset: 1,
				length: 1,
				line: 1,
				column: 2,
				suggestion: {
					offset: 1,
					length: 1,
					text: "x"
				}
			}]
		},
		multiple: true,
		onResult: () => {},
	});
	validator.flush("ab\n\ncd");
	const result = validator.current();
	assert.equal(result.errors, 2);
	assert.deepEqual(result.diagnostics.map(item => [item.offset, item.line, item.suggestion?.offset]), [
		[1, 1, 1],
		[5, 3, 5]
	]);
	validator.destroy();
});
test("debounce replaces pending work and destroy cancels it", t => {
	t.mock.timers.enable({
		apis: ["setTimeout"]
	});
	const states = new Set();
	const lint = t.mock.fn((text = "") => {
		assert.equal(typeof text, "string");
		return [];
	});
	const validator = createValidator({
		engine: {
			lint
		},
		delayMs: 20,
		onResult: result => states.add(result.state)
	});
	validator.schedule("old");
	validator.schedule("new");
	assert.equal(validator.current().state, "checking");
	assert.equal(lint.mock.callCount(), 0);
	t.mock.timers.tick(20);
	assert.equal(lint.mock.callCount(), 1);
	assert.equal(lint.mock.calls[0]?.arguments[0], "new");
	assert.equal(validator.current().state, "valid");
	validator.schedule("cancelled");
	validator.destroy();
	t.mock.timers.tick(20);
	assert.equal(lint.mock.callCount(), 1);
	assert.deepEqual([...states], ["checking", "valid"]);
});
