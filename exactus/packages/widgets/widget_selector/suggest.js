/** Context-aware suggestions for the selector language. */
/** @typedef {{label:string, insert?:string, adjust?:number, group:string, detail?:string, kind?:string, branch?:boolean, children?:Item[], flag?:string|undefined}} Item */
/** @typedef {{path:string, scope:"env"|"flow", type:"num"|"bool"|"text", value?:string|number|boolean, detail?:string}} VariableDef */
/** Environment variables every selector may use (types only; values come from the host). */
export const ENVIRONMENT_VARIABLES = /** @type {readonly VariableDef[]} */ (
  Object.freeze([
    { path: "device/width", scope: "env", type: "num", detail: "Viewport width of the active profile" },
    { path: "device/height", scope: "env", type: "num", detail: "Viewport height" },
    { path: "device/scale", scope: "env", type: "num", detail: "Device pixel ratio" },
    { path: "device/touch", scope: "env", type: "bool", detail: "Touch device" },
    { path: "device/profile", scope: "env", type: "text", detail: "Profile id" },
    { path: "device/mode", scope: "env", type: "text", detail: "Device mode" },
    { path: "env/colorScheme", scope: "env", type: "text", detail: "light or dark" },
    { path: "env/locale", scope: "env", type: "text", detail: "Browser locale" },
    { path: "env/reducedMotion", scope: "env", type: "bool", detail: "Reduced motion preferred" },
    { path: "target/url", scope: "env", type: "text", detail: "Address of the page under test" },
  ])
);
const PSEUDO_CLASSES = ":hover :focus :focus-visible :focus-within :active :checked :disabled :enabled :empty :first-child :last-child :only-child :first-of-type :last-of-type :root :target :link :any-link :required :optional :valid :invalid :read-only :read-write :placeholder-shown :default :indeterminate :in-range :out-of-range :visited :is() :where() :not() :has() :nth-child() :nth-last-child() :nth-of-type() :nth-last-of-type() :lang() :dir() :host :state() :popover-open :modal :fullscreen :defined".split(" ");
const PSEUDO_ELEMENTS = "::before ::after ::first-line ::first-letter ::marker ::placeholder ::selection ::backdrop ::file-selector-button ::cue ::slotted() ::part() ::highlight()".split(" ");
/**
 * Count page features under a scope, bounded by `cap` elements and cached.
 * @returns {{reads:number, invalidate:()=>void, sample:(scope?:string)=>any}} The sampler API.
 */
export const createSampler = (/** @type {{root?:Document|Element, cap?:number}} */ { root = document, cap = 2000 } = {}) => {
  /** @type {Map<string, any>} */
  const cache = new Map();
  const api = {
    reads: 0,
    invalidate: () => cache.clear(),
    /** @param {string} [scope] */
    sample: (scope = "") => {
      if (cache.has(scope)) return cache.get(scope);
      api.reads += 1;
      const elements = (() => {
        try {
          return [...root.querySelectorAll(scope ? `${scope} *` : "*")].slice(0, cap);
        } catch {
          return /** @type {Element[]} */ ([]);
        }
      })();
      const tags = new Map();
      const classes = new Map();
      const ids = new Map();
      const attributes = new Map();
      /**
       * Increment a map counter by one.
       * @param {Map<string, number>} map Target map.
       * @param {string} key Counter key.
       * @returns {Map<string, number>} The updated map.
       */
      const bump = (map, key) =>
        map.set(key, (map.get(key) ?? 0) + 1);
      for (const element of elements) {
        bump(tags, element.tagName.toLowerCase());
        for (const name of element.classList) bump(classes, name);
        if (element.id) bump(ids, element.id);
        for (const attribute of element.attributes)
          if (!["class", "id", "style"].includes(attribute.name)) bump(attributes, attribute.name);
      }
      const result = { tags, classes, ids, attributes, scanned: elements.length };
      cache.set(scope, result);
      return result;
    },
  };
  return api;
};
/**
 * Convert counted names into suggestion items filtered by a prefix.
 * @param {Map<string, number>} map Name counts.
 * @param {string} prefix Filter prefix.
 * @param {string} lead Prefix prepended to each suggestion.
 * @param {string} group Suggestion group.
 * @param {string} kind Suggestion kind.
 * @param {number} [limit] Maximum items.
 * @returns {Item[]} Suggestion items.
 */
const fromMap = (map, prefix, lead, group, kind, limit = 12) =>
  [...map.entries()]
    .filter(([name]) => name.toLowerCase().includes(prefix.toLowerCase()))
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, count]) => ({ label: `${lead}${name}`, insert: `${lead}${name}`, group, kind, detail: `${count}` }));
/**
 * Suggestions for the draft at the caret.
 * @returns {{title:string, items:Item[]}} Suggestion group and items.
 */
export const suggest = (/** @type {{draft:string, role?:string, scope?:string, signatures:Record<string, any>, predicateTypes:Record<string,string>, sampler:ReturnType<typeof createSampler>, saved:{name:string,count?:number|null}[], variables:VariableDef[], supports:(selector:string)=>boolean}} */ { draft, role = "", scope = "", signatures, predicateTypes, sampler, saved, variables, supports }) => {
  const sample = sampler.sample(scope);
  const title = role ? `Argument: ${role}` : "Suggestions";
  /**
   * List variable and saved-selector suggestions matching a query.
   * @param {string} q Query text.
   * @returns {Item[]} Suggestion items.
   */
  const mention = q => {
    const all = [...ENVIRONMENT_VARIABLES, ...variables.filter(v => !ENVIRONMENT_VARIABLES.some(e => e.path === v.path))];
    /**
     * Convert a variable definition into a suggestion item.
     * @param {VariableDef} v Variable definition.
     * @returns {Item} Suggestion item.
     */
    const leaf = v => ({
      label: v.path,
      insert: `{{${v.path}}}`,
      group: v.scope === "env" ? "Environment" : "Flow variables",
      kind: v.scope,
      detail: `${v.type}${v.value === undefined ? "" : ` = ${v.value}`}`,
    });
    const savedItems = saved.map(s => ({
      label: `@${s.name}`,
      insert: `[extended-selector="${s.name}"]`,
      group: "Saved selectors",
      kind: "saved",
      detail: s.count == null ? "" : `${s.count} now`,
    }));
    if (/^[.#:[]/.test(q)) return suggest({ draft: q, role, scope, signatures, predicateTypes, sampler, saved, variables, supports }).items;
    if (q.includes("/") || q.includes(".")) {
      const needle = q.toLowerCase();
      return [...all.map(leaf), ...savedItems].filter(i => i.label.toLowerCase().replace("@", "").startsWith(needle) || i.label.toLowerCase().includes(needle));
    }
    if (q) return [...all.map(leaf), ...savedItems].filter(i => i.label.toLowerCase().includes(q.toLowerCase()));
    /** @type {Map<string, Item[]>} */
    const branches = new Map();
    const loose = /** @type {Item[]} */ ([]);
    for (const v of all) {
      const slash = v.path.indexOf("/");
      if (slash < 0) loose.push(leaf(v));
      else {
        const key = v.path.slice(0, slash + 1);
        branches.set(key, [...(branches.get(key) ?? []), leaf(v)]);
      }
    }
    return [
      ...[...branches.entries()].map(([key, children]) => ({ label: key, group: key.startsWith("device") ? "Environment" : "Variables", kind: "env", branch: true, children, detail: `${children.length}` })),
      ...loose,
      ...savedItems,
    ];
  };
  if (draft.startsWith("@")) return { title: "Variables and saved selectors", items: mention(draft.slice(1)) };
  const q = draft;
  if (q.startsWith("::")) {
    const items = PSEUDO_ELEMENTS.filter(n => n.startsWith(q) && supports(n.replace("()", ""))).map(n => ({ label: n, insert: n, adjust: n.endsWith("()") ? -1 : 0, group: "Pseudo-elements", kind: "pseudo-element", flag: "unmatchable", detail: "not matchable from script" }));
    return { title, items };
  }
  if (q.startsWith(":"))
    return { title, items: PSEUDO_CLASSES.filter(n => n.startsWith(q) && supports(n.replace("()", ""))).map(n => ({ label: n, insert: n, adjust: n.endsWith("()") ? -1 : 0, group: "Pseudo-classes", kind: "pseudo-class", flag: n === ":visited" ? "unmatchable" : undefined, detail: n === ":visited" ? "never matches" : "" })) };
  if (q.startsWith(".")) {
    const items = fromMap(sample.classes, q.slice(1), ".", "Page", "class");
    if (!items.length && scope) return suggest({ draft, role, scope: "", signatures, predicateTypes, sampler, saved, variables, supports });
    return { title: scope ? `Classes inside ${scope}` : "Classes on the page", items };
  }
  if (q.startsWith("#")) {
    const items = fromMap(sample.ids, q.slice(1), "#", "Page", "id");
    if (!items.length && scope) return suggest({ draft, role, scope: "", signatures, predicateTypes, sampler, saved, variables, supports });
    return { title: "Ids on the page", items };
  }
  if (q.startsWith("[")) {
    const needle = q.slice(1).toLowerCase();
    /** @type {Item[]} */
    const items = Object.entries(predicateTypes)
      .filter(([name]) => name.toLowerCase().startsWith(needle))
      .slice(0, 12)
      .map(([name, type]) => ({
        label: `[${name}`,
        insert: type === "text" ? `[${name}*=""]` : type === "boolean" ? `[${name}=true]` : `[${name}>=0]`,
        adjust: type === "text" ? -2 : type === "number" ? -1 : 0,
        group: "Predicates",
        kind: "attribute",
        detail: type,
      }));
    for (const [name, count] of sample.attributes)
      if (name.toLowerCase().startsWith(needle) && !(name in predicateTypes))
        items.push({ label: `[${name}`, insert: `[${name}]`, group: "Page attributes", kind: "attribute", detail: `${count}` });
    return { title, items: items.slice(0, 16) };
  }
  const operators = Object.entries(signatures)
    .filter(([name]) => name.startsWith(q.toLowerCase()))
    .map(([name, s]) => ({ label: `${name}(`, insert: `${name}()`, adjust: -1, group: "Operators", kind: "operator", detail: s.roles.join(", ") }));
  const tags = fromMap(sample.tags, q, "", "Page", "tag", 8);
  if (!tags.length && scope && q) return suggest({ draft, role, scope: "", signatures, predicateTypes, sampler, saved, variables, supports });
  const savedItems = saved
    .filter(s => s.name.toLowerCase().includes(q.toLowerCase()))
    .map(s => ({ label: `@${s.name}`, insert: `[extended-selector="${s.name}"]`, group: "Saved selectors", kind: "saved", detail: s.count == null ? "" : `${s.count} now` }));
  return { title, items: [...tags, ...savedItems, ...operators].slice(0, 24) };
};
