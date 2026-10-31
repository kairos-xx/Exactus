/** The first-run screen: when it covers the editor and what its buttons do. */
import assert from "node:assert/strict";
import test from "node:test";
import { modulePage, WEB } from "./module-page.mjs";
import {
  shouldWelcome,
  DISMISSED_KEY,
} from "../../../../tools/record/studio/web/welcome.js";
/** A snapshot that qualifies for the welcome screen, with overrides.
 * @param {Record<string, unknown>} [extra] Fields to replace.
 * @returns {any}
 */
const fresh = (extra = {}) => ({
  library: {
    projects: [],
    recents: [],
    tags: [],
  },
  project: {
    saved: false,
  },
  workspace: {
    flows: [
      {
        events: [],
      },
    ],
  },
  ...extra,
});
test("the welcome screen shows only for an empty, unsaved, untouched editor", () => {
  assert.equal(shouldWelcome(fresh(), "edit", false), true);
  assert.equal(shouldWelcome(fresh(), "edit", true), false);
  assert.equal(shouldWelcome(fresh(), "play", false), false);
  assert.equal(shouldWelcome(null, "edit", false), false);
  assert.equal(
    shouldWelcome(
      {
        library: fresh().library,
      },
      "edit",
      false,
    ),
    false,
  );
  assert.equal(
    shouldWelcome(
      fresh({
        library: {
          projects: [
            {
              slug: "a",
            },
          ],
          recents: [],
          tags: [],
        },
      }),
      "edit",
      false,
    ),
    false,
  );
  assert.equal(
    shouldWelcome(
      fresh({
        project: {
          saved: true,
        },
      }),
      "edit",
      false,
    ),
    false,
  );
  assert.equal(
    shouldWelcome(
      fresh({
        workspace: {
          flows: [
            {
              events: [
                {
                  id: "x",
                },
              ],
            },
          ],
        },
      }),
      "edit",
      false,
    ),
    false,
  );
  assert.equal(
    shouldWelcome(
      fresh({
        workspace: undefined,
      }),
      "edit",
      false,
    ),
    true,
  );
  assert.equal(DISMISSED_KEY, "studio.welcome.dismissed");
});
test("the welcome screen offers three ways to begin and a way to skip", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(async (/** @type {string} */ web) => {
      const { renderWelcome } = await import(`${web}/welcome.js`);
      const root = document.createElement("section");
      document.body.append(root);
      /** @type {string[]} */
      const calls = [];
      const actions = {
        create: () => calls.push("create"),
        openDemo: () => calls.push("demo"),
        importFile: () => calls.push("import"),
        dismiss: () => calls.push("dismiss"),
      };
      renderWelcome(root, actions);
      const first = root.innerHTML;
      renderWelcome(root, actions);
      const stable = root.innerHTML === first;
      for (const button of root.querySelectorAll("button")) button.click();
      return {
        calls,
        stable,
        title: root.querySelector("h2")?.textContent,
        clips: root.querySelectorAll(".welcome-clip").length,
        ticks: root.querySelectorAll(".welcome-tick").length,
        hidden: root
          .querySelector(".welcome-timeline")
          ?.getAttribute("aria-hidden"),
      };
    }, WEB);
    assert.deepEqual(outcome.calls, ["create", "demo", "import", "dismiss"]);
    assert.equal(outcome.stable, true);
    assert.match(outcome.title, /Record a flow once/);
    assert.equal(outcome.clips, 3);
    assert.equal(outcome.ticks, 5);
    assert.equal(outcome.hidden, "true");
  });
});
