/** Variable-aware form controls with mention suggestions and token pills. */
import { iconElement } from "./icons.js";
import { variableInspector } from "./variable-inspector.js";
const templatePattern = /\{\{([^{}]+)\}\}/g;
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
/** A variable an action can read: its name, and what it holds when known.
 * @typedef {string|{name:string,type?:string,icon?:string,tone?:string}} VariableSource
 */
/** The name of a variable source.
 * @param {VariableSource} source
 * @returns {string}
 */
export const variableName = source =>
  typeof source === "string" ? source : source.name;
/** Enhance a text control with @variable mentions.
 * @param {HTMLInputElement|HTMLTextAreaElement} input Portable form value.
 * @param {VariableSource[]} variables Variables available above this action.
 * @returns {HTMLElement} The visible mention editor.
 */
export const variableMentionField = (input, variables) => {
  const sources = variables.map(item => ({
    name: variableName(item),
    type: typeof item === "string" ? "" : (item.type ?? ""),
    icon: typeof item === "string" ? "tag" : (item.icon ?? "tag"),
    tone: typeof item === "string" ? "silver" : (item.tone ?? "silver"),
  }));
  const known = new Map(sources.map(item => [item.name, item]));
  /** Dress an element as a variable pill: the colour and icon of its source, then its name.
   * @param {HTMLElement} pill
   * @param {string} token Text between the braces.
   * @returns {void}
   */
  const paint = (pill, token) => {
    const asked = token.startsWith("ask:");
    const base = /^([^.[|]+)/.exec(token)?.[1] ?? token;
    const source = known.get(base);
    pill.className = "variable-pill action-pill";
    pill.setAttribute("data-tone", asked ? "silver" : (source?.tone ?? "silver"));
    pill.replaceChildren(
      iconElement(asked ? "keyboard" : (source?.icon ?? "tag")),
      asked ? `Ask: ${token.slice(4)}` : token,
    );
  };
  const names = [...new Set(sources.map(item => item.name))].sort();
  const wrapper = make("div", "variable-field");
  const editor = make("div", "variable-editor");
  const menu = make("div", "variable-menu");
  let activeIndex = 0;
  editor.contentEditable = "true";
  editor.setAttribute("role", "textbox");
  editor.setAttribute("aria-label", input.getAttribute("aria-label") ?? input.name);
  editor.setAttribute("aria-multiline", String(input instanceof HTMLTextAreaElement));
  editor.setAttribute("data-placeholder", input.placeholder);
  menu.setAttribute("role", "listbox");
  menu.setAttribute("aria-label", "Results from earlier actions");
  menu.hidden = true;
  // A {{token}} is not a valid URL to the browser, and a hidden control
  // cannot show its own validation message.
  if (input instanceof HTMLInputElement && input.type === "url") input.type = "text";
  input.hidden = true;
  input.before(wrapper);
  const picker = make("button", "variable-picker");
  picker.type = "button";
  picker.setAttribute("aria-label", "Insert a variable");
  picker.setAttribute("aria-haspopup", "listbox");
  picker.title = "Insert a variable";
  picker.textContent = "{x}";
  wrapper.append(editor, picker, menu, input);
  /** True while the editor itself is writing the carrier. */
  let selfWrite = false;
  /** Copy the editor's text and pills into the hidden form value.
   * @returns {void}
   */
  const sync = () => {
    input.value = [...editor.childNodes].map(node => {
      if (node instanceof HTMLElement && node.getAttribute("data-variable"))
        return `{{${node.getAttribute("data-variable")}}}`;
      if (node instanceof HTMLElement && node.tagName === "BR") return "\n";
      return node.textContent ?? "";
    }).join("");
    selfWrite = true;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    selfWrite = false;
  };
  /** Move the caret to the end of the editor.
   * @returns {void}
   */
  const caretEnd = () => {
    const range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
  };
  /** Redraw the editor from a stored value, turning tokens into pills.
   * @param {string} value
   * @returns {void}
   */
  const render = value => {
    const parts = [];
    let cursor = 0;
    for (const match of value.matchAll(templatePattern)) {
      if (match.index > cursor)
        parts.push(document.createTextNode(value.slice(cursor, match.index)));
      const pill = make("span", "variable-pill");
      pill.setAttribute("data-variable", match[1] ?? "");
      pill.contentEditable = "false";
      paint(pill, match[1] ?? "");
      parts.push(pill);
      cursor = match.index + match[0].length;
    }
    if (cursor < value.length)
      parts.push(document.createTextNode(value.slice(cursor)));
    editor.replaceChildren(...parts);
  };
  /** The editor's text with each pill written as one invisible separator.
   * @returns {string}
   */
  const visibleText = () => [...editor.childNodes].map(node => {
    // A pill is one opaque unit; its name must never read as a typed `@name`.
    if (node instanceof HTMLElement && node.getAttribute("data-variable"))
      return "\u2063";
    return node.textContent ?? "";
  }).join("");
  /** Hide the suggestion menu.
   * @returns {void}
   */
  const close = () => {
    menu.hidden = true;
    activeIndex = 0;
    editor.setAttribute("aria-expanded", "false");
  };
  /** Insert a variable token in place of the typed `@fragment`.
   * @param {string} name
   * @returns {void}
   */
  const choose = name => {
    const token = `{{${name}}}`;
    const text = /@[^@{}]*$/.test(visibleText())
      ? input.value.replace(/@[^@{}]*$/, token)
      : `${input.value}${token}`;
    render(text);
    sync();
    close();
    editor.focus();
    caretEnd();
  };
  /** Offer variables matching the `@fragment` being typed.
   * @returns {void}
   */
  const suggest = () => {
    const match = /@([^@{}]*)$/.exec(visibleText());
    const fragment = match?.[1]?.toLowerCase() ?? "";
    const shown = match
      ? names.filter(name => name.toLowerCase().includes(fragment)).slice(0, 8)
      : [];
    activeIndex = 0;
    menu.replaceChildren(...shown.map((name, index) => {
      const option = document.createElement("button");
      const pill = make("span", "variable-pill");
      option.type = "button";
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", String(index === activeIndex));
      paint(pill, name);
      option.append(pill);
      option.addEventListener("pointerdown", event => {
        event.preventDefault();
        choose(name);
      });
      option.addEventListener("pointerenter", () => {
        activeIndex = index;
        for (const [optionIndex, button] of [...menu.querySelectorAll("button")].entries())
          button.setAttribute("aria-selected", String(optionIndex === activeIndex));
      });
      return option;
    }));
    menu.hidden = shown.length === 0;
    editor.setAttribute("aria-expanded", String(shown.length > 0));
  };
  editor.addEventListener("input", () => {
    sync();
    if (/\{\{[^{}]+\}\}/.test(editor.textContent ?? "")) {
      render(input.value);
      caretEnd();
    }
    suggest();
  });
  const popover = make("div", "variable-popover");
  popover.hidden = true;
  popover.setAttribute("role", "dialog");
  wrapper.append(popover);
  /** Open the inspector for one variable pill.
   * @param {HTMLElement} pill
   * @returns {void}
   */
  const openInspector = pill => {
    const token = pill.getAttribute("data-variable") ?? "";
    const base = /^([^.[|]+)/.exec(token)?.[1] ?? token;
    const source = known.get(base);
    popover.replaceChildren(
      variableInspector({
        token,
        type: source?.type ?? "",
        icon: source?.icon ?? "tag",
        tone: source?.tone ?? "silver",
        onChange: next => {
          pill.setAttribute("data-variable", next);
          paint(pill, next);
          sync();
        },
        onClear: () => {
          pill.remove();
          popover.hidden = true;
          sync();
        },
        onReveal: name => {
          popover.hidden = true;
          wrapper.dispatchEvent(
            new CustomEvent("variable-reveal", { bubbles: true, detail: { name } }),
          );
        },
      }),
    );
    popover.hidden = false;
  };
  editor.addEventListener("click", event => {
    const target = event.target;
    if (target instanceof HTMLElement && target.getAttribute("data-variable")) openInspector(target);
    else popover.hidden = true;
  });
  picker.addEventListener("click", () => {
    if (!menu.hidden) {
      close();
      return;
    }
    const ask = document.createElement("button");
    ask.type = "button";
    ask.setAttribute("role", "option");
    ask.append(iconElement("keyboard"), "Ask Each Time");
    ask.addEventListener("pointerdown", event => {
      event.preventDefault();
      choose(`ask:${input.getAttribute("aria-label") ?? input.name}`);
    });
    menu.replaceChildren(ask, ...names.map(name => {
      const option = document.createElement("button");
      const pill = make("span", "variable-pill");
      option.type = "button";
      option.setAttribute("role", "option");
      paint(pill, name);
      option.append(pill);
      option.addEventListener("pointerdown", event => {
        event.preventDefault();
        choose(name);
      });
      return option;
    }));
    menu.hidden = false;
  });
  editor.addEventListener("blur", () => window.requestAnimationFrame(close));
  editor.addEventListener("keydown", event => {
    if (event.key === "Escape") close();
    if (!menu.hidden && ["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      const options = [...menu.querySelectorAll("button")];
      const direction = event.key === "ArrowDown" ? 1 : -1;
      activeIndex = (activeIndex + direction + options.length) % options.length;
      for (const [index, option] of options.entries())
        option.setAttribute("aria-selected", String(index === activeIndex));
    }
    if (event.key === "Enter" && !menu.hidden) {
      const options = [...menu.querySelectorAll("button")];
      const active = options[activeIndex];
      if (active instanceof HTMLButtonElement) {
        event.preventDefault();
        active.dispatchEvent(new PointerEvent("pointerdown"));
      }
    }
  });
  // Programmatic writes (a picked selector, a restored draft) reach the carrier
  // without the editor's own input event, so redraw the pills for those.
  input.addEventListener("input", () => {
    if (!selfWrite) render(input.value);
  });
  render(input.value);
  editor.setAttribute("aria-expanded", "false");
  return wrapper;
};
