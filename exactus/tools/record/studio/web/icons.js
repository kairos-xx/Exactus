/** Icons as real `<svg>` elements.
 *
 * Every icon is an `<svg viewBox="0 0 24 24">` with no width or height of its
 * own, so CSS sizes it with `--studio-icon-size` and it follows `currentColor`
 * for hover and pressed states. The shapes come from `icon-set.js`, generated
 * from the files in `icons/`.
 *
 * `watchIcons()` also tells the stylesheet what each button holds, by setting
 * `data-kind` to "icon" (an icon and nothing else) or "icon-text" (an icon and
 * a label). CSS cannot see bare text nodes, so this is read from the DOM.
 *
 * Markup can ask for an icon by writing an empty
 * `<svg class="studio-icon" data-icon="name">`; `watchIcons()` fills it in as
 * it enters the page and again whenever its `data-icon` changes, so code that
 * swaps an icon only has to change that attribute.
 */
import { ICONS } from "./icon-set.js";
const SVG_NS = "http://www.w3.org/2000/svg";
const SELECTOR = "svg.studio-icon[data-icon]";
/** What each painted icon currently shows, so a repaint happens only on change.
 * @type {WeakMap<Element,string>}
 */
const painted = new WeakMap();
/** The markup of an icon, for code that builds HTML as text.
 * @param {string} name An icon in `icons/`.
 * @param {string} [className] Extra classes beside `studio-icon`.
 * @returns {string}
 */
export const iconMarkup = (name, className = "") =>
  `<svg class="studio-icon${className ? ` ${className}` : ""}" data-icon="${name}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICONS[name] ?? ""}</svg>`;
/** Fill an icon shell with the shapes of the icon it names.
 * @param {Element} svg
 * @returns {void}
 */
export const paintIcon = svg => {
  const name = svg.getAttribute("data-icon") ?? "";
  if (painted.get(svg) === name) return;
  painted.set(svg, name);
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.innerHTML = ICONS[name] ?? "";
};
/** A new icon element.
 * @param {string} name An icon in `icons/`.
 * @param {string} [className] Extra classes beside `studio-icon`.
 * @returns {SVGSVGElement}
 */
export const iconElement = (name, className = "") => {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", `studio-icon${className ? ` ${className}` : ""}`);
  svg.setAttribute("data-icon", name);
  paintIcon(svg);
  return svg;
};
/** What a button holds: an icon alone, an icon and text, or neither.
 * @param {Element} button
 * @returns {"icon"|"icon-text"|""}
 */
export const kindOf = button => {
  if (!button.querySelector(":scope > svg.studio-icon")) return "";
  const labelled = [...button.childNodes].some(node =>
    node instanceof Element
      ? !node.matches("svg.studio-icon, .sr-only") &&
        Boolean(node.textContent?.trim())
      : node.nodeType === Node.TEXT_NODE && Boolean(node.textContent?.trim()),
  );
  return labelled ? "icon-text" : "icon";
};
/** Record what a button holds, so CSS can style icon-only and icon-and-text apart.
 * @param {Element} button
 * @returns {void}
 */
const classify = button => {
  const kind = kindOf(button);
  if (kind && button.getAttribute("data-kind") !== kind)
    button.setAttribute("data-kind", kind);
  else if (!kind && button.hasAttribute("data-kind"))
    button.removeAttribute("data-kind");
};
/** Classify every button under a node, the node itself included.
 * @param {ParentNode|Element} root
 * @returns {void}
 */
const classifyWithin = root => {
  if (root instanceof Element && root.matches("button")) classify(root);
  root.querySelectorAll?.("button").forEach(classify);
};
/** Paint every icon shell under a node, the node itself included.
 * @param {ParentNode|Element} root
 * @returns {void}
 */
const paintWithin = root => {
  if (root instanceof Element && root.matches(SELECTOR)) paintIcon(root);
  root.querySelectorAll?.(SELECTOR).forEach(paintIcon);
};
/** Re-read the button that holds a node, after something inside it changed.
 * @param {Node|null} node
 * @returns {void}
 */
const reclassify = node => {
  const holder = node instanceof Element ? node : node?.parentElement;
  const button = holder?.closest("button");
  if (button) classify(button);
};
/** Keep icon shells painted and buttons classified: now, as nodes are added or
 * their text changes, and when `data-icon` changes.
 * @param {Document} [root]
 * @returns {void}
 */
export const watchIcons = (root = document) => {
  paintWithin(root);
  classifyWithin(root);
  new MutationObserver(records => {
    for (const record of records) {
      if (record.type === "attributes")
        paintWithin(record.target.parentNode ?? root);
      else if (record.type === "characterData") reclassify(record.target);
      else {
        reclassify(record.target);
        record.addedNodes.forEach(node => {
          if (node instanceof Element) {
            paintWithin(node);
            classifyWithin(node);
          }
        });
      }
    }
  }).observe(root, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["data-icon"],
  });
};
