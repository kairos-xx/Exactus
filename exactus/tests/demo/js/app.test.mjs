import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import test from "node:test";
/**
 * @typedef {{currentTarget: FakeElement | null}} FakeEvent
 */
/**
 * @typedef {(event: FakeEvent) => void} FakeEventListener
 */
/** Minimal element double implementing the APIs `app.js` touches. */
class FakeElement {
  /**
   * Create an element with initial attributes.
   *
   * @param {Record<string, string>} attributes Initial attribute values.
   */
  constructor(attributes = {}) {
    /** @type {Map<string, string>} */
    this.attributes = new Map(Object.entries(attributes));
    /** @type {FakeEventListener[]} */
    this.listeners = [];
    /** @type {boolean} */
    this.hidden = false;
    /** @type {string} */
    this.textContent = "";
  }
  /**
   * Return an attribute value.
   *
   * @param {string} name Attribute name.
   * @returns {string | null} The value, or `null` when absent.
   */
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  /**
   * Store an attribute value.
   *
   * @param {string} name Attribute name.
   * @param {string} value Attribute value.
   * @returns {void}
   */
  setAttribute(name, value) {
    this.attributes.set(name, value);
  }
  /**
   * Register an event listener.
   *
   * @param {string} _type Event type.
   * @param {FakeEventListener} listener Listener to call.
   * @returns {void}
   */
  addEventListener(_type, listener) {
    this.listeners.push(listener);
  }
  /**
   * Dispatch a click to every registered listener.
   *
   * @returns {void}
   */
  click() {
    for (const listener of this.listeners)
      listener({
        currentTarget: this,
      });
  }
}
/** Dialog double tracking the `open` state. */
class FakeDialog extends FakeElement {
  /** Create a closed dialog. */
  constructor() {
    super();
    /** @type {boolean} */
    this.open = false;
  }
  /**
   * Open the dialog non-modally.
   *
   * @returns {void}
   */
  show() {
    this.open = true;
  }
  /**
   * Close the dialog.
   *
   * @returns {void}
   */
  close() {
    this.open = false;
  }
}
/** `classList` double backed by a set. */
class FakeClassList {
  /** Create an empty class list. */
  constructor() {
    /** @type {Set<string>} */
    this.names = new Set();
  }
  /**
   * Add or remove a class name.
   *
   * @param {string} name Class name.
   * @param {boolean} force Whether the class must be present.
   * @returns {void}
   */
  toggle(name, force) {
    if (force) this.names.add(name);
    else this.names.delete(name);
  }
}
/** Document double answering the selectors used by the controller. */
class FakeDocument {
  /**
   * Create a document from selector and id lookup tables.
   *
   * @param {Record<string, FakeElement>} single `querySelector` results.
   * @param {Record<string, FakeElement[]>} all `querySelectorAll` results.
   * @param {Record<string, FakeElement>} ids `getElementById` results.
   */
  constructor(single = {}, all = {}, ids = {}) {
    /** @type {Record<string, FakeElement>} */
    this.single = single;
    /** @type {Record<string, FakeElement[]>} */
    this.all = all;
    /** @type {Record<string, FakeElement>} */
    this.ids = ids;
    this.body = {
      classList: new FakeClassList(),
    };
  }
  /**
   * Return the first element for a selector.
   *
   * @param {string} selector CSS selector.
   * @returns {FakeElement | null} The element, or `null`.
   */
  querySelector(selector) {
    return this.single[selector] ?? null;
  }
  /**
   * Return every element for a selector.
   *
   * @param {string} selector CSS selector.
   * @returns {FakeElement[]} Matching elements.
   */
  querySelectorAll(selector) {
    return this.all[selector] ?? [];
  }
  /**
   * Return the element with an id.
   *
   * @param {string} id Element id.
   * @returns {FakeElement | null} The element, or `null`.
   */
  getElementById(id) {
    return this.ids[id] ?? null;
  }
}
const panels = {
  "panel-overview": new FakeElement(),
  "panel-metrics": new FakeElement(),
  "panel-settings": new FakeElement(),
  details: new FakeElement(),
};
const overviewTab = new FakeElement({
  "aria-controls": "panel-overview",
});
const metricsTab = new FakeElement({
  "aria-controls": "panel-metrics",
});
const settingsTab = new FakeElement({
  "aria-controls": "panel-settings",
});
/** @type {FakeElement[]} */
const tabs = [overviewTab, metricsTab, settingsTab];
const status = new FakeElement();
status.textContent = "Ready";
const toggleStatus = new FakeElement();
const saveDraft = new FakeElement();
const disclosure = new FakeElement({
  "aria-controls": "details",
  "aria-expanded": "false",
});
const density = new FakeElement({
  "aria-checked": "false",
});
const preview = new FakeDialog();
const openPreview = new FakeElement();
const closePreview = new FakeElement();
const page = new FakeDocument(
  {
    "[data-status]": status,
    ".preview": preview,
    "[data-toggle-status]": toggleStatus,
    "[data-save-draft]": saveDraft,
    "[data-density]": density,
    "[data-open-preview]": openPreview,
    "[data-close-preview]": closePreview,
  },
  {
    "[role=tab]": tabs,
    "[data-disclosure]": [disclosure],
  },
  panels,
);
/** @type {string[]} */
const fetched = [];
/** @type {string[]} */
const logged = [];
/** @type {string[]} */
const errors = [];
Object.assign(globalThis, {
  HTMLElement: FakeElement,
  HTMLDialogElement: FakeDialog,
  document: page,
  /**
   * @param {string | URL | Request} url Requested URL.
   * @param {RequestInit} [init] Request configuration.
   * @returns {Promise<{ok: boolean, status: number}>} Fake response.
   */
  fetch: (url, init = {}) => {
    fetched.push(`${init.method ?? "GET"} ${url.toString()}`);
    return Promise.resolve({
      ok: false,
      status: 500,
    });
  },
});
const { error, log, warn } = console;
Object.assign(console, {
  /**
   * Capture an error message.
   *
   * @param {unknown} message Logged value.
   * @returns {void}
   */
  error: message => {
    errors.push(String(message));
  },
  /**
   * Capture a log message.
   *
   * @param {unknown} message Logged value.
   * @returns {void}
   */
  log: message => {
    logged.push(String(message));
  },
  /**
   * Capture a warning message.
   *
   * @param {unknown} message Logged value.
   * @returns {void}
   */
  warn: message => {
    logged.push(String(message));
  },
});
// The suite runs from the repository and from the coverage demo copy.
const appUrl = [
  "../../../../demo/static/app.js",
  "../../../demo/static/app.js",
]
  .map(relative => new URL(relative, import.meta.url))
  .find(candidate => existsSync(candidate));
if (!appUrl)
  throw new Error("demo app.js entry point not found");
const source = await import(appUrl.href);
await Promise.resolve();
await Promise.resolve();
Object.assign(console, {
  error,
  log,
  warn,
});
const Controller = Reflect.get(globalThis, "demoController").constructor;
test("nextStatus activates a ready state", () => {
  assert.equal(source.nextStatus("Ready"), "Active");
});
test("nextStatus returns ready for an active state", () => {
  assert.equal(source.nextStatus("Active"), "Ready");
});
test("flipFlag toggles ARIA boolean strings", () => {
  assert.equal(source.flipFlag("true"), "false");
  assert.equal(source.flipFlag("false"), "true");
  assert.equal(source.flipFlag(null), "true");
});
test("panelHidden keeps only the selected panel visible", () => {
  assert.equal(source.panelHidden("panel-a", "panel-a"), false);
  assert.equal(source.panelHidden("panel-b", "panel-a"), true);
});
test("module start-up leaves the failed response to browser diagnostics", () => {
  assert.deepEqual(fetched, ["GET /api/error"]);
  assert.deepEqual(errors, []);
  assert.deepEqual(logged, ["The demo HTTP error is intentional."]);
});
test("saving a draft updates the status without a request", async () => {
  const controller = Reflect.get(globalThis, "demoController");
  await controller.saveDraft();
  assert.equal(status.textContent, "Draft saved");
  saveDraft.click();
  assert.equal(status.textContent, "Draft saved");
  assert.ok(!fetched.some(entry => entry.includes("/api/draft")));
  status.textContent = "Ready";
});
test("status toggle flips the visible label", () => {
  toggleStatus.click();
  assert.equal(status.textContent, "Active");
  toggleStatus.click();
  assert.equal(status.textContent, "Ready");
});
test("selecting a tab reveals only its panel", () => {
  metricsTab.click();
  assert.equal(metricsTab.getAttribute("aria-selected"), "true");
  assert.equal(overviewTab.getAttribute("aria-selected"), "false");
  assert.equal(panels["panel-metrics"].hidden, false);
  assert.equal(panels["panel-overview"].hidden, true);
  assert.equal(panels["panel-settings"].hidden, true);
});
test("disclosure expands and collapses its region", () => {
  disclosure.click();
  assert.equal(disclosure.getAttribute("aria-expanded"), "true");
  assert.equal(panels.details.hidden, false);
  disclosure.click();
  assert.equal(panels.details.hidden, true);
});
test("density switch toggles the compact class", () => {
  density.click();
  assert.equal(density.getAttribute("aria-checked"), "true");
  assert.ok(page.body.classList.names.has("compact"));
  density.click();
  assert.ok(!page.body.classList.names.has("compact"));
});
test("preview panel opens once and closes", () => {
  openPreview.click();
  assert.equal(preview.open, true);
  openPreview.click();
  assert.equal(preview.open, true);
  closePreview.click();
  assert.equal(preview.open, false);
});
test("handlers ignore events without an element target", () => {
  const controller = Reflect.get(globalThis, "demoController");
  /** @type {FakeEvent} */
  const event = {
    currentTarget: null,
  };
  controller.selectTab(event);
  controller.toggleDisclosure(event);
  controller.toggleDensity(event);
  assert.equal(density.getAttribute("aria-checked"), "false");
});
test("controls without targets or a page lacking widgets are tolerated", async () => {
  const orphanTab = new FakeElement({
    "aria-controls": "missing",
  });
  const orphanDisclosure = new FakeElement({
    "aria-controls": "missing",
  });
  const bare = new FakeDocument(
    {},
    {
      "[role=tab]": [orphanTab],
      "[data-disclosure]": [orphanDisclosure],
    },
  );
  const controller = new Controller(bare);
  orphanTab.click();
  orphanDisclosure.click();
  controller.toggleStatus();
  await controller.saveDraft();
  controller.openPreview();
  controller.closePreview();
  assert.equal(orphanTab.getAttribute("aria-selected"), "true");
  assert.equal(orphanDisclosure.getAttribute("aria-expanded"), "true");
});
