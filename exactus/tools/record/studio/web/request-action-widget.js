/** Request-action editor shared by REST and WebSocket flow actions. */
import { iconElement } from "./icons.js";
import { variableMentionField } from "./variable-mention-field.js";
/** @typedef {import("./variable-mention-field.js").VariableSource} VariableSource */
/** @typedef {"http"|"websocket"} RequestTransport */
const VALUE_TYPES = Object.freeze([
  ["string", "Text"],
  ["integer", "Integer"],
  ["float", "Number"],
  ["boolean", "Boolean"],
  ["json", "JSON"],
]);
/** Create an element and apply one class name.
 * @template {keyof HTMLElementTagNameMap} K
 * @param {K} tag
 * @param {string} [className]
 * @returns {HTMLElementTagNameMap[K]}
 */
const make = (tag, className = "") => {
  const node = document.createElement(tag);
  node.className = className;
  return node;
};
/** Create a labelled native select.
 * @param {string} name
 * @param {string} label
 * @param {ReadonlyArray<ReadonlyArray<string>>} choices
 * @param {string} selected
 * @returns {HTMLSelectElement}
 */
const selectControl = (name, label, choices, selected) => {
  const select = make("select");
  select.name = name;
  select.setAttribute("aria-label", label);
  for (const [value = "", text = ""] of choices) {
    const option = make("option");
    option.value = value;
    option.textContent = text;
    option.selected = value === selected;
    select.append(option);
  }
  return select;
};
/** Create a small remove button.
 * @param {string} label
 * @param {HTMLElement} owner
 * @returns {HTMLButtonElement}
 */
const removeButton = (label, owner) => {
  const button = make("button", "request-row-remove");
  button.type = "button";
  button.setAttribute("aria-label", label);
  button.title = label;
  button.append(iconElement("x"));
  button.addEventListener("click", () => owner.remove());
  return button;
};
/** Add a visible field label around a control.
 * @param {string} text
 * @param {HTMLElement} control
 * @param {string} [className]
 * @returns {HTMLLabelElement}
 */
const labelled = (text, control, className = "") => {
  const label = make("label", className);
  const caption = make("span", "request-field-label");
  caption.textContent = text;
  label.append(caption, control);
  return label;
};
/** Normalize saved request JSON without trusting its shape.
 * @param {unknown} value
 * @returns {Record<string, any>}
 */
const objectValue = value => value && typeof value === "object" && !Array.isArray(value)
  ? /** @type {Record<string, any>} */ (value)
  : {};
/** Parse a persisted request configuration.
 * @param {string|null|undefined} payload
 * @returns {Record<string, any>}
 */
const parseConfig = payload => {
  try {
    return objectValue(JSON.parse(payload || "{}"));
  } catch {
    return {};
  }
};
/** Produce one enabled key/value request row.
 * @param {"query"|"header"} kind
 * @param {number} index
 * @param {Record<string, any>} initial
 * @param {VariableSource[]} variables
 * @returns {HTMLElement}
 */
const pairRow = (kind, index, initial, variables) => {
  const {
    enabled: initialEnabled,
    key: initialKey,
    name: initialName,
    value: initialValue,
  } = initial;
  const row = make("div", "request-pair-row");
  row.setAttribute("data-request-row", kind);
  const enabled = make("input");
  enabled.type = "checkbox";
  enabled.name = `${kind}_${index}_enabled`;
  enabled.checked = initialEnabled !== false;
  enabled.setAttribute("aria-label", `Use ${kind}`);
  const key = make("input");
  key.name = `${kind}_${index}_key`;
  key.value = String(initialKey ?? initialName ?? "");
  key.placeholder = kind === "query" ? "Parameter" : "Header";
  key.setAttribute("aria-label", key.placeholder);
  const value = make("input");
  value.name = `${kind}_${index}_value`;
  value.value = String(initialValue ?? "");
  value.placeholder = "Value or @variable";
  value.setAttribute("aria-label", `${kind} value`);
  row.append(
    enabled,
    key,
    variableMentionField(value, variables),
    removeButton(`Remove ${kind}`, row),
  );
  return row;
};
/** Produce one response-to-variable mapping row.
 * @param {RequestTransport} transport
 * @param {number} index
 * @param {Record<string, any>} initial
 * @returns {HTMLElement}
 */
const captureRow = (transport, index, initial) => {
  const {
    name: initialName,
    path: initialPath,
    required: initialRequired,
    source: initialSource,
    value_type: initialValueType,
  } = initial;
  const row = make("div", "response-capture-row");
  row.setAttribute("data-request-row", "capture");
  const sources = transport === "http"
    ? [
        ["json", "JSON path"],
        ["body", "Response body"],
        ["header", "Response header"],
        ["status", "Status code"],
        ["url", "Final URL"],
      ]
    : [
        ["message_json", "Last message JSON"],
        ["message_text", "Last message text"],
        ["protocol", "Negotiated protocol"],
        ["close_code", "Close code"],
        ["messages", "All messages"],
      ];
  const source = selectControl(
    `capture_${index}_source`,
    "Response source",
    sources,
    String(initialSource ?? sources[0]?.[0] ?? ""),
  );
  const path = make("input");
  path.name = `capture_${index}_path`;
  path.value = String(initialPath ?? "");
  path.placeholder = transport === "http" ? "data.customer.id" : "payload.id";
  path.setAttribute("aria-label", "Response path or header name");
  const name = make("input");
  name.name = `capture_${index}_name`;
  name.value = String(initialName ?? "");
  name.placeholder = "Variable name";
  name.required = true;
  name.setAttribute("aria-label", "Variable name");
  const type = selectControl(
    `capture_${index}_value_type`,
    "Variable type",
    VALUE_TYPES,
    String(initialValueType ?? "string"),
  );
  const required = selectControl(
    `capture_${index}_required`,
    "Missing response value",
    [["true", "Required"], ["false", "Optional"]],
    String(initialRequired !== false),
  );
  row.append(
    source,
    path,
    name,
    type,
    required,
    removeButton("Remove response variable", row),
  );
  return row;
};
/** Produce one response validation row.
 * @param {number} index
 * @param {Record<string, any>} initial
 * @param {VariableSource[]} variables
 * @returns {HTMLElement}
 */
const validationRow = (index, initial, variables) => {
  const {
    expected: initialExpected,
    kind: initialKind,
    operator: initialOperator,
    path: initialPath,
  } = initial;
  const row = make("div", "response-check-row");
  row.setAttribute("data-request-row", "validation");
  const source = selectControl(
    `validation_${index}_kind`,
    "Response value",
    [["status", "Status"], ["json", "JSON path"], ["header", "Header"], ["body", "Body"]],
    String(initialKind ?? "status"),
  );
  const path = make("input");
  path.name = `validation_${index}_path`;
  path.value = String(initialPath ?? "");
  path.placeholder = "Path or header";
  path.setAttribute("aria-label", "JSON path or header name");
  const operator = selectControl(
    `validation_${index}_operator`,
    "Comparison",
    [["equals", "Equals"], ["contains", "Contains"], ["exists", "Exists"], ["matches", "Matches regex"]],
    String(initialOperator ?? "equals"),
  );
  const expected = make("input");
  expected.name = `validation_${index}_expected`;
  expected.value = String(initialExpected ?? "");
  expected.placeholder = "Expected or @variable";
  expected.setAttribute("aria-label", "Expected response value");
  row.append(
    source,
    path,
    operator,
    variableMentionField(expected, variables),
    removeButton("Remove response check", row),
  );
  return row;
};
/** Build an accessible request tab and its panel.
 * @param {string} id
 * @param {string} label
 * @param {HTMLElement} tabs
 * @param {HTMLElement} panels
 * @returns {HTMLElement}
 */
const tabPanel = (id, label, tabs, panels) => {
  const tab = make("button", "request-tab");
  tab.type = "button";
  tab.id = `request-tab-${id}`;
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-controls", `request-panel-${id}`);
  tab.setAttribute("aria-selected", String(tabs.children.length === 0));
  tab.textContent = label;
  const panel = make("section", "request-tab-panel");
  panel.id = `request-panel-${id}`;
  panel.setAttribute("role", "tabpanel");
  panel.setAttribute("aria-labelledby", tab.id);
  panel.hidden = tabs.children.length > 0;
  tab.addEventListener("click", () => {
    for (const item of tabs.querySelectorAll('[role="tab"]'))
      item.setAttribute("aria-selected", String(item === tab));
    for (const item of panels.querySelectorAll('[role="tabpanel"]'))
      if (item instanceof HTMLElement) item.hidden = item !== panel;
  });
  tabs.append(tab);
  panels.append(panel);
  return panel;
};
/** Add a row collection and its add action to a panel.
 * @param {HTMLElement} panel
 * @param {"query"|"header"} kind
 * @param {ReadonlyArray<Record<string, any>>} initial
 * @param {VariableSource[]} variables
 * @returns {void}
 */
const addPairs = (panel, kind, initial, variables) => {
  const rows = make("div", "request-pair-rows");
  rows.setAttribute("data-request-rows", kind);
  const add = make("button", "request-add-row");
  add.type = "button";
  add.append(iconElement("plus"), kind === "query" ? "Add parameter" : "Add header");
  add.addEventListener("click", () =>
    rows.append(pairRow(kind, rows.children.length, {}, variables)),
  );
  for (const [index, item] of initial.entries())
    rows.append(pairRow(kind, index, objectValue(item), variables));
  panel.append(rows, add);
};
/** Add response capture controls to a panel.
 * @param {HTMLElement} panel
 * @param {RequestTransport} transport
 * @param {ReadonlyArray<Record<string, any>>} initial
 * @returns {void}
 */
const addCaptures = (panel, transport, initial) => {
  const intro = make("p", "request-panel-help");
  intro.textContent = "Save response values for later actions.";
  const rows = make("div", "response-capture-rows");
  rows.setAttribute("data-request-rows", "capture");
  const add = make("button", "request-add-row");
  add.type = "button";
  add.append(iconElement("plus"), "Add response variable");
  add.addEventListener("click", () =>
    rows.append(captureRow(transport, rows.children.length, {})),
  );
  for (const [index, item] of initial.entries())
    rows.append(captureRow(transport, index, objectValue(item)));
  panel.append(intro, rows, add);
};
/** Build the request action widget.
 * @param {object} options
 * @param {RequestTransport} options.transport
 * @param {any} options.snapshot
 * @param {VariableSource[]} options.variables
 * @param {Record<string, any>} [options.event] Saved action whose request this editor starts from.
 * @returns {HTMLElement}
 */
export const requestActionWidget = options => {
  const { transport, snapshot, variables, event: initial } = options;
  const root = make("div", "request-action-widget");
  root.setAttribute("data-request-transport", transport);
  const saved = selectControl("saved_request", "Saved request", [["", "New request"]], "");
  for (const flow of snapshot?.flows ?? [])
    for (const event of flow.events ?? []) {
      const matches = transport === "http"
        ? event.kind === "http_call"
        : event.kind === "websocket_call";
      if (!matches) continue;
      const option = make("option");
      option.value = event.id;
      option.textContent = event.label;
      option.setAttribute("data-request-event", JSON.stringify(event));
      saved.append(option);
    }
  const requestLine = make("div", "request-action-line");
  if (transport === "http")
    requestLine.append(selectControl(
      "method",
      "HTTP method",
      ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"].map(value => [value, value]),
      "GET",
    ));
  const url = make("input");
  url.name = "url";
  url.required = true;
  url.placeholder = transport === "http" ? "https://api.example.test/items/@id" : "wss://stream.example.test/@channel";
  url.setAttribute("aria-label", transport === "http" ? "Request URL" : "WebSocket URL");
  requestLine.append(variableMentionField(url, variables));
  const tabs = make("div", "request-tabs");
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", transport === "http" ? "REST request settings" : "WebSocket request settings");
  const panels = make("div", "request-panels");
  if (transport === "http") {
    const queryPanel = tabPanel("params", "Params", tabs, panels);
    addPairs(queryPanel, "query", [], variables);
    const headerPanel = tabPanel("headers", "Headers", tabs, panels);
    addPairs(headerPanel, "header", [], variables);
    const bodyPanel = tabPanel("body", "Body", tabs, panels);
    const bodyFormat = selectControl(
      "body_format",
      "Body format",
      [["json", "JSON"], ["text", "Text"], ["xml", "XML"]],
      "json",
    );
    const body = make("textarea");
    body.name = "body";
    body.placeholder = '{"customer":"@Customer"}';
    body.setAttribute("aria-label", "Request body");
    bodyPanel.append(
      labelled("Format", bodyFormat, "request-compact-field"),
      variableMentionField(body, variables),
    );
    const checksPanel = tabPanel("checks", "Checks", tabs, panels);
    const validations = make("div", "rest-rows");
    validations.setAttribute("data-request-rows", "validation");
    const checksHelp = make("p", "request-panel-help");
    checksHelp.textContent = "Fail the action when the response does not match these checks.";
    checksPanel.append(checksHelp, validations);
    const addCheck = make("button", "request-add-row");
    addCheck.type = "button";
    addCheck.append(iconElement("plus"), "Add response check");
    addCheck.addEventListener("click", () =>
      validations.append(validationRow(validations.children.length, {}, variables)),
    );
    checksPanel.append(addCheck);
    const capturePanel = tabPanel("captures", "Variables", tabs, panels);
    addCaptures(capturePanel, transport, []);
  } else {
    const messagePanel = tabPanel("messages", "Messages", tabs, panels);
    const protocols = make("input");
    protocols.name = "protocols";
    protocols.placeholder = "graphql-transport-ws, chat.v2";
    protocols.setAttribute("aria-label", "WebSocket protocols");
    const message = make("textarea");
    message.name = "message";
    message.placeholder = '{"type":"subscribe","channel":"@Channel"}';
    message.setAttribute("aria-label", "Message to send after connecting");
    const receiveCount = make("input");
    receiveCount.name = "receive_count";
    receiveCount.type = "number";
    receiveCount.min = "0";
    receiveCount.value = "1";
    receiveCount.setAttribute("aria-label", "Messages to receive before closing");
    messagePanel.append(
      labelled("Protocols", variableMentionField(protocols, variables)),
      labelled("Send after connecting", variableMentionField(message, variables)),
      labelled("Receive before closing", receiveCount, "request-compact-field"),
    );
    const capturePanel = tabPanel("captures", "Variables", tabs, panels);
    addCaptures(capturePanel, transport, []);
  }
  const extra = make("div", "request-action-options");
  const timeout = make("input");
  timeout.name = "request_timeout_ms";
  timeout.type = "number";
  timeout.min = "1";
  timeout.max = "60000";
  timeout.value = "5000";
  timeout.setAttribute("aria-label", "Request timeout in milliseconds");
  extra.append(labelled("Timeout (ms)", timeout, "request-compact-field"));
  if (transport === "http") {
    const share = selectControl(
      "share_session_cookies",
      "Cookie source",
      [["true", "Browser session"], ["false", "Isolated request"]],
      "true",
    );
    extra.append(labelled("Cookies", share, "request-compact-field"));
  }
  const note = make("p", "request-action-note");
  note.textContent = transport === "http"
    ? "The full response and variables are saved at run time."
    : "Messages use the project browser and are saved.";
  root.append(labelled("Saved requests", saved), requestLine, tabs, panels, extra, note);
  /** Apply a saved action to this editor.
   * @param {Record<string, any>} event
   * @returns {void}
   */
  const load = event => {
    const { method: eventMethod, payload: eventPayload, url: eventUrl } = event;
    const config = parseConfig(String(eventPayload ?? "{}"));
    const {
      body: configBody,
      body_format: configBodyFormat,
      captures: configCaptures,
      headers: configHeaders,
      message: configMessage,
      protocols: configProtocols,
      query: configQuery,
      receive_count: configReceiveCount,
      share_session_cookies: configShareSessionCookies,
      timeout_ms: configTimeout,
      validations: configValidations,
    } = config;
    url.value = String(eventUrl ?? "");
    url.dispatchEvent(new Event("input", { bubbles: true }));
    const method = root.querySelector('[name="method"]');
    if (method instanceof HTMLSelectElement) method.value = String(eventMethod ?? "GET");
    const body = root.querySelector('[name="body"]');
    if (body instanceof HTMLTextAreaElement) {
      body.value = String(configBody?.content ?? configBody ?? "");
      body.dispatchEvent(new Event("input", { bubbles: true }));
    }
    const message = root.querySelector('[name="message"]');
    if (message instanceof HTMLTextAreaElement) {
      message.value = String(configMessage ?? "");
      message.dispatchEvent(new Event("input", { bubbles: true }));
    }
    for (const kind of ["query", "header"]) {
      const rows = root.querySelector(`[data-request-rows="${kind}"]`);
      if (!(rows instanceof HTMLElement)) continue;
      const legacyHeaders = typeof configHeaders === "string"
        ? configHeaders.split("\n").map((line, index) => {
            const [key, ...parts] = line.split(":");
            return {
              enabled: true,
              key: key?.trim() || `Header ${index + 1}`,
              value: parts.join(":").trim(),
            };
          }).filter(item => item.value || !item.key.startsWith("Header "))
        : [];
      const items = kind === "query"
        ? configQuery ?? []
        : Array.isArray(configHeaders) ? configHeaders : legacyHeaders;
      rows.replaceChildren(...items.map((/** @type {Record<string, any>} */ item, /** @type {number} */ index) =>
        pairRow(/** @type {"query"|"header"} */ (kind), index, item, variables)));
    }
    const captureRows = root.querySelector('[data-request-rows="capture"]');
    if (captureRows instanceof HTMLElement)
      captureRows.replaceChildren(...(configCaptures ?? []).map((/** @type {Record<string, any>} */ item, /** @type {number} */ index) =>
        captureRow(transport, index, item)));
    const validationRows = root.querySelector('[data-request-rows="validation"]');
    if (validationRows instanceof HTMLElement)
      validationRows.replaceChildren(...(configValidations ?? []).map((/** @type {Record<string, any>} */ item, /** @type {number} */ index) =>
        validationRow(index, item, variables)));
    for (const [name, value] of [
      ["body_format", configBodyFormat ?? configBody?.format ?? "json"],
      ["protocols", Array.isArray(configProtocols) ? configProtocols.join(", ") : configProtocols ?? ""],
      ["receive_count", configReceiveCount ?? 1],
      ["request_timeout_ms", configTimeout ?? 5000],
    ]) {
      const field = root.querySelector(`[name="${name}"]`);
      if (field instanceof HTMLInputElement || field instanceof HTMLSelectElement)
        field.value = String(value);
    }
    const share = root.querySelector('[name="share_session_cookies"]');
    if (share instanceof HTMLSelectElement)
      share.value = String(configShareSessionCookies !== false);
  };
  saved.addEventListener("change", () => {
    const stored = saved.selectedOptions[0]?.getAttribute("data-request-event");
    if (stored) load(objectValue(JSON.parse(stored)));
  });
  if (initial) load(initial);
  return root;
};
/** Read one named native control.
 * @param {HTMLFormElement} form
 * @param {string} name
 * @returns {string}
 */
const valueOf = (form, name) => {
  const control = form.elements.namedItem(name);
  return control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement || control instanceof HTMLSelectElement
    ? control.value
    : "";
};
/** Serialize request rows of one kind.
 * @param {HTMLFormElement} form
 * @param {"query"|"header"|"capture"|"validation"} kind
 * @returns {Array<Record<string, string|boolean>>}
 */
const rowValues = (form, kind) => [...form.querySelectorAll(`[data-request-row="${kind}"]`)].map(row => {
  /** @type {Record<string, string|boolean>} */
  const value = {};
  for (const field of row.querySelectorAll("input, select")) {
    if (!(field instanceof HTMLInputElement || field instanceof HTMLSelectElement)) continue;
    const name = field.name.split("_").slice(2).join("_");
    value[name] = field.type === "checkbox"
      ? field.checked
      : name === "required"
        ? field.value === "true"
        : field.value;
  }
  return value;
}).filter(item => Object.values(item).some(Boolean));
/** Serialize the complete portable request action configuration.
 * @param {HTMLFormElement} form
 * @param {RequestTransport} transport
 * @returns {Record<string, any>}
 */
export const requestActionConfig = (form, transport) => transport === "http"
  ? {
      version: 2,
      transport,
      query: rowValues(form, "query"),
      headers: rowValues(form, "header"),
      body: valueOf(form, "body"),
      body_format: valueOf(form, "body_format") || "json",
      timeout_ms: Number(valueOf(form, "request_timeout_ms") || 5000),
      share_session_cookies: valueOf(form, "share_session_cookies") === "true",
      validations: rowValues(form, "validation"),
      captures: rowValues(form, "capture"),
    }
  : {
      version: 2,
      transport,
      protocols: valueOf(form, "protocols").split(",").map(value => value.trim()).filter(Boolean),
      message: valueOf(form, "message"),
      receive_count: Number(valueOf(form, "receive_count") || 0),
      timeout_ms: Number(valueOf(form, "request_timeout_ms") || 5000),
      captures: rowValues(form, "capture"),
    };
