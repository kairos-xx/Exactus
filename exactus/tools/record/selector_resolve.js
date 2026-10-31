/**
 * Resolve one ExtendedSelector expression inside the engine's isolated world.
 *
 * Evaluated as a function expression and called with one argument:
 * `{expression, definitions, checks, compile}`. It returns plain JSON.
 */
/**
 * @param {ResolveArgs} args
 * @returns {ResolveResult}
 */
args => {
  const Engine = /** @type {any} */ (globalThis).__EXACTUS_ES__;
  const engine = new Engine(document, { deep: true });
  /** @type {ResolveResult} */
  const out = { count: 0, matches: [], error: null, definitionErrors: [] };
  /** First line of an error message.
   * @param {unknown} error Caught value.
   * @returns {string}
   */
  const firstLine = error =>
    String(/** @type {Error} */ (error).message).split("\n")[0] ?? "";
  for (const [name, expression] of Object.entries(args.definitions))
    try {
      engine.define(name, expression);
    } catch (error) {
      out.definitionErrors.push(`${name}: ${firstLine(error)}`);
    }
  /** @type {HTMLElement[]} */
  let elements;
  try {
    elements = engine.query(args.expression);
  } catch (error) {
    out.error = firstLine(error);
    return out;
  }
  out.count = elements.length;
  const attributes = [
    "id",
    "class",
    "name",
    "type",
    "href",
    "data-testid",
    "aria-label",
  ];
  elements.forEach((element, index) => {
    const box = element.getBoundingClientRect();
    const text = element.innerText ?? element.textContent ?? "";
    /** @type {ResolveMatch} */
    const match = {
      index,
      css: null,
      cssError: null,
      rect: { x: box.x, y: box.y, width: box.width, height: box.height },
      evidence: {
        tag: element.localName,
        role: engine.predicateValue(element, "role"),
        text: text.trim().slice(0, 200),
        visible: engine.predicateValue(element, "visible") === "true",
        enabled: engine.predicateValue(element, "enabled") === "true",
        attributes: Object.fromEntries(
          attributes
            .filter(name => element.hasAttribute(name))
            .map(name => [name, element.getAttribute(name)]),
        ),
      },
      failed: [],
    };
    if (args.compile)
      try {
        match.css = engine.bestSelector(element, {
          engines: ["native"],
          deep: true,
          includeCandidates: false,
        }).selector;
      } catch (error) {
        match.cssError = firstLine(error);
      }
    for (const check of args.checks)
      try {
        if (!engine.matches(element, check)) match.failed.push(check);
      } catch (error) {
        match.failed.push(`${check} (${firstLine(error)})`);
      }
    out.matches.push(match);
  });
  return out;
};
