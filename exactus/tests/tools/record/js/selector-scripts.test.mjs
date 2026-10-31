/** Exercise the selector resolver and sandbox page scripts directly. */
import assert from "node:assert/strict";
import test from "node:test";
import { browserTest } from "../../../common/browser.mjs";
const RECORD = "/exactus/tools/record";
/** Load a function-expression page script with an attributable source URL.
 * @param {any} page Browser page.
 * @param {string} url Repository server origin.
 * @param {string} name Script basename.
 * @returns {Promise<void>}
 */
const load = async (page, url, name) => {
  await page.goto(`${url}/exactus/tests/packages/extended_selector/fixture.html`);
  const sourceUrl = `${url}${RECORD}/${name}.js`;
  const response = await fetch(sourceUrl);
  const source = (await response.text()).replace(/;\s*$/, "");
  await page.addScriptTag({
    content: `globalThis.${name} = ${source};\n//# sourceURL=${sourceUrl}`,
  });
};
test("selector resolver reports evidence, definitions, checks and CSS", async t => {
  await browserTest(t, async (page, url) => {
    await load(page, url, "selector_resolve");
    const result = await page.evaluate(() => {
      const first = document.createElement("button");
      first.id = "save";
      first.className = "primary";
      first.setAttribute("aria-label", "Save");
      first.textContent = "  Save now  ";
      const second = document.createElement("input");
      second.id = "broken-css";
      second.setAttribute("type", "text");
      document.body.append(first, second);
      /** Fake selector engine covering resolver success and failure paths. */
      class Engine {
        /** Define a stored selector.
         * @param {string} name Stored selector name.
         * @throws {Error} When the fixture requests a broken definition.
         */
        define(name) {
          if (name === "broken") throw new Error("bad definition\nignored");
        }
        /** Return the two fixture matches.
         * @returns {Element[]} Fixture elements.
         */
        query() {
          return [first, second];
        }
        /** Return one synthetic predicate value.
         * @param {Element} element Fixture element.
         * @param {"role"|"visible"|"enabled"} property Predicate name.
         * @returns {string} Synthetic predicate value.
         */
        predicateValue(element, property) {
          const values = /** @type {Record<"role"|"visible"|"enabled", string>} */ ({
            role: element === first ? "button" : "textbox",
            visible: "true",
            enabled: element === first ? "true" : "false",
          });
          return values[property];
        }
        /** Compile a fixture element to CSS.
         * @param {Element} element Fixture element.
         * @returns {{selector:string}} Compiled selector result.
         * @throws {Error} When the fixture requests compilation failure.
         */
        bestSelector(element) {
          if (element === second) throw new Error("no selector\ndetail");
          return { selector: "#save" };
        }
        /** Evaluate one synthetic element check.
         * @param {Element} element Fixture element.
         * @param {string} check Check expression.
         * @returns {boolean} Whether the element satisfies the check.
         * @throws {Error} When the fixture requests a malformed check.
         */
        matches(element, check) {
          if (check === "throws") throw new Error("invalid check\ndetail");
          return element === first && check === "passes";
        }
      }
      Object.defineProperty(globalThis, "__EXACTUS_ES__", {
        value: Engine,
        configurable: true,
      });
      const resolve = /** @type {Function} */ (
        Reflect.get(globalThis, "selector_resolve")
      );
      return resolve({
        expression: ".target",
        definitions: { valid: ".target", broken: "bad(" },
        checks: ["passes", "fails", "throws"],
        compile: true,
      });
    });
    assert.equal(result.count, 2);
    assert.deepEqual(result.definitionErrors, ["broken: bad definition"]);
    assert.equal(result.matches[0].css, "#save");
    assert.equal(result.matches[0].evidence.role, "button");
    assert.equal(result.matches[0].evidence.text, "Save now");
    assert.equal(result.matches[0].evidence.attributes["aria-label"], "Save");
    assert.deepEqual(result.matches[0].failed, [
      "fails",
      "throws (invalid check)",
    ]);
    assert.equal(result.matches[1].css, null);
    assert.equal(result.matches[1].cssError, "no selector");
    assert.equal(result.matches[1].evidence.enabled, false);
  });
});
test("selector resolver returns query errors and can skip CSS compilation", async t => {
  await browserTest(t, async (page, url) => {
    await load(page, url, "selector_resolve");
    const result = await page.evaluate(() => {
      /** Fake selector engine covering query failure and empty results. */
      class Engine {
        /** Accept an unused stored-selector definition. */
        define() {}
        /** Resolve a fixture expression.
         * @param {string} expression Expression to resolve.
         * @returns {Element[]} Empty match list.
         * @throws {Error} When the expression is the broken fixture.
         */
        query(expression) {
          if (expression === "bad") throw new Error("bad query\ndetail");
          return [];
        }
      }
      Object.defineProperty(globalThis, "__EXACTUS_ES__", {
        value: Engine,
        configurable: true,
      });
      const resolve = /** @type {Function} */ (
        Reflect.get(globalThis, "selector_resolve")
      );
      return {
        failed: resolve({
          expression: "bad",
          definitions: {},
          checks: [],
          compile: true,
        }),
        empty: resolve({
          expression: "none",
          definitions: {},
          checks: [],
          compile: false,
        }),
      };
    });
    assert.equal(result.failed.error, "bad query");
    assert.equal(result.failed.count, 0);
    assert.deepEqual(result.empty.matches, []);
  });
});
test("selector sandbox exposes targets, facades, variables and streams", async t => {
  await browserTest(t, async (page, url) => {
    await load(page, url, "selector_sandbox");
    const result = await page.evaluate(async () => {
      const first = document.createElement("p");
      first.id = "first";
      const second = document.createElement("p");
      second.id = "second";
      document.body.append(first, second);
      /** Fake selector engine used by the sandbox facade. */
      class Engine {
        /** Define a stored selector.
         * @param {string} name Stored selector name.
         * @throws {Error} When the fixture requests a broken definition.
         */
        define(name) {
          if (name === "broken") throw new Error("ignored");
        }
        /** Resolve the first matching fixture element.
         * @param {string} text Selector text.
         * @returns {Element|null} First fixture element, when selected.
         */
        queryOne(text) {
          return text === "named" ? first : null;
        }
        /** Resolve all matching fixture elements.
         * @param {string} text Selector text.
         * @returns {Element[]} Matching fixture elements.
         */
        query(text) {
          return text === "named" ? [first, second] : [];
        }
        /** Resolve one target chain.
         * @param {string} text Selector text.
         * @returns {Element[]} Matching fixture chain.
         */
        queryChain(text) {
          return text === "#first" ? [first] : [second];
        }
      }
      Object.defineProperty(globalThis, "__EXACTUS_ES__", {
        value: Engine,
        configurable: true,
      });
      const sandbox = /** @type {Function} */ (
        Reflect.get(globalThis, "selector_sandbox")
      );
      return sandbox({
        script:
          "__EXACTUS_FLOW__.vars.runs = (__EXACTUS_FLOW__.vars.runs ?? 0) + 1; " +
          "__EXACTUS_FLOW__.log('target', __EXACTUS_FLOW__.target.id, {ok: true}); " +
          "return [document.querySelector('named').id, " +
          "document.querySelectorAll('named').length, window === self, " +
          "globalThis === window, __EXACTUS_FLOW__.logs.length]",
        definitions: { valid: ".x", broken: "bad(" },
        vars: {},
        logs: [],
        warnings: [],
        errors: [],
        flowId: "flow-1",
        actionId: "action-1",
        runId: "run-1",
        flowName: "Flow",
        actionKind: "javascript",
        actionLabel: "Script",
        project: { id: "project-1", name: "Project", revision: "1" },
        context: { id: "context-1", name: "Context", baseUrl: "", origin: "" },
        targets: ["#first", "#second"],
        indices: [0, 1],
        count: 2,
      });
    });
    assert.equal(result.results.length, 2);
    assert.deepEqual(result.results[0].value, ["first", 2, true, true, 1]);
    assert.deepEqual(result.results[1].value, ["first", 2, true, true, 2]);
    assert.equal(result.results[0].out[0].message, 'target first {"ok":true}');
    assert.equal(result.results[1].out[0].message, 'target second {"ok":true}');
    assert.equal(result.vars.runs, 2);
  });
});
test("selector sandbox handles expressions, assertions and compile errors", async t => {
  await browserTest(t, async (page, url) => {
    await load(page, url, "selector_sandbox");
    const result = await page.evaluate(async () => {
      /** Minimal selector engine for expression and error scenarios. */
      class Engine {
        /** Accept an unused stored-selector definition. */
        define() {}
        /** Return an empty target chain.
         * @returns {Element[]} Empty chain.
         */
        queryChain() {
          return [];
        }
      }
      Object.defineProperty(globalThis, "__EXACTUS_ES__", {
        value: Engine,
        configurable: true,
      });
      const sandbox = /** @type {Function} */ (
        Reflect.get(globalThis, "selector_sandbox")
      );
      const context = {
        definitions: {},
        vars: {},
        logs: [],
        warnings: [],
        errors: [],
        flowId: "flow-1",
        actionId: "action-1",
        runId: "run-1",
        flowName: "Flow",
        actionKind: "javascript",
        actionLabel: "Script",
        project: { id: "project-1", name: "Project", revision: "1" },
        context: { id: "context-1", name: "Context", baseUrl: "", origin: "" },
        targets: [],
        indices: [0],
        count: 1,
      };
      return {
        expression: await sandbox({
          ...context,
          script: "({answer: 42})",
        }),
        assertion: await sandbox({
          ...context,
          script: "__EXACTUS_FLOW__.assert(false, 'expected failure')",
        }),
        compile: await sandbox({
          ...context,
          script: ")",
          indices: [2, 3],
        }),
      };
    });
    assert.deepEqual(result.expression.results[0].value, { answer: 42 });
    assert.equal(result.assertion.results[0].error, "expected failure");
    assert.deepEqual(
      result.compile.results.map((/** @type {{index:number}} */ item) => item.index),
      [2, 3],
    );
    assert.ok(
      result.compile.results.every(
        (/** @type {{error:string}} */ item) => item.error.length > 0,
      ),
    );
  });
});
test("selector sandbox exposes the exactus facade and edge cases", async t => {
  await browserTest(t, async (page, url) => {
    await load(page, url, "selector_sandbox");
    const result = await page.evaluate(async () => {
      /** Minimal selector engine for exactus-facade scenarios. */
      class Engine {
        /** Accept an unused stored-selector definition. */
        define() {}
        /** Resolve stored selectors to an empty list.
         * @returns {Element[]} Empty match list.
         */
        query() {
          return [];
        }
        /** Resolve stored selectors to no element.
         * @returns {null} No match.
         */
        queryOne() {
          return null;
        }
        /** Return an empty target chain.
         * @returns {Element[]} Empty chain.
         */
        queryChain() {
          return [];
        }
      }
      Object.defineProperty(globalThis, "__EXACTUS_ES__", {
        value: Engine,
        configurable: true,
      });
      const sandbox = /** @type {Function} */ (
        Reflect.get(globalThis, "selector_sandbox")
      );
      const context = {
        definitions: {},
        vars: {},
        logs: [],
        warnings: [],
        errors: [],
        flowId: "flow-1",
        actionId: "action-1",
        runId: "run-1",
        flowName: "Flow",
        actionKind: "javascript",
        actionLabel: "Script",
        project: { id: "project-1", name: "Project", revision: "1" },
        context: { id: "context-1", name: "Context", baseUrl: "", origin: "" },
        targets: [],
        indices: [0],
        count: 1,
      };
      return {
        facade: await sandbox({
          ...context,
          script:
            "exactus.vars.set('seen', 7); " +
            "const meta = exactus.vars.metadata('seen'); " +
            "exactus.warn('warned'); " +
            "exactus.error('failed'); " +
            "const circular = {}; " +
            "circular.self = circular; " +
            "exactus.log(circular); " +
            "window.__probe = meta.available; " +
            "return [exactus.vars.get('seen'), meta.name, meta.type, " +
            "meta.available, exactus.vars.has('seen'), " +
            "exactus.vars.has('missing'), " +
            "exactus.selectors.describe('#x').source, " +
            "exactus.flow.name, exactus.action.kind, " +
            "exactus.project.id, exactus.context.id, " +
            "exactus.selectors.query('named').length, " +
            "exactus.selectors.queryOne('named') === null]",
        }),
        invoked: await sandbox({
          ...context,
          script: "() => ({coarse: true, dpr: 3})",
        }),
        unserializable: await sandbox({
          ...context,
          script: "Symbol('mark')",
        }),
      };
    });
    assert.deepEqual(result.facade.results[0].value, [
      7,
      "seen",
      "number",
      true,
      true,
      false,
      "#x",
      "Flow",
      "javascript",
      "project-1",
      "context-1",
      0,
      true,
    ]);
    assert.deepEqual(result.facade.vars, { seen: 7 });
    assert.equal(result.facade.results[0].out[0].level, "warn");
    assert.equal(result.facade.results[0].out[1].level, "error");
    assert.equal(result.facade.results[0].out[2].message, "[object Object]");
    assert.deepEqual(result.invoked.results[0].value, {
      coarse: true,
      dpr: 3,
    });
    assert.equal(result.unserializable.results[0].value, "Symbol(mark)");
  });
});
