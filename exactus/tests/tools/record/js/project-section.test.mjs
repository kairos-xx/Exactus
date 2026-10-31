/** The Project section of Settings: draft, validation, apply, revert and gallery. */
import assert from "node:assert/strict";
import test from "node:test";
import { modulePage, WEB } from "./module-page.mjs";
const HARNESS = "/exactus/tests/tools/record/js/project-harness.js";
/** Run a scenario against a ProjectSection built over a fake action set.
 * @param {import("node:test").TestContext} t Test context.
 * @param {string} body Async function body receiving `env`.
 * @returns {Promise<any>} The scenario's return value.
 * @throws {Error} From the fake `send` when the scenario asks it to fail.
 */
const inSection = async (t, body) => {
  /** @type {any} */
  let outcome;
  await modulePage(t, async page => {
    await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectSection } = await import(`${web}/project-section.js`);
        const { summary, type, settle } = await import(harness);
        const log = /** @type {unknown[]} */ ([]);
        const state = {
          fail: false,
          project: /** @type {any} */ ({
            slug: "alpha",
            name: "Alpha",
            description: "First",
            tags: ["web"],
            author: "Ana",
            version: "1.0",
            created_at: "2026-10-01T00:00:00",
            saved: true,
          }),
        };
        const actions = {
          project: () => state.project,
          library: () => ({
            projects: [summary({}), summary({ slug: "beta", name: "Beta" })],
            recents: [],
            tags: [],
          }),
          gallery: () => log.push("gallery"),
          send: async (
            /** @type {string} */ name,
            /** @type {unknown} */ payload,
          ) => {
            if (state.fail) throw new Error("rejected");
            log.push([name, payload]);
          },
          host: { say: (/** @type {string} */ text) => log.push(text) },
        };
        const section = new ProjectSection(actions);
        /** Redraw the section into the page.
         * @returns {HTMLElement} The new section.
         */
        const draw = () => {
          const node = section.section();
          document.body.replaceChildren(node);
          return node;
        };
        /** @type {any} */ (globalThis).env = {
          section,
          draw,
          state,
          log,
          type,
          settle,
        };
      },
      { web: WEB, harness: HARNESS },
    );
    outcome = await page.evaluate(
      `(async () => { const env = globalThis.env; ${body} })()`,
    );
  });
  return outcome;
};
test("without a project the section only says so", async t => {
  const out = await inSection(
    t,
    `env.state.project = null; return env.draw().textContent;`,
  );
  assert.equal(out, "No project is open.");
});
test("the form starts clean and the gallery button opens the gallery", async t => {
  const out = await inSection(
    t,
    `const node = env.draw();
     const apply = node.querySelector('button[type="submit"]');
     const revert = node.querySelectorAll("form button")[1];
     [...node.querySelectorAll("button")].find((b) => b.textContent.includes("gallery")).click();
     return { apply: apply.disabled, revert: revert.disabled, log: env.log,
       intro: node.querySelector(".settings-intro").textContent,
       tags: node.querySelector('[name="tags"]').value };`,
  );
  assert.equal(out.apply, true);
  assert.equal(out.revert, true);
  assert.deepEqual(out.log, ["gallery"]);
  assert.match(out.intro, /^Created .*The base address is the target below\.$/);
  assert.equal(out.tags, "web");
});
test("an unsaved project says so", async t => {
  const out = await inSection(
    t,
    `env.state.project.saved = false; return env.draw().querySelector(".settings-intro").textContent;`,
  );
  assert.match(out, /Not saved yet\./);
});
test("typing keeps a draft across redraws and flags a taken name", async t => {
  const out = await inSection(
    t,
    `let node = env.draw();
     env.type(node.querySelector('[name="name"]'), "Beta");
     const issue = node.querySelector('[role="status"]').textContent;
     const invalid = node.querySelector('[name="name"]').hasAttribute("aria-invalid");
     const blocked = node.querySelector('button[type="submit"]').disabled;
     node = env.draw();
     const kept = node.querySelector('[name="name"]').value;
     env.state.project = { ...env.state.project, slug: "other", name: "Other" };
     node = env.draw();
     return { issue, invalid, blocked, kept, reset: node.querySelector('[name="name"]').value };`,
  );
  assert.notEqual(out.issue, "");
  assert.equal(out.invalid, true);
  assert.equal(out.blocked, true);
  assert.equal(out.kept, "Beta");
  assert.equal(out.reset, "Other");
});
test("apply sends normalized details, and failure shows an error", async t => {
  const out = await inSection(
    t,
    `let node = env.draw();
     env.type(node.querySelector('[name="name"]'), " Gamma ");
     env.type(node.querySelector('[name="tags"]'), "web, new ,");
     env.type(node.querySelector('[name="description"]'), " Notes ");
     node.querySelector("form").requestSubmit();
     await env.settle();
     const sent = env.log.slice();
     node = env.draw();
     env.state.fail = true;
     env.type(node.querySelector('[name="author"]'), "Zed");
     node.querySelector("form").requestSubmit();
     await env.settle();
     return { sent, error: node.querySelector('[role="alert"]').textContent,
       cleanSubmit: (() => { node.querySelector("form"); return true; })() };`,
  );
  assert.deepEqual(out.sent, [
    [
      "project.update",
      {
        name: "Gamma",
        description: "Notes",
        tags: ["web", "new"],
        author: "Ana",
        version: "1.0",
      },
    ],
    "Project details applied. Save the project to keep them.",
  ]);
  assert.equal(out.error, "rejected");
});
test("submitting an unchanged form sends nothing and revert restores values", async t => {
  const out = await inSection(
    t,
    `const node = env.draw();
     node.querySelector("form").requestSubmit();
     await env.settle();
     env.type(node.querySelector('[name="version"]'), "2.0");
     const dirty = node.querySelectorAll("form button")[1].disabled;
     node.querySelectorAll("form button")[1].click();
     return { log: env.log, dirty, version: node.querySelector('[name="version"]').value,
       applyDisabled: node.querySelector('button[type="submit"]').disabled };`,
  );
  assert.deepEqual(out.log, []);
  assert.equal(out.dirty, false);
  assert.equal(out.version, "1.0");
  assert.equal(out.applyDisabled, true);
});
