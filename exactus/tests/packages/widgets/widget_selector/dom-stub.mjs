/** Minimal DOM stand-in for node --test widget suites. */
/**
 * @typedef {object} FakeText
 * @property {number} nodeType DOM text-node marker.
 * @property {string} textContent Node text.
 * @property {FakeElement | null} parentElement Parent element, when attached.
 * @property {(() => void) | undefined} [remove] Optional detach hook.
 */
/** @typedef {FakeElement | FakeText} FakeNode */
/**
 * @typedef {object} StubDocument
 * @property {(tag: string) => FakeElement} createElement
 * @property {(_namespace: string, tag: string) => FakeElement} createElementNS
 * @property {(text: string) => FakeText} createTextNode
 * @property {() => FakeElement[]} querySelectorAll
 * @property {FakeElement | null} activeElement
 * @property {FakeElement} documentElement
 * @property {FakeElement} body
 */
/** Minimal classList implementation for {@link FakeElement}. */
class FakeClassList {
  /** @type {FakeElement} */
  #element;
  /** @param {FakeElement} element Owning element. */
  constructor(element) {
    this.#element = element;
  }
  /**
   * Current class-name count.
   *
   * @returns {number} Number of class names.
   */
  get length() {
    return this.#names().length;
  }
  /**
   * Append class names to the element.
   *
   * @param {...string} names Class names to add.
   */
  add(...names) {
    this.#write([...this.#names(), ...names]);
  }
  /**
   * Remove class names from the element.
   *
   * @param {...string} names Class names to remove.
   */
  remove(...names) {
    const drop = new Set(names);
    this.#write(this.#names().filter(name => !drop.has(name)));
  }
  /**
   * Toggle a class name, optionally forcing the state.
   *
   * @param {string} name Class name to toggle.
   * @param {boolean} [force] Forced state, when supplied.
   * @returns {boolean} Resulting presence.
   */
  toggle(name, force) {
    const on = force ?? !this.contains(name);
    if (on) this.add(name);
    else this.remove(name);
    return on;
  }
  /**
   * Test whether a class name is present.
   *
   * @param {string} name Class name to test.
   * @returns {boolean} Whether the class is present.
   */
  contains(name) {
    return this.#names().includes(name);
  }
  /**
   * Read the element's current class names.
   *
   * @returns {string[]} Current class names.
   */
  #names() {
    return this.#element.className.split(/\s+/).filter(Boolean);
  }
  /**
   * Replace the element's class names.
   *
   * @param {string[]} names Replacement class names.
   */
  #write(names) {
    this.#element.className = [...new Set(names.filter(Boolean))].join(" ");
  }
  /** @returns {Generator<string>} Class-name iterator. */
  *[Symbol.iterator]() {
    yield* this.#names();
  }
}
/**
 * Test whether an element satisfies a simple selector.
 *
 * @param {FakeElement} element Element under test.
 * @param {string} selector Tag, class or attribute selector.
 * @returns {boolean} Whether the element matches.
 */
const matchesSimple = (element, selector) => {
  const trimmed = selector.trim();
  const attribute = /^\[([\w-]+)(?:="([^"]*)")?\]$/.exec(trimmed);
  if (attribute) {
    const name = attribute[1];
    if (name === undefined) return false;
    return (
      element.getAttribute(name) !== null &&
      (attribute[2] === undefined || element.getAttribute(name) === attribute[2])
    );
  }
  const pieces = trimmed.split(".");
  const tag = pieces[0];
  if (tag && tag !== "*" && element.localName !== tag.toLowerCase())
    return false;
  return pieces.slice(1).every(name => element.classList.contains(name));
};

/** Minimal element stand-in for node-based widget tests. */
export class FakeElement {
  /**
   * @param {string} tag Tag name.
   * @param {StubDocument | null} [ownerDocument] Owning document.
   */
  constructor(tag, ownerDocument = null) {
    this.tagName = String(tag).toUpperCase();
    this.localName = String(tag).toLowerCase();
    /** @type {StubDocument | null} */
    this.ownerDocument = ownerDocument;
    /** @type {FakeElement | null} */
    this.parentElement = null;
    /** @type {FakeNode[]} */
    this.children = [];
    /** @type {Map<string, string>} */
    this.attributesMap = new Map();
    this.className = "";
    this.id = "";
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.checked = false;
    this.type = "";
    this.name = "";
    this.size = 0;
    this.title = "";
    this.placeholder = "";
    this.spellcheck = true;
    this.selectionStart = 0;
    this.selectionEnd = 0;
    this.scrollWidth = 0;
    this.scrollHeight = 0;
    this.clientWidth = 0;
    this.clientHeight = 0;
    this.offsetWidth = 100;
    this.offsetHeight = 20;
    /** @type {Record<string, string>} */
    this.dataset = {};
    this.ownText = "";
    /** @type {Record<string, ((event: Event) => void)[]>} */
    this.listeners = {};
    this.classList = new FakeClassList(this);
    /** @type {Record<string, string>} */
    const styleStore = {};
    this.style = {
      /**
       * @param {string} name Property name.
       * @param {string} value Property value.
       */
      setProperty: (name, value) => {
        styleStore[name] = value;
      },
      /** @param {string} name Property name. */
      removeProperty: name => {
        delete styleStore[name];
      },
      /**
       * @param {string} name Property name.
       * @returns {string} Stored value or the empty string.
       */
      getPropertyValue: name => styleStore[name] ?? "",
    };
  }

  /**
   * Child nodes of this element.
   *
   * @returns {FakeNode[]} Child nodes.
   */
  get childNodes() {
    return this.children;
  }

  /**
   * Attribute pairs in insertion order.
   *
   * @returns {{name: string, value: string}[]} Attribute pairs.
   */
  get attributes() {
    return [...this.attributesMap].map(([name, value]) => ({ name, value }));
  }

  /**
   * Concatenated text of this subtree.
   *
   * @returns {string} Concatenated text content.
   */
  get textContent() {
    return (
      this.ownText +
      this.children.map(child => child.textContent ?? "").join("")
    );
  }

  /**
   * Replace children with a single text value.
   *
   * @param {unknown} value New text content.
   */
  set textContent(value) {
    this.ownText = String(value);
    for (const child of this.children) child.parentElement = null;
    this.children.length = 0;
  }

  /**
   * Visible text content.
   *
   * @returns {string} Visible text content.
   */
  get innerText() {
    return this.textContent;
  }

  /**
   * Append child nodes.
   *
   * @param {...FakeNode} nodes Nodes to append.
   */
  append(...nodes) {
    for (const node of nodes) {
      node.remove?.();
      node.parentElement = this;
      this.children.push(node);
    }
  }

  /**
   * Prepend child nodes.
   *
   * @param {...FakeNode} nodes Nodes to prepend.
   */
  prepend(...nodes) {
    for (const node of nodes.reverse()) {
      node.remove?.();
      node.parentElement = this;
      this.children.unshift(node);
    }
  }

  /**
   * Insert a node after this element.
   *
   * @param {FakeNode} node Node to insert after this element.
   */
  after(node) {
    const parent = this.parentElement;
    if (!parent) return;
    node.remove?.();
    node.parentElement = parent;
    parent.children.splice(parent.children.indexOf(this) + 1, 0, node);
  }

  /** Detach this element from its parent. */
  remove() {
    const parent = this.parentElement;
    if (parent) {
      parent.children.splice(parent.children.indexOf(this), 1);
      this.parentElement = null;
    }
  }

  /**
   * Replace all children.
   *
   * @param {...FakeNode} nodes Replacement children.
   */
  replaceChildren(...nodes) {
    for (const child of this.children) child.parentElement = null;
    this.children.length = 0;
    this.append(...nodes);
  }

  /**
   * Test whether a node is a descendant of this element.
   *
   * @param {FakeNode | null} node Candidate descendant.
   * @returns {boolean} Whether the node is contained.
   */
  contains(node) {
    for (let current = node; current; current = current.parentElement)
      if (current === this) return true;
    return false;
  }

  /**
   * Set an attribute value.
   *
   * @param {string} name Attribute name.
   * @param {unknown} value Attribute value.
   */
  setAttribute(name, value) {
    this.attributesMap.set(String(name), String(value));
  }

  /**
   * Read an attribute value.
   *
   * @param {string} name Attribute name.
   * @returns {string | null} Attribute value or null.
   */
  getAttribute(name) {
    return this.attributesMap.has(name)
      ? this.attributesMap.get(name) ?? null
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
   * Test whether an attribute exists.
   *
   * @param {string} name Attribute name.
   * @returns {boolean} Whether the attribute exists.
   */
  hasAttribute(name) {
    return this.attributesMap.has(name);
  }

  /**
   * Test a simple selector against this element.
   *
   * @param {string} selector Simple selector.
   * @returns {boolean} Whether the element matches.
   */
  matches(selector) {
    return matchesSimple(this, selector);
  }

  /**
   * Find the closest matching ancestor, inclusive of self.
   *
   * @param {string} selector Simple selector.
   * @returns {FakeElement | null} Closest matching ancestor, inclusive.
   */
  closest(selector) {
    for (
      let current = /** @type {FakeElement | null} */ (this);
      current;
      current = current.parentElement
    )
      if (current.matches(selector)) return current;
    return null;
  }

  /**
   * Find all matching descendants.
   *
   * @param {string} selector Space-separated simple selectors.
   * @returns {FakeElement[]} Matching descendants in document order.
   */
  querySelectorAll(selector) {
    const parts = selector.trim().split(/\s+/);
    const last = parts.at(-1) ?? "*";
    const ancestors = parts.slice(0, -1);
    /** @type {FakeElement[]} */
    const found = [];
    /**
     * @param {FakeElement} element Candidate element.
     * @returns {boolean} Whether the ancestor chain matches.
     */
    const chain = element => {
      let index = ancestors.length - 1;
      for (
        let node = element.parentElement;
        node && index >= 0;
        node = node.parentElement
      ) {
        const ancestor = ancestors[index];
        if (ancestor !== undefined && node.matches(ancestor)) index -= 1;
      }
      return index < 0;
    };
    /** @param {FakeElement} node Subtree root. */
    const walk = node => {
      for (const child of node.children) {
        if (!(child instanceof FakeElement)) continue;
        if (child.matches(last) && chain(child)) found.push(child);
        walk(child);
      }
    };
    walk(this);
    return found;
  }

  /**
   * Find the first matching descendant.
   *
   * @param {string} selector Space-separated simple selectors.
   * @returns {FakeElement | null} First matching descendant.
   */
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }

  /**
   * @returns {{top: number, left: number, right: number, bottom: number,
   *   width: number, height: number, x: number, y: number}} Fixed box.
   */
  getBoundingClientRect() {
    return {
      top: 0,
      left: 0,
      right: 100,
      bottom: 20,
      width: 100,
      height: 20,
      x: 0,
      y: 0,
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

  /** Clear this element from the document's active element. */
  blur() {
    if (this.ownerDocument?.activeElement === this)
      this.ownerDocument.activeElement = null;
  }

  /** Dispatch a synthetic click. */
  click() {
    this.dispatchEvent(new Event("click"));
  }

  /** Accept programmatic scrolling requests. */
  scrollIntoView() {}

  /**
   * Register an event listener.
   *
   * @param {string} type Event type.
   * @param {(event: Event) => void} listener Event handler.
   */
  addEventListener(type, listener) {
    (this.listeners[type] ??= []).push(listener);
  }

  /**
   * Unregister an event listener.
   *
   * @param {string} type Event type.
   * @param {(event: Event) => void} listener Event handler.
   */
  removeEventListener(type, listener) {
    const list = this.listeners[type];
    if (list) {
      const index = list.indexOf(listener);
      if (index >= 0) list.splice(index, 1);
    }
  }

  /**
   * Dispatch an event through this element and its ancestors.
   *
   * @param {Event} event Event to dispatch through ancestor listeners.
   * @returns {boolean} Always true.
   */
  dispatchEvent(event) {
    if (!event.target)
      Object.defineProperty(event, "target", {
        value: this,
        configurable: true,
      });
    for (
      let node = /** @type {FakeElement | null} */ (this);
      node;
      node = node.parentElement
    )
      for (const listener of [...(node.listeners[event.type] ?? [])])
        listener.call(node, event);
    return true;
  }
}

/**
 * Build a fresh stub document.
 *
 * @returns {StubDocument} Document-shaped fake.
 */
export const createDocument = () => {
  /** @type {StubDocument} */
  const document = {
    createElement: tag => new FakeElement(tag, document),
    createElementNS: (_namespace, tag) => new FakeElement(tag, document),
    createTextNode: text => ({
      nodeType: 3,
      textContent: text,
      parentElement: null,
    }),
    querySelectorAll: () => [],
    activeElement: null,
    documentElement: new FakeElement("html"),
    body: new FakeElement("body"),
  };
  document.documentElement.ownerDocument = document;
  document.body.ownerDocument = document;
  return document;
};

/**
 * Install the stub document on globalThis.
 *
 * @returns {StubDocument} The installed document.
 */
export const installDom = () => {
  const document = createDocument();
  globalThis.document = /** @type {Document} */ (
    /** @type {unknown} */ (document)
  );
  globalThis.HTMLElement = /** @type {typeof HTMLElement} */ (
    /** @type {unknown} */ (FakeElement)
  );
  return document;
};

/**
 * Build a synthetic keydown event.
 *
 * @param {string} key Pressed key.
 * @param {Record<string, unknown>} [options] Extra event fields.
 * @returns {KeyboardEvent} Synthetic key event.
 */
export const keyEvent = (key, options = {}) =>
  /** @type {KeyboardEvent} */ (
    /** @type {unknown} */ (
      Object.assign(new Event("keydown", { bubbles: true }), {
        key,
        preventDefault: () => {},
        ...options,
      })
    )
  );

/**
 * Build a synthetic input event targeting an element.
 *
 * @param {FakeElement} target Event target.
 * @param {Record<string, unknown>} [options] Extra event fields.
 * @returns {Event} Synthetic input event.
 */
export const inputEvent = (target, options = {}) => {
  const event = Object.assign(new Event("input", { bubbles: true }), options);
  Object.defineProperty(event, "target", { value: target });
  return event;
};
