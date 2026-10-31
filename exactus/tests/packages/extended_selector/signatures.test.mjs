/** Exercise the public operator signatures and predicate types of the engine. */
import assert from "node:assert/strict";
import {
	readFile
} from "node:fs/promises";
import test from "node:test";
import {
	browserTest
} from "../../common/browser.mjs";
/** Open the fixture page and wait until the engine module has loaded.
 * @param {any} page Browser page from browserTest.
 * @param {string} url Origin of the repository server.
 * @returns {Promise<void>}
 */
const open = async (page, url) => {
	await page.goto(`${url}/exactus/tests/packages/extended_selector/fixture.html`);
	await page.waitForFunction(() => globalThis.engineReady === true);
};
test("signatures describe each operator by role", t => browserTest(t, async (page, url) => {
	await open(page, url);
	const result = await page.evaluate(() => {
		const {
			SIGNATURES,
			CAPABILITIES
		} = globalThis.ExtendedSelector;
		/** Require one named operator signature to exist.
		 * @param {string} name Operator name.
		 * @returns {{min:number, max:number, roles:string[], optionalFrom:number, kinds:string[], variadicRole?:string, summary:string}}
		 * @throws {Error} When no signature exists for name.
		 */
		const signature = name => {
			const found = SIGNATURES[name];
			if (!found)
				throw new Error(`missing signature ${name}`);
			return found;
		};
		return {
			has: signature("has"),
			childRoles: signature("child").roles,
			frozen: Object.isFrozen(SIGNATURES),
			andVariadic: signature("and").variadicRole,
			childrenVariadic: signature("children").variadicRole,
			any: signature("any").roles,
			pseudo: signature("pseudo").roles,
			near: signature("near"),
			types: {
				visible: Reflect.get(CAPABILITIES.predicateTypes, "visible"),
				innerText: Reflect.get(CAPABILITIES.predicateTypes, "innerText"),
				width: Reflect.get(CAPABILITIES.predicateTypes, "width"),
			},
		};
	});
	assert.equal(result.has.min, 2);
	assert.equal(result.has.max, 2);
	assert.deepEqual(result.has.roles, ["base", "condition"]);
	assert.deepEqual(result.childRoles, ["base", "index", "condition"]);
	assert.equal(result.frozen, true);
	assert.equal(result.andVariadic, "expression");
	assert.equal(result.childrenVariadic, "child");
	assert.deepEqual(result.any, ["base", "relation", "condition"]);
	assert.deepEqual(result.pseudo, ["base", "pseudo", "condition"]);
	assert.deepEqual(result.near.roles, ["base", "reference", "distance"]);
	assert.deepEqual(result.types, {
		visible: "boolean",
		innerText: "text",
		width: "number",
	});
}));
test("lint arity messages are unchanged after the table became public", t => browserTest(t, async (page, url) => {
	await open(page, url);
	const golden = JSON.parse(await readFile(new URL("./fixtures/lint-arity.golden.json", import.meta.url), "utf8", ), );
	const rows = await page.evaluate(
		( /** @type {string[]} */ list) => list.map(expression => {
			const found = globalThis.engine.lint(expression);
			return {
				expression,
				messages: found.map(( /** @type {{message:string}} */ x) => x.message),
				codes: found.map(( /** @type {{code:string}} */ x) => x.code),
			};
		}), golden.map(( /** @type {{expression:string}} */ row) => row.expression), );
	assert.deepEqual(rows, golden);
}));
