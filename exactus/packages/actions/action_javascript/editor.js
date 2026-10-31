/** The code editor: a textarea over a highlighted mirror, with a line-number gutter.
 * Ctrl/Cmd+Enter dispatches an `editor-run` event on `element`. */
import { tokenizeLines } from "./highlight.js";
/**
 * @typedef {object} EditorOptions
 * @property {HTMLElement} host Element that receives the editor.
 * @property {string} label Accessible name of the textarea.
 * @property {string} value Initial source.
 * @property {boolean} [readOnly] Whether editing is disabled.
 * @property {number} [minRows] Fewest visible lines.
 * @property {number} [maxRows] Most visible lines before scrolling.
 * @property {(value:string)=>void} [onChange] Called after every edit.
 * @property {(caret:{line:number, column:number, lines:number})=>void} [onCaret] Called when the caret moves.
 */
const INDENT = "  ";
/**
 * Create an element with an optional class.
 * @template {keyof HTMLElementTagNameMap} K
 * @param {K} tag Tag name.
 * @param {string} [className] Class list.
 * @returns {HTMLElementTagNameMap[K]} The new element.
 */
const make = (tag, className = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
};
/**
 * Create the editor.
 * @param {EditorOptions} options Editor options.
 * @returns The editor API.
 */
export const createEditor = options => {
  const { host, label, minRows = 6, maxRows = 16 } = options;
  const wrap = make("div", "jr-editor");
  const gutter = make("div", "jr-gutter");
  gutter.setAttribute("aria-hidden", "true");
  const stage = make("div", "jr-stage");
  const mirror = make("div", "jr-mirror");
  mirror.setAttribute("aria-hidden", "true");
  const input = make("textarea", "jr-input");
  input.spellcheck = false;
  input.wrap = "off";
  input.autocomplete = "off";
  input.autocapitalize = "off";
  input.value = options.value;
  input.readOnly = options.readOnly ?? false;
  input.setAttribute("aria-label", label);
  stage.append(mirror, input);
  wrap.append(gutter, stage);
  host.append(wrap);
  /** @type {number|null} */
  let errorLine = null;
  /**
   * Describe where the caret is.
   * @returns {{line:number, column:number, lines:number}} One-based caret position.
   */
  const caret = () => {
    const before = input.value.slice(0, input.selectionStart);
    const line = before.split("\n").length;
    return { line, column: before.length - before.lastIndexOf("\n"), lines: input.value.split("\n").length };
  };
  /** Keep the mirror and gutter aligned with the textarea scroll. */
  const syncScroll = () => {
    mirror.scrollTop = input.scrollTop;
    mirror.scrollLeft = input.scrollLeft;
    gutter.scrollTop = input.scrollTop;
  };
  /**
   * Rebuild the mirror and the gutter from the current value.
   * @returns {void}
   */
  const paint = () => {
    const lines = tokenizeLines(input.value);
    mirror.replaceChildren(
      ...lines.map((tokens, index) => {
        const row = make("div", "jr-line");
        if (errorLine === index + 1) row.setAttribute("data-error", "");
        for (const token of tokens) {
          const span = make("span", "jr-t");
          span.setAttribute("data-kind", token.type);
          span.textContent = token.text;
          row.append(span);
        }
        return row;
      }),
    );
    gutter.replaceChildren(
      ...lines.map((_tokens, index) => {
        const number = make("div", "jr-num");
        number.textContent = String(index + 1);
        if (errorLine === index + 1) number.setAttribute("data-error", "");
        return number;
      }),
    );
    input.rows = Math.min(Math.max(lines.length, minRows), maxRows);
    syncScroll();
  };
  /**
   * Replace a range and place the selection, keeping native undo when possible.
   * @param {number} start Range start.
   * @param {number} end Range end.
   * @param {string} text Replacement text.
   * @param {number} [selectStart] New selection start, after the text by default.
   * @param {number} [selectEnd] New selection end.
   * @returns {void}
   */
  const edit = (start, end, text, selectStart = start + text.length, selectEnd = selectStart) => {
    input.focus();
    input.setSelectionRange(start, end);
    if (!document.execCommand("insertText", false, text)) {
      input.setRangeText(text, start, end, "end");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    input.setSelectionRange(selectStart, selectEnd);
  };
  /**
   * Find the start of the line containing an offset.
   * @param {number} offset Character offset.
   * @returns {number} Offset of the line start.
   */
  const lineStart = offset => input.value.lastIndexOf("\n", offset - 1) + 1;
  /**
   * Find the end of the line containing an offset.
   * @param {number} offset Character offset.
   * @returns {number} Offset of the line end.
   */
  const lineEnd = offset => {
    const found = input.value.indexOf("\n", offset);
    return found === -1 ? input.value.length : found;
  };
  /**
   * Indent or outdent the selected lines, or insert one indent at the caret.
   * @param {boolean} outdent Whether to remove indentation.
   * @returns {void}
   */
  const indent = outdent => {
    const { selectionStart: start, selectionEnd: end, value } = input;
    if (start === end && !outdent) {
      edit(start, end, INDENT);
      return;
    }
    const from = lineStart(start);
    const to = lineEnd(end);
    const block = value.slice(from, to).split("\n");
    const changed = block.map(line => (outdent ? line.replace(/^ {1,2}/, "") : line === "" ? line : `${INDENT}${line}`));
    const text = changed.join("\n");
    const firstDelta = (changed[0]?.length ?? 0) - (block[0]?.length ?? 0);
    edit(from, to, text, Math.max(from, start + firstDelta), end + text.length - (to - from));
  };
  /**
   * Toggle `//` comments on the selected lines.
   * @returns {void}
   */
  const toggleComment = () => {
    const { selectionStart: start, selectionEnd: end, value } = input;
    const from = lineStart(start);
    const to = lineEnd(end);
    const block = value.slice(from, to).split("\n");
    const filled = block.filter(line => line.trim() !== "");
    const commented = filled.length > 0 && filled.every(line => /^\s*\/\//.test(line));
    const margin = Math.min(...filled.map(line => /^\s*/.exec(line)?.[0].length ?? 0));
    const changed = block.map(line => {
      if (line.trim() === "") return line;
      return commented ? line.replace(/^(\s*)\/\/ ?/, "$1") : `${line.slice(0, margin)}// ${line.slice(margin)}`;
    });
    const text = changed.join("\n");
    edit(from, to, text, from, from + text.length);
  };
  /** Insert a newline that keeps indentation and opens a block after a bracket. */
  const newline = () => {
    const { selectionStart: start, selectionEnd: end, value } = input;
    const head = value.slice(lineStart(start), start);
    const base = /^\s*/.exec(head)?.[0] ?? "";
    const opens = /[{([]\s*$/.test(head);
    const closes = /^[})\]]/.test(value.slice(end));
    const inner = `${base}${opens ? INDENT : ""}`;
    if (opens && closes) {
      const text = `\n${inner}\n${base}`;
      edit(start, end, text, start + 1 + inner.length);
      return;
    }
    edit(start, end, `\n${inner}`);
  };
  input.addEventListener("keydown", event => {
    const modifier = event.metaKey || event.ctrlKey;
    if (input.readOnly && event.key !== "Tab") return;
    if (modifier && event.key === "Enter") {
      event.preventDefault();
      wrap.dispatchEvent(new CustomEvent("editor-run"));
    } else if (modifier && event.key === "/") {
      event.preventDefault();
      toggleComment();
    } else if (event.key === "Tab" && !modifier && !event.altKey) {
      if (input.readOnly) return;
      event.preventDefault();
      indent(event.shiftKey);
    } else if (event.key === "Enter" && !modifier && !event.shiftKey && !event.altKey) {
      event.preventDefault();
      newline();
    }
  });
  input.addEventListener("input", () => {
    paint();
    options.onChange?.(input.value);
    options.onCaret?.(caret());
  });
  input.addEventListener("scroll", syncScroll);
  for (const type of /** @type {const} */ (["keyup", "click", "focus"]))
    input.addEventListener(type, () => options.onCaret?.(caret()));
  paint();
  return {
    element: wrap,
    input,
    caret,
    getValue: () => input.value,
    /**
     * Replace the source.
     * @param {string} value New source.
     * @returns {void}
     */
    setValue: value => {
      input.value = value;
      errorLine = null;
      paint();
      options.onChange?.(value);
    },
    /**
     * Insert text at the caret, replacing the selection.
     * @param {string} text Text to insert.
     * @returns {void}
     */
    insert: text => edit(input.selectionStart, input.selectionEnd, text),
    /**
     * Mark one line as failing, or clear the mark.
     * @param {number|null} line One-based line, or null.
     * @returns {void}
     */
    setErrorLine: line => {
      errorLine = line;
      paint();
    },
    /**
     * Move the caret to a position and scroll it into view.
     * @param {number} line One-based line.
     * @param {number} [column] One-based column.
     * @returns {void}
     */
    goTo: (line, column = 1) => {
      const rows = input.value.split("\n");
      const target = Math.min(Math.max(line, 1), rows.length);
      const offset = rows.slice(0, target - 1).reduce((sum, row) => sum + row.length + 1, 0) + Math.min(column - 1, rows[target - 1]?.length ?? 0);
      input.focus();
      input.setSelectionRange(offset, offset);
      const height = Number.parseFloat(getComputedStyle(input).lineHeight) || input.scrollHeight / rows.length;
      input.scrollTop = Math.max(0, (target - 3) * height);
      syncScroll();
      options.onCaret?.(caret());
    },
    focus: () => input.focus(),
    /**
     * Enable or disable editing.
     * @param {boolean} value Whether the editor is read-only.
     * @returns {void}
     */
    setReadOnly: value => {
      input.readOnly = value;
    },
  };
};
