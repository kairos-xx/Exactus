import { iconElement } from "./icons.js";
/** The project dialogs: new project, ask for a name, unsaved changes, and the gallery.
 *
 * Each one is a native `<dialog>` opened with `showModal()`, so focus is
 * trapped, Escape closes it and the page behind is inert. Focus returns to the
 * control that opened it. Rules about names, tags and filtering come from
 * `project-model.js`, shared with the Project tab.
 */
import {
  ago,
  emptyFilter,
  filterProjects,
  isFiltered,
  nameIssue,
  parseTags,
  recentProjects,
  when,
} from "./project-model.js";
/**
 * @typedef {object} DialogHost What the dialogs need from the editor.
 * @property {() => LibraryData} library The projects, kept current by the editor.
 * @property {() => ProjectState|null} project The project that is open now.
 */
/**
 * @typedef {object} GalleryActions What the gallery asks the editor to do.
 * @property {(slug:string) => Promise<void>} open Open a project.
 * @property {(slug:string, name:string) => Promise<void>} duplicate Copy a project.
 * @property {(slug:string) => Promise<void>} remove Delete a project.
 * @property {() => Promise<void>} importFile Add a project from a file.
 * @property {() => Promise<void>} create Start the new-project dialog.
 * @property {(slug:string) => string} exportUrl Where a project downloads from.
 */
/** Build an element with attributes and children.
 * @param {string} tag
 * @param {Record<string,string|boolean>} [attributes] `class`, text under `text`, anything else as an attribute.
 * @param {(Node|string)[]} [children]
 * @returns {HTMLElement}
 */
export const h = (tag, attributes = {}, children = []) => {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (key === "text") node.textContent = String(value);
    else if (key === "class") node.className = String(value);
    else if (value === true) node.setAttribute(key, "");
    else if (value !== false) node.setAttribute(key, String(value));
  }
  node.append(...children);
  return node;
};
/** A decorative icon from the Studio's icon set.
 * @param {string} name
 * @returns {SVGSVGElement}
 */
export const icon = name => iconElement(name);
/** A button.
 * @param {string} label
 * @param {Record<string,string|boolean>} [attributes]
 * @param {string} [iconName]
 * @returns {HTMLButtonElement}
 */
const button = (label, attributes = {}, iconName = "") =>
  /** @type {HTMLButtonElement} */ (
    h("button", { type: "button", ...attributes }, [
      ...(iconName ? [icon(iconName)] : []),
      h("span", { text: label }),
    ])
  );
/** A labelled field.
 * @param {string} label
 * @param {HTMLElement} control
 * @param {string} [help]
 * @returns {HTMLElement}
 */
const field = (label, control, help = "") =>
  h("label", { class: "pd-field" }, [
    h("span", { class: "pd-label", text: label }),
    control,
    ...(help ? [h("small", { class: "pd-help", text: help })] : []),
  ]);
/** A native modal that removes itself and returns focus when it closes.
 * @param {string} className
 * @param {string} title Accessible name of the dialog.
 * @returns {{dialog:HTMLDialogElement,done:Promise<void>}}
 */
const modal = (className, title) => {
  const trigger = document.activeElement;
  const dialog = /** @type {HTMLDialogElement} */ (
    h("dialog", { class: `project-dialog ${className}`, "aria-label": title })
  );
  /** Resolves `done` when the dialog closes.
   * @type {() => void}
   */
  let finish = () => undefined;
  const done = new Promise(resolve => {
    finish = () => resolve(undefined);
  });
  dialog.addEventListener("close", () => {
    dialog.remove();
    if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus();
    finish();
  });
  document.body.append(dialog);
  return { dialog, done };
};
/** The open-and-wait part shared by the small dialogs.
 * @param {HTMLDialogElement} dialog
 * @returns {void}
 */
const show = dialog => {
  dialog.showModal();
  const first = dialog.querySelector("[autofocus], input, textarea, button");
  if (first instanceof HTMLElement) first.focus();
};
/** Modal dialogs for project-level actions. */
export class ProjectDialogs {
  /** @type {(() => void)|null} Redraws the gallery while it is open. */
  refreshGallery = null;
  /** @param {DialogHost} host */
  constructor(host) {
    this.host = host;
  }
  /** Ask for the details of a new project. The name is required and unique.
   * @param {(details:Record<string,unknown>) => Promise<boolean|void>} create Makes the project; throws a readable error when it cannot, or returns false to keep the dialog open.
   * @returns {Promise<void>} Settles when the dialog closes.
   */
  async newProject(create) {
    const { dialog, done } = modal("new-project", "New project");
    const name = /** @type {HTMLInputElement} */ (
      h("input", {
        name: "name",
        required: true,
        maxlength: "80",
        autocomplete: "off",
        spellcheck: "false",
        autofocus: true,
      })
    );
    const nameHelp = h("small", { class: "pd-help pd-issue", role: "status" });
    const base = /** @type {HTMLInputElement} */ (
      h("input", {
        name: "base_url",
        placeholder: "https://localhost:3000",
        autocomplete: "off",
        spellcheck: "false",
        inputmode: "url",
      })
    );
    const description = /** @type {HTMLTextAreaElement} */ (
      h("textarea", { name: "description", rows: "2" })
    );
    const tags = /** @type {HTMLInputElement} */ (
      h("input", {
        name: "tags",
        placeholder: "web, smoke",
        autocomplete: "off",
      })
    );
    const author = h("input", {
      name: "author",
      maxlength: "80",
      autocomplete: "name",
    });
    const version = h("input", {
      name: "version",
      maxlength: "80",
      placeholder: "0.1.0",
      autocomplete: "off",
    });
    const error = h("p", { class: "pd-error", role: "alert" });
    const create_ = /** @type {HTMLButtonElement} */ (
      h("button", { type: "submit", class: "accent", disabled: true }, [
        h("span", { text: "Create project" }),
      ])
    );
    const cancel = button("Cancel");
    cancel.addEventListener("click", () => dialog.close());
    const form = /** @type {HTMLFormElement} */ (
      h("form", { class: "pd-form", novalidate: true }, [
        h("header", { class: "pd-header" }, [
          h("div", {}, [
            h("h2", { text: "New project" }),
            h("p", {
              class: "pd-sub",
              text: "A project keeps its own flows, selectors and results in a folder of its own.",
            }),
          ]),
        ]),
        h("div", { class: "pd-scroll" }, [
          h("div", { class: "pd-group" }, [
            field("Project name", name, ""),
            nameHelp,
            field(
              "Base URL",
              base,
              "Where the tests start when a flow has no Navigate action.",
            ),
          ]),
          h("fieldset", { class: "pd-group" }, [
            h("legend", { text: "Details, all optional" }),
            field("Description", description),
            field("Tags", tags, "Separate tags with commas."),
            h("div", { class: "pd-pair" }, [
              field("Author", author),
              field("Version", version),
            ]),
          ]),
        ]),
        error,
        h("footer", { class: "pd-actions" }, [cancel, create_]),
      ])
    );
    const check = () => {
      const issue = name.value
        ? nameIssue(name.value, this.host.library().projects)
        : "";
      nameHelp.textContent = issue;
      name.toggleAttribute("aria-invalid", Boolean(issue));
      create_.disabled = Boolean(
        nameIssue(name.value, this.host.library().projects),
      );
    };
    name.addEventListener("input", check);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      check();
      if (create_.disabled) {
        name.focus();
        return;
      }
      create_.toggleAttribute("disabled", true);
      error.textContent = "";
      const data = new FormData(form);
      try {
        const finished = await create({
          name: name.value.trim(),
          base_url: String(data.get("base_url") ?? "").trim(),
          description: String(data.get("description") ?? "").trim(),
          tags: parseTags(String(data.get("tags") ?? "")),
          author: String(data.get("author") ?? "").trim(),
          version: String(data.get("version") ?? "").trim(),
        });
        if (finished === false) create_.toggleAttribute("disabled", false);
        else dialog.close();
      } catch (failure) {
        error.textContent =
          failure instanceof Error ? failure.message : String(failure);
        create_.toggleAttribute("disabled", false);
      }
    });
    // A click outside the dialog does not close it: a half-filled form is work.
    dialog.append(form);
    show(dialog);
    await done;
  }
  /** Ask for a name that no other project uses.
   * @param {{title:string,confirm:string,initial?:string,hint?:string,ignore?:string}} options
   * @returns {Promise<string|null>} The name, or null when cancelled.
   */
  async askName(options) {
    const { dialog, done } = modal("ask-name", options.title);
    const name = /** @type {HTMLInputElement} */ (
      h("input", {
        name: "name",
        required: true,
        maxlength: "80",
        value: options.initial ?? "",
        autocomplete: "off",
        autofocus: true,
      })
    );
    const issue = h("small", { class: "pd-help pd-issue", role: "status" });
    const ok = /** @type {HTMLButtonElement} */ (
      h("button", { type: "submit", class: "accent" }, [
        h("span", { text: options.confirm }),
      ])
    );
    const cancel = button("Cancel");
    /** @type {string|null} */
    let answer = null;
    const check = () => {
      const problem = nameIssue(
        name.value,
        this.host.library().projects,
        options.ignore ?? "",
      );
      issue.textContent = name.value ? problem : "";
      ok.disabled = Boolean(problem);
    };
    name.addEventListener("input", check);
    cancel.addEventListener("click", () => dialog.close());
    const form = h("form", { class: "pd-form", novalidate: true }, [
      h("header", { class: "pd-header" }, [h("h2", { text: options.title })]),
      h("div", { class: "pd-scroll" }, [
        field("Project name", name, options.hint ?? ""),
        issue,
      ]),
      h("footer", { class: "pd-actions" }, [cancel, ok]),
    ]);
    form.addEventListener("submit", event => {
      event.preventDefault();
      check();
      if (ok.disabled) return;
      answer = name.value.trim();
      dialog.close();
    });
    dialog.append(form);
    check();
    show(dialog);
    name.select();
    await done;
    return answer;
  }
  /** Ask what to do with unsaved changes before leaving them.
   * @param {string} projectName
   * @returns {Promise<"save"|"discard"|"cancel">}
   */
  static unsaved = async projectName => {
    const { dialog, done } = modal("unsaved", "Unsaved changes");
    /** @type {"save"|"discard"|"cancel"} */
    let choice = "cancel";
    /** @param {"save"|"discard"|"cancel"} value */
    const pick = value => () => {
      choice = value;
      dialog.close();
    };
    const save = button("Save and continue", {
      class: "accent",
      autofocus: true,
    });
    const discard = button("Discard changes", { class: "pd-danger" });
    const cancel = button("Cancel");
    save.addEventListener("click", pick("save"));
    discard.addEventListener("click", pick("discard"));
    cancel.addEventListener("click", pick("cancel"));
    dialog.append(
      h("div", { class: "pd-form" }, [
        h("header", { class: "pd-header" }, [
          h("h2", { text: `Unsaved changes in “${projectName}”` }),
        ]),
        h("div", { class: "pd-scroll" }, [
          h("p", {
            text: "Save them first to keep your work. Discarding them cannot be undone.",
          }),
        ]),
        h("footer", { class: "pd-actions" }, [cancel, discard, save]),
      ]),
    );
    show(dialog);
    await done;
    return choice;
  };
  /** Open the gallery of all projects.
   * @param {GalleryActions} actions
   * @returns {Promise<void>} Settles when the gallery closes.
   */
  async gallery(actions) {
    const { dialog, done } = modal("project-gallery", "Projects");
    const filter = emptyFilter();
    /** @type {string} */
    let selected = this.host.project()?.slug ?? "";
    let advanced = false;
    /** @type {string} Project being deleted, which needs its name typed. */
    let deleting = "";
    /** The pieces below call each other, so they hang off one object.
     * @type {{draw:() => void,open:() => Promise<void>}}
     */
    const view = { draw: () => undefined, open: async () => undefined };
    const search = /** @type {HTMLInputElement} */ (
      h("input", {
        type: "search",
        placeholder: "Search by name, tag, author, address…",
        "aria-label": "Search projects",
        autocomplete: "off",
        autofocus: true,
      })
    );
    const toggle = button(
      "Advanced",
      { "aria-expanded": "false", class: "pd-toggle" },
      "adjustments-horizontal",
    );
    const panel = h("section", {
      class: "pd-advanced",
      hidden: true,
      "aria-label": "Advanced search",
    });
    const list = h("ul", {
      class: "pd-list",
      role: "listbox",
      "aria-label": "Projects",
    });
    const details = h("aside", { class: "pd-details", "aria-live": "polite" });
    const count = h("p", { class: "pd-count", role: "status" });
    const close = button(
      "Close",
      { class: "pd-icon-only", "aria-label": "Close gallery", title: "Close" },
      "x",
    );
    close.querySelector("span:not(.studio-icon)")?.classList.add("sr-only");
    close.addEventListener("click", () => dialog.close());
    const create = button("New project", { class: "accent" }, "plus");
    const upload = button("Import…", {}, "upload");
    create.addEventListener("click", () => {
      dialog.close();
      actions.create();
    });
    upload.addEventListener("click", () => actions.importFile());
    /** Advanced controls. */
    const tagBox = h("div", {
      class: "pd-tags",
      role: "group",
      "aria-label": "Tags",
    });
    const matchSelect = /** @type {HTMLSelectElement} */ (
      h("select", { "aria-label": "Tag match" }, [
        h("option", { value: "all", text: "Has all selected tags" }),
        h("option", { value: "any", text: "Has any selected tag" }),
      ])
    );
    const authorInput = /** @type {HTMLInputElement} */ (
      h("input", { placeholder: "Anyone", autocomplete: "off" })
    );
    const within = /** @type {HTMLSelectElement} */ (
      h("select", {}, [
        h("option", { value: "0", text: "Any time" }),
        h("option", { value: "1", text: "Today" }),
        h("option", { value: "7", text: "Last 7 days" }),
        h("option", { value: "30", text: "Last 30 days" }),
      ])
    );
    const runs = /** @type {HTMLSelectElement} */ (
      h("select", {}, [
        h("option", { value: "any", text: "Either" }),
        h("option", { value: "yes", text: "Has been run" }),
        h("option", { value: "no", text: "Never run" }),
      ])
    );
    const sort = /** @type {HTMLSelectElement} */ (
      h("select", {}, [
        h("option", { value: "modified", text: "Last changed" }),
        h("option", { value: "run", text: "Last run" }),
        h("option", { value: "created", text: "Created" }),
        h("option", { value: "name", text: "Name" }),
      ])
    );
    const clear = button("Clear filters", { class: "pd-link" });
    panel.append(
      h("div", { class: "pd-adv-grid" }, [
        field("Tags", tagBox),
        field("Tag match", matchSelect),
        field("Author", authorInput),
        field("Changed", within),
        field("Runs", runs),
        field("Sort by", sort),
      ]),
      clear,
    );
    /** @returns {ProjectSummaryData[]} */
    const visible = () => filterProjects(this.host.library().projects, filter);
    const current = () => this.host.project()?.slug ?? "";
    const drawTags = () => {
      const all = this.host.library().tags;
      tagBox.replaceChildren(
        ...(all.length
          ? all.map(tag => {
              const on = filter.tags.some(
                item => item.toLowerCase() === tag.toLowerCase(),
              );
              const chip = button(
                tag,
                { class: "pd-chip button-small", "aria-pressed": String(on) },
                "tag",
              );
              chip.addEventListener("click", () => {
                filter.tags = on
                  ? filter.tags.filter(
                      item => item.toLowerCase() !== tag.toLowerCase(),
                    )
                  : [...filter.tags, tag];
                view.draw();
              });
              return chip;
            })
          : [
              h("span", {
                class: "pd-muted",
                text: "No project has tags yet.",
              }),
            ]),
      );
    };
    /** @param {ProjectSummaryData} project */
    const row = project => {
      const item = h(
        "li",
        {
          class: "pd-item",
          role: "option",
          tabindex: project.slug === selected ? "0" : "-1",
          "aria-selected": String(project.slug === selected),
          "data-slug": project.slug,
        },
        [
          h("div", { class: "pd-item-main" }, [
            h("strong", { text: project.name }),
            ...(project.slug === current()
              ? [h("span", { class: "pd-badge", text: "Open now" })]
              : []),
          ]),
          h("small", {
            class: "pd-item-meta",
            text: `${project.flows} ${project.flows === 1 ? "flow" : "flows"} · changed ${ago(project.modified_at)}`,
          }),
          ...(project.tags.length
            ? [
                h(
                  "div",
                  { class: "pd-item-tags" },
                  project.tags
                    .slice(0, 4)
                    .map(tag => h("span", { class: "pd-tag", text: tag })),
                ),
              ]
            : []),
        ],
      );
      item.addEventListener("click", () => {
        selected = project.slug;
        deleting = "";
        view.draw();
        /** @type {HTMLElement|null} */ (
          list.querySelector('[aria-selected="true"]')
        )?.focus();
      });
      item.addEventListener("dblclick", () => view.open());
      return item;
    };
    view.open = async () => {
      if (!selected) return;
      const slug = selected;
      dialog.close();
      await actions.open(slug);
    };
    /** @param {string} label @param {string|Node} value @returns {HTMLElement[]} */
    const fact = (label, value) => [
      h("dt", { text: label }),
      h("dd", {}, [
        typeof value === "string"
          ? document.createTextNode(value || "—")
          : value,
      ]),
    ];
    const drawDetails = () => {
      const project = this.host
        .library()
        .projects.find(item => item.slug === selected);
      if (!project) {
        details.replaceChildren(
          h("p", {
            class: "pd-muted",
            text: this.host.library().projects.length
              ? "Choose a project to see its details."
              : "",
          }),
        );
        return;
      }
      const isOpen = project.slug === current();
      const facts = h("dl", { class: "pd-facts" }, [
        ...fact("Base URL", project.base_url),
        ...fact(
          "Tags",
          project.tags.length
            ? h(
                "span",
                { class: "pd-item-tags" },
                project.tags.map(tag =>
                  h("span", { class: "pd-tag", text: tag }),
                ),
              )
            : "",
        ),
        ...fact("Author", project.author),
        ...fact("Version", project.version),
        ...fact("Created", when(project.created_at)),
        ...fact("Last changed", when(project.modified_at)),
        ...fact(
          "Last run",
          project.last_run_at
            ? `${when(project.last_run_at)} (${ago(project.last_run_at)})`
            : "Never run",
        ),
        ...fact("Flows", String(project.flows)),
        ...fact("Runs kept", String(project.runs)),
        ...fact(
          "Folder",
          project.legacy
            ? "The Studio folder itself"
            : `projects/${project.slug}`,
        ),
      ]);
      const open = button(
        isOpen ? "Open now" : "Open",
        { class: "accent" },
        "folder-open",
      );
      open.disabled = isOpen;
      open.addEventListener("click", () => view.open());
      const copy = button("Duplicate", {}, "copy");
      copy.addEventListener("click", async () => {
        const name = await this.askName({
          title: "Duplicate project",
          confirm: "Duplicate",
          initial: `${project.name} copy`,
          hint: "Copies flows, connections, selectors and settings, not results.",
        });
        if (name) await actions.duplicate(project.slug, name);
      });
      const download = h(
        "a",
        {
          class: "pd-button",
          href: actions.exportUrl(project.slug),
          download: `${project.slug.replace("@", "")}.pwflow.json`,
        },
        [icon("download"), h("span", { text: "Export" })],
      );
      const remove = button("Delete…", { class: "pd-danger" }, "trash");
      const blocked = isOpen
        ? "Open another project to delete this one."
        : project.legacy
          ? "This is the Studio folder itself."
          : "";
      remove.disabled = Boolean(blocked);
      if (blocked) remove.title = blocked;
      remove.addEventListener("click", () => {
        deleting = project.slug;
        drawDetails();
        /** @type {HTMLElement|null} */ (
          details.querySelector("[data-confirm-input]")
        )?.focus();
      });
      /** @type {HTMLElement} */
      let footer = h("div", { class: "pd-detail-actions" }, [
        open,
        copy,
        download,
        remove,
      ]);
      if (deleting === project.slug) {
        const typed = /** @type {HTMLInputElement} */ (
          h("input", {
            "data-confirm-input": true,
            autocomplete: "off",
            spellcheck: "false",
            "aria-label": `Type ${project.name} to confirm`,
          })
        );
        const confirm = button("Delete project", {
          class: "pd-danger",
          disabled: true,
        });
        const keep = button("Keep project");
        typed.addEventListener("input", () => {
          confirm.disabled = typed.value.trim() !== project.name;
        });
        keep.addEventListener("click", () => {
          deleting = "";
          drawDetails();
        });
        confirm.addEventListener("click", async () => {
          deleting = "";
          await actions.remove(project.slug);
          selected = current();
          view.draw();
        });
        footer = h(
          "div",
          {
            class: "pd-confirm",
            role: "group",
            "aria-label": "Confirm deletion",
          },
          [
            h("p", {}, [
              document.createTextNode("Delete "),
              h("strong", { text: project.name }),
              document.createTextNode(
                "? Its flows, selectors and screenshots are removed for good.",
              ),
            ]),
            h("label", { class: "pd-field" }, [
              h("span", {
                class: "pd-label",
                text: `Type “${project.name}” to confirm`,
              }),
              typed,
            ]),
            h("div", { class: "pd-actions" }, [keep, confirm]),
          ],
        );
      }
      details.replaceChildren(
        h("header", {}, [
          h("h3", { text: project.name }),
          ...(project.description
            ? [h("p", { class: "pd-desc", text: project.description })]
            : []),
        ]),
        facts,
        footer,
      );
    };
    view.draw = () => {
      const projects = visible();
      const all = this.host.library().projects;
      if (projects.length && !projects.some(item => item.slug === selected))
        selected = projects[0]?.slug ?? "";
      list.replaceChildren(...projects.map(row));
      const filtered = isFiltered(filter);
      count.textContent = all.length
        ? `${projects.length} of ${all.length} ${all.length === 1 ? "project" : "projects"}`
        : "";
      if (!projects.length)
        list.replaceChildren(
          h("li", { class: "pd-empty", role: "presentation" }, [
            h("p", {
              text: all.length
                ? "No project matches these filters."
                : "There are no projects yet.",
            }),
          ]),
        );
      clear.hidden = !filtered;
      toggle.setAttribute("aria-expanded", String(advanced));
      panel.hidden = !advanced;
      drawTags();
      drawDetails();
    };
    this.refreshGallery = () => view.draw();
    search.addEventListener("input", () => {
      filter.query = search.value;
      view.draw();
    });
    toggle.addEventListener("click", () => {
      advanced = !advanced;
      view.draw();
    });
    matchSelect.addEventListener("change", () => {
      filter.tagMatch = matchSelect.value === "any" ? "any" : "all";
      view.draw();
    });
    authorInput.addEventListener("input", () => {
      filter.author = authorInput.value;
      view.draw();
    });
    within.addEventListener("change", () => {
      filter.modifiedWithin = Number(within.value);
      view.draw();
    });
    runs.addEventListener("change", () => {
      filter.runs =
        runs.value === "yes" || runs.value === "no" ? runs.value : "any";
      view.draw();
    });
    sort.addEventListener("change", () => {
      const value = sort.value;
      filter.sort =
        value === "run" || value === "created" || value === "name"
          ? value
          : "modified";
      view.draw();
    });
    clear.addEventListener("click", () => {
      Object.assign(filter, emptyFilter());
      search.value = "";
      authorInput.value = "";
      within.value = "0";
      runs.value = "any";
      sort.value = "modified";
      matchSelect.value = "all";
      view.draw();
    });
    list.addEventListener("keydown", event => {
      const projects = visible();
      const index = projects.findIndex(item => item.slug === selected);
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const next =
          projects[
            Math.min(
              projects.length - 1,
              Math.max(0, index + (event.key === "ArrowDown" ? 1 : -1)),
            )
          ];
        if (next) {
          selected = next.slug;
          deleting = "";
          view.draw();
          /** @type {HTMLElement|null} */ (
            list.querySelector('[aria-selected="true"]')
          )?.focus();
        }
      } else if (event.key === "Enter") {
        event.preventDefault();
        view.open();
      }
    });
    dialog.append(
      h("div", { class: "pd-form pd-gallery" }, [
        h("header", { class: "pd-header" }, [
          h("div", {}, [h("h2", { text: "Projects" }), count]),
          h("div", { class: "pd-header-actions" }, [upload, create, close]),
        ]),
        h("div", { class: "pd-search" }, [
          h("label", { class: "pd-search-box" }, [icon("search"), search]),
          toggle,
        ]),
        panel,
        h("div", { class: "pd-body" }, [list, details]),
      ]),
    );
    view.draw();
    show(dialog);
    await done;
    this.refreshGallery = null;
  }
  /** The recent projects, for menus.
   * @returns {ProjectSummaryData[]}
   */
  recents() {
    return recentProjects(this.host.library());
  }
}
