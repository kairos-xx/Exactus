/** The Text view: a plain textarea with a colour overlay and problem underlines. */
import { tokenize } from "./selector-tree.js";
/**
 * Create the plain-text view bound to a host element.
 * @returns {{element:HTMLElement, input:HTMLTextAreaElement, getText:()=>string, setText:Function, setDiagnostics:Function, focus:()=>void, getCaret:()=>number, setCaret:Function}} The text view API.
 */
export const createTextView = (/** @type {{host:HTMLElement, label:string, onChange:(text:string)=>void}} */ { host, label, onChange }) => {
  const wrap = document.createElement("div");
  wrap.className = "ese-text";
  const mirror = document.createElement("div");
  mirror.className = "ese-mirror";
  mirror.setAttribute("aria-hidden", "true");
  const input = document.createElement("textarea");
  input.className = "ese-input";
  input.spellcheck = false;
  input.setAttribute("aria-label", label);
  wrap.append(mirror, input);
  host.append(wrap);
  /** @type {{offset:number, length:number, severity:string}[]} */
  let problems = [];
  /** Repaint the mirror overlay from the input value. */
  const paint = () => {
    mirror.replaceChildren();
    const text = input.value;
    for (const token of tokenize(text)) {
      const span = document.createElement("span");
      span.className = "ese-t";
      span.setAttribute("data-kind", token.type === "glyph" ? "operator" : token.kind);
      const problem = problems.find(p => p.offset < token.end && p.offset + p.length > token.start);
      if (problem) span.setAttribute("data-problem", problem.severity);
      span.textContent = token.text;
      mirror.append(span);
    }
    mirror.append(document.createTextNode("\n"));
  };
  input.addEventListener("input", () => {
    paint();
    onChange(input.value);
  });
  paint();
  return {
    element: wrap,
    input,
    getText: () => input.value,
    /** @param {string} text */
    setText: text => {
      input.value = text;
      paint();
    },
    /** @param {{offset:number, length:number, severity:string}[]} list */
    setDiagnostics: list => {
      problems = list;
      paint();
    },
    focus: () => input.focus(),
    getCaret: () => input.selectionStart ?? input.value.length,
    /** @param {number} at */
    setCaret: at => input.setSelectionRange(at, at),
  };
};
