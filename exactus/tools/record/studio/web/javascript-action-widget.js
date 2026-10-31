/** JavaScript authoring workbench: a runnable snippet editor plus a runtime-value catalog. */
import { mountRunner } from "../../../../packages/actions/action_javascript/index.js";
import { variableName } from "./variable-mention-field.js";
/** @typedef {import("./variable-mention-field.js").VariableSource} VariableSource */
/**
 * @typedef {object} RuntimeSymbol
 * @property {string} category
 * @property {string} path
 * @property {string} type
 * @property {string} description
 * @property {string} insertText
 * @property {string} [preview]
 * @property {string} [availability]
 */
/** Create an element with a class.
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
/** Read a safe string from an untrusted snapshot object.
 * @param {unknown} value
 * @returns {string}
 */
const text = value => typeof value === "string" ? value : "";
/** Build the values known while authoring this action.
 * @param {any} snapshot
 * @param {VariableSource[]} variables
 * @returns {RuntimeSymbol[]}
 */
const runtimeSymbols = (snapshot, variables) => {
  const project = snapshot?.project ?? {};
  const viewport = snapshot?.viewport ?? {};
  const activeFlow = (snapshot?.workspace?.flows ?? []).find(
    (/** @type {{id?:string}} */ flow) => flow.id === snapshot?.active_flow_id,
  );
  /** @type {RuntimeSymbol[]} */
  const system = [
    {
      category: "Page & frame",
      path: "exactus.page.url",
      type: "URL",
      description: "Actual page URL immediately before this action runs.",
      insertText: "exactus.page.url",
      preview: text(snapshot?.target_url) || "Runtime only",
    },
    {
      category: "Page & frame",
      path: "exactus.page.title",
      type: "string",
      description: "Current document title in the bound page.",
      insertText: "exactus.page.title",
      availability: "Runtime only",
    },
    {
      category: "Project & context",
      path: "exactus.project.id",
      type: "string",
      description: "Stable project slug without a local filesystem path.",
      insertText: "exactus.project.id",
      preview: text(project.slug),
    },
    {
      category: "Project & context",
      path: "exactus.project.name",
      type: "string",
      description: "Project display name frozen for this run.",
      insertText: "exactus.project.name",
      preview: text(project.name),
    },
    {
      category: "Project & context",
      path: "exactus.context.baseUrl",
      type: "URL",
      description: "Base URL supplied by the selected project context.",
      insertText: "exactus.context.baseUrl",
      preview: text(project.base_url),
    },
    {
      category: "Flow",
      path: "exactus.flow.id",
      type: "string",
      description: "Reusable flow identity for this invocation.",
      insertText: "exactus.flow.id",
      preview: text(snapshot?.active_flow_id),
    },
    {
      category: "Flow",
      path: "exactus.flow.name",
      type: "string",
      description: "Flow display name frozen for this invocation.",
      insertText: "exactus.flow.name",
      preview: text(activeFlow?.name),
    },
    {
      category: "Run & action",
      path: "exactus.run.id",
      type: "string",
      description: "Current run identity.",
      insertText: "exactus.run.id",
      preview: text(snapshot?.execution_run_id) || "Created on run",
    },
    {
      category: "Run & action",
      path: "exactus.action.id",
      type: "string",
      description: "Stable action identity for the current attempt.",
      insertText: "exactus.action.id",
      availability: "Created after saving",
    },
    {
      category: "Device",
      path: "exactus.device.profileId",
      type: "string",
      description: "Project-owned device profile selected for this run.",
      insertText: "exactus.device.profileId",
      preview: text(snapshot?.device_mode),
    },
    {
      category: "Device",
      path: "exactus.device.viewport.width",
      type: "integer",
      description: "Effective viewport width after earlier device actions.",
      insertText: "exactus.device.viewport.width",
      preview: viewport.width === undefined ? "Runtime only" : String(viewport.width),
    },
    {
      category: "Device",
      path: "exactus.device.viewport.height",
      type: "integer",
      description: "Effective viewport height after earlier device actions.",
      insertText: "exactus.device.viewport.height",
      preview: viewport.height === undefined ? "Runtime only" : String(viewport.height),
    },
    {
      category: "Targets & selectors",
      path: "exactus.target",
      type: "Element | null",
      description: "Current matched element in the isolated page world.",
      insertText: "exactus.target",
      availability: "When the action has a target",
    },
    {
      category: "Targets & selectors",
      path: "exactus.selectors.queryOne(sourceOrId)",
      type: "function",
      description: "Query one element with the shared Extended Selector engine.",
      insertText: "exactus.selectors.queryOne(\"selector\")",
    },
    {
      category: "Logs & evidence",
      path: "exactus.log(...values)",
      type: "function",
      description: "Write a structured line to this action attempt.",
      insertText: "exactus.log()",
    },
    {
      category: "Logs & evidence",
      path: "exactus.assert(condition, message)",
      type: "function",
      description: "Fail this action unless the condition is truthy.",
      insertText: "exactus.assert(condition, \"Expected condition\")",
    },
  ];
  const user = variables.map(source => {
    const name = variableName(source);
    const typeName = typeof source === "string" ? "value" : (source.type ?? "value");
    return {
      category: "Earlier action results",
      path: name,
      type: typeName,
      description: "Value produced by an earlier reachable action.",
      insertText: `exactus.vars.get(${JSON.stringify(name)})`,
      availability: "Available now",
    };
  });
  return [...user, ...system];
};
/** Make one tab and associated panel.
 * @param {string} id
 * @param {string} label
 * @param {HTMLElement} tabs
 * @param {HTMLElement} panels
 * @returns {HTMLElement}
 */
const tabPanel = (id, label, tabs, panels) => {
  const tab = make("button", "javascript-tab");
  tab.type = "button";
  tab.id = `javascript-tab-${id}`;
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-controls", `javascript-panel-${id}`);
  tab.setAttribute("aria-selected", String(tabs.children.length === 0));
  tab.textContent = label;
  const panel = make("section", "javascript-panel");
  panel.id = `javascript-panel-${id}`;
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
/**
 * @typedef {object} JavascriptWidgetOptions
 * @property {string} source Initial snippet.
 * @property {string} sourceLabel Accessible name of the editor.
 * @property {VariableSource[]} variables Values produced by earlier actions.
 * @property {any} snapshot Workspace snapshot, for the runtime context.
 * @property {string|null} outputName Default result variable, or null when the field has none.
 * @property {boolean} [runnable] False when the snippet runs in the live page and cannot be previewed.
 * @property {string} [name] Form field that carries the code, `payload` by default.
 */
/** Describe the flow, project and action the preview run pretends to be in.
 * @param {any} snapshot
 * @returns {Record<string, Record<string, string>>}
 */
const previewContext = snapshot => {
  const project = snapshot?.project ?? {};
  const flowId = text(snapshot?.active_flow_id);
  const flow = (snapshot?.workspace?.flows ?? []).find(
    (/** @type {{id?:string}} */ item) => item.id === flowId,
  );
  return {
    project: { id: text(project.slug), name: text(project.name) },
    context: { baseUrl: text(project.base_url) },
    flow: { id: flowId, name: text(flow?.name) },
  };
};
/** Create a runnable code editor with a runtime-value catalog.
 * @param {JavascriptWidgetOptions} options
 * @returns {HTMLElement}
 */
export const javascriptActionWidget = options => {
  const { source, sourceLabel, variables, snapshot, outputName, runnable = true, name = "payload" } = options;
  const root = make("div", "javascript-action-widget");
  const tabs = make("div", "javascript-tabs");
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "JavaScript action settings");
  const panels = make("div", "javascript-panels");
  const codePanel = tabPanel("code", "Code", tabs, panels);
  const valuesPanel = tabPanel("values", `Values ${variables.length}`, tabs, panels);
  const carrier = make("textarea");
  carrier.value = source;
  codePanel.append(carrier);
  const runner = mountRunner(carrier, {
    label: sourceLabel,
    theme: "dark",
    mode: "playback",
    runnable,
    name,
    required: true,
    source,
    context: previewContext(snapshot),
    variables: variables.map(item => ({
      name: variableName(item),
      value: undefined,
      type: typeof item === "string" ? "value" : (item.type ?? "value"),
    })),
    ...(outputName === null ? {} : { outputName }),
  });
  const valuesTools = make("div", "javascript-values-tools");
  const search = make("input");
  search.type = "search";
  search.placeholder = "Search values, types and context";
  search.setAttribute("aria-label", "Search available JavaScript values");
  const count = make("output", "javascript-values-count");
  valuesTools.append(search, count);
  const catalog = make("div", "javascript-value-catalog");
  const symbols = runtimeSymbols(snapshot, variables);
  /** Draw filtered catalog groups.
   * @returns {void}
   */
  const renderCatalog = () => {
    const query = search.value.trim().toLowerCase();
    const shown = symbols.filter(symbol =>
      `${symbol.category} ${symbol.path} ${symbol.type} ${symbol.description}`
        .toLowerCase()
        .includes(query),
    );
    count.value = `${shown.length} values`;
    const groups = new Map();
    for (const symbol of shown) {
      if (!groups.has(symbol.category)) groups.set(symbol.category, []);
      groups.get(symbol.category).push(symbol);
    }
    catalog.replaceChildren(...[...groups].map(([category, items]) => {
      const group = make("section", "javascript-value-group");
      const heading = make("h4");
      heading.textContent = category;
      group.append(heading);
      for (const symbol of items) {
        const row = make("article", "javascript-value-row");
        const description = make("div", "javascript-value-description");
        const path = make("code");
        path.textContent = symbol.path;
        const meta = make("small");
        meta.textContent = `${symbol.type} · ${symbol.description}`;
        const preview = make("small", "javascript-value-preview");
        preview.textContent = symbol.preview || symbol.availability || "Available at playback";
        description.append(path, meta, preview);
        const insert = make("button", "javascript-value-insert");
        insert.type = "button";
        insert.textContent = "Insert";
        insert.setAttribute("aria-label", `Insert ${symbol.path}`);
        insert.addEventListener("click", () => {
          tabs.querySelector('[aria-controls="javascript-panel-code"]')?.dispatchEvent(
            new MouseEvent("click", { bubbles: true }),
          );
          runner.editor.insert(symbol.insertText);
          runner.editor.focus();
        });
        row.append(description, insert);
        group.append(row);
      }
      return group;
    }));
  };
  search.addEventListener("input", renderCatalog);
  renderCatalog();
  valuesPanel.append(valuesTools, catalog);
  root.append(tabs, panels);
  return root;
};
/** Create the editor for the condition that guards an action.
 * @param {object} options
 * @param {string} options.source Current condition, empty when the action is unguarded.
 * @param {VariableSource[]} options.variables Values produced by earlier actions.
 * @param {any} options.snapshot Workspace snapshot, for the runtime context.
 * @returns {HTMLElement}
 */
export const conditionWidget = options => {
  const { source, variables, snapshot } = options;
  const root = make("div", "javascript-action-widget");
  const carrier = make("textarea");
  carrier.value = source;
  root.append(carrier);
  mountRunner(carrier, {
    label: "Run only if",
    theme: "dark",
    mode: "expression",
    runnable: true,
    name: "when_expression",
    required: false,
    source,
    context: previewContext(snapshot),
    variables: variables.map(item => ({
      name: variableName(item),
      value: undefined,
      type: typeof item === "string" ? "value" : (item.type ?? "value"),
    })),
  });
  return root;
};
