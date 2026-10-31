/** Exercise Flow Studio editing, recording, Actions recipes and keyboard dialogs. */
import { Buffer } from "node:buffer";
import { readFile, writeFile } from "node:fs/promises";
import assert from "node:assert/strict";
import process from "node:process";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";
/** Shared panel identifiers used to access the dynamic dock model. */
const panelKeys = Object.freeze({
  workspace: "workspace",
  actions: "actions",
  steps: "steps",
  target: "target",
  properties: "properties",
  timeline: "timeline",
  runs: "runs",
});
/** Require geometry to exist before using it in an assertion.
 * @template T
 * @param {T|null|undefined} value Measured geometry or selected model.
 * @returns {T} Present value.
 */
const requiredValue = value => {
  assert.ok(value !== undefined && value !== null);
  return value;
};
import { browserTest } from "../../../common/browser.mjs";
/** @typedef {{request:()=>{postDataJSON:()=>{id:string}},fulfill:(options:{contentType:string,body:string})=>Promise<void>}} RejectedCommandRoute */
/** @typedef {Window & {studioEvents?:{onmessage:(message:{data:string})=>void}}} StudioTestWindow */
import { actionHandlers, flow, studio } from "./studio-mock.mjs";
export { studio };
/** Resolve once a host-side condition holds, or after two seconds.
 * @param {() => boolean} check
 * @param {number} [deadline] Absolute time in milliseconds to give up.
 * @returns {Promise<void>}
 */
const until = async (check, deadline = Date.now() + 2000) => {
  if (check() || Date.now() > deadline) return;
  await delay(10);
  await until(check, deadline);
};
test("An added action is selected and configured in its row or Properties, never in the library", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url, actionHandlers);
    // An action that expands is configured in its own flow row; a single-line
    // action keeps its target tools in Properties.
    const inRow = ".edit-step-detail-form";
    const properties = '[data-panel-id="properties"]';
    /** Let the settings move focus to their first control, as a person's typing would wait for.
     * @returns {Promise<void>}
     */
    const settle = () =>
      page.evaluate(
        () =>
          new Promise(resolve => {
            requestAnimationFrame(() => requestAnimationFrame(() => resolve(null)));
          }),
      );
    /** Add an action from the library; it is selected and its settings open.
     * @param {string} name Visible action name.
     * @param {boolean} [exact] Whether the name must match in full.
     * @param {string} [where] The settings that open: its row, or Properties.
     * @returns {Promise<void>}
     */
    const add = async (name, exact = false, where = inRow) => {
      await page.getByRole("button", { name: "Add action" }).click();
      await page.getByRole("button", { name, exact }).click();
      await page.locator(where).waitFor();
      await settle();
    };
    /** Save the action and wait for the host to confirm the new settings.
     * @param {string} [where] The settings being saved: its row, or Properties.
     * @returns {Promise<void>}
     */
    const save = async (where = inRow) => {
      const before = commands.filter(item => item.command === "event.configure").length;
      await (where === inRow
        ? page.locator(inRow).getByRole("button", { name: "Apply" })
        : page.getByRole("button", { name: "Save step" })
      ).click();
      await until(
        () => commands.filter(item => item.command === "event.configure").length > before,
      );
    };
    /** The newest command of one kind.
     * @param {string} name Command name.
     * @returns {any} Its payload.
     */
    const last = name => commands.filter(item => item.command === name).at(-1)?.payload;
    await page.getByRole("button", { name: "Add action" }).click();
    await page
      .getByRole("button", { name: "Get input value", exact: false })
      .focus();
    await page.locator(".action-library-body").evaluate((/** @type {HTMLElement} */ element) => {
      element.scrollTop = 0;
    });
    const { EXACTUS_ACTION_CATALOG_AUDIT_SCREENSHOT: catalogScreenshot } =
      process.env;
    if (catalogScreenshot)
      await page.locator('[data-panel-id="actions"]').screenshot({
        path: catalogScreenshot,
      });
    const { EXACTUS_ACTION_CATALOG_COMPACT_AUDIT_SCREENSHOT: compactScreenshot } =
      process.env;
    if (compactScreenshot) {
      const viewport = page.viewportSize();
      await page.setViewportSize({ width: 390, height: 844 });
      await page.getByRole("button", { name: "Add action" }).click();
      await page.locator(".action-library-body").evaluate((/** @type {HTMLElement} */ element) => {
        element.scrollTop = 0;
      });
      await page.locator('[data-panel-id="actions"]').screenshot({
        path: compactScreenshot,
      });
      if (viewport) await page.setViewportSize(viewport);
    }
    // The library holds only the palette: choosing an action adds it at once.
    assert.equal(await page.locator("#action-form").count(), 0);
    const setVariableAction = page.locator('[data-add-action="set_variable"]');
    assert.equal(await setVariableAction.getAttribute("draggable"), "true");
    await page.evaluate(() => {
      const source = document.querySelector('[data-add-action="set_variable"]');
      const target = document.querySelector("#table");
      if (!(source instanceof HTMLButtonElement))
        throw new Error("Set-variable action is unavailable");
      if (!(target instanceof HTMLElement))
        throw new Error("Flow drop target is unavailable");
      const transfer = new window.DataTransfer();
      source.dispatchEvent(new DragEvent("dragstart", {
        bubbles: true,
        dataTransfer: transfer,
      }));
      target.dispatchEvent(new DragEvent("dragover", {
        bubbles: true,
        cancelable: true,
        dataTransfer: transfer,
      }));
      target.dispatchEvent(new DragEvent("drop", {
        bubbles: true,
        cancelable: true,
        dataTransfer: transfer,
      }));
      source.dispatchEvent(new DragEvent("dragend", {
        bubbles: true,
        dataTransfer: transfer,
      }));
    });
    await page.locator(inRow).waitFor();
    await settle();
    // Dropping added it already, with a default variable name, and selected it.
    assert.equal(last("event.add").kind, "set_variable");
    assert.ok(last("event.add").output_variable);
    assert.equal(
      await page.locator('.edit-step-row[data-step="added-3"]').getAttribute("aria-pressed"),
      "true",
    );
    assert.equal(
      await page.locator(properties).getByRole("heading", { name: "set_variable" }).count(),
      1,
    );
    await page.locator('.edit-step-detail-form [name="output_variable"]').fill("customerId");
    await page
      .locator('.edit-step-detail-form .variable-field:has([name="variable_value"]) .variable-editor')
      .fill("42");
    await page.locator('.edit-step-detail-form [name="value_type"]').selectOption("integer");
    await save();
    assert.equal(last("event.configure").event_id, "added-3");
    assert.equal(last("event.configure").kind, "set_variable");
    assert.equal(last("event.configure").output_variable, "customerId");
    assert.deepEqual(JSON.parse(last("event.configure").payload), {
      value: "42",
      value_type: "integer",
    });
    await add("REST request");
    const requestUrl = page.locator(
      '.edit-step-detail-form .variable-field:has([name="url"]) .variable-editor',
    );
    await requestUrl.fill("/api/customer/@cust");
    const mentionOption = page
      .locator('.edit-step-detail-form .variable-field:has([name="url"]) .variable-menu')
      .getByRole("option", { name: "customerId" });
    await mentionOption.waitFor({ state: "visible" });
    const { EXACTUS_VARIABLE_MENTION_AUDIT_SCREENSHOT: mentionScreenshot } =
      process.env;
    if (mentionScreenshot)
      await page.waitForTimeout(100);
    if (mentionScreenshot)
      await page.locator(".edit-step-detail").screenshot({
        path: mentionScreenshot,
      });
    await mentionOption.dispatchEvent("pointerdown");
    assert.equal(
      await page.locator('.edit-step-detail-form [name="url"]').inputValue(),
      "/api/customer/{{customerId}}",
    );
    await page.getByRole("tab", { name: "Params" }).click();
    await page.getByRole("button", { name: "Add parameter" }).click();
    await page.locator('.edit-step-detail-form [name="query_0_key"]').fill("include");
    await page
      .locator('.edit-step-detail-form .variable-field:has([name="query_0_value"]) .variable-editor')
      .fill("orders");
    await page.getByRole("tab", { name: "Headers" }).click();
    await page.getByRole("button", { name: "Add header" }).click();
    await page.locator('.edit-step-detail-form [name="header_0_key"]').fill("Authorization");
    await page
      .locator('.edit-step-detail-form .variable-field:has([name="header_0_value"]) .variable-editor')
      .fill("Bearer @customer");
    await page.getByRole("tab", { name: "Variables" }).click();
    await page.getByRole("button", { name: "Add response variable" }).click();
    await page.locator('.edit-step-detail-form [name="capture_0_path"]').fill("data.customer.id");
    await page.locator('.edit-step-detail-form [name="capture_0_name"]').fill("Customer ID");
    await page.locator('.edit-step-detail-form [name="capture_0_value_type"]').selectOption("integer");
    const { EXACTUS_REST_ACTION_AUDIT_SCREENSHOT: restScreenshot } = process.env;
    if (restScreenshot)
      await page.locator(".edit-step-detail").screenshot({
        path: restScreenshot,
      });
    await page.locator('.edit-step-detail-form [name="output_variable"]').fill("customer");
    await save();
    const request = last("event.configure");
    assert.equal(request.kind, "http_call");
    assert.equal(request.url, "/api/customer/{{customerId}}");
    assert.equal(request.output_variable, "customer");
    assert.equal(JSON.parse(request.request_config).query[0].key, "include");
    const { EXACTUS_WEBSOCKET_ACTION_AUDIT_SCREENSHOT: socketScreenshot } =
      process.env;
    if (socketScreenshot) {
      await add("WebSocket session");
      await page
        .locator('.edit-step-detail-form .variable-field:has([name="url"]) .variable-editor')
        .fill("wss://stream.example.test/@customer");
      await page
        .locator('.edit-step-detail-form .variable-field:has([name="url"]) .variable-menu')
        .getByRole("option", { name: "customer", exact: true })
        .dispatchEvent("pointerdown");
      await page
        .locator('.edit-step-detail-form .variable-field:has([name="protocols"]) .variable-editor')
        .fill("updates.v1");
      await page
        .locator('.edit-step-detail-form .variable-field:has([name="message"]) .variable-editor')
        .fill('{"type":"subscribe","customer":"@customer"}');
      await page
        .locator('.edit-step-detail-form .variable-field:has([name="message"]) .variable-editor')
        .press("Escape");
      await page.getByRole("tab", { name: "Variables" }).click();
      await page.getByRole("button", { name: "Add response variable" }).click();
      await page.locator('.edit-step-detail-form [name="capture_0_path"]').fill("payload.total");
      await page.locator('.edit-step-detail-form [name="capture_0_name"]').fill("Live Total");
      await page.locator('.edit-step-detail-form [name="capture_0_value_type"]').selectOption("float");
      await page.locator(".edit-step-detail").screenshot({
        path: socketScreenshot,
      });
      const {
        EXACTUS_SPACING_CAPTURE_SCRIPT: spacingScript,
        EXACTUS_SPACING_CAPTURE_OUTPUT: spacingOutput,
      } = process.env;
      if (spacingScript && spacingOutput) {
        const script = await readFile(spacingScript, { encoding: "utf8" });
        const viewport = page.viewportSize();
        const states = await [390, 1440, 1728].reduce(
          async (previous, width) => {
            const collected = await previous;
            await page.setViewportSize({ width, height: 900 });
            const state = await page.evaluate(script);
            collected.push(
              await page.evaluate(
                (
                  /** @type {{captured: {name: string, elements: Array<{rect: {x: number, y: number, width: number, height: number}}>}, selector: string}} */ payload,
                ) => {
                  const { captured, selector } = payload;
                  const panel = document.querySelector(selector);
                  if (!(panel instanceof HTMLElement)) return captured;
                  const bounds = panel.getBoundingClientRect();
                  captured.name = `request-action-${window.innerWidth}`;
                  captured.elements = captured.elements.filter(element =>
                    element.rect.x >= bounds.x &&
                    element.rect.y >= bounds.y &&
                    element.rect.x + element.rect.width <= bounds.right &&
                    element.rect.y + element.rect.height <= bounds.bottom,
                  );
                  return captured;
                },
                {
                  captured: state,
                  selector: ".edit-step-detail",
                },
              ),
            );
            return collected;
          },
          Promise.resolve(/** @type {object[]} */ ([])),
        );
        await writeFile(spacingOutput, JSON.stringify(states), { encoding: "utf8" });
        if (viewport) await page.setViewportSize(viewport);
      }
    }
    await add("JavaScript");
    await page
      .locator('.edit-step-detail-form [name="payload"]')
      .fill("return __EXACTUS_FLOW__.vars.customer.status === 200;");
    const javascriptOutput = page.locator(
      '.edit-step-detail-form [name="output_variable"]',
    );
    await javascriptOutput.fill("allowed");
    await javascriptOutput.press("Tab");
    assert.equal(
      await javascriptOutput.inputValue(),
      "allowed",
    );
    const {
      EXACTUS_JAVASCRIPT_ACTION_AUDIT_SCREENSHOT: javascriptScreenshot,
      EXACTUS_JAVASCRIPT_VALUES_AUDIT_SCREENSHOT: javascriptValuesScreenshot,
    } = process.env;
    if (javascriptScreenshot) {
      await page.getByRole("tab", { name: "Code" }).click();
      await page.locator(".edit-step-detail").screenshot({
        path: javascriptScreenshot,
      });
    }
    if (javascriptValuesScreenshot) {
      await page.getByRole("tab", { name: /^Values/ }).click();
      await page.locator(".edit-step-detail").screenshot({
        path: javascriptValuesScreenshot,
      });
    }
    await save();
    assert.equal(last("event.configure").kind, "javascript");
    assert.equal(last("event.configure").output_variable, "allowed");
    // If puts a condition on the selected action instead of adding a step.
    const selectedScript = last("event.configure").event_id;
    const beforeIf = commands.filter(item => item.command === "event.add").length;
    await page.getByRole("button", { name: "Add action" }).click();
    await page.getByRole("button", { name: "If", exact: true }).click();
    await until(() => commands.some(item => item.command === "event.update"));
    assert.equal(last("event.update").event_id, selectedScript);
    assert.equal(
      last("event.update").when_expression,
      "__EXACTUS_FLOW__.vars.allowed === true",
    );
    assert.equal(
      commands.filter(item => item.command === "event.add").length,
      beforeIf,
    );
    await add("Pointer & touch", true);
    assert.equal(
      await page.getByText("Selector bookmark", { exact: true }).isVisible(),
      true,
    );
    assert.equal(
      await page.getByRole("button", { name: "Pick on page" }).isVisible(),
      true,
    );
    assert.equal(
      await page.getByRole("button", { name: "Highlight on page" }).isVisible(),
      true,
    );
    // A Click has no target yet, so it is added as unfinished until one is set.
    assert.ok(!last("event.add").selector);
    await page
      .locator('.edit-step-detail-form .variable-field:has([name="selector"]) .variable-editor')
      .fill('ext=[data-customer-id="{{customerId}}"]');
    await save(inRow);
    assert.equal(last("event.configure").kind, "click");
    assert.equal(
      last("event.configure").selector,
      'ext=[data-customer-id="{{customerId}}"]',
    );
  });
});
test("Recording parents contain live steps and timed clips and retain collapse state", async t => {
  await browserTest(t, async (page, url) => {
    const { snapshot } = await studio(page, url);
    snapshot.revision += 1;
    snapshot.recording_state = "recording";
    snapshot.recording_session_id = "take-one";
    snapshot.workspace.flows[0] = {
      ...snapshot.workspace.flows[0],
      events: snapshot.workspace.flows[0].events.map(
        (/** @type {(typeof flow.events)[number]} */ event) => ({
          ...event,
        }),
      ),
      recordings: [
        {
          id: "take-one",
          label: "Recording 1",
          start_ms: 2100,
        },
      ],
    };
    /** Emit a real-time workspace notification through the editor transport.
     * @returns {Promise<void>} Resolves when the state is emitted.
     */
    const update = () =>
      page.evaluate((/** @type {any} */ state) => {
        const targetWindow = /** @type {StudioTestWindow} */ (window);
        targetWindow.studioEvents?.onmessage({
          data: JSON.stringify({
            protocol: 1,
            event: "workspace.changed",
            payload: state,
          }),
        });
      }, snapshot);
    await update();
    const group = page.locator(".recording-group");
    await group.waitFor();
    assert.match(await group.innerText(), /Recording 1.*0 actions/s);
    assert.equal(await page.locator(".recording-band").count(), 1);
    assert.equal(
      await page
        .locator(".edit-step-list > :last-child")
        .getAttribute("data-recording-group"),
      "take-one",
    );
    snapshot.workspace.flows[0].events.push({
      id: "recorded-click",
      kind: "click",
      label: "Click Continue",
      selector: "#continue",
      layer: "interaction",
      elapsed_ms: 2350,
      recording_group_id: "take-one",
    });
    snapshot.revision += 1;
    await update();
    await group.locator('[data-step="recorded-click"]').waitFor();
    assert.equal(
      await page
        .locator('.recording-band [data-step="recorded-click"]')
        .count(),
      1,
    );
    assert.equal(
      await page.locator('#timeline [data-step="recorded-click"]').count(),
      1,
    );
    assert.match(await group.innerText(), /#continue/);
    await group.locator("summary").click();
    assert.equal(await group.getAttribute("open"), null);
    snapshot.revision += 1;
    await update();
    assert.equal(await group.getAttribute("open"), null);
    await group.locator("summary").press("Enter");
    await group.locator('[data-step="recorded-click"]').click();
    assert.equal(
      await page.locator('.edit-step-detail-form [name="selector"]').inputValue(),
      "#continue",
    );
  });
});
/** Select a task workspace through the visible compact navigation.
 * @param {any} page Playwright page driving the editor window.
 * @param {string} view Workspace identifier.
 * @returns {Promise<void>} Resolves after the workspace change is dispatched.
 */
const selectWorkspace = async (page, view) => {
  // Views that existed before the five-tab layout now live inside these tabs.
  /** @type {Record<string, string>} */
  const aliases = {
    record: "edit",
    timeline: "edit",
    inspector: "edit",
    debug: "play",
    profiles: "settings",
    recovery: "settings",
    controls: "settings",
  };
  // Crawl is part of the Flow editor and opens from its transport bar.
  if (view === "crawl") {
    await page.locator("#browser-crawl").click();
    return;
  }
  const tab = aliases[view] ?? view;
  await page.locator(`.section-nav > [data-workspace-view="${tab}"]`).click();
  // The graph draws its connections again in the next animation frame, so wait
  // two frames before a test presses one that is about to be replaced.
  await page.evaluate(
    () =>
      new Promise(resolve => {
        requestAnimationFrame(() => requestAnimationFrame(resolve));
      }),
  );
};
test("Studio sections occupy an independent row between the identity row and the workspace", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    /** Assert the section and command rows at one viewport width.
     * @param {number} width Viewport width under test.
     * @returns {Promise<void>} Resolves after the row assertions run.
     */
    const checkRows = async width => {
      await page.setViewportSize({
        width,
        height: 900,
      });
      const identity = await page.locator(".topbar").boundingBox();
      const sections = await page.locator("#app > .section-nav").boundingBox();
      assert.ok(sections.y >= identity.y + identity.height - 1);
      // No command bar: the workspace starts right under the sections row.
      assert.equal(await page.locator(".workspace-nav").count(), 0);
      const content = await page.locator("#workbench").boundingBox();
      assert.ok(content.y >= sections.y + sections.height - 1);
      assert.ok(Math.abs(sections.width - width) <= 1);
      const footer = await page.locator("#app > footer").boundingBox();
      assert.ok(Math.abs(footer.y + footer.height - 900) <= 1);
      await selectWorkspace(page, "settings");
      assert.equal(
        await page.locator("#app").getAttribute("data-workspace-mode"),
        "settings",
      );
      await selectWorkspace(page, "edit");
    };
    await checkRows(1440);
    await checkRows(1728);
    await checkRows(390);
  });
});
test("Header icons keep their visibility and geometry across hover", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    const header = page.locator('[data-panel-id="workspace"] > header');
    const tools = header.locator(".panel-tool");
    /** Read tool visibility and geometry for the hover regression.
     * @returns {Promise<any[]>} Rendered tool measurements.
     */
    const read = () =>
      tools.evaluateAll((/** @type {Element[]} */ nodes) =>
        nodes.map(node => ({
          opacity: getComputedStyle(node).opacity,
          rect: node.getBoundingClientRect().toJSON(),
        })),
      );
    await page.mouse.move(700, 600);
    const before = await read();
    const box = await header.boundingBox();
    assert.ok(box);
    await page.mouse.move(box.x + 30, box.y + 15);
    assert.deepEqual(await read(), before);
    assert.ok(
      before.every(
        (/** @type {{opacity:string}} */ tool) => tool.opacity === "1",
      ),
    );
    await page.mouse.move(700, 600);
    assert.deepEqual(await read(), before);
  });
});
/** Wait until the editor has posted a command, then return the latest one.
 * @param {Array<{command:string,payload:any}>} commands Commands captured by the route.
 * @param {string} name Command to wait for.
 * @param {(command:{command:string,payload:any}) => boolean} [accept] Extra condition the command must meet.
 * @returns {Promise<{command:string,payload:any}>}
 * @throws {Error} When the expected command was not posted before the deadline.
 */
const posted = async (commands, name, accept = () => true) => {
  const deadline = Date.now() + 2000;
  /** Retry until the expected command is found or its deadline expires.
   * @returns {Promise<{command:string,payload:any}>} Captured command.
   * @throws {Error} When no matching command arrived before the deadline.
   */
  const poll = async () => {
    const found = [...commands]
      .reverse()
      .find(command => command.command === name && accept(command));
    if (found) return found;
    if (Date.now() >= deadline)
      throw new Error(
        `${name} was never posted: ${commands.map((item) => item.command)}`,
      );
    await new Promise(resolve => {
      setTimeout(resolve, 50);
    });
    return poll();
  };
  return poll();
};
/** Bounding box of an element once two reads 50 ms apart agree.
 * @param {{boundingBox: () => Promise<{x:number,y:number,width:number,height:number}|null>}} locator
 * @param {{x:number,y:number,width:number,height:number}|null} [previous]
 * @param {number} [attempts] Reads left before giving up.
 * @returns {Promise<{x:number,y:number,width:number,height:number}|null>}
 */
const settledBox = async (locator, previous = null, attempts = 40) => {
  const box = await locator.boundingBox();
  const same =
    previous !== null &&
    box !== null &&
    Math.abs(previous.x - box.x) < 0.5 &&
    Math.abs(previous.y - box.y) < 0.5 &&
    Math.abs(previous.width - box.width) < 0.5 &&
    Math.abs(previous.height - box.height) < 0.5;
  if (same || attempts === 0) return box;
  await delay(50);
  return settledBox(locator, box, attempts - 1);
};
/** One-pixel PNG used as a stand-in preview frame. */
const pixel = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);
/** Serve scripted preview responses and count the requests made.
 * @param {any} page Studio page.
 * @param {(count:number)=>{status:number,body?:Buffer,headers?:Record<string,string>}} reply Scripted response.
 * @returns {Promise<{count:()=>number}>} Request counter.
 */
const scriptedPreview = async (page, reply) => {
  let count = 0;
  await page.route("**/api/target-preview", (/** @type {any} */ route) => {
    count += 1;
    const { status, body, headers } = reply(count);
    return route.fulfill({
      status,
      body: body ?? "",
      headers: headers ?? {},
    });
  });
  return {
    count: () => count,
  };
};
/** Serve a blank page of the given size as the live preview frame.
 * @param {any} page Studio page.
 * @param {number} width Frame width.
 * @param {number} height Frame height.
 * @returns {Promise<void>}
 */
const serveFrame = async (page, width, height) => {
  const body = Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="${width}" height="${height}" fill="white"/></svg>`,
  );
  await scriptedPreview(page, () => ({
    status: 200,
    body,
    headers: {
      "Content-Type": "image/svg+xml",
      "X-Frame-Age-Ms": "5",
    },
  }));
};
test("Clicks in the letterbox around a preview never reach the target page", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await serveFrame(page, 100, 300);
    await page.waitForSelector('.live-target-frame[data-preview="live"]');
    await page.evaluate(() => {
      const image = document.getElementById("live-target-image");
      if (image) image.style.height = "300px";
    });
    await page.waitForFunction(() => {
      const image = document.getElementById("live-target-image");
      return image instanceof HTMLImageElement && image.naturalWidth > 0;
    });
    const box = await page.locator("#live-target-image").boundingBox();
    assert.ok(box);
    /**
     * Count click commands recorded so far.
     * @returns {number} Recorded click commands.
     */
    const presses = () =>
      commands.filter(
        item =>
          item.command === "browser.input" &&
          item.payload.action === "pointer_down",
      ).length;
    const image = page.locator("#live-target-image");
    await image.click({
      position: {
        x: 3,
        y: box.height / 2,
      },
    });
    assert.equal(presses(), 0);
    await image.click({
      position: {
        x: box.width / 2,
        y: box.height / 2,
      },
    });
    await posted(
      commands,
      "browser.input",
      item => item.payload.action === "pointer_down",
    );
    assert.equal(presses(), 1);
  });
});
/** Boxes of the docked panels, keyed by panel id.
 * @param {any} page Playwright page driving the editor window.
 * @returns {Promise<Record<string,{x:number,y:number,width:number,height:number,grid:string|null}>>}
 */
const panelBoxes = page =>
  page.evaluate(() =>
    Object.fromEntries(
      [...document.querySelectorAll(".workbench > .panel[data-panel-id]")]
        .filter(
          panel =>
            panel.getBoundingClientRect().width > 0 &&
            !panel.classList.contains("is-floating"),
        )
        .map(panel => {
          const box = panel.getBoundingClientRect();
          return [
            panel.getAttribute("data-panel-id"),
            {
              x: box.x,
              y: box.y,
              width: box.width,
              height: box.height,
              grid: panel.getAttribute("data-grid"),
            },
          ];
        }),
    ),
  );
test("Maximized live browser restores on Escape, workspace change and keeps focus reachable", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    await selectWorkspace(page, "record");
    const before = await panelBoxes(page);
    const panel = page.locator('[data-panel-id="target"]');
    await page.locator("#live-target-maximize").click();
    assert.equal(await panel.getAttribute("data-live-maximized"), "");
    await page.locator("#live-target-pick").click();
    await page.locator("#live-target-pick").press("Escape");
    assert.equal(await panel.getAttribute("data-live-maximized"), null);
    assert.equal(
      await page.locator("#live-target-pick").getAttribute("aria-pressed"),
      "false",
    );
    assert.deepEqual(await panelBoxes(page), before);
    await page.locator("#live-target-maximize").click();
    // The maximized panel covers the section tabs, so switch by shortcut-style click.
    await page
      .locator('.section-nav > [data-workspace-view="edit"]')
      .dispatchEvent("click");
    await selectWorkspace(page, "record");
    assert.equal(await panel.getAttribute("data-live-maximized"), null);
    assert.equal(
      await page.locator("#live-target-maximize").getAttribute("aria-pressed"),
      "false",
    );
  });
});
test("Picker hover is throttled and Escape exits picking first", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await serveFrame(page, 200, 100);
    await page.waitForFunction(() => {
      const image = document.getElementById("live-target-image");
      return image instanceof HTMLImageElement && image.naturalWidth > 0;
    });
    await page.locator("#live-target-pick").click();
    const panel = page.locator('[data-panel-id="target"]');
    assert.equal(await panel.getAttribute("data-live-maximized"), "");
    await page.evaluate(() => {
      const image = document.getElementById("live-target-image");
      if (!(image instanceof HTMLImageElement)) return;
      const box = image.getBoundingClientRect();
      /** Dispatch one pointer move over the middle of the image.
       * @returns {boolean} Whether the event was not cancelled.
       */
      const move = () =>
        image.dispatchEvent(
          new PointerEvent("pointermove", {
            bubbles: true,
            pointerId: 1,
            clientX: box.left + box.width / 2,
            clientY: box.top + box.height / 2,
          }),
        );
      move();
      move();
    });
    await posted(commands, "browser.input");
    /** Hover inspections the editor has requested so far.
     * @returns {Array<{command:string,payload:any}>}
     */
    const hoverInspections = () =>
      commands.filter(
        item =>
          item.command === "browser.input" &&
          item.payload.action === "inspect" &&
          item.payload.picked === false,
      );
    assert.equal(hoverInspections().length, 1);
    await page.waitForTimeout(170);
    await page.locator("#live-target-image").hover({
      position: {
        x: 10,
        y: 10,
      },
    });
    await page.waitForTimeout(100);
    assert.equal(hoverInspections().length, 2);
    await page.locator("#live-target-image").press("Escape");
    assert.equal(await panel.getAttribute("data-live-maximized"), null);
    assert.equal(
      await page.locator("#live-target-pick").getAttribute("aria-pressed"),
      "false",
    );
    assert.equal(
      await page.locator("#live-target-maximize").evaluate(
        (/** @type {HTMLElement} */ button) => button === document.activeElement,
      ),
      true,
    );
  });
});
test("Live browser forwards hover, drag and held keyboard modifiers", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await serveFrame(page, 200, 100);
    await page.waitForFunction(() => {
      const image = document.getElementById("live-target-image");
      return image instanceof HTMLImageElement && image.naturalWidth > 0;
    });
    const image = page.locator("#live-target-image");
    const box = await image.boundingBox();
    assert.ok(box);
    const start = commands.length;
    await page.mouse.move(box.x + box.width / 3, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 2 / 3, box.y + box.height / 2);
    await page.mouse.up();
    await image.focus();
    await page.keyboard.down("Shift");
    await page.keyboard.down("Control");
    await page.keyboard.press("KeyA");
    await page.keyboard.up("Control");
    await page.keyboard.up("Shift");
    await posted(commands, "browser.input");
    await page.waitForTimeout(100);
    const actions = commands.slice(start).map(item => item.payload.action);
    assert.ok(actions.includes("pointer_move"));
    assert.ok(actions.includes("pointer_down"));
    assert.ok(actions.includes("pointer_up"));
    assert.deepEqual(
      commands
        .slice(start)
        .filter(item => item.payload.action.startsWith("key_"))
        .map(item => [item.payload.action, item.payload.code]),
      [
        ["key_down", "ShiftLeft"],
        ["key_down", "ControlLeft"],
        ["key_down", "KeyA"],
        ["key_up", "KeyA"],
        ["key_up", "ControlLeft"],
        ["key_up", "ShiftLeft"],
      ],
    );
  });
});
test("Browser panel exposes its tools, target state and preview to assistive technology", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    await selectWorkspace(page, "record");
    await serveFrame(page, 200, 100);
    const panel = page.getByRole("region", {
      name: "Browser panel",
    });
    await panel.waitFor();
    await page.waitForFunction(() => {
      const image = document.getElementById("live-target-image");
      return (
        image instanceof HTMLImageElement &&
        image.naturalWidth === 200 &&
        image.naturalHeight === 100
      );
    });
    const targetStatus = panel.locator("#browser-status");
    assert.equal(await targetStatus.getAttribute("role"), "status");
    assert.equal(await targetStatus.getAttribute("aria-live"), "polite");
    assert.match(await targetStatus.textContent() || "", /Target (ready|closed)/);
    assert.equal(
      await panel.getByRole("toolbar", {
        name: "Browser tools",
      }).count(),
      1,
    );
    const pick = panel.getByRole("button", {
      name: "Pick element",
    });
    const maximize = panel.getByRole("button", {
      name: "Maximize browser",
    });
    assert.equal(await pick.getAttribute("aria-pressed"), "false");
    assert.equal(await maximize.getAttribute("aria-pressed"), "false");
    const { EXACTUS_AUDIT_SCREENSHOT: auditScreenshot } = process.env;
    if (auditScreenshot)
      await page.screenshot({
        path: auditScreenshot,
        fullPage: false,
      });
    await pick.click();
    assert.equal(await pick.getAttribute("aria-pressed"), "true");
    assert.equal(await maximize.getAttribute("aria-pressed"), "true");
    await page
      .getByAltText(
        "Live view of the test browser. Hover, click, drag, touch, type or scroll to interact.",
      )
      .press("Escape");
    assert.equal(await pick.getAttribute("aria-pressed"), "false");
    assert.equal(await maximize.getAttribute("aria-pressed"), "false");
  });
});
test("Every Browser tool keeps an accessible name, even when its label is hidden by a narrow panel", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    await selectWorkspace(page, "record");
    const names = [
      "Record",
      "Pause recording",
      "Stop",
      "Crawl",
      "Pick element",
      "Maximize browser",
    ];
    await [1440, 760].reduce(async (pending, width) => {
      await pending;
      await page.setViewportSize({
        width,
        height: 900,
      });
      // Pause and Stop are hidden until a recording runs, so read the
      // attribute rather than the role tree, which skips hidden controls.
      const counts = await Promise.all(
        names.map(name =>
          page
            .locator(`.live-target-tools button[aria-label="${name}"]`)
            .count(),
        ),
      );
      names.forEach((name, index) => {
        assert.equal(
          counts[index],
          1,
          `${name} should be one named button at ${width}px`,
        );
      });
      // Hiding the text must never remove it from the accessibility tree.
      const removed = await page
        .locator(".live-target-tools .tool-label")
        .evaluateAll((/** @type {Element[]} */ labels) =>
          labels.filter(label => getComputedStyle(label).display === "none"),
        );
      assert.equal(removed.length, 0);
    }, Promise.resolve());
  });
});
test("On a phone the task tabs own the screen and the editor panels stay hidden", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    await page.setViewportSize({
      width: 390,
      height: 844,
    });
    await ["play", "compare", "settings"].reduce(async (pending, view) => {
      await pending;
      await selectWorkspace(page, view);
      const layout = await page.evaluate(() => {
        /** Bounding box of the first element matching the selector.
         * @returns {DOMRect|undefined}
         */
        const box = (/** @type {string} */ selector) =>
          document.querySelector(selector)?.getBoundingClientRect();
        /** Whether a matching element exists and is not display:none.
         * @returns {boolean}
         */
        const visible = (/** @type {string} */ selector) => {
          const element = document.querySelector(selector);
          return (
            element !== null && getComputedStyle(element).display !== "none"
          );
        };
        return {
          workbench: visible("#workbench"),
          panelTabs: visible(".mobile-panel-tabs"),
          surface: box("#workspace-surface"),
          footer: box(".studio > footer"),
          scrollWidth: document.documentElement.scrollWidth,
        };
      });
      assert.equal(layout.workbench, false, `${view}: workbench hidden`);
      assert.equal(layout.panelTabs, false, `${view}: panel tabs hidden`);
      assert.ok(
        layout.surface.height > 500,
        `${view}: surface fills the screen (${layout.surface.height}px)`,
      );
      assert.ok(layout.footer.top >= layout.surface.bottom - 1);
      assert.ok(layout.scrollWidth <= 390, `${view}: no sideways scroll`);
    }, Promise.resolve());
  });
});
test("The compact Runs timeline keeps playback separate from the clock", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    await page.setViewportSize({
      width: 390,
      height: 844,
    });
    await page.locator('[data-mobile-panel="runs"]').click();
    const play = requiredValue(
      await page.locator("#timeline-play").boundingBox(),
    );
    const toolbar = requiredValue(
      await page.locator(".timeline-toolbar").boundingBox(),
    );
    assert.ok(play.x >= toolbar.x);
    assert.ok(play.x + play.width <= toolbar.x + toolbar.width);
    await page.locator("#timecode").waitFor({
      state: "hidden",
    });
    assert.equal(
      await page.locator(".timeline-toolbar").evaluate(
        (/** @type {HTMLElement} */ element) => element.scrollWidth,
      ),
      Math.round(toolbar.width),
    );
    const { EXACTUS_TIMELINE_AUDIT_SCREENSHOT: auditScreenshot } = process.env;
    if (auditScreenshot)
      await page.screenshot({
        path: auditScreenshot,
      });
  });
});
test("Choosing a capture in Compare asks the server by artifact id and opens its preview", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await selectWorkspace(page, "compare");
    await page.locator('[data-surface-shot="screen"]').first().click();
    assert.deepEqual((await posted(commands, "screenshot.open")).payload, {
      artifact_id: "screen",
    });
    const dialog = page.locator("#screenshot-dialog");
    await dialog.waitFor({
      state: "visible",
    });
    assert.match(
      await page.locator("#screenshot-preview").getAttribute("src") ?? "",
      /screenshots\/test\.png$/,
    );
  });
});
test("Each step has an actions menu that moves it and closes on Escape", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    const rows = page.locator(".edit-step-row");
    await rows.first().waitFor();
    await rows.nth(1).locator(".edit-step-more").click();
    assert.equal(await page.locator(".step-menu-item").count(), 3);
    await page.keyboard.press("Escape");
    assert.equal(await page.locator(".step-menu").count(), 0);
    await rows.nth(1).locator(".edit-step-more").click();
    await page
      .getByRole("menuitem", {
        name: "Move up",
      })
      .click();
    const move = await posted(commands, "event.move");
    assert.equal(move.payload.offset, "-1");
    await rows.first().locator(".edit-step-more").click();
    assert.equal(
      await page
        .getByRole("menuitem", {
          name: "Move up",
        })
        .isDisabled(),
      true,
    );
  });
});
test("The Flow toolbar duplicates and removes selected steps, and Add action matches Open browser", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    const rows = page.locator(".edit-step-row");
    await rows.first().waitFor();
    const duplicate = page.locator("#step-duplicate");
    const remove = page.locator("#step-remove");
    assert.equal(await duplicate.isDisabled(), true);
    assert.equal(await remove.isDisabled(), true);
    await rows.first().click();
    assert.equal(await duplicate.isDisabled(), false);
    assert.equal(
      await duplicate.getAttribute("aria-label"),
      "Duplicate 1 step",
    );
    await duplicate.click();
    const copy = await posted(commands, "event.duplicate");
    assert.equal(copy.payload.event_id, "open");
    await remove.click();
    await page
      .locator("dialog.delete-dialog")
      .getByRole("button", {
        name: "Delete step",
      })
      .click();
    const removed = await posted(commands, "event.delete");
    assert.equal(removed.payload.event_id, "open");
    const add = await page.locator("#add-action").boundingBox();
    const open = await page.locator("#browser-toggle").boundingBox();
    assert.ok(add && open);
    assert.equal(Math.round(add.height), Math.round(open.height));
    const small = await duplicate.boundingBox();
    assert.ok(small && small.height < add.height);
    await page.locator("#add-action").click();
    await page.locator('[data-panel-id="actions"]').waitFor({
      state: "visible",
    });
  });
});
test("A step points at a stored selector, sets its targeting and shows why it last warned", async t => {
  await browserTest(t, async (page, url) => {
    const { commands, snapshot } = await studio(page, url);
    snapshot.revision += 1;
    snapshot.target_url = "http://localhost/other";
    snapshot.selectors = [
      {
        selector_id: "sel-card",
        name: "card",
        expression: ".card",
        expected_count: null,
        checks: [],
        validated_on: [
          {
            url: "http://localhost/",
            at: "2026-10-09T10:00:00",
            matches: 3,
          },
        ],
      },
    ];
    // The fixture flow is shared between tests, so edit a copy of it.
    const events = snapshot.workspace.flows[0].events.map(
      (/** @type {any} */ event) => ({
        ...event,
      }),
    );
    events[1] = {
      ...events[1],
      selector: undefined,
      selector_id: "sel-card",
      targets: "all",
      run_mode: "sequential",
    };
    snapshot.workspace.flows[0] = {
      ...snapshot.workspace.flows[0],
      events,
    };
    snapshot.workspace.runs[0].action_records = [
      {
        event_id: "save",
        status: "warning",
        error: "Match count: expected 3, found 2",
        unit: {
          index: 1,
          count: 3,
        },
        cause: {
          phase: "count",
          message: "Expected 3 matches, found 2",
          expected_count: 3,
          found_count: 2,
          target_index: 1,
        },
      },
    ];
    await page.evaluate((/** @type {any} */ state) => {
      const targetWindow = /** @type {StudioTestWindow} */ (window);
      targetWindow.studioEvents?.onmessage({
        data: JSON.stringify({
          protocol: 1,
          event: "workspace.changed",
          payload: state,
        }),
      });
    }, snapshot);
    await page.locator('[data-selector="sel-card"]').click();
    await page.locator("#inspector #selector-form").waitFor();
    assert.equal(
      await page.locator('[data-panel-id="selector-editor"]').count(),
      0,
    );
    assert.equal(
      await page.getByRole("button", { name: "Pick on page" }).isVisible(),
      true,
    );
    assert.equal(
      await page.getByRole("button", { name: "Highlight on page" }).isVisible(),
      true,
    );
    const { EXACTUS_SELECTOR_WIDGET_AUDIT_SCREENSHOT: selectorScreenshot } =
      process.env;
    if (selectorScreenshot) {
      await page.locator("#inspector .selector-live-tools").scrollIntoViewIfNeeded();
      await page.locator('[data-panel-id="properties"]').screenshot({
        path: selectorScreenshot,
      });
    }
    const badge = page.locator(
      '.edit-step-row[data-step="save"] .edit-step-checks',
    );
    await badge.waitFor();
    assert.equal(await badge.textContent(), "Warning");
    assert.equal(await badge.getAttribute("data-state"), "warning");
    await page.locator('.edit-step-row[data-step="save"]').click();
    const form = page.locator("#step-form");
    const detail = page.locator(".edit-step-detail-form");
    await detail.waitFor();
    assert.equal(
      await detail.locator('[name="selector_id"]').inputValue(),
      "sel-card",
    );
    assert.deepEqual(
      await detail.locator('[name="selector_id"] option').allTextContents(),
      ["New expression", "card"],
    );
    assert.equal(await detail.locator('[name="selector"]').isVisible(), false);
    assert.match(
      await form.locator("[data-field=scope-warning]").textContent() ?? "",
      /not tested on the page/,
    );
    const lastRun = form.locator(".last-run");
    assert.match(
      await lastRun.textContent() ?? "",
      /Expected 3 matches, found 2/,
    );
    assert.match(await lastRun.textContent() ?? "", /match 2 of 3/);
    assert.equal(await form.locator('[name="run_mode"]').isVisible(), true);
    assert.equal(
      await form.locator('[name="run_mode"] option[value="parallel"]').evaluate(
        (/** @type {Element} */ option) =>
          /** @type {HTMLOptionElement} */
          (option).disabled,
      ),
      true,
    );
    await form.locator('[name="pace_delay"]').fill("250");
    await form.locator('[name="continue_on_failure"]').check();
    await form.locator('[name="after_until"]').fill("sel_card_exists");
    await form.locator('button[type="submit"]').click();
    // The click's own settings live in its row; saving Properties updates the
    // step's targeting and failure policy.
    const update = await posted(commands, "event.update");
    assert.equal(update.payload.selector_id, "sel-card");
    assert.equal(update.payload.selector, "");
    assert.equal(update.payload.targets, "all");
    assert.equal(update.payload.run_mode, "sequential");
    assert.equal(update.payload.pace_between.delay_ms, 250);
    assert.equal(update.payload.pace.until, "sel_card_exists");
    assert.equal(update.payload.continue_on_failure, true);
    assert.equal("pace_delay" in update.payload, false);
  });
});
test("A collapsed floating window stays a title bar instead of shrinking to a line", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    const panel = page.locator('[data-panel-id="steps"]');
    await panel.locator('[data-panel-action="float"]').first().click({
      force: true,
    });
    await page.waitForFunction(() =>
      document
        .querySelector('[data-panel-id="steps"]')
        ?.classList.contains("is-floating"),
    );
    const open = await panel.boundingBox();
    await panel.locator('[data-panel-action="collapse"]').click();
    await page.waitForFunction(() =>
      document
        .querySelector('[data-panel-id="steps"]')
        ?.classList.contains("is-collapsed"),
    );
    const bar = await panel.boundingBox();
    const header = await panel.locator(":scope > header").boundingBox();
    assert.ok(open && bar && header);
    assert.ok(bar.height >= header.height, "the whole header stays visible");
    assert.ok(bar.height < open.height, "the body is folded away");
    assert.equal(Math.round(bar.x), Math.round(open.x));
    assert.equal(Math.round(bar.y), Math.round(open.y));
    assert.equal(
      await panel.locator(".panel-title-text").first().isVisible(),
      true,
    );
    await panel.locator('[data-panel-action="collapse"]').click();
    await page.waitForFunction(
      () =>
        !document
          .querySelector('[data-panel-id="steps"]')
          ?.classList.contains("is-collapsed"),
    );
    const restored = await panel.boundingBox();
    assert.ok(
      restored && Math.round(restored.height) === Math.round(open.height),
    );
  });
});
test("The condition builder offers searchable spreadsheet-style tokens", async t => {
  await browserTest(t, async (page, url) => {
    const { snapshot } = await studio(page, url);
    snapshot.revision += 1;
    snapshot.condition_vocabulary = [
      {
        name: "flow_succeeded",
        kind: "system",
        value_type: "boolean",
        detail: "Flow succeeded",
      },
      {
        name: "sel_card_text",
        kind: "probe",
        value_type: "string",
        detail: "Text",
      },
      {
        name: "draft_saved",
        kind: "output",
        value_type: "boolean",
        detail: "Draft saved",
      },
    ];
    snapshot.selectors = [
      {
        selector_id: "sel-card",
        name: "card",
        expression: ".card",
        expected_count: null,
        checks: [],
        validated_on: [],
      },
    ];
    const events = snapshot.workspace.flows[0].events.map(
      (/** @type {any} */ event) => ({
        ...event,
      }),
    );
    events[1] = {
      ...events[1],
      selector: undefined,
      selector_id: "sel-card",
    };
    snapshot.workspace.flows[0] = {
      ...snapshot.workspace.flows[0],
      events,
    };
    await page.evaluate((/** @type {any} */ state) => {
      const targetWindow = /** @type {StudioTestWindow} */ (window);
      targetWindow.studioEvents?.onmessage({
        data: JSON.stringify({
          protocol: 1,
          event: "workspace.changed",
          payload: state,
        }),
      });
    }, snapshot);
    await page.locator('.edit-step-row[data-step="save"]').click();
    const input = page.locator('#step-form [name="after_until"]');
    await input.waitFor({
      state: "attached",
    });
    await input.evaluate((/** @type {HTMLInputElement} */ field) => {
      field.value =
        'contains(sel_card_text, "search-string") and (draft_saved or flow_succeeded)';
      field.dispatchEvent(
        new Event("input", {
          bubbles: true,
        }),
      );
    });
    const field = page.locator(".condition-field").last();
    assert.equal(
      await field.locator(".pill-call .pill-name").textContent(),
      "contains",
    );
    assert.equal(
      await field.locator(".pill-name").first().evaluate(
        (/** @type {HTMLElement} */ item) =>
          getComputedStyle(item).textTransform,
      ),
      "uppercase",
    );
    assert.equal(await field.locator(".pill-slot").count(), 0);
    assert.equal(await field.locator(".pill-add").count(), 0);
    assert.ok(await field.locator("svg.st0").count());
    assert.ok(await field.locator("svg.st00").count());
    const colors = await field.locator(".pill-ref").evaluateAll(
      (/** @type {HTMLElement[]} */ items) =>
        items.map(item => getComputedStyle(item).backgroundColor),
    );
    assert.equal(new Set(colors).size, 3);
    await field.locator(".pill-name").first().click();
    await field.locator(".condition-menu-search").fill("mat");
    assert.deepEqual(
      await field.locator(".condition-menu-item strong").allTextContents(),
      ["matches"],
    );
    await field.locator(".condition-menu-search").press("Escape");
    const { EXACTUS_EXPRESSION_AUDIT_SCREENSHOT: auditScreenshot } =
      process.env;
    if (auditScreenshot) {
      await page.mouse.move(0, 0);
      await field.screenshot({
        path: auditScreenshot,
      });
    }
    await field.locator(".condition-mode").click();
    assert.equal(
      await field.locator(".condition-editor").getAttribute("data-collapsed"),
      null,
    );
  });
});
test("The top bar creates projects with unique names and opens the gallery", async t => {
  await browserTest(t, async (page, url) => {
    const { commands, snapshot } = await studio(page, url);
    snapshot.revision += 1;
    snapshot.project = {
      slug: "checkout",
      name: "Checkout",
      description: "",
      tags: [],
      author: "",
      version: "",
      created_at: "2026-10-01T00:00:00",
      base_url: "",
      saved: true,
    };
    snapshot.library = {
      projects: [
        {
          slug: "checkout",
          name: "Checkout",
          description: "Staging flows",
          tags: ["web"],
          author: "Ana",
          version: "",
          created_at: "2026-10-01T00:00:00",
          modified_at: "2026-10-08T00:00:00",
          last_run_at: "",
          flows: 3,
          runs: 0,
          base_url: "",
          legacy: false,
        },
        {
          slug: "admin",
          name: "Admin panel",
          description: "",
          tags: ["internal"],
          author: "",
          version: "",
          created_at: "2026-10-02T00:00:00",
          modified_at: "2026-10-07T00:00:00",
          last_run_at: "",
          flows: 1,
          runs: 0,
          base_url: "",
          legacy: false,
        },
      ],
      recents: ["checkout", "admin"],
      tags: ["internal", "web"],
    };
    await page.evaluate((/** @type {any} */ state) => {
      const targetWindow = /** @type {StudioTestWindow} */ (window);
      targetWindow.studioEvents?.onmessage({
        data: JSON.stringify({
          protocol: 1,
          event: "workspace.changed",
          payload: state,
        }),
      });
    }, snapshot);
    assert.equal(await page.locator("#project-name").textContent(), "Checkout");
    await page.locator('[data-bar="new"]').click();
    const dialog = page.locator("dialog.new-project");
    const create = dialog.getByRole("button", {
      name: "Create project",
    });
    assert.equal(await create.isDisabled(), true);
    await dialog.locator('input[name="name"]').fill(" checkout ");
    assert.match(
      await dialog.locator(".pd-issue").first().textContent() ?? "",
      /already exists/,
    );
    assert.equal(await create.isDisabled(), true);
    await dialog.locator('input[name="name"]').fill("Billing");
    await dialog.locator('input[name="tags"]').fill("web, Smoke, web");
    snapshot.dirty = false;
    await create.click();
    const made = await posted(commands, "project.create");
    assert.equal(made.payload.name, "Billing");
    assert.deepEqual(made.payload.tags, ["web", "Smoke"]);
    await dialog.waitFor({
      state: "detached",
    });
    await page.locator('[data-bar="open"]').click();
    const gallery = page.locator("dialog.project-gallery");
    assert.equal(await gallery.locator(".pd-item").count(), 2);
    await gallery.locator('input[type="search"]').fill("internal");
    assert.equal(await gallery.locator(".pd-item").count(), 1);
    await gallery.locator(".pd-item").click();
    await gallery
      .getByRole("button", {
        name: "Open",
        exact: true,
      })
      .click();
    const opened = await posted(commands, "project.open");
    assert.equal(opened.payload.slug, "admin");
  });
});
test("Icons are inline SVG on one grid, and icon-only buttons have no box in any state", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    await page.locator(".edit-step-row").first().click();
    const report = await page.evaluate(() => {
      const icons = [...document.querySelectorAll("svg.studio-icon")];
      return {
        count: icons.length,
        empty: icons.filter(icon => !icon.firstElementChild).length,
        wrongBox: icons.filter(
          icon => icon.getAttribute("viewBox") !== "0 0 24 24",
        ).length,
        sized: icons.filter(
          icon => icon.hasAttribute("width") || icon.hasAttribute("height"),
        ).length,
        spans: document.querySelectorAll("span.studio-icon").length,
        masks: [...document.querySelectorAll("*")].filter(node => {
          const style = getComputedStyle(node);
          return style.maskImage !== "none" || style.webkitMaskImage !== "none";
        }).length,
      };
    });
    assert.ok(report.count > 20);
    assert.deepEqual(
      {
        empty: report.empty,
        wrongBox: report.wrongBox,
        sized: report.sized,
        spans: report.spans,
        masks: report.masks,
      },
      {
        empty: 0,
        wrongBox: 0,
        sized: 0,
        spans: 0,
        masks: 0,
      },
    );
    /** Read the computed style of one element.
     * @param {string} selector Element to inspect.
     * @returns {Promise<{
     *   background: string,
     *   border: string,
     *   color: string,
     * }>}
     */
    const look = selector =>
      page.evaluate((/** @type {string} */ query) => {
        const style = getComputedStyle(
          /** @type {Element} */
          (document.querySelector(query)),
        );
        return {
          background: style.backgroundColor,
          border: style.borderTopWidth,
          color: style.color,
        };
      }, selector);
    // Colours animate when the page settles; read them once they have.
    await page.evaluate(() =>
      Promise.all(
        document.getAnimations().map(animation => animation.finished),
      ),
    );
    const selectors = [
      "#command-palette-open",
      "#timeline-play",
      ".edit-step-row .edit-step-grip",
    ];
    const rests = await Promise.all(selectors.map(look));
    assert.deepEqual(
      rests.map(rest => rest.background),
      selectors.map(() => "rgba(0, 0, 0, 0)"),
    );
    await page.locator("#timeline-play").hover();
    await page.evaluate(() =>
      Promise.all(
        document.getAnimations().map(animation => animation.finished),
      ),
    );
    const hover = await look("#timeline-play");
    assert.equal(hover.background, "rgba(0, 0, 0, 0)");
    assert.notEqual(hover.color, (await look("#command-palette-open")).color);
  });
});
test("The picker offers selector strategies and warns when a selector is ambiguous", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    await selectWorkspace(page, "record");
    await page.evaluate(() => {
      const targetWindow = /** @type {StudioTestWindow} */ (window);
      targetWindow.studioEvents?.onmessage({
        data: JSON.stringify({
          event: "target.inspected",
          payload: {
            target_inspection: {
              picked: true,
              element: {
                selector: "button",
                text: "Save",
                role: "button",
                name: "Save",
                matches: 3,
                frame: "main page",
                page: "http://demo.test/",
                alternatives: [
                  {
                    strategy: "css",
                    selector: "button",
                    matches: 3,
                  },
                  {
                    strategy: "role and name",
                    selector: 'role=button[name="Save"]',
                    matches: 1,
                  },
                ],
                rect: {
                  x: 10,
                  y: 10,
                  width: 50,
                  height: 20,
                },
              },
            },
          },
        }),
      });
    });
    const strategy = page.locator("#live-target-strategy");
    // The unique strategy is preferred over the first one.
    assert.equal(
      await page.locator("#live-target-selector").inputValue(),
      'role=button[name="Save"]',
    );
    assert.match(
      await page.locator("#live-target-identity").textContent() || "",
      /button “Save” · 1 match · main page/,
    );
    await strategy.selectOption({
      label: "css (3)",
    });
    assert.match(
      await page.locator("#live-target-identity").textContent() || "",
      /3 matches — choose a more specific strategy/,
    );
    assert.equal(
      await page
        .locator("#live-target-identity")
        .getAttribute("data-ambiguous"),
      "",
    );
  });
});
for (const mode of [
  "docked",
  "floating",
  "maximized",
  "zoomed",
  "dense",
  "tall",
]) {
  test(`Preview pointer mapping reaches the page centre when ${mode}`, async t => {
    await browserTest(t, async (page, url) => {
      const { commands } = await studio(page, url);
      // A wide frame in the panel exercises the letterbox on one axis.
      const frameWidth = mode === "tall" ? 100 : 200;
      const frameHeight = mode === "tall" ? 200 : 100;
      await serveFrame(page, frameWidth, frameHeight);
      await page.waitForSelector('.live-target-frame[data-preview="live"]');
      await page.waitForFunction(() => {
        const image = document.getElementById("live-target-image");
        return image instanceof HTMLImageElement && image.naturalWidth > 0;
      });
      if (mode === "maximized")
        await page.locator("#live-target-maximize").click();
      if (mode === "floating") {
        const panel = page.locator('[data-panel-id="target"]');
        await panel.locator('[data-panel-action="float"]').click();
        await page.waitForFunction(() =>
          document
            .querySelector('[data-panel-id="target"]')
            ?.classList.contains("is-floating"),
        );
      }
      if (mode === "zoomed" || mode === "dense") {
        // Browser zoom shrinks the CSS viewport and raises the pixel ratio; a
        // high-density display raises only the pixel ratio.
        const session = await page.context().newCDPSession(page);
        await session.send("Emulation.setDeviceMetricsOverride", {
          width: mode === "zoomed" ? 960 : 1440,
          height: mode === "zoomed" ? 600 : 900,
          deviceScaleFactor: mode === "zoomed" ? 1.5 : 2,
          mobile: false,
        });
        await page.waitForTimeout(200);
      }
      const image = page.locator("#live-target-image");
      const box = await settledBox(image);
      assert.ok(box);
      const before = commands.length;
      await image.click({
        position: {
          x: box.width / 2,
          y: box.height / 2,
        },
      });
      await posted(
        commands,
        "browser.input",
        item => item.payload.action === "pointer_down",
      );
      const click = commands
        .slice(before)
        .find(item => item.payload.action === "pointer_down");
      assert.ok(click);
      assert.ok(commands.length > before);
      assert.equal(click.payload.action, "pointer_down");
      // Integer pointer events can resolve only to one displayed image pixel.
      // Keep the tolerance at that rendered precision after letterboxing.
      const scale = Math.min(
        box.width / frameWidth,
        box.height / frameHeight,
      );
      const xTolerance = Math.max(1.5, 1440 / (frameWidth * scale));
      const yTolerance = Math.max(1.5, 900 / (frameHeight * scale));
      assert.ok(
        Math.abs(click.payload.x - 720) <= xTolerance,
        `x ${click.payload.x} (tolerance ${xTolerance})`,
      );
      assert.ok(
        Math.abs(click.payload.y - 450) <= yTolerance,
        `y ${click.payload.y} (tolerance ${yTolerance})`,
      );
    });
  });
}
test("A floating letterboxed preview aligns the inspected element overlay", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    await serveFrame(page, 200, 100);
    await page.waitForFunction(() => {
      const image = document.getElementById("live-target-image");
      return image instanceof HTMLImageElement && image.naturalWidth > 0;
    });
    const panel = page.locator('[data-panel-id="target"]');
    await panel.locator('[data-panel-action="float"]').click();
    await page.waitForFunction(() =>
      document
        .querySelector('[data-panel-id="target"]')
        ?.classList.contains("is-floating"),
    );
    await page.evaluate(() => {
      const targetWindow = /** @type {StudioTestWindow} */ (window);
      targetWindow.studioEvents?.onmessage({
        data: JSON.stringify({
          event: "target.inspected",
          payload: {
            target_inspection: {
              picked: false,
              element: {
                selector: "#quarter-frame",
                text: "Quarter frame",
                rect: {
                  x: 360,
                  y: 225,
                  width: 720,
                  height: 450,
                },
              },
            },
          },
        }),
      });
    });
    const image = await page.locator("#live-target-image").boundingBox();
    const overlay = await page.locator("#live-target-highlight").boundingBox();
    assert.ok(image && overlay);
    const scale = Math.min(image.width / 200, image.height / 100);
    const pageBox = {
      x: image.x + (image.width - 200 * scale) / 2,
      y: image.y + (image.height - 100 * scale) / 2,
      width: 200 * scale,
      height: 100 * scale,
    };
    for (const [actual, expected] of [
      [overlay.x, pageBox.x + pageBox.width / 4],
      [overlay.y, pageBox.y + pageBox.height / 4],
      [overlay.width, pageBox.width / 2],
      [overlay.height, pageBox.height / 2],
    ])
      assert.ok(
        Math.abs(actual - expected) <= 1,
        `${actual} differs from ${expected}`,
      );
  });
});
test("The live preview names its state and stops fetching while hidden", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    await selectWorkspace(page, "record");
    const frame = page.locator(".live-target-frame");
    await page.waitForFunction(() =>
      document
        .querySelector(".live-target-frame")
        ?.hasAttribute("data-preview"),
    );
    assert.ok(
      ["loading", "live", "stale", "closed", "error"].includes(
        await frame.getAttribute("data-preview") || "",
      ),
    );
    // Graph has no Browser panel, so the preview is hidden there.
    await selectWorkspace(page, "graph");
    let fetched = 0;
    page.on("request", (/** @type {{url:()=>string}} */ request) => {
      if (request.url().endsWith("/api/target-preview")) fetched += 1;
    });
    await page.waitForTimeout(1500);
    assert.ok(fetched <= 2, `hidden preview fetched ${fetched} times`);
  });
});
test("A finished recording can be renamed, moved and deleted from its menu, but not while capturing", async t => {
  await browserTest(t, async (page, url) => {
    const { commands, snapshot } = await studio(page, url);
    snapshot.revision += 1;
    snapshot.workspace.flows[0] = {
      ...snapshot.workspace.flows[0],
      events: [
        {
          id: "recorded-click",
          kind: "click",
          label: "Click Continue",
          selector: "#continue",
          layer: "interaction",
          elapsed_ms: 2350,
          recording_group_id: "take-one",
        },
      ],
      recordings: [
        {
          id: "take-one",
          label: "Recording 1",
          start_ms: 2100,
        },
      ],
    };
    /** Emit the current snapshot as a real-time notification.
     * @returns {Promise<void>}
     */
    const update = () =>
      page.evaluate((/** @type {any} */ state) => {
        const targetWindow = /** @type {StudioTestWindow} */ (window);
        targetWindow.studioEvents?.onmessage({
          data: JSON.stringify({
            protocol: 1,
            event: "workspace.changed",
            payload: state,
          }),
        });
      }, snapshot);
    await update();
    const more = page.locator(".recording-more");
    await more.waitFor();
    // The menu button is keyboard reachable and does not toggle the group.
    await more.focus();
    await page.keyboard.press("Enter");
    await page
      .getByRole("menuitem", {
        name: "Start 1 s later",
      })
      .click();
    const moved = await posted(commands, "recording.retime");
    assert.deepEqual(moved.payload, {
      recording_id: "take-one",
      delta_ms: "1000",
    });
    assert.equal(
      await page.locator(".recording-group").getAttribute("open"),
      "",
    );
    // Rename saves on Enter, keeps the old name when empty, and cancels on Escape.
    await more.click();
    await page
      .getByRole("menuitem", {
        name: "Rename",
      })
      .click();
    const name = page.locator(".recording-rename");
    await name.fill("  Login   flow ");
    await name.press("Enter");
    const renamed = await posted(commands, "recording.rename");
    assert.equal(renamed.payload.label, "Login flow");
    await more.click();
    await page
      .getByRole("menuitem", {
        name: "Rename",
      })
      .click();
    await page.locator(".recording-rename").fill("");
    await page.locator(".recording-rename").press("Enter");
    assert.match(
      await page.locator("#status").textContent() || "",
      /needs a name/,
    );
    assert.equal(
      commands.filter(item => item.command === "recording.rename").length,
      1,
    );
    // Deleting asks once and states what goes with it.
    await more.click();
    await page
      .getByRole("menuitem", {
        name: "Delete recording",
      })
      .click();
    assert.match(
      await page.locator(".delete-dialog").textContent() || "",
      /1 action/,
    );
    await page
      .getByRole("button", {
        name: "Keep recording",
      })
      .click();
    assert.equal(
      commands.filter(item => item.command === "recording.delete").length,
      0,
    );
    await more.click();
    await page
      .getByRole("menuitem", {
        name: "Delete recording",
      })
      .click();
    await page
      .getByRole("button", {
        name: "Delete recording",
      })
      .click();
    assert.deepEqual((await posted(commands, "recording.delete")).payload, {
      recording_id: "take-one",
    });
    // While the same recording is capturing, its menu stays closed.
    snapshot.revision += 1;
    snapshot.recording_state = "recording";
    snapshot.recording_session_id = "take-one";
    await update();
    await more.click();
    assert.equal(await page.locator(".step-menu").count(), 0);
  });
});
test("Arrow conditions are edited atomically in the dockable Graph inspector", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await selectWorkspace(page, "graph");
    assert.equal(
      await page
        .locator(".edge-table, #connection-form, .graph-node-action")
        .count(),
      0,
    );
    await page.locator(".composition-link").first().press("Enter");
    const form = page.locator(".graph-connection-form");
    await form.locator('[name="mode"]').selectOption("condition");
    await form.locator('[name="condition_expression"]').fill("success == true");
    await form.locator('[name="priority"]').fill("3");
    await form.locator('[name="max_traversals"]').fill("4");
    await form.locator('[type="submit"]').click();
    const update = await posted(commands, "edge.update");
    assert.equal(update.payload.index, "0");
    assert.equal(update.payload.source, flow.id);
    assert.equal(update.payload.target, "second");
    assert.equal(update.payload.condition_expression, "success == true");
    assert.equal(update.payload.priority, 3);
    assert.equal(update.payload.max_traversals, 4);
    assert.equal(
      commands.some(item => item.command === "edge.remove"),
      false,
    );
  });
});
test("Creating a flow updates the shared Flows panel and graph from one snapshot", async t => {
  await browserTest(t, async (page, url) => {
    const { snapshot } = await studio(page, url);
    const shared = await page
      .locator('[data-panel-id="workspace"]')
      .elementHandle();
    assert.ok(shared);
    let created = 0;
    await page.route("**/api/command**", async (/** @type {any} */ route) => {
      const request = route.request().postDataJSON();
      if (request.command !== "flow.create") {
        await route.fallback();
        return;
      }
      created++;
      snapshot.workspace.flows.push({
        ...flow,
        id: `new-${created}`,
        name: `New flow ${created}`,
        events: [],
      });
      snapshot.revision++;
      await route.fulfill({
        json: {
          protocol: 1,
          id: request.id,
          ok: true,
          result: snapshot,
        },
      });
    });
    await page.locator('[data-cmd="flow.create"]').first().click();
    await page.locator('#flows [data-flow="new-1"]').waitFor();
    assert.equal(await page.locator('[data-node-flow="new-1"]').count(), 1);
    await selectWorkspace(page, "graph");
    assert.equal(
      await shared.evaluate(
        /** @param {HTMLElement} node */
        node =>
          node === document.querySelector('[data-panel-id="workspace"]'),
      ),
      true,
    );
    await page.locator('[data-cmd="flow.create"]').click();
    await page.locator('[data-node-flow="new-2"]').waitFor();
    assert.equal(await page.locator('#flows [data-flow="new-2"]').count(), 1);
    assert.equal(await page.locator(".flow-node").count(), 4);
    await selectWorkspace(page, "edit");
    assert.equal(
      await page.locator('#flows [data-flow="new-2"]').isVisible(),
      true,
    );
  });
});
test("A rejected arrow property save retains the condition draft", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    await selectWorkspace(page, "graph");
    await page.locator(".composition-link").first().press("Enter");
    await page.route("**/api/command**", async (/** @type {any} */ route) => {
      const request = route.request().postDataJSON();
      if (request.command !== "edge.update") {
        await route.fallback();
        return;
      }
      await route.fulfill({
        json: {
          protocol: 1,
          id: request.id,
          ok: false,
          error: "Revision conflict",
        },
      });
    });
    const form = page.locator(".graph-connection-form");
    await form.locator('[name="mode"]').selectOption("condition");
    await form.locator('[name="condition_expression"]').fill("result == true");
    await form.locator('[type="submit"]').click();
    await form
      .getByRole("status")
      .filter({
        hasText: "Revision conflict",
      })
      .waitFor();
    assert.equal(
      await form.locator('[name="condition_expression"]').inputValue(),
      "result == true",
    );
    assert.equal(await form.locator('[type="submit"]').isDisabled(), false);
  });
});
test("Graph connections are keyboard-selectable, removable and fit inside a compact viewport", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await selectWorkspace(page, "graph");
    assert.ok(await page.locator('[data-panel-id="properties"]').isVisible());
    const connection = page.locator(".composition-link").first();
    await connection.press("Enter");
    assert.equal(await connection.getAttribute("aria-pressed"), "true");
    assert.equal(
      await page.locator(".graph-connection-inspector h2").textContent(),
      "Connection",
    );
    assert.match(
      await page.locator(".graph-connection-details").textContent(),
      /Checkout.*Cleanup/,
    );
    await page
      .getByRole("button", {
        name: "Remove connection",
        exact: true,
      })
      .click();
    const remove = await posted(commands, "edge.remove");
    assert.equal(remove.payload.mode, "always");
    assert.equal(remove.payload.priority, 1);
    await page.setViewportSize({
      width: 390,
      height: 844,
    });
    assert.equal(
      await page
        .locator('.mobile-panel-tabs [data-mobile-panel="steps"]')
        .textContent(),
      "Graph",
    );
    assert.equal(
      await page
        .locator('.mobile-panel-tabs [data-mobile-panel="runs"]')
        .isVisible(),
      false,
    );
    await page
      .locator('.mobile-panel-tabs [data-mobile-panel="steps"]')
      .click();
    await page.locator("#graph-fit").click();
    const geometry = await page.evaluate(() => {
      const canvas = document.getElementById("graph");
      if (!canvas) throw new Error("Missing graph canvas");
      const frame = canvas.getBoundingClientRect();
      return [...canvas.querySelectorAll(".flow-node")].map(node => {
        const bounds = node.getBoundingClientRect();
        return (
          bounds.left >= frame.left &&
          bounds.right <= frame.right &&
          bounds.top >= frame.top &&
          bounds.bottom <= frame.bottom
        );
      });
    });
    assert.ok(geometry.length && geometry.every(Boolean));
    assert.equal(
      await page
        .locator(".flow-node")
        .first()
        .evaluate(
          (/** @type {HTMLElement} */ node) => getComputedStyle(node).position,
        ),
      "absolute",
    );
    await page.locator('[data-graph-output="second"]').press("Enter");
    await page.locator("#graph").press("Escape");
    assert.equal(
      await page.locator("#graph").getAttribute("data-connecting"),
      null,
    );
  });
});
/** Layout saved by the dock grid.
 * @param {any} page Playwright page driving the editor window.
 * @returns {Promise<any>}
 */
const savedLayout = page =>
  page.evaluate(() =>
    JSON.parse(localStorage.getItem("studio.dock-grid.v1") ?? "null"),
  );
/** Assert panels neither overlap nor leave the workbench and fill all of it.
 * @param {Record<string,{x:number,y:number,width:number,height:number}>} boxes
 * @param {{x:number,y:number,width:number,height:number}} area
 * @returns {void}
 */
const assertTiled = (boxes, area) => {
  const list = Object.entries(boxes);
  let covered = 0;
  for (const [id, box] of list) {
    assert.ok(
      box.x >= area.x - 1 && box.y >= area.y - 1,
      `${id} starts outside`,
    );
    assert.ok(
      box.x + box.width <= area.x + area.width + 1 &&
        box.y + box.height <= area.y + area.height + 1,
      `${id} ends outside`,
    );
    covered += box.width * box.height;
  }
  for (let first = 0; first < list.length; first += 1)
    for (let second = first + 1; second < list.length; second += 1) {
      const firstEntry = list[first];
      const secondEntry = list[second];
      assert.ok(firstEntry && secondEntry);
      const [, a] = firstEntry;
      const [, b] = secondEntry;
      const across =
        Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
      const down =
        Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
      assert.ok(
        across < 2 || down < 2,
        `${firstEntry[0]} overlaps ${secondEntry[0]}`,
      );
    }
  assert.ok(covered / (area.width * area.height) > 0.97, `gaps: ${covered}`);
};
/** Drag a panel header with the mouse and report the drop preview.
 * @param {any} page Playwright page driving the editor window.
 * @param {string} id Panel being dragged.
 * @param {{x:number,y:number}} to Pointer destination.
 * @param {boolean} [release] Whether to drop at the destination.
 * @returns {Promise<{kind:string|null,blocked:boolean}>}
 */
const dragPanel = async (page, id, to, release = true) => {
  const header = await page
    .locator(`.workbench > [data-panel-id="${id}"] > header .panel-title`)
    .boundingBox();
  assert.ok(header);
  await page.mouse.move(header.x + 6, header.y + header.height / 2);
  await page.mouse.down();
  await page.mouse.move(header.x + 40, header.y + 40, {
    steps: 3,
  });
  await page.mouse.move(to.x, to.y, {
    steps: 10,
  });
  const preview = await page.evaluate(() => {
    const drop = document.querySelector(".dock-drop:not([hidden])");
    return {
      kind: drop?.getAttribute("data-kind") ?? null,
      blocked: drop?.hasAttribute("data-blocked") ?? false,
      selected: window.getSelection()?.toString() ?? "",
      dragging: document.body.classList.contains("panel-dock-dragging"),
    };
  });
  assert.equal(preview.selected, "", "dragging must not select text");
  assert.ok(preview.dragging);
  if (release) await page.mouse.up();
  return preview;
};
test("Dock grid panels tile the workspace and share one set of track lines", async t => {
  await browserTest(t, async (page, url) => {
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });
    await studio(page, url);
    const boxes = await panelBoxes(page);
    assert.deepEqual(Object.keys(boxes).sort(), [
      "properties",
      "steps",
      "target",
      "timeline",
      "workspace",
    ]);
    const area = await page.locator(".workbench").boundingBox();
    assertTiled(boxes, area);
    // Columns line up across rows: the right column's panels share one edge.
    assert.ok(
      Math.abs(
        requiredValue(boxes[panelKeys.target]).x -
          requiredValue(boxes[panelKeys.properties]).x,
      ) <= 1,
    );
    assert.ok(
      Math.abs(
        requiredValue(boxes[panelKeys.target]).width -
          requiredValue(boxes[panelKeys.properties]).width,
      ) <= 1,
    );
    assert.ok(
      Math.abs(
        requiredValue(boxes[panelKeys.workspace]).x +
          requiredValue(boxes[panelKeys.workspace]).width +
          1 -
          requiredValue(boxes[panelKeys.steps]).x,
      ) <= 1,
    );
    // The timeline fills the area beside the full-height Flows panel.
    assert.ok(
      Math.abs(
        requiredValue(boxes[panelKeys.timeline]).x +
          requiredValue(boxes[panelKeys.timeline]).width -
          (area.x + area.width),
      ) <= 1,
    );
    // Every handle sits on an edge shared by panels.
    const edges = new Set(
      Object.values(boxes).flatMap(box => [
        Math.round(box.x),
        Math.round(box.x + box.width),
        Math.round(box.y),
        Math.round(box.y + box.height),
      ]),
    );
    const handles = await page
      .locator(".dock-handle")
      .evaluateAll((/** @type {Element[]} */ nodes) =>
        nodes.map(node => {
          const box = node.getBoundingClientRect();
          return {
            axis: node.getAttribute("data-axis"),
            line: Math.round(
              node.getAttribute("data-axis") === "c"
                ? box.x + box.width / 2
                : box.y + box.height / 2,
            ),
          };
        }),
      );
    assert.ok(handles.length >= 3);
    for (const handle of handles)
      assert.ok(
        [...edges].some(edge => Math.abs(edge - handle.line) <= 2),
        JSON.stringify({
          handle,
          edges: [...edges],
        }),
      );
  });
});
test("Resizing a shared track line moves it for every panel and is remembered", async t => {
  await browserTest(t, async (page, url) => {
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });
    await studio(page, url);
    const handle = page.locator('.dock-handle[data-axis="c"]').first();
    const line = await handle.boundingBox();
    const before = await panelBoxes(page);
    await page.mouse.move(line.x + line.width / 2, line.y + 120);
    await page.mouse.down();
    await page.mouse.move(line.x + line.width / 2 + 40, line.y + 120, {
      steps: 4,
    });
    const moving = await handle.boundingBox();
    assert.ok(
      Math.abs(moving.x - line.x - 40) <= 2,
      "the marker follows the pointer",
    );
    await page.mouse.move(line.x + line.width / 2 + 60, line.y + 120, {
      steps: 4,
    });
    await page.mouse.up();
    const after = await panelBoxes(page);
    assert.ok(
      Math.abs(
        requiredValue(after[panelKeys.workspace]).width -
          requiredValue(before[panelKeys.workspace]).width -
          60,
      ) <= 2,
    );
    assert.ok(
      Math.abs(
        requiredValue(before[panelKeys.steps]).width -
          requiredValue(after[panelKeys.steps]).width -
          60,
      ) <= 2,
    );
    await handle.press("ArrowRight");
    const nudged = await panelBoxes(page);
    assert.ok(
      Math.abs(
        requiredValue(nudged[panelKeys.workspace]).width -
          requiredValue(after[panelKeys.workspace]).width -
          16,
      ) <= 2,
    );
    // A panel never shrinks below its minimum.
    await page.mouse.move(line.x + line.width / 2 + 76, line.y + 120);
    await page.mouse.down();
    await page.mouse.move(2, line.y + 120, {
      steps: 8,
    });
    await page.mouse.up();
    const floor = await panelBoxes(page);
    assert.ok(
      requiredValue(floor[panelKeys.workspace]).width >= 120,
      JSON.stringify(floor[panelKeys.workspace]),
    );
    await page.reload();
    await page.waitForSelector(".dock-handle");
    const restored = await panelBoxes(page);
    assert.ok(
      Math.abs(
        requiredValue(restored[panelKeys.workspace]).width -
          requiredValue(floor[panelKeys.workspace]).width,
      ) <= 1,
    );
  });
});
test("Collapsing frees space for neighbours by position and restoring returns the old size", async t => {
  await browserTest(t, async (page, url) => {
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });
    await studio(page, url);
    /** Toggle a panel's collapsed state through its visible header control.
     * @param {string} id Panel id.
     * @returns {Promise<void>} Completed click.
     */
    const toggle = id =>
      page
        .locator(`[data-panel-id="${id}"] [data-panel-action="collapse"]`)
        .click();
    const start = await panelBoxes(page);
    // The bottom timeline collapses to a horizontal bar; the area above grows.
    await toggle("timeline");
    const bar = await panelBoxes(page);
    assert.equal(
      await page
        .locator('[data-panel-id="timeline"]')
        .getAttribute("data-collapse"),
      "v",
    );
    assert.ok(
      Math.abs(requiredValue(bar[panelKeys.timeline]).height - 36) <= 1,
    );
    assert.ok(
      requiredValue(bar[panelKeys.steps]).height >
        requiredValue(start[panelKeys.steps]).height + 150,
    );
    await toggle("timeline");
    const back = await panelBoxes(page);
    assert.ok(
      Math.abs(
        requiredValue(back[panelKeys.timeline]).height -
          requiredValue(start[panelKeys.timeline]).height,
      ) <= 1,
    );
    assert.ok(
      Math.abs(
        requiredValue(back[panelKeys.steps]).height -
          requiredValue(start[panelKeys.steps]).height,
      ) <= 1,
    );
    // The left panel collapses sideways into a vertical bar.
    await toggle("workspace");
    const side = await panelBoxes(page);
    assert.equal(
      await page
        .locator('[data-panel-id="workspace"]')
        .getAttribute("data-collapse"),
      "h",
    );
    assert.ok(
      Math.abs(requiredValue(side[panelKeys.workspace]).width - 36) <= 1,
    );
    assert.ok(
      requiredValue(side[panelKeys.steps]).width >
        requiredValue(start[panelKeys.steps]).width + 150,
    );
    await toggle("workspace");
    const sideBack = await panelBoxes(page);
    assert.ok(
      Math.abs(
        requiredValue(sideBack[panelKeys.workspace]).width -
          requiredValue(start[panelKeys.workspace]).width,
      ) <= 1,
    );
    assert.ok(
      Math.abs(
        requiredValue(sideBack[panelKeys.steps]).width -
          requiredValue(start[panelKeys.steps]).width,
      ) <= 1,
    );
    // Stacked panels collapse vertically and the neighbour fills the column.
    await toggle("properties");
    const stacked = await panelBoxes(page);
    assert.ok(
      Math.abs(requiredValue(stacked[panelKeys.properties]).height - 36) <= 1,
    );
    assert.ok(
      requiredValue(stacked[panelKeys.target]).height >
        requiredValue(start[panelKeys.target]).height + 150,
    );
    await toggle("properties");
    const restored = await panelBoxes(page);
    assert.ok(
      Math.abs(
        requiredValue(restored[panelKeys.target]).height -
          requiredValue(start[panelKeys.target]).height,
      ) <= 1,
    );
    assert.ok(
      Math.abs(
        requiredValue(restored[panelKeys.properties]).height -
          requiredValue(start[panelKeys.properties]).height,
      ) <= 1,
    );
    // A collapsed panel keeps only the chevron and its icon.
    await toggle("target");
    const visible = await page.evaluate(() =>
      [...document.querySelectorAll('[data-panel-id="target"] > header *')]
        .filter(node => node.getBoundingClientRect().width > 0)
        .map(node => node.className)
        .filter(name => /panel-title-text|status|address/.test(name)),
    );
    assert.deepEqual(visible, []);
  });
});
test("Dragging a panel docks it beside another, swaps places, or docks along the window edge", async t => {
  await browserTest(t, async (page, url) => {
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });
    await studio(page, url);
    const area = await page.locator(".workbench").boundingBox();
    const start = await panelBoxes(page);
    // Pressing Escape cancels a drag without touching the layout.
    await page.keyboard.down("Escape");
    await page.keyboard.up("Escape");
    const steps = start[panelKeys.steps];
    const near = await dragPanel(
      page,
      "properties",
      {
        x: requiredValue(steps).x + 12,
        y: requiredValue(steps).y + requiredValue(steps).height / 2,
      },
      false,
    );
    assert.equal(near.kind, "edge");
    await page.keyboard.press("Escape");
    await page.mouse.up();
    assert.equal(
      requiredValue((await panelBoxes(page))[panelKeys.properties]).grid,
      requiredValue(start[panelKeys.properties]).grid,
    );
    // Dropping on a panel's edge places it beside that panel.
    await dragPanel(page, "properties", {
      x: requiredValue(steps).x + 12,
      y: requiredValue(steps).y + requiredValue(steps).height / 2,
    });
    const beside = await panelBoxes(page);
    assertTiled(beside, area);
    assert.ok(
      requiredValue(beside[panelKeys.properties]).x <
        requiredValue(beside[panelKeys.steps]).x,
    );
    assert.ok(
      requiredValue(beside[panelKeys.properties]).x >=
        requiredValue(beside[panelKeys.workspace]).x +
          requiredValue(beside[panelKeys.workspace]).width -
          1,
    );
    assert.ok(
      Math.abs(
        requiredValue(beside[panelKeys.properties]).height -
          requiredValue(beside[panelKeys.steps]).height,
      ) <= 2,
    );
    assert.ok((await savedLayout(page)).cells.properties);
    // Dropping on the middle of a panel swaps the two.
    const middle = beside[panelKeys.steps];
    const swapPreview = await dragPanel(
      page,
      "workspace",
      {
        x: requiredValue(middle).x + requiredValue(middle).width / 2,
        y: requiredValue(middle).y + requiredValue(middle).height / 2,
      },
      false,
    );
    assert.equal(swapPreview.kind, "swap");
    await page.mouse.up();
    const swapped = await panelBoxes(page);
    assertTiled(swapped, area);
    assert.ok(
      requiredValue(swapped[panelKeys.workspace]).x >
        requiredValue(swapped[panelKeys.steps]).x,
    );
    // Dropping at the window edge docks along the whole edge.
    await dragPanel(page, "target", {
      x: area.x + 6,
      y: area.y + area.height / 2,
    });
    const outer = await panelBoxes(page);
    assertTiled(outer, area);
    assert.ok(Math.abs(requiredValue(outer[panelKeys.target]).x - area.x) <= 1);
    assert.ok(
      Math.abs(requiredValue(outer[panelKeys.target]).height - area.height) <=
        1,
    );
    // A drop that would leave a panel too small is refused.
    await page.setViewportSize({
      width: 1000,
      height: 700,
    });
    const tiny = (await panelBoxes(page))[panelKeys.timeline];
    const refused = await dragPanel(
      page,
      "steps",
      {
        x: requiredValue(tiny).x + requiredValue(tiny).width - 8,
        y: requiredValue(tiny).y + requiredValue(tiny).height / 2,
      },
      false,
    );
    assert.ok(refused.kind);
    await page.keyboard.press("Escape");
    await page.mouse.up();
  });
});
test("The panel menu docks, places beside, floats and resets", async t => {
  await browserTest(t, async (page, url) => {
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });
    await studio(page, url);
    const area = await page.locator(".workbench").boundingBox();
    const properties = page.locator('[data-panel-id="properties"]');
    /** Open the properties panel docking menu.
     * @returns {Promise<void>} Completed menu opening.
     */
    const menu = async () => {
      await properties.locator('[data-panel-action="dock-menu"]').click();
    };
    await menu();
    await properties.locator('[data-panel-dock="left"]').click();
    const left = await panelBoxes(page);
    assertTiled(left, area);
    assert.ok(
      Math.abs(requiredValue(left[panelKeys.properties]).x - area.x) <= 1,
    );
    assert.ok(
      Math.abs(
        requiredValue(left[panelKeys.properties]).height - area.height,
      ) <= 2,
    );
    await menu();
    await properties
      .locator("[data-panel-beside-target]")
      .selectOption("steps");
    await properties.locator('[data-panel-edge="bottom"]').click();
    const below = await panelBoxes(page);
    assertTiled(below, area);
    assert.ok(
      requiredValue(below[panelKeys.properties]).y >
        requiredValue(below[panelKeys.steps]).y,
    );
    // Floating removes the panel from the grid and docking returns it.
    await properties.locator('[data-panel-action="float"]').click();
    assert.ok(
      await properties.evaluate((/** @type {HTMLElement} */ node) =>
        node.classList.contains("is-floating"),
      ),
    );
    assert.equal(
      await properties.evaluate(
        (/** @type {HTMLElement} */ node) => getComputedStyle(node).position,
      ),
      "fixed",
    );
    assert.equal((await panelBoxes(page))[panelKeys.properties], undefined);
    await properties.locator('[data-panel-action="float"]').click();
    const docked = await panelBoxes(page);
    assert.ok(docked[panelKeys.properties]);
    assertTiled(docked, area);
    // The command palette resets everything to the default layout.
    await page.locator("#command-palette-open").click();
    await page.locator('[data-palette-command="reset-layout"]').click();
    const reset = await panelBoxes(page);
    assert.equal(requiredValue(reset[panelKeys.properties]).grid, "2,1,1,1");
    assert.equal(requiredValue(reset[panelKeys.workspace]).grid, "0,0,1,3");
  });
});
test("Steps reorder by dragging and clips retime by dragging along the timeline", async t => {
  await browserTest(t, async (page, url) => {
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });
    const { commands } = await studio(page, url);
    const rows = page.locator(".edit-step-row");
    const first = await rows.nth(0).boundingBox();
    const third = await rows.nth(2).boundingBox();
    await page.mouse.move(first.x + 120, first.y + first.height / 2);
    await page.mouse.down();
    await page.mouse.move(first.x + 120, third.y + third.height - 4, {
      steps: 8,
    });
    assert.equal(
      await page.evaluate(() => window.getSelection()?.toString()),
      "",
    );
    assert.ok(await page.locator(".edit-step-row[data-drop]").count());
    await page.mouse.up();
    const reorder = await posted(commands, "event.reorder");
    assert.equal(reorder.payload.event_id, "open");
    assert.equal(reorder.payload.index, "2");
    // Alt+Arrow moves a focused step without the mouse.
    await rows.nth(1).focus();
    await page.keyboard.press("Alt+ArrowDown");
    const nudge = await posted(commands, "event.move");
    assert.equal(nudge.payload.offset, "1");
    // Dragging a clip along the ruler sets its time.
    await selectWorkspace(page, "timeline");
    const clip = page.locator('#timeline .clip[data-step="save"]').first();
    const box = await clip.boundingBox();
    await page.mouse.move(box.x + 20, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + 20 + 96, box.y + box.height / 2, {
      steps: 6,
    });
    assert.ok(await page.locator(".timeline-drop-line").count());
    await page.mouse.up();
    const retime = await posted(commands, "event.retime");
    assert.equal(retime.payload.event_id, "save");
    assert.equal(retime.payload.elapsed_ms, "2000");
  });
});
test("Text is never selectable outside inputs, even while pressing and dragging", async t => {
  await browserTest(t, async (page, url) => {
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });
    await studio(page, url);
    await page.locator(".edit-step-row").first().dblclick();
    await page.locator('[data-panel-id="steps"] > header').dblclick();
    await page.locator("body").press("Control+a");
    assert.equal(
      await page.evaluate(() => window.getSelection()?.toString()),
      "",
    );
    assert.equal(
      await page.evaluate(() => getComputedStyle(document.body).userSelect),
      "none",
    );
    assert.equal(
      await page
        .locator(".inspector-content input")
        .first()
        .evaluate(
          (/** @type {Element} */ node) => getComputedStyle(node).userSelect,
        ),
      "text",
    );
  });
});
test("Panel content adapts to the width of its panel", async t => {
  await browserTest(t, async (page, url) => {
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });
    await studio(page, url);
    const label = page
      .locator(".timeline-tools > button span:not(.studio-icon)")
      .first();
    const tools = page.locator(".timeline-tools");
    await label.waitFor({
      state: "visible",
    });
    // The timeline sits beside the 232 px Flows panel, so the panel is
    // narrower than the window by that much.
    await page.setViewportSize({
      width: 1300,
      height: 900,
    });
    await label.waitFor({
      state: "hidden",
    });
    await tools.waitFor({
      state: "visible",
    });
    await page.setViewportSize({
      width: 1100,
      height: 900,
    });
    await tools.waitFor({
      state: "hidden",
    });
    assert.ok(await page.locator(".timeline-timecode").isVisible());
    // Narrowing the panel itself, not the window, triggers the same change.
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });
    await tools.waitFor({
      state: "visible",
    });
    const flows = page.locator('[data-panel-id="workspace"]');
    const title = flows.locator(".panel-title-text");
    await title.waitFor({
      state: "visible",
    });
    const handle = page.locator('.dock-handle[data-axis="c"]').first();
    await handle.waitFor({
      state: "visible",
    });
    const line = await handle.boundingBox();
    assert.ok(line);
    await page.mouse.move(line.x + line.width / 2, line.y + 100);
    await page.mouse.down();
    await page.mouse.move(line.x - 400, line.y + 100, {
      steps: 8,
    });
    await page.mouse.up();
    await title.waitFor({
      state: "hidden",
    });
    assert.ok(await flows.locator(".panel-title .studio-icon").isVisible());
  });
});
test("Graph has its own panels, and the Flows panel is one component shared with Edit", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    const edit = await panelBoxes(page);
    await selectWorkspace(page, "graph");
    const graph = await panelBoxes(page);
    assert.deepEqual(Object.keys(graph).sort(), [
      "composition",
      "properties",
      "workspace",
    ]);
    assert.equal(
      await page.locator('[data-panel-id="timeline"]').isVisible(),
      false,
    );
    assert.equal(
      await page.locator('[data-panel-id="target"]').isVisible(),
      false,
    );
    // Flows sits in the same place and has the same size in both workspaces.
    for (const key of /** @type {const} */ (["x", "y", "width", "height"]))
      assert.equal(
        requiredValue(graph[panelKeys.workspace])[key],
        requiredValue(edit[panelKeys.workspace])[key],
        key,
      );
    // Collapsing it in Graph collapses the same panel in Edit.
    const library = page.locator('[data-panel-id="workspace"]');
    await library.locator('[data-panel-action="collapse"]').click();
    await selectWorkspace(page, "edit");
    assert.equal(
      await library
        .locator('[data-panel-action="collapse"]')
        .getAttribute("aria-expanded"),
      "false",
    );
    // Expanding it again restores Edit's layout exactly.
    await library.locator('[data-panel-action="collapse"]').click();
    assert.deepEqual(await panelBoxes(page), edit);
    await selectWorkspace(page, "graph");
    assert.equal(
      await library
        .locator('[data-panel-action="collapse"]')
        .getAttribute("aria-expanded"),
      "true",
    );
  });
});
test("Resizing the Flows panel in Graph resizes it in the Flow editor too", async t => {
  await browserTest(t, async (page, url) => {
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });
    await studio(page, url);
    await selectWorkspace(page, "graph");
    const handle = page.locator('.dock-handle[data-axis="c"]').first();
    const line = requiredValue(await handle.boundingBox());
    await page.mouse.move(line.x + line.width / 2, line.y + 80);
    await page.mouse.down();
    await page.mouse.move(line.x + 60, line.y + 80, {
      steps: 8,
    });
    await page.mouse.up();
    /** Measure the workspace panel width while a view is selected.
     * @param {string} view Workspace identifier to select.
     * @returns {Promise<number>} Workspace panel width in CSS pixels.
     */
    const widthIn = async view => {
      await selectWorkspace(page, view);
      return requiredValue((await panelBoxes(page))[panelKeys.workspace]).width;
    };
    const graph = await widthIn("graph");
    assert.ok(graph > 232, `Flows should have grown, was ${graph}`);
    assert.ok(Math.abs(await widthIn("edit") - graph) <= 1);
    await page.reload();
    await page.locator("#flows .tree-item").first().waitFor();
    assert.ok(Math.abs(await widthIn("edit") - graph) <= 1);
  });
});
test("Graph docks resize collapse float and reload independently of Edit", async t => {
  await browserTest(t, async (page, url) => {
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });
    await studio(page, url);
    const edit = await panelBoxes(page);
    await selectWorkspace(page, "graph");
    const area = requiredValue(await page.locator("#workbench").boundingBox());
    assertTiled(await panelBoxes(page), area);
    // The second column line separates Graph-only panels; the first one is the
    // shared Flows panel's edge and is covered by its own test.
    const handle = page.locator('.dock-handle[data-axis="c"]').nth(1);
    const line = requiredValue(await handle.boundingBox());
    await page.mouse.move(line.x + line.width / 2, line.y + 80);
    await page.mouse.down();
    await page.mouse.move(line.x + 40, line.y + 80, {
      steps: 8,
    });
    await page.mouse.up();
    const properties = page.locator('[data-panel-id="properties"]');
    await properties.locator('[data-panel-action="float"]').click();
    assertTiled(await panelBoxes(page), area);
    await properties.locator('[data-panel-action="float"]').click();
    const graph = await panelBoxes(page);
    await selectWorkspace(page, "edit");
    assert.deepEqual(await panelBoxes(page), edit);
    await page.reload();
    await page.locator("#flows .tree-item").first().waitFor();
    await selectWorkspace(page, "graph");
    const restored = await panelBoxes(page);
    for (const id of Object.keys(graph))
      for (const key of /** @type {const} */ (["x", "y", "width", "height"]))
        assert.ok(
          Math.abs(
            requiredValue(restored[id])[key] - requiredValue(graph[id])[key],
          ) <= 1,
        );
    assert.ok(
      await page.evaluate(() =>
        localStorage.getItem("studio.dock-grid.v1.graph"),
      ),
    );
  });
});
test("Live browser maximizes without rearranging docks and picks without clicking the target", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await selectWorkspace(page, "record");
    const before = await panelBoxes(page);
    await page.locator("#live-target-maximize").click();
    const maximized = await page
      .locator('[data-panel-id="target"]')
      .boundingBox();
    assert.ok(maximized && maximized.x === 0 && maximized.y === 0);
    await page.locator("#browser-record").click();
    await posted(commands, "recorder.record");
    await page.locator("#live-target-pick").click();
    const pickedResponse = page.waitForResponse(
      (
        /** @type {{url:()=>string,request:()=>{postDataJSON:()=>{command?:string,payload?:{picked?:boolean}}}}} */
        response,
      ) => {
        if (!response.url().endsWith("/api/command")) return false;
        const body = response.request().postDataJSON();
        return (
          body?.command === "browser.input" && body.payload?.picked === true
        );
      },
    );
    await page.locator("#live-target-image").click({
      position: {
        x: 100,
        y: 5,
      },
    });
    await pickedResponse;
    const input = [...commands]
      .reverse()
      .find(
        command =>
          command.command === "browser.input" &&
          command.payload.picked === true,
      );
    assert.ok(input);
    assert.equal(input.payload.action, "inspect");
    assert.equal(input.payload.picked, true);
    await page.evaluate(() => {
      const targetWindow = /** @type {StudioTestWindow} */ (window);
      targetWindow.studioEvents?.onmessage({
        data: JSON.stringify({
          event: "target.inspected",
          payload: {
            target_inspection: {
              picked: true,
              element: {
                selector: "[data-toggle-status]",
                text: "Toggle state",
                rect: {
                  x: 200,
                  y: 100,
                  width: 100,
                  height: 30,
                },
              },
            },
          },
        }),
      });
    });
    assert.equal(
      await page.locator("#live-target-selector").inputValue(),
      "[data-toggle-status]",
    );
    await page.locator("#live-target-use").click();
    // With nothing selected, using the pick adds a Click that already targets it.
    const added = await posted(commands, "event.add");
    assert.equal(added.payload.kind, "click");
    assert.equal(added.payload.selector, "[data-toggle-status]");
    assert.ok(
      !await page
        .locator('[data-panel-id="target"]')
        .getAttribute("data-live-maximized"),
    );
    const after = await panelBoxes(page);
    assert.deepEqual(after[panelKeys.target], before[panelKeys.target]);
  });
});
test("A picked selector goes into the selected step without touching its other draft fields", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await page.locator(".edit-step-row").nth(1).click();
    await page.locator('#step-form [name="label"]').fill("Unsaved order label");
    await page.evaluate(() => {
      const targetWindow = /** @type {StudioTestWindow} */ (window);
      targetWindow.studioEvents?.onmessage({
        data: JSON.stringify({
          event: "target.inspected",
          payload: {
            target_inspection: {
              picked: true,
              element: {
                selector: "[data-picked]",
                text: "Picked",
                rect: {
                  x: 1,
                  y: 1,
                  width: 10,
                  height: 10,
                },
              },
            },
          },
        }),
      });
    });
    /** Count the event.add commands issued so far.
     * @returns {number}
     */
    const adds = () =>
      commands.filter(item => item.command === "event.add").length;
    await page.locator("#live-target-use").click();
    assert.equal(
      await page
        .locator('.edit-step-detail-form [name="selector"]')
        .inputValue(),
      "[data-picked]",
    );
    assert.equal(
      await page.locator('#step-form [name="label"]').inputValue(),
      "Unsaved order label",
    );
    assert.equal(adds(), 0);
    assert.equal(
      commands.filter(item => item.command === "event.update").length,
      0,
    );
    assert.ok(
      await page
        .getByRole("button", {
          name: "Discard edits",
          exact: true,
        })
        .isVisible(),
    );
  });
});
test("A pick inside a frame is reported as unsupported instead of a false match", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    await selectWorkspace(page, "record");
    await page.evaluate(() => {
      const targetWindow = /** @type {StudioTestWindow} */ (window);
      targetWindow.studioEvents?.onmessage({
        data: JSON.stringify({
          event: "target.inspected",
          payload: {
            target_inspection: {
              picked: true,
              element: {
                selector: "#deep",
                text: "Deep",
                role: "button",
                name: "Deep",
                matches: 1,
                frame: "frame inner",
                page: "about:srcdoc",
                unsupported: "Elements inside frames can not be targeted.",
                rect: {
                  x: 10,
                  y: 120,
                  width: 80,
                  height: 30,
                },
              },
            },
          },
        }),
      });
    });
    assert.equal(await page.locator("#live-target-use").isDisabled(), true);
    const identity = page.locator("#live-target-identity");
    assert.match(await identity.textContent() || "", /inside frames/);
    assert.equal(await identity.getAttribute("data-ambiguous"), "");
  });
});
/** Push a changed snapshot to the editor as a live notification.
 * @param {any} page Studio page.
 * @param {any} state Snapshot to publish.
 * @returns {Promise<void>}
 */
const publish = (page, state) =>
  page.evaluate((/** @type {any} */ value) => {
    /** @type {any} */
    (window).studioEvents.onmessage({
      data: JSON.stringify({
        protocol: 1,
        event: "workspace.changed",
        payload: value,
      }),
    });
  }, state);
test("The browser opens on its own once, and stays closed after the user closes it", async t => {
  await browserTest(t, async (page, url) => {
    const { commands, snapshot } = await studio(page, url);
    /**
     * Count the recorded "browser.open" commands.
     * @returns {number} How many open commands the page issued.
     */
    const opens = () =>
      commands.filter(item => item.command === "browser.open").length;
    // Nothing is open and an address is ready: the page appears without a click.
    await publish(page, {
      ...snapshot,
      revision: snapshot.revision + 1,
      target_state: "closed",
      recorder_clients: 0,
    });
    await posted(commands, "browser.open");
    assert.equal(opens(), 1);
    // Another closed snapshot does not open it again.
    await publish(page, {
      ...snapshot,
      revision: snapshot.revision + 2,
      target_state: "closed",
      recorder_clients: 0,
    });
    await page.waitForTimeout(200);
    assert.equal(opens(), 1);
    // Closing is a choice and is respected.
    await publish(page, {
      ...snapshot,
      revision: snapshot.revision + 3,
      target_state: "ready",
      recorder_clients: 1,
    });
    await page.locator("#browser-toggle").click();
    await posted(commands, "browser.close");
    await publish(page, {
      ...snapshot,
      revision: snapshot.revision + 4,
      target_state: "closed",
      recorder_clients: 0,
    });
    await page.waitForTimeout(200);
    assert.equal(opens(), 1);
    assert.equal(
      await page.locator("#status").textContent(),
      "Open the target browser to record or run tests.",
    );
  });
});
test("An empty browser says what is missing instead of only 'closed'", async t => {
  await browserTest(t, async (page, url) => {
    const { snapshot } = await studio(page, url);
    await scriptedPreview(page, () => ({
      status: 204,
    }));
    /** Read the message the empty preview shows.
     * @returns {Promise<string>}
     */
    const message = () =>
      page.evaluate(() => {
        const frame = document.querySelector(".live-target-frame");
        return frame
          ? getComputedStyle(frame, "::after").content.replaceAll('"', "")
          : "";
      });
    const closed = {
      ...snapshot,
      target_state: "closed",
      recorder_clients: 0,
    };
    // A service project whose service is not running yet.
    await publish(page, {
      ...closed,
      revision: 10,
      target_address: null,
    });
    await page.waitForFunction(
      () =>
        document
          .querySelector(".live-target-frame")
          ?.getAttribute("data-hint") === "service",
    );
    await page.waitForSelector('.live-target-frame[data-preview="closed"]');
    assert.match(await message(), /Start the service in Settings/);
    // A project with no address.
    await publish(page, {
      ...closed,
      revision: 11,
      target_address: "about:blank",
    });
    await page.waitForFunction(
      () =>
        document
          .querySelector(".live-target-frame")
          ?.getAttribute("data-hint") === "address",
    );
    assert.match(await message(), /Set the address in Settings/);
  });
});
/** Every command of one name sent so far.
 * @param {any[]} commands Commands the mock service received.
 * @param {string} name Command name.
 * @returns {any[]}
 */
const sentAs = (commands, name) =>
  commands.filter(item => item.command === name);
test("Settings edits a profile with typed fields, a linked aspect ratio and clear errors", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await selectWorkspace(page, "settings");
    await page.locator('[data-profile="mobile"]').click();
    const width = page.locator('#settings-profiles [name="width"]');
    const height = page.locator('#settings-profiles [name="height"]');
    assert.equal(await width.inputValue(), "390");
    // The ratio shows the profile's own shape and edits the height.
    assert.equal(await page.locator('[name="ratio-n"]').inputValue(), "195");
    assert.equal(await page.locator('[name="ratio-d"]').inputValue(), "422");
    await page.locator('[name="ratio-n"]').fill("9");
    await page.locator('[name="ratio-d"]').fill("16");
    assert.equal(await height.inputValue(), String(Math.round(390 * 16 / 9)));
    // Orientation swaps the two sides.
    await page.locator('[name="orientation"]').selectOption("landscape");
    assert.equal(await width.inputValue(), String(Math.round(390 * 16 / 9)));
    assert.equal(await height.inputValue(), "390");
    await page.locator('[name="orientation"]').selectOption("portrait");
    // A value outside the range is explained next to its field and not sent.
    await width.fill("10");
    await width.blur();
    assert.match(
      await page.locator('[data-field="width"] .field-error').innerText(),
      /160 to 8192 px/,
    );
    assert.equal(await width.getAttribute("aria-invalid"), "true");
    await page.locator("[data-profile-save]").click();
    assert.equal(sentAs(commands, "profile.save").length, 0);
    // A valid profile is saved with typed values and only supported media.
    await width.fill("390");
    await page.locator('[name="prefers-color-scheme"]').selectOption("dark");
    await page.locator('[name="touch"]').selectOption("touch");
    await page.locator("[data-profile-save]").click();
    const saved = await posted(commands, "profile.save");
    assert.equal(saved.payload.profile.id, "mobile");
    assert.equal(saved.payload.profile.touch, true);
    assert.deepEqual(saved.payload.profile.media, {
      "prefers-color-scheme": "dark",
    });
    assert.equal(typeof saved.payload.profile.width, "number");
    // What the test browser cannot emulate is listed, not offered.
    assert.match(
      await page.locator(".settings-unsupported").textContent() || "",
      /monochrome/,
    );
  });
});
test("Settings creates a profile from the name and refuses to delete the last one", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await selectWorkspace(page, "settings");
    await page.locator("[data-profile-new]").click();
    await page.locator('#settings-profiles [name="name"]').fill("Dark Phone");
    await page.locator("[data-profile-save]").click();
    const created = await posted(commands, "profile.save");
    assert.equal(created.payload.profile.id, "dark-phone");
    assert.equal(created.payload.profile.name, "Dark Phone");
    // Deleting asks once, and names what is deleted.
    await page.locator('[data-profile="mobile"]').click();
    await page.locator("[data-profile-delete]").click();
    assert.match(
      await page.locator(".delete-dialog").textContent() || "",
      /Delete Mobile\?/,
    );
    await page
      .getByRole("button", {
        name: "Keep profile",
      })
      .click();
    assert.equal(sentAs(commands, "profile.delete").length, 0);
    await page.locator("[data-profile-delete]").click();
    await page.locator('.delete-dialog button[value="delete"]').click();
    assert.deepEqual((await posted(commands, "profile.delete")).payload, {
      profile_id: "mobile",
    });
  });
});
test("Settings offers the demo server, and Start saves it, runs it and opens the browser", async t => {
  await browserTest(t, async (page, url) => {
    const { commands, snapshot } = await studio(page, url);
    const demo = {
      mode: "service",
      url: "",
      port: null,
      command: ["/venv/bin/python", "/repo/demo/server.py", "--port", "0"],
      cwd: "",
      service_port: null,
      path: "/",
    };
    await publish(page, {
      ...snapshot,
      revision: 20,
      target_suggestion: demo,
      workspace: {
        ...snapshot.workspace,
        target: {
          mode: "url",
          url: "",
          port: null,
          command: [],
          cwd: "",
          service_port: null,
          path: "/",
        },
      },
    });
    await selectWorkspace(page, "settings");
    // Pre-filled: "Start a service" chosen, with the demo's own command shown.
    assert.equal(
      await page.locator('input[name="mode"]:checked').getAttribute("value"),
      "service",
    );
    assert.equal(
      await page.locator('#settings-target [name="command"]').inputValue(),
      "/venv/bin/python /repo/demo/server.py --port 0",
    );
    assert.match(
      await page.locator("[data-target-notice]").innerText(),
      /only when you press Start service/,
    );
    assert.match(
      await page.locator("#settings-target").innerText(),
      /Nothing is saved until you press Start or Save/,
    );
    // Nothing ran until the button is pressed.
    assert.equal(sentAs(commands, "target.start").length, 0);
    assert.equal(await page.locator("[data-target-stop]").isDisabled(), true);
    await page.locator("[data-target-start]").click();
    const target = await posted(commands, "target.save");
    assert.deepEqual(target.payload.target.command, [
      "/venv/bin/python",
      "/repo/demo/server.py",
      "--port",
      "0",
    ]);
    assert.equal(target.payload.target.mode, "service");
    assert.equal(target.payload.target.service_port, null);
    const started = await posted(commands, "target.start");
    assert.deepEqual(started.payload, {
      open: true,
    });
  });
});
test("Settings reads an address and a port, and shows service progress while a button has focus", async t => {
  await browserTest(t, async (page, url) => {
    const { commands, snapshot } = await studio(page, url);
    await selectWorkspace(page, "settings");
    await page.locator('input[name="mode"][value="service"]').check();
    await page.locator('input[name="mode"][value="url"]').check();
    await page.locator('#settings-target [name="url"]').fill("localhost:3000");
    await page.locator('#settings-target [name="port"]').fill("abc");
    await page.locator('[data-mode-group="url"] [data-target-save]').click();
    // A bad port is explained and nothing is sent.
    assert.match(
      await page.locator("[data-target-status]").innerText(),
      /1 to 65535/,
    );
    assert.equal(sentAs(commands, "target.save").length, 0);
    await page.locator('#settings-target [name="port"]').fill("");
    await page.locator('[data-mode-group="url"] [data-target-save]').click();
    const saved = await posted(commands, "target.save");
    assert.equal(saved.payload.target.url, "localhost:3000");
    assert.equal(saved.payload.target.port, null);
    // Service progress reaches the screen although a button inside has focus.
    await page.locator('input[name="mode"][value="service"]').check();
    await page.locator('#settings-target [name="command"]').fill("npm run dev");
    await page.locator("[data-target-stop]").focus();
    await publish(page, {
      ...snapshot,
      revision: 30,
      target_service: {
        state: "running",
        url: "http://127.0.0.1:5173",
        port: 5173,
        pid: 42,
        candidates: [
          {
            url: "http://127.0.0.1:5173",
            port: 5173,
            status: 200,
          },
          {
            url: "http://127.0.0.1:24678",
            port: 24678,
            status: 200,
          },
        ],
      },
    });
    await page.waitForFunction(() =>
      document
        .querySelector("[data-target-status]")
        ?.textContent?.includes("Running at http://127.0.0.1:5173"),
    );
    assert.match(
      await page.locator("[data-target-status]").innerText(),
      /Also listening on 24678/,
    );
    assert.equal(await page.locator("[data-target-start]").isDisabled(), true);
    assert.equal(await page.locator("[data-target-stop]").isDisabled(), false);
  });
});
test("A maximized browser restores when the target closes and its tools fit a narrow window", async t => {
  await browserTest(t, async (page, url) => {
    await page.setViewportSize({
      width: 360,
      height: 700,
    });
    await studio(page, url);
    let closed = false;
    await scriptedPreview(page, () =>
      closed
        ? {
            status: 204,
          }
        : {
            status: 200,
            body: pixel,
            headers: {
              "Content-Type": "image/png",
              "X-Frame-Age-Ms": "5",
            },
          },
    );
    await page
      .locator('.mobile-panel-tabs [data-mobile-panel="browser"]')
      .click();
    await page.waitForSelector('.live-target-frame[data-preview="live"]');
    await page.locator("#live-target-maximize").click();
    const panel = page.locator('[data-panel-id="target"]');
    assert.equal(await panel.getAttribute("data-live-maximized"), "");
    const tools = await page.evaluate(() => {
      const bar = document.querySelector(".live-target-tools");
      return bar
        ? {
            scroll: bar.scrollWidth,
            client: bar.clientWidth,
          }
        : {
            scroll: 0,
            client: 0,
          };
    });
    assert.ok(tools.scroll <= tools.client + 1, JSON.stringify(tools));
    await page.locator("#live-target-pick").click();
    closed = true;
    // The editor learns the browser closed from the snapshot's client count.
    await page.evaluate(() =>
      document.getElementById("app")?.removeAttribute("data-target-ready"),
    );
    await page.waitForSelector('.live-target-frame[data-preview="closed"]');
    assert.equal(await panel.getAttribute("data-live-maximized"), null);
    assert.equal(
      await page.locator("#live-target-pick").getAttribute("aria-pressed"),
      "false",
    );
  });
});
test("Panels dock, collapse and float from the keyboard and announce the change", async t => {
  await browserTest(t, async (page, url) => {
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });
    await studio(page, url);
    const area = await page.locator(".workbench").boundingBox();
    const properties = page.locator('[data-panel-id="properties"]');
    await properties.locator('[data-panel-action="collapse"]').focus();
    await page.keyboard.press("Alt+Shift+ArrowLeft");
    assert.match(
      await page.locator("#status").textContent() || "",
      /docked along the left edge/,
    );
    const left = await panelBoxes(page);
    assertTiled(left, area);
    assert.ok(
      Math.abs(requiredValue(left[panelKeys.properties]).x - area.x) <= 1,
    );
    await properties.locator('[data-panel-action="collapse"]').focus();
    await page.keyboard.press("Alt+Shift+KeyC");
    assert.match(
      await page.locator("#status").textContent() || "",
      /collapsed/,
    );
    await page.keyboard.press("Alt+Shift+KeyC");
    assert.match(
      await page.locator("#status").textContent() || "",
      /expanded/,
    );
  });
});
test("Compact windows reach every panel through tabs without horizontal overflow", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    /** Check one compact width.
     * @param {number} width Viewport width.
     * @returns {Promise<void>} Completed check.
     */
    const check = async width => {
      await page.setViewportSize({
        width,
        height: 800,
      });
      await page
        .locator('.mobile-panel-tabs [data-mobile-panel="flows"]')
        .click();
      assert.equal(
        await page.locator('[data-panel-id="workspace"]').isVisible(),
        true,
      );
      const scroll = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      assert.ok(scroll <= 0, `${width}px overflows by ${scroll}`);
    };
    await check(320);
    await check(390);
    await check(600);
  });
});
test("An expired preview session says so and backs off instead of polling", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    const requests = await scriptedPreview(page, () => ({
      status: 401,
    }));
    await selectWorkspace(page, "record");
    await page.waitForSelector(
      '.live-target-frame[data-preview="unauthorized"]',
    );
    const first = requests.count();
    await page.waitForTimeout(1500);
    assert.ok(
      requests.count() - first <= 1,
      `unauthorized preview polled ${requests.count() - first} more times`,
    );
  });
});
test("A failing preview endpoint backs off exponentially and recovers", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    let healthy = false;
    const requests = await scriptedPreview(page, () =>
      healthy
        ? {
            status: 200,
            body: pixel,
            headers: {
              "Content-Type": "image/png",
              "X-Frame-Age-Ms": "5",
            },
          }
        : {
            status: 500,
          },
    );
    await selectWorkspace(page, "record");
    await page.waitForSelector('.live-target-frame[data-preview="error"]');
    const before = requests.count();
    await page.waitForTimeout(2000);
    // 250 ms polling would make ~8 requests; backoff makes at most 4.
    assert.ok(
      requests.count() - before <= 4,
      `failing preview polled ${requests.count() - before} times in 2 s`,
    );
    healthy = true;
    await page.waitForSelector('.live-target-frame[data-preview="live"]', {
      timeout: 8000,
    });
  });
});
test("Empty frames never replace the last frame and a closed browser releases it", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    let mode = "frame";
    await scriptedPreview(page, () =>
      mode === "empty"
        ? {
            status: 200,
            headers: {
              "Content-Type": "image/jpeg",
            },
          }
        : mode === "frame"
          ? {
              status: 200,
              body: pixel,
              headers: {
                "Content-Type": "image/png",
                "X-Frame-Age-Ms": "9000",
              },
            }
          : {
              status: 204,
            },
    );
    await selectWorkspace(page, "record");
    await page.waitForSelector('.live-target-frame[data-preview="stale"]');
    const image = page.locator("#live-target-image");
    assert.equal(await image.getAttribute("data-frame-age"), "9000");
    const shown = await image.getAttribute("src");
    assert.ok(shown?.startsWith("blob:"));
    mode = "empty";
    await page.waitForTimeout(700);
    assert.equal(await image.getAttribute("src"), shown);
    mode = "closed";
    await page.evaluate(() =>
      document.getElementById("app")?.removeAttribute("data-target-ready"),
    );
    await page.waitForSelector('.live-target-frame[data-preview="closed"]');
    assert.equal(await image.getAttribute("src"), null);
  });
});
for (const [name, seeded] of /** @type {[string, Record<string,string>][]} */ ([
  [
    "old unversioned keys",
    {
      "studio.panel-layout": '{"zone":"left"}',
      "studio.dock-sizes": "{}",
    },
  ],
  [
    "a partial grid layout",
    {
      "studio.dock-grid.v1": '{"version":1,"cols":[]}',
    },
  ],
  [
    "corrupt storage",
    {
      "studio.dock-grid.v1": "{not json",
      "studio.panel-groups": "][",
    },
  ],
])) {
  test(`Saved layout from ${name} falls back to the shipped layout and keeps other preferences`, async t => {
    await browserTest(t, async (page, url) => {
      await page.setViewportSize({
        width: 1440,
        height: 900,
      });
      await page.addInitScript(
        (/** @type {[Record<string,string>]} */ [entries]) => {
          if (sessionStorage.getItem("seeded")) return;
          sessionStorage.setItem("seeded", "1");
          localStorage.setItem("studio.actions", "keep me");
          for (const [key, value] of Object.entries(entries))
            localStorage.setItem(key, value);
        },
        [seeded],
      );
      await studio(page, url);
      const boxes = await panelBoxes(page);
      assert.equal(requiredValue(boxes[panelKeys.properties]).grid, "2,1,1,1");
      assert.equal(requiredValue(boxes[panelKeys.workspace]).grid, "0,0,1,3");
      assert.equal(
        await page.evaluate(() => localStorage.getItem("studio.actions")),
        "keep me",
      );
      const retired = Object.keys(seeded).filter(
        (/** @type {string} */ item) => item !== "studio.dock-grid.v1",
      );
      const left = await page.evaluate(
        (/** @type {string[]} */ keys) =>
          keys.filter(item => localStorage.getItem(item) !== null),
        retired,
      );
      assert.deepEqual(left, []);
    });
  });
}
test("Dragging a graph node never selects the flow, but a later click still does", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await selectWorkspace(page, "graph");
    /**
     * Count flow.select commands recorded so far.
     * @returns {number} Recorded flow.select commands.
     */
    const selects = () =>
      commands.filter(item => item.command === "flow.select").length;
    const title = page.locator('.flow-node-title[data-select-flow="second"]');
    const box = await title.boundingBox();
    assert.ok(box);
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    // A real drag past the threshold moves the node and does not select it.
    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.mouse.move(x + 40, y + 30, {
      steps: 5,
    });
    await page.mouse.up();
    assert.equal(selects(), 0);
    // Suppression lasts for that one click only; a later click selects.
    await page.waitForTimeout(500);
    await title.click();
    await posted(commands, "flow.select");
    assert.equal(selects(), 1);
  });
});
test("A sub-threshold graph press and a cancelled drag still allow selection", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await selectWorkspace(page, "graph");
    /**
     * Count flow.select commands recorded so far.
     * @returns {number} Recorded flow.select commands.
     */
    const selects = () =>
      commands.filter(item => item.command === "flow.select").length;
    const title = page.locator('.flow-node-title[data-select-flow="second"]');
    const box = await title.boundingBox();
    assert.ok(box);
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    // One pixel of jitter is a click, not a drag.
    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.mouse.move(x + 1, y + 1);
    await page.mouse.up();
    await posted(commands, "flow.select");
    assert.equal(selects(), 1);
    // A pen drag that the system cancels leaves no stale suppression behind.
    await title
      .evaluate((/** @type {HTMLElement} */ node) => {
        const init = {
          pointerId: 7,
          pointerType: "pen",
          button: 0,
          bubbles: true,
        };
        node.dispatchEvent(
          new PointerEvent("pointerdown", {
            ...init,
            clientX: 10,
            clientY: 10,
          }),
        );
        node.dispatchEvent(
          new PointerEvent("pointermove", {
            ...init,
            clientX: 80,
            clientY: 60,
          }),
        );
        node.dispatchEvent(
          new PointerEvent("pointercancel", {
            ...init,
            clientX: 80,
            clientY: 60,
          }),
        );
      })
      .catch(() => undefined);
    await page.locator('.flow-node-title[data-select-flow="second"]').click();
    await page.waitForFunction(
      () =>
        document.querySelector(
          '.flow-node-title[data-select-flow="second"]',
        ) !== null,
    );
    assert.ok(selects() >= 2);
  });
});
test("Timeline segment clock uses accent, subtle off segments and a stopped placeholder", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    const clock = page.locator("#timecode .sst-clock");
    assert.equal(await clock.getAttribute("aria-label"), "--:--:--.--");
    assert.equal(
      await page.locator("#timecode .sst-segment.sst-on").count(),
      8,
    );
    const colors = await page
      .locator("#timecode")
      .evaluate((/** @type {HTMLElement} */ element) => ({
        on: getComputedStyle(
          /** @type {Element} */
          (element.querySelector(".sst-on")),
        ).fill,
        off: getComputedStyle(
          /** @type {Element} */
          (element.querySelector(".sst-segment:not(.sst-on)")),
        ).fill,
        gap: getComputedStyle(
          /** @type {Element} */
          (element.querySelector(".sst-group")),
        ).columnGap,
      }));
    assert.notEqual(colors.on, colors.off);
    assert.equal(colors.gap, "16px");
    const clockBox = requiredValue(
      await page.locator("#timecode").boundingBox(),
    );
    const playBox = requiredValue(
      await page.locator("#timeline-play").boundingBox(),
    );
    assert.equal(clockBox.height, playBox.height);
    const zoom = page.locator("#timeline-zoom");
    const initialZoom = Number(await zoom.inputValue());
    await zoom.focus();
    await zoom.press("ArrowRight");
    assert.equal(Number(await zoom.inputValue()), initialZoom + 1);
    await [32, 40].reduce(
      (pending, height) =>
        pending.then(async () => {
          await page.locator("#timecode").evaluate(
            (
              /** @type {HTMLElement} */
              element,
              /** @type {number} */
              size,
            ) => {
              element.style.height = `${size}px`;
            },
            height,
          );
          await page.waitForFunction((/** @type {number} */ size) => {
            const digit = document.querySelector("#timecode .sst-digit");
            return (
              digit !== null &&
              Math.abs(digit.getBoundingClientRect().height - size) < 1
            );
          }, height);
        }),
      Promise.resolve(),
    );
    await page
      .locator("#timecode")
      .evaluate((/** @type {HTMLElement} */ element) =>
        element.style.removeProperty("height"),
      );
    await page.locator(".edit-step-row").first().click();
    assert.match(
      await clock.getAttribute("aria-label"),
      /^\d{2}:\d{2}:\d{2}\.\d{3}$/,
    );
    await page.locator("#timeline-stop").click();
    assert.equal(await clock.getAttribute("aria-label"), "--:--:--.--");
  });
});
test("Timeline playhead scrubs, keeps time through zoom, and scrolls at the edge", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    const ruler = requiredValue(
      await page.locator(".ruler-ticks").boundingBox(),
    );
    await page.mouse.click(ruler.x + 144, ruler.y + 12);
    const cursor = page.getByRole("slider", {
      name: "Timeline playhead",
    });
    assert.equal(await cursor.getAttribute("aria-valuenow"), "1500");
    assert.equal(
      await page.locator("#timecode .sst-clock").getAttribute("aria-label"),
      "00:00:01.500",
    );
    const handle = requiredValue(await cursor.boundingBox());
    await page.mouse.move(handle.x + handle.width / 2, handle.y + 12);
    await page.mouse.down();
    await page.mouse.move(handle.x + handle.width / 2 + 96, handle.y + 12);
    await page.waitForFunction(
      () =>
        document
          .querySelector(".timeline-cursor")
          ?.getAttribute("aria-valuenow") === "2500",
    );
    await page.mouse.up();
    await cursor.press("ArrowRight");
    assert.equal(await cursor.getAttribute("aria-valuenow"), "2600");
    await page.locator("#timeline-zoom").press("End");
    assert.equal(await cursor.getAttribute("aria-valuenow"), "2600");
    const timeline = requiredValue(
      await page.locator("#timeline").boundingBox(),
    );
    const dragHead = requiredValue(await cursor.boundingBox());
    await page.mouse.move(dragHead.x + dragHead.width / 2, dragHead.y + 12);
    await page.mouse.down();
    await page.mouse.move(timeline.x + timeline.width - 5, timeline.y + 12);
    await page.waitForFunction(
      () => (document.querySelector("#timeline")?.scrollLeft ?? 0) > 0,
    );
    await page.keyboard.press("Escape");
    await page.mouse.up();
    assert.equal(await cursor.getAttribute("aria-valuenow"), "2600");
    assert.equal(await page.locator("#timeline.is-scrubbing").count(), 0);
    assert.equal(await page.locator(".timeline-cursor").count(), 1);
    await page
      .locator("#timeline")
      .evaluate((/** @type {HTMLElement} */ element) => {
        element.scrollTop = 80;
        element.scrollLeft = element.scrollWidth - element.clientWidth - 100;
      });
    await page.waitForFunction(() => {
      const container = document.querySelector("#timeline");
      const grip = document.querySelector(".timeline-cursor-grip");
      return (
        container !== null &&
        grip !== null &&
        Math.abs(
          container.getBoundingClientRect().top -
            grip.getBoundingClientRect().top,
        ) < 1
      );
    });
    const beforeScroll = requiredValue(await cursor.boundingBox());
    await page
      .locator("#timeline")
      .evaluate((/** @type {HTMLElement} */ element) => {
        element.scrollLeft = element.scrollWidth - element.clientWidth;
      });
    await page.waitForFunction(() => {
      const element = document.querySelector("#timeline");
      return (
        element !== null &&
        element.scrollLeft >= element.scrollWidth - element.clientWidth - 1
      );
    });
    const afterScroll = requiredValue(await cursor.boundingBox());
    assert.ok(Math.abs(beforeScroll.x - afterScroll.x - 100) < 1);
    await page
      .locator("#timeline")
      .evaluate((/** @type {HTMLElement} */ element) => {
        element.scrollLeft = 900;
      });
    await page.waitForFunction(() => {
      const head = document.querySelector(".timeline-cursor");
      return head !== null && getComputedStyle(head).visibility === "hidden";
    });
    const extent = await page
      .locator("#timeline")
      .evaluate((/** @type {HTMLElement} */ element) => {
        const track = Array.from(element.querySelectorAll(".track")).at(-1);
        return Math.max(
          element.clientHeight,
          track instanceof HTMLElement
            ? track.offsetTop + track.offsetHeight
            : 0,
        );
      });
    await page
      .locator("#timeline")
      .evaluate((/** @type {HTMLElement} */ element) => {
        element.scrollLeft = 0;
        element.scrollTop = element.scrollHeight;
      });
    await page.waitForFunction(() => {
      const container = document.querySelector("#timeline");
      const grip = document.querySelector(".timeline-cursor-grip");
      return (
        container !== null &&
        grip !== null &&
        Math.abs(
          container.getBoundingClientRect().top -
            grip.getBoundingClientRect().top,
        ) < 1
      );
    });
    assert.ok(
      Math.abs(
        await page
          .locator("#timeline")
          .evaluate(
            (/** @type {HTMLElement} */ element) => element.scrollHeight,
          ) - extent,
      ) <= 1,
    );
  });
});
test("Running a flow with inputs asks for them and sends typed answers", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await page.getByRole("button", { name: "Run this flow" }).click();
    const dialog = page.locator(".ask-dialog");
    await dialog.waitFor();
    assert.equal(await dialog.getByText("user", { exact: true }).count(), 1);
    await dialog.locator("input").fill("Ana");
    await dialog.getByRole("button", { name: "Run flow" }).click();
    const run = await posted(commands, "run.play");
    assert.deepEqual(run.payload.flow_inputs, { user: "Ana" });
    assert.deepEqual(run.payload.inputs, {});
  });
});
test("Cancelling the input dialog does not start a run", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url);
    await page.getByRole("button", { name: "Run this flow" }).click();
    await page.locator(".ask-dialog").waitFor();
    await page.locator(".ask-dialog").getByRole("button", { name: "Cancel" }).click();
    await page.locator(".ask-dialog").waitFor({ state: "detached" });
    await delay(100);
    assert.equal(commands.some(command => command.command === "run.play"), false);
  });
});
test("Pause, Continue and Step follow the run's state and mark the next action", async t => {
  await browserTest(t, async (page, url) => {
    const { commands, snapshot } = await studio(page, url);
    /** Send the editor a new run state, as the host does.
     * @param {unknown} runControl
     * @param {string|null} runId
     * @returns {Promise<void>}
     */
    const show = async (runControl, runId) => {
      snapshot.execution_run_id = runId;
      snapshot.run_control = runControl;
      snapshot.revision += 1;
      await page.evaluate((/** @type {unknown} */ state) => {
        /** @type {any} */ (window).studioEvents?.onmessage({
          data: JSON.stringify({ protocol: 1, event: "workspace.changed", payload: state }),
        });
      }, snapshot);
    };
    const pause = page.locator("#timeline-pause");
    const step = page.locator("#timeline-step");
    await show({ state: "running", before_event_id: null }, null);
    await pause.waitFor();
    assert.equal(await pause.isDisabled(), true);
    await show({ state: "running", before_event_id: null }, "run-1");
    await page.waitForFunction(() => !document.querySelector("#timeline-pause")?.hasAttribute("disabled"));
    assert.equal(await step.isDisabled(), true);
    await pause.click();
    await posted(commands, "run.pause");
    // The host's reply to the command arrives first; only then does the
    // runner report that it is held.
    await page.waitForFunction(() =>
      document.getElementById("status")?.textContent === "Pausing before the next action");
    await show({ state: "paused", before_event_id: "save" }, "run-1");
    await page.waitForFunction(() =>
      document.querySelector("#timeline-pause")?.getAttribute("aria-label") === "Continue the run");
    assert.equal(await step.isDisabled(), false);
    const next = page.locator('[data-step="save"][data-run-next="true"]');
    await next.waitFor();
    assert.match(await next.textContent() ?? "", /Runs next/);
    await step.click();
    await posted(commands, "run.step");
    await page.waitForFunction(() =>
      document.getElementById("status")?.textContent === "Running one action, then pausing");
    await show({ state: "paused", before_event_id: "save" }, "run-1");
    await pause.click();
    await posted(commands, "run.resume");
    await page.waitForFunction(() =>
      document.getElementById("status")?.textContent === "Run continues");
    await show({ state: "running", before_event_id: null }, null);
    await page.waitForFunction(() => !document.querySelector("[data-run-next]"));
  });
});
