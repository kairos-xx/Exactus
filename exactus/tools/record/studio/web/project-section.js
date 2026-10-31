/** The Project section of the Settings tab: name, details and the gallery.
 *
 * It sits above the target, which already holds the project's base address,
 * so the address is not asked for twice. The fields are the ones the New
 * project dialog asks for. Changes apply to the open project; Save project
 * writes them to disk, like every other edit.
 */
import { h, icon } from "./project-dialogs.js";
import { nameIssue, parseTags, when } from "./project-model.js";
/** The fields of the form, as text.
 * @typedef {{name:string,description:string,tags:string,author:string,version:string}} ProjectDraft
 */
export class ProjectSection {
  /** @type {ProjectDraft|null} What is typed and not yet applied. */
  draft = null;
  /** @type {string} The project the draft belongs to. */
  slug = "";
  /** @param {import("./project-actions.js").ProjectActions} actions */
  constructor(actions) {
    this.actions = actions;
  }
  /** The project's own values, as form text.
   * @param {ProjectState} project
   * @returns {ProjectDraft}
   */
  static saved = project => ({
    name: project.name,
    description: project.description,
    tags: project.tags.join(", "),
    author: project.author,
    version: project.version,
  });
  /** Draw the section for the open project.
   * @returns {HTMLElement}
   */
  section() {
    const project = this.actions.project();
    const section = h("section", {
      class: "settings-section",
      id: "settings-project",
      "aria-labelledby": "settings-project-title",
    });
    if (!project) {
      section.append(
        h("p", { class: "settings-intro", text: "No project is open." }),
      );
      return section;
    }
    if (this.slug !== project.slug) {
      this.slug = project.slug;
      this.draft = null;
    }
    const library = this.actions.library();
    const base = ProjectSection.saved(project);
    const values = this.draft ?? base;
    /** @param {string} name @param {string} value @param {Record<string,string|boolean>} [extra] */
    const input = (name, value, extra = {}) =>
      /** @type {HTMLInputElement} */ (
        h("input", {
          name,
          value,
          id: `project-field-${name}`,
          autocomplete: "off",
          spellcheck: "false",
          ...extra,
        })
      );
    const name = input("name", values.name, {
      required: true,
      maxlength: "80",
    });
    const tags = input("tags", values.tags, { placeholder: "web, smoke" });
    const author = input("author", values.author, { maxlength: "80" });
    const version = input("version", values.version, {
      maxlength: "80",
      placeholder: "0.1.0",
    });
    const description = /** @type {HTMLTextAreaElement} */ (
      h("textarea", {
        name: "description",
        id: "project-field-description",
        rows: "3",
      })
    );
    description.value = values.description;
    const error = h("p", { class: "field-error", role: "alert" });
    const issue = h("p", { class: "field-error", role: "status" });
    const apply = /** @type {HTMLButtonElement} */ (
      h("button", { type: "submit", class: "accent" }, [
        h("span", { text: "Apply changes" }),
      ])
    );
    const revert = /** @type {HTMLButtonElement} */ (
      h("button", { type: "button" }, [h("span", { text: "Revert" })])
    );
    const gallery = /** @type {HTMLButtonElement} */ (
      h("button", { type: "button" }, [
        icon("folder-open"),
        h("span", { text: "Open project gallery" }),
      ])
    );
    gallery.addEventListener("click", () => this.actions.gallery());
    /** @param {string} label @param {HTMLElement} control @param {string} [note] */
    const row = (label, control, note = "") =>
      h("div", { class: "settings-field" }, [
        h("label", { for: control.id, text: label }),
        control,
        ...(note ? [h("p", { class: "field-note", text: note })] : []),
      ]);
    const form = /** @type {HTMLFormElement} */ (
      h(
        "form",
        {
          class: "profile-form project-form",
          novalidate: true,
          "aria-label": "Project details",
        },
        [
          row("Name", name),
          issue,
          row("Description", description),
          row(
            "Tags",
            tags,
            "Separate tags with commas. The gallery filters by them.",
          ),
          row("Author", author),
          row("Version", version),
          error,
          h("div", { class: "settings-actions" }, [
            h("div", { class: "settings-actions-main" }, [apply, revert]),
          ]),
        ],
      )
    );
    /** @returns {ProjectDraft} */
    const typed = () => ({
      name: name.value.trim(),
      description: description.value.trim(),
      tags: parseTags(tags.value).join(", "),
      author: author.value.trim(),
      version: version.value.trim(),
    });
    const changed = () => JSON.stringify(typed()) !== JSON.stringify(base);
    const check = () => {
      const problem = nameIssue(name.value, library.projects, project.slug);
      issue.textContent = problem;
      name.toggleAttribute("aria-invalid", Boolean(problem));
      apply.disabled = Boolean(problem) || !changed();
      revert.disabled = !changed();
    };
    form.addEventListener("input", () => {
      this.draft = changed()
        ? {
            name: name.value,
            description: description.value,
            tags: tags.value,
            author: author.value,
            version: version.value,
          }
        : null;
      check();
    });
    revert.addEventListener("click", () => {
      this.draft = null;
      name.value = base.name;
      description.value = base.description;
      tags.value = base.tags;
      author.value = base.author;
      version.value = base.version;
      error.textContent = "";
      check();
    });
    form.addEventListener("submit", async event => {
      event.preventDefault();
      check();
      if (apply.disabled) return;
      error.textContent = "";
      const details = typed();
      try {
        await this.actions.send("project.update", {
          name: details.name,
          description: details.description,
          tags: parseTags(details.tags),
          author: details.author,
          version: details.version,
        });
        this.draft = null;
        this.actions.host.say(
          "Project details applied. Save the project to keep them.",
        );
      } catch (failure) {
        error.textContent =
          failure instanceof Error ? failure.message : String(failure);
      }
    });
    check();
    section.append(
      h("header", {}, [
        h("h3", { id: "settings-project-title", text: "Project" }),
        h("p", {
          class: "settings-intro",
          text: `Created ${when(project.created_at)}. ${
            project.saved ? "" : "Not saved yet. "
          }The base address is the target below.`,
        }),
      ]),
      form,
      h("div", { class: "settings-actions-main" }, [gallery]),
    );
    return section;
  }
}
