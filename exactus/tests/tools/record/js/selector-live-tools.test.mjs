/** The shared Pick/Highlight/strategy row every selector editing surface mounts. */
import assert from "node:assert/strict";
import test from "node:test";
import { modulePage, WEB } from "./module-page.mjs";
/** Run a scenario in a blank page with the live-tools module loaded as `tools`.
 * @param {import("node:test").TestContext} t Test context.
 * @param {string} body Async function body receiving `tools`.
 * @returns {Promise<any>} The scenario's return value.
 */
const inTools = async (t, body) => {
  /** @type {any} */
  let outcome;
  await modulePage(t, async page => {
    await page.evaluate(async (/** @type {string} */ web) => {
      const tools = await import(`${web}/selector-live-tools.js`);
      /** Fresh value carrier plus call log for one mount.
       * @returns {{value:{value:string}, calls:any[], options:object}} The scenario state.
       */
      const state = () => {
        /** @type {any[]} */
        const calls = [];
        const box = { value: "" };
        return {
          value: box,
          calls,
          options: {
            getValue: () => box.value,
            /** @param {string} next New selector text. */
            setValue: next => {
              box.value = next;
              calls.push(["set", next]);
            },
          },
        };
      };
      /** @type {any} */ (globalThis).env = { tools, state };
    }, WEB);
    outcome = await page.evaluate(
      `(async () => { const { tools, state } = globalThis.env; ${body} })()`,
    );
  });
  return outcome;
};
test("pick builds strategy choices and applies the single-match one", async t => {
  const out = await inTools(
    t,
    `const s = state();
     let pickedApply = null;
     const view = tools.selectorLiveTools({
       ...s.options,
       onPick: apply => { pickedApply = apply; },
       onHighlight: (v, done) => s.calls.push(["highlight", v]),
     });
     document.body.replaceChildren(view.element);
     const buttons = document.querySelectorAll(".selector-live-actions button");
     buttons[0].click();
     pickedApply({ selector: "button", matches: 3, alternatives: [
       { strategy: "css", selector: "button", matches: 3 },
       { strategy: "role", selector: "role=button", matches: 1 },
     ] });
     const strategy = document.querySelector(".selector-live-strategy");
     return {
       labels: [...buttons].map(b => b.textContent),
       disabled: [buttons[0].disabled, buttons[1].disabled],
       choices: [...strategy.options].map(o => o.textContent),
       selected: strategy.value,
       value: s.value.value,
       count: document.querySelector(".selector-live-count").textContent,
     };`,
  );
  assert.deepEqual(out.labels, ["Pick on page", "Highlight on page"]);
  assert.deepEqual(out.disabled, [false, false]);
  assert.deepEqual(out.choices, ["css — 3 matches", "role — 1 match"]);
  assert.equal(out.selected, "1");
  assert.equal(out.value, "role=button");
  assert.equal(out.count, "1 match");
});
test("pick without alternatives hides the chooser and writes the selector", async t => {
  const out = await inTools(
    t,
    `const s = state();
     let pickedApply = null;
     const view = tools.selectorLiveTools({
       ...s.options,
       onPick: apply => { pickedApply = apply; },
     });
     document.body.replaceChildren(view.element);
     document.querySelector(".selector-live-actions button").click();
     pickedApply({ selector: "#one", matches: 1 });
     const strategy = document.querySelector(".selector-live-strategy");
     return { hidden: strategy.hidden, value: s.value.value,
       count: document.querySelector(".selector-live-count").textContent };`,
  );
  assert.equal(out.hidden, true);
  assert.equal(out.value, "#one");
  assert.equal(out.count, "1 match");
});
test("choosing another strategy writes it and reports its matches", async t => {
  const out = await inTools(
    t,
    `const s = state();
     let pickedApply = null;
     const view = tools.selectorLiveTools({
       ...s.options,
       onPick: apply => { pickedApply = apply; },
     });
     document.body.replaceChildren(view.element);
     document.querySelector(".selector-live-actions button").click();
     pickedApply({ selector: "div", matches: 4, alternatives: [
       { strategy: "css", selector: "div", matches: 4 },
       { strategy: "text", selector: "text=Hi", matches: 1 },
     ] });
     const strategy = document.querySelector(".selector-live-strategy");
     strategy.value = "0";
     strategy.dispatchEvent(new Event("change"));
     return { value: s.value.value,
       count: document.querySelector(".selector-live-count").textContent,
       calls: s.calls };`,
  );
  assert.equal(out.value, "div");
  assert.equal(out.count, "4 matches");
  assert.deepEqual(out.calls, [["set", "text=Hi"], ["set", "div"]]);
});
test("highlight reports the count and an empty value clears instead", async t => {
  const out = await inTools(
    t,
    `const s = state();
     const view = tools.selectorLiveTools({
       ...s.options,
       onHighlight: (v, done) => { s.calls.push(["highlight", v]); done({ count: 2 }); },
       onClear: () => s.calls.push(["clear"]),
     });
     document.body.replaceChildren(view.element);
     const highlight = document.querySelectorAll(".selector-live-actions button")[1];
     const count = document.querySelector(".selector-live-count");
     s.value.value = "css:.card";
     highlight.click();
     const checked = count.textContent;
     s.value.value = "   ";
     highlight.click();
     return { checked, cleared: count.textContent,
       empty: count.hasAttribute("data-empty"), calls: s.calls };`,
  );
  assert.equal(out.checked, "2 matches");
  assert.equal(out.cleared, "0 matches");
  assert.equal(out.empty, false);
  assert.deepEqual(out.calls, [["highlight", "css:.card"], ["clear"]]);
});
test("missing handlers leave both buttons disabled", async t => {
  const out = await inTools(
    t,
    `const s = state();
     const view = tools.selectorLiveTools({ ...s.options, matchCount: 5 });
     document.body.replaceChildren(view.element);
     const buttons = [...document.querySelectorAll(".selector-live-actions button")];
     return { disabled: buttons.map(b => b.disabled),
       count: document.querySelector(".selector-live-count").textContent };`,
  );
  assert.deepEqual(out.disabled, [true, true]);
  assert.equal(out.count, "5 matches");
});
test("setCount words counts and empty states", async t => {
  const out = await inTools(
    t,
    `const s = state();
     const view = tools.selectorLiveTools(s.options);
     document.body.replaceChildren(view.element);
     const count = document.querySelector(".selector-live-count");
     const seen = [];
     for (const value of [null, 0, 1, 3]) {
       view.setCount(value);
       seen.push([count.textContent, count.hasAttribute("data-empty")]);
     }
     return seen;`,
  );
  assert.deepEqual(out, [
    ["Not checked", true],
    ["0 matches", false],
    ["1 match", false],
    ["3 matches", false],
  ]);
});
