import { iconElement } from "./icons.js";
import { selectorExpressionField } from "./selector-expression-field.js";
/** The Selectors list and the selector inspector.
 *
 * Both are plain DOM builders with no dependency on the editor, in the same way
 * as flow-list.js: the editor passes data and handlers in, and gets elements back.
 */
/**
 * @typedef {{selector_id:string,name:string,expression:string,expected_count:number|null,checks:string[],validated_on:{url:string,at:string,matches:number}[]}} SelectorItem
 * @typedef {{actions:{flow_id:string,event_id:string}[],flows:number,selectors:string[],conditions:number}} SelectorUse
 * @typedef {{index:number,css:string|null,css_error:string|null,rect:{x:number,y:number,width:number,height:number},tag:string|null,text:string|null,failed:string[]}} TestMatch
 * @typedef {{expression:string,selector_id:string|null,ok:boolean,count:number,expected_count:number|null,elapsed_ms:number,polls:number,error:string|null,definition_errors:string[],cause:{message?:string,[field:string]:any}|null,url:string,matches:TestMatch[]}} TestResult
 * @typedef {{selector_id:string,name:string,expression:string,expected_count:number|null,checks:string[]}} SelectorValues
 */
/** The most matches the result list draws; the rest are summarised. */
const MAX_LISTED = 50;
/** Build an element with optional class and text.
 * @param {string} tag
 * @param {string} [className]
 * @param {string} [text]
 * @returns {HTMLElement}
 */
const make = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
/** An icon from the shared icon set, as a real inline SVG.
 * @param {string} name
 * @returns {SVGSVGElement}
 */
const icon = name => iconElement(name);
/** Say how many actions and flows use a selector.
 * @param {SelectorUse|undefined} use
 * @returns {string}
 */
export const usageSentence = use => {
  const actions = use?.actions.length ?? 0;
  if (!actions && !use?.selectors.length && !use?.conditions)
    return "Not used yet";
  const parts = [];
  if (actions)
    parts.push(
      `${actions} ${actions === 1 ? "action" : "actions"} in ${use?.flows} ${use?.flows === 1 ? "flow" : "flows"}`,
    );
  if (use?.selectors.length)
    parts.push(
      `${use.selectors.length} ${use.selectors.length === 1 ? "selector" : "selectors"}`,
    );
  if (use?.conditions)
    parts.push(
      `${use.conditions} ${use.conditions === 1 ? "condition" : "conditions"}`,
    );
  return `Used by ${parts.join(", ")}`;
};
/** Render the project's selectors as selectable rows.
 * @param {HTMLElement} target Container that receives the rows.
 * @param {SelectorItem[]} selectors Stored selectors.
 * @param {Record<string,SelectorUse>} usage What depends on each selector.
 * @param {string|null} selectedId The selector shown in the inspector.
 * @param {(id:string)=>void} onSelect Called when a row is chosen.
 * @returns {void}
 */
export const renderSelectorList = (
  target,
  selectors,
  usage,
  selectedId,
  onSelect,
) => {
  if (!selectors.length) {
    target.replaceChildren(
      make(
        "p",
        "side-empty",
        "No selectors yet. A selector finds elements once and any action can reuse it.",
      ),
    );
    return;
  }
  target.replaceChildren(
    ...selectors.map(item => {
      const use = usage[item.selector_id];
      const button = /** @type {HTMLButtonElement} */ (
        make("button", "tree-item")
      );
      button.type = "button";
      button.classList.toggle("active", item.selector_id === selectedId);
      button.setAttribute("data-selector", item.selector_id);
      button.setAttribute(
        "aria-pressed",
        String(item.selector_id === selectedId),
      );
      const count = use?.actions.length ?? 0;
      button.append(icon("crosshair"), make("span", "", item.name));
      if (!item.validated_on.length) {
        const warn = make("span", "tree-item-flag");
        warn.append(icon("alert-triangle"));
        warn.title = "Not tested on any page yet";
        button.append(warn);
      }
      const badge = make("span", "tree-item-count", count ? String(count) : "");
      badge.title = usageSentence(use);
      button.append(badge);
      button.addEventListener("click", () => onSelect(item.selector_id));
      return button;
    }),
  );
};
/** Describe an expected count for the select control.
 * @param {number|null|undefined} count
 * @returns {{mode:"one"|"any"|"exact",exact:number}}
 */
const countMode = count => {
  if (count === null) return { mode: "any", exact: 2 };
  if (count === undefined || count === 1) return { mode: "one", exact: 2 };
  return { mode: "exact", exact: count };
};
/** Turn the count controls into the value the server stores.
 * @param {string} mode
 * @param {string} exact
 * @returns {number|null}
 */
const countValue = (mode, exact) => {
  if (mode === "any") return null;
  if (mode === "exact") return Math.max(0, Number.parseInt(exact, 10) || 0);
  return 1;
};
/** Fill the result area with the outcome of a live test.
 * @param {HTMLElement} target
 * @param {TestResult|null} result
 * @param {boolean} [running]
 * @returns {void}
 */
export const renderTestResult = (target, result, running = false) => {
  target.replaceChildren();
  if (running) {
    target.append(make("p", "selector-note", "Testing against the live page…"));
    return;
  }
  if (!result) {
    target.append(
      make(
        "p",
        "selector-note",
        "Test the expression against the open page to see what it matches.",
      ),
    );
    return;
  }
  const head = make("div", `selector-verdict ${result.ok ? "pass" : "fail"}`);
  head.setAttribute("role", "status");
  head.append(icon(result.ok ? "circle-check" : "alert-triangle"));
  const found = `${result.count} ${result.count === 1 ? "match" : "matches"}`;
  head.append(
    make(
      "strong",
      "",
      result.error || (result.ok ? found : result.cause?.message || found),
    ),
  );
  head.append(
    make(
      "small",
      "",
      result.ok
        ? `in ${result.elapsed_ms} ms`
        : `Found ${result.count} in ${result.elapsed_ms} ms`,
    ),
  );
  target.append(head);
  for (const message of result.definition_errors)
    target.append(make("p", "selector-note warn", message));
  const list = make("ol", "selector-matches");
  for (const match of result.matches.slice(0, MAX_LISTED)) {
    const row = make("li", "selector-match");
    row.append(make("span", "selector-match-n", String(match.index + 1)));
    const body = make("div", "selector-match-body");
    const title = [match.tag, match.text].filter(Boolean).join(" ");
    body.append(make("span", "selector-match-text", title || "(empty)"));
    body.append(
      make(
        "code",
        "selector-match-css",
        match.css || match.css_error || "No selector found",
      ),
    );
    for (const failed of match.failed)
      body.append(make("span", "selector-match-failed", `Failed: ${failed}`));
    row.append(body);
    list.append(row);
  }
  if (result.matches.length > MAX_LISTED)
    list.append(
      make(
        "li",
        "selector-note",
        `And ${result.matches.length - MAX_LISTED} more`,
      ),
    );
  target.append(list);
};
/** Fill the "Tested on" area: the pages the selector passed on, and a warning
 * when the page that is open now is not one of them.
 * @param {HTMLElement} target
 * @param {SelectorItem|null} selector
 * @param {string} pageUrl
 * @returns {void}
 */
export const renderSeen = (target, selector, pageUrl) => {
  target.replaceChildren(make("h3", "", "Tested on"));
  const pages = selector?.validated_on ?? [];
  if (!pages.length) {
    target.append(
      make("p", "selector-note warn", "Not tested on any page yet."),
    );
    return;
  }
  const list = make("ul", "selector-pages");
  for (const page of pages) {
    const row = make("li");
    row.append(
      make("span", "selector-page-url", page.url),
      make(
        "small",
        "",
        `${page.matches} ${page.matches === 1 ? "match" : "matches"}`,
      ),
    );
    list.append(row);
  }
  target.append(list);
  if (pageUrl && !pages.some(page => page.url === pageUrl))
    target.append(
      make(
        "p",
        "selector-note warn",
        "Not tested on the page that is open now. It may not match there.",
      ),
    );
};
/** Build the selector inspector.
 * @param {object} options Inspector inputs.
 * @param {SelectorItem|null} options.selector Selector being edited, `null` for a new one.
 * @param {SelectorUse|undefined} options.usage What depends on the selector.
 * @param {(flowId:string, eventId:string)=>string} options.labelFor Flow step label lookup.
 * @param {string} options.pageUrl URL of the open target page.
 * @param {TestResult|null} options.test Latest live-test outcome.
 * @param {string[]} options.selectors Saved selector names available as references.
 * @param {any} options.engine Formula lint engine.
 * @param {any} options.Editor Formula editor class.
 * @param {(values:SelectorValues)=>void} options.onSave Saves the form.
 * @param {(values:SelectorValues)=>void} options.onSaveCopy Saves under a new name.
 * @param {(values:SelectorValues, done?:((result:{count?:number})=>void)|null)=>void} options.onTest Runs the live test.
 * @param {(apply:(element:{selector:string,matches?:number,alternatives?:Array<{strategy:string,selector:string,matches:number}>})=>void)=>void} options.onPick Starts picking on the page.
 * @param {(()=>void)|undefined} options.onClear Removes the page highlight.
 * @param {((expression:string)=>Promise<object>)|undefined} options.onStats Silent test returning widget stats.
 * @param {(()=>object[])|undefined} options.variables Variables the host offers.
 * @param {()=>void} options.onDelete Removes the selector.
 * @param {(flowId:string, eventId:string)=>void} options.onOpenAction Opens a flow step.
 * @returns {{fragment:DocumentFragment,form:HTMLFormElement,result:HTMLElement}}
 */
export const selectorInspector = options => {
  const { selector, usage } = options;
  const fragment = document.createDocumentFragment();
  const heading = make("div", "edit-inspector-heading");
  const mark = make("span", "edit-inspector-mark");
  mark.append(icon("crosshair"));
  const titles = make("div");
  titles.append(
    make("h2", "", selector ? selector.name : "New selector"),
    make("small", "", selector ? usageSentence(usage) : "Not saved yet"),
  );
  heading.append(mark, titles);
  const form = /** @type {HTMLFormElement} */ (make("form", "selector-form"));
  form.id = "selector-form";
  form.noValidate = true;
  const name = /** @type {HTMLInputElement} */ (make("input"));
  name.name = "name";
  name.required = true;
  name.maxLength = 48;
  name.spellcheck = false;
  name.value = selector?.name ?? "";
  name.placeholder = "order_card";
  const nameLabel = make("label");
  nameLabel.append("Name", name);
  const nameHint = make(
    "small",
    "selector-hint",
    "Letters, digits and underscores. Conditions read it as sel_<name>_count.",
  );
  const expression = /** @type {HTMLTextAreaElement} */ (make("textarea"));
  expression.name = "expression";
  expression.spellcheck = false;
  expression.value = selector?.expression ?? "";
  /** Read the form into the stored selector shape. The values exist only
   * after the later controls are built, so the highlighter reads them
   * through this binding, which is filled in below.
   * @type {() => SelectorValues}
   */
  let readValues = () => ({
    selector_id: "",
    name: "",
    expression: "",
    expected_count: null,
    checks: [],
  });
  const expressionField = selectorExpressionField({
    label: "Expression",
    textarea: expression,
    Editor: options.Editor,
    engine: options.engine,
    selectors: options.selectors,
    matchCount: options.test?.count,
    onPick: options.onPick,
    onHighlight: (value, done) =>
      options.onTest({ ...readValues(), expression: value }, done),
    onClear: options.onClear,
    onStats: options.onStats,
    variables: options.variables,
    saved: () => options.selectors.map(savedName => ({ name: savedName })),
    expected: () => {
      const values = readValues();
      return values.expected_count;
    },
  });
  const initial = countMode(selector?.expected_count);
  const mode = /** @type {HTMLSelectElement} */ (make("select"));
  mode.name = "count_mode";
  for (const [value = "", label = ""] of [
    ["one", "Exactly one"],
    ["any", "One or more"],
    ["exact", "Exactly…"],
  ]) {
    const option = /** @type {HTMLOptionElement} */ (make("option", "", label));
    option.value = value;
    mode.append(option);
  }
  mode.value = initial.mode;
  const exact = /** @type {HTMLInputElement} */ (make("input"));
  exact.name = "count_exact";
  exact.type = "number";
  exact.min = "0";
  exact.value = String(initial.exact);
  exact.setAttribute("aria-label", "Exact match count");
  /** Show the exact-count field only when that mode is chosen.
   * @returns {void}
   */
  const syncExact = () => {
    exact.hidden = mode.value !== "exact";
  };
  syncExact();
  mode.addEventListener("change", syncExact);
  const countRow = make("div", "selector-count");
  countRow.append(mode, exact);
  const countLabel = make("div", "selector-field");
  countLabel.append(
    make("span", "selector-field-label", "Should match"),
    countRow,
  );
  const checks = /** @type {HTMLTextAreaElement} */ (make("textarea"));
  checks.name = "checks";
  checks.rows = 2;
  checks.spellcheck = false;
  checks.placeholder = '[aria-disabled!="true"]';
  checks.value = (selector?.checks ?? []).join("\n");
  const checksField = selectorExpressionField({
    label: "Every match must satisfy",
    textarea: checks,
    Editor: options.Editor,
    engine: options.engine,
    selectors: options.selectors,
    multiple: true,
    startAsText: true,
  });
  /** Read the form into the stored selector shape.
   * @returns {SelectorValues}
   */
  const values = () => ({
    selector_id: selector?.selector_id ?? "",
    name: name.value.trim(),
    expression: expression.value.trim(),
    expected_count: countValue(mode.value, exact.value),
    checks: checks.value
      .split("\n")
      .map(line => line.trim())
      .filter(Boolean),
  });
  readValues = values;
  const actions = make("div", "selector-actions");
  const save = /** @type {HTMLButtonElement} */ (
    make("button", "selector-save")
  );
  save.type = "submit";
  save.append(icon("check"), "Save");
  actions.append(save);
  if (selector) {
    const copy = /** @type {HTMLButtonElement} */ (
      make("button", "selector-icon")
    );
    copy.type = "button";
    copy.title = "Save as a new selector";
    copy.setAttribute("aria-label", "Save as a new selector");
    copy.append(icon("copy"));
    copy.addEventListener("click", () => options.onSaveCopy(values()));
    const remove = /** @type {HTMLButtonElement} */ (
      make("button", "selector-icon")
    );
    remove.type = "button";
    remove.title = "Delete selector";
    remove.setAttribute("aria-label", "Delete selector");
    remove.append(icon("trash"));
    remove.addEventListener("click", () => options.onDelete());
    actions.append(copy, remove);
  }
  form.append(
    nameLabel,
    nameHint,
    expressionField.field,
    countLabel,
    checksField.field,
    actions,
  );
  form.addEventListener("submit", event => {
    event.preventDefault();
    options.onSave(values());
  });
  const result = make("section", "selector-result");
  result.id = "selector-result";
  result.setAttribute("aria-label", "Test result");
  renderTestResult(result, options.test);
  const seen = make("section", "selector-seen");
  renderSeen(seen, selector, options.pageUrl);
  const used = make("section", "selector-used");
  if (usage?.actions.length) {
    used.append(make("h3", "", "Actions that use it"));
    const list = make("ul", "selector-actions-list");
    for (const ref of usage.actions) {
      const row = make("li");
      const open = /** @type {HTMLButtonElement} */ (
        make("button", "selector-open")
      );
      open.type = "button";
      open.textContent = options.labelFor(ref.flow_id, ref.event_id);
      open.addEventListener("click", () =>
        options.onOpenAction(ref.flow_id, ref.event_id),
      );
      row.append(open);
      list.append(row);
    }
    used.append(list);
  }
  fragment.append(heading, form, result, seen, used);
  return { fragment, form, result };
};
