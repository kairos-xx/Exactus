/** Action catalog and schema-driven insertion form for Flow Studio. */
import { iconElement } from "./icons.js";
import { mountPointerStudio } from "../../../../packages/actions/action_pointer/index.js";
import { javascriptActionWidget } from "./javascript-action-widget.js";
import { requestActionConfig, requestActionWidget } from "./request-action-widget.js";
import { variableMentionField, variableName } from "./variable-mention-field.js";
export const ACTION_DRAG_TYPE = "application/x-exactus-action";
/**
 * @typedef {object} ActionField
 * @property {string} name Form field name sent with the command.
 * @property {string} label Visible label.
 * @property {string} type Control kind: text, url, number, select, code, ...
 * @property {string} [value] Initial value.
 * @property {string} [placeholder] Hint shown while the field is empty.
 * @property {boolean} [required] False for optional fields.
 * @property {string} [step] Numeric step.
 * @property {Array<[string, string]>} [choices] Options of a select.
 * @property {boolean} [runnable] False for code that runs in the live page, so it cannot be previewed.
 */
/**
 * @typedef {object} ActionDefinition
 * @property {string} id Action identifier.
 * @property {string} label Name shown in the palette.
 * @property {string} icon Icon name.
 * @property {ActionField[]} fields Parameters of the action.
 * @property {string} [command] Command kind when it differs from `id`.
 * @property {{gesture?: string, extract?: string, [field: string]: string|undefined}} [fixed] Fields sent with every insert.
 * @property {string} [produces] Name of the value the action produces.
 * @property {number} [family] Palette group index, for colour.
 */
/**
 * @typedef {object} ActionGroup
 * @property {string} name Group heading.
 * @property {number} [family] Palette group index, kept when siblings hide.
 * @property {ReadonlyArray<ActionDefinition>} actions Actions in the group.
 */
/**
 * @typedef {object} SavedAction
 * @property {string} kind Event kind.
 * @property {string|null} [selector] Inline selector expression.
 * @property {string|null} [selector_id] Saved selector the action uses.
 * @property {string|null} [url] Address the action opens or requests.
 * @property {string|null} [payload] Encoded settings.
 * @property {string|null} [output_variable] Variable that receives the result.
 * @property {string|null} [position_action] Pointer operation of a positioned action.
 * @property {number|null} [x] Horizontal coordinate.
 * @property {number|null} [y] Vertical coordinate.
 */
/**
 * @typedef {object} ActionSource
 * @property {Record<string, string>} [values] Field values of an action already in the flow.
 * @property {SavedAction} [event] That action, for controls that restore a whole document.
 */
/** Describe one action parameter.
 * @param {string} name
 * @param {string} label
 * @param {string} [type]
 * @param {Partial<ActionField>} [options]
 * @returns {ActionField}
 */
const field = (name, label, type = "text", options = {}) => ({
  name,
  label,
  type,
  ...options,
});
/** @type {ReadonlyArray<ActionGroup>} */
export const ACTION_GROUPS = Object.freeze([
  {
    name: "Pointer",
    actions: [
      { id: "pointer", label: "Pointer & touch", icon: "pointer", fields: [field("pointer", "Interaction", "pointer")] },
    ],
  },
  {
    name: "Forms & keyboard",
    actions: [
      { id: "input_text", label: "Fill text", icon: "keyboard", fields: [field("selector", "Input", "selector"), field("payload", "Text", "textarea")] },
      { id: "select_option", label: "Select option", icon: "list-check", fields: [field("selector", "Select", "selector"), field("options", "Values", "textarea", { placeholder: "One value per line" })] },
      { id: "check", label: "Check", icon: "check", fields: [field("selector", "Checkbox", "selector")] },
      { id: "uncheck", label: "Uncheck", icon: "minus", fields: [field("selector", "Checkbox", "selector")] },
      { id: "keystroke", label: "Press key", icon: "keyboard", fields: [field("payload", "Key or chord", "text", { placeholder: "Control+Shift+K" })] },
    ],
  },
  {
    name: "Browser",
    actions: [
      { id: "url_change", label: "Navigate", icon: "world", fields: [field("url", "Page URL", "url", { placeholder: "https://example.test/path" })] },
      { id: "viewport_rotate", command: "viewport", label: "Rotate viewport", icon: "device-mobile", fixed: { viewport_action: "rotate" }, fields: [] },
      { id: "viewport_resize", command: "viewport", label: "Resize viewport", icon: "fit-all", fixed: { viewport_action: "resize" }, fields: [field("width", "Width", "number", { value: "1440" }), field("height", "Height", "number", { value: "900" })] },
      { id: "javascript", label: "JavaScript", icon: "code", produces: "result", fields: [field("payload", "Sandbox code", "code", { value: "__EXACTUS_FLOW__.log('step');" }), field("output_variable", "Save result as", "text", { required: false, placeholder: "result" })] },
      { id: "http_call", label: "REST request", icon: "world", produces: "response", fields: [field("request", "Request", "rest"), field("output_variable", "Save response as", "text", { required: false, placeholder: "response" })] },
      { id: "websocket_call", label: "WebSocket session", icon: "arrows-join", produces: "session", fields: [field("request", "Session", "websocket"), field("output_variable", "Save session as", "text", { required: false, placeholder: "session" })] },
    ],
  },
  {
    name: "Variables & data",
    actions: [
      {
        id: "set_variable",
        label: "Set variable",
        icon: "tag",
        produces: "value",
        fields: [
          field("output_variable", "Variable name", "text", { placeholder: "customerId" }),
          field("value_type", "Type", "select", { choices: [["text", "Text"], ["integer", "Integer"], ["float", "Float"], ["boolean", "Boolean"], ["json", "JSON"]] }),
          field("variable_value", "Value or {{variable}}", "textarea"),
        ],
      },
      {
        id: "extract_text",
        command: "extract_value",
        label: "Get element text",
        icon: "file",
        produces: "text",
        fixed: { extract: "text" },
        fields: [field("selector", "Element", "selector"), field("output_variable", "Save text as", "text", { placeholder: "labelText" })],
      },
      {
        id: "extract_value",
        command: "extract_value",
        label: "Get input value",
        icon: "keyboard",
        produces: "value",
        fixed: { extract: "value" },
        fields: [field("selector", "Input", "selector"), field("output_variable", "Save value as", "text", { placeholder: "inputValue" })],
      },
      {
        id: "extract_checked",
        command: "extract_value",
        label: "Get checked state",
        icon: "check",
        produces: "boolean",
        fixed: { extract: "checked" },
        fields: [field("selector", "Checkbox", "selector"), field("output_variable", "Save state as", "text", { placeholder: "isChecked" })],
      },
      {
        id: "extract_number",
        command: "extract_value",
        label: "Get input number",
        icon: "list-numbers",
        produces: "number",
        fixed: { extract: "float" },
        fields: [field("selector", "Number input", "selector"), field("output_variable", "Save number as", "text", { placeholder: "total" })],
      },
      {
        id: "count_matches",
        command: "extract_value",
        label: "Count matches",
        icon: "list-check",
        produces: "integer",
        fixed: { extract: "count" },
        fields: [field("selector", "Elements", "selector"), field("output_variable", "Save count as", "text", { placeholder: "itemCount" })],
      },
      {
        id: "extract_attribute",
        command: "extract_value",
        label: "Get attribute",
        icon: "tag",
        produces: "text",
        fixed: { extract: "attribute" },
        fields: [field("selector", "Element", "selector"), field("attribute", "Attribute name", "text", { placeholder: "href" }), field("output_variable", "Save attribute as", "text", { placeholder: "targetUrl" })],
      },
    ],
  },
  {
    name: "Wait for",
    actions: [
      { id: "wait_element", command: "wait", label: "Element", icon: "eye", fixed: { wait_for: "element" }, fields: [field("payload", "Selector", "text", { placeholder: "#ready" }), field("timeout_ms", "Timeout (ms)", "number", { value: "5000" })] },
      { id: "wait_text", command: "wait", label: "Text", icon: "file", fixed: { wait_for: "text" }, fields: [field("payload", "Text", "text", { placeholder: "Saved" }), field("timeout_ms", "Timeout (ms)", "number", { value: "5000" })] },
      { id: "wait_url", command: "wait", label: "URL", icon: "world", fixed: { wait_for: "url" }, fields: [field("payload", "URL or pattern", "text", { placeholder: "**/complete" }), field("timeout_ms", "Timeout (ms)", "number", { value: "5000" })] },
      { id: "wait_expression", command: "wait", label: "Expression", icon: "code", fixed: { wait_for: "expression" }, fields: [field("payload", "JavaScript expression", "code", { value: "() => document.readyState === 'complete'", runnable: false }), field("timeout_ms", "Timeout (ms)", "number", { value: "5000" })] },
    ],
  },
  {
    name: "Logic",
    actions: [
      { id: "if", label: "If", icon: "arrows-join", fields: [field("payload", "Condition", "code", { value: "__EXACTUS_FLOW__.vars.allowed === true" })] },
    ],
  },
  {
    name: "Evidence",
    actions: [
      { id: "snapshot", label: "Element snapshot", icon: "fit-selection", fields: [field("selector", "Target", "selector")] },
      { id: "screenshot", label: "Page screenshot", icon: "camera", fields: [] },
    ],
  },
]);
/** @type {Map<string, ActionDefinition>} */
const definitions = new Map(
  ACTION_GROUPS.flatMap((group, family) =>
    group.actions.map(
      action =>
        /** @type {[string, ActionDefinition]} */ ([action.id, { ...action, family }]),
    ),
  ),
);
const ACTION_HELP = Object.freeze({
  pointer: "Configure any mouse, pointer-position, or touch interaction in one action.",
  click: "Click the first element matched by a saved or extended selector.",
  double_click: "Double-click a matched element.",
  right_click: "Open the target element's context menu.",
  hover: "Move the pointer over a matched element without clicking.",
  drag: "Drag from one selector to another selector.",
  scroll: "Scroll a page or container to exact coordinates.",
  position_pointer: "Use exact viewport coordinates when no selector is available.",
  touch_tap: "Send a touch tap to a matched element.",
  touch_long_press: "Press and hold a matched element for a chosen duration.",
  touch_swipe: "Swipe from a matched element in a chosen direction.",
  touch_pinch: "Pinch or zoom around a matched element.",
  input_text: "Replace the value of a text field. Variables are accepted.",
  select_option: "Choose one or more values from a select control.",
  check: "Set a checkbox or switch to checked.",
  uncheck: "Clear a checkbox or switch.",
  keystroke: "Send a key or modifier chord to the active page.",
  url_change: "Navigate the browser to a URL, including variable tokens.",
  viewport_rotate: "Swap the current viewport width and height.",
  viewport_resize: "Set an exact browser viewport size.",
  javascript: "Run sandboxed JavaScript and optionally publish its return value.",
  http_call: "Send a saved REST request, validate its response, and publish it.",
  websocket_call: "Connect in the project browser, exchange frames, and publish the session.",
  set_variable: "Create a typed value for later actions in this flow.",
  extract_text: "Read visible element text into a named variable.",
  extract_value: "Read an input's current value into a named variable.",
  extract_checked: "Read a checkbox state as true or false.",
  extract_number: "Read a numeric input as a number, not text.",
  count_matches: "Count every element matched by an extended selector.",
  extract_attribute: "Read an attribute such as href or aria-label.",
  wait_element: "Continue when an element becomes visible.",
  wait_text: "Continue when visible text appears.",
  wait_url: "Continue when the browser reaches a URL or pattern.",
  wait_expression: "Continue when a JavaScript condition becomes true.",
  if: "Run the selected action only when this condition is true.",
  snapshot: "Capture structured evidence for one matched element.",
  screenshot: "Capture the current browser page as visual evidence.",
});
/**
 * @typedef {object} PayloadDocument
 * @property {string} [gesture] Touch gesture name.
 * @property {string} [extract] What an extraction reads.
 * @property {string} [condition] What a wait waits for.
 * @property {string} [action] Viewport operation.
 * @property {string} [attribute] Attribute an extraction reads.
 * @property {unknown} [value] Value a variable or wait holds.
 * @property {string} [value_type] Type of a variable.
 * @property {unknown} [x] Horizontal position.
 * @property {unknown} [y] Vertical position.
 * @property {unknown} [width] Viewport width.
 * @property {unknown} [height] Viewport height.
 * @property {unknown} [timeout_ms] Wait timeout.
 * @property {unknown} [direction] Swipe direction.
 * @property {unknown} [distance] Swipe distance.
 * @property {unknown} [duration_ms] Gesture duration.
 * @property {unknown} [scale] Pinch scale.
 */
/** Decode an action payload that holds a JSON object.
 * @param {string|null|undefined} payload
 * @returns {PayloadDocument}
 */
const payloadDocument = payload => {
  try {
    const document = JSON.parse(payload ?? "");
    return document !== null && typeof document === "object" && !Array.isArray(document) ? document : {};
  } catch {
    return {};
  }
};
/** @type {ReadonlySet<string>} */
const POINTER_KINDS = Object.freeze(new Set([
  "click", "double_click", "right_click", "hover", "drag", "scroll", "position_pointer", "gesture",
]));
/** Palette ids behind the kinds that several actions share.
 * @type {Record<string, (document: PayloadDocument) => string>}
 */
const SHARED_KINDS = Object.freeze({
  gesture: document => `touch_${document.gesture}`,
  extract_value: document => ({
    text: "extract_text",
    value: "extract_value",
    checked: "extract_checked",
    float: "extract_number",
    count: "count_matches",
    attribute: "extract_attribute",
  })[String(document.extract)] ?? "",
  wait: document => `wait_${document.condition}`,
  viewport: document => `viewport_${document.action}`,
});
/** The palette action an action in the flow was made from.
 * @param {{kind: string, payload?: string|null}} event
 * @returns {ActionDefinition|undefined} Undefined for recorded steps the palette cannot edit.
 */
export const definitionForEvent = event => {
  if (event.kind === "note") return event.payload === "__screenshot__" ? definitions.get("screenshot") : undefined;
  if (POINTER_KINDS.has(event.kind)) return definitions.get("pointer");
  const shared = SHARED_KINDS[event.kind];
  return definitions.get(shared ? shared(payloadDocument(event.payload)) : event.kind);
};
/** Fields a flow card already lets you edit inside its single line. */
const SENTENCE_FIELDS = Object.freeze(["selector", "url", "payload", "output_variable"]);
/** Whether an action needs room of its own inside its flow row.
 * An action whose every parameter is a token in its sentence, such as a click
 * or a navigation, is configured in the single line. One with a code editor, a
 * request or several other parameters expands in place instead.
 * @param {ActionDefinition} definition
 * @returns {boolean}
 */
export const editsInRow = definition =>
  definition.fields.some(
    item => ["code", "pointer", "rest", "websocket"].includes(item.type ?? "") || !SENTENCE_FIELDS.includes(item.name),
  );
/** Field values of an action already in the flow, the inverse of {@link actionCommand}.
 * @param {SavedAction} event
 * @param {ActionDefinition} definition
 * @returns {Record<string, string>}
 */
export const actionValues = (event, definition) => {
  const document = payloadDocument(event.payload);
  /** Read a value as text, falling back when it is null or undefined. */
  const text = (/** @type {unknown} */ value, /** @type {string} */ fallback = "") => String(value ?? fallback);
  /** @type {Record<string, string>} */
  const values = {
    selector: text(event.selector),
    selector_id: text(event.selector_id),
    url: text(event.url),
    output_variable: text(event.output_variable),
    payload: text(event.payload),
  };
  /** @type {Record<string, () => Record<string, string>>} */
  const byAction = {
    scroll: () => ({ scroll_x: text(document.x, "0"), scroll_y: text(document.y, "0") }),
    select_option: () => {
      const list = JSON.parse(text(event.payload, "[]"));
      return { options: Array.isArray(list) ? list.join("\n") : "" };
    },
    drag: () => ({ destination: text(event.payload) }),
    set_variable: () => ({ variable_value: text(document.value), value_type: text(document.value_type, "text") }),
    extract_attribute: () => ({ attribute: text(document.attribute) }),
    viewport_resize: () => ({ width: text(document.width, "1440"), height: text(document.height, "900") }),
    position_pointer: () => ({ position_action: text(event.position_action, "hover"), x: text(event.x, "0"), y: text(event.y, "0") }),
    pointer: () => ({
      pointer_action: event.kind === "gesture" ? `touch_${text(document.gesture, "tap")}` : event.kind,
      destination: event.kind === "drag" ? text(event.payload) : "",
      scroll_x: text(document.x, "0"),
      scroll_y: text(document.y, "600"),
      position_action: text(event.position_action, "hover"),
      x: text(event.x, "0"),
      y: text(event.y, "0"),
      direction: text(document.direction, "up"),
      distance: text(document.distance, "240"),
      duration_ms: text(document.duration_ms, event.kind === "gesture" && document.gesture === "long_press" ? "650" : "350"),
      scale: text(document.scale, "1.5"),
    }),
  };
  /** @type {Record<string, string>} */
  const gesture = definition.command === "gesture"
    ? {
        direction: text(document.direction),
        distance: text(document.distance, "240"),
        duration_ms: text(document.duration_ms, "350"),
        scale: text(document.scale, "1.5"),
      }
    : {};
  /** @type {Record<string, string>} */
  const wait = definition.command === "wait"
    ? { payload: text(document.value), timeout_ms: text(document.timeout_ms, "5000") }
    : {};
  return { ...values, ...gesture, ...wait, ...byAction[definition.id]?.() };
};
/** Pick a variable name that no earlier action already uses.
 * @param {string} label
 * @param {string[]} taken
 * @returns {string}
 */
const uniqueVariable = (label, taken) => {
  const base = `${label} Result`;
  let name = base;
  for (let count = 2; taken.includes(name); count += 1) name = `${base} ${count}`;
  return name;
};
/**
 * @typedef {(apply: (element: {selector: string, matches?: number, alternatives?: Array<{strategy: string, selector: string, matches: number}>}) => void) => void} PickHandler
 */
/**
 * @typedef {(expression: string, done: (result: {count?: number}) => void) => void} HighlightHandler
 */
/**
 * @typedef {object} SelectorTools
 * @property {PickHandler|undefined} [onPick]
 * @property {HighlightHandler|undefined} [onHighlight]
 * @property {((carrier:HTMLInputElement|HTMLTextAreaElement, label:string)=>unknown)|undefined} [mount] Mounts the expression widget on a control.
 */
/** Wrap a control in a label.
 * @param {string} labelText
 * @param {HTMLElement} node
 * @returns {HTMLLabelElement}
 */
const labelled = (labelText, node) => {
  const label = document.createElement("label");
  const text = document.createElement("span");
  text.textContent = labelText;
  label.append(text, node);
  return label;
};
/** Build the selector bookmark chooser plus its expression editor.
 * @param {ActionField} spec
 * @param {any} snapshot
 * @param {import("./variable-mention-field.js").VariableSource[]} variables
 * @param {SelectorTools} selectorTools
 * @param {string} [bookmark] Saved selector the action already uses.
 * @returns {HTMLElement}
 */
const selectorControl = (spec, snapshot, variables, selectorTools, bookmark = "") => {
  const group = document.createElement("div");
  group.className = "action-selector-control";
  const saved = document.createElement("select");
  saved.name = "selector_id";
  saved.setAttribute("aria-label", `${spec.label}: selector bookmark`);
  const custom = document.createElement("option");
  custom.value = "";
  custom.textContent = "New expression";
  saved.append(custom);
  for (const item of /** @type {Array<{selector_id:string,name:string}>} */ (
    snapshot?.selectors ?? []
  )) {
    const option = document.createElement("option");
    option.value = item.selector_id;
    option.textContent = item.name;
    saved.append(option);
  }
  const input = document.createElement("input");
  input.name = spec.name;
  input.required = true;
  input.placeholder = spec.placeholder ?? "#submit or ext=[visible=true]";
  input.value = spec.value ?? "";
  saved.addEventListener("change", () => {
    input.hidden = Boolean(saved.value);
    input.required = !saved.value;
  });
  const mount = selectorTools.mount;
  const editor = variableMentionField(input, variables);
  saved.addEventListener("change", () => {
    const hidden = Boolean(saved.value);
    for (const part of group.querySelectorAll(
      ".variable-field, .selector-expression-field, .selector-live-tools, .ese-widget",
    ))
      if (part instanceof HTMLElement) part.hidden = hidden;
  });
  const bookmarkLabel = document.createElement("span");
  bookmarkLabel.className = "selector-bookmark-label";
  bookmarkLabel.textContent = "Selector bookmark";
  group.append(bookmarkLabel, saved, editor);
  mount?.(input, spec.label);
  if (bookmark) {
    saved.value = bookmark;
    saved.dispatchEvent(new Event("change"));
  }
  return group;
};
/** Build the sandbox code editor and its runtime-value workbench.
 * @param {ActionField} spec
 * @param {import("./variable-mention-field.js").VariableSource[]} variables
 * @param {any} snapshot
 * @returns {HTMLElement}
 */
const codeControl = (spec, variables, snapshot) =>
  javascriptActionWidget({
    source: spec.value ?? "",
    sourceLabel: spec.label,
    variables,
    snapshot,
    outputName: null,
    runnable: spec.runnable !== false,
  });
/** Read one saved field value.
 * @param {ActionSource} source
 * @param {string} name
 * @returns {string|undefined}
 */
const savedValue = (source, name) => source.values?.[name];
/** Build the control for one action parameter.
 * @param {ActionField} spec
 * @param {any} snapshot Workspace snapshot, for selector bookmarks.
 * @param {import("./variable-mention-field.js").VariableSource[]} [variables] Variables produced above this action.
 * @param {SelectorTools} [selectorTools]
 * @param {ActionSource} [source] Saved action the controls start from.
 * @returns {HTMLElement}
 */
const control = (spec, snapshot, variables = [], selectorTools = {}, source = {}) => {
  if (spec.type === "select") {
    const select = document.createElement("select");
    select.name = spec.name;
    for (const [value, label] of spec.choices ?? []) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.append(option);
    }
    if (spec.value !== undefined) select.value = spec.value;
    return select;
  }
  if (spec.type === "selector")
    return selectorControl(spec, snapshot, variables, selectorTools, savedValue(source, "selector_id") ?? "");
  if (spec.type === "code") return codeControl(spec, variables, snapshot);
  if (spec.type === "rest")
    return requestActionWidget({ transport: "http", snapshot, variables, ...(source.event ? { event: source.event } : {}) });
  if (spec.type === "websocket")
    return requestActionWidget({ transport: "websocket", snapshot, variables, ...(source.event ? { event: source.event } : {}) });
  if (spec.type === "pointer") {
    const host = document.createElement("div");
    mountPointerStudio(host, source.values ?? {}, {
      selectorField: (label, seed) =>
        selectorControl(
          { name: "selector", label, type: "selector", value: seed.selector ?? "" },
          snapshot,
          variables,
          selectorTools,
          savedValue(source, "selector_id") ?? ""
        ),
    });
    return host;
  }
  const node = spec.type === "textarea"
    ? document.createElement("textarea")
    : document.createElement("input");
  node.name = spec.name;
  node.required = spec.required !== false;
  if (node instanceof HTMLInputElement) {
    node.type = spec.type;
    if (spec.step) node.step = spec.step;
  }
  node.value = spec.value ?? "";
  node.placeholder = spec.placeholder ?? "";
  node.setAttribute("aria-label", spec.label);
  const mentionable = ["text", "url", "textarea"].includes(spec.type)
    && spec.name !== "output_variable";
  return mentionable ? variableMentionField(node, variables) : node;
};
const PREFS_KEY = "exactus.studio.actionPrefs";
export const ACTION_PREFS_EVENT = "studio:action-prefs";
/** Every action id the palette can show.
 * @returns {Set<string>}
 */
const knownActionIds = () =>
  new Set(ACTION_GROUPS.flatMap(group => group.actions.map(action => action.id)));
/** Per-viewer palette preferences: hidden actions and pinned favourites.
 * Stored in the browser only, because they describe how one person likes the
 * palette arranged, not anything the flow itself depends on.
 * @returns {{hidden:string[], pinned:string[]}}
 */
export const loadActionPrefs = () => {
  const known = knownActionIds();
  /** Keep only known action ids.
   * @param {unknown} value
   * @returns {string[]}
   */
  const clean = value =>
    Array.isArray(value)
      ? [...new Set(value.filter(id => typeof id === "string" && known.has(id)))]
      : [];
  try {
    const stored = JSON.parse(window.localStorage.getItem(PREFS_KEY) ?? "{}");
    return { hidden: clean(stored?.hidden), pinned: clean(stored?.pinned) };
  } catch {
    return { hidden: [], pinned: [] };
  }
};
/** Persist palette preferences and tell open surfaces to redraw.
 * @param {{hidden:string[], pinned:string[]}} prefs
 * @returns {void}
 */
export const saveActionPrefs = prefs => {
  try {
    window.localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    // Storage can be blocked; the change still applies for this session below.
  }
  window.dispatchEvent(new CustomEvent(ACTION_PREFS_EVENT, { detail: prefs }));
};
/** The groups the palette shows after applying preferences.
 * @param {{hidden:string[], pinned:string[]}} prefs
 * @returns {ActionGroup[]}
 */
const visibleGroups = prefs => {
  const hidden = new Set(prefs.hidden);
  const shown = ACTION_GROUPS.map((group, family) => ({
    name: group.name,
    family,
    actions: group.actions.filter(action => !hidden.has(action.id)),
  })).filter(group => group.actions.length > 0);
  const pinned = prefs.pinned
    .filter(id => !hidden.has(id))
    .map(id => definitions.get(id))
    .filter(
      /** @param {ActionDefinition|undefined} action
       * @returns {action is ActionDefinition} */
      action => action !== undefined,
    );
  return pinned.length > 0 ? [{ name: "Pinned", actions: pinned }, ...shown] : shown;
};
/** Draw the action palette.
 * @param {HTMLElement} container Element that receives the groups.
 * @param {(id: string) => void} choose Called with the picked action id.
 * @returns {void}
 */
export const renderActionCatalog = (container, choose) => {
  container.replaceChildren();
  const groups = visibleGroups(loadActionPrefs());
  if (groups.length === 0) {
    const empty = document.createElement("p");
    empty.className = "action-catalog-empty";
    empty.textContent = "Every action is hidden. Show some again in Settings → Actions.";
    container.append(empty);
    return;
  }
  const helpTitle = document.querySelector("#action-help-title");
  const helpCopy = document.querySelector("#action-help-copy");
  const helpIcon = document.querySelector("#action-help-icon");
  /** Show an action's help in the palette footer.
   * @param {ActionDefinition} action
   * @returns {void}
   */
  const explain = action => {
    if (helpTitle) helpTitle.textContent = action.label;
    if (helpCopy)
      helpCopy.textContent =
        /** @type {Record<string,string>} */ (ACTION_HELP)[action.id] ??
        "Add this action to the flow.";
    if (helpIcon) helpIcon.replaceChildren(iconElement(action.icon));
  };
  for (const group of groups) {
    const section = document.createElement("section");
    section.className = "action-group";
    // Family keeps its colour when a sibling group is hidden; Pinned has none.
    if (group.family !== undefined)
      section.setAttribute("data-family", String(group.family));
    const heading = document.createElement("h3");
    heading.textContent = group.name;
    const grid = document.createElement("div");
    grid.className = "action-grid";
    for (const action of group.actions) {
      const button = document.createElement("button");
      button.type = "button";
      button.draggable = true;
      button.setAttribute("data-add-action", action.id);
      button.setAttribute("aria-describedby", "action-help-copy");
      button.title = `Select ${action.label} to add it, then set it up in Properties, or drag it into the Flow panel`;
      const icon = document.createElement("span");
      icon.className = "action-icon";
      icon.append(iconElement(action.icon));
      const label = document.createElement("span");
      label.className = "action-label";
      label.textContent = action.label;
      const result = document.createElement("small");
      result.className = "action-result";
      result.textContent = action.produces ? `→ ${action.produces}` : "";
      button.append(icon, label, result);
      button.addEventListener("click", () => choose(action.id));
      button.addEventListener("dragstart", event => {
        if (!event.dataTransfer) return;
        event.dataTransfer.effectAllowed = "copy";
        event.dataTransfer.setData(ACTION_DRAG_TYPE, action.id);
        event.dataTransfer.setData("text/plain", action.label);
        button.closest(".action-library")?.classList.add("is-action-dragging");
      });
      button.addEventListener("dragend", () =>
        button.closest(".action-library")?.classList.remove("is-action-dragging"),
      );
      button.addEventListener("pointerenter", () => explain(action));
      button.addEventListener("focus", () => explain(action));
      grid.append(button);
    }
    section.append(heading, grid);
    container.append(section);
  }
};
/** Fill a form with the controls of one action.
 * @param {object} options
 * @param {HTMLElement} options.fields Container receiving the controls.
 * @param {string} options.kind Action id.
 * @param {any} options.snapshot Workspace snapshot.
 * @param {import("./variable-mention-field.js").VariableSource[]} [options.variables] Variables produced above.
 * @param {SelectorTools} [options.selectorTools]
 * @param {SavedAction} [options.event] An action already in the flow, shown for editing.
 * @returns {ActionDefinition}
 * @throws {Error} When the action id is not in the palette.
 */
export const configureActionForm = options => {
  const { fields, kind, snapshot, variables = [], selectorTools = {}, event } = options;
  const definition = definitions.get(kind);
  if (!definition) throw new Error(`Unknown action: ${kind}`);
  const editing = event !== undefined;
  const source = /** @type {ActionSource} */ (editing ? { values: actionValues(event, definition), event } : {});
  const workbench = document.createElement("article");
  workbench.className = "action-workbench";
  workbench.setAttribute("data-action-kind", definition.id);
  workbench.setAttribute("data-family", String(definition.family ?? 0));
  if (editing) workbench.setAttribute("data-mode", "edit");
  const header = document.createElement("header");
  header.className = "action-workbench-header";
  const identity = document.createElement("div");
  identity.className = "action-workbench-identity";
  const icon = document.createElement("span");
  icon.className = "action-workbench-icon";
  icon.append(iconElement(definition.icon));
  const copy = document.createElement("div");
  const heading = document.createElement("strong");
  heading.textContent = definition.label;
  const help = document.createElement("small");
  help.textContent =
    /** @type {Record<string,string>} */ (ACTION_HELP)[definition.id]
    ?? "Configure this action.";
  copy.append(heading, help);
  identity.append(icon, copy);
  const contract = document.createElement("span");
  contract.className = "action-workbench-contract";
  contract.textContent = definition.produces ? `Produces ${definition.produces}` : "Action only";
  header.append(identity, contract);
  const body = document.createElement("div");
  body.className = "action-workbench-body";
  if (definition.id === "javascript") {
    const code = definition.fields.find(item => item.name === "payload");
    if (!code) throw new Error("JavaScript action is missing its source field.");
    body.append(javascriptActionWidget({
      source: savedValue(source, "payload") ?? code.value ?? "",
      sourceLabel: code.label,
      variables,
      snapshot,
      outputName: editing
        ? savedValue(source, "output_variable") ?? ""
        : uniqueVariable(definition.label, variables.map(variableName)),
    }));
  } else {
    for (const base of definition.fields) {
      // Every produced value is a named variable, defaulting to the action's
      // label and made unique among earlier outputs.
      const saved = savedValue(source, base.name);
      const named = base.name === "output_variable"
        ? {
          ...base,
          label: "Variable name",
          required: false,
          value: saved ?? (base.value || uniqueVariable(definition.label, variables.map(variableName))),
          placeholder: definition.label,
        }
        : base;
      const spec = saved !== undefined && base.name !== "output_variable"
        ? { ...named, value: saved }
        : named;
      const node = control(spec, snapshot, variables, selectorTools, source);
      if (["code", "pointer", "rest", "websocket"].includes(spec.type)) {
        const section = document.createElement("section");
        section.className = "action-workbench-composite-field";
        const caption = document.createElement("h3");
        caption.textContent = spec.label;
        section.append(caption, node);
        body.append(section);
      } else
        body.append(labelled(spec.label, node));
    }
  }
  if (editing) {
    // The action is already in the flow: Properties names it and owns its timing.
    workbench.append(body);
    fields.replaceChildren(workbench);
    return definition;
  }
  const gap = control(field("gap_ms", "Timeline gap before step (ms)", "number", { value: "500" }), snapshot, []);
  const timing = document.createElement("details");
  timing.className = "action-workbench-timing";
  const timingTitle = document.createElement("summary");
  timingTitle.textContent = "Timing";
  timing.append(timingTitle, labelled("Timeline gap before step (ms)", gap));
  body.append(timing);
  const footer = document.createElement("footer");
  footer.className = "action-workbench-footer";
  const available = document.createElement("span");
  available.append(iconElement("tag"), `${variables.length} earlier values available`);
  const ordering = document.createElement("span");
  ordering.append(iconElement("timeline"), "Dependencies keep this action after its producers");
  footer.append(available, ordering);
  workbench.append(header, body, footer);
  fields.replaceChildren(workbench);
  return definition;
};
/** What the condition says before the user has written one. */
export const DEFAULT_GUARD = "__EXACTUS_FLOW__.vars.allowed === true";
/** Read one form control's text value.
 * @param {HTMLFormElement} form
 * @param {string} name
 * @returns {string}
 */
const valueOf = (form, name) => {
  const item = form.elements.namedItem(name);
  return item instanceof HTMLInputElement || item instanceof HTMLTextAreaElement || item instanceof HTMLSelectElement
    ? item.value
    : "";
};
/**
 * @typedef {object} ActionCommand
 * @property {string} kind Command kind.
 * @property {string} [payload] Encoded action payload.
 * @property {string} [request_config] Encoded REST client configuration.
 */
/** Build the editor command payload for a submitted action form.
 * @param {HTMLFormElement} form
 * @param {ActionDefinition} definition
 * @returns {ActionCommand & Record<string, string|undefined>}
 */
export const actionCommand = (form, definition) => {
  /** @type {ActionCommand & Record<string, string|undefined>} */
  const data = { kind: definition.command ?? definition.id, ...(definition.fixed ?? {}) };
  for (const item of new FormData(form).entries()) data[item[0]] = String(item[1]);
  if (definition.id === "pointer") {
    const action = valueOf(form, "pointer_action");
    const touch = action.startsWith("touch_");
    data.kind = touch ? "gesture" : action;
    Reflect.deleteProperty(data, "pointer_action");
    if (touch)
      data.payload = JSON.stringify({
        gesture: action.slice("touch_".length),
        direction: valueOf(form, "direction"),
        distance: Number(valueOf(form, "distance") || 0),
        duration_ms: Number(valueOf(form, "duration_ms") || 0),
        scale: Number(valueOf(form, "scale") || 0),
      });
    else if (action === "scroll")
      data.payload = JSON.stringify({ x: Number(valueOf(form, "scroll_x")), y: Number(valueOf(form, "scroll_y")) });
    else if (action === "drag") data.payload = valueOf(form, "destination");
  }
  else if (definition.command === "gesture")
    data.payload = JSON.stringify({
      gesture: definition.fixed?.gesture,
      direction: valueOf(form, "direction"),
      distance: Number(valueOf(form, "distance") || 0),
      duration_ms: Number(valueOf(form, "duration_ms") || 0),
      scale: Number(valueOf(form, "scale") || 0),
    });
   else if (definition.id === "scroll")
    data.payload = JSON.stringify({ x: Number(valueOf(form, "scroll_x")), y: Number(valueOf(form, "scroll_y")) });
   else if (definition.id === "select_option")
    data.payload = JSON.stringify(valueOf(form, "options").split("\n").map(item => item.trim()).filter(Boolean));
   else if (definition.id === "drag") data.payload = valueOf(form, "destination");
  else if (definition.id === "set_variable")
    data.payload = JSON.stringify({
      value: valueOf(form, "variable_value"),
      value_type: valueOf(form, "value_type"),
    });
   else if (definition.command === "extract_value")
    data.payload = JSON.stringify({
      extract: definition.fixed?.extract,
      attribute: valueOf(form, "attribute"),
    });
  else if (definition.id === "http_call") {
    const request = requestActionConfig(form, "http");
    const { share_session_cookies: shareSessionCookies } = request;
    data.request_config = JSON.stringify(request);
    data.payload = valueOf(form, "body");
    Object.assign(data, { share_session_cookies: String(shareSessionCookies === true) });
  }
  else if (definition.id === "websocket_call") {
    data.request_config = JSON.stringify(requestActionConfig(form, "websocket"));
    data.payload = valueOf(form, "message");
  }
  return data;
};
/** The command that adds an action with every setting at its default.
 * @returns {ActionCommand & Record<string, string|undefined>}
 */
export const defaultActionCommand = (/** @type {{kind:string, snapshot:any, variables:import("./variable-mention-field.js").VariableSource[]}} */ { kind, snapshot, variables }) => {
  const form = document.createElement("form");
  const fields = document.createElement("div");
  form.append(fields);
  const definition = configureActionForm({ fields, kind, snapshot, variables });
  return actionCommand(form, definition);
};
