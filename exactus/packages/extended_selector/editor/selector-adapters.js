import { getCssSelector } from "css-selector-generator";
import * as optimalModule from "optimal-select";
import { finder } from "@medv/finder";
const optimal = optimalModule.default ?? optimalModule;
/** Inject locally installed selector generators into ExtendedSelector.
 * @param {import("./extended-selector.js").ExtendedSelector} engine
 * @param {Element | Element[]} targets
 * @param {import("./extended-selector.js").GeneratorOptions} [options]
 * @returns {import("./extended-selector.js").BestSelectorResult}
 */
export const bestLocalSelector = (engine, targets, options = {}) =>
  engine.bestSelector(targets, {
    ...options,
    generator: (elements, settings) => getCssSelector(elements, settings),
    optimal: {
      getSingleSelector: element => optimal.getSingleSelector(element),
      getMultiSelector: elements => optimal.getMultiSelector(elements),
      optimize: selector =>
        optimal.optimize(
          selector,
          Array.isArray(targets) ? targets : [targets],
        ),
    },
    finder: (element, settings) => {
      const root = settings?.root ?? element.ownerDocument;
      return finder(element, {
        root:
          root.nodeType === Node.DOCUMENT_NODE
            ? /** @type {Document} */ (root).body
            : /** @type {Element} */ (root),
      });
    },
  });
