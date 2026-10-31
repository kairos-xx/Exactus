/** The Expression view: shapes plus one inline draft input at the caret. */
import { createMenu } from "./mention-menu.js";
import { buildShape, joinOf } from "./shapes.js";
import { enclosing, matchingClose, slotsOf, tokenize } from "./selector-tree.js";
/** @typedef {import("./selector-tree.js").Token} Token */
const COMMIT_END = /[,)>+~ ]$/;
/**
 * Create the view.
 * @returns {{surface:HTMLElement, menu:object, getText:()=>string, setText:Function, setDiagnostics:Function, focus:()=>void, getCaret:()=>number, setCaret:Function}} The expression view API.
 */
export const createExpressionView = (/** @type {{host:HTMLElement, signatures:Record<string, any>, onChange:(text:string)=>void, suggestions:(ctx:{draft:string, role:string, scope:string})=>{title:string, items:import("./suggest.js").Item[]}|null, label:string}} */ { host, signatures, onChange, suggestions, label }) => {
  const surface = document.createElement("div");
  surface.className = "ese-surface";
  surface.setAttribute("role", "group");
  surface.setAttribute("aria-label", label);
  host.append(surface);
  let text = "";
  let caret = 0;
  /** @type {Token[]} */
  let tokens = [];
  /** @type {{offset:number, length:number, severity:string}[]} */
  let problems = [];
  /** @type {HTMLInputElement|null} */
  let draftInput = null;
  /** @param {boolean} [focus] */
  const render = (focus = false) => {
    const hadFocus = focus || surface.contains(document.activeElement);
    tokens = tokenize(text);
    const slots = slotsOf(tokens, signatures);
    surface.replaceChildren();
    /** @type {string|null} */
    let prev = null;
    let spaced = false;
    let placed = false;
    /** Append the draft input at the caret position. */
    const placeDraft = () => {
      placed = true;
      draftInput = document.createElement("input");
      draftInput.className = "ese-draft";
      draftInput.placeholder = " ";
      draftInput.size = 1;
      draftInput.setAttribute("aria-label", label);
      draftInput.setAttribute("autocomplete", "off");
      draftInput.spellcheck = false;
      surface.append(draftInput);
    };
    /**
     * Append a shape recording its join and previous type.
     * @param {HTMLElement} shape Shape element.
     * @param {string} type Shape type.
     */
    const append = (shape, type) => {
      shape.setAttribute("data-join", prev === null ? "flush" : joinOf(spaced && prev !== "glyph" ? "descendant" : prev, type));
      surface.append(shape);
      prev = type;
      spaced = false;
    };
    /** @type {{at:number, build:()=>void}[]} */
    const seq = [];
    tokens.forEach((token, i) => {
      for (const gap of slots.filter(slot => slot.before === i))
        seq.push({ at: gap.start, build: () => append(buildShape({ type: "slot", kind: "slot", label: gap.role }), "slot") });
      seq.push({
        at: token.start,
        build: () => {
          if (token.type === "space") {
            spaced = true;
            return;
          }
          if (token.type === "glyph") {
            const glyph = document.createElement("span");
            glyph.className = "ese-glyph";
            glyph.textContent = token.text;
            glyph.setAttribute("data-start", String(token.start));
            glyph.setAttribute("data-end", String(token.end));
            surface.append(glyph);
            prev = "glyph";
            spaced = false;
            return;
          }
          const type = token.type === "draft" ? "leaf" : token.type;
          const shape = buildShape({ type, kind: token.kind, label: type === "close" ? "" : token.label, editable: Boolean(token.editable), title: token.kind });
          shape.setAttribute("data-start", String(token.start));
          shape.setAttribute("data-end", String(token.end));
          const problem = problems.find(p => p.offset < token.end && p.offset + p.length > token.start);
          if (problem) shape.setAttribute("data-problem", problem.severity);
          append(shape, type);
        },
      });
    });
    for (const gap of slots.filter(slot => slot.before >= tokens.length))
      seq.push({ at: gap.start, build: () => append(buildShape({ type: "slot", kind: "slot", label: gap.role }), "slot") });
    for (const item of seq) {
      if (!placed && item.at >= caret) placeDraft();
      item.build();
    }
    if (!placed) placeDraft();
    if (hadFocus) draftInput?.focus();
  };
  /**
   * Replace the text and caret, re-rendering and emitting on change.
   * @param {string} next New text.
   * @param {number} at Caret offset.
   */
  const set = (next, at) => {
    const changed = next !== text;
    text = next;
    caret = Math.max(0, Math.min(at, text.length));
    render();
    if (changed) onChange(text);
  };
  /**
   * Insert text at the caret, adding what the language needs around it.
   * @param {string} insert Text to insert.
   * @param {number} [adjust] Caret offset from the end of the insert.
   */
  const commit = (insert, adjust = 0) => {
    if (!insert) return;
    const before = text.slice(0, caret);
    const frame = enclosing(tokens, caret);
    const needsComma =
      frame &&
      /^[A-Za-z_.#:[*{@]/.test(insert) &&
      before.trim() !== "" &&
      !/[(,]\s*$/.test(before) &&
      signatures[frame.open.name ?? ""] &&
      frame.arg + 1 < (signatures[frame.open.name ?? ""].min ?? 0) &&
      !/[>+~,]\s*$/.test(before);
    const lead = needsComma ? ", " : "";
    let piece = insert;
    let back = adjust;
    if (/^[A-Za-z_][\w-]*\($/.test(piece) || /^::?[\w-]+\($/.test(piece)) {
      piece += ")";
      back = -1;
    }
    set(before + lead + piece + text.slice(caret), caret + lead.length + piece.length + back);
  };
  const menu = createMenu({ host, onChoose: item => commit(item.insert ?? item.label, item.adjust ?? 0) });
  /** Anchor the menu under the draft input, kept inside the field. */
  const placeMenu = () => {
    if (!draftInput || !menu.isOpen()) return;
    const bounds = host.getBoundingClientRect();
    const anchor = draftInput.getBoundingClientRect();
    const width = menu.element.offsetWidth;
    const x = Math.max(0, Math.min(anchor.left - bounds.left, bounds.width - width));
    menu.element.style.setProperty("--dynamic-esw-menu-x", `${x}px`);
    menu.element.style.setProperty("--dynamic-esw-menu-y", `${anchor.bottom - bounds.top + 3}px`);
  };
  /**
   * Open the suggestion menu for the current draft.
   * @param {boolean} [force] Open even with an empty draft (explicit request).
   * @returns {void}
   */
  const showMenu = (force = false) => {
    if (!force && !draftInput?.value) {
      menu.close();
      return;
    }
    const frame = enclosing(tokens, caret);
    const role = frame ? (signatures[frame.open.name ?? ""]?.roles?.[frame.arg] ?? signatures[frame.open.name ?? ""]?.variadicRole ?? "") : "";
    const scope = (() => {
      if (!frame || frame.arg === 0) return "";
      const first = tokens.slice(frame.openIndex + 1).find(t => t.type === "leaf" && ["tag", "class", "id"].includes(t.kind));
      return first?.text ?? "";
    })();
    const found = draftInput ? suggestions({ draft: draftInput.value, role, scope }) : null;
    if (!found) menu.close();
    else {
      menu.open(found.title, found.items, draftInput?.value.startsWith("@") ? draftInput.value.slice(1) : "");
      placeMenu();
    }
  };
  /**
   * Dissolve a token back into draft text at the caret.
   * @param {number} index Token index.
   */
  const dissolve = index => {
    const token = tokens[index];
    if (!token) return;
    if (token.type === "open") {
      const close = matchingClose(tokens, index);
      const name = token.text.replace(/\($/, "");
      const without = close < 0 ? text.slice(0, token.start) + text.slice(token.end) : text.slice(0, token.start) + text.slice(token.end, tokens[close]?.start) + text.slice(tokens[close]?.end);
      text = without;
      caret = token.start;
      render(true);
      onChange(text);
      if (draftInput) {
        draftInput.value = name;
        draftInput.size = Math.max(1, name.length);
        draftInput.setSelectionRange(name.length, name.length);
        showMenu();
      }
      return;
    }
    const keep = token.type === "leaf" ? token.text : "";
    text = text.slice(0, token.start) + text.slice(token.end);
    caret = token.start;
    render(true);
    onChange(text);
    if (keep && draftInput) {
      draftInput.value = keep;
      draftInput.size = Math.max(1, keep.length);
      draftInput.setSelectionRange(keep.length, keep.length);
      showMenu();
    }
  };
  /**
   * Handle draft input, committing completed fragments.
   * @param {Event} event Input event.
   */
  const onDraftInput = event => {
    const input = /** @type {HTMLInputElement} */ (event.target);
    const value = input.value;
    input.size = Math.max(1, value.length);
    const pasted = /** @type {InputEvent} */ (event).inputType === "insertFromPaste";
    if (value.length > 1 && (pasted || /\s.*\S/.test(value.trim()) || /\)|,/.test(value) && value.length > 2 && !value.startsWith("@"))) {
      input.value = "";
      commit(value);
      menu.close();
      return;
    }
    if (/^[A-Za-z_][\w-]*\($/.test(value) || /^::?[A-Za-z][\w-]*\($/.test(value)) {
      input.value = "";
      commit(value);
      menu.close();
      return;
    }
    if (COMMIT_END.test(value) && !value.startsWith("@")) {
      input.value = "";
      commit(value);
      menu.close();
      return;
    }
    showMenu();
  };
  /**
   * Handle draft key presses: menu keys, commit, dissolve, caret moves.
   * @param {KeyboardEvent} event Key event.
   */
  const onDraftKey = event => {
    const input = /** @type {HTMLInputElement} */ (event.target);
    if (menu.key(event)) {
      event.preventDefault();
      placeMenu();
      return;
    }
    if ((event.key === "ArrowDown" && !input.value) || ((event.ctrlKey || event.metaKey) && event.key === " ")) {
      event.preventDefault();
      showMenu(true);
      return;
    }
    if (event.key === "Enter" || (event.key === "Tab" && input.value && !event.shiftKey)) {
      if (input.value) {
        event.preventDefault();
        const value = input.value;
        input.value = "";
        commit(value);
        menu.close();
      }
      return;
    }
    const before = tokens.filter(t => t.end <= caret);
    const after = tokens.filter(t => t.start >= caret);
    if (event.key === "Backspace" && !input.value) {
      const last = before.at(-1);
      if (last) {
        event.preventDefault();
        dissolve(tokens.indexOf(last));
      }
    } else if (event.key === "Delete" && !input.value) {
      const next = after[0];
      if (next) {
        event.preventDefault();
        dissolve(tokens.indexOf(next));
      }
    } else if ((event.key === "Home" || event.key === "End") && !input.value) {
      event.preventDefault();
      caret = event.key === "Home" ? 0 : text.length;
      render(true);
    } else if (event.key === "ArrowLeft" && input.selectionStart === 0) {
      const last = before.at(-1);
      if (last) {
        event.preventDefault();
        const value = input.value;
        if (value) input.value = "";
        caret = last.start;
        render(true);
      }
    } else if (event.key === "ArrowRight" && input.selectionStart === input.value.length) {
      const next = after[0];
      if (next) {
        event.preventDefault();
        caret = next.end;
        render(true);
      }
    }
  };
  /** Put the caret at the boundary nearest a click: the closest element on the
   * clicked row, before it when the click is in its left half, otherwise after.
   * @param {MouseEvent} event */
  const placeCaret = event => {
    if (event.target === draftInput) return;
    const marks = [...surface.querySelectorAll("[data-start]")];
    /** @type {{mark:HTMLElement, rect:DOMRect}|null} */
    let best = null;
    let bestDistance = Infinity;
    for (const mark of marks) {
      const rect = mark.getBoundingClientRect();
      const dy = event.clientY < rect.top ? rect.top - event.clientY : event.clientY > rect.bottom ? event.clientY - rect.bottom : 0;
      const dx = event.clientX < rect.left ? rect.left - event.clientX : event.clientX > rect.right ? event.clientX - rect.right : 0;
      const distance = dy * 1000 + dx;
      if (distance < bestDistance) {
        best = { mark: /** @type {HTMLElement} */ (mark), rect };
        bestDistance = distance;
      }
    }
    if (!best) caret = text.length;
    else
      caret = Number(
        event.clientX < best.rect.left + best.rect.width / 2
          ? best.mark.getAttribute("data-start")
          : best.mark.getAttribute("data-end"),
      );
    render(true);
  };
  surface.addEventListener("click", placeCaret);
  surface.addEventListener("input", event => {
    if (event.target === draftInput) onDraftInput(event);
  });
  surface.addEventListener("keydown", event => {
    if (event.target === draftInput) onDraftKey(/** @type {KeyboardEvent} */ (event));
  });
  surface.addEventListener("focusout", event => {
    if (event.target === draftInput) setTimeout(() => menu.close(), 120);
  });
  render();
  return {
    surface,
    menu,
    getText: () => text,
    /** @param {string} next */
    setText: next => {
      text = next;
      caret = next.length;
      render();
    },
    /** @param {{offset:number, length:number, severity:string}[]} list */
    setDiagnostics: list => {
      problems = list;
      render();
    },
    focus: () => draftInput?.focus(),
    getCaret: () => caret,
    /** @param {number} at */
    setCaret: at => {
      caret = Math.max(0, Math.min(at, text.length));
      render();
    },
  };
};
