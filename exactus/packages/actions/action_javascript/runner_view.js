/** The runner widget: edit a snippet, run it in a sandbox, read the result and console. */
import { Describer } from "../../widgets/widget_console/describe.js";
import { mountConsole } from "../../widgets/widget_console/console_view.js";
import { icon } from "../../widgets/widget_console/icons.js";
import { renderValue } from "../../widgets/widget_console/inspect.js";
import { createEditor } from "./editor.js";
import { WorkerExecutor } from "./executor.js";
import { createVariablesMenu } from "./variables_menu.js";
/** @typedef {import("./executor.js").RunResult} RunResult */
/** @typedef {import("./executor.js").Execute} Execute */
/** @typedef {import("./variables_menu.js").Variable} Variable */
/** @typedef {import("../../widgets/widget_console/describe.js").Descriptor} Descriptor */
/** @typedef {"idle"|"running"|"ok"|"error"|"timeout"|"cancelled"} RunState */
/**
 * @typedef {object} RunnerOptions
 * @property {string} [source] Initial snippet when the carrier is empty.
 * @property {string} [label] Title text.
 * @property {string|null} [theme] `light`, `dark`, or null to inherit.
 * @property {number} [timeoutMs] Default time limit per run.
 * @property {"auto"|"playback"|"expression"|"statements"} [mode] How a snippet becomes a function; `playback` matches Studio runs.
 * @property {Variable[]} [variables] Values offered to `exactus.vars`.
 * @property {Record<string, unknown>} [context] Sections `project`, `context`, `flow`, `run`, `action` and `inputs` of `exactus`.
 * @property {string} [outputName] Name the return value is saved under; shows the field when set.
 * @property {boolean} [clearOnRun] Clear the console before each run.
 * @property {boolean} [readOnly] Whether editing is disabled.
 * @property {boolean} [runnable] False for an editor-only widget that never runs the snippet.
 * @property {string} [name] Form field name for the visible editor, so it submits with its form.
 * @property {boolean} [required] Whether the visible editor is a required form field.
 * @property {Execute} [execute] Replacement for the default worker executor.
 */
const TIMEOUTS = /** @type {const} */ ([[1000, "1 s"], [5000, "5 s"], [30000, "30 s"], [60000, "60 s"]]);
const STATE_TEXT = /** @type {Record<RunState, string>} */ ({
  idle: "Ready",
  running: "Running",
  ok: "Done",
  error: "Failed",
  timeout: "Timed out",
  cancelled: "Stopped",
});
/**
 * Create an element with an optional class and text.
 * @template {keyof HTMLElementTagNameMap} K
 * @param {K} tag Tag name.
 * @param {string} [className] Class list.
 * @param {string} [text] Text content.
 * @returns {HTMLElementTagNameMap[K]} The new element.
 */
const make = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
/**
 * Format a duration for the status chip.
 * @param {number} ms Milliseconds.
 * @returns {string} Display text.
 */
const duration = ms => ms < 1 ? "<1 ms" : ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
/**
 * Label the type of a returned value.
 * @param {Descriptor|undefined} value Returned value descriptor.
 * @returns {string} Type label.
 */
const typeLabel = value => {
  if (!value) return "";
  if (value.t === "object") return value.kind === "object" ? value.cls : value.preview.split(/[ (]/)[0] ?? value.kind;
  return value.t;
};
/**
 * Mount a runner on a carrier element that keeps the stored snippet.
 * @param {HTMLTextAreaElement|HTMLInputElement} carrier Hidden element holding the value.
 * @param {RunnerOptions} [options] Widget options.
 * @returns The widget API.
 */
export const mountRunner = (carrier, options = {}) => {
  const { label = "JavaScript", theme = null, mode = "auto", context = {}, execute = WorkerExecutor.run, readOnly = false, runnable = true } = options;
  /** @type {Variable[]} */
  let variables = [...(options.variables ?? [])];
  /** @type {Record<string, Set<(detail:any)=>void>>} */
  const listeners = {};
  /** @type {import("./executor.js").RunHandle|null} */
  let handle = null;
  /** @type {RunResult|null} */
  let lastResult = null;
  let runs = 0;
  /**
   * Notify registered listeners.
   * @param {string} type Event type.
   * @param {unknown} detail Event payload.
   * @returns {void}
   */
  const emit = (type, detail) => {
    for (const listener of listeners[type] ?? []) listener(detail);
  };
  const root = make("section", "jr-runner");
  if (theme) root.setAttribute("data-theme", theme);
  root.setAttribute("aria-label", label);
  root.setAttribute("data-runnable", String(runnable));
  const head = make("div", "jr-head");
  const title = make("span", "jr-title", label);
  const status = make("span", "jr-status");
  status.setAttribute("role", "status");
  status.setAttribute("data-state", "idle");
  const statusText = make("span", "jr-status-text", STATE_TEXT.idle);
  status.append(make("i", "jr-dot"), statusText);
  const spacer = make("span", "jr-spacer");
  const menuHost = make("span", "jr-menu-host");
  const valuesButton = make("button", "jc-button");
  valuesButton.type = "button";
  valuesButton.title = "Insert a value";
  valuesButton.setAttribute("aria-label", "Insert a value");
  valuesButton.append(icon("braces"));
  valuesButton.hidden = variables.length === 0;
  menuHost.append(valuesButton);
  const timeoutWrap = make("span", "jc-select");
  const timeoutSelect = make("select");
  timeoutSelect.setAttribute("aria-label", "Time limit");
  const limits = [...TIMEOUTS];
  const wanted = options.timeoutMs ?? 5000;
  if (!limits.some(([value]) => value === wanted)) limits.push(/** @type {never} */ ([wanted, `${wanted / 1000} s`]));
  for (const [value, text] of limits) {
    const option = make("option", "", text);
    option.value = String(value);
    timeoutSelect.append(option);
  }
  timeoutSelect.value = String(wanted);
  timeoutWrap.append(timeoutSelect);
  const runButton = make("button", "jr-run");
  runButton.type = "button";
  runButton.setAttribute("aria-keyshortcuts", "Control+Enter Meta+Enter");
  const runLabel = make("span", "jr-run-label", "Run");
  runButton.append(icon("play"), runLabel);
  head.append(title, status, spacer, menuHost, timeoutWrap, runButton);
  const editorHost = make("div", "jr-editor-host");
  const foot = make("div", "jr-foot");
  const caretText = make("span", "jr-caret", "Ln 1, Col 1");
  const sandbox = make("span", "jr-note", "Sandboxed worker · no DOM");
  const spacerFoot = make("span", "jr-spacer");
  /** @type {HTMLInputElement|null} */
  let outputInput = null;
  if (options.outputName !== undefined) {
    const field = make("label", "jr-field");
    outputInput = make("input");
    outputInput.name = "output_variable";
    outputInput.value = options.outputName;
    outputInput.placeholder = "result";
    outputInput.autocomplete = "off";
    outputInput.setAttribute("aria-label", "Save result as");
    field.append(make("span", "jr-field-label", "Save as"), outputInput);
    foot.append(caretText, sandbox, spacerFoot, field);
  } else
    foot.append(caretText, sandbox);
  const clearLabel = make("label", "jr-check");
  const clearBox = make("input");
  clearBox.type = "checkbox";
  clearBox.checked = options.clearOnRun ?? true;
  clearLabel.append(clearBox, make("span", "", "Clear console on run"));
  foot.append(clearLabel);
  const result = make("section", "jr-result");
  result.hidden = true;
  result.setAttribute("aria-label", "Result");
  const resultMarker = make("span", "jr-result-marker");
  const resultBody = make("div", "jr-result-body");
  const resultMeta = make("span", "jr-result-meta");
  result.append(resultMarker, resultBody, resultMeta);
  const consoleHost = make("div", "jr-console");
  root.append(head, editorHost, foot, result, consoleHost);
  carrier.hidden = true;
  carrier.after(root);
  const view = mountConsole(consoleHost, { label: "Console", theme, search: false });
  const editor = createEditor({
    host: editorHost,
    label,
    value: carrier.value || options.source || "",
    readOnly,
    onChange: value => {
      carrier.value = value;
      carrier.dispatchEvent(new Event("input", { bubbles: true }));
      emit("change", { value });
    },
    onCaret: ({ line, column, lines }) => {
      caretText.textContent = `Ln ${line}, Col ${column} · ${lines} line${lines === 1 ? "" : "s"}`;
    },
  });
  carrier.value = editor.getValue();
  if (options.name) editor.input.name = options.name;
  if (options.required) editor.input.required = true;
  const menu = createVariablesMenu({
    anchor: valuesButton,
    variables: () => variables,
    onPick: name => {
      editor.insert(`exactus.vars.get(${JSON.stringify(name)})`);
      editor.focus();
    },
  });
  menuHost.append(menu.element);
  view.on(
    "source",
    /** @param {{line:number, column:number}} position Snippet position of the message. */
    position => editor.goTo(position.line, position.column),
  );
  /**
   * Show a run state in the header and on the run button.
   * @param {RunState} state New state.
   * @param {string} [detail] Extra text after the state name.
   * @returns {void}
   */
  const setState = (state, detail = "") => {
    status.setAttribute("data-state", state);
    statusText.textContent = detail ? `${STATE_TEXT[state]} · ${detail}` : STATE_TEXT[state];
    root.setAttribute("data-running", String(state === "running"));
    runLabel.textContent = state === "running" ? "Stop" : "Run";
    runButton.replaceChildren(icon(state === "running" ? "stop" : "play"), runLabel);
    runButton.setAttribute("aria-label", state === "running" ? "Stop the run" : "Run the snippet");
    runButton.title = state === "running" ? "Stop" : "Run (Ctrl+Enter)";
  };
  /**
   * Draw the pinned result block for a finished run.
   * @param {RunResult} outcome Finished run.
   * @returns {void}
   */
  const showResult = outcome => {
    result.hidden = false;
    result.setAttribute("data-state", outcome.status);
    resultMarker.replaceChildren(outcome.status === "ok" ? document.createTextNode("‹") : icon(outcome.status === "error" ? "error" : "warn"));
    resultMeta.textContent = "";
    if (outcome.status === "ok") {
      const empty = outcome.value?.t === "undefined";
      resultBody.replaceChildren(outcome.value ? renderValue(outcome.value, true) : make("span", "", ""));
      const saved = outputInput?.value.trim();
      const parts = [empty ? "no return value" : typeLabel(outcome.value)];
      if (!empty && !outcome.jsonSafe) parts.push("not JSON-safe");
      else if (!empty && saved) parts.push(`saved as ${saved}`);
      resultMeta.textContent = parts.filter(Boolean).join(" · ");
      return;
    }
    if (outcome.status === "error" && outcome.value) {
      const body = make("div", "jr-error");
      body.append(renderValue(outcome.value));
      const where = outcome.error?.location;
      if (where) {
        const jump = make("button", "jc-source", `line ${where.line}:${where.column}`);
        jump.type = "button";
        jump.addEventListener("click", () => editor.goTo(where.line, where.column));
        body.append(jump);
        editor.setErrorLine(where.line);
      }
      resultBody.replaceChildren(body);
      return;
    }
    const seconds = Number(timeoutSelect.value) / 1000;
    resultBody.replaceChildren(
      make("span", "jr-note", outcome.status === "timeout" ? `Stopped after ${seconds} s. The worker was terminated, so long or endless loops cannot freeze the page.` : "The run was stopped before it finished."),
    );
  };
  /**
   * Run the snippet once.
   * @returns {Promise<RunResult|null>} The result, or null when a run is already active.
   */
  const run = async () => {
    if (handle || !runnable) return null;
    const code = editor.getValue();
    editor.setErrorLine(null);
    runs += 1;
    if (clearBox.checked) view.clear();
    else if (view.entries().length > 0) view.append({ kind: "divider", parts: [Describer.describe(`Run ${runs}`)] });
    setState("running");
    emit("run", { code });
    const active = execute(
      {
        code,
        mode,
        variables: Object.fromEntries(variables.map(variable => [variable.name, variable.value])),
        context,
        timeoutMs: Number(timeoutSelect.value),
      },
      {
        onEntry: entry => {
          view.append(entry);
        },
        onClear: () => view.clear(),
      },
    );
    handle = active;
    const outcome = await active.promise;
    if (handle === active) handle = null;
    lastResult = outcome;
    showResult(outcome);
    setState(outcome.status, outcome.status === "ok" || outcome.status === "error" ? duration(outcome.durationMs) : "");
    emit("result", { ...outcome, saveAs: outputInput?.value.trim() || null });
    return outcome;
  };
  /** Cancel the active run, if one is in flight. */
  const stop = () => handle?.cancel();
  runButton.addEventListener("click", () => (handle ? stop() : run()));
  editor.element.addEventListener("editor-run", () => run());
  setState("idle");
  editor.setReadOnly(readOnly);
  carrier.value = editor.getValue();
  return {
    element: root,
    editor,
    console: view,
    run,
    stop,
    getValue: () => editor.getValue(),
    /**
     * Replace the snippet.
     * @param {string} value New source.
     * @returns {void}
     */
    setValue: value => editor.setValue(value),
    /**
     * Replace the values offered to the snippet.
     * @param {Variable[]} next New values.
     * @returns {void}
     */
    setVariables: next => {
      variables = [...next];
      valuesButton.hidden = variables.length === 0;
    },
    lastResult: () => lastResult,
    outputName: () => outputInput?.value.trim() ?? null,
    /**
     * Subscribe to `run`, `result` or `change` events.
     * @param {string} type Event type.
     * @param {(detail:any)=>void} listener Event listener.
     * @returns {()=>void} Unsubscribe function.
     */
    on: (type, listener) => {
      (listeners[type] ??= new Set()).add(listener);
      return () => listeners[type]?.delete(listener);
    },
    /**
     * Set or clear the widget theme.
     * @param {string|null} value `light`, `dark` or null.
     * @returns {void}
     */
    setTheme: value => {
      if (value) root.setAttribute("data-theme", value);
      else root.removeAttribute("data-theme");
      view.setTheme(value);
    },
    /** Stop any run and remove the widget. */
    destroy: () => {
      stop();
      menu.destroy();
      view.destroy();
      root.remove();
      carrier.hidden = false;
      for (const set of Object.values(listeners)) set.clear();
    },
  };
};
