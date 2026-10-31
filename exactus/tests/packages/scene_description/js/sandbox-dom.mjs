/** Rich fake browser environment for the scene evidence runtime tests. */
/** @typedef {{left: number, top: number, width: number, height: number}} FakeRect */
/**
 * @typedef {object} ListenerEntry
 * @property {(event: any) => void} listener Event handler.
 * @property {boolean} once Single-dispatch flag.
 */
/**
 * @typedef {FakeNode & {textContent?: string | null}} ChildNode
 */
/**
 * @typedef {object} FakeDocument
 * @property {string} title
 * @property {string} baseURI
 * @property {string} referrer
 * @property {string} characterSet
 * @property {string} contentType
 * @property {string} compatMode
 * @property {Element | null} activeElement
 * @property {HTMLElement} documentElement
 * @property {HTMLElement} head
 * @property {HTMLElement} body
 * @property {() => FakeRange} createRange
 * @property {() => null} elementFromPoint
 * @property {() => Element[]} elementsFromPoint
 * @property {(element: Element, pseudo?: string | null) =>
 *   Record<string, string>} getComputedStyle
 * @property {(tag: string) => Element} createElement
 * @property {(ns: string | null, tag: string) => Element} createElementNS
 * @property {(text: string) => FakeTextNode} createTextNode
 * @property {(selector: string) => Element[]} querySelectorAll
 * @property {(selector: string) => Element | null} querySelector
 * @property {(id: string) => Element | null} getElementById
 * @property {(type: string, listener: unknown) => void} addEventListener
 * @property {(type: string, listener: unknown) => void} removeEventListener
 */
/** @typedef {{stop: () => void, kind: string}} FakeTrack */
/** @type {FakeDocument | null} */
let currentDocument = null;
/** Minimal classList implementation for the fake Element. */
class FakeClassList {
  /** @type {Element} */
  #element;
  /**
   * Owning element.
   *
   * @param {Element} element Owning element.
   */
  constructor(element) {
    this.#element = element;
  }
  /**
   * Class count.
   *
   * @returns {number} Class count.
   */
  get length() {
    return this.#names().length;
  }
  /**
   * Append class names.
   *
   * @param {...string} names Names to add.
   */
  add(...names) {
    this.#write([...this.#names(), ...names]);
  }
  /**
   * Drop class names.
   *
   * @param {...string} names Names to remove.
   */
  remove(...names) {
    const drop = new Set(names);
    this.#write(this.#names().filter(name => !drop.has(name)));
  }
  /**
   * Whether the class is present afterwards.
   *
   * @param {string} name Class name.
   * @param {boolean} [force] Forced presence state.
   * @returns {boolean} Whether the class is present afterwards.
   */
  toggle(name, force) {
    const on = force ?? !this.contains(name);
    if (on) this.add(name);
    else this.remove(name);
    return on;
  }
  /**
   * Whether the element carries the class.
   *
   * @param {string} name Class name.
   * @returns {boolean} Whether the element carries the class.
   */
  contains(name) {
    return this.#names().includes(name);
  }
  /**
   * Current class names.
   *
   * @returns {string[]} Current class names.
   */
  #names() {
    return this.#element.className.split(/\s+/).filter(Boolean);
  }
  /**
   * Persist the element's class names.
   *
   * @param {string[]} names Names to persist.
   */
  #write(names) {
    this.#element.className = [...new Set(names)].join(" ");
  }
  *[Symbol.iterator]() {
    yield* this.#names();
  }
}
/** Minimal EventTarget stand-in tracking listeners. */
export class FakeEventTarget {
  constructor() {
    /** @type {Record<string, ListenerEntry[]>} */
    this.__listeners = {};
  }
  /**
   * Register an event listener.
   *
   * @param {string} type Event type.
   * @param {(event: any) => void} listener Event handler.
   * @param {{capture?: boolean, once?: boolean} | boolean} [options] Options.
   */
  addEventListener(type, listener, options = {}) {
    if (typeof options === "boolean") options = { capture: options };
    (this.__listeners[type] ??= []).push({
      listener,
      once: Boolean(options.once),
    });
  }
  /**
   * Remove a matching listener.
   *
   * @param {string} type Event type.
   * @param {(event: any) => void} listener Event handler.
   */
  removeEventListener(type, listener) {
    this.__listeners[type] = (this.__listeners[type] ?? []).filter(
      entry => entry.listener !== listener,
    );
  }
  /**
   * Dispatch an event to registered listeners.
   *
   * @param {Event} event Event to dispatch.
   * @returns {boolean} Always true.
   */
  dispatchEvent(event) {
    if (!event.target)
      Object.defineProperty(event, "target", {
        value: this,
        configurable: true,
      });
    const list = this.__listeners[event.type] ?? [];
    this.__listeners[event.type] = list.filter(entry => !entry.once);
    for (const entry of list) entry.listener.call(this, event);
    return true;
  }
}
/** Tree node base with parent and sibling links. */
export class FakeNode extends FakeEventTarget {
  /**
   * Owning document.
   *
   * @param {FakeDocument | null} ownerDocument Owning document.
   */
  constructor(ownerDocument) {
    super();
    /** @type {FakeDocument | null} */
    this.ownerDocument = ownerDocument;
    /** @type {Element | null} */
    this.parentElement = null;
    this.nodeType = 0;
    /** @type {FakeNode[]} */
    this.childNodes = [];
  }
  /**
   * Previous sibling.
   *
   * @returns {FakeNode | null} Previous sibling.
   */
  get previousSibling() {
    const nodes = this.parentElement?.childNodes ?? [];
    return nodes[nodes.indexOf(this) - 1] ?? null;
  }
  /**
   * Next sibling.
   *
   * @returns {FakeNode | null} Next sibling.
   */
  get nextSibling() {
    const nodes = this.parentElement?.childNodes ?? [];
    return nodes[nodes.indexOf(this) + 1] ?? null;
  }
  /**
   * Whether the node hangs below a root.
   *
   * @returns {boolean} Whether the node hangs below a root.
   */
  get isConnected() {
    return Boolean(this.parentElement);
  }
  /** Detach this node from its parent. */
  remove() {
    const parent = this.parentElement;
    if (parent?.childNodes) {
      const index = parent.childNodes.indexOf(this);
      if (index >= 0) parent.childNodes.splice(index, 1);
    }
    this.parentElement = null;
  }
  /**
   * Insert sibling nodes before this node.
   *
   * @param {...FakeNode} nodes Nodes to insert.
   */
  before(...nodes) {
    const parent = this.parentElement;
    if (!parent) return;
    const index = parent.childNodes.indexOf(this);
    for (const node of nodes) node.remove?.();
    parent.childNodes.splice(index, 0, ...nodes);
    for (const node of nodes) node.parentElement = parent;
  }
  /**
   * Insert sibling nodes after this node.
   *
   * @param {...FakeNode} nodes Nodes to insert.
   */
  after(...nodes) {
    const parent = this.parentElement;
    if (!parent) return;
    const index = parent.childNodes.indexOf(this);
    for (const node of nodes) node.remove?.();
    parent.childNodes.splice(index + 1, 0, ...nodes);
    for (const node of nodes) node.parentElement = parent;
  }
  /**
   * Replace this node with sibling nodes.
   *
   * @param {...FakeNode} nodes Replacement nodes.
   */
  replaceWith(...nodes) {
    this.before(...nodes);
    this.remove();
  }
  /**
   * Return a detached copy.
   *
   * @param {boolean} [deep] Clone descendants as well.
   * @returns {FakeNode} Detached copy.
   */
  cloneNode(deep = false) {
    const copy = new FakeNode(this.ownerDocument);
    copy.nodeType = this.nodeType;
    if (deep) {
      for (const child of this.childNodes ?? [])
        copy.childNodes.push(child.cloneNode(true));
      for (const child of copy.childNodes)
        child.parentElement = /** @type {Element} */ (
          /** @type {unknown} */ (copy)
        );
    }
    return copy;
  }
}
/** Text node carrying a string payload. */
export class FakeTextNode extends FakeNode {
  /**
   * Owning document.
   *
   * @param {string} text Text payload.
   * @param {FakeDocument | null} ownerDocument Owning document.
   */
  constructor(text, ownerDocument) {
    super(ownerDocument);
    this.nodeType = 3;
    /** @type {string} */
    this.textContent = text;
  }
  /**
   * Set the character data.
   *
   * @returns {string} Character data.
   */
  get data() {
    return this.textContent;
  }
  /**
   * Set the character data.
   *
   * @param {string} value Character data.
   */
  set data(value) {
    this.textContent = value;
  }
  /**
   * Node value.
   *
   * @returns {string} Node value.
   */
  get nodeValue() {
    return this.textContent;
  }
  /**
   * Return a detached copy.
   *
   * @override
   * @returns {FakeTextNode} Detached copy.
   */
  cloneNode() {
    return new FakeTextNode(this.textContent, this.ownerDocument);
  }
}
/**
 * Minimal selector matcher for tag, class, attribute, and :nth-child.
 *
 * @param {Element} element Candidate element.
 * @returns {{match: (selector: string) => boolean}} Matcher facade.
 */
const parseSimple = element => ({
  match: (/** @type {string} */ selector) => {
    const trimmed = selector.trim();
    if (trimmed.includes(","))
      return trimmed
        .split(",")
        .some(part => parseSimple(element).match(part));
    const nth = /:nth-child\((\d+)\)$/.exec(trimmed);
    const positional = /:(first-child|last-child|focus-within)$/.exec(
      trimmed,
    );
    const base = (nth ? trimmed.slice(0, nth.index) : trimmed).replace(
      /:(first-child|last-child|focus-within)$/,
      "",
    );
    if (nth || positional?.[1] === "first-child" || positional?.[1] === "last-child") {
      const parent = element.parentElement;
      if (!parent) return false;
      const index = parent.children.indexOf(element) + 1;
      const expected = nth
        ? Number(nth[1])
        : positional?.[1] === "first-child"
          ? 1
          : parent.children.length;
      if (index !== expected) return false;
    }
    if (positional?.[1] === "focus-within") {
      const active = element.ownerDocument?.activeElement;
      if (active !== element && !element.contains(active ?? null))
        return false;
    }
    if (!base || base === ":scope") return true;
    const attribute = /^\[([\w-]+)(?:=["']([^"']*)["'])?\]$/.exec(base);
    if (attribute)
      return (
        element.getAttribute(attribute[1] ?? "") !== null &&
        (attribute[2] === undefined ||
          element.getAttribute(attribute[1] ?? "") === attribute[2])
      );
    const pieces = base.split(".");
    const tag = pieces[0];
    if (tag && tag !== "*" && element.localName !== tag.toLowerCase())
      return false;
    return pieces.slice(1).every(name => element.classList.contains(name));
  },
});
/** Media stream stand-in with scripted tracks. */
class FakeMediaStream extends FakeEventTarget {
  constructor() {
    super();
    /** @type {FakeTrack[]} */
    this.__tracks = [{ stop: () => {}, kind: "video" }];
  }
  /**
   * All tracks.
   *
   * @returns {FakeTrack[]} All tracks.
   */
  getTracks() {
    return this.__tracks;
  }
  /**
   * Audio tracks.
   *
   * @returns {FakeTrack[]} Audio tracks.
   */
  getAudioTracks() {
    return this.__tracks.filter(track => track.kind === "audio");
  }
  /**
   * Video tracks.
   *
   * @returns {FakeTrack[]} Video tracks.
   */
  getVideoTracks() {
    return this.__tracks.filter(track => track.kind === "video");
  }
  /**
   * Drop a track.
   *
   * @param {FakeTrack} track Track to drop.
   */
  removeTrack(track) {
    this.__tracks = this.__tracks.filter(item => item !== track);
  }
}
/** Fake DOM element covering the APIs the runtime exercises. */
export class Element extends FakeNode {
  /**
   * Owning document.
   *
   * @param {string} tag Tag name.
   * @param {FakeDocument | null} [ownerDocument] Owning document.
   */
  constructor(tag, ownerDocument) {
    super(ownerDocument ?? currentDocument);
    this.nodeType = 1;
    this.tagName = String(tag).toUpperCase();
    this.localName = String(tag).toLowerCase();
    this.className = "";
    this.id = "";
    this.lang = "";
    /** @type {Map<string, string>} */
    this.attributesMap = new Map();
    /** @type {ChildNode[]} */
    this.childNodes = [];
    this.ownText = "";
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.checked = false;
    this.selected = false;
    this.multiple = false;
    this.type = "";
    this.name = "";
    this.title = "";
    this.alt = "";
    this.href = "";
    this.src = "";
    this.currentSrc = "";
    this.download = "";
    this.placeholder = "";
    /** @type {number | null} */
    this.min = null;
    /** @type {number | null} */
    this.max = null;
    /** @type {number | null} */
    this.step = null;
    /** @type {number | null} */
    this.low = null;
    /** @type {number | null} */
    this.high = null;
    /** @type {number | null} */
    this.optimum = null;
    this.tabIndex = 0;
    this.isContentEditable = false;
    /** @type {any} */
    this.shadowRoot = null;
    /** @type {Element[]} */
    this.labels = [];
    /** @type {any} */
    this.form = null;
    /** @type {any[]} */
    this.files = [];
    /** @type {any} */
    this.list = null;
    this.scrollTop = 0;
    this.scrollLeft = 0;
    this.scrollWidth = 0;
    this.scrollHeight = 0;
    this.clientWidth = 0;
    this.clientHeight = 0;
    this.offsetWidth = 0;
    this.offsetHeight = 0;
    this.selectionStart = 0;
    this.selectionEnd = 0;
    this.readyState = 4;
    this.currentTime = 0;
    this.duration = 60;
    this.paused = false;
    this.videoWidth = 640;
    this.videoHeight = 360;
    this.naturalWidth = 100;
    this.naturalHeight = 100;
    this.poster = "";
    this.style = {
      /** @type {Map<string, string>} */
      __vars: new Map(),
      /**
       * Property value.
       *
       * @param {string} name Property name.
       * @param {string} value Property value.
       */
      setProperty(name, value) {
        this.__vars.set(name, String(value));
      },
      /**
       * Property value.
       *
       * @param {string} name Property name.
       * @returns {string} Property value.
       */
      getPropertyValue(name) {
        return this.__vars.get(name) ?? "";
      },
    };
    /** @type {FakeRect} */
    this.rect = { left: 0, top: 0, width: 100, height: 20 };
    /** @type {Record<string, string>} */
    this.styleOverrides = {};
    /** @type {Record<string, Record<string, string>> | undefined} */
    this.pseudoStyles = undefined;
    this.classList = new FakeClassList(this);
    /** @type {Record<string, string>} */
    this.dataset = {};
  }
  /**
   * Element children only.
   *
   * @returns {Element[]} Element children only.
   */
  get children() {
    return /** @type {Element[]} */ (
      this.childNodes.filter(node => node.nodeType === 1)
    );
  }
  /**
   * Flattened attributes.
   *
   * @returns {{name: string, value: string}[]} Flattened attributes.
   */
  get attributes() {
    return [...this.attributesMap].map(([name, value]) => ({
      name,
      value,
    }));
  }
  /**
   * First child, if any.
   *
   * @returns {ChildNode | null} First child, if any.
   */
  get firstChild() {
    return this.childNodes[0] ?? null;
  }
  /**
   * First element child.
   *
   * @returns {Element | null} First element child.
   */
  get firstElementChild() {
    return this.children[0] ?? null;
  }
  /**
   * Last element child.
   *
   * @returns {Element | null} Last element child.
   */
  get lastElementChild() {
    return this.children[this.children.length - 1] ?? null;
  }
  /**
   * Next element sibling.
   *
   * @returns {Element | null} Next element sibling.
   */
  get nextElementSibling() {
    const siblings = this.parentElement?.children ?? [];
    return siblings[siblings.indexOf(this) + 1] ?? null;
  }
  /**
   * Previous element sibling.
   *
   * @returns {Element | null} Previous element sibling.
   */
  get previousElementSibling() {
    const siblings = this.parentElement?.children ?? [];
    return siblings[siblings.indexOf(this) - 1] ?? null;
  }
  /**
   * Replace children with a single text value.
   *
   * @returns {string} Combined text payload.
   */
  get textContent() {
    return (
      this.ownText +
      this.childNodes
        .map(child => /** @type {ChildNode} */ (child).textContent ?? "")
        .join("")
    );
  }
  /**
   * Replace children with a single text value.
   *
   * @param {unknown} value Replacement text.
   */
  set textContent(value) {
    this.ownText = String(value);
    this.childNodes.length = 0;
  }
  /**
   * Rendered text.
   *
   * @returns {string} Rendered text.
   */
  get innerText() {
    return this.textContent;
  }
  /**
   * Serialized element.
   *
   * @returns {string} Serialized element.
   */
  get outerHTML() {
    const attrs = [...this.attributesMap]
      .map(([name, value]) => ` ${name}="${value}"`)
      .join("");
    return `<${this.localName}${attrs}>${this.textContent}</${this.localName}>`;
  }
  /**
   * Option children.
   *
   * @returns {Element[]} Option children.
   */
  get options() {
    return this.children.filter(child => child.localName === "option");
  }
  /**
   * Element child count.
   *
   * @returns {number} Element child count.
   */
  get childElementCount() {
    return this.children.length;
  }
  /**
   * Last child, if any.
   *
   * @returns {FakeNode | null} Last child, if any.
   */
  get lastChild() {
    return this.childNodes[this.childNodes.length - 1] ?? null;
  }
  /**
   * Append child nodes or strings.
   *
   * @param {...(FakeNode | string)} nodes Nodes to append.
   */
  append(...nodes) {
    for (const node of nodes) {
      const target =
        typeof node === "string"
          ? new FakeTextNode(node, this.ownerDocument)
          : node;
      target.remove();
      target.parentElement = this;
      this.childNodes.push(target);
    }
  }
  /**
   * Prepend child nodes.
   *
   * @param {...FakeNode} nodes Nodes to prepend.
   */
  prepend(...nodes) {
    for (const node of nodes.reverse()) {
      node.remove();
      node.parentElement = this;
      this.childNodes.unshift(node);
    }
  }
  /**
   * Insert a node before a reference child.
   *
   * @param {FakeNode} node Node to insert.
   * @param {FakeNode | null} reference Reference child.
   * @returns {FakeNode} The inserted node.
   */
  insertBefore(node, reference) {
    node.remove();
    node.parentElement = this;
    const index =
      reference === null ? -1 : this.childNodes.indexOf(reference);
    if (index < 0) this.childNodes.push(node);
    else this.childNodes.splice(index, 0, node);
    return node;
  }
  /** Text-input selection helper. */
  select() {}
  /**
   * Return a detached copy.
   *
   * @override
   * @param {boolean} [deep] Clone descendants as well.
   * @returns {Element} Detached element copy.
   */
  cloneNode(deep = false) {
    const copy = /** @type {Element} */ (
      Reflect.construct(this.constructor, [this.localName, this.ownerDocument])
    );
    copy.className = this.className;
    copy.id = this.id;
    copy.ownText = this.ownText;
    for (const [name, value] of this.attributesMap)
      copy.attributesMap.set(name, value);
    if (deep)
      for (const child of this.childNodes)
        copy.append(child.cloneNode(true));
    return copy;
  }
  /**
   * Set an attribute value.
   *
   * @param {string} name Attribute name.
   * @param {string} value Attribute value.
   */
  setAttribute(name, value) {
    this.attributesMap.set(String(name), String(value));
  }
  /**
   * Attribute value, if present.
   *
   * @param {string} name Attribute name.
   * @returns {string | null} Attribute value, if present.
   */
  getAttribute(name) {
    return this.attributesMap.has(name)
      ? (this.attributesMap.get(name) ?? null)
      : null;
  }
  /**
   * Remove an attribute.
   *
   * @param {string} name Attribute name.
   */
  removeAttribute(name) {
    this.attributesMap.delete(name);
  }
  /**
   * Whether the attribute exists.
   *
   * @param {string} name Attribute name.
   * @returns {boolean} Whether the attribute exists.
   */
  hasAttribute(name) {
    return this.attributesMap.has(name);
  }
  /**
   * Whether the attribute is present afterwards.
   *
   * @param {string} name Attribute name.
   * @param {boolean} [force] Forced presence state.
   * @returns {boolean} Whether the attribute is present afterwards.
   */
  toggleAttribute(name, force) {
    const on = force ?? !this.attributesMap.has(name);
    if (on) this.attributesMap.set(name, "");
    else this.attributesMap.delete(name);
    return on;
  }
  /**
   * Replace all children.
   *
   * @param {...(FakeNode | string)} nodes Replacement children.
   */
  replaceChildren(...nodes) {
    for (const child of this.childNodes) child.parentElement = null;
    this.childNodes.length = 0;
    this.append(...nodes);
  }
  /**
   * Whether the element matches.
   *
   * @param {string} selector Simple selector.
   * @returns {boolean} Whether the element matches.
   */
  matches(selector) {
    return parseSimple(this).match(selector);
  }
  /**
   * Closest matching ancestor or self.
   *
   * @param {string} selector Ancestor selector.
   * @returns {Element | null} Closest matching ancestor or self.
   */
  closest(selector) {
    for (
      let node = /** @type {Element | null} */ (this);
      node;
      node = node.parentElement
    )
      if (node.matches(selector)) return node;
    return null;
  }
  /**
   * Whether the node is inside this element.
   *
   * @param {FakeNode | null} node Candidate node.
   * @returns {boolean} Whether the node is inside this element.
   */
  contains(node) {
    for (let current = node; current; current = current.parentElement)
      if (current === this) return true;
    return false;
  }
  /**
   * Compare document position, DOM-style bit mask.
   *
   * @param {FakeNode} other Other node.
   * @returns {number} Position mask.
   */
  compareDocumentPosition(other) {
    if (other === this) return 0;
    if (this.contains(other)) return 16 | 4;
    if (other instanceof Element && other.contains(this)) return 8 | 2;
    /**
     * Start node.
     *
     * @param {FakeNode} node Start node.
     */
    const rootOf = node => {
      let top = /** @type {FakeNode | null} */ (node);
      while (top?.parentElement) top = top.parentElement;
      return top;
    };
    const mine = rootOf(this);
    if (mine !== rootOf(other)) return 1;
    /** @type {FakeNode[]} */
    const order = [];
    /**
     * Subtree node.
     *
     * @param {FakeNode} node Subtree node.
     */
    const walk = node => {
      order.push(node);
      for (const child of node.childNodes) walk(child);
    };
    if (mine) walk(mine);
    return order.indexOf(this) < order.indexOf(other) ? 4 : 2;
  }
  /**
   * Matching descendants.
   *
   * @param {string} selector Simple descendant selector.
   * @returns {Element[]} Matching descendants.
   */
  querySelectorAll(selector) {
    const scoped = selector.trim().startsWith(":scope>");
    const parts = selector
      .trim()
      .replace(/^:scope>\s*/, "")
      .split(/\s*(?:>|\s)\s*/);
    const last = parts.at(-1) ?? "*";
    const ancestors = parts.slice(0, -1);
    /**
     * Candidate element.
     *
     * @param {Element} element Candidate element.
     */
    const chain = element => {
      let index = ancestors.length - 1;
      for (
        let node = element.parentElement;
        node && index >= 0;
        node = node.parentElement
      )
        if (node.matches(ancestors[index] ?? "*")) index -= 1;
      return index < 0;
    };
    const pool = scoped ? this.children : this.#descendants();
    return pool.filter(
      element => element.matches(last) && chain(element),
    );
  }
  /**
   * First matching descendant.
   *
   * @param {string} selector Simple descendant selector.
   * @returns {Element | null} First matching descendant.
   */
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
  /**
   * Bounding rectangle.
   *
   * @returns {object} Bounding rectangle.
   */
  getBoundingClientRect() {
    const { left, top, width, height } = this.rect;
    return {
      x: left,
      y: top,
      left,
      top,
      width,
      height,
      right: left + width,
      bottom: top + height,
      toJSON() {
        return this;
      },
    };
  }
  /**
   * Set the text selection bounds.
   *
   * @param {number} start Selection start.
   * @param {number} end Selection end.
   */
  setSelectionRange(start, end) {
    this.selectionStart = start;
    this.selectionEnd = end;
  }
  /** Mark this element as the document's active element. */
  focus() {
    if (this.ownerDocument) this.ownerDocument.activeElement = this;
  }
  /** Accept blur requests. */
  blur() {}
  /** Dispatch a synthetic click event. */
  click() {
    this.dispatchEvent(Object.assign(new Event("click"), {}));
  }
  /** Accept programmatic scrolling requests. */
  scrollIntoView() {}
  /**
   * Fake captured stream.
   *
   * @returns {FakeMediaStream} Fake captured stream.
   */
  captureStream() {
    return new FakeMediaStream();
  }
  /**
   * All descendant elements.
   *
   * @returns {Element[]} All descendant elements.
   */
  #descendants() {
    /** @type {Element[]} */
    const all = [];
    /**
     * Subtree root.
     *
     * @param {Element} node Subtree root.
     */
    const walk = node => {
      for (const child of node.childNodes) {
        if (child instanceof Element) {
          all.push(child);
          walk(child);
        }
      }
    };
    walk(this);
    return all;
  }
}
/** Stand-in for HTMLElement. */
export class HTMLElement extends Element {}
/** Stand-in for HTMLAnchorElement. */
export class HTMLAnchorElement extends HTMLElement {}
/** Stand-in for HTMLButtonElement. */
export class HTMLButtonElement extends HTMLElement {}
/** Stand-in for HTMLInputElement. */
export class HTMLInputElement extends HTMLElement {}
/** Stand-in for HTMLSelectElement. */
export class HTMLSelectElement extends HTMLElement {}
/** Stand-in for HTMLOptionElement. */
export class HTMLOptionElement extends HTMLElement {}
/** Stand-in for HTMLOptGroupElement. */
export class HTMLOptGroupElement extends HTMLElement {}
/** Stand-in for HTMLTextAreaElement. */
export class HTMLTextAreaElement extends HTMLElement {}
/** Stand-in for HTMLProgressElement. */
export class HTMLProgressElement extends HTMLElement {}
/** Stand-in for HTMLMeterElement. */
export class HTMLMeterElement extends HTMLElement {}
/** Stand-in for HTMLImageElement. */
export class HTMLImageElement extends HTMLElement {}
/** Stand-in for HTMLMediaElement. */
export class HTMLMediaElement extends HTMLElement {
  static HAVE_CURRENT_DATA = 2;
}
/** Stand-in for HTMLVideoElement. */
export class HTMLVideoElement extends HTMLMediaElement {}
/** Stand-in for HTMLFormElement. */
export class HTMLFormElement extends HTMLElement {}
/** Stand-in for HTMLDetailsElement. */
export class HTMLDetailsElement extends HTMLElement {
  /**
   * Owning document.
   *
   * @param {string} tag Tag name.
   * @param {FakeDocument | null} [doc] Owning document.
   */
  constructor(tag, doc) {
    super(tag, doc);
    this.open = false;
  }
}
/** Stand-in for SVGElement. */
export class SVGElement extends Element {}
/** SVG graphics stand-in exposing a bounding box. */
export class SVGGraphicsElement extends SVGElement {
  /**
   * Bounding box.
   *
   * @returns {object} Bounding box.
   */
  getBBox() {
    const { left, top, width, height } = this.rect;
    return {
      x: left,
      y: top,
      width,
      height,
      toJSON() {
        return this;
      },
    };
  }
}
/** Stand-in for SVGSVGElement. */
export class SVGSVGElement extends SVGGraphicsElement {}
/** Stand-in for SVGTextElement. */
export class SVGTextElement extends SVGGraphicsElement {}
/** Minimal 2D affine matrix compatible with DOMMatrixReadOnly. */
export class FakeDOMMatrixReadOnly {
  /**
   * @param {string | {a?: number, b?: number, c?: number, d?: number, e?: number, f?: number}} [init]
   *   Matrix init.
   */
  constructor(init = "") {
    const values = { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 };
    if (typeof init === "string") {
      const match = /matrix\(([^)]*)\)/.exec(init);
      const parts = match?.[1]
        ?.split(/[\s,]+/)
        .map(Number)
        .filter(value => Number.isFinite(value));
      if (parts?.length === 6)
        [values.a, values.b, values.c, values.d, values.e, values.f] =
          /** @type {[number, number, number, number, number, number]} */ (
            parts
          );
    } else if (init && typeof init === "object") Object.assign(values, init);
    this.a = values.a;
    this.b = values.b;
    this.c = values.c;
    this.d = values.d;
    this.e = values.e;
    this.f = values.f;
    this.m11 = this.a;
    this.m12 = this.b;
    this.m21 = this.c;
    this.m22 = this.d;
    this.m41 = this.e;
    this.m42 = this.f;
  }
  /**
   * Whether the matrix is two-dimensional.
   *
   * @returns {boolean} Whether the matrix is two-dimensional.
   */
  get is2D() {
    return true;
  }
  /**
   * Post-multiply by another matrix.
   *
   * @param {FakeDOMMatrixReadOnly} other Matrix to post-multiply.
   * @returns {FakeDOMMatrixReadOnly} Combined matrix.
   */
  multiply(other) {
    return new FakeDOMMatrixReadOnly({
      a: this.a * other.a + this.c * other.b,
      b: this.b * other.a + this.d * other.b,
      c: this.a * other.c + this.c * other.d,
      d: this.b * other.c + this.d * other.d,
      e: this.a * other.e + this.c * other.f + this.e,
      f: this.b * other.e + this.d * other.f + this.f,
    });
  }
}
/** Mutable DOMMatrix alias of FakeDOMMatrixReadOnly. */
export class FakeDOMMatrix extends FakeDOMMatrixReadOnly {}
/**
 * Canvas 2d context stand-in.
 *
 * @returns {object} Canvas 2d context stand-in.
 */
const createContext2d = () => ({
  canvas: null,
  fillStyle: "",
  strokeStyle: "",
  globalAlpha: 1,
  globalCompositeOperation: "source-over",
  imageSmoothingEnabled: true,
  lineWidth: 1,
  save: () => {},
  restore: () => {},
  beginPath: () => {},
  closePath: () => {},
  clip: () => {},
  rect: () => {},
  moveTo: () => {},
  lineTo: () => {},
  arc: () => {},
  translate: () => {},
  scale: () => {},
  rotate: () => {},
  setTransform: () => {},
  clearRect: () => {},
  fillRect: () => {},
  strokeRect: () => {},
  fill: () => {},
  stroke: () => {},
  setLineDash: () => {},
  roundRect: () => {},
  ellipse: () => {},
  quadraticCurveTo: () => {},
  bezierCurveTo: () => {},
  arcTo: () => {},
  drawImage: () => {},
  fillText: () => {},
  strokeText: () => {},
  measureText: (/** @type {string} */ text) => ({
    width: String(text).length * 8,
  }),
  getImageData: (
    /** @type {number} */ _x,
    /** @type {number} */ _y,
    w = 1,
    h = 1,
  ) => ({
    width: w,
    height: h,
    data: new Uint8ClampedArray(w * h * 4).fill(255),
  }),
  putImageData: () => {},
  createImageData: (/** @type {number} */ w, /** @type {number} */ h) => ({
    width: w,
    height: h,
    data: new Uint8ClampedArray(w * h * 4),
  }),
});
/** Canvas element returning a fake 2d context. */
export class HTMLCanvasElement extends HTMLElement {
  /**
   * Owning document.
   *
   * @param {string} tag Tag name.
   * @param {FakeDocument | null} [doc] Owning document.
   */
  constructor(tag, doc) {
    super(tag, doc);
    this.width = 0;
    this.height = 0;
  }
  /**
   * 2d context stand-in.
   *
   * @returns {object} 2d context stand-in.
   */
  getContext() {
    return createContext2d();
  }
  /**
   * Data URL.
   *
   * @param {string} [type] MIME type.
   * @returns {string} Data URL.
   */
  toDataURL(type = "image/png") {
    return `data:${type};base64,AAAA`;
  }
  /**
   * Encode a PNG-like blob asynchronously.
   *
   * @param {(blob: Blob) => void} callback Result handler.
   * @param {string} [type] MIME type.
   */
  toBlob(callback, type = "image/png") {
    queueMicrotask(() =>
      callback(new Blob([new Uint8Array(32)], { type })),
    );
  }
}
/** Minimal Range stand-in for selection tests. */
class FakeRange {
  /**
   * Owning document.
   *
   * @param {FakeDocument} ownerDocument Owning document.
   */
  constructor(ownerDocument) {
    this.ownerDocument = ownerDocument;
    /** @type {Element | null} */
    this.node = null;
    /** @type {FakeNode | null} */
    this.startContainer = null;
    /** @type {FakeNode | null} */
    this.endContainer = null;
    this.startOffset = 0;
    this.endOffset = 0;
    this.collapsed = false;
  }
  /**
   * Set the start boundary.
   *
   * @param {FakeNode} node Boundary node.
   * @param {number} offset Boundary offset.
   */
  setStart(node, offset) {
    this.startContainer = node;
    this.startOffset = offset;
  }
  /**
   * Set the end boundary.
   *
   * @param {FakeNode} node Boundary node.
   * @param {number} offset Boundary offset.
   */
  setEnd(node, offset) {
    this.endContainer = node;
    this.endOffset = offset;
  }
  /**
   * Collapse the range, optionally to the start.
   *
   * @param {boolean} [toStart] Collapse to the start boundary.
   */
  collapse(toStart = false) {
    this.collapsed = true;
    if (toStart) {
      this.endContainer = this.startContainer;
      this.endOffset = this.startOffset;
    }
  }
  /**
   * Detached copy of this range.
   *
   * @returns {FakeRange} Detached copy of this range.
   */
  cloneRange() {
    const copy = new FakeRange(this.ownerDocument);
    copy.node = this.node;
    copy.startContainer = this.startContainer;
    copy.endContainer = this.endContainer;
    copy.startOffset = this.startOffset;
    copy.endOffset = this.endOffset;
    copy.collapsed = this.collapsed;
    return copy;
  }
  /**
   * Empty fragment-like holder.
   *
   * @returns {Element} Empty fragment-like holder.
   */
  cloneContents() {
    const holder = new HTMLElement("div", this.ownerDocument);
    const source = this.node ?? this.startContainer;
    if (source) holder.append(source.cloneNode?.(true) ?? source);
    return holder;
  }
  /** Remove the selected content. */
  deleteContents() {
    this.node?.remove?.();
    this.node = null;
  }
  /**
   * Insert a node at the start boundary.
   *
   * @param {FakeNode} node Node to insert.
   */
  insertNode(node) {
    (this.startContainer ?? this.node)?.before?.(node);
  }
  /**
   * Whether the node intersects the range.
   *
   * @param {FakeNode} node Candidate node.
   * @returns {boolean} Whether the node intersects the range.
   */
  intersectsNode(node) {
    const anchor = this.node ?? this.startContainer;
    if (!anchor) return false;
    return (
      anchor === node ||
      anchor.parentElement === node ||
      node.parentElement === anchor
    );
  }
  /**
   * Select a node's contents.
   *
   * @param {Element} node Node to select.
   */
  selectNodeContents(node) {
    this.node = node;
  }
  /**
   * Select a node.
   *
   * @param {Element} node Node to select.
   */
  selectNode(node) {
    this.node = node;
  }
  /**
   * Client rectangles.
   *
   * @returns {object[]} Client rectangles.
   */
  getClientRects() {
    const rect = this.node?.getBoundingClientRect() ?? {
      left: 0,
      top: 0,
      width: 60,
      height: 14,
      right: 60,
      bottom: 14,
    };
    return [rect];
  }
  /**
   * Bounding rectangle.
   *
   * @returns {object | undefined} Bounding rectangle.
   */
  getBoundingClientRect() {
    return this.getClientRects()[0];
  }
}
/** MediaRecorder stand-in emitting synthetic chunks. */
class FakeMediaRecorder extends FakeEventTarget {
  /**
   * Recorder options.
   *
   * @param {FakeMediaStream} stream Captured stream.
   * @param {{mimeType?: string}} [options] Recorder options.
   */
  constructor(stream, options = {}) {
    super();
    this.stream = stream;
    this.mimeType = options.mimeType ?? "video/webm";
    /** @type {"inactive" | "recording" | "paused"} */
    this.state = "inactive";
  }
  /**
   * Type support probe.
   *
   * @returns {boolean} Type support probe.
   */
  static isTypeSupported = () => true;
  /** Begin recording and emit one chunk. */
  start() {
    this.state = "recording";
    queueMicrotask(() =>
      this.dispatchEvent(
        Object.assign(new Event("dataavailable"), {
          data: this.#chunk(),
        }),
      ),
    );
  }
  /** Emit a data chunk on demand. */
  requestData() {
    this.dispatchEvent(
      Object.assign(new Event("dataavailable"), { data: this.#chunk() }),
    );
  }
  /** Pause the fake recording. */
  pause() {
    this.state = "paused";
  }
  /** Resume the fake recording. */
  resume() {
    this.state = "recording";
  }
  /** Stop recording, emitting a final chunk and stop event. */
  stop() {
    if (this.state === "inactive") return;
    this.state = "inactive";
    this.dispatchEvent(
      Object.assign(new Event("dataavailable"), { data: this.#chunk() }),
    );
    this.dispatchEvent(new Event("stop"));
  }
  /**
   * Synthetic video chunk.
   *
   * @returns {Blob} Synthetic video chunk.
   */
  #chunk() {
    const head = Uint8Array.of(0x1a, 0x45, 0xdf, 0xa3);
    const body = new Uint8Array(512).fill(7);
    return new Blob([head, body], { type: this.mimeType });
  }
}
/** Image stand-in resolving loads immediately. */
class FakeImage {
  constructor() {
    this.width = 100;
    this.height = 100;
    this.naturalWidth = 100;
    this.naturalHeight = 100;
    /** @type {(() => void) | null} */
    this.onload = null;
    /** @type {(() => void) | null} */
    this.onerror = null;
  }
  /**
   * Set the image source and resolve onload.
   *
   * @param {string} _value Image source.
   */
  set src(_value) {
    queueMicrotask(() => this.onload?.());
  }
  /**
   * Immediate decode.
   *
   * @returns {Promise<void>} Immediate decode.
   */
  decode() {
    return Promise.resolve();
  }
}
/** FileReader stand-in backed by blob.arrayBuffer. */
class FakeFileReader {
  /** @type {string | ArrayBuffer | null} */
  result = null;
  /** @type {unknown} */
  error = null;
  /** @type {(() => void) | null} */
  onload = null;
  /** @type {(() => void) | null} */
  onloadend = null;
  /** @type {(() => void) | null} */
  onerror = null;
  /**
   * Read a blob as a base64 data URL.
   *
   * @param {Blob} blob Source blob.
   */
  readAsDataURL(blob) {
    blob
      .arrayBuffer()
      .then(buffer => {
        let binary = "";
        for (const byte of new Uint8Array(buffer))
          binary += String.fromCharCode(byte);
        this.result = `data:${blob.type || "application/octet-stream"};base64,${btoa(binary)}`;
        this.onload?.();
        this.onloadend?.();
      })
      .catch(error => {
        this.error = error;
        this.onerror?.();
      });
  }
  /**
   * Read a blob as an ArrayBuffer.
   *
   * @param {Blob} blob Source blob.
   */
  readAsArrayBuffer(blob) {
    blob
      .arrayBuffer()
      .then(buffer => {
        this.result = buffer;
        this.onload?.();
        this.onloadend?.();
      })
      .catch(error => {
        this.error = error;
        this.onerror?.();
      });
  }
}
/** URL subclass with fake object-URL helpers. */
class FakeURL extends URL {
  /** @override */
  static createObjectURL = () => "blob:fake/1";
  /** @override */
  static revokeObjectURL = () => {};
}
const STYLE_DEFAULTS = {
  accentColor: "auto",
  alignItems: "normal",
  appearance: "none",
  backdropFilter: "none",
  backgroundAttachment: "scroll",
  backgroundBlendMode: "normal",
  backgroundClip: "border-box",
  backgroundColor: "rgba(0, 0, 0, 0)",
  backgroundImage: "none",
  backgroundOrigin: "padding-box",
  backgroundPosition: "0% 0%",
  backgroundRepeat: "repeat",
  backgroundSize: "auto",
  borderBottomColor: "rgb(0, 0, 0)",
  borderBottomLeftRadius: "0px",
  borderBottomRightRadius: "0px",
  borderBottomStyle: "none",
  borderBottomWidth: "0px",
  borderCollapse: "separate",
  borderImage: "none",
  borderLeftColor: "rgb(0, 0, 0)",
  borderLeftStyle: "none",
  borderLeftWidth: "0px",
  borderRightColor: "rgb(0, 0, 0)",
  borderRightStyle: "none",
  borderRightWidth: "0px",
  borderTopColor: "rgb(0, 0, 0)",
  borderTopLeftRadius: "0px",
  borderTopRightRadius: "0px",
  borderTopStyle: "none",
  borderTopWidth: "0px",
  bottom: "auto",
  boxDecorationBreak: "slice",
  boxShadow: "none",
  boxSizing: "content-box",
  caretColor: "auto",
  clear: "none",
  clipPath: "none",
  color: "rgb(0, 0, 0)",
  colorScheme: "normal",
  columnCount: "auto",
  columnGap: "normal",
  contain: "none",
  containerType: "normal",
  content: "none",
  cursor: "auto",
  direction: "ltr",
  display: "block",
  filter: "none",
  flexBasis: "auto",
  flexDirection: "row",
  flexGrow: "0",
  flexShrink: "1",
  flexWrap: "nowrap",
  float: "none",
  fontFamily: "sans-serif",
  fontFeatureSettings: "normal",
  fontKerning: "auto",
  fontSize: "16px",
  fontStretch: "normal",
  fontStyle: "normal",
  fontVariant: "normal",
  fontWeight: "400",
  gap: "normal",
  gridArea: "auto",
  gridAutoFlow: "row",
  gridTemplateColumns: "none",
  gridTemplateRows: "none",
  height: "20px",
  isolation: "auto",
  justifyContent: "normal",
  left: "auto",
  letterSpacing: "normal",
  lineHeight: "normal",
  listStylePosition: "outside",
  listStyleType: "disc",
  marginBottom: "0px",
  marginLeft: "0px",
  marginRight: "0px",
  marginTop: "0px",
  maskImage: "none",
  mixBlendMode: "normal",
  objectFit: "fill",
  objectPosition: "50% 50%",
  opacity: "1",
  order: "0",
  outlineColor: "rgb(0, 0, 0)",
  outlineOffset: "0px",
  outlineStyle: "none",
  outlineWidth: "0px",
  overflow: "visible",
  overflowX: "visible",
  overflowY: "visible",
  overscrollBehavior: "auto",
  paddingBottom: "0px",
  paddingLeft: "0px",
  paddingRight: "0px",
  paddingTop: "0px",
  perspective: "none",
  pointerEvents: "auto",
  position: "static",
  right: "auto",
  rowGap: "normal",
  scrollBehavior: "auto",
  tableLayout: "auto",
  textAlign: "start",
  textDecorationColor: "rgb(0, 0, 0)",
  textDecorationLine: "none",
  textIndent: "0px",
  textOverflow: "clip",
  textShadow: "none",
  textTransform: "none",
  top: "auto",
  transform: "none",
  transformOrigin: "50% 50%",
  transformStyle: "flat",
  transitionDuration: "0s",
  userSelect: "auto",
  verticalAlign: "baseline",
  visibility: "visible",
  whiteSpace: "normal",
  width: "100px",
  willChange: "auto",
  wordBreak: "normal",
  writingMode: "horizontal-tb",
  zIndex: "auto",
};
/** @type {Record<string, new (tag: string, doc: FakeDocument) => Element>} */
const TAG_CLASSES = {
  a: HTMLAnchorElement,
  button: HTMLButtonElement,
  input: HTMLInputElement,
  select: HTMLSelectElement,
  option: HTMLOptionElement,
  optgroup: HTMLOptGroupElement,
  textarea: HTMLTextAreaElement,
  progress: HTMLProgressElement,
  meter: HTMLMeterElement,
  img: HTMLImageElement,
  video: HTMLVideoElement,
  audio: HTMLMediaElement,
  canvas: HTMLCanvasElement,
  details: HTMLDetailsElement,
  form: HTMLFormElement,
  svg: SVGSVGElement,
  text: SVGTextElement,
};
/**
 * Fixture document.
 *
 * @returns {FakeDocument} Fixture document.
 */
export const createDocument = () => {
  /**
   * Resolved style map.
   *
   * @param {Element} element Target element.
   * @param {string | null} [pseudo] Optional pseudo element.
   * @returns {Record<string, string>} Resolved style map.
   */
  const styleFor = (element, pseudo = null) => {
    /** @type {Record<string, string>} */
    const overrides = pseudo
      ? (element.pseudoStyles?.[pseudo] ?? {})
      : element.styleOverrides;
    /** @type {Record<string, string>} */
    const styles = { ...STYLE_DEFAULTS, ...overrides };
    return new Proxy(styles, {
      get: (target, property) => {
        if (property === "getPropertyValue")
          return (/** @type {string} */ name) => target[name] ?? "";
        return target[String(property)] ?? "";
      },
    });
  };
  const document = /** @type {FakeDocument} */ (
    /** @type {any} */ ({
      title: "Scene fixture",
      baseURI: "https://scene-tests.local/",
      referrer: "",
      characterSet: "UTF-8",
      contentType: "text/html",
      compatMode: "CSS1Compat",
      activeElement: null,
      createRange: () => new FakeRange(document),
      elementFromPoint: () => null,
      elementsFromPoint: () => [],
      getComputedStyle: styleFor,
      createElement: (/** @type {string} */ tag) =>
        new (TAG_CLASSES[String(tag).toLowerCase()] ?? HTMLElement)(
          tag,
          document,
        ),
      createElementNS: (
        /** @type {string | null} */ _ns,
        /** @type {string} */ tag,
      ) =>
        new (TAG_CLASSES[String(tag).toLowerCase()] ?? SVGElement)(
          tag,
          document,
        ),
      createTextNode: (/** @type {string} */ text) =>
        new FakeTextNode(text, document),
      querySelectorAll: (/** @type {string} */ selector) =>
        document.documentElement.querySelectorAll(selector),
      querySelector: (/** @type {string} */ selector) =>
        document.documentElement.querySelector(selector),
      getElementById: (/** @type {string} */ id) =>
        document.documentElement
          .querySelectorAll("*")
          .find(element => element.id === id) ?? null,
      addEventListener: () => {},
      removeEventListener: () => {},
    })
  );
  document.documentElement = new HTMLElement("html", document);
  document.documentElement.lang = "en";
  document.head = new HTMLElement("head", document);
  document.body = new HTMLElement("body", document);
  document.documentElement.append(document.head, document.body);
  currentDocument = document;
  return document;
};
/**
 * @typedef {object} SandboxGlobal
 * @property {Console} console
 * @property {typeof TextEncoder} TextEncoder
 * @property {typeof TextDecoder} TextDecoder
 * @property {typeof FakeEventTarget} EventTarget
 * @property {typeof Event} Event
 * @property {typeof Event} CustomEvent
 * @property {typeof FakeURL} URL
 * @property {import("node:crypto").webcrypto.Crypto} crypto
 * @property {Performance} performance
 * @property {(data: string) => string} btoa
 * @property {(data: string) => string} atob
 * @property {typeof queueMicrotask} queueMicrotask
 * @property {typeof setTimeout} setTimeout
 * @property {typeof clearTimeout} clearTimeout
 * @property {typeof setInterval} setInterval
 * @property {typeof clearInterval} clearInterval
 * @property {PromiseConstructor} Promise
 * @property {MapConstructor} Map
 * @property {SetConstructor} Set
 * @property {WeakMapConstructor} WeakMap
 * @property {WeakSetConstructor} WeakSet
 * @property {JSON} JSON
 * @property {Math} Math
 * @property {DateConstructor} Date
 * @property {NumberConstructor} Number
 * @property {StringConstructor} String
 * @property {BooleanConstructor} Boolean
 * @property {RegExpConstructor} RegExp
 * @property {ErrorConstructor} Error
 * @property {TypeErrorConstructor} TypeError
 * @property {RangeErrorConstructor} RangeError
 * @property {SymbolConstructor} Symbol
 * @property {ArrayConstructor} Array
 * @property {ObjectConstructor} Object
 * @property {typeof Reflect} Reflect
 * @property {typeof Proxy} Proxy
 * @property {typeof Intl} Intl
 * @property {typeof Blob} Blob
 * @property {ArrayBufferConstructor} ArrayBuffer
 * @property {SharedArrayBufferConstructor} SharedArrayBuffer
 * @property {Uint8ArrayConstructor} Uint8Array
 * @property {Uint8ClampedArrayConstructor} Uint8ClampedArray
 * @property {Uint16ArrayConstructor} Uint16Array
 * @property {Uint32ArrayConstructor} Uint32Array
 * @property {Int8ArrayConstructor} Int8Array
 * @property {Int16ArrayConstructor} Int16Array
 * @property {Int32ArrayConstructor} Int32Array
 * @property {Float32ArrayConstructor} Float32Array
 * @property {Float64ArrayConstructor} Float64Array
 * @property {DataViewConstructor} DataView
 * @property {BigIntConstructor} BigInt
 * @property {typeof FakeTextNode} Text
 * @property {typeof FakeDOMMatrix} DOMMatrix
 * @property {typeof FakeDOMMatrixReadOnly} DOMMatrixReadOnly
 * @property {typeof FakeNode} Node
 * @property {typeof Element} Element
 * @property {typeof HTMLElement} HTMLElement
 * @property {typeof HTMLAnchorElement} HTMLAnchorElement
 * @property {typeof HTMLButtonElement} HTMLButtonElement
 * @property {typeof HTMLCanvasElement} HTMLCanvasElement
 * @property {typeof HTMLDetailsElement} HTMLDetailsElement
 * @property {typeof HTMLFormElement} HTMLFormElement
 * @property {typeof HTMLImageElement} HTMLImageElement
 * @property {typeof HTMLInputElement} HTMLInputElement
 * @property {typeof HTMLMediaElement} HTMLMediaElement
 * @property {typeof HTMLMeterElement} HTMLMeterElement
 * @property {typeof HTMLOptGroupElement} HTMLOptGroupElement
 * @property {typeof HTMLOptionElement} HTMLOptionElement
 * @property {typeof HTMLProgressElement} HTMLProgressElement
 * @property {typeof HTMLSelectElement} HTMLSelectElement
 * @property {typeof HTMLTextAreaElement} HTMLTextAreaElement
 * @property {typeof HTMLVideoElement} HTMLVideoElement
 * @property {typeof SVGElement} SVGElement
 * @property {typeof SVGGraphicsElement} SVGGraphicsElement
 * @property {typeof SVGSVGElement} SVGSVGElement
 * @property {typeof SVGTextElement} SVGTextElement
 * @property {typeof FakeRange} Range
 * @property {typeof FakeImage} Image
 * @property {typeof FakeFileReader} FileReader
 * @property {typeof FakeMediaRecorder} MediaRecorder
 * @property {typeof FakeMediaStream} MediaStream
 * @property {object} XMLSerializer
 * @property {object} MutationObserver
 * @property {object} PerformanceObserver
 * @property {{href: string}} location
 * @property {{escape: (value: string) => string,
 *   supports: () => boolean}} CSS
 * @property {number} innerWidth
 * @property {number} innerHeight
 * @property {number} outerWidth
 * @property {number} outerHeight
 * @property {number} scrollX
 * @property {number} scrollY
 * @property {number} pageXOffset
 * @property {number} pageYOffset
 * @property {number} devicePixelRatio
 * @property {number} screenX
 * @property {number} screenY
 * @property {FakeEventTarget & {
 *   width: number,
 *   height: number,
 *   offsetLeft: number,
 *   offsetTop: number,
 *   pageLeft: number,
 *   pageTop: number,
 *   scale: number
 * }} visualViewport
 * @property {(query: string) =>
 *   {matches: boolean, media: string}} matchMedia
 * @property {(element: Element, pseudo?: string | null) =>
 *   Record<string, string>} getComputedStyle
 * @property {object} navigator
 * @property {object} screen
 * @property {() => Promise<{blob: () => Promise<Blob>}>} fetch
 * @property {{toCanvas: () => Promise<HTMLCanvasElement>}} htmlToImage
 * @property {FakeDocument} document
 * @property {(type: string, listener: (event: any) => void) => void}
 *   addEventListener
 * @property {(type: string, listener: (event: any) => void) => void}
 *   removeEventListener
 * @property {(event: Event) => boolean} dispatchEvent
 * @property {FakeEventTarget} __globalListeners
 * @property {Map<unknown, unknown>} __listeners
 * @property {(buffer: BufferSource) => Promise<ArrayBuffer>}
 *   __evidenceSha256
 * @property {unknown} [key]
 */
/**
 * Populate a VM sandbox global with the fake browser environment.
 *
 * @param {{webcrypto: import("node:crypto").webcrypto.Crypto}} dependencies
 *   Runtime dependencies.
 * @returns {SandboxGlobal} Populated VM sandbox global.
 */
export const buildSandbox = dependencies => {
  const { webcrypto } = dependencies;
  const listeners = new Map();
  const document = createDocument();
  const visualViewport = /** @type {FakeEventTarget & {
   *   width: number,
   *   height: number,
   *   offsetLeft: number,
   *   offsetTop: number,
   *   pageLeft: number,
   *   pageTop: number,
   *   scale: number
   * }} */ (new FakeEventTarget());
  Object.assign(visualViewport, {
    width: 800,
    height: 600,
    offsetLeft: 0,
    offsetTop: 0,
    pageLeft: 0,
    pageTop: 0,
    scale: 1,
  });
  const globalListeners = new FakeEventTarget();
  const sandbox = {
    console,
    TextEncoder,
    TextDecoder,
    EventTarget: FakeEventTarget,
    Event,
    CustomEvent: class extends Event {
      /** @type {unknown} */
      detail;
      /**
       * Event init.
       *
       * @param {string} type Event type.
       * @param {{detail?: unknown} & EventInit} [options] Event init.
       */
      constructor(type, options = {}) {
        super(type, options);
        this.detail = options.detail;
      }
    },
    URL: FakeURL,
    crypto: webcrypto,
    performance,
    btoa,
    atob,
    queueMicrotask,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    Promise,
    Map,
    Set,
    WeakMap,
    WeakSet,
    JSON,
    Math,
    Date,
    Number,
    String,
    Boolean,
    RegExp,
    Error,
    TypeError,
    RangeError,
    Symbol,
    Array,
    Object,
    Reflect,
    Proxy,
    Intl,
    Blob: globalThis.Blob,
    ArrayBuffer,
    SharedArrayBuffer,
    Uint8Array,
    Uint8ClampedArray,
    Uint16Array,
    Uint32Array,
    Int8Array,
    Int16Array,
    Int32Array,
    Float32Array,
    Float64Array,
    DataView,
    BigInt,
    Text: FakeTextNode,
    DOMMatrix: FakeDOMMatrix,
    DOMMatrixReadOnly: FakeDOMMatrixReadOnly,
    Node: Object.assign(FakeNode, {
      ELEMENT_NODE: 1,
      TEXT_NODE: 3,
      DOCUMENT_POSITION_DISCONNECTED: 1,
      DOCUMENT_POSITION_PRECEDING: 2,
      DOCUMENT_POSITION_FOLLOWING: 4,
      DOCUMENT_POSITION_CONTAINS: 8,
      DOCUMENT_POSITION_CONTAINED_BY: 16,
    }),
    Element,
    HTMLElement,
    HTMLAnchorElement,
    HTMLButtonElement,
    HTMLCanvasElement,
    HTMLDetailsElement,
    HTMLFormElement,
    HTMLImageElement,
    HTMLInputElement,
    HTMLMediaElement,
    HTMLMeterElement,
    HTMLOptGroupElement,
    HTMLOptionElement,
    HTMLProgressElement,
    HTMLSelectElement,
    HTMLTextAreaElement,
    HTMLVideoElement,
    SVGElement,
    SVGGraphicsElement,
    SVGSVGElement,
    SVGTextElement,
    Range: FakeRange,
    Image: FakeImage,
    FileReader: FakeFileReader,
    MediaRecorder: FakeMediaRecorder,
    MediaStream: FakeMediaStream,
    XMLSerializer: class {
      /**
       * Node to serialize.
       *
       * @param {Element} node Node to serialize.
       */
      serializeToString(node) {
        const attrs = [...(node.attributesMap?.entries() ?? [])]
          .map(([name, value]) => ` ${name}="${value}"`)
          .join("");
        return `<${node.localName}${attrs}></${node.localName}>`;
      }
    },
    MutationObserver: class {
      /** @type {(mutations: unknown[], observer: unknown) => void} */
      callback;
      /** @type {[unknown, unknown][]} */
      observed;
      /** @type {boolean | undefined} */
      disconnected;
      /**
       * @param {(mutations: unknown[], observer: unknown) => void} callback
       *   Observation callback.
       */
      constructor(callback) {
        this.callback = callback;
        this.observed = [];
      }
      /**
       * Observation options.
       *
       * @param {unknown} target Observed node.
       * @param {unknown} options Observation options.
       */
      observe(target, options) {
        this.observed.push([target, options]);
      }
      disconnect() {
        this.disconnected = true;
      }
    },
    PerformanceObserver: class {
      /** @type {unknown} */
      callback;
      /** @type {unknown} */
      options;
      /** @type {boolean | undefined} */
      disconnected;
      /**
       * Observation callback.
       *
       * @param {unknown} callback Observation callback.
       */
      constructor(callback) {
        this.callback = callback;
      }
      /**
       * Observation options.
       *
       * @param {unknown} options Observation options.
       */
      observe(options) {
        this.options = options;
      }
      disconnect() {
        this.disconnected = true;
      }
    },
    location: { href: "https://scene-tests.local/page" },
    CSS: {
      /**
       * Identifier to escape.
       *
       * @param {string} value Identifier to escape.
       */
      escape: (/** @type {unknown} */ value) =>
        String(value).replace(/[^a-zA-Z0-9_-]/g, "\\$&"),
      /**
       * Always supported.
       *
       * @returns {boolean} Always supported.
       */
      supports: () => true,
    },
    innerWidth: 800,
    innerHeight: 600,
    outerWidth: 820,
    outerHeight: 700,
    scrollX: 0,
    scrollY: 0,
    pageXOffset: 0,
    pageYOffset: 0,
    devicePixelRatio: 2,
    screenX: 10,
    screenY: 20,
    visualViewport,
    matchMedia: (/** @type {string} */ query) => ({
      matches: false,
      media: query,
    }),
    getComputedStyle: (
      /** @type {Element} */ element,
      /** @type {string | null} */ pseudo = null,
    ) => document.getComputedStyle(element, pseudo),
    navigator: {
      language: "en-US",
      languages: ["en-US", "en"],
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
        "AppleWebKit/537.36 (KHTML, like Gecko) " +
        "Chrome/124.0.0.0 Safari/537.36",
      appVersion: "5.0",
      vendor: "Google Inc.",
      platform: "MacIntel",
      maxTouchPoints: 0,
      hardwareConcurrency: 8,
      cookieEnabled: true,
      onLine: true,
      webdriver: false,
      pdfViewerEnabled: true,
      connection: {
        effectiveType: "4g",
        downlink: 10,
        rtt: 50,
        saveData: false,
        type: "wifi",
      },
      storage: { quota: 1000, usage: 100, usageDetails: {} },
      userAgentData: { mobile: false },
    },
    screen: {
      width: 1920,
      height: 1080,
      availWidth: 1920,
      availHeight: 1040,
      availLeft: 0,
      availTop: 0,
      colorDepth: 24,
      pixelDepth: 24,
      isExtended: false,
    },
    fetch: async () => ({
      blob: async () =>
        new Blob([new Uint8Array(16)], { type: "image/png" }),
    }),
    htmlToImage: {
      toCanvas: async () => {
        const canvas = new HTMLCanvasElement("canvas", document);
        canvas.width = 200;
        canvas.height = 100;
        return canvas;
      },
    },
    document,
    addEventListener: (
      /** @type {string} */ type,
      /** @type {(event: any) => void} */ listener,
    ) => globalListeners.addEventListener(type, listener),
    removeEventListener: (
      /** @type {string} */ type,
      /** @type {(event: any) => void} */ listener,
    ) => globalListeners.removeEventListener(type, listener),
    dispatchEvent: (/** @type {Event} */ event) =>
      globalListeners.dispatchEvent(event),
    __globalListeners: globalListeners,
    __listeners: listeners,
    __evidenceSha256: async (/** @type {BufferSource} */ buffer) =>
      webcrypto.subtle.digest("SHA-256", buffer),
  };
  return sandbox;
};
