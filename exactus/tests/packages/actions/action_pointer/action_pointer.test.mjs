import assert from "node:assert/strict";
import test from "node:test";
import { browserTest } from "../../../common/browser.mjs";
const PAGE = "/exactus/packages/actions/action_rest/examples/web/index.html";
const DEMO = "/exactus/packages/actions/action_pointer/examples/web/index.html";
test("the runnable example previews values and target interactions", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}${DEMO}`);
		assert.equal(await page.title(), "Pointer Action Frontend");
		await page.locator('[name="pointer_action"]').selectOption("touch_swipe");
		await page.locator('[name="selector"]').fill("#primary-target");
		await page.locator('[name="direction"]').selectOption("left");
		await page.locator("#pointer-demo").evaluate((/** @type {HTMLFormElement} */ form) => form.requestSubmit());
		assert.match(await page.locator("#preview").textContent(), /"pointer_action": "touch_swipe"/);
		await page.locator("#primary-target").click();
		assert.equal(await page.locator("#activity").textContent(), "Clicked primary-target.");
		await page.locator("#reset").click();
		assert.equal(await page.locator('[name="pointer_action"]').inputValue(), "click");
		await page.setViewportSize({ width: 1440, height: 900 });
		assert.ok(await page.locator("#pointer-demo").boundingBox() !== null);
		await page.setViewportSize({ width: 390, height: 900 });
		assert.ok(await page.locator("#pointer-demo").boundingBox() !== null);
	});
});
test("pointer studio exposes every mouse, pointer, and touch action", async t => {
  await browserTest(t, async (page, url) => {
    await page.goto(`${url}${PAGE}`);
    const result = await page.evaluate(async (/** @type {string} */ specifier) => {
      const host = document.createElement("div");
      document.body.replaceChildren(host);
      const module = await import(specifier);
      const studio = module.mountPointerStudio(host, {
        pointer_action: "touch_swipe",
        selector: "#carousel",
        direction: "left",
      });
      const chooser = /** @type {HTMLSelectElement} */ (host.querySelector('select[name="pointer_action"]'));
      const target = /** @type {HTMLInputElement} */ (host.querySelector('[name="selector"]'));
      /** Return every submitted control name.
       * @returns {string[]} Control names.
       */
      const fieldNames = () => Array.from(host.querySelectorAll("[name]"), item => item instanceof HTMLInputElement || item instanceof HTMLSelectElement ? item.name : "");
      const actions = Array.from(chooser.options, item => item.value);
      const initial = { value: studio.value(), selector: target.value, fields: fieldNames() };
      chooser.value = "position_pointer";
      chooser.dispatchEvent(new Event("change"));
      const position = fieldNames();
      chooser.value = "touch_pinch";
      chooser.dispatchEvent(new Event("change"));
      const pinch = fieldNames();
      return { actions, initial, position, pinch, defaultMatches: module.default === module.mountPointerStudio };
    }, "/exactus/packages/actions/action_pointer/index.js");
    assert.deepEqual(result.actions, ["click", "double_click", "right_click", "hover", "drag", "scroll", "position_pointer", "touch_tap", "touch_long_press", "touch_swipe", "touch_pinch"]);
    assert.deepEqual(result.initial, {
      value: "touch_swipe",
      selector: "#carousel",
      fields: ["pointer_action", "selector", "direction", "distance", "duration_ms"],
    });
    assert.deepEqual(result.position, ["pointer_action", "position_action", "x", "y"]);
    assert.deepEqual(result.pinch, ["pointer_action", "selector", "scale", "duration_ms"]);
    assert.equal(result.defaultMatches, true);
  });
});
test("Flow Studio converts the common pointer form into runtime events", async t => {
  await browserTest(t, async (page, url) => {
    await page.goto(`${url}${PAGE}`);
    const result = await page.evaluate(async (/** @type {string} */ specifier) => {
      const module = await import(specifier);
      const form = document.createElement("form");
      const fields = document.createElement("div");
      form.append(fields);
      const definition = module.configureActionForm({ fields, kind: "pointer", snapshot: {}, variables: [] });
      /** Find one named form control.
       * @param {string} name Control name.
       * @returns {HTMLInputElement|HTMLSelectElement} Form control.
       */
      const control = name => /** @type {HTMLInputElement|HTMLSelectElement} */ (form.elements.namedItem(name));
      const chooser = /** @type {HTMLSelectElement} */ (control("pointer_action"));
      chooser.value = "touch_swipe";
      chooser.dispatchEvent(new Event("change"));
      control("selector").value = "#carousel";
      control("direction").value = "left";
      const swipe = module.actionCommand(form, definition);
      chooser.value = "scroll";
      chooser.dispatchEvent(new Event("change"));
      control("selector").value = "html";
      control("scroll_y").value = "720";
      const scroll = module.actionCommand(form, definition);
      return { swipe, scroll };
    }, "/exactus/tools/record/studio/web/action-library.js");
    assert.equal(result.swipe.kind, "gesture");
    assert.equal(result.swipe.selector, "#carousel");
    assert.deepEqual(JSON.parse(result.swipe.payload), {
      gesture: "swipe",
      direction: "left",
      distance: 240,
      duration_ms: 350,
      scale: 0,
    });
    assert.equal(result.scroll.kind, "scroll");
    assert.equal(result.scroll.selector, "html");
    assert.deepEqual(JSON.parse(result.scroll.payload), { x: 0, y: 720 });
  });
});
