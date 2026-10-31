/** Verify recorded browser interactions and semantic target metadata. */
import assert from "node:assert/strict";
import test from "node:test";
import { browserTest } from "../../../common/browser.mjs";
test("recorder captures semantic interactions, targets, and unique sequence numbers", async t => {
  await browserTest(t, async (page, url) => {
    /** @type {any[]} */
    const actions = [];
    page.on("console", (/** @type {any} */ message) => {
      if (message.text().startsWith("__EXACTUS_ACTION__"))
        actions.push(
          JSON.parse(message.text().slice("__EXACTUS_ACTION__".length)),
        );
    });
    await page.goto(`${url}/exactus/tools/actions/examples/web/index.html`);
    await page.locator("#save").click();
    assert.equal(await page.locator("#result").innerText(), "Saved");
    await page.evaluate(() => {
      document.body.innerHTML =
        '<label>Name<input id="name" aria-label="Name"></label><button data-testid="save">Save</button><input id="check" type="checkbox"><select id="choice"><option value="a">Alpha</option><option value="b">Beta</option></select><div contenteditable="true" aria-label="Notes"></div><div id="scroll" style="height:50px;overflow:auto"><p style="height:500px">Long text</p></div><div id="drag" draggable="true">Drag</div><div id="drop">Drop</div>';
    });
    await page.addScriptTag({
      url: `${url}/exactus/tools/record/action_recorder.js`,
    });
    await page.addScriptTag({
      url: `${url}/exactus/tools/record/action_recorder.js`,
    });
    await page.locator("#name").fill("Ada");
    await page.locator('[data-testid="save"]').click();
    await page.locator("#name").press("Enter");
    await page.locator("#check").check();
    await page.locator("#check").uncheck();
    await page.locator("#choice").selectOption("b");
    await page.locator('[contenteditable="true"]').fill("Notes here");
    await page.locator('[data-testid="save"]').dblclick();
    await page.evaluate(() => {
      const scroller = /** @type {HTMLElement} */ (
        document.querySelector("#scroll")
      );
      scroller.scrollTop = 100;
      scroller.dispatchEvent(new Event("scroll"));
      const source = /** @type {Element} */ (document.querySelector("#drag"));
      source.dispatchEvent(
        new DragEvent("dragstart", {
          bubbles: true,
        }),
      );
      const drop = /** @type {Element} */ (document.querySelector("#drop"));
      drop.dispatchEvent(
        new DragEvent("drop", {
          bubbles: true,
        }),
      );
    });
    await page.waitForTimeout(400);
    for (const kind of [
      "fill",
      "click",
      "key",
      "check",
      "uncheck",
      "select",
      "contenteditable",
      "drag",
      "scroll",
    ])
      assert.ok(
        actions.some(action => action.type === kind),
        `Missing ${kind}`,
      );
    assert.equal(
      new Set(actions.map(action => action.id)).size,
      actions.length,
    );
    const click = actions.find(action => action.type === "click");
    assert.match(JSON.stringify(click), /save|Save/);
    assert.equal(
      actions.filter(
        action => action.type === "fill" && action.value === "Ada",
      ).length,
      1,
    );
  });
});
