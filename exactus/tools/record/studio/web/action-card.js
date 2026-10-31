/** Shortcuts-style action cards: an icon tile and one sentence with tokens.
 *
 * A card reads like "Set variable [Customer] to [Ana]". Each bracketed part is
 * a token: an empty one shows its placeholder, a filled one shows its value,
 * and a `{{variable}}` inside a value becomes a pill that carries the colour
 * of the action that produces it. Tokens that can be edited in place carry
 * `data-field`; the editor opens a small editor on click.
 */
import { iconElement } from "./icons.js";
/**
 * @typedef {{id:string,kind:string,label?:string,selector?:string|null,url?:string|null,payload?:string|null,method?:string|null,output_variable?:string|null,when_expression?:string|null}} CardEvent
 * @typedef {{icon:string,tone:string}} Producer
 * @typedef {{producers:Map<string,Producer>}} CardContext
 * @typedef {{kind:"text",text:string}} TextPart
 * @typedef {{kind:"token",field:string|null,value:string,placeholder:string,editor:"text"|"code"|null,json?:string}} TokenPart
 * @typedef {TextPart|TokenPart} SentencePart
 * @typedef {{tone:string,icon:string,parts:SentencePart[],code:string|null}} CardSpec
 */
/** A phrase of the sentence.
 * @param {string} text
 * @returns {TextPart}
 */
const say = text => ({ kind: "text", text });
/** A token of the sentence.
 * @param {string|null} field Event field an edit writes, or null when read-only.
 * @param {string|null|undefined} value Current value.
 * @param {string} placeholder Shown while the value is empty.
 * @param {Partial<TokenPart>} [options]
 * @returns {TokenPart}
 */
const token = (field, value, placeholder, options = {}) => ({
  kind: "token",
  field,
  value: value ?? "",
  placeholder,
  editor: field ? "text" : null,
  ...options,
});
/** Read a JSON object payload, or an empty one.
 * @param {string|null|undefined} payload
 * @returns {Record<string, unknown>}
 */
const structured = payload => {
  if (!payload?.startsWith("{")) return {};
  try {
    const parsed = JSON.parse(payload);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
};
/** Text of one member of a structured payload.
 * @param {Record<string, unknown>} data
 * @param {string} key
 * @returns {string}
 */
const member = (data, key) => {
  const value = Reflect.get(data, key);
  return value === undefined || value === null ? "" : String(value);
};
/** The values a menu action selects, as one phrase.
 * @param {string|null|undefined} payload JSON list of values.
 * @returns {string}
 */
const options = payload => {
  try {
    const parsed = JSON.parse(payload ?? "[]");
    return Array.isArray(parsed) ? parsed.join(", ") : String(payload ?? "");
  } catch {
    return String(payload ?? "");
  }
};
/** The colour family of each action kind. */
const TONES = Object.freeze({
  click: "blue",
  double_click: "blue",
  right_click: "blue",
  hover: "blue",
  check: "blue",
  uncheck: "blue",
  drag: "blue",
  scroll: "blue",
  gesture: "blue",
  position_pointer: "blue",
  url_change: "blue",
  viewport: "blue",
  input_text: "yellow",
  keystroke: "yellow",
  select_option: "yellow",
  wait: "silver",
  javascript: "silver",
  snapshot: "silver",
  http_call: "green",
  websocket_call: "green",
  extract_value: "orange",
  set_variable: "orange",
});
/** The icon of each action kind. */
const ICONS = Object.freeze({
  click: "mouse",
  double_click: "mouse",
  right_click: "mouse",
  hover: "eye",
  check: "check",
  uncheck: "minus",
  drag: "arrows-horizontal",
  scroll: "arrow-down",
  gesture: "pointer",
  position_pointer: "crosshair",
  url_change: "world",
  viewport: "device-mobile",
  input_text: "keyboard",
  keystroke: "keyboard",
  select_option: "list-check",
  wait: "clock",
  javascript: "code",
  snapshot: "camera",
  http_call: "download",
  websocket_call: "arrows-join",
  extract_value: "search",
  set_variable: "tag",
});
/** What a wait condition is called in a sentence. */
const WAIT_LABELS = Object.freeze({
  element: "element",
  text: "text",
  url: "address",
  expression: "condition",
});
/** Verb and target of the actions that act on one element.
 * @type {Readonly<Record<string, string>>}
 */
const ON_ELEMENT = Object.freeze({
  click: "Click",
  double_click: "Double click",
  right_click: "Right click",
  hover: "Hover over",
  check: "Check",
  uncheck: "Uncheck",
  scroll: "Scroll",
});
/** Describe an action as a sentence.
 * @param {CardEvent} event
 * @returns {CardSpec}
 */
export const cardSpec = event => {
  const kind = event.kind;
  const tone = Reflect.get(TONES, kind) ?? "silver";
  const icon = event.payload === "__screenshot__"
    ? "camera"
    : (Reflect.get(ICONS, kind) ?? "mouse");
  const data = structured(event.payload);
  /** @type {SentencePart[]} */
  let parts;
  /** @type {string|null} */
  let code = null;
  if (event.payload === "__screenshot__") parts = [say("Take screenshot")];
  else if (kind in ON_ELEMENT)
    parts = [say(Reflect.get(ON_ELEMENT, kind)), token("selector", event.selector, "Element")];
  else if (kind === "url_change")
    parts = [say("Go to"), token("url", event.url, "URL")];
  else if (kind === "input_text")
    parts = [
      say("Type"),
      token("payload", event.payload, "Text"),
      say("in"),
      token("selector", event.selector, "Field"),
    ];
  else if (kind === "keystroke")
    parts = [say("Press"), token("payload", event.payload, "Key")];
  else if (kind === "select_option")
    parts = [
      say("Select"),
      token(null, options(event.payload), "Option"),
      say("in"),
      token("selector", event.selector, "Menu"),
    ];
  else if (kind === "drag")
    parts = [
      say("Drag"),
      token("selector", event.selector, "Element"),
      say("to"),
      token("payload", event.payload, "Destination"),
    ];
  else if (kind === "set_variable")
    parts = [
      say("Set variable"),
      token("output_variable", event.output_variable, "Variable Name"),
      say("to"),
      token("value", member(data, "value"), "Value", { json: "value" }),
    ];
  else if (kind === "extract_value")
    parts = [
      say("Get"),
      token(null, member(data, "extract") || "text", "Text"),
      say("of"),
      token("selector", event.selector, "Element"),
    ];
  else if (kind === "http_call")
    parts = [
      say(`${event.method || "GET"} request to`),
      token("url", event.url, "URL"),
    ];
  else if (kind === "websocket_call")
    parts = [say("Open WebSocket at"), token("url", event.url, "WebSocket URL")];
  else if (kind === "wait") {
    const condition = member(data, "condition");
    parts = condition
      ? [
        say("Wait for"),
        token(null, Reflect.get(WAIT_LABELS, condition) ?? condition, "Condition"),
        token(null, member(data, "value"), "Value"),
      ]
      : [say("Wait"), token(null, `${event.payload || "0"} ms`, "Time")];
  } else if (kind === "javascript") {
    parts = [say("Run JavaScript")];
    code = event.payload ?? "";
  } else if (kind === "viewport")
    parts = [
      say("Set viewport"),
      token(null, member(data, "action") === "rotate"
        ? "Rotate"
        : `${member(data, "width")} × ${member(data, "height")}`, "Size"),
    ];
  else
    parts = [
      say(event.label || kind),
      token(null, event.selector || event.url || "", "Details"),
    ];
  return { tone, icon, parts, code };
};
/** Split a value into text and `{{variable}}` pills.
 * @param {HTMLElement} target Token element to fill.
 * @param {string} value
 * @param {CardContext} context
 * @returns {void}
 */
const fill = (target, value, context) => {
  let cursor = 0;
  for (const match of value.matchAll(/\{\{([^{}]+)\}\}/g)) {
    if (match.index > cursor)
      target.append(document.createTextNode(value.slice(cursor, match.index)));
    const name = match[1] ?? "";
    const asked = name.startsWith("ask:");
    const base = /^([^.[|]+)/.exec(name)?.[1] ?? name;
    const producer = context.producers.get(base);
    const pill = document.createElement("span");
    pill.className = "action-pill";
    pill.setAttribute("data-variable", name);
    pill.setAttribute("data-tone", asked ? "silver" : (producer?.tone ?? "silver"));
    pill.append(
      iconElement(asked ? "keyboard" : (producer?.icon ?? "tag")),
      asked ? `Ask: ${name.slice(4)}` : name,
    );
    target.append(pill);
    cursor = match.index + match[0].length;
  }
  if (cursor < value.length)
    target.append(document.createTextNode(value.slice(cursor)));
};
/** Draw a sentence: bold phrases and tokens.
 * @param {SentencePart[]} parts
 * @param {CardContext} context
 * @returns {HTMLElement}
 */
export const renderSentence = (parts, context) => {
  const sentence = document.createElement("span");
  sentence.className = "action-sentence";
  for (const part of parts) {
    if (part.kind === "text") {
      const phrase = document.createElement("strong");
      phrase.textContent = part.text;
      sentence.append(phrase);
      continue;
    }
    const chip = document.createElement("span");
    chip.className = "action-token";
    if (part.field) {
      chip.setAttribute("data-field", part.field);
      if (part.json) chip.setAttribute("data-json", part.json);
      chip.setAttribute("data-editor", part.editor ?? "text");
    }
    if (part.value) fill(chip, part.value, context);
    else {
      chip.textContent = part.placeholder;
      chip.setAttribute("data-empty", "true");
    }
    sentence.append(chip);
  }
  return sentence;
};
/** How each comparison reads in a sentence. */
const OPERATORS = Object.freeze({
  "==": "is",
  "!=": "is not",
  ">=": "is at least",
  "<=": "is at most",
  ">": "is greater than",
  "<": "is less than",
  contains: "contains",
  matches: "matches",
});
/** Describe a guard as "If [value] [is greater than] [value]".
 * @param {string} expression Condition that must hold.
 * @returns {SentencePart[]}
 */
export const guardParts = expression => {
  const split = /^(.*?)\s+(==|!=|>=|<=|>|<|contains|matches)\s+(.*)$/.exec(expression);
  if (!split) return [say("If"), token(null, expression, "Condition")];
  return [
    say("If"),
    token(null, split[1], "Value"),
    token(null, Reflect.get(OPERATORS, split[2] ?? "") ?? split[2], "Comparison"),
    token(null, split[3], "Value"),
  ];
};
/** Build the visible parts of one card.
 * @param {CardEvent} event
 * @param {CardContext} context
 * @returns {{tile:HTMLElement,sentence:HTMLElement,code:HTMLElement|null,tone:string}}
 */
export const buildCard = (event, context) => {
  const spec = cardSpec(event);
  const tile = document.createElement("span");
  tile.className = "action-tile";
  tile.setAttribute("data-tone", spec.tone);
  tile.append(iconElement(spec.icon));
  /** @type {HTMLElement|null} */
  let code = null;
  if (spec.code !== null) {
    code = document.createElement("span");
    code.className = "action-code";
    code.setAttribute("data-field", "payload");
    code.setAttribute("data-editor", "code");
    code.textContent = spec.code || "Write the script to run";
    if (!spec.code) code.setAttribute("data-empty", "true");
  }
  return { tile, sentence: renderSentence(spec.parts, context), code, tone: spec.tone };
};
/** Every variable an action publishes, including response mappings.
 * @param {CardEvent} event
 * @returns {Array<{name:string,type:string}>}
 */
export const producedVariables = event => {
  /** @type {Array<{name:string,type:string}>} */
  const result = [];
  if (typeof event.output_variable === "string" && event.output_variable.length > 0)
    result.push({ name: event.output_variable, type: "Any" });
  if (!["http_call", "websocket_call"].includes(event.kind)) return result;
  const captures = Reflect.get(structured(event.payload), "captures");
  if (!Array.isArray(captures)) return result;
  for (const capture of captures) {
    if (!capture || typeof capture !== "object") continue;
    const name = Reflect.get(capture, "name");
    if (typeof name !== "string" || name.length === 0) continue;
    const valueType = String(Reflect.get(capture, "value_type") ?? "string");
    const type = {
      boolean: "Boolean",
      integer: "Number",
      float: "Number",
      json: "Dictionary",
    }[valueType] ?? "Text";
    result.push({ name, type });
  }
  return result;
};
/** What each action can offer to the actions after it.
 * @param {CardEvent[]} events
 * @returns {Map<string, Producer>}
 */
export const producersOf = events => {
  /** @type {Map<string, Producer>} */
  const producers = new Map();
  for (const event of events) {
    const spec = cardSpec(event);
    for (const output of producedVariables(event))
      producers.set(output.name, { icon: spec.icon, tone: spec.tone });
  }
  return producers;
};
