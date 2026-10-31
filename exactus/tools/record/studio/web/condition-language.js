/** The token system of the condition language.
 *
 * Connections and pauses share one condition language: a safe subset of
 * Python expressions. This module is the single place that knows its tokens,
 * operators, helper functions and value types. It has no DOM, so the editor can
 * use it for colouring, for type-checking and for suggesting what may come
 * next, and the same rules can be tested without a browser.
 *
 * The server stays the authority (it validates on save); everything here
 * exists to guide the author before that.
 */
/** What a token is. Each kind has one colour in `styles/components/condition-field/`.
 * @typedef {"system"|"probe"|"output"|"logic"|"compare"|"membership"|"function"|"number"|"string"|"literal"|"paren"|"comma"|"unknown"} TokenKind
 */
/** What a value is, as far as a condition can tell.
 * @typedef {"boolean"|"number"|"string"|"none"|"any"} Semantic
 */
/**
 * @typedef {object} Token
 * @property {TokenKind} kind
 * @property {string} text
 * @property {number} start Offset of the first character.
 * @property {number} end Offset after the last character.
 * @property {Semantic} [semantic] Type of the value a name, literal or call gives.
 * @property {string} [note] A problem with the token itself, such as `&&`.
 */
/**
 * @typedef {object} Issue
 * @property {number} start
 * @property {number} end
 * @property {string} message
 * @property {"error"|"warning"} level
 */
/**
 * @typedef {object} OperatorInfo
 * @property {string} symbol
 * @property {"logic"|"compare"|"membership"} kind
 * @property {Semantic[]} left Types the left side may have.
 * @property {boolean} ordered Whether it orders values, which booleans cannot take.
 * @property {string} detail One line for the suggestion list.
 */
/** The operators, in the order suggestions list them.
 * @type {readonly OperatorInfo[]}
 */
export const OPERATORS = Object.freeze([
  {
    symbol: "==",
    kind: "compare",
    left: ["number", "string", "boolean", "any"],
    ordered: false,
    detail: "Is equal to",
  },
  {
    symbol: "!=",
    kind: "compare",
    left: ["number", "string", "boolean", "any"],
    ordered: false,
    detail: "Is not equal to",
  },
  {
    symbol: ">",
    kind: "compare",
    left: ["number", "string"],
    ordered: true,
    detail: "Is greater than",
  },
  {
    symbol: ">=",
    kind: "compare",
    left: ["number", "string"],
    ordered: true,
    detail: "Is at least",
  },
  {
    symbol: "<",
    kind: "compare",
    left: ["number", "string"],
    ordered: true,
    detail: "Is less than",
  },
  {
    symbol: "<=",
    kind: "compare",
    left: ["number", "string"],
    ordered: true,
    detail: "Is at most",
  },
  {
    symbol: "in",
    kind: "membership",
    left: ["string"],
    ordered: false,
    detail: "The text is part of another text",
  },
  {
    symbol: "not in",
    kind: "membership",
    left: ["string"],
    ordered: false,
    detail: "The text is not part of another text",
  },
  {
    symbol: "and",
    kind: "logic",
    left: ["boolean", "number", "string", "any"],
    ordered: false,
    detail: "Both sides must hold",
  },
  {
    symbol: "or",
    kind: "logic",
    left: ["boolean", "number", "string", "any"],
    ordered: false,
    detail: "Either side may hold",
  },
]);
/**
 * @typedef {object} FunctionInfo
 * @property {string} name
 * @property {Semantic[]} args Type of each argument.
 * @property {string[]} labels What each argument is for, shown on its empty slot.
 * @property {string} detail
 */
/** The helper functions a condition may call.
 * @type {readonly FunctionInfo[]}
 */
export const FUNCTIONS = Object.freeze([
  {
    name: "exists",
    args: ["any"],
    labels: ["value"],
    detail: "True when the value is set",
  },
  {
    name: "contains",
    args: ["string", "string"],
    labels: ["text", "part"],
    detail: "True when the first text contains the second",
  },
  {
    name: "matches",
    args: ["string", "string"],
    labels: ["text", "pattern"],
    detail: "True when the text matches the pattern",
  },
]);
/** The literal names and what each is.
 * @type {Readonly<Record<string, Semantic>>}
 */
export const LITERALS = Object.freeze({
  True: "boolean",
  False: "boolean",
  None: "none",
});
/** Plain-language names for the types, for messages. */
const TYPE_WORDS = Object.freeze({
  boolean: "true or false",
  number: "a number",
  string: "text",
  none: "nothing",
  any: "a value",
});
/** Words people reach for from other languages, and what to write instead.
 * @type {Readonly<Record<string, string>>}
 */
const ALIASES = Object.freeze({
  "&&": "and",
  "||": "or",
  "!": "not",
  "=": "==",
  true: "True",
  false: "False",
  null: "None",
  none: "None",
  AND: "and",
  OR: "or",
  NOT: "not",
});
/** Map a server value type to what a condition can tell about it.
 * @param {string} valueType
 * @returns {Semantic}
 */
export const semanticOf = valueType => {
  if (valueType === "integer" || valueType === "float") return "number";
  if (valueType === "boolean" || valueType === "string") return valueType;
  return "any";
};
/** Whether two types could be the same value.
 * @param {Semantic} left
 * @param {Semantic} right
 * @returns {boolean}
 */
const compatible = (left, right) =>
  left === "any" || right === "any" || left === right;
/** Split a condition into tokens. Never throws: text it cannot read becomes an
 * `unknown` token, with a note when it is a familiar mistake.
 * @param {string} text
 * @param {ConditionTerm[]} [terms] Names the project offers.
 * @returns {Token[]}
 */
export const tokenize = (text, terms = []) => {
  /** @type {Token[]} */
  const tokens = [];
  const byName = new Map(terms.map(term => [term.name, term]));
  let at = 0;
  while (at < text.length) {
    const char = text.charAt(at);
    if (/\s/.test(char)) {
      at += 1;
      continue;
    }
    const rest = text.slice(at);
    /** @type {RegExpExecArray|null} */
    let found;
    if ((found = /^[A-Za-z_][A-Za-z0-9_]*/.exec(rest))) {
      const word = found[0];
      /** @type {Token} */
      const token = {
        kind: "unknown",
        text: word,
        start: at,
        end: at + word.length,
      };
      const term = byName.get(word);
      if (term) {
        token.kind = term.kind;
        token.semantic = semanticOf(term.value_type);
      } else if (word === "and" || word === "or" || word === "not")
        token.kind = "logic";
      else if (word === "in") token.kind = "membership";
      else if (FUNCTIONS.some(item => item.name === word))
        token.kind = "function";
      else if (word in LITERALS) {
        token.kind = "literal";
        token.semantic = LITERALS[word] ?? "any";
      } else if (word in ALIASES)
        token.note = `Write ${ALIASES[word]} instead.`;
      tokens.push(token);
      at += word.length;
    } else if ((found = /^\d+(?:\.\d+)?/.exec(rest))) {
      tokens.push({
        kind: "number",
        text: found[0],
        start: at,
        end: at + found[0].length,
        semantic: "number",
      });
      at += found[0].length;
    } else if (char === '"' || char === "'") {
      let end = at + 1;
      while (end < text.length && text.charAt(end) !== char)
        end += text.charAt(end) === "\\" ? 2 : 1;
      const closed = end < text.length;
      end = Math.min(end + 1, text.length);
      /** @type {Token} */
      const token = {
        kind: "string",
        text: text.slice(at, end),
        start: at,
        end,
        semantic: "string",
      };
      if (!closed) token.note = "This text is missing its closing quote.";
      tokens.push(token);
      at = end;
    } else if ((found = /^(?:==|!=|>=|<=|>|<)/.exec(rest))) {
      tokens.push({
        kind: "compare",
        text: found[0],
        start: at,
        end: at + found[0].length,
      });
      at += found[0].length;
    } else if (char === "(" || char === ")") {
      tokens.push({ kind: "paren", text: char, start: at, end: at + 1 });
      at += 1;
    } else if (char === ",") {
      tokens.push({ kind: "comma", text: char, start: at, end: at + 1 });
      at += 1;
    } else {
      const word = /^(?:&&|\|\||[=!&|]+|\S)/.exec(rest)?.[0] ?? char;
      /** @type {Token} */
      const token = {
        kind: "unknown",
        text: word,
        start: at,
        end: at + word.length,
      };
      const alias = ALIASES[word];
      if (alias) token.note = `Write ${alias} instead.`;
      tokens.push(token);
      at += word.length;
    }
  }
  return tokens;
};
/** Edit distance between two names, to suggest the one that was meant.
 * @param {string} left
 * @param {string} right
 * @returns {number}
 */
const distance = (left, right) => {
  /** @type {number[]} */
  let row = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let i = 1; i <= left.length; i += 1) {
    const next = [i];
    for (let j = 1; j <= right.length; j += 1)
      next.push(
        Math.min(
          (next[j - 1] ?? 0) + 1,
          (row[j] ?? 0) + 1,
          (row[j - 1] ?? 0) +
            (left.charAt(i - 1) === right.charAt(j - 1) ? 0 : 1),
        ),
      );
    row = next;
  }
  return row[right.length] ?? 0;
};
/** The offered name closest to a misspelled one, if any is close.
 * @param {string} word
 * @param {ConditionTerm[]} terms
 * @returns {string}
 */
const closest = (word, terms) => {
  let best = "";
  let bestDistance = Math.max(2, Math.floor(word.length / 4)) + 1;
  for (const term of terms) {
    const gap = distance(word.toLowerCase(), term.name.toLowerCase());
    if (gap < bestDistance) {
      best = term.name;
      bestDistance = gap;
    }
  }
  return best;
};
/**
 * @typedef {object} TreeNode One part of a parsed condition, with its place in the text.
 * @property {"call"|"binary"|"not"|"group"|"term"|"literal"|"missing"} kind
 * @property {number} start Offset of the first character.
 * @property {number} end Offset after the last character.
 * @property {Semantic} semantic What the part evaluates to.
 * @property {Token} [token] The word, number or text of a term or literal.
 * @property {Token} [name] The function name of a call, or the operator of a binary or not.
 * @property {TreeNode[]} [args] The arguments of a call.
 * @property {TreeNode} [left] Left side of a binary.
 * @property {TreeNode} [right] Right side of a binary.
 * @property {TreeNode} [operand] What a not or a group applies to.
 * @property {string} [label] What a missing value is for, such as "text" or "pattern".
 * @property {number} [close] Offset where a call's closing parenthesis goes (or is).
 * @property {string} [lead] Text that must come before a value inserted into a missing slot, such as ", ".
 */
/** Type-check a condition and build its tree.
 * @param {string} text
 * @param {ConditionTerm[]} terms
 * @param {string[]} [selectors] Names of the stored selectors.
 * @returns {{tokens:Token[],issues:Issue[],semantic:Semantic,tree:TreeNode|null}}
 */
export const analyse = (text, terms, selectors = []) => {
  const tokens = tokenize(text, terms);
  /** @type {Issue[]} */
  const issues = [];
  let at = 0;
  /**
   * Record a diagnostic for a token.
   * @param {Token|undefined} token Token associated with the diagnostic.
   * @param {string} message Diagnostic message.
   * @param {"error"|"warning"} [level] Diagnostic severity.
   */
  const report = (token, message, level = "error") => {
    const start = token ? token.start : text.length;
    issues.push({ start, end: token ? token.end : start, message, level });
  };
  /** Return the current token. */
  const peek = () => tokens[at];
  /**
   * Test whether the current token has the requested text.
   * @param {string} wanted Token text.
   * @returns {boolean} Whether the token matches.
   */
  const isText = wanted =>
    peek()?.text === wanted && peek()?.kind !== "string";
  for (const token of tokens) {
    if (token.note) report(token, token.note);
    else if (token.kind === "unknown" && !token.note) {
      const word = token.text;
      if (/^[A-Za-z_]/.test(word)) {
        const missing =
          /^sel_([A-Za-z][A-Za-z0-9_]*?)_(?:count|exists|visible|text|enabled)$/.exec(
            word,
          );
        const name = missing?.[1] ?? "";
        if (name && !selectors.includes(name))
          report(token, `There is no selector named "${name}".`);
        else {
          const near = closest(word, terms);
          report(
            token,
            `${word} is not a name a condition can use.${near ? ` Did you mean ${near}?` : ""}`,
          );
        }
      } else report(token, `${word} is not allowed in a condition.`);
    }
  }
  /**
   * Create a missing-value tree node.
   * @param {string} label Missing-value label.
   * @returns {TreeNode} Missing-value node.
   */
  const missing = label => {
    const where = peek()?.start ?? text.length;
    return {
      kind: "missing",
      start: where,
      end: where,
      semantic: "any",
      label,
    };
  };
  /** The grammar, one rule per precedence level. The rules call each other,
   * so they live on one object instead of as separate constants.
   * @type {{or:()=>TreeNode,and:()=>TreeNode,not:()=>TreeNode,compare:()=>TreeNode,primary:(label?:string)=>TreeNode,call:(token:Token)=>TreeNode}}
   */
  const rules = {
    or: () => missing("value"),
    and: () => missing("value"),
    not: () => missing("value"),
    compare: () => missing("value"),
    primary: () => missing("value"),
    call: () => missing("value"),
  };
  /**
   * Join two tree nodes with a named operator.
   * @param {TreeNode} left Left operand.
   * @param {Token} name Operator token.
   * @param {TreeNode} right Right operand.
   * @returns {TreeNode} Joined binary node.
   */
  const join = (left, name, right) => ({
    kind: "binary",
    start: left.start,
    end: Math.max(right.end, name.end),
    semantic: "boolean",
    left,
    name,
    right,
  });
  rules.or = () => {
    let node = rules.and();
    while (peek()?.kind === "logic" && peek()?.text === "or") {
      const name = /** @type {Token} */ (peek());
      at += 1;
      node = join(node, name, rules.and());
    }
    return node;
  };
  rules.and = () => {
    let node = rules.not();
    while (peek()?.kind === "logic" && peek()?.text === "and") {
      const name = /** @type {Token} */ (peek());
      at += 1;
      node = join(node, name, rules.not());
    }
    return node;
  };
  rules.not = () => {
    const name = peek();
    if (name?.kind === "logic" && name.text === "not") {
      at += 1;
      const operand = rules.not();
      return {
        kind: "not",
        start: name.start,
        end: Math.max(operand.end, name.end),
        semantic: "boolean",
        name,
        operand,
      };
    }
    return rules.compare();
  };
  rules.compare = () => {
    let node = rules.primary();
    for (;;) {
      const token = peek();
      if (!token) break;
      let symbol = "";
      /** @type {Token} */
      let name = token;
      if (token.kind === "compare") symbol = token.text;
      else if (token.kind === "membership") symbol = "in";
      else if (
        token.kind === "logic" &&
        token.text === "not" &&
        tokens[at + 1]?.text === "in"
      ) {
        symbol = "not in";
        const inside = /** @type {Token} */ (tokens[at + 1]);
        name = {
          kind: "membership",
          text: "not in",
          start: token.start,
          end: inside.end,
        };
        at += 1;
      } else break;
      at += 1;
      const rightToken = peek();
      const right = rules.primary();
      const left = node.semantic;
      const there = right.semantic;
      const info = OPERATORS.find(item => item.symbol === symbol);
      if (info?.ordered) {
        if (left === "boolean" || there === "boolean")
          report(
            name,
            `${symbol} compares numbers or text, not ${TYPE_WORDS.boolean}.`,
          );
        else if (
          !compatible(left, there) ||
          left === "none" ||
          there === "none"
        )
          report(
            name,
            `Compare numbers with numbers and text with text; this compares ${TYPE_WORDS[left]} with ${TYPE_WORDS[there]}.`,
          );
      } else if (info?.kind === "membership") {
        if (
          (left !== "string" && left !== "any") ||
          (there !== "string" && there !== "any")
        )
          report(name, `${symbol} needs text on both sides.`);
      } else if (
        !compatible(left, there) &&
        left !== "none" &&
        there !== "none"
      )
        report(
          name,
          `${TYPE_WORDS[left]} is never equal to ${TYPE_WORDS[there]}.`,
          "warning",
        );
      node = join(node, name, right);
      if (!rightToken) break;
    }
    return node;
  };
  rules.primary = () => {
    const token = peek();
    if (!token) {
      report(undefined, "The condition ends where a value is expected.");
      return missing("value");
    }
    if (
      token.kind === "number" ||
      token.kind === "string" ||
      token.kind === "literal"
    ) {
      at += 1;
      return {
        kind: "literal",
        start: token.start,
        end: token.end,
        semantic: token.semantic ?? "any",
        token,
      };
    }
    if (
      token.kind === "system" ||
      token.kind === "probe" ||
      token.kind === "output"
    ) {
      at += 1;
      return {
        kind: "term",
        start: token.start,
        end: token.end,
        semantic: token.semantic ?? "any",
        token,
      };
    }
    if (token.kind === "function") return rules.call(token);
    if (token.kind === "paren" && token.text === "(") {
      at += 1;
      const operand = rules.or();
      let end = operand.end;
      if (isText(")")) {
        end = /** @type {Token} */ (peek()).end;
        at += 1;
      } else report(token, "This parenthesis is never closed.");
      return {
        kind: "group",
        start: token.start,
        end,
        semantic: operand.semantic,
        operand,
      };
    }
    if (token.kind === "unknown") {
      at += 1;
      return {
        kind: "term",
        start: token.start,
        end: token.end,
        semantic: "any",
        token,
      };
    }
    report(token, `${token.text} cannot start a value here.`);
    at += 1;
    return missing("value");
  };
  rules.call = token => {
    at += 1;
    const info = FUNCTIONS.find(item => item.name === token.text);
    /** @type {TreeNode} */
    const node = {
      kind: "call",
      start: token.start,
      end: token.end,
      semantic: "boolean",
      name: token,
      args: [],
      close: token.end,
    };
    if (!isText("(")) {
      report(
        token,
        `${token.text} is called with parentheses, like ${token.text}(…).`,
      );
      node.close = token.end;
      return node;
    }
    at += 1;
    if (!isText(")")) {
      node.args?.push(rules.or());
      while (isText(",")) {
        at += 1;
        node.args?.push(rules.or());
      }
    }
    if (isText(")")) {
      node.close = /** @type {Token} */ (peek()).start;
      node.end = /** @type {Token} */ (peek()).end;
      at += 1;
    } else {
      report(token, `${token.text}( is never closed.`);
      node.close = node.args?.at(-1)?.end ?? token.end + 1;
      node.end = node.close;
    }
    if (info && node.args) {
      if (node.args.length !== info.args.length)
        report(
          token,
          `${info.name}() takes ${info.args.length} ${info.args.length === 1 ? "value" : "values"}, not ${node.args.length}.`,
        );
      else
        info.args.forEach((wanted, index) => {
          const got = node.args?.[index]?.semantic ?? "any";
          if (wanted === "string" && !compatible("string", got))
            report(
              token,
              `Value ${index + 1} of ${info.name}() must be text, not ${TYPE_WORDS[got]}.`,
            );
        });
      // A call short of arguments shows what each missing one is for.
      for (let index = node.args.length; index < info.args.length; index += 1) {
        const where = node.close ?? node.end;
        node.args.push({
          kind: "missing",
          start: where,
          end: where,
          semantic: info.args[index] ?? "any",
          label: info.labels[index] ?? "value",
          lead: index > 0 ? ", " : "",
        });
      }
    }
    return node;
  };
  /** @type {Semantic} */
  let semantic = "any";
  /** @type {TreeNode|null} */
  let tree = null;
  if (!tokens.length) report(undefined, "The condition is empty.");
  else {
    tree = rules.or();
    semantic = tree.semantic;
    const extra = peek();
    if (extra) {
      if (extra.kind !== "unknown")
        report(
          extra,
          `${extra.text} does not fit here. Join conditions with and, or.`,
        );
    } else if (semantic !== "boolean" && semantic !== "any") {
      const only =
        tokens.length === 1
          ? ` For example: ${tokens[0]?.text} ${semantic === "number" ? "> 0" : '== "…"'}.`
          : "";
      report(
        tokens[0],
        `This gives ${TYPE_WORDS[semantic]}, not true or false.${only}`,
      );
    }
  }
  return { tokens, issues, semantic, tree };
};
/**
 * @typedef {object} Guidance What may come next at the caret.
 * @property {"operand"|"operator"|"call"} position
 * @property {Semantic} left Type of the value just before, when an operator is due.
 * @property {boolean} closable Whether a `)` would close something open.
 * @property {OperatorInfo|null} pending The comparison waiting for its right side.
 * @property {{name:string,index:number}|null} call The helper being filled in.
 */
/** Work out what may be written at the caret, from the text before it.
 * @param {string} before Text before the fragment being typed.
 * @param {ConditionTerm[]} terms
 * @returns {Guidance}
 */
export const guide = (before, terms) => {
  /** @type {{call:string|null,index:number}[]} */
  const stack = [];
  let operand = true;
  /** @type {Semantic} */
  let left = "any";
  /** @type {OperatorInfo|null} */
  let pending = null;
  let callName = "";
  const tokens = tokenize(before, terms);
  tokens.forEach((token, index) => {
    if (token.kind === "function") {
      callName = token.text;
      operand = false;
      left = "boolean";
    } else if (token.kind === "paren" && token.text === "(") {
      stack.push({ call: callName || null, index: 0 });
      callName = "";
      operand = true;
      pending = null;
    } else if (token.kind === "paren") {
      stack.pop();
      operand = false;
      left = "boolean";
    } else if (token.kind === "comma") {
      const top = stack.at(-1);
      if (top) top.index += 1;
      operand = true;
      pending = null;
    } else if (token.kind === "logic" && token.text === "not" && !operand)
      pending = OPERATORS.find(item => item.symbol === "not in") ?? null;
    else if (token.kind === "logic") {
      operand = true;
      pending = null;
    } else if (token.kind === "compare" || token.kind === "membership") {
      const symbol =
        token.text === "in" && tokens[index - 1]?.text === "not"
          ? "not in"
          : token.text;
      pending = OPERATORS.find(item => item.symbol === symbol) ?? null;
      operand = true;
    } else {
      operand = false;
      left = token.semantic ?? "any";
      if (pending && pending.kind !== "logic") pending = null;
    }
  });
  const top = stack.at(-1);
  return {
    position: callName ? "call" : operand ? "operand" : "operator",
    left,
    closable: stack.length > 0,
    pending,
    call: top?.call ? { name: top.call, index: top.index } : null,
  };
};
/**
 * @typedef {object} Suggestion
 * @property {string} text What to insert.
 * @property {TokenKind} kind Which colour it carries.
 * @property {string} detail One line of explanation.
 * @property {string} [type] Plain name of the value type, for names.
 */
/** Suggest what may follow the text before the caret, narrowed by a fragment.
 * @param {string} before Text before the fragment being typed.
 * @param {string} fragment What the author has typed of the next word.
 * @param {ConditionTerm[]} terms
 * @returns {Suggestion[]}
 */
export const suggestNext = (before, fragment, terms) => {
  const state = guide(before, terms);
  /** @type {Suggestion[]} */
  const options = [];
  if (state.position === "call")
    options.push({ text: "(", kind: "paren", detail: "Open the call" });
  else if (state.position === "operator") {
    for (const info of OPERATORS)
      if (info.left.includes(state.left) || state.left === "any")
        options.push({
          text: info.symbol,
          kind: info.kind === "logic" ? "logic" : info.kind,
          detail: info.detail,
        });
    if (state.closable)
      options.push({
        text: ")",
        kind: "paren",
        detail: "Close the group or call",
      });
    if (
      state.call &&
      state.call.index <
        (FUNCTIONS.find(item => item.name === state.call?.name)?.args
          .length ?? 1) -
          1
    )
      options.push({ text: ",", kind: "comma", detail: "Next value" });
  } else {
    const wantedType = state.pending
      ? state.pending.kind === "membership"
        ? "string"
        : state.left
      : state.call
        ? (FUNCTIONS.find(item => item.name === state.call?.name)?.args[
            state.call.index
          ] ?? "any")
        : "any";
    const ordered = Boolean(state.pending?.ordered);
    for (const term of terms) {
      const semantic = semanticOf(term.value_type);
      if (wantedType !== "any" && semantic !== wantedType && semantic !== "any")
        continue;
      if (ordered && semantic === "boolean") continue;
      options.push({
        text: term.name,
        kind: term.kind,
        detail: term.detail,
        type: TYPE_WORDS[semantic],
      });
    }
    if (!state.pending) {
      options.push({ text: "not", kind: "logic", detail: "The opposite" });
      for (const info of FUNCTIONS)
        options.push({
          text: info.name,
          kind: "function",
          detail: info.detail,
        });
    }
    if (!ordered && (wantedType === "boolean" || wantedType === "any"))
      for (const literal of ["True", "False"])
        options.push({
          text: literal,
          kind: "literal",
          detail: "A fixed true or false",
        });
  }
  const wanted = fragment.toLowerCase();
  const starts = options.filter(item =>
    item.text.toLowerCase().startsWith(wanted),
  );
  if (!wanted) return starts;
  const inside = options.filter(
    item =>
      !item.text.toLowerCase().startsWith(wanted) &&
      item.text.toLowerCase().includes(wanted),
  );
  return [...starts, ...inside].filter(item => item.text !== fragment);
};
/** The text to write at the end of `before` for a chosen suggestion: words and
 * operators get a space around them, and brackets and commas hug their word.
 * @param {string} before Text before the insertion point.
 * @param {Suggestion} item
 * @returns {string}
 */
export const insertionFor = (before, item) => {
  const hugs = item.text === ")" || item.text === "(" || item.text === ",";
  const lead = before && !/[\s(]$/.test(before) && !hugs ? " " : "";
  let trail = " ";
  if (item.kind === "function") trail = "(";
  else if (item.text === "(" || item.text === ")") trail = "";
  return `${lead}${item.text}${trail}`;
};
