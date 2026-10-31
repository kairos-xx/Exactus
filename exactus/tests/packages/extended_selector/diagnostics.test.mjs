/** Exercise diagnostic severity, narrow ranges, suggestions and roles. */
import assert from "node:assert/strict";
import test from "node:test";
import {
	browserTest
} from "../../common/browser.mjs";
/** Open the fixture page and wait until the engine module has loaded.
 * @param {any} page
 * @param {string} url
 * @returns {Promise<void>}
 */
const open = async (page, url) => {
	await page.goto(`${url}/exactus/tests/packages/extended_selector/fixture.html`);
	await page.waitForFunction(() => globalThis.engineReady === true);
};
/** Lint an expression with warnings enabled.
 * @param {any} page
 * @param {string} expression
 * @returns {Promise<any[]>}
 */
const lintAll = (page, expression) => page.evaluate(
	( /** @type {string} */ text) => globalThis.engine.lint(text, {
		warnings: true
	}), expression, );
test("an unknown pseudo-class is narrowed to its token with a suggestion", t => browserTest(t, async (page, url) => {
	await open(page, url);
	const found = await lintAll(page, "button:hovr");
	assert.equal(found.length, 1);
	assert.equal(found[0].code, "unknown-pseudo");
	assert.equal(found[0].severity, "error");
	assert.equal(found[0].offset, 6);
	assert.equal(found[0].length, 5);
	assert.deepEqual(found[0].suggestion, {
		offset: 6,
		length: 5,
		text: ":hover",
	});
}));
test("pseudo-elements and :visited are warnings, not errors", t => browserTest(t, async (page, url) => {
	await open(page, url);
	const element = await lintAll(page, "a::before");
	assert.equal(element.length, 1);
	assert.equal(element[0].code, "pseudo-element-unmatchable");
	assert.equal(element[0].severity, "warning");
	assert.match(element[0].message, /pseudo\(sel, "::before", expr\)/);
	const visited = await lintAll(page, ":visited");
	assert.equal(visited[0].code, "visited-unmatchable");
	assert.equal(visited[0].severity, "warning");
	const plain = await page.evaluate(() => [
		globalThis.engine.lint("a::before"),
		globalThis.engine.lint(":visited"),
	]);
	assert.deepEqual(plain, [
		[],
		[]
	]);
}));
test("arity problems name the first missing role", t => browserTest(t, async (page, url) => {
	await open(page, url);
	assert.equal((await lintAll(page, "has(.card)"))[0].role, "condition");
	assert.equal((await lintAll(page, "child(.a, 1)"))[0].role, "condition");
	assert.equal((await lintAll(page, "has(.a, .b, .c)"))[0].role, undefined);
}));
test("valid expressions have no diagnostics and old errors keep severity", t => browserTest(t, async (page, url) => {
	await open(page, url);
	assert.deepEqual(await lintAll(page, "and(.a, has(.b, .c))"), []);
	const open1 = await lintAll(page, ".card:not(");
	assert.equal(open1[0].code, "unclosed-delimiter");
	assert.equal(open1[0].severity, "error");
	const op = await lintAll(page, "hass(.a, .b)");
	assert.equal(op[0].code, "unknown-operator");
	assert.equal(op[0].suggestion.text, "has");
}));
