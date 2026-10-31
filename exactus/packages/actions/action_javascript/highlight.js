/** A small JavaScript tokenizer for colouring the editor overlay. */
/** @typedef {"comment"|"string"|"template"|"number"|"keyword"|"literal"|"name"|"punct"|"text"|"space"} TokenType */
/** @typedef {{type:TokenType, text:string}} Token */
const KEYWORDS = new Set([
  "async", "await", "break", "case", "catch", "class", "const", "continue", "debugger", "default", "delete", "do",
  "else", "export", "extends", "finally", "for", "function", "if", "import", "in", "instanceof", "let", "new",
  "of", "return", "static", "super", "switch", "this", "throw", "try", "typeof", "var", "void", "while", "yield",
]);
const LITERALS = new Set(["true", "false", "null", "undefined", "NaN", "Infinity"]);
const NAMES = new Set(["exactus", "console"]);
/** @type {readonly (readonly [TokenType, RegExp])[]} */
const PATTERNS = Object.freeze([
  ["comment", /\/\/[^\n]*|\/\*[\s\S]*?(?:\*\/|$)/y],
  ["string", /"(?:[^"\\\n]|\\.)*"?|'(?:[^'\\\n]|\\.)*'?/y],
  ["template", /`(?:[^`\\]|\\[\s\S])*`?/y],
  ["number", /0[xX][\da-fA-F_]+n?|0[bB][01_]+n?|0[oO][0-7_]+n?|(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:[eE][+-]?\d+)?n?/y],
  ["text", /[A-Za-z_$][\w$]*/y],
  ["space", /\s+/y],
  ["punct", /[^\sA-Za-z0-9_$"'`]/y],
]);

/**
 * Split source text into coloured tokens.
 * @param {string} source JavaScript source.
 * @returns {Token[]} Tokens whose texts concatenate back to the source.
 */
export const tokenize = source => {
  /** @type {Token[]} */
  const tokens = [];
  let index = 0;
  while (index < source.length) {
    let matched = false;
    for (const [type, pattern] of PATTERNS) {
      pattern.lastIndex = index;
      const found = pattern.exec(source);
      if (!found || found.index !== index || found[0] === "") continue;
      const text = found[0];
      /** @type {TokenType} */
      let kind = type;
      if (type === "text") kind = KEYWORDS.has(text) ? "keyword" : LITERALS.has(text) ? "literal" : NAMES.has(text) ? "name" : "text";
      tokens.push({ type: kind, text });
      index += text.length;
      matched = true;
      break;
    }
    if (!matched) {
      tokens.push({ type: "text", text: source.charAt(index) });
      index += 1;
    }
  }
  return tokens;
};

/**
 * Group tokens into lines, splitting multi-line tokens at each newline.
 * @param {string} source JavaScript source.
 * @returns {Token[][]} One token list per source line.
 */
export const tokenizeLines = source => {
  /** @type {Token[][]} */
  const lines = [[]];
  for (const token of tokenize(source)) {
    const pieces = token.text.split("\n");
    pieces.forEach((piece, position) => {
      if (position > 0) lines.push([]);
      if (piece !== "") lines.at(-1)?.push({ type: token.type, text: piece });
    });
  }
  return lines;
};
