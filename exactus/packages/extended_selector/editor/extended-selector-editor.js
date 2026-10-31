/**
 * Formula-style structured editor for ExtendedSelector.
 *
 * The visible surface is directly editable. Calls are nested capsules bounded
 * by parenthesis shells, operators are dropdown controls, and caret stops are
 * inserted between every structural token so the caret can be positioned at
 * every expression boundary.
 *
 * @typedef {import("./extended-selector.js").ExtendedSelector} Engine
 * @typedef {import("./extended-selector.js").SelectorDiagnostic} SelectorDiagnostic
 * @typedef {{kind: "atom", value: string}} EditorAtom
 * @typedef {{kind: "call", name: string, children: EditorNode[]}} EditorCall
 * @typedef {EditorAtom | EditorCall} EditorNode
 * @typedef {{engine?: Engine | null, selectors?: string[]}} EditorOptions
 */
import ExtendedSelector from "./extended-selector.js";
/**
 * Structured expression editor bound to a hidden textarea.
 */
export class ExtendedSelectorEditor extends EventTarget {
  static OPERATORS = Object.freeze([
    "and",
    "or",
    "not",
    "nand",
    "nor",
    "xor",
    "xnor",
    "apply",
    "has",
    "children",
    "child",
    "sibling",
    "siblings",
    "prev",
    "next",
    "parent",
    "ancestor",
    "closest",
    "before",
    "after",
    "any",
    "all",
    "none",
    "left_of",
    "right_of",
    "above",
    "below",
    "overlaps",
    "inside",
    "near",
    "aligned_left",
    "aligned_center_x",
    "shadow",
    "slot",
    "pseudo",
    "sort",
    "nearest",
    "nearest_above",
    "nearest_below",
    "nearest_left",
    "nearest_right",
    "media",
  ]);
  static PREDICATES = Object.freeze([
    "textContent",
    "innerText",
    "innerHTML",
    "normalizedText",
    "value",
    "role",
    "accessible_name",
    "visible",
    "rendered",
    "enabled",
    "disabled",
    "focused",
    "checked",
    "selected",
    "editable",
    "clickable",
    "draggable",
    "scrollable",
    "in_viewport",
    "viewport_ratio",
    "above_viewport",
    "below_viewport",
    "width",
    "height",
    "area",
    "aspect_ratio",
    "x_abs",
    "y_abs",
    "right_abs",
    "bottom_abs",
    "center_x_abs",
    "center_y_abs",
    "x_view",
    "y_view",
    "children",
    "descendants",
    "siblings",
    "index",
    "index_of_type",
    "depth",
    "text_nodes",
    "scrollLeft",
    "scrollTop",
    "scrollWidth",
    "scrollHeight",
    "scroll_x",
    "scroll_y",
    "scroll_x_max",
    "scroll_y_max",
    "scroll_x_percent",
    "scroll_y_percent",
  ]);
  static PSEUDOS = Object.freeze([
    ":hover",
    ":focus",
    ":focus-visible",
    ":focus-within",
    ":checked",
    ":disabled",
    ":enabled",
    ":required",
    ":optional",
    ":first-child",
    ":last-child",
    ":only-child",
    ":nth-child(2)",
    ":not()",
    ":has()",
    ":is()",
    ":where()",
  ]);
  static STARTERS = Object.freeze([
    "#id",
    ".class",
    "button",
    "input",
    "[role=\"button\"]",
    "[aria-label=\"…\"]",
    "[data-testid=\"…\"]",
    "[normalizedText*=\"…\"]",
    "[visible=true]",
  ]);
  /**
   * Create an editor bound to `target`, replacing it with an editable
   * structured surface while keeping the textarea as the value carrier.
   *
   * @param {HTMLTextAreaElement} target
   * @param {EditorOptions} [options]
   * @throws {TypeError} When `target` is not a textarea element.
   */
  constructor(target, options = {}) {
    super();
    if (!(target instanceof HTMLTextAreaElement))
      throw new TypeError("target must be a textarea.");
    this.target = target;
    this.options = {
      engine: null,
      ...options,
    };
    this.surface = document.createElement("div");
    this.surface.className = "ese-editor";
    this.surface.setAttribute("role", "textbox");
    this.surface.setAttribute("aria-multiline", "true");
    this.surface.setAttribute("aria-label", "Selector expression");
    this.popup = document.createElement("div");
    this.popup.className = "ese-options";
    this.popup.setAttribute("role", "listbox");
    this.popup.setAttribute("aria-label", "Selector suggestions");
    this.popup.hidden = true;
    target.hidden = true;
    target.after(this.surface);
    document.body.append(this.popup);
    this.surface.addEventListener("input", event => this.onInput(event));
    this.surface.addEventListener("keydown", event => this.onKeydown(event));
    this.surface.addEventListener("click", event => this.onClick(event));
    this.surface.addEventListener("focusin", event =>
      this.offer(/** @type {FocusEvent} */ (event)),
    );
    this.render();
  }
  /**
   * Serialized expression currently held by the hidden textarea.
   *
   * @returns {string}
   */
  get value() {
    return this.target.value;
  }
  /**
   * Replace the expression and re-render the structured surface.
   *
   * @param {string} value
   */
  set value(value) {
    this.target.value = value;
    this.render();
  }
  /**
   * Attach or detach an engine used for live diagnostics.
   *
   * @param {Engine | null} engine
   * @returns {this}
   */
  setEngine(engine) {
    this.options.engine = engine;
    this.validate();
    return this;
  }
  /**
   * Split a top-level argument list on commas, ignoring commas nested inside
   * parentheses, brackets, or quoted strings.
   *
   * @param {string} value
   * @returns {string[]}
   */
  static split = value => {
    /** @type {string[]} */
    const parts = [];
    let depth = 0;
    let quote = "";
    let start = 0;
    [...value].forEach((char, index) => {
      if (quote) {
        if (char === quote && value[index - 1] !== "\\") quote = "";
      } else if (`"'`.includes(char)) quote = char;
      else if ("([".includes(char)) depth += 1;
      else if (")]".includes(char)) depth -= 1;
      else if (!depth && char === ",") {
        parts.push(value.slice(start, index).trim());
        start = index + 1;
      }
    });
    parts.push(value.slice(start).trim());
    return parts.filter(Boolean);
  };
  /**
   * Parse an expression string into a shallow atom/call node tree.
   *
   * @param {string} source
   * @returns {EditorNode}
   */
  static parse = source => {
    const value = source.trim();
    const call = /^([a-z_][\w-]*)\(([\s\S]*)\)$/i.exec(value);
    return call
      ? {
          kind: "call",
          name: /** @type {string} */ (call[1]).toLowerCase(),
          children: ExtendedSelectorEditor.split(
            /** @type {string} */
            (call[2]),
          ).map(ExtendedSelectorEditor.parse),
        }
      : {
          kind: "atom",
          value,
        };
  };
  /**
   * Build a namespaced element with a class and optional text content.
   *
   * @template {keyof HTMLElementTagNameMap} T
   * @param {T} tag
   * @param {string} className
   * @param {string} [text]
   * @returns {HTMLElementTagNameMap[T]}
   */
  static el = (tag, className, text = "") => {
    const node = document.createElement(tag);
    node.className = className;
    node.textContent = text;
    return node;
  };
  /**
   * Create an editable caret stop used between structural tokens.
   *
   * @returns {HTMLSpanElement}
   */
  static caret = () => {
    const node = ExtendedSelectorEditor.el("span", "ese-caret");
    node.contentEditable = "true";
    node.spellcheck = false;
    node.setAttribute("data-role", "caret");
    node.setAttribute("aria-label", "expression insertion point");
    return node;
  };
  /**
   * Create the operator dropdown control shown at the head of a call capsule.
   *
   * @param {string} name
   * @returns {HTMLSpanElement}
   */
  static operator = name => {
    const wrap = ExtendedSelectorEditor.el("span", "ese-op-wrap");
    const button = ExtendedSelectorEditor.el("button", "ese-operator", name);
    button.type = "button";
    button.setAttribute("data-role", "operator");
    button.setAttribute("aria-haspopup", "listbox");
    button.append(ExtendedSelectorEditor.el("span", "ese-arrow", "▾"));
    wrap.append(button);
    return wrap;
  };
  /**
   * Create an editable atom capsule split into selector and predicate spans.
   *
   * @param {string} value
   * @returns {HTMLSpanElement}
   */
  static atom = value => {
    const node = ExtendedSelectorEditor.el("span", "ese-atom");
    node.contentEditable = "true";
    node.spellcheck = false;
    node.setAttribute("data-role", "atom");
    const match = /^([^[]*)(.*)$/.exec(value);
    node.append(
      ExtendedSelectorEditor.el("span", "ese-selector", match?.[1] || value),
    );
    if (match?.[2])
      node.append(ExtendedSelectorEditor.el("span", "ese-predicate", match[2]));
    return node;
  };
  /**
   * Render a parsed node into DOM, recursing for nested calls.
   *
   * @param {EditorNode} node
   * @param {number} [depth]
   * @returns {HTMLSpanElement}
   */
  static renderNode = (node, depth = 0) => {
    if (node.kind === "atom") return ExtendedSelectorEditor.atom(node.value);
    const call = ExtendedSelectorEditor.el("span", "ese-call");
    call.setAttribute("data-operator", node.name);
    call.style.setProperty("--ese-depth", String(depth));
    const open = ExtendedSelectorEditor.el("span", "ese-paren ese-open", "(");
    open.setAttribute("data-role", "paren");
    const close = ExtendedSelectorEditor.el("span", "ese-paren ese-close", ")");
    close.setAttribute("data-role", "paren");
    const args = ExtendedSelectorEditor.el("span", "ese-args");
    args.append(ExtendedSelectorEditor.caret());
    node.children.forEach((child, index) => {
      if (index) {
        args.append(ExtendedSelectorEditor.el("span", "ese-separator", ","));
        args.append(ExtendedSelectorEditor.caret());
      }
      args.append(ExtendedSelectorEditor.renderNode(child, depth + 1));
      args.append(ExtendedSelectorEditor.caret());
    });
    call.append(ExtendedSelectorEditor.operator(node.name), open, args, close);
    return call;
  };
  /**
   * Rebuild the editable surface from the textarea value and revalidate.
   *
   * @returns {this}
   */
  render() {
    /** @type {EditorNode} */
    let ast;
    try {
      ast = ExtendedSelectorEditor.parse(this.value);
    } catch {
      ast = {
        kind: "atom",
        value: this.value,
      };
    }
    this.surface.replaceChildren(
      ExtendedSelectorEditor.caret(),
      ExtendedSelectorEditor.renderNode(ast),
      ExtendedSelectorEditor.caret(),
    );
    this.validate();
    return this;
  }
  /**
   * Walk the surface DOM and fold capsules back into expression text.
   *
   * @param {HTMLElement} [node]
   * @returns {string}
   */
  serialize(node = this.surface) {
    /**
     * Keep only structural children that carry expression meaning.
     *
     * @param {HTMLElement} child
     * @returns {boolean}
     */
    const kept = child =>
      child.classList.contains("ese-call") ||
      child.classList.contains("ese-atom") ||
      child.classList.contains("ese-caret") &&
        Boolean((child.textContent ?? "").trim());
    /**
     * Serialize one structural child into its text fragment.
     *
     * @param {HTMLElement} child
     * @returns {string}
     */
    const part = child =>
      child.classList.contains("ese-caret")
        ? (child.textContent ?? "").trim()
        : this.serialize(child);
    if (node.classList.contains("ese-call")) {
      const name = node.getAttribute("data-operator") ?? "";
      const args = [
        ...(node.querySelector(":scope > .ese-args")?.children ?? []),
      ]
        .map(child => /** @type {HTMLElement} */ (child))
        .filter(kept)
        .map(part)
        .filter(Boolean);
      return `${name}(${args.join(", ")})`;
    }
    if (node.classList.contains("ese-atom"))
      return (node.textContent ?? "").trim();
    return [...node.children]
      .map(child => /** @type {HTMLElement} */ (child))
      .filter(kept)
      .map(part)
      .filter(Boolean)
      .join(" ");
  }
  /**
   * Push the serialized surface into the textarea and emit input/change.
   *
   * @returns {void}
   */
  sync() {
    this.target.value = this.serialize();
    this.target.dispatchEvent(
      new Event("input", {
        bubbles: true,
      }),
    );
    this.validate();
    this.dispatchEvent(
      new CustomEvent("change", {
        detail: {
          value: this.value,
          diagnostics: this.options.engine?.lint?.(this.value) ?? [],
        },
      }),
    );
  }
  /**
   * Lint the current expression and reflect validity on the surface.
   *
   * @returns {SelectorDiagnostic[]}
   */
  validate() {
    const diagnostics = this.options.engine?.lint?.(this.value) ?? [];
    this.surface.toggleAttribute("data-invalid", Boolean(diagnostics.length));
    this.surface.title = diagnostics[0]
      ? ExtendedSelector.formatDiagnostic(diagnostics[0])
      : "";
    return diagnostics;
  }
  /**
   * Open the operator dropdown or toggle a call's active state on click.
   *
   * @param {MouseEvent} event
   * @returns {void}
   */
  onClick(event) {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const operator = target.closest(".ese-operator");
    if (operator) {
      event.preventDefault();
      this.showOperators(/** @type {HTMLElement} */ (operator));
      return;
    }
    const editable = target.closest(".ese-atom,.ese-caret");
    if (editable) this.offerAt(/** @type {HTMLElement} */ (editable));
    target
      .closest(".ese-paren")
      ?.closest(".ese-call")
      ?.classList.toggle("ese-active");
  }
  /**
   * Reserialize after edits and offer operator completions at filled carets.
   *
   * @param {Event} event
   * @returns {void}
   */
  onInput(event) {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const editable = target.closest(".ese-atom,.ese-caret");
    if (!editable) return;
    this.sync();
    this.offerAt(/** @type {HTMLElement} */ (editable));
  }
  /** Offer syntax valid for the focused editable region.
   * @param {FocusEvent} event
   * @returns {void}
   */
  offer(event) {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const editable = target.closest(".ese-atom,.ese-caret");
    if (editable) this.offerAt(/** @type {HTMLElement} */ (editable));
  }
  /** Route completion to an expression slot or a selector atom.
   * @param {HTMLElement} editable
   * @returns {void}
   */
  offerAt(editable) {
    if (editable.classList.contains("ese-caret"))
      this.showExpressionOptions(editable);
    else this.showAtomOptions(editable);
  }
  /**
   * Handle Enter-to-pick and symmetric bracket/quote insertion.
   *
   * @param {KeyboardEvent} event
   * @returns {void}
   */
  onKeydown(event) {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (!target.closest(".ese-atom,.ese-caret")) return;
    if (event.key === "Enter") {
      event.preventDefault();
      this.popup
        .querySelector("button")
        ?.dispatchEvent(
          new MouseEvent("mousedown", { bubbles: true, cancelable: true }),
        );
      return;
    }
    if (event.key === "Escape" && !this.popup.hidden) {
      event.preventDefault();
      this.popup.hidden = true;
      return;
    }
    const pairs = /** @type {Record<string, string>} */ ({
      "[": "]",
      "(": ")",
      '"': '"',
      "'": "'",
    });
    const close = pairs[event.key];
    if (!close) return;
    event.preventDefault();
    const selection = window.getSelection();
    const selected = selection?.toString() ?? "";
    document.execCommand(
      "insertText",
      false,
      `${event.key}${selected}${close}`,
    );
    if (!selected && selection?.focusNode) {
      selection.modify("move", "backward", "character");
      queueMicrotask(() =>
        this.offerAt(/** @type {HTMLElement} */ (target.closest(".ese-atom,.ese-caret"))),
      );
    }
  }
  /**
   * Show the full operator list anchored on an operator button.
   *
   * @param {HTMLElement} anchor
   * @returns {void}
   */
  showOperators(anchor) {
    this.showOptions(anchor, ExtendedSelectorEditor.OPERATORS, operator => {
      const call = anchor.closest(".ese-call");
      if (!call) return;
      call.setAttribute("data-operator", operator);
      if (anchor.firstChild) anchor.firstChild.textContent = operator;
      this.sync();
    });
  }
  /**
   * Offer operators filtered by caret text and wrap the caret in a call.
   *
   * @param {HTMLElement} anchor
   * @returns {void}
   */
  showExpressionOptions(anchor) {
    const needle = (anchor.textContent ?? "").trim().toLowerCase();
    this.showOptions(
      anchor,
      ExtendedSelectorEditor.OPERATORS.filter(operator =>
        operator.startsWith(needle),
      ),
      operator => {
        anchor.textContent = "";
        const call = ExtendedSelectorEditor.el("span", "ese-call");
        call.setAttribute("data-operator", operator);
        const open = ExtendedSelectorEditor.el(
          "span",
          "ese-paren ese-open",
          "(",
        );
        open.setAttribute("data-role", "paren");
        const close = ExtendedSelectorEditor.el(
          "span",
          "ese-paren ese-close",
          ")",
        );
        close.setAttribute("data-role", "paren");
        const args = ExtendedSelectorEditor.el("span", "ese-args");
        const slot = ExtendedSelectorEditor.caret();
        args.append(slot);
        call.append(
          ExtendedSelectorEditor.operator(operator),
          open,
          args,
          close,
        );
        anchor.replaceWith(call);
        this.sync();
        ExtendedSelectorEditor.focus(slot);
      },
    );
  }
  /** Offer CSS, pseudo-class, extended predicate and saved-selector syntax.
   * @param {HTMLElement} anchor
   * @returns {void}
   */
  showAtomOptions(anchor) {
    const value = anchor.textContent ?? "";
    const caret = ExtendedSelectorEditor.caretOffset(anchor);
    const before = value.slice(0, caret);
    const pseudo = /:[\w-]*$/.exec(before);
    const predicate = /\[([\w:-]*)$/.exec(before);
    const reference = /\[extended-selector=([\x22\x27])([^\x22\x27]*)$/.exec(before);
    let start = caret;
    /** @type {string[]} */
    let values = [];
    if (reference) {
      const [, quote = '"', typed = ""] = reference;
      start = caret - typed.length;
      values = (this.options.selectors ?? []).map(
        name => `${name}${quote}]`,
      );
    } else if (pseudo) {
      start = caret - pseudo[0].length;
      values = ExtendedSelectorEditor.PSEUDOS.filter(option =>
        option.startsWith(pseudo[0] ?? ""),
      );
    } else if (predicate) {
      start = caret - predicate[0].length;
      const needle = (predicate[1] ?? "").toLowerCase();
      values = ExtendedSelectorEditor.PREDICATES.filter(name =>
        name.toLowerCase().startsWith(needle),
      ).map(name => ExtendedSelectorEditor.predicateTemplate(name));
    } else if (!value.trim()) {
      values = [
        ...ExtendedSelectorEditor.STARTERS,
        ...(this.options.selectors ?? []).map(
          name => `[extended-selector="${name}"]`,
        ),
      ];
      start = 0;
    }
    this.showOptions(anchor, values, choice => {
      let suffix = value.slice(caret);
      if (choice.endsWith("]") && suffix.startsWith("]"))
        suffix = suffix.slice(1);
      anchor.textContent = `${value.slice(0, start)}${choice}${suffix}`;
      this.sync();
      ExtendedSelectorEditor.focusAt(anchor, start + choice.length);
    });
  }
  /** Build a useful first predicate expression for a property.
   * @param {string} name
   * @returns {string}
   */
  static predicateTemplate = name => {
    if (
      [
        "visible",
        "rendered",
        "enabled",
        "disabled",
        "focused",
        "checked",
        "selected",
        "editable",
        "clickable",
        "draggable",
        "scrollable",
        "in_viewport",
        "above_viewport",
        "below_viewport",
      ].includes(name)
    )
      return `[${name}=true]`;
    if (
      [
        "width",
        "height",
        "area",
        "aspect_ratio",
        "viewport_ratio",
        "children",
        "descendants",
        "siblings",
        "index",
        "depth",
      ].includes(name)
    )
      return `[${name}>=0]`;
    return `[${name}*="…"]`;
  };
  /**
   * Populate and position the floating option list near `anchor`.
   *
   * @param {HTMLElement} anchor
   * @param {readonly string[]} values
   * @param {(value: string) => void} action
   * @returns {void}
   */
  showOptions(anchor, values, action) {
    this.popup.replaceChildren(
      ...values.map(value => {
        const button = ExtendedSelectorEditor.el("button", "ese-option", value);
        button.type = "button";
        button.setAttribute("role", "option");
        button.addEventListener("mousedown", event => {
          event.preventDefault();
          action(value);
          this.popup.hidden = true;
        });
        return button;
      }),
    );
    const rect = anchor.getBoundingClientRect();
    Object.assign(this.popup.style, {
      left: `${Math.min(rect.left, innerWidth - 320)}px`,
      top: `${Math.min(rect.bottom + 6, innerHeight - 220)}px`,
    });
    this.popup.hidden = !values.length;
  }
  /**
   * Move DOM focus and the caret to the end of `node`.
   *
   * @param {HTMLElement} node
   * @returns {void}
   */
  static focus = node => {
    node.focus();
    const range = document.createRange();
    range.selectNodeContents(node);
    range.collapse(false);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
  };
  /** Return the text offset of the current caret within an editable node.
   * @param {HTMLElement} node
   * @returns {number}
   */
  static caretOffset = node => {
    const selection = window.getSelection();
    const focus = selection?.focusNode;
    if (!selection?.rangeCount || !focus || !node.contains(focus))
      return (node.textContent ?? "").length;
    const range = selection.getRangeAt(0).cloneRange();
    range.selectNodeContents(node);
    range.setEnd(focus, selection.focusOffset);
    return range.toString().length;
  };
  /** Place the DOM caret at a text offset after accepting a completion.
   * @param {HTMLElement} node
   * @param {number} offset
   * @returns {void}
   */
  static focusAt = (node, offset) => {
    node.focus();
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    let remaining = offset;
    let text = walker.nextNode();
    while (text && remaining > (text.textContent ?? "").length) {
      remaining -= (text.textContent ?? "").length;
      text = walker.nextNode();
    }
    if (!text) return;
    const range = document.createRange();
    range.setStart(text, Math.min(remaining, (text.textContent ?? "").length));
    range.collapse(true);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
  };
  /**
   * Wrap the node containing the current selection in a call capsule.
   *
   * @param {string} [operator]
   * @returns {boolean}
   */
  wrapSelection(operator = "and") {
    const selection = window.getSelection();
    if (!selection?.rangeCount) return false;
    const range = selection.getRangeAt(0);
    const node = (
      range.commonAncestorContainer instanceof Element
        ? range.commonAncestorContainer
        : range.commonAncestorContainer.parentElement
    )?.closest(".ese-call,.ese-atom");
    if (!node) return false;
    return this.wrapNode(node, operator);
  }
  /**
   * Wrap `node` in a new call capsule and focus the empty argument slot.
   *
   * @param {Element} node
   * @param {string} [operator]
   * @returns {boolean}
   */
  wrapNode(node, operator = "and") {
    const current = node.closest(".ese-call,.ese-atom");
    if (!current) return false;
    const wrapper = ExtendedSelectorEditor.el("span", "ese-call ese-active");
    wrapper.setAttribute("data-operator", operator);
    const open = ExtendedSelectorEditor.el("span", "ese-paren ese-open", "(");
    const close = ExtendedSelectorEditor.el("span", "ese-paren ese-close", ")");
    const args = ExtendedSelectorEditor.el("span", "ese-args");
    const comma = ExtendedSelectorEditor.el("span", "ese-separator", ",");
    const slot = ExtendedSelectorEditor.caret();
    current.replaceWith(wrapper);
    args.append(current, ExtendedSelectorEditor.caret(), comma, slot);
    wrapper.append(
      ExtendedSelectorEditor.operator(operator),
      open,
      args,
      close,
    );
    this.sync();
    ExtendedSelectorEditor.focus(slot);
    return true;
  }
}
export default ExtendedSelectorEditor;
