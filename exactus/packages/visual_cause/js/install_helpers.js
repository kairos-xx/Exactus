() => {
  window.__cssCauseSelector = element => {
    if (element.id) return `#${CSS.escape(element.id)}`;
    /** @type {string[]} */
    const parts = [];
    /** @type {Element | null} */
    let node = element;
    while (node && node.nodeType === Node.ELEMENT_NODE && parts.length < 8) {
      const current = /** @type {Element} */ (node);
      let part = current.localName;
      if (current.classList.length)
        part += [...current.classList]
          .slice(0, 3)
          .map(name => `.${CSS.escape(name)}`)
          .join("");
      if (current.parentElement) {
        const same = [...current.parentElement.children].filter(
          child => child.localName === current.localName,
        );
        if (same.length > 1)
          part += `:nth-of-type(${same.indexOf(current) + 1})`;
      }
      parts.unshift(part);
      node = current.parentElement;
    }
    return parts.join(" > ");
  };
  /** Query every element matching a standard or extended CSS selector.
   * Native `querySelectorAll` runs first; when it rejects extended selector
   * syntax the packaged `ExtendedSelector` engine resolves the query instead.
   * @param {string} selector Selector text to resolve.
   * @returns {Element[]} Matching elements.
   */
  window.__cssCauseQueryAll = selector => {
    try {
      return [...document.querySelectorAll(selector)];
    } catch {
      // Extended selector syntax falls through to the packaged engine.
    }
    const Engine = window.ExtendedSelector;
    if (Engine === undefined) return [];
    try {
      window.__cssCauseExtended ??= new Engine(document);
      const engine = /** @type {CssCauseExtendedEngine} */ (
        window.__cssCauseExtended
      );
      return [...engine.query(selector)];
    } catch {
      return [];
    }
  };
  /** Query the first element matching a standard or extended CSS selector.
   * @param {string} selector Selector text to resolve.
   * @returns {Element | null} First matching element, when present.
   */
  window.__cssCauseQuery = selector =>
    window.__cssCauseQueryAll(selector)[0] ?? null;
  return "ok";
};
