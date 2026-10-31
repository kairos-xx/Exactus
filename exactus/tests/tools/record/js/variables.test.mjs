/** Variables: picking, pills, the inspector, Ask Each Time and action forms. */
import assert from "node:assert/strict";
import test from "node:test";
import { modulePage, WEB } from "./module-page.mjs";
test("Ask Each Time labels are read from every text field of an action", async t => {
  await modulePage(t, async page => {
    const labels = await page.evaluate(async (/** @type {string} */ web) => {
      const { askLabels } = await import(`${web}/ask-inputs.js`);
      return askLabels([
        { url: "{{ask:Page URL}}" },
        { payload: "{{ask:Customer}} and {{ask:Page URL}}", label: "x" },
        { selector: "#a", payload: null },
      ]);
    }, WEB);
    assert.deepEqual(labels, ["Page URL", "Customer"]);
  });
});
test("the Ask Each Time dialog returns answers, or null when cancelled", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(async (/** @type {string} */ web) => {
      const { askInputs } = await import(`${web}/ask-inputs.js`);
      const answered = askInputs(["Name", "City"]);
      const dialog = /** @type {HTMLElement} */ (
        document.querySelector(".ask-dialog")
      );
      const inputs = /** @type {HTMLInputElement[]} */ ([
        ...dialog.querySelectorAll("input"),
      ]);
      /** @type {[HTMLInputElement, HTMLInputElement]} */
      const [name, city] = [
        /** @type {HTMLInputElement} */ (inputs[0]),
        /** @type {HTMLInputElement} */ (inputs[1]),
      ];
      name.value = "Ana";
      city.value = "Porto";
      /** @type {HTMLElement} */ (
        dialog.querySelector("button[type=submit]")
      ).click();
      const first = await answered;
      const cancelled = askInputs(["Name"]);
      /** @type {HTMLElement} */ (
        [...document.querySelectorAll(".ask-dialog button")].find(
          button => button.textContent === "Cancel",
        )
      ).click();
      return {
        first,
        cancelled: await cancelled,
        left: document.querySelectorAll(".ask-dialog").length,
      };
    }, WEB);
    assert.deepEqual(outcome.first, {
      ask: { Name: "Ana", City: "Porto" },
      flow: {},
    });
    assert.equal(outcome.cancelled, null);
    assert.equal(outcome.left, 0);
  });
});
test("the picker inserts earlier results and Ask Each Time as pills", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(async (/** @type {string} */ web) => {
      const { variableMentionField } = await import(
        `${web}/variable-mention-field.js`
      );
      const input = document.createElement("input");
      input.name = "url";
      input.type = "url";
      document.body.append(input);
      const wrapper = variableMentionField(input, ["JavaScript Result", "Customer"]);
      const editor = /** @type {HTMLElement} */ (
        wrapper.querySelector(".variable-editor")
      );
      const menu = /** @type {HTMLElement} */ (
        wrapper.querySelector(".variable-menu")
      );
      const picker = /** @type {HTMLElement} */ (
        wrapper.querySelector(".variable-picker")
      );
      /** Pick one menu entry by its text.
       * @param {string} text
       * @returns {void}
       */
      const choose = text => {
        const target = [...menu.querySelectorAll("button")].find(
          button => button.textContent === text,
        );
        target?.dispatchEvent(
          new PointerEvent("pointerdown", { bubbles: true, cancelable: true }),
        );
      };
      picker.click();
      const items = [...menu.querySelectorAll("button")].map(b => b.textContent);
      choose("JavaScript Result");
      const afterPick = input.value;
      picker.click();
      choose("Ask Each Time");
      return {
        items,
        afterPick,
        afterAsk: input.value,
        pills: [...editor.querySelectorAll(".variable-pill")].map(
          pill => pill.textContent,
        ),
        type: input.type,
      };
    }, WEB);
    assert.deepEqual(outcome.items, [
      "Ask Each Time",
      "Customer",
      "JavaScript Result",
    ]);
    assert.equal(outcome.afterPick, "{{JavaScript Result}}");
    assert.equal(outcome.afterAsk, "{{JavaScript Result}}{{ask:url}}");
    assert.deepEqual(outcome.pills, ["JavaScript Result", "Ask: url"]);
    assert.equal(outcome.type, "text");
  });
});
test("typing @ suggests variables and the inspector edits, reveals and clears a pill", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(async (/** @type {string} */ web) => {
      const { variableMentionField } = await import(
        `${web}/variable-mention-field.js`
      );
      const input = document.createElement("textarea");
      input.name = "payload";
      document.body.append(input);
      const wrapper = variableMentionField(input, ["Customer", "Order"]);
      const editor = /** @type {HTMLElement} */ (
        wrapper.querySelector(".variable-editor")
      );
      const menu = /** @type {HTMLElement} */ (
        wrapper.querySelector(".variable-menu")
      );
      editor.textContent = "id=@Cus";
      editor.dispatchEvent(new Event("input", { bubbles: true }));
      const suggestions = [...menu.querySelectorAll("button")].map(
        b => b.textContent,
      );
      editor.dispatchEvent(
        new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }),
      );
      editor.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
      );
      const chosen = input.value;
      const pill = /** @type {HTMLElement} */ (
        editor.querySelector(".variable-pill")
      );
      pill.click();
      const popover = /** @type {HTMLElement} */ (
        wrapper.querySelector(".variable-popover")
      );
      const key = /** @type {HTMLInputElement} */ (
        popover.querySelector("input")
      );
      key.value = "items[0]";
      key.dispatchEvent(new Event("input", { bubbles: true }));
      const withPath = input.value;
      key.value = "name";
      key.dispatchEvent(new Event("input", { bubbles: true }));
      const withKey = input.value;
      let revealed = "";
      document.addEventListener("variable-reveal", event => {
        revealed = /** @type {CustomEvent} */ (event).detail.name;
      });
      /** Click a popover button by its text.
       * @param {string} text
       * @returns {void}
       */
      const press = text =>
        /** @type {HTMLElement} */ (
          [...popover.querySelectorAll("button")].find(
            button => button.textContent === text,
          )
        ).click();
      press("Reveal");
      pill.click();
      press("Clear");
      editor.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
      return {
        suggestions,
        chosen,
        withPath,
        withKey,
        revealed,
        cleared: input.value,
        pills: editor.querySelectorAll(".variable-pill").length,
      };
    }, WEB);
    assert.deepEqual(outcome.suggestions, ["Customer"]);
    assert.equal(outcome.chosen, "id={{Customer}}");
    assert.equal(outcome.withPath, "id={{Customer.items[0]}}");
    assert.equal(outcome.withKey, "id={{Customer.name}}");
    assert.equal(outcome.revealed, "Customer");
    assert.equal(outcome.cleared, "id=");
    assert.equal(outcome.pills, 0);
  });
});
/** A saved REST request the form can load, as the workspace stores it. */
const SAVED_REQUEST = {
  kind: "http_call",
  id: "h",
  label: "Ping",
  method: "POST",
  url: "/p",
  payload: JSON.stringify({
    headers: "A: 1",
    body: "b",
    bindings: [{ name: "x", selector: "#a", extract: "text" }],
    validations: [{ kind: "status", operator: "equals", expected: "200" }],
  }),
};
test("the palette lists, pins and hides actions and remembers the choice", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(async (/** @type {string} */ web) => {
      const library = await import(`${web}/action-library.js`);
      const catalog = document.createElement("div");
      for (const name of ["title", "copy", "icon"]) {
        const node = document.createElement("span");
        node.id = `action-help-${name}`;
        document.body.append(node);
      }
      /** @type {string[]} */
      const chosen = [];
      library.renderActionCatalog(catalog, (/** @type {string} */ id) =>
        chosen.push(id),
      );
      const first = /** @type {HTMLElement} */ (
        catalog.querySelector("[data-add-action]")
      );
      first.dispatchEvent(new Event("pointerenter"));
      first.click();
      library.saveActionPrefs({ hidden: ["pointer"], pinned: ["javascript"] });
      library.renderActionCatalog(catalog, () => undefined);
      const groups = [...catalog.querySelectorAll(".action-group h3")].map(
        h => h.textContent,
      );
      const hasPointer = Boolean(
        catalog.querySelector('[data-add-action="pointer"]'),
      );
      const prefs = library.loadActionPrefs();
      library.saveActionPrefs({ hidden: [], pinned: [] });
      return {
        chosen: chosen.length,
        helped: document.getElementById("action-help-title")?.textContent,
        groups,
        hasPointer,
        prefs,
      };
    }, WEB);
    assert.equal(outcome.chosen, 1);
    assert.ok(outcome.helped);
    assert.equal(outcome.groups[0], "Pinned");
    assert.equal(outcome.hasPointer, false);
    assert.deepEqual(outcome.prefs, {
      hidden: ["pointer"],
      pinned: ["javascript"],
    });
  });
});
test("every palette action builds a form and turns it into a command", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(
      async (/** @type {{web:string, saved:object}} */ args) => {
        const library = await import(`${args.web}/action-library.js`);
        const snapshot = {
          selectors: [{ selector_id: "s1", name: "Card", expression: ".a" }],
          flows: [{ events: [args.saved] }],
        };
        /** @type {Record<string, {output: string|null, kind: string, payload?: string}>} */
        const commands = {};
        for (const group of library.ACTION_GROUPS) {
          for (const action of group.actions) {
            const form = document.createElement("form");
            const fields = document.createElement("div");
            form.append(fields);
            document.body.append(form);
            const definition = library.configureActionForm({
              fields,
              title: document.createElement("h2"),
              kind: action.id,
              snapshot,
              variables: ["JavaScript Result"],
              selectorTools: {},
            });
            const named = /** @type {HTMLInputElement|null} */ (
              form.querySelector('[name="output_variable"]')
            );
            const command = library.actionCommand(form, definition);
            commands[action.id] = {
              output: named ? named.value : null,
              kind: command.kind,
              ...(command.payload === undefined
                ? {}
                : { payload: command.payload }),
            };
          }
        }
        const rest = document.createElement("div");
        const restForm = document.createElement("form");
        restForm.append(rest);
        document.body.append(restForm);
        const restDefinition = library.configureActionForm({
          fields: rest,
          title: document.createElement("h2"),
          kind: "http_call",
          snapshot,
          variables: [],
          selectorTools: {},
        });
        const saved = /** @type {HTMLSelectElement} */ (
          rest.querySelector('[name="saved_request"]')
        );
        saved.value = "h";
        saved.dispatchEvent(new Event("change", { bubbles: true }));
        const rows = rest.querySelectorAll("[data-request-row]").length;
        for (const add of rest.querySelectorAll(".request-add-row"))
          /** @type {HTMLElement} */ (add).click();
        /** @type {HTMLElement|null} */ (
          rest.querySelector(".request-row-remove")
        )?.click();
        const restCommand = library.actionCommand(restForm, restDefinition);
        /** @type {unknown} */
        let failure = null;
        try {
          library.configureActionForm({
            fields: rest,
            title: document.createElement("h2"),
            kind: "nope",
            snapshot: null,
          });
        } catch (error) {
          failure = error instanceof Error ? error.message : String(error);
        }
        return { commands, rows, restCommand, failure };
      },
      { web: WEB, saved: SAVED_REQUEST },
    );
    const { commands } = outcome;
    assert.equal(commands.javascript?.output, "JavaScript Result 2");
    assert.equal(commands.javascript?.kind, "javascript");
    assert.equal(commands.pointer?.kind, "click");
    assert.equal(commands.set_variable?.kind, "set_variable");
    assert.equal(outcome.rows, 2);
    assert.match(outcome.restCommand.request_config, /"version":2/);
    assert.match(String(outcome.failure), /Unknown action/);
  });
});
test("REST and WebSocket responses publish typed flow variables", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(async (/** @type {string} */ web) => {
      const library = await import(`${web}/action-library.js`);
      /** Build one action form and return its definition.
       * @param {string} kind
       * @returns {{form:HTMLFormElement, fields:HTMLElement, definition:any}}
       */
      const build = kind => {
        const form = document.createElement("form");
        const fields = document.createElement("div");
        form.append(fields);
        document.body.append(form);
        const definition = library.configureActionForm({
          fields,
          title: document.createElement("h2"),
          kind,
          snapshot: { flows: [] },
          variables: ["Project Token"],
          selectorTools: {},
        });
        return { form, fields, definition };
      };
      const rest = build("http_call");
      /** @type {HTMLInputElement} */ (rest.fields.querySelector('[name="url"]')).value = "https://api.test/customers/@Project";
      /** @type {HTMLButtonElement} */ (rest.fields.querySelector('[aria-controls="request-panel-captures"]')).click();
      /** @type {HTMLButtonElement} */ (rest.fields.querySelector("#request-panel-captures .request-add-row")).click();
      /** @type {HTMLSelectElement} */ (rest.fields.querySelector('[name="capture_0_source"]')).value = "json";
      /** @type {HTMLInputElement} */ (rest.fields.querySelector('[name="capture_0_path"]')).value = "data.customer.id";
      /** @type {HTMLInputElement} */ (rest.fields.querySelector('[name="capture_0_name"]')).value = "Customer ID";
      /** @type {HTMLSelectElement} */ (rest.fields.querySelector('[name="capture_0_value_type"]')).value = "integer";
      const restCommand = library.actionCommand(rest.form, rest.definition);
      const socket = build("websocket_call");
      /** @type {HTMLInputElement} */ (socket.fields.querySelector('[name="url"]')).value = "wss://stream.test/@Channel";
      /** @type {HTMLTextAreaElement} */ (socket.fields.querySelector('[name="message"]')).value = '{"type":"subscribe"}';
      /** @type {HTMLButtonElement} */ (socket.fields.querySelector('[aria-controls="request-panel-captures"]')).click();
      /** @type {HTMLButtonElement} */ (socket.fields.querySelector("#request-panel-captures .request-add-row")).click();
      /** @type {HTMLSelectElement} */ (socket.fields.querySelector('[name="capture_0_source"]')).value = "message_json";
      /** @type {HTMLInputElement} */ (socket.fields.querySelector('[name="capture_0_path"]')).value = "payload.total";
      /** @type {HTMLInputElement} */ (socket.fields.querySelector('[name="capture_0_name"]')).value = "Live Total";
      /** @type {HTMLSelectElement} */ (socket.fields.querySelector('[name="capture_0_value_type"]')).value = "float";
      const socketCommand = library.actionCommand(socket.form, socket.definition);
      return {
        rest: JSON.parse(restCommand.request_config),
        socket: JSON.parse(socketCommand.request_config),
        socketKind: socketCommand.kind,
      };
    }, WEB);
    assert.deepEqual(outcome.rest.captures, [{
      source: "json",
      path: "data.customer.id",
      name: "Customer ID",
      value_type: "integer",
      required: true,
    }]);
    assert.deepEqual(outcome.socket.captures, [{
      source: "message_json",
      path: "payload.total",
      name: "Live Total",
      value_type: "float",
      required: true,
    }]);
    assert.equal(outcome.socketKind, "websocket_call");
  });
});
test("the run dialog asks for typed flow inputs with their defaults", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(async (/** @type {string} */ web) => {
      const { askInputs } = await import(`${web}/ask-inputs.js`);
      const answered = askInputs([], [
        { name: "Customer", value_type: "string", required: true },
        { name: "Count", value_type: "integer", required: true },
        { name: "Express", value_type: "boolean", required: false, default_value: "false" },
        { name: "Mode", value_type: "string", required: false, default_value: "fast" },
      ]);
      const dialog = /** @type {HTMLElement} */ (document.querySelector(".ask-dialog"));
      const controls = [...dialog.querySelectorAll("input, select")];
      const types = controls.map(control =>
        control instanceof HTMLInputElement ? control.type : control.tagName.toLowerCase());
      const [customer, count] = /** @type {HTMLInputElement[]} */ (controls);
      /** @type {HTMLInputElement} */ (customer).value = "Ana";
      /** @type {HTMLInputElement} */ (count).value = "3";
      /** @type {HTMLElement} */ (dialog.querySelector("button[type=submit]")).click();
      return { types, answers: await answered };
    }, WEB);
    assert.deepEqual(outcome.types, ["text", "number", "select", "text"]);
    assert.deepEqual(outcome.answers, {
      ask: {},
      flow: { Customer: "Ana", Count: "3", Express: "false", Mode: "fast" },
    });
  });
});
test("the flow settings list edits, adds and removes flow inputs", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(async (/** @type {string} */ web) => {
      const { flowInputsField } = await import(`${web}/flow-inputs.js`);
      const field = flowInputsField([
        { name: "Customer", value_type: "string", required: true },
        { name: "Mode", value_type: "string", required: false, default_value: "fast" },
      ]);
      document.body.append(field.element);
      /** @type {HTMLButtonElement} */ (field.element.querySelector(".flow-inputs-add")).click();
      const [first, second, third] = /** @type {[HTMLElement, HTMLElement, HTMLElement]} */ (
        /** @type {unknown} */ ([...field.element.querySelectorAll(".flow-input")])
      );
      /** @type {HTMLInputElement} */ (third.querySelector('[data-part="name"]')).value = " Count ";
      /** @type {HTMLSelectElement} */ (third.querySelector('[data-part="type"]')).value = "integer";
      const required = /** @type {HTMLInputElement} */ (second.querySelector('[data-part="required"]'));
      const fallback = /** @type {HTMLInputElement} */ (second.querySelector('[data-part="default"]'));
      const before = fallback.disabled;
      required.click();
      const after = { disabled: fallback.disabled, value: fallback.value };
      /** @type {HTMLButtonElement} */ (first.querySelector("button")).click();
      return { before, after, read: field.read() };
    }, WEB);
    assert.equal(outcome.before, false);
    assert.deepEqual(outcome.after, { disabled: true, value: "" });
    assert.deepEqual(outcome.read.map((/** @type {{name:string}} */ item) => item.name), ["Mode", "Count"]);
    assert.equal(outcome.read[1].value_type, "integer");
  });
});
test("the inspector shows a variable's type and reads it as keys, values or a count", async t => {
  await modulePage(t, async page => {
    const outcome = await page.evaluate(async (/** @type {string} */ web) => {
      const { variableMentionField } = await import(`${web}/variable-mention-field.js`);
      const input = document.createElement("textarea");
      input.name = "payload";
      input.value = "{{Order}} {{Total}}";
      document.body.append(input);
      const wrapper = variableMentionField(input, [
        { name: "Order", type: "Dictionary" },
        { name: "Total", type: "Number" },
      ]);
      const [order, total] = /** @type {[HTMLElement, HTMLElement]} */ (
        /** @type {unknown} */ ([...wrapper.querySelectorAll(".variable-pill")])
      );
      const popover = /** @type {HTMLElement} */ (wrapper.querySelector(".variable-popover"));
      order.click();
      const orderType = popover.querySelector(".variable-inspector-type")?.textContent;
      const orderChoices = [...popover.querySelectorAll("option")].map(option => option.value);
      const how = /** @type {HTMLSelectElement} */ (popover.querySelector("select"));
      how.value = "keys";
      how.dispatchEvent(new Event("change", { bubbles: true }));
      const asKeys = input.value;
      total.click();
      const totalType = popover.querySelector(".variable-inspector-type")?.textContent;
      const totalChoices = [...popover.querySelectorAll("option")].map(option => option.value);
      return { orderType, orderChoices, asKeys, totalType, totalChoices };
    }, WEB);
    assert.equal(outcome.orderType, "Dictionary");
    assert.deepEqual(outcome.orderChoices, ["", "keys", "values", "count"]);
    assert.equal(outcome.asKeys, "{{Order|keys}} {{Total}}");
    assert.equal(outcome.totalType, "Number");
    assert.deepEqual(outcome.totalChoices, [""]);
  });
});
