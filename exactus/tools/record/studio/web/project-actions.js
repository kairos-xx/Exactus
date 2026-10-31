/** What a person can do with projects: create, open, save, import, export.
 *
 * The top bar, the gallery, the Project tab and the command palette all call
 * these same actions, so leaving unsaved changes is guarded in one place and
 * errors are reported in one voice.
 */
import { ProjectDialogs } from "./project-dialogs.js";
/**
 * @typedef {object} ActionsHost What the actions need from the editor.
 * @property {(name:string,payload:Record<string,unknown>|null) => Promise<unknown>} call Send a command to the Studio service.
 * @property {(snapshot:unknown) => void} apply Show the snapshot a command returned.
 * @property {(text:string) => void} say Report something in the status line.
 * @property {() => {dirty?:boolean,project?:ProjectState,library?:LibraryData}|null} state The latest snapshot.
 * @property {(view:string) => void} showView Switch the workspace tab.
 */
/** @type {LibraryData} */
const NO_LIBRARY = { projects: [], recents: [], tags: [] };
/** Project-level actions shared by the bar and dialogs. */
export class ProjectActions {
  /** @type {HTMLInputElement|null} */
  picker = null;
  /** @param {ActionsHost} host */
  constructor(host) {
    this.host = host;
    this.dialogs = new ProjectDialogs({
      library: () => this.library(),
      project: () => this.project(),
    });
  }
  /** The projects the Studio knows.
   * @returns {LibraryData}
   */
  library() {
    return this.host.state()?.library ?? NO_LIBRARY;
  }
  /** The open project.
   * @returns {ProjectState|null}
   */
  project() {
    return this.host.state()?.project ?? null;
  }
  /** Whether the open project has changes that are not saved.
   * @returns {boolean}
   */
  dirty() {
    return this.host.state()?.dirty === true;
  }
  /** The name to show for the open project.
   * @returns {string}
   */
  name() {
    return this.project()?.name || "Untitled project";
  }
  /** Run something that can fail, reporting the failure instead of throwing.
   * @template T
   * @param {() => Promise<T>} work
   * @returns {Promise<T|undefined>}
   */
  async attempt(work) {
    try {
      return await work();
    } catch (error) {
      this.host.say(error instanceof Error ? error.message : String(error));
      return undefined;
    }
  }
  /** Send a command and show the snapshot it returns.
   * @param {string} name
   * @param {Record<string,unknown>} payload
   * @returns {Promise<void>}
   */
  async send(name, payload) {
    this.host.apply(await this.host.call(name, payload));
  }
  /** Make sure leaving the open project loses nothing.
   * @returns {Promise<{replace:boolean}|null>} Whether edits are being discarded, or null when the person cancelled.
   */
  async leave() {
    if (!this.dirty()) return { replace: false };
    const choice = await ProjectDialogs.unsaved(this.name());
    if (choice === "cancel") return null;
    if (choice === "save") {
      const saved = await this.attempt(async () => {
        await this.send("workspace.save", {});
        return true;
      });
      return this.dirty() || saved !== true ? null : { replace: false };
    }
    return { replace: true };
  }
  /** Save the open project.
   * @returns {Promise<void>}
   */
  async save() {
    await this.attempt(async () => {
      await this.send("workspace.save", {});
      this.host.say(`Saved “${this.name()}”.`);
    });
  }
  /** Ask for a new project's details, then create and open it.
   * @returns {Promise<void>}
   */
  async create() {
    await this.dialogs.newProject(async details => {
      const left = await this.leave();
      if (!left) return false;
      await this.send("project.create", { ...details, replace: left.replace });
      const { name } = details;
      this.host.say(`Created “${String(name)}”.`);
      this.host.showView("edit");
      return true;
    });
  }
  /** Open a project from the library.
   * @param {string} slug
   * @returns {Promise<void>}
   */
  async open(slug) {
    if (slug === this.project()?.slug) return;
    const left = await this.leave();
    if (!left) return;
    await this.attempt(async () => {
      await this.send("project.open", { slug, replace: left.replace });
      this.host.say(`Opened “${this.name()}”.`);
    });
  }
  /** Copy a project under a new name.
   * @param {string} slug
   * @param {string} name
   * @returns {Promise<void>}
   */
  async duplicate(slug, name) {
    await this.attempt(async () => {
      await this.send("project.duplicate", { slug, name });
      this.host.say(`Duplicated as “${name}”.`);
    });
  }
  /** Delete a project that is not open.
   * @param {string} slug
   * @returns {Promise<void>}
   */
  async remove(slug) {
    await this.attempt(async () => {
      await this.send("project.delete", { slug });
      this.host.say("Project deleted.");
    });
  }
  /** Open the bundled demo as a project of its own.
   * @returns {Promise<void>}
   */
  async openDemo() {
    const left = await this.leave();
    if (!left) return;
    await this.attempt(async () => {
      await this.send("demo.open", { replace: left.replace, project: true });
      this.host.say("Demo flow ready. Run it from Play.");
    });
  }
  /** Show the gallery of all projects.
   * @returns {Promise<void>}
   */
  async gallery() {
    await this.dialogs.gallery({
      open: slug => this.open(slug),
      duplicate: (slug, name) => this.duplicate(slug, name),
      remove: slug => this.remove(slug),
      importFile: () => this.importFile(false),
      create: () => this.create(),
      exportUrl: slug => ProjectActions.exportUrl(slug),
    });
  }
  /** Where a project downloads from.
   * @param {string} [slug] A project, or the open one when blank.
   * @returns {string}
   */
  static exportUrl = (slug = "") =>
    slug ? `/api/export?project=${encodeURIComponent(slug)}` : "/api/export";
  /** Download the open project.
   * @returns {void}
   */
  exportOpen() {
    const link = document.createElement("a");
    link.href = ProjectActions.exportUrl();
    const open = this.project();
    link.download = `${open?.slug.replace("@", "") || "project"}.pwflow.json`;
    document.body.append(link);
    link.click();
    link.remove();
  }
  /** Choose a file and add the project it holds.
   * @param {boolean} openIt Whether to open the project afterwards.
   * @returns {Promise<void>}
   * @throws {Error} When the file is not a project export.
   */
  async importFile(openIt) {
    const file = await this.pickFile();
    if (!file) return;
    await this.attempt(async () => {
      /** @type {unknown} */
      let document;
      try {
        document = JSON.parse(await file.text());
      } catch {
        throw new Error("That file is not a project export.");
      }
      const left = openIt ? await this.leave() : { replace: false };
      if (!left) return;
      await this.send("project.import", {
        workspace: document,
        open: openIt,
        replace: left.replace,
      });
      this.host.say(`Imported “${file.name}”.`);
    });
  }
  /** Let the person choose a project file.
   * @returns {Promise<File|null>}
   */
  pickFile() {
    this.picker ??= Object.assign(document.createElement("input"), {
      type: "file",
      accept: ".json,application/json",
      hidden: true,
    });
    const input = this.picker;
    if (!input.isConnected) document.body.append(input);
    input.value = "";
    return new Promise(resolve => {
      input.addEventListener(
        "change",
        () => resolve(input.files?.[0] ?? null),
        { once: true },
      );
      input.addEventListener("cancel", () => resolve(null), { once: true });
      input.click();
    });
  }
}
