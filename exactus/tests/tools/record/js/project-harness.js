/** A fake editor host and sample library for the project modules, run in a page. */
/** Wait for pending promise callbacks and the next task.
 * @returns {Promise<void>}
 */
export const settle = () =>
  new Promise(resolve => {
    setTimeout(resolve, 0);
  });
/** A project summary with any field overridden.
 * @param {Record<string, unknown>} extra
 * @returns {any}
 */
export const summary = extra => ({
  slug: "alpha",
  name: "Alpha",
  description: "First project",
  tags: ["web", "smoke"],
  author: "Ana",
  version: "1.0.0",
  created_at: "2026-10-01T00:00:00",
  modified_at: "2026-10-08T00:00:00",
  last_run_at: "2026-10-08T10:00:00",
  flows: 2,
  runs: 3,
  base_url: "http://localhost:3000",
  legacy: false,
  ...extra,
});
/** A host that records every command, message and view change.
 * @param {{failing?:string[]}} [options] Command names that reject.
 * @returns {any}
 * @throws {Error} From any command named in `failing`.
 */
export const makeHost = (options = {}) => {
  const alpha = summary({});
  const beta = summary({
    slug: "beta",
    name: "Beta",
    tags: ["admin"],
    author: "Bo",
    last_run_at: "",
    runs: 0,
    flows: 1,
    description: "",
    base_url: "",
    modified_at: "2026-09-01T00:00:00",
  });
  const legacy = summary({
    slug: "@legacy",
    name: "Legacy",
    legacy: true,
    tags: [],
    author: "",
    version: "",
    description: "",
  });
  const state = {
    dirty: false,
    library: {
      projects: [alpha, beta, legacy],
      recents: ["beta", "alpha"],
      tags: ["web", "smoke", "admin"],
    },
    project: {
      slug: "alpha",
      name: "Alpha",
      description: "First project",
      tags: ["web", "smoke"],
      author: "Ana",
      version: "1.0.0",
      created_at: "2026-10-01T00:00:00",
      saved: true,
    },
  };
  /** @type {[string, unknown][]} */
  const calls = [];
  /** @type {string[]} */
  const said = [];
  /** @type {unknown[]} */
  const applied = [];
  /** @type {string[]} */
  const views = [];
  const host = {
    state,
    calls,
    said,
    applied,
    views,
    call: async (
      /** @type {string} */ name,
      /** @type {unknown} */ payload,
    ) => {
      calls.push([name, payload]);
      if (options.failing?.includes(name)) throw new Error(`${name} failed`);
      if (name === "workspace.save") state.dirty = false;
      return { command: name };
    },
    apply: (/** @type {unknown} */ snapshot) => applied.push(snapshot),
    say: (/** @type {string} */ text) => said.push(text),
    showView: (/** @type {string} */ view) => views.push(view),
  };
  return { ...host, host: { ...host, state: () => state } };
};
/** The visible dialog, if any.
 * @returns {HTMLDialogElement|null}
 */
export const openDialog = () => document.querySelector("dialog[open]");
/** Click the first button inside a root whose text matches.
 * @param {ParentNode} root
 * @param {string} text
 * @returns {boolean} Whether a button was found.
 */
export const press = (root, text) => {
  const target = [...root.querySelectorAll("button, a")].find(item =>
    (item.textContent ?? "").trim().startsWith(text),
  );
  if (!(target instanceof HTMLElement)) return false;
  target.click();
  return true;
};
/** Type into an input and notify listeners.
 * @param {HTMLInputElement|HTMLTextAreaElement} input
 * @param {string} value
 * @returns {void}
 */
export const type = (input, value) => {
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
};
