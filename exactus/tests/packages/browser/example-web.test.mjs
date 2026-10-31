import assert from "node:assert/strict";
import test from "node:test";
import {
	browserTest,
} from "../../common/browser.mjs";
test("browser example binds every control", async t => {
	await browserTest(t, async (page, url) => {
		await page.addInitScript(() => {
			globalThis.opened = [];
			globalThis.wasClosed = false;
			globalThis.open = (target, name) => {
				globalThis.opened.push([String(target), String(name)]);
				return null;
			};
			globalThis.close = () => {
				globalThis.wasClosed = true;
			};
		});
		await page.goto(
			`${url}/exactus/tests/packages/browser/example-fixture.html`,
		);
		assert.equal(
			await page.evaluate(() => globalThis.browserExample.log.entries.length),
			0,
		);
		await page.click("#log");
		await page.click("#log");
		assert.equal(
			await page.evaluate(
				() => document.getElementById("events")?.textContent,
			),
			"event\nevent",
		);
		await page.click("#clear");
		assert.equal(
			await page.evaluate(
				() => document.getElementById("events")?.textContent,
			),
			"",
		);
		await page.click("#open");
		assert.deepEqual(
			await page.evaluate(() => globalThis.opened),
			[["about:blank", "_blank"]],
		);
		await page.click("#close");
		assert.equal(await page.evaluate(() => globalThis.wasClosed), true);
	});
});
test("browser example reports missing controls", async t => {
	await browserTest(t, async (page, url) => {
		/** @type {Error[]} */
		const errors = [];
		page.on("pageerror", (/** @type {Error} */ error) =>
			errors.push(error),
		);
		await page.goto(
			`${url}/exactus/tests/packages/browser/example-broken.html`,
		);
		assert.ok(
			errors.some(error =>
				error.message.includes("Required element not found: #open")
			),
		);
		assert.equal(
			await page.evaluate(
				() => /** @type {any} */ (globalThis).browserExample,
			),
			undefined,
		);
	});
});
test("browser example getElement rejects unknown selectors", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(
			`${url}/exactus/tests/packages/browser/example-fixture.html`,
		);
		const message = await page.evaluate(() => {
			try {
				globalThis.browserExample.getElement("#missing");
				return "";
			} catch (error) {
				return error instanceof Error ? error.message : String(error);
			}
		});
		assert.equal(message, "Required element not found: #missing");
	});
});
