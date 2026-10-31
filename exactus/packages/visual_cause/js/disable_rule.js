/** Execute the browser-side CSS analysis operation.
 * @param {number} index Flat index of the style rule to empty.
 * @returns {void}
 */
/** @param {number} index @returns {void} */
index => {
  const styleElement = /** @type {HTMLStyleElement | null} */ (
    document.getElementById("__css_cause_style__")
  );
  const sheet = styleElement ? styleElement.sheet : null;
  if (!sheet) return;
  let current = 0;
  /** Traverse nested CSS rules.
   * @param {CSSRuleList} rules Rules to traverse.
   * @returns {boolean} True when the target rule was disabled.
   */
  const walk = rules => {
    for (const rule of rules) {
      if (rule instanceof CSSStyleRule) {
        if (current === index) {
          for (const name of [...rule.style]) rule.style.removeProperty(name);
          return true;
        }
        current += 1;
      } else if (
        "cssRules" in rule &&
        walk(/** @type {CSSRuleList} */ (rule.cssRules))
      )
        return true;
    }
    return false;
  };
  walk(sheet.cssRules);
};
