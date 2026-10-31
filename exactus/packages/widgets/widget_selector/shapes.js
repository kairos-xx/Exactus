/** Pill shapes from the pills.svg design sheet at 20px: open, leaf, closing cap, slot. */
const SVG = "http://www.w3.org/2000/svg";
/** The shape's fixed measures, mirrored by the geometry tokens in CSS. */
export const SHAPE = Object.freeze({
  height: 20,
  radius: 10,
  horn: 5.8,
  cap: 15,
  gap: 3,
  descendantGap: 9,
});
/** Horns of an open shape: the concave notch is cut between them. */
export const HORN_PATH = "M0 0H5.8C3.5 2 0 5.7 0 10C0 14.3 2.4 18 5.8 20H0Z";
/** Closing cap: concave on the left, round on the right. */
export const CAP_PATH =
  "M5.3 0H0C3.3 2 5.6 5.7 5.6 10C5.6 14.3 3.4 18 0 20H5.3C10.6 20 15 15.5 15 10C15 4.5 10.7 0 5.3 0Z";
/** How two neighbours join.
 * @param {string|null} prev Previous item type: open, leaf, close, slot, glyph, descendant.
 * @param {string|null} next Next item type.
 * @returns {"flush"|"tight"|"descendant"}
 */
export const joinOf = (prev, next) => {
  if (prev === "descendant") return "descendant";
  if (prev === "open") return "flush";
  if (next === "close" && (prev === "leaf" || prev === "close" || prev === "slot"))
    return "flush";
  return "tight";
};
/**
 * Create an SVG node with one path.
 * @param {string} className SVG class list.
 * @param {string} viewBox View box.
 * @param {string} d Path data.
 * @returns {SVGSVGElement} The new SVG element.
 */
const svg = (className, viewBox, d) => {
  const node = document.createElementNS(SVG, "svg");
  node.setAttribute("class", className);
  node.setAttribute("viewBox", viewBox);
  node.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG, "path");
  path.setAttribute("d", d);
  node.append(path);
  return node;
};
/**
 * Build one shape.
 * @returns {HTMLElement} The shape element.
 */
export const buildShape = (/** @type {{type:"open"|"leaf"|"close"|"slot", kind:string, label?:string, editable?:boolean, title?:string}} */ { type, kind, label = "", editable = false, title = "" }) => {
  const shape = document.createElement("span");
  shape.className = "ese-shape";
  shape.setAttribute("data-type", type);
  shape.setAttribute("data-kind", kind);
  if (editable) shape.setAttribute("data-editable", "true");
  if (title) shape.title = title;
  if (type === "close") {
    shape.append(svg("ese-cap", "0 0 15 20", CAP_PATH));
    shape.setAttribute("aria-label", "end");
    return shape;
  }
  const body = document.createElement("span");
  body.className = "ese-body";
  body.textContent = label;
  shape.append(body);
  if (type === "open") shape.append(svg("ese-horn", "0 0 5.8 20", HORN_PATH));
  return shape;
};
