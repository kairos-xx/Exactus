/** Exercise {{variables}}, frozen values, escapes and widened saved names. */
import assert from "node:assert/strict";
import test from "node:test";
import {
	browserTest
} from "../../common/browser.mjs";
/**
 * Open the fixture page and wait for the engine.
 * @param {any} page Playwright page.
 * @param {string} url Server base URL.
 * @returns {Promise<void>}
 */
const open = async (page, url) => {
	await page.goto(`${url}/exactus/tests/packages/extended_selector/fixture.html`);
	await page.waitForFunction(() => globalThis.engineReady === true);
};
test("substitute renders typed values by position", t => browserTest(t, async (page, url) => {
	await open(page, url);
	const r = await page.evaluate(() => {
		const E = globalThis.ExtendedSelector;
		return {
			number: E.substitute("[width >= {{device/width}}]", {
				"device/width": 390
			}),
			text: E.substitute("[innerText = {{label}}]", {
				label: 'Save "all"'
			}),
			bool: E.substitute("[visible = {{on}}]", {
				on: true
			}),
			quoted: E.substitute('[innerText*="{{label}}"]', {
				label: 'a"b'
			}),
			frozen: E.substitute("[width >= {{device/width=390}}]", {}),
			escaped: E.substitute("[innerText=\"\\{{x}}\"]", {
				x: 1
			}),
			missing: E.substitute("[width >= {{x}}]", {}),
			open: E.substitute('[innerText="a {{ b"]', {
				b: 1
			}),
		};
	});
	assert.deepEqual(r.number, {
		text: "[width >= 390]",
		missing: []
	});
	assert.equal(r.text.text, '[innerText = "Save \\"all\\""]');
	assert.equal(r.bool.text, "[visible = true]");
	assert.equal(r.quoted.text, '[innerText*="a\\"b"]');
	assert.equal(r.frozen.text, "[width >= 390]");
	assert.equal(r.escaped.text, '[innerText="{{x}}"]');
	assert.deepEqual(r.missing.missing, ["x"]);
	assert.equal(r.open.text, '[innerText="a {{ b"]');
}));
test("variables lists live and frozen occurrences and skips escapes", t => browserTest(t, async (page, url) => {
	await open(page, url);
	const list = await page.evaluate(() => globalThis.ExtendedSelector.variables('[a={{p/q}}][b={{w=390}}]["\\{{no}}"]{{ open', ), );
	assert.deepEqual(list.map(( /** @type {any} */ v) => [v.path, v.frozen, v.value]),
		[
			["p/q", false, undefined],
			["w", true, 390],
		], );
}));
test("lint treats variables as placeholders and keeps offsets", t => browserTest(t, async (page, url) => {
	await open(page, url);
	const r = await page.evaluate(() => ({
		ok: globalThis.engine.lint("[width >= {{device/width}}]"),
		bad: globalThis.engine.lint("[width >= {{device/width}"),
		offset: globalThis.engine.lint("has(.a, {{x}}.b")[0]?.offset,
	}));
	assert.deepEqual(r.ok, []);
	assert.equal(r.bad[0].offset, 0);
	assert.equal(r.offset, 3);
}));
test("query resolves variables and fails loudly when one is missing", t => browserTest(t, async (page, url) => {
	await open(page, url);
	const r = await page.evaluate(() => {
		const wide = globalThis.engine.query("[width >= {{w}}]", {
			variables: {
				w: 150
			}
		}).length;
		const frozen = globalThis.engine.query("[width >= {{w=150}}]").length;
		let error;
		try {
			globalThis.engine.query("[width >= {{w}}]");
		} catch (e) {
			const error_ = /** @type {{code?: unknown, message?: unknown}} */ (e);
			error = {
				code: error_.code,
				message: error_.message
			};
		}
		return {
			wide,
			frozen,
			error
		};
	});
	assert.ok(r.wide > 0);
	assert.equal(r.wide, r.frozen);
	assert.deepEqual(r.error, {
		code: "missing-variable",
		message: "No value for {{w}}."
	});
}));
test("saved selector names may contain slash and dot", t => browserTest(t, async (page, url) => {
	await open(page, url);
	const r = await page.evaluate(() => {
		const engine = new globalThis.ExtendedSelector(document);
		engine.define("group/save.button", "#ref");
		const hit = engine.query('[extended-selector="group/save.button"]').length;
		const bad = [];
		for (const name of ["1a", "a b", "/a"]) try {
			engine.define(name, "#ref");
		} catch {
			bad.push(name);
		}
		return {
			hit,
			bad
		};
	});
	assert.equal(r.hit, 1);
	assert.deepEqual(r.bad, ["1a", "a b", "/a"]);
}));
