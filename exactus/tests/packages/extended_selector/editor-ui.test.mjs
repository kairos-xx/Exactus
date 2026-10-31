import assert from "node:assert/strict";
import test from "node:test";
import {
	browserTest,
} from "../../common/browser.mjs";
/** Fixture page exposing a mounted structured editor. */
const PAGE = "/exactus/tests/packages/extended_selector/editor-fixture.html";
/**
 * Evaluate an editor interaction inside the fixture page.
 *
 * @param {any} page Browser page.
 * @param {(arg?: any) => any} fn Interaction body.
 * @param {any} [arg] Optional argument.
 * @returns {Promise<any>} Result.
 */
const inside = (page, fn, arg) => page.evaluate(fn, arg);
test("editor renders values and folds them back to text", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(() => globalThis.editorReady === true);
		const result = await inside(page, () => {
			const editor = globalThis.editor;
			/** @type {string[]} */
			const changes = [];
			editor.addEventListener("change", (/** @type {any} */ event) => {
				changes.push(event.detail.value);
			});
			editor.value = 'and(.card, or(#a[x="1,2"], has(.b, .c)), "lit,(e)")';
			const rendered = editor.surface.querySelectorAll(".ese-call").length;
			const serialized = editor.serialize();
			const atomless = globalThis.Editor.parse("   ").kind;
			const split = globalThis.Editor.split('a, "b,c", [d,e], (f,g)');
			const title = globalThis.Editor.predicateTemplate("visible");
			const numeric = globalThis.Editor.predicateTemplate("width");
			const fallback = globalThis.Editor.predicateTemplate("role");
			const badType = (() => {
				try {
					return String(
						new globalThis.Editor(
							/** @type {any} */ (document.createElement("div")),
						).value,
					) && "";
				} catch (error) {
					return error instanceof Error ? error.message : String(error);
				}
			})();
			return {rendered, serialized, atomless, split, title, numeric, fallback, badType};
		});
		assert.equal(result.rendered, 3);
		assert.equal(result.serialized, 'and(.card, or(#a[x="1,2"], has(.b, .c)), "lit,(e)")');
		assert.equal(result.atomless, "atom");
		assert.deepEqual(result.split, ["a", '"b,c"', "[d,e]", "(f,g)"]);
		assert.equal(result.title, "[visible=true]");
		assert.equal(result.numeric, "[width>=0]");
		assert.equal(result.fallback, '[role*="…"]');
		assert.equal(result.badType, "target must be a textarea.");
	});
});
test("editor validates against the engine and marks invalid", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(() => globalThis.editorReady === true);
		const result = await inside(page, () => {
			const editor = globalThis.editor;
			editor.value = "(((";
			const diagnostics = editor.validate();
			const invalid = editor.surface.hasAttribute("data-invalid");
			const title = editor.surface.title;
			editor.setEngine(null);
			const cleared = editor.validate().length === 0 &&
				!editor.surface.hasAttribute("data-invalid");
			const chained = editor.setEngine(globalThis.engine) === editor;
			return {count: diagnostics.length, invalid, title, cleared, chained};
		});
		assert.ok(result.count > 0);
		assert.equal(result.invalid, true);
		assert.ok(result.title.length > 0);
		assert.equal(result.cleared, true);
		assert.equal(result.chained, true);
	});
});
test("editor opens operator menus and swaps operators", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(() => globalThis.editorReady === true);
		const swapped = await inside(page, () => {
			const editor = globalThis.editor;
			editor.value = "and(.a, .b)";
			const operator = globalThis.must(editor.surface.querySelector(".ese-operator"));
			operator.dispatchEvent(new MouseEvent("click", {bubbles: true}));
			const opened = !editor.popup.hidden;
			const options = [...editor.popup.querySelectorAll("button")].map(
				(/** @type {Element} */ button) => button.textContent ?? "",
			);
			const choice = globalThis.must(
				[...editor.popup.querySelectorAll("button")].find(
					(/** @type {Element} */ button) => button.textContent === "xor",
				),
			);
			choice.dispatchEvent(new MouseEvent("mousedown", {bubbles: true}));
			return {
				opened,
				closed: editor.popup.hidden,
				count: options.length,
				text: editor.value,
				label: operator.textContent,
			};
		});
		assert.equal(swapped.opened, true);
		assert.equal(swapped.closed, true);
		assert.ok(swapped.count > 30);
		assert.equal(swapped.text, "xor(.a, .b)");
		assert.equal(swapped.label, "xor▾");
	});
});
test("editor wraps a caret selection into a call from the menu", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(() => globalThis.editorReady === true);
		const result = await inside(page, async () => {
			const editor = globalThis.editor;
			editor.value = "";
			const caret = globalThis.must(editor.surface.querySelector(".ese-caret"));
			caret.textContent = "has";
			caret.dispatchEvent(new Event("input", {bubbles: true}));
			const options = [...editor.popup.querySelectorAll("button")].map(
				(/** @type {Element} */ button) => button.textContent ?? "",
			);
			const choice = globalThis.must(
				[...editor.popup.querySelectorAll("button")].find(
					(/** @type {Element} */ button) => button.textContent === "has",
				),
			);
			choice.dispatchEvent(new MouseEvent("mousedown", {bubbles: true}));
			await new Promise(done => {
				setTimeout(done, 0);
			});
			return {
				options,
				value: editor.value,
				slotFocused: document.activeElement?.getAttribute("data-role") === "caret",
			};
		});
		assert.deepEqual(result.options, ["has"]);
		assert.equal(result.value, "has()");
		assert.equal(result.slotFocused, true);
	});
});
test("editor offers atom completions for pseudo, predicate, and references", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(() => globalThis.editorReady === true);
		const offered = await inside(page, () => {
			const editor = globalThis.editor;
			/** Offer completions for atom content.
			 * @param {string} text Atom text.
			 * @returns {string[]} Listed options.
			 */
			const offer = text => {
				editor.value = "x";
				const atom = globalThis.must(editor.surface.querySelector(".ese-atom"));
				atom.textContent = text;
				globalThis.Editor.focusAt(atom, text.length);
				editor.showAtomOptions(atom);
				return [...editor.popup.querySelectorAll("button")].map(
					(/** @type {Element} */ button) => button.textContent ?? "",
				);
			};
			return {
				pseudo: offer(":hov"),
				predicate: offer("[wid"),
				reference: offer('[extended-selector="saved-o'),
				starters: offer(""),
				none: offer(".card[x=1]"),
			};
		});
		assert.ok(offered.pseudo.includes(":hover"));
		assert.ok(offered.predicate.includes("[width>=0]"));
		assert.deepEqual(offered.reference, ['saved-one"]', 'saved-two"]']);
		assert.ok(offered.starters.includes("#id"));
		assert.ok(offered.starters.includes('[extended-selector="saved-one"]'));
		assert.equal(offered.none.length, 0);
	});
});
test("editor applies an atom completion at the caret offset", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(() => globalThis.editorReady === true);
		const applied = await inside(page, async () => {
			const editor = globalThis.editor;
			editor.value = ".card";
			const atom = globalThis.must(editor.surface.querySelector(".ese-atom"));
			atom.textContent = ".card:hov]suffix";
			globalThis.Editor.focusAt(atom, 9);
			editor.showAtomOptions(atom);
			const choice = globalThis.must(
				[...editor.popup.querySelectorAll("button")].find(
					(/** @type {Element} */ button) => button.textContent === ":hover",
				),
			);
			choice.dispatchEvent(new MouseEvent("mousedown", {bubbles: true}));
			await new Promise(done => {
				setTimeout(done, 0);
			});
			return {value: editor.value};
		});
		assert.equal(applied.value, ".card:hover]suffix");
	});
});
test("editor routes clicks to parens, editables, and ignores stray targets", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(() => globalThis.editorReady === true);
		const result = await inside(page, () => {
			const editor = globalThis.editor;
			editor.value = "and(.a, .b)";
			editor.onClick(new MouseEvent("click"));
			editor.onInput(new Event("input"));
			editor.offer(new FocusEvent("focusin"));
			editor.onKeydown(new KeyboardEvent("keydown"));
			const paren = globalThis.must(editor.surface.querySelector(".ese-paren"));
			const call = globalThis.must(paren.closest(".ese-call"));
			paren.dispatchEvent(new MouseEvent("click", {bubbles: true}));
			const active = call.classList.contains("ese-active");
			const stray = document.createElement("div");
			editor.surface.append(stray);
			stray.dispatchEvent(new MouseEvent("click", {bubbles: true}));
			stray.dispatchEvent(new Event("input", {bubbles: true}));
			stray.dispatchEvent(new FocusEvent("focusin", {bubbles: true}));
			const caret = globalThis.must(editor.surface.querySelector(".ese-caret"));
			caret.dispatchEvent(new FocusEvent("focusin", {bubbles: true}));
			const offered = !editor.popup.hidden;
			return {active, offered};
		});
		assert.equal(result.active, true);
		assert.equal(result.offered, true);
	});
});
test("editor handles Enter, Escape, and paired-key insertion", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(() => globalThis.editorReady === true);
		const result = await inside(page, async () => {
			const editor = globalThis.editor;
			editor.value = ".a";
			const atom = globalThis.must(editor.surface.querySelector(".ese-atom"));
			/**
			 * Dispatch a keydown against an editable target.
			 *
			 * @param {string} keyName Key value.
			 * @param {Element} [target] Event target.
			 * @returns {boolean} Whether the event was not canceled.
			 */
			const key = (keyName, target = atom) =>
				target.dispatchEvent(new KeyboardEvent("keydown", {
					key: keyName,
					bubbles: true,
					cancelable: true,
				}));
			const skipped = key("x");
			editor.showExpressionOptions(
				globalThis.must(editor.surface.querySelector(".ese-caret")),
			);
			key("Enter", atom);
			const wrapped = editor.value;
			editor.popup.hidden = false;
			key("Escape", atom);
			const escaped = editor.popup.hidden;
			atom.dispatchEvent(new FocusEvent("focusin", {bubbles: true}));
			atom.focus();
			const selection = globalThis.must(window.getSelection());
			const range = document.createRange();
			range.selectNodeContents(atom);
			range.collapse(false);
			selection.removeAllRanges();
			selection.addRange(range);
			key("[");
			await new Promise(done => {
				setTimeout(done, 0);
			});
			const bracketed = atom.textContent;
			return {skipped, wrapped, escaped, bracketed};
		});
		assert.equal(result.skipped, true);
		assert.equal(result.wrapped, "and() .a");
		assert.equal(result.escaped, true);
		assert.ok(result.bracketed.includes("["));
	});
});
test("editor wraps the current selection and reports failures", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(() => globalThis.editorReady === true);
		const result = await inside(page, () => {
			const editor = globalThis.editor;
			editor.value = ".card";
			const atom = globalThis.must(editor.surface.querySelector(".ese-atom"));
			const selection = globalThis.must(window.getSelection());
			selection.removeAllRanges();
			const withoutSelection = editor.wrapSelection("has");
			const range = document.createRange();
			range.selectNodeContents(atom);
			range.collapse(false);
			selection.addRange(range);
			const wrapped = editor.wrapSelection("not");
			const value = editor.value;
			const orphan = document.createElement("span");
			const noNode = editor.wrapNode(orphan, "and");
			return {withoutSelection, wrapped, value, noNode};
		});
		assert.equal(result.withoutSelection, false);
		assert.equal(result.wrapped, true);
		assert.equal(result.value, "not(.card)");
		assert.equal(result.noNode, false);
	});
});
test("editor measures caret offsets with and without a selection", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(() => globalThis.editorReady === true);
		const result = await inside(page, () => {
			const editor = globalThis.editor;
			editor.value = ".card";
			const atom = globalThis.must(editor.surface.querySelector(".ese-atom"));
			globalThis.must(window.getSelection()).removeAllRanges();
			const full = globalThis.Editor.caretOffset(atom);
			const selection = globalThis.must(window.getSelection());
			const range = document.createRange();
			const text = globalThis.must(
				globalThis.must(atom.querySelector(".ese-selector")).firstChild,
			);
			range.setStart(text, 2);
			range.collapse(true);
			selection.removeAllRanges();
			selection.addRange(range);
			const partial = globalThis.Editor.caretOffset(atom);
			return {full, partial};
		});
		assert.equal(result.full, 5);
		assert.equal(result.partial, 2);
	});
});
test("editor falls back to an atom when parsing fails", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(() => globalThis.editorReady === true);
		const result = await inside(page, () => {
			const editor = globalThis.editor;
			const parse = globalThis.Editor.parse;
			globalThis.Editor.parse = () => {
				throw new Error("parse exploded");
			};
			try {
				editor.value = ".card";
			} finally {
				globalThis.Editor.parse = parse;
			}
			return {serialized: editor.serialize()};
		});
		assert.equal(result.serialized, ".card");
	});
});
test("focusAt returns quietly when the offset exceeds the text", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${PAGE}`);
		await page.waitForFunction(() => globalThis.editorReady === true);
		const result = await inside(page, () => {
			const editor = globalThis.editor;
			editor.value = ".a";
			const atom = globalThis.must(editor.surface.querySelector(".ese-atom"));
			globalThis.Editor.focusAt(atom, 9999);
			const selection = globalThis.must(window.getSelection());
			return {ranges: selection.rangeCount};
		});
		assert.ok(result.ranges <= 1);
	});
});
test("demo harness runs registration and clearing", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(
			`${url}/exactus/tests/packages/extended_selector/demo-fixture.html`,
		);
		await page.waitForFunction(
			() =>
				(document.getElementById("status")?.textContent?.length ?? 0) > 0,
		);
		const run = await page.evaluate(() => {
			const expression = /** @type {HTMLTextAreaElement} */ (
				globalThis.must(document.getElementById("expression"))
			);
			expression.value = ".card";
			expression.dispatchEvent(new Event("input", {bubbles: true}));
			globalThis.must(document.getElementById("run")).click();
			return {
				result: document.getElementById("css-result")?.textContent ?? "",
				icons: document.querySelectorAll('[extended-selector="card"] > svg')
					.length,
			};
		});
		assert.match(run.result, /card\.register = /);
		assert.match(run.result, /1 match\(es\)/);
		assert.equal(run.icons, 1);
		const rerun = await page.evaluate(() => {
			globalThis.must(document.getElementById("run")).click();
			return document.getElementById("css-result")?.textContent ?? "";
		});
		assert.match(rerun, /1 match\(es\)/);
		const failed = await page.evaluate(() => {
			const expression = /** @type {HTMLTextAreaElement} */ (
				globalThis.must(document.getElementById("expression"))
			);
			expression.value = ".nothing-here";
			expression.dispatchEvent(new Event("input", {bubbles: true}));
			globalThis.must(document.getElementById("run")).click();
			return document.getElementById("css-result")?.textContent ?? "";
		});
		assert.match(failed, /No card matched/);
		const status = await page.evaluate(() => {
			const surface = globalThis.must(document.querySelector(".ese-editor"));
			const atom = globalThis.must(surface.querySelector(".ese-atom"));
			atom.textContent = "(((";
			atom.dispatchEvent(new Event("input", {bubbles: true}));
			return document.getElementById("status")?.textContent ?? "";
		});
		assert.notEqual(status, "Valid");
		const cleared = await page.evaluate(() => {
			globalThis.must(document.getElementById("clear")).click();
			return {
				result: document.getElementById("css-result")?.textContent ?? "",
				registered: document.querySelectorAll("[extended-selector]").length,
			};
		});
		assert.equal(cleared.result, "Registration cleared.");
		assert.equal(cleared.registered, 0);
	});
});
test("demo harness rejects an incomplete fixture", async t => {
	await browserTest(t, async (page, url) => {
		/** @type {Error[]} */
		const errors = [];
		page.on("pageerror", (/** @type {Error} */ error) =>
			errors.push(error),
		);
		await page.goto(
			`${url}/exactus/tests/packages/extended_selector/demo-broken.html`,
		);
		await page.waitForTimeout(200);
		assert.ok(
			errors.some(error =>
				error.message.includes("demo fixture incomplete")
			),
		);
	});
});
