/** Per-run answers for "Ask Each Time" variables. */
/** Matches one Ask Each Time token and captures its label. */
const askPattern = /\{\{ask:([^{}]+)\}\}/g;
/** Labels of every Ask Each Time token an action list uses, in order.
 * @param {Array<Record<string, unknown>>} events
 * @returns {string[]}
 */
export const askLabels = events => {
  const labels = new Set();
  for (const event of events)
    for (const key of ["selector", "url", "payload", "label", "when_expression"]) {
      const value = event[key];
      if (typeof value !== "string") continue;
      for (const match of value.matchAll(askPattern)) labels.add(match[1]);
    }
  return [...labels];
};
/** Build the control that answers one flow input.
 * @param {import("./flow-inputs.js").FlowInput} input
 * @returns {HTMLInputElement|HTMLSelectElement}
 */
const inputControl = input => {
  if (input.value_type === "boolean") {
    const menu = document.createElement("select");
    for (const text of ["true", "false"]) {
      const option = document.createElement("option");
      option.value = text;
      option.textContent = text === "true" ? "True" : "False";
      menu.append(option);
    }
    menu.value = String(input.default_value ?? "true");
    return menu;
  }
  const control = document.createElement("input");
  if (input.value_type === "integer") {
    control.type = "number";
    control.step = "1";
  } else if (input.value_type === "float") {
    control.type = "number";
    control.step = "any";
  }
  control.required = input.required;
  control.value = input.default_value === undefined || input.default_value === null
    ? ""
    : String(input.default_value);
  return control;
};
/** Ask the person for each value; resolves null when they cancel.
 * @param {string[]} labels Ask Each Time labels used by the actions.
 * @param {import("./flow-inputs.js").FlowInput[]} [inputs] The flow's inputs.
 * @returns {Promise<{ask:Record<string,string>,flow:Record<string,string>}|null>}
 */
export const askInputs = (labels, inputs = []) =>
  new Promise(resolve => {
    const dialog = document.createElement("dialog");
    dialog.className = "ask-dialog";
    const form = document.createElement("form");
    form.method = "dialog";
    const title = document.createElement("strong");
    title.textContent = "Provide values for this run";
    form.append(title);
    /** Add one labelled row.
     * @param {string} text
     * @param {HTMLInputElement|HTMLSelectElement} control
     * @returns {void}
     */
    const row = (text, control) => {
      const label = document.createElement("label");
      const caption = document.createElement("span");
      caption.textContent = text;
      label.append(caption, control);
      form.append(label);
    };
    /** @type {Map<string, HTMLInputElement|HTMLSelectElement>} */
    const asked = new Map();
    /** @type {Map<string, HTMLInputElement|HTMLSelectElement>} */
    const flowControls = new Map();
    for (const input of inputs) {
      const control = inputControl(input);
      flowControls.set(input.name, control);
      row(input.name, control);
    }
    for (const label of labels) {
      const control = document.createElement("input");
      control.required = true;
      asked.set(label, control);
      row(label, control);
    }
    const actions = document.createElement("div");
    actions.className = "ask-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", () => dialog.close("cancel"));
    const run = document.createElement("button");
    run.type = "submit";
    run.textContent = "Run flow";
    actions.append(cancel, run);
    form.append(actions);
    dialog.append(form);
    dialog.addEventListener("close", () => {
      const cancelled =
        dialog.returnValue === "cancel" || dialog.returnValue === "";
      /** Read every control into an answers object.
       * @param {Map<string, HTMLInputElement|HTMLSelectElement>} controls
       * @returns {Record<string, string>}
       */
      const read = controls =>
        Object.fromEntries(
          [...controls].map(([name, control]) => [name, control.value]),
        );
      const answers = { ask: read(asked), flow: read(flowControls) };
      dialog.remove();
      resolve(cancelled ? null : answers);
    });
    form.addEventListener("submit", () => {
      dialog.returnValue = "run";
    });
    document.body.append(dialog);
    dialog.showModal();
  });
