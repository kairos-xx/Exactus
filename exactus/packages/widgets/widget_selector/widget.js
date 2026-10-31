/** The widget shell: header, semaphore, mode toggle, field, message row, footer slot. */
import { createExpressionView } from "./expression-view.js";
import { createFooter } from "./footer.js";
import { icon } from "./icons.js";
import { suggest, createSampler, ENVIRONMENT_VARIABLES } from "./suggest.js";
import { createTextView } from "./text-view.js";
import { createValidator } from "./validator.js";
/**
 * Create an element with an optional class and text.
 * @param {string} tag Tag name.
 * @param {string} [className] Class list.
 * @param {string} [text] Text content.
 * @returns {HTMLElement} The new element.
 */
const make = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
/** @typedef {import("./validator.js").ValidationResult} ValidationResult */
/**
 * Create a widget around a carrier element.
 * @returns {{element:HTMLElement, surface:HTMLElement, value:string, mode:()=>string, setMode:Function, validation:()=>ValidationResult, on:Function, setTheme:Function, focus:()=>void, destroy:()=>void, environment:readonly import("./suggest.js").VariableDef[]}} The widget API.
 */
export const createWidget = (/** @type {{carrier:HTMLTextAreaElement|HTMLInputElement, engine:any, label:string, multiple?:boolean, startAsText?:boolean, theme?:string|null, providers?:{variables?:()=>import("./suggest.js").VariableDef[], saved?:()=>{name:string,count?:number|null}[], expected?:()=>number|null}, host?:{pick?:Function, highlight?:Function, stats?:Function, profiles?:Function}, root?:Document|Element}} */ { carrier, engine, label, multiple = false, startAsText, theme = null, providers = {}, host = {}, root = document }) => {
  const Engine = engine?.constructor ?? {};
  const signatures = Engine.SIGNATURES ?? {};
  const predicateTypes = Engine.CAPABILITIES?.predicateTypes ?? {};
  const sampler = createSampler({ root });
  const widget = make("div", "ese-widget");
  if (theme) widget.setAttribute("data-theme", theme);
  const head = make("div", "ese-head");
  const title = make("div", "ese-title");
  const labelNode = make("span", "ese-label", label);
  const dot = /** @type {HTMLElement} */ (make("span", "ese-dot"));
  dot.setAttribute("role", "status");
  title.append(labelNode, dot);
  const toggle = make("div", "ese-toggle");
  const sideExpression = make("span");
  sideExpression.setAttribute("data-side", "expression");
  sideExpression.append(icon("expression"), make("span", "ese-toggle-word", "Expression"));
  sideExpression.title = "Expression";
  const sideText = make("span");
  sideText.setAttribute("data-side", "text");
  sideText.append(make("span", "ese-toggle-word", "Text"), icon("text"));
  sideText.title = "Text";
  const switcher = /** @type {HTMLButtonElement} */ (make("button", "ese-switch"));
  switcher.type = "button";
  switcher.setAttribute("role", "switch");
  switcher.setAttribute("aria-label", "Text mode");
  toggle.append(sideExpression, switcher, sideText);
  head.append(title, toggle);
  const grid = make("div", "ese-body-grid");
  const main = make("div", "ese-main");
  const field = make("div", "ese-field");
  const message = make("div", "ese-message");
  message.hidden = true;
  message.setAttribute("role", "status");
  const messageText = make("span", "ese-msg-text");
  const fix = /** @type {HTMLButtonElement} */ (make("button", "ese-link", "Fix"));
  fix.type = "button";
  const prev = /** @type {HTMLButtonElement} */ (make("button", "ese-link", "‹"));
  const next = /** @type {HTMLButtonElement} */ (make("button", "ese-link", "›"));
  prev.type = "button";
  next.type = "button";
  prev.setAttribute("aria-label", "Previous problem");
  next.setAttribute("aria-label", "Next problem");
  const counter = make("span", "ese-msg-count");
  message.append(messageText, fix, prev, counter, next);
  main.append(field, message);
  grid.append(main);
  widget.append(head, grid);
  carrier.hidden = true;
  carrier.after(widget);
  /** @type {Record<string, Function[]>} */
  const listeners = {};
  /**
   * Emit an event to registered listeners.
   * @param {string} type Event type.
   * @param {any} [detail] Event payload.
   */
  const emit = (type, detail) => {
    for (const fn of listeners[type] ?? []) fn(detail);
  };
  let mode = "expression";
  let text = carrier.value;
  /** @type {ValidationResult} */
  let last = { state: "idle", diagnostics: [], errors: 0, warnings: 0, index: 0 };
  /** @type {ReturnType<typeof createFooter>|null} */
  let footer = null;
  /**
   * List saved selector records from the provider.
   * @returns {{name:string,count?:number|null}[]} Saved selector records.
   */
  const savedList = () => providers.saved?.() ?? [];
  /**
   * List live variable records from the provider.
   * @returns {any[]} Live variable records.
   */
  const variableList = () => providers.variables?.() ?? [];
  const expression = createExpressionView({
    host: field,
    signatures,
    label,
    onChange: value =>
      emit("sync", { incoming: value, source: "expression" }),
    suggestions: ({ draft, role, scope }) =>
      suggest({
        draft,
        role,
        scope,
        signatures,
        predicateTypes,
        sampler,
        saved: savedList(),
        variables: variableList(),
        supports: selector => {
          try {
            return CSS.supports(`selector(${selector.includes(":") && !selector.startsWith(":") ? selector : `a${selector}`})`);
          } catch {
            return true;
          }
        },
      }),
  });
  const textView = createTextView({
    host: field,
    label,
    onChange: value => emit("sync", { incoming: value, source: "text" }),
  });
  /** Repaint the semaphore dot and diagnostic message row. */
  const paintStatus = () => {
    const state = text.trim() ? last.state : "idle";
    dot.setAttribute("data-state", state);
    field.setAttribute("data-state", state);
    const name =
      state === "valid" ? "Valid expression" : state === "error" ? `${last.errors} error${last.errors === 1 ? "" : "s"}` : state === "warning" ? `${last.warnings} warning${last.warnings === 1 ? "" : "s"}` : state === "checking" ? "Checking" : "Empty";
    dot.setAttribute("aria-label", name);
    dot.title = name;
    const current = last.diagnostics[last.index] ?? null;
    message.hidden = !current || state === "checking" || state === "idle";
    if (!current) return;
    message.setAttribute("data-severity", current.severity);
    messageText.textContent = `${current.line}:${current.column}  ${current.message}`;
    fix.hidden = !current.suggestion;
    fix.textContent = current.suggestion ? `Use ${current.suggestion.text}` : "Fix";
    const many = last.diagnostics.length > 1;
    prev.hidden = !many;
    next.hidden = !many;
    counter.hidden = !many;
    counter.textContent = `${last.index + 1} of ${last.diagnostics.length}`;
  };
  const validator = createValidator({
    engine,
    multiple,
    onResult: result => {
      last = result;
      paintStatus();
      expression.setDiagnostics(result.diagnostics);
      textView.setDiagnostics(result.diagnostics);
      footer?.onValidation(result);
      emit("validate", { ...result, paused: result.state === "error" });
    },
  });
  /**
   * Sync the expression text across views, carrier and validators.
   * @param {string} incoming New expression text.
   * @param {"expression"|"text"|"api"} source Change origin.
   */
  const sync = (incoming, source) => {
    text = incoming;
    if (carrier.value !== incoming) carrier.value = incoming;
    if (source === "api") {
      expression.setText(incoming);
      textView.setText(incoming);
    } else if (source === "expression") textView.setText(incoming);
    else expression.setText(incoming);
    validator.schedule(incoming);
    footer?.onText();
    if (source !== "api") {
      carrier.dispatchEvent(new Event("input", { bubbles: true }));
      carrier.dispatchEvent(new Event("change", { bubbles: true }));
    }
    emit("change", incoming);
  };
  const channel = "sync";
  listeners[channel] = [
    (/** @type {{incoming:string, source:"expression"|"text"|"api"}} */ payload) =>
      sync(payload.incoming, payload.source),
  ];
  fix.addEventListener("click", () => {
    const suggestion = last.diagnostics[last.index]?.suggestion;
    if (!suggestion) return;
    sync(text.slice(0, suggestion.offset) + suggestion.text + text.slice(suggestion.offset + suggestion.length), "api");
    validator.flush(text);
  });
  prev.addEventListener("click", () => validator.step(-1));
  next.addEventListener("click", () => validator.step(1));
  widget.addEventListener("keydown", event => {
    if (event.key === "F8") {
      event.preventDefault();
      validator.step(event.shiftKey ? -1 : 1);
    }
  });
  /**
   * Switch between expression and text modes.
   * @param {"expression"|"text"} nextMode Target mode.
   */
  const setMode = nextMode => {
    mode = nextMode;
    const isText = mode === "text";
    expression.surface.hidden = isText;
    textView.element.hidden = !isText;
    switcher.setAttribute("aria-checked", String(isText));
    sideExpression.setAttribute("data-active", String(!isText));
    sideText.setAttribute("data-active", String(isText));
    if (isText) {
      textView.setText(text);
      textView.focus();
    } else expression.setText(text);
    validator.flush(text);
    emit("mode", mode);
  };
  switcher.addEventListener("click", () => setMode(mode === "expression" ? "text" : "expression"));
  if (host.pick || host.highlight || host.stats) {
    footer = createFooter({
      host,
      getValue: () => text,
      setValue: value => sync(value, "api"),
      usesLiveVariables: () => /\{\{[^{}=]*\}\}/.test(text),
      ...(providers.expected ? { expected: providers.expected } : {}),
    });
    main.append(footer.element);
    grid.append(footer.panel);
  }
  expression.setText(text);
  textView.setText(text);
  setMode(startAsText ?? false ? "text" : "expression");
  validator.flush(text);
  return {
    element: widget,
    surface: expression.surface,
    get value() {
      return text;
    },
    set value(incoming) {
      sync(String(incoming), "api");
      validator.flush(text);
    },
    mode: () => mode,
    setMode,
    validation: () => last,
    /** @param {"change"|"validate"|"mode"} type @param {Function} fn */
    on: (type, fn) => {
      (listeners[type] ??= []).push(fn);
    },
    /** @param {string|null} tone */
    setTheme: tone => {
      if (tone) widget.setAttribute("data-theme", tone);
      else widget.removeAttribute("data-theme");
    },
    focus: () => mode === "text" ? textView.focus() : expression.focus(),
    destroy: () => {
      validator.destroy();
      widget.remove();
      carrier.hidden = false;
    },
    environment: ENVIRONMENT_VARIABLES,
  };
};
