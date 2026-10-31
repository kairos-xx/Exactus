/** Last-run causes: worst status, summaries, fact rows and the rendered list. */
import assert from "node:assert/strict";
import test from "node:test";
import { modulePage, WEB } from "./module-page.mjs";
/** Run a scenario in a blank page with the run-cause module loaded as `cause`.
 * @param {import("node:test").TestContext} t Test context.
 * @param {string} body Async function body receiving `cause`.
 * @returns {Promise<any>} The scenario's return value.
 */
const inCause = async (t, body) => {
  /** @type {any} */
  let outcome;
  await modulePage(t, async page => {
    await page.evaluate(async (/** @type {string} */ web) => {
      const cause = await import(`${web}/run-cause.js`);
      /** @type {any} */ (globalThis).env = { cause };
    }, WEB);
    outcome = await page.evaluate(
      `(async () => { const { cause } = globalThis.env; ${body} })()`,
    );
  });
  return outcome;
};
test("worstStatus ranks failure above everything else", async t => {
  const out = await inCause(
    t,
    `const status = (...statuses) => cause.worstStatus(statuses.map(s => ({ status: s })));
     return {
       mixed: status("succeeded", "warning", "skipped"),
       failed: status("succeeded", "failed", "warning"),
       skipped: status("skipped", "succeeded"),
       ok: status("succeeded"),
       none: cause.worstStatus([]),
     };`,
  );
  assert.equal(out.mixed, "warning");
  assert.equal(out.failed, "failed");
  assert.equal(out.skipped, "skipped");
  assert.equal(out.ok, "succeeded");
  assert.equal(out.none, "");
});
test("causeSummary prefers a phase prefix that the message lacks", async t => {
  const out = await inCause(
    t,
    `return {
       joined: cause.causeSummary({ cause: { phase: "resolve", message: "nothing matched" } }),
       repeats: cause.causeSummary({ cause: { phase: "count", message: "Match count differed" } }),
       message: cause.causeSummary({ error: "boom" }),
       phase: cause.causeSummary({ cause: { phase: "timeout" } }),
       unknown: cause.causeSummary({ cause: { phase: "weird" } }),
       empty: cause.causeSummary({}),
     };`,
  );
  assert.equal(out.joined, "Selector: nothing matched");
  assert.equal(out.repeats, "Match count differed");
  assert.equal(out.message, "boom");
  assert.equal(out.phase, "Timed out");
  assert.equal(out.unknown, "weird");
  assert.equal(out.empty, "");
});
test("causeFacts keeps only the facts a cause carries", async t => {
  const out = await inCause(
    t,
    `const facts = cause.causeFacts({
       phase: "count",
       expression: "css:.card",
       expected_count: null,
       found_count: 0,
       resolved_css: ".card",
       target_index: 2,
       timeout_ms: 1500,
       failed: [{ index: 1, checks: ["[a]", "[b]"] }],
       changes: [{ field: "text", baseline: "a", current: "b" }],
       playwright_error: "locator strictness",
     });
     const sparse = cause.causeFacts({});
     return { facts, sparse };`,
  );
  assert.deepEqual(out.facts, [
    ["Phase", "Match count"],
    ["Expression", "css:.card"],
    ["Expected and found", "one or more expected, 0 found"],
    ["Resolved to", ".card"],
    ["Match number", "3"],
    ["Waited", "1500 ms"],
    ["Match 2 failed", "[a], [b]"],
    ["text changed", '"a" to "b"'],
    ["Browser said", "locator strictness"],
  ]);
  assert.deepEqual(out.sparse, []);
});
test("renderLastRun hides an empty target and renders records", async t => {
  const out = await inCause(
    t,
    `const target = document.createElement("section");
     cause.renderLastRun(target, []);
     const empty = target.hidden;
     cause.renderLastRun(target, [
       { status: "failed",
         unit: { index: 0, count: 2 },
         cause: { phase: "check", message: "check failed", expected_count: 1, found_count: 2 },
         streams: [
           { source: "snippet", level: "error", message: "kept line" },
           { source: "stdout", level: "info", message: "dropped" },
         ] },
       { status: "succeeded" },
     ]);
     const items = [...target.querySelectorAll(".last-run-item")];
     return {
       empty,
       shown: !target.hidden,
       states: items.map(item => item.getAttribute("data-state")),
       head: items[0].querySelector("small")?.textContent ?? "",
       summary: items[0].querySelector(".last-run-summary")?.textContent ?? "",
       facts: [...items[0].querySelectorAll("dt")].map(dt => dt.textContent),
       lines: [...items[0].querySelectorAll(".last-run-line")].map(
         line => [line.className, line.textContent]),
       second: items[1].querySelectorAll(".last-run-facts, .last-run-line").length,
     };`,
  );
  assert.equal(out.empty, true);
  assert.equal(out.shown, true);
  assert.deepEqual(out.states, ["failed", "succeeded"]);
  assert.equal(out.head, "match 1 of 2");
  assert.equal(out.summary, "Check: check failed");
  assert.deepEqual(out.facts, [
    "Phase",
    "Expected and found",
  ]);
  assert.deepEqual(out.lines, [
    ["last-run-line error", "kept line"],
  ]);
  assert.equal(out.second, 0);
});
