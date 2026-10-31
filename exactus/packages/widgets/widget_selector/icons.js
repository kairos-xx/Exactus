/** Inline SVG icons (one 24-unit grid, stroked). */
const SVG = "http://www.w3.org/2000/svg";
const PATHS = Object.freeze({
  expression: "M9 5H6v14h3M15 5h3v14h-3",
  text: "M5 7V5h14v2M12 5v14M9 19h6",
  crosshair: "M12 4v4M12 16v4M4 12h4M16 12h4M12 12h.01M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18",
  eye: "M2 12s4-7 10-7s10 7 10 7s-4 7-10 7S2 12 2 12M12 9a3 3 0 1 0 0 6a3 3 0 0 0 0-6",
  chevron: "M6 9l6 6l6-6",
  target: "M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0-8",
  visible: "M2 12s4-7 10-7s10 7 10 7s-4 7-10 7S2 12 2 12",
  view: "M4 4h16v16H4zM9 9h6v6H9z",
  clock: "M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18M12 7v5l3 2",
  check: "M5 12l5 5L20 7",
  scan: "M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4",
  devices: "M3 6h12v9H3zM17 9h4v9h-4z",
  enabled: "M4 12h16M4 7h16M4 17h10",
  close: "M6 6l12 12M18 6L6 18",
});
/**
 * Build an inline SVG icon.
 * @param {keyof typeof PATHS} name Icon name.
 * @param {boolean} [always] Whether the icon always renders.
 * @returns {SVGSVGElement} The new SVG icon.
 */
export const icon = (name, always = false) => {
  const node = document.createElementNS(SVG, "svg");
  node.setAttribute("viewBox", "0 0 24 24");
  node.setAttribute("aria-hidden", "true");
  node.setAttribute("class", "ese-ico");
  if (always) node.setAttribute("data-always", "");
  const path = document.createElementNS(SVG, "path");
  path.setAttribute("d", PATHS[name]);
  node.append(path);
  return node;
};
