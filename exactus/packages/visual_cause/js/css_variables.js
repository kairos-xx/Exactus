/** Execute the browser-side CSS analysis operation. */
() => {
  const varPattern = /var\(\s*(--[\w-]+)/g;
  /** @type {object[]} */
  const rows = [];
  let order = 0;
  /** Traverse nested CSS rules.
   * @param {CSSRuleList} rules Rules to traverse.
   * @param {string[]} conditions Active conditional-rule descriptions.
   * @returns {void}
   */
  const walk = (rules, conditions = []) => {
    for (const rule of rules) {
      if (rule instanceof CSSStyleRule) {
        const matches = window
          .__cssCauseQueryAll(rule.selectorText)
          .slice(0, 64)
          .map(node => window.__cssCauseSelector(node));
        for (const property of rule.style) {
          const value = rule.style.getPropertyValue(property).trim();
          /** @type {string[]} */
          const refs = [];
          for (const match of value.matchAll(varPattern)) {
            const group = match[1];
            if (group !== undefined) refs.push(group);
          }
          if (property.startsWith("--") || refs.length)
            rows.push({
              order: order++,
              selector: rule.selectorText,
              property,
              value,
              important:
                rule.style.getPropertyPriority(property) === "important",
              references: refs,
              defines: property.startsWith("--") ? property : null,
              matches,
              conditions,
            });
        }
      } else if ("cssRules" in rule) {
        const conditional =
          /** @type {{conditionText?: string; media?: {mediaText?: string}; name?: string}} */ (
            rule
          );
        const label =
          conditional.conditionText ||
          conditional.media?.mediaText ||
          conditional.name ||
          "";
        walk(
          /** @type {CSSRuleList} */ (rule.cssRules),
          label ? [...conditions, label] : conditions,
        );
      }
    }
  };
  for (const sheet of [...document.styleSheets]) {
    try {
      walk(sheet.cssRules);
    } catch {
      // Cross-origin stylesheets throw SecurityError; skip them.
    }
  }
  return JSON.stringify(rows);
};
