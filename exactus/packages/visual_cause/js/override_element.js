/** Execute the browser-side CSS analysis operation.
 * @param {[string, Record<string, string>]} args Selector and properties.
 * @returns {boolean} True when the element was found and overridden.
 */
/** @param {[string, Record<string, string>]} args @returns {boolean} True when the element was found. */
args => {
  const [selector, properties] = args;
  const element = /** @type {HTMLElement | null} */ (
    window.__cssCauseQuery(selector)
  );
  if (!element) return false;
  for (const [name, value] of Object.entries(properties))
    element.style.setProperty(name, value, "important");
  return true;
};
