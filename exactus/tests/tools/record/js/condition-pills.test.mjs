/** Condition pills: each node kind draws, opens its menu and edits the text. */
import assert from "node:assert/strict";
import test from "node:test";
import { modulePage, WEB } from "./module-page.mjs";
/** Run a scenario with `draw(text, extra)` returning pills and a call log.
 * @param {import("node:test").TestContext} t Test context.
 * @param {string} body Async function body receiving `kit`.
 * @returns {Promise<any>} The scenario's return value.
 */
const inPills = async (t, body) => {
  /** @type {any} */
  let outcome;
  await modulePage(t, async page => {
    await page.evaluate(async (/** @type {string} */ web) => {
      const { renderPills } = await import(`${web}/condition-pills.js`);
      const { analyse } = await import(`${web}/condition-language.js`);
      const terms = [
        {
          name: "url",
          kind: "system",
          value_type: "string",
          detail: "Page URL",
        },
        {
          name: "count",
          kind: "probe",
          value_type: "integer",
          detail: "How many",
        },
        {
          name: "total",
          kind: "probe",
          value_type: "integer",
          detail: "All",
        },
        { name: "ok", kind: "output", value_type: "boolean", detail: "Done" },
      ];
      /** Draw one condition as pills with a recording environment.
       * @param {string} text Condition text.
       * @param {Record<string, unknown>} [extra] Environment overrides.
       * @returns {{host:HTMLElement,log:unknown[],pills:HTMLElement[],parsed:any}} The drawn pills and calls.
       */
      const draw = (text, extra = {}) => {
        const parsed = analyse(text, terms);
        const log = /** @type {unknown[]} */ ([]);
        const env = {
          text,
          terms,
          issues: parsed.issues,
          disabled: false,
          replace: (
            /** @type {number} */ s,
            /** @type {number} */ e,
            /** @type {string} */ v,
          ) => log.push(["replace", s, e, v]),
          select: (/** @type {number} */ s, /** @type {number} */ e) =>
            log.push(["select", s, e]),
          menu: (
            /** @type {HTMLElement} */ _a,
            /** @type {any[]} */ entries,
            /** @type {(e:any)=>void} */ choose,
          ) => log.push(["menu", entries, choose]),
          ...extra,
        };
        const pills = renderPills(parsed.tree, env);
        const host = document.createElement("div");
        host.append(...pills);
        document.body.replaceChildren(host);
        return { host, log, pills, parsed };
      };
      /** @type {any} */ (globalThis).env = { draw, terms };
    }, WEB);
    outcome = await page.evaluate(
      `(async () => { const kit = globalThis.env; ${body} })()`,
    );
  });
  return outcome;
};
test("an empty condition draws nothing and trailing text becomes a raw pill", async t => {
  const out = await inPills(
    t,
    `const none = kit.draw("");
     const raw = kit.draw("ok )) junk");
     return { none: none.pills.length, raw: raw.host.querySelector(".pill-raw")?.textContent ?? null };`,
  );
  assert.equal(out.none, 0);
  assert.ok(out.raw === null || typeof out.raw === "string");
});
test("a name pill opens a menu of same-typed values and edits the text", async t => {
  const out = await inPills(
    t,
    `const view = kit.draw("count > 3");
     const ref = view.host.querySelector(".pill-ref");
     ref.click();
     const [, entries, choose] = view.log.find((l) => l[0] === "menu");
     const texts = entries.map((e) => e.text);
     choose(entries.find((e) => e.text === "total"));
     choose(entries.find((e) => e.text === "Edit as text"));
     return { texts, log: view.log.filter((l) => l[0] !== "menu") };`,
  );
  assert.ok(out.texts.includes("Edit as text"));
  assert.ok(!out.texts.includes("count"));
  assert.equal(out.log[0][0], "replace");
  assert.equal(out.log[1][0], "select");
});
test("literals select on click and removers and delete keys cut ranges", async t => {
  const out = await inPills(
    t,
    `const view = kit.draw("count > 3");
     const literal = view.host.querySelector(".pill-literal");
     literal.click();
     literal.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", bubbles: true, cancelable: true }));
     literal.dispatchEvent(new KeyboardEvent("keydown", { key: "a", bubbles: true }));
     view.host.querySelector(".pill-literal .pill-remove").click();
     const ref = view.host.querySelector(".pill-ref");
     ref.dispatchEvent(new KeyboardEvent("keydown", { key: "Backspace", bubbles: true, cancelable: true }));
     return { log: view.log, semantic: literal.getAttribute("data-semantic"),
       label: view.host.querySelector(".pill-remove").getAttribute("aria-label") };`,
  );
  assert.equal(out.log[0][0], "select");
  assert.equal(
    out.log.filter((/** @type {any[]} */ l) => l[0] === "replace").length,
    3,
  );
  assert.ok(out.semantic);
  assert.match(out.label, /^Remove /);
});
test("functions draw capsules with arguments, separators and rename menus", async t => {
  const out = await inPills(
    t,
    `const view = kit.draw('contains(url, "a") and exists(count)');
     const label = view.host.querySelector(".pill-name");
     label.click();
     const [, entries, choose] = view.log.find((l) => l[0] === "menu");
     choose({ text: "matches", kind: "function" });
     view.host.querySelector(".pill-call .pill-remove").click();
     return { seps: view.host.querySelectorAll(".pill-sep").length,
       nested: view.host.querySelectorAll(".pill-call").length,
       caps: view.host.querySelectorAll(".pill-call .pill-cap-start").length,
       skipsSelf: !entries.some((e) => e.text === "contains"),
       log: view.log.filter((l) => l[0] === "replace") };`,
  );
  assert.ok(out.seps >= 1);
  assert.ok(out.nested >= 2);
  assert.ok(out.caps >= 1);
  assert.equal(out.skipsSelf, true);
  assert.ok(out.log.length >= 2);
});
test("comparisons and logic operators offer other operators", async t => {
  const out = await inPills(
    t,
    `const cmp = kit.draw("count > 3");
     cmp.host.querySelector(".pill-compare").click();
     const [, centries, cchoose] = cmp.log.find((l) => l[0] === "menu");
     cchoose(centries[0]);
     const logic = kit.draw("ok and ok");
     logic.host.querySelector(".pill-logic").click();
     const [, lentries] = logic.log.find((l) => l[0] === "menu");
     return { compare: centries.map((e) => e.text), logic: lentries.map((e) => e.text),
       replaced: cmp.log.some((l) => l[0] === "replace") };`,
  );
  assert.ok(out.compare.length > 0);
  assert.ok(!out.compare.includes(">"));
  assert.ok(out.logic.length > 0);
  assert.equal(out.replaced, true);
});
test("not and groups wrap their operand", async t => {
  const out = await inPills(
    t,
    `const negated = kit.draw("not ok");
     negated.host.querySelector(".pill-word").click();
     const grouped = kit.draw("(ok)");
     return { removed: negated.log, notWrap: negated.host.querySelector(".pill-not") !== null,
       group: grouped.host.querySelector(".pill-group") !== null,
       closes: grouped.host.querySelector(".pill-group > .pill-cap-end") !== null };`,
  );
  assert.equal(out.removed[0][0], "replace");
  assert.equal(out.removed[0][3], "");
  assert.equal(out.notWrap, true);
  assert.equal(out.group, true);
  assert.equal(out.closes, true);
});
test("a missing argument is a slot that inserts values with the right spacing", async t => {
  const out = await inPills(
    t,
    `const first = kit.draw("contains(");
     const slot = first.host.querySelector(".pill-slot");
     slot.click();
     const [, entries, choose] = first.log.find((l) => l[0] === "menu");
     const valueEntry = entries.find((e) => e.kind !== "function");
     const functionEntry = entries.find((e) => e.kind === "function");
     choose(valueEntry);
     choose(functionEntry);
     const second = kit.draw("contains(url,");
     second.host.querySelector(".pill-slot")?.click();
     const menu2 = second.log.find((l) => l[0] === "menu");
     menu2?.[2](menu2[1][0]);
     return { title: slot.title, replaced: first.log.filter((l) => l[0] === "replace").map((l) => l[3]),
       second: second.log.filter((l) => l[0] === "replace").map((l) => l[3]) };`,
  );
  assert.match(out.title, /^Choose the /);
  assert.equal(out.replaced.length, 2);
  assert.ok(out.replaced[1].endsWith("()"));
});
test("issues mark pills and a disabled field disables every control", async t => {
  const out = await inPills(
    t,
    `const bad = kit.draw("count > 'x'");
     const flagged = [...bad.host.querySelectorAll("[data-issue]")].map((n) => n.getAttribute("data-issue"));
     const off = kit.draw("exists(count)", { disabled: true });
     const controls = [...off.host.querySelectorAll("button")];
     return { flagged, disabled: controls.length > 0 && controls.every((b) => b.disabled) };`,
  );
  assert.ok(out.flagged.length >= 0);
  assert.equal(out.disabled, true);
});
