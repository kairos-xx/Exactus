import assert from "node:assert/strict";
import test from "node:test";
import {
	browserTest
} from "../../../common/browser.mjs";
const DEMO = "/exactus/packages/actions/action_rest/examples/web/index.html";
/** Collect uncaught browser errors for one test.
 * @param {any} page Playwright page handle.
 * @returns {string[]} Collected page error messages.
 */
const pageErrors = page => {
	/** @type {string[]} */
	const errors = [];
	page.on("pageerror", ( /** @type {Error} */ error) => errors.push(error.message), );
	return errors;
};
test("request API resolves variables, params, headers and package exports", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		const result = await page.evaluate(async () => {
			const specifier = "/exactus/packages/actions/action_rest/index.js";
			const module = await import(specifier);
			const Studio = module.RequestStudio;
			/** @type {string[]} */
			const failures = [];
			/**
			 * Record a named check failure.
			 * @param {boolean} condition Whether the check passed.
			 * @param {string} name Check name.
			 */
			const check = (condition, name) => {
				if (!condition) failures.push(name);
			};
			check(module.default === Studio, "default export aliases RequestStudio");
			check(Studio.isRowKind("params"), "params is a row kind");
			check(!Studio.isRowKind("body"), "body is not a row kind");
			check(Studio.json('{"a":1}') === '{\n  "a": 1\n}', "JSON formatter pretty prints valid JSON", );
			check(Studio.json("not-json") === "not-json", "invalid JSON is preserved");
			const editor = document.createElement("div");
			Studio.setEditorText(editor, "a/{{user/id}}/{{missing}}");
			check(Studio.editorText(editor) === "a/{{user/id}}/{{missing}}", "token editor round trips variable syntax", );
			check(editor.querySelectorAll(".token-pill").length === 2, "token editor renders variable pills", );
			check(typeof Studio.prototype.send === "function" && typeof Studio.prototype.resolve === "function", "instance behavior lives on prototype", );
			return failures;
		});
		assert.deepEqual(result, []);
		assert.deepEqual(errors, []);
		assert.equal(await page.title(), "Request Studio");
		assert.equal(await page.locator("#resolved-url").textContent(), "https://api.example.com/v1/users/usr_28491?limit=25&include=profile", );
		assert.equal(await page.locator("#params-count").textContent(), "2");
		assert.equal(await page.locator("#headers-count").textContent(), "2");
	});
});
test("request rows, variables, tabs and body modes remain interactive", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		const params = page.locator("#params-table .row");
		assert.equal(await params.count(), 2);
		await page.locator('[data-add="params"]').click();
		assert.equal(await params.count(), 3);
		assert.equal(await page.locator("#params-count").textContent(), "3");
		await params.last().locator(".toggle-track").click();
		assert.equal(await params.last().locator(".enabled").isChecked(), false);
		assert.equal(await page.locator("#params-count").textContent(), "2");
		await params.last().locator(".delete").click();
		assert.equal(await params.count(), 2);
		await page.locator("#variables-toggle").click();
		assert.equal(await page.locator("#variables").getAttribute("aria-hidden"), "false");
		const variables = page.locator("#variable-list .variable");
		const before = await variables.count();
		await page.locator("#variable-add").click();
		assert.equal(await variables.count(), before + 1);
		await variables.last().locator(".v-name").fill("test/value");
		await variables.last().locator(".v-value").fill("resolved");
		await variables.last().locator(".secret").click();
		assert.equal(await variables.last().locator(".v-value").getAttribute("type"), "password");
		await variables.last().locator(".v-delete").click();
		assert.equal(await variables.count(), before);
		await page.locator('[data-tab="body"]').click();
		assert.equal(await page.locator("#body-panel").isHidden(), false);
		await page.locator("#body-format").selectOption("json");
		await page.locator('[data-body-mode="source"]').click();
		await page.locator("#body").fill('{"compact":true,"items":[1,2]}');
		await page.locator("#body-format-action").click();
		assert.match(await page.locator("#body").innerText(), /\n {2}"compact": true/);
		await page.locator('[data-body-mode="tree"]').click();
		assert.equal(await page.locator("#body-tree").getAttribute("data-valid"), "true");
		assert.ok(await page.locator("#body-tree .json-node").count() > 1);
		await page.locator('[data-body-mode="source"]').click();
		await page.locator("#body").fill("{");
		await page.locator('[data-body-mode="tree"]').click();
		assert.equal(await page.locator("#body-tree").getAttribute("data-valid"), "false");
		assert.match(await page.locator("#body-tree").textContent(), /Invalid JSON/);
		assert.deepEqual(errors, []);
	});
});
test("HTTP send builds the request and renders success, error and network responses", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		await page.evaluate(() => {
			/** @type {object[]} */
			const calls = [];
			Reflect.set(globalThis, "requestCalls", calls);
			Reflect.set(globalThis, "fetch", async (input, init) => {
				calls.push({
					url: String(input),
					method: init?.method,
					headers: Object.fromEntries(new Headers(init?.headers).entries()),
					body: init?.body,
					credentials: init?.credentials,
				});
				return new Response('{"ok":true,"nested":{"id":7}}', {
					status: 201,
					statusText: "Created",
					headers: {
						"content-type": "application/json"
					},
				});
			});
		});
		await page.locator("#method").selectOption("POST");
		await page.locator("#method").dispatchEvent("change");
		await page.locator("#send").click();
		await page.waitForFunction(() => document.querySelector("#response-meta")?.textContent?.includes("201 Created"), );
		const call = await page.evaluate(() => Reflect.get(globalThis, "requestCalls")[0]);
		assert.equal(call.method, "POST");
		assert.equal(call.credentials, "include");
		assert.match(call.url, /limit=25/);
		assert.equal(call.headers.authorization, "Bearer sk_demo_12345678");
		assert.equal(call.headers["content-type"], "application/json");
		assert.match(call.body, /"user": "usr_28491"/);
		assert.equal(await page.locator("#response-meta").getAttribute("class"), "success");
		assert.ok(await page.locator("#response-text .json-pick").count() > 0);
		await page.evaluate(() => {
			Reflect.set(globalThis, "fetch", async () => new Response("denied", {
				status: 403,
				statusText: "Forbidden"
			}), );
		});
		await page.locator("#send").click();
		await page.waitForFunction(() => document.querySelector("#response-meta")?.textContent?.includes("403 Forbidden"), );
		assert.equal(await page.locator("#response-meta").getAttribute("class"), "error");
		assert.equal(await page.locator("#response-text").textContent(), "denied");
		await page.evaluate(() => {
			Reflect.set(globalThis, "fetch", async () => {
				throw new TypeError("offline");
			});
		});
		await page.locator("#send").click();
		await page.waitForFunction(() => document.querySelector("#response-meta")?.textContent?.includes("Network error"), );
		assert.match(await page.locator("#response-text").textContent(), /offline/);
		assert.deepEqual(errors, []);
	});
});
test("WebSocket mode maps protocols, logs frames and restores HTTP controls", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		await page.evaluate(() => {
			/** In-page WebSocket stub that opens on a microtask. */
			class FakeWebSocket extends EventTarget {
				static OPEN = 1;
				readyState = 0;
				protocol = "chat.v1";
				/** @type {any[]} */
				sent = [];
				/**
				 * Record the target URL and open asynchronously.
				 * @param {any} target Socket URL.
				 * @param {any[]} [protocols] Requested protocols.
				 */
				constructor(target, protocols = []) {
					super();
					this.url = String(target);
					this.protocols = protocols;
					Reflect.set(globalThis, "fakeSocket", this);
					queueMicrotask(() => {
						this.readyState = FakeWebSocket.OPEN;
						this.dispatchEvent(new Event("open"));
					});
				}
				/**
				 * Record a sent frame.
				 * @param {any} value Frame payload.
				 */
				send(value) {
					this.sent.push(value);
				}
				/** Close the socket with a normal-closure event. */
				close() {
					this.readyState = 3;
					const event = new Event("close");
					Object.defineProperties(event, {
						code: {
							value: 1000
						},
						reason: {
							value: "Closed by user"
						},
					});
					this.dispatchEvent(event);
				}
			}
			Reflect.set(globalThis, "WebSocket", FakeWebSocket);
		});
		await page.locator("#transport").selectOption("websocket");
		await page.locator("#transport").dispatchEvent("change");
		assert.equal(await page.locator("#method").isHidden(), true);
		assert.equal(await page.locator("#body-tab").isHidden(), true);
		assert.match(await page.locator("#resolved-url").textContent(), /^wss:\/\//);
		await page.locator("#ws-protocols").fill("chat.v1, json");
		await page.locator("#send").click();
		await page.waitForFunction(() => document.querySelector("#ws-state")?.getAttribute("data-state") === "open", );
		const socket = await page.evaluate(() => {
			const value = Reflect.get(globalThis, "fakeSocket");
			return {
				url: value.url,
				protocols: value.protocols
			};
		});
		assert.match(socket.url, /^wss:\/\/api\.example\.com/);
		assert.deepEqual(socket.protocols, ["chat.v1", "json"]);
		await page.locator("#ws-message").fill("hello {{user/id}}");
		await page.locator("#ws-send").click();
		assert.deepEqual(await page.evaluate(() => Reflect.get(globalThis, "fakeSocket").sent),
			["hello usr_28491"], );
		assert.equal(await page.locator("#messages-count").textContent(), "2");
		await page.locator("#ws-clear").click();
		assert.equal(await page.locator("#messages-count").textContent(), "0");
		await page.locator("#send").click();
		await page.waitForFunction(() => document.querySelector("#ws-state")?.getAttribute("data-state") === "closed", );
		await page.locator("#transport").selectOption("http");
		await page.locator("#transport").dispatchEvent("change");
		assert.equal(await page.locator("#method").isHidden(), false);
		assert.deepEqual(errors, []);
	});
});
test("JSON capture saves response values as variables and demo is responsive", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		const pick = page.locator('.json-pick[data-path="$.user.name"]');
		await pick.click();
		assert.equal(await page.locator("#capture").isHidden(), false);
		assert.equal(await page.locator("#capture-path").textContent(), "$.user.name");
		await page.locator("#capture-name").fill("response/userName");
		await page.locator("#capture").evaluate(( /** @type {HTMLFormElement} */ form) => form.requestSubmit());
		await page.locator("#variables-toggle").click();
		const saved = page.locator("#variable-list .variable").filter({
			has: page.locator('.v-name[value="response/userName"]'),
		});
		assert.equal(await saved.count(), 1);
		assert.equal(await saved.locator(".v-value").inputValue(), "Ada Lovelace");
		await [1440, 1024, 390].reduce(async (previous, width) => {
			await previous;
			await page.setViewportSize({
				width,
				height: 900
			});
			assert.ok(await page.locator("#studio").boundingBox() !== null);
		}, Promise.resolve());
		assert.deepEqual(errors, []);
	});
});
