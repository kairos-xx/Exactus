import assert from "node:assert/strict";
import { test } from "node:test";
import { installDom, inputEvent, keyEvent, FakeElement } from "./dom-stub.mjs";
installDom();
await import("../../../../packages/widgets/widget_selector/widget.js");
const { mountExpressionWidget } = await import(
  "../../../../packages/widgets/widget_selector/index.js"
);
const { icon } = await import(
  "../../../../packages/widgets/widget_selector/icons.js"
);
const { buildShape, joinOf } = await import(
  "../../../../packages/widgets/widget_selector/shapes.js"
);
const { suggest, createSampler, ENVIRONMENT_VARIABLES } = await import(
  "../../../../packages/widgets/widget_selector/suggest.js"
);
const { createMenu } = await import(
  "../../../../packages/widgets/widget_selector/mention-menu.js"
);
/** Minimal suggestion engine stand-in for menu tests. */
class FakeEngine {
  static SIGNATURES = {
    child: { roles: ["subject", "part"], min: 2 },
    has: { roles: ["subject"], variadicRole: "part", min: 1 },
  };
  static CAPABILITIES = {
    predicateTypes: { text: "text", width: "number", visible: "boolean" },
  };
  static lintResult = /** @type {(text: string) => any[]} */ (() => []);
  /**
   * Return the scripted lint findings for a draft.
   *
   * @param {string} text Draft text.
   * @returns {any[]} Scripted lint findings.
   */
  lint(text) {
    return FakeEngine.lintResult(text);
  }
}
const STATS = {
  count: 2,
  visible: 2,
  inView: 1,
  enabled: 2,
  scanned: 10,
  truncated: false,
  elapsedMs: 3.4,
  nodes: [{ path: [0], label: "div", kind: "tag", count: 2 }],
  first: { tag: "div", css: "div.card", text: "hello" },
};
/**
 * Wait for a delay.
 *
 * @param {number} ms Delay in milliseconds.
 * @returns {Promise<void>} Resolution after the delay.
 */
const sleep = ms =>
  new Promise(resolve => {
    setTimeout(resolve, ms);
  });
/**
 * @typedef {object} MountOptions
 * @property {string} [value] Initial carrier value.
 * @property {boolean} [startAsText] Mount in text mode.
 * @property {object} [host] Picker/stats host.
 * @property {object} [providers] Footer providers.
 * @property {boolean} [multiple] Multi-line lint mode.
 */
/**
 * Mount the widget under a fresh carrier.
 *
 * @param {MountOptions} [options] Mount overrides.
 * @returns {{parent: HTMLDivElement, carrier: HTMLTextAreaElement,
 *   widget: ReturnType<typeof mountExpressionWidget>}} Mounted fixture.
 */
const mount = (options = {}) => {
  const parent = document.createElement("div");
  const carrier = document.createElement("textarea");
  carrier.value = options.value ?? "div.card";
  parent.append(carrier);
  const widget = mountExpressionWidget(carrier, {
    engine: new FakeEngine(),
    label: "Selector",
    ...options,
  });
  return { parent, carrier, widget };
};
/**
 * Cast a DOM query result to the stub element type.
 *
 * @param {unknown} node Query result.
 * @returns {FakeElement} The node as a fake element.
 */
const asElement = node =>
  /** @type {FakeElement} */ (/** @type {unknown} */ (node));
/**
 * Collect descendant matches as fake elements.
 *
 * @param {{querySelectorAll: (selector: string) => Iterable<unknown>}} root
 *   Root element.
 * @param {string} selector Descendant selector.
 * @returns {FakeElement[]} Matching descendants.
 */
const qsa = (root, selector) =>
  /** @type {FakeElement[]} */ (
    /** @type {unknown} */ ([...root.querySelectorAll(selector)])
  );
/**
 * Locate the widget's draft editor.
 *
 * @param {ReturnType<typeof mountExpressionWidget>} widget Widget API.
 * @returns {FakeElement} The draft element.
 */
const draftOf = widget =>
  /** @type {FakeElement} */ (
    /** @type {unknown} */ (widget.element.querySelector(".ese-draft"))
  );
test("mount hides the carrier and mirrors its value", () => {
  const { carrier, widget } = mount({ value: "div.card" });
  assert.equal(carrier.hidden, true);
  assert.equal(widget.value, "div.card");
  assert.equal(widget.mode(), "expression");
  assert.ok(widget.element.classList.contains("ese-widget"));
  assert.ok(widget.element.querySelectorAll(".ese-draft").length > 0);
  widget.destroy();
  assert.equal(carrier.hidden, false);
});
test("mountExpressionWidget rejects unsupported languages", () => {
  const carrier = document.createElement("textarea");
  assert.throws(
    () =>
      mountExpressionWidget(
        carrier,
        /** @type {any} */ ({ language: "python" }),
      ),
    /language/i,
  );
});
test("value setter syncs carrier and emits change events", () => {
  const { carrier, widget } = mount();
  /** @type {string[]} */
  const seen = [];
  widget.on("change", (/** @type {string} */ value) => seen.push(value));
  widget.value = "span.item";
  assert.equal(widget.value, "span.item");
  assert.equal(carrier.value, "span.item");
  assert.deepEqual(seen, ["span.item"]);
  widget.destroy();
});
test("setMode toggles between expression and text surfaces", () => {
  const { widget } = mount();
  /** @type {string[]} */
  const modes = [];
  widget.on("mode", (/** @type {string} */ mode) => modes.push(mode));
  widget.setMode("text");
  assert.equal(widget.mode(), "text");
  assert.equal(asElement(widget.element.querySelector(".ese-text")).hidden, false);
  widget.setMode("expression");
  assert.equal(widget.mode(), "expression");
  assert.deepEqual(modes, ["text", "expression"]);
  widget.destroy();
});
test("startAsText mounts the widget in text mode", () => {
  const { widget } = mount({ startAsText: true });
  assert.equal(widget.mode(), "text");
  widget.destroy();
});
test("validation paints diagnostics and the fix button applies suggestions", () => {
  FakeEngine.lintResult = () => [
    {
      code: "typo",
      message: "did you mean .card",
      offset: 4,
      length: 3,
      line: 1,
      column: 5,
      severity: "error",
      suggestion: { offset: 4, length: 3, text: "card" },
    },
    {
      code: "slow",
      message: "selector is slow",
      offset: 0,
      length: 3,
      line: 1,
      column: 1,
      severity: "warning",
    },
  ];
  const { widget } = mount();
  /** @type {unknown[]} */
  const results = [];
  widget.on("validate", (/** @type {unknown} */ result) => results.push(result));
  widget.value = "div.crx";
  const last = widget.validation();
  assert.equal(last.state, "error");
  assert.equal(last.errors, 1);
  assert.equal(last.warnings, 1);
  const message = asElement(widget.element.querySelector(".ese-message"));
  assert.equal(message.hidden, false);
  const fix = qsa(widget.element, "button").find(button =>
    button.textContent.includes("Use"),
  );
  assert.ok(fix);
  fix.dispatchEvent(new Event("click"));
  assert.equal(widget.value, "div.card");
  widget.value = "div.crx";
  const next = qsa(widget.element, "button").find(
    button => button.getAttribute("aria-label") === "Next problem",
  );
  assert.ok(next);
  next.dispatchEvent(new Event("click"));
  assert.equal(widget.validation().index, 1);
  widget.element.dispatchEvent(keyEvent("F8"));
  widget.element.dispatchEvent(keyEvent("F8", { shiftKey: true }));
  widget.destroy();
  FakeEngine.lintResult = () => [];
});
test("valid text reports an idle-valid semaphore state", () => {
  FakeEngine.lintResult = () => [];
  const { widget } = mount();
  widget.value = "a[href]";
  assert.equal(widget.validation().state, "valid");
  const dot = asElement(widget.element.querySelector(".ese-dot"));
  assert.equal(dot.getAttribute("data-state"), "valid");
  widget.value = "";
  assert.equal(widget.validation().state, "idle");
  widget.destroy();
});
test("multiple mode lints each non-empty line", () => {
  /** @type {string[]} */
  const calls = [];
  FakeEngine.lintResult = () => [];
  const engine = new FakeEngine();
  const original = engine.lint;
  engine.lint = line => {
    calls.push(line);
    return original.call(engine, line);
  };
  const carrier = document.createElement("textarea");
  carrier.value = "";
  const parent = document.createElement("div");
  parent.append(carrier);
  const widget = mountExpressionWidget(carrier, {
    engine,
    label: "Selectors",
    multiple: true,
  });
  widget.value = "div\n\nspan";
  assert.deepEqual(calls, ["div", "span"]);
  widget.destroy();
});
test("typing into the draft opens suggestions and Enter commits", () => {
  const { widget } = mount({ value: "" });
  const draft = draftOf(widget);
  assert.ok(draft);
  draft.value = "ch";
  draft.dispatchEvent(inputEvent(draft));
  const menu = asElement(widget.element.querySelector(".ese-menu"));
  assert.equal(menu.hidden, false);
  draft.dispatchEvent(keyEvent("ArrowDown"));
  draft.dispatchEvent(keyEvent("Enter"));
  assert.ok(widget.value.length > 0);
  widget.destroy();
});
test("explicit menu request, branch expansion and Escape", () => {
  const { widget } = mount({ value: "" });
  const draft = draftOf(widget);
  draft.value = "";
  draft.dispatchEvent(keyEvent("ArrowDown"));
  const menu = asElement(widget.element.querySelector(".ese-menu"));
  if (menu.hidden === false) {
    draft.dispatchEvent(keyEvent("Escape"));
    assert.equal(menu.hidden, true);
  }
  draft.value = "@";
  draft.dispatchEvent(inputEvent(draft));
  if (asElement(menu).hidden === false) {
    draft.dispatchEvent(keyEvent("ArrowRight"));
    draft.dispatchEvent(keyEvent("ArrowLeft"));
    draft.dispatchEvent(keyEvent("Tab"));
  }
  widget.destroy();
});
test("Backspace dissolves the previous token and Home/End move the caret", () => {
  const { widget } = mount({ value: "div span" });
  const draft = draftOf(widget);
  draft.value = "";
  draft.dispatchEvent(keyEvent("Backspace"));
  assert.notEqual(widget.value, "div span");
  widget.setMode("text");
  widget.setMode("expression");
  const again = draftOf(widget);
  again.value = "";
  again.dispatchEvent(keyEvent("Home"));
  again.dispatchEvent(keyEvent("End"));
  again.dispatchEvent(keyEvent("ArrowLeft"));
  again.dispatchEvent(keyEvent("ArrowRight"));
  widget.destroy();
});
test("clicking the surface places the caret at the nearest boundary", () => {
  const { widget } = mount({ value: "div span" });
  widget.surface.dispatchEvent(
    Object.assign(new Event("click", { bubbles: true }), {
      clientX: 50,
      clientY: 10,
    }),
  );
  widget.focus();
  widget.destroy();
});
test("setTheme sets and clears the data-theme attribute", () => {
  const { widget } = mount();
  widget.setTheme("dark");
  assert.equal(widget.element.getAttribute("data-theme"), "dark");
  widget.setTheme(null);
  assert.equal(widget.element.hasAttribute("data-theme"), false);
  widget.destroy();
});
test("footer renders chips, stats panel and pick alternatives", async () => {
  /** @type {((result: Record<string, unknown>) => void) | null} */
  let pickedCallback = null;
  const host = {
    pick: (/** @type {(result: Record<string, unknown>) => void} */ done) => {
      pickedCallback = done;
    },
    highlight: () => {},
    stats: async () => STATS,
  };
  const { widget } = mount({ host, providers: { expected: () => 2 } });
  widget.value = "div.card";
  await sleep(260);
  const panel = asElement(widget.element.querySelector(".ese-panel"));
  const pickButton = qsa(widget.element, "button").find(
    button => button.getAttribute("aria-label") === "Pick on page",
  );
  assert.ok(pickButton);
  pickButton.dispatchEvent(new Event("click"));
  assert.ok(pickedCallback);
  /** @type {(result: Record<string, unknown>) => void} */
  const picked = pickedCallback;
  picked({
    element: { tag: "div", text: "hi" },
    selector: "#one",
    matches: 1,
    alternatives: [
      { strategy: "id", selector: "#one", matches: 1 },
      { strategy: "class", selector: ".card", matches: 2 },
    ],
  });
  assert.equal(widget.value, "#one");
  const rows = qsa(widget.element, ".ese-pick-row");
  assert.ok(rows.length >= 2);
  const radios = qsa(widget.element, "input").filter(
    input => input.type === "radio",
  );
  const other = radios.find(radio => !radio.checked);
  if (other)
    other.dispatchEvent(new Event("change"));
  const chevron = qsa(widget.element, "button").find(
    button => button.getAttribute("aria-label") === "Show stats",
  );
  assert.ok(chevron);
  chevron.dispatchEvent(new Event("click"));
  assert.equal(panel.hidden, false);
  const close = qsa(widget.element, "button").find(
    button => button.getAttribute("aria-label") === "Dismiss",
  );
  assert.ok(close);
  close.dispatchEvent(new Event("click"));
  const highlight = qsa(widget.element, "button").find(
    button => button.getAttribute("aria-label") === "Highlight on page",
  );
  assert.ok(highlight);
  highlight.dispatchEvent(new Event("click"));
  highlight.dispatchEvent(new Event("click"));
  widget.destroy();
});
test("stats errors clear chips and live variables reveal devices chip", async () => {
  const failure = Object.assign(new Error("no variable"), {
    code: "missing-variable",
  });
  const host = {
    stats: async () => {
      throw failure;
    },
    highlight: () => {},
  };
  const { widget } = mount({ host, value: "{{flow/x}}" });
  widget.value = "div";
  await sleep(260);
  widget.destroy();
});
test("icon builds an svg element and rejects nothing for known names", () => {
  const node = icon("check", true);
  assert.equal(node.localName, "svg");
  assert.equal(node.getAttribute("viewBox"), "0 0 24 24");
  assert.equal(node.getAttribute("data-always"), "");
  assert.ok(node.children.length > 0);
});
test("buildShape renders cap, body and horn for each type", () => {
  const types = /** @type {("open" | "close" | "leaf" | "slot")[]} */ (
    ["open", "close", "leaf", "slot"]
  );
  for (const type of types) {
    const shape = buildShape({
      type,
      kind: "tag",
      label: "div",
      editable: true,
      title: "tag",
    });
    assert.equal(shape.getAttribute("data-type"), type);
    assert.ok(shape.children.length >= 1);
  }
  assert.equal(joinOf("open", "leaf"), "flush");
  assert.equal(joinOf("leaf", "glyph"), "tight");
  assert.equal(joinOf("descendant", "leaf"), "descendant");
});
test("createMenu paints rows, expands branches and chooses items", () => {
  const host = document.createElement("div");
  /** @type {import("../../../../packages/widgets/widget_selector/suggest.js").Item[]} */
  const chosen = [];
  const menu = createMenu({ host, onChoose: item => chosen.push(item) });
  /** @type {import("../../../../packages/widgets/widget_selector/suggest.js").Item[]} */
  const items = [
    {
      label: "device/",
      group: "Environment",
      branch: true,
      children: [{ label: "device/width", group: "Environment" }],
    },
    { label: "div", group: "Page" },
  ];
  menu.open("Suggestions", items, "device/");
  assert.equal(menu.isOpen(), true);
  assert.equal(menu.key(keyEvent("ArrowRight")), true);
  assert.equal(menu.key(keyEvent("ArrowLeft")), true);
  menu.key(keyEvent("ArrowDown"));
  menu.key(keyEvent("Enter"));
  const rows = qsa(menu.element, ".ese-item");
  const lastRow = rows.at(-1);
  assert.ok(lastRow);
  lastRow.dispatchEvent(
    Object.assign(new Event("mousedown", { bubbles: true }), {
      preventDefault: () => {},
    }),
  );
  assert.ok(chosen.length >= 1);
  menu.open("Again", items);
  assert.equal(menu.key(keyEvent("Escape")), true);
  assert.equal(menu.isOpen(), false);
  menu.open("Empty", []);
  assert.equal(menu.isOpen(), false);
  menu.close();
});
test("sampler counts tags, classes, ids and attributes once per scope", () => {
  const root = new FakeElement("div");
  const child = new FakeElement("button");
  child.className = "primary big";
  child.id = "go";
  child.setAttribute("data-kind", "cta");
  root.append(child);
  const sampler = createSampler({
    root: /** @type {Element} */ (/** @type {unknown} */ (root)),
    cap: 10,
  });
  const one = sampler.sample();
  assert.equal(one.tags.get("button"), 1);
  assert.equal(one.classes.get("primary"), 1);
  assert.equal(one.ids.get("go"), 1);
  assert.equal(one.attributes.get("data-kind"), 1);
  const two = sampler.sample();
  assert.equal(sampler.reads, 1);
  sampler.invalidate();
  sampler.sample("main");
  assert.equal(sampler.reads, 2);
  assert.equal(two.scanned, one.scanned);
});
test("suggest covers tags, predicates, pseudos, variables and saved", () => {
  const root = new FakeElement("main");
  const card = new FakeElement("article");
  card.className = "card";
  card.id = "hero";
  card.setAttribute("data-role", "tile");
  root.append(card);
  const sampler = createSampler({
    root: /** @type {Element} */ (/** @type {unknown} */ (root)),
  });
  /**
   * Build a suggestion context with optional overrides.
   *
   * @param {Record<string, unknown>} [overrides] Context overrides.
   */
  const context = overrides =>
    /** @type {Parameters<typeof suggest>[0]} */ ({
      draft: "",
      signatures: FakeEngine.SIGNATURES,
      predicateTypes: FakeEngine.CAPABILITIES.predicateTypes,
      sampler,
      saved: [{ name: "cards", count: 3 }],
      variables: [
        { path: "flow/name", scope: "flow", type: "text", value: "x" },
        { path: "device/width", scope: "env", type: "num" },
        { path: "loose", scope: "flow", type: "bool" },
      ],
      supports: () => true,
      ...overrides,
    });
  assert.ok(suggest(context({ draft: "art" })).items.length > 0);
  assert.ok(suggest(context({ draft: "ch" })).items.length > 0);
  assert.ok(
    suggest(context({ draft: ".c" })).items.some(i => i.label === ".card"),
  );
  assert.ok(
    suggest(context({ draft: "#h" })).items.some(i => i.label === "#hero"),
  );
  assert.ok(
    suggest(context({ draft: "[te" })).items.some(i =>
      i.label.includes("text"),
    ),
  );
  assert.ok(
    suggest(context({ draft: ":hov" })).items.some(i => i.label === ":hover"),
  );
  assert.ok(
    suggest(context({ draft: "::bef" })).items.some(
      i => i.label === "::before",
    ),
  );
  const mention = suggest(context({ draft: "@" }));
  assert.ok(mention.items.some(i => i.branch));
  assert.ok(
    suggest(context({ draft: "@dev" })).items.some(
      i => i.label === "device/width",
    ),
  );
  assert.ok(
    suggest(context({ draft: "@.c" })).items.some(i => i.label === ".card"),
  );
  const scoped = suggest(context({ draft: ".zzz", scope: "main" }));
  assert.ok(scoped.items !== undefined);
  const scopedTag = suggest(context({ draft: "zzz", scope: "main" }));
  assert.ok(scopedTag.items !== undefined);
  assert.ok(ENVIRONMENT_VARIABLES.length > 5);
});
