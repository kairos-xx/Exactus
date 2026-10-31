/** Execute the browser-side CSS analysis operation. */
() => {
  /** @type {object[]} */
  const result = [];
  /** Traverse nested CSS rules.
   * @param {CSSRuleList} rules Rules to traverse.
   * @param {string[]} parents Parent conditional-rule descriptions.
   * @returns {void}
   */
  const walk = (rules, parents = []) => {
    for (const rule of rules) {
      if (rule.constructor.name === "CSSContainerRule") {
        const containerRule =
          /** @type {CSSContainerRule & {name?: string}} */ (rule);
        const query = containerRule.conditionText || "";
        const name = containerRule.name || "";
        result.push({
          name,
          query,
          nested_rules: containerRule.cssRules.length,
          parents,
          condition_evaluation: "requires-container-context",
        });
        walk(containerRule.cssRules, [
          ...parents,
          `@container ${name} ${query}`,
        ]);
      } else if ("cssRules" in rule) {
        walk(/** @type {CSSRuleList} */ (rule.cssRules), parents);
      }
    }
  };
  for (const sheet of document.styleSheets) {
    try {
      walk(sheet.cssRules);
    } catch {
      // Cross-origin stylesheets throw SecurityError; skip them.
    }
  }
  return JSON.stringify(result);
};
