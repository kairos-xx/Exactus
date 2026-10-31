/** Action cards: one sentence per action, tokens, pills, branch cards and in-place edits. */
import assert from "node:assert/strict";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import { modulePage, WEB } from "./module-page.mjs";
import { actionHandlers, flow, studio } from "./studio-mock.mjs";
import { browserTest } from "../../../common/browser.mjs";
/** Wait until the host has received a command, then return it.
 * @param {Array<{command:string, payload:any}>} commands Commands the host has received.
 * @param {string} name Command name.
 * @param {number} [attempts] Polls left before giving up.
 * @returns {Promise<{command:string, payload:any}>} The newest matching command.
 */
const posted = async (commands, name, attempts = 300) => {
  const found = commands.filter(item => item.command === name).at(-1);
  if (found) return found;
  assert.ok(attempts > 0, `${name} was never posted`);
  await delay(10);
  return posted(commands, name, attempts - 1);
};
test("every action kind reads as one sentence with its tokens", async t => {
  await modulePage(t, async page => {
    const sentences = await page.evaluate(async (/** @type {string} */ web) => {
      const { buildCard } = await import(`${web}/action-card.js`);
      const context = { producers: new Map() };
      /** One event rendered as its card sentence.
       * @param {Record<string, unknown>} event
       * @returns {string|null}
       */
      const say = event => buildCard({ id: "x", ...event }, context).sentence.textContent;
      return {
        click: say({ kind: "click", selector: "#save" }),
        hover: say({ kind: "hover", selector: "#menu" }),
        navigate: say({ kind: "url_change", url: "https://a.test" }),
        type: say({ kind: "input_text", selector: "#name", payload: "Ana" }),
        press: say({ kind: "keystroke", payload: "Enter" }),
        set: say({ kind: "set_variable", output_variable: "Customer", payload: '{"value":"Ana","value_type":"text"}' }),
        extract: say({ kind: "extract_value", selector: "#total", payload: '{"extract":"text"}' }),
        request: say({ kind: "http_call", url: "https://api.test", method: "POST" }),
        waitFor: say({ kind: "wait", payload: '{"condition":"element","value":"#ready"}' }),
        waitTime: say({ kind: "wait", payload: "500" }),
        shot: say({ kind: "snapshot", payload: "__screenshot__" }),
        empty: say({ kind: "set_variable", payload: "{}" }),
      };
    }, WEB);
    assert.equal(sentences.click, "Click#save");
    assert.equal(sentences.hover, "Hover over#menu");
    assert.equal(sentences.navigate, "Go tohttps://a.test");
    assert.equal(sentences.type, "TypeAnain#name");
    assert.equal(sentences.press, "PressEnter");
    assert.equal(sentences.set, "Set variableCustomertoAna");
    assert.equal(sentences.extract, "Gettextof#total");
    assert.equal(sentences.request, "POST request tohttps://api.test");
    assert.equal(sentences.waitFor, "Wait forelement#ready");
    assert.equal(sentences.waitTime, "Wait500 ms");
    assert.equal(sentences.shot, "Take screenshot");
    assert.equal(sentences.empty, "Set variableVariable NametoValue");
  });
});
test("a variable in a value becomes a pill with its source's colour and icon", async t => {
  await modulePage(t, async page => {
    const pills = await page.evaluate(async (/** @type {string} */ web) => {
      const { buildCard } = await import(`${web}/action-card.js`);
      const producers = new Map([["Customer", { icon: "tag", tone: "orange" }]]);
      const card = buildCard(
        { id: "x", kind: "input_text", selector: "#name", payload: "{{Customer}} and {{ask:City}} {{Missing.key|keys}}" },
        { producers },
      );
      return [...card.sentence.querySelectorAll(".action-pill")].map(pill => ({
        tone: pill.getAttribute("data-tone"),
        text: pill.textContent,
        icon: pill.querySelector("svg")?.getAttribute("data-icon"),
      }));
    }, WEB);
    assert.deepEqual(pills, [
      { tone: "orange", text: "Customer", icon: "tag" },
      { tone: "silver", text: "Ask: City", icon: "keyboard" },
      { tone: "silver", text: "Missing.key|keys", icon: "tag" },
    ]);
  });
});
test("request response captures become typed variable producers", async t => {
  await modulePage(t, async page => {
    const outputs = await page.evaluate(async (/** @type {string} */ web) => {
      const { producedVariables, producersOf } = await import(`${web}/action-card.js`);
      const event = {
        id: "request",
        kind: "http_call",
        output_variable: "Full response",
        payload: JSON.stringify({
          captures: [
            { name: "Customer ID", value_type: "integer" },
            { name: "Profile", value_type: "json" },
          ],
        }),
      };
      return {
        values: producedVariables(event),
        names: [...producersOf([event]).keys()],
      };
    }, WEB);
    assert.deepEqual(outputs.values, [
      { name: "Full response", type: "Any" },
      { name: "Customer ID", type: "Number" },
      { name: "Profile", type: "Dictionary" },
    ]);
    assert.deepEqual(outputs.names, ["Full response", "Customer ID", "Profile"]);
  });
});
test("a guard reads as If [value] [comparison] [value]", async t => {
  await modulePage(t, async page => {
    const text = await page.evaluate(async (/** @type {string} */ web) => {
      const { guardParts, renderSentence } = await import(`${web}/action-card.js`);
      const context = { producers: new Map() };
      return [
        renderSentence(guardParts("{{Count}} > 3"), context).textContent,
        renderSentence(guardParts("{{Name}} contains Ana"), context).textContent,
        renderSentence(guardParts("ready"), context).textContent,
      ];
    }, WEB);
    assert.deepEqual(text, ["IfCountis greater than3", "IfNamecontainsAna", "Ifready"]);
  });
});
test("cards wrap guarded actions in If and End If, and an edited token is saved", async t => {
  await browserTest(t, async (page, url) => {
    const { commands, snapshot } = await studio(page, url);
    snapshot.workspace.flows[0].events = [
      { id: "set", kind: "set_variable", label: "Set", output_variable: "Customer", payload: '{"value":"Ana","value_type":"text"}', layer: "interaction", elapsed_ms: 0 },
      { id: "go", kind: "url_change", label: "Go", url: "http://localhost/", layer: "navigation", elapsed_ms: 100, when_expression: "{{Customer}} == Ana" },
      { id: "type", kind: "input_text", label: "Type", selector: "#name", payload: "{{Customer}}", layer: "interaction", elapsed_ms: 200, when_expression: "{{Customer}} == Ana" },
      { id: "end", kind: "click", label: "Click", selector: "#save", layer: "interaction", elapsed_ms: 300 },
    ];
    snapshot.revision += 1;
    await page.evaluate((/** @type {unknown} */ state) => {
      /** @type {any} */ (window).studioEvents?.onmessage({
        data: JSON.stringify({ protocol: 1, event: "workspace.changed", payload: state }),
      });
    }, snapshot);
    await page.locator('.edit-step-row[data-step="type"]').waitFor();
    const order = await page.evaluate(() =>
      [...document.querySelectorAll(".edit-step-list > *")].map(node =>
        node.getAttribute("data-block") ?? node.getAttribute("data-step"),
      ),
    );
    assert.deepEqual(order, ["set", "if", "go", "type", "end", "end"]);
    assert.equal(
      await page.locator('.edit-step-row[data-step="go"]').getAttribute("data-nested"),
      "true",
    );
    assert.match(
      await page.locator(".edit-step-block[data-block=if]").textContent() ?? "",
      /IfCustomerisAna/,
    );
    await page.locator('.edit-step-row[data-step="set"] .action-token[data-field="value"]').click();
    const editor = page.locator(".token-editor .variable-editor");
    await editor.waitFor();
    await editor.fill("Bob");
    await editor.press("Enter");
    const update = await new Promise(resolve => {
      /** Resolve once the event.update command arrives.
       * @returns {void}
       */
      const check = () => {
        const found = commands.find(command => command.command === "event.update");
        if (found) resolve(found);
        else setTimeout(check, 20);
      };
      check();
    });
    assert.equal(/** @type {any} */ (update).payload.event_id, "set");
    assert.equal(/** @type {any} */ (update).payload.payload, '{"value":"Bob","value_type":"text"}');
    assert.equal(/** @type {any} */ (update).payload.output_variable, "Customer");
    await page.locator('.edit-step-row[data-step="type"] .action-pill').click();
    const inspector = page.locator(".token-editor .variable-inspector");
    await inspector.waitFor();
    assert.match(await inspector.textContent() ?? "", /CustomerClearRevealTypeTextRead as/);
    await inspector.locator("select").selectOption("count");
    const rewritten = await new Promise(resolve => {
      /** Resolve once the event.update command for "type" arrives.
       * @returns {void}
       */
      const check = () => {
        const found = [...commands].reverse().find(
          command => command.command === "event.update" && command.payload.event_id === "type",
        );
        if (found) resolve(found);
        else setTimeout(check, 20);
      };
      check();
    });
    assert.equal(/** @type {any} */ (rewritten).payload.payload, "{{Customer|count}}");
    assert.equal(flow.id, "flow-one");
  });
});
test("a JavaScript action opens in its row, runs its snippet and saves payload and output name", async t => {
  await browserTest(t, async (page, url) => {
    const { commands } = await studio(page, url, actionHandlers);
    await page.getByRole("button", { name: "Add action" }).click();
    await page.getByRole("button", { name: "JavaScript" }).click();
    await page.waitForSelector(".edit-step-detail-form .jr-runner");
    // The library only adds; the code editor opens inside the new action's row.
    assert.equal(await page.locator("#action-form").count(), 0);
    assert.equal(commands.filter(item => item.command === "event.add").length, 1);
    // Properties keeps only what every action shares, such as its "Run only
    // if" condition, never the action's own code.
    assert.equal(await page.locator('[data-panel-id="properties"] [name="payload"]').count(), 0);
    const code = page.locator('.edit-step-detail-form [name="payload"]');
    await code.fill("console.log('pages', Math.ceil(120 / 25));\nreturn { size: 25 };");
    await page.locator(".edit-step-detail-form .jr-run").click();
    await page.waitForFunction(() => document.querySelector(".edit-step-detail-form .jr-status")?.getAttribute("data-state") === "ok");
    assert.match(await page.locator(".edit-step-detail-form .jr-result").textContent() ?? "", /size/);
    assert.match(await page.locator(".edit-step-detail-form .jc-console").textContent() ?? "", /pages/);
    await code.fill("const user = undefined;\nreturn user.name;");
    await page.locator(".edit-step-detail-form .jr-run").click();
    await page.waitForFunction(() => document.querySelector(".edit-step-detail-form .jr-status")?.getAttribute("data-state") === "error");
    assert.match(await page.locator(".edit-step-detail-form .jr-error").textContent() ?? "", /TypeError/);
    await page.locator(".edit-step-detail-form").getByRole("button", { name: "Apply" }).click();
    const saved = await posted(commands, "event.configure");
    assert.equal(saved.payload.kind, "javascript");
    assert.equal(saved.payload.payload, "const user = undefined;\nreturn user.name;");
    assert.ok("output_variable" in saved.payload);
  });
});
