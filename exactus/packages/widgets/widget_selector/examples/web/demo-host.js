/**
 * Demo host: implements pick, highlight and stats against the demo page itself.
 * @returns {{stats:Function, pick:Function, highlight:Function}} The demo host API.
 */
export const createDemoHost = (/** @type {{engine:any, stage:HTMLElement, layer:HTMLElement}} */ { engine, stage, layer }) => {
  /**
   * Count matches for a selector, tolerating engine errors.
   * @param {string} value Selector text.
   * @returns {number} Match count.
   */
  const safeCount = value => {
    try {
      return engine.query(value).length;
    } catch {
      return 0;
    }
  };
  /**
   * Build ranked selector alternatives for a picked element.
   * @param {Element} element Picked element.
   * @returns {{strategy:string, selector:string, matches:number}[]} Candidate selectors.
   */
  const alternatives = element => {
    const tag = element.tagName.toLowerCase();
    const classes = [...element.classList];
    const text = (/** @type {HTMLElement} */ (element).innerText ?? "").trim().replace(/\s+/g, " ").slice(0, 24);
    const candidates = [
      ...(element.id ? [{ strategy: "id", selector: `#${element.id}` }] : []),
      ...(classes.length ? [{ strategy: "class", selector: `${tag}.${classes.join(".")}` }] : []),
      ...(text ? [{ strategy: "text", selector: `${tag}[innerText*="${text}"]` }] : []),
      { strategy: "tag", selector: tag },
      ...(element.parentElement?.classList.length ? [{ strategy: "in parent", selector: `has(.${element.parentElement.classList[0]}, ${tag}${classes.length ? `.${classes[0]}` : ""})` }] : []),
    ];
    return candidates.map(c => ({ ...c, matches: safeCount(c.selector) }));
  };
  return {
    /** @param {string} value */
    stats: async value => engine.stats(value, { root: stage }),
    /** @param {(picked:object)=>void} apply */
    pick: apply => {
      document.body.setAttribute("data-picking", "true");
      /**
       * Handle the pick click inside the stage.
       * @param {MouseEvent} event Click event.
       */
      const onClick = event => {
        event.preventDefault();
        event.stopPropagation();
        document.removeEventListener("click", onClick, true);
        document.body.removeAttribute("data-picking");
        const element = /** @type {Element} */ (event.target);
        if (!stage.contains(element)) return;
        const alts = alternatives(element);
        apply({
          selector: alts.find(a => a.matches === 1)?.selector ?? alts[0]?.selector ?? element.tagName.toLowerCase(),
          alternatives: alts,
          element: { tag: element.tagName.toLowerCase(), className: element.className, text: (/** @type {HTMLElement} */ (element).innerText ?? "").trim().slice(0, 28) },
        });
      };
      document.addEventListener("click", onClick, true);
    },
    /** @param {string} value @param {(r:{count?:number})=>void} done */
    highlight: (value, done) => {
      layer.replaceChildren();
      if (!value) {
        done({ count: 0 });
        return;
      }
      const found = (() => {
        try {
          return /** @type {Element[]} */ (engine.query(value, { root: stage }));
        } catch {
          return /** @type {Element[]} */ ([]);
        }
      })();
      const origin = stage.getBoundingClientRect();
      for (const element of found) {
        const rect = element.getBoundingClientRect();
        if (!rect.width || !rect.height) continue;
        const box = document.createElement("div");
        box.className = "hl";
        box.style.setProperty("--dynamic-esd-hl-x", `${rect.left - origin.left}px`);
        box.style.setProperty("--dynamic-esd-hl-y", `${rect.top - origin.top}px`);
        box.style.setProperty("--dynamic-esd-hl-w", `${rect.width}px`);
        box.style.setProperty("--dynamic-esd-hl-h", `${rect.height}px`);
        layer.append(box);
      }
      done({ count: found.length });
    },
  };
};
