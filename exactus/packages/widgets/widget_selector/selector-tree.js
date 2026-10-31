/** Flat token model of an ExtendedSelector expression.
 *
 * The expression stays plain text. `tokenize` cuts it into shapes (open,
 * leaf, close), glyphs and spaces without losing a character, so the
 * concatenated token text is always the input. Nesting is carried by the
 * open/close pairs, which is exactly how the shapes are drawn.
 */
/** @typedef {{type:"open"|"leaf"|"close"|"glyph"|"space"|"draft", kind:string, text:string, label:string, start:number, end:number, name?:string, editable?:boolean}} Token */
const IDENT = /[A-Za-z_][\w-]*/y;
const VARIABLE = /\{\{([^{}]*)\}\}/y;
const ENVIRONMENT = /^(device|env|target)\//;
/**
 * Which family a variable path belongs to.
 * @param {string} path Variable path.
 * @returns {"env"|"flow"} The variable family.
 */
export const variableKind = path => ENVIRONMENT.test(path) ? "env" : "flow";
/**
 * Index of the bracket that closes `[` at `from`, honouring quotes.
 * @param {string} text Expression text.
 * @param {number} from Offset of the opening bracket.
 * @returns {number} The close-bracket index or -1.
 */
const closeBracket = (text, from) => {
  let quote = "";
  for (let i = from + 1; i < text.length; i += 1) {
    const c = text.charAt(i);
    if (quote) {
      if (c === "\\") i += 1;
      else if (c === quote) quote = "";
    } else if (c === '"' || c === "'") quote = c;
    else if (c === "]") return i;
  }
  return -1;
};
/** Cut an expression into tokens.
 * @param {string} text
 * @returns {Token[]}
 */
export const tokenize = text => {
  /** @type {Token[]} */
  const out = [];
  /**
   * Push a token built from a source span.
   * @param {Token["type"]} type Token type.
   * @param {string} kind Token kind.
   * @param {number} start Start offset.
   * @param {number} end End offset.
   * @param {Partial<Token>} [extra] Extra token fields.
   * @returns {number} Tokens pushed.
   */
  const push = (type, kind, start, end, extra = {}) =>
    out.push({
      type,
      kind,
      text: text.slice(start, end),
      label: text.slice(start, end),
      start,
      end,
      ...extra,
    });
  let i = 0;
  while (i < text.length) {
    const c = text.charAt(i);
    if (/\s/.test(c)) {
      let j = i;
      while (j < text.length && /\s/.test(text.charAt(j))) j += 1;
      push("space", "space", i, j);
      i = j;
      continue;
    }
    if (c === "{" && text.startsWith("{{", i)) {
      VARIABLE.lastIndex = i;
      const found = VARIABLE.exec(text);
      if (found) {
        const inner = (found[1] ?? "").trim();
        const path = (inner.includes("=") ? inner.slice(0, inner.indexOf("=")) : inner).trim();
        push("leaf", variableKind(path), i, i + found[0].length, {
          label: inner.includes("=") ? `${path} = ${inner.slice(inner.indexOf("=") + 1).trim()}` : path,
          name: path,
          editable: true,
        });
        i += found[0].length;
        continue;
      }
    }
    if (c === "[") {
      const close = closeBracket(text, i);
      if (close < 0) {
        push("draft", "draft", i, text.length);
        i = text.length;
        continue;
      }
      const raw = text.slice(i, close + 1);
      const saved = /^\[extended-selector\s*=\s*(["'])(.*)\1\]$/.exec(raw);
      const variable = /\{\{[^{}]*\}\}/.exec(raw);
      const quoted = /["'][^"']*\{\{/.test(raw);
      if (saved) push("leaf", "saved", i, close + 1, { label: `@${saved[2]}`, name: saved[2] ?? "", editable: true });
      else if (variable && !quoted) {
        const head = i + (variable.index ?? 0);
        push("open", "attribute", i, head, { label: raw.slice(0, variable.index).trim() });
        const variableEnd = head + variable[0].length;
        const inner = variable[0].slice(2, -2).trim();
        const path = (inner.includes("=") ? inner.slice(0, inner.indexOf("=")) : inner).trim();
        push("leaf", variableKind(path), head, variableEnd, { label: path, name: path, editable: true });
        push("close", "attribute", variableEnd, close + 1, { label: "]" });
      } else push("leaf", "attribute", i, close + 1, { editable: false });
      i = close + 1;
      continue;
    }
    if (c === "(") {
      push("open", "operator", i, i + 1, { label: "", name: "" });
      i += 1;
      continue;
    }
    if (c === ")") {
      push("close", "operator", i, i + 1);
      i += 1;
      continue;
    }
    if (c === "|" && text.charAt(i + 1) === "|") {
      push("glyph", "glyph", i, i + 2);
      i += 2;
      continue;
    }
    if (c === "," || c === ">" || c === "+" || c === "~") {
      push("glyph", "glyph", i, i + 1);
      i += 1;
      continue;
    }
    if (c === ":") {
      const pe = text.charAt(i + 1) === ":";
      IDENT.lastIndex = i + (pe ? 2 : 1);
      const name = IDENT.exec(text);
      if (name) {
        const end = IDENT.lastIndex;
        const kind = pe ? "pseudo-element" : "pseudo-class";
        if (text.charAt(end) === "(") {
          push("open", kind, i, end + 1, { name: text.slice(i, end), label: text.slice(i, end + 1) });
          i = end + 1;
        } else {
          push("leaf", kind, i, end, { editable: false });
          i = end;
        }
        continue;
      }
    }
    if (c === "#" || c === ".") {
      IDENT.lastIndex = i + 1;
      const name = IDENT.exec(text);
      if (name) {
        push("leaf", c === "#" ? "id" : "class", i, IDENT.lastIndex, { editable: true });
        i = IDENT.lastIndex;
        continue;
      }
    }
    if (c === "*") {
      push("leaf", "tag", i, i + 1);
      i += 1;
      continue;
    }
    IDENT.lastIndex = i;
    const word = IDENT.exec(text);
    if (word) {
      const end = IDENT.lastIndex;
      if (text.charAt(end) === "(") {
        push("open", "operator", i, end + 1, { name: word[0], label: `${word[0]}(` });
        i = end + 1;
      } else {
        push("leaf", "tag", i, end, { editable: true });
        i = end;
      }
      continue;
    }
    let j = i + 1;
    while (j < text.length && !/[\s[\](),>+~:#.*{|A-Za-z_]/.test(text.charAt(j))) j += 1;
    push("draft", "draft", i, j);
    i = j;
  }
  return out;
};
/** Rebuild the text a token sequence stands for.
 * @param {Token[]} tokens @returns {string}
 */
export const serialize = tokens => tokens.map(token => token.text).join("");
/**
 * Index of the close token matching the open token at `index`, or -1.
 * @param {Token[]} tokens Token sequence.
 * @param {number} index Index of the open token.
 * @returns {number} The matching close index or -1.
 */
export const matchingClose = (tokens, index) => {
  let depth = 0;
  for (let i = index; i < tokens.length; i += 1) {
    const type = tokens[i]?.type;
    if (type === "open") depth += 1;
    else if (type === "close") {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return -1;
};
/**
 * The open token enclosing a text offset and which argument the offset is in.
 * @param {Token[]} tokens Token sequence.
 * @param {number} caret Text offset.
 * @returns {{open:Token, openIndex:number, arg:number, closeIndex:number}|null} The enclosing frame.
 */
export const enclosing = (tokens, caret) => {
  /** @type {{open:Token, openIndex:number, arg:number}[]} */
  const stack = [];
  for (let i = 0; i < tokens.length; i += 1) {
    const token = /** @type {Token} */ (tokens[i]);
    if (token.start >= caret) break;
    if (token.type === "open") stack.push({ open: token, openIndex: i, arg: 0 });
    else if (token.type === "close") stack.pop();
    else if (token.type === "glyph" && token.text === ",") {
      const top = stack.at(-1);
      if (top) top.arg += 1;
    }
  }
  const top = stack.at(-1);
  return top ? { ...top, closeIndex: matchingClose(tokens, top.openIndex) } : null;
};
/** Required arguments still missing, to draw as dashed slots before the close.
 * @param {Token[]} tokens
 * @param {Record<string, {min:number, roles:string[], variadicRole?:string}>} signatures
 * @returns {{before:number, role:string, index:number, start:number}[]}
 */
export const slotsOf = (tokens, signatures) => {
  /** @type {{index:number, name:string, args:boolean[]}[]} */
  const stack = [];
  /** @type {{before:number, role:string, index:number, start:number}[]} */
  const slots = [];
  /**
   * Emit slot entries for a frame's missing required arguments.
   * @param {{index:number, name:string, args:boolean[]}} frame Open frame.
   * @param {number} before Token index the frame ends before.
   */
  const finish = (frame, before) => {
    const signature = signatures[frame.name];
    if (!signature) return;
    const start = tokens[before]?.start ?? tokens.at(-1)?.end ?? 0;
    for (let k = 0; k < signature.min; k += 1)
      if (!frame.args[k])
        slots.push({
          before,
          role: signature.roles[k] ?? signature.variadicRole ?? "argument",
          index: k,
          start,
        });
  };
  tokens.forEach((token, i) => {
    const top = stack.at(-1);
    if (token.type === "space") return;
    if (token.type === "glyph" && token.text === ",") {
      top?.args.push(false);
      return;
    }
    if (token.type === "close") {
      const frame = stack.pop();
      if (frame) finish(frame, i);
      return;
    }
    if (top) top.args[top.args.length - 1] = true;
    if (token.type === "open")
      stack.push({ index: i, name: token.name ?? "", args: [false] });
  });
  while (stack.length) {
    const frame = /** @type {{index:number, name:string, args:boolean[]}} */ (stack.pop());
    finish(frame, tokens.length);
  }
  return slots;
};
