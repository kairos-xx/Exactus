() => {
  /** Serialize a Typed OM value.
   * @param {*} value Typed OM value.
   * @returns {*} JSON-compatible value.
   */
  const serializeTyped = value => {
    const base = {
      type: value?.constructor?.name || typeof value,
      text: String(value),
    };
    if (value instanceof CSSUnitValue)
      return {
        ...base,
        value: value.value,
        unit: value.unit,
      };
    if (
      typeof CSSKeywordValue !== "undefined" &&
      value instanceof CSSKeywordValue
    )
      return {
        ...base,
        value: value.value,
      };
    if (
      typeof CSSUnparsedValue !== "undefined" &&
      value instanceof CSSUnparsedValue
    )
      return {
        ...base,
        unparsed: [...value].map(part =>
          typeof part === "string"
            ? {
                type: "string",
                text: part,
              }
            : serializeTyped(part),
        ),
      };
    if (
      typeof CSSTransformValue !== "undefined" &&
      value instanceof CSSTransformValue
    )
      return {
        ...base,
        components: [...value].map(component => ({
          type: component.constructor?.name || "CSSTransformComponent",
          text: String(component),
          is2D: component.is2D,
        })),
      };
    if (value && typeof value === "object" && Symbol.iterator in value) {
      try {
        return {
          ...base,
          items: [...value].map(serializeTyped),
        };
      } catch {
        // Iterating a non-list Typed OM value throws; keep the base form.
      }
    }
    return base;
  };
  /** @type {object[]} */
  const output = [];
  /** Traverse rendered DOM and shadow DOM.
   * @param {ParentNode} root Root node to traverse.
   * @param {string} prefix Selector prefix.
   * @param {string} parentPath Parent selector path.
   * @returns {void}
   */
  const walk = (root, prefix, parentPath) => {
    const children =
      root instanceof ShadowRoot ? [...root.children] : [...root.children];
    children.forEach((node, index) => {
      const segment = `${node.localName}[${index}]`;
      const path = prefix ? `${prefix}/${segment}` : segment;
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      if (
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden"
      )
        output.push({
          selector: window.__cssCauseSelector(node),
          domPath: path,
          parentPath,
          tag: node.localName,
          text: (node.textContent || "")
            .replace(/\s+/g, " ")
            .trim()
            .slice(0, 240),
          ownText: [...node.childNodes]
            .filter(child => child.nodeType === Node.TEXT_NODE)
            .map(child => child.textContent || "")
            .join(" ")
            .replace(/\s+/g, " ")
            .trim()
            .slice(0, 240),
          x: rect.x + scrollX,
          y: rect.y + scrollY,
          width: rect.width,
          height: rect.height,
          position: style.position,
          zIndex: style.zIndex,
          computed: Object.fromEntries(
            [...style].map(name => [name, style.getPropertyValue(name)]),
          ),
          typedComputed: (() => {
            if (!node.computedStyleMap) return {};
            const map = node.computedStyleMap();
            return Object.fromEntries(
              [...map].map(([name, values]) => [
                name,
                Array.isArray(values)
                  ? values.map(serializeTyped)
                  : serializeTyped(values),
              ]),
            );
          })(),
          beforeContent: getComputedStyle(node, "::before").content,
          afterContent: getComputedStyle(node, "::after").content,
          childCount: node.childNodes.length,
          scrollWidth: node.scrollWidth,
          scrollHeight: node.scrollHeight,
          clientWidth: node.clientWidth,
          clientHeight: node.clientHeight,
          overflowX: style.overflowX,
          overflowY: style.overflowY,
        });
      walk(node, path, path);
      if (node.shadowRoot) walk(node.shadowRoot, `${path}/#shadow-root`, path);
    });
  };
  walk(document.documentElement, "html-root", "");
  return JSON.stringify(output);
};
