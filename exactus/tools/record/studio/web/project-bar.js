/** The top bar's project controls: name, saved state, actions and menus.
 *
 * The same actions sit in three places as room runs out. With room they are
 * labelled buttons. Less, they shrink to icons and the "Unsaved changes" pill
 * to a single LED. Least, they move into one "…" menu. The markup carries all
 * three; `fit()` measures the room that is really there (the project name and
 * the window both change it) and sets `data-tier` on the bar, the stylesheet
 * shows the matching one, and every control is wired once, by its `data-bar`
 * name.
 */
/** Room kept for the project name before the actions give up their labels. */
const NAME_ROOM = 150;
import { h, icon } from "./project-dialogs.js";
import { ago, recentProjects } from "./project-model.js";
/**
 * @typedef {object} MenuItem One line of a menu.
 * @property {string} label
 * @property {string} [icon]
 * @property {string} [hint] Quieter text at the right edge.
 * @property {boolean} [disabled]
 * @property {boolean} [heading] A group title, not a choice.
 * @property {() => unknown} [run]
 */
/** The top bar hosting the project menu. */
export class ProjectBar {
  /** @type {HTMLElement|null} */
  menu = null;
  /** @type {HTMLElement|null} */
  anchor = null;
  /**
   * @param {HTMLElement} root The top bar.
   * @param {import("./project-actions.js").ProjectActions} actions
   * @param {{commands:() => void, projectView:() => void}} host
   */
  constructor(root, actions, host) {
    this.root = root;
    this.actions = actions;
    this.host = host;
    root.addEventListener("click", event => {
      const target =
        event.target instanceof Element
          ? event.target.closest("[data-bar]")
          : null;
      if (!(target instanceof HTMLElement)) return;
      this.run(target.getAttribute("data-bar") ?? "", target);
    });
    document.addEventListener("pointerdown", event => {
      if (!this.menu || this.menu.contains(/** @type {Node} */ (event.target)))
        return;
      if (this.anchor?.contains(/** @type {Node} */ (event.target))) return;
      this.close(false);
    });
    window.addEventListener("resize", () => this.close(false));
    new ResizeObserver(() => this.fit()).observe(root);
    document.fonts?.ready.then(() => this.fit());
    this.fit();
  }
  /** Choose how much of the actions fits: labels, icons only, or the menu.
   * @returns {void}
   */
  fit() {
    const bar = this.root;
    const actions = bar.querySelector(".bar-actions");
    const brand = bar.querySelector(".brand");
    if (!(actions instanceof HTMLElement) || !(brand instanceof HTMLElement))
      return;
    const room = bar.clientWidth - brand.offsetWidth - NAME_ROOM;
    for (const tier of ["full", "icons"]) {
      bar.setAttribute("data-tier", tier);
      const gap = Number.parseFloat(getComputedStyle(actions).columnGap) || 0;
      const shown = [...actions.children].filter(
        item => item instanceof HTMLElement && item.offsetParent !== null,
      );
      const width =
        shown.reduce(
          (sum, item) => sum + item.getBoundingClientRect().width,
          0,
        ) +
        gap * Math.max(0, shown.length - 1) +
        16;
      if (width <= room) return;
    }
    bar.setAttribute("data-tier", "menu");
  }
  /** Do what a control asks for.
   * @param {string} name
   * @param {HTMLElement} anchor
   * @returns {void}
   */
  run(name, anchor) {
    const { actions } = this;
    switch (name) {
      case "new":
        actions.create();
        break;
      case "save":
        actions.save();
        break;
      case "open":
        actions.gallery();
        break;
      case "open-menu":
        this.toggle(anchor, this.openItems());
        break;
      case "export":
        actions.exportOpen();
        break;
      case "commands":
        this.host.commands();
        break;
      case "overflow":
        this.toggle(anchor, this.overflowItems());
        break;
      case "project":
        this.host.projectView();
        break;
      default:
        break;
    }
  }
  /** The recent projects as menu lines.
   * @returns {MenuItem[]}
   */
  recentItems() {
    const recent = recentProjects(this.actions.library());
    return recent.length
      ? recent.map(project => ({
          label: project.name,
          icon: "folder",
          hint:
            project.slug === this.actions.project()?.slug
              ? "Open now"
              : ago(project.modified_at),
          disabled: project.slug === this.actions.project()?.slug,
          run: () => this.actions.open(project.slug),
        }))
      : [{ label: "No recent projects", disabled: true }];
  }
  /** What the Open project arrow offers.
   * @returns {MenuItem[]}
   */
  openItems() {
    return [
      { label: "Recent projects", heading: true },
      ...this.recentItems(),
      {
        label: "Open project gallery…",
        icon: "folder-open",
        run: () => this.actions.gallery(),
      },
      {
        label: "Import from file…",
        icon: "upload",
        run: () => this.actions.importFile(true),
      },
      {
        label: "Open demo flow",
        icon: "world",
        run: () => this.actions.openDemo(),
      },
    ];
  }
  /** Everything, for the narrowest window.
   * @returns {MenuItem[]}
   */
  overflowItems() {
    return [
      { label: "New project", icon: "plus", run: () => this.actions.create() },
      {
        label: "Save project",
        icon: "device-floppy",
        run: () => this.actions.save(),
      },
      {
        label: "Open project gallery…",
        icon: "folder-open",
        run: () => this.actions.gallery(),
      },
      { label: "Recent projects", heading: true },
      ...this.recentItems(),
      {
        label: "Import from file…",
        icon: "upload",
        run: () => this.actions.importFile(true),
      },
      {
        label: "Open demo flow",
        icon: "world",
        run: () => this.actions.openDemo(),
      },
      {
        label: "Export project",
        icon: "download",
        run: () => this.actions.exportOpen(),
      },
      {
        label: "Commands",
        icon: "keyboard",
        hint: "⌘K",
        run: () => this.host.commands(),
      },
    ];
  }
  /** Open a menu under a control, or close it when it is already open there.
   * @param {HTMLElement} anchor
   * @param {MenuItem[]} items
   * @returns {void}
   */
  toggle(anchor, items) {
    const same = this.anchor === anchor && this.menu !== null;
    this.close(false);
    if (same) return;
    const menu = h("div", { class: "bar-menu", role: "menu" });
    for (const item of items) {
      if (item.heading) {
        menu.append(
          h("p", {
            class: "bar-menu-heading",
            role: "presentation",
            text: item.label,
          }),
        );
        continue;
      }
      const line = /** @type {HTMLButtonElement} */ (
        h(
          "button",
          { type: "button", role: "menuitem", class: "bar-menu-item" },
          [
            ...(item.icon
              ? [icon(item.icon)]
              : [h("span", { class: "bar-menu-gap", "aria-hidden": "true" })]),
            h("span", { class: "bar-menu-label", text: item.label }),
            ...(item.hint ? [h("small", { text: item.hint })] : []),
          ],
        )
      );
      line.disabled = Boolean(item.disabled);
      line.addEventListener("click", () => {
        this.close(true);
        item.run?.();
      });
      menu.append(line);
    }
    menu.addEventListener("keydown", event => {
      const lines = /** @type {HTMLElement[]} */ ([
        ...menu.querySelectorAll("button:not(:disabled)"),
      ]);
      const at = lines.indexOf(
        /** @type {HTMLElement} */ (document.activeElement),
      );
      if (event.key === "ArrowDown") lines[(at + 1) % lines.length]?.focus();
      else if (event.key === "ArrowUp")
        lines[(at - 1 + lines.length) % lines.length]?.focus();
      else if (event.key === "Home") lines[0]?.focus();
      else if (event.key === "End") lines.at(-1)?.focus();
      else if (event.key === "Escape") this.close(true);
      else if (event.key === "Tab") this.close(false);
      else return;
      event.preventDefault();
    });
    document.body.append(menu);
    const box = anchor.getBoundingClientRect();
    menu.style.top = `${box.bottom + 4}px`;
    menu.style.right = `${Math.max(8, window.innerWidth - box.right)}px`;
    anchor.setAttribute("aria-expanded", "true");
    this.menu = menu;
    this.anchor = anchor;
    menu
      .querySelector("button:not(:disabled)")
      ?.dispatchEvent(new Event("focus"));
    /** @type {HTMLElement|null} */ (
      menu.querySelector("button:not(:disabled)")
    )?.focus();
  }
  /** Close the open menu.
   * @param {boolean} refocus Whether focus goes back to the control.
   * @returns {void}
   */
  close(refocus) {
    this.menu?.remove();
    this.anchor?.setAttribute("aria-expanded", "false");
    if (refocus) this.anchor?.focus();
    this.menu = null;
    this.anchor = null;
  }
  /** Show the open project's name and whether it is saved.
   * @returns {void}
   */
  render() {
    const dirty = this.actions.dirty();
    const name = this.root.querySelector("#project-name");
    if (name) name.textContent = this.actions.name();
    const state = this.root.querySelector("#project-save-state");
    if (state instanceof HTMLElement) {
      state.setAttribute("data-state", dirty ? "dirty" : "saved");
      state.title = dirty
        ? "There are changes that are not saved"
        : "All changes are saved";
      const text = state.querySelector(".save-text");
      if (text) text.textContent = dirty ? "Unsaved changes" : "Saved";
    }
    document.title = `${dirty ? "● " : ""}${this.actions.name()} · Flow Studio`;
    // The name and the pill change the room the actions have.
    this.fit();
  }
}
