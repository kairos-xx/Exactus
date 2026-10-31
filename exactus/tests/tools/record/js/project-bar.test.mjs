/** The top bar: control routing, menus, keyboard, fit tiers and the saved pill. */
import assert from "node:assert/strict";
import test from "node:test";
import { modulePage, WEB } from "./module-page.mjs";
const HARNESS = "/exactus/tests/tools/record/js/project-harness.js";
/** Build a bar over a fake action set inside the page and run a scenario.
 * @param {import("node:test").TestContext} t Test context.
 * @param {string} scenario Body of an async function receiving (env).
 * @returns {Promise<any>} Whatever the scenario returned.
 */
const inBar = async (t, scenario) => {
  /** @type {any} */
  let outcome;
  await modulePage(t, async page => {
    await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectBar } = await import(`${web}/project-bar.js`);
        const { summary, settle } = await import(harness);
        const root = document.createElement("header");
        root.innerHTML = `<div class="brand" style="width:100px">B</div>
          <span id="project-name"></span>
          <span id="project-save-state"><span class="save-text"></span></span>
          <div class="bar-actions">
            ${[
              "new",
              "save",
              "open",
              "open-menu",
              "export",
              "commands",
              "overflow",
              "project",
              "nothing",
            ]
              .map((name) => `<button data-bar="${name}">${name}</button>`)
              .join("")}
          </div>`;
        document.body.append(root);
        const log = /** @type {string[]} */ ([]);
        const state = {
          dirty: false,
          name: "Alpha",
          slug: "alpha",
          projects: [summary({}), summary({ slug: "beta", name: "Beta" })],
          recents: ["alpha", "beta"],
        };
        const actions = {
          create: () => log.push("create"),
          save: () => log.push("save"),
          gallery: () => log.push("gallery"),
          exportOpen: () => log.push("export"),
          importFile: (/** @type {boolean} */ open) =>
            log.push(`import:${open}`),
          openDemo: () => log.push("demo"),
          open: (/** @type {string} */ slug) => log.push(`open:${slug}`),
          dirty: () => state.dirty,
          name: () => state.name,
          project: () => ({ slug: state.slug }),
          library: () => ({
            projects: state.projects,
            recents: state.recents,
            tags: [],
          }),
        };
        const host = {
          commands: () => log.push("commands"),
          projectView: () => log.push("projectView"),
        };
        const bar = new ProjectBar(root, actions, host);
        /** @type {any} */ (globalThis).env = {
          root,
          bar,
          log,
          state,
          actions,
          settle,
        };
      },
      { web: WEB, harness: HARNESS },
    );
    outcome = await page.evaluate(
      `(async () => { const env = globalThis.env; ${scenario} })()`,
    );
  });
  return outcome;
};
test("each control reaches its action and unknown names do nothing", async t => {
  const log = await inBar(
    t,
    `for (const n of ["new","save","open","export","commands","project","nothing"])
       env.root.querySelector('[data-bar="'+n+'"]').click();
     env.root.click();
     return env.log;`,
  );
  assert.deepEqual(log, [
    "create",
    "save",
    "gallery",
    "export",
    "commands",
    "projectView",
  ]);
});
test("the open arrow lists recents with the open one disabled and runs a choice", async t => {
  const out = await inBar(
    t,
    `env.root.querySelector('[data-bar="open-menu"]').click();
     const menu = document.querySelector(".bar-menu");
     const lines = [...menu.querySelectorAll("button")].map((b) => [b.textContent.trim(), b.disabled]);
     const expanded = env.root.querySelector('[data-bar="open-menu"]').getAttribute("aria-expanded");
     [...menu.querySelectorAll("button")].find((b) => b.textContent.includes("Beta")).click();
     return { lines, expanded, gone: document.querySelector(".bar-menu") === null, log: env.log };`,
  );
  assert.equal(out.expanded, "true");
  assert.deepEqual(out.log, ["open:beta"]);
  assert.equal(out.gone, true);
  assert.ok(
    out.lines.some((/** @type {any[]} */ l) => l[0].includes("Alpha") && l[1]),
  );
  assert.ok(
    out.lines.some((/** @type {any[]} */ l) =>
      l[0].includes("Open project gallery"),
    ),
  );
});
test("every menu item runs its action", async t => {
  const log = await inBar(
    t,
    `const names = ["Open project gallery", "Import from file", "Open demo flow"];
     for (const n of names) {
       env.root.querySelector('[data-bar="open-menu"]').click();
       [...document.querySelectorAll(".bar-menu button")].find((b) => b.textContent.includes(n)).click();
     }
     const all = ["New project","Save project","Open project gallery","Import from file","Open demo flow","Export project","Commands"];
     for (const n of all) {
       env.root.querySelector('[data-bar="overflow"]').click();
       [...document.querySelectorAll(".bar-menu button")].find((b) => b.textContent.includes(n)).click();
     }
     return env.log;`,
  );
  assert.deepEqual(log, [
    "gallery",
    "import:true",
    "demo",
    "create",
    "save",
    "gallery",
    "import:true",
    "demo",
    "export",
    "commands",
  ]);
});
test("no recent projects shows one disabled line", async t => {
  const out = await inBar(
    t,
    `env.state.recents = [];
     env.state.projects = [];
     env.root.querySelector('[data-bar="open-menu"]').click();
     return [...document.querySelectorAll(".bar-menu button")].map((b) => [b.textContent.trim(), b.disabled]);`,
  );
  assert.ok(
    out.some((/** @type {any[]} */ l) => l[0] === "No recent projects" && l[1]),
  );
});
test("the menu toggles, closes outside, on resize and with the keyboard", async t => {
  const out = await inBar(
    t,
    `const trigger = env.root.querySelector('[data-bar="overflow"]');
     const open = () => document.querySelector(".bar-menu") !== null;
     const seen = [];
     trigger.click(); seen.push(open());
     trigger.click(); seen.push(open());
     trigger.click();
     const menu = document.querySelector(".bar-menu");
     menu.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
     seen.push(open());
     document.body.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
     seen.push(open());
     trigger.click();
     trigger.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
     seen.push(open());
     window.dispatchEvent(new Event("resize"));
     seen.push(open());
     trigger.click();
     const key = (k) => document.querySelector(".bar-menu").dispatchEvent(
       new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true }));
     const focused = () => document.activeElement.textContent.trim();
     const order = [focused()];
     key("ArrowDown"); order.push(focused());
     key("ArrowUp"); order.push(focused());
     key("End"); order.push(focused());
     key("Home"); order.push(focused());
     key("x");
     key("Tab"); seen.push(open());
     trigger.click();
     key("Escape"); seen.push(open());
     return { seen, order, refocused: document.activeElement === trigger };`,
  );
  assert.deepEqual(out.seen, [
    true,
    false,
    true,
    false,
    true,
    false,
    false,
    false,
  ]);
  assert.equal(out.order[0], out.order[2]);
  assert.notEqual(out.order[0], out.order[1]);
  assert.equal(out.order[0], out.order[4]);
  assert.equal(out.refocused, true);
});
test("render shows the name and saved state and updates the title", async t => {
  const out = await inBar(
    t,
    `env.bar.render();
     const saved = [document.title, env.root.querySelector("#project-name").textContent,
       env.root.querySelector("#project-save-state").dataset.state,
       env.root.querySelector(".save-text").textContent];
     env.state.dirty = true;
     env.bar.render();
     return { saved, dirty: [document.title, env.root.querySelector("#project-save-state").dataset.state,
       env.root.querySelector("#project-save-state").title,
       env.root.querySelector(".save-text").textContent] };`,
  );
  assert.deepEqual(out.saved, [
    "Alpha · Flow Studio",
    "Alpha",
    "saved",
    "Saved",
  ]);
  assert.deepEqual(out.dirty, [
    "● Alpha · Flow Studio",
    "dirty",
    "There are changes that are not saved",
    "Unsaved changes",
  ]);
});
test("fit chooses full, icons or menu by the room available", async t => {
  const out = await inBar(
    t,
    `const tiers = [];
     for (const width of [1600, 520, 160]) {
       env.root.style.display = "block";
       env.root.style.width = width + "px";
       env.bar.fit();
       tiers.push(env.root.getAttribute("data-tier"));
     }
     const empty = document.createElement("header");
     document.body.append(empty);
     const { ProjectBar } = await import("${WEB}/project-bar.js");
     new ProjectBar(empty, env.actions, { commands() {}, projectView() {} });
     return { tiers, bare: empty.getAttribute("data-tier") };`,
  );
  assert.equal(out.tiers[0], "full");
  assert.equal(out.tiers[2], "menu");
  assert.ok(["full", "icons", "menu"].includes(out.tiers[1]));
  assert.equal(out.bare, null);
});
