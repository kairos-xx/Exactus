/** Execute the browser-side CSS analysis operation. */
() => {
  const styleElement = /** @type {HTMLStyleElement | null} */ (
    document.getElementById("__css_cause_style__")
  );
  const sheet = styleElement ? styleElement.sheet : null;
  if (!sheet) return JSON.stringify([]);
  /** @type {object[]} */
  const output = [];
  /** Traverse nested CSS rules.
   * @param {CSSRuleList} rules Rules to traverse.
   * @returns {void}
   */
  const walk = rules => {
    for (const rule of rules) {
      if (rule instanceof CSSStyleRule) {
        /** @type {string[]} */
        const matched = [];
        /** @type {Element[]} */
        const nodes = window.__cssCauseQueryAll(rule.selectorText);
        for (const node of nodes.slice(0, 16))
          matched.push(window.__cssCauseSelector(node));
        output.push({
          index: output.length,
          selector: rule.selectorText,
          cssText: rule.cssText,
          declarations: [...rule.style].map(
            name =>
              `${name}: ${rule.style.getPropertyValue(name).trim()}${
                rule.style.getPropertyPriority(name) ? " !important" : ""
              }`,
          ),
          matched,
        });
      } else if ("cssRules" in rule) {
        walk(/** @type {CSSRuleList} */ (rule.cssRules));
      }
    }
  };
  walk(sheet.cssRules);
  return JSON.stringify(output);
};
