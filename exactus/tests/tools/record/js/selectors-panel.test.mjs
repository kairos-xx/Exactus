/** The selectors list, test result, tested-on pages and the selector inspector. */
import assert from "node:assert/strict";
import test from "node:test";
import { modulePage, WEB } from "./module-page.mjs";
/** Run a scenario in a blank page with the panel module loaded as `panel`.
 * @param {import("node:test").TestContext} t Test context.
 * @param {string} body Async function body receiving `panel`.
 * @returns {Promise<any>} The scenario's return value.
 */
const inPanel = async (t, body) => {
  /** @type {any} */
  let outcome;
  await modulePage(t, async page => {
    await page.evaluate(async (/** @type {string} */ web) => {
      const panel = await import(`${web}/selectors-panel.js`);
      /** A stored selector with fields overridden.
       * @param {Record<string, unknown>} extra Field overrides.
       * @returns {Record<string, unknown>} The selector.
       */
      const item = extra => ({
        selector_id: "s1",
        name: "card",
        expression: "css:.card",
        expected_count: 1,
        checks: ["[a]", "[b]"],
        validated_on: [{ url: "http://x/", at: "now", matches: 1 }],
        ...extra,
      });
      /** @type {any} */ (globalThis).env = { panel, item };
    }, WEB);
    outcome = await page.evaluate(
      `(async () => { const { panel, item } = globalThis.env; ${body} })()`,
    );
  });
  return outcome;
};
test("usage sentences count actions, selectors and conditions", async t => {
  const out = await inPanel(
    t,
    `const use = (a, s, c) => ({ actions: Array(a).fill({}), flows: a ? 1 : 0, selectors: Array(s).fill("x"), conditions: c });
     return [panel.usageSentence(undefined), panel.usageSentence(use(0,0,0)),
       panel.usageSentence(use(1,1,1)), panel.usageSentence(use(3,2,4))];`,
  );
  assert.deepEqual(out, [
    "Not used yet",
    "Not used yet",
    "Used by 1 action in 1 flow, 1 selector, 1 condition",
    "Used by 3 actions in 1 flow, 2 selectors, 4 conditions",
  ]);
});
test("the list is empty, then rows with flags, counts and selection", async t => {
  const out = await inPanel(
    t,
    `const box = document.createElement("div");
     panel.renderSelectorList(box, [], {}, null, () => {});
     const empty = box.textContent;
     const chosen = [];
     panel.renderSelectorList(box,
       [item({}), item({ selector_id: "s2", name: "other", validated_on: [] })],
       { s1: { actions: [{}, {}], flows: 1, selectors: [], conditions: 0 } },
       "s2", (id) => chosen.push(id));
     const rows = [...box.querySelectorAll("button")];
     rows[0].click();
     return { empty, chosen, count: rows.length,
       active: rows.map((r) => r.classList.contains("active")),
       pressed: rows.map((r) => r.getAttribute("aria-pressed")),
       flags: rows.map((r) => r.querySelector(".tree-item-flag") !== null),
       badges: rows.map((r) => r.querySelector(".tree-item-count").textContent) };`,
  );
  assert.match(out.empty, /No selectors yet/);
  assert.deepEqual(out.chosen, ["s1"]);
  assert.deepEqual(out.active, [false, true]);
  assert.deepEqual(out.pressed, ["false", "true"]);
  assert.deepEqual(out.flags, [false, true]);
  assert.deepEqual(out.badges, ["2", ""]);
});
test("test results cover running, idle, pass, fail, errors and truncation", async t => {
  const out = await inPanel(
    t,
    `const box = document.createElement("div");
     const text = () => box.textContent;
     const match = (i, extra = {}) => ({ index: i, css: ".c", css_error: null,
       rect: { x: 0, y: 0, width: 1, height: 1 }, tag: "div", text: "hi", failed: [], ...extra });
     const base = { expression: "x", selector_id: null, ok: true, count: 1,
       expected_count: 1, elapsed_ms: 5, polls: 1, error: null, definition_errors: [],
       cause: null, url: "u", matches: [match(0)] };
     const seen = {};
     panel.renderTestResult(box, null, true); seen.running = text();
     panel.renderTestResult(box, null); seen.idle = text();
     panel.renderTestResult(box, base); seen.pass = text();
     panel.renderTestResult(box, { ...base, ok: false, count: 0, matches: [],
       cause: { message: "Not there" } }); seen.fail = text();
     panel.renderTestResult(box, { ...base, ok: false, count: 2, matches: [] }); seen.plain = text();
     panel.renderTestResult(box, { ...base, ok: false, error: "Bad syntax",
       definition_errors: ["Unknown"], matches: [
         match(0, { css: null, css_error: "no css", tag: null, text: null, failed: ["[a]"] }),
         match(1, { css: null }) ] });
     seen.error = text();
     seen.rows = box.querySelectorAll(".selector-match").length;
     panel.renderTestResult(box, { ...base, count: 60, matches: Array.from({ length: 60 }, (_, i) => match(i)) });
     seen.long = box.querySelectorAll(".selector-match").length;
     seen.more = box.textContent.includes("And 10 more");
     return seen;`,
  );
  assert.match(out.running, /Testing against the live page/);
  assert.match(out.idle, /Test the expression/);
  assert.match(out.pass, /1 match.*in 5 ms/);
  assert.match(out.fail, /Not there.*Found 0 in 5 ms/);
  assert.match(out.plain, /2 matches/);
  assert.match(out.error, /Bad syntax/);
  assert.match(out.error, /Unknown/);
  assert.match(out.error, /Failed: \[a\]/);
  assert.match(out.error, /no css/);
  assert.match(out.error, /No selector found/);
  assert.match(out.error, /\(empty\)/);
  assert.equal(out.rows, 2);
  assert.equal(out.long, 50);
  assert.equal(out.more, true);
});
test("the tested-on area lists pages and warns about the open one", async t => {
  const out = await inPanel(
    t,
    `const box = document.createElement("div");
     const text = () => box.textContent;
     const seen = {};
     panel.renderSeen(box, null, ""); seen.none = text();
     panel.renderSeen(box, item({}), "http://x/"); seen.same = text();
     panel.renderSeen(box, item({ validated_on: [{ url: "http://x/", at: "", matches: 2 }] }), "http://other/");
     seen.other = text();
     return seen;`,
  );
  assert.match(out.none, /Not tested on any page yet/);
  assert.match(out.same, /http:\/\/x\/1 match$/);
  assert.match(out.other, /2 matches.*Not tested on the page that is open now/);
});
/** Scenario preamble building an inspector with a recording option set. */
const SETUP = `
  const calls = [];
  const options = (extra = {}) => ({
    selector: item({}),
    usage: { actions: [{ flow_id: "f", event_id: "e" }], flows: 1, selectors: [], conditions: 0 },
    labelFor: (f, e) => "Step " + f + "/" + e,
    pageUrl: "http://x/",
    test: null,
    engine: null,
    Editor: null,
    onSave: (v) => calls.push(["save", v]),
    onSaveCopy: (v) => calls.push(["copy", v]),
    onTest: (v) => calls.push(["test", v]),
    onDelete: () => calls.push(["delete"]),
    onOpenAction: (f, e) => calls.push(["open", f, e]),
    ...extra,
  });
  const mount = (opts) => {
    const view = panel.selectorInspector(opts);
    document.body.replaceChildren(view.fragment);
    return view;
  };
`;
test("the inspector reads the form back and wires every handler", async t => {
  const out = await inPanel(
    t,
    `${SETUP}
     const view = mount(options());
     const form = view.form;
     const mode = form.querySelector('[name="count_mode"]');
     const exact = form.querySelector('[name="count_exact"]');
     const hiddenOne = exact.hidden;
     mode.value = "exact"; mode.dispatchEvent(new Event("change"));
     exact.value = "4";
     const shown = !exact.hidden;
     form.querySelector('[name="name"]').value = " renamed ";
     form.querySelector('[name="checks"]').value = "[x]\\n\\n  [y] \\n";
     form.requestSubmit();
     form.querySelectorAll(".selector-live-actions button")[1].click();
     mode.value = "any";
     [...form.querySelectorAll(".selector-icon")][0].click();
     [...form.querySelectorAll(".selector-icon")][1].click();
     document.querySelector(".selector-open").click();
     return { calls, hiddenOne, shown, title: document.querySelector("h2").textContent,
       open: document.querySelector(".selector-open").textContent };`,
  );
  assert.equal(out.hiddenOne, true);
  assert.equal(out.shown, true);
  assert.equal(out.title, "card");
  assert.equal(out.open, "Step f/e");
  assert.equal(out.calls[0][0], "save");
  assert.deepEqual(out.calls[0][1], {
    selector_id: "s1",
    name: "renamed",
    expression: "css:.card",
    expected_count: 4,
    checks: ["[x]", "[y]"],
  });
  assert.equal(out.calls[1][1].expected_count, 4);
  assert.equal(out.calls[2][0], "copy");
  assert.equal(out.calls[2][1].expected_count, null);
  assert.deepEqual(out.calls.slice(3), [["delete"], ["open", "f", "e"]]);
});
test("the selector widget picks a generated strategy and reports page matches", async t => {
  const out = await inPanel(
    t,
    `${SETUP}
     const view = mount(options({
       onPick: (apply) => apply({ selector: "button", matches: 3, alternatives: [
         { strategy: "css", selector: "button", matches: 3 },
         { strategy: "role and name", selector: 'role=button[name="Save"]', matches: 1 },
       ] }),
       onTest: (values, done) => { calls.push(["highlight", values]); done({ count: 1 }); },
     }));
     const form = view.form;
     const buttons = [...form.querySelectorAll(".selector-live-actions button")];
     buttons[0].click();
     const strategy = form.querySelector(".selector-live-strategy");
     const picked = form.querySelector('[name="expression"]').value;
     buttons[1].click();
     return {
       labels: buttons.map(button => button.textContent),
       picked,
       choices: [...strategy.options].map(option => option.textContent),
       selected: strategy.value,
       count: form.querySelector(".selector-live-count").textContent,
       highlighted: calls[0][1].expression,
     };`,
  );
  assert.deepEqual(out.labels, ["Pick on page", "Highlight on page"]);
  assert.equal(out.picked, 'role=button[name="Save"]');
  assert.deepEqual(out.choices, [
    "css — 3 matches",
    "role and name — 1 match",
  ]);
  assert.equal(out.selected, "1");
  assert.equal(out.count, "1 match");
  assert.equal(out.highlighted, 'role=button[name="Save"]');
});
test("a new selector has no copy or delete and no actions list", async t => {
  const out = await inPanel(
    t,
    `${SETUP}
     const view = mount(options({ selector: null, usage: undefined }));
     const mode = view.form.querySelector('[name="count_mode"]').value;
     view.form.querySelector('[name="count_exact"]').value = "";
     return { title: document.querySelector("h2").textContent,
       sub: document.querySelector("small").textContent,
       icons: view.form.querySelectorAll(".selector-icon").length,
       used: document.querySelector(".selector-used").children.length, mode,
       hidden: view.form.querySelector('[name="expression"]').hidden };`,
  );
  assert.equal(out.title, "New selector");
  assert.equal(out.sub, "Not saved yet");
  assert.equal(out.icons, 0);
  assert.equal(out.used, 0);
  assert.equal(out.mode, "one");
  assert.equal(out.hidden, false);
});
test("the count modes map to null, a number or one", async t => {
  const out = await inPanel(
    t,
    `${SETUP}
     const modes = [];
     for (const expected of [null, 3, 1, undefined]) {
       const view = mount(options({ selector: item({ expected_count: expected }) }));
       modes.push(view.form.querySelector('[name="count_mode"]').value);
       view.form.requestSubmit();
     }
     return { modes, saved: calls.map((c) => c[1].expected_count) };`,
  );
  assert.deepEqual(out.modes, ["any", "exact", "one", "one"]);
  assert.deepEqual(out.saved, [null, 3, 1, 1]);
});
/** Scenario preamble adding a fake formula editor and lint engine. */
const EDITOR = `
  class FakeEditor extends EventTarget {
    constructor(host, config) {
      super();
      this.host = host;
      this.config = config;
      this.surface = document.createElement("div");
      this.atom = document.createElement("span");
      this.atom.dataset.role = "atom";
      this.atom.tabIndex = 0;
      this.surface.append(this.atom);
      host.after(this.surface);
      this.set = [];
    }
    set value(text) { this.set.push(text); }
  }
  class FakeEngine {
    static formatDiagnostic(issue) { return issue.message + "\\nsecond line"; }
    lint(text) { return text.includes("bad") ? [{ message: "Broken" }] : []; }
  }
`;
test("with an editor the formula view lints, toggles to text and back", async t => {
  const out = await inPanel(
    t,
    `${SETUP}${EDITOR}
     const view = mount(options({ Editor: FakeEditor, engine: new FakeEngine() }));
     const form = view.form;
     const toggle = form.querySelector(".selector-link");
     const expression = form.querySelector('[name="expression"]');
     const diagnostic = form.querySelector(".selector-diagnostic");
     const seen = {};
     seen.initial = { toggle: toggle.hidden, text: toggle.textContent, diagnosticHidden: diagnostic.hidden };
     toggle.click();
     seen.textMode = { label: toggle.textContent, expressionHidden: expression.hidden };
     expression.value = "bad thing";
     expression.dispatchEvent(new Event("input"));
     seen.diagnostic = diagnostic.textContent;
     toggle.click();
     seen.formulaMode = { label: toggle.textContent, expressionHidden: expression.hidden };
     const editorSurface = form.querySelector('[data-role="atom"]').parentElement;
     editorSurface.click();
     seen.focused = document.activeElement === form.querySelector('[data-role="atom"]');
     form.querySelector('[data-role="atom"]').click();
     return seen;`,
  );
  assert.deepEqual(out.initial, {
    toggle: false,
    text: "Edit as text",
    diagnosticHidden: true,
  });
  assert.deepEqual(out.textMode, {
    label: "Edit as expression",
    expressionHidden: false,
  });
  assert.equal(out.diagnostic, "Broken");
  assert.deepEqual(out.formulaMode, {
    label: "Edit as text",
    expressionHidden: true,
  });
  assert.equal(out.focused, true);
});
test("an empty expression starts in text mode and an editor change re-lints", async t => {
  const out = await inPanel(
    t,
    `${SETUP}${EDITOR}
     const made = [];
     class Spy extends FakeEditor { constructor(h, c) { super(h, c); made.push(this); } }
     const view = mount(options({ selector: item({ expression: "" }), Editor: Spy, engine: new FakeEngine() }));
     const expression = view.form.querySelector('[name="expression"]');
     const startsText = !expression.hidden;
     expression.value = "bad";
     made[0].dispatchEvent(new Event("change"));
     const diagnostic = view.form.querySelector(".selector-expression-field .selector-diagnostic");
     return { startsText, diag: diagnostic.textContent,
       shown: !diagnostic.hidden };`,
  );
  assert.equal(out.startsText, true);
  assert.equal(out.diag, "Broken");
  assert.equal(out.shown, true);
});
