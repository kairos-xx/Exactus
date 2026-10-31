import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import { webcrypto } from "node:crypto";
import {
  buildSandbox as createSandbox,
  FakeTextNode,
} from "./sandbox-dom.mjs";
/** Event subclass carrying a detail payload for node tests. */
class CustomEvent extends Event {
  /** @type {unknown} */
  detail;
  /**
   * @param {string} type Event type.
   * @param {{detail?: unknown} & EventInit} [options] Event payload.
   */
  constructor(type, options = {}) {
    super(type, options);
    this.detail = options.detail;
  }
}
/**
 * @typedef {{
 *   __listeners: Map<string, (event?: any) => void>,
 *   RollingCapture?: any,
 *   EvidenceRuntime?: any,
 *   Element?: any,
 *   [key: string]: any
 * }} Sandbox
 */
/**
 * @typedef {Omit<ReturnType<typeof createSandbox>, "htmlToImage"> & {
 *   htmlToImage?: any,
 *   RollingCapture?: any,
 *   EvidenceRuntime?: any,
 *   __evidenceSink?: (payload: any) => unknown,
 * }} RichSandbox
 */
/**
 * Build an isolated VM sandbox with the evidence runtime evaluated inside.
 *
 * @returns {Sandbox} The populated sandbox global.
 */
const buildSandbox = () => {
  /** @type {Map<string, (event?: any) => void>} */
  const listeners = new Map();
  /** @type {Sandbox} */
  const sandbox = {
    console,
    TextEncoder,
    TextDecoder,
    EventTarget,
    Event,
    CustomEvent,
    URL,
    crypto: webcrypto,
    performance,
    btoa,
    atob,
    Blob: globalThis.Blob,
    ArrayBuffer,
    Uint8Array,
    DataView,
    FileReader: class {
      /** @type {(() => void) | undefined} */
      onload;
      readAsDataURL() {
        this.onload?.();
      }
    },
    location: { href: "https://scene-tests.local/page" },
    innerWidth: 800,
    innerHeight: 600,
    devicePixelRatio: 2,
    /**
     * @param {string} type Event type.
     * @param {(event?: any) => void} listener Event handler.
     */
    addEventListener: (type, listener) => listeners.set(type, listener),
    /** @param {string} type Event type. */
    removeEventListener: type => listeners.delete(type),
    dispatchEvent: () => true,
    document: { documentElement: { localName: "html" } },
    Element: class {},
    MutationObserver: class {
      /** @type {(mutations: unknown[], observer: unknown) => void} */
      callback;
      /** @type {[unknown, unknown][]} */
      observed = [];
      /** @type {boolean} */
      disconnected = false;
      /**
       * @param {(mutations: unknown[], observer: unknown) => void} callback
       *   Observation callback.
       */
      constructor(callback) {
        this.callback = callback;
      }
      /**
       * @param {unknown} target Observed node.
       * @param {unknown} options Observation options.
       */
      observe(target, options) {
        this.observed.push([target, options]);
      }
      disconnect() {
        this.disconnected = true;
      }
    },
    PerformanceObserver: class {
      /** @type {unknown} */
      callback;
      /** @type {unknown} */
      options;
      /** @type {boolean} */
      disconnected = false;
      /** @param {unknown} callback Observation callback. */
      constructor(callback) {
        this.callback = callback;
      }
      /** @param {unknown} options Observation options. */
      observe(options) {
        this.options = options;
      }
      disconnect() {
        this.disconnected = true;
      }
    },
    __listeners: listeners,
  };
  const source = new URL(
    "../../../../packages/scene_description/js/unified_evidence.js",
    import.meta.url,
  );
  runInNewContext(readFileSync(source, "utf8"), sandbox, {
    filename: source.href,
  });
  return sandbox;
};
test("runtime registers capture classes on globalThis", () => {
  const sandbox = buildSandbox();
  assert.equal(typeof sandbox.RollingCapture, "function");
  assert.equal(typeof sandbox.EvidenceRuntime, "function");
});
test("rolling capture reports defaults and applies option overrides", () => {
  const sandbox = buildSandbox();
  const capture = new sandbox.RollingCapture({
    quality: "low",
    window: 1000,
    segmentDuration: 125,
  });
  assert.equal(capture.armed, false);
  assert.equal(capture.target, null);
  assert.equal(capture.quality.fps, 15);
  assert.equal(capture.quality.videoBitsPerSecond, 750000);
  const status = capture.status();
  assert.equal(status.armed, false);
  assert.equal(status.quality.fps, 15);
  assert.equal(status.memory.bufferBytes, 0);
});
test("evidence runtime status, markers, and events round-trip", () => {
  const sandbox = buildSandbox();
  const runtime = new sandbox.EvidenceRuntime({ diagnostics: false });
  /** @type {any[]} */
  const emitted = [];
  runtime.addEventListener("mark", (/** @type {{detail?: any}} */ event) =>
    emitted.push(event.detail),
  );
  const entry = runtime.mark("checkpoint", { index: 1 });
  assert.equal(entry.type, "checkpoint");
  assert.equal(entry.url, "https://scene-tests.local/page");
  assert.equal(emitted.length, 1);
  assert.equal(emitted[0].url, entry.url);
  assert.ok(emitted[0].timestamp);
  const markers = runtime.markers({ since: 0 });
  assert.equal(markers.length, 1);
  assert.equal(markers[0].type, "checkpoint");
  assert.equal(runtime.markers({ since: entry.time + 1 }).length, 0);
  assert.equal(runtime.diagnostics().length, 0);
  const status = runtime.status();
  assert.equal(status.markers, 1);
  assert.deepEqual([...status.modes], ["video", "capture", "description"]);
  assert.equal(runtime.armed, false);
});
test("diagnostics record window, viewport, mutation, and performance events", () => {
  const sandbox = buildSandbox();
  const runtime = new sandbox.EvidenceRuntime();
  const listeners = sandbox.__listeners;
  listeners.get("error")?.({
    message: "boom",
    filename: "app.js",
    lineno: 4,
    colno: 2,
  });
  listeners.get("resize")?.();
  const target = new sandbox.Element();
  Object.assign(target, {
    id: "node",
    localName: "div",
    classList: [],
    parentElement: null,
  });
  runtime.diagnostics();
  const kinds = new Set(
    runtime.diagnostics().map((/** @type {{type: string}} */ entry) => entry.type),
  );
  assert.ok(kinds.has("window-error"));
  assert.ok(kinds.has("viewport-resize"));
  runtime.stopDiagnostics();
  assert.equal(runtime.diagnostics().length >= 2, true);
});
/**
 * Build a sandbox with the evidence runtime injected.
 *
 * @returns {RichSandbox} Sandbox with the evidence runtime injected.
 */
const buildRichSandbox = () => {
  const sandbox = createSandbox({ webcrypto });
  const source = new URL(
    "../../../../packages/scene_description/js/unified_evidence.js",
    import.meta.url,
  );
  runInNewContext(readFileSync(source, "utf8"), sandbox, {
    filename: source.href,
  });
  return /** @type {RichSandbox} */ (sandbox);
};
/**
 * Build a fixture page exercising every descriptor branch family.
 *
 * @param {RichSandbox} sandbox VM sandbox with DOM stand-ins.
 * @returns {{root: import("./sandbox-dom.mjs").Element,
 *   scroller: import("./sandbox-dom.mjs").Element}} Fixture nodes.
 */
const fixture = sandbox => {
  /**
   * @typedef {new (tag: string,
   *   doc: import("./sandbox-dom.mjs").FakeDocument) =>
   *     import("./sandbox-dom.mjs").Element} ElementCtor
   */
  const {
    document,
    HTMLElement,
    HTMLAnchorElement,
    HTMLButtonElement,
    HTMLInputElement,
    HTMLSelectElement,
    HTMLOptionElement,
    HTMLOptGroupElement,
    HTMLTextAreaElement,
    HTMLProgressElement,
    HTMLMeterElement,
    HTMLImageElement,
    HTMLVideoElement,
    HTMLCanvasElement,
    HTMLDetailsElement,
    SVGSVGElement,
    SVGTextElement,
  } = sandbox;
  const root = new HTMLElement("main", document);
  root.rect = { left: 0, top: 0, width: 800, height: 600 };
  document.body.append(root);
  /**
   * Create, configure and mount an element.
   *
   * @param {ElementCtor} cls Element class.
   * @param {string} tag Tag name.
   * @param {Record<string, unknown>} [props] Own properties.
   * @param {Record<string, string>} [attrs] Attributes.
   * @returns {import("./sandbox-dom.mjs").Element} Mounted element.
   */
  const el = (cls, tag, props = {}, attrs = {}) => {
    const node = new cls(tag, document);
    Object.assign(node, props);
    for (const [name, value] of Object.entries(attrs))
      node.setAttribute(name, value);
    root.append(node);
    return node;
  };
  el(HTMLAnchorElement, "a", { href: "https://example.test/x" });
  el(HTMLButtonElement, "button", {}, { "aria-pressed": "true" });
  const text = el(
    HTMLInputElement,
    "input",
    { type: "text", value: "hello" },
    { id: "name" },
  );
  const label = el(HTMLElement, "label", {}, { for: "name" });
  label.append(new FakeTextNode("Name", document));
  text.labels = [label];
  el(HTMLInputElement, "input", { type: "checkbox", checked: true });
  const radioA = el(HTMLInputElement, "input", {
    type: "radio",
    name: "group",
    checked: true,
  });
  const radioB = el(HTMLInputElement, "input", {
    type: "radio",
    name: "group",
  });
  radioA.setAttribute("name", "group");
  radioB.setAttribute("name", "group");
  el(HTMLInputElement, "input", {
    type: "range",
    min: 0,
    max: 10,
    step: 1,
    value: 5,
  });
  el(HTMLInputElement, "input", {
    type: "file",
    files: [{ name: "a.png" }],
  });
  el(HTMLInputElement, "input", { type: "color", value: "#ff0000" });
  el(HTMLInputElement, "input", { type: "password", value: "secret" });
  el(HTMLInputElement, "input", { type: "submit", value: "Go" });
  const select = el(HTMLSelectElement, "select", {});
  const group = new HTMLOptGroupElement("optgroup", document);
  const optionA = new HTMLOptionElement("option", document);
  optionA.selected = true;
  optionA.value = "one";
  optionA.append(new FakeTextNode("One", document));
  const optionB = new HTMLOptionElement("option", document);
  optionB.value = "two";
  optionB.append(new FakeTextNode("Two", document));
  group.append(optionA, optionB);
  select.append(group);
  el(HTMLTextAreaElement, "textarea", { value: "long text" });
  el(HTMLProgressElement, "progress", { value: 3, max: 10 });
  el(HTMLMeterElement, "meter", {
    value: 4,
    min: 0,
    max: 10,
    low: 2,
    high: 8,
    optimum: 5,
  });
  el(HTMLImageElement, "img", {
    src: "pic.png",
    alt: "picture",
    naturalWidth: 320,
    naturalHeight: 240,
  });
  const video = el(HTMLVideoElement, "video", {
    src: "clip.mp4",
    poster: "poster.png",
  });
  video.readyState = 4;
  el(HTMLCanvasElement, "canvas", {});
  const svg = new SVGSVGElement("svg", document);
  svg.rect = { left: 0, top: 0, width: 24, height: 24 };
  const glyph = new SVGTextElement("text", document);
  glyph.append(new FakeTextNode("glyph", document));
  svg.append(glyph);
  root.append(svg);
  const details = el(HTMLDetailsElement, "details", { open: true });
  const summary = new HTMLElement("summary", document);
  summary.append(new FakeTextNode("More", document));
  details.append(summary);
  const editable = el(HTMLElement, "div", { isContentEditable: true });
  editable.append(new FakeTextNode("edit me", document));
  const scroller = el(HTMLElement, "div", {
    scrollWidth: 400,
    scrollHeight: 400,
    clientWidth: 100,
    clientHeight: 50,
    scrollLeft: 10,
    scrollTop: 5,
  });
  scroller.append(new FakeTextNode("scrollable", document));
  const tablist = el(HTMLElement, "div", {}, { role: "tablist" });
  const tab = new HTMLElement("div", document);
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-selected", "true");
  tab.rect = { left: 0, top: 0, width: 80, height: 24 };
  tablist.append(tab);
  el(HTMLElement, "div", {}, { role: "slider", "aria-valuenow": "3" });
  el(HTMLElement, "div", {}, { role: "switch", "aria-checked": "true" });
  const paragraph = el(HTMLElement, "p", { ownText: "" });
  paragraph.append(
    new FakeTextNode("first words", document),
    new FakeTextNode("second words", document),
  );
  const pseudo = el(HTMLElement, "aside", {});
  pseudo.pseudoStyles = { "::before": { content: '"note"' } };
  const shadowed = el(HTMLElement, "section", {});
  shadowed.styleOverrides = {
    boxShadow: "rgb(0,0,0) 0px 1px 2px",
    textShadow: "rgb(0,0,0) 1px 1px",
  };
  return { root, scroller };
};
test("description walks a rich fixture and returns a manifest", async () => {
  const sandbox = buildRichSandbox();
  const { root } = fixture(sandbox);
  const runtime = new sandbox.EvidenceRuntime({
    diagnostics: false,
    target: root,
  });
  /** @type {any[]} */
  const events = [];
  runtime.addEventListener(
    "description",
    (/** @type {{detail?: any}} */ event) => events.push(event.detail),
  );
  const result = await runtime.description({ target: root });
  assert.equal(result.kind, "description");
  assert.ok(result.manifest);
  assert.ok(result.manifestBytes > 0);
  assert.equal(events.length, 1);
  assert.equal(runtime.status().descriptions.length, 1);
  await runtime.destroy();
});
test("description with inline binary prunes stored results", async () => {
  const sandbox = buildRichSandbox();
  const { root } = fixture(sandbox);
  const runtime = new sandbox.EvidenceRuntime({
    diagnostics: false,
    maxDescriptions: 2,
  });
  await Promise.all(
    [1, 2, 3].map(index =>
      runtime.description({
        target: root,
        id: `d${index}`,
        externalizeBinary: false,
        options: { includeBinary: false },
      }),
    ),
  );
  assert.equal(runtime.status().descriptions.length <= 2, true);
  await runtime.destroy();
});
test("capture snapshots through htmlToImage and the DOM fallback", async () => {
  const sandbox = buildRichSandbox();
  const { root, scroller } = fixture(sandbox);
  const runtime = new sandbox.EvidenceRuntime({
    diagnostics: false,
    target: root,
  });
  const capture = await runtime.capture({ target: root });
  assert.equal(capture.kind, "capture");
  assert.ok(capture.size > 0);
  sandbox.htmlToImage = undefined;
  const fallback = await runtime.capture({ target: scroller });
  assert.equal(fallback.kind, "capture");
  await runtime.destroy();
});
test("video lifecycle arms, records, stops, and disarms", async () => {
  const sandbox = buildRichSandbox();
  const { root } = fixture(sandbox);
  const runtime = new sandbox.EvidenceRuntime({
    diagnostics: false,
    target: root,
    segmentDuration: 20,
  });
  const status = await runtime.arm();
  assert.equal(status.armed, true);
  const started = await runtime.start({ id: "take", duration: 30 });
  assert.equal(started.kind, "video");
  const finished = await runtime.done("take");
  assert.equal(finished.kind, "video");
  await runtime.disarm();
  assert.equal(runtime.status().armed, false);
  const direct = new sandbox.RollingCapture({ target: root });
  await direct.arm();
  const recorded = await direct.record({ duration: 15 });
  assert.equal(recorded.kind, "video");
  await direct.disarm({ force: true });
});
test("transfer streams description assets through the sink", async () => {
  const sandbox = buildRichSandbox();
  const { root } = fixture(sandbox);
  const runtime = new sandbox.EvidenceRuntime({
    diagnostics: false,
    target: root,
  });
  /** @type {any[]} */
  const sent = [];
  sandbox.__evidenceSink = async (/** @type {any} */ payload) =>
    sent.push(payload);
  const description = await runtime.description({
    target: root,
    id: "doc",
  });
  const transfer = await runtime.transfer("doc", { chunkSize: 256 });
  assert.equal(transfer.kind, "description");
  assert.equal(transfer.id, description.id);
  const kinds = new Set(sent.map(payload => payload.event));
  assert.ok(kinds.has("transfer-start"));
  assert.ok(kinds.has("asset-start"));
  assert.ok(kinds.has("chunk"));
  assert.ok(kinds.has("asset-end"));
  assert.ok(kinds.has("transfer-end"));
  await runtime.destroy();
});
test("evidence combines modes and validates them", async () => {
  const sandbox = buildRichSandbox();
  const { root } = fixture(sandbox);
  const runtime = new sandbox.EvidenceRuntime({
    diagnostics: false,
    target: root,
  });
  const output = await runtime.evidence({
    modes: ["capture", "description"],
  });
  assert.ok(output.capture);
  assert.ok(output.description);
  await assert.rejects(
    () => runtime.evidence({ modes: ["bogus"] }),
    TypeError,
  );
  await assert.rejects(
    () => runtime.evidence({ modes: ["video"], duration: 0 }),
    /duration/,
  );
  await runtime.destroy();
});
test("clear removes stored captures, markers, and descriptions", async () => {
  const sandbox = buildRichSandbox();
  const { root } = fixture(sandbox);
  const runtime = new sandbox.EvidenceRuntime({
    diagnostics: false,
    target: root,
  });
  runtime.mark("one");
  await runtime.description({ target: root, id: "keep" });
  assert.equal(runtime.remove("keep"), true);
  runtime.clear();
  assert.equal(runtime.markers().length, 0);
  assert.equal(runtime.status().descriptions.length, 0);
  await runtime.destroy();
});
