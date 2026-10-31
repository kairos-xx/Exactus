import assert from "node:assert/strict";
import test from "node:test";
import {
	browserTest
} from "../../../common/browser.mjs";
const DEMO = "/exactus/packages/widgets/widget_console/examples/web/index.html";
const LIBRARY = "/exactus/packages/widgets/widget_console/index.js";
/** Collect uncaught browser errors for one test.
 * @param {any} page Playwright page handle.
 * @returns {string[]} Collected page error messages.
 */
const pageErrors = page => {
	/** @type {string[]} */
	const errors = [];
	page.on("pageerror", ( /** @type {Error} */ error) => errors.push(error.message));
	return errors;
};
/** Run async steps one after another without awaiting inside a loop.
 * @template T
 * @param {readonly T[]} items Items to visit in order.
 * @param {(item:T)=>Promise<void>} step Async step per item.
 * @returns {Promise<void>} Settles after the last step.
 */
const each = (items, step) => items.reduce((chain, item) => chain.then(() => step(item)), Promise.resolve());
test("describer, formatter and recorder keep their contracts", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		const failures = await page.evaluate(async ( /** @type {string} */ specifier) => {
			const library = await import(specifier);
			const {
				describe,
				partsText,
				applyFormat,
				formatValue,
				ConsoleRecorder
			} = library;
			/** @type {string[]} */
			const problems = [];
			/** Record a failed expectation.
			 * @param {boolean} condition Whether the check passed.
			 * @param {string} name Check name. */
			const check = (condition, name) => {
				if (!condition) problems.push(name);
			};
			/** @type {{name:string, self?:unknown}} */
			const cyclic = {
				name: "a"
			};
			cyclic.self = cyclic;
			let getterRan = false;
			Object.defineProperty(cyclic, "lazy", {
				enumerable: true,
				get: () => {
					getterRan = true;
					return 1;
				},
			});
			const tree = describe(cyclic);
			check(tree.entries.some(( /** @type {any} */ entry) => entry.k === "self" && entry.v.circular), "cycles are marked circular");
			check(!getterRan, "accessors are never invoked");
			check(tree.entries.some(( /** @type {any} */ entry) => entry.k === "lazy" && entry.v.t === "accessor"), "accessors are described, not read");
			check(structuredClone(tree) !== undefined, "descriptors survive structured clone");
			check(describe(new Map([
				[1, 2]
			])).kind === "map" && describe(new Set([1])).kind === "set", "maps and sets are classified");
			check(describe([1, 2, 3]).size === 3, "arrays report their size");
			check(describe("x".repeat(20000)).more === 10000, "long strings are capped");
			check(describe(Array.from({
				length: 300
			}, (_, index) => index)).more === 200, "long lists report omitted members");
			check(describe(new RangeError("bad")).error.name === "RangeError", "errors keep name and message");
			check(describe(-0).v === 0 && Object.is(describe(-0).v, -0), "negative zero survives");
			check(formatValue(describe(-0)) === "-0", "negative zero prints with its sign");
			check(describe(10n).t === "bigint" && formatValue(describe(10n)) === "10n", "bigint prints with a suffix");
			/** Describe each value into a descriptor.
			 * @param {...unknown} values Values to describe. */
			const parts = (...values) => values.map(value => describe(value));
			check(partsText(applyFormat(parts("%s is %d%% done %c!", "Ada", 42.9, "color:red"))) === "Ada is 42% done !", "printf specifiers substitute and %c is dropped");
			check(partsText(applyFormat(parts("100%", 1))) === "100% 1", "a lone percent sign is kept");
			check(applyFormat(parts("obj %o", {
				a: 1
			})).length === 2, "%o keeps the object inspectable");
			/** @type {any[]} */
			const sunk = [];
			let cleared = 0;
			const recorder = new ConsoleRecorder({
				append: ( /** @type {any} */ entry) => sunk.push(entry),
				clear: () => (cleared += 1)
			});
			const methods = recorder.methods();
			methods.group("outer");
			methods.count();
			methods.count();
			methods.group("inner");
			methods.warn("nested");
			methods.groupEnd();
			methods.groupEnd();
			methods.groupEnd();
			methods.timeEnd("never-started");
			methods.assert(true, "silent");
			methods.assert(false, "loud");
			methods.table([{
				a: 1
			}]);
			methods.clear();
			const text = sunk.map(entry => `${entry.kind}/${entry.level}/${entry.depth}/${partsText(entry.parts)}`);
			check(text[0] === "group/log/0/outer", "group opens at the current depth");
			check(text[1] === "message/log/1/default: 1" && text[2] === "message/log/1/default: 2", "count increments inside the group");
			check(text[4] === "message/warn/2/nested", "nested groups indent further");
			check(text[5] === 'message/warn/0/Timer "never-started" does not exist', "unknown timers warn and depth never goes negative");
			check(text[6] === "message/error/0/Assertion failed: loud", "failed assertions are errors");
			check(sunk.length === 8 && sunk[7].kind === "table", "passing assertions are silent and tables keep their kind");
			check(cleared === 1, "console.clear reaches the sink");
			return problems;
		}, LIBRARY);
		assert.deepEqual(failures, []);
		assert.deepEqual(errors, []);
	});
});
test("console widget filters, folds repeats, trims and exposes its text", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		const result = await page.evaluate(async ( /** @type {string} */ specifier) => {
			const {
				mountConsole
			} = await import(specifier);
			/** Query one element.
			 * @param {string} selector Selector to query.
			 * @param {ParentNode} [root] Search root. */
			const $ = (selector, root = document) => /** @type {HTMLElement} */ (root.querySelector(selector));
			/** Query all matching elements.
			 * @param {string} selector Selector to query.
			 * @param {ParentNode} [root] Search root. */
			const $$ = (selector, root = document) => /** @type {HTMLElement[]} */ ([...root.querySelectorAll(selector)]);
			const host = document.createElement("div");
			host.style.height = "320px";
			document.body.append(host);
			const view = mountConsole(host, {
				maxEntries: 50
			});
			view.log("log", "alpha");
			view.log("info", "beta");
			view.log("warn", "gamma");
			view.log("error", "delta");
			view.log("debug", "epsilon");
			for (let index = 0; index < 3; index += 1) view.log("log", "same");
			const all = view.entries().length;
			const folded = $(".jc-repeat:not([hidden])", host).textContent;
			const counts = view.counts();
			view.setFilter("error");
			const onlyErrors = $$(".jc-entry", host).filter(row => !row.hidden).map(row => $(".jc-message", row).textContent?.trim());
			view.setFilter("all");
			view.setQuery("GAM");
			const searched = $$(".jc-entry", host).filter(row => !row.hidden).length;
			view.setQuery("zzz");
			const emptyText = $(".jc-empty", host).textContent;
			view.setQuery("");
			const copied = view.text();
			const chips = $$(".jc-chip", host).map(chip => `${chip.getAttribute("data-level")}:${chip.hidden ? "hidden" : chip.textContent?.trim()}`);
			view.setTimestamps(true);
			const stamped = $(".jc-console", host).getAttribute("data-time");
			for (let index = 0; index < 80; index += 1) view.log("log", `line ${index}`);
			const trimmed = {
				rows: view.entries().length,
				notice: !$(".jc-trimmed", host).hidden
			};
			/** @type {unknown[]} */
			const changes = [];
			view.on("change", ( /** @type {unknown} */ detail) => changes.push(detail));
			view.clear();
			return {
				all,
				folded,
				counts,
				onlyErrors,
				searched,
				emptyText,
				copied,
				chips,
				stamped,
				trimmed,
				afterClear: view.entries().length,
				lastChange: changes.at(-1),
				empty: !$(".jc-empty", host).hidden
			};
		}, LIBRARY);
		assert.equal(result.all, 6, "identical consecutive messages fold into one row");
		assert.equal(result.folded, "×3");
		assert.deepEqual(result.counts, {
			log: 4,
			info: 1,
			warn: 1,
			error: 1,
			debug: 1
		});
		assert.deepEqual(result.onlyErrors, ["delta"]);
		assert.equal(result.searched, 1);
		assert.equal(result.emptyText, "No messages match the filter.");
		assert.match(result.copied, /alpha\nbeta\ngamma\ndelta\nepsilon\nsame \(×3\)/);
		assert.deepEqual(result.chips, ["error:1", "warn:1"]);
		assert.equal(result.stamped, "true");
		assert.deepEqual(result.trimmed, {
			rows: 50,
			notice: true
		});
		assert.equal(result.afterClear, 0);
		assert.deepEqual(result.lastChange, {
			count: 0,
			errors: 0,
			warnings: 0
		});
		assert.equal(result.empty, true);
		assert.deepEqual(errors, []);
	});
});
test("inspector trees expand lazily with accessible toggles", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		const result = await page.evaluate(async ( /** @type {string} */ specifier) => {
			const {
				mountConsole
			} = await import(specifier);
			/** Query one element.
			 * @param {string} selector Selector to query.
			 * @param {ParentNode} [root] Search root. */
			const $ = (selector, root = document) => /** @type {HTMLElement} */ (root.querySelector(selector));
			/** Query all matching elements.
			 * @param {string} selector Selector to query.
			 * @param {ParentNode} [root] Search root. */
			const $$ = (selector, root = document) => /** @type {HTMLElement[]} */ ([...root.querySelectorAll(selector)]);
			const host = document.createElement("div");
			document.body.append(host);
			const view = mountConsole(host);
			view.log("log", {
				user: {
					name: "Ada",
					tags: ["a", "b"]
				},
				run: () => {}
			}, new Map([
				["k", 1]
			]), new RangeError("boom"));
			const first = $(".jc-object-head .jc-twisty", host);
			const before = {
				expanded: first.getAttribute("aria-expanded"),
				children: host.querySelectorAll(".jc-children").length
			};
			first.click();
			const topKeys = $$(".jc-entry .jc-object > .jc-children > .jc-prop > .jc-key", host).map(key => key.textContent);
			$(".jc-children .jc-twisty", host).click();
			const nestedKeys = $$(".jc-children .jc-children .jc-key", host).map(key => key.textContent);
			const functionRow = $$(".jc-prop", host).find(row => $(".jc-key", row).textContent === "run");
			if (functionRow) $(".jc-twisty", functionRow).click();
			const source = functionRow ? $(".jc-stack", functionRow).textContent : "";
			const errorHead = $$(".jc-v[data-type=error]", host).map(node => node.textContent);
			const labels = $$(".jc-twisty", host).map(button => button.getAttribute("aria-label"));
			first.click();
			return {
				before,
				topKeys,
				nestedKeys,
				source,
				errorHead,
				labels: labels.length,
				after: first.getAttribute("aria-expanded"),
				hidden: $(".jc-children", host).hidden
			};
		}, LIBRARY);
		assert.deepEqual(result.before, {
			expanded: "false",
			children: 0
		});
		assert.deepEqual(result.topKeys, ["user", "run"]);
		assert.deepEqual(result.nestedKeys, ["name", "tags"]);
		assert.match(result.source ?? "", /\(\) => \{\}/);
		assert.deepEqual(result.errorHead, ["RangeError: boom"]);
		assert.ok(result.labels >= 4, "every expandable value has a labelled toggle");
		assert.equal(result.after, "false");
		assert.equal(result.hidden, true);
		assert.deepEqual(errors, []);
	});
});
test("capture mirrors the page console and uncaught errors, then restores it", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		const result = await page.evaluate(async ( /** @type {string} */ specifier) => {
			const {
				mountConsole
			} = await import(specifier);
			const host = document.createElement("div");
			document.body.append(host);
			const view = mountConsole(host);
			const original = console.warn;
			const release = view.capture();
			const replaced = console.warn !== original;
			console.warn("mirrored", 7);
			console.group("g");
			console.log("inside");
			console.groupEnd();
			window.dispatchEvent(new ErrorEvent("error", {
				error: new TypeError("uncaught!"),
				message: "uncaught!"
			}));
			const captured = view.entries().map(( /** @type {any} */ entry) => `${entry.level}/${entry.kind}/${entry.depth}`);
			release();
			const restored = console.warn === original;
			console.warn("after release");
			return {
				replaced,
				captured,
				restored,
				total: view.entries().length
			};
		}, LIBRARY);
		assert.equal(result.replaced, true);
		assert.deepEqual(result.captured, ["warn/message/0", "log/group/0", "log/message/1", "error/message/0"]);
		assert.equal(result.restored, true);
		assert.equal(result.total, 4, "nothing is recorded after release");
		assert.deepEqual(errors, []);
	});
});
test("demo actions render tables, groups, repeats and keyboard-reachable controls", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		assert.equal(await page.title(), "Console Widget");
		await each(["levels", "table", "group", "repeat", "format"], async action => {
			await page.locator(`[data-action="${action}"]`).click();
		});
		assert.equal(await page.locator(".jc-table tr").count(), 4);
		assert.equal(await page.locator('.jc-entry[data-kind="group"]').count(), 2);
		assert.equal(await page.locator('.jc-entry[data-depth="2"]').count(), 1);
		assert.equal(await page.locator(".jc-repeat:not([hidden])").textContent(), "×4");
		assert.equal(await page.locator(".jc-list").getAttribute("role"), "log");
		assert.equal(await page.locator(".jc-list").getAttribute("aria-live"), "polite");
		await page.locator(".jc-chip[data-level=error]").click();
		assert.equal(await page.locator(".jc-entry:not([hidden])").count() > 0, true);
		assert.equal(await page.locator(".jc-entry[data-level=error]:not([hidden])").count(), 1);
		assert.equal(await page.locator(".jc-entry[data-level=log]:not([hidden])").count(), 0);
		await page.locator(".jc-chip[data-level=error]").click();
		assert.equal(await page.locator(".jc-select select").inputValue(), "all");
		await page.locator(".jc-button[aria-label='Clear console']").click();
		assert.equal(await page.locator(".jc-entry").count(), 0);
		await page.locator('[data-action="uncaught"]').click();
		await page.waitForSelector(".jc-entry[data-level=error]");
		assert.match(await page.locator(".jc-entry[data-level=error]").textContent() ?? "", /Cannot read properties of undefined/);
		assert.deepEqual(errors.filter(message => !message.includes("Cannot read properties")), []);
	});
});
test("themes and compact widths keep the widget inside its container", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await each(["dark", "light"], async theme => {
			await page.goto(`${url}${DEMO}?theme=${theme}`);
			await page.locator('[data-action="object"]').click();
			await page.locator('[data-action="levels"]').click();
			const field = await page.evaluate(() => getComputedStyle( /** @type {Element} */ (document.querySelector(".jc-list"))).backgroundColor);
			assert.equal(field, theme === "dark" ? "rgb(23, 26, 32)" : "rgb(255, 255, 255)");
			await each([200, 240, 340, 600], async width => {
				await page.setViewportSize({
					width: width + 32,
					height: 700
				});
				const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
				assert.ok(overflow <= 1, `${theme} ${width}px overflows by ${overflow}px`);
			});
		});
		assert.deepEqual(errors, []);
	});
});
test("the theme option recolours one widget without touching the page", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}?theme=dark`);
		const result = await page.evaluate(async ( /** @type {string} */ specifier) => {
			const {
				mountConsole
			} = await import(specifier);
			/** Read the computed background colour of an element.
			 * @param {Element|null} element Element to read. */
			const field = element => getComputedStyle( /** @type {Element} */ (element)).backgroundColor;
			const host = document.createElement("div");
			document.body.append(host);
			const view = mountConsole(host, {
				theme: "light"
			});
			view.log("log", "x");
			const light = field(host.querySelector(".jc-list"));
			const ink = getComputedStyle( /** @type {Element} */ (host.querySelector(".jc-entry"))).color;
			view.setTheme("dark");
			const dark = field(host.querySelector(".jc-list"));
			view.setTheme(null);
			return {
				light,
				ink,
				dark,
				inherited: field(host.querySelector(".jc-list")),
				page: field(document.querySelector(".jc-list"))
			};
		}, LIBRARY);
		assert.equal(result.light, "rgb(255, 255, 255)");
		assert.equal(result.ink, "rgb(23, 26, 32)");
		assert.equal(result.dark, "rgb(23, 26, 32)");
		assert.equal(result.inherited, "rgb(23, 26, 32)", "clearing the option falls back to the page theme");
		assert.equal(result.page, "rgb(23, 26, 32)", "the page console stays dark");
		assert.deepEqual(errors, []);
	});
});
