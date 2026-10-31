/** Pills for the condition language.
 *
 * Draws a parsed condition the way a spreadsheet draws a formula: a function is
 * a capsule that wraps its arguments, names are coloured pills with a dropdown,
 * an argument still to be filled is an empty slot that says what it is for, and
 * operators sit between their values. Every pill maps back to a range of the
 * text, so a change made on a pill is a change to the text; the text stays the
 * one source of truth and the pills are a view of it.
 */
import { FUNCTIONS, OPERATORS, semanticOf } from "./condition-language.js";
const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const CAP_PATHS = Object.freeze({
  start:
    "M84.2 10c0-4.3 2.3-8 5.8-10H10C4.5 0 0 4.5 0 10s4.5 10 10 10h80c-3.4-2-5.8-5.7-5.8-10Z",
  end: "M5.3 0H0c3.3 2 5.6 5.7 5.6 10S3.4 18 0 20h5.3c5.3 0 9.7-4.5 9.7-10S10.7 0 5.3 0Z",
});
/**
 * @typedef {object} MenuEntry One choice in a pill's dropdown.
 * @property {string} text What it writes.
 * @property {string} kind Token kind, which sets its colour.
 * @property {string} detail One line of explanation.
 * @property {() => void} [action] What to do instead of writing the text.
 */
/**
 * @typedef {object} PillEnv What the pills need from the field that hosts them.
 * @property {string} text The condition as written.
 * @property {ConditionTerm[]} terms Names the project offers.
 * @property {import("./condition-language.js").Issue[]} issues What the language rejects.
 * @property {boolean} disabled Whether the field is switched off.
 * @property {(start:number,end:number,text:string)=>void} replace Change a range of the text.
 * @property {(start:number,end:number)=>void} select Move to the text and select a range, to edit it by hand.
 * @property {(anchor:HTMLElement,entries:MenuEntry[],choose:(entry:MenuEntry)=>void)=>void} menu Open a dropdown under a pill.
 */
/** Build an element.
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
/** Draw one interlocking cap from the supplied SVG reference geometry.
 * @param {"start"|"end"} side Which edge of a function capsule this closes.
 * @returns {SVGSVGElement}
 */
const cap = side => {
  const svg = document.createElementNS(SVG_NAMESPACE, "svg");
  svg.setAttribute(
    "class",
    `pill-cap pill-cap-${side} ${side === "start" ? "st0" : "st00"}`,
  );
  svg.setAttribute("viewBox", side === "start" ? "0 0 90 20" : "0 0 15 20");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG_NAMESPACE, "path");
  path.setAttribute("d", CAP_PATHS[side]);
  svg.append(path);
  return svg;
};
/** A pill that can be pressed.
 * @param {string} className
 * @param {string} text
 * @param {PillEnv} env
 * @param {boolean} [dropdown] Whether it opens a menu, shown with a small arrow.
 * @returns {HTMLButtonElement}
 */
const button = (className, text, env, dropdown = false) => {
  const node = /** @type {HTMLButtonElement} */ (make("button", className));
  node.type = "button";
  node.disabled = env.disabled;
  node.append(make("span", "pill-text", text));
  if (dropdown) {
    node.append(make("i", "pill-arrow"));
    node.setAttribute("aria-haspopup", "dialog");
  }
  return node;
};
/** Whether an issue touches a range of the text.
 * @param {PillEnv} env
 * @param {number} start
 * @param {number} end
 * @returns {"error"|"warning"|""}
 */
const issueAt = (env, start, end) => {
  const hits = env.issues.filter(
    issue =>
      issue.end > issue.start && issue.start < end && issue.end > start,
  );
  if (hits.some(issue => issue.level === "error")) return "error";
  return hits.length ? "warning" : "";
};
/** Choices that can fill a value of a given type.
 * @param {ConditionTerm[]} terms
 * @param {import("./condition-language.js").Semantic} semantic
 * @param {string} [skip] A name to leave out, such as the one being replaced.
 * @returns {MenuEntry[]}
 */
const valueEntries = (terms, semantic, skip = "") => {
  /** @type {MenuEntry[]} */
  const entries = [];
  for (const term of terms) {
    const kind = semanticOf(term.value_type);
    if (term.name === skip) continue;
    if (semantic !== "any" && kind !== "any" && kind !== semantic) continue;
    entries.push({ text: term.name, kind: term.kind, detail: term.detail });
  }
  if (semantic === "boolean" || semantic === "any")
    for (const literal of ["True", "False"])
      if (literal !== skip)
        entries.push({
          text: literal,
          kind: "literal",
          detail: "A fixed true or false",
        });
  return entries;
};
/** Draw the whole tree as pills.
 * @param {import("./condition-language.js").TreeNode|null} tree
 * @param {PillEnv} env
 * @returns {HTMLElement[]}
 */
export const renderPills = (tree, env) => {
  /** One rule per kind of node; they call each other for the parts inside.
   * @type {Record<"call"|"binary"|"not"|"group"|"term"|"literal"|"missing",(node:import("./condition-language.js").TreeNode,depth:number,cut:[number,number])=>HTMLElement>}
   */
  const draw = {
    call: () => make("span"),
    binary: () => make("span"),
    not: () => make("span"),
    group: () => make("span"),
    term: () => make("span"),
    literal: () => make("span"),
    missing: () => make("span"),
  };
  /** Draw one tree node at a nesting depth.
   * @param {import("./condition-language.js").TreeNode} node Node to draw.
   * @param {number} depth Nesting depth of the node.
   * @param {[number,number]} cut Range removed with the node.
   * @returns {HTMLSpanElement}
   */
  const part = (node, depth, cut) => draw[node.kind](node, depth, cut);
  /** A small remove button for a node.
   * @param {[number,number]} cut
   * @param {string} what
   * @returns {HTMLButtonElement}
   */
  const remover = (cut, what) => {
    const node = /** @type {HTMLButtonElement} */ (
      make("button", "pill-remove")
    );
    node.type = "button";
    node.textContent = "×";
    node.disabled = env.disabled;
    node.title = `Remove ${what}`;
    node.setAttribute("aria-label", `Remove ${what}`);
    node.addEventListener("click", event => {
      event.stopPropagation();
      env.replace(cut[0], cut[1], "");
    });
    return node;
  };
  /** Pressing Delete on a focused pill removes it.
   * @param {HTMLElement} pill
   * @param {[number,number]} cut
   */
  const deletable = (pill, cut) => {
    pill.addEventListener("keydown", event => {
      if (event.key !== "Delete" && event.key !== "Backspace") return;
      event.preventDefault();
      env.replace(cut[0], cut[1], "");
    });
  };
  draw.term = (node, _depth, cut) => {
    const token = /** @type {import("./condition-language.js").Token} */ (
      node.token
    );
    const pill = button(
      `pill pill-ref pill-${token.kind}`,
      token.text,
      env,
      true,
    );
    const problem = issueAt(env, node.start, node.end);
    if (problem) pill.setAttribute("data-issue", problem);
    pill.addEventListener("click", () => {
      const entries = [
        ...valueEntries(
          env.terms,
          node.semantic === "any" ? "any" : node.semantic,
          token.text,
        ),
        {
          text: "Edit as text",
          kind: "paren",
          detail: "Change it by typing",
          action: () => env.select(node.start, node.end),
        },
      ];
      env.menu(pill, entries, entry => {
        if (entry.action) entry.action();
        else env.replace(node.start, node.end, entry.text);
      });
    });
    deletable(pill, cut);
    pill.append(remover(cut, token.text));
    return pill;
  };
  draw.literal = (node, _depth, cut) => {
    const token = /** @type {import("./condition-language.js").Token} */ (
      node.token
    );
    const pill = button("pill pill-literal", token.text, env);
    pill.setAttribute("data-semantic", node.semantic);
    const problem = issueAt(env, node.start, node.end);
    if (problem) pill.setAttribute("data-issue", problem);
    pill.title = "Edit as text";
    pill.addEventListener("click", () => env.select(node.start, node.end));
    deletable(pill, cut);
    pill.append(remover(cut, token.text));
    return pill;
  };
  draw.missing = node => {
    const pill = button("pill pill-slot", node.label ?? "value", env);
    pill.title = `Choose the ${node.label ?? "value"}`;
    pill.addEventListener("click", () => {
      const entries = [
        ...valueEntries(env.terms, node.semantic),
        ...FUNCTIONS.map(info => ({
          text: info.name,
          kind: "function",
          detail: info.detail,
        })),
      ];
      env.menu(pill, entries, entry => {
        const before = env.text.slice(0, node.start);
        const lead =
          node.lead ??
          (before && !/[\s(,]$/.test(before)
            ? " "
            : before.endsWith(",")
              ? " "
              : "");
        const insert =
          entry.kind === "function" ? `${entry.text}()` : entry.text;
        env.replace(node.start, node.end, `${lead}${insert}`);
      });
    });
    return pill;
  };
  draw.not = (node, depth, cut) => {
    const name = /** @type {import("./condition-language.js").Token} */ (
      node.name
    );
    const operand = /** @type {import("./condition-language.js").TreeNode} */ (
      node.operand
    );
    const wrap = make("span", "pill pill-not");
    const word = button("pill-op pill-word", name.text, env);
    word.title = "Click to remove not";
    word.addEventListener("click", () =>
      env.replace(name.start, operand.start, ""),
    );
    wrap.append(word, part(operand, depth, cut));
    return wrap;
  };
  draw.group = (node, depth, cut) => {
    const operand = /** @type {import("./condition-language.js").TreeNode} */ (
      node.operand
    );
    const wrap = make("span", "pill pill-call pill-group");
    wrap.append(cap("start"), part(operand, depth + 1, cut), cap("end"));
    return wrap;
  };
  draw.binary = (node, depth) => {
    const left = /** @type {import("./condition-language.js").TreeNode} */ (
      node.left
    );
    const right = /** @type {import("./condition-language.js").TreeNode} */ (
      node.right
    );
    const name = /** @type {import("./condition-language.js").Token} */ (
      node.name
    );
    const wrap = make("span", "pill-binary");
    const logic = name.kind === "logic";
    const operator = button(
      `pill-op ${logic ? "pill pill-logic" : "pill-compare"}`,
      name.text,
      env,
      true,
    );
    const problem = issueAt(env, name.start, name.end);
    if (problem) operator.setAttribute("data-issue", problem);
    operator.addEventListener("click", () => {
      /** @type {MenuEntry[]} */
      const entries = OPERATORS.filter(info =>
        logic
          ? info.kind === "logic"
          : info.kind !== "logic" &&
            (info.left.includes(left.semantic) || left.semantic === "any"),
      )
        .filter(info => info.symbol !== name.text)
        .map(info => ({
          text: info.symbol,
          kind: info.kind,
          detail: info.detail,
        }));
      env.menu(operator, entries, entry =>
        env.replace(name.start, name.end, entry.text),
      );
    });
    // Removing one side takes the operator with it.
    wrap.append(
      part(left, depth, [left.start, right.start]),
      operator,
      part(right, depth, [left.end, right.end]),
    );
    return wrap;
  };
  draw.call = (node, depth, cut) => {
    const name = /** @type {import("./condition-language.js").Token} */ (
      node.name
    );
    const args = node.args ?? [];
    const wrap = make("span", "pill pill-call");
    const label = button("pill-name", name.text, env, true);
    label.classList.add("pill-cap-host");
    label.prepend(cap("start"));
    const problem = issueAt(env, name.start, name.end);
    if (problem) label.setAttribute("data-issue", problem);
    label.addEventListener("click", () => {
      const entries = FUNCTIONS.filter(info => info.name !== name.text).map(
        info => ({
          text: info.name,
          kind: "function",
          detail: info.detail,
        }),
      );
      env.menu(label, entries, entry =>
        env.replace(name.start, name.end, entry.text),
      );
    });
    deletable(label, cut);
    wrap.append(label);
    // The last argument and the closing bracket stay together on one line.
    const end = make("span", "pill-end");
    args.forEach((arg, index) => {
      if (index) wrap.append(make("span", "pill-sep", ";"));
      /** @type {[number,number]} */
      let range = [arg.start, arg.end];
      if (index > 0) range = [args[index - 1]?.end ?? arg.start, arg.end];
      else if (args.length > 1) range = [arg.start, args[1]?.start ?? arg.end];
      const piece = part(arg, depth + 1, range);
      if (index === args.length - 1) end.append(piece);
      else wrap.append(piece);
    });
    end.append(cap("end"));
    wrap.append(end);
    wrap.append(remover(cut, `${name.text}()`));
    return wrap;
  };
  if (!tree) return [];
  /** @type {HTMLElement[]} */
  const parts = [part(tree, 0, [tree.start, tree.end])];
  const rest = env.text.slice(tree.end);
  if (rest.trim()) parts.push(make("span", "pill-raw", rest.trim()));
  return parts;
};
