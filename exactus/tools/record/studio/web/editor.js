import { DockGrid } from "./dock-grid.js";
import { askInputs, askLabels } from "./ask-inputs.js";
import { buildCard, cardSpec, guardParts, producedVariables, producersOf, renderSentence } from "./action-card.js";
import { flowInputsField } from "./flow-inputs.js";
import { openFloatingPanel, openTokenEditor } from "./token-editor.js";
import { variableInspector } from "./variable-inspector.js";
import { AnalogClock } from "../../../../packages/widgets/widget_clock/index.js";
import { StudioTransport } from "./transport.js";
import { LiveTarget } from "./live-target.js";
import { SettingsSurface } from "./settings.js";
import { iconElement, iconMarkup, watchIcons } from "./icons.js";
import { DISMISSED_KEY, renderWelcome, shouldWelcome } from "./welcome.js";
import { ProjectActions } from "./project-actions.js";
import { ProjectBar } from "./project-bar.js";
import { ProjectSection } from "./project-section.js";
import { renderFlowList } from "./flow-list.js";
import { attachConditionField } from "./condition-field.js";
import { selectorLiveTools } from "./selector-live-tools.js";
import { bindSelectorReference } from "./selector-reference-field.js";
import { renderLastRun, worstStatus, causeSummary } from "./run-cause.js";
import {
  renderSeen,
  renderSelectorList,
  renderTestResult,
  selectorInspector,
} from "./selectors-panel.js";
import { groupCaptures, pairFor } from "./compare-pairs.js";
import {
  ACTION_DRAG_TYPE,
  actionCommand,
  configureActionForm,
  DEFAULT_GUARD,
  defaultActionCommand,
  definitionForEvent,
  editsInRow,
  renderActionCatalog,
  ACTION_PREFS_EVENT,
} from "./action-library.js";
import { conditionWidget } from "./javascript-action-widget.js";
import {
  graphNodes,
  graphLinks,
  graphBounds,
  graphSvg,
  graphConnectionInspector,
} from "./graph-surface.js";
/** @typedef {{id:string,label:string,start_ms:number}} EditorRecording */
/** @typedef {{id:string,name:string,device_modes?:string[],task_description?:string,expected_behavior?:string,capture_record_images?:boolean,capture_play_images?:boolean,events?:EditorEvent[],recordings?:EditorRecording[],parameters?:import("./flow-inputs.js").FlowInput[],outputs?:unknown[]}} EditorFlow */
/** @typedef {{event_id:string,status:string,unit?:{index:number,count:number},streams?:Array<{source:string,level:string,message:string}>,response?:any,error?:any,[field:string]:any}} RunRecord */
/** @typedef {{id:string,selector_id?:string,recording_group_id?:string|null,contract?:{postconditions?:Array<{id:string,label:string,kind:string,target?:string,expected?:string}>},layer?:string,label?:string,kind:string,selector?:string,url?:string,payload?:string,elapsed_ms?:number,output_variable?:string|null,when_expression?:string|null,incomplete?:boolean}} EditorEvent */
/** @typedef {{source:string,target:string,condition_expression?:string,priority?:number,max_traversals?:number,mode?:string}} EditorEdge */
/** @typedef {{id:string,status:string,failure_reason?:string,action_records?:RunRecord[],current_flow_id?:string,initial_flow_id:string,device_mode:string}} EditorRun */
/** @typedef {{id:string,flow_id:string,event_id:string,path:string,phase:string,width:number,height:number}} EditorScreenshot */
/** @typedef {{flows:EditorFlow[],edges?:EditorEdge[],runs?:EditorRun[],screenshots?:EditorScreenshot[]}} EditorWorkspace */
/** @typedef {{selector_id:string,name:string,expression:string,expected_count?:number|null,checks?:string[]}} EditorSelector */
/** @typedef {{condition_vocabulary?:ConditionTerm[],status?:string,error?:string,execution_run_id?:string|null,run_control?:{state:string,before_event_id:string|null},device_mode?:string,viewport?:{width:number,height:number},crawl?:{state?:string,action_id?:string,tool?:string,error?:string},target_url?:string,target_inspection?:{picked?:boolean,element?:{selector:string,text:string,rect:{x:number,y:number,width:number,height:number}}},recording_state?:string,target_state?:string,target_address?:string|null,dirty?:boolean,recorder_clients?:number,revision?:number,active_flow_id?:string,workspace?:EditorWorkspace&{profiles?:Array<{id:string,touch?:boolean}>},flows?:EditorFlow[],path?:string,selectors?:EditorSelector[],selector_usage?:Record<string,import("./selectors-panel.js").SelectorUse>,selector_test?:Record<string,unknown>}} EditorSnapshot */
/** @typedef {{protocol:number,id?:string,ok?:boolean,result?:EditorSnapshot,error?:string,event?:string,payload?:EditorSnapshot}} BridgeMessage */
/** @typedef {{resolve:(value:EditorSnapshot)=>void,reject:(reason:Error)=>void,timer?:number}} PendingRequest */
/** Browser-side studio editor application controller.
 */
export class EditorApp {
  /** @type {AnalogClock} */
  timelineClock;
  /** @type {LiveTarget|null} */
  liveTarget = null;
  /** Smallest size, in pixels, each panel keeps while docks are resized.
   * @type {Readonly<Record<string,{width:number,height:number}>>}
   */
  static panelMinimums = Object.freeze({
    workspace: { width: 160, height: 120 },
    actions: { width: 260, height: 180 },
    steps: { width: 260, height: 160 },
    composition: { width: 280, height: 180 },
    target: { width: 240, height: 120 },
    properties: { width: 240, height: 140 },
    timeline: { width: 360, height: 120 },
    runs: { width: 240, height: 120 },
  });
  /** @type {DockGrid} */
  dock;
  /** @type {EditorWorkspace|null} */
  workspace = null;
  /** @type {string|null} */
  activeFlowId = null;
  /** @type {number} */
  revision = 0;
  /** The step the inspector shows; also the last one chosen. */
  _primary = "";
  /** The step a Shift-click range starts from. */
  _anchor = "";
  /** @type {Set<string>} Every selected step. */
  selectedEventIds = new Set();
  /** The step the inspector shows; also the last one chosen.
   * @returns {string}
   */
  get selectedEventId() {
    return this._primary;
  }
  /** Selecting one step by assignment replaces any larger selection.
   * @param {string} value
   */
  set selectedEventId(value) {
    this._primary = value;
    this._anchor = value;
    this.selectedEventIds = new Set(value ? [value] : []);
    if (value) this.selectedSelectorId = "";
  }
  inspectorKey = "";
  /** The selector open in the inspector: an id, "new" for a draft, or "". */
  selectedSelectorId = "";
  /** Latest live selector test, kept as text so a repeated snapshot is not news. */
  selectorTestText = "";
  /** Which selector the editor window is showing, so edits are not rebuilt away. */
  selectorEditorKey = "";
  /** @type {any} */
  selectorTest = null;
  selectorTesting = false;
  /** @type {((result:any)=>void)|null} */
  selectorTestSink = null;
  /** True while the running test reports only to its caller. */
  selectorTestSilent = false;
  /** Last silent stats request, so requests run one at a time. */
  statsQueue = Promise.resolve();
  /** @type {(((element:{selector:string,matches?:number,alternatives?:Array<{strategy:string,selector:string,matches:number}>})=>void)|null)} */
  selectorPickSink = null;
  /** Selector currently requested by action selection, to avoid repeat work. */
  actionHighlightKey = "";
  inspectorToken = 0;
  /** @type {Promise<any>|null} */
  selectorLibrary = null;
  waitDuration = "500";
  timelineTick = 1000;
  timelineScale = 6;
  /** Rem per second. The tick interval and its spacing are derived from it. */
  timelineZoom = 6;
  timelineTool = "select";
  timelineSnap = true;
  /** A drop ends with a click; ignore it so a drag never selects.
   */
  suppressClickUntil = 0;
  /** Set while a step or clip is dragged; redraws wait until it ends.
   */
  dragging = false;
  renderDeferred = false;
  /** @type {number|null} */
  timelineMarker = null;
  timelineCursorMs = 0;
  graphZoom = 1;
  graphConnectionSource = "";
  selectedGraphEdge = "";
  graphPanBound = false;
  compareMode = "side";
  compareKey = "";
  compareDecision = "";
  inspectorTab = "settings";
  dirty = false;
  workspaceView = "edit";
  /** @type {SettingsSurface|null} */
  settings = null;
  /** @type {ProjectActions|null} */
  projects = null;
  /** @type {ProjectBar|null} */
  projectBar = null;
  /** @type {ProjectSection|null} */
  projectSection = null;
  /** The browser is opened on its own once per page load, never after the user closed it. */
  autoOpened = false;
  userClosedBrowser = false;
  /** @type {EditorSnapshot|null} */
  snapshot = null;
  /** @type {number} */
  sequence = 0;
  /** @type {Map<string, PendingRequest>} */
  pending = new Map();
  /** Properties drafts are local to this tab until explicitly applied.
   * @type {Map<string, Record<string, string|boolean>>}
   */
  inspectorDrafts = new Map();
  /** In-row action editors kept while their settings are unchanged, so a draft survives a redraw.
   * @type {Map<string, {key: string, node: HTMLElement}>}
   */
  actionEditors = new Map();
  /** @type {{postMessage:(message:string)=>void,outbound:{connect:(handler:(message:string)=>void)=>void}}} */
  transport;
  /** function Object() { [native code] }
   * @param {{postMessage:(message:string)=>void,outbound:{connect:(handler:(message:string)=>void)=>void}}} transport
   */
  constructor(transport) {
    this.transport = transport;
    this.timelineClock = new AnalogClock(EditorApp.element("timecode"), {
      mode: "segment",
      template: "dd:dd:dd.ddd",
      live: false,
      recVisible: "hidden",
      recording: false,
      segmentGlowSize: 0,
      segmentOnDuration: 0,
      segmentOffDuration: 0,
      blinkSeparatorsOnSecond: false,
      background: "transparent",
      segmentOnColor: "--accent",
      segmentOffColor: "--timeline-clock-off",
      digitGap: 16,
      groupGap: 20,
      separatorWidth: 32,
      dotSize: 96,
      digitInset: 0,
      padding: 0,
    });
    this.updateTimelineClock(null);
    const timelineObserver = new ResizeObserver(this.updateTimelineCursor);
    timelineObserver.observe(EditorApp.element("timeline"));
    window.addEventListener("pagehide", event => {
      if (!event.persisted) {
        this.timelineClock.destroy();
        timelineObserver.disconnect();
      }
    });
    /** @type {Set<string>} */
    this.collapsedRecordings = new Set();
    this.transport.outbound.connect(raw => this.receive(raw));
    EditorApp.migrateMockWorkspaceLayout();
    this.dock = new DockGrid({
      root: EditorApp.element("workbench"),
      minimums: EditorApp.panelMinimums,
      onStatus: message => {
        EditorApp.element("status").textContent = message;
      },
    });
    this.bind();
    this.command("workspace.snapshot");
    EditorApp.element("status").textContent = "Studio connected";
  }
  /** What the status bar says once a command has finished.
   * @type {Readonly<Record<string,string>>}
   */
  static doneMessages = Object.freeze({
    "demo.open": "Demo flow ready — run from Open demo",
    "browser.close": "Open the target browser to record or run tests.",
    "browser.navigate": "Page opened",
    "browser.open": "Opening the test browser",
    "crawl.cancel": "Discovery cancelled",
    "crawl.start": "Discovery started",
    "edge.add": "Flows connected",
    "edge.move": "Connection reordered",
    "edge.remove": "Connection removed",
    "edge.update": "Connection updated",
    "event.add": "Step added",
    "event.assert": "Check added",
    "event.assert.remove": "Check removed",
    "event.delete": "Step deleted",
    "event.duplicate": "Step duplicated",
    "selector.save": "Selector saved",
    "selector.delete": "Selector deleted",
    "selector.test": "Testing the selector on the page…",
    "event.move": "Step moved",
    "event.reorder": "Step moved",
    "event.retime": "Step retimed",
    "event.update": "Step saved",
    "flow.create": "Flow created",
    "flow.select": "Flow selected",
    "flow.update": "Flow saved",
    "recorder.pause": "Recording paused",
    "recorder.record": "Recording started",
    "recorder.stop": "Recording stopped",
    "run.cancel": "Run stopped",
    "run.play": "Run started",
    "run.pause": "Pausing before the next action",
    "run.resume": "Run continues",
    "run.step": "Running one action, then pausing",
    "viewport.preset": "Viewport changed",
    "workspace.open": "Project opened",
    "workspace.save": "Project saved",
    "workspace.snapshot": "Project loaded",
  });
  /** @param {string} command
   * @returns {string}
   */
  static doneMessage = command => EditorApp.doneMessages[command] ?? "Done";
  /** @param {string} id
   * @returns {HTMLElement}
   */
  static element = id => {
    const node = document.getElementById(id);
    if (!(node instanceof HTMLElement))
      throw new Error(`Missing editor element: ${id}`);
    return node;
  };
  /** The first line of an error: enough to name a failure in a small panel.
   * @param {unknown} text Raw error text, possibly a multi-line call log.
   * @returns {string} Its first non-empty line.
   */
  static headline = text =>
    String(text ?? "")
      .split("\n")
      .map(line => line.trim())
      .find(Boolean) ?? "";
  /** @param {string} value
   * @returns {string}
   */
  static escape = value =>
    String(value ?? "").replace(
      /[&<>"']/g,
      char =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[char] ?? char,
    );
  /** @param {string} name
   * @returns {string}
   */
  static icon = name => iconMarkup(name);
  /** Clone a static UI template without parsing runtime HTML strings.
   * @param {string} id Template element identifier.
   * @returns {DocumentFragment} Cloned template content.
   * @throws {Error} When the element is missing or not a template.
   */
  static template = id => {
    const template = EditorApp.element(id);
    if (!(template instanceof HTMLTemplateElement))
      throw new Error(`Missing template: ${id}`);
    return /** @type {DocumentFragment} */ (template.content.cloneNode(true));
  };
  /** Apply the mock-oriented default once while keeping the former layout recoverable.
   */
  static migrateMockWorkspaceLayout = () => {
    const contract = "default-layout-20261008m";
    if (localStorage.getItem("studio.layout-contract") === contract) return;
    for (const key of [
      "studio.panel-layout",
      "studio.panel-groups",
      "studio.dock-sizes",
      "studio.split-sizes",
    ]) {
      const value = localStorage.getItem(key);
      if (value) localStorage.setItem(`${key}.before-${contract}`, value);
      localStorage.removeItem(key);
    }
    localStorage.setItem("studio.layout-contract", contract);
  };
  /** @param {EditorEvent} event
   * @returns {string}
   */
  static eventIcon = event => {
    if (event.kind === "url_change") return "world";
    if (event.kind === "viewport") return "device-mobile";
    if (event.payload === "__screenshot__") return "camera";
    if (event.kind === "wait") return "clock";
    if (event.kind === "javascript") return "keyboard";
    if (event.kind === "input_text" || event.kind === "fill") return "keyboard";
    if (event.layer === "assertion") return "list-check";
    return "mouse";
  };
  /** @param {EditorEvent} event
   * @returns {string}
   */
  static eventDetail = event => {
    if (event.payload === "__screenshot__") return "Screenshot checkpoint";
    if (event.kind === "wait") return `${event.payload || "0"} ms`;
    const structured = EditorApp.structuredDetail(event.payload);
    const detail =
      event.selector || event.url || structured || event.payload || event.kind;
    // A subtitle that only repeats the title adds noise, not information.
    /** Normalise text for comparing a subtitle with its title.
     * @param {unknown} value
     * @returns {string}
     */
    const norm = value => String(value).replace(/\/+$/, "").toLowerCase();
    return norm(event.label || EditorApp.eventTitle(event)).includes(norm(detail))
      ? ""
      : detail;
  };
  /** Turn a JSON action payload into a readable phrase, or "" for plain text.
   * @param {string|undefined} payload
   * @returns {string}
   */
  static structuredDetail = payload => {
    if (!payload?.startsWith("{")) return "";
    try {
      const data = JSON.parse(payload);
      if (data.action === "rotate") return "Swap portrait and landscape";
      if (data.action === "resize") return `${data.width} × ${data.height} px`;
      return Object.entries(data)
        .map(([key, value]) => `${key.replace(/_/g, " ")}: ${value}`)
        .join(" · ");
    } catch {
      return "";
    }
  };
  /** @param {string} layer
   * @returns {string}
   */
  static layerIcon = layer => {
    if (layer === "navigation") return "world";
    if (layer === "network") return "arrows-join";
    if (layer === "assertion") return "list-check";
    if (layer === "timing") return "clock";
    if (layer === "javascript") return "code";
    if (layer === "screenshots") return "camera";
    if (layer === "diagnostics") return "circle-check";
    return "mouse";
  };
  /** @param {EditorEvent} event
   * @returns {string}
   */
  static eventTitle = event => {
    if (
      event.kind === "url_change" &&
      event.label === `Navigate to ${event.url}`
    )
      return event.url === "about:blank" ? "Open blank page" : "Open page";
    return event.label || event.kind;
  };
  /** What the Pause and Step controls can do for the current run state.
   * @param {EditorSnapshot|null|undefined} snapshot
   * @returns {{running:boolean,state:string,canPause:boolean,canStep:boolean,pauseLabel:string,pauseIcon:string}}
   */
  static runControls = snapshot => {
    const running = Boolean(snapshot?.execution_run_id);
    const state = snapshot?.run_control?.state ?? "running";
    const ready =
      (snapshot?.recorder_clients ?? 0) > 0 &&
      snapshot?.recording_state !== "recording";
    return {
      running,
      state,
      canPause: running && state === "running",
      canStep: running ? state === "paused" : ready,
      pauseLabel:
        running && state === "paused"
          ? "Continue"
          : state === "pausing"
            ? "Pausing…"
            : "Pause",
      pauseIcon: running && state === "paused" ? "player-play" : "player-pause",
    };
  };
  /** Show the Pause and Step controls of the timeline for the run state.
   * @param {EditorSnapshot} snapshot
   * @returns {void}
   */
  static syncRunControls = snapshot => {
    const controls = EditorApp.runControls(snapshot);
    const pause = EditorApp.element("timeline-pause");
    const step = EditorApp.element("timeline-step");
    if (!(pause instanceof HTMLButtonElement) || !(step instanceof HTMLButtonElement))
      return;
    const continues = controls.running && controls.state === "paused";
    pause.disabled = !(controls.canPause || continues);
    const pauseText = continues
      ? "Continue the run"
      : controls.state === "pausing"
        ? "Pausing after this action"
        : "Pause the run before its next action";
    pause.title = pauseText;
    pause.setAttribute("aria-label", pauseText);
    pause.querySelector("svg")?.setAttribute("data-icon", controls.pauseIcon);
    step.disabled = !controls.canStep;
    const stepText = controls.running
      ? "Run one more action, then pause"
      : "Start the flow paused and run its first action";
    step.title = stepText;
    step.setAttribute("aria-label", stepText);
  };
  /** What a variable holds, from the action that produces it.
   * @param {EditorEvent} event
   * @returns {string} A type label: Text, Number, Boolean, Dictionary or Any.
   */
  static variableType = event => {
    /** @type {{extract?:unknown,value_type?:unknown}} */
    let spec = {};
    try {
      const parsed = JSON.parse(String(event.payload ?? "{}"));
      if (parsed && typeof parsed === "object") spec = parsed;
    } catch {
      return "Any";
    }
    if (event.kind === "extract_value")
      return (
        { checked: "Boolean", int: "Number", float: "Number", count: "Number" }[
          String(spec.extract)
        ] ?? "Text"
      );
    if (event.kind === "set_variable")
      return (
        {
          boolean: "Boolean",
          integer: "Number",
          float: "Number",
          json: "Dictionary",
        }[String(spec.value_type)] ?? "Text"
      );
    return "Any";
  };
  /** Everything a step in this flow can read as a variable, with its type:
   * the flow's inputs first, then each action's named result.
   * @param {EditorFlow|undefined} flow
   * @returns {Array<{name:string,type:string,icon:string,tone:string}>}
   */
  static variableSources = flow => [
    ...(flow?.parameters ?? []).map(input => ({
      name: input.name,
      type:
        { integer: "Number", float: "Number", boolean: "Boolean", json: "Dictionary" }[
          input.value_type
        ] ?? "Text",
      icon: "download",
      tone: "silver",
    })),
    ...(flow?.events ?? []).flatMap(event => {
      const spec = cardSpec(event);
      return producedVariables(event).map(output => ({
        name: output.name,
        type: output.type === "Any" ? EditorApp.variableType(event) : output.type,
        icon: spec.icon,
        tone: spec.tone,
      }));
    }),
  ];
  /** Variables a step reads that neither the flow's inputs nor an earlier
   * step provide.
   * @param {EditorEvent[]} events
   * @param {number} index
   * @param {string[]} [inputs] Names of the flow's inputs.
   * @returns {string[]}
   */
  static missingVariables = (events, index, inputs = []) => {
    const known = new Set([
      ...inputs,
      ...events
        .slice(0, index)
        .flatMap(event => producedVariables(event).map(output => output.name)),
    ]);
    const source = /** @type {any} */ (events[index]);
    const text = [source.url, source.selector, source.payload, source.when_expression]
      .filter(value => typeof value === "string")
      .join("\n");
    /** @type {Set<string>} */
    const missing = new Set();
    for (const match of text.matchAll(/\{\{([^{}]+)\}\}/g)) {
      const token = match[1] ?? "";
      const base = /^([^.[|]+)/.exec(token)?.[1] ?? token;
      if (token.startsWith("ask:") || known.has(base)) continue;
      missing.add(base);
    }
    return [...missing];
  };
  /** Whether a step reads a variable produced by an earlier step. Only such
   * steps are drawn joined to the card above, as in Shortcuts.
   * @param {EditorEvent[]} events
   * @param {number} index
   * @returns {boolean}
   */
  static isConnected = (events, index) => {
    if (index === 0) return false;
    const names = events
      .slice(0, index)
      .flatMap(event => producedVariables(event).map(output => output.name));
    const source = /** @type {any} */ (events[index]);
    const text = [source.url, source.selector, source.payload, source.label, source.when_expression]
      .filter(value => typeof value === "string")
      .join("\n");
    return names.some(name => text.includes(`{{${name}`));
  };
  /** Recording parents worth showing. A flow is already the single ordered
   * chain of actions, so groups created only to wrap hand-added actions are
   * never shown as a parent; their steps simply belong to the flow.
   * @returns {EditorRecording[]}
   */
  visibleRecordings() {
    return (this.activeFlow()?.recordings ?? []).filter(
      group => group.label !== "Action chain",
    );
  }
  /** Return the currently active flow, falling back to the first flow.
   * @returns {EditorFlow|undefined} The active flow, if any exist.
   */
  activeFlow() {
    return (
      this.workspace?.flows.find(flow => flow.id === this.activeFlowId) ??
      this.workspace?.flows[0]
    );
  }
  /** Handle a raw bridge message delivered by the studio service.
   * @param {string} raw Serialized bridge message payload.
   * @returns {void}
   */
  receive(raw) {
    /** @type {BridgeMessage} */
    const msg = JSON.parse(raw);
    if (msg.event) {
      if (msg.event === "workspace.changed" && msg.payload)
        this.applySnapshot(msg.payload);
      if (msg.event === "target.inspected" && msg.payload?.target_inspection)
        this.liveTarget?.inspect(msg.payload.target_inspection);
      if (msg.event === "selector.tested" && msg.payload?.selector_test)
        this.onSelectorTested(msg.payload.selector_test);
      if (msg.event === "flow.result" && msg.payload) {
        EditorApp.element("status").textContent =
          msg.payload.error || `Test ${msg.payload.status}`;
        EditorApp.element("status").setAttribute(
          "data-state",
          msg.payload.status || "failed",
        );
      }
      return;
    }
    if (!msg.id) return;
    const request = this.pending.get(msg.id);
    if (!request) return;
    this.pending.delete(msg.id);
    window.clearTimeout(request.timer);
    if (msg.ok && msg.result) request.resolve(msg.result);
    else request.reject(new Error(msg.error ?? "Bridge request failed."));
  }
  /** Apply a workspace snapshot pushed by the studio service.
   * @param {EditorSnapshot} snapshot Workspace snapshot payload.
   * @returns {void}
   */
  applySnapshot(snapshot) {
    this.snapshot = snapshot;
    this.dirty = Boolean(snapshot.dirty);
    this.workspace =
      snapshot.workspace ?? /** @type {EditorWorkspace} */ (snapshot);
    this.revision = snapshot.revision ?? this.revision;
    if (snapshot.selector_test) this.onSelectorTested(snapshot.selector_test);
    this.activeFlowId =
      snapshot.active_flow_id ??
      this.activeFlowId ??
      this.workspace.flows[0]?.id ??
      null;
    this.projectBar?.render();
    this.projects?.dialogs.refreshGallery?.();
    this.renderWelcomeScreen();
    EditorApp.element("app").toggleAttribute("data-dirty", this.dirty);
    const recording = snapshot.recording_state === "recording";
    const modeRunning = Boolean(snapshot.execution_run_id);
    const recordButton = document.querySelector('[data-cmd="recorder.record"]');
    const pauseButton = document.querySelector('[data-cmd="recorder.pause"]');
    const stopButton = document.querySelector('[data-cmd="run.cancel"]');
    if (recordButton instanceof HTMLElement)
      recordButton.hidden = recording || modeRunning;
    const crawlButton = EditorApp.element("browser-crawl");
    crawlButton.hidden = recording || modeRunning;
    if (pauseButton instanceof HTMLElement) pauseButton.hidden = !recording;
    if (stopButton instanceof HTMLElement)
      stopButton.hidden = !recording && !modeRunning;
    EditorApp.renderBrowserBar(snapshot);
    EditorApp.syncRunControls(snapshot);
    this.autoOpenBrowser(snapshot);
    const connected = (snapshot.recorder_clients ?? 0) > 0;
    EditorApp.element("app").toggleAttribute("data-target-ready", connected);
    EditorApp.element("browser-status").textContent = connected
      ? "Target ready"
      : "Target closed";
    EditorApp.element("browser-status").setAttribute(
      "data-state",
      connected ? "succeeded" : "disconnected",
    );
    document
      .querySelectorAll('[data-cmd="recorder.record"]')
      .forEach(node => {
        if (node instanceof HTMLButtonElement)
          node.disabled = !connected || Boolean(snapshot.execution_run_id);
      });
    const operation = snapshot.crawl;
    const running = operation?.state === "running";
    const submit = document.querySelector("#actions-form [type=submit]");
    if (submit instanceof HTMLButtonElement) submit.disabled = running;
    if (running)
      EditorApp.element("status").textContent =
        `Running ${operation.tool || "discovery"}${operation.action_id ? `, ${operation.action_id}` : ""}`;
    else if (operation?.state === "failed")
      EditorApp.element("status").textContent =
        operation.error || "Actions finished with findings. Open the report.";
    else if (operation?.state === "succeeded")
      EditorApp.element("status").textContent =
        "Actions completed. Open the report.";
    else if (operation?.state === "cancelled")
      EditorApp.element("status").textContent =
        "Operation cancelled. Earlier artifacts remain available.";
    else if (!connected)
      EditorApp.element("status").textContent =
        "Open the target browser to record or run tests.";
    this.render();
  }
  /** @returns {void}
   */
  render() {
    if (this.dragging) {
      this.renderDeferred = true;
      return;
    }
    const active = document.activeElement;
    const id = active instanceof HTMLElement ? active.id : "";
    const step =
      active instanceof HTMLElement ? active.getAttribute("data-step") : "";
    const panels = ["flows", "table", "inspector", "timeline", "runs"];
    const positions = panels.map(name => {
      const node = EditorApp.element(name);
      return {
        node,
        top: node.scrollTop,
        left: node.scrollLeft,
      };
    });
    this.renderFlows();
    this.renderGraph();
    this.renderTable();
    this.renderInspector();
    this.renderTimeline();
    this.renderRuns();
    this.renderEditEvidence();
    this.renderWorkspaceSurface();
    positions.forEach(({ node, top, left }) => {
      node.scrollTop = top;
      node.scrollLeft = left;
    });
    let target = id ? document.getElementById(id) : null;
    if (!target && step)
      target =
        document.querySelector(
          `.data-table [data-step="${CSS.escape(step)}"]`,
        ) || document.querySelector(`[data-step="${CSS.escape(step)}"]`);
    if (!target && id.startsWith("step-"))
      target = document.querySelector(".data-table [data-step]");
    if (target instanceof HTMLElement && target !== active)
      target.focus({
        preventScroll: true,
      });
  }
  /** Render the workspace flow list into the flows panel.
   * @returns {void}
   */
  renderFlows() {
    renderFlowList(
      EditorApp.element("flows"),
      this.workspace?.flows ?? [],
      this.activeFlowId,
      id => this.selectGraphFlow(id),
      (id, anchor) => this.openFlowMenu(anchor, id),
    );
    this.renderSelectors();
    this.refreshSelectorSeen();
  }
  /** Redraw the open selector's "Tested on" list after a test updated it.
   * @returns {void}
   */
  refreshSelectorSeen() {
    const area = document.querySelector("#inspector .selector-seen");
    const selector = this.selectors().find(
      item => item.selector_id === this.selectedSelectorId,
    );
    if (area instanceof HTMLElement && selector)
      renderSeen(area, selector, this.snapshot?.target_url ?? "");
  }
  /** Show the first-run screen over the editor while there is no project, and
   * make everything behind it unreachable by keyboard until it goes.
   * @returns {void}
   */
  renderWelcomeScreen() {
    const root = document.getElementById("welcome");
    const projects = this.projects;
    if (!(root instanceof HTMLElement) || !projects) return;
    /** @returns {boolean} */
    const wasDismissed = () => {
      try {
        return sessionStorage.getItem(DISMISSED_KEY) === "1";
      } catch {
        return false;
      }
    };
    const show = shouldWelcome(
      /** @type {any} */ (this.snapshot),
      this.workspaceView,
      wasDismissed(),
    );
    if (show)
      renderWelcome(root, {
        create: () => projects.create(),
        openDemo: () => projects.openDemo(),
        importFile: () => projects.importFile(true),
        dismiss: () => {
          try {
            sessionStorage.setItem(DISMISSED_KEY, "1");
          } catch {
            // Without session storage the screen simply returns on reload.
          }
          this.renderWelcomeScreen();
        },
      });
    root.hidden = !show;
    document
      .querySelectorAll("#workbench, .studio > .bottom")
      .forEach(node => {
        if (node instanceof HTMLElement) node.inert = show;
      });
  }
  /** Where condition fields read their suggestions: the server's vocabulary and the stored selectors.
   * @returns {import("./condition-field.js").ConditionSource}
   */
  conditionSource() {
    return {
      terms: () => this.snapshot?.condition_vocabulary ?? [],
      selectors: () => this.selectors().map(item => item.name),
    };
  }
  /** The project's stored selectors.
   * @returns {any[]}
   */
  selectors() {
    return this.snapshot?.selectors ?? [];
  }
  /** Render the Selectors list under the Flows list.
   * @returns {void}
   */
  renderSelectors() {
    const target = document.getElementById("selectors");
    if (!target) return;
    renderSelectorList(
      target,
      this.selectors(),
      this.snapshot?.selector_usage ?? {},
      this.selectedSelectorId,
      id => this.selectSelector(id),
    );
  }
  /** Open a selector in the inspector.
   * @param {string} id A selector id, or "new" for an empty draft.
   * @returns {void}
   */
  selectSelector(id) {
    this.selectedSelectorId = id;
    this.selectedEventIds = new Set();
    this._primary = "";
    this.selectorTest = null;
    this.selectorTesting = false;
    this.inspectorKey = "";
    LiveTarget.clearMatches();
    this.selectorEditorKey = "";
    this.renderSelectors();
    this.renderTable();
    this.renderInspector();
    this.dock.openWindow("properties", { x: 1080, y: 96, w: 344, h: 660 });
  }
  /** Load the formula editor and the engine once; null when they cannot load.
   * @returns {Promise<{Engine:any,Editor:any}|null>}
   */
  /** Values of the environment variables for the active device profile.
   * @returns {Record<string,string|number|boolean>}
   */
  environmentValues() {
    const snapshot = this.snapshot;
    const viewport = snapshot?.viewport;
    const profile = snapshot?.workspace?.profiles?.find(item => item.id === snapshot?.device_mode);
    /** @type {Record<string,string|number|boolean>} */
    const values = {
      "device/profile": snapshot?.device_mode ?? "desktop",
      "device/mode": snapshot?.device_mode ?? "desktop",
      "device/touch": Boolean(profile?.touch),
      "env/colorScheme": "dark",
      "env/locale": navigator.language,
      "env/reducedMotion": window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      "target/url": snapshot?.target_url ?? "",
    };
    if (viewport) {
      values["device/width"] = viewport.width;
      values["device/height"] = viewport.height;
    }
    values["device/scale"] = window.devicePixelRatio;
    return values;
  }
  /** Variables a selector expression may use: environment values and flow outputs.
   * @returns {Array<{path:string,scope:"env"|"flow",type:"num"|"bool"|"text",value?:string|number|boolean,detail?:string}>}
   */
  selectorVariables() {
    const values = this.environmentValues();
    const kinds = /** @type {Record<string,"num"|"bool"|"text">} */ ({
      "device/width": "num",
      "device/height": "num",
      "device/scale": "num",
      "device/touch": "bool",
      "env/reducedMotion": "bool",
    });
    const environment = Object.entries(values).map(([path, value]) => ({
      path,
      scope: /** @type {"env"} */ ("env"),
      type: kinds[path] ?? "text",
      value,
    }));
    const outputs = (this.snapshot?.condition_vocabulary ?? [])
      .filter(term => term.kind === "output")
      .map(term => ({
        path: term.name,
        scope: /** @type {"flow"} */ ("flow"),
        type: /** @type {"num"|"bool"|"text"} */ (
          term.value_type === "boolean" ? "bool" : ["integer", "float"].includes(term.value_type) ? "num" : "text"
        ),
        detail: term.detail,
      }));
    return [...environment, ...outputs];
  }
  /** Run a test that draws nothing and resolve with the engine's statistics.
   * @param {string} expression
   * @returns {Promise<any>}
   */
  statsSelector(expression) {
    const run = () =>
      new Promise((resolve, reject) => {
        this.testSelector({ selector_id: "", expression, expected_count: null, checks: [] }, result => {
          const reply = /** @type {any} */ (result)?.stats;
          if (reply?.ok) resolve(reply.stats);
          else reject(Object.assign(new Error(reply?.message || /** @type {any} */ (result)?.error || "Not available"), { code: reply?.code ?? null }));
        }, true);
      });
    const next = this.statsQueue.then(run, run);
    this.statsQueue = next.catch(() => undefined);
    return next;
  }
  /** What every selector field needs from the editor: page actions, stats and data.
   * @returns {object}
   */
  selectorHostOptions() {
    return {
      onPick: (/** @type {any} */ apply) => {
        this.selectorPickSink = apply;
        this.liveTarget?.startPicking();
      },
      onHighlight: (/** @type {string} */ expression, /** @type {any} */ done) =>
        this.testSelector({ selector_id: "", expression, expected_count: null, checks: [] }, done),
      onClear: () => LiveTarget.clearMatches(),
      onStats: (/** @type {string} */ expression) => this.statsSelector(expression),
      variables: () => this.selectorVariables(),
      saved: () => this.selectors().map(item => ({ name: item.name })),
    };
  }
  /** Add the shared page tools beside a selector control's editing surface.
   * The carrier keeps whatever editor its field already mounted; the tools only
   * read and write its stored value.
   * @param {HTMLInputElement|HTMLTextAreaElement} carrier Stored form control.
   * @param {string} label Visible field label.
   * @returns {void}
   */
  mountSelectorWidget(carrier, label) {
    const options = /** @type {any} */ (this.selectorHostOptions());
    const live = selectorLiveTools({
      getValue: () => carrier.value,
      setValue: value => {
        carrier.value = value;
        carrier.dispatchEvent(new Event("input", { bubbles: true }));
        carrier.dispatchEvent(new Event("change", { bubbles: true }));
      },
      onPick: options.onPick,
      onHighlight: options.onHighlight,
      onClear: options.onClear,
    });
    live.element.setAttribute("aria-label", `${label} page tools`);
    const anchor =
      carrier.closest(".variable-field") ?? carrier.closest("label") ?? carrier;
    anchor.after(live.element);
  }
  /**
   * Load the extended-selector engine and editor modules once.
   * @returns {Promise<{Engine:any, Editor:any}|null>} The library promise.
   */
  loadSelectorLibrary() {
    this.selectorLibrary ??= Promise.all([
      import(String("/studio/packages/extended_selector/editor/extended-selector.js")),
      import(String("/studio/packages/widgets/widget_selector/extended-selector-editor.js")),
    ])
      .then(([engine, editor]) => ({
        Engine: engine.default,
        Editor: editor.ExtendedSelectorEditor,
      }))
      .catch(() => null);
    return this.selectorLibrary;
  }
  /** Name the action a selector is used by.
   * @param {string} flowId
   * @param {string} eventId
   * @returns {string}
   */
  selectorUseLabel(flowId, eventId) {
    const flow = this.workspace?.flows?.find(item => item.id === flowId);
    const event = flow?.events?.find(item => item.id === eventId);
    return `${flow?.name ?? flowId}: ${event?.label || event?.kind || eventId}`;
  }
  /** Jump to an action that uses the open selector.
   * @param {string} flowId
   * @param {string} eventId
   * @returns {Promise<void>}
   */
  async openSelectorAction(flowId, eventId) {
    this.selectedSelectorId = "";
    this.inspectorKey = "";
    if (flowId !== this.activeFlowId)
      await this.command("flow.select", { flow_id: flowId });
    this.setSelection([eventId], eventId);
    this.renderSelectors();
  }
  /** Show the open selector bookmark or draft in the contextual Properties panel.
   * @returns {Promise<void>}
   */
  async renderSelectorEditor() {
    const target = document.getElementById("inspector");
    const id = this.selectedSelectorId;
    if (!target) return;
    if (!id) {
      if (this.selectorEditorKey) {
        this.selectorEditorKey = "";
        const note = document.createElement("p");
        note.className = "selector-note";
        note.textContent = "Pick a selector from the list, or add one with +.";
        target.replaceChildren(note);
      }
      return;
    }
    const key = `selector:${id}`;
    if (this.selectorEditorKey === key) return;
    this.selectorEditorKey = key;
    const token = ++this.inspectorToken;
    const selector =
      id === "new"
        ? null
        : (this.selectors().find(item => item.selector_id === id) ?? null);
    if (id !== "new" && !selector) {
      this.selectedSelectorId = "";
      this.selectorEditorKey = "";
      this.renderSelectors();
      return;
    }
    const library = await this.loadSelectorLibrary();
    if (token !== this.inspectorToken || this.selectedSelectorId !== id) return;
    const built = selectorInspector({
      selector,
      usage: selector ? this.snapshot?.selector_usage?.[id] : undefined,
      labelFor: (flowId, eventId) => this.selectorUseLabel(flowId, eventId),
      pageUrl: this.snapshot?.target_url ?? "",
      test: this.selectorTest,
      selectors: this.selectors().map(item => item.name),
      engine: library ? new library.Engine(document) : null,
      Editor: library?.Editor ?? null,
      onSave: values => this.saveSelector(values, selector),
      onSaveCopy: values => this.saveSelectorCopy(values),
      onTest: (values, done) => this.testSelector(values, done),
      onPick: apply => {
        this.selectorPickSink = apply;
        this.liveTarget?.startPicking();
      },
      onClear: () => LiveTarget.clearMatches(),
      onStats: expression => this.statsSelector(expression),
      variables: () => this.selectorVariables(),
      onDelete: () => this.deleteSelector(selector),
      onOpenAction: (flowId, eventId) =>
        this.openSelectorAction(flowId, eventId),
    });
    target.replaceChildren(built.fragment);
    target.scrollTop = 0;
    const first = built.form.querySelector("[name=name]");
    if (first instanceof HTMLElement && id === "new") first.focus();
  }
  /** Test the expression in the form against the live page.
   * @param {{selector_id:string,expression:string,expected_count:number|null,checks:string[]}} values
   * @param {((result:{count?:number})=>void)|null} [done] Receives the outcome.
   * @param {boolean} [silent] Report only to `done`: draw nothing in the inspector or the page.
   * @returns {Promise<void>}
   */
  async testSelector(values, done = null, silent = false) {
    const result = document.getElementById("selector-result");
    if (!values.expression) {
      if (result)
        renderTestResult(result, {
          ok: false,
          count: 0,
          expected_count: values.expected_count,
          elapsed_ms: 0,
          polls: 0,
          error: "Write an expression first.",
          definition_errors: [],
          cause: {},
          url: "",
          matches: [],
          expression: "",
          selector_id: null,
        });
      return;
    }
    this.selectorTesting = true;
    this.selectorTestSink = done;
    this.selectorTestSilent = silent;
    if (!silent) {
      LiveTarget.clearMatches();
      if (result) renderTestResult(result, null, true);
    }
    try {
      await this.call("selector.test", {
        selector_id: values.selector_id,
        expression: values.expression,
        expected_count: values.expected_count ?? "any",
        checks: values.checks,
        variables: this.environmentValues(),
      });
    } catch (error) {
      this.selectorTesting = false;
      this.selectorTestSink = null;
      EditorApp.element("status").textContent =
        error instanceof Error ? error.message : String(error);
      if (result) renderTestResult(result, null);
    }
  }
  /** Show a finished test in the inspector and on the live page.
   * @param {any} result
   * @returns {void}
   */
  onSelectorTested(result) {
    const text = JSON.stringify(result);
    const sink = this.selectorTestSink;
    const silent = this.selectorTestSilent;
    this.selectorTestSink = null;
    this.selectorTestSilent = false;
    if (silent) {
      this.selectorTesting = false;
      sink?.(result);
      return;
    }
    if (text === this.selectorTestText) {
      this.selectorTesting = false;
      sink?.(result);
      return;
    }
    this.selectorTestText = text;
    this.selectorTest = result;
    this.selectorTesting = false;
    sink?.(result);
    const area = document.getElementById("selector-result");
    if (area) renderTestResult(area, result);
    this.liveTarget?.showMatches(result.matches ?? []);
  }
  /** Save the form; a selector that other actions use asks first.
   * @param {{selector_id:string,name:string,expression:string,expected_count:number|null,checks:string[]}} values
   * @param {any} existing
   * @returns {Promise<void>}
   */
  async saveSelector(values, existing) {
    const use = existing
      ? this.snapshot?.selector_usage?.[existing.selector_id]
      : null;
    const changed =
      existing &&
      (existing.expression !== values.expression ||
        existing.expected_count !== values.expected_count ||
        existing.checks.join("\n") !== values.checks.join("\n"));
    if (use?.actions?.length && changed) {
      const choice = await EditorApp.confirmShared(use);
      if (choice === "cancel") return;
      if (choice === "copy") {
        await this.saveSelectorCopy(values);
        return;
      }
    }
    await this.command("selector.save", {
      ...values,
      selector_id: existing?.selector_id ?? "",
    });
    const saved = this.selectors().find(item => item.name === values.name);
    this.selectedSelectorId = saved?.selector_id ?? this.selectedSelectorId;
    this.selectorEditorKey = "";
    this.renderSelectors();
    this.renderSelectorEditor();
  }
  /** Save the form as a new selector, leaving the original alone.
   * @param {{name:string,expression:string,expected_count:number|null,checks:string[]}} values
   * @returns {Promise<void>}
   */
  async saveSelectorCopy(values) {
    const taken = new Set(this.selectors().map(item => item.name));
    let name = `${values.name || "selector"}_copy`;
    for (let n = 2; taken.has(name); n += 1)
      name = `${values.name || "selector"}_copy${n}`;
    await this.command("selector.save", { ...values, name, selector_id: "" });
    const saved = this.selectors().find(item => item.name === name);
    if (saved) this.selectSelector(saved.selector_id);
  }
  /** Delete a selector, naming what will break when it is in use.
   * @param {any} selector
   * @returns {Promise<void>}
   */
  async deleteSelector(selector) {
    if (!selector) {
      this.selectedSelectorId = "";
      this.renderSelectors();
      this.renderSelectorEditor();
      return;
    }
    const use = this.snapshot?.selector_usage?.[selector.selector_id];
    const inUse = Boolean(
      use?.actions?.length || use?.selectors?.length || use?.conditions,
    );
    const approved = await EditorApp.confirmDelete({
      title: `Delete ${selector.name}?`,
      body: inUse
        ? "Actions that use it will fail until you pick another selector."
        : "Nothing uses it.",
      keep: "Keep selector",
      remove: "Delete selector",
    });
    if (!approved) return;
    this.selectedSelectorId = "";
    LiveTarget.clearMatches();
    await this.command("selector.delete", {
      selector_id: selector.selector_id,
      force: inUse,
    });
    this.renderSelectors();
    this.renderSelectorEditor();
  }
  /** Open the actions menu of one flow; it is the same in every workspace.
   * @param {HTMLElement} anchor
   * @param {string} id
   * @returns {void}
   */
  openFlowMenu(anchor, id) {
    const only = (this.workspace?.flows?.length ?? 0) <= 1;
    EditorApp.openMenu(anchor, [
      [
        "trash",
        only ? "Delete flow (a project needs one)" : "Delete flow",
        only,
        () => this.deleteFlow(id),
      ],
    ]);
  }
  /** Ask once, then remove a flow with its steps, screenshots and connections.
   * @param {string} id
   * @returns {Promise<void>}
   */
  async deleteFlow(id) {
    const flow = this.workspace?.flows?.find(item => item.id === id);
    if (!flow) return;
    const approved = await EditorApp.confirmDelete({
      title: `Delete ${flow.name}?`,
      body: "This also removes its steps, screenshots and connections.",
      keep: "Keep flow",
      remove: "Delete flow",
    });
    if (!approved) return;
    this.selectedGraphEdge = "";
    this.inspectorKey = "";
    await this.command("flow.delete", { flow_id: id });
  }
  /** Render the graph visualization for the active flow.
   * @returns {void}
   */
  renderGraph() {
    const flows = this.workspace?.flows ?? [];
    const flow = this.activeFlow();
    this.renderFlows();
    const edges = this.workspace?.edges ?? [];
    /** @type {Record<string, {x:number,y:number}>} */
    let positions = {};
    try {
      positions = JSON.parse(
        localStorage.getItem("studio.graph-nodes") || "{}",
      );
      if (!positions || typeof positions !== "object") positions = {};
    } catch {
      localStorage.removeItem("studio.graph-nodes");
    }
    EditorApp.element("flow-title").textContent = flow?.name ?? "Untitled";
    EditorApp.element("flow-summary").textContent =
      `${flows.length} flows · ${edges.length} connections`;
    EditorApp.element("graph").replaceChildren(
      graphNodes(flows, flow?.id ?? null, positions, edges),
    );
    window.requestAnimationFrame(() => this.renderConnections());
    EditorApp.element("graph")
      .querySelectorAll("[data-select-flow]")
      .forEach(node => {
        node.addEventListener("click", () => {
          const flowNode = node.closest(".flow-node");
          if (flowNode?.getAttribute("data-suppress-select") === "true") {
            flowNode.removeAttribute("data-suppress-select");
            return;
          }
          this.selectGraphFlow(node.getAttribute("data-select-flow") || "");
        });
      });
    this.bindGraphConnections();
  }
  /** Selecting a flow anywhere (panel, graph node, tab) selects it globally.
   * @param {string} id Whole flow identifier.
   * @returns {void}
   */
  selectGraphFlow(id) {
    this.selectedGraphEdge = "";
    this.selectedSelectorId = "";
    this.inspectorKey = "";
    this.command("flow.select", { flow_id: id });
  }
  /** Create a transition using the chosen source and target flows.
   * @param {string} source
   * @param {string} target
   * @returns {void}
   */
  connectFlows(source, target) {
    if (!source || !target) return;
    if (source === target) {
      EditorApp.element("status").textContent =
        "Choose a different flow for the connection.";
      return;
    }
    if (
      (this.workspace?.edges ?? []).some(
        edge => edge.source === source && edge.target === target,
      )
    ) {
      EditorApp.element("status").textContent =
        "Those flows are already connected.";
      return;
    }
    this.graphConnectionSource = "";
    EditorApp.element("graph").removeAttribute("data-connecting");
    EditorApp.element("graph")
      .querySelector(".composition-preview-links")
      ?.remove();
    this.command("edge.add", {
      source,
      target,
      mode: "always",
      condition_expression: "",
    });
    const flows = this.workspace?.flows ?? [];
    const sourceName = flows.find(flow => flow.id === source)?.name || source;
    const targetName = flows.find(flow => flow.id === target)?.name || target;
    EditorApp.element("status").textContent =
      `Connecting ${sourceName} to ${targetName}`;
  }
  /** Bind graph connection creation and cancellation gestures.
   * @returns {void}
   */
  bindGraphConnections() {
    const graph = EditorApp.element("graph");
    const canvas = graph.querySelector(".composition-nodes");
    if (!(canvas instanceof HTMLElement)) return;
    const clearPreview = () => {
      canvas.querySelector(".composition-preview-links")?.remove();
      canvas.querySelectorAll(".is-connection-source").forEach(node => {
        node.classList.remove("is-connection-source");
      });
    };
    /** @param {string} source
     * @returns {void}
     */
    const begin = source => {
      this.graphConnectionSource = source;
      graph.setAttribute("data-connecting", source);
      clearPreview();
      canvas
        .querySelector(`[data-node-flow="${CSS.escape(source)}"]`)
        ?.classList.add("is-connection-source");
      EditorApp.element("status").textContent =
        "Choose an input port. Drag or click to connect.";
    };
    /** @param {number} clientX
     * @param {number} clientY
     * @returns {void}
     */
    const preview = (clientX, clientY) => {
      if (!this.graphConnectionSource) return;
      const output = canvas.querySelector(
        `[data-graph-output="${CSS.escape(this.graphConnectionSource)}"]`,
      );
      if (!(output instanceof HTMLElement)) return;
      const canvasRect = canvas.getBoundingClientRect();
      const portRect = output.getBoundingClientRect();
      const zoom = this.graphZoom || 1;
      const x1 = (portRect.left + portRect.width / 2 - canvasRect.left) / zoom;
      const y1 = (portRect.top + portRect.height / 2 - canvasRect.top) / zoom;
      const x2 = (clientX - canvasRect.left) / zoom;
      const y2 = (clientY - canvasRect.top) / zoom;
      const mid = x1 + Math.max(32, Math.abs(x2 - x1) / 2);
      canvas.querySelector(".composition-preview-links")?.remove();
      const svg = graphSvg("svg", {
        class: "composition-links composition-preview-links",
        "aria-hidden": "true",
        width: String(canvas.scrollWidth),
        height: String(canvas.scrollHeight),
        viewBox: `0 0 ${canvas.scrollWidth} ${canvas.scrollHeight}`,
      });
      svg.append(
        graphSvg("path", {
          d: `M ${x1} ${y1} C ${mid} ${y1}, ${x2 - Math.max(24, Math.abs(x2 - x1) / 3)} ${y2}, ${x2} ${y2}`,
        }),
      );
      canvas.prepend(svg);
    };
    canvas.querySelectorAll("[data-graph-output]").forEach(node => {
      let skipClick = false;
      node.addEventListener("click", () => {
        if (skipClick) {
          skipClick = false;
          return;
        }
        const source = node.getAttribute("data-graph-output") || "";
        if (this.graphConnectionSource === source) {
          this.graphConnectionSource = "";
          graph.removeAttribute("data-connecting");
          clearPreview();
          EditorApp.element("status").textContent = "Connection cancelled";
        } else begin(source);
      });
      node.addEventListener("pointerdown", event => {
        if (!(event instanceof PointerEvent)) return;
        begin(node.getAttribute("data-graph-output") || "");
        node.setPointerCapture(event.pointerId);
        preview(event.clientX, event.clientY);
      });
      node.addEventListener("pointermove", event => {
        if (
          event instanceof PointerEvent &&
          node.hasPointerCapture(event.pointerId)
        )
          preview(event.clientX, event.clientY);
      });
      node.addEventListener("pointerup", event => {
        if (!(event instanceof PointerEvent)) return;
        const drop = document
          .elementFromPoint(event.clientX, event.clientY)
          ?.closest("[data-graph-input]");
        if (drop instanceof HTMLElement) {
          skipClick = true;
          this.connectFlows(
            this.graphConnectionSource,
            drop.getAttribute("data-graph-input") || "",
          );
        } else {
          graph.removeAttribute("data-connecting");
          this.graphConnectionSource = "";
          clearPreview();
        }
      });
    });
    canvas.querySelectorAll("[data-graph-input]").forEach(node => {
      node.addEventListener("click", () => {
        if (!this.graphConnectionSource) {
          EditorApp.element("status").textContent =
            "Start from an output port, then choose this input.";
          return;
        }
        this.connectFlows(
          this.graphConnectionSource,
          node.getAttribute("data-graph-input") || "",
        );
      });
    });
    canvas.querySelectorAll(".flow-node").forEach(flowNode => {
      if (!(flowNode instanceof HTMLElement)) return;
      const handle = flowNode.querySelector(".flow-node-title");
      if (!(handle instanceof HTMLElement)) return;
      handle.addEventListener("pointerdown", event => {
        if (!(event instanceof PointerEvent) || event.button !== 0) return;
        const startX = event.clientX;
        const startY = event.clientY;
        const startLeft = flowNode.offsetLeft;
        const startTop = flowNode.offsetTop;
        let moved = false;
        handle.setPointerCapture(event.pointerId);
        flowNode.classList.add("is-node-dragging");
        /** @param {PointerEvent} moveEvent
         * @returns {void}
         */
        const move = moveEvent => {
          const dx = (moveEvent.clientX - startX) / (this.graphZoom || 1);
          const dy = (moveEvent.clientY - startY) / (this.graphZoom || 1);
          moved ||= Math.hypot(dx, dy) > 3;
          if (!moved) return;
          flowNode.style.left = `${Math.max(8, startLeft + dx)}px`;
          flowNode.style.top = `${Math.max(8, startTop + dy)}px`;
          this.renderConnections();
        };
        /** @param {Event} [ending] The pointer event that ended the gesture.
         * @returns {void}
         */
        const finish = ending => {
          flowNode.classList.remove("is-node-dragging");
          handle.removeEventListener("pointermove", move);
          handle.removeEventListener("pointerup", finish);
          handle.removeEventListener("pointercancel", finish);
          if (!moved) return;
          // The click that ends a drag must not select the flow. Only a real
          // release produces that click, and a missed one must not linger and
          // swallow a later intentional selection.
          if (ending?.type === "pointerup") {
            flowNode.setAttribute("data-suppress-select", "true");
            window.setTimeout(
              () => flowNode.removeAttribute("data-suppress-select"),
              400,
            );
          }
          /** @type {Record<string, {x:number,y:number}>} */
          const positions = (() => {
            try {
              return /** @type {Record<string, {x:number,y:number}>} */ (
                JSON.parse(localStorage.getItem("studio.graph-nodes") || "{}")
              );
            } catch {
              return {};
            }
          })();
          positions[flowNode.getAttribute("data-node-flow") || ""] = {
            x: Math.round(flowNode.offsetLeft),
            y: Math.round(flowNode.offsetTop),
          };
          localStorage.setItem("studio.graph-nodes", JSON.stringify(positions));
          EditorApp.element("status").textContent = "Flow position saved";
        };
        handle.addEventListener("pointermove", move);
        handle.addEventListener("pointerup", finish);
        handle.addEventListener("pointercancel", finish);
      });
    });
    if (this.graphPanBound) return;
    this.graphPanBound = true;
    graph.addEventListener("pointerdown", event => {
      if (
        !(event instanceof PointerEvent) ||
        event.button !== 0 ||
        event.target instanceof Element &&
          event.target.closest(".flow-node, .composition-link")
      )
        return;
      const startX = event.clientX;
      const startY = event.clientY;
      const startLeft = graph.scrollLeft;
      const startTop = graph.scrollTop;
      graph.setPointerCapture(event.pointerId);
      graph.classList.add("is-graph-panning");
      /** @param {PointerEvent} moveEvent
       * @returns {void}
       */
      const move = moveEvent => {
        graph.scrollLeft = startLeft - (moveEvent.clientX - startX);
        graph.scrollTop = startTop - (moveEvent.clientY - startY);
      };
      const finish = () => {
        graph.classList.remove("is-graph-panning");
        graph.removeEventListener("pointermove", move);
        graph.removeEventListener("pointerup", finish);
        graph.removeEventListener("pointercancel", finish);
      };
      graph.addEventListener("pointermove", move);
      graph.addEventListener("pointerup", finish);
      graph.addEventListener("pointercancel", finish);
    });
  }
  /** Render selectable transition paths between flow nodes.
   * @returns {void}
   */
  renderConnections() {
    const canvas =
      EditorApp.element("graph").querySelector(".composition-nodes");
    if (!(canvas instanceof HTMLElement)) return;
    graphLinks(
      canvas,
      this.workspace?.edges ?? [],
      this.workspace?.flows ?? [],
      this.graphZoom,
      this.selectedGraphEdge,
      edge => {
        this.selectedGraphEdge = `${edge.source}:${edge.target}`;
        this.inspectorKey = "";
        canvas.querySelectorAll(".composition-link").forEach(node => {
          const active =
            node.getAttribute("data-edge") === this.selectedGraphEdge;
          node.classList.toggle("is-selected", active);
          node.setAttribute("aria-pressed", String(active));
        });
        this.renderInspector();
      },
    );
  }
  /** Fit all nodes, including saved positions, inside the visible canvas.
   * @returns {void}
   */
  fitGraph() {
    const graph = EditorApp.element("graph");
    const canvas = graph.querySelector(".composition-nodes");
    if (
      !(canvas instanceof HTMLElement) ||
      !graph.clientWidth ||
      !graph.clientHeight
    )
      return;
    const bounds = graphBounds(canvas);
    this.setGraphZoom(
      Math.min(
        1,
        (graph.clientWidth - 24) / Math.max(1, bounds.width),
        (graph.clientHeight - 24) / Math.max(1, bounds.height),
      ),
    );
    graph.scrollLeft = 0;
    graph.scrollTop = 0;
  }
  /** Clamp and apply the graph zoom level.
   * @param {number} value
   * @returns {void}
   */
  setGraphZoom(value) {
    this.graphZoom = Math.min(
      1.5,
      Math.max(0.1, Math.round(value * 100) / 100),
    );
    EditorApp.element("graph").style.setProperty(
      "--dynamic-graph-zoom",
      String(this.graphZoom),
    );
    EditorApp.element("graph-zoom-label").textContent =
      `${Math.round(this.graphZoom * 100)}%`;
    EditorApp.element("status").textContent =
      `Graph zoom ${Math.round(this.graphZoom * 100)}%`;
    window.requestAnimationFrame(() => this.renderConnections());
  }
  /** Render the active flow's steps in the table.
   * @returns {void}
   */
  renderTable() {
    const target = EditorApp.element("table");
    const events = this.activeFlow()?.events ?? [];
    target.replaceChildren(EditorApp.template("edit-steps-template"));
    EditorApp.element("edit-step-count").textContent = this.activeFlow()
      ? `${events.length} ${events.length === 1 ? "step" : "steps"}`
      : "No flow";
    const list = target.querySelector(".edit-step-list");
    /** @type {Map<string,HTMLElement>} */
    const recordingLists = new Map();
    for (const group of this.visibleRecordings()) {
      const children = events.filter(
        event => event.recording_group_id === group.id,
      );
      const section = document.createElement("details");
      section.className = "recording-group";
      section.setAttribute("data-recording-group", group.id);
      section.open = !this.collapsedRecordings.has(group.id);
      const summary = document.createElement("summary");
      const disclosure = iconElement("chevron-right", "recording-disclosure");
      const label = document.createElement("strong");
      label.textContent = group.label;
      const timing = document.createElement("small");
      const end = Math.max(
        group.start_ms,
        ...children.map(event => event.elapsed_ms ?? group.start_ms),
      );
      const recordingSnapshot =
        /** @type {EditorSnapshot & {recording_session_id?:string|null}} */ (
          this.snapshot
        );
      const state =
        recordingSnapshot?.recording_session_id === group.id
          ? recordingSnapshot.recording_state
          : "idle";
      const status =
        state === "recording"
          ? "Capturing · "
          : state === "paused"
            ? "Paused · "
            : "";
      timing.textContent = `${status}${children.length} actions · ${EditorApp.timecode(end - group.start_ms)}`;
      const capturing = state === "recording" || state === "paused";
      const more = document.createElement("span");
      more.className = "edit-step-more recording-more";
      more.setAttribute("role", "button");
      more.setAttribute("aria-haspopup", "menu");
      more.setAttribute("aria-label", `Actions for ${group.label}`);
      more.title = capturing
        ? "Stop recording to change this task"
        : "Recording actions";
      more.tabIndex = 0;
      more.toggleAttribute("aria-disabled", capturing);
      more.innerHTML = EditorApp.icon("dots");
      const earliest = Math.min(
        group.start_ms,
        ...children.map(event => event.elapsed_ms ?? group.start_ms),
      );
      const openMenu = () => {
        if (capturing) return;
        EditorApp.openMenu(more, [
          [
            "keyboard",
            "Rename",
            false,
            () => this.renameRecording(summary, group),
          ],
          [
            "arrow-right",
            "Start 1 s later",
            false,
            () =>
              this.command("recording.retime", {
                recording_id: group.id,
                delta_ms: "1000",
              }),
          ],
          [
            "arrow-left",
            "Start 1 s earlier",
            earliest < 1000,
            () =>
              this.command("recording.retime", {
                recording_id: group.id,
                delta_ms: "-1000",
              }),
          ],
          [
            "trash",
            "Delete recording",
            false,
            async () => {
              if (
                await EditorApp.confirmDelete({
                  title: `Delete ${group.label}?`,
                  body: `This removes its ${children.length} ${children.length === 1 ? "action" : "actions"} and their screenshots.`,
                  keep: "Keep recording",
                  remove: "Delete recording",
                })
              )
                this.command("recording.delete", { recording_id: group.id });
            },
          ],
        ]);
      };
      more.addEventListener("click", click => {
        // The summary would otherwise toggle its disclosure.
        click.preventDefault();
        click.stopPropagation();
        openMenu();
      });
      more.addEventListener("keydown", key => {
        if (!["Enter", " ", "ContextMenu"].includes(key.key)) return;
        key.preventDefault();
        key.stopPropagation();
        openMenu();
      });
      summary.append(disclosure, label, timing, more);
      const body = document.createElement("div");
      body.className = "recording-children";
      section.append(summary, body);
      summary.addEventListener("click", () => {
        // Capture the intended state before the native disclosure toggles.
        // Asynchronous toggle events from replaced snapshots can arrive late.
        if (section.open) this.collapsedRecordings.add(group.id);
        else this.collapsedRecordings.delete(group.id);
      });
      if (children.length === 0) {
        // An empty parent stays visible and says what happens next.
        const hint = document.createElement("p");
        hint.className = "recording-empty";
        hint.textContent = capturing
          ? "Waiting for your first action in the browser."
          : "No actions captured. Record again or delete this recording.";
        body.append(hint);
      }
      recordingLists.set(group.id, body);
      // Insert the parent at its first child's sequence, not ahead of authored steps.
    }
    /** Put a card in its recording parent, or in the flow list itself.
     * @param {HTMLElement} node
     * @param {EditorEvent} owner The action the card belongs to.
     * @returns {void}
     */
    const place = (node, owner) => {
      const parent = owner.recording_group_id
        ? recordingLists.get(owner.recording_group_id)
        : undefined;
      if (parent) {
        if (!parent.parentElement?.isConnected)
          list?.append(parent.parentElement ?? parent);
        parent.append(node);
      } else list?.append(node);
    };
    /** @type {string|null} */
    let openGuard = null;
    /** @type {EditorEvent|null} */
    let previous = null;
    events.forEach((event, index) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "edit-step-row";
      row.setAttribute("data-step", event.id);
      if (EditorApp.isConnected(events, index)) row.setAttribute("data-connected", "true");
      const missing = EditorApp.missingVariables(
        events,
        index,
        (this.activeFlow()?.parameters ?? []).map(input => input.name),
      );
      const producers = producersOf(events.slice(0, index));
      for (const input of this.activeFlow()?.parameters ?? [])
        producers.set(input.name, { icon: "download", tone: "silver" });
      const card = buildCard(event, { producers });
      row.setAttribute("data-tone", card.tone);
      if (event.when_expression) row.setAttribute("data-nested", "true");
      row.title = card.sentence.textContent ?? EditorApp.eventTitle(event);
      const content = document.createElement("span");
      content.className = "edit-step-text";
      content.append(card.sentence);
      /** Open the token or code block that was clicked, without selecting the card.
       * @param {Event} click
       * @returns {void}
       */
      const openToken = click => {
        const hit = click.target instanceof Element ? click.target : null;
        const pill = hit?.closest(".action-pill");
        const chip = hit?.closest("[data-field]");
        if (!(chip instanceof HTMLElement)) return;
        click.stopPropagation();
        if (pill instanceof HTMLElement) this.inspectPill(event, index, chip, pill);
        else this.editToken(event, index, chip);
      };
      content.addEventListener("click", openToken);
      card.code?.addEventListener("click", openToken);
      const checks = document.createElement("span");
      checks.className = "edit-step-checks";
      const count = event.contract?.postconditions?.length || 0;
      checks.textContent = count
        ? `${count} ${count === 1 ? "check" : "checks"}`
        : "";
      // A step that failed or only warned in the latest run says so in the
      // slot the check count uses, so the row grid stays the same.
      const outcome = (this.workspace?.runs?.[0]?.action_records ?? []).filter(
        (/** @type {any} */ record) => record.event_id === event.id,
      );
      const worst = worstStatus(outcome);
      if (worst === "failed" || worst === "warning") {
        const hit = outcome.find(
          (/** @type {any} */ record) => record.status === worst,
        );
        checks.textContent = worst === "failed" ? "Failed" : "Warning";
        checks.setAttribute("data-state", worst);
        checks.title = hit ? causeSummary(hit) : "";
      }
      const published = producedVariables(event);
      if (!checks.textContent && published.length > 0) {
        checks.textContent = published.length === 1
          ? published[0]?.name ?? "1 variable"
          : `${published.length} variables`;
        checks.setAttribute("data-state", "produces");
        checks.title = `Produces ${published.map(item => `“${item.name}”`).join(", ")}`;
      }
      if (missing.length > 0 && worst !== "failed") {
        checks.textContent = "Missing variable";
        checks.setAttribute("data-state", "failed");
        checks.title = `No earlier action produces: ${missing.join(", ")}`;
      }
      if (event.incomplete) {
        const setup = definitionForEvent(event);
        const where = setup && editsInRow(setup) ? "in its row" : "in Properties";
        checks.textContent = "Needs setup";
        checks.setAttribute("data-state", "warning");
        checks.title = `Finish this action's settings ${where}. The flow cannot run until then.`;
      }
      if (this.snapshot?.run_control?.before_event_id === event.id) {
        row.setAttribute("data-run-next", "true");
        checks.textContent = "Runs next";
        checks.setAttribute("data-state", "paused");
        checks.title = "The run is paused before this action";
      }
      const grip = document.createElement("span");
      grip.className = "edit-step-grip";
      grip.setAttribute("aria-hidden", "true");
      grip.title = "Drag to reorder (Alt+↑ or Alt+↓ with the keyboard)";
      grip.innerHTML = EditorApp.icon("grip-vertical");
      const kind = card.tile;
      kind.classList.add("edit-step-kind");
      const more = document.createElement("span");
      more.className = "edit-step-more";
      more.setAttribute("role", "button");
      more.setAttribute("aria-haspopup", "menu");
      more.setAttribute("aria-label", `Actions for step ${index + 1}`);
      more.title = "Step actions";
      more.tabIndex = -1;
      more.innerHTML = EditorApp.icon("dots");
      more.addEventListener("click", click => {
        click.stopPropagation();
        this.openStepMenu(more, event.id, index, events.length);
      });
      row.append(grip, kind, content, checks, more);
      const definition = definitionForEvent(event);
      const expanded =
        definition !== undefined &&
        editsInRow(definition) &&
        this.selectedEventIds.size === 1 &&
        this.selectedEventIds.has(event.id);
      if (definition !== undefined && editsInRow(definition))
        row.setAttribute("aria-expanded", String(expanded));
      if (card.code && !expanded) row.append(card.code);
      const guard = event.when_expression || null;
      if (guard !== openGuard) {
        if (openGuard && previous) place(this.guardBlock("End If", "", ""), previous);
        if (guard) place(this.guardBlock("If", guard, event.id, producers), event);
        openGuard = guard;
      }
      place(row, event);
      const home = this.activeFlow();
      if (expanded && definition && home)
        place(this.actionEditor(home, event, definition), event);
      previous = event;
    });
    if (openGuard && previous) place(this.guardBlock("End If", "", ""), previous);
    const empty = target.querySelector(".edit-empty");
    for (const body of recordingLists.values()) {
      const parent = body.parentElement;
      if (parent && !parent.isConnected) list?.append(parent);
    }
    if (empty instanceof HTMLElement)
      empty.hidden = events.length > 0 || recordingLists.size > 0;
    this.bindSteps(target);
    if (list instanceof HTMLElement) this.bindStepDrag(list);
  }
  /** A branch card that opens or closes a guarded run of actions.
   * @param {string} word "If" or "End If".
   * @param {string} expression Condition of the guard.
   * @param {string} firstId First guarded action, selected when the card is clicked.
   * @param {Map<string, {icon:string,tone:string}>} [producers]
   * @returns {HTMLElement}
   */
  guardBlock(word, expression, firstId, producers = new Map()) {
    const block = document.createElement("div");
    block.className = "edit-step-block";
    block.setAttribute("data-block", word === "If" ? "if" : "end");
    const tile = document.createElement("span");
    tile.className = "action-tile edit-step-kind";
    tile.setAttribute("data-tone", "silver");
    tile.append(iconElement("arrows-join"));
    const sentence = renderSentence(
      expression ? guardParts(expression) : [{ kind: "text", text: word }],
      { producers },
    );
    const content = document.createElement("span");
    content.className = "edit-step-text";
    content.append(sentence);
    block.append(tile, content);
    if (firstId)
      block.addEventListener("click", () => {
        this.selectedEventId = firstId;
        this.afterSelectionChange();
      });
    return block;
  }
  /** Open the inspector of a variable pill inside an action card.
   * @param {EditorEvent} event
   * @param {number} index Position of the action in the flow.
   * @param {HTMLElement} chip The token holding the pill.
   * @param {HTMLElement} pill The clicked pill.
   * @returns {void}
   */
  inspectPill(event, index, chip, pill) {
    const field = chip.getAttribute("data-field") ?? "";
    const json = chip.getAttribute("data-json");
    const anyEvent = /** @type {Record<string, any>} */ (event);
    /** @type {Record<string, unknown>} */
    let spec = {};
    try {
      spec = JSON.parse(String(event.payload ?? "{}"));
    } catch {
      spec = {};
    }
    const current = json
      ? String(Reflect.get(spec, json) ?? "")
      : String(anyEvent[field] ?? "");
    const position = [...chip.querySelectorAll(".action-pill")].indexOf(pill);
    const match = [...current.matchAll(/\{\{([^{}]+)\}\}/g)][position];
    if (!match) return;
    const token = match[1] ?? "";
    const base = /^([^.[|]+)/.exec(token)?.[1] ?? token;
    const flow = this.activeFlow();
    const known = EditorApp.variableSources({
      ...(flow ?? { id: "", name: "" }),
      events: (flow?.events ?? []).slice(0, index),
    }).find(item => item.name === base);
    /** Write a changed value back to the action.
     * @param {string} value
     * @returns {void}
     */
    const save = value => {
      this.command("event.update", {
        event_id: event.id,
        label: event.label || EditorApp.eventTitle(event),
        selector: event.selector ?? "",
        url: event.url ?? "",
        output_variable: event.output_variable ?? "",
        ...(event.payload === null || event.payload === undefined
          ? {}
          : { payload: event.payload }),
        ...(json
          ? { payload: JSON.stringify({ ...spec, [json]: value }) }
          : { [field]: value }),
      });
    };
    /** Replace the clicked pill's token in the value.
     * @param {string} next
     * @returns {string}
     */
    const rewritten = next =>
      `${current.slice(0, match.index)}{{${next}}}${current.slice(match.index + match[0].length)}`;
    const close = openFloatingPanel(
      pill,
      variableInspector({
        token,
        type: known?.type ?? "",
        icon: known?.icon ?? "tag",
        tone: known?.tone ?? "silver",
        onChange: next => save(rewritten(next)),
        onClear: () => {
          close();
          save(rewritten("").replace("{{}}", ""));
        },
        onReveal: name => {
          close();
          this.revealVariable(name);
        },
      }),
    );
  }
  /** Open the in-place editor for one token of an action card.
   * @param {EditorEvent} event
   * @param {number} index Position of the action in the flow.
   * @param {HTMLElement} chip The clicked token.
   * @returns {void}
   */
  editToken(event, index, chip) {
    const field = chip.getAttribute("data-field") ?? "";
    const json = chip.getAttribute("data-json");
    const anyEvent = /** @type {Record<string, any>} */ (event);
    /** @type {Record<string, unknown>} */
    let spec = {};
    try {
      spec = JSON.parse(String(event.payload ?? "{}"));
    } catch {
      spec = {};
    }
    const current = json
      ? String(Reflect.get(spec, json) ?? "")
      : String(anyEvent[field] ?? "");
    const flow = this.activeFlow();
    openTokenEditor({
      anchor: chip,
      value: current,
      code: chip.getAttribute("data-editor") === "code",
      variables: EditorApp.variableSources({
        ...(flow ?? { id: "", name: "" }),
        events: (flow?.events ?? []).slice(0, index),
      }),
      onCommit: value => {
        const retitled =
          field === "url" &&
          event.kind === "url_change" &&
          event.label === `Navigate to ${event.url}`;
        this.command("event.update", {
          event_id: event.id,
          label: retitled
            ? `Navigate to ${value}`
            : event.label || EditorApp.eventTitle(event),
          selector: event.selector ?? "",
          url: event.url ?? "",
          output_variable: event.output_variable ?? "",
          ...(event.payload === null || event.payload === undefined
            ? {}
            : { payload: event.payload }),
          ...(json
            ? { payload: JSON.stringify({ ...spec, [json]: value }) }
            : { [field]: value }),
        });
      },
    });
  }
  /** Rename a recording parent in place; Enter saves and Escape cancels.
   * @param {HTMLElement} summary Parent heading holding the name.
   * @param {{id:string,label:string}} group Recording parent.
   * @returns {void}
   */
  renameRecording(summary, group) {
    const label = summary.querySelector("strong");
    if (!label) return;
    const input = document.createElement("input");
    input.value = group.label;
    input.maxLength = 80;
    input.className = "recording-rename";
    input.setAttribute("aria-label", "Recording name");
    let done = false;
    /** @param {boolean} save */
    const finish = save => {
      if (done) return;
      done = true;
      const name = input.value.trim().replace(/\s+/g, " ");
      input.replaceWith(label);
      if (!save || name === group.label) return;
      if (!name) {
        EditorApp.element("status").textContent =
          "A recording needs a name. The previous name was kept.";
        return;
      }
      this.command("recording.rename", { recording_id: group.id, label: name });
    };
    // Typing inside a summary must not toggle the disclosure.
    for (const type of ["click", "keyup"])
      input.addEventListener(type, event => event.stopPropagation());
    input.addEventListener("keydown", event => {
      event.stopPropagation();
      if (event.key === "Enter") {
        event.preventDefault();
        finish(true);
      } else if (event.key === "Escape") {
        event.preventDefault();
        finish(false);
      }
    });
    input.addEventListener("blur", () => finish(true));
    label.replaceWith(input);
    input.focus();
    input.select();
  }
  /** Open the per-step actions menu beside its "…" button.
   * @param {HTMLElement} anchor Button that opened the menu.
   * @param {string} id Step identifier.
   * @param {number} index Step position.
   * @param {number} count Number of steps in the flow.
   * @returns {void}
   */
  openStepMenu(anchor, id, index, count) {
    EditorApp.openMenu(anchor, [
      [
        "arrow-up",
        "Move up",
        index === 0,
        () => this.command("event.move", { event_id: id, offset: "-1" }),
      ],
      [
        "arrow-down",
        "Move down",
        index === count - 1,
        () => this.command("event.move", { event_id: id, offset: "1" }),
      ],
      [
        "trash",
        "Delete step",
        false,
        async () => {
          if (await EditorApp.confirmDelete())
            this.command("event.delete", { event_id: id });
        },
      ],
    ]);
  }
  /** Show a keyboard-operable menu next to its trigger.
   * @param {HTMLElement} anchor Element the menu opens from.
   * @param {Array<[string,string,boolean,()=>unknown]>} items Icon, label, disabled and action.
   * @returns {void}
   */
  static openMenu = (anchor, items) => {
    document.querySelector(".step-menu")?.remove();
    const menu = document.createElement("div");
    menu.className = "step-menu";
    menu.setAttribute("role", "menu");
    const listeners = {
      /** @param {Event} event */
      outside: event => {
        if (!(event.target instanceof Node) || !menu.contains(event.target))
          listeners.close();
      },
      /** @param {KeyboardEvent} event */
      escape: event => {
        if (event.key !== "Escape") return;
        event.stopPropagation();
        listeners.close();
      },
      close: () => {
        menu.remove();
        document.removeEventListener("pointerdown", listeners.outside, true);
        document.removeEventListener("keydown", listeners.escape, true);
      },
    };
    items.forEach(([glyph, label, disabled, run]) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "step-menu-item";
      item.setAttribute("role", "menuitem");
      item.disabled = Boolean(disabled);
      item.innerHTML = `${EditorApp.icon(String(glyph))}<span>${label}</span>`;
      item.addEventListener("click", () => {
        listeners.close();
        Promise.resolve(/** @type {() => unknown} */ (run)()).catch(
          () => undefined,
        );
      });
      menu.append(item);
    });
    document.body.append(menu);
    const box = anchor.getBoundingClientRect();
    menu.style.top = `${Math.min(box.bottom + 2, window.innerHeight - menu.offsetHeight - 4)}px`;
    menu.style.left = `${Math.max(4, Math.min(box.right - menu.offsetWidth, window.innerWidth - menu.offsetWidth - 4))}px`;
    document.addEventListener("pointerdown", listeners.outside, true);
    document.addEventListener("keydown", listeners.escape, true);
    const first = menu.querySelector("button:not(:disabled)");
    if (first instanceof HTMLElement) first.focus();
  };
  static tickSteps = [
    100, 200, 500, 1000, 2000, 5000, 10000, 15000, 30000, 60000, 120000, 300000,
  ];
  static minTickRem = 5;
  static zoomMin = 0.5;
  static zoomMax = 64;
  /** The tick interval that keeps ruler labels legible at a zoom level.
   * @param {number} zoom Rem per second.
   * @returns {number} Milliseconds between ticks.
   */
  static tickFor = zoom =>
    EditorApp.tickSteps.find(
      milliseconds => milliseconds / 1000 * zoom >= EditorApp.minTickRem,
    ) ??
    EditorApp.tickSteps.at(-1) ??
    300000;
  /** @param {number} value Slider position, 0 to 70.
   * @returns {number} Rem per second; each 10 steps double the zoom.
   */
  static zoomFromSlider = value => EditorApp.zoomMin * 2 ** (value / 10);
  /** @param {number} zoom Rem per second.
   * @returns {number} Slider position.
   */
  static sliderFromZoom = zoom =>
    Math.round(10 * Math.log2(zoom / EditorApp.zoomMin));
  /** Where time zero sits inside the scrolling timeline, in pixels.
   * @returns {number}
   */
  static timelineOrigin = () => {
    const timeline = EditorApp.element("timeline");
    const ruler = timeline.querySelector(".ruler-ticks");
    return ruler instanceof HTMLElement
      ? ruler.getBoundingClientRect().left -
          timeline.getBoundingClientRect().left +
          timeline.scrollLeft
      : 0;
  };
  /** Zoom the timeline. The tick interval follows; nothing else sets it.
   * @param {number} zoom Requested rem per second.
   * @param {number|null} [focusMs] Time to keep centred; the current centre by default.
   * @returns {void}
   */
  setTimelineZoom(zoom, focusMs = null) {
    const timeline = EditorApp.element("timeline");
    const rem =
      Number.parseFloat(getComputedStyle(document.documentElement).fontSize) ||
      16;
    const origin = EditorApp.timelineOrigin();
    /** @param {number} ms
     * @returns {number} Pixels from the timeline's left edge to a moment, before scrolling.
     */
    const at = ms =>
      origin + ms / this.timelineTick * this.timelineScale * rem;
    // Zoom around the playhead while it is on screen, else around the middle,
    // and keep that moment exactly where it was on screen.
    const cursorOffset = at(this.timelineCursorMs) - timeline.scrollLeft;
    const cursorVisible =
      focusMs === null &&
      cursorOffset >= origin &&
      cursorOffset <= timeline.clientWidth;
    const middle =
      (timeline.scrollLeft + timeline.clientWidth / 2 - origin) /
        rem /
        this.timelineScale *
      this.timelineTick;
    const anchor = focusMs ?? (cursorVisible ? this.timelineCursorMs : middle);
    const offset = cursorVisible
      ? cursorOffset
      : focusMs === null
        ? timeline.clientWidth / 2
        : timeline.clientWidth / 2;
    this.timelineZoom = Math.min(
      EditorApp.zoomMax,
      Math.max(EditorApp.zoomMin, zoom),
    );
    this.timelineTick = EditorApp.tickFor(this.timelineZoom);
    this.timelineScale = this.timelineTick / 1000 * this.timelineZoom;
    const slider = EditorApp.element("timeline-zoom");
    if (slider instanceof HTMLInputElement)
      slider.value = String(EditorApp.sliderFromZoom(this.timelineZoom));
    this.renderTimeline();
    timeline.scrollLeft = Math.max(0, at(anchor) - offset);
  }
  /** Zoom so a stretch of time fills the visible timeline.
   * @param {number} startMs First moment to show.
   * @param {number} endMs Last moment to show.
   * @returns {void}
   */
  fitTimeline(startMs, endMs) {
    const timeline = EditorApp.element("timeline");
    const rem =
      Number.parseFloat(getComputedStyle(document.documentElement).fontSize) ||
      16;
    const clipRem = 5.75;
    const room =
      (timeline.clientWidth - EditorApp.timelineOrigin()) / rem - 1.5;
    const seconds = Math.max(0, endMs - startMs) / 1000;
    const zoom = Math.min(
      EditorApp.zoomMax,
      Math.max(
        EditorApp.zoomMin,
        seconds > 0 ? (room - clipRem) / seconds : 24,
      ),
    );
    this.setTimelineZoom(
      zoom,
      startMs + (seconds * 1000 + clipRem / zoom * 1000) / 2,
    );
  }
  /** Replace the selection and refresh everything that shows it.
   * @param {Iterable<string>} ids Steps to select.
   * @param {string} [primary] The step the inspector shows.
   * @returns {void}
   */
  setSelection(ids, primary) {
    this.selectedEventIds = new Set(ids);
    this._primary = primary ?? [...this.selectedEventIds].at(-1) ?? "";
    if (this.selectedEventIds.size) this.selectedSelectorId = "";
    this.afterSelectionChange();
  }
  /** Redraw the flow when the selection changes which action opens its row.
   * Only one selected action that expands shows its settings in place, so a
   * click that keeps the same row open, or none, leaves the flow untouched.
   * @returns {void}
   */
  syncExpandedRow() {
    const shown =
      document
        .querySelector('#table .edit-step-row[aria-expanded="true"]')
        ?.getAttribute("data-step") ?? "";
    const [only = ""] =
      this.selectedEventIds.size === 1 ? this.selectedEventIds : [];
    const event = this.activeFlow()?.events?.find(item => item.id === only);
    const definition = event ? definitionForEvent(event) : undefined;
    const wanted = definition && editsInRow(definition) ? only : "";
    if (wanted !== shown) this.renderTable();
  }
  /** Show the selection on every step and clip, and update what depends on it.
   * @returns {void}
   */
  afterSelectionChange() {
    this.syncExpandedRow();
    document.querySelectorAll("[data-step]").forEach(item => {
      const selected = this.selectedEventIds.has(
        item.getAttribute("data-step") ?? "",
      );
      item.classList.toggle("selected", selected);
      item.setAttribute("aria-pressed", String(selected));
    });
    const fit = document.getElementById("timeline-fit-selection");
    if (fit instanceof HTMLButtonElement)
      fit.disabled = this.selectedEventIds.size === 0;
    this.updateFlowBar();
    const primary = this.activeFlow()?.events?.find(
      event => event.id === this._primary,
    );
    this.updateTimelineClock(primary ? (primary.elapsed_ms ?? 0) : null);
    this.renderInspector();
    this.renderEditEvidence();
    EditorApp.element("inspector").scrollTop = 0;
    this.highlightSelectedAction();
    const count = this.selectedEventIds.size;
    if (count > 1)
      EditorApp.element("status").textContent = `${count} steps selected`;
  }
  /** Highlight the element targeted by the one selected action.
   * @returns {Promise<void>}
   */
  async highlightSelectedAction() {
    const event =
      this.selectedEventIds.size === 1
        ? this.activeFlow()?.events?.find(item => item.id === this._primary)
        : undefined;
    const saved = event?.selector_id
      ? this.selectors().find(item => item.selector_id === event.selector_id)
      : undefined;
    const expression = saved?.expression ?? event?.selector ?? "";
    const key = event && expression ? `${event.id}:${expression}` : "";
    if (
      !key ||
      key === this.actionHighlightKey ||
      this.snapshot?.target_state !== "ready" ||
      this.snapshot?.execution_run_id
    ) {
      if (!key) {
        this.actionHighlightKey = "";
        LiveTarget.clearMatches();
      }
      return;
    }
    this.actionHighlightKey = key;
    try {
      await this.call("selector.test", {
        selector_id: saved?.selector_id ?? "",
        expression,
        expected_count: saved?.expected_count ?? "any",
        checks: saved?.checks ?? [],
      });
    } catch (error) {
      this.actionHighlightKey = "";
      EditorApp.element("status").textContent =
        error instanceof Error ? error.message : String(error);
    }
  }
  /** Drag an empty area of the timeline to select the clips it touches.
   * Shift, Ctrl or ⌘ adds them to the current selection instead of replacing it.
   * @param {PointerEvent} down
   * @returns {void}
   */
  beginMarquee = down => {
    const timeline = EditorApp.element("timeline");
    if (
      down.button !== 0 ||
      this.timelineTool !== "select" ||
      !(down.target instanceof Element) ||
      !down.target.closest(".clips") ||
      down.target.closest(".clip, .timeline-cursor")
    )
      return;
    const additive = down.shiftKey || down.ctrlKey || down.metaKey;
    const base = additive ? [...this.selectedEventIds] : [];
    /** @param {PointerEvent} event
     * @returns {{x:number,y:number}}
     */
    const space = event => {
      const box = timeline.getBoundingClientRect();
      return {
        x: event.clientX - box.left + timeline.scrollLeft,
        y: event.clientY - box.top + timeline.scrollTop,
      };
    };
    const from = space(down);
    const box = timeline.getBoundingClientRect();
    const targets = [...timeline.querySelectorAll(".clip[data-step]")]
      .filter(clip => clip instanceof HTMLElement)
      .map(clip => {
        const rect = clip.getBoundingClientRect();
        return {
          clip,
          id: clip.getAttribute("data-step") ?? "",
          left: rect.left - box.left + timeline.scrollLeft,
          right: rect.right - box.left + timeline.scrollLeft,
          top: rect.top - box.top + timeline.scrollTop,
          bottom: rect.bottom - box.top + timeline.scrollTop,
        };
      });
    const band = document.createElement("div");
    band.className = "timeline-marquee";
    band.setAttribute("aria-hidden", "true");
    /** @type {typeof targets} */
    let hits = [];
    let moved = false;
    const gesture = {
      /** @param {PointerEvent} move
       */
      move: move => {
        if (
          !moved &&
          Math.hypot(move.clientX - down.clientX, move.clientY - down.clientY) <
            4
        )
          return;
        if (!moved) {
          moved = true;
          window.getSelection()?.removeAllRanges();
          timeline.classList.add("is-marquee");
          timeline.append(band);
        }
        const edge = timeline.getBoundingClientRect();
        if (move.clientX > edge.right - 28) timeline.scrollLeft += 14;
        else if (move.clientX < edge.left + 190) timeline.scrollLeft -= 14;
        const to = space(move);
        const x = Math.min(from.x, to.x);
        const y = Math.min(from.y, to.y);
        const width = Math.abs(to.x - from.x);
        const height = Math.abs(to.y - from.y);
        Object.assign(band.style, {
          left: `${x}px`,
          top: `${y}px`,
          width: `${width}px`,
          height: `${height}px`,
        });
        hits = targets.filter(
          item =>
            item.left < x + width &&
            item.right > x &&
            item.top < y + height &&
            item.bottom > y,
        );
        for (const item of targets)
          item.clip.classList.toggle("is-marquee-hit", hits.includes(item));
      },
      finish: () => {
        timeline.removeEventListener("pointermove", gesture.move);
        timeline.removeEventListener("pointerup", gesture.finish);
        timeline.removeEventListener("pointercancel", gesture.finish);
        if (timeline.hasPointerCapture(down.pointerId))
          timeline.releasePointerCapture(down.pointerId);
        band.remove();
        timeline.classList.remove("is-marquee");
        for (const item of targets)
          item.clip.classList.remove("is-marquee-hit");
        if (!moved) {
          if (!additive && this.selectedEventIds.size) {
            this.selectedEventId = "";
            this.afterSelectionChange();
          }
          return;
        }
        this.suppressClickUntil = performance.now() + 300;
        const earliest = [...hits].sort((a, b) => a.left - b.left)[0]?.id;
        this.setSelection(
          [...base, ...hits.map(item => item.id)],
          earliest ?? base.at(-1),
        );
      },
    };
    timeline.setPointerCapture(down.pointerId);
    timeline.addEventListener("pointermove", gesture.move);
    timeline.addEventListener("pointerup", gesture.finish);
    timeline.addEventListener("pointercancel", gesture.finish);
  };
  /** Bind step selection, editing and ordering interactions.
   * @param {HTMLElement} target
   */
  bindSteps(target) {
    target.querySelectorAll("[data-step]").forEach(node => {
      const activeStep = this.selectedEventIds.has(
        node.getAttribute("data-step") ?? "",
      );
      node.classList.toggle("selected", activeStep);
      node.setAttribute("aria-pressed", String(activeStep));
      if (node instanceof HTMLButtonElement && node.matches(".edit-step-row"))
        node.addEventListener("keydown", event => {
          if (
            event.altKey &&
            !event.ctrlKey &&
            !event.metaKey &&
            (event.key === "ArrowUp" || event.key === "ArrowDown")
          ) {
            event.preventDefault();
            this.command("event.move", {
              event_id: node.getAttribute("data-step") ?? "",
              offset: event.key === "ArrowUp" ? "-1" : "1",
            });
            return;
          }
          if (event.altKey || event.ctrlKey || event.metaKey) return;
          const rows = Array.from(target.querySelectorAll(".edit-step-row"));
          const index = rows.indexOf(node);
          const next =
            event.key === "ArrowDown"
              ? index + 1
              : event.key === "ArrowUp"
                ? index - 1
                : event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? rows.length - 1
                    : null;
          if (next === null) return;
          event.preventDefault();
          const destination =
            rows[Math.max(0, Math.min(rows.length - 1, next))];
          if (destination instanceof HTMLButtonElement) {
            destination.focus();
            destination.click();
          }
        });

      node.addEventListener("contextmenu", menu => {
        if (!(menu instanceof MouseEvent) || !menu.ctrlKey) return;
        menu.preventDefault();
        node.dispatchEvent(
          new MouseEvent("click", { bubbles: true, ctrlKey: true }),
        );
      });
      node.addEventListener("click", click => {
        if (
          performance.now() < this.suppressClickUntil ||
          !(click instanceof MouseEvent)
        )
          return;
        const id = node.getAttribute("data-step") ?? "";
        const events = this.activeFlow()?.events ?? [];
        if (click.shiftKey && this._anchor) {
          const a = events.findIndex(event => event.id === this._anchor);
          const b = events.findIndex(event => event.id === id);
          if (a >= 0 && b >= 0) {
            const range = events.slice(Math.min(a, b), Math.max(a, b) + 1);
            this.setSelection(
              range.map(event => event.id),
              id,
            );
            return;
          }
        }
        if (click.ctrlKey || click.metaKey) {
          const next = new Set(this.selectedEventIds);
          if (next.has(id)) next.delete(id);
          else next.add(id);
          this._anchor = id;
          this.setSelection(next, next.has(id) ? id : ([...next].at(-1) ?? ""));
          return;
        }
        this.selectedEventId = id;
        this.afterSelectionChange();
      });
    });
  }
  /** Resume redraws held back while an item was being dragged.
   * @returns {void}
   */
  endDrag() {
    this.dragging = false;
    if (!this.renderDeferred) return;
    this.renderDeferred = false;
    this.render();
  }
  /** Reorder steps by dragging a row; the drop line shows the landing spot.
   * @param {HTMLElement} list
   * @returns {void}
   */
  bindStepDrag(list) {
    this.bindRowDrag(list, ".edit-step-row", {
      // Tokens and code blocks keep their own clicks, so a drag starts from the rest of the card.
      skip: target => Boolean(target.closest(".edit-step-more, [data-field]")),
      drop: (row, index) =>
        this.command("event.reorder", {
          event_id: row.getAttribute("data-step") || "",
          index: String(index),
        }),
    });
  }
  /** Drag any list row with one look: lifted row, drop line, Escape cancels.
   * @param {HTMLElement} list Container of the rows.
   * @param {string} selector Selects the draggable rows.
   * @param {{skip:(target:Element)=>boolean,drop:(row:HTMLElement,index:number)=>void}} options
   * Skip names controls that must keep their own clicks; drop receives the new index.
   * @returns {void}
   */
  bindRowDrag(list, selector, options) {
    const rows = () =>
      Array.from(list.querySelectorAll(selector)).filter(
        item => item instanceof HTMLElement,
      );
    rows().forEach(row => {
      row.addEventListener("pointerdown", down => {
        if (down.button !== 0) return;
        if (down.target instanceof Element && options.skip(down.target)) return;
        const grip =
          down.target instanceof Element &&
          down.target.closest(".edit-step-grip");
        if (down.pointerType === "touch" && !grip) return;
        const originY = down.clientY;
        const scroller = row.closest(".table-content");
        let moved = false;
        let cancelled = false;
        let dropIndex = -1;
        const drag = {
          /** @param {PointerEvent} move
           */
          move: move => {
            const dy = move.clientY - originY;
            if (!moved && Math.abs(dy) < 5) return;
            if (!moved) {
              moved = true;
              this.dragging = true;
              window.getSelection()?.removeAllRanges();
              row.classList.add("is-dragging");
              document.body.classList.add("step-dragging");
            }
            if (scroller instanceof HTMLElement) {
              const box = scroller.getBoundingClientRect();
              if (move.clientY < box.top + 28) scroller.scrollTop -= 10;
              else if (move.clientY > box.bottom - 28) scroller.scrollTop += 10;
            }
            row.style.transform = `translateY(${dy}px)`;
            const others = rows().filter(item => item !== row);
            for (const item of others) item.removeAttribute("data-drop");
            const before = others.find(item => {
              const box = item.getBoundingClientRect();
              return move.clientY < box.top + box.height / 2;
            });
            dropIndex = before ? others.indexOf(before) : others.length;
            if (before) before.setAttribute("data-drop", "before");
            else others.at(-1)?.setAttribute("data-drop", "after");
          },
          /** @param {KeyboardEvent} key
           */
          key: key => {
            if (key.key !== "Escape") return;
            cancelled = true;
            drag.finish();
          },
          finish: () => {
            row.removeEventListener("pointermove", drag.move);
            row.removeEventListener("pointerup", drag.finish);
            row.removeEventListener("pointercancel", drag.finish);
            document.removeEventListener("keydown", drag.key);
            if (row.hasPointerCapture(down.pointerId))
              row.releasePointerCapture(down.pointerId);
            const current = rows().indexOf(row);
            for (const item of rows()) item.removeAttribute("data-drop");
            row.classList.remove("is-dragging");
            row.style.removeProperty("transform");
            document.body.classList.remove("step-dragging");
            if (!moved) return;
            this.endDrag();
            this.suppressClickUntil = performance.now() + 300;
            if (!cancelled && dropIndex >= 0 && dropIndex !== current)
              options.drop(row, dropIndex);
          },
        };
        row.setPointerCapture(down.pointerId);
        row.addEventListener("pointermove", drag.move);
        row.addEventListener("pointerup", drag.finish);
        row.addEventListener("pointercancel", drag.finish);
        document.addEventListener("keydown", drag.key);
      });
    });
  }
  /** Drag a clip along the time axis; dropping re-times the step and orders the flow by time. Alt+←/→ nudges a focused clip.
   * @param {HTMLElement} root
   * @returns {void}
   */
  bindClipDrag(root) {
    const rem =
      Number.parseFloat(getComputedStyle(document.documentElement).fontSize) ||
      16;
    /** @returns {number}
     */
    const quantum = () => this.timelineSnap ? this.timelineTick / 2 : 10;
    /** @param {number} milliseconds
     * @returns {number}
     */
    const snap = milliseconds =>
      Math.max(0, Math.round(milliseconds / quantum()) * quantum());
    root.querySelectorAll(".clip[data-step]").forEach(clip => {
      if (!(clip instanceof HTMLElement)) return;
      const eventId = clip.getAttribute("data-step") || "";
      const start =
        this.activeFlow()?.events?.find(item => item.id === eventId)
          ?.elapsed_ms ?? 0;
      clip.addEventListener("keydown", key => {
        if (
          !key.altKey ||
          (key.key !== "ArrowLeft" && key.key !== "ArrowRight")
        )
          return;
        key.preventDefault();
        this.command("event.retime", {
          event_id: eventId,
          elapsed_ms: String(
            Math.max(
              0,
              start + (key.key === "ArrowRight" ? 1 : -1) * quantum(),
            ),
          ),
        });
      });
      clip.addEventListener("pointerdown", down => {
        const lane = clip.closest(".clips");
        if (
          down.button !== 0 ||
          this.timelineTool !== "select" ||
          !(lane instanceof HTMLElement)
        )
          return;
        const originX = down.clientX;
        let moved = false;
        let cancelled = false;
        let target = start;
        let delta = 0;
        // Dragging a selected clip moves the whole selection together.
        const grouped =
          this.selectedEventIds.has(eventId) && this.selectedEventIds.size > 1;
        const clips = grouped
          ? [...root.querySelectorAll(".clip[data-step]")].flatMap(item =>
              item instanceof HTMLElement &&
              this.selectedEventIds.has(item.getAttribute("data-step") ?? "")
                ? [item]
                : [],
            )
          : [clip];
        const starts = new Map(
          clips.map(item => {
            const id = item.getAttribute("data-step") ?? "";
            return [
              id,
              this.activeFlow()?.events?.find(event => event.id === id)
                ?.elapsed_ms ?? 0,
            ];
          }),
        );
        const earliest = Math.min(...starts.values());
        const line = document.createElement("span");
        line.className = "timeline-drop-line";
        line.setAttribute("aria-hidden", "true");
        const drag = {
          /** @param {PointerEvent} move
           */
          move: move => {
            const dx = move.clientX - originX;
            if (!moved && Math.abs(dx) < 4) return;
            if (!moved) {
              moved = true;
              this.dragging = true;
              window.getSelection()?.removeAllRanges();
              for (const item of clips) item.classList.add("is-dragging");
              document.body.classList.add("clip-dragging");
              lane.append(line);
            }
            // No clip of the group may be pushed before time zero.
            delta = Math.max(
              snap(
                start + dx / rem / this.timelineScale * this.timelineTick,
              ) - start,
              -earliest,
            );
            target = start + delta;
            const shift =
              delta / this.timelineTick * this.timelineScale * rem;
            for (const item of clips)
              item.style.transform = `translateX(${shift}px)`;
            line.style.left = `${(target / this.timelineTick) * this.timelineScale}rem`;
            this.updateTimelineClock(target);
          },
          /** @param {KeyboardEvent} key
           */
          key: key => {
            if (key.key !== "Escape") return;
            cancelled = true;
            drag.finish();
          },
          finish: () => {
            clip.removeEventListener("pointermove", drag.move);
            clip.removeEventListener("pointerup", drag.finish);
            clip.removeEventListener("pointercancel", drag.finish);
            document.removeEventListener("keydown", drag.key);
            if (clip.hasPointerCapture(down.pointerId))
              clip.releasePointerCapture(down.pointerId);
            line.remove();
            for (const item of clips) {
              item.classList.remove("is-dragging");
              item.style.removeProperty("transform");
            }
            document.body.classList.remove("clip-dragging");
            if (!moved) return;
            this.endDrag();
            this.suppressClickUntil = performance.now() + 300;
            this.updateTimelineClock(cancelled ? start : target);
            if (cancelled || delta === 0) return;
            // One retime per step, in order, so each reply carries the revision the next needs.
            Promise.resolve(
              [...starts.entries()].reduce(async (pending, [id, from]) => {
                await pending;
                await this.command("event.retime", {
                  event_id: id,
                  elapsed_ms: String(Math.max(0, from + delta)),
                });
              }, Promise.resolve()),
            ).catch(() => undefined);
          },
        };
        clip.setPointerCapture(down.pointerId);
        clip.addEventListener("pointermove", drag.move);
        clip.addEventListener("pointerup", drag.finish);
        clip.addEventListener("pointercancel", drag.finish);
        document.addEventListener("keydown", drag.key);
      });
    });
  }
  /** Render settings for the selected flow, step or transition.
   * @returns {void}
   * @throws {Error} When a selected connection was removed before it saved.
   */
  renderInspector() {
    const flow = this.activeFlow();
    const target = EditorApp.element("inspector");

    if (this.selectedSelectorId) {
      this.renderSelectorEditor();
      return;
    }

    const edge =
      this.workspaceView === "graph"
        ? this.workspace?.edges?.find(
            item =>
              `${item.source}:${item.target}` === this.selectedGraphEdge,
          )
        : undefined;
    if (edge) {
      const inspector = graphConnectionInspector(
        edge,
        this.workspace?.flows ?? [],
        () => {
          this.selectedGraphEdge = "";
          this.inspectorKey = "";
          this.command("edge.remove", {
            source: edge.source,
            target: edge.target,
            mode: edge.mode || "always",
            condition_expression: edge.condition_expression || "",
            priority: edge.priority ?? 0,
            max_traversals: edge.max_traversals ?? 1,
          });
        },
        async value => {
          const index = this.workspace?.edges?.indexOf(edge) ?? -1;
          if (index < 0) throw new Error("This connection no longer exists.");
          const snapshot = await this.call("edge.update", {
            index: String(index),
            ...value,
          });
          this.applySnapshot(snapshot);
        },
      );
      target.replaceChildren(inspector);
      const condition = inspector.querySelector(
        '[name="condition_expression"]',
      );
      if (condition instanceof HTMLInputElement)
        attachConditionField(condition, this.conditionSource());
      return;
    }
    if (!flow) {
      target.textContent = "Create a flow to begin.";
      return;
    }
    // Graph shows flows and connections only; steps are edited in the Flow editor.
    const event =
      this.workspaceView === "graph"
        ? undefined
        : flow.events?.find(item => item.id === this.selectedEventId);
    const key = `${this.workspaceView === "graph" ? "graph" : "edit"}:${flow.id}:${event?.id || "settings"}`;
    if (this.inspectorKey === key && target.contains(document.activeElement))
      return;
    this.inspectorKey = key;
    if (event) {
      target.replaceChildren(
        EditorApp.template("edit-step-inspector-template"),
      );
      target
        .querySelector("[data-inspector-icon]")
        ?.setAttribute("data-icon", EditorApp.eventIcon(event));
      const heading = target.querySelector("[data-inspector-title]");
      if (heading)
        heading.textContent = event.label || EditorApp.eventTitle(event);
      const subtitle = target.querySelector("[data-inspector-subtitle]");
      if (subtitle)
        subtitle.textContent = `Step ${String((flow.events || []).indexOf(event) + 1).padStart(2, "0")} · ${event.kind}`;
      for (const name of /** @type {const} */ ([
        "label",
        "selector",
        "url",
        "payload",
      ])) {
        const input = target.querySelector(`#step-form [name="${name}"]`);
        if (
          input instanceof HTMLInputElement ||
          input instanceof HTMLTextAreaElement
        )
          input.value =
            name === "label" ? event.label || event.kind : event[name] || "";
        if (name === "payload" && event.payload === "__screenshot__")
          input?.parentElement?.remove();
        else if (input?.parentElement) {
          if (name === "url")
            input.parentElement.hidden =
              event.kind !== "url_change" && !event.url;
          if (name === "selector")
            input.parentElement.hidden =
              ["url_change", "wait"].includes(event.kind) ||
              event.payload === "__screenshot__";
          if (name === "payload")
            input.parentElement.hidden =
              ![
                "input_text",
                "fill",
                "keystroke",
                "javascript",
                "wait",
              ].includes(event.kind) && !event.payload;
        }
      }
      const definition = definitionForEvent(event);
      // An action that expands keeps its parameters in its flow row, so
      // Properties holds only the settings every action shares.
      const ownedByRow = definition !== undefined && editsInRow(definition);
      const actionFields = target.querySelector("#action-fields");
      if (definition && !ownedByRow && actionFields instanceof HTMLElement) {
        configureActionForm({
          fields: actionFields,
          kind: definition.id,
          snapshot: this.snapshot,
          variables: EditorApp.variableSources({
            ...flow,
            events: (flow.events ?? []).slice(
              0,
              (flow.events ?? []).indexOf(event),
            ),
          }),
          selectorTools: this.actionSelectorTools(),
          event,
        });
        actionFields.hidden = false;
      }
      if (definition) this.mountGuard(target, flow, event);
      const checks = target.querySelector(".edit-check-list");
      for (const check of event.contract?.postconditions || []) {
        const item = document.createElement("li");
        const label = document.createElement("span");
        label.textContent = `${check.kind.replaceAll("_", " ")} · ${check.target || check.expected || ""}`;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.textContent = "Remove check";
        remove.setAttribute("data-remove-check", check.id);
        item.append(label, remove);
        checks?.append(item);
      }
      EditorApp.element("back-settings").addEventListener("click", () => {
        this.selectedEventId = "";
        this.renderTable();
        this.renderInspector();
        this.renderEditEvidence();
      });
      this.populateStepTargeting(
        target,
        event,
        definition?.fields.some(item => item.type === "selector") ?? false,
      );
      // A single-line action's own settings ride inside the form in
      // #action-fields, so one save configures the action and its targeting
      // and failure policy. An expanding action is configured in its row, so
      // this save sends its parameters back unchanged.
      const stepForm = target.querySelector("#step-form");
      const configures = definition !== undefined && !ownedByRow;
      this.bindForm(
        "step-form",
        configures ? "event.configure" : "event.update",
        ownedByRow
          ? {
              event_id: event.id,
              selector: event.selector ?? "",
              selector_id: event.selector_id ?? "",
              url: event.url ?? "",
              ...(event.payload === null || event.payload === undefined
                ? {}
                : { payload: event.payload }),
            }
          : {
              event_id: event.id,
              payload: event.payload || "",
            },
        data => {
          if (!(configures && stepForm instanceof HTMLFormElement))
            return EditorApp.stepPayload(data);
          const merged = { ...data, ...actionCommand(stepForm, definition) };
          // The workbench FormData reads checkboxes as "on"; keep the booleans.
          for (const input of stepForm.querySelectorAll('input[type="checkbox"]'))
            if (input instanceof HTMLInputElement)
              merged[input.name] = input.checked;
          return EditorApp.stepPayload(merged);
        },
      );
      this.bindStepTargeting(target, event);
      const assertSelector = target.querySelector(
        '#assert-form select[name="target_selector_id"]',
      );
      const assertInline = target.querySelector(
        '#assert-form input[name="target"]',
      );
      const assertAdd = target.querySelector("[data-add-check-selector]");
      if (
        assertSelector instanceof HTMLSelectElement &&
        assertInline instanceof HTMLInputElement
      )
        bindSelectorReference({
          select: assertSelector,
          inline: assertInline,
          selectors: this.selectors(),
          add: assertAdd instanceof HTMLElement ? assertAdd : null,
          onAdd: () => this.selectSelector("new"),
        });
      if (assertInline instanceof HTMLInputElement) this.mountSelectorWidget(assertInline, "Expression");
      this.bindForm(
        "assert-form",
        "event.assert",
        { event_id: event.id },
        ({ target_selector_id: reference, target: expression, ...rest }) => ({
          ...rest,
          selector_id: reference,
          target: reference ? "" : expression,
          target_selector_id: undefined,
        }),
      );
      target.querySelectorAll("[data-remove-check]").forEach(node => {
        node.addEventListener("click", () => {
          this.command("event.assert.remove", {
            event_id: event.id,
            assertion_id: node.getAttribute("data-remove-check") || "",
          });
        });
      });
      const checkKind = target.querySelector('select[name="kind"]');
      const checkTarget = target.querySelector(
        '#assert-form input[name="target"]',
      );
      const checkExpected = target.querySelector(
        '#assert-form input[name="expected"]',
      );
      const updateCheckFields = () => {
        if (
          checkKind instanceof HTMLSelectElement &&
          checkTarget instanceof HTMLInputElement &&
          checkExpected instanceof HTMLInputElement
        ) {
          const dom = checkKind.value.startsWith("dom_");
          checkTarget.required = dom;
          const targetField = target.querySelector("[data-check-target]");
          if (targetField instanceof HTMLElement) targetField.hidden = !dom;
          checkExpected.required = checkKind.value !== "dom_visible";
          if (checkExpected.parentElement)
            checkExpected.parentElement.hidden = !checkExpected.required;
        }
      };
      checkKind?.addEventListener("change", updateCheckFields);
      updateCheckFields();
      const eventIndex = (flow.events || []).indexOf(event);
      const up = EditorApp.element("step-up");
      const down = EditorApp.element("step-down");
      if (up instanceof HTMLButtonElement) up.disabled = eventIndex === 0;
      if (down instanceof HTMLButtonElement)
        down.disabled = eventIndex === (flow.events || []).length - 1;
      up.addEventListener("click", () =>
        this.command("event.move", {
          event_id: event.id,
          offset: "-1",
        }),
      );
      EditorApp.element("step-down").addEventListener("click", () =>
        this.command("event.move", {
          event_id: event.id,
          offset: "1",
        }),
      );
      EditorApp.element("step-delete").addEventListener("click", async () => {
        if (await EditorApp.confirmDelete())
          this.command("event.delete", {
            event_id: event.id,
          });
      });
    } else {
      target.replaceChildren(
        EditorApp.template("edit-flow-inspector-template"),
      );
      const summary = target.querySelector("[data-flow-summary]");
      if (summary)
        summary.textContent = `${flow.events?.length || 0} steps · ${flow.device_modes?.join(", ") || "shared"}`;
      for (const name of /** @type {const} */ ([
        "name",
        "task_description",
        "expected_behavior",
      ])) {
        const input = target.querySelector(`[name="${name}"]`);
        if (
          input instanceof HTMLInputElement ||
          input instanceof HTMLTextAreaElement
        )
          input.value = flow[name] || "";
      }
      for (const name of /** @type {const} */ ([
        "capture_record_images",
        "capture_play_images",
      ])) {
        const input = target.querySelector(`[name="${name}"]`);
        if (input instanceof HTMLInputElement)
          input.checked = Boolean(flow[name]);
      }
      const scope = target.querySelector("[data-flow-scope-options]");
      if (scope instanceof HTMLElement) {
        const profiles = /** @type {Array<{id:string,name:string}>} */ (
          /** @type {{profiles?:unknown}} */ (this.workspace ?? {}).profiles ??
            []
        );
        const selected = new Set(flow.device_modes?.length
          ? flow.device_modes
          : ["shared"]);
        /** One profile scope checkbox row.
         * @param {string} id
         * @param {string} label
         * @returns {HTMLLabelElement}
         */
        const choice = (id, label) => {
          const input = document.createElement("input");
          input.type = "checkbox";
          input.name = `device_scope__${id}`;
          input.checked = selected.has(id);
          const row = document.createElement("label");
          row.className = "check";
          row.append(input, label);
          return row;
        };
        scope.replaceChildren(
          choice("shared", "Shared across profiles"),
          ...profiles.map(profile => choice(profile.id, profile.name)),
        );
        scope.addEventListener("change", changeEvent => {
          const changed = changeEvent.target;
          if (!(changed instanceof HTMLInputElement) || !changed.checked)
            return;
          const shared = scope.querySelector('[name="device_scope__shared"]');
          if (changed === shared)
            scope.querySelectorAll('input:not([name="device_scope__shared"])')
              .forEach(input => {
                if (input instanceof HTMLInputElement) input.checked = false;
              });
          else if (shared instanceof HTMLInputElement) shared.checked = false;
        });
      }
      const inputsField = flowInputsField(flow.parameters ?? []);
      target.querySelector("[data-flow-inputs]")?.replaceChildren(inputsField.element);
      this.bindForm("flow-form", "flow.update", {}, data => {
        const scopes = Object.entries(data)
          .filter(([name, value]) => name.startsWith("device_scope__") && value)
          .map(([name]) => name.slice("device_scope__".length));
        const payload = {
          ...data,
          device_scopes: scopes.length ? scopes : ["shared"],
          parameters: inputsField.read(),
        };
        return Object.fromEntries(
          Object.entries(payload).filter(
            ([name]) => !name.startsWith("device_scope__"),
          ),
        );
      });
      const remove = target.querySelector("#flow-delete");
      const note = target.querySelector("#flow-delete-note");
      const last = (this.workspace?.flows?.length ?? 0) <= 1;
      if (remove instanceof HTMLButtonElement) {
        remove.disabled = last;
        remove.addEventListener("click", () => this.deleteFlow(flow.id));
      }
      if (note)
        note.textContent = last ? "A project needs at least one flow." : "";
    }
  }
  /** Render owned screenshot evidence; never imply a live embedded browser.
   */
  renderEditEvidence() {
    const target = EditorApp.element("edit-evidence");
    const shot = (this.workspace?.screenshots || []).find(
      item =>
        item.flow_id === this.activeFlowId &&
        (!this.selectedEventId || item.event_id === this.selectedEventId),
    );
    target.replaceChildren();
    if (shot) {
      const image = document.createElement("img");
      image.src = `/artifacts/${encodeURIComponent(shot.id)}`;
      image.alt = `Captured ${shot.phase} evidence for the selected flow`;
      const caption = document.createElement("small");
      caption.textContent = `Captured evidence · ${shot.width} × ${shot.height}`;
      target.append(image, caption);
    }
  }
  /** @returns {Promise<boolean>}
   */
  static confirmDelete = (
    copy = {
      title: "Delete this step?",
      body: "This also removes screenshots attached to this step.",
      keep: "Keep step",
      remove: "Delete step",
    },
  ) => {
    const trigger = document.activeElement;
    const dialog = document.createElement("dialog");
    dialog.className = "delete-dialog";
    dialog.setAttribute("aria-labelledby", "delete-dialog-title");
    const form = document.createElement("form");
    form.method = "dialog";
    const title = document.createElement("h2");
    title.id = "delete-dialog-title";
    title.textContent = copy.title;
    const body = document.createElement("p");
    body.textContent = copy.body;
    const tools = document.createElement("div");
    tools.className = "step-tools";
    const keep = document.createElement("button");
    keep.value = "cancel";
    keep.autofocus = true;
    keep.textContent = copy.keep;
    const remove = document.createElement("button");
    remove.value = "delete";
    remove.className = "step-delete";
    remove.textContent = copy.remove;
    tools.append(keep, remove);
    form.append(title, body, tools);
    dialog.append(form);
    dialog.addEventListener("keydown", event => {
      if (event.key !== "Tab") return;
      const buttons = Array.from(dialog.querySelectorAll("button"));
      const index = buttons.findIndex(
        button => button === document.activeElement,
      );
      const next =
        buttons[
          (index + (event.shiftKey ? -1 : 1) + buttons.length) % buttons.length
        ];
      if (next) {
        event.preventDefault();
        next.focus();
      }
    });
    document.body.append(dialog);
    return new Promise(resolve => {
      dialog.addEventListener(
        "close",
        () => {
          const approved = dialog.returnValue === "delete";
          dialog.remove();
          if (trigger instanceof HTMLElement && trigger.isConnected)
            trigger.focus({
              preventScroll: true,
            });
          resolve(approved);
        },
        {
          once: true,
        },
      );
      dialog.showModal();
    });
  };
  /** Ask how to save a selector that other actions already use.
   * @param {{actions:unknown[],flows:number}} use
   * @returns {Promise<"update"|"copy"|"cancel">}
   */
  static confirmShared = use => {
    const trigger = document.activeElement;
    const dialog = document.createElement("dialog");
    dialog.className = "delete-dialog";
    dialog.setAttribute("aria-labelledby", "shared-dialog-title");
    const form = document.createElement("form");
    form.method = "dialog";
    const title = document.createElement("h2");
    title.id = "shared-dialog-title";
    title.textContent = "Other actions use this selector";
    const body = document.createElement("p");
    const n = use.actions.length;
    body.textContent = `${n} ${n === 1 ? "action" : "actions"} in ${use.flows} ${use.flows === 1 ? "flow" : "flows"} would change with it. Update them all, or keep them as they are and save your edit as a new selector.`;
    const tools = document.createElement("div");
    tools.className = "step-tools";
    const cancel = document.createElement("button");
    cancel.value = "cancel";
    cancel.autofocus = true;
    cancel.textContent = "Cancel";
    const copy = document.createElement("button");
    copy.value = "copy";
    copy.textContent = "Save as new selector";
    const update = document.createElement("button");
    update.value = "update";
    update.className = "selector-save";
    update.textContent = `Update ${n} ${n === 1 ? "action" : "actions"}`;
    tools.append(cancel, copy, update);
    form.append(title, body, tools);
    dialog.append(form);
    document.body.append(dialog);
    return new Promise(resolve => {
      dialog.addEventListener(
        "close",
        () => {
          const value = dialog.returnValue;
          dialog.remove();
          if (trigger instanceof HTMLElement && trigger.isConnected)
            trigger.focus({ preventScroll: true });
          resolve(value === "update" || value === "copy" ? value : "cancel");
        },
        { once: true },
      );
      dialog.showModal();
    });
  };
  /** Bind typed field updates to the selected editor model.
   * @param {string} id
   * @param {string} command
   * @param {Record<string,string|boolean> & {event_id?:string}} extra
   * @param {(data: Record<string,string|boolean>) => Record<string,unknown>} [transform]
   * @returns {void} Fields are bound in place when the form exists.
   */
  bindForm(id, command, extra = {}, transform = undefined) {
    const form = EditorApp.element(id);
    if (!(form instanceof HTMLFormElement)) return;
    const draftKey = `${this.activeFlow()?.id || ""}:${extra.event_id || "settings"}:${id}`;
    const controls = Array.from(
      form.querySelectorAll("input, select, textarea"),
    );
    const restored = this.inspectorDrafts.get(draftKey);
    for (const input of controls) {
      if (!(
        input instanceof HTMLInputElement ||
        input instanceof HTMLSelectElement ||
        input instanceof HTMLTextAreaElement
      ))
        continue;
      const value = restored?.[input.name];
      if (typeof value === "boolean" && input instanceof HTMLInputElement)
        input.checked = value;
      else if (typeof value === "string") input.value = value;
    }
    const state = document.createElement("div");
    state.className = "edit-form-state";
    const message = document.createElement("span");
    message.setAttribute("role", "status");
    message.textContent = "Unsaved edits";
    const discard = document.createElement("button");
    discard.type = "button";
    discard.textContent = "Discard edits";
    discard.addEventListener("click", () => {
      this.inspectorDrafts.delete(draftKey);
      this.inspectorKey = "";
      this.renderInspector();
      const refreshed = document.getElementById(id);
      const first = refreshed?.querySelector("input, select, textarea");
      if (first instanceof HTMLElement) first.focus();
    });
    state.append(message, discard);
    form.append(state);
    state.hidden = !restored;
    /** @returns {Record<string,string|boolean>}
     */
    const values = () => {
      const data = { ...extra };
      new FormData(form).forEach((value, key) => {
        data[key] = String(value);
      });
      form.querySelectorAll('input[type="checkbox"]').forEach(input => {
        if (input instanceof HTMLInputElement) data[input.name] = input.checked;
      });
      return data;
    };
    form.addEventListener("input", () => {
      this.inspectorDrafts.set(draftKey, values());
      state.hidden = false;
    });
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      if (button instanceof HTMLButtonElement) button.disabled = true;
      message.textContent = "Applying changes…";
      state.hidden = false;
      try {
        const result = await this.call(
          command,
          transform ? transform(values()) : values(),
        );
        this.inspectorDrafts.delete(draftKey);
        state.hidden = true;
        if (result.workspace) {
          this.inspectorKey = "";
          this.applySnapshot(result);
        }
        EditorApp.element("status").textContent =
          EditorApp.doneMessage(command);
      } catch (error) {
        message.textContent = "Could not apply. Your edits are kept; retry.";
        EditorApp.element("status").textContent =
          error instanceof Error ? error.message : String(error);
      } finally {
        if (button instanceof HTMLButtonElement) button.disabled = false;
      }
    });
  }
  /** Put a picked selector into the selected step's draft.
   * Only the selector changes; other unsaved fields of the step stay as typed
   * and nothing is saved until the user applies the step.
   * @param {string} selector Picked selector or strategy expression.
   * @returns {boolean} False when no visible selected step can take it.
   */
  applyPickedSelector(selector) {
    // An action's settings show the selector in a rich editor that owns the text.
    const editor = document.querySelector(
      '#step-form #action-fields .variable-field:has([name="selector"]) .variable-editor, .edit-step-detail-form .variable-field:has([name="selector"]) .variable-editor',
    );
    if (this.selectedEventId && editor instanceof HTMLElement) {
      editor.textContent = selector;
      editor.dispatchEvent(new Event("input", { bubbles: true }));
      editor.focus();
      EditorApp.element("status").textContent =
        "Selector placed in the selected step. Save the step to keep it.";
      return true;
    }
    const field = document.querySelector(
      '#step-form [name="selector"], .edit-step-detail-form [name="selector"]',
    );
    if (
      !this.selectedEventId ||
      !(field instanceof HTMLInputElement) ||
      field.closest("label")?.hidden ||
      !field.offsetParent
    )
      return false;
    field.value = selector;
    // The form's input listener stores the whole draft, including other fields.
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.focus();
    EditorApp.element("status").textContent =
      "Selector placed in the selected step. Save the step to keep it.";
    return true;
  }
  /** Render event timing tracks for the active flow.
   * @returns {void}
   */
  renderTimeline() {
    const events = this.activeFlow()?.events ?? [];
    const latestRun = this.workspace?.runs?.[0];
    const failedIds = new Set(
      (latestRun?.action_records ?? [])
        .filter(record => record.status === "failed")
        .map(record => record.event_id),
    );
    const groups = [
      "navigation",
      "interaction",
      "javascript",
      "assertion",
      "screenshots",
      "network",
      "timing",
      "diagnostics",
    ];
    const present = new Set(events.map(event => event.id));
    if ([...this.selectedEventIds].some(id => !present.has(id))) {
      this.selectedEventIds = new Set(
        [...this.selectedEventIds].filter(id => present.has(id)),
      );
      if (!present.has(this._primary))
        this._primary = [...this.selectedEventIds].at(-1) ?? "";
      if (!present.has(this._anchor)) this._anchor = this._primary;
    }
    const fitSelection = document.getElementById("timeline-fit-selection");
    if (fitSelection instanceof HTMLButtonElement)
      fitSelection.disabled = this.selectedEventIds.size === 0;
    this.updateFlowBar();
    const target = EditorApp.element("timeline");
    const interval = this.timelineTick;
    const scale = this.timelineScale;
    // Lane height lives in CSS (--dynamic-lane-h), so a short panel can shrink it.
    target.setAttribute(
      "data-lanes",
      this.workspaceView === "edit" ? "compact" : "roomy",
    );
    // The ruler always fills the panel, but never forces it wider: a fixed
    // minimum of ticks would make "fit" impossible at fine tick intervals.
    const rootRem =
      Number.parseFloat(getComputedStyle(document.documentElement).fontSize) ||
      16;
    const visibleMs =
      Math.max(0, target.clientWidth - EditorApp.timelineOrigin()) /
        rootRem /
        scale *
      interval;
    const clipMs = 5.75 / scale * interval;
    const duration = Math.max(
      visibleMs,
      ...events.map(event => (event.elapsed_ms || 0) + clipMs),
      (this.timelineMarker || 0) + interval,
      // The playhead is always reachable, however far the view is zoomed in.
      (this.timelineCursorMs || 0) + interval,
    );
    const count = Math.floor(duration / interval);
    target.style.setProperty(
      "--dynamic-timeline-duration",
      `${(duration / interval) * scale}rem`,
    );
    const selected = events.find(event => event.id === this.selectedEventId);
    const failedEvent = events.find(event => failedIds.has(event.id));
    const executed = events.find(
      event => event.id === latestRun?.action_records?.at(-1)?.event_id,
    );
    const playheadTime =
      latestRun?.status === "running"
        ? executed?.elapsed_ms
        : this.snapshot?.recording_state === "recording"
          ? events.at(-1)?.elapsed_ms
          : this.timelineStopped
            ? (selected?.elapsed_ms ?? failedEvent?.elapsed_ms)
            : this.timelineCursorMs;
    this.updateTimelineClock(
      latestRun?.status === "running" ||
        this.snapshot?.recording_state === "recording"
        ? (playheadTime ?? 0)
        : this.timelineStopped
          ? null
          : (playheadTime ?? null),
    );
    /** @param {number} milliseconds
     * @returns {string}
     */
    const position = milliseconds =>
      `${((milliseconds || 0) / interval) * scale}rem`;
    const playhead = "";
    const marker =
      this.timelineMarker === null
        ? ""
        : `<span class="timeline-marker" style="left:${position(this.timelineMarker)}"><small>${EditorApp.timecode(this.timelineMarker)}</small></span>`;
    const ruler = `<div class="timeline-ruler"><div class="ruler-label">Time, ${EditorApp.tickLabel(interval)} / tick</div><div class="ruler-ticks">${Array.from(
      { length: count + 1 },
      (_, index) =>
        `<span style="left:${index * scale}rem">${EditorApp.tickLabel(index * interval)}</span>`,
    ).join("")}${playhead}${marker}</div></div>`;
    const lanes = groups
      .map(layer => {
        /** @type {number[]} */
        const rowEnds = [];
        const clips = events
          .filter(event => {
            if (layer === "assertion")
              return (event.contract?.postconditions?.length ?? 0) > 0;
            if (layer === "diagnostics") return failedIds.has(event.id);
            if (
              event.recording_group_id &&
              this.visibleRecordings().some(
                group => group.id === event.recording_group_id,
              )
            )
              return false;
            return EditorApp.laneOf(event) === layer;
          })
          .map(event => {
            const left = (event.elapsed_ms || 0) / interval * scale;
            let row = rowEnds.findIndex(rowEnd => rowEnd <= left);
            if (row < 0) row = rowEnds.length;
            rowEnds[row] = left + 5.75;
            return `<button style="left:${left}rem;--dynamic-clip-top:calc(${row} * var(--dynamic-lane-h) + 0.25rem)" data-step="${EditorApp.escape(event.id)}" class="clip ${EditorApp.escape(layer)}" title="${EditorApp.escape(EditorApp.eventTitle(event))}, ${EditorApp.timecode(event.elapsed_ms || 0)}">${EditorApp.icon(EditorApp.eventIcon(event))}<span>${EditorApp.escape(EditorApp.eventTitle(event))}</span></button>`;
          })
          .join("");
        return `<div class="track"><div class="track-label">${EditorApp.icon(EditorApp.layerIcon(layer))}<span>${EditorApp.laneNames[layer] || layer}</span></div><div class="clips" style="min-height:calc(${Math.max(1, rowEnds.length)} * var(--dynamic-lane-h))">${clips}${playhead}</div></div>`;
      })
      .join("");
    target.innerHTML = `${ruler}${lanes}`;
    const firstLane = target.children[1] ?? null;
    for (const group of this.visibleRecordings()) {
      const children = events.filter(
        event => event.recording_group_id === group.id,
      );
      const track = document.createElement("div");
      track.className = "track recording-track";
      const label = document.createElement("div");
      label.className = "track-label";
      label.textContent = group.label;
      const clips = document.createElement("div");
      clips.className = "clips";
      const band = document.createElement("div");
      band.className = "recording-band";
      band.setAttribute("role", "group");
      band.setAttribute("aria-label", group.label);
      band.style.left = position(group.start_ms);
      const end = Math.max(
        group.start_ms + interval,
        ...children.map(
          event => (event.elapsed_ms ?? group.start_ms) + interval,
        ),
      );
      band.style.width = position(end - group.start_ms);
      /** @type {number[]} */
      const rowEnds = [];
      for (const event of children) {
        const left =
          ((event.elapsed_ms ?? group.start_ms) - group.start_ms) / interval *
          scale;
        band.style.width = `${Math.max(Number.parseFloat(band.style.width), left + 5.75)}rem`;
        let row = rowEnds.findIndex(rowEnd => rowEnd <= left);
        if (row < 0) row = rowEnds.length;
        rowEnds[row] = left + 5.75;
        const clip = document.createElement("button");
        clip.type = "button";
        clip.className = "clip interaction";
        clip.setAttribute("data-step", event.id);
        const icon = iconElement(EditorApp.eventIcon(event));
        const text = document.createElement("span");
        text.textContent = EditorApp.eventTitle(event);
        clip.append(icon, text);
        clip.title = `${EditorApp.eventTitle(event)} · ${EditorApp.timecode(event.elapsed_ms ?? 0)}`;
        clip.style.left = `${left}rem`;
        clip.style.setProperty(
          "--dynamic-clip-top",
          `calc(${row} * var(--dynamic-lane-h) + 0.25rem)`,
        );
        band.append(clip);
      }
      clips.style.minHeight = `calc(${Math.max(1, rowEnds.length)} * var(--dynamic-lane-h) + 0.5rem)`;
      clips.append(band);
      track.append(label, clips);
      target.insertBefore(track, firstLane);
    }
    this.bindSteps(EditorApp.element("timeline"));
    this.bindClipDrag(EditorApp.element("timeline"));
    const cursor = document.createElement("div");
    cursor.className = "timeline-cursor";
    cursor.tabIndex = 0;
    cursor.setAttribute("role", "slider");
    cursor.setAttribute("aria-label", "Timeline playhead");
    cursor.setAttribute("aria-orientation", "horizontal");
    cursor.setAttribute("aria-valuemin", "0");
    cursor.setAttribute("aria-valuemax", String(duration));
    const grip = document.createElement("span");
    grip.className = "timeline-cursor-grip";
    grip.setAttribute("aria-hidden", "true");
    cursor.append(grip);
    target.append(cursor);
    cursor.addEventListener("keydown", key => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(key.key)) return;
      key.preventDefault();
      const step = key.shiftKey ? this.timelineTick : this.timelineTick / 10;
      this.updateTimelineClock(
        key.key === "Home"
          ? 0
          : key.key === "End"
            ? duration
            : Math.max(
                0,
                Math.min(
                  duration,
                  this.timelineCursorMs +
                    (key.key === "ArrowRight" ? step : -step),
                ),
              ),
      );
      const box = cursor.getBoundingClientRect();
      const viewport = target.getBoundingClientRect();
      if (box.right > viewport.right)
        target.scrollLeft += box.right - viewport.right;
      else if (box.left < viewport.left)
        target.scrollLeft -= viewport.left - box.left;
    });
    this.updateTimelineCursor();
  }
  /** Align one continuous playhead with the shared, scrollable time axis. */
  updateTimelineCursor = () => {
    const timeline = EditorApp.element("timeline");
    const ruler = timeline.querySelector(".ruler-ticks");
    const cursor = timeline.querySelector(".timeline-cursor");
    if (!(ruler instanceof HTMLElement) || !(cursor instanceof HTMLElement))
      return;
    const rem =
      Number.parseFloat(getComputedStyle(document.documentElement).fontSize) ||
      16;
    const left =
      ruler.getBoundingClientRect().left -
      timeline.getBoundingClientRect().left +
      timeline.scrollLeft +
      this.timelineCursorMs / this.timelineTick * this.timelineScale * rem;
    const label = timeline.querySelector(".track-label");
    const labelRight = label
      ? label.getBoundingClientRect().right -
        timeline.getBoundingClientRect().left
      : 0;
    cursor.style.left = `${left}px`;
    const lastTrack = Array.from(timeline.querySelectorAll(".track")).at(-1);
    cursor.style.height = `${Math.max(timeline.clientHeight, lastTrack instanceof HTMLElement ? lastTrack.offsetTop + lastTrack.offsetHeight : 0)}px`;
    cursor.style.visibility =
      left - timeline.scrollLeft < labelRight ||
      left - timeline.scrollLeft > timeline.clientWidth
        ? "hidden"
        : "visible";
    cursor.setAttribute("aria-valuenow", String(this.timelineCursorMs));
    cursor.setAttribute(
      "aria-valuetext",
      EditorApp.timecode(this.timelineCursorMs),
    );
  };
  /** Scrub without changing actions; keep scrolling while held near either edge.
   * @param {PointerEvent} down
   */
  beginTimelineScrub = down => {
    const timeline = EditorApp.element("timeline");
    const ruler = timeline.querySelector(".ruler-ticks");
    if (
      down.button !== 0 ||
      this.timelineTool !== "select" ||
      !(down.target instanceof Element) ||
      !down.target.closest(".ruler-ticks, .timeline-cursor") ||
      !(ruler instanceof HTMLElement)
    )
      return;
    down.preventDefault();
    const start = this.timelineCursorMs;
    const maximum = Number(
      timeline
        .querySelector(".timeline-cursor")
        ?.getAttribute("aria-valuemax") ?? 0,
    );
    const rem =
      Number.parseFloat(getComputedStyle(document.documentElement).fontSize) ||
      16;
    let pointerX = down.clientX;
    let frame = 0;
    this.dragging = true;
    timeline.classList.add("is-scrubbing");
    timeline.setPointerCapture(down.pointerId);
    const position = () =>
      this.updateTimelineClock(
        Math.max(
          0,
          Math.min(
            maximum,
            Math.round(
              (pointerX - ruler.getBoundingClientRect().left) /
                rem /
                this.timelineScale *
                this.timelineTick,
            ),
          ),
        ),
      );
    const scroll = () => {
      const box = timeline.getBoundingClientRect();
      const left = Math.max(box.left, ruler.getBoundingClientRect().left);
      timeline.scrollLeft +=
        pointerX > box.right - 32 ? 10 : pointerX < left + 32 ? -10 : 0;
      position();
      frame = requestAnimationFrame(scroll);
    };
    const gesture = {
      /** @param {PointerEvent} event */
      move: event => {
        if (event.pointerId === down.pointerId) pointerX = event.clientX;
      },
      finish: () => {
        cancelAnimationFrame(frame);
        timeline.removeEventListener("pointermove", gesture.move);
        timeline.removeEventListener("pointerup", gesture.finish);
        timeline.removeEventListener("pointercancel", gesture.cancel);
        document.removeEventListener("keydown", gesture.escape);
        timeline.classList.remove("is-scrubbing");
        if (timeline.hasPointerCapture(down.pointerId))
          timeline.releasePointerCapture(down.pointerId);
        this.endDrag();
      },
      cancel: () => {
        this.updateTimelineClock(start);
        gesture.finish();
      },
      /** @param {KeyboardEvent} key */
      escape: key => {
        if (key.key === "Escape") gesture.cancel();
      },
    };
    timeline.addEventListener("pointermove", gesture.move);
    timeline.addEventListener("pointerup", gesture.finish);
    timeline.addEventListener("pointercancel", gesture.cancel);
    document.addEventListener("keydown", gesture.escape);
    position();
    frame = requestAnimationFrame(scroll);
  };
  /** Compact ruler label, for example 0s or 2.5s.
   * @param {number} milliseconds
   * @returns {string}
   */
  static tickLabel = milliseconds => {
    const seconds = milliseconds / 1000;
    if (seconds >= 60 && seconds % 60 === 0) return `${seconds / 60}m`;
    return `${Number.isInteger(seconds) ? seconds : seconds.toFixed(1)}s`;
  };
  /** Lane a step belongs to on the timeline.
   * @param {EditorEvent} event
   * @returns {string}
   */
  static laneOf = event => {
    if (event.kind === "screenshot" || event.payload === "__screenshot__")
      return "screenshots";
    if (event.kind === "javascript") return "javascript";
    return event.layer || "interaction";
  };
  /** @type {Record<string, string>} */
  static laneNames = {
    navigation: "Navigation",
    interaction: "Input",
    javascript: "JavaScript",
    assertion: "Assertions",
    screenshots: "Screenshots",
    network: "Network",
    timing: "Timing",
    diagnostics: "Diagnostics",
  };
  timelineStopped = true;
  /** Update only the display; playback remains owned by Studio.
   * @param {number|null} milliseconds Current elapsed playhead position, or stopped.
   * @returns {void}
   */
  updateTimelineClock = (/** @type {number|null} */ milliseconds) => {
    if (milliseconds !== null) this.timelineCursorMs = milliseconds;
    this.timelineStopped = milliseconds === null;
    const template = this.timelineStopped ? "dd:dd:dd.dd" : "dd:dd:dd.ddd";
    if (this.timelineClock.settings.template !== template)
      this.timelineClock.settings.template = template;
    if (milliseconds === null) this.timelineClock.clear();
    else
      this.timelineClock.setTime(
        Math.max(0, Math.min(359999999, milliseconds)),
      );
    EditorApp.element("timecode").title =
      milliseconds === null
        ? "Playhead stopped"
        : `Playhead ${EditorApp.timecode(milliseconds)}`;
    this.updateTimelineCursor();
  };
  static timecode = (/** @type {number} */ milliseconds) => {
    const seconds = Math.floor(milliseconds / 1000);
    return `${String(Math.floor(seconds / 3600)).padStart(2, "0")}:${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}.${String(milliseconds % 1000).padStart(3, "0")}`;
  };
  /** Kinds whose targets may be processed at the same time. */
  static PARALLEL_KINDS = Object.freeze([
    "javascript",
    "input_text",
    "select_option",
    "note",
    "snapshot",
  ]);
  /** Kinds that act on an element, so they can use a selector and targeting. */
  static TARGETED_KINDS = Object.freeze([
    "click",
    "double_click",
    "right_click",
    "hover",
    "drag",
    "scroll",
    "gesture",
    "check",
    "uncheck",
    "select_option",
    "input_text",
    "javascript",
    "snapshot",
    "note",
  ]);
  /** Turn the flat step form into the command the server expects.
   * @param {Record<string,string|boolean|undefined>} data
   * @returns {Record<string,unknown>}
   */
  static stepPayload = data => {
    /** @param {unknown} value */
    const number = value => Number.parseInt(String(value ?? ""), 10) || 0;
    /** @param {unknown} value */
    const text = value => String(value ?? "").trim();
    const {
      selector_id = "",
      selector = "",
      targets = "first",
      run_mode = "sequential",
      pace_delay = "",
      pace_until = "",
      after_delay = "",
      after_until = "",
    } = data;
    const targeted = Boolean(selector_id || text(selector));
    const all = targeted && targets === "all";
    /** @param {unknown} delay @param {unknown} until */
    const pace = (delay, until) =>
      number(delay) > 0 || text(until)
        ? {
            delay_ms: number(delay),
            until: text(until) || null,
            poll_ms: 100,
            timeout_ms: 5000,
          }
        : null;
    const payload = /** @type {Record<string, unknown>} */ ({
      ...data,
      targets: all ? "all" : "first",
      run_mode: all ? run_mode : "sequential",
      pace_between: all ? pace(pace_delay, pace_until) : null,
      pace: pace(after_delay, after_until),
      selector: selector_id ? "" : selector,
    });
    for (const key of [
      "pace_delay",
      "pace_until",
      "after_delay",
      "after_until",
    ])
      delete payload[key];
    return payload;
  };
  /** The editor an expanded action carries inside its flow row.
   * It holds the action's own parameters, such as the code of a JavaScript
   * action or a REST request. It is kept while the settings stay unchanged, so
   * unsaved edits survive a redraw of the flow.
   * @param {EditorFlow} flow The flow the action belongs to.
   * @param {EditorEvent} event The action.
   * @param {import("./action-library.js").ActionDefinition} definition What the action was made from.
   * @returns {HTMLElement}
   */
  actionEditor(flow, event, definition) {
    const anyEvent = /** @type {Record<string, any>} */ (event);
    const key = JSON.stringify(
      [
        "kind",
        "payload",
        "url",
        "selector",
        "selector_id",
        "output_variable",
        "method",
        "request_config",
        "position_action",
        "x",
        "y",
        "share_session_cookies",
      ].map(name => anyEvent[name] ?? null),
    );
    const kept = this.actionEditors.get(event.id);
    if (kept?.key === key) return kept.node;
    const section = document.createElement("section");
    section.className = "edit-step-detail";
    section.setAttribute("data-detail", event.id);
    section.setAttribute("aria-label", `${definition.label} settings`);
    const form = document.createElement("form");
    form.className = "edit-step-detail-form";
    const slot = document.createElement("div");
    slot.className = "action-settings";
    const earlier = {
      ...flow,
      events: (flow.events ?? []).slice(0, (flow.events ?? []).indexOf(event)),
    };
    configureActionForm({
      fields: slot,
      kind: definition.id,
      snapshot: this.snapshot,
      variables: EditorApp.variableSources(earlier),
      selectorTools: this.actionSelectorTools(),
      event,
    });
    const apply = document.createElement("button");
    apply.type = "submit";
    apply.className = "edit-save";
    apply.append(iconElement("check"), "Apply");
    const revert = document.createElement("button");
    revert.type = "button";
    revert.textContent = "Revert";
    revert.addEventListener("click", () => {
      this.actionEditors.delete(event.id);
      this.renderTable();
      EditorApp.focusActionEditor(event.id);
    });
    const footer = document.createElement("footer");
    footer.className = "edit-step-detail-footer";
    footer.append(revert, apply);
    form.append(slot, footer);
    form.addEventListener("submit", async submit => {
      submit.preventDefault();
      apply.disabled = true;
      try {
        await this.command("event.configure", {
          event_id: event.id,
          ...actionCommand(form, definition),
        });
      } finally {
        apply.disabled = false;
      }
    });
    section.append(form);
    this.actionEditors.set(event.id, { key, node: section });
    return section;
  }
  /** Put the cursor in the first control of an action's in-row editor.
   * @param {string} eventId The action.
   * @returns {void}
   */
  static focusActionEditor = eventId => {
    window.requestAnimationFrame(() => {
      const first = document.querySelector(
        `[data-detail="${CSS.escape(eventId)}"] :is(input, textarea, select, [contenteditable="true"])`,
      );
      if (first instanceof HTMLElement) first.focus({ preventScroll: true });
    });
  };
  /** Show the "Run only if" condition of an action in Properties.
   * The parameters themselves live in the action's flow row.
   * @param {HTMLElement} root The inspector.
   * @param {EditorFlow} flow The flow the action belongs to.
   * @param {EditorEvent} event The selected action.
   * @returns {void}
   */
  mountGuard(root, flow, event) {
    for (const name of ["url", "payload", "selector-ref", "selector-inline"])
      root.querySelector(`[data-field="${name}"]`)?.remove();
    const guard = root.querySelector('[data-field="guard"]');
    const guardSlot = root.querySelector("[data-guard-slot]");
    if (!(guard instanceof HTMLDetailsElement && guardSlot instanceof HTMLElement))
      return;
    guard.hidden = false;
    guard.open = Boolean(event.when_expression);
    guardSlot.replaceChildren(
      conditionWidget({
        source: event.when_expression ?? "",
        variables: EditorApp.variableSources({
          ...flow,
          events: (flow.events ?? []).slice(0, (flow.events ?? []).indexOf(event)),
        }),
        snapshot: this.snapshot,
      }),
    );
  }
  /** Fill the target, policy and last-run parts of the step form.
   * @param {HTMLElement} root
   * @param {any} event
   * @param {boolean} [owned] True when the action's own settings drive the target.
   * @returns {void}
   */
  populateStepTargeting(root, event, owned = false) {
    const form = root.querySelector("#step-form");
    if (!(form instanceof HTMLFormElement)) return;
    /** @param {string} name */
    const field = name => form.elements.namedItem(name);
    const ref = field("selector_id");
    const inline = field("selector");
    if (!owned && ref instanceof HTMLSelectElement && inline instanceof HTMLInputElement)
      bindSelectorReference({
        select: ref,
        inline,
        selectors: this.selectors(),
        selected: event.selector_id || "",
      });
    if (!owned && inline instanceof HTMLInputElement) this.mountSelectorWidget(inline, "Expression");
    /** @param {string} name @param {string} value */
    const set = (name, value) => {
      const control = field(name);
      if (
        control instanceof HTMLInputElement ||
        control instanceof HTMLSelectElement
      )
        control.value = value;
    };
    set("targets", event.targets || "first");
    set("run_mode", event.run_mode || "sequential");
    set(
      "pace_delay",
      event.pace_between?.delay_ms ? String(event.pace_between.delay_ms) : "",
    );
    set("pace_until", event.pace_between?.until || "");
    set(
      "after_delay",
      event.contract?.pace?.delay_ms
        ? String(event.contract.pace.delay_ms)
        : "",
    );
    set("after_until", event.contract?.pace?.until || "");
    const keep = field("continue_on_failure");
    if (keep instanceof HTMLInputElement)
      keep.checked = Boolean(event.contract?.continue_on_failure);
    const sandbox = field("sandbox");
    if (sandbox instanceof HTMLInputElement)
      sandbox.checked = Boolean(event.sandbox);
    const latest = this.workspace?.runs?.[0];
    const records = (latest?.action_records ?? []).filter(
      (/** @type {any} */ record) => record.event_id === event.id,
    );
    const section = form.querySelector("[data-field=last-run]");
    if (section instanceof HTMLElement) renderLastRun(section, records);
  }
  /** Show only the targeting controls that apply to the step, and keep them current.
   * @param {HTMLElement} root
   * @param {any} event
   * @returns {void}
   */
  bindStepTargeting(root, event) {
    const form = root.querySelector("#step-form");
    if (!(form instanceof HTMLFormElement)) return;
    for (const name of ["pace_until", "after_until"]) {
      const field = form.elements.namedItem(name);
      if (field instanceof HTMLInputElement)
        attachConditionField(field, this.conditionSource());
    }
    /** @param {string} name */
    const control = name => form.elements.namedItem(name);
    /** @param {string} name */
    const wrap = name => form.querySelector(`[data-field="${name}"]`);
    const ref = control("selector_id");
    const inline = control("selector");
    const targets = control("targets");
    const run = control("run_mode");
    const save = form.querySelector("#save-as-selector");
    const warning = form.querySelector("[data-field=scope-warning]");
    const targeted = EditorApp.TARGETED_KINDS.includes(event.kind);
    const refresh = () => {
      // Row-edited actions carry their target in the row's detail form, so
      // the shared controls were removed; fall back to the saved target.
      const chosen =
        ref instanceof HTMLSelectElement
          ? ref.value
          : String(event.selector_id ?? "");
      const text =
        inline instanceof HTMLInputElement
          ? inline.value.trim()
          : String(event.selector ?? "");
      const all =
        targets instanceof HTMLSelectElement && targets.value === "all";
      const hasTarget = Boolean(chosen || text);
      const inlineLabel = wrap("selector-inline");
      if (inlineLabel instanceof HTMLElement && targeted)
        inlineLabel.hidden = Boolean(chosen);
      for (const [name, visible] of /** @type {[string,boolean][]} */ ([
        ["target", targeted],
        ["scope", targeted && hasTarget],
        ["run", targeted && hasTarget && all],
        ["pause", targeted && hasTarget && all],
        ["pause-until", targeted && hasTarget && all],
        ["sandbox", event.kind === "javascript"],
      ])) {
        const node = wrap(name);
        if (node instanceof HTMLElement) node.hidden = !visible;
      }
      if (run instanceof HTMLSelectElement) {
        const allowed = EditorApp.PARALLEL_KINDS.includes(event.kind);
        const option = run.querySelector('option[value="parallel"]');
        if (option instanceof HTMLOptionElement) option.disabled = !allowed;
        if (!allowed && run.value === "parallel") run.value = "sequential";
        run.title = allowed
          ? ""
          : "Actions that use the mouse or keyboard run one at a time.";
      }
      if (save instanceof HTMLElement)
        save.hidden = !targeted || Boolean(chosen);
      if (warning instanceof HTMLElement) {
        const stored = this.selectors().find(
          item => item.selector_id === chosen,
        );
        const page = this.snapshot?.target_url ?? "";
        const unseen =
          stored &&
          !stored.validated_on.some(
            (/** @type {any} */ seen) => seen.url === page,
          );
        warning.hidden = !unseen;
        warning.textContent = unseen
          ? "This selector was not tested on the page that is open now."
          : "";
      }
    };
    form.addEventListener("input", refresh);
    form.addEventListener("change", refresh);
    refresh();
    if (save instanceof HTMLButtonElement)
      save.addEventListener("click", () =>
        this.saveInlineAsSelector(event, inline),
      );
  }
  /** Turn a step's inline selector into a stored selector and open it to refine.
   * @param {any} event
   * @param {unknown} inline
   * @returns {Promise<void>}
   */
  async saveInlineAsSelector(event, inline) {
    const raw = inline instanceof HTMLInputElement ? inline.value.trim() : "";
    const expression = raw.replace(/^ext=/, "");
    if (!expression) {
      this.selectSelector("new");
      return;
    }
    if (
      !expression ||
      /^(role|text|xpath|id|data-testid|internal:)[=:]/.test(expression) ||
      expression.includes(" >> ")
    ) {
      EditorApp.element("status").textContent =
        "Only CSS and extended expressions can be saved as a selector.";
      return;
    }
    const taken = new Set(this.selectors().map(item => item.name));
    const base =
      (event.label || event.kind)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "") || "selector";
    let name = /^[a-z]/.test(base) ? base : `s_${base}`;
    for (let n = 2; taken.has(name); n += 1) name = `${base}_${n}`;
    await this.command("selector.save", {
      name,
      expression,
      expected_count: "any",
      checks: [],
    });
    const saved = this.selectors().find(item => item.name === name);
    if (!saved) return;
    await this.command("event.update", {
      event_id: event.id,
      label: event.label || event.kind,
      selector: "",
      payload: event.payload ?? "",
      url: event.url ?? "",
      selector_id: saved.selector_id,
    });
    this.selectSelector(saved.selector_id);
  }
  /** The selected steps, in the order they run.
   * @returns {string[]}
   */
  selectedStepIds() {
    return (this.activeFlow()?.events ?? [])
      .map(event => event.id)
      .filter(id => this.selectedEventIds.has(id));
  }
  /** Enable Duplicate and Remove while steps are selected, and name the count.
   * @returns {void}
   */
  updateFlowBar() {
    const count = this.selectedStepIds().length;
    for (const [id, verb] of /** @type {[string, string][]} */ ([
      ["step-duplicate", "Duplicate"],
      ["step-remove", "Remove"],
    ])) {
      const button = document.getElementById(id);
      if (!(button instanceof HTMLButtonElement)) continue;
      const label = `${verb} ${count} ${count === 1 ? "step" : "steps"}`;
      button.disabled = count === 0;
      button.title =
        count === 0 ? `Select a step to ${verb.toLowerCase()} it` : label;
      button.setAttribute("aria-label", count === 0 ? `${verb} step` : label);
    }
  }
  /** Copy every selected step; each copy lands after its source and is selected.
   * @returns {Promise<void>}
   */
  async duplicateSelected() {
    const before = new Set(
      (this.activeFlow()?.events ?? []).map(event => event.id),
    );
    await this.selectedStepIds().reduce(
      (pending, id) =>
        pending.then(() => this.command("event.duplicate", { event_id: id })),
      Promise.resolve(),
    );
    const copies = (this.activeFlow()?.events ?? [])
      .map(event => event.id)
      .filter(id => !before.has(id));
    if (copies.length) this.setSelection(copies);
  }
  /** Delete every selected step after one confirmation.
   * @returns {Promise<void>}
   */
  async removeSelected() {
    const ids = this.selectedStepIds();
    if (!ids.length) return;
    const several = ids.length > 1;
    const approved = await EditorApp.confirmDelete(
      several
        ? {
            title: `Delete ${ids.length} steps?`,
            body: "This also removes screenshots attached to these steps.",
            keep: "Keep steps",
            remove: `Delete ${ids.length} steps`,
          }
        : undefined,
    );
    if (!approved) return;
    await Promise.all(
      ids.map(id => this.command("event.delete", { event_id: id })),
    );
    this.setSelection([]);
  }
  /** Open the action library, the one place actions are chosen from.
   * @returns {void}
   */
  openActionLibrary() {
    this.dock.openWindow("actions", { x: 16, y: 80, w: 720, h: 760 });
  }
  /** The tools a selector control needs inside an action's settings.
   * @returns {{mount: (carrier: HTMLInputElement|HTMLTextAreaElement, label: string) => unknown, onPick: (apply: (element: any) => void) => void, onHighlight: (expression: string, done: (result: any) => void) => void}}
   */
  actionSelectorTools() {
    return {
      mount: (carrier, label) => this.mountSelectorWidget(carrier, label),
      onPick: apply => {
        this.selectorPickSink = apply;
        this.liveTarget?.startPicking();
      },
      onHighlight: (expression, done) =>
        this.testSelector({
          selector_id: "",
          expression,
          expected_count: null,
          checks: [],
        }, done),
    };
  }
  /** Add an action to the flow with its default settings and select it.
   * Properties then shows the action's settings, so nothing is configured in
   * the library. An action that still needs a target or value is added too and
   * is marked as unfinished until those are filled in.
   * @param {string} kind Palette action id.
   * @param {Record<string,string>} [settings] Settings to start with instead of the defaults.
   * @returns {Promise<void>}
   */
  async insertAction(kind, settings = {}) {
    const flow = this.activeFlow();
    const status = EditorApp.element("status");
    if (!flow) {
      status.textContent = "Create a flow before adding actions.";
      return;
    }
    if (kind === "if") {
      await this.guardSelected();
      return;
    }
    const before = new Set((flow.events ?? []).map(item => item.id));
    try {
      const result = await this.call("event.add", {
        ...defaultActionCommand({
          kind,
          snapshot: this.snapshot,
          variables: EditorApp.variableSources(flow),
        }),
        ...settings,
      });
      this.inspectorKey = "";
      this.applySnapshot(result);
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : String(error);
      return;
    }
    const added = this.activeFlow()?.events?.find(item => !before.has(item.id));
    if (!added) return;
    this.setSelection([added.id], added.id);
    this.dock.openWindow("properties", { x: 1080, y: 96, w: 344, h: 660 });
    if (this.dock.mobile)
      document.querySelector('[data-panel-id="actions"]')?.removeAttribute("data-open");
    else this.dock.collapse("actions");
    const definition = definitionForEvent(added);
    const inRow = definition !== undefined && editsInRow(definition);
    const where = inRow ? "in its row" : "in Properties";
    status.textContent = added.incomplete
      ? `Action added. Finish its settings ${where}.`
      : `Action added. Adjust it ${where}.`;
    const flowList = EditorApp.element("table");
    window.requestAnimationFrame(() => {
      flowList.scrollTop = flowList.scrollHeight;
      if (inRow) {
        EditorApp.focusActionEditor(added.id);
        return;
      }
      const first = document.querySelector("#step-form #action-fields input, #step-form #action-fields textarea, #step-form #action-fields select");
      if (first instanceof HTMLElement) first.focus({ preventScroll: true });
    });
  }
  /** Make the selected action, or the last one, run only when a condition holds.
   * @returns {Promise<void>}
   */
  async guardSelected() {
    const events = this.activeFlow()?.events ?? [];
    const target =
      events.find(item => item.id === this.selectedEventId) ?? events.at(-1);
    const status = EditorApp.element("status");
    if (!target) {
      status.textContent = "Add an action first, then use If to run it only when a condition holds.";
      return;
    }
    if (!definitionForEvent(target)) {
      status.textContent = "This recorded step cannot take a condition.";
      return;
    }
    await this.command("event.update", {
      event_id: target.id,
      label: target.label || target.kind,
      selector: target.selector ?? "",
      payload: target.payload ?? "",
      url: target.url ?? "",
      selector_id: target.selector_id ?? "",
      when_expression: target.when_expression || DEFAULT_GUARD,
    });
    this.setSelection([target.id], target.id);
    this.dock.openWindow("properties", { x: 1080, y: 96, w: 344, h: 660 });
    if (this.dock.mobile)
      document.querySelector('[data-panel-id="actions"]')?.removeAttribute("data-open");
    else this.dock.collapse("actions");
    window.requestAnimationFrame(() =>
      document
        .querySelector('#step-form [data-field="guard"]')
        ?.scrollIntoView({ block: "nearest" }),
    );
    status.textContent = "Condition added. Edit it under Run only if in Properties.";
  }

  /** Render completed and active execution results.
   * @returns {void}
   */
  /** One action result in the Runs list: status, step, match number, cause and console lines.
   * @param {RunRecord} record
   * @returns {string}
   */
  runActionHtml(record) {
    const escape = EditorApp.escape;
    const event = this.workspace?.flows
      ?.flatMap(flow => flow.events || [])
      .find((/** @type {any} */ item) => item.id === record.event_id);
    const match = record.unit
      ? ` (match ${record.unit.index + 1} of ${record.unit.count})`
      : "";
    const why = causeSummary(record);
    const lines = (record.streams ?? [])
      .filter(entry => entry.source === "snippet")
      .map(
        entry =>
          `<small class="run-line" data-level="${escape(entry.level)}">${escape(entry.message)}</small>`,
      )
      .join("");
    const response =
      record.response !== undefined && event?.kind === "javascript"
        ? `<pre class="run-response">${escape(JSON.stringify(record.response, null, 2))}</pre>`
        : "";
    return `<small class="run-action" data-state="${escape(record.status)}">${escape(record.status)}, ${escape(event?.label || "Step")}${escape(match)}${why ? `: ${escape(why)}` : ""}</small>${lines}${response}`;
  }
  /** Redraw the run history, newest first.
   * @returns {void}
   */
  renderRuns() {
    const runs = this.workspace?.runs ?? [];
    EditorApp.element("runs").innerHTML = runs.length
      ? runs
          .slice()
          .reverse()
          .map(
            (run, index) =>
              `<div class="run-item"><strong title="${EditorApp.escape(run.id)}">Run ${runs.length - index}</strong><span class="run-status" data-state="${EditorApp.escape(run.status)}">${run.status === "succeeded" ? EditorApp.icon("check") : ""}${EditorApp.escape(run.status)}</span><small>${EditorApp.escape(this.workspace?.flows?.find((flow) => flow.id === (run.current_flow_id || run.initial_flow_id))?.name || "Flow")}</small><small>${EditorApp.escape(run.device_mode)}</small>${(run.action_records ?? []).map((record) => this.runActionHtml(record)).join("")}</div>`,
          )
          .join("")
      : `<div class="run-item"><strong>No runs yet</strong><small>Execution telemetry appears here.</small></div>`;
    const shots = (this.workspace?.screenshots ?? []).filter(
      shot => shot.flow_id === this.activeFlow()?.id,
    );
    EditorApp.element("runs").insertAdjacentHTML(
      "beforeend",
      shots
        .map(
          shot =>
            `<figure class="shot"><button class="shot-open" data-shot="${EditorApp.escape(shot.id)}" aria-label="Open ${EditorApp.escape(shot.phase)} screenshot"><img src="${EditorApp.escape(shot.path)}" alt="${EditorApp.escape(shot.phase)} screenshot for step ${EditorApp.escape(shot.event_id)}" loading="lazy"></button><figcaption>${EditorApp.escape(shot.phase)}, ${shot.width}×${shot.height} px</figcaption></figure>`,
        )
        .join(""),
    );
    EditorApp.element("runs")
      .querySelectorAll("[data-shot]")
      .forEach(node => {
        const thumbnail = node.querySelector("img");
        if (thumbnail instanceof HTMLImageElement)
          thumbnail.addEventListener("error", () => {
            node.textContent =
              "Screenshot file unavailable. Run the test again.";
            if (node instanceof HTMLButtonElement) node.disabled = true;
          });
        node.addEventListener("click", async () => {
          const id = node.getAttribute("data-shot") || "";
          try {
            await this.call("screenshot.open", {
              artifact_id: id,
            });
            const image = EditorApp.element("screenshot-preview");
            const link = EditorApp.element("screenshot-download");
            const dialog = EditorApp.element("screenshot-dialog");
            if (
              image instanceof HTMLImageElement &&
              link instanceof HTMLAnchorElement &&
              dialog instanceof HTMLDialogElement
            ) {
              image.src = `/artifacts/${encodeURIComponent(id)}`;
              image.style.removeProperty("--dynamic-screenshot-width");
              link.href = image.src;
              link.download = `${id}.png`;
              dialog.showModal();
            }
          } catch (error) {
            EditorApp.element("status").textContent =
              error instanceof Error ? error.message : String(error);
          }
        });
      });
  }
  /** Run a workspace command and show its outcome in the status line.
   * @param {string} name Command name.
   * @param {Record<string,unknown>|null} payload Command arguments.
   * @returns {Promise<void>}
   */
  async command(name, payload = null) {
    try {
      if (name === "run.play") {
        const flow = this.activeFlow();
        const labels = askLabels(flow?.events ?? []);
        const flowInputs = flow?.parameters ?? [];
        if (labels.length > 0 || flowInputs.length > 0) {
          const answers = await askInputs(labels, flowInputs);
          if (answers === null) return;
          payload = {
            ...(payload ?? {}),
            inputs: answers.ask,
            flow_inputs: answers.flow,
          };
        }
      }
      const result = await this.call(name, payload);
      if (result.workspace) {
        this.inspectorKey = "";
        this.applySnapshot(result);
      }
      EditorApp.element("status").textContent = EditorApp.doneMessage(name);
    } catch (error) {
      EditorApp.element("status").textContent =
        error instanceof Error ? error.message : String(error);
    }
  }
  /** Send a command to the editor host and await its snapshot.
   * @param {string} name Command name.
   * @param {Record<string,unknown>|null} payload Command arguments.
   * @returns {Promise<EditorSnapshot>}
   */
  call(name, payload = null) {
    const id = `ui-${++this.sequence}`;
    const msg = {
      protocol: 1,
      id,
      command: name,
      revision: this.revision,
      payload,
    };
    return new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => {
        this.pending.delete(id);
        reject(
          new Error("Editor did not respond. Reopen Flow Studio and retry."),
        );
      }, 10000);
      this.pending.set(id, {
        resolve,
        reject,
        timer,
      });
      this.transport.postMessage(JSON.stringify(msg));
    });
  }
  /** @returns {Promise<boolean>}
   */
  static confirmReplacement = () => {
    const dialog = EditorApp.element("replace-dialog");
    if (!(dialog instanceof HTMLDialogElement)) return Promise.resolve(false);
    return new Promise(resolve => {
      dialog.returnValue = "cancel";
      dialog.addEventListener(
        "close",
        () => resolve(dialog.returnValue === "replace"),
        {
          once: true,
        },
      );
      dialog.showModal();
    });
  };
  /** Views that existed before the five-tab layout, and where they live now. */
  static VIEW_ALIASES = Object.freeze({
    record: "edit",
    timeline: "edit",
    inspector: "edit",
    debug: "play",
    profiles: "settings",
    recovery: "settings",
    controls: "settings",
  });
  /** Map any view name, current or retired, onto a view that exists.
   * @param {string} view
   * @returns {string}
   */
  static canonicalView = view =>
    /** @type {Record<string,string>} */ (EditorApp.VIEW_ALIASES)[view] ?? view;
  /** The tab that owns a view; Crawl is part of the Flow editor.
   * @param {string} view
   * @returns {string}
   */
  static tabOf = view => view === "crawl" ? "edit" : view;
  /** Switch the workspace to the requested tab.
   * @param {string} requested View name, canonicalized on entry.
   * @returns {void}
   */
  setWorkspaceView(requested) {
    const view = EditorApp.canonicalView(requested);
    this.workspaceView = view;
    this.renderFlows();
    const app = EditorApp.element("app");
    app.setAttribute("data-workspace-mode", view);
    document.querySelectorAll("[data-workspace-view]").forEach(item => {
      const active =
        item.getAttribute("data-workspace-view") === EditorApp.tabOf(view);
      item.classList.toggle("active", active);
      if (active) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    });
    const workspaceSelect = document.getElementById("workspace-view-select");
    if (workspaceSelect instanceof HTMLSelectElement)
      workspaceSelect.value = EditorApp.tabOf(view);
    const mobilePrimary = document.querySelector(
      '.mobile-panel-tabs [data-mobile-panel="steps"]',
    );
    if (mobilePrimary instanceof HTMLButtonElement) {
      mobilePrimary.textContent = view === "graph" ? "Graph" : "Steps";
      if (view === "graph") mobilePrimary.click();
    }
    const mobileBrowser = document.querySelector(
      '.mobile-panel-tabs [data-mobile-panel="browser"]',
    );
    if (mobileBrowser instanceof HTMLButtonElement)
      mobileBrowser.hidden = view === "graph";
    const mobileRuns = document.querySelector(
      '.mobile-panel-tabs [data-mobile-panel="runs"]',
    );
    if (mobileRuns instanceof HTMLButtonElement)
      mobileRuns.hidden = view === "graph";
    const destination =
      view === "graph"
        ? document.querySelector('[data-panel-id="composition"]')
        : ["play", "compare"].includes(view)
          ? document.querySelector(".runs")
          : view === "crawl"
            ? document.querySelector(".preview")
            : document.querySelector(".table-panel");
    this.renderWorkspaceSurface();
    this.renderWelcomeScreen();
    this.dock.render(view);
    if (destination instanceof HTMLElement) {
      destination.setAttribute("tabindex", "-1");
      destination.focus({ preventScroll: true });
    }
    this.renderInspector();
    window.requestAnimationFrame(() => this.renderConnections());
  }
  /** @returns {void}
   */
  /** @returns {void} */
  static openCommandPalette = () => {
    const dialog = EditorApp.element("command-palette");
    const search = EditorApp.element("command-search");
    if (!(dialog instanceof HTMLDialogElement)) return;
    dialog.showModal();
    if (search instanceof HTMLInputElement) {
      search.value = "";
      search.dispatchEvent(new Event("input"));
      search.focus();
    }
  };
  /** Show or hide the shared surface used by the specialized views.
   * @returns {void}
   */
  renderWorkspaceSurface() {
    const surface = EditorApp.element("workspace-surface");
    const content = EditorApp.element("workspace-surface-content");
    const actions = EditorApp.element("workspace-surface-actions");
    const specialized = ["play", "compare", "crawl", "settings"];
    if (!specialized.includes(this.workspaceView)) {
      surface.hidden = true;
      return;
    }
    surface.hidden = false;
    const flow = this.activeFlow();
    const events = flow?.events ?? [];
    const runs = this.workspace?.runs ?? [];
    const latestRun = runs[0];
    const shots = this.workspace?.screenshots ?? [];
    const groups = groupCaptures(
      shots,
      this.workspace?.flows ?? [],
      EditorApp.eventTitle,
    );
    const {
      group: pairGroup,
      expected,
      actual,
    } = pairFor(groups, this.compareKey);
    const title = {
      play: "Play",
      compare: "Compare screenshots",
      crawl: "Discover flows",
      settings: "Settings",
    }[this.workspaceView];
    const description = {
      play: "Run a flow or the whole graph, and inspect what each action did.",
      compare: "Compare captured screenshots before approving a baseline.",
      crawl: "Discover flows and add them to this project.",
      settings:
        "The project's details, the target application, browser profiles and recovery.",
    }[this.workspaceView];
    EditorApp.element("workspace-surface-kicker").textContent =
      flow?.name ?? "No active flow";
    EditorApp.element("workspace-surface-title").textContent =
      title || "Workspace";
    EditorApp.element("workspace-surface-description").textContent =
      description || "";
    const back = `<button type="button" data-workspace-return="edit">${EditorApp.icon("arrow-left")}Back to editor</button>`;
    const running = Boolean(this.snapshot?.execution_run_id);
    const runBlocked = running
      ? "A test is already running."
      : this.snapshot?.recording_state === "recording"
        ? "Stop recording first."
        : (this.snapshot?.recorder_clients ?? 0) > 0
          ? ""
          : "Open the browser first.";
    const connected = (this.workspace?.edges ?? []).some(
      edge => edge.source === flow?.id,
    );
    const graphBlocked =
      runBlocked || (connected ? "" : "This flow has no outgoing connections.");
    const playButton = (
      /** @type {string} */ scope,
      /** @type {string} */ hint,
      /** @type {string} */ blocked,
      /** @type {string} */ icon,
      /** @type {string} */ label,
    ) =>
      `<button${scope === "flow" ? ' class="accent"' : ""} data-surface-command="run.play" data-surface-scope="${scope}" title="${EditorApp.escape(blocked || hint)}"${blocked ? " disabled" : ""}>${EditorApp.icon(icon)}${label}</button>`;
    const controls = EditorApp.runControls(this.snapshot);
    const resumes = controls.running && controls.state === "paused";
    const pauseBlocked = resumes || controls.canPause ? "" : running ? "The run is pausing." : "Nothing is running.";
    const stepBlocked = controls.canStep ? "" : running ? "Pause the run first." : runBlocked;
    const heldControls = `<button data-surface-command="${resumes ? "run.resume" : "run.pause"}"${pauseBlocked ? ` disabled title="${EditorApp.escape(pauseBlocked)}"` : ""}>${EditorApp.icon(controls.pauseIcon)}${controls.pauseLabel}</button><button data-surface-command="run.step" data-surface-scope="flow"${stepBlocked ? ` disabled title="${EditorApp.escape(stepBlocked)}"` : ' title="Run one action, then pause"'}>${EditorApp.icon("player-skip-forward")}Step</button>`;
    const playActions = `${playButton("flow", "Run only this flow", runBlocked, "player-play", "Run flow")}${heldControls}${playButton("graph", "Run this flow, then follow its connections", graphBlocked, "arrow-right", "Run with connections")}<button data-surface-command="run.cancel" ${running ? "" : 'disabled title="Nothing is running."'}>${EditorApp.icon("square")}Stop</button>`;
    const surfaceActions =
      {
        play: playActions,
        compare: `<button data-compare-decision="reject" ${expected ? "" : "disabled"}>Reject change</button><button class="accent" data-compare-decision="review" ${expected ? "" : "disabled"}>Review baseline</button>`,
      }[this.workspaceView] || "";
    actions.innerHTML = `${surfaceActions}${back}`;
    if (this.workspaceView === "settings") {
      this.settings?.render(
        /** @type {Parameters<SettingsSurface["render"]>[0]} */ (
          /** @type {unknown} */ (this.snapshot)
        ),
      );
      return;
    }
    const eventRows = events.length
      ? events
          .map(
            (event, index) =>
              `<button type="button" class="surface-row ${event.id === this.selectedEventId ? "selected" : ""}" data-surface-event="${EditorApp.escape(event.id)}"><span class="surface-index">${String(index + 1).padStart(2, "0")}</span>${EditorApp.icon(EditorApp.eventIcon(event))}<strong>${EditorApp.escape(EditorApp.eventTitle(event))}</strong><small>${EditorApp.escape(EditorApp.eventDetail(event))}</small></button>`,
          )
          .join("")
      : '<p class="surface-empty">No actions yet. Record the target or insert an action.</p>';
    if (this.workspaceView === "play") {
      const records = latestRun?.action_records ?? [];
      const next = this.snapshot?.run_control?.before_event_id ?? null;
      const debugRows = events.length
        ? events
            .map((event, index) => {
              const record = records.find(item => item.event_id === event.id);
              return `<button type="button" class="surface-row ${event.id === this.selectedEventId ? "selected" : ""}" data-surface-event="${EditorApp.escape(event.id)}"><span class="surface-index">${String(index + 1).padStart(2, "0")}</span>${EditorApp.icon(EditorApp.eventIcon(event))}<strong>${EditorApp.escape(EditorApp.eventTitle(event))}</strong><span class="surface-status" data-state="${EditorApp.escape(next === event.id ? "paused" : record?.status || "pending")}">${EditorApp.escape(next === event.id ? "runs next" : record?.status || "pending")}</span></button>`;
            })
            .join("")
        : eventRows;
      const failed = records.find(record => record.status === "failed");
      const selected = events.find(
        event => event.id === this.selectedEventId,
      );
      const evidence = selected
        ? [...shots]
            .reverse()
            .find(
              shot =>
                shot.flow_id === flow?.id && shot.event_id === selected.id,
            )
        : undefined;
      const evidenceView =
        selected && evidence
          ? `<figure class="evidence-shot"><img src="${EditorApp.escape(evidence.path)}" alt="Page after ${EditorApp.escape(EditorApp.eventTitle(selected))}"><figcaption>After ${EditorApp.escape(EditorApp.eventTitle(selected))} · ${evidence.width}×${evidence.height}</figcaption></figure>`
          : `<div class="target-stage-placeholder">${EditorApp.icon("device-imac")}<strong>${failed ? "Failure evidence available" : selected ? "No screenshot for this action" : "Run a flow to collect evidence"}</strong><p>${EditorApp.escape(EditorApp.headline(failed?.error) || (selected ? "Turn on screenshots while testing in Flow settings." : "Select an action to see the page after it ran."))}</p></div>`;
      content.innerHTML = `<div class="surface-grid surface-grid-debug"><section class="surface-card"><header><h3>Actions</h3><span>${latestRun ? `Run ${EditorApp.escape(latestRun.id)}` : "No run selected"}</span></header><div class="surface-list">${debugRows}</div></section><section class="surface-card surface-evidence"><header><h3>Target evidence</h3><span>${EditorApp.escape(latestRun?.device_mode || this.snapshot?.device_mode || "desktop")}</span></header>${evidenceView}</section><section class="surface-card"><header><h3>Variables</h3><span>Current revision ${this.revision}</span></header><pre class="surface-code">${EditorApp.escape(JSON.stringify(records.find((record) => record.response !== undefined)?.response ?? { profile: latestRun?.device_mode || this.snapshot?.device_mode || "desktop", flow: flow?.name || null }, null, 2))}</pre></section><section class="surface-card surface-console"><header><h3>Assertions and console</h3><span>${failed ? "Failure selected" : "No failure selected"}</span></header><div class="console-detail"><strong>${EditorApp.escape(failed?.error || "No failed assertion in the selected run.")}</strong><small>Seeking evidence does not restore browser state.</small></div></section></div>`;
    } else if (this.workspaceView === "compare") {
      /** @param {EditorScreenshot|undefined} shot
       * @param {string} label
       * @returns {string}
       */
      const image = (shot, label) =>
        shot
          ? `<button class="compare-image" data-surface-shot="${EditorApp.escape(shot.id)}"><span>${label}</span><img src="${EditorApp.escape(shot.path)}" alt="${label} screenshot"></button>`
          : `<div class="compare-empty"><strong>${label}</strong><span>${label === "Expected baseline" ? "Run this step again to compare" : "No capture available"}</span></div>`;
      content.innerHTML = `<div class="surface-grid surface-grid-compare"><section class="surface-card"><header><h3>Captures</h3><span>${groups.length} steps · ${shots.length} captures</span></header><div class="surface-list">${groups.map((item) => `<button class="surface-row surface-row-capture ${item.key === pairGroup?.key ? "selected" : ""}" data-compare-key="${EditorApp.escape(item.key)}">${EditorApp.icon("camera")}<strong>${EditorApp.escape(item.label)}</strong><small>${EditorApp.escape(item.flowName)} · ${item.shots.length} ${item.shots.length === 1 ? "capture" : "captures"}</small></button>`).join("") || '<p class="surface-empty">Run with screenshots enabled to create comparison evidence.</p>'}</div></section><section class="surface-card compare-stage"><header><div class="surface-tabs"><button class="${this.compareMode === "side" ? "active" : ""}" data-compare-mode="side">Side by side</button><button class="${this.compareMode === "overlay" ? "active" : ""}" data-compare-mode="overlay">Overlay</button><button class="${this.compareMode === "difference" ? "active" : ""}" data-compare-mode="difference">Difference</button><button class="${this.compareMode === "wipe" ? "active" : ""}" data-compare-mode="wipe">Wipe</button></div></header><div class="compare-pair" data-mode="${this.compareMode}">${image(expected, "Expected baseline")}${image(actual, "Actual run")}</div></section><section class="surface-card"><header><h3>Comparison settings</h3><span>${this.compareDecision ? "Decision selected" : "Manual review"}</span></header><dl class="surface-properties"><div><dt>Profile</dt><dd>${EditorApp.escape(latestRun?.device_mode || "Not selected")}</dd></div><div><dt>Threshold</dt><dd>0.50%</dd></div><div><dt>Captured size</dt><dd>${actual ? `${actual.width}×${actual.height}` : "—"}</dd></div><div><dt>Result</dt><dd>${this.compareDecision === "review" ? "Ready for baseline review" : this.compareDecision === "reject" ? "Change rejected" : actual ? "Needs review" : "No comparison"}</dd></div></dl><p class="surface-note">Baselines change only after approval.</p></section></div>`;
    } else if (this.workspaceView === "crawl") {
      const address = this.snapshot?.target_address;
      content.innerHTML = `<form id="surface-crawl-form" class="surface-grid surface-grid-crawl"><section class="surface-card crawl-main"><header><h3>Discover flows</h3><span>${address ? EditorApp.escape(address) : "Set the target in Settings"}</span></header><div class="surface-form-grid"><label>Limit to elements<input name="selector" placeholder="All interactive elements" spellcheck="false"></label><label>Maximum depth<input name="max_depth" type="number" min="1" max="10" value="3"></label><label>State limit<input name="max_states" type="number" min="1" max="200" value="20"></label></div><fieldset><legend>Interactions</legend><label class="check"><input name="follow_links" type="checkbox" checked>Visit links</label><label class="check"><input name="click_controls" type="checkbox" checked>Click controls</label><label class="check"><input name="capture_ui_changes" type="checkbox" checked>UI-change screenshots</label></fieldset><footer><button type="button" data-surface-command="crawl.cancel">Cancel</button><button type="button" data-surface-command="actions.recipe">Actions recipe…</button><a class="export-button" href="/reports/actions/result_web/index.html" target="_blank" rel="noopener">Open Actions report</a><button class="accent" type="submit" ${address ? "" : 'disabled title="Set the target in Settings first."'}>Discover flows</button></footer></section><section class="surface-card"><header><h3>Generated Studio project</h3><span>Editable output</span></header><div class="surface-list">${eventRows}</div><p class="surface-note">Discovery output opens as a standard project with portable flows, profiles, and screenshot assets.</p></section></form>`;
    }
  }
  /** Show the profile choice, the open/close control and where the browser will open.
   * @param {EditorSnapshot} snapshot
   * @returns {void}
   */
  static renderBrowserBar = (snapshot) => {
    const select = EditorApp.element("device");
    const profiles =
      /** @type {Array<{id:string,name:string,width:number,height:number}>} */ (
        /** @type {{profiles?:unknown}} */ (snapshot.workspace ?? {})
          .profiles ?? []
      );
    if (select instanceof HTMLSelectElement) {
      const custom = snapshot.device_mode === "custom";
      const wanted = JSON.stringify([profiles, custom]);
      if (select.getAttribute("data-options") !== wanted) {
        select.replaceChildren(
          ...profiles.map((profile) => {
            const option = document.createElement("option");
            option.value = profile.id;
            option.textContent = profile.name;
            return option;
          }),
          ...(custom
            ? [
                Object.assign(document.createElement("option"), {
                  value: "custom",
                  textContent: "Custom size",
                }),
              ]
            : []),
        );
        select.setAttribute("data-options", wanted);
      }
      if (snapshot.device_mode && document.activeElement !== select)
        select.value = snapshot.device_mode;
    }
    const viewport = snapshot.viewport;
    EditorApp.element("viewport-summary").textContent = viewport
      ? `${viewport.width}×${viewport.height}`
      : "";
    const live = ["ready", "opening"].includes(snapshot.target_state ?? "");
    const address = snapshot.target_address;
    const toggle = EditorApp.element("browser-toggle");
    if (toggle instanceof HTMLButtonElement) {
      const label = live ? "Close browser" : "Open browser";
      toggle.innerHTML = `${EditorApp.icon(live ? "x" : "player-play")}<span class="browser-open-label">${label}</span>`;
      toggle.setAttribute("aria-label", label);
      const blocked = !live && address === null;
      toggle.disabled = blocked;
      toggle.title = blocked ? "Start the service in Settings first." : label;
    }
    // Say why there is nothing to show when it is not just "closed".
    document
      .querySelector(".live-target-frame")
      ?.setAttribute(
        "data-hint",
        address === null
          ? "service"
          : address === "about:blank" || address === undefined
            ? "address"
            : "",
      );
    toggle?.classList.toggle("accent", !live && address !== null);
    EditorApp.element("browser-address-text").textContent =
      address === null
        ? "· Start the service in Settings to open it."
        : address === "about:blank"
          ? "· Blank page. Set the address in Settings."
          : typeof address === "string"
            ? `· ${address}`
            : "";
  };
  /** Show the page without a click once there is an address and nothing is open.
   * Done once per page load, and never after the user closed the browser.
   * @param {EditorSnapshot} snapshot
   * @returns {void}
   */
  autoOpenBrowser(snapshot) {
    const live = ["ready", "opening"].includes(snapshot.target_state ?? "");
    const address = snapshot.target_address;
    if (
      live ||
      this.autoOpened ||
      this.userClosedBrowser ||
      typeof address !== "string" ||
      address === "about:blank"
    )
      return;
    this.autoOpened = true;
    this.command("browser.open");
  }
  /** Scroll to the action that produces a variable and focus its card.
   * @param {string} name Variable name.
   * @returns {void}
   */
  revealVariable(name) {
    const source = (this.activeFlow()?.events ?? []).find(
      item => producedVariables(item).some(output => output.name === name),
    );
    const row = source
      ? document.querySelector(`[data-step="${CSS.escape(source.id)}"]`)
      : null;
    row?.scrollIntoView({ block: "center" });
    if (row instanceof HTMLElement) row.focus({ preventScroll: true });
  }
  /** @returns {void}
   */
  bind() {
    document.addEventListener("variable-reveal", event =>
      this.revealVariable(/** @type {CustomEvent} */ (event).detail?.name),
    );
    this.projects = new ProjectActions({
      call: (name, payload) => this.call(name, payload),
      apply: (result) => {
        this.inspectorKey = "";
        this.applySnapshot(/** @type {EditorSnapshot} */ (result));
      },
      say: (text) => {
        EditorApp.element("status").textContent = text;
      },
      state: () => /** @type {any} */ (this.snapshot),
      showView: (view) => this.setWorkspaceView(view),
    });
    const topbar = document.querySelector(".topbar");
    if (topbar instanceof HTMLElement)
      this.projectBar = new ProjectBar(topbar, this.projects, {
        commands: () => EditorApp.openCommandPalette(),
        projectView: () => {
          this.setWorkspaceView("settings");
          document
            .getElementById("settings-project")
            ?.scrollIntoView({ block: "start" });
        },
      });
    this.projectSection = new ProjectSection(this.projects);
    this.settings = new SettingsSurface(
      EditorApp.element("workspace-surface-content"),
      {
        call: (name, payload) => this.call(name, payload),
        apply: (result) => {
          this.inspectorKey = "";
          this.applySnapshot(/** @type {EditorSnapshot} */ (result));
        },
        say: (text) => {
          EditorApp.element("status").textContent = text;
        },
        confirm: (copy) => EditorApp.confirmDelete(copy),
        projectSection: () => this.projectSection?.section() ?? null,
      },
    );
    const liveTarget = EditorApp.element("live-target-image");
    if (liveTarget instanceof HTMLImageElement)
      this.liveTarget = new LiveTarget(
        liveTarget,
        async (payload) => {
          try {
            const snapshot = await this.call("browser.input", payload);
            this.revision = snapshot.revision ?? this.revision;
          } catch (error) {
            EditorApp.element("status").textContent =
              error instanceof Error ? error.message : String(error);
          }
        },
        () => this.snapshot?.viewport ?? { width: 1440, height: 900 },
        () =>
          Boolean(
            this.snapshot?.workspace?.profiles?.find(
              profile => profile.id === this.snapshot?.device_mode,
            )?.touch,
          ),
        element => {
          const sink = this.selectorPickSink;
          this.selectorPickSink = null;
          sink?.(/** @type {any} */ (element));
        },
      );
    EditorApp.element("live-target-use").addEventListener("click", () => {
      const selector = EditorApp.element("live-target-selector");
      if (!(selector instanceof HTMLInputElement) || !selector.value) return;
      this.liveTarget?.maximize(false);
      if (this.applyPickedSelector(selector.value)) return;
      this.insertAction("pointer", { selector: selector.value });
    });
    EditorApp.element("browser-crawl").addEventListener("click", () =>
      this.setWorkspaceView("crawl"),
    );
    document.addEventListener(
      "selectstart",
      (event) => {
        const node = event.target;
        const element =
          node instanceof Element
            ? node
            : node instanceof Node
              ? node.parentElement
              : null;
        const editable = element?.closest(
          "input, textarea, [contenteditable='true'], pre, code, .runs-content, .selectable",
        );
        const dragging = document.body.matches(
          ".panel-dock-dragging, .step-dragging, .clip-dragging",
        );
        if (!editable || dragging) event.preventDefault();
      },
      true,
    );
    this.dock.render(this.workspaceView);
    this.dock.syncSizes();
    const actionsDialog = EditorApp.element("actions-dialog");
    const actionsSource = EditorApp.element("actions-source");
    if (actionsSource instanceof HTMLTextAreaElement)
      actionsSource.value =
        localStorage.getItem("studio.actions") ||
        JSON.stringify(
          {
            version: 1,
            actions: [
              {
                id: "discover",
                tool: "record.crawl",
                arguments: {
                  entrypoint: "demo/server.py",
                  url: "http://127.0.0.1/",
                  port: 0,
                  screenshots: true,
                  server_errors: true,
                  javascript: ["() => document.title"],
                  environments: [
                    {
                      width: 390,
                      height: 844,
                      theme: "light",
                    },
                    {
                      width: 1440,
                      height: 900,
                      theme: "dark",
                    },
                  ],
                  max_depth: 2,
                  max_states: 5,
                },
              },
              {
                id: "verify",
                tool: "frontend.run",
                arguments: {
                  projects: "$discover.projects",
                  server_log: "$discover.server_log",
                },
              },
            ],
          },
          null,
          2,
        );
    EditorApp.element("actions-close").addEventListener("click", () => {
      if (actionsDialog instanceof HTMLDialogElement) actionsDialog.close();
    });
    EditorApp.element("actions-import").addEventListener("click", () => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".json";
      input.addEventListener("change", async () => {
        const file = input.files?.[0];
        if (file) {
          const text = await file.text();
          if (actionsSource instanceof HTMLTextAreaElement)
            actionsSource.value = text;
        }
      });
      input.click();
    });
    EditorApp.element("actions-export").addEventListener("click", () => {
      if (!(actionsSource instanceof HTMLTextAreaElement)) return;
      const link = document.createElement("a");
      const url = URL.createObjectURL(
        new Blob([actionsSource.value], {
          type: "application/json",
        }),
      );
      link.href = url;
      link.download = "actions.json";
      link.click();
      URL.revokeObjectURL(url);
    });
    EditorApp.element("actions-form").addEventListener(
      "submit",
      async (event) => {
        event.preventDefault();
        if (!(actionsSource instanceof HTMLTextAreaElement)) return;
        try {
          const recipe = JSON.parse(actionsSource.value);
          if (this.dirty && !(await EditorApp.confirmReplacement())) return;
          const snapshot = await this.call("actions.run", recipe);
          this.applySnapshot(snapshot);
          localStorage.setItem("studio.actions", actionsSource.value);
          if (actionsDialog instanceof HTMLDialogElement) actionsDialog.close();
        } catch (error) {
          EditorApp.element("actions-error").textContent =
            error instanceof Error
              ? error.message
              : "Check the recipe and retry.";
          actionsSource.focus();
        }
      },
    );
    window.addEventListener("beforeunload", (event) => {
      if (this.dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    });
    EditorApp.element("screenshot-close").addEventListener("click", () => {
      const dialog = EditorApp.element("screenshot-dialog");
      if (dialog instanceof HTMLDialogElement) dialog.close();
    });
    EditorApp.element("screenshot-zoom").addEventListener("input", (event) => {
      if (event.target instanceof HTMLInputElement)
        EditorApp.element("screenshot-preview").style.setProperty(
          "--dynamic-screenshot-width",
          `${event.target.value}%`,
        );
    });
    window.addEventListener("resize", () => this.renderConnections());
    EditorApp.element("add-action").addEventListener("click", () =>
      this.openActionLibrary(),
    );
    EditorApp.element("selector-new").addEventListener("click", () =>
      this.selectSelector("new"),
    );
    EditorApp.element("step-duplicate").addEventListener("click", () =>
      this.duplicateSelected(),
    );
    EditorApp.element("step-remove").addEventListener("click", () =>
      this.removeSelected(),
    );
    const drawCatalog = () => {
      renderActionCatalog(EditorApp.element("action-catalog"), kind =>
        this.insertAction(kind),
      );
      // Keep the current search applied after the palette is redrawn.
      EditorApp.element("action-search").dispatchEvent(new Event("input"));
    };
    drawCatalog();
    window.addEventListener(ACTION_PREFS_EVENT, drawCatalog);
    const flowDropTarget = EditorApp.element("table");
    flowDropTarget.addEventListener("dragover", event => {
      if (!event.dataTransfer?.types.includes(ACTION_DRAG_TYPE)) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      flowDropTarget.classList.add("is-action-drop-target");
    });
    flowDropTarget.addEventListener("dragleave", event => {
      if (
        event.relatedTarget instanceof Node &&
        flowDropTarget.contains(event.relatedTarget)
      ) return;
      flowDropTarget.classList.remove("is-action-drop-target");
    });
    flowDropTarget.addEventListener("drop", event => {
      const kind = event.dataTransfer?.getData(ACTION_DRAG_TYPE) ?? "";
      flowDropTarget.classList.remove("is-action-drop-target");
      if (!kind) return;
      event.preventDefault();
      this.insertAction(kind);
    });
    EditorApp.element("action-search").addEventListener("input", event => {
      if (!(event.target instanceof HTMLInputElement)) return;
      const query = event.target.value.trim().toLowerCase();
      document.querySelectorAll(".action-group").forEach(group => {
        let visible = 0;
        group.querySelectorAll("[data-add-action]").forEach(button => {
          if (!(button instanceof HTMLElement)) return;
          const match = !query || button.textContent?.toLowerCase().includes(query);
          button.hidden = !match;
          if (match) visible += 1;
        });
        if (group instanceof HTMLElement) group.hidden = visible === 0;
      });
    });
    EditorApp.element("timeline-zoom").addEventListener("input", (event) => {
      if (!(event.target instanceof HTMLInputElement)) return;
      this.setTimelineZoom(
        EditorApp.zoomFromSlider(Number(event.target.value)),
      );
    });
    document.querySelectorAll("[data-timeline-tool]").forEach((node) => {
      node.addEventListener("click", () => {
        this.timelineTool =
          node.getAttribute("data-timeline-tool") === "marker"
            ? "marker"
            : "select";
        document.querySelectorAll("[data-timeline-tool]").forEach((tool) => {
          tool.classList.toggle("active", tool === node);
        });
        EditorApp.element("status").textContent =
          node.getAttribute("data-timeline-tool") === "marker"
            ? "Marker tool active. Click the ruler to place a marker."
            : "Timeline selection tool active.";
      });
    });
    EditorApp.element("timeline-snap").addEventListener("click", (event) => {
      if (!(event.currentTarget instanceof HTMLButtonElement)) return;
      const pressed =
        event.currentTarget.getAttribute("aria-pressed") !== "true";
      event.currentTarget.setAttribute("aria-pressed", String(pressed));
      event.currentTarget.classList.toggle("active", pressed);
      this.timelineSnap = pressed;
    });
    EditorApp.element("timeline").addEventListener("click", (event) => {
      if (
        this.timelineTool !== "marker" ||
        !(event.target instanceof Element) ||
        !event.target.closest(".ruler-ticks")
      )
        return;
      const ruler = event.target.closest(".ruler-ticks");
      if (!(ruler instanceof HTMLElement)) return;
      const rem =
        Number.parseFloat(
          getComputedStyle(document.documentElement).fontSize,
        ) || 16;
      const raw =
        ((event.clientX - ruler.getBoundingClientRect().left) /
          rem /
          this.timelineScale) *
        this.timelineTick;
      const quantum = this.timelineSnap ? this.timelineTick / 2 : 1;
      const marker = Math.max(0, Math.round(raw / quantum) * quantum);
      this.timelineMarker = marker;
      this.renderTimeline();
      EditorApp.element("status").textContent =
        `Marker placed at ${EditorApp.timecode(marker)}`;
    });
    EditorApp.element("timeline").addEventListener(
      "pointerdown",
      this.beginTimelineScrub,
    );
    EditorApp.element("timeline").addEventListener(
      "scroll",
      this.updateTimelineCursor,
      { passive: true },
    );
    EditorApp.element("timeline-fit-all").addEventListener("click", () => {
      const events = this.activeFlow()?.events ?? [];
      this.fitTimeline(
        0,
        Math.max(0, ...events.map((event) => event.elapsed_ms ?? 0)),
      );
      EditorApp.element("timeline").scrollLeft = 0;
    });
    EditorApp.element("timeline-rewind").addEventListener("click", () => {
      const first = document.querySelector(
        ".edit-step-row, #timeline .clip[data-step]",
      );
      if (first instanceof HTMLElement) first.click();
    });
    EditorApp.element("timeline-play").addEventListener("click", () =>
      this.command("run.play", { scope: "flow" }),
    );
    EditorApp.element("timeline-stop").addEventListener("click", () => {
      this.updateTimelineClock(null);
      this.command("run.cancel");
    });
    EditorApp.element("timeline-pause").addEventListener("click", () =>
      this.command(
        this.snapshot?.run_control?.state === "paused"
          ? "run.resume"
          : "run.pause",
      ),
    );
    EditorApp.element("timeline-step").addEventListener("click", () =>
      this.command("run.step", { scope: "flow" }),
    );
    [
      ["timeline-zoom-out", -1],
      ["timeline-zoom-in", 1],
    ].forEach(([id, direction]) => {
      EditorApp.element(String(id)).addEventListener("click", () => {
        const slider = EditorApp.element("timeline-zoom");
        if (!(slider instanceof HTMLInputElement)) return;
        this.setTimelineZoom(
          EditorApp.zoomFromSlider(
            Math.min(
              Number(slider.max),
              Math.max(
                Number(slider.min),
                Number(slider.value) + Number(direction) * 5,
              ),
            ),
          ),
        );
      });
    });
    EditorApp.element("timeline-fit-selection").addEventListener(
      "click",
      () => {
        const chosen = (this.activeFlow()?.events ?? []).filter((event) =>
          this.selectedEventIds.has(event.id),
        );
        if (!chosen.length) return;
        const times = chosen.map((event) => event.elapsed_ms ?? 0);
        this.fitTimeline(Math.min(...times), Math.max(...times));
      },
    );
    EditorApp.element("timeline").addEventListener(
      "pointerdown",
      this.beginMarquee,
    );
    EditorApp.element("timeline").addEventListener("keydown", (key) => {
      if ((key.ctrlKey || key.metaKey) && key.key.toLowerCase() === "a") {
        key.preventDefault();
        this.setSelection(
          (this.activeFlow()?.events ?? []).map((event) => event.id),
        );
      }
    });
    /** Clamp and apply a new graph zoom level.
     * @param {number} value Requested zoom level.
     * @returns {void}
     */
    EditorApp.element("graph-zoom-out").addEventListener("click", () =>
      this.setGraphZoom(this.graphZoom - 0.1),
    );
    EditorApp.element("graph-zoom-in").addEventListener("click", () =>
      this.setGraphZoom(this.graphZoom + 0.1),
    );
    EditorApp.element("graph-fit").addEventListener("click", () =>
      this.fitGraph(),
    );
    EditorApp.element("graph").addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      this.graphConnectionSource = "";
      const graph = EditorApp.element("graph");
      graph.removeAttribute("data-connecting");
      graph.querySelector(".composition-preview-links")?.remove();
      graph
        .querySelector(".is-connection-source")
        ?.classList.remove("is-connection-source");
      EditorApp.element("status").textContent = "Connection cancelled";
    });
    new ResizeObserver(() => {
      if (this.workspaceView === "graph") this.renderConnections();
    }).observe(EditorApp.element("graph"));
    document
      .querySelectorAll(".mobile-panel-tabs [data-mobile-panel]")
      .forEach((node) => {
        node.addEventListener("click", () => {
          const panel = node.getAttribute("data-mobile-panel") || "steps";
          EditorApp.element("app").setAttribute("data-mobile-panel", panel);
          document
            .querySelectorAll(".mobile-panel-tabs [data-mobile-panel]")
            .forEach((item) => {
              const active = item.getAttribute("data-mobile-panel") === panel;
              item.classList.toggle("active", active);
              item.setAttribute("aria-pressed", String(active));
            });
          const destination =
            panel === "properties"
              ? document.querySelector(".inspector")
              : panel === "runs"
                ? document.querySelector(".runs")
                : document.querySelector(
                    this.workspaceView === "graph" ? ".graph" : ".table-panel",
                  );
          if (destination instanceof HTMLElement)
            destination.focus({ preventScroll: true });
        });
      });
    document.querySelectorAll("[data-workspace-view]").forEach((node) => {
      node.addEventListener("click", () => {
        const view = node.getAttribute("data-workspace-view") || "edit";
        this.setWorkspaceView(view);
      });
    });
    const workspaceSelect = document.getElementById("workspace-view-select");
    workspaceSelect?.addEventListener("change", () => {
      if (workspaceSelect instanceof HTMLSelectElement)
        this.setWorkspaceView(workspaceSelect.value || "edit");
    });
    const workspaceSurface = EditorApp.element("workspace-surface");
    workspaceSurface.addEventListener("click", async (event) => {
      if (!(event.target instanceof Element)) return;
      const compareButton = event.target.closest("[data-compare-mode]");
      if (compareButton) {
        this.compareMode =
          compareButton.getAttribute("data-compare-mode") || "side";
        this.renderWorkspaceSurface();
        return;
      }
      const compareDecision = event.target.closest("[data-compare-decision]");
      if (compareDecision) {
        this.compareDecision =
          compareDecision.getAttribute("data-compare-decision") || "";
        EditorApp.element("status").textContent =
          this.compareDecision === "review"
            ? "Baseline review selected. Confirm it when comparison persistence is connected."
            : "Visual change rejected; the saved baseline is unchanged.";
        this.renderWorkspaceSurface();
        return;
      }
      const inspectorButton = event.target.closest("[data-inspector-tab]");
      if (inspectorButton) {
        this.inspectorTab =
          inspectorButton.getAttribute("data-inspector-tab") || "settings";
        this.renderWorkspaceSurface();
        return;
      }
      const returnButton = event.target.closest("[data-workspace-return]");
      if (returnButton) {
        this.setWorkspaceView(
          returnButton.getAttribute("data-workspace-return") || "edit",
        );
        return;
      }
      const commandButton = event.target.closest("[data-surface-command]");
      if (commandButton) {
        const command =
          commandButton.getAttribute("data-surface-command") || "";
        if (command === "palette") EditorApp.openCommandPalette();
        else if (command === "actions.recipe") {
          const dialog = EditorApp.element("actions-dialog");
          if (dialog instanceof HTMLDialogElement) dialog.showModal();
        } else if (command === "workspace.open") {
          this.projects?.gallery();
        } else if (command) {
          const scope = commandButton.getAttribute("data-surface-scope");
          this.command(command, scope ? { scope } : {});
        }
        return;
      }
      const profileButton = event.target.closest("[data-surface-profile]");
      if (profileButton) {
        this.command("viewport.preset", {
          mode: profileButton.getAttribute("data-surface-profile") || "desktop",
        });
        return;
      }
      const eventButton = event.target.closest("[data-surface-event]");
      if (eventButton) {
        this.selectedEventId =
          eventButton.getAttribute("data-surface-event") || "";
        if (this.workspaceView !== "play") this.setWorkspaceView("edit");
        else this.renderWorkspaceSurface();
        return;
      }
      if (event.target.closest("[data-surface-reset-layout]")) {
        this.dock.reset();
        return;
      }
      const stepButton = event.target.closest("[data-compare-key]");
      if (stepButton) {
        this.compareKey = stepButton.getAttribute("data-compare-key") || "";
        this.renderWorkspaceSurface();
        return;
      }
      const shotButton = event.target.closest("[data-surface-shot]");
      if (shotButton) {
        const shotId = shotButton.getAttribute("data-surface-shot") || "";
        // The server checks the file still exists; the snapshot already holds
        // the path it is served from, so the reply does not need to repeat it.
        const result = await this.call("screenshot.open", {
          artifact_id: shotId,
        });
        const path =
          this.workspace?.screenshots?.find((shot) => shot.id === shotId)
            ?.path ?? result.path;
        const image = EditorApp.element("screenshot-preview");
        const link = EditorApp.element("screenshot-download");
        const dialog = EditorApp.element("screenshot-dialog");
        if (
          image instanceof HTMLImageElement &&
          link instanceof HTMLAnchorElement &&
          dialog instanceof HTMLDialogElement &&
          path
        ) {
          image.src = path;
          link.href = path;
          dialog.showModal();
        }
      }
    });
    workspaceSurface.addEventListener("submit", async (event) => {
      if (!(event.target instanceof HTMLFormElement)) return;
      if (event.target.id !== "surface-crawl-form") return;
      event.preventDefault();
      // Discovery replaces the project when it finishes, so unsaved edits
      // are never lost without asking.
      if (this.dirty && !(await EditorApp.confirmReplacement())) return;
      const data = new FormData(event.target);
      this.command("crawl.start", {
        include_selector: String(data.get("selector") || ""),
        max_depth: String(data.get("max_depth") || "3"),
        max_states: String(data.get("max_states") || "20"),
        follow_links: data.has("follow_links"),
        click_controls: data.has("click_controls"),
        capture_ui_changes: data.has("capture_ui_changes"),
      });
    });
    const commandSearch = EditorApp.element("command-search");
    commandSearch.addEventListener("input", () => {
      const query =
        commandSearch instanceof HTMLInputElement
          ? commandSearch.value.trim().toLowerCase()
          : "";
      document.querySelectorAll("[data-palette-command]").forEach((item) => {
        if (item instanceof HTMLElement)
          item.hidden = !item.textContent?.toLowerCase().includes(query);
      });
    });
    document.querySelectorAll("[data-palette-command]").forEach((node) => {
      node.addEventListener("click", () => {
        const action = node.getAttribute("data-palette-command") || "";
        const dialog = EditorApp.element("command-palette");
        if (dialog instanceof HTMLDialogElement) dialog.close();
        if (action === "run") this.command("run.play");
        else if (action === "record") this.command("recorder.record");
        else if (action === "screenshot")
          this.command("event.add", { kind: "screenshot" });
        else if (action === "save") this.projects?.save();
        else if (action === "new-project") this.projects?.create();
        else if (action === "open-gallery") this.projects?.gallery();
        else if (action === "reset-layout") this.dock.reset();
        else this.setWorkspaceView(action);
      });
    });
    window.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        EditorApp.openCommandPalette();
      }
    });
    document.querySelectorAll("[data-cmd]").forEach((node) => {
      node.addEventListener("click", async () => {
        const commandName = node.getAttribute("data-cmd");
        if (commandName) await this.command(commandName);
      });
    });
    EditorApp.element("device").addEventListener("change", () => {
      const device = EditorApp.element("device");
      if (device instanceof HTMLSelectElement)
        this.command("viewport.preset", {
          mode: device.value,
        });
    });
    EditorApp.element("browser-profiles").addEventListener("click", () =>
      this.setWorkspaceView("settings"),
    );
    EditorApp.element("browser-toggle").addEventListener("click", () => {
      const live = ["ready", "opening"].includes(
        this.snapshot?.target_state ?? "",
      );
      // Closing is a choice; do not reopen it behind the user's back.
      this.userClosedBrowser = live;
      this.command(live ? "browser.close" : "browser.open");
    });
  }
}
watchIcons();
const transport = new StudioTransport();
try {
  await transport.connect();
  const app = new EditorApp(transport);
  app.render();
} catch (error) {
  EditorApp.element("status").textContent =
    error instanceof Error ? error.message : String(error);
}
