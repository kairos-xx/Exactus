/** Reusable saved-selector chooser with an inline-expression escape hatch. */
/** @typedef {{selector_id:string,name:string,expression:string}} SelectorChoice */
/** Populate and bind a selector choice field.
 * @param {object} options
 * @param {HTMLSelectElement} options.select Saved selector control.
 * @param {HTMLInputElement} options.inline Inline expression control.
 * @param {SelectorChoice[]} options.selectors Available saved selectors.
 * @param {string} [options.selected] Initially selected identifier.
 * @param {HTMLElement|null} [options.add] Optional create-selector button.
 * @param {()=>void} [options.onAdd] Opens the new-selector workflow.
 * @returns {()=>void} Refreshes inline visibility and the create action.
 */
export const bindSelectorReference = options => {
  options.select.replaceChildren(
    new Option("New expression", ""),
    ...options.selectors.map(
      selector => new Option(selector.name, selector.selector_id),
    ),
  );
  if (
    options.selected &&
    !options.selectors.some(selector => selector.selector_id === options.selected)
  )
    options.select.add(new Option("Missing selector", options.selected));
  options.select.value = options.selected ?? "";
  /** Hide the inline editor while a stored selector is chosen.
   * @returns {void}
   */
  const refresh = () => {
    const wrapper = options.inline.closest("label");
    if (wrapper instanceof HTMLElement)
      wrapper.hidden = Boolean(options.select.value);
    if (options.add) options.add.hidden = Boolean(options.select.value);
  };
  options.select.addEventListener("change", refresh);
  options.add?.addEventListener("click", () => options.onAdd?.());
  refresh();
  return refresh;
};
/** Resolve a chooser value to the selected expression or inline text.
 * @param {string} id
 * @param {string} inline
 * @param {SelectorChoice[]} selectors
 * @returns {string}
 */
export const selectorExpression = (id, inline, selectors) =>
  selectors.find(selector => selector.selector_id === id)?.expression ?? inline;
