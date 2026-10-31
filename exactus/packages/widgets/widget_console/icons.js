/** Inline SVG icons (one 24-unit grid, stroked), shared by the console and runner widgets. */
const SVG = "http://www.w3.org/2000/svg";
const PATHS = Object.freeze({
  braces: "M8 4c-2 0-3 1-3 3v2c0 1-1 2-2 3c1 1 2 2 2 3v2c0 2 1 3 3 3M16 4c2 0 3 1 3 3v2c0 1 1 2 2 3c-1 1-2 2-2 3v2c0 2-1 3-3 3",
  bug: "M9 9a3 3 0 0 1 6 0v6a3 3 0 0 1-6 0zM3 13h4M17 13h4M5 7l3 2M19 7l-3 2M5 19l3-2M19 19l-3-2",
  check: "M5 12l5 5L20 7",
  chevron: "M9 6l6 6l-6 6",
  clear: "M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18M5.6 5.6l12.8 12.8",
  clock: "M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18M12 7v5l3 2",
  close: "M6 6l12 12M18 6L6 18",
  copy: "M9 9h11v11H9zM5 15H4V4h11v1",
  error: "M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18M9 9l6 6M15 9l-6 6",
  info: "M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18M12 11v5M12 8h.01",
  play: "M7 5l12 7l-12 7z",
  search: "M11 4a7 7 0 1 0 0 14a7 7 0 0 0 0-14M20 20l-4-4",
  stop: "M7 7h10v10H7z",
  warn: "M12 4l9 16H3zM12 10v4M12 17h.01",
});
/** @typedef {keyof typeof PATHS} IconName */
/**
 * Build an inline SVG icon.
 * @param {IconName} name Icon name.
 * @returns {SVGSVGElement} The new SVG icon.
 */
export const icon = name => {
  const node = document.createElementNS(SVG, "svg");
  node.setAttribute("viewBox", "0 0 24 24");
  node.setAttribute("aria-hidden", "true");
  node.setAttribute("class", "jc-ico");
  const path = document.createElementNS(SVG, "path");
  path.setAttribute("d", PATHS[name]);
  node.append(path);
  return node;
};
