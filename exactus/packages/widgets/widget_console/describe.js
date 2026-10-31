/** Describe any JavaScript value as a structured-clone-safe tree.
 *
 * The class source is embedded verbatim in sandbox workers, so every helper
 * lives on the class itself and nothing here may reference module scope.
 */
/**
 * @typedef {"object"|"array"|"map"|"set"|"date"|"regexp"|"error"|"typed"|"buffer"|"promise"|"node"|"boxed"|"weak"} ObjectKind
 */
/**
 * @typedef {object} Entry
 * @property {string} [k] Property name of an object or array member.
 * @property {Descriptor} [kd] Key of a Map member.
 * @property {Descriptor} v Member value.
 */
/**
 * @typedef {object} ErrorInfo
 * @property {string} name Error name.
 * @property {string} message Error message.
 * @property {string} stack Stack text, possibly empty.
 */
/**
 * @typedef {object} ObjectDescriptor
 * @property {"object"} t Descriptor tag.
 * @property {ObjectKind} kind Structural family.
 * @property {string} cls Constructor name.
 * @property {string} preview One-token summary such as `Array(3)`.
 * @property {number} [size] Item count for collections.
 * @property {Entry[]} [entries] Described members, capped by the limits.
 * @property {number} [more] Members omitted by the cap.
 * @property {boolean} [circular] True when this is a back reference.
 * @property {boolean} [lazy] True when the depth or node budget ended here.
 * @property {ErrorInfo} [error] Error details for `kind: "error"`.
 */
/**
 * @typedef {{t:"undefined"}|{t:"null"}|{t:"boolean",v:boolean}|{t:"number",v:number}|{t:"bigint",v:string}|{t:"string",v:string,more?:number}|{t:"symbol",v:string}|{t:"function",name:string,kind:"function"|"async"|"generator"|"class",src:string}|{t:"accessor",get:boolean,set:boolean}|ObjectDescriptor} Descriptor
 */
/**
 * @typedef {object} Limits
 * @property {number} depth Nesting levels described before `lazy`.
 * @property {number} entries Members described per container.
 * @property {number} text Characters kept per string.
 * @property {number} nodes Total descriptors allowed per call.
 */
/** @typedef {Limits & {budget:{left:number}}} Walk */
/** Describe JavaScript values as structured-clone-safe descriptor trees. */
export class Describer {
  /** @type {Readonly<Limits>} */
  static LIMITS = Object.freeze({ depth: 5, entries: 100, text: 10000, nodes: 3000 });
  /**
   * Describe one value.
   * @param {unknown} value Any value, including throwing proxies.
   * @param {Partial<Limits>} [limits] Overrides for the default limits.
   * @returns {Descriptor} A structured-clone-safe descriptor tree.
   */
  static describe = (value, limits = {}) => {
    const merged = { ...Describer.LIMITS, ...limits };
    return Describer.walk(value, 0, [], { ...merged, budget: { left: merged.nodes } });
  };
  /**
   * Describe one value at a depth.
   * @param {unknown} value Value to describe.
   * @param {number} depth Current nesting level.
   * @param {unknown[]} path Ancestors, for cycle detection.
   * @param {Walk} limits Active limits and shared node budget.
   * @returns {Descriptor} The descriptor.
   */
  static walk = (value, depth, path, limits) => {
    limits.budget.left -= 1;
    if (value === undefined) return { t: "undefined" };
    if (value === null) return { t: "null" };
    switch (typeof value) {
      case "boolean":
        return { t: "boolean", v: value };
      case "number":
        return { t: "number", v: value };
      case "bigint":
        return { t: "bigint", v: value.toString() };
      case "symbol":
        return { t: "symbol", v: value.toString() };
      case "string":
        return value.length > limits.text
          ? { t: "string", v: value.slice(0, limits.text), more: value.length - limits.text }
          : { t: "string", v: value };
      case "function":
        return Describer.func(value);
      default:
        return Describer.object(/** @type {object} */ (value), depth, path, limits);
    }
  };
  /**
   * Describe a function without calling it.
   * @param {Function} fn Function value.
   * @returns {Descriptor} The function descriptor.
   */
  static func = fn => {
    let src = "function () { [native code] }";
    let name = "";
    try {
      src = Function.prototype.toString.call(fn);
    } catch {
      // A revoked proxy has no readable source; the native placeholder stays.
    }
    try {
      name = typeof fn.name === "string" ? fn.name : "";
    } catch {
      // A hostile name accessor must not break describing; the empty name stays.
    }
    let kind = /** @type {"function"|"async"|"generator"|"class"} */ ("function");
    if (/^class\b/.test(src)) kind = "class";
    else if (/^(?:async\s+)?function\s*\*/.test(src) || /^(?:async\s+)?\*/.test(src)) kind = "generator";
    else if (/^async\b/.test(src)) kind = "async";
    return { t: "function", name, kind, src: src.slice(0, 240) };
  };
  /**
   * Read the constructor name of an object.
   * @param {object} value Object value.
   * @returns {string} Constructor name, or `Object` when none exists.
   */
  static className = value => {
    try {
      const ctor = /** @type {{constructor?:{name?:unknown}}} */ (value).constructor;
      if (ctor && typeof ctor.name === "string" && ctor.name) return ctor.name;
      return Object.getPrototypeOf(value) === null ? "Object (null prototype)" : "Object";
    } catch {
      return "Object";
    }
  };
  /**
   * Classify an object by its toString tag so other realms still match.
   * @param {object} value Object value.
   * @returns {{kind:ObjectKind, size?:number}} Structural family and size.
   */
  static classify = value => {
    if (Array.isArray(value)) return { kind: "array", size: value.length };
    const tag = Object.prototype.toString.call(value).slice(8, -1);
    if (ArrayBuffer.isView(value)) {
      return { kind: "typed", size: /** @type {{length?:number}} */ (value).length ?? value.byteLength };
    }
    switch (tag) {
      case "Map":
        return { kind: "map", size: /** @type {Map<unknown,unknown>} */ (value).size };
      case "Set":
        return { kind: "set", size: /** @type {Set<unknown>} */ (value).size };
      case "Date":
        return { kind: "date" };
      case "RegExp":
        return { kind: "regexp" };
      case "Error":
        return { kind: "error" };
      case "Promise":
        return { kind: "promise" };
      case "ArrayBuffer":
      case "SharedArrayBuffer":
        return { kind: "buffer", size: /** @type {ArrayBuffer} */ (value).byteLength };
      case "WeakMap":
      case "WeakSet":
      case "WeakRef":
        return { kind: "weak" };
      case "Number":
      case "String":
      case "Boolean":
      case "Symbol":
      case "BigInt":
        return { kind: "boxed" };
      default:
        break;
    }
    if (typeof Node !== "undefined" && value instanceof Node) return { kind: "node" };
    return { kind: "object" };
  };
  /**
   * Build the one-token summary for a classified object.
   * @param {object} value Object value.
   * @param {ObjectKind} kind Structural family.
   * @param {string} cls Constructor name.
   * @param {number|undefined} size Item count when known.
   * @returns {string} The summary.
   */
  static summary = (value, kind, cls, size) => {
    switch (kind) {
      case "array":
      case "map":
      case "set":
      case "typed":
      case "buffer":
        return `${cls}(${size ?? 0})`;
      case "date": {
        const time = /** @type {Date} */ (value).getTime();
        return Number.isNaN(time) ? "Invalid Date" : /** @type {Date} */ (value).toISOString();
      }
      case "regexp":
        return String(value);
      case "error":
        return `${/** @type {Error} */ (value).name}: ${/** @type {Error} */ (value).message}`;
      case "node": {
        const node = /** @type {{nodeName?:string, id?:string, className?:unknown}} */ (value);
        const id = node.id ? `#${node.id}` : "";
        const classes = typeof node.className === "string" && node.className ? `.${node.className.trim().split(/\s+/).join(".")}` : "";
        return `<${String(node.nodeName ?? "node").toLowerCase()}${id}${classes}>`;
      }
      case "boxed":
        return `${cls}(${JSON.stringify(/** @type {{valueOf:()=>unknown}} */ (value).valueOf()) ?? String(value)})`;
      default:
        return cls;
    }
  };
  /**
   * Describe an object, array, collection, error or similar value.
   * @param {object} value Object value.
   * @param {number} depth Current nesting level.
   * @param {unknown[]} path Ancestors, for cycle detection.
   * @param {Walk} limits Active limits and shared node budget.
   * @returns {Descriptor} The descriptor.
   */
  static object = (value, depth, path, limits) => {
    const cls = Describer.className(value);
    const { kind, size } = Describer.classify(value);
    /** @type {ObjectDescriptor} */
    const base = { t: "object", kind, cls, preview: Describer.summary(value, kind, cls, size) };
    if (size !== undefined) base.size = size;
    if (kind === "error") base.error = Describer.errorInfo(value);
    if (path.includes(value)) return { ...base, circular: true };
    if (depth >= limits.depth || limits.budget.left <= 0) return { ...base, lazy: true };
    path.push(value);
    try {
      const { entries, more } = Describer.members(value, kind, depth, path, limits);
      if (entries.length > 0) base.entries = entries;
      if (more > 0) base.more = more;
    } catch {
      base.lazy = true;
    } finally {
      path.pop();
    }
    return base;
  };
  /**
   * Read name, message and stack of an error-like value safely.
   * @param {object} value Error-like value.
   * @returns {ErrorInfo} Error details.
   */
  static errorInfo = value => {
    const read = (/** @type {string} */ key) => {
      try {
        const field = /** @type {Record<string, unknown>} */ (value)[key];
        return typeof field === "string" ? field : "";
      } catch {
        return "";
      }
    };
    return { name: read("name") || "Error", message: read("message"), stack: read("stack") };
  };
  /**
   * Describe the members of a classified object.
   * @param {object} value Object value.
   * @param {ObjectKind} kind Structural family.
   * @param {number} depth Current nesting level.
   * @param {unknown[]} path Ancestors, for cycle detection.
   * @param {Walk} limits Active limits and shared node budget.
   * @returns {{entries:Entry[], more:number}} Members and the omitted count.
   */
  static members = (value, kind, depth, path, limits) => {
    /** @type {Entry[]} */
    const entries = [];
    const next = (/** @type {unknown} */ item) => Describer.walk(item, depth + 1, path, limits);
    let total = 0;
    if (kind === "array" || kind === "typed") {
      const list = /** @type {ArrayLike<unknown>} */ (value);
      total = list.length;
      for (let index = 0; index < Math.min(total, limits.entries); index += 1)
        entries.push({ k: String(index), v: next(list[index]) });
    } else if (kind === "map") {
      const map = /** @type {Map<unknown, unknown>} */ (value);
      total = map.size;
      for (const [key, item] of map) {
        if (entries.length >= limits.entries) break;
        entries.push({ kd: next(key), v: next(item) });
      }
    } else if (kind === "set") {
      const set = /** @type {Set<unknown>} */ (value);
      total = set.size;
      for (const item of set) {
        if (entries.length >= limits.entries) break;
        entries.push({ v: next(item) });
      }
    } else if (kind === "object" || kind === "error" || kind === "node" || kind === "boxed") {
      const keys = Object.keys(value).filter(key => kind !== "error" || (key !== "stack" && key !== "message"));
      total = keys.length;
      for (const key of keys.slice(0, limits.entries)) {
        const own = Object.getOwnPropertyDescriptor(value, key);
        if (own && (own.get || own.set))
          entries.push({ k: key, v: { t: "accessor", get: Boolean(own.get), set: Boolean(own.set) } });
         else
          entries.push({ k: key, v: next(own?.value) });
      }
      if (kind === "error" && "cause" in value) {
        entries.push({ k: "cause", v: next(/** @type {{cause:unknown}} */ (value).cause) });
      }
    }
    return { entries, more: Math.max(0, total - limits.entries) };
  };
}
export const describe = Describer.describe;
