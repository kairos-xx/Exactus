/**
 * ExtendedSelector — portable DOM/visual query engine.
 *
 * Browser-native, dependency-free, synchronous core. It supports CSS atoms,
 * extended predicates, boolean/structural/spatial relations, open Shadow DOM,
 * slots and pseudo-element computed-style predicates.
 */
/**
 * Portable DOM/visual query engine combining CSS atoms with extended
 * predicates, structural relations, and spatial operators.
 *
 * @typedef {{type: "atom", value: string} | {type: "call", name: string, args: AstNode[], rawArgs?: string[]}} AstNode
 * @typedef {{code: string, message: string, offset: number, line: number, column: number, length: number, lineText: string, pointer: string, severity: "error" | "warning", suggestion?: {offset: number, length: number, text: string}, role?: string}} SelectorDiagnostic
 * @typedef {{strict?: boolean, deduplicate?: boolean, sortDocumentOrder?: boolean, deep?: boolean}} EngineOptions
 * @typedef {{strict: boolean, deduplicate: boolean, sortDocumentOrder: boolean, deep: boolean}} ResolvedEngineOptions
 * @typedef {{root?: Document | Element, universe?: Element[], deep?: boolean, variables?: Record<string, string | number | boolean>}} QueryOptions
 * @typedef {(element: Element, context: {engine: ExtendedSelector, key: string}) => unknown} PredicateResolver
 * @typedef {(context: {engine: ExtendedSelector, node: AstNode, universe: Element[], args: AstNode[], raw: string[]}) => Element[]} OperatorHandler
 * @typedef {{key: string, operator: string, expected: string}} PredicateRule
 * @typedef {{key: string, reference: string, operator: string, expected: string}} ReferenceRule
 * @typedef {{selector: string, engine: string, specificity: number[], fragility: number, length: number, exact: boolean, unique: boolean}} SelectorCandidate
 * @typedef {SelectorCandidate & {candidates: SelectorCandidate[]}} BestSelectorResult
 * @typedef {{getSingleSelector?: (element: Element, options?: {root: Document | Element}) => string | undefined, getMultiSelector?: (targets: Element[], options?: {root: Document | Element}) => string | undefined, optimize?: (selector: string, root: Document | Element) => string | undefined}} OptimalSelectApi
 * @typedef {{engines?: string[], generator?: (target: Element | Element[], context?: {root: Document | Element}) => unknown, optimal?: OptimalSelectApi, finder?: (element: Element, context?: {root: Document | Element}) => string, includeCandidates?: boolean, deep?: boolean}} GeneratorOptions
 */
export class ExtendedSelector extends EventTarget {
  static VERSION = "2.1.0";
  static TOLERANCE_OPERATORS = Object.freeze([
    "left_of",
    "right_of",
    "above",
    "below",
    "overlaps",
    "inside",
    "near",
    "aligned_left",
    "aligned_center_x",
    "nearest",
    "nearest_above",
    "nearest_below",
    "nearest_left",
    "nearest_right",
  ]);
  static ORDERING_OPERATORS = Object.freeze([
    "sort",
    "nearest",
    "nearest_above",
    "nearest_below",
    "nearest_left",
    "nearest_right",
  ]);
  /**
   * Operator signatures: argument counts, the role each argument plays and
   * what kind of value goes there. `lint()` reads the counts from here and
   * editors read the roles to name empty slots.
   *
   * @type {Readonly<Record<string, {min: number, max: number, roles: string[], optionalFrom: number, kinds: string[], variadicRole?: string, summary: string}>>}
   */
  static SIGNATURES = (() => {
    /** Operator name, min, max, roles, kinds, variadic role, summary. */
    const rows = /** @type {[string, number, number, string[], string[], string | undefined, string][]} */ ([
      ["not", 1, 1, ["condition"], ["expression"], undefined, "Elements that do not satisfy the condition."],
      ["apply", 2, 2, ["base", "expression"], ["selector", "expression"], undefined, "Apply an expression to the base set."],
      ["has", 2, 2, ["base", "condition"], ["selector", "expression"], undefined, "Base elements with a descendant satisfying the condition."],
      ["children", 2, Infinity, ["base", "child"], ["selector", "expression"], "child", "Base elements whose children satisfy each argument in order."],
      ["child", 3, 3, ["base", "index", "condition"], ["selector", "number", "expression"], undefined, "The child at an index satisfying the condition."],
      ["sibling", 2, 2, ["base", "condition"], ["selector", "expression"], undefined, "An adjacent sibling satisfying the condition."],
      ["siblings", 2, 2, ["base", "condition"], ["selector", "expression"], undefined, "Siblings satisfying the condition."],
      ["prev", 2, 2, ["base", "condition"], ["selector", "expression"], undefined, "The previous sibling satisfying the condition."],
      ["next", 2, 2, ["base", "condition"], ["selector", "expression"], undefined, "The next sibling satisfying the condition."],
      ["parent", 2, 2, ["base", "condition"], ["selector", "expression"], undefined, "The parent satisfying the condition."],
      ["ancestor", 2, 2, ["base", "condition"], ["selector", "expression"], undefined, "An ancestor satisfying the condition."],
      ["closest", 2, 2, ["base", "condition"], ["selector", "expression"], undefined, "The closest ancestor satisfying the condition."],
      ["before", 2, 2, ["base", "reference"], ["selector", "selector"], undefined, "Base elements before the reference in document order."],
      ["after", 2, 2, ["base", "reference"], ["selector", "selector"], undefined, "Base elements after the reference in document order."],
      ["any", 3, 3, ["base", "relation", "condition"], ["selector", "string", "expression"], undefined, "Some related element satisfies the condition."],
      ["all", 3, 3, ["base", "relation", "condition"], ["selector", "string", "expression"], undefined, "Every related element satisfies the condition."],
      ["none", 3, 3, ["base", "relation", "condition"], ["selector", "string", "expression"], undefined, "No related element satisfies the condition."],
      ["left_of", 2, 3, ["base", "reference", "tolerance"], ["selector", "selector", "tolerance"], undefined, "Base elements left of the reference."],
      ["right_of", 2, 3, ["base", "reference", "tolerance"], ["selector", "selector", "tolerance"], undefined, "Base elements right of the reference."],
      ["above", 2, 3, ["base", "reference", "tolerance"], ["selector", "selector", "tolerance"], undefined, "Base elements above the reference."],
      ["below", 2, 3, ["base", "reference", "tolerance"], ["selector", "selector", "tolerance"], undefined, "Base elements below the reference."],
      ["overlaps", 2, 3, ["base", "reference", "tolerance"], ["selector", "selector", "tolerance"], undefined, "Base elements overlapping the reference."],
      ["inside", 2, 3, ["base", "reference", "tolerance"], ["selector", "selector", "tolerance"], undefined, "Base elements inside the reference."],
      ["near", 2, 3, ["base", "reference", "distance"], ["selector", "selector", "number"], undefined, "Base elements within a distance of the reference."],
      ["aligned_left", 2, 3, ["base", "reference", "tolerance"], ["selector", "selector", "tolerance"], undefined, "Base elements whose left edge aligns with the reference."],
      ["aligned_center_x", 2, 3, ["base", "reference", "tolerance"], ["selector", "selector", "tolerance"], undefined, "Base elements whose horizontal centre aligns with the reference."],
      ["shadow", 2, 2, ["base", "condition"], ["selector", "expression"], undefined, "Elements inside the base shadow root satisfying the condition."],
      ["slot", 2, 2, ["base", "condition"], ["selector", "expression"], undefined, "Slotted elements satisfying the condition."],
      ["pseudo", 3, 3, ["base", "pseudo", "condition"], ["selector", "string", "expression"], undefined, "Base elements whose pseudo-element style satisfies the condition."],
      ["and", 2, Infinity, ["expression"], ["expression"], "expression", "Every argument holds."],
      ["or", 2, Infinity, ["expression"], ["expression"], "expression", "At least one argument holds."],
      ["nand", 2, Infinity, ["expression"], ["expression"], "expression", "Not every argument holds."],
      ["nor", 2, Infinity, ["expression"], ["expression"], "expression", "No argument holds."],
      ["xor", 2, Infinity, ["expression"], ["expression"], "expression", "An odd number of arguments hold."],
      ["xnor", 2, Infinity, ["expression"], ["expression"], "expression", "An even number of arguments hold."],
      ["sort", 2, Infinity, ["base", "key"], ["selector", "keys"], "key", "Order the base set by one or more keys."],
      ["nearest", 2, 3, ["base", "reference", "limit"], ["selector", "selector", "number"], undefined, "The base element nearest the reference."],
      ["nearest_above", 2, 3, ["base", "reference", "limit"], ["selector", "selector", "number"], undefined, "The nearest base element above the reference."],
      ["nearest_below", 2, 3, ["base", "reference", "limit"], ["selector", "selector", "number"], undefined, "The nearest base element below the reference."],
      ["nearest_left", 2, 3, ["base", "reference", "limit"], ["selector", "selector", "number"], undefined, "The nearest base element left of the reference."],
      ["nearest_right", 2, 3, ["base", "reference", "limit"], ["selector", "selector", "number"], undefined, "The nearest base element right of the reference."],
      ["media", 1, 1, ["query"], ["string"], undefined, "Elements only when the media query matches."],
    ]);
    return Object.freeze(
      Object.fromEntries(
        rows.map(([name, min, max, roles, kinds, variadicRole, summary]) => [
          name,
          Object.freeze({
            min,
            max,
            roles,
            optionalFrom: min,
            kinds,
            ...(variadicRole ? { variadicRole } : {}),
            summary,
          }),
        ]),
      ),
    );
  })();
  static CAPABILITIES = Object.freeze({
    environment: Object.freeze(["media"]),
    ordering: Object.freeze([
      "sort",
      "nearest",
      "nearest_above",
      "nearest_below",
      "nearest_left",
      "nearest_right",
    ]),
    comparators: Object.freeze([
      "=",
      "!=",
      "<",
      "<=",
      ">",
      ">=",
      "^=",
      "$=",
      "*=",
      "~=",
      "~~",
    ]),
    boolean: Object.freeze(["and", "or", "not", "nand", "nor", "xor", "xnor"]),
    structural: Object.freeze([
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
    ]),
    spatial: Object.freeze([
      "left_of",
      "right_of",
      "above",
      "below",
      "overlaps",
      "inside",
      "near",
      "aligned_left",
      "aligned_center_x",
    ]),
    dom: Object.freeze(["shadow", "slot", "pseudo"]),
    generators: Object.freeze([
      "register",
      "css-selector-generator",
      "optimal-select",
      "optimal-select.optimize",
      "@medv/finder",
      "native",
    ]),
    namespaces: Object.freeze(["attr:", "prop:", "data:", "aria:"]),
    cssPseudoClasses: Object.freeze(
      ":is :where :not :has :nth-child :nth-last-child :nth-of-type :nth-last-of-type :first-child :last-child :only-child :first-of-type :last-of-type :only-of-type :empty :root :scope :hover :active :focus :focus-visible :focus-within :target :target-within :visited :link :any-link :local-link :checked :indeterminate :default :disabled :enabled :read-only :read-write :placeholder-shown :required :optional :valid :invalid :in-range :out-of-range :user-valid :user-invalid :blank :autofill :playing :paused :seeking :buffering :stalled :muted :volume-locked :fullscreen :modal :popover-open :picture-in-picture :open :closed :defined :dir :lang :state :host :host-context".split(
        " ",
      ),
    ),
    cssPseudoElements: Object.freeze(
      "::before ::after ::first-line ::first-letter ::marker ::placeholder ::selection ::backdrop ::file-selector-button ::cue ::slotted ::part ::highlight ::target-text ::spelling-error ::grammar-error".split(
        " ",
      ),
    ),
    predicateTypes: Object.freeze({
      ...Object.fromEntries(
        [
          "textContent",
          "innerText",
          "innerHTML",
          "normalizedText",
          "value",
          "role",
          "accessible_name",
        ].map(name => [name, "text"]),
      ),
      ...Object.fromEntries(
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
        ].map(name => [name, "boolean"]),
      ),
      ...Object.fromEntries(
        [
          "viewport_ratio",
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
          "distance_to_viewport_top",
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
          "scrollX",
          "scrollY",
          "scroll_x",
          "scroll_y",
          "scroll_x_max",
          "scroll_y_max",
          "scroll_x_percent",
          "scroll_y_percent",
        ].map(name => [name, "number"]),
      ),
    }),
    referenceGeometry: Object.freeze([
      "left",
      "right",
      "top",
      "bottom",
      "center_x",
      "center_y",
      "gap_left",
      "gap_right",
      "gap_top",
      "gap_bottom",
      "overlap_x",
      "overlap_y",
      "width_ratio",
      "height_ratio",
      "x_percent",
      "y_percent",
      "distance",
      "intersection",
      "inside",
      "contains_geometry",
      "z_ref",
    ]),
  });
  /**
   * @param {Document | Element} [root]
   * @param {EngineOptions} [options]
   */
  constructor(root = document, options = {}) {
    super();
    this.root = root;
    this.options = /** @type {ResolvedEngineOptions} */ ({
      strict: true,
      deduplicate: true,
      sortDocumentOrder: true,
      deep: false,
      ...options,
    });
    this.predicates = /** @type {Map<string, PredicateResolver>} */ (new Map());
    this.operators = /** @type {Map<string, OperatorHandler>} */ (new Map());
    this.definitions = /** @type {Map<string, string>} */ (new Map());
    this.resolving = /** @type {Set<string>} */ (new Set());
  }
  /**
   * Merge option overrides into the live engine configuration.
   *
   * @param {EngineOptions} [options]
   * @returns {this}
   */
  configure(options = {}) {
    Object.assign(this.options, options);
    return this;
  }
  /**
   * Replace the document root used by subsequent queries.
   *
   * @param {Document | Element} root
   * @returns {this}
   */
  setRoot(root) {
    this.root = root;
    return this;
  }
  /**
   * Register a named predicate resolver.
   *
   * @param {string} name
   * @param {PredicateResolver} resolver
   * @returns {this}
   * @throws {TypeError} When `name` is empty or `resolver` is not a function.
   */
  registerPredicate(name, resolver) {
    if (typeof resolver !== "function")
      throw new TypeError("Predicate resolver must be a function.");
    this.predicates.set(name, resolver);
    return this;
  }
  /**
   * Remove a previously registered predicate.
   *
   * @param {string} name
   * @returns {this}
   */
  unregisterPredicate(name) {
    this.predicates.delete(name);
    return this;
  }
  /**
   * Register a named operator handler.
   *
   * @param {string} name
   * @param {OperatorHandler} handler
   * @returns {this}
   * @throws {TypeError} When `name` is empty or `handler` is not a function.
   */
  registerOperator(name, handler) {
    if (typeof handler !== "function")
      throw new TypeError("Operator handler must be a function.");
    this.operators.set(name.toLowerCase(), handler);
    return this;
  }
  /**
   * Remove a previously registered operator.
   *
   * @param {string} name
   * @returns {this}
   */
  unregisterOperator(name) {
    this.operators.delete(name.toLowerCase());
    return this;
  }
  /**
   * @param {Node} left
   * @param {Node} right
   * @returns {number}
   */
  static documentOrder = (left, right) =>
    left === right
      ? 0
      : left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_PRECEDING
        ? 1
        : -1;
  /**
   * True when the expression's outermost operator fixes the result order.
   * @param {AstNode} ast
   * @returns {boolean}
   */
  static isOrdered = ast =>
    ast.type === "call" &&
    ExtendedSelector.ORDERING_OPERATORS.includes(ast.name);
  /**
   * Collect the element universe under a root scope.
   *
   * @param {Document | Element} [root]
   * @param {boolean} [deep] Whether to descend into shadow roots.
   * @returns {Element[]}
   */
  universe(root, deep = this.options.deep) {
    const scope = root ?? this.root;
    const own = scope instanceof Element ? [scope] : [];
    if (!deep) return [...own, ...scope.querySelectorAll("*")];
    /** @type {(node: Document | Element | ShadowRoot) => Element[]} */
    const walk = node =>
      [...node.querySelectorAll("*")].flatMap(element =>
        element.shadowRoot ? [element, ...walk(element.shadowRoot)] : [element],
      );
    return [...own, ...walk(scope)];
  }
  /**
   * Resolve a Playwright-style "a >> b" chain: each step searches inside the
   * previous matches, including their open shadow roots.
   * @param {string} chain
   * @returns {Element[]}
   */
  queryChain(chain) {
    /** @type {(Document | Element)[]} */
    let scopes = [this.root];
    let found = /** @type {Element[]} */ ([]);
    for (const step of chain.split(" >> ")) {
      found = [
        ...new Set(scopes.flatMap(scope => this.deepQueryAll(step, scope))),
      ];
      scopes = found;
    }
    return found;
  }
  /**
   * Evaluate an expression and return all matching elements.
   *
   * @param {string | AstNode} expression
   * @param {QueryOptions} [options]
   * @returns {Element[]}
   */
  query(expression, options = {}) {
    const started = performance.now();
    const ast =
      typeof expression === "string"
        ? this.parse(
            ExtendedSelector.resolveVariables(expression, options.variables),
          )
        : expression;
    const deep = options.deep ?? this.options.deep;
    const universe =
      options.universe ?? this.universe(options.root ?? this.root, deep);
    let elements = this.evaluateAst(ast, universe);
    if (this.options.deduplicate) elements = [...new Set(elements)];
    if (this.options.sortDocumentOrder && !ExtendedSelector.isOrdered(ast)) {
      // Elements in different shadow trees have no document order between
      // them, so a deep query keeps the order of its own tree walk.
      const position = new Map(
        universe.map((element, index) => [element, index]),
      );
      elements.sort((a, b) =>
        deep && position.has(a) && position.has(b)
          ? (position.get(a) ?? 0) - (position.get(b) ?? 0)
          : ExtendedSelector.documentOrder(a, b),
      );
    }
    elements.forEach(element => {
      ExtendedSelector.decorate(element);
    });
    this.dispatchEvent(
      new CustomEvent("query", {
        detail: {
          expression,
          ast,
          elements,
          count: elements.length,
          duration: performance.now() - started,
        },
      }),
    );
    return elements;
  }
  /**
   * Query a scope and every open shadow root below it.
   * @param {string} selector
   * @param {Document | Element | ShadowRoot} root
   * @returns {Element[]}
   */
  static deepQueryAll = (selector, root) => {
    const found = [...root.querySelectorAll(selector)];
    const hosts = [
      ...(root instanceof Element ? [root] : []),
      ...root.querySelectorAll("*"),
    ].filter(element => element.shadowRoot);
    for (const host of hosts)
      found.push(
        ...ExtendedSelector.deepQueryAll(
          selector,
          /** @type {ShadowRoot} */
          (host.shadowRoot),
        ),
      );
    return [...new Set(found)];
  };
  /**
   * Query the root and every open shadow root below it.
   * @param {string} selector
   * @param {Document | Element | ShadowRoot} [root]
   * @returns {Element[]}
   */
  deepQueryAll(selector, root) {
    return ExtendedSelector.deepQueryAll(selector, root ?? this.root);
  }
  /**
   * Attach the `register` accessor pair to an element.
   *
   * @param {Element} element
   * @returns {Element & {register: string | null}}
   */
  static decorate = element => {
    if (!Object.hasOwn(element, "register"))
      Object.defineProperty(element, "register", {
        configurable: true,
        enumerable: false,
        get: () => element.getAttribute("extended-selector"),
        set: name => {
          ExtendedSelector.claim(element, name);
        },
      });
    return /** @type {Element & {register: string | null}} */ (element);
  };
  /**
   * Assign a named registration to an element.
   *
   * @param {Element} element
   * @param {string | null} name
   * @param {{replace?: boolean}} [options] replace moves the name from its holder.
   * @returns {Element}
   */
  static register = (element, name, { replace = false } = {}) => {
    ExtendedSelector.decorate(element);
    ExtendedSelector.claim(element, name, replace);
    return element;
  };
  /**
   * Set or clear the registration name, keeping names unique in the document.
   * @param {Element} element
   * @param {string | null | undefined} name
   * @param {boolean} [replace] Move the name from its current holder.
   * @returns {void}
   */
  static claim = (element, name, replace = false) => {
    const wanted =
      name === null || name === undefined ? "" : String(name).trim();
    if (wanted === "") {
      element.removeAttribute("extended-selector");
      return;
    }
    if (!/^[A-Za-z][\w-]*$/.test(wanted))
      throw new SyntaxError(
        `Invalid register name "${wanted}": use letters, digits, "_" or "-", starting with a letter.`,
      );
    const holder = ExtendedSelector.deepQueryAll(
      `[extended-selector="${wanted}"]`,
      element.ownerDocument,
    ).find(other => other !== element);
    if (holder && !replace)
      throw new Error(
        `Register name "${wanted}" is already used by another element.`,
      );
    holder?.removeAttribute("extended-selector");
    element.setAttribute("extended-selector", wanted);
  };
  /**
   * Clear an element's named registration.
   *
   * @param {Element} element
   * @returns {Element}
   */
  static unregister = element => {
    ExtendedSelector.decorate(element).register = null;
    return element;
  };
  /**
   * Name an expression so [extended-selector="name"] resolves through it.
   * @param {string} name
   * @param {string} expression
   * @returns {this}
   * @throws {SyntaxError} When the name or expression is invalid.
   */
  define(name, expression) {
    if (!/^[A-Za-z][\w./-]*$/.test(name))
      throw new SyntaxError(`Invalid selector name "${name}".`);
    this.parse(expression);
    this.definitions.set(name, expression);
    return this;
  }
  /**
   * Remove a named expression.
   * @param {string} name
   * @returns {this}
   */
  undefine(name) {
    this.definitions.delete(name);
    return this;
  }
  /**
   * Replace [extended-selector="name"] with the exact CSS of the defined match.
   * Nothing is written to the page: the attribute is only a name here.
   * @param {string} atom
   * @returns {string}
   * @throws {SyntaxError} When a definition refers to itself.
   */
  expandDefinitions(atom) {
    if (!this.definitions.size || !atom.includes("extended-selector"))
      return atom;
    return atom.replace(
      /\[extended-selector=(["'])([^"']+)\1\]/g,
      (whole, _quote, name) => {
        const expression = this.definitions.get(name);
        if (expression === undefined) return whole;
        if (this.resolving.has(name))
          throw new SyntaxError(
            `Selector "${name}" refers to itself (${[...this.resolving, name].join(" -> ")}).`,
          );
        this.resolving.add(name);
        try {
          const matches = this.query(expression);
          if (!matches.length) return ":not(*)";
          const css = this.bestSelector(matches, {
            engines: ["native"],
            includeCandidates: false,
          }).selector;
          return `:is(${css})`;
        } finally {
          this.resolving.delete(name);
        }
      },
    );
  }
  /**
   * Return the first element matching an expression.
   *
   * @param {string} expression
   * @param {QueryOptions} [options]
   * @returns {Element | null}
   */
  queryOne(expression, options = {}) {
    return this.query(expression, options)[0] ?? null;
  }
  /**
   * Count the elements matching an expression.
   *
   * @param {string} expression
   * @param {QueryOptions} [options]
   * @returns {number}
   */
  count(expression, options = {}) {
    return this.query(expression, options).length;
  }
  /**
   * Report whether any element matches an expression.
   *
   * @param {string} expression
   * @param {QueryOptions} [options]
   * @returns {boolean}
   */
  exists(expression, options = {}) {
    return this.queryOne(expression, options) !== null;
  }
  /**
   * Report whether a single element matches an expression.
   *
   * @param {Element} element
   * @param {string} expression
   * @returns {boolean}
   */
  matches(element, expression) {
    return this.evaluateAst(this.parse(expression), [element]).includes(
      element,
    );
  }
  /**
   * Filter an element list down to expression matches.
   *
   * @param {Iterable<Element>} elements
   * @param {string} expression
   * @returns {Element[]}
   */
  filter(elements, expression) {
    return this.evaluateAst(this.parse(expression), [...elements]);
  }
  /**
   * @param {string} expression
   * @param {number} offset
   * @returns {{offset: number, line: number, column: number}}
   */
  static position = (expression, offset) => {
    const lines = expression.slice(0, Math.max(0, offset)).split("\n");
    return {
      offset,
      line: lines.length,
      column: (lines.at(-1)?.length ?? 0) + 1,
    };
  };
  /**
   * @param {string} expression
   * @param {string} message
   * @param {number} [offset]
   * @param {number} [length]
   * @param {string} [code]
   * @param {{severity?: "error" | "warning", suggestion?: {offset: number, length: number, text: string}, role?: string}} [extra]
   * @returns {SelectorDiagnostic}
   */
  static diagnostic = (
    expression,
    message,
    offset = 0,
    length = 1,
    code = "syntax",
    extra = {},
  ) => {
    const position = ExtendedSelector.position(expression, offset);
    return {
      code,
      message,
      ...position,
      length: Math.max(1, length),
      lineText: expression.split("\n")[position.line - 1] ?? "",
      pointer: `${" ".repeat(Math.max(0, position.column - 1))}${"^".repeat(Math.max(1, length))}`,
      severity: extra.severity ?? "error",
      ...(extra.suggestion ? { suggestion: extra.suggestion } : {}),
      ...(extra.role ? { role: extra.role } : {}),
    };
  };
  /**
   * The name in `names` nearest to `name` (edit distance 2 or less).
   *
   * @param {string} name
   * @param {readonly string[]} names
   * @returns {string | undefined}
   */
  static nearestName = (name, names) => {
    /** @param {string} a @param {string} b */
    const distance = (a, b) => {
      let row = Array.from({ length: b.length + 1 }, (_, i) => i);
      for (let i = 1; i <= a.length; i += 1) {
        const next = [i];
        for (let j = 1; j <= b.length; j += 1)
          next.push(
            Math.min(
              (next[j - 1] ?? 0) + 1,
              (row[j] ?? 0) + 1,
              (row[j - 1] ?? 0) + (a[i - 1] === b[j - 1] ? 0 : 1),
            ),
          );
        row = next;
      }
      return row[b.length] ?? Infinity;
    };
    let best;
    let bestDistance = 3;
    for (const candidate of names) {
      const d = distance(name, candidate);
      if (d < bestDistance) {
        best = candidate;
        bestDistance = d;
      }
    }
    return best;
  };
  /**
   * @param {string} expression
   * @param {string} message
   * @param {number} [offset]
   * @param {number} [length]
   * @param {string} [code]
   * @returns {SyntaxError & {diagnostic: SelectorDiagnostic}}
   */
  static syntaxError = (
    expression,
    message,
    offset = 0,
    length = 1,
    code = "syntax",
  ) => {
    const diagnostic = ExtendedSelector.diagnostic(
      expression,
      message,
      offset,
      length,
      code,
    );
    const error = new SyntaxError(
      `${message} at ${diagnostic.line}:${diagnostic.column}\n${diagnostic.lineText}\n${diagnostic.pointer}`,
    );
    Object.assign(error, {
      diagnostic,
    });
    return /** @type {SyntaxError & {diagnostic: SelectorDiagnostic}} */ (
      error
    );
  };
  /**
   * List the `{{path}}` and frozen `{{path=JSON}}` variables in an expression.
   * An escaped `\\{{` and a `{{` that never closes are not variables.
   *
   * @param {string} expression
   * @returns {{path: string, frozen: boolean, value?: string | number | boolean, offset: number, length: number}[]}
   */
  static variables = expression => {
    const found = [];
    for (const match of String(expression).matchAll(/(\\)?\{\{([^{}]*)\}\}/g)) {
      if (match[1]) continue;
      const inner = (match[2] ?? "").trim();
      const eq = inner.indexOf("=");
      const path = (eq < 0 ? inner : inner.slice(0, eq)).trim();
      if (!/^[A-Za-z_][\w./-]*$/.test(path)) continue;
      /** @type {string | number | boolean | undefined} */
      let value;
      if (eq >= 0)
        try {
          value = JSON.parse(inner.slice(eq + 1).trim());
        } catch {
          value = inner.slice(eq + 1).trim();
        }
      found.push({
        path,
        frozen: eq >= 0,
        ...(eq >= 0 && value !== undefined ? { value } : {}),
        offset: match.index ?? 0,
        length: match[0].length,
      });
    }
    return found;
  };
  /**
   * Replace variables with typed values. With `values === null` each
   * variable becomes a same-length placeholder (`0…` outside quotes, `x…`
   * inside), which keeps every diagnostic offset exact for `lint()`.
   *
   * @param {string} expression
   * @param {Record<string, string | number | boolean> | null} values
   * @returns {{text: string, missing: string[]}}
   */
  static substitute = (expression, values) => {
    const source = String(expression);
    const spans = ExtendedSelector.variables(source);
    const missing = /** @type {string[]} */ ([]);
    let out = "";
    let cursor = 0;
    let quote = "";
    let index = 0;
    const advance = (/** @type {number} */ to) => {
      for (; index < to; index += 1) {
        const char = source.charAt(index);
        if (quote) {
          if (char === "\\") index += 1;
          else if (char === quote) quote = "";
        } else if (char === '"' || char === "'") quote = char;
      }
    };
    for (const span of spans) {
      advance(span.offset);
      out += source.slice(cursor, span.offset);
      cursor = span.offset + span.length;
      if (values === null) {
        out += (quote ? "x" : "0").repeat(span.length);
        index = cursor;
        continue;
      }
      const value = span.frozen ? span.value : values[span.path];
      if (value === undefined) {
        missing.push(span.path);
        out += source.slice(span.offset, cursor);
      } else if (typeof value === "string")
        out += quote
          ? value.replace(/\\/g, "\\\\").split(quote).join(`\\${quote}`)
          : `"${value.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
      else out += String(value);
      index = cursor;
    }
    out += source.slice(cursor);
    return {
      text: values === null ? out : out.replace(/\\\{\{/g, "{{"),
      missing,
    };
  };
  /**
   * Substitute live and frozen variables for evaluation, or fail loudly.
   *
   * @param {string} expression
   * @param {Record<string, string | number | boolean>} [variables]
   * @returns {string}
   * @throws {Error} With `code` "missing-variable" when a live variable has no value.
   */
  static resolveVariables = (expression, variables = {}) => {
    if (!expression.includes("{{")) return expression;
    const { text, missing } = ExtendedSelector.substitute(expression, variables);
    if (missing.length)
      throw Object.assign(new Error(`No value for {{${missing[0]}}}.`), {
        code: "missing-variable",
      });
    return text;
  };
  /**
   * Check an expression and return its diagnostics.
   *
   * @param {unknown} expression
   * @param {{warnings?: boolean}} [options] Include warnings (default: errors only).
   * @returns {SelectorDiagnostic[]}
   */
  lint(expression, options = {}) {
    if (typeof expression === "string" && expression.includes("{{")) {
      const { text } = ExtendedSelector.substitute(expression, null);
      if (text !== expression) return this.lint(text, options);
    }
    const diagnostics = /** @type {SelectorDiagnostic[]} */ ([]);
    if (typeof expression !== "string")
      return [
        ExtendedSelector.diagnostic(
          "",
          "Expression must be a string.",
          0,
          1,
          "type",
        ),
      ];
    if (!expression.trim())
      return [
        ExtendedSelector.diagnostic(
          expression,
          "Expression must not be empty.",
          0,
          1,
          "empty",
        ),
      ];
    const stack =
      /** @type {{char: string, index: number, quote?: boolean}[]} */
      ([]);
    const pairs = /** @type {Record<string, string>} */ ({
      ")": "(",
      "]": "[",
    });
    let quote = "";
    let escaped = false;
    for (let index = 0; index < expression.length; index += 1) {
      const char = expression.charAt(index);
      if (quote) {
        if (escaped) escaped = false;
        else if (char === "\\") escaped = true;
        else if (char === quote) {
          quote = "";
          stack.pop();
        }
        continue;
      }
      if (char === '"' || char === "'") {
        quote = char;
        stack.push({
          char,
          index,
          quote: true,
        });
        continue;
      }
      if (char === "(" || char === "[")
        stack.push({
          char,
          index,
        });
      else if (char in pairs) {
        const top = stack.at(-1);
        if (!top || top.quote || top.char !== pairs[char]) {
          diagnostics.push(
            ExtendedSelector.diagnostic(
              expression,
              `Unexpected "${char}".`,
              index,
              1,
              "unexpected-close",
            ),
          );
          break;
        }
        stack.pop();
      }
    }
    if (quote) {
      const item = [...stack].reverse().find(entry => entry.quote);
      diagnostics.push(
        ExtendedSelector.diagnostic(
          expression,
          `Unterminated ${quote} string.`,
          item?.index ?? expression.length - 1,
          Math.max(
            1,
            expression.length - (item?.index ?? expression.length - 1),
          ),
          "unterminated-string",
        ),
      );
    } else if (stack.length) {
      const item = stack.at(-1);
      if (item)
        diagnostics.push(
          ExtendedSelector.diagnostic(
            expression,
            `Unclosed "${item.char}".`,
            item.index,
            1,
            "unclosed-delimiter",
          ),
        );
    }
    if (diagnostics.length) return diagnostics;
    try {
      /**
       * @param {AstNode} node
       * @returns {void}
       */
      const inspect = node => {
        if (node.type === "atom") {
          const atom = node.value.trim();
          try {
            document
              .createDocumentFragment()
              .querySelector(
                atom.replace(
                  /\[[\w:-]+(?:\([^)]+\))?\s*(?:~~|~=|\^=|\$=|\*=|<=|>=|!=|=|<|>)\s*(?:"(?:\\.|[^"])*"|'(?:\\.|[^'])*'|[^\]]+)\]/g,
                  (match, offset, whole) =>
                    ExtendedSelector.isCssBracket(whole, offset)
                      ? match
                      : offset === ExtendedSelector.subjectStart(whole)
                        ? "*"
                        : "",
                ) || "*",
              );
          } catch (error) {
            const base = Math.max(0, expression.indexOf(atom));
            const known = new Set(
              [
                ...ExtendedSelector.CAPABILITIES.cssPseudoClasses,
                ...ExtendedSelector.CAPABILITIES.cssPseudoElements,
              ].map(name => name.toLowerCase()),
            );
            const unknown = [...atom.matchAll(/::?[a-zA-Z][\w-]*/g)].find(
              match => !known.has(match[0].toLowerCase()),
            );
            const nearest = unknown
              ? ExtendedSelector.nearestName(
                  unknown[0].toLowerCase(),
                  [...known].filter(name => name.startsWith("::") === unknown[0].startsWith("::")),
                )
              : undefined;
            diagnostics.push(
              unknown
                ? ExtendedSelector.diagnostic(
                    expression,
                    `Unknown pseudo "${unknown[0]}"${nearest ? `; did you mean "${nearest}"?` : "."}`,
                    base + (unknown.index ?? 0),
                    unknown[0].length,
                    "unknown-pseudo",
                    nearest
                      ? {
                          suggestion: {
                            offset: base + (unknown.index ?? 0),
                            length: unknown[0].length,
                            text: nearest,
                          },
                        }
                      : {},
                  )
                : ExtendedSelector.diagnostic(
                    expression,
                    `Invalid CSS atom: ${error instanceof Error ? error.message : String(error)}`,
                    base,
                    Math.max(1, atom.length),
                    "invalid-css",
                  ),
            );
            return;
          }
          if (options.warnings) {
            const base = Math.max(0, expression.indexOf(atom));
            for (const match of atom.matchAll(/::?[a-zA-Z][\w-]*/g)) {
              const name = match[0].toLowerCase();
              const at = base + (match.index ?? 0);
              if (
                name.startsWith("::") ||
                [":before", ":after", ":first-line", ":first-letter"].includes(name)
              )
                diagnostics.push(
                  ExtendedSelector.diagnostic(
                    expression,
                    `${match[0]} cannot be matched from script. Use pseudo(sel, "${name.startsWith("::") ? name : `:${name}`}", expr) to test its style.`,
                    at,
                    match[0].length,
                    "pseudo-element-unmatchable",
                    { severity: "warning" },
                  ),
                );
              else if (name === ":visited")
                diagnostics.push(
                  ExtendedSelector.diagnostic(
                    expression,
                    ":visited never matches from script, for privacy.",
                    at,
                    match[0].length,
                    "visited-unmatchable",
                    { severity: "warning" },
                  ),
                );
            }
          }
          return;
        }
        const signature = ExtendedSelector.SIGNATURES[node.name];
        const arity = /** @type {[number, number] | undefined} */ (
          signature ? [signature.min, signature.max] : undefined
        );
        if (!arity && !this.operators.has(node.name)) {
          diagnostics.push(
            ExtendedSelector.diagnostic(
              expression,
              `Unknown operator "${node.name}".`,
              Math.max(0, expression.indexOf(`${node.name}(`)),
              node.name.length,
              "unknown-operator",
              (() => {
                const near = ExtendedSelector.nearestName(node.name, [
                  ...Object.keys(ExtendedSelector.SIGNATURES),
                  ...this.operators.keys(),
                ]);
                return near
                  ? {
                      suggestion: {
                        offset: Math.max(0, expression.indexOf(`${node.name}(`)),
                        length: node.name.length,
                        text: near,
                      },
                    }
                  : {};
              })(),
            ),
          );
          return;
        }
        const argCount = node.type === "call" ? node.args.length : 0;
        if (arity && (argCount < arity[0] || argCount > arity[1])) {
          const role = signature?.roles[argCount] ?? signature?.variadicRole;
          diagnostics.push(
            ExtendedSelector.diagnostic(
              expression,
              `${node.name}() expects ${arity[0] === arity[1] ? arity[0] : `${arity[0]}–${arity[1] === Infinity ? "∞" : arity[1]}`} arguments; received ${argCount}.`,
              Math.max(0, expression.indexOf(`${node.name}(`)),
              node.name.length,
              "arity",
              argCount < arity[0] && role !== undefined ? { role } : {},
            ),
          );
        }
        if (node.name === "media") {
          const query = (node.rawArgs?.[0] ?? "").replace(
            /^(["'])([\s\S]*)\1$/,
            "$2",
          );
          if (
            matchMedia(query).media === "not all" &&
            query.trim() !== "not all"
          )
            diagnostics.push(
              ExtendedSelector.diagnostic(
                expression,
                `Invalid media query: ${query}`,
                Math.max(0, expression.indexOf("media(")),
                5,
                "invalid-media",
              ),
            );
          return;
        }
        let inspected = ExtendedSelector.TOLERANCE_OPERATORS.includes(node.name)
          ? node.args.slice(0, 2)
          : node.args;
        if (node.name === "sort")
          try {
            inspected = ExtendedSelector.sortLayout(node.rawArgs ?? [])
              .referenceForm
              ? node.args.slice(0, 2)
              : node.args.slice(0, 1);
          } catch (error) {
            diagnostics.push(
              ExtendedSelector.diagnostic(
                expression,
                error instanceof Error ? error.message : String(error),
                Math.max(0, expression.indexOf("sort(")),
                4,
                "sort-keys",
              ),
            );
            return;
          }

        inspected.forEach(inspect);
      };
      inspect(this.parseExtended(expression));
    } catch (error) {
      diagnostics.push(
        ExtendedSelector.diagnostic(
          expression,
          error instanceof Error ? error.message : String(error),
          0,
          Math.max(1, expression.length),
          "parse",
        ),
      );
    }
    return diagnostics;
  }
  /**
   * Render a diagnostic as a human-readable string.
   *
   * @param {SelectorDiagnostic} diagnostic
   * @returns {string}
   */
  static formatDiagnostic = diagnostic =>
    `${diagnostic.code}: ${diagnostic.message} (${diagnostic.line}:${diagnostic.column})\n${diagnostic.lineText}\n${diagnostic.pointer}`;
  /**
   * Tokenize an expression into a token stream.
   *
   * @param {string} expression
   * @returns {AstNode}
   */
  parse(expression) {
    const diagnostics = this.lint(expression);
    if (diagnostics.length) {
      const first = /** @type {SelectorDiagnostic} */ (diagnostics[0]);
      const error = ExtendedSelector.syntaxError(
        typeof expression === "string" ? expression : "",
        first.message,
        first.offset,
        first.length,
        first.code,
      );
      Object.assign(error, {
        diagnostics,
      });
      throw error;
    }
    return this.parseExtended(expression);
  }
  /**
   * Compile an expression into an executable matcher.
   *
   * @param {string} expression
   * @returns {((options?: QueryOptions) => Element[]) & {ast: AstNode, expression: string}}
   */
  compile(expression) {
    const ast = this.parse(expression);
    return Object.assign(
      /**
       * @param {QueryOptions} [options]
       * @returns {Element[]}
       */
      (options = {}) => this.query(ast, options),
      {
        ast,
        expression,
      },
    );
  }
  /**
   * Validate an expression and return its diagnostics.
   *
   * @param {string} expression
   * @returns {{valid: boolean, ast: AstNode | null, error: string | null, diagnostics: SelectorDiagnostic[]}}
   */
  validate(expression) {
    const diagnostics = this.lint(expression);
    return diagnostics.length
      ? {
          valid: false,
          ast: null,
          error: /** @type {SelectorDiagnostic} */ (diagnostics[0]).message,
          diagnostics,
        }
      : {
          valid: true,
          ast: this.parseExtended(expression),
          error: null,
          diagnostics: [],
        };
  }
  /**
   * Evaluate an expression and report totals plus a match count for every
   * node of its tree.
   *
   * @param {string} expression
   * @param {QueryOptions & {limit?: number}} [options] `limit` caps the scanned elements (default 5000).
   * @returns {{count: number, visible: number, inView: number, enabled: number, scanned: number, truncated: boolean, elapsedMs: number, nodes: {path: number[], label: string, kind: string, count: number}[], first: {tag: string, css: string, text: string} | null}}
   */
  stats(expression, options = {}) {
    const started = performance.now();
    const ast = this.parse(
      ExtendedSelector.resolveVariables(expression, options.variables),
    );
    const limit = options.limit ?? 5000;
    const full = this.universe(
      options.root ?? this.root,
      options.deep ?? this.options.deep,
    );
    const truncated = full.length > limit;
    const universe = truncated ? full.slice(0, limit) : full;
    const matches = [...new Set(this.evaluateAst(ast, universe))];
    /** @type {{path: number[], label: string, kind: string, count: number}[]} */
    const nodes = [];
    /** @param {AstNode} node @param {number[]} path */
    const walk = (node, path) => {
      const atom = node.type === "atom" ? node.value.trim() : "";
      const kind =
        node.type === "call"
          ? "operator"
          : atom.startsWith("[extended-selector=")
            ? "saved"
            : atom.startsWith("#")
              ? "id"
              : atom.startsWith(".")
                ? "class"
                : atom.startsWith("[")
                  ? "attribute"
                  : atom.startsWith("::")
                    ? "pseudo-element"
                    : atom.startsWith(":")
                      ? "pseudo-class"
                      : "tag";
      nodes.push({
        path,
        label: node.type === "call" ? `${node.name}(` : atom,
        kind,
        count: new Set(this.evaluateAst(node, universe)).size,
      });
      if (node.type === "call")
        node.args.forEach((child, index) => {
          walk(child, [...path, index]);
        });
    };
    walk(ast, []);
    const flag = (/** @type {Element} */ element, /** @type {string} */ key) =>
      this.predicateValue(element, key) === "true";
    const head = matches[0];
    return {
      count: matches.length,
      visible: matches.filter(element => flag(element, "visible")).length,
      inView: matches.filter(element => flag(element, "in_viewport")).length,
      enabled: matches.filter(element => flag(element, "enabled")).length,
      scanned: universe.length,
      truncated,
      elapsedMs: performance.now() - started,
      nodes,
      first: head
        ? {
            tag: head.tagName.toLowerCase(),
            css: `${head.tagName.toLowerCase()}${head.id ? `#${head.id}` : ""}${[...head.classList].map(name => `.${name}`).join("")}`,
            text: (/** @type {HTMLElement} */ (head).innerText ?? head.textContent ?? "")
              .replace(/\s+/g, " ")
              .trim()
              .slice(0, 80),
          }
        : null,
    };
  }
  /**
   * Describe how an expression evaluates against the root.
   *
   * @param {string} expression
   * @param {QueryOptions} [options]
   * @returns {{expression: string, ast: AstNode, count: number, elements: Element[], summary: string}}
   */
  explain(expression, options = {}) {
    const ast = this.parse(expression);
    const elements = this.query(ast, options);
    return {
      expression,
      ast,
      count: elements.length,
      elements,
      summary: `${elements.length} element${elements.length === 1 ? "" : "s"} matched`,
    };
  }
  /**
   * @param {string} value
   * @returns {string}
   */
  static escape = value => CSS.escape(value);
  /**
   * @param {string} value
   * @param {string} [delimiter]
   * @returns {string[]}
   */
  static splitTopLevel = (value, delimiter = ",") => {
    const result = /** @type {string[]} */ ([]);
    let depth = 0;
    let quote = "";
    let start = 0;
    [...value].forEach((character, index) => {
      if (quote) {
        if (character === quote && value.charAt(index - 1) !== "\\") quote = "";
      } else if (`"'`.includes(character)) quote = character;
      else if ("([".includes(character)) depth += 1;
      else if (")]".includes(character)) depth -= 1;
      else if (!depth && character === delimiter) {
        result.push(value.slice(start, index).trim());
        start = index + 1;
      }
    });
    result.push(value.slice(start).trim());
    return result.filter(Boolean);
  };
  /**
   * @param {string} pattern
   * @returns {RegExp}
   */
  static wildcardRegex = pattern =>
    new RegExp(
      `^${pattern.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replaceAll("*", ".*")}$`,
      "s",
    );
  /**
   * @param {string} value
   * @returns {number[] | null}
   */
  static color = value => {
    const probe = document.createElement("span");
    probe.style.color = value.trim();
    if (!probe.style.color) return null;
    document.body.append(probe);
    const resolved = getComputedStyle(probe).color;
    probe.remove();
    const values = resolved.match(/[\d.]+/g)?.map(Number) ?? [];
    return values.length >= 3
      ? [values[0] ?? 0, values[1] ?? 0, values[2] ?? 0, values[3] ?? 1]
      : null;
  };
  /**
   * @param {string} actual
   * @param {string} expected
   * @param {number} similarity
   * @returns {boolean}
   */
  static colorSimilarity = (actual, expected, similarity) => {
    const left = ExtendedSelector.color(actual);
    const right = ExtendedSelector.color(expected);
    if (!left || !right) return false;
    return (
      1 -
        Math.sqrt(
          left
            .slice(0, 3)
            .reduce(
              (sum, value, index) => sum + (value - (right[index] ?? 0)) ** 2,
              0,
            ),
        ) /
          Math.sqrt(3 * 255 ** 2) >=
      similarity
    );
  };
  /**
   * @param {Element} element
   * @param {Element} reference
   * @returns {string}
   */
  static stacking = (element, reference) => {
    const a = element.getBoundingClientRect();
    const b = reference.getBoundingClientRect();
    if (!(
      Math.min(a.right, b.right) > Math.max(a.left, b.left) &&
      Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top)
    ))
      return "none";
    const stack = document.elementsFromPoint(
      Math.max(a.left, b.left) +
        Math.max(1, Math.min(a.right, b.right) - Math.max(a.left, b.left)) / 2,
      Math.max(a.top, b.top) +
        Math.max(1, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)) / 2,
    );
    const ai = stack.indexOf(element);
    const bi = stack.indexOf(reference);
    return ai < 0 || bi < 0
      ? "unknown"
      : ai < bi
        ? "front"
        : ai > bi
          ? "back"
          : "same";
  };
  /**
   * @param {string} actual
   * @param {string} operator
   * @param {string} expected
   * @returns {boolean}
   */
  static compareValue = (actual, operator, expected) => {
    const value = String(actual);
    if (operator === "^=") return value.startsWith(expected);
    if (operator === "$=") return value.endsWith(expected);
    if (operator === "*=") return value.includes(expected);
    if (operator === "~~") {
      const parts = ExtendedSelector.splitTopLevel(expected);
      const threshold = Number.parseFloat(parts.at(-1) ?? "");
      const wanted = parts.slice(0, -1).join(",").trim();
      if (
        !wanted ||
        !Number.isFinite(threshold) ||
        threshold < 0 ||
        threshold > 1
      )
        throw new SyntaxError(
          'Fuzzy comparison expects ~~"text",<similarity 0..1>.',
        );
      return ExtendedSelector.stringSimilarity(value, wanted) >= threshold;
    }
    if (operator === "~=") {
      const regex = expected.match(/^\/((?:\\.|[^/])*)\/([dgimsuvy]*)$/);
      if (regex)
        try {
          return new RegExp(regex[1] ?? "", regex[2] ?? "").test(value);
        } catch (error) {
          throw new SyntaxError(
            `Invalid regular expression: ${error instanceof Error ? error.message : String(error)}`,
          );
        }

      const parts = ExtendedSelector.splitTopLevel(expected);
      const similarity = Number.parseFloat(parts.at(-1) ?? "");
      const color = parts.slice(0, -1).join(",").trim();
      if (
        !color ||
        !Number.isFinite(similarity) ||
        similarity < 0 ||
        similarity > 1
      )
        throw new SyntaxError(
          "~= expects /regex/flags or <color>,<similarity 0..1>.",
        );
      return ExtendedSelector.colorSimilarity(value, color, similarity);
    }
    if (expected.includes("*") && ["=", "!="].includes(operator)) {
      const match = ExtendedSelector.wildcardRegex(expected).test(value);
      return operator === "=" ? match : !match;
    }
    /**
     * @param {string} input
     * @returns {number}
     */
    const number = input => Number.parseFloat(input);
    if (Number.isFinite(number(value)) && Number.isFinite(number(expected))) {
      const left = number(value);
      const right = number(expected);
      return operator === "="
        ? left === right
        : operator === "!="
          ? left !== right
          : operator === "<"
            ? left < right
            : operator === "<="
              ? left <= right
              : operator === ">"
                ? left > right
                : left >= right;
    }
    return operator === "="
      ? value === expected
      : operator === "!="
        ? value !== expected
        : operator === "<"
          ? value < expected
          : operator === "<="
            ? value <= expected
            : operator === ">"
              ? value > expected
              : value >= expected;
  };
  /**
   * Return normalized Levenshtein similarity in the inclusive range 0..1.
   * @param {string} left
   * @param {string} right
   * @returns {number}
   */
  static stringSimilarity = (left, right) => {
    if (left === right) return 1;
    if (!left.length || !right.length) return 0;
    let previous = Array.from(
      {
        length: right.length + 1,
      },
      (_, index) => index,
    );
    [...left].forEach((a, row) => {
      const current = [row + 1];
      [...right].forEach((b, column) => {
        current.push(
          Math.min(
            (current[column] ?? 0) + 1,
            (previous[column + 1] ?? 0) + 1,
            (previous[column] ?? 0) + Number(a !== b),
          ),
        );
      });
      previous = current;
    });
    return 1 - (previous.at(-1) ?? 0) / Math.max(left.length, right.length);
  };
  /**
   * @param {string} value
   * @param {number} [reference]
   * @returns {number}
   */
  static unitValue = (value, reference = 1) => {
    const number = Number.parseFloat(value);
    return value.trim().endsWith("%") ? (reference * number) / 100 : number;
  };
  /**
   * @param {Element} element
   * @param {Element} reference
   * @returns {Record<string, number>}
   */
  static geometry = (element, reference) => {
    const a = element.getBoundingClientRect();
    const b = reference.getBoundingClientRect();
    return {
      left: a.left - b.left,
      right: a.right - b.right,
      top: a.top - b.top,
      bottom: a.bottom - b.bottom,
      center_x: (a.left + a.right - b.left - b.right) / 2,
      center_y: (a.top + a.bottom - b.top - b.bottom) / 2,
      gap_left: b.left - a.right,
      gap_right: a.left - b.right,
      gap_top: b.top - a.bottom,
      gap_bottom: a.top - b.bottom,
      overlap_x: Math.max(
        0,
        Math.min(a.right, b.right) - Math.max(a.left, b.left),
      ),
      overlap_y: Math.max(
        0,
        Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top),
      ),
      width_ratio: a.width / Math.max(b.width, 1) * 100,
      height_ratio: a.height / Math.max(b.height, 1) * 100,
      x_percent: (a.left - b.left) / Math.max(b.width, 1) * 100,
      y_percent: (a.top - b.top) / Math.max(b.height, 1) * 100,
      distance: Math.hypot(
        (a.left + a.right - b.left - b.right) / 2,
        (a.top + a.bottom - b.top - b.bottom) / 2,
      ),
      intersection:
        a.width * a.height
          ? (Math.max(
              0,
              Math.min(a.right, b.right) - Math.max(a.left, b.left),
            ) *
              Math.max(
                0,
                Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top),
              ) /
              (a.width * a.height)) *
            100
          : 0,
      inside: Number(
        a.left >= b.left &&
          a.right <= b.right &&
          a.top >= b.top &&
          a.bottom <= b.bottom,
      ),
      contains_geometry: Number(
        b.left >= a.left &&
          b.right <= a.right &&
          b.top >= a.top &&
          b.bottom <= a.bottom,
      ),
    };
  };
  /**
   * Resolve a reference expression to concrete values.
   *
   * @param {Element} element
   * @param {string} expression
   * @returns {Element[]}
   * @throws {SyntaxError} When the reference expression is malformed.
   */
  resolveReference(element, expression) {
    const token = expression.trim();
    if (token === "parent")
      return element.parentElement ? [element.parentElement] : [];
    if (token === "prev")
      return element.previousElementSibling
        ? [element.previousElementSibling]
        : [];
    if (token === "next")
      return element.nextElementSibling ? [element.nextElementSibling] : [];
    if (token === "siblings")
      return element.parentElement
        ? [...element.parentElement.children].filter(node => node !== element)
        : [];
    if (token.startsWith("closest:")) {
      const match = element.closest(token.slice(8));
      return match ? [match] : [];
    }
    try {
      return [...this.root.querySelectorAll(token)].filter(
        node => node !== element,
      );
    } catch {
      throw new SyntaxError(`Invalid reference selector: ${token}`);
    }
  }
  /**
   * Evaluate one predicate rule against a reference.
   *
   * @param {Element} element
   * @param {string} key
   * @param {string} referenceExpression
   * @param {string} operator
   * @param {string} expected
   * @returns {boolean}
   * @throws {SyntaxError} When the predicate rule is malformed.
   */
  referencePredicate(element, key, referenceExpression, operator, expected) {
    return this.resolveReference(element, referenceExpression).some(
      reference => {
        if (key === "z_ref")
          return ExtendedSelector.compareValue(
            ExtendedSelector.stacking(element, reference),
            operator,
            expected,
          );
        const geometry = ExtendedSelector.geometry(element, reference);
        const property =
          /** @type {Record<string, string>} */
          ({
            x_ref: "x_percent",
            y_ref: "y_percent",
            x: "left",
            y: "top",
            cx: "center_x",
            cy: "center_y",
          })[key] ?? key;
        if (!(property in geometry))
          throw new SyntaxError(`Unknown geometry property: ${key}`);
        return ExtendedSelector.compareValue(
          String(geometry[property] ?? 0),
          operator,
          ["inside", "contains_geometry"].includes(property) &&
            /^(?:true|false)$/i.test(expected.trim())
            ? String(Number(expected.trim().toLowerCase() === "true"))
            : String(
                expected.trim().endsWith("%") &&
                  ![
                    "x_percent",
                    "y_percent",
                    "width_ratio",
                    "height_ratio",
                  ].includes(property)
                  ? ExtendedSelector.unitValue(
                      expected,
                      [
                        "left",
                        "right",
                        "center_x",
                        "gap_left",
                        "gap_right",
                        "overlap_x",
                      ].includes(property)
                        ? reference.getBoundingClientRect().width
                        : reference.getBoundingClientRect().height,
                    )
                  : Number.parseFloat(expected),
              ),
        );
      },
    );
  }
  /**
   * Extract the value a predicate key exposes on an element.
   *
   * @param {Element} element
   * @param {string} key
   * @returns {string}
   */
  predicateValue(element, key) {
    const resolver = this.predicates.get(key);
    if (resolver)
      return String(
        resolver(element, {
          engine: this,
          key,
        }),
      );
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    const parent = element.parentElement;
    const viewportHeight = innerHeight;
    const viewportRatio =
      rect.width * rect.height
        ? (Math.max(
            0,
            Math.min(rect.right, innerWidth) - Math.max(rect.left, 0),
          ) *
            Math.max(
              0,
              Math.min(rect.bottom, viewportHeight) - Math.max(rect.top, 0),
            )) /
          (rect.width * rect.height)
        : 0;
    const attr = key.startsWith("attr:")
      ? element.getAttribute(key.slice(5))
      : undefined;
    const propKey = key.startsWith("prop:") ? key.slice(5) : "";
    const dataKey = key.startsWith("data:") ? key.slice(5) : "";
    const ariaKey = key.startsWith("aria:") ? key.slice(5) : "";
    if (attr !== undefined) return attr ?? "";
    if (propKey) return String(Reflect.get(element, propKey) ?? "");
    if (dataKey) return element.getAttribute(`data-${dataKey}`) ?? "";
    if (ariaKey) return element.getAttribute(`aria-${ariaKey}`) ?? "";
    const innerText = /** @type {HTMLElement} */ (element).innerText ?? "";
    const values = /** @type {Record<string, string>} */ ({
      textContent: element.textContent ?? "",
      innerText,
      innerHTML: element.innerHTML,
      normalizedText: innerText.replace(/\s+/g, " ").trim(),
      value: "value" in element ? String(element.value ?? "") : "",
      role:
        element.getAttribute("role") ||
        /** @type {Record<string, string>} */
        ({
          BUTTON: "button",
          A: "link",
          INPUT: "textbox",
          SELECT: "combobox",
          TEXTAREA: "textbox",
          IMG: "img",
        })[element.tagName] ||
        "",
      accessible_name:
        element.getAttribute("aria-label") ||
        element
          .getAttribute("aria-labelledby")
          ?.split(/\s+/)
          .map(id => document.getElementById(id)?.textContent ?? "")
          .join(" ")
          .trim() ||
        element.getAttribute("alt") ||
        element.getAttribute("title") ||
        innerText.trim(),
      visible: String(
        style.display !== "none" &&
          style.visibility !== "hidden" &&
          Number.parseFloat(style.opacity || "1") > 0 &&
          rect.width > 0 &&
          rect.height > 0,
      ),
      rendered: String(
        rect.width > 0 && rect.height > 0 && style.display !== "none",
      ),
      enabled: String(!("disabled" in element) || !element.disabled),
      disabled: String("disabled" in element && Boolean(element.disabled)),
      focused: String(document.activeElement === element),
      checked: String("checked" in element && Boolean(element.checked)),
      selected: String("selected" in element && Boolean(element.selected)),
      editable: String(
        /** @type {HTMLElement} */
        (element).isContentEditable ||
          ["INPUT", "TEXTAREA"].includes(element.tagName),
      ),
      clickable: String(
        element.matches(
          "button,a[href],input,select,textarea,[role=button],[onclick]",
        ) || style.cursor === "pointer",
      ),
      draggable: String(/** @type {HTMLElement} */ (element).draggable),
      scrollable: String(
        element.scrollHeight > element.clientHeight ||
          element.scrollWidth > element.clientWidth,
      ),
      in_viewport: String(viewportRatio > 0),
      viewport_ratio: String(viewportRatio),
      above_viewport: String(rect.bottom <= 0),
      below_viewport: String(rect.top >= viewportHeight),
      width: `${rect.width}px`,
      height: `${rect.height}px`,
      area: `${rect.width * rect.height}px`,
      aspect_ratio: String(rect.height ? rect.width / rect.height : 0),
      x_abs: `${rect.left + scrollX}px`,
      y_abs: `${rect.top + scrollY}px`,
      right_abs: `${rect.right + scrollX}px`,
      bottom_abs: `${rect.bottom + scrollY}px`,
      center_x_abs: `${(rect.left + rect.right) / 2 + scrollX}px`,
      center_y_abs: `${(rect.top + rect.bottom) / 2 + scrollY}px`,
      x_view: `${rect.left}px`,
      y_view: `${rect.top}px`,
      distance_to_viewport_top: `${Math.abs(rect.top)}px`,
      children: String([...element.children].length),
      descendants: String(element.querySelectorAll("*").length),
      siblings: String(parent ? parent.children.length - 1 : 0),
      index: String(parent ? [...parent.children].indexOf(element) + 1 : 1),
      index_of_type: String(
        parent
          ? [...parent.children]
              .filter(node => node.tagName === element.tagName)
              .indexOf(element) + 1
          : 1,
      ),
      depth: String(
        (() => {
          let d = 0;
          for (
            let n = element.parentElement;
            n && n !== document.body;
            n = n.parentElement
          )
            d += 1;
          return d;
        })(),
      ),
      text_nodes: String(
        [...element.childNodes].filter(
          node =>
            node.nodeType === Node.TEXT_NODE && node.textContent?.trim(),
        ).length,
      ),
      scrollLeft: `${element.scrollLeft}px`,
      scrollTop: `${element.scrollTop}px`,
      scrollWidth: `${element.scrollWidth}px`,
      scrollHeight: `${element.scrollHeight}px`,
      scrollX: `${scrollX}px`,
      scrollY: `${scrollY}px`,
      scroll_x: `${element.scrollLeft}px`,
      scroll_y: `${element.scrollTop}px`,
      scroll_x_max: `${Math.max(0, element.scrollWidth - element.clientWidth)}px`,
      scroll_y_max: `${Math.max(0, element.scrollHeight - element.clientHeight)}px`,
      scroll_x_percent: `${element.scrollWidth > element.clientWidth ? (element.scrollLeft / (element.scrollWidth - element.clientWidth)) * 100 : 0}%`,
      scroll_y_percent: `${element.scrollHeight > element.clientHeight ? (element.scrollTop / (element.scrollHeight - element.clientHeight)) * 100 : 0}%`,
    });
    if (key in values) return values[key] ?? "";
    if (element.hasAttribute(key)) return element.getAttribute(key) ?? "";
    return style
      .getPropertyValue(
        key.replace(/[A-Z]/g, letter => `-${letter.toLowerCase()}`),
      )
      .trim();
  }
  /**
   * Parse one sort key such as "-width", "[data-priority]" or "distance".
   * @param {string} token
   * @returns {{descending: boolean, name: string}}
   */
  static sortKey = token => {
    const text = token.trim();
    const descending = text.startsWith("-");
    const body = (descending ? text.slice(1) : text).trim();
    const bracket = body.match(/^\[([^\]]+)\]$/);
    return {
      descending,
      name: bracket ? `attr:${(bracket[1] ?? "").trim()}` : body,
    };
  };
  /**
   * Decide between sort(base, key...) and sort(base, reference, key...).
   * The reference form applies when a later argument is a geometry key or the
   * second argument is not shaped like a key.
   * @param {string[]} raw
   * @returns {{referenceForm: boolean, keys: {descending: boolean, name: string}[]}}
   */
  static sortLayout = raw => {
    const shape = /^-?(?:[A-Za-z_][\w:-]*|\[[^\]]+\])$/;
    const geometry = new Set(ExtendedSelector.CAPABILITIES.referenceGeometry);
    const isGeometry = (/** @type {string} */ token) =>
      geometry.has(ExtendedSelector.sortKey(token).name);
    const second = (raw[1] ?? "").trim();
    const referenceForm =
      raw.length >= 3 && (!shape.test(second) || raw.slice(2).some(isGeometry));
    const tokens = raw.slice(referenceForm ? 2 : 1);
    if (!tokens.length)
      throw new SyntaxError(
        "sort() needs at least one key after the reference.",
      );
    for (const token of tokens)
      if (!shape.test(token.trim()))
        throw new SyntaxError(`Invalid sort key "${token.trim()}".`);
    if (!referenceForm && tokens.some(isGeometry))
      throw new SyntaxError(
        "Geometry sort keys need a reference: sort(base, reference, key, ...).",
      );
    return {
      referenceForm,
      keys: tokens.map(ExtendedSelector.sortKey),
    };
  };
  /**
   * Stable sort by keys; empty values always sort last.
   * @param {Element[]} elements
   * @param {{descending: boolean, name: string}[]} keys
   * @param {Element | null} reference
   * @returns {Element[]}
   */
  sortElements(elements, keys, reference) {
    const unique = [...new Set(elements)];
    const geometry = new Map(
      unique.map(element => [
        element,
        reference ? ExtendedSelector.geometry(element, reference) : null,
      ]),
    );
    /** @type {(element: Element, name: string) => string | number} */
    const read = (element, name) => {
      const own = geometry.get(element);
      return own && name in own
        ? (own[name] ?? 0)
        : this.predicateValue(element, name);
    };
    return unique
      .sort(ExtendedSelector.documentOrder)
      .map((element, index) => ({
        element,
        index,
      }))
      .sort((a, b) => {
        for (const key of keys) {
          const left = read(a.element, key.name);
          const right = read(b.element, key.name);
          if (left === "" && right !== "") return 1;
          if (right === "" && left !== "") return -1;
          const x = typeof left === "number" ? left : Number.parseFloat(left);
          const y =
            typeof right === "number" ? right : Number.parseFloat(right);
          const order =
            Number.isFinite(x) && Number.isFinite(y)
              ? x - y
              : String(left).localeCompare(String(right), undefined, {
                  numeric: true,
                });
          if (order) return key.descending ? -order : order;
        }
        return a.index - b.index;
      })
      .map(({ element }) => element);
  }
  /**
   * Offset where the last compound selector (the subject) starts.
   * @param {string} text
   * @returns {number}
   */
  static subjectStart = text => {
    let paren = 0;
    let bracket = 0;
    let quote = "";
    let start = 0;
    for (let index = 0; index < text.length; index += 1) {
      const character = text.charAt(index);
      if (quote) {
        if (character === quote && text.charAt(index - 1) !== "\\") quote = "";
      } else if (`"'`.includes(character)) quote = character;
      else if (character === "(") paren += 1;
      else if (character === ")") paren -= 1;
      else if (character === "[") bracket += 1;
      else if (character === "]") bracket -= 1;
      else if (!paren && !bracket && /[\s>+~]/.test(character))
        start = index + 1;
    }
    return start;
  };
  /**
   * Count the parentheses open at an offset, ignoring quoted text.
   * @param {string} text
   * @param {number} offset
   * @returns {number}
   */
  static parenDepth = (text, offset) => {
    let depth = 0;
    let quote = "";
    for (let index = 0; index < offset; index += 1) {
      const character = text.charAt(index);
      if (quote) {
        if (character === quote && text.charAt(index - 1) !== "\\") quote = "";
      } else if (`"'`.includes(character)) quote = character;
      else if (character === "(") depth += 1;
      else if (character === ")") depth -= 1;
    }
    return depth;
  };
  /**
   * A bracket is plain CSS, not an extended predicate, when it sits inside
   * parentheses or in a compound that is not the subject of the atom.
   * @param {string} text
   * @param {number} offset
   * @returns {boolean}
   */
  static isCssBracket = (text, offset) =>
    ExtendedSelector.parenDepth(text, offset) > 0 ||
    offset < ExtendedSelector.subjectStart(text);
  /**
   * Evaluate one extended atom over the universe.
   *
   * @param {string} expression
   * @param {Element[]} [universe]
   * @returns {Element[]}
   * @throws {SyntaxError} When the atom cannot be parsed.
   */
  extendedAtom(expression, universe = [...this.root.querySelectorAll("*")]) {
    const predicates = /** @type {PredicateRule[]} */ ([]);
    const references = /** @type {ReferenceRule[]} */ ([]);
    const css =
      this.expandDefinitions(expression)
        .trim()
        .replace(
          /\[([\w:-]+)\(([^)]+)\)\s*(~~|~=|\^=|\$=|\*=|<=|>=|!=|=|<|>)\s*("(?:\\.|[^"])*"|'(?:\\.|[^'])*'|[^\]]+)\]/g,
          /**
           * @param {string} match
           * @param {string} key
           * @param {string} reference
           * @param {string} operator
           * @param {string} raw
           * @returns {string}
           */
          (match, key, reference, operator, raw, offset, whole) => {
            if (ExtendedSelector.isCssBracket(whole, offset)) return match;
            const lead = offset === ExtendedSelector.subjectStart(whole);
            references.push({
              key,
              reference: reference.trim(),
              operator,
              expected: raw.trim().replace(/^(["'])(.*)\1$/, "$2"),
            });
            return lead ? "*" : "";
          },
        )
        .replace(
          /\[([\w:-]+)\s*(~~|~=|\^=|\$=|\*=|<=|>=|!=|=|<|>)\s*("(?:\\.|[^"])*"|'(?:\\.|[^'])*'|[^\]]+)\]/g,
          /**
           * @param {string} match
           * @param {string} key
           * @param {string} operator
           * @param {string} raw
           * @returns {string}
           */
          (match, key, operator, raw, offset, whole) => {
            if (ExtendedSelector.isCssBracket(whole, offset)) return match;
            const lead = offset === ExtendedSelector.subjectStart(whole);
            predicates.push({
              key,
              operator,
              expected: raw.trim().replace(/^(["'])(.*)\1$/, "$2"),
            });
            return lead ? "*" : "";
          },
        )
        .trim() || "*";
    /** @type {Element[]} */
    let base;
    try {
      base = universe.filter(element => element.matches(css));
    } catch {
      throw new SyntaxError(`Invalid CSS atom: ${css}`);
    }
    return base.filter(
      element =>
        predicates.every(({ key, operator, expected }) => {
          if (key === "z_ref") {
            const parent = element.parentElement;
            return parent
              ? ExtendedSelector.compareValue(
                  ExtendedSelector.stacking(element, parent),
                  operator,
                  expected,
                )
              : false;
          }
          if (["x_rel", "y_rel", "x_ref", "y_ref"].includes(key)) {
            const parent = element.parentElement;
            if (!parent) return false;
            const rect = element.getBoundingClientRect();
            const box = parent.getBoundingClientRect();
            const horizontal = key.startsWith("x_");
            const pixels = horizontal
              ? rect.left - box.left
              : rect.top - box.top;
            return ExtendedSelector.compareValue(
              String(
                expected.trim().endsWith("%")
                  ? (pixels /
                      Math.max(horizontal ? box.width : box.height, 1)) *
                      100
                  : pixels,
              ),
              operator,
              String(Number.parseFloat(expected)),
            );
          }
          return ExtendedSelector.compareValue(
            this.predicateValue(element, key),
            operator,
            expected,
          );
        }) &&
        references.every(({ key, reference, operator, expected }) =>
          this.referencePredicate(element, key, reference, operator, expected),
        ),
    );
  }
  /**
   * Parse an extended expression into an AST.
   *
   * @param {string} expression
   * @returns {AstNode}
   */
  parseExtended(expression) {
    const value = expression.trim();
    if (value.startsWith("!(") && value.endsWith(")"))
      return {
        type: "call",
        name: "not",
        args: [this.parseExtended(value.slice(2, -1))],
      };
    const call = value.match(/^([a-z_][\w-]*)\((.*)\)$/is);
    return call
      ? {
          type: "call",
          name: (call[1] ?? "").toLowerCase(),
          args: ExtendedSelector.splitTopLevel(call[2] ?? "").map(arg =>
            this.parseExtended(arg),
          ),
          rawArgs: ExtendedSelector.splitTopLevel(call[2] ?? ""),
        }
      : {
          type: "atom",
          value,
        };
  }
  /**
   * Evaluate an AST node over a universe of elements.
   *
   * @param {AstNode} node
   * @param {Element[]} universe
   * @returns {Element[]}
   * @throws {SyntaxError} When the AST contains an unknown operator.
   */
  evaluateAst(node, universe) {
    if (node.type === "atom") return this.extendedAtom(node.value, universe);
    const op = node.name;
    const args = node.args;
    const raw = node.rawArgs ?? [];
    const handler = this.operators.get(op);
    if (handler)
      return handler({
        engine: this,
        node,
        universe,
        args,
        raw,
      });
    /**
     * @param {number} index
     * @param {Element[]} [scope]
     * @returns {Element[]}
     */
    const evalArg = (index, scope = universe) =>
      this.evaluateAst(/** @type {AstNode} */ (args[index]), scope);
    if (op === "media") {
      const query = (raw[0] ?? "").trim().replace(/^(["'])([\s\S]*)\1$/, "$2");
      const list = matchMedia(query);
      if (list.media === "not all" && query.trim() !== "not all")
        throw new SyntaxError(`Invalid media query: ${query}`);
      return list.matches ? universe : [];
    }
    if (op === "sort") {
      const layout = ExtendedSelector.sortLayout(raw);
      const base = evalArg(0);
      const reference = layout.referenceForm ? (evalArg(1)[0] ?? null) : null;
      if (layout.referenceForm && !reference) return [];
      return this.sortElements(base, layout.keys, reference);
    }
    if (
      [
        "nearest",
        "nearest_above",
        "nearest_below",
        "nearest_left",
        "nearest_right",
      ].includes(op)
    ) {
      if (args.length < 2 || args.length > 3)
        throw new SyntaxError(`${op}(base,reference[,tolerance])`);
      const limit = args.length === 3 ? Number.parseFloat(raw[2] ?? "0") : 0;
      const reference = evalArg(1)[0];
      if (!reference) return [];
      const gap = /** @type {Record<string, string>} */ ({
        nearest_above: "gap_top",
        nearest_below: "gap_bottom",
        nearest_left: "gap_left",
        nearest_right: "gap_right",
      })[op];
      // Overlap within the tolerance counts as touching (gap 0); real gaps
      // rank by size, then by center distance, then by document order.
      const gapOf = (/** @type {Record<string, number>} */ geometry) =>
        gap ? Math.max(0, geometry[gap] ?? 0) : 0;
      return [...new Set(evalArg(0))]
        .filter(element => element !== reference)
        .sort(ExtendedSelector.documentOrder)
        .map((element, index) => {
          const geometry = ExtendedSelector.geometry(element, reference);
          const { distance = 0 } = geometry;
          return {
            element,
            index,
            geometry,
            distance,
          };
        })
        .filter(({ geometry }) => !gap || (geometry[gap] ?? 0) >= -limit)
        .sort(
          (a, b) =>
            gapOf(a.geometry) - gapOf(b.geometry) ||
            a.distance - b.distance ||
            a.index - b.index,
        )
        .map(({ element }) => element);
    }
    if (op === "apply") {
      if (args.length !== 2)
        throw new SyntaxError("apply(base,expr) requires two expressions.");
      return evalArg(1, [
        ...new Set(
          evalArg(0).flatMap(base => [base, ...base.querySelectorAll("*")]),
        ),
      ]);
    }
    if (op === "has") {
      if (args.length !== 2)
        throw new SyntaxError("has(base,condition) requires two expressions.");
      return evalArg(0).filter(
        base => evalArg(1, [...base.querySelectorAll("*")]).length,
      );
    }
    if (
      [
        "sibling",
        "siblings",
        "prev",
        "next",
        "parent",
        "ancestor",
        "closest",
      ].includes(op)
    ) {
      if (args.length !== 2)
        throw new SyntaxError(
          `${op}(base,condition) requires two expressions.`,
        );
      return evalArg(0).filter(base => {
        let candidates = /** @type {Element[]} */ ([]);
        if (op === "prev")
          candidates = /** @type {Element[]} */ (
            [base.previousElementSibling].filter(Boolean)
          );
        else if (op === "next")
          candidates = /** @type {Element[]} */ (
            [base.nextElementSibling].filter(Boolean)
          );
        else if (["sibling", "siblings"].includes(op))
          candidates = base.parentElement
            ? [...base.parentElement.children].filter(n => n !== base)
            : [];
        else if (op === "parent")
          candidates = /** @type {Element[]} */ (
            [base.parentElement].filter(Boolean)
          );
        else {
          let n = base.parentElement;
          while (n && n !== this.root) {
            candidates.push(n);
            n = n.parentElement;
          }
        }
        return op === "closest"
          ? candidates.some(candidate =>
              evalArg(1, [candidate]).includes(candidate),
            )
          : candidates.some(candidate =>
              evalArg(1, [candidate]).includes(candidate),
            );
      });
    }
    if (op === "children") {
      if (args.length < 2)
        throw new SyntaxError(
          "children(base,c1,c2,...) requires child conditions.",
        );
      return evalArg(0).filter(
        base =>
          [...base.children].length === args.length - 1 &&
          args.slice(1).every((condition, index) => {
            const child = base.children[index];
            return (
              child !== undefined &&
              this.evaluateAst(condition, [child]).includes(child)
            );
          }),
      );
    }
    if (op === "child") {
      if (args.length !== 3)
        throw new SyntaxError(
          "child(base,index,condition) requires three arguments.",
        );
      const index = Number.parseInt(raw[1] ?? "", 10);
      return evalArg(0).filter(base => {
        const child = base.children[index - 1];
        return (
          Number.isInteger(index) &&
          index > 0 &&
          child !== undefined &&
          this.evaluateAst(/** @type {AstNode} */ (args[2]), [child]).includes(
            child,
          )
        );
      });
    }
    if (["before", "after"].includes(op)) {
      if (args.length !== 2)
        throw new SyntaxError(
          `${op}(base,reference) requires two expressions.`,
        );
      return evalArg(0).filter(base =>
        evalArg(1).some(ref =>
          op === "before"
            ? Boolean(
                base.compareDocumentPosition(ref) &
                Node.DOCUMENT_POSITION_FOLLOWING,
              )
            : Boolean(
                base.compareDocumentPosition(ref) &
                Node.DOCUMENT_POSITION_PRECEDING,
              ),
        ),
      );
    }
    if (
      [
        "left_of",
        "right_of",
        "above",
        "below",
        "overlaps",
        "inside",
        "near",
        "aligned_left",
        "aligned_center_x",
      ].includes(op)
    ) {
      if (args.length < 2 || args.length > 3)
        throw new SyntaxError(`${op}(base,reference[,distance])`);
      const limit = args.length === 3 ? Number.parseFloat(raw[2] ?? "0") : 0;
      return evalArg(0).filter(base =>
        evalArg(1).some(ref => {
          const a = base.getBoundingClientRect();
          const b = ref.getBoundingClientRect();
          return op === "left_of"
            ? a.right <= b.left + limit
            : op === "right_of"
              ? a.left >= b.right - limit
              : op === "above"
                ? a.bottom <= b.top + limit
                : op === "below"
                  ? a.top >= b.bottom - limit
                  : op === "overlaps"
                    ? Math.min(a.right, b.right) > Math.max(a.left, b.left) &&
                      Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top)
                    : op === "inside"
                      ? a.left >= b.left &&
                        a.right <= b.right &&
                        a.top >= b.top &&
                        a.bottom <= b.bottom
                      : op === "near"
                        ? Math.hypot(
                            (a.left + a.right - b.left - b.right) / 2,
                            (a.top + a.bottom - b.top - b.bottom) / 2,
                          ) <= limit
                        : op === "aligned_left"
                          ? Math.abs(a.left - b.left) <= limit
                          : Math.abs(
                              (a.left + a.right - b.left - b.right) / 2,
                            ) <= limit;
        }),
      );
    }
    if (["any", "all", "none"].includes(op)) {
      if (args.length !== 3)
        throw new SyntaxError(
          `${op}(base,relation,condition) requires three arguments.`,
        );
      const relation = (raw[1] ?? "").trim().toLowerCase();
      return evalArg(0).filter(base => {
        if (!["children", "descendants", "siblings"].includes(relation))
          throw new SyntaxError(`Unknown relation: ${relation}`);
        const candidates =
          relation === "children"
            ? [...base.children]
            : relation === "descendants"
              ? [...base.querySelectorAll("*")]
              : base.parentElement
                ? [...base.parentElement.children].filter(n => n !== base)
                : [];
        const hits = candidates.filter(candidate =>
          this.evaluateAst(/** @type {AstNode} */ (args[2]), [
            candidate,
          ]).includes(candidate),
        ).length;
        return op === "any"
          ? hits > 0
          : op === "all"
            ? candidates.length > 0 && hits === candidates.length
            : hits === 0;
      });
    }
    if (op === "count") {
      if (args.length !== 6)
        throw new SyntaxError(
          "count(base,relation,condition,operator,value,mode) requires six arguments; mode is reserved and use any.",
        );
      throw new SyntaxError(
        "Use count predicates such as [children>=2], or any/all/none for relational counts.",
      );
    }
    if (op === "shadow") {
      if (args.length !== 2)
        throw new SyntaxError(
          "shadow(base,condition) requires two expressions.",
        );
      return evalArg(0).flatMap(base =>
        base.shadowRoot
          ? this.evaluateAst(/** @type {AstNode} */ (args[1]), [
              ...base.shadowRoot.querySelectorAll("*"),
            ])
          : [],
      );
    }
    if (op === "slot") {
      if (args.length !== 2)
        throw new SyntaxError("slot(base,condition) requires two expressions.");
      return evalArg(0).flatMap(base =>
        base instanceof HTMLSlotElement
          ? this.evaluateAst(
              /** @type {AstNode} */
              (args[1]),
              base.assignedElements({
                flatten: true,
              }),
            )
          : [],
      );
    }
    if (op === "pseudo") {
      if (raw.length !== 3)
        throw new SyntaxError(
          "pseudo(base,before|after,condition) requires three arguments.",
        );
      return evalArg(0).filter(base => {
        const match = (raw[2] ?? "")
          .trim()
          .match(/^\[([\w-]+)\s*(~~|~=|\^=|\$=|\*=|<=|>=|!=|=|<|>)\s*(.+)\]$/);
        return (
          match &&
          ExtendedSelector.compareValue(
            getComputedStyle(
              base,
              `::${(raw[1] ?? "").trim().replace(/^::?/, "")}`,
            )
              .getPropertyValue(match[1] ?? "")
              .trim(),
            match[2] ?? "",
            (match[3] ?? "").trim().replace(/^(["'])(.*)\1$/, "$2"),
          )
        );
      });
    }
    const sets = args.map(arg => new Set(this.evaluateAst(arg, universe)));
    if (op === "not") {
      if (sets.length !== 1)
        throw new SyntaxError("not() requires one expression.");
      return universe.filter(element => !sets[0]?.has(element));
    }
    if (!["and", "or", "nand", "nor", "xor", "xnor"].includes(op))
      throw new SyntaxError(`Unknown operator: ${op}`);
    if (sets.length < 2)
      throw new SyntaxError(`${op}() requires at least two expressions.`);
    return universe.filter(element => {
      const hits = sets.reduce(
        (total, set) => total + Number(set.has(element)),
        0,
      );
      return op === "and"
        ? hits === sets.length
        : op === "or"
          ? hits > 0
          : op === "nand"
            ? hits !== sets.length
            : op === "nor"
              ? hits === 0
              : op === "xor"
                ? hits === 1
                : hits === 0 || hits === sets.length;
    });
  }
  /**
   * Evaluate a complete extended expression.
   *
   * @param {string} expression
   * @param {Element[]} [universe]
   * @returns {Element[]}
   */
  evaluateExtended(
    expression,
    universe = [...this.root.querySelectorAll("*")],
  ) {
    return this.evaluateAst(this.parseExtended(expression), universe);
  }
  /** Generate and rank exact CSS selectors using available selector engines.
   * @param {Element | Element[]} target
   * @param {GeneratorOptions} [options]
   * @returns {BestSelectorResult}
   * @throws {TypeError} When `target` is empty or contains non-elements.
   * @throws {Error} When no candidate selector can be produced.
   */
  bestSelector(target, options = {}) {
    const targets = Array.isArray(target) ? target : [target];
    if (
      !targets.length ||
      targets.some(element => !(element instanceof Element))
    )
      throw new TypeError("target must contain Element instances.");
    const root = this.root;
    /**
     * @param {string} selector
     * @returns {Element[]}
     */
    const query = selector => {
      try {
        return options.deep
          ? this.queryChain(selector)
          : [...root.querySelectorAll(selector)];
      } catch {
        return [];
      }
    };
    /**
     * @param {string} selector
     * @returns {boolean}
     */
    const exact = selector => {
      const found = query(selector);
      return (
        found.length === targets.length &&
        found.every(element => targets.includes(element))
      );
    };
    /**
     * @param {string} selector
     * @returns {number[]}
     */
    const specificity = selector => {
      const stripped = selector.replace(/:where\([^)]*\)/g, "");
      return [
        (stripped.match(/#[\w-]+/g) ?? []).length,
        (
          stripped.match(/\.[\w-]+|\[[^\]]+\]|:(?!:)[\w-]+(?:\([^)]*\))?/g) ??
          []
        ).length,
        (stripped.match(/(^|[\s>+~,])(?:[a-z][\w-]*|\*)/gi) ?? []).filter(
          item => !item.trim().endsWith("*"),
        ).length,
      ];
    };
    /**
     * @param {string} selector
     * @returns {number}
     */
    const fragility = selector =>
      (selector.match(/:nth-(?:child|of-type)\(/g) ?? []).length * 12 +
      (selector.match(/[+~]/g) ?? []).length * 4 +
      (selector.match(/>/g) ?? []).length * 2 +
      (selector.match(/\s+/g) ?? []).length;
    const candidates = /** @type {SelectorCandidate[]} */ ([]);
    /**
     * @param {string} engine
     * @param {unknown} selector
     * @returns {void}
     */
    const add = (engine, selector) => {
      if (
        typeof selector !== "string" ||
        !selector.trim() ||
        !exact(selector.trim())
      )
        return;
      const normalized = selector.trim();
      const spec = specificity(normalized);
      if (
        !candidates.some(
          candidate =>
            candidate.engine === engine && candidate.selector === normalized,
        )
      )
        candidates.push({
          selector: normalized,
          engine,
          specificity: spec,
          fragility: fragility(normalized),
          length: normalized.length,
          exact: true,
          unique: targets.length === 1,
        });
    };
    /**
     * @param {unknown} value
     * @returns {string}
     */
    const attr = value =>
      `"${String(value).replaceAll("\\", "\\\\").replaceAll('"', '\\"')}"`;
    const registered = targets.map(element =>
      element.getAttribute("extended-selector"),
    );
    if (registered.every(Boolean))
      add(
        "register",
        targets
          .map((_, index) => `[extended-selector=${attr(registered[index])}]`)
          .join(","),
      );
    /**
     * @param {Element} element
     * @param {Document | Element | ShadowRoot} scope
     * @param {(selector: string) => boolean} unique
     * @returns {string}
     */
    const within = (element, scope, unique) => {
      if (element.id) {
        const id = `#${CSS.escape(element.id)}`;
        if (unique(id)) return id;
      }
      for (const name of [
        "data-testid",
        "data-test",
        "data-qa",
        "name",
        "aria-label",
      ]) {
        const value = element.getAttribute(name);
        if (value) {
          const selector = `[${name}=${attr(value)}]`;
          if (unique(selector)) return selector;
        }
      }
      const tag = element.localName || "*";
      const classes = [...element.classList]
        .map(name => `.${CSS.escape(name)}`)
        .join("");
      for (const selector of [tag + classes, classes])
        if (selector && unique(selector)) return selector;
      const path = /** @type {string[]} */ ([]);
      for (
        let node = /** @type {Element | null} */ (element);
        node && node instanceof Element && node !== scope;
        node = node.parentElement
      ) {
        const parent = node.parentElement;
        const siblings = parent
          ? [...parent.children].filter(
              item => item.localName === node.localName,
            )
          : [];
        path.unshift(
          `${node.localName}${siblings.length > 1 ? `:nth-of-type(${siblings.indexOf(node) + 1})` : ""}`,
        );
        const selector = path.join(" > ");
        if (unique(selector)) return selector;
      }
      return path.join(" > ");
    };
    /**
     * @param {Element} element
     * @returns {string}
     */
    const native = element => {
      const home = element.getRootNode();
      if (options.deep && home instanceof ShadowRoot) {
        // Inside a shadow tree: find a selector that is unique in that tree,
        // then anchor it to its host with Playwright's ">>" chaining.
        const inner = within(element, home, selector => {
          try {
            return home.querySelectorAll(selector).length === 1;
          } catch {
            return false;
          }
        });
        return query(inner).length === 1
          ? inner
          : `${native(home.host)} >> ${inner}`;
      }
      return within(element, root, selector => query(selector).length === 1);
    };
    const engines = options.engines ?? [
      "register",
      "generator",
      "optimal",
      "finder",
      "native",
    ];
    engines.forEach(engine => {
      try {
        if (engine === "register") {
          if (registered.every(Boolean))
            add(
              engine,
              targets
                .map(
                  (_, index) =>
                    `[extended-selector=${attr(registered[index])}]`,
                )
                .join(","),
            );
        } else if (engine === "generator" && options.generator)
          add(
            engine,
            options.generator(
              targets.length === 1
                ? /** @type {Element} */ (targets[0])
                : targets,
              {
                root,
              },
            ),
          );
        else if (engine === "optimal" && options.optimal) {
          const api = options.optimal;
          const selector =
            targets.length === 1
              ? api.getSingleSelector?.(/** @type {Element} */ (targets[0]), {
                  root,
                })
              : api.getMultiSelector?.(targets, {
                  root,
                });
          add(engine, selector);
          if (selector && api.optimize)
            add("optimal:optimize", api.optimize(selector, root));
        } else if (engine === "finder" && options.finder) {
          const finder = options.finder;
          add(
            engine,
            targets
              .map(element =>
                finder(element, {
                  root,
                }),
              )
              .join(","),
          );
        } else if (engine === "native")
          add(engine, targets.map(native).join(","));
      } catch {
        /* engines that throw are skipped */
      }
    });
    if (!candidates.length)
      throw new Error("No selector engine produced an exact selector.");
    candidates.sort(
      (a, b) =>
        (a.specificity[0] ?? 0) - (b.specificity[0] ?? 0) ||
        (a.specificity[1] ?? 0) - (b.specificity[1] ?? 0) ||
        (a.specificity[2] ?? 0) - (b.specificity[2] ?? 0) ||
        a.fragility - b.fragility ||
        a.length - b.length ||
        a.selector.localeCompare(b.selector) ||
        a.engine.localeCompare(b.engine),
    );
    return {
      .../** @type {SelectorCandidate} */ (candidates[0]),
      candidates: options.includeCandidates === false ? [] : candidates,
    };
  }
  /** Alias for bestSelector().
   * @param {Element | Element[]} target
   * @param {GeneratorOptions} [options]
   * @returns {BestSelectorResult}
   */
  generateSelector(target, options = {}) {
    return this.bestSelector(target, options);
  }
}
export default ExtendedSelector;
