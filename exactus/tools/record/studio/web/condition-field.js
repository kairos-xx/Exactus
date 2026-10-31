/** A text field for conditions that colours, checks and completes them.
 *
 * Connections and pauses share one condition language, described in
 * `condition-language.js`. This is the one editor for it. The field paints each
 * token in the colour of its kind, underlines what the language rejects and says
 * why, and suggests only what may come next: after a number, comparisons; after
 * `>`, numbers; inside `contains(`, text. Plain DOM, like the other editor
 * modules.
 */
import { analyse, insertionFor, suggestNext } from "./condition-language.js";
import { renderPills } from "./condition-pills.js";
/**
 * @typedef {object} ConditionSource What the field reads when it needs data.
 * @property {() => ConditionTerm[]} terms Names the project offers.
 * @property {() => string[]} selectors Names of the stored selectors.
 */
/** Most suggestions shown at once. */
const LIMIT = 8;
/** The identifier fragment that ends at the caret.
 * @param {string} text
 * @param {number} caret
 * @returns {{start:number,fragment:string}}
 */
export const tokenAt = (text, caret) => {
  const match = /[A-Za-z_][A-Za-z0-9_]*$/.exec(text.slice(0, caret));
  return match
    ? { start: caret - match[0].length, fragment: match[0] }
    : { start: caret, fragment: "" };
};
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
let sequence = 0;
/** Turn a text input into a condition field.
 * @param {HTMLInputElement} input The field to enhance, already in the page.
 * @param {ConditionSource} source Where its names come from.
 * @returns {void}
 */
export const attachConditionField = (input, source) => {
  sequence += 1;
  const listId = `condition-options-${sequence}`;
  const wrapper = make("span", "condition-field");
  const editor = make("span", "condition-editor");
  const paint = make("span", "condition-paint");
  paint.setAttribute("aria-hidden", "true");
  const pills = make("div", "condition-pills");
  pills.setAttribute("role", "group");
  pills.setAttribute("aria-label", "Condition");
  const menu = make("div", "condition-menu");
  menu.setAttribute("role", "dialog");
  menu.setAttribute("aria-label", "Choose a condition token");
  menu.hidden = true;
  const toggle = /** @type {HTMLButtonElement} */ (
    make("button", "condition-mode", "Edit as text")
  );
  toggle.type = "button";
  toggle.setAttribute("aria-pressed", "false");
  const list = make("ul", "condition-options");
  list.id = listId;
  list.setAttribute("role", "listbox");
  list.hidden = true;
  const issues = make("ul", "condition-issues");
  issues.setAttribute("role", "status");
  issues.hidden = true;
  input.replaceWith(wrapper);
  editor.append(input, paint);
  wrapper.append(pills, editor, list, menu, issues, toggle);
  wrapper.setAttribute("data-mode", "pills");
  editor.setAttribute("data-collapsed", "");
  input.classList.add("condition-input");
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-controls", listId);
  input.setAttribute("aria-expanded", "false");
  input.autocomplete = "off";
  input.spellcheck = false;
  /** @type {import("./condition-language.js").Suggestion[]} */
  let shown = [];
  let active = -1;
  /** Show or hide the suggestion list.
   * @param {boolean} open Whether the list should be visible.
   * @returns {void}
   */
  const setOpen = open => {
    list.hidden = !open;
    input.setAttribute("aria-expanded", String(open));
    if (!open) {
      input.removeAttribute("aria-activedescendant");
      return;
    }
    // Open upward when the panel's edge would clip the list below.
    const edge = input.closest(".panel")?.getBoundingClientRect().bottom;
    const room =
      (edge ?? window.innerHeight) - input.getBoundingClientRect().bottom;
    list.classList.toggle("above", room < list.offsetHeight + 8);
  };
  /** Mark the active suggestion for assistive technology.
   * @returns {void}
   */
  const highlight = () => {
    list.querySelectorAll("[role=option]").forEach((option, index) => {
      option.setAttribute("aria-selected", String(index === active));
      if (index === active)
        input.setAttribute("aria-activedescendant", option.id);
    });
  };
  /** The pill view is built further down, once the menu and mode exist.
   * @type {{pills:(result:ReturnType<typeof analyse>)=>void}}
   */
  const view = { pills: () => undefined };
  /** Draw the tokens under the transparent input text, in step with its scroll.
   * @returns {void}
   */
  const draw = () => {
    const terms = source.terms();
    const result = analyse(input.value, terms, source.selectors());
    const style = getComputedStyle(input);
    paint.style.lineHeight = `${input.getBoundingClientRect().height}px`;
    paint.style.paddingLeft = `${Number.parseFloat(style.paddingLeft) + Number.parseFloat(style.borderLeftWidth)}px`;
    const parts = [];
    let at = 0;
    for (const token of result.tokens) {
      if (token.start > at)
        parts.push(document.createTextNode(input.value.slice(at, token.start)));
      const span = make(
        "span",
        `condition-token condition-${token.kind}`,
        token.text,
      );
      const problem = result.issues.find(
        issue =>
          issue.start <= token.start &&
          issue.end >= token.end &&
          issue.end > issue.start,
      );
      if (problem) span.setAttribute("data-issue", problem.level);
      parts.push(span);
      at = token.end;
    }
    if (at < input.value.length)
      parts.push(document.createTextNode(input.value.slice(at)));
    paint.replaceChildren(...parts);
    paint.scrollLeft = input.scrollLeft;
    issues.replaceChildren(
      ...result.issues.slice(0, 3).map(issue => {
        const item = make("li", "condition-issue", issue.message);
        item.setAttribute("data-level", issue.level);
        return item;
      }),
    );
    // An empty field is not yet wrong; the issue list waits for some text.
    issues.hidden = !input.value.trim() || !result.issues.length;
    view.pills(result);
    input.setAttribute(
      "aria-invalid",
      String(
        result.issues.some(issue => issue.level === "error") &&
          Boolean(input.value.trim()),
      ),
    );
  };
  /** Insert a suggestion at the caret.
   * @param {import("./condition-language.js").Suggestion} item Chosen suggestion.
   * @returns {void}
   */
  const choose = item => {
    const caret = input.selectionStart ?? input.value.length;
    const { start } = tokenAt(input.value, caret);
    const before = input.value.slice(0, start);
    const text = insertionFor(before, item);
    input.value = `${before}${text}${input.value.slice(caret)}`;
    const end = before.length + text.length;
    input.setSelectionRange(end, end);
    setOpen(false);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus();
  };
  /** Recompute suggestions for the caret position.
   * @returns {void}
   */
  const suggest = () => {
    const caret = input.selectionStart ?? input.value.length;
    const { start, fragment } = tokenAt(input.value, caret);
    const before = input.value.slice(0, start);
    shown = suggestNext(before, fragment, source.terms()).slice(0, LIMIT);
    active = shown.length ? 0 : -1;
    list.replaceChildren(
      ...shown.map((item, index) => {
        const option = make("li", "condition-option");
        option.id = `${listId}-${index}`;
        option.setAttribute("role", "option");
        option.append(
          make("strong", `condition-token condition-${item.kind}`, item.text),
          make(
            "small",
            "",
            item.type ? `${item.detail} · ${item.type}` : item.detail,
          ),
        );
        option.addEventListener("pointerdown", event => {
          event.preventDefault();
          choose(item);
        });
        return option;
      }),
    );
    setOpen(shown.length > 0);
    highlight();
  };
  /** Show a dropdown of choices under a pill.
   * @param {HTMLElement} anchor
   * @param {import("./condition-pills.js").MenuEntry[]} entries
   * @param {(entry:import("./condition-pills.js").MenuEntry)=>void} pick
   * @returns {void}
   */
  const openMenu = (anchor, entries, pick) => {
    const search = /** @type {HTMLInputElement} */ (
      make("input", "condition-menu-search")
    );
    search.type = "search";
    search.placeholder = "Search tokens";
    search.setAttribute("aria-label", "Search condition tokens");
    const choices = make("div", "condition-menu-choices");
    /** Draw only entries matching the current autocomplete query.
     * @returns {void}
     */
    const filter = () => {
      const query = search.value.trim().toLowerCase();
      const matches = entries.filter(entry =>
        `${entry.text} ${entry.detail}`.toLowerCase().includes(query),
      );
      choices.replaceChildren(
        ...matches.map(entry => {
        const item = /** @type {HTMLButtonElement} */ (
          make("button", "condition-menu-item")
        );
        item.type = "button";
        item.append(
          make("strong", `condition-token condition-${entry.kind}`, entry.text),
          make("small", "", entry.detail),
        );
        item.addEventListener("click", () => {
          menu.hidden = true;
          pick(entry);
        });
        return item;
        }),
      );
    };
    search.addEventListener("input", filter);
    filter();
    menu.replaceChildren(search, choices);
    menu.hidden = false;
    const box = wrapper.getBoundingClientRect();
    const at = anchor.getBoundingClientRect();
    const left = Math.max(
      0,
      Math.min(at.left - box.left, box.width - menu.offsetWidth),
    );
    menu.style.left = `${left}px`;
    const room =
      (input.closest(".panel")?.getBoundingClientRect().bottom ??
        window.innerHeight) - at.bottom;
    const below = room >= menu.offsetHeight + 8;
    menu.style.top = below
      ? `${at.bottom - box.top + 2}px`
      : `${at.top - box.top - menu.offsetHeight - 2}px`;
    search.focus();
  };
  menu.addEventListener("keydown", event => {
    const items = /** @type {HTMLElement[]} */ ([
      ...menu.querySelectorAll("button"),
    ]);
    const at = items.indexOf(
      /** @type {HTMLElement} */ (document.activeElement),
    );
    if (event.key === "ArrowDown") items[(at + 1) % items.length]?.focus();
    else if (event.key === "ArrowUp")
      items[(at - 1 + items.length) % items.length]?.focus();
    else if (event.key === "Escape") {
      menu.hidden = true;
      pills.querySelector("button")?.focus();
    } else return;
    event.preventDefault();
  });
  document.addEventListener("pointerdown", event => {
    if (!menu.hidden && !menu.contains(/** @type {Node} */ (event.target)))
      menu.hidden = true;
  });
  /** Switch between the pill view and plain text editing.
   * @param {"pills"|"text"} mode Mode to switch to.
   * @returns {void}
   */
  const setMode = mode => {
    wrapper.setAttribute("data-mode", mode);
    toggle.textContent = mode === "pills" ? "Edit as text" : "Show as pills";
    toggle.setAttribute("aria-pressed", String(mode === "text"));
    if (mode === "text") editor.removeAttribute("data-collapsed");
    else editor.setAttribute("data-collapsed", "");
    menu.hidden = true;
    setOpen(false);
  };
  toggle.addEventListener("click", () => {
    const next =
      wrapper.getAttribute("data-mode") === "pills" ? "text" : "pills";
    setMode(next);
    if (next === "text") input.focus();
  });
  /** Change a range of the text; the pills follow from the new text.
   * @param {number} start
   * @param {number} end
   * @param {string} text
   */
  const replace = (start, end, text) => {
    const value = `${input.value.slice(0, start)}${text}${input.value.slice(end)}`;
    input.value = value
      .replace(/ {2,}/g, " ")
      .replace(/\(\s+/g, "(")
      .replace(/\s+\)/g, ")")
      .replace(/,\s*\)/g, ")")
      .trim();
    input.dispatchEvent(new Event("input", { bubbles: true }));
  };
  /** Open context-aware suggestions at the end of the condition.
   * @param {HTMLElement} anchor Where to place the chooser.
   * @returns {void}
   */
  const addToken = anchor => {
    const value = input.value;
    const options = suggestNext(value, "", source.terms()).map(item => ({
      text: item.text,
      kind: item.kind,
      detail: item.detail,
    }));
    openMenu(anchor, options, entry => {
      const insert =
        entry.kind === "function"
          ? `${/^[\s(]?$/.test(value.slice(-1)) ? "" : " "}${entry.text}()`
          : insertionFor(value, {
              text: entry.text,
              kind: /** @type {import("./condition-language.js").TokenKind} */ (
                entry.kind
              ),
              detail: entry.detail,
            });
      input.value = `${value}${insert}`.trimEnd();
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
  };
  pills.tabIndex = 0;
  pills.title = "Click empty space to add another token";
  pills.addEventListener("click", event => {
    if (event.target === pills) addToken(pills);
  });
  pills.addEventListener("keydown", event => {
    if (event.target !== pills || !["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    addToken(pills);
  });
  view.pills = result => {
    const disabled = input.disabled;
    wrapper.toggleAttribute("data-disabled", disabled);
    /** @type {import("./condition-pills.js").PillEnv} */
    const env = {
      text: input.value,
      terms: source.terms(),
      issues: result.issues,
      disabled,
      replace,
      select: (start, end) => {
        setMode("text");
        input.focus();
        input.setSelectionRange(start, end);
      },
      menu: openMenu,
    };
    const add = /** @type {HTMLButtonElement} */ (
      make("button", "pill pill-add", "+")
    );
    add.type = "button";
    add.disabled = disabled;
    add.title = "Add to the condition";
    add.setAttribute("aria-label", "Add to the condition");
    add.setAttribute("aria-haspopup", "dialog");
    add.addEventListener("click", () => addToken(add));
    const parts = renderPills(result.tree, env);
    if (!parts.length)
      parts.push(
        make(
          "span",
          "pill-hint",
          disabled ? "Not used for this kind of connection" : "Add a condition",
        ),
      );
    pills.replaceChildren(...parts, ...(result.tree ? [] : [add]));
  };
  new MutationObserver(() => draw()).observe(input, {
    attributes: true,
    attributeFilter: ["disabled"],
  });
  /** Repaint tokens and refresh suggestions.
   * @returns {void}
   */
  const refresh = () => {
    draw();
    if (wrapper.getAttribute("data-mode") === "text") suggest();
  };
  input.addEventListener("input", refresh);
  input.addEventListener("focus", () => {
    // Something focused the hidden text, such as form validation: show it.
    if (wrapper.getAttribute("data-mode") === "pills") setMode("text");
    refresh();
  });
  input.addEventListener("click", suggest);
  input.addEventListener("scroll", () => {
    paint.scrollLeft = input.scrollLeft;
  });
  input.addEventListener("blur", () => setOpen(false));
  input.addEventListener("keydown", event => {
    if (event.key === " " && event.ctrlKey) {
      event.preventDefault();
      suggest();
      return;
    }
    if (list.hidden || !shown.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      active = (active + step + shown.length) % shown.length;
      highlight();
    } else if (event.key === "Enter" || event.key === "Tab") {
      const item = shown[active];
      if (!item) return;
      event.preventDefault();
      choose(item);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
    }
  });
  draw();
};
