import assert from "node:assert/strict";
import test from "node:test";
import { webcrypto } from "node:crypto";
import { buildSandbox } from "../../scene_description/js/sandbox-dom.mjs";
import { RequestStudio } from "../../../../packages/actions/action_rest/request_studio.js";
const IDS = [
  "studio",
  "transport",
  "method",
  "url",
  "resolved-url",
  "send",
  "body",
  "body-format",
  "body-format-action",
  "body-tree",
  "body-source",
  "body-mode",
  "response-text",
  "response-view",
  "response-meta",
  "copy",
  "capture",
  "capture-path",
  "capture-name",
  "variables",
  "variables-toggle",
  "variables-close",
  "variable-list",
  "variable-add",
  "autocomplete",
  "toast",
  "row-template",
  "variable-template",
  "params-table",
  "headers-table",
  "cookies-table",
  "params-count",
  "headers-count",
  "cookies-count",
  "messages-count",
  "ws-protocols",
  "ws-state",
  "ws-log",
  "ws-message",
  "ws-send",
  "ws-clear",
];
/** @typedef {import("../../scene_description/js/sandbox-dom.mjs").SandboxGlobal} SandboxGlobal */
/**
 * @typedef {object} FakeSelection
 * @property {boolean} isCollapsed Collapse flag.
 * @property {number} rangeCount Range count.
 * @property {Node | null} anchorNode Anchor node.
 * @property {number} anchorOffset Anchor offset.
 * @property {Node | null} focusNode Focus node.
 * @property {number} focusOffset Focus offset.
 * @property {Range[]} ranges Active ranges.
 * @property {(index: number) => Range} getRangeAt
 * @property {() => void} removeAllRanges
 * @property {(range: Range) => void} addRange
 * @property {() => void} deleteFromDocument
 * @property {() => void} collapse
 * @property {() => void} extend
 * @property {() => void} setBaseAndExtent
 * @property {() => void} selectAllChildren
 * @property {() => void} empty
 */
/**
 * @typedef {HTMLElement & {
 *   value: string,
 *   checked: boolean,
 *   content: HTMLElement
 * }} FixtureElement
 */
/** Minimal beforeinput event carrying inputType and data. */
class InputEvent extends Event {
  /** @type {string | null} */
  inputType;
  /** @type {string | null} */
  data;
  /**
   * @param {string} type Event type.
   * @param {{inputType?: string, data?: string | null} & EventInit} [init]
   *   Event init.
   */
  constructor(type, init = {}) {
    super(type, init);
    this.inputType = init.inputType ?? null;
    this.data = init.data ?? null;
  }
}
/** WebSocket stand-in recording frames and exposing fake lifecycle helpers. */
class FakeWebSocket extends EventTarget {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;
  /** @type {FakeWebSocket[]} */
  static instances = [];
  /** @type {string} */
  url;
  /** @type {string[]} */
  protocols;
  /** @type {string} */
  protocol;
  /** @type {number} */
  readyState;
  /** @type {string[]} */
  sent;
  /**
   * @param {string | URL} url Socket URL.
   * @param {string[] | string} [protocols] Offered sub-protocols.
   */
  constructor(url, protocols = []) {
    super();
    this.url = String(url);
    this.protocols = Array.isArray(protocols) ? protocols : [protocols];
    this.protocol = this.protocols[0] ?? "";
    this.readyState = FakeWebSocket.CONNECTING;
    this.sent = [];
    FakeWebSocket.instances.push(this);
  }
  /**
   * Record a sent frame.
   *
   * @param {unknown} message Frame payload.
   */
  send(message) {
    this.sent.push(String(message));
  }
  /**
   * Close the socket and dispatch a close event.
   *
   * @param {number} [code] Close code.
   * @param {string} [reason] Close reason.
   */
  close(code = 1000, reason = "") {
    this.readyState = FakeWebSocket.CLOSED;
    this.dispatchEvent(Object.assign(new Event("close"), { code, reason }));
  }
  /** Mark the socket open and dispatch an open event. */
  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.dispatchEvent(new Event("open"));
  }
  /**
   * Dispatch a received frame.
   *
   * @param {unknown} data Frame payload.
   */
  receive(data) {
    this.dispatchEvent(Object.assign(new Event("message"), { data }));
  }
  /** Dispatch an error event. */
  fail() {
    this.dispatchEvent(new Event("error"));
  }
}
/**
 * Build a mutable selection stand-in.
 *
 * @param {Document} document Owning document.
 * @returns {FakeSelection} Mutable selection stand-in.
 */
const makeSelection = document => ({
  isCollapsed: true,
  rangeCount: 1,
  anchorNode: null,
  anchorOffset: 0,
  focusNode: null,
  focusOffset: 0,
  ranges: [],
  getRangeAt(index) {
    return this.ranges[index] ?? document.createRange();
  },
  removeAllRanges() {
    this.ranges = [];
  },
  addRange(range) {
    this.ranges.push(range);
  },
  deleteFromDocument() {
    this.getRangeAt(0).deleteContents();
  },
  collapse: () => {},
  extend: () => {},
  setBaseAndExtent: () => {},
  selectAllChildren: () => {},
  empty: () => {},
});
/**
 * Install a fresh fake DOM, element fixture, and studio instance.
 *
 * @param {Record<string, unknown>} [seedOverrides] Seed overrides.
 * @returns {{studio: RequestStudio, document: Document,
 *   selection: FakeSelection, sandbox: SandboxGlobal,
 *   clipboard: {written: string[]}}} Fixture handles.
 */
const build = (seedOverrides = {}) => {
  const sandbox = buildSandbox({ webcrypto });
  const document = /** @type {Document} */ (
    /** @type {unknown} */ (sandbox.document)
  );
  const selection = makeSelection(document);
  selection.addRange(document.createRange());
  /** @type {{written: string[]}} */
  const clipboard = { written: [] };
  const navigatorStub = {
    ...sandbox.navigator,
    clipboard: {
      writeText: async (/** @type {string} */ text) =>
        clipboard.written.push(text),
    },
  };
  Object.assign(globalThis, {
    document,
    Text: sandbox.Text,
    Node: sandbox.Node,
    Element: sandbox.Element,
    HTMLElement: sandbox.HTMLElement,
    HTMLInputElement: sandbox.HTMLInputElement,
    HTMLButtonElement: sandbox.HTMLButtonElement,
    HTMLSelectElement: sandbox.HTMLSelectElement,
    HTMLFormElement: sandbox.HTMLFormElement,
    HTMLAnchorElement: sandbox.HTMLAnchorElement,
    SVGElement: sandbox.SVGElement,
    Range: sandbox.Range,
    MutationObserver: sandbox.MutationObserver,
    InputEvent,
    WebSocket: FakeWebSocket,
    performance: sandbox.performance,
  });
  Object.defineProperty(globalThis, "navigator", {
    value: navigatorStub,
    configurable: true,
    writable: true,
  });
  Object.defineProperty(globalThis, "window", {
    value: {
      getSelection: () => selection,
      innerWidth: sandbox.innerWidth,
      innerHeight: sandbox.innerHeight,
      location: sandbox.location,
      document,
      addEventListener: () => {},
      removeEventListener: () => {},
    },
    configurable: true,
    writable: true,
  });
  for (const id of IDS) {
    const element = document.createElement("div");
    element.id = id;
    document.body.append(element);
  }
  /**
   * Look up a fixture element by id.
   *
   * @param {string} id Element id.
   * @returns {FixtureElement} The mounted fixture element.
   */
  const el = id => {
    const found = document.getElementById(id);
    assert.ok(found, `missing fixture element ${id}`);
    return /** @type {FixtureElement} */ (found);
  };
  el("transport").value = "http";
  el("method").value = "POST";
  el("body-format").value = "json";
  el("ws-protocols").value = "";
  el("send").append(document.createTextNode(" Send "));
  el("ws-state").append(document.createTextNode(" idle"));
  el("response-meta").append(document.createTextNode(" idle"));
  for (const mode of ["source", "tree"]) {
    const button = document.createElement("button");
    button.setAttribute("data-body-mode", mode);
    el("body-mode").append(button);
  }
  for (const name of ["params", "headers", "cookies", "body", "messages"]) {
    const tab = document.createElement("button");
    tab.setAttribute("data-tab", name);
    document.body.append(tab);
    const panel = document.createElement("div");
    panel.setAttribute("data-panel", name);
    document.body.append(panel);
  }
  const bodyTab = document.createElement("button");
  bodyTab.id = "body-tab";
  document.body.append(bodyTab);
  const rowTemplate = el("row-template");
  rowTemplate.content = document.createElement("div");
  const row = document.createElement("div");
  row.className = "row";
  const enabled = document.createElement("input");
  enabled.className = "enabled";
  const key = document.createElement("div");
  key.className = "key token-editor";
  const value = document.createElement("div");
  value.className = "value token-editor";
  const remove = document.createElement("button");
  remove.className = "delete";
  row.append(enabled, key, value, remove);
  rowTemplate.content.append(row);
  const variableTemplate = el("variable-template");
  variableTemplate.content = document.createElement("div");
  const variable = document.createElement("div");
  variable.className = "variable";
  const vName = document.createElement("input");
  vName.className = "v-name";
  const vValue = document.createElement("input");
  vValue.className = "v-value";
  const secret = document.createElement("button");
  secret.className = "secret";
  const vDelete = document.createElement("button");
  vDelete.className = "v-delete";
  variable.append(vName, vValue, secret, vDelete);
  variableTemplate.content.append(variable);
  const empty = document.createElement("p");
  empty.className = "ws-empty";
  el("ws-log").append(empty);
  FakeWebSocket.instances = [];
  const studio = new RequestStudio({
    rows: {
      params: [{ enabled: true, key: "id", value: "{{user/id}}" }],
      headers: [{ enabled: true, key: "X-Trace", value: "1" }],
      cookies: [{ enabled: false, key: "session", value: "abc" }],
    },
    variables: [
      { name: "alpha", value: "A", secret: false },
      { name: "api/users/x", value: "ux", secret: false },
      { name: "api/keys/y", value: "ky", secret: true },
      { name: "user/id", value: "42", secret: false },
    ],
    url: "https://api.test/users",
    body: '{"a":1}',
    ...seedOverrides,
  });
  return { studio, document, selection, sandbox, clipboard };
};
/**
 * Build a minimal keyboard-event stand-in.
 *
 * @param {string} key Pressed key.
 * @param {Element} target Event target.
 * @returns {KeyboardEvent & {prevented: boolean}} Synthetic key event.
 */
const keydownEvent = (key, target) => {
  const event = {
    key,
    target,
    prevented: false,
    preventDefault: () => {
      event.prevented = true;
    },
  };
  return /** @type {KeyboardEvent & {prevented: boolean}} */ (
    /** @type {unknown} */ (event)
  );
};
test("editor input updates the url preview and detects completion", () => {
  const { studio, document, selection } = build();
  const editor = studio.el.url;
  editor.classList.add("token-editor");
  editor.replaceChildren(document.createTextNode("bad url"));
  assert.equal(studio.el.resolved_url.textContent.includes("api.test"), true);
  RequestStudio.setEditorText(editor, "call @a");
  studio.detectCompletion(editor);
  assert.equal(studio.el.autocomplete.hidden, true);
  const node = document.createTextNode("call @a");
  editor.replaceChildren(node);
  selection.anchorNode = node;
  selection.anchorOffset = 7;
  studio.detectCompletion(editor);
  assert.equal(studio.completion.query, "a");
  const segments = studio.completion.items.map(item => item.segment);
  assert.deepEqual([...segments].sort(), ["alpha", "api"]);
  assert.equal(studio.el.autocomplete.hidden, false);
});
test("completion tree expands, navigates, and commits variables", () => {
  const { studio, document, selection } = build();
  const editor = studio.el.url;
  editor.classList.add("token-editor");
  const node = document.createTextNode("call @a");
  editor.replaceChildren(node);
  selection.anchorNode = node;
  selection.anchorOffset = 7;
  studio.detectCompletion(editor);
  const branch = studio.completion.items.find(item => item.branch);
  assert.ok(branch);
  studio.choose(branch);
  const children = studio.completion.items.filter(item => item.depth === 1);
  assert.deepEqual(children.map(item => item.segment), ["keys", "users"]);
  /**
   * Select the completion item at a path.
   *
   * @param {string} path Completion path.
   */
  const select = path => {
    studio.completion.selected = studio.completion.items.findIndex(
      item => item.path === path,
    );
  };
  select("api");
  assert.equal(studio.treeKey("ArrowLeft"), true);
  assert.equal(studio.completion.expanded.has("api"), false);
  select("api");
  assert.equal(studio.treeKey("ArrowRight"), true);
  assert.equal(studio.completion.expanded.has("api"), true);
  select("api");
  assert.equal(studio.treeKey("ArrowRight"), true);
  assert.ok(studio.completion.selected > 0);
  const nested = studio.completion.items.find(item => item.depth === 1);
  assert.ok(nested);
  select(nested.path);
  assert.equal(studio.treeKey("ArrowLeft"), true);
  studio.move(1);
  const open = studio.completion.items.find(
    item => item.branch && studio.completion.expanded.has(item.path),
  );
  assert.ok(open);
  studio.toggleBranch(open, false);
  assert.equal(studio.completion.expanded.has(open.path), false);
  const event = keydownEvent("ArrowDown", editor);
  studio.keydown(event);
  assert.equal(event.prevented, true);
  const leaf = studio.completion.items.find(
    item => !item.branch && item.path === "alpha",
  );
  assert.ok(leaf);
  studio.completion.selected = studio.completion.items.indexOf(leaf);
  selection.anchorOffset = 7;
  studio.chooseSelected();
  assert.ok(editor.querySelector(".token-pill"));
  assert.equal(studio.el.autocomplete.hidden, true);
});
test("exact-name commit, escape, and empty detection paths", () => {
  const { studio, document, selection } = build();
  const editor = studio.el.url;
  editor.classList.add("token-editor");
  const node = document.createTextNode("x @alpha");
  editor.replaceChildren(node);
  selection.anchorNode = node;
  selection.anchorOffset = 8;
  studio.detectCompletion(editor);
  const enter = keydownEvent("Enter", editor);
  studio.keydown(enter);
  assert.equal(enter.prevented, true);
  assert.ok(editor.querySelector("[data-token='alpha']"));
  const plain = document.createTextNode("no query");
  editor.replaceChildren(plain);
  selection.anchorNode = plain;
  selection.anchorOffset = 3;
  studio.detectCompletion(editor);
  assert.equal(studio.completion.editor, null);
  selection.anchorNode = null;
  studio.detectCompletion(editor);
  assert.equal(studio.completion.editor, null);
});
test("token selection, dissolution, and adjacent-token edits", () => {
  const { studio, document, selection } = build();
  const editor = studio.el.url;
  editor.classList.add("token-editor");
  RequestStudio.setEditorText(editor, "call {{alpha}}");
  const token = editor.querySelector(".token-pill");
  assert.ok(token);
  const down = {
    target: token,
    prevented: false,
    preventDefault() {
      this.prevented = true;
    },
  };
  studio.tokenPointerDown(
    /** @type {PointerEvent} */ (/** @type {unknown} */ (down)),
  );
  assert.equal(studio.selectedToken, token);
  assert.equal(token.classList.contains("token-selected"), true);
  const remove = keydownEvent("Backspace", editor);
  studio.keydown(remove);
  assert.equal(remove.prevented, true);
  assert.equal(studio.selectedToken, null);
  assert.equal(editor.querySelector(".token-pill"), null);
  RequestStudio.setEditorText(editor, "{{beta}}x");
  const pill = editor.querySelector(".token-pill");
  const boundary = pill?.nextSibling ?? null;
  selection.isCollapsed = true;
  selection.anchorNode = boundary;
  selection.anchorOffset = 1;
  assert.equal(studio.dissolveAdjacentToken(editor, "Backspace"), true);
  assert.equal(editor.querySelector(".token-pill"), null);
  assert.equal(
    RequestStudio.adjacentToken(
      /** @type {Selection} */ (/** @type {unknown} */ (selection)),
      "Backspace",
    ),
    null,
  );
  const text = document.createTextNode("ab");
  selection.anchorNode = text;
  selection.anchorOffset = 0;
  assert.equal(
    RequestStudio.adjacentToken(
      /** @type {Selection} */ (/** @type {unknown} */ (selection)),
      "Backspace",
    ),
    null,
  );
  studio.outside(
    /** @type {PointerEvent} */ (
      /** @type {unknown} */ ({ target: document.body })
    ),
  );
});
test("beforeInput, paste, and clipboard serialization", () => {
  const { studio, document, selection } = build();
  const editor = studio.el.url;
  editor.classList.add("token-editor");
  RequestStudio.setEditorText(editor, "a{{alpha}}b");
  const paragraph = new InputEvent("beforeinput", {
    inputType: "insertParagraph",
  });
  let prevented = false;
  paragraph.preventDefault = () => {
    prevented = true;
  };
  Object.defineProperty(paragraph, "target", { value: editor });
  studio.beforeInput(paragraph);
  assert.equal(prevented, true);
  const multiline = document.createElement("div");
  multiline.classList.add("token-editor");
  multiline.setAttribute("aria-multiline", "true");
  RequestStudio.setEditorText(multiline, "x\ny");
  assert.equal(RequestStudio.editorText(multiline), "x\ny");
  selection.isCollapsed = true;
  selection.anchorNode = editor;
  selection.anchorOffset = 0;
  const insert = new InputEvent("beforeinput", {
    inputType: "insertText",
    data: "z",
  });
  Object.defineProperty(insert, "target", { value: editor });
  studio.beforeInput(insert);
  assert.equal(editor.firstChild?.textContent, "z");
  /** @type {string[]} */
  const pasteText = [];
  RequestStudio.paste(
    /** @type {ClipboardEvent} */ (
      /** @type {unknown} */ ({
        target: editor,
        clipboardData: { getData: () => "p\nq" },
        preventDefault: () => pasteText.push("prevented"),
      })
    ),
  );
  const pills = editor.querySelectorAll(".token-pill");
  assert.ok(pills.length >= 1);
  selection.isCollapsed = false;
  selection.anchorNode = editor.firstChild;
  selection.focusNode = editor.lastChild;
  const range = document.createRange();
  /** @type {{startContainer: Node | null}} */ (range).startContainer =
    editor;
  selection.ranges = [range];
  /** @type {string[]} */
  const copied = [];
  /**
   * Build a clipboard-event stand-in targeting the editor.
   *
   * @returns {ClipboardEvent} Synthetic clipboard event.
   */
  const clipboardEvent = () =>
    /** @type {ClipboardEvent} */ (
      /** @type {unknown} */ ({
        target: editor,
        clipboardData: {
          /**
           * Record the serialized payload.
           *
           * @param {string} kind MIME kind.
           * @param {string} text Payload text.
           */
          setData: (kind, text) => {
            assert.ok(kind);
            copied.push(text);
          },
        },
        preventDefault: () => {},
      })
    );
  studio.clipboard(clipboardEvent(), false);
  assert.equal(copied[0]?.includes("alpha"), true);
  studio.clipboard(clipboardEvent(), true);
});
test("rows add, edit, and delete through rendered controls", () => {
  const { studio, document } = build();
  const before = studio.rows.params.length;
  studio.addRow("params");
  assert.equal(studio.rows.params.length, before + 1);
  studio.changeRow("headers", 0, "value", "2");
  assert.equal(studio.rows.headers[0]?.value, "2");
  studio.changeRow("headers", 9, "key", "x");
  const table = studio.el.params_table;
  const deleteButton = table.querySelector(".delete");
  assert.ok(deleteButton);
  deleteButton.dispatchEvent(new Event("click"));
  assert.equal(studio.rows.params.length, before);
  const enabledBox = table.querySelector(".enabled");
  assert.ok(enabledBox);
  /** @type {HTMLInputElement} */ (enabledBox).checked = false;
  enabledBox.dispatchEvent(new Event("change"));
  assert.equal(studio.rows.params[0]?.enabled, false);
  assert.equal(studio.el.params_count.textContent, "0");
  const variablesBefore = studio.variables.length;
  studio.addVariable();
  assert.equal(studio.variables.length, variablesBefore + 1);
  const input = [
    ...studio.el.variable_list.querySelectorAll(".v-name"),
  ].at(-1);
  assert.ok(input);
  /** @type {HTMLInputElement} */ (input).value = "renamed";
  input.dispatchEvent(new Event("input"));
  assert.equal(studio.variables.at(-1)?.name, "renamed");
  const secretButton = [
    ...studio.el.variable_list.querySelectorAll(".secret"),
  ].at(-1);
  assert.ok(secretButton);
  secretButton.dispatchEvent(new Event("click"));
  assert.equal(studio.variables.at(-1)?.secret, true);
  const vDelete = [
    ...studio.el.variable_list.querySelectorAll(".v-delete"),
  ].at(-1);
  assert.ok(vDelete);
  vDelete.dispatchEvent(new Event("click"));
  assert.equal(studio.variables.length, variablesBefore);
  studio.activate("headers");
  assert.equal(
    [...document.querySelectorAll("[data-tab]")]
      .find(tab => tab.getAttribute("data-tab") === "headers")
      ?.classList.contains("active"),
    true,
  );
  studio.toggleVariables();
  studio.toggleVariables(false);
});
test("http send resolves variables and renders json response", async () => {
  const { studio } = build();
  /** @type {{url: string, init: RequestInit | undefined} | undefined} */
  let request;
  globalThis.fetch = /** @type {typeof fetch} */ (
    /** @type {unknown} */ (
      async (
        /** @type {RequestInfo | URL} */ url,
        /** @type {RequestInit | undefined} */ init,
      ) => {
        request = { url: String(url), init };
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          headers: new Headers({ "content-type": "application/json" }),
          text: async () => '{"a":1,"b":[2,3],"c":"x"}',
        };
      }
    )
  );
  await studio.send();
  assert.equal(request?.init?.method, "POST");
  assert.equal(request?.url.includes("id=42"), true);
  assert.equal(
    (/** @type {Headers | undefined} */ (request?.init?.headers))?.get(
      "Content-Type",
    ),
    "application/json",
  );
  assert.equal(
    studio.el.response_view.classList.contains("json-mode"),
    true,
  );
  assert.ok(studio.el.response_text.querySelector(".json-node"));
  globalThis.fetch = /** @type {typeof fetch} */ (
    /** @type {unknown} */ (
      async () => {
        throw new Error("offline");
      }
    )
  );
  await studio.send();
  assert.equal(studio.el.response_meta.className, "error");
  RequestStudio.setEditorText(studio.el.url, "not a url");
  await studio.send();
  assert.equal(
    studio.el.response_text.textContent.includes("Invalid URL"),
    true,
  );
});
test("websocket lifecycle sends, logs, and clears frames", () => {
  const { studio } = build();
  studio.el.transport.value = "websocket";
  RequestStudio.setEditorText(studio.el.url, "wss://api.test/socket");
  studio.setTransport();
  assert.equal(studio.el.method.hidden, true);
  studio.el.ws_protocols.value = "chat, super";
  studio.toggleWebSocket();
  const socket = FakeWebSocket.instances[0];
  assert.ok(socket);
  assert.equal(socket.url, "wss://api.test/socket?id=42");
  assert.deepEqual(socket.protocols, ["chat", "super"]);
  socket.open();
  assert.equal(studio.el.ws_send.disabled, false);
  RequestStudio.setEditorText(studio.el.ws_message, "hi {{alpha}}");
  studio.sendWebSocketMessage();
  assert.deepEqual(socket.sent, ["hi A"]);
  socket.receive("hello");
  socket.receive(new Uint8Array([1, 2]));
  assert.equal(studio.wsMessageCount >= 3, true);
  socket.fail();
  socket.close(1000, "bye");
  assert.equal(studio.socket, null);
  studio.clearWebSocketLog();
  assert.equal(studio.el.messages_count.textContent, "0");
  assert.ok(studio.el.ws_log.querySelector(".ws-empty"));
  RequestStudio.setEditorText(studio.el.url, "ftp://bad");
  studio.toggleWebSocket();
  assert.equal(
    studio.el.ws_state.getAttribute("data-state"),
    "error",
  );
});
test("json tree capture opens, places, and saves variables", () => {
  const { studio } = build();
  studio.showJson({ user: { id: 42 } });
  const pick = [
    ...studio.el.response_text.querySelectorAll(".json-pick"),
  ].find(button => button.getAttribute("data-path") === "$.user.id");
  assert.ok(pick);
  studio.captureJson(/** @type {HTMLButtonElement} */ (pick));
  assert.equal(studio.el.capture.hidden, false);
  assert.equal(studio.el.capture_path.textContent, "$.user.id");
  studio.el.capture_name.value = "user/id";
  studio.saveCaptured(
    /** @type {Event} */ (
      /** @type {unknown} */ ({ preventDefault: () => {} })
    ),
  );
  const saved = studio.variables.find(variable => variable.name === "user/id");
  assert.equal(saved?.value, "42");
  assert.equal(studio.el.capture.hidden, true);
  studio.el.capture_name.value = "bad name!!";
  studio.captureJson(/** @type {HTMLButtonElement} */ (pick));
  studio.saveCaptured(
    /** @type {Event} */ (
      /** @type {unknown} */ ({ preventDefault: () => {} })
    ),
  );
  assert.equal(
    studio.el.toast.textContent.includes("letters"),
    true,
  );
  studio.closeCapture({ focusResponse: true });
  assert.equal(studio.el.capture.hidden, true);
});
test("body modes, formatting, and xml trees", () => {
  const { studio, document } = build();
  studio.el.body_format.value = "json";
  RequestStudio.setEditorText(studio.el.body, '{"z":2,"a":1}');
  studio.setBodyMode("tree");
  assert.equal(studio.el.body_tree.hidden, false);
  assert.ok(studio.el.body_tree.querySelector(".json-node"));
  studio.formatBodySource();
  assert.equal(
    RequestStudio.editorText(studio.el.body).includes("\n"),
    true,
  );
  RequestStudio.setEditorText(studio.el.body, "{bad");
  studio.refreshBodyTree();
  assert.equal(studio.el.body_tree.getAttribute("data-valid"), "false");
  studio.formatBodySource();
  assert.equal(
    studio.el.toast.textContent.includes("Cannot format"),
    true,
  );
  globalThis.DOMParser = /** @type {typeof DOMParser} */ (
    /** @type {unknown} */ (
      class {
        /**
         * Parse an XML source string into a fake document shape.
         *
         * @param {string} source XML source.
         * @returns {{documentElement: Element | null,
         *   querySelector: () => Element | null}} Parsed document.
         */
        parseFromString(source) {
          let index = 0;
          /**
           * Parse one element at the current cursor.
           *
           * @returns {Element | null} Parsed element, if present.
           */
          const parseElement = () => {
            if (source[index] !== "<" || source[index + 1] === "/")
              return null;
            const open = /^<(\w+)((?:\s+\w+="[^"]*")*)\s*(\/?)>/.exec(
              source.slice(index),
            );
            if (!open) return null;
            index += open[0].length;
            const node = document.createElement(open[1] ?? "span");
            for (const attr of
              open[2]?.trim().split(/\s+/).filter(Boolean) ?? []) {
              const [name, value] = attr.split("=");
              node.setAttribute(name ?? "", (value ?? "").replace(/^"|"$/g, ""));
            }
            if (open[3] === "/") return node;
            while (index < source.length) {
              if (source.startsWith("</", index)) {
                index = source.indexOf(">", index) + 1;
                break;
              }
              if (source[index] === "<") {
                const child = parseElement();
                if (!child) break;
                node.append(child);
              } else {
                const next = source.indexOf("<", index);
                const text = source.slice(
                  index,
                  next < 0 ? source.length : next,
                );
                index = next < 0 ? source.length : next;
                if (text.trim())
                  node.append(document.createTextNode(text));
              }
            }
            return node;
          };
          const root = parseElement();
          return {
            documentElement: root,
            querySelector: () =>
              root ? null : document.createElement("parsererror"),
          };
        }
      }
    )
  );
  studio.el.body_format.value = "xml";
  RequestStudio.setEditorText(studio.el.body, '<root a="1">text</root>');
  studio.refreshBodyTree();
  assert.equal(studio.el.body_tree.getAttribute("data-valid"), "true");
  const formatted = RequestStudio.prettyXml("<a><b>t</b></a>");
  assert.equal(formatted.toLowerCase().includes("<b>"), true);
  studio.el.body_format.value = "text";
  studio.refreshBodyTree();
  assert.equal(studio.el.body_mode.hidden, true);
});

test("copy, toast, and helper paths", async () => {
  const { studio, clipboard } = build();
  studio.el.response_text.textContent = "payload";
  await studio.copy();
  assert.deepEqual(clipboard.written, ["payload"]);
  assert.equal(studio.el.toast.hidden, false);
  studio.setMethodTone();
  assert.equal(studio.el.method.getAttribute("data-method"), "POST");
  studio.el.transport.value = "websocket";
  RequestStudio.setEditorText(studio.el.url, "wss://api.test/s");
  studio.updateUrl();
  assert.equal(
    studio.el.resolved_url.textContent.startsWith("wss://"),
    true,
  );
  const headers = studio.headers();
  assert.equal(headers.get("X-Trace"), "1");
  assert.equal(studio.resolve("{{alpha}}!"), "A!");
  assert.equal(studio.map().get("alpha"), "A");
});
