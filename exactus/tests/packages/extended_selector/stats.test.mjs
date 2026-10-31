/** Exercise per-node match statistics. */
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
	await page.evaluate(() => {
		document.body.insertAdjacentHTML("beforeend", '<section id="sx"><div class="card"><button>Save</button></div><div class="card"><button disabled>Off</button></div><div class="card" hidden><button>Hid</button></div></section>', );
	});
};
test("stats returns totals and one count per tree node", t => browserTest(t, async (page, url) => {
	await open(page, url);
	const s = await page.evaluate(() => globalThis.engine.stats("and(.card, has(.card, button))"), );
	assert.equal(s.count, 3);
	assert.deepEqual(s.nodes.map(( /** @type {any} */ n) => [n.path, n.label, n.kind, n.count]),
		[
			[
				[], "and(", "operator", 3
			],
			[
				[0], ".card", "class", 3
			],
			[
				[1], "has(", "operator", 3
			],
			[
				[1, 0], ".card", "class", 3
			],
			[
				[1, 1], "button", "tag", 3
			],
		], );
	assert.equal(s.visible, 2);
	assert.equal(s.enabled, 3);
	assert.equal(s.first.tag, "div");
	assert.equal(s.truncated, false);
	assert.ok(Number.isFinite(s.elapsedMs));
}));
test("stats caps the scanned universe", t => browserTest(t, async (page, url) => {
	await open(page, url);
	const s = await page.evaluate(() => {
		const host = document.createElement("div");
		host.innerHTML = "<i class=\"bulk\"></i>".repeat(10000);
		document.body.append(host);
		return globalThis.engine.stats(".bulk", {
			limit: 2000
		});
	});
	assert.equal(s.truncated, true);
	assert.equal(s.scanned, 2000);
	assert.ok(s.count <= 2000);
}));
