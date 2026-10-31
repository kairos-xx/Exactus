/** Text rendering of value descriptors: previews, plain text and printf-style substitution. */
/** @typedef {import("./describe.js").Descriptor} Descriptor */
/** @typedef {import("./describe.js").Entry} Entry */
/**
 * @typedef {object} FormatOptions
 * @property {boolean} [nested] Quote strings, as inside a container.
 * @property {number} [depth] Container levels expanded inline.
 * @property {number} [entries] Members shown per container.
 */
const IDENTIFIER = /^[A-Za-z_$][\w$]*$/;
/**
 * Format a property key for display.
 * @param {string} key Property name.
 * @returns {string} The key, quoted when it is not an identifier or index.
 */
const formatKey = key => IDENTIFIER.test(key) || /^\d+$/.test(key) ? key : JSON.stringify(key);
/**
 * Format a number with its sign of zero preserved.
 * @param {number} value Number value.
 * @returns {string} Display text.
 */
export const formatNumber = value => Object.is(value, -0) ? "-0" : String(value);
/**
 * Format a function descriptor.
 * @param {Extract<Descriptor, {t:"function"}>} descriptor Function descriptor.
 * @returns {string} Display text.
 */
export const formatFunction = descriptor => {
  if (descriptor.kind === "class") return `class ${descriptor.name || "(anonymous)"}`;
  const prefix = { async: "async ƒ", generator: "ƒ*", function: "ƒ" }[descriptor.kind];
  return `${prefix} ${descriptor.name || "(anonymous)"}()`;
};
/**
 * Format members of a container as `a, b, …`.
 * @param {Entry[]} entries Members to show.
 * @param {boolean} truncated Whether members were omitted.
 * @param {(entry:Entry)=>string} show Member formatter.
 * @param {number} limit Members shown.
 * @returns {string} Joined members.
 */
const formatMembers = (entries, truncated, show, limit) => {
  const shown = entries.slice(0, limit).map(show);
  if (truncated || entries.length > limit) shown.push("…");
  return shown.join(", ");
};
/**
 * Format any descriptor as one line of text.
 * @param {Descriptor} descriptor Value descriptor.
 * @param {FormatOptions} [options] Formatting options.
 * @returns {string} Display text.
 */
export const formatValue = (descriptor, options = {}) => {
  const { nested = false, depth = 1, entries: limit = 5 } = options;
  switch (descriptor.t) {
    case "undefined":
      return "undefined";
    case "null":
      return "null";
    case "boolean":
      return String(descriptor.v);
    case "number":
      return formatNumber(descriptor.v);
    case "bigint":
      return `${descriptor.v}n`;
    case "symbol":
      return descriptor.v;
    case "string": {
      const tail = descriptor.more ? `… +${descriptor.more} characters` : "";
      return nested ? `${JSON.stringify(descriptor.v)}${tail}` : `${descriptor.v}${tail}`;
    }
    case "function":
      return formatFunction(descriptor);
    case "accessor":
      return descriptor.get && descriptor.set ? "(getter/setter)" : descriptor.get ? "(getter)" : "(setter)";
    default:
      break;
  }
  if (descriptor.circular) return "[Circular]";
  const inner = { nested: true, depth: depth - 1, entries: limit };
  const members = descriptor.entries ?? [];
  const truncated = Boolean(descriptor.more);
  const expandable = !descriptor.lazy && depth > 0;
  switch (descriptor.kind) {
    case "error":
      return nested ? `[${descriptor.preview}]` : descriptor.error?.stack || descriptor.preview;
    case "array":
    case "typed": {
      const lead = descriptor.kind === "typed" ? `${descriptor.preview} ` : "";
      if (!expandable) return descriptor.preview;
      return `${lead}[${formatMembers(members, truncated, entry => formatValue(entry.v, inner), limit)}]`;
    }
    case "map": {
      if (!expandable) return descriptor.preview;
      /** Format one map member as `key => value`. */
      const show = (/** @type {Entry} */ entry) => `${entry.kd ? formatValue(entry.kd, inner) : "?"} => ${formatValue(entry.v, inner)}`;
      return `${descriptor.preview} {${formatMembers(members, truncated, show, limit)}}`;
    }
    case "set": {
      if (!expandable) return descriptor.preview;
      return `${descriptor.preview} {${formatMembers(members, truncated, entry => formatValue(entry.v, inner), limit)}}`;
    }
    case "object": {
      const lead = descriptor.cls === "Object" ? "" : `${descriptor.cls} `;
      if (!expandable) return lead ? descriptor.cls : "{…}";
      if (members.length === 0) return `${lead}{}`;
      /** Format one object member as `key: value`. */
      const show = (/** @type {Entry} */ entry) => `${formatKey(entry.k ?? "")}: ${formatValue(entry.v, inner)}`;
      return `${lead}{ ${formatMembers(members, truncated, show, limit)} }`;
    }
    case "promise":
      return "Promise {…}";
    case "weak":
      return `${descriptor.cls} {…}`;
    default:
      return descriptor.preview;
  }
};
/**
 * Format descriptors the way a console line reads in plain text.
 * @param {Descriptor[]} parts Message parts.
 * @returns {string} Space-joined text.
 */
export const partsText = parts =>
  parts.map(part => formatValue(part, { depth: 3, entries: 100 })).join(" ");
/**
 * Apply printf-style substitutions to the first message part.
 * Supports `%s %d %i %f %o %O %c %%`; `%c` consumes its argument and
 * styling is dropped, object specifiers keep the value inspectable.
 * @param {Descriptor[]} parts Raw message parts.
 * @returns {Descriptor[]} Parts after substitution.
 */
export const applyFormat = parts => {
  const [first, ...rest] = parts;
  if (first?.t !== "string" || !first.v.includes("%") || rest.length === 0) return parts;
  /** @type {Descriptor[]} */
  const out = [];
  let text = "";
  let used = 0;
  /** Push the accumulated text as a string part. */
  const flush = () => {
    if (text) out.push({ t: "string", v: text });
    text = "";
  };
  const source = first.v;
  for (let index = 0; index < source.length; index += 1) {
    const char = source.charAt(index);
    const spec = source.charAt(index + 1);
    if (char !== "%" || spec === "") {
      text += char;
      continue;
    }
    if (spec === "%") {
      text += "%";
      index += 1;
      continue;
    }
    if (!"sdifoOc".includes(spec) || used >= rest.length) {
      text += char;
      continue;
    }
    const arg = /** @type {Descriptor} */ (rest[used]);
    used += 1;
    index += 1;
    if (spec === "c") continue;
    if (spec === "o" || spec === "O") {
      flush();
      out.push(arg);
      continue;
    }
    if (spec === "s") {
      text += formatValue(arg, { depth: 0 });
      continue;
    }
    const numeric = arg.t === "number" ? arg.v : arg.t === "string" ? Number(arg.v) : arg.t === "boolean" ? Number(arg.v) : Number.NaN;
    text += formatNumber(spec === "f" ? numeric : Math.trunc(numeric));
  }
  flush();
  return [...out, ...rest.slice(used)];
};
