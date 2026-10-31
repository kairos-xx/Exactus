/** Execute the browser-side CSS analysis operation.
 * @param {Array<[number, string]>} items Flat rule index and property pairs.
 * @returns {boolean} True when the pass completed.
 */
/** @param {Array<[number, string]>} items @returns {boolean} True when done. */
items => {
  const styleElement = /** @type {HTMLStyleElement | null} */ (
    document.getElementById("__css_cause_style__")
  );
  const sheet = styleElement ? styleElement.sheet : null;
  if (!sheet) return false;
  /** @type {CSSStyleRule[]} */
  const flat = [];
  /** Traverse nested CSS rules.
   * @param {CSSRuleList} rules Rules to traverse.
   * @returns {void}
   */
  const walk = rules => {
    for (const rule of rules) {
      if (rule instanceof CSSStyleRule) flat.push(rule);
      else if ("cssRules" in rule)
        walk(/** @type {CSSRuleList} */ (rule.cssRules));
    }
  };
  walk(sheet.cssRules);
  for (const [ruleIndex, property] of items) {
    const rule = flat[ruleIndex];
    if (rule) rule.style.removeProperty(property);
  }
  return true;
};
