import assert from "node:assert/strict";
import test from "node:test";
import {
	browserTest,
} from "../../../common/browser.mjs";
/** Fixture page path served by the harness server. */
const PAGE = "/exactus/tests/packages/exactus_mcp/web/app-fixture.html";
/** Broken fixture missing required elements. */
const BROKEN = "/exactus/tests/packages/exactus_mcp/web/app-broken.html";
/**
 * Page predicate: an element's text contains a substring.
 *
 * @param {[string, string]} pair Element identifier and substring.
 * @returns {boolean} Whether the text contains the substring.
 */
const textContains = pair =>
	document.getElementById(pair[0])?.textContent?.includes(pair[1]) ??
	false;
/**
 * Page predicate: an element's text equals a string.
 *
 * @param {[string, string]} pair Element identifier and expected text.
 * @returns {boolean} Whether the text matches.
 */
const textIs = pair =>
	document.getElementById(pair[0])?.textContent === pair[1];
/**
 * Intercept the app's JSON endpoints with canned responses.
 *
 * @param {any} page Browser page.
 * @param {{status: any, activity: any, delay?: number}} bodies Response
 *   bodies or null for HTTP 500.
 * @returns {Promise<void>}
 */
const stubApi = async (page, bodies) => {
	const {status, activity, delay = 0} = bodies;
	await page.route("**/api/status", async (/** @type {any} */ route) => {
		if (delay)
			await new Promise(done => {
				setTimeout(done, delay);
			});
		await route.fulfill(
			status === null
				? {status: 500, body: "down"}
				: {contentType: "application/json", body: JSON.stringify(status)},
		);
	});
	await page.route("**/api/activity", (/** @type {any} */ route) =>
		route.fulfill(
			activity === null
				? {status: 500, body: "down"}
				: {contentType: "application/json", body: JSON.stringify(activity)},
		),
	);
};
/** Activity payload exercising every row branch. */
const ACTIVITY = {
	call_count: 3,
	active_calls: 1,
	phase: "serving",
	events: [
		{
			started_at: "2026-10-20T12:00:00Z",
			tool: "get_exactus_status",
			state: "done",
			duration_ms: 42,
			request: {method: "tools/call"},
			response: {ok: true},
		},
		{
			duration_ms: null,
		},
		null,
	],
};
test("app renders status and redacted activity", async t => {
	await browserTest(t, async (page, url) => {
		await stubApi(page, {
			status: {mcp_url: "https://tunnel.example/mcp"},
			activity: ACTIVITY,
		});
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(textContains, ["mcp-url", "tunnel"]);
		assert.equal(
			await page.locator("#service-phase").textContent(),
			"serving",
		);
		assert.equal(await page.locator("#total-calls").textContent(), "3");
		const rows = page.locator("#activity-rows tr");
		assert.equal(await rows.count(), 2);
		assert.match(await rows.nth(0).textContent(), /42 ms/);
		assert.match(await rows.nth(0).textContent(), /get_exactus_status/);
		assert.match(await rows.nth(1).textContent(), /In progress/);
		assert.match(await rows.nth(1).textContent(), /Unknown/);
		assert.match(await rows.nth(1).textContent(), /—/);
		assert.match(
			await page.locator("#activity-note").textContent(),
			/Secrets and raw report bodies are excluded/,
		);
	});
});
test("app renders the empty activity placeholder", async t => {
	await browserTest(t, async (page, url) => {
		await stubApi(page, {
			status: {mcp_url: "https://tunnel.example/mcp"},
			activity: {
				call_count: 0,
				active_calls: 0,
				phase: "idle",
				events: [],
			},
		});
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(
			() => document.getElementById("activity-rows")?.children.length === 1,
		);
		assert.match(
			await page.locator("#activity-rows").textContent(),
			/No MCP calls yet/,
		);
	});
});
test("app reports endpoint failures to the user", async t => {
	await browserTest(t, async (page, url) => {
		await stubApi(page, {status: null, activity: null});
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(textIs, ["mcp-url", "Address unavailable"]);
		assert.match(
			await page.locator("#copy-status").textContent(),
			/Reload after the public tunnel is ready/,
		);
		assert.match(
			await page.locator("#activity-note").textContent(),
			/Activity unavailable\. Try again\./,
		);
		await page.click("#refresh-activity");
		await page.waitForFunction(
			textIs,
			["activity-note", "Activity unavailable. Try again."],
		);
		await page.waitForTimeout(3200);
		assert.match(
			await page.locator("#activity-note").textContent(),
			/Live refresh paused/,
		);
	});
});
test("app rejects malformed API payloads", async t => {
	await browserTest(t, async (page, url) => {
		await stubApi(page, {
			status: {mcp_url: 42},
			activity: {events: "nope"},
		});
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(textIs, ["mcp-url", "Address unavailable"]);
		assert.match(
			await page.locator("#activity-note").textContent(),
			/Activity unavailable\. Try again\./,
		);
	});
});
test("app copies the endpoint through the clipboard", async t => {
	await browserTest(t, async (page, url) => {
		await page.addInitScript(() => {
			globalThis.copied = [];
			Object.defineProperty(globalThis.navigator, "clipboard", {
				value: {
					writeText: (/** @type {string} */ value) => {
						globalThis.copied.push(value);
						return Promise.resolve();
					},
				},
			});
		});
		await stubApi(page, {
			status: {mcp_url: "https://tunnel.example/mcp"},
			activity: {call_count: 0, active_calls: 0, phase: "ok", events: []},
			delay: 400,
		});
		await page.goto(`${url}${PAGE}`);
		await page.click("#copy-endpoint");
		await page.waitForTimeout(100);
		assert.equal(
			await page.locator("#copy-status").textContent(),
			"",
		);
		await page.waitForFunction(textContains, ["mcp-url", "tunnel"]);
		await page.click("#copy-endpoint");
		await page.waitForFunction(textIs, ["copy-status", "Address copied."]);
		assert.deepEqual(
			await page.evaluate(() => globalThis.copied),
			["https://tunnel.example/mcp"],
		);
	});
});
test("app reports clipboard failures", async t => {
	await browserTest(t, async (page, url) => {
		await page.addInitScript(() => {
			Object.defineProperty(globalThis.navigator, "clipboard", {
				value: {
					writeText: () => Promise.reject(new Error("denied")),
				},
			});
		});
		await stubApi(page, {
			status: {mcp_url: "https://tunnel.example/mcp"},
			activity: {call_count: 0, active_calls: 0, phase: "ok", events: []},
		});
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(textContains, ["mcp-url", "tunnel"]);
		await page.click("#copy-endpoint");
		await page.waitForFunction(
			textContains,
			["copy-status", "Copy failed"],
		);
	});
});
test("app fails loudly when required elements are missing", async t => {
	await browserTest(t, async (page, url) => {
		/** @type {Error[]} */
		const errors = [];
		page.on("pageerror", (/** @type {Error} */ error) =>
			errors.push(error),
		);
		await page.goto(`${url}${BROKEN}`);
		await page.waitForTimeout(200);
		assert.ok(
			errors.some(error =>
				error.message.includes("Missing required element: copy-endpoint")
			),
		);
	});
});
