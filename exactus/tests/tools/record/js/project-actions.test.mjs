/** Project actions and the dialogs they open: save, leave, create, import and the gallery. */
import assert from "node:assert/strict";
import test from "node:test";
import { modulePage, WEB } from "./module-page.mjs";
const HARNESS = "/exactus/tests/tools/record/js/project-harness.js";
test("save reports success and failure in one voice", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectActions } = await import(`${web}/project-actions.js`);
        const { makeHost } = await import(harness);
        const ok = makeHost();
        const actions = new ProjectActions(ok.host);
        await actions.save();
        const bad = makeHost({ failing: ["workspace.save"] });
        await new ProjectActions(bad.host).save();
        return {
          calls: ok.calls.map((/** @type {any[]} */ c) => c[0]),
          said: ok.said,
          failed: bad.said,
          name: actions.name(),
          dirty: actions.dirty(),
        };
      },
      { web: WEB, harness: HARNESS },
    );
    assert.deepEqual(outcome.calls, ["workspace.save"]);
    assert.deepEqual(outcome.said, ["Saved “Alpha”."]);
    assert.deepEqual(outcome.failed, ["workspace.save failed"]);
    assert.equal(outcome.name, "Alpha");
    assert.equal(outcome.dirty, false);
  });
});
test("an empty host shows an untitled project and an empty library", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(
      async (/** @type {{web:string}} */ { web }) => {
        const { ProjectActions } = await import(`${web}/project-actions.js`);
        const actions = new ProjectActions({
          call: async () => null,
          apply: () => undefined,
          say: () => undefined,
          state: () => null,
          showView: () => undefined,
        });
        return {
          name: actions.name(),
          projects: actions.library().projects.length,
          project: actions.project(),
          exportUrl: ProjectActions.exportUrl(),
          exportOne: ProjectActions.exportUrl("a b"),
        };
      },
      { web: WEB },
    );
    assert.equal(outcome.name, "Untitled project");
    assert.equal(outcome.projects, 0);
    assert.equal(outcome.project, null);
    assert.equal(outcome.exportUrl, "/api/export");
    assert.equal(outcome.exportOne, "/api/export?project=a%20b");
  });
});
test("leaving unsaved changes asks to save, discard or cancel", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectActions } = await import(`${web}/project-actions.js`);
        const { makeHost, openDialog, press, settle } = await import(harness);
        /** Run one leave attempt and answer the dialog.
         * @param {string} choice Button label to press.
         * @returns {Promise<object>} The dialog title and what the host saw.
         */
        const attempt = async choice => {
          const env = makeHost();
          env.state.dirty = true;
          const actions = new ProjectActions(env.host);
          const pending = actions.open("beta");
          await settle();
          const title = openDialog()?.querySelector("h2")?.textContent;
          press(openDialog(), choice);
          await pending;
          return { title, calls: env.calls, said: env.said };
        };
        const discard = await attempt("Discard changes");
        const save = await attempt("Save and continue");
        const cancel = await attempt("Cancel");
        const same = makeHost();
        await new ProjectActions(same.host).open("alpha");
        return { discard, save, cancel, same: same.calls };
      },
      { web: WEB, harness: HARNESS },
    );
    assert.match(outcome.discard.title, /Unsaved changes in “Alpha”/);
    assert.deepEqual(outcome.discard.calls, [
      ["project.open", { slug: "beta", replace: true }],
    ]);
    assert.deepEqual(
      outcome.save.calls.map((/** @type {any[]} */ c) => c[0]),
      ["workspace.save", "project.open"],
    );
    assert.deepEqual(outcome.cancel.calls, []);
    assert.deepEqual(outcome.same, []);
  });
});
test("a failed save keeps the person in the open project", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectActions } = await import(`${web}/project-actions.js`);
        const { makeHost, press, openDialog, settle } = await import(harness);
        const env = makeHost({ failing: ["workspace.save"] });
        env.state.dirty = true;
        const actions = new ProjectActions(env.host);
        const pending = actions.openDemo();
        await settle();
        press(openDialog(), "Save and continue");
        await pending;
        return {
          calls: env.calls.map((/** @type {any[]} */ c) => c[0]),
          said: env.said,
        };
      },
      { web: WEB, harness: HARNESS },
    );
    assert.deepEqual(outcome.calls, ["workspace.save"]);
    assert.deepEqual(outcome.said, ["workspace.save failed"]);
  });
});
test("duplicate, delete and demo send their commands and report them", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectActions } = await import(`${web}/project-actions.js`);
        const { makeHost } = await import(harness);
        const env = makeHost();
        const actions = new ProjectActions(env.host);
        await actions.duplicate("beta", "Beta copy");
        await actions.remove("beta");
        await actions.openDemo();
        return {
          calls: env.calls,
          said: env.said,
          applied: env.applied.length,
        };
      },
      { web: WEB, harness: HARNESS },
    );
    assert.deepEqual(outcome.calls, [
      ["project.duplicate", { slug: "beta", name: "Beta copy" }],
      ["project.delete", { slug: "beta" }],
      ["demo.open", { replace: false, project: true }],
    ]);
    assert.deepEqual(outcome.said, [
      "Duplicated as “Beta copy”.",
      "Project deleted.",
      "Demo flow ready. Run it from Play.",
    ]);
    assert.equal(outcome.applied, 3);
  });
});
test("the new project dialog checks the name, creates and reports errors", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectActions } = await import(`${web}/project-actions.js`);
        const { makeHost, openDialog, type, settle } = await import(harness);
        const env = makeHost();
        const actions = new ProjectActions(env.host);
        const pending = actions.create();
        await settle();
        const dialog = openDialog();
        const name = dialog.querySelector('input[name="name"]');
        const submit = dialog.querySelector('button[type="submit"]');
        const initialDisabled = submit.disabled;
        type(name, "alpha");
        const duplicate = dialog.querySelector(".pd-issue").textContent;
        const duplicateDisabled = submit.disabled;
        type(name, "Gamma");
        type(dialog.querySelector('input[name="base_url"]'), " http://x ");
        type(dialog.querySelector('textarea[name="description"]'), " Notes ");
        type(dialog.querySelector('input[name="tags"]'), "web, new");
        type(dialog.querySelector('input[name="author"]'), "Cy");
        type(dialog.querySelector('input[name="version"]'), "0.2.0");
        dialog.querySelector("form").requestSubmit();
        await pending;
        return {
          initialDisabled,
          duplicate,
          duplicateDisabled,
          calls: env.calls,
          views: env.views,
          said: env.said,
          open: openDialog() === null,
        };
      },
      { web: WEB, harness: HARNESS },
    );
    assert.equal(outcome.initialDisabled, true);
    assert.match(outcome.duplicate, /already|use/i);
    assert.equal(outcome.duplicateDisabled, true);
    assert.deepEqual(outcome.calls, [
      [
        "project.create",
        {
          name: "Gamma",
          base_url: "http://x",
          description: "Notes",
          tags: ["web", "new"],
          author: "Cy",
          version: "0.2.0",
          replace: false,
        },
      ],
    ]);
    assert.deepEqual(outcome.views, ["edit"]);
    assert.deepEqual(outcome.said, ["Created “Gamma”."]);
    assert.equal(outcome.open, true);
  });
});
test("the new project dialog shows a failure, stays open and can be cancelled", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectDialogs } = await import(`${web}/project-dialogs.js`);
        const { makeHost, openDialog, press, type, settle } = await import(
          harness
        );
        const env = makeHost();
        const dialogs = new ProjectDialogs({
          library: () => env.state.library,
          project: () => env.state.project,
        });
        let attempts = 0;
        const pending = dialogs.newProject(async () => {
          attempts += 1;
          if (attempts === 1) throw new Error("Disk is full");
          if (attempts === 2) return false;
          return true;
        });
        await settle();
        const dialog = openDialog();
        const name = dialog.querySelector('input[name="name"]');
        const form = dialog.querySelector("form");
        form.requestSubmit();
        const emptyBlocked = attempts === 0;
        type(name, "Delta");
        form.requestSubmit();
        await settle();
        const error = dialog.querySelector(".pd-error").textContent;
        form.requestSubmit();
        await settle();
        const stillOpen = openDialog() !== null;
        press(dialog, "Cancel");
        await pending;
        return {
          emptyBlocked,
          error,
          attempts,
          stillOpen,
          closed: openDialog() === null,
        };
      },
      { web: WEB, harness: HARNESS },
    );
    assert.equal(outcome.emptyBlocked, true);
    assert.equal(outcome.error, "Disk is full");
    assert.equal(outcome.attempts, 2);
    assert.equal(outcome.stillOpen, true);
    assert.equal(outcome.closed, true);
  });
});
test("create stays open when leaving unsaved changes is cancelled", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectActions } = await import(`${web}/project-actions.js`);
        const { makeHost, openDialog, press, type, settle } = await import(
          harness
        );
        const env = makeHost();
        env.state.dirty = true;
        const actions = new ProjectActions(env.host);
        const pending = actions.create();
        await settle();
        const form = openDialog();
        type(form.querySelector('input[name="name"]'), "Echo");
        form.querySelector("form").requestSubmit();
        await settle();
        press(document.querySelector("dialog.unsaved[open]"), "Cancel");
        await settle();
        const stillForm =
          document.querySelector("dialog.new-project[open]") !== null;
        press(document.querySelector("dialog.new-project[open]"), "Cancel");
        await pending;
        return { calls: env.calls, stillForm };
      },
      { web: WEB, harness: HARNESS },
    );
    assert.deepEqual(outcome.calls, []);
    assert.equal(outcome.stillForm, true);
  });
});
test("import reads a project file, rejects other files and ignores a cancelled choice", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectActions } = await import(`${web}/project-actions.js`);
        const { makeHost } = await import(harness);
        const env = makeHost();
        const actions = new ProjectActions(env.host);
        /** @type {File|null} */
        let chosen = new File(['{"flows":[]}'], "mine.json");
        actions.pickFile = async () => chosen;
        await actions.importFile(false);
        chosen = new File(["not json"], "bad.json");
        await actions.importFile(true);
        chosen = null;
        await actions.importFile(true);
        return { calls: env.calls, said: env.said };
      },
      { web: WEB, harness: HARNESS },
    );
    assert.deepEqual(outcome.calls, [
      [
        "project.import",
        { workspace: { flows: [] }, open: false, replace: false },
      ],
    ]);
    assert.deepEqual(outcome.said, [
      "Imported “mine.json”.",
      "That file is not a project export.",
    ]);
  });
});
test("the file picker wires one hidden input and resolves on change or cancel", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectActions } = await import(`${web}/project-actions.js`);
        const { makeHost } = await import(harness);
        const actions = new ProjectActions(makeHost().host);
        /** @type {HTMLInputElement|null} */
        let seen = null;
        const click = HTMLInputElement.prototype.click;
        HTMLInputElement.prototype.click = function () {
          seen = this;
        };
        const first = actions.pickFile();
        const input = /** @type {HTMLInputElement} */ (
          /** @type {unknown} */ (seen)
        );
        input.dispatchEvent(new Event("cancel"));
        const second = actions.pickFile();
        input.dispatchEvent(new Event("change"));
        HTMLInputElement.prototype.click = click;
        return {
          cancelled: await first,
          changed: await second,
          inputs: document.querySelectorAll('input[type="file"]').length,
          hidden: input.hidden,
        };
      },
      { web: WEB, harness: HARNESS },
    );
    assert.equal(outcome.cancelled, null);
    assert.equal(outcome.changed, null);
    assert.equal(outcome.inputs, 1);
    assert.equal(outcome.hidden, true);
  });
});
test("export downloads the open project by its folder name", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(
      async (/** @type {{web:string,harness:string}} */ { web, harness }) => {
        const { ProjectActions } = await import(`${web}/project-actions.js`);
        const { makeHost } = await import(harness);
        const env = makeHost();
        env.state.project.slug = "@legacy";
        const actions = new ProjectActions(env.host);
        /** @type {{href:string,download:string}[]} */
        const clicks = [];
        const click = HTMLAnchorElement.prototype.click;
        HTMLAnchorElement.prototype.click = function () {
          clicks.push({
            href: String(this.getAttribute("href")),
            download: this.download,
          });
        };
        actions.exportOpen();
        env.state.project = null;
        actions.exportOpen();
        HTMLAnchorElement.prototype.click = click;
        return clicks;
      },
      { web: WEB, harness: HARNESS },
    );
    assert.deepEqual(outcome, [
      { href: "/api/export", download: "legacy.pwflow.json" },
      { href: "/api/export", download: "project.pwflow.json" },
    ]);
  });
});
