import assert from "node:assert/strict";
import test from "node:test";
import {
	browserTest,
} from "../../../../common/browser.mjs";
/** Root of the fixtures served by the harness. */
const BASE = "/exactus/tests/packages/widgets/widget_selector/demo";
test("demo page mounts widgets and binds its controls", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${BASE}/fixture.html`);
		await page.waitForFunction(
			() => document.documentElement.getAttribute("data-theme") === "dark",
		);
		assert.match(
			await page.locator("#expression").evaluate(
				(/** @type {HTMLInputElement} */ element) => element.value,
			),
			/has\(\.card/,
		);
		assert.match(
			await page.locator("#checks").evaluate(
				(/** @type {HTMLInputElement} */ element) => element.value,
			),
			/:hovr/,
		);
		await page.locator("#width").evaluate(
			(/** @type {HTMLInputElement} */ element) => {
				element.value = "640";
				element.dispatchEvent(new Event("input", {bubbles: true}));
			},
		);
		assert.equal(
			await page.locator("#readout").textContent(),
			"640px",
		);
		assert.equal(
			await page.locator("#panel").evaluate(
				(/** @type {HTMLElement} */ element) =>
					element.style.getPropertyValue("--dynamic-esd-panel-w"),
			),
			"640px",
		);
		await page.click('[data-theme-choice="light"]');
		assert.equal(
			await page.evaluate(
				() => document.documentElement.getAttribute("data-theme"),
			),
			"light",
		);
		await page.click("#plain-choice");
		assert.equal(
			await page.evaluate(
				() => document.documentElement.getAttribute("data-theme"),
			),
			"dark",
		);
	});
});
test("demo host reports stats, picks, and highlights", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${BASE}/host-fixture.html`);
		await page.waitForFunction(() => globalThis.hostReady === true);
		const stats = await page.evaluate(() => globalThis.demoHost.stats(".card"));
		assert.ok(typeof stats === "object");
		const cleared = await page.evaluate(
			() =>
				new Promise(done => {
					globalThis.demoHost.highlight("", done);
				}),
		);
		assert.deepEqual(cleared, {count: 0});
		const found = await page.evaluate(
			() =>
				new Promise(done => {
					globalThis.demoHost.highlight(".card", done);
				}),
		);
		assert.equal(found.count, 2);
		const bad = await page.evaluate(
			() =>
				new Promise(done => {
					globalThis.demoHost.highlight("(((", done);
				}),
		);
		assert.equal(bad.count, 0);
		const picked = await page.evaluate(
			() =>
				new Promise(done => {
					globalThis.demoHost.pick((/** @type {any} */ result) => {
						done(result);
					});
					document.getElementById("unique")?.dispatchEvent(
						new MouseEvent("click", {bubbles: true}),
					);
				}),
		);
		assert.equal(picked.selector, "#unique");
		assert.ok(picked.alternatives.length >= 2);
		assert.equal(picked.element.tag, "div");
		assert.equal(
			await page.evaluate(
				() => document.body.hasAttribute("data-picking"),
			),
			false,
		);
		const outside = await page.evaluate(
			() =>
				new Promise(done => {
					globalThis.demoHost.pick(() => {
						done("picked");
					});
					document.getElementById("layer")?.dispatchEvent(
						new MouseEvent("click", {bubbles: true}),
					);
					setTimeout(() => {
						done("ignored");
					}, 50);
				}),
		);
		assert.equal(outside, "ignored");
		const failing = await page.evaluate(async () => {
			const module = await import(
				"../../../../../packages/widgets/widget_selector/" +
					"examples/web/demo-host.js"
			);
			return new Promise(done => {
				const host = module.createDemoHost({
					engine: {
						query: () => {
							throw new Error("engine down");
						},
						stats: async () => ({count: 0}),
					},
					stage: globalThis.must(document.getElementById("stage")),
					layer: globalThis.must(document.getElementById("layer")),
				});
				host.pick((/** @type {any} */ result) => {
					done(result);
				});
				globalThis.must(document.querySelector(".plain")).dispatchEvent(
					new MouseEvent("click", {bubbles: true}),
				);
			});
		});
		assert.ok(
			failing.alternatives.every(
				(/** @type {any} */ alt) => alt.matches === 0,
			),
		);
		assert.equal(failing.selector, "span.plain");
		const unlabeled = await page.evaluate(
			() =>
				new Promise(done => {
					const ghost = document.createElement("em");
					document.getElementById("stage")?.append(ghost);
					globalThis.demoHost.pick((/** @type {any} */ result) => {
						done(result);
					});
					ghost.dispatchEvent(new MouseEvent("click", {bubbles: true}));
				}),
		);
		assert.equal(unlabeled.selector, "em");
	});
});
test("widget editor wrapper adapts the widget contract", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${BASE}/wrapper-fixture.html`);
		await page.waitForFunction(() => globalThis.wrapperReady === true);
		const result = await page.evaluate(() => {
			const target = /** @type {HTMLTextAreaElement} */ (
				document.getElementById("target")
			);
			/** @type {string[]} */
			const changes = [];
			const editor = new globalThis.EditorClass(target, {
				selectors: ["saved-card"],
				variables: () => [{path: "a"}],
				expected: () => 1,
				host: {highlight: () => {}},
				theme: "dark",
				multiple: true,
				startAsText: true,
				label: "Custom label",
			});
			editor.addEventListener("change", () => changes.push("change"));
			editor.value = "and(.a, .b)";
			const read = editor.value;
			const engineless = new globalThis.EditorClass(
				document.createElement("textarea"),
			);
			engineless.setEngine({marker: true});
			return {
				read,
				changes: changes.length,
				engine: engineless.options.engine.marker,
			};
		});
		assert.equal(result.read, "and(.a, .b)");
		assert.ok(result.changes >= 0);
		assert.equal(result.engine, true);
	});
});
