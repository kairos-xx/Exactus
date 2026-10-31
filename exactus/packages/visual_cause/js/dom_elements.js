/**
 * @param {Element[]} elements Candidate DOM elements.
 * @returns {string} Serialized visible-element geometry.
 */
elements => {
  /**
   * Escape a fragment for use inside a CSS selector.
   * @param {string} value Selector fragment.
   * @returns {string} Escaped selector fragment.
   */
  const escape = value => CSS.escape(value);
  /**
   * Build a stable human-readable selector for an element.
   * @param {Element} node Element to identify.
   * @returns {string} Stable human-readable selector.
   */
  const selector = node => {
    if (node.id) return `#${escape(node.id)}`;
    /** @type {string[]} */
    const parts = [];
    /** @type {Element | null} */
    let current = node;
    while (
      current &&
      current.nodeType === Node.ELEMENT_NODE &&
      current !== document.documentElement
    ) {
      const localName = current.localName;
      let part = localName;
      if (current.classList.length)
        part += `.${[...current.classList].slice(0, 3).map(escape).join(".")}`;
      if (current.parentElement) {
        let siblingIndex = 0;
        let siblingCount = 0;
        for (const sibling of [...current.parentElement.children]) {
          if (sibling.localName !== localName) continue;
          siblingCount += 1;
          if (sibling === current) siblingIndex = siblingCount;
        }
        if (siblingCount > 1) part += `:nth-of-type(${siblingIndex})`;
      }
      parts.unshift(part);
      current = current.parentElement;
    }
    return parts.join(" > ");
  };
  return JSON.stringify(
    elements.flatMap(element => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      if (
        rect.width <= 0 ||
        rect.height <= 0 ||
        style.visibility === "hidden" ||
        style.display === "none"
      )
        return [];
      return [
        {
          selector: selector(element),
          tag: element.localName,
          element_id: element.id,
          classes: [...element.classList].join(" "),
          text: (
            (element instanceof HTMLElement ? element.innerText : null) ||
            element.textContent ||
            ""
          )
            .replace(/\s+/g, " ")
            .trim()
            .slice(0, 160),
          x: rect.x + scrollX,
          y: rect.y + scrollY,
          width: rect.width,
          height: rect.height,
        },
      ];
    }),
  );
};
