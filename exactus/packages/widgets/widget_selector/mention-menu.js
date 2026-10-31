/** A suggestion menu with expandable branches, like action_rest's `@` list. */
/** @typedef {import("./suggest.js").Item} Item */
/**
 * Create the suggestion menu bound to a host element.
 * @returns {{element:HTMLElement, isOpen:()=>boolean, open:Function, close:Function, key:Function}} The menu API.
 */
export const createMenu = (/** @type {{host:HTMLElement, onChoose:(item:Item)=>void}} */ { host, onChoose }) => {
  const root = document.createElement("div");
  root.className = "ese-menu";
  root.setAttribute("role", "listbox");
  root.hidden = true;
  host.append(root);
  /** @type {Item[]} */
  let items = [];
  let title = "";
  let index = 0;
  let navigated = false;
  const expanded = new Set();
  /**
   * Flatten items and expanded children into renderable rows.
   * @returns {{item:Item, depth:number}[]} Visible rows.
   */
  const rows = () =>
    items.flatMap(item => [
      { item, depth: 0 },
      ...(item.branch && expanded.has(item.label) ? (item.children ?? []).map(child => ({ item: child, depth: 1 })) : []),
    ]);
  /** Repaint the menu rows. */
  const paint = () => {
    root.replaceChildren();
    const heading = document.createElement("div");
    heading.className = "ese-menu-title";
    heading.textContent = title;
    root.append(heading);
    rows().forEach(({ item, depth }, position) => {
      const row = document.createElement("div");
      row.className = `ese-item${item.branch ? " ese-branch" : ""}`;
      row.setAttribute("role", "option");
      row.setAttribute("aria-selected", String(position === index));
      row.setAttribute("data-depth", String(depth));
      row.setAttribute("data-position", String(position));
      if (item.branch) row.setAttribute("aria-expanded", String(expanded.has(item.label)));
      const label = document.createElement("span");
      label.textContent = item.label;
      row.append(label);
      if (item.detail) {
        const detail = document.createElement("span");
        detail.className = "ese-item-detail";
        detail.textContent = item.detail;
        row.append(detail);
      }
      root.append(row);
    });
    root.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  };
  /** Hide the menu. */
  const close = () => {
    root.hidden = true;
    navigated = false;
  };
  /** Activate the current row: toggle a branch or emit the item. */
  const choose = () => {
    const row = rows()[index];
    if (!row) return;
    if (row.item.branch) {
      if (expanded.has(row.item.label)) expanded.delete(row.item.label);
      else expanded.add(row.item.label);
      paint();
      return;
    }
    close();
    onChoose(row.item);
  };
  root.addEventListener("mousedown", event => {
    const row = /** @type {HTMLElement} */ (event.target).closest(".ese-item");
    if (!(row instanceof HTMLElement)) return;
    event.preventDefault();
    index = Number(row.getAttribute("data-position"));
    choose();
  });
  return {
    element: root,
    isOpen: () => !root.hidden,
    /**
     * Open the menu with a title and items.
     * @param {string} heading Menu title.
     * @param {Item[]} list Items to show.
     * @param {string} [open] Branch to expand.
     */
    open: (heading, list, open = "") => {
      title = heading;
      items = list;
      index = 0;
      navigated = false;
      expanded.clear();
      for (const item of list.filter(i => i.branch && open.startsWith(i.label))) expanded.add(item.label);
      if (!list.length) {
        close();
        return;
      }
      root.hidden = false;
      paint();
    },
    close,
    /**
     * Handle menu keyboard navigation.
     * @param {KeyboardEvent} event Key event.
     * @returns {boolean} Whether the key was used.
     */
    key: event => {
      if (root.hidden) return false;
      const count = rows().length;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        index = (index + (event.key === "ArrowDown" ? 1 : count - 1)) % count;
        navigated = true;
        paint();
        return true;
      }
      if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
        const row = rows()[index];
        if (!row?.item.branch) return false;
        if (event.key === "ArrowRight") expanded.add(row.item.label);
        else expanded.delete(row.item.label);
        paint();
        return true;
      }
      if (event.key === "Enter" || event.key === "Tab") {
        if (!navigated && event.key === "Enter") return false;
        choose();
        return true;
      }
      if (event.key === "Escape") {
        close();
        return true;
      }
      return false;
    },
  };
};
