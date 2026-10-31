import { iconElement } from "./icons.js";
/** The one Flows list: every place that shows saved flows renders it here. */
/**
 * @typedef {{id:string,name:string}} FlowItem
 */
/** Render saved flows as selectable rows, each with its own actions menu.
 * @param {HTMLElement} target Container that receives the rows.
 * @param {FlowItem[]} flows Saved flows in workspace order.
 * @param {string|null} selectedId Active flow identifier.
 * @param {(id:string)=>void} onSelect Called when a row is chosen.
 * @param {(id:string,anchor:HTMLElement)=>void} onMenu Called to open a row's actions.
 * @returns {void}
 */
export const renderFlowList = (target, flows, selectedId, onSelect, onMenu) => {
  target.replaceChildren(
    ...flows.map(flow => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "tree-item";
      button.classList.toggle("active", flow.id === selectedId);
      button.setAttribute("data-flow", flow.id);
      button.setAttribute("aria-pressed", String(flow.id === selectedId));
      const icon = iconElement("arrows-join");
      const name = document.createElement("span");
      name.textContent = flow.name;
      const more = document.createElement("span");
      more.className = "tree-item-more";
      more.setAttribute("role", "button");
      more.setAttribute("aria-haspopup", "menu");
      more.setAttribute("aria-label", `Actions for ${flow.name}`);
      more.tabIndex = 0;
      const dots = iconElement("dots");
      more.append(dots);
      more.addEventListener("click", click => {
        // The row would otherwise select the flow.
        click.preventDefault();
        click.stopPropagation();
        onMenu(flow.id, more);
      });
      more.addEventListener("keydown", key => {
        if (!["Enter", " ", "ContextMenu"].includes(key.key)) return;
        key.preventDefault();
        key.stopPropagation();
        onMenu(flow.id, more);
      });
      button.append(icon, name, more);
      button.addEventListener("click", () => onSelect(flow.id));
      return button;
    }),
  );
};
