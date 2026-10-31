import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
/**
 * Evaluate a visual-cause browser operation inside a fresh VM context.
 *
 * @param {string} [name] Operation module name.
 * @param {Record<string, unknown>} [globals] VM sandbox globals.
 * @returns {any} Whatever the evaluated module returns.
 */
const operation = (name = "", globals = {}) => {
  const source = new URL(`../../../packages/visual_cause/js/${name}.js`, import.meta.url);
  return runInNewContext(readFileSync(source, "utf8"), globals, { filename: source.href });
};
/** CSSStyleRule stand-in with a mutable declaration list. */
class CSSStyleRule {
  selectorText = ".card";
  cssText = ".card { color: var(--tone); --tone: red; }";
  style = Object.assign(["color", "--tone", "display"], {
    getPropertyValue: (name = "") => ({ color: " var(--tone) ", "--tone": " red ", display: "block" })[name],
    getPropertyPriority: (name = "") => name === "color" ? "important" : "",
    removeProperty: (name = "") => {
      const index = this.style.indexOf(name);
      if (index >= 0) this.style.splice(index, 1);
      return name;
    },
  });
}
/** CSSContainerRule stand-in exposing a name and nested rules. */
class CSSContainerRule {
  name = "panel";
  conditionText = "(width > 10px)";
  cssRules = [new CSSStyleRule()];
}
for (const name of ["disable_declaration", "disable_declarations", "disable_rule"])
  test(`${name} handles missing sheets and nested flat rule indices`, () => {
    const first = new CSSStyleRule();
    const nested = new CSSStyleRule();
    const cssRules = [first, { cssRules: [nested] }, {}];
    /** Fake document exposing the sheet by id. */
    const document = { getElementById: () => ({ sheet: { cssRules } }) };
    const execute = operation(name, { document, CSSStyleRule });
    const absent = operation(name, { document: { getElementById: () => null }, CSSStyleRule });
    if (name === "disable_declaration") {
      assert.equal(absent([0, "color"]), false);
      assert.equal(execute([99, "color"]), false);
      assert.equal(execute([1, "color"]), true);
      assert.equal(nested.style.includes("color"), false);
      assert.equal(first.style.includes("color"), true);
    } else if (name === "disable_declarations") {
      assert.equal(absent([[0, "color"]]), false);
      assert.equal(execute([[0, "color"], [1, "--tone"], [99, "color"]]), true);
      assert.equal(first.style.includes("color"), false);
      assert.equal(nested.style.includes("--tone"), false);
    } else {
      assert.equal(absent(0), undefined);
      execute(99);
      assert.equal(first.style.length, 3);
      execute(1);
      assert.equal(nested.style.length, 0);
      assert.equal(first.style.length, 3);
      execute(0);
      assert.equal(first.style.length, 0);
    }
  });
test("rules serialize nested matches, declaration priority and missing sheets", () => {
  const rule = new CSSStyleRule();
  /** Fake window exposing selector probes. */
  const window = { __cssCauseQueryAll: () => [{ id: "target" }], __cssCauseSelector: (node = { id: "" }) => `#${node.id}` };
  /** Fake document exposing the sheet by id. */
  const document = { getElementById: () => ({ sheet: { cssRules: [{ cssRules: [rule] }, {}] } }) };
  const rows = JSON.parse(operation("rules", { document, window, CSSStyleRule })());
  assert.equal(rows.length, 1);
  assert.deepEqual(rows[0].matched, ["#target"]);
  assert.equal(rows[0].index, 0);
  assert.deepEqual(rows[0].declarations, ["color: var(--tone) !important", "--tone: red", "display: block"]);
  assert.equal(operation("rules", { document: { getElementById: () => null } })(), "[]");
});
test("CSS variables retain dependency references and nested conditions", () => {
  /** Fake window exposing selector probes. */
  const window = { __cssCauseQueryAll: () => [{ id: "target" }], __cssCauseSelector: (node = { id: "" }) => `#${node.id}` };
  const inaccessible = { get cssRules() { throw new Error("cross-origin"); } };
  const document = { styleSheets: [inaccessible, { cssRules: [{ conditionText: "screen", cssRules: [new CSSStyleRule()] }, { cssRules: [new CSSStyleRule()] }] }] };
  const rows = JSON.parse(operation("css_variables", { document, window, CSSStyleRule })());
  assert.equal(rows.length, 4);
  assert.deepEqual(rows[0].references, ["--tone"]);
  assert.equal(rows[0].defines, null);
  assert.equal(rows[0].important, true);
  assert.deepEqual(rows[0].conditions, ["screen"]);
  assert.equal(rows[1].defines, "--tone");
  assert.deepEqual(rows[2].conditions, []);
  assert.equal(rows[3].order, 3);
});
test("container rule discovery retains parent context and skips inaccessible sheets", () => {
  const inaccessible = { get cssRules() { throw new Error("cross-origin"); } };
  const parent = new CSSContainerRule();
  const nested = new CSSContainerRule();
  nested.name = "child";
  Reflect.set(parent, "cssRules", [{ cssRules: [nested] }]);
  const document = { styleSheets: [inaccessible, { cssRules: [parent, {}] }] };
  const rows = JSON.parse(operation("container_rules", { document })());
  assert.equal(rows.length, 2);
  assert.equal(rows[0].name, "panel");
  assert.deepEqual(rows[1].parents, ["@container panel (width > 10px)"]);
  assert.equal(rows[1].condition_evaluation, "requires-container-context");
});
test("element overrides reject missing targets and set important declarations", () => {
  const calls = new Map();
  /**
   * Fake element recording style mutations.
   *
   * @param {string} name Declaration name.
   * @param {string} value Declaration value.
   * @param {string} priority Declaration priority.
   */
  const element = { style: { setProperty: (name = "", value = "", priority = "") => calls.set(name, [value, priority]) } };
  /**
   * Fake window resolving the target selector.
   *
   * @param {string} selector Query selector.
   */
  const window = { __cssCauseQuery: (selector = "") => selector === "#target" ? element : null };
  const override = operation("override_element", { window });
  assert.equal(override(["#missing", { color: "red" }]), false);
  assert.equal(override(["#target", { color: "red", display: "block" }]), true);
  assert.deepEqual([...calls], [["color", ["red", "important"]], ["display", ["block", "important"]]]);
});
test("prepare removes stray styles, pauses videos, and installs a stylesheet", () => {
  /** @type {unknown[]} */
  const removed = [];
  /** @type {string[]} */
  const paused = [];
  const styleNode = { id: "" };
  const document = {
    querySelectorAll: (selector = "") =>
      selector.includes("stylesheet")
        ? [
            { id: "__css_cause_style__", remove: () => removed.push("kept") },
            { id: "stray", remove: () => removed.push("stray") },
          ]
        : [{ pause: () => paused.push("video") }],
    createElement: () => styleNode,
    head: { append: (/** @type {unknown} */ node) => removed.push(node) },
  };
  assert.equal(operation("prepare", { document })(), "ok");
  assert.deepEqual(removed.slice(0, 1), ["stray"]);
  assert.deepEqual(paused, ["video"]);
  assert.equal(removed.at(-1), styleNode);
  assert.equal(styleNode.id, "__css_cause_style__");
});
test("install helpers build selectors and resolve standard and extended queries", () => {
  const child = {
    id: "",
    localName: "span",
    classList: ["tone"],
    nodeType: 1,
    parentElement: /** @type {object | null} */ (null),
  };
  const parent = {
    id: "root",
    localName: "div",
    classList: [],
    nodeType: 1,
    children: [child, { localName: "span" }, { localName: "b" }],
    parentElement: null,
  };
  child.parentElement = parent;
  /** @type {string[]} */
  const engineQueries = [];
  /** Selector engine stand-in recording issued queries. */
  class ExtendedSelector {
    /** @type {object} */
    documentRoot;
    /**
     * @param {object} documentRoot Query root.
     */
    constructor(documentRoot) {
      this.documentRoot = documentRoot;
    }
    /**
     * Record and answer an extended selector query.
     *
     * @param {string} [selector] Selector text.
     * @returns {string[]} Matching marker ids.
     * @throws {Error} When the selector is "fail".
     */
    query(selector = "") {
      engineQueries.push(selector);
      return selector === "fail" ? (() => { throw new Error("bad"); })() : ["extended-hit"];
    }
  }
  const document = {
    querySelectorAll: (selector = "") => {
      if (selector === "div") return ["native-a", "native-b"];
      throw new Error("unsupported selector");
    },
  };
  /** @type {{
   *   ExtendedSelector?: typeof ExtendedSelector,
   *   __cssCauseSelector: (node: {id?: string, localName?: string,
   *     classList?: string[]}) => string,
   *   __cssCauseQueryAll: (selector: string) => Iterable<unknown>,
   *   __cssCauseQuery: (selector: string) => unknown,
   *   __cssCauseExtended?: unknown
   * }} */
  const window = /** @type {any} */ ({ ExtendedSelector });
  const globals = {
    CSS: { escape: (/** @type {unknown} */ value) => `E<${value}>` },
    Node: { ELEMENT_NODE: 1 },
    document,
    window,
  };
  assert.equal(operation("install_helpers", globals)(), "ok");
  assert.equal(window.__cssCauseSelector({ id: "card" }), "#E<card>");
  assert.equal(
    window.__cssCauseSelector(child),
    "div > span.E<tone>:nth-of-type(1)",
  );
  assert.deepEqual([...window.__cssCauseQueryAll("div")], ["native-a", "native-b"]);
  assert.deepEqual([...window.__cssCauseQueryAll(":has(x)")], ["extended-hit"]);
  assert.deepEqual([...window.__cssCauseQueryAll("fail")], []);
  assert.equal(window.__cssCauseQuery("div"), "native-a");
  delete window.ExtendedSelector;
  window.__cssCauseExtended = undefined;
  assert.deepEqual([...window.__cssCauseQueryAll(":has(x)")], []);
});
test("dom element serialization filters hidden nodes and builds stable selectors", () => {
  const classes = ["card", "wide", "shadow", "extra"];
  const target = {
    id: "",
    localName: "article",
    classList: classes,
    nodeType: 1,
    textContent: "  many   spaces \n text  ",
    getBoundingClientRect: () => ({ width: 4, height: 3, x: 2, y: 5 }),
    parentElement: /** @type {object | null} */ (null),
  };
  const parent = {
    id: "root",
    localName: "section",
    classList: [],
    nodeType: 1,
    children: [target, { localName: "article" }],
    getBoundingClientRect: () => ({ width: 1, height: 1, x: 0, y: 0 }),
    parentElement: null,
  };
  target.parentElement = parent;
  const hidden = {
    id: "gone",
    localName: "p",
    classList: [],
    nodeType: 1,
    getBoundingClientRect: () => ({ width: 0, height: 1, x: 0, y: 0 }),
    parentElement: null,
  };
  const document = { documentElement: parent };
  const style = { visibility: "visible", display: "block" };
  const globals = {
    CSS: { escape: (/** @type {unknown} */ value) => `E<${value}>` },
    Node: { ELEMENT_NODE: 1 },
    HTMLElement: class {},
    document,
    getComputedStyle: () => style,
    scrollX: 10,
    scrollY: 20,
  };
  const rows = /** @type {any[]} */ (
    JSON.parse(
      operation("dom_elements", globals)([target, hidden, parent]),
    )
  );
  assert.equal(rows.length, 2);
  const targetRow = rows.find(row => row.tag === "article");
  assert.equal(targetRow.selector, "article.E<card>.E<wide>.E<shadow>:nth-of-type(1)");
  assert.equal(targetRow.classes, "card wide shadow extra");
  assert.equal(targetRow.text, "many spaces text");
  assert.equal(targetRow.x, 12);
  assert.equal(targetRow.y, 25);
  assert.equal(rows.find(row => row.tag === "section").selector, "#E<root>");
});
test("element inventory walks shadow roots and serializes typed styles", () => {
  /** CSSUnitValue stand-in carrying a numeric value and unit. */
  class CSSUnitValue {
    constructor(value = 0, unit = "px") {
      this.value = value;
      this.unit = unit;
    }
  }
  /** CSSKeywordValue stand-in carrying a keyword. */
  class CSSKeywordValue {
    constructor(value = "") {
      this.value = value;
    }
  }
  const textNode = { nodeType: 3, textContent: "  own text " };
  const shadowChild = {
    localName: "b",
    children: [],
    childNodes: [],
    getBoundingClientRect: () => ({ width: 2, height: 2, x: 0, y: 0 }),
    computedStyleMap: null,
    shadowRoot: null,
  };
  const shadow = { children: [shadowChild] };
  const child = {
    localName: "span",
    children: [],
    childNodes: [textNode],
    textContent: "child",
    getBoundingClientRect: () => ({ width: 2, height: 2, x: 1, y: 1 }),
    computedStyleMap: () => [
      ["width", [new CSSUnitValue(5, "px")]],
      ["color", new CSSKeywordValue("red")],
      ["display", "block"],
    ],
    shadowRoot: shadow,
  };
  const hidden = {
    localName: "i",
    children: [],
    childNodes: [],
    getBoundingClientRect: () => ({ width: 0, height: 0, x: 0, y: 0 }),
    shadowRoot: null,
  };
  const root = {
    localName: "html",
    children: [child, hidden],
    childNodes: [],
    getBoundingClientRect: () => ({ width: 9, height: 9, x: 0, y: 0 }),
    computedStyleMap: null,
    shadowRoot: null,
  };
  const style = Object.assign(["position"], {
    display: "block",
    visibility: "visible",
    position: "static",
    zIndex: "0",
    overflowX: "visible",
    overflowY: "visible",
    getPropertyValue: (/** @type {string} */ name) =>
      /** @type {Record<string, string>} */ ({ position: "static" })[name],
  });
  const beforeAfter = { content: "none" };
  const document = { documentElement: root };
  const window = {
    __cssCauseSelector: (/** @type {{localName: string}} */ node) =>
      `#${node.localName}`,
  };
  const globals = {
    CSSUnitValue,
    CSSKeywordValue,
    Node: { TEXT_NODE: 3, ELEMENT_NODE: 1 },
    ShadowRoot: class {},
    document,
    window,
    getComputedStyle: (
      /** @type {unknown} */ _node,
      /** @type {string} */ pseudo = "",
    ) => pseudo ? beforeAfter : style,
    scrollX: 0,
    scrollY: 0,
  };
  const rows = /** @type {any[]} */ (
    JSON.parse(operation("elements", globals)())
  );
  const tags = rows.map(row => row.tag);
  assert.deepEqual(tags, ["span", "b"]);
  const span = rows[0];
  assert.equal(span.domPath, "html-root/span[0]");
  assert.equal(span.parentPath, "");
  assert.equal(span.ownText, "own text");
  assert.equal(span.beforeContent, "none");
  assert.equal(span.typedComputed.width[0].value, 5);
  assert.equal(span.typedComputed.width[0].unit, "px");
  assert.equal(span.typedComputed.color.value, "red");
  assert.equal(span.typedComputed.display.type, "String");
  assert.equal(rows[1].domPath, "html-root/span[0]/#shadow-root/b[0]");
});
