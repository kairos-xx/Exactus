/** Exercise the ExtendedSelector engine in a real Chromium page. */
import assert from "node:assert/strict";
import test from "node:test";
import {
	browserTest
} from "../../common/browser.mjs";
/**
 * @typedef {import("../../../packages/extended_selector/editor/extended-selector.js").AstNode} AstNode
 * @typedef {import("../../../packages/extended_selector/editor/extended-selector.js").ExtendedSelector} ExtendedSelector
 */
/** Open the fixture page and wait until the engine module has loaded.
 * @param {any} page Browser page from browserTest.
 * @param {string} url Origin of the repository server.
 * @returns {Promise<void>}
 */
const open = async (page, url) => {
	await page.goto(`${url}/exactus/tests/packages/extended_selector/fixture.html`);
	await page.waitForFunction(() => globalThis.engineReady === true);
};
/** Query and return each element's id (or class name when it has no id).
 * @param {any} page
 * @param {string} expression
 * @param {Record<string, unknown>} [options]
 * @returns {Promise<string[]>}
 */
const ids = (page, expression, options) => page.evaluate(
	(
		/** @type {[string, Record<string, unknown>|undefined]} */
		[text, extra], ) => globalThis.engine.query(text, extra ?? {}).map(
		( /** @type {Element} */ element) => element.id || element.className, ),
	[expression, options], );
/** Return the message of the error a query throws, or an empty string.
 * @param {any} page
 * @param {string} expression
 * @returns {Promise<string>}
 */
const failure = (page, expression) => page.evaluate(( /** @type {string} */ text) => {
	try {
		globalThis.engine.query(text);
		return "";
	} catch (error) {
		return error instanceof Error ? error.message : String(error);
	}
}, expression);
/** Return the lint diagnostic codes for an expression.
 * @param {any} page
 * @param {string} expression
 * @returns {Promise<string[]>}
 */
const lint = (page, expression) => page.evaluate(
	( /** @type {string} */ text) => globalThis.engine.lint(text).map(( /** @type {{code:string}} */ item) => item.code), expression, );
test("existing behavior is unchanged", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		assert.deepEqual(await ids(page, "left_of(.item, #ref)"), ["left-near"]);
		assert.deepEqual(await ids(page, ".item[width>=200px]"), ["above-near"]);
		assert.deepEqual(await ids(page, "a.box"), ["link"]);
		assert.deepEqual(await ids(page, "body [href]"), ["link"]);
		assert.deepEqual(await ids(page, ".item:not(#above-far)"), ["above-near", "below-near", "left-near", "right-near", ]);
		assert.deepEqual(await lint(page, 'children(.card, .title[textContent="Order *"], button[innerText="Save *"])', ),
			[], );
		assert.equal(await page.evaluate(
			() => globalThis.engine.bestSelector(
				/** @type {Element} */
				(document.getElementById("link")), ).selector, ), "#link", );
	});
});
test("attribute selectors behave like CSS", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		assert.deepEqual(await ids(page, '[data-testid="save"]'), ["link"]);
		assert.deepEqual(await ids(page, 'a[href="/x"]'), ["link"]);
		assert.deepEqual(await ids(page, '.item[data-priority="3"]'), ["above-far", ]);
		assert.deepEqual(await ids(page, 'input[type="text"]'), ["field"]);
		assert.deepEqual(await ids(page, '[data-testid^="sa"]'), ["link"]);
		// Brackets inside parentheses are plain CSS.
		assert.deepEqual(await ids(page, '.item:not([data-priority="3"])'), ["above-near", "below-near", "left-near", "right-near", ]);
		assert.deepEqual(await ids(page, ':is(a[data-testid="save"])'), ["link"]);
		// Brackets outside the subject compound are plain CSS and must lint.
		assert.deepEqual(await ids(page, '#stage[id="stage"] > a'), ["link"]);
		assert.deepEqual(await ids(page, '[class="box"] > a'), []);
		assert.deepEqual(await ids(page, '#stage [data-testid="save"]'), ["link"]);
		assert.deepEqual(await ids(page, '[id="stage"] .item[data-priority="1"]'), ["above-near", ]);
	});
});
test("documented tolerance arguments lint and apply", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		assert.deepEqual(await lint(page, "left_of(.item, #ref, 150)"), []);
		assert.deepEqual(await ids(page, "left_of(.item, #ref, 150)"), ["above-far", "below-near", "left-near", ]);
	});
});
test("register keeps names unique", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		const result = await page.evaluate(() => {
			const Library = globalThis.ExtendedSelector;
			/** The shadow root of the host element with this id.
			 * @param {string} id Host element id.
			 * @returns {ShadowRoot}
			 */
			const shadowRootOf = id =>
				/** @type {ShadowRoot} */
				(
					/** @type {HTMLElement} */
					(document.getElementById(id)).shadowRoot);
			const first = /** @type {any} */ (document.getElementById("above-far"));
			const second = /** @type {any} */ (document.getElementById("above-near"));
			const inner = /** @type {Element} */ (shadowRootOf("host").querySelector(".inner"));
			/** @type {any} */
			const out = {};
			Library.register(first, "dup");
			try {
				Library.register(second, "dup");
				out.conflict = "no error";
			} catch (error) {
				out.conflict = /** @type {Error} */ (error).message;
			}
			Library.register(first, "dup");
			out.same = first.register;
			try {
				second.register = "dup";
				out.setter = "no error";
			} catch (error) {
				out.setter = /** @type {Error} */ (error).message;
			}
			try {
				Library.register(second, "bad name");
				out.bad = "no error";
			} catch (error) {
				out.bad = /** @type {Error} */ (error).name;
			}
			Library.register(second, "dup", {
				replace: true
			});
			out.moved = [first.register, second.register];
			second.register = null;
			out.cleared = second.register;
			Library.register(inner, "shadowed");
			try {
				Library.register(first, "shadowed");
				out.deep = "no error";
			} catch (error) {
				out.deep = /** @type {Error} */ (error).message;
			}
			return out;
		});
		assert.match(result.conflict, /already used/);
		assert.equal(result.same, "dup");
		assert.match(result.setter, /already used/);
		assert.equal(result.bad, "SyntaxError");
		assert.deepEqual(result.moved, [null, "dup"]);
		assert.equal(result.cleared, null);
		assert.match(result.deep, /already used/);
	});
});
test("sort orders results by keys", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		const byPriority = ["above-near", "below-near", "above-far", "right-near", "left-near", ];
		assert.deepEqual(await ids(page, "sort(.item, [data-priority])"), byPriority, );
		assert.deepEqual(await ids(page, "sort(.item, -[data-priority])"),
			[...byPriority].reverse(), );
		assert.deepEqual(await ids(page, "sort(.item, data:priority)"), byPriority);
		// Equal widths keep document order.
		assert.deepEqual(await ids(page, "sort(.item, width)"), ["below-near", "above-far", "left-near", "right-near", "above-near", ]);
		assert.deepEqual(await ids(page, "sort(.item, -width, [data-priority])"), ["above-near", "above-far", "right-near", "left-near", "below-near", ]);
		// Missing values sort last for both directions.
		assert.deepEqual(await ids(page, "sort(.item, -[data-nothing])"), ["above-far", "above-near", "below-near", "left-near", "right-near", ]);
	});
});
test("sort can rank by geometry relative to a reference", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		assert.deepEqual(await ids(page, "sort(.item, #ref, distance)"), ["below-near", "above-near", "left-near", "right-near", "above-far", ]);
		assert.deepEqual(await ids(page, "sort(.item, #nothing, distance)"), []);
	});
});
test("sort rejects malformed keys at lint time", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		assert.deepEqual(await lint(page, "sort(.item, #oops)"), ["sort-keys"]);
		assert.match(await failure(page, "sort(.item, #oops)"), /Invalid sort key/);
		assert.match(await failure(page, "sort(.item, distance)"), /need a reference/, );
	});
});
test("queryOne returns the first element in sort order", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		const first = await page.evaluate(
			() => globalThis.engine.queryOne("sort(.item, -[data-priority])")?.id, );
		assert.equal(first, "left-near");
	});
});
test("nearest ranks by distance and direction", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		assert.deepEqual(await ids(page, "nearest(.item, #ref)"), ["below-near", "above-near", "left-near", "right-near", "above-far", ]);
		assert.deepEqual(await ids(page, "nearest_above(.item, #ref)"), ["above-near", "above-far", ]);
		assert.deepEqual(await ids(page, "nearest_below(.item, #ref)"), ["below-near", ]);
		assert.deepEqual(await ids(page, "nearest_left(.item, #ref)"), ["left-near", ]);
		assert.deepEqual(await ids(page, "nearest_right(.item, #ref)"), ["right-near", ]);
		assert.deepEqual(await ids(page, "nearest(.item, #nothing)"), []);
		// Overlap inside the tolerance counts as touching, then distance decides.
		assert.deepEqual(await ids(page, "nearest_left(.item, #ref, 150)"), ["below-near", "above-far", "left-near", ]);
		const first = await page.evaluate(
			() => globalThis.engine.queryOne("nearest_above(.item, #ref)")?.id, );
		assert.equal(first, "above-near");
	});
});
test("media evaluates a media query", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		assert.equal(
			(await ids(page, 'and(.item, media("(min-width: 900px)"))')).length, 5, );
		assert.deepEqual(await ids(page, 'and(.item, media("(max-width: 480px)"))'),
			[], );
		assert.equal(
			(await ids(page, 'and(.item, media("(max-width: 480px), (min-width: 900px)"))', )).length, 5, );
		await page.setViewportSize({
			width: 400,
			height: 800
		});
		assert.equal(
			(await ids(page, 'and(.item, media("(orientation: portrait)"))')).length, 5, );
	});
});
test("an invalid media query fails at lint time", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		assert.deepEqual(await lint(page, 'media("garbage ((")'), ["invalid-media", ]);
		assert.match(await failure(page, 'media("garbage ((")'), /Invalid media query/, );
	});
});
test("define resolves a name without touching the page", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		const result = await page.evaluate(() => {
			const engine = globalThis.engine;
			engine.define("cardbox", "#stage");
			engine.define("lefty", "nearest_left(.item, #ref)");
			engine.define("ghost", "#does-not-exist");
			engine.define("loop1", '[extended-selector="loop2"]');
			engine.define("loop2", '[extended-selector="loop1"]');
			/** @type {any} */
			const out = {
				direct: engine.query('[extended-selector="lefty"]').map(( /** @type {Element} */ item) => item.id),
				asAncestor: engine.query('[extended-selector="cardbox"] > a').map(( /** @type {Element} */ item) => item.id),
				empty: engine.query('[extended-selector="ghost"]').length,
			};
			try {
				engine.query('[extended-selector="loop1"]');
				out.cycle = "no error";
			} catch (error) {
				out.cycle = /** @type {Error} */ (error).message;
			}
			try {
				engine.define("no good", ".x");
				out.badName = "no error";
			} catch (error) {
				out.badName = /** @type {Error} */ (error).name;
			}
			try {
				engine.define("broken", "sort(.item, #oops)");
				out.badExpression = "no error";
			} catch (error) {
				out.badExpression = /** @type {Error} */ (error).name;
			}
			// A real stamp with the same name loses to the definition.
			const decoy = /** @type {any} */ (document.getElementById("above-far"));
			decoy.setAttribute("extended-selector", "lefty");
			out.shadowedByDefinition = engine.query('[extended-selector="lefty"]').map(( /** @type {Element} */ item) => item.id);
			decoy.removeAttribute("extended-selector");
			engine.undefine("lefty");
			out.stamped = document.querySelectorAll("[extended-selector]").length;
			return out;
		});
		assert.deepEqual(result.direct, ["left-near"]);
		assert.deepEqual(result.asAncestor, ["link"]);
		assert.equal(result.empty, 0);
		assert.match(result.cycle, /refers to itself/);
		assert.equal(result.badName, "SyntaxError");
		assert.notEqual(result.badExpression, "no error");
		assert.deepEqual(result.shadowedByDefinition, ["left-near"]);
		assert.equal(result.stamped, 0);
	});
});
test("deep mode reaches open shadow roots", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		const result = await page.evaluate(() => {
			const engine = globalThis.engine;
			/** The shadow root of the host element with this id.
			 * @param {string} id Host element id.
			 * @returns {ShadowRoot}
			 */
			const shadowRootOf = id =>
				/** @type {ShadowRoot} */
				(
					/** @type {HTMLElement} */
					(document.getElementById(id)).shadowRoot);
			const inner = ["host", "host2"].map(id =>
				/** @type {Element} */
				(shadowRootOf(id).querySelector(".inner")), );
			const selectors = inner.map(
				( /** @type {Element} */ element) => engine.bestSelector(element, {
					engines: ["native"],
					deep: true,
					includeCandidates: false,
				}).selector, );
			return {
				plain: engine.query("button").length,
				deep: engine.query("button", {
					deep: true
				}).length,
				selectors,
				resolved: selectors.map(
					( /** @type {string} */ selector) => engine.queryChain(selector).length, ),
				light: engine.bestSelector(
					/** @type {Element} */
					(document.getElementById("link")), {
						engines: ["native"],
						deep: true,
						includeCandidates: false,
					}, ).selector,
			};
		});
		assert.equal(result.plain, 0);
		assert.equal(result.deep, 2);
		assert.deepEqual(result.resolved, [1, 1]);
		assert.ok(result.selectors.every(( /** @type {string} */ selector) => selector.includes(" >> "), ), );
		assert.equal(result.light, "#link");
	});
});
test("the engine reports its capabilities", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		const info = await page.evaluate(() => ({
			version: globalThis.ExtendedSelector.VERSION,
			ordering: globalThis.ExtendedSelector.CAPABILITIES.ordering,
			environment: globalThis.ExtendedSelector.CAPABILITIES.environment,
		}));
		assert.equal(info.version, "2.1.0");
		assert.deepEqual(info.ordering, ["sort", "nearest", "nearest_above", "nearest_below", "nearest_left", "nearest_right", ]);
		assert.deepEqual(info.environment, ["media"]);
	});
});
test("traversal, spatial, and relational operators", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		const items = ["above-far", "above-near", "below-near", "left-near", "right-near", ];
		// Traversal operators filter base elements by a related condition.
		assert.deepEqual(await ids(page, "prev(.item, #ref)"), ["above-far"]);
		assert.deepEqual(await ids(page, "next(.item, #below-near)"), ["above-near", ]);
		assert.deepEqual(await ids(page, "siblings(.item, #ref)"), items);
		assert.deepEqual(await ids(page, "parent(.item, #stage)"), items);
		assert.deepEqual(await ids(page, "ancestor(#link, #stage)"), ["link"]);
		assert.deepEqual(await ids(page, "closest(.item, .stage)"), items);
		assert.deepEqual(await ids(page, "before(.item, #below-near)"), ["above-far", "above-near", ]);
		assert.deepEqual(await ids(page, "after(.item, #ref)"), items);
		assert.deepEqual(await ids(page, "children(#stage, .box, .box, .box, .box, .box, .box, .box, .box)", ),
			["stage"], );
		assert.deepEqual(await ids(page, "has(#stage, #link)"), ["stage"]);
		assert.deepEqual(await ids(page, "apply(#stage, .item)"), items);
		// Spatial operators measure against the reference rectangle.
		assert.deepEqual(await ids(page, "right_of(.item, #ref)"), ["right-near"]);
		assert.deepEqual(await ids(page, "above(.item, #ref)"), ["above-far", "above-near", ]);
		assert.deepEqual(await ids(page, "below(.item, #ref)"), ["below-near"]);
		assert.deepEqual(await ids(page, "overlaps(.item, #stage)"), items);
		assert.deepEqual(await ids(page, "inside(.item, #stage)"), items);
		assert.deepEqual(await ids(page, "inside(.item, #ref)"), []);
		assert.deepEqual(await ids(page, "near(.item, #ref, 150)"), ["above-near", "below-near", ]);
		assert.deepEqual(await ids(page, "aligned_left(.item, #ref)"), ["above-far", "above-near", "below-near", ]);
		assert.deepEqual(await ids(page, "aligned_center_x(.item, #ref, 50)"), ["above-far", "above-near", "below-near", ]);
		// Relational quantifiers evaluate a condition over related elements.
		assert.deepEqual(await ids(page, "any(.item, siblings, #ref)"), items);
		assert.deepEqual(await ids(page, "all(#stage, children, .box)"), ["stage"]);
		assert.deepEqual(await ids(page, "none(.item, descendants, .item)"), items);
		// Shadow roots expose their interior to the shadow() operator.
		assert.deepEqual(await ids(page, "shadow(#host, .inner)"), ["inner"]);
		// Ordering operators rank by geometry relative to the reference.
		assert.deepEqual(await ids(page, "nearest(.item, #ref)"), ["below-near", "above-near", "left-near", "right-near", "above-far", ]);
		assert.deepEqual(await ids(page, "nearest_above(.item, #ref)"), ["above-near", "above-far", ]);
		assert.deepEqual(await ids(page, "nearest_below(.item, #ref)"), ["below-near", ]);
		assert.deepEqual(await ids(page, "nearest_left(.item, #ref)"), ["left-near", ]);
		assert.deepEqual(await ids(page, "nearest_right(.item, #ref)"), ["right-near", ]);
		assert.deepEqual(await ids(page, "nearest_left(.item, #ref, 50)"), ["below-near", "left-near", ]);
		assert.deepEqual(await ids(page, "sort(.item, #ref, distance)"), ["below-near", "above-near", "left-near", "right-near", "above-far", ]);
		assert.deepEqual(await ids(page, "sort(.item, #ref, -gap_top)"), ["above-far", "above-near", "left-near", "right-near", "below-near", ]);
		// Set algebra combines evaluated sub-expressions over the universe.
		assert.deepEqual(await ids(page, "and(.item, .box)"), items);
		assert.deepEqual(await ids(page, "or(#ref, #link)"), ["ref", "link"]);
		assert.deepEqual(await ids(page, "xor(.box, .item)"), ["ref", "link", "field", ]);
		assert.deepEqual(await ids(page, 'media("print")'), []);
	});
});
test("predicate operators cover every comparison form", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		const items = ["above-far", "above-near", "below-near", "left-near", "right-near", ];
		// String comparison operators evaluate attribute values.
		assert.deepEqual(await ids(page, ".item[id^=above]"), ["above-far", "above-near", ]);
		assert.deepEqual(await ids(page, ".item[id$=near]"), ["above-near", "below-near", "left-near", "right-near", ]);
		assert.deepEqual(await ids(page, ".item[id*=elo]"), ["below-near"]);
		assert.deepEqual(await ids(page, ".item[id=*near*]"), ["above-near", "below-near", "left-near", "right-near", ]);
		assert.deepEqual(await ids(page, ".item[id!=*near*]"), ["above-far"]);
		// Fuzzy and regular-expression comparisons handle approximate matches.
		assert.deepEqual(await ids(page, ".item[id~~left-near,0.9]"), ["left-near", ]);
		assert.deepEqual(await ids(page, ".item[id~=/-near$/]"), ["above-near", "below-near", "left-near", "right-near", ]);
		assert.deepEqual(await ids(page, ".item[id~=/-NEAR$/i]"), ["above-near", "below-near", "left-near", "right-near", ]);
		assert.deepEqual(await ids(page, ".item[id~=red,0.5]"), []);
		// Parent-relative geometry predicates read element offsets.
		assert.deepEqual(await ids(page, ".item[x_rel>=300]"), ["above-far", "above-near", "below-near", "right-near", ]);
		assert.deepEqual(await ids(page, ".item[x_rel>=50%]"), ["right-near"]);
		assert.deepEqual(await ids(page, ".item[y_rel>=300]"), ["below-near", "left-near", "right-near", ]);
		assert.deepEqual(await ids(page, ".item[z_ref=front]"), items);
		// Reference predicates compare geometry against resolved elements.
		assert.deepEqual(await ids(page, ".item[gap_left(#ref)>=90]"), ["left-near", ]);
		assert.deepEqual(await ids(page, ".item[gap_top(prev)>=0]"), ["above-far", "left-near", ]);
		assert.deepEqual(await ids(page, ".item[gap_bottom(next)>=0]"), ["below-near", ]);
		assert.deepEqual(await ids(page, ".item[inside(closest:.stage)=true]"), ["above-far", "above-near", "below-near", "left-near", "right-near", ]);
		assert.deepEqual(await ids(page, ".item[z_ref(#ref)=none]"), items);
		assert.deepEqual(await ids(page, ".item[z_ref(parent)=front]"), items);
	});
});
test("engine extension points and diagnostics", async t => {
	await browserTest(t, async (page, url) => {
		await open(page, url);
		// Registered predicates and operators extend the query language.
		const custom = await page.evaluate(() => {
			const engine = /** @type {ExtendedSelector} */ (globalThis.engine);
			engine.registerPredicate("always", () => "yes");
			engine.registerOperator("first_of", ({
				engine: e,
				args,
				universe
			}) => e.evaluateAst( /** @type {AstNode} */ (args[0]), universe).slice(0, 1), );
			const scoped = engine.configure({}).setRoot( /** @type {Element} */ (document.getElementById("stage"))).query("first_of(.item)").map(( /** @type {Element} */ element) => element.id);
			engine.setRoot(document).unregisterPredicate("always");
			engine.unregisterOperator("first_of");
			let predicateError = "";
			let operatorError = "";
			try {
				engine.registerPredicate("bad", /** @type {any} */ (null));
			} catch (error) {
				predicateError = String(error);
			}
			try {
				engine.registerOperator("bad", /** @type {any} */ (null));
			} catch (error) {
				operatorError = String(error);
			}
			return {
				scoped,
				predicateError,
				operatorError
			};
		});
		assert.deepEqual(custom.scoped, ["above-far"]);
		assert.ok(custom.predicateError.includes("must be a function"));
		assert.ok(custom.operatorError.includes("must be a function"));
		// Malformed expressions raise diagnostics instead of throwing.
		const diagnostics = await page.evaluate(() => {
			const engine = /** @type {ExtendedSelector} */ (globalThis.engine);
			return {
				nonString: engine.lint(42).map(d => d.code),
				empty: engine.lint("").map(d => d.code),
				unclosed: engine.lint("left_of(").map(d => d.code),
				unterminated: engine.lint('a[href="x').map(d => d.code),
			};
		});
		assert.deepEqual(diagnostics.nonString, ["type"]);
		assert.deepEqual(diagnostics.empty, ["empty"]);
		assert.deepEqual(diagnostics.unclosed, ["unclosed-delimiter"]);
		assert.deepEqual(diagnostics.unterminated, ["unterminated-string"]);
		assert.deepEqual(await lint(page, "bogus(.a)"), ["unknown-operator"]);
		// Invalid syntax surfaces descriptive errors.
		assert.ok(
			(await failure(page, "prev(.a)")).includes("expects 2 arguments"), );
		assert.ok((await failure(page, "count(.a, .b)")).includes("count"));
		assert.ok(
			(await failure(page, "sort(.item, gap_top)")).includes("reference"), );
		assert.ok(
			(await failure(page, "sort(.item, #ref, not a key)")).includes("Invalid sort key", ), );
		assert.ok(
			(await failure(page, ".item[zzz(#ref)=1]")).includes("Unknown geometry property", ), );
		assert.ok(
			(await failure(page, ".item[gap_top(###)>=0]")).includes("Invalid reference selector", ), );
		assert.ok(
			(await failure(page, '.item[id~~"x",2]')).includes("Fuzzy comparison"), );
		assert.ok((await failure(page, ".item[id~=x]")).includes("~="));
		// Selector generation accepts pluggable engines.
		const generated = await page.evaluate(() => {
			const engine = /** @type {ExtendedSelector} */ (globalThis.engine);
			const link = /** @type {Element} */ (document.getElementById("link"));
			link.setAttribute("extended-selector", "registered-link");
			const result = engine.bestSelector(link, {
				engines: ["register", "generator", "optimal", "finder", "native"],
				generator: () => "a[href]",
				optimal: {
					getSingleSelector: () => '[data-testid="save"]',
					getMultiSelector: () => "#link",
					optimize: () => "a",
				},
				finder: () => "#link",
				includeCandidates: true,
			});
			let emptyError = "";
			let typeError = "";
			try {
				engine.bestSelector([]);
			} catch (error) {
				emptyError = String(error);
			}
			try {
				engine.bestSelector( /** @type {any} */ (document.createTextNode("x")));
			} catch (error) {
				typeError = String(error);
			}
			return {
				candidates: result.candidates.map(item => item.selector),
				emptyError,
				typeError,
			};
		});
		assert.ok(generated.candidates.some(( /** @type {string} */ selector) => selector.includes("registered-link"), ), );
		assert.ok(generated.candidates.includes("a[href]"));
		assert.ok(generated.candidates.some(( /** @type {string} */ selector) => selector.includes('data-testid="save"'), ), );
		assert.ok(generated.candidates.includes("#link"));
		assert.ok(generated.emptyError.includes("Element"));
		assert.ok(generated.typeError.includes("Element"));
	});
});
