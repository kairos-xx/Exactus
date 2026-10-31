/** Execute the browser-side CSS analysis operation.
 * @param {[number, string]} args Flat rule index and declaration property.
 * @returns {boolean} True when the declaration was removed.
 */
/** @param {[number, string]} args @returns {boolean} True when removed. */
args => {
  const [ruleIndex, property] = args;
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
  const rule = flat[ruleIndex];
  if (!rule) return false;
  rule.style.removeProperty(property);
  return true;
};
