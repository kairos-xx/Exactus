/** Ambient browser globals for the visual-cause page scripts.
 *
 * `install_helpers.js` installs `window.__cssCauseSelector` and the
 * `__cssCauseQuery(All)` selector helpers before the other evaluated helpers
 * run, so every script can rely on them.
 */

/** Subset of the packaged ExtendedSelector engine used by the page scripts. */
interface CssCauseExtendedEngine {
  /** Resolve one standard or extended selector to matching elements. */
  query(expression: string): Element[];
}

interface Window {
  /** Build a readable CSS selector path for one element. */
  __cssCauseSelector(element: Element): string;
  /** Query every element matching a standard or extended CSS selector. */
  __cssCauseQueryAll(selector: string): Element[];
  /** Query the first element matching a standard or extended CSS selector. */
  __cssCauseQuery(selector: string): Element | null;
  /** Lazily created shared ExtendedSelector engine instance. */
  __cssCauseExtended?: CssCauseExtendedEngine;
  /** Vendored extended-selector engine constructor, when installed. */
  ExtendedSelector?: new (
    root: Document | Element,
  ) => CssCauseExtendedEngine;
}
