/** Verify viewport capture and restoration after screenshot failures. */
import assert from "node:assert/strict";
import test from "node:test";
import {
	SnapshotCapture
} from "../../../../packages/screenshot/js/capture_screen.js";
import {
	browserTest
} from "../../../common/browser.mjs";
test("capture rejects missing viewports and elements before mutating a page", async () => {
	await assert.rejects(new SnapshotCapture(
		/** @type {any} */
		({
			viewportSize: () => null,
		}), "body", ).capture(), /configured viewport/, );
	await assert.rejects(new SnapshotCapture(
		/** @type {any} */
		({
			viewportSize: () => ({
				width: 390,
				height: 900,
			}),
			$: async () => null,
		}), "missing", ).capture(), /not found/, );
});
test("nested overflow is expanded for capture and restored even after failure", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}/exactus/tools/actions/examples/web/index.html`);
		const result = await page.evaluate(async ( /** @type {string} */ base) => {
			const {
				SnapshotCapture: Capture
			} = await import(`${base}/exactus/packages/screenshot/js/capture_screen.js`);
			document.body.innerHTML = '<div id="outer" style="height:40px;overflow:hidden"><div id="inner" style="height:20px;overflow:auto"><p style="height:200px">Full content</p></div></div>';
			const outer = /** @type {HTMLElement} */ (document.querySelector("#outer"));
			const original = outer.getAttribute("style");
			let expanded = false;
			let size = {
				width: innerWidth,
				height: innerHeight,
			};
			const adapter = {
				viewportSize: () => size,
				$: async ( /** @type {string} */ selector) => ({
					evaluate: async ( /** @type {any} */ fn) => fn(document.querySelector(selector)),
				}),
				evaluate: async ( /** @type {any} */ fn) => fn(),
				setViewportSize: async ( /** @type {any} */ next) => {
					size = next;
				},
				screenshot: async () => {
					expanded = outer.style.getPropertyValue("overflow-y") === "visible";
					return [1, 2, 3];
				},
			};
			const capture = new Capture(adapter, "#outer");
			const bytes = await capture.capture();
			const restored = outer.getAttribute("style") === original;
			adapter.screenshot = async () => {
				throw new Error("capture failed");
			};
			let failed = false;
			try {
				await capture.capture();
			} catch {
				failed = true;
			}
			return {
				bytes,
				expanded,
				restored,
				failed,
				finalStyle: outer.getAttribute("style"),
				original,
				stash: /** @type {any} */ (window).__snapshotCapture,
				size,
			};
		}, url);
		assert.deepEqual(result.bytes, [1, 2, 3]);
		assert.ok(result.expanded && result.restored && result.failed);
		assert.equal(result.finalStyle, result.original);
		assert.equal(result.stash, undefined);
		assert.deepEqual(result.size, {
			width: 1440,
			height: 900,
		});
	});
});
