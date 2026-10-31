/** The project gallery: search, advanced filters, selection, details and deletion. */
import assert from "node:assert/strict";
import test from "node:test";
import { modulePage, WEB } from "./module-page.mjs";
const HARNESS = "/exactus/tests/tools/record/js/project-harness.js";
/** Open the gallery over a fake library and run a scenario against it.
 * @param {import("node:test").TestContext} t Test context.
 * @param {string} body Async function body receiving `env`.
 * @returns {Promise<any>} The scenario's return value.
 */
const inGallery = async (t, body) => {
  /** @type {any} */
  let outcome;
  await modulePage(t, async page => {
    await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectDialogs } = await import(`${web}/project-dialogs.js`);
        const { summary, settle, press, type } = await import(harness);
        const library = {
          projects: [
            summary({}),
            summary({
              slug: "beta",
              name: "Beta",
              tags: ["admin"],
              author: "Bo",
              last_run_at: "",
              runs: 0,
              flows: 1,
              description: "",
              base_url: "",
            }),
            summary({
              slug: "@legacy",
              name: "Legacy",
              legacy: true,
              tags: [],
              author: "",
              version: "",
            }),
          ],
          recents: [],
          tags: ["web", "smoke", "admin"],
        };
        const state = { project: { slug: "alpha" } };
        const log = /** @type {unknown[]} */ ([]);
        const actions = {
          open: async (/** @type {string} */ slug) => log.push(["open", slug]),
          create: () => log.push("create"),
          importFile: () => log.push("import"),
          duplicate: async (/** @type {string} */ s, /** @type {string} */ n) =>
            log.push(["duplicate", s, n]),
          remove: async (/** @type {string} */ s) => {
            log.push(["remove", s]);
            library.projects = library.projects.filter(p => p.slug !== s);
            state.project = { slug: "alpha" };
          },
          exportUrl: (/** @type {string} */ slug) =>
            `/api/export?project=${slug}`,
        };
        const dialogs = new ProjectDialogs({
          library: () => library,
          project: () => state.project,
        });
        const closed = dialogs.gallery(actions);
        await settle();
        /** @type {any} */ (globalThis).env = {
          dialogs,
          library,
          state,
          log,
          actions,
          settle,
          press,
          type,
          closed,
          dialog: () => document.querySelector("dialog.project-gallery[open]"),
          names: () =>
            [...document.querySelectorAll(".pd-item strong")].map(
              n => n.textContent,
            ),
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
test("the gallery lists projects, shows details and counts them", async t => {
  const out = await inGallery(
    t,
    `const d = env.dialog();
     const result = { names: env.names(), count: d.querySelector(".pd-count").textContent,
       selected: d.querySelector('[aria-selected="true"]').dataset.slug,
       badge: d.querySelector(".pd-badge").textContent,
       heading: d.querySelector(".pd-details h3").textContent,
       openDisabled: [...d.querySelectorAll(".pd-detail-actions button")][0].disabled,
       deleteTitle: [...d.querySelectorAll(".pd-detail-actions button")].at(-1).title,
       facts: d.querySelectorAll(".pd-facts dt").length,
       link: d.querySelector(".pd-detail-actions a").getAttribute("href"),
       download: d.querySelector(".pd-detail-actions a").download };
     d.querySelector(".pd-icon-only").click();
     await env.closed;
     return result;`,
  );
  assert.deepEqual(out.names, ["Alpha", "Beta", "Legacy"]);
  assert.equal(out.count, "3 of 3 projects");
  assert.equal(out.selected, "alpha");
  assert.equal(out.badge, "Open now");
  assert.equal(out.heading, "Alpha");
  assert.equal(out.openDisabled, true);
  assert.match(out.deleteTitle, /Open another project/);
  assert.equal(out.facts, 10);
  assert.equal(out.link, "/api/export?project=alpha");
  assert.equal(out.download, "alpha.pwflow.json");
});
test("search, tag chips and advanced filters narrow the list and clear resets", async t => {
  const out = await inGallery(
    t,
    `const d = env.dialog();
     const seen = {};
     env.type(d.querySelector('input[type="search"]'), "beta");
     seen.search = env.names();
     d.querySelector(".pd-link").click();
     seen.cleared = env.names().length;
     d.querySelector(".pd-toggle").click();
     seen.panelOpen = !d.querySelector(".pd-advanced").hidden;
     [...d.querySelectorAll(".pd-chip")].find((c) => c.textContent.includes("admin")).click();
     seen.tag = env.names();
     [...d.querySelectorAll(".pd-chip")].find((c) => c.textContent.includes("admin")).click();
     const selects = d.querySelectorAll(".pd-advanced select");
     selects[0].value = "any"; selects[0].dispatchEvent(new Event("change"));
     env.type(d.querySelector(".pd-advanced input"), "Bo");
     seen.author = env.names();
     d.querySelector(".pd-link").click();
     selects[1].value = "7"; selects[1].dispatchEvent(new Event("change"));
     selects[2].value = "no"; selects[2].dispatchEvent(new Event("change"));
     seen.never = env.names();
     selects[2].value = "yes"; selects[2].dispatchEvent(new Event("change"));
     selects[3].value = "name"; selects[3].dispatchEvent(new Event("change"));
     seen.sorted = env.names();
     env.type(d.querySelector('input[type="search"]'), "zzz");
     seen.empty = d.querySelector(".pd-empty").textContent;
     d.querySelector(".pd-link").click();
     return seen;`,
  );
  assert.deepEqual(out.search, ["Beta"]);
  assert.equal(out.cleared, 3);
  assert.equal(out.panelOpen, true);
  assert.deepEqual(out.tag, ["Beta"]);
  assert.deepEqual(out.author, ["Beta"]);
  assert.ok(Array.isArray(out.never));
  assert.ok(Array.isArray(out.sorted));
  assert.match(out.empty, /No project matches these filters/);
});
test("selecting, keyboard moves, enter and double click open projects", async t => {
  const out = await inGallery(
    t,
    `const d = env.dialog();
     const list = d.querySelector(".pd-list");
     const key = (k) => list.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true }));
     d.querySelector('[data-slug="beta"]').click();
     const afterClick = d.querySelector('[aria-selected="true"]').dataset.slug;
     key("ArrowDown");
     const down = d.querySelector('[aria-selected="true"]').dataset.slug;
     key("ArrowDown");
     const clamp = d.querySelector('[aria-selected="true"]').dataset.slug;
     key("ArrowUp"); key("ArrowUp"); key("ArrowUp");
     const up = d.querySelector('[aria-selected="true"]').dataset.slug;
     key("x");
     d.querySelector('[data-slug="beta"]').click();
     key("Enter");
     await env.closed;
     return { afterClick, down, clamp, up, log: env.log };`,
  );
  assert.deepEqual(
    [out.afterClick, out.down, out.clamp, out.up],
    ["beta", "@legacy", "@legacy", "alpha"],
  );
  assert.deepEqual(out.log, [["open", "beta"]]);
});
test("double click opens, and open, new and import call the actions", async t => {
  const out = await inGallery(
    t,
    `const d = env.dialog();
     d.querySelector('[data-slug="beta"]').click();
     d.querySelector('[data-slug="beta"]').dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
     await env.closed;
     return env.log;`,
  );
  assert.deepEqual(out, [["open", "beta"]]);
  const more = await inGallery(
    t,
    `const d = env.dialog();
     env.press(d, "Import");
     d.querySelector('[data-slug="beta"]').click();
     const open = [...d.querySelectorAll(".pd-detail-actions button")][0];
     open.click();
     await env.closed;
     return env.log;`,
  );
  assert.deepEqual(more, ["import", ["open", "beta"]]);
  const created = await inGallery(
    t,
    `const d = env.dialog();
     env.press(d, "New project");
     await env.closed;
     return env.log;`,
  );
  assert.deepEqual(created, ["create"]);
});
test("duplicate asks for a name and sends it; legacy cannot be deleted", async t => {
  const out = await inGallery(
    t,
    `const d = env.dialog();
     d.querySelector('[data-slug="beta"]').click();
     env.press(d.querySelector(".pd-details"), "Duplicate");
     await env.settle();
     const ask = document.querySelector("dialog.ask-name[open]");
     const initial = ask.querySelector("input").value;
     env.type(ask.querySelector("input"), "alpha");
     const issue = ask.querySelector(".pd-issue").textContent;
     env.type(ask.querySelector("input"), "Beta two");
     ask.querySelector("form").requestSubmit();
     for (let tick = 0; tick < 200 && !env.log.length; tick += 1) await env.settle();
     d.querySelector('[data-slug="@legacy"]').click();
     const legacyBlocked = [...d.querySelectorAll(".pd-detail-actions button")].at(-1);
     const folder = d.querySelector(".pd-facts").textContent.includes("The Studio folder itself");
     return { initial, issue, log: env.log, legacy: [legacyBlocked.disabled, legacyBlocked.title], folder };`,
  );
  assert.equal(out.initial, "Beta copy");
  assert.notEqual(out.issue, "");
  assert.deepEqual(out.log, [["duplicate", "beta", "Beta two"]]);
  assert.deepEqual(out.legacy, [true, "This is the Studio folder itself."]);
  assert.equal(out.folder, true);
});
test("deleting needs the typed name, can be kept, and refreshes the list", async t => {
  const out = await inGallery(
    t,
    `const d = env.dialog();
     d.querySelector('[data-slug="beta"]').click();
     const askDelete = () => [...d.querySelectorAll(".pd-detail-actions button")].at(-1).click();
     askDelete();
     const input = d.querySelector("[data-confirm-input]");
     const confirm = [...d.querySelectorAll(".pd-confirm button")].at(-1);
     const before = confirm.disabled;
     env.type(input, "Be");
     const partial = confirm.disabled;
     env.press(d.querySelector(".pd-confirm"), "Keep project");
     const backToActions = d.querySelector(".pd-confirm") === null;
     askDelete();
     const again = d.querySelector("[data-confirm-input]");
     env.type(again, "Beta");
     const ready = [...d.querySelectorAll(".pd-confirm button")].at(-1);
     const enabled = !ready.disabled;
     ready.click();
     await env.settle();
     d.querySelector('[data-slug="beta"]') ?? null;
     return { before, partial, backToActions, enabled, log: env.log, names: env.names() };`,
  );
  assert.equal(out.before, true);
  assert.equal(out.partial, true);
  assert.equal(out.backToActions, true);
  assert.equal(out.enabled, true);
  assert.deepEqual(out.log, [["remove", "beta"]]);
  assert.deepEqual(out.names, ["Alpha", "Legacy"]);
});
test("an empty library says so and the gallery can refresh when it changes", async t => {
  const out = await inGallery(
    t,
    `env.library.projects = [];
     env.library.tags = [];
     env.dialogs.refreshGallery();
     const d = env.dialog();
     const seen = { empty: d.querySelector(".pd-empty").textContent,
       count: d.querySelector(".pd-count").textContent,
       tags: d.querySelector(".pd-tags").textContent };
     d.querySelector(".pd-icon-only").click();
     await env.closed;
     seen.refresh = env.dialogs.refreshGallery;
     seen.recents = env.dialogs.recents().length;
     return seen;`,
  );
  assert.match(out.empty, /There are no projects yet/);
  assert.equal(out.count, "");
  assert.match(out.tags, /No project has tags yet/);
  assert.equal(out.refresh, null);
  assert.equal(out.recents, 0);
});
