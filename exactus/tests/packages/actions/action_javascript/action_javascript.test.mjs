import assert from "node:assert/strict";
import test from "node:test";
import {
	browserTest
} from "../../../common/browser.mjs";
const DEMO = "/exactus/packages/actions/action_javascript/examples/web/index.html";
const LIBRARY = "/exactus/packages/actions/action_javascript/index.js";
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
test("tokenizer round-trips source and classifies the pieces", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		const result = await page.evaluate(async ( /** @type {string} */ specifier) => {
			const {
				tokenize,
				tokenizeLines
			} = await import(specifier);
			const source = `const n = 0x1F + 1_000n; // note\nlet s = "a\\"b" + \`t \${n}\`;\n/* multi\nline */ exactus.log(true, null);`;
			const tokens = tokenize(source);
			/** Find the type of the token with the given text.
			 * @param {string} text Token text to find. */
			const kind = text => tokens.find(( /** @type {any} */ token) => token.text === text)?.type;
			return {
				roundTrip: tokens.map(( /** @type {any} */ token) => token.text).join("") === source,
				lines: tokenizeLines(source).length,
				kinds: [kind("const"), kind("0x1F"), kind("1_000n"), kind("// note"), kind('"a\\"b"'), kind(`\`t \${n}\``), kind("true"), kind("null"), kind("exactus"), kind("n")],
				unterminated: tokenize('x = "open').at(-1)?.type,
				blockSplit: tokenizeLines("/* a\nb */")[1]?.[0]?.type,
			};
		}, LIBRARY);
		assert.equal(result.roundTrip, true);
		assert.equal(result.lines, 4);
		assert.deepEqual(result.kinds, ["keyword", "number", "number", "comment", "string", "template", "literal", "literal", "name", "text"]);
		assert.equal(result.unterminated, "string");
		assert.equal(result.blockSplit, "comment");
		assert.deepEqual(errors, []);
	});
});
test("worker executor returns values, maps errors to lines and ends runaway code", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		const result = await page.evaluate(async ( /** @type {string} */ specifier) => {
			const {
				WorkerExecutor
			} = await import(specifier);
			/** Run one snippet through the worker and capture its entries.
			 * @param {string} code Snippet.
			 * @param {any} [extra] Request overrides.
			 * @returns {Promise<{outcome:{status:string, value:any, json:string|null, jsonSafe:boolean, durationMs:number, error:any}, entries:any[], cleared:number}>} Run outcome, captured entries and clear count. */
			const run = async (code, extra = {}) => {
				/** @type {any[]} */
				const entries = [];
				let cleared = 0;
				const handle = WorkerExecutor.run({
					code,
					mode: "auto",
					variables: {
						"user/id": "usr_1",
						n: 5
					},
					context: {
						run: 1
					},
					timeoutMs: 2000,
					...extra
				}, {
					onEntry: ( /** @type {any} */ entry) => entries.push(entry),
					onClear: () => (cleared += 1)
				}, );
				if (extra.cancelAfter) setTimeout(handle.cancel, extra.cancelAfter);
				const outcome = await handle.promise;
				return {
					outcome,
					entries,
					cleared
				};
			};
			/** Read the printable value of a descriptor.
			 * @param {any} descriptor Value descriptor. */
			const plain = descriptor => descriptor?.v ?? descriptor?.t;
			const expression = await run("1 + 2");
			const implicit = await run("const a = exactus.vars.get('n');\na * 2");
			const statements = await run("console.log('hi');\nreturn exactus.vars.get('user/id');");
			const asyncRun = await run("await new Promise(resolve => { setTimeout(resolve, 40); });\n'late'");
			const failure = await run("const a = 1;\nconst b = a.x.y;\nb");
			const assertion = await run("exactus.assert(1 === 2, 'math broke')");
			const missing = await run("exactus.vars.get('nope')");
			const semantics = await run("console.group('g'); console.count(); console.assert(false, 'bad'); console.clear(); 7");
			const syntax = await run("const = ;");
			const loop = await run("while (true) {}", {
				timeoutMs: 300
			});
			const cancelled = await run("while (true) {}", {
				timeoutMs: 5000,
				cancelAfter: 100
			});
			const dom = await run("typeof document");
			const ids = {
				context: {
					flow: {
						id: "f1"
					},
					action: {
						id: "a1"
					},
					run: {
						id: "r1"
					},
					context: {
						id: "phone"
					}
				}
			};
			const playback = {
				mode: "playback",
				variables: {
					Count: 3
				}
			};
			const facade = await run("[__EXACTUS_FLOW__.id, __EXACTUS_FLOW__.actionId, exactus.run.id, exactus.context.id]", {
				...ids,
				...playback
			});
			const flowExpression = await run("__EXACTUS_FLOW__.vars.Count + 1", playback);
			const flowBody = await run("return __EXACTUS_FLOW__.vars.Count + 1;", playback);
			const noImplicit = await run("console.log('x'); 7", playback);
			const template = await run("{{Count}} + 1", playback);
			const sharedVars = await run("exactus.vars.set('x', 5); return [__EXACTUS_FLOW__.vars.x, exactus.vars.has('x'), exactus.vars.metadata('x').type, exactus.vars.get('Count')]", playback);
			const pageOnly = await run("exactus.page.url", playback);
			const returnedFunction = await run("() => 2 + 3", playback);
			const unwrapped = await run("() => 2 + 3");
			const flowAssert = await run("__EXACTUS_FLOW__.assert(false, 'nope')", playback);
			const flood = await run("for (let i = 0; i < 1500; i += 1) console.log(i);");
			const circular = await run("const a = {}; a.self = a; a");
			const midLine = await run("console.log('a;b'); 7");
			const midError = await run("const first = 1;\nconst o = {}; o.x.y");
			return {
				expression: [expression.outcome.status, plain(expression.outcome.value), expression.outcome.json, expression.outcome.jsonSafe],
				implicit: plain(implicit.outcome.value),
				statements: [plain(statements.outcome.value), statements.entries[0]?.source],
				asyncRun: [asyncRun.outcome.status, plain(asyncRun.outcome.value), asyncRun.outcome.durationMs >= 35],
				failure: [failure.outcome.status, failure.outcome.error.name, failure.outcome.error.location],
				assertion: [assertion.outcome.error.name, assertion.outcome.error.message, assertion.outcome.error.location?.line],
				missing: [plain(missing.outcome.value), missing.entries[0]?.level],
				semantics: [semantics.entries.map(( /** @type {any} */ entry) => `${entry.kind}/${entry.level}/${entry.depth}`), semantics.cleared, plain(semantics.outcome.value)],
				syntax: [syntax.outcome.status, syntax.outcome.error.name, syntax.outcome.error.location],
				loop: [loop.outcome.status, loop.outcome.durationMs < 1500],
				cancelled: [cancelled.outcome.status, cancelled.outcome.durationMs < 1500],
				dom: plain(dom.outcome.value),
				facade: facade.outcome.json,
				playback: [plain(flowExpression.outcome.value), plain(flowBody.outcome.value), plain(noImplicit.outcome.value), template.outcome.status, sharedVars.outcome.json],
				pageOnly: [pageOnly.outcome.status, pageOnly.outcome.error.message],
				returnedFunction: [plain(returnedFunction.outcome.value), unwrapped.outcome.value.t],
				flowAssert: [flowAssert.outcome.error.name, flowAssert.outcome.error.message],
				flood: [flood.entries.length, flood.entries.at(-1)?.level],
				circular: [circular.outcome.status, circular.outcome.jsonSafe, circular.outcome.json],
				midLine: [plain(midLine.outcome.value), midLine.entries.length],
				midError: [midError.outcome.status, midError.outcome.error.location],
			};
		}, "/exactus/packages/actions/action_javascript/executor.js");
		assert.deepEqual(result.expression, ["ok", 3, "3", true]);
		assert.equal(result.implicit, 10, "the last expression of a snippet is returned");
		assert.deepEqual(result.statements, ["usr_1", {
			line: 1,
			column: 9
		}]);
		assert.deepEqual(result.asyncRun, ["ok", "late", true]);
		assert.deepEqual(result.failure, ["error", "TypeError", {
			line: 2,
			column: 15
		}]);
		assert.deepEqual(result.assertion, ["AssertionError", "math broke", 1]);
		assert.deepEqual(result.missing, ["undefined", "warn"]);
		assert.deepEqual(result.semantics, [
			["group/log/0", "message/log/1", "message/error/1"], 1, 7
		]);
		assert.deepEqual(result.syntax, ["error", "SyntaxError", null]);
		assert.deepEqual(result.loop, ["timeout", true]);
		assert.deepEqual(result.cancelled, ["cancelled", true]);
		assert.equal(result.dom, "undefined", "the worker has no DOM");
		assert.equal(result.facade, '["f1","a1","r1","phone"]');
		assert.deepEqual(result.playback, [4, 4, "undefined", "error", '[5,true,"number",3]'], "playback compiles like a Studio run: expression first, then a body");
		assert.deepEqual(result.pageOnly, ["error", "exactus.page is only available during playback; the preview worker has no page."]);
		assert.deepEqual(result.returnedFunction, [5, "function"], "playback calls a returned function; auto mode returns it");
		assert.deepEqual(result.flowAssert, ["AssertionError", "nope"]);
		assert.deepEqual(result.flood, [1001, "warn"], "output is capped with one truncation warning");
		assert.deepEqual(result.circular, ["ok", false, null]);
		assert.deepEqual(result.midLine, [7, 1], "a trailing expression on a statement line is still returned");
		assert.deepEqual(result.midError, ["error", {
			line: 2,
			column: 19
		}], "positions inside a mid-line tail map back to the snippet");
		assert.deepEqual(errors, []);
	});
});
test("runner demo runs samples and reports value, console and failure", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		assert.equal(await page.title(), "JavaScript Runner Widget");
		assert.equal(await page.locator(".jr-status").getAttribute("data-state"), "idle");
		await page.locator('[data-sample="variables"]').click();
		await page.waitForFunction(() => document.querySelector(".jr-status")?.getAttribute("data-state") === "ok");
		assert.equal(await page.locator(".jr-result").getAttribute("data-state"), "ok");
		assert.match(await page.locator(".jr-result-body").textContent() ?? "", /id: "usr_28491", pages: 5/);
		assert.match(await page.locator(".jr-result-meta").textContent() ?? "", /saved as result/);
		assert.equal(await page.locator('[data-component="saved"]').textContent(), 'Saved result = {"id":"usr_28491","pages":5}');
		assert.equal(await page.locator(".jc-table tr").count(), 6);
		assert.equal(await page.locator('.jc-entry[data-kind="message"]').count(), 1);
		await page.locator('[data-sample="error"]').click();
		await page.waitForFunction(() => document.querySelector(".jr-status")?.getAttribute("data-state") === "error");
		assert.equal(await page.locator(".jr-result").getAttribute("data-state"), "error");
		assert.match(await page.locator(".jr-result-body").textContent() ?? "", /TypeError: Cannot read properties of undefined/);
		assert.equal(await page.locator(".jr-num[data-error]").textContent(), "3");
		assert.equal(await page.locator(".jr-line[data-error]").count(), 1);
		assert.equal(await page.locator(".jc-chip[data-level=warn]").isVisible(), true);
		await page.locator(".jr-error .jc-source").click();
		const caret = await page.evaluate(() => {
			const input = /** @type {HTMLTextAreaElement} */ (document.querySelector(".jr-input"));
			return {
				focused: document.activeElement === input,
				line: input.value.slice(0, input.selectionStart).split("\n").length
			};
		});
		assert.deepEqual(caret, {
			focused: true,
			line: 3
		});
		await page.locator('.jc-entry .jc-source').first().click();
		assert.equal(await page.evaluate(() => /** @type {HTMLTextAreaElement} */ (document.querySelector(".jr-input")).value.slice(0, /** @type {HTMLTextAreaElement} */ (document.querySelector(".jr-input")).selectionStart).split("\n").length), 2);
		await page.locator('[data-sample="expression"]').click();
		await page.waitForFunction(() => document.querySelector(".jr-status")?.getAttribute("data-state") === "ok");
		assert.equal(await page.locator(".jr-num[data-error]").count(), 0, "a new run clears the failing line");
		assert.equal(await page.locator(".jc-entry").count(), 0, "the console clears on each run by default");
		assert.match(await page.locator(".jr-result-meta").textContent() ?? "", /Array/);
		assert.deepEqual(errors, []);
	});
});
test("endless loops are stopped by the time limit and by the Stop button", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		await page.locator('[data-sample="loop"]').click();
		await page.waitForFunction(() => document.querySelector(".jr-run-label")?.textContent === "Stop");
		assert.equal(await page.locator(".jr-status").getAttribute("data-state"), "running");
		assert.equal(await page.locator(".jr-runner").getAttribute("data-running"), "true");
		await page.locator(".jr-run").click();
		await page.waitForFunction(() => document.querySelector(".jr-status")?.getAttribute("data-state") === "cancelled");
		assert.equal(await page.locator(".jr-run-label").textContent(), "Run");
		assert.match(await page.locator(".jr-result-body").textContent() ?? "", /stopped before it finished/);
		await page.locator(".jr-run").click();
		await page.waitForFunction(() => document.querySelector(".jr-status")?.getAttribute("data-state") === "timeout", undefined, {
			timeout: 8000
		});
		assert.match(await page.locator(".jr-result-body").textContent() ?? "", /Stopped after 2 s/);
		assert.equal(await page.locator(".jr-result").getAttribute("data-state"), "timeout");
		assert.deepEqual(errors, []);
	});
});
test("editor keys indent, split braces, comment and run", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		const result = await page.evaluate(async () => {
			const input = /** @type {HTMLTextAreaElement} */ (document.querySelector(".jr-input"));
			/** Dispatch a keydown event at the editor input.
			 * @param {string} name Key name.
			 * @param {KeyboardEventInit} [extra] Modifiers. */
			const press = (name, extra = {}) => input.dispatchEvent(new KeyboardEvent("keydown", {
				key: name,
				bubbles: true,
				cancelable: true,
				...extra
			}));
			/** Set the editor value and selection.
			 * @param {string} value New value.
			 * @param {number} start Selection start.
			 * @param {number} [end] Selection end. */
			const set = (value, start, end = start) => {
				input.focus();
				input.value = value;
				input.dispatchEvent(new Event("input", {
					bubbles: true
				}));
				input.setSelectionRange(start, end);
			};
			set("if (a) {", 8);
			press("Enter");
			const bracket = [input.value, input.selectionStart];
			set("{}", 1);
			press("Enter");
			const braces = [input.value, input.selectionStart];
			set("  a\nb\nc", 0, 7);
			press("Tab");
			const indent = input.value;
			press("Tab", {
				shiftKey: true
			});
			const outdent = input.value;
			set("x = 1;\ny = 2;", 0, 13);
			press("/", {
				ctrlKey: true
			});
			const commented = input.value;
			press("/", {
				ctrlKey: true
			});
			const uncommented = input.value;
			set("x", 1);
			press("Tab");
			const tab = input.value;
			set("40 + 2", 6);
			press("Enter", {
				ctrlKey: true
			});
			await new Promise(resolve => {
				setTimeout(resolve, 250);
			});
			return {
				bracket,
				braces,
				indent,
				outdent,
				commented,
				uncommented,
				tab,
				ran: document.querySelector(".jr-result-body")?.textContent,
				carrier: /** @type {HTMLTextAreaElement} */ (document.querySelector('[data-component="snippet"]')).value,
				gutter: document.querySelectorAll(".jr-num").length,
			};
		});
		assert.deepEqual(result.bracket, ["if (a) {\n  ", 11]);
		assert.deepEqual(result.braces, ["{\n  \n}", 4]);
		assert.equal(result.indent, "    a\n  b\n  c");
		assert.equal(result.outdent, "  a\nb\nc");
		assert.equal(result.commented, "// x = 1;\n// y = 2;");
		assert.equal(result.uncommented, "x = 1;\ny = 2;");
		assert.equal(result.tab, "x  ");
		assert.equal(result.ran, "42");
		assert.equal(result.carrier, "40 + 2");
		assert.equal(result.gutter, 1);
		assert.deepEqual(errors, []);
	});
});
test("values menu searches, masks secrets, inserts and closes", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		const trigger = page.locator(".jr-menu-host .jc-button");
		assert.equal(await trigger.getAttribute("aria-expanded"), "false");
		await trigger.click();
		assert.equal(await trigger.getAttribute("aria-expanded"), "true");
		const items = await page.locator(".jr-menu-item").allTextContents();
		assert.equal(items.length, 4);
		assert.ok(items.some(( /** @type {string} */ item) => item.includes("••••••••")), "secret values are masked");
		assert.ok(!items.join("").includes("sk_demo"), "secret values never appear in the menu");
		await page.locator(".jr-menu-search").fill("page");
		assert.equal(await page.locator(".jr-menu-item").count(), 1);
		await page.locator(".jr-menu-search").fill("nothing-matches");
		assert.equal(await page.locator(".jr-menu-empty").textContent(), "No matching values.");
		await page.locator(".jr-menu-search").fill("scheme");
		await page.locator(".jr-menu-search").press("Enter");
		assert.equal(await page.locator(".jr-menu").isHidden(), true);
		assert.match(await page.locator(".jr-input").inputValue(), /exactus\.vars\.get\("auth\/scheme"\)/);
		await trigger.click();
		await page.keyboard.press("Escape");
		assert.equal(await page.locator(".jr-menu").isHidden(), true);
		assert.equal(await page.evaluate(() => document.activeElement?.classList.contains("jc-button")), true, "focus returns to the trigger");
		await trigger.click();
		await page.mouse.click(5, 5);
		assert.equal(await page.locator(".jr-menu").isHidden(), true);
		assert.deepEqual(errors, []);
	});
});
test("runner accepts an injected executor and keeps the carrier in sync", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}`);
		const result = await page.evaluate(async ( /** @type {string} */ specifier) => {
			const {
				mountRunner
			} = await import(specifier);
			const describerPath = "/exactus/packages/widgets/widget_console/describe.js";
			const {
				Describer
			} = await import(describerPath);
			const carrier = document.createElement("textarea");
			carrier.value = "stored();";
			document.body.append(carrier);
			/** @type {any[]} */
			const requests = [];
			const events = /** @type {string[]} */ ([]);
			const runner = mountRunner(carrier, {
				outputName: "answer",
				mode: "statements",
				context: {
					flow: "demo"
				},
				variables: [{
					name: "a",
					value: 1
				}],
				execute: ( /** @type {any} */ request, /** @type {any} */ handlers) => {
					requests.push(request);
					handlers.onEntry({
						level: "info",
						kind: "message",
						parts: [Describer.describe("from host")],
						time: Date.now(),
						depth: 0
					});
					return {
						promise: Promise.resolve({
							status: "ok",
							durationMs: 12,
							value: Describer.describe({
								ok: true
							}),
							jsonSafe: true,
							json: '{"ok":true}'
						}),
						cancel: () => {}
					};
				},
			});
			runner.on("run", ( /** @type {any} */ detail) => events.push(`run:${detail.code}`));
			runner.on("result", ( /** @type {any} */ detail) => events.push(`result:${detail.status}:${detail.saveAs}:${detail.json}`));
			runner.on("change", ( /** @type {any} */ detail) => events.push(`change:${detail.value}`));
			const hidden = carrier.hidden;
			const initial = runner.getValue();
			runner.setValue("edited();");
			const synced = carrier.value;
			await runner.run();
			const secondRun = await runner.run();
			const status = runner.element.querySelector(".jr-status-text")?.textContent;
			/** @type {HTMLInputElement} */
			(runner.element.querySelector('input[name="output_variable"]')).value = "renamed";
			const output = runner.outputName();
			runner.setVariables([]);
			const valuesHidden = /** @type {HTMLElement} */ (runner.element.querySelector(".jr-menu-host .jc-button")).hidden;
			const rows = runner.console.entries().length;
			runner.destroy();
			return {
				hidden,
				initial,
				synced,
				request: requests[0],
				secondRun: secondRun === null ? "null" : secondRun.status,
				status,
				events,
				output,
				valuesHidden,
				rows,
				afterDestroy: [carrier.hidden, document.querySelector(".jr-runner:not([data-demo])") === null || true]
			};
		}, LIBRARY);
		assert.equal(result.hidden, true, "the carrier is hidden while the widget is mounted");
		assert.equal(result.initial, "stored();");
		assert.equal(result.synced, "edited();");
		assert.deepEqual(result.request, {
			code: "edited();",
			mode: "statements",
			variables: {
				a: 1
			},
			context: {
				flow: "demo"
			},
			timeoutMs: 5000
		});
		assert.equal(result.status, "Done · 12 ms");
		assert.deepEqual(result.events, ["change:edited();", "run:edited();", 'result:ok:answer:{"ok":true}', "run:edited();", 'result:ok:answer:{"ok":true}']);
		assert.equal(result.output, "renamed");
		assert.equal(result.valuesHidden, true);
		assert.equal(result.rows, 1, "the console clears per run and shows the host entry");
		assert.equal(result.afterDestroy[0], false);
		assert.deepEqual(errors, []);
	});
});
test("runner honours read-only mode and stays inside narrow containers in both themes", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await each(["dark", "light"], async theme => {
			await page.goto(`${url}${DEMO}?theme=${theme}&run`);
			await page.waitForFunction(() => document.querySelector(".jr-status")?.getAttribute("data-state") === "ok");
			const field = await page.evaluate(() => getComputedStyle( /** @type {Element} */ (document.querySelector(".jr-editor"))).backgroundColor);
			assert.equal(field, theme === "dark" ? "rgb(23, 26, 32)" : "rgb(255, 255, 255)");
			await each([200, 240, 340, 700], async width => {
				await page.setViewportSize({
					width: width + 32,
					height: 800
				});
				const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
				assert.ok(overflow <= 1, `${theme} ${width}px overflows by ${overflow}px`);
			});
		});
		const readOnly = await page.evaluate(async ( /** @type {string} */ specifier) => {
			const {
				mountRunner
			} = await import(specifier);
			const carrier = document.createElement("textarea");
			document.body.append(carrier);
			const runner = mountRunner(carrier, {
				source: "1",
				readOnly: true
			});
			const input = /** @type {HTMLTextAreaElement} */ (runner.element.querySelector(".jr-input"));
			return {
				readOnly: input.readOnly,
				label: input.getAttribute("aria-label"),
				spellcheck: input.spellcheck
			};
		}, LIBRARY);
		assert.deepEqual(readOnly, {
			readOnly: true,
			label: "JavaScript",
			spellcheck: false
		});
		assert.deepEqual(errors, []);
	});
});
test("the runner theme reaches its editor, result and embedded console", async t => {
	await browserTest(t, async (page, url) => {
		const errors = pageErrors(page);
		await page.goto(`${url}${DEMO}?theme=dark`);
		const result = await page.evaluate(async ( /** @type {string} */ specifier) => {
			const {
				mountRunner
			} = await import(specifier);
			/** Read the computed background colour of an element.
			 * @param {Element|null} element Element to read. */
			const field = element => getComputedStyle( /** @type {Element} */ (element)).backgroundColor;
			const carrier = document.createElement("textarea");
			document.body.append(carrier);
			const runner = mountRunner(carrier, {
				theme: "light",
				source: "console.log(1); 2"
			});
			await runner.run();
			/** Read the themed background of the editor, result and console. */
			const parts = () => [".jr-editor", ".jr-result", ".jc-list"].map(selector => field(runner.element.querySelector(selector)));
			const light = parts();
			runner.setTheme("dark");
			return {
				light,
				dark: parts()
			};
		}, LIBRARY);
		assert.deepEqual(result.light, ["rgb(255, 255, 255)", "rgb(255, 255, 255)", "rgb(255, 255, 255)"]);
		assert.deepEqual(result.dark, ["rgb(23, 26, 32)", "rgb(23, 26, 32)", "rgb(23, 26, 32)"]);
		assert.deepEqual(errors, []);
	});
});
