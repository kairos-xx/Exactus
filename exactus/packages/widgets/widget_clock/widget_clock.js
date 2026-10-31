/** @typedef {{value:any,groupValues:any,live:any,fps:any,mode:any,template:any,structure:any,matrixLayout:any,matrixRows:any,matrixColumns:any,matrixDotSize:any,matrixDotGap:any,matrixOnColor:any,matrixOffColor:any,matrixGlowSize:any,digitWidth:any,digitHeight:any,digitInset?:number,segmentLength:any,segmentThickness:any,segmentGap:any,digitGap:any,groupGap:any,separatorWidth:any,dotSize:any,blinkSeparatorsOnSecond:any,dotBlinkDuration:any,segmentOnColor:any,segmentOffColor:any,segmentGlowColor:any,segmentGlowSize:any,segmentOnDuration:any,segmentOffDuration:any,transitionEasing:any,recVisible:any,recEnabled:any,recording:any,recPulse:any,recLedSize:any,recLedOnColor:any,recLedOffColor:any,recLedGlowColor:any,recLedGlowSize:any,recPulseDuration:any,recLabel:any,recFontFamily:any,recFontSize:any,recFontWeight:any,recLetterSpacing:any,recTextColor:any,recGap:any,recWidgetGap:any,background:any,align:any,padding:any, [key:string]:any}} ClockSettings */
"use strict";
/** Seven-segment and matrix timecode widget rendered into a container.
 */
class AnalogClock {
  static #sheet = (() => {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync(
      '.sst-root {\n  position: relative;\n  inline-size: 100%;\n  block-size: 100%;\n  overflow: hidden;\n  display: flex;\n  align-items: center;\n  justify-content: var(--sst-align,center);\n  background: var(--sst-bg);\n  padding: var(--sst-padding);\n  container-type: size;\n}\n\n.sst-stage {\n  display: flex;\n  align-items: center;\n  justify-content: flex-start;\n  gap: var(--sst-widget-gap);\n  transform: scale(var(--sst-scale));\n  transform-origin: center center;\n  inline-size: max-content;\n  block-size: max-content;\n  flex: none;\n}\n\n.sst-clock {\n  display: flex;\n  align-items: center;\n  gap: 0;\n  flex: none;\n}\n\n.sst-root[data-mode="matrix"] .sst-stage {\n  transform: none;\n}\n\n.sst-root[data-mode="matrix"][data-matrix-layout="target"] .sst-stage,\n      .sst-root[data-mode="matrix"][data-matrix-layout="target"] .sst-clock {\n  inline-size: 100%;\n  block-size: 100%;\n}\n\n.sst-root[data-mode="matrix"][data-matrix-layout="target"] .sst-matrix {\n  inline-size: max-content;\n  block-size: max-content;\n}\n\n.sst-group {\n  display: flex;\n  align-items: center;\n  column-gap: var(--sst-digit-gap);\n  flex: none;\n}\n\n.sst-between {\n  margin-inline-start: var(--sst-group-gap);\n  margin-inline-end: var(--sst-group-gap);\n}\n\n.sst-digit {\n  inline-size: var(--sst-digit-width);\n  block-size: 192px;\n  overflow: visible;\n  flex: none;\n}\n\n.sst-separator {\n  inline-size: var(--sst-separator-width);\n  block-size: 192px;\n  overflow: visible;\n  flex: none;\n}\n\n.sst-matrix {\n  display: grid;\n  grid-template-columns: repeat(\n          var(--sst-matrix-cols),\n          var(--sst-matrix-dot)\n        );\n  grid-template-rows: repeat(\n          var(--sst-matrix-rows),\n          var(--sst-matrix-dot)\n        );\n  gap: var(--sst-matrix-gap);\n  align-content: center;\n  justify-content: center;\n  inline-size: max-content;\n  block-size: max-content;\n  flex: none;\n}\n\n.sst-matrix[data-layout="target"] {\n  inline-size: 100%;\n  block-size: 100%;\n  grid-template-columns: repeat(\n          var(--sst-matrix-physical-cols),\n          var(--sst-matrix-dot)\n        );\n  grid-template-rows: repeat(\n          var(--sst-matrix-physical-rows),\n          var(--sst-matrix-dot)\n        );\n  gap: var(--sst-matrix-gap);\n  align-content: center;\n  justify-content: center;\n}\n\n.sst-matrix-dot {\n  inline-size: var(--sst-matrix-dot);\n  min-inline-size: var(--sst-matrix-dot);\n  max-inline-size: var(--sst-matrix-dot);\n  block-size: var(--sst-matrix-dot);\n  min-block-size: var(--sst-matrix-dot);\n  max-block-size: var(--sst-matrix-dot);\n  place-self: center;\n  border-radius: 50%;\n  background: var(--sst-matrix-off);\n  opacity: 1;\n  transition: opacity var(--sst-dot-time) ease;\n}\n\n.sst-matrix-dot.sst-on {\n  background: var(--sst-matrix-on);\n  box-shadow: var(--sst-matrix-glow);\n}\n\n.sst-custom-marker {\n  display: flex;\n  align-items: flex-end;\n  justify-content: center;\n  min-inline-size: var(--marker-size);\n  margin-inline-start: var(--marker-before);\n  margin-inline-end: var(--marker-after);\n  color: var(--marker-color);\n  font-size: var(--marker-size);\n  line-height: 1;\n  text-shadow: 0 0 var(--marker-glow-size) var(--marker-glow-color);\n  flex: none;\n  transition: opacity var(--sst-dot-time) ease;\n}\n\n.sst-segment {\n  fill: var(--sst-off);\n  transition: fill var(--sst-off-time) var(--sst-ease),\n          filter var(--sst-off-time) var(--sst-ease);\n}\n\n.sst-segment.sst-on {\n  fill: var(--sst-on);\n  filter: drop-shadow(var(--sst-segment-glow));\n  transition-duration: var(--sst-on-time),var(--sst-on-time);\n}\n\n.sst-dot {\n  fill: var(--sst-on);\n  opacity: 1;\n  transition: opacity var(--sst-dot-time) ease;\n}\n\n.sst-blink .sst-dot,\n      .sst-blink .sst-matrix-dot.sst-separator-dot[data-blink="true"],\n      .sst-blink .sst-custom-marker[data-blink="true"] {\n  opacity: 0;\n}\n\n.sst-rec {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  gap: var(--sst-rec-gap);\n  flex: none;\n  min-block-size: 192px;\n  color: var(--sst-rec-text);\n  font-family: var(--sst-rec-font);\n  font-size: var(--sst-rec-font-size);\n  font-weight: var(--sst-rec-weight);\n  letter-spacing: var(--sst-rec-spacing);\n  line-height: 1;\n}\n\n.sst-rec[data-visibility="reserved"] {\n  visibility: hidden;\n}\n\n.sst-rec[data-visibility="hidden"] {\n  display: none;\n}\n\n.sst-led {\n  inline-size: var(--sst-rec-size);\n  block-size: var(--sst-rec-size);\n  flex: none;\n  border-radius: 50%;\n  background: var(--sst-rec-off);\n  box-shadow: inset 0 0 0 1px rgb(255 255 255 / 8%);\n}\n\n.sst-rec.sst-recording .sst-led {\n  background: var(--sst-rec-on);\n  box-shadow: var(--sst-rec-glow-effect);\n}\n\n.sst-rec.sst-pulse .sst-led {\n  animation: sst-pulse var(--sst-rec-pulse) ease-in-out infinite;\n}\n\n.sst-rec:not(.sst-enabled) {\n  opacity: .38;\n}\n\n@keyframes sst-pulse {\n0%,100%{opacity:1} 50%{opacity:.3}\n}\n\n@media (prefers-reduced-motion:reduce) {\n.sst-segment,.sst-dot { transition-duration:0ms; }\n        .sst-rec.sst-pulse .sst-led { animation:none; }\n}\n',
    );
    return sheet;
  })();
  /** @type {HTMLDivElement} */
  root = Object.assign(document.createElement("div"), {
    className: "sst-root",
  });
  /** @type {HTMLDivElement} */
  stage = Object.assign(document.createElement("div"), {
    className: "sst-stage",
  });
  /** @type {HTMLDivElement} */
  clock = Object.assign(document.createElement("div"), {
    className: "sst-clock",
    role: "timer",
  });
  /** @type {HTMLDivElement} */
  rec = Object.assign(document.createElement("div"), {
    className: "sst-rec",
    ariaLabel: "Recording indicator",
  });
  /** @type {HTMLSpanElement} */
  led = Object.assign(document.createElement("span"), {
    className: "sst-led",
    ariaHidden: "true",
  });
  /** @type {HTMLSpanElement} */
  recLabel = document.createElement("span");
  /** @type {any[]} */
  digits;
  /** @type {any[]} */
  separators;
  /** @type {any[]} */
  matrixDots = [];
  /** @type {number|undefined} */
  lastSecond;
  static NS = "http://www.w3.org/2000/svg";
  /** @type {Record<string,string>} */
  static DIGITS = Object.freeze({
    0: "abcdef",
    1: "bc",
    2: "abdeg",
    3: "abcdg",
    4: "bcfg",
    5: "acdfg",
    6: "acdefg",
    7: "abc",
    8: "abcdefg",
    9: "abcdfg",
    "-": "g",
  });
  /** @type {ClockSettings} */
  static DEFAULTS = Object.freeze({
    value: null,
    groupValues: null,
    live: true,
    fps: 30,
    mode: "segment",
    template: "dd:dd:dd.dd",
    structure: null,
    matrixLayout: "content",
    matrixRows: 7,
    matrixColumns: 5,
    matrixDotSize: 7,
    matrixDotGap: 4,
    matrixOnColor: "#ff3b30",
    matrixOffColor: "#251514",
    matrixGlowSize: 5,
    digitWidth: 120,
    digitHeight: 192,
    digitInset: 14,
    segmentLength: 76,
    segmentThickness: 14,
    segmentGap: 4,
    digitGap: 0,
    groupGap: 0,
    separatorWidth: 24,
    dotSize: 10,
    blinkSeparatorsOnSecond: true,
    dotBlinkDuration: 160,
    segmentOnColor: "#ff3b30",
    segmentOffColor: "#251514",
    segmentGlowColor: "#ff3b30",
    segmentGlowSize: 5,
    segmentOnDuration: 120,
    segmentOffDuration: 300,
    transitionEasing: "cubic-bezier(.2,.8,.2,1)",
    recVisible: "visible",
    recEnabled: true,
    recording: true,
    recPulse: true,
    recLedSize: 12,
    recLedOnColor: "#ff2d2d",
    recLedOffColor: "#3b1818",
    recLedGlowColor: "#ff2d2d",
    recLedGlowSize: 12,
    recPulseDuration: 1000,
    recLabel: "REC",
    recFontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
    recFontSize: 15,
    recFontWeight: 700,
    recLetterSpacing: 2,
    recTextColor: "#aeb3ba",
    recGap: 10,
    recWidgetGap: 20,
    background: "transparent",
    align: "center",
    padding: 0,
  });
  static #instanceSheet = new CSSStyleSheet();
  static #installedDocuments = new WeakSet();
  static #instances = new Map();
  static #nextId = 1;
  /** Settings with native CSS consumers: preserve the binding, not its snapshot. */
  /** @type {Record<string, [string,string]>} */
  static CSS_SETTINGS = Object.freeze({
    segmentOnDuration: ["--sst-on-time", "ms"],
    segmentOffDuration: ["--sst-off-time", "ms"],
    dotBlinkDuration: ["--sst-dot-time", "ms"],
    transitionEasing: ["--sst-ease", ""],
    segmentOnColor: ["--sst-on", ""],
    segmentOffColor: ["--sst-off", ""],
    recPulseDuration: ["--sst-rec-pulse", "ms"],
    recTextColor: ["--sst-rec-text", ""],
    recLedOnColor: ["--sst-rec-on", ""],
    recLedOffColor: ["--sst-rec-off", ""],
    recFontSize: ["--sst-rec-font-size", "px"],
    recFontWeight: ["--sst-rec-weight", ""],
    recFontFamily: ["--sst-rec-font", ""],
    recLetterSpacing: ["--sst-rec-spacing", "px"],
    background: ["--sst-bg", ""],
    align: ["--sst-align", ""],
  });
  static isCssVariable = (/** @type {any} */ value) =>
    typeof value === "string" && /^--[a-zA-Z_][\w-]*$/.test(value);
  static resolveCssValue = (
    /** @type {any} */ name,
    /** @type {any} */ text,
    /** @type {any} */ fallback,
  ) => {
    if (!text.trim()) return fallback;
    const value = text.trim();
    if (typeof AnalogClock.DEFAULTS[name] === "number") {
      const match = /^([+-]?(?:\d+(?:\.\d*)?|\.\d+))(ms|s|px)?$/.exec(value);
      if (!match)
        throw new TypeError(`${name} requires a numeric CSS variable`);
      const unit = match[2] ?? "";
      const expected =
        AnalogClock.CSS_SETTINGS[name]?.[1] ??
        (name.endsWith("Duration") ? "ms" : "");
      if (unit && unit !== expected && !(unit === "s" && expected === "ms"))
        throw new TypeError(`Invalid CSS unit for ${name}`);
      return Number(match[1]) * (unit === "s" ? 1000 : 1);
    }
    if (typeof AnalogClock.DEFAULTS[name] === "boolean") {
      if (!["true", "false", "1", "0"].includes(value))
        throw new TypeError(`${name} requires true/false or 1/0`);
      return value === "true" || value === "1";
    }
    return value;
  };
  /** Pure validation: never partially apply an invalid configuration. */
  static validateSettings = (/** @type {any} */ settings) => {
    if (!settings || typeof settings !== "object" || Array.isArray(settings))
      throw new TypeError("settings must be an options object");
    Object.entries(settings).forEach((/** @type {any} */ [name, value]) => {
      if (value === undefined) return;
      if (!Object.hasOwn(AnalogClock.DEFAULTS, name))
        throw new TypeError(`Unknown setting: ${name}`);
      if (
        AnalogClock.isCssVariable(value) &&
        !["value", "groupValues", "structure", "template"].includes(name)
      )
        return;
      const defaultValue = AnalogClock.DEFAULTS[name];
      if (
        typeof defaultValue === "number" &&
        (!Number.isFinite(value) || value < 0)
      )
        throw new RangeError(`${name} must be a finite non-negative number`);
      if (typeof defaultValue === "boolean" && typeof value !== "boolean")
        throw new TypeError(`${name} must be a boolean`);
      if (typeof defaultValue === "string" && typeof value !== "string")
        throw new TypeError(`${name} must be a string`);
    });
    if (!AnalogClock.isCssVariable(settings.fps))
      AnalogClock.validateFps(settings.fps ?? AnalogClock.DEFAULTS.fps);
    Object.entries({
      mode: ["segment", "matrix"],
      matrixLayout: ["content", "target"],
      recVisible: ["visible", "reserved", "hidden"],
      align: ["flex-start", "center", "flex-end"],
    }).forEach((/** @type {any} */ [name, values]) => {
      if (
        settings[name] !== undefined &&
        !AnalogClock.isCssVariable(settings[name]) &&
        !values.includes(settings[name])
      )
        throw new TypeError(`Invalid ${name}`);
    });
    ["matrixRows", "matrixColumns"].forEach((/** @type {any} */ name) => {
      if (
        settings[name] !== undefined &&
        !AnalogClock.isCssVariable(settings[name]) &&
        (!Number.isInteger(settings[name]) ||
          settings[name] < 1 ||
          settings[name] > 64)
      )
        throw new RangeError(`${name} must be an integer from 1 to 64`);
    });
    if (settings.structure !== undefined && settings.structure !== null) {
      if (
        !Array.isArray(settings.structure) ||
        !settings.structure.some(
          (/** @type {any} */ item) => item?.type === "group",
        )
      )
        throw new TypeError("structure must contain a digit group");
      settings.structure.forEach((/** @type {any} */ item) => {
        if (
          item?.type === "group" &&
          Number.isInteger(item.digits) &&
          item.digits >= 1 &&
          item.digits <= 12
        )
          return;
        if (
          item?.type === "marker" &&
          typeof item.symbol === "string" &&
          item.symbol.length === 1
        )
          return;
        throw new TypeError(
          "structure entries must be digit groups (1–12 digits) or single-character markers",
        );
      });
    }
    if (
      settings.template !== undefined &&
      !/^d+[.:d]*$/.test(settings.template)
    )
      throw new TypeError("template must contain digits and colon/dot markers");
    if (settings.matrixDotSize === 0 && settings.matrixDotGap === 0)
      throw new RangeError("matrix dot pitch must be positive");
  };
  static validateFps = (/** @type {any} */ fps) => {
    if (!Number.isInteger(fps) || fps < 1 || fps > 100)
      throw new RangeError(
        "fps must be an integer from 1 to 100 (non-drop-frame)",
      );
  };
  /** Non-drop-frame HH:MM:SS.FF, independent of timezone or wall clock. */
  static formatFrame = (
    /** @type {any} */ frame,
    /** @type {any} */ { fps = 30 } = {},
  ) => {
    AnalogClock.validateFps(fps);
    if (!Number.isSafeInteger(frame) || frame < 0 || frame >= 360000 * fps)
      throw new RangeError(
        "frame must be a non-negative integer below 100 hours",
      );
    const seconds = Math.floor(frame / fps);
    return `${AnalogClock.two(Math.floor(seconds / 3600))}:${AnalogClock.two(Math.floor(seconds / 60) % 60)}:${AnalogClock.two(seconds % 60)}.${AnalogClock.two(frame % fps)}`;
  };
  /** Floor to a frame boundary; input is elapsed milliseconds, not seconds. */
  static formatTime = (
    /** @type {number} */ milliseconds,
    /** @type {{fps?:number,precision?:"frames"|"milliseconds"}} */ {
      fps = 30,
      precision = "frames",
    } = {},
  ) => {
    AnalogClock.validateFps(fps);
    if (
      !Number.isFinite(milliseconds) ||
      milliseconds < 0 ||
      milliseconds >= 360000000
    )
      throw new RangeError(
        "time must be finite milliseconds from 0 to below 100 hours",
      );
    if (precision === "milliseconds")
      return `${AnalogClock.formatFrame(Math.floor(milliseconds / 1000) * fps, { fps }).slice(0, -2)}${String(Math.floor(milliseconds) % 1000).padStart(3, "0")}`;
    if (precision !== "frames")
      throw new TypeError("precision must be frames or milliseconds");
    return AnalogClock.formatFrame(Math.floor(milliseconds * fps / 1000), {
      fps,
    });
  };
  #destroyed = false;
  /** @type {ClockSettings} */
  #settings;
  /** @type {ClockSettings} */
  #settingsView;
  #bindings = new Map();
  /** @type {number|undefined} */
  #bindingRequest;
  /** Resolved settings the clock currently runs with.
   * @returns {ClockSettings}
   */
  get settings() {
    return this.#settingsView;
  }
  /** Resolve a bound CSS variable or the literal setting value.
   * @param {any} name
   * @param {any} unit
   * @returns {any}
   */
  cssValue(name, unit = "") {
    return this.#bindings.has(name)
      ? `var(${this.#bindings.get(name)}, ${this.#settings[name]}${unit})`
      : `${this.#settings[name]}${unit}`;
  }
  /** Merge given settings over computed CSS-variable values.
   * @param {any} settings
   * @returns {any}
   */
  resolveSettings(settings) {
    const computed = getComputedStyle(this.target);
    return Object.fromEntries(
      Object.entries(settings)
        .filter((/** @type {any} */ [, value]) => value !== undefined)
        .map((/** @type {any} */ [name, value]) => [
          name,
          AnalogClock.isCssVariable(value)
            ? AnalogClock.resolveCssValue(
                name,
                computed.getPropertyValue(value),
                this.#settings[name],
              )
            : value,
        ]),
    );
  }
  /** Rebind CSS variables once custom properties resolve.
   */
  watchBindings() {
    this.#bindingRequest = undefined;
    if (this.#destroyed) return;
    const computed = getComputedStyle(this.target);
    /** @type {Record<string, any>} */
    const changes = {};
    this.#bindings.forEach(
      (/** @type {any} */ variable, /** @type {any} */ name) => {
        if (Object.hasOwn(AnalogClock.CSS_SETTINGS, name)) return;
        try {
          const value = AnalogClock.resolveCssValue(
            name,
            computed.getPropertyValue(variable),
            this.#settings[name],
          );
          if (value !== this.#settings[name]) changes[name] = value;
        } catch {
          /* Keep the last valid runtime value while CSS is incomplete. */
        }
      },
    );
    if (Object.keys(changes).length) {
      try {
        this.applySettings(changes, true);
      } catch {
        /* Invalid runtime CSS never corrupts the renderer. */
      }
    }
    if (
      [...this.#bindings.keys()].some(
        (/** @type {any} */ name) =>
          !Object.hasOwn(AnalogClock.CSS_SETTINGS, name),
      )
    )
      this.#bindingRequest = requestAnimationFrame(() => this.watchBindings());
  }
  /** @type {number|undefined} */
  #fitRequest;
  /** @type {number|null} */
  #timeMilliseconds = null;
  /** Reject interaction after the clock was destroyed.
   * @throws {Error}
   */
  assertActive() {
    if (this.#destroyed) throw new Error("AnalogClock has been destroyed");
  }
  static installStyles = (/** @type {any} */ documentRef) => {
    if (AnalogClock.#installedDocuments.has(documentRef)) return;
    documentRef.adoptedStyleSheets = [
      ...documentRef.adoptedStyleSheets,
      AnalogClock.#sheet,
      AnalogClock.#instanceSheet,
    ];
    AnalogClock.#installedDocuments.add(documentRef);
  };
  static refreshInstanceStyles = () => {
    AnalogClock.#instanceSheet.replaceSync(
      [...AnalogClock.#instances.entries()]
        .map((/** @type {any} */ [id, variables]) => {
          const body = Object.entries(variables)
            .map((/** @type {any} */ [name, value]) => `${name}:${value}`)
            .join(";");
          return `[data-seven-segment="${id}"]{${body}}`;
        })
        .join("\n"),
    );
  };
  static createId = () => {
    const cryptoApi = globalThis.crypto;
    return (
      cryptoApi?.randomUUID?.() ?? `seven-segment-${AnalogClock.#nextId++}`
    );
  };
  /** Mount a clock into a container element.
   * @param {any} target Container element that receives the clock DOM.
   * @param {any} settings Initial clock settings.
   * @throws {TypeError} When target is not an element of this document or already holds a clock.
   */
  constructor(/** @type {any} */ target, /** @type {any} */ settings = {}) {
    if (!(target instanceof HTMLElement))
      throw new TypeError("target must be an HTMLElement");
    if (target.ownerDocument !== document)
      throw new TypeError("target must belong to the current document");
    if (target.getAttribute("data-seven-segment"))
      throw new Error("target already contains a clock");
    this.target = target;
    this.#settings = {
      ...AnalogClock.DEFAULTS,
    };
    AnalogClock.validateSettings(settings);
    const resolved = this.resolveSettings(settings);
    AnalogClock.validateSettings({
      ...this.#settings,
      ...resolved,
    });
    Object.entries(resolved).forEach((/** @type {any} */ [name, value]) => {
      this.#settings[name] =
        name === "structure" && value !== null ? structuredClone(value) : value;
    });
    Object.entries(settings).forEach((/** @type {any} */ [name, value]) => {
      if (AnalogClock.isCssVariable(value)) this.#bindings.set(name, value);
    });
    this.#settingsView = new Proxy(this.#settings, {
      get: (/** @type {any} */ settingsTarget, /** @type {any} */ name) =>
        this.#bindings.get(name) ?? structuredClone(settingsTarget[name]),
      set: (
        /** @type {any} */ _settingsTarget,
        /** @type {any} */ name,
        /** @type {any} */ value,
      ) => {
        this.set({
          [name]: value,
        });
        return true;
      },
      deleteProperty: () => {
        throw new TypeError("Use set() to update clock settings");
      },
      defineProperty: () => {
        throw new TypeError("Use set() to update clock settings");
      },
    });
    this.digits = [];
    this.separators = [];
    this.lastDigits = "";
    this.lastSecond = undefined;
    this.blinkTimer = undefined;
    this.frameRequest = undefined;
    this.id = AnalogClock.createId();
    this.target.setAttribute("data-seven-segment", String(this.id));
    AnalogClock.installStyles(this.target.ownerDocument);
    AnalogClock.#instances.set(this.id, {});
    this.build();
    this.observer = new ResizeObserver(() => {
      if (
        this.#settings.mode === "matrix" &&
        this.#settings.matrixLayout === "target"
      ) {
        this.rebuildMatrixDots();
        this.renderValue(this.#settings.value);
      }
      this.fit();
    });
    this.observer.observe(this.target);
    this.applySettings();
    this.watchBindings();
    if (settings.value !== undefined && settings.value !== null)
      this.value = settings.value;
    if (settings.groupValues !== undefined && settings.groupValues !== null)
      this.value = settings.groupValues;
  }
  /** Create the clock DOM inside the target element.
   */
  build() {
    this.rec.append(this.led, this.recLabel);
    this.stage.append(this.clock, this.rec);
    this.root.append(this.stage);
    this.target.replaceChildren(this.root);
    this.rebuildRenderer();
  }
  /** Rebuild whichever renderer the current mode needs.
   */
  rebuildRenderer() {
    this.clock.replaceChildren();
    Object.assign(this, {
      lastDigits: "",
      digits: [],
      separators: [],
      matrixDots: [],
    });
    if (this.#settings.mode === "matrix") this.buildMatrix();
    else this.buildSegments();
  }
  /** Structure parsed from the default template.
   * @returns {any}
   */
  defaultStructure() {
    return this.structureFromTemplate("dd:dd:dd.dd");
  }
  /** Structure entries parsed from a template string.
   * @param {any} template
   * @returns {any}
   */
  structureFromTemplate(template) {
    /** @type {any[]} */
    const result = [];
    let digits = 0;
    const flush = () => {
      if (digits < 1) return;
      result.push({
        type: "group",
        digits,
        digitGap: this.#settings.digitGap,
        color: this.#settings.segmentOnColor,
        offColor: this.#settings.segmentOffColor,
        glowColor: this.#settings.segmentGlowColor,
        glowSize: this.#settings.segmentGlowSize,
        segmentLength: this.#settings.segmentLength,
        segmentThickness: this.#settings.segmentThickness,
        segmentGap: this.#settings.segmentGap,
        onDuration: this.#settings.segmentOnDuration,
        offDuration: this.#settings.segmentOffDuration,
        easing: this.#settings.transitionEasing,
        matrixColumns: this.#settings.matrixColumns,
        matrixDotSize: this.#settings.matrixDotSize,
        matrixDotGap: this.#settings.matrixDotGap,
      });
      digits = 0;
    };
    [...template].forEach((/** @type {any} */ symbol) => {
      if (symbol === "d") {
        digits += 1;
        return;
      }
      flush();
      result.push({
        type: "marker",
        symbol,
        size: this.#settings.dotSize,
        color: this.#settings.segmentOnColor,
        offColor: this.#settings.segmentOffColor,
        glowColor: this.#settings.segmentGlowColor,
        glowSize: this.#settings.segmentGlowSize,
        gapBefore: this.#settings.groupGap,
        gapAfter: this.#settings.groupGap,
        blink: true,
      });
    });
    flush();
    return result;
  }
  /** Structure entries normalised to plain objects.
   * @returns {any}
   */
  normalizedStructure() {
    if (
      Array.isArray(this.#settings.structure) &&
      this.#settings.structure.length > 0
    )
      return structuredClone(this.#settings.structure);
    const template =
      typeof this.#settings.template === "string" &&
      this.#settings.template.length > 0
        ? this.#settings.template
        : "dd:dd:dd.dd";
    return this.structureFromTemplate(template);
  }
  /** Digit-group entries taken from the structure.
   * @returns {any}
   */
  groupItems() {
    return this.normalizedStructure().filter(
      (/** @type {any} */ item) => item.type === "group",
    );
  }
  /** Split flat digits into per-group strings.
   * @param {any} digits
   * @returns {any}
   */
  groupValuesFromDigits(digits) {
    let offset = 0;
    return this.groupItems().map((/** @type {any} */ group) => {
      const width = Number(group.digits);
      const value = digits.slice(offset, offset + width);
      offset += width;
      return value.padEnd(width, "-");
    });
  }
  /** Normalise per-group values into digit strings.
   * @param {any} values
   * @returns {any}
   * @throws {TypeError}
   */
  normalizeGroupValues(values) {
    const groups = this.groupItems();
    if (!Array.isArray(values) || values.length !== groups.length)
      throw new TypeError(
        `groupValues must contain exactly ${groups.length} values`,
      );
    return values.map((/** @type {any} */ value, /** @type {any} */ index) => {
      const width = Number(groups[index].digits);
      const stringValue = String(value);
      if (!new RegExp(`^\\d{${width}}$`).test(stringValue))
        throw new TypeError(
          `group ${index + 1} must contain exactly ${width} digits`,
        );
      return stringValue;
    });
  }
  /** Total digit count across all groups.
   * @returns {any}
   */
  digitCount() {
    return this.normalizedStructure().reduce(
      (/** @type {any} */ total, /** @type {any} */ item) =>
        total + (item.type === "group" ? Number(item.digits) : 0),
      0,
    );
  }
  /** Separator and marker entries in the structure.
   * @returns {any}
   */
  markerItems() {
    return this.normalizedStructure().filter(
      (/** @type {any} */ item) => item.type === "marker",
    );
  }
  /** Template split into digit groups and separators.
   * @returns {any}
   */
  templateTokens() {
    return this.normalizedStructure().flatMap((/** @type {any} */ item) => {
      if (item.type === "group")
        return Array.from(
          {
            length: Number(item.digits),
          },
          () => "d",
        );
      return [String(item.symbol)];
    });
  }
  /** Lay out the seven-segment digits in the clock element.
   * @returns {any}
   */
  buildSegments() {
    this.normalizedStructure().forEach(
      (/** @type {any} */ item, /** @type {any} */ itemIndex) => {
        if (item.type === "group") {
          const group = document.createElement("div");
          group.className = "sst-group";
          group.style.setProperty(
            "column-gap",
            `${Number(item.digitGap ?? this.#settings.digitGap)}px`,
          );
          group.style.setProperty(
            "--sst-on",
            this.#settings.structure
              ? String(item.color ?? this.#settings.segmentOnColor)
              : this.cssValue("segmentOnColor"),
          );
          group.style.setProperty(
            "--sst-off",
            this.#settings.structure
              ? String(item.offColor ?? this.#settings.segmentOffColor)
              : this.cssValue("segmentOffColor"),
          );
          group.style.setProperty(
            "--sst-glow",
            String(item.glowColor ?? this.#settings.segmentGlowColor),
          );
          group.style.setProperty(
            "--sst-segment-glow",
            `0 0 ${Number(item.glowSize ?? this.#settings.segmentGlowSize)}px ${String(item.glowColor ?? this.#settings.segmentGlowColor)}`,
          );
          group.style.setProperty(
            "--sst-on-time",
            this.#settings.structure
              ? `${Number(item.onDuration ?? this.#settings.segmentOnDuration)}ms`
              : this.cssValue("segmentOnDuration", "ms"),
          );
          group.style.setProperty(
            "--sst-off-time",
            this.#settings.structure
              ? `${Number(item.offDuration ?? this.#settings.segmentOffDuration)}ms`
              : this.cssValue("segmentOffDuration", "ms"),
          );
          group.style.setProperty(
            "--sst-ease",
            String(item.easing ?? this.#settings.transitionEasing),
          );
          Array.from(
            {
              length: Number(item.digits),
            },
            () => {
              const digit = this.createDigit();
              digit.setAttribute("data-group-index", String(String(itemIndex)));
              group.append(digit);
              return digit;
            },
          );
          this.clock.append(group);
          return;
        }
        const marker = this.createMarker(item, itemIndex);
        this.clock.append(marker);
      },
    );
  }
  /** Create one separator or custom-marker element.
   * @param {any} item
   * @param {any} itemIndex
   * @returns {any}
   */
  createMarker(item, itemIndex) {
    const marker = document.createElement("span");
    marker.className = "sst-custom-marker";
    marker.setAttribute("data-marker-index", String(String(itemIndex)));
    marker.setAttribute(
      "data-blink",
      String(item.blink === false ? "false" : "true"),
    );
    marker.textContent = String(item.symbol);
    const size = Number(item.size ?? this.#settings.dotSize);
    marker.style.setProperty("--marker-size", `${size}px`);
    marker.style.setProperty(
      "--marker-color",
      this.#settings.structure
        ? String(item.color ?? this.#settings.segmentOnColor)
        : this.cssValue("segmentOnColor"),
    );
    marker.style.setProperty(
      "--marker-off",
      String(item.offColor ?? this.#settings.segmentOffColor),
    );
    marker.style.setProperty(
      "--marker-glow-color",
      String(item.glowColor ?? item.color ?? this.#settings.segmentGlowColor),
    );
    marker.style.setProperty(
      "--marker-glow-size",
      `${Number(item.glowSize ?? 0)}px`,
    );
    marker.style.setProperty(
      "--marker-before",
      `${Number(item.gapBefore ?? 0)}px`,
    );
    marker.style.setProperty(
      "--marker-after",
      `${Number(item.gapAfter ?? 0)}px`,
    );
    return marker;
  }
  /** Build the dot-matrix DOM and its dots.
   */
  buildMatrix() {
    const matrix = document.createElement("div");
    matrix.className = "sst-matrix";
    matrix.setAttribute("data-layout", String(this.#settings.matrixLayout));
    this.matrix = matrix;
    this.clock.append(matrix);
    this.rebuildMatrixDots();
  }
  /** Re-create matrix dots after the layout changes.
   */
  rebuildMatrixDots() {
    if (!this.matrix) return;
    this.matrix.replaceChildren();
    this.matrixDots = [];
    const { rows, columns } = this.matrixPhysicalSize();
    this.matrixPhysicalRows = rows;
    this.matrixPhysicalColumns = columns;
    this.setInstanceVariable("--sst-matrix-physical-cols", String(columns));
    this.setInstanceVariable("--sst-matrix-physical-rows", String(rows));
    this.matrixDots = Array.from(
      {
        length: rows * columns,
      },
      () =>
        Object.assign(document.createElement("span"), {
          className: "sst-matrix-dot",
        }),
    );
    this.matrix.append(...this.matrixDots);
  }
  /** Pixel size of the physical dot grid.
   * @returns {any}
   */
  matrixPhysicalSize() {
    const logicalColumns = this.matrixTemplateWidth();
    const logicalRows = this.#settings.matrixRows;
    if (this.#settings.matrixLayout !== "target")
      return {
        rows: logicalRows,
        columns: logicalColumns,
      };
    const width = Math.max(0, this.root.clientWidth);
    const height = Math.max(0, this.root.clientHeight);
    const pitch = this.#settings.matrixDotSize + this.#settings.matrixDotGap;
    const fittedColumns = Math.max(
      logicalColumns,
      Math.floor((width + this.#settings.matrixDotGap) / pitch),
    );
    const fittedRows = Math.max(
      logicalRows,
      Math.floor((height + this.#settings.matrixDotGap) / pitch),
    );
    const columns =
      fittedColumns > logicalColumns && fittedColumns % 2 !== logicalColumns % 2
        ? fittedColumns - 1
        : fittedColumns;
    const rows =
      fittedRows > logicalRows && fittedRows % 2 !== logicalRows % 2
        ? fittedRows - 1
        : fittedRows;
    return {
      rows,
      columns,
    };
  }
  /** Gap column count covering a pixel width.
   * @param {any} pixels
   * @returns {any}
   */
  matrixGapColumns(pixels) {
    const pitch = this.#settings.matrixDotSize + this.#settings.matrixDotGap;
    return Math.max(0, Math.round(Number(pixels ?? 0) / pitch));
  }
  /** Logical matrix width implied by the template.
   * @returns {any}
   */
  matrixTemplateWidth() {
    return this.normalizedStructure().reduce(
      (/** @type {any} */ width, /** @type {any} */ item) => {
        if (item.type === "group") {
          const digits = Number(item.digits);
          const digitGapColumns = this.matrixGapColumns(
            item.digitGap ?? this.#settings.digitGap,
          );
          const columns = Number(
            item.matrixColumns ?? this.#settings.matrixColumns,
          );
          return (
            width + digits * columns + Math.max(0, digits - 1) * digitGapColumns
          );
        }
        return (
          width +
          this.matrixGapColumns(item.gapBefore) +
          1 +
          this.matrixGapColumns(item.gapAfter)
        );
      },
      0,
    );
  }
  static matrixGlyph = (/** @type {any} */ char) => {
    /** @type {Record<string,string[]>} */
    const glyphs = {
      0: ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
      1: ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
      2: ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
      3: ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
      4: ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
      5: ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
      6: ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
      7: ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
      8: ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
      9: ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
      "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    };
    return glyphs[char] ?? glyphs["-"] ?? ["00000"];
  };
  /** Current value as per-group digit strings, or undefined when live.
   * @returns {any}
   */
  get value() {
    return this.#settings.groupValues
      ? [...this.#settings.groupValues]
      : undefined;
  }
  /** Set the clock to an explicit value and stop the live loop.
   * @param {any} value Timecode string or per-group digit strings.
   * @throws {TypeError} When value does not fill every configured digit.
   */
  set value(value) {
    this.assertActive();
    if (value === undefined || value === null || value === "") {
      this.#settings.live = false;
      this.#settings.groupValues = undefined;
      this.#settings.value = undefined;
      this.renderValue(undefined);
      cancelAnimationFrame(this.frameRequest ?? 0);
      this.frameRequest = undefined;
      this.#timeMilliseconds = null;
      return;
    }
    const digits = Array.isArray(value)
      ? this.normalizeGroupValues(value).join("")
      : String(value).replace(/\D/g, "");
    if (
      !Array.isArray(value) &&
        (typeof value !== "string" || !/^[\d:.]+$/.test(value)) ||
      digits.length !== this.digitCount() ||
      !/^\d+$/.test(digits)
    )
      throw new TypeError(
        `value must provide exactly ${this.digitCount()} digits`,
      );
    const previous = this.#settings.groupValues?.join("");
    const groups = this.groupValuesFromDigits(digits);
    this.#settings.live = false;
    cancelAnimationFrame(this.frameRequest ?? 0);
    this.frameRequest = undefined;
    this.#timeMilliseconds = null;
    this.#settings.groupValues = groups;
    this.#settings.value = digits;
    if (previous !== undefined && previous !== digits) this.blink();
    this.renderValue(digits);
  }
  /** Per-group digit strings for the current value.
   * @returns {any}
   */
  get groupValues() {
    return this.#settings.groupValues
      ? [...this.#settings.groupValues]
      : undefined;
  }
  /** Set the value one digit group at a time.
   * @param {any} values Per-group digit strings.
   */
  set groupValues(values) {
    this.value = values;
  }
  /** Whether the clock advances on its own animation-frame loop.
   * @returns {any}
   */
  get live() {
    return this.#settings.live;
  }
  /** Start or stop the live playback loop.
   * @param {any} value Whether the clock ticks by itself.
   */
  set live(value) {
    this.set({
      live: value,
    });
  }
  /** Gap between digits within a group.
   * @returns {any}
   */
  get digitGap() {
    return this.#settings.digitGap;
  }
  /** Set the gap between digits within a group.
   * @param {any} value Gap in pixels or a CSS variable name.
   */
  set digitGap(value) {
    this.set({
      digitGap: value,
    });
  }
  /** Gap between digit groups.
   * @returns {any}
   */
  get groupGap() {
    return this.#settings.groupGap;
  }
  /** Set the gap between digit groups.
   * @param {any} value Gap in pixels or a CSS variable name.
   */
  set groupGap(value) {
    this.set({
      groupGap: value,
    });
  }
  /** Gap between segments inside a digit.
   * @returns {any}
   */
  get segmentGap() {
    return this.#settings.segmentGap;
  }
  /** Set the gap between segments inside a digit.
   * @param {any} value Gap in pixels or a CSS variable name.
   */
  set segmentGap(value) {
    this.set({
      segmentGap: value,
    });
  }
  /** Whether the recording indicator pulses while the clock runs.
   * @returns {any}
   */
  get recording() {
    return this.#settings.recording;
  }
  /** Turn the recording indicator on or off.
   * @param {any} value Whether the indicator is active.
   */
  set recording(value) {
    this.set({
      recording: value,
    });
  }
  /** Record-indicator visibility: visible, reserved or hidden.
   * @returns {any}
   */
  get recVisible() {
    return this.#settings.recVisible;
  }
  /** Choose whether the indicator shows, reserves space or hides.
   * @param {any} value One of "visible", "reserved" or "hidden".
   * @throws {TypeError} When value is not one of the three modes.
   */
  set recVisible(value) {
    if (!["visible", "reserved", "hidden"].includes(value))
      throw new TypeError("recVisible must be visible, reserved, or hidden");
    this.set({
      recVisible: value,
    });
  }
  /** Whether the clock has been torn down.
   * @returns {boolean}
   */
  get destroyed() {
    return this.#destroyed;
  }
  /** Current timeline position in milliseconds.
   * @returns {any}
   */
  get timeMilliseconds() {
    return this.#timeMilliseconds;
  }
  /** Timecode text carried by the aria label.
   * @returns {any}
   */
  get timecode() {
    return this.clock.getAttribute("aria-label");
  }
  /** Paint the matrix for a digit string.
   * @param {any} value
   */
  renderMatrix(value) {
    if (!this.matrix) return;
    const structure = this.normalizedStructure();
    const logicalRows = this.#settings.matrixRows;
    const logicalColumns = this.matrixTemplateWidth();
    const physicalRows = this.matrixPhysicalRows ?? logicalRows;
    const physicalColumns = this.matrixPhysicalColumns ?? logicalColumns;
    /** @type {any} */
    const logical = Array.from(
      {
        length: logicalRows,
      },
      () =>
        Array.from(
          {
            length: logicalColumns,
          },
          () => false,
        ),
    );
    /** @type {any} */
    const separators = Array.from(
      {
        length: logicalRows,
      },
      () =>
        Array.from(
          {
            length: logicalColumns,
          },
          () => null,
        ),
    );
    /** @type {any} */
    const groupStyles = Array.from(
      {
        length: logicalRows,
      },
      () =>
        Array.from(
          {
            length: logicalColumns,
          },
          () => null,
        ),
    );
    let valueIndex = 0;
    let columnOffset = 0;
    structure.forEach((/** @type {any} */ item) => {
      if (item.type === "group") {
        const digits = Number(item.digits);
        const digitGapColumns = this.matrixGapColumns(
          item.digitGap ?? this.#settings.digitGap,
        );
        for (let digit = 0; digit < digits; digit += 1) {
          const glyph = AnalogClock.matrixGlyph(value[valueIndex] ?? "-");
          valueIndex += 1;
          for (let row = 0; row < logicalRows; row += 1) {
            const source =
              glyph[Math.floor(row * glyph.length / logicalRows)] ?? "00000";
            const groupColumns = Number(
              item.matrixColumns ?? this.#settings.matrixColumns,
            );
            for (let column = 0; column < groupColumns; column += 1) {
              const sourceIndex = Math.min(
                source.length - 1,
                Math.floor(column * source.length / groupColumns),
              );
              const active = source[sourceIndex] === "1";
              logical[row][columnOffset + column] = active;
              if (active) groupStyles[row][columnOffset + column] = item;
            }
          }
          columnOffset += Number(
            item.matrixColumns ?? this.#settings.matrixColumns,
          );
          if (digit < digits - 1) columnOffset += digitGapColumns;
        }
        return;
      }
      columnOffset += this.matrixGapColumns(item.gapBefore);
      const symbol = String(item.symbol ?? "");
      for (let row = 0; row < logicalRows; row += 1) {
        const active =
          symbol === ":"
            ? row === Math.floor(logicalRows * 0.3) ||
              row === Math.floor(logicalRows * 0.7)
            : symbol === "."
              ? row === logicalRows - 1
              : row === Math.floor(logicalRows / 2);
        logical[row][columnOffset] = active;
        if (active) separators[row][columnOffset] = item;
      }
      columnOffset += 1;
      columnOffset += this.matrixGapColumns(item.gapAfter);
    });
    this.matrixDots.forEach((/** @type {any} */ dot) => {
      dot.classList.remove("sst-on", "sst-separator-dot");
    });
    const rowStart = Math.floor((physicalRows - logicalRows) / 2);
    const columnStart = Math.floor((physicalColumns - logicalColumns) / 2);
    logical.forEach((/** @type {any} */ row, /** @type {any} */ rowIndex) => {
      row.forEach((/** @type {any} */ on, /** @type {any} */ columnIndex) => {
        const index =
          (rowStart + rowIndex) * physicalColumns + columnStart + columnIndex;
        const dot = this.matrixDots[index];
        if (!dot) return;
        const marker = separators[rowIndex][columnIndex];
        const groupStyle = groupStyles[rowIndex][columnIndex];
        if (marker) {
          dot.classList.add("sst-separator-dot");
          dot.setAttribute(
            "data-blink",
            String(marker.blink === false ? "false" : "true"),
          );
          const markerSize = Math.min(
            this.#settings.matrixDotSize,
            Number(
              marker.matrixSize ?? marker.size ?? this.#settings.matrixDotSize,
            ),
          );
          dot.style.setProperty("inline-size", `${markerSize}px`);
          dot.style.setProperty("min-inline-size", `${markerSize}px`);
          dot.style.setProperty("max-inline-size", `${markerSize}px`);
          dot.style.setProperty("block-size", `${markerSize}px`);
          dot.style.setProperty("min-block-size", `${markerSize}px`);
          dot.style.setProperty("max-block-size", `${markerSize}px`);
          dot.style.background = String(
            marker.matrixColor ?? marker.color ?? this.#settings.matrixOnColor,
          );
          dot.style.boxShadow = `0 0 ${Number(
            marker.matrixGlowSize ?? marker.glowSize ?? 0,
          )}px ${String(marker.matrixGlowColor ?? marker.glowColor ?? marker.matrixColor ?? marker.color ?? this.#settings.matrixOnColor)}`;
        } else if (groupStyle) {
          dot.setAttribute("data-blink", String("false"));
          dot.style.background = String(
            groupStyle.matrixOnColor ??
              groupStyle.color ??
              this.#settings.matrixOnColor,
          );
          dot.style.boxShadow = `0 0 ${Number(
            groupStyle.matrixGlowSize ??
              groupStyle.glowSize ??
              this.#settings.matrixGlowSize,
          )}px ${String(groupStyle.matrixGlowColor ?? groupStyle.glowColor ?? groupStyle.matrixOnColor ?? groupStyle.color ?? this.#settings.matrixOnColor)}`;
        } else {
          dot.setAttribute("data-blink", String("false"));
          [
            "inline-size",
            "min-inline-size",
            "max-inline-size",
            "block-size",
            "min-block-size",
            "max-block-size",
            "background",
            "box-shadow",
          ].forEach((/** @type {any} */ property) => {
            dot.style.removeProperty(property);
          });
        }
        if (on) dot.classList.add("sst-on");
      });
    });
  }
  /** Create one seven-segment digit element.
   * @returns {any}
   */
  createDigit() {
    const svg = AnalogClock.svg("svg");
    svg.classList.add("sst-digit");
    svg.setAttribute("viewBox", "0 0 94 192");
    svg.setAttribute("aria-hidden", "true");
    const segments = new Map();
    ["a", "b", "c", "d", "e", "f", "g"].forEach((/** @type {any} */ name) => {
      const segment = AnalogClock.svg("polygon");
      segment.classList.add("sst-segment");
      svg.append(segment);
      segments.set(name, segment);
    });
    this.digits.push(segments);
    return svg;
  }
  /** Create one separator element of a given kind.
   * @param {any} kind
   * @returns {any}
   */
  createSeparator(kind) {
    const svg = AnalogClock.svg("svg");
    svg.classList.add(
      "sst-separator",
      `sst-separator-${kind === ":" ? "colon" : "decimal"}`,
    );
    svg.setAttribute("data-separator", String(kind));
    svg.setAttribute("viewBox", "0 0 24 192");
    svg.setAttribute("aria-hidden", "true");
    /** @type {SVGElement[]} */
    const dots = [];
    Array.from(
      {
        length: kind === ":" ? 2 : 1,
      },
      () => {
        const dot = AnalogClock.svg("circle");
        dot.classList.add("sst-dot");
        svg.append(dot);
        dots.push(dot);
        return dot;
      },
    );
    this.separators.push({
      kind,
      dots,
    });
    return svg;
  }
  /** Apply validated settings and rebuild what changed.
   * @param {any} settings
   * @param {any} preserveBindings
   * @returns {any}
   */
  applySettings(settings = undefined, preserveBindings = false) {
    this.assertActive();
    const supplied = settings;
    if (settings !== undefined) {
      AnalogClock.validateSettings(settings);
      settings = this.resolveSettings(settings);
      AnalogClock.validateSettings({
        ...this.#settings,
        ...settings,
      });
    }
    if (supplied && !preserveBindings)
      Object.entries(supplied).forEach((/** @type {any} */ [name, value]) => {
        if (value === undefined) return;
        if (AnalogClock.isCssVariable(value)) this.#bindings.set(name, value);
        else this.#bindings.delete(name);
      });
    const previous = {
      mode: this.#settings.mode,
      template: this.#settings.template,
      matrixLayout: this.#settings.matrixLayout,
      matrixRows: this.#settings.matrixRows,
      matrixColumns: this.#settings.matrixColumns,
      structure: this.#settings.structure,
    };
    if (settings)
      Object.entries(settings).forEach((/** @type {any} */ [name, value]) => {
        if (value !== undefined)
          this.#settings[name] =
            name === "structure" && value !== null
              ? structuredClone(value)
              : value;
      });
    const s = this.#settings;
    this.root.setAttribute("data-mode", String(s.mode));
    this.root.setAttribute("data-matrix-layout", String(s.matrixLayout));
    const rebuild =
      previous.mode !== s.mode ||
      previous.template !== s.template ||
      previous.matrixLayout !== s.matrixLayout ||
      previous.matrixRows !== s.matrixRows ||
      previous.matrixColumns !== s.matrixColumns ||
      previous.structure !== s.structure ||
      Object.keys(settings ?? {}).some((/** @type {any} */ name) =>
        /^(segment|digit|group|transition|dot|matrix)/.test(name),
      );
    const vars = {
      "--sst-matrix-cols": String(s.matrixColumns),
      "--sst-matrix-rows": String(s.matrixRows),
      "--sst-matrix-physical-cols": String(this.matrixTemplateWidth()),
      "--sst-matrix-physical-rows": String(s.matrixRows),
      "--sst-matrix-dot": `${s.matrixDotSize}px`,
      "--sst-matrix-gap": `${s.matrixDotGap}px`,
      "--sst-matrix-on": s.matrixOnColor,
      "--sst-matrix-off": s.matrixOffColor,
      "--sst-matrix-glow-size": `${s.matrixGlowSize}px`,
      "--sst-matrix-glow": `0 0 ${s.matrixGlowSize}px ${s.matrixOnColor}`,
      "--sst-digit-gap": `${s.digitGap}px`,
      "--sst-group-gap": `${s.groupGap}px`,
      "--sst-separator-width": `${s.separatorWidth}px`,
      "--sst-on": s.segmentOnColor,
      "--sst-off": s.segmentOffColor,
      "--sst-glow": s.segmentGlowColor,
      "--sst-glow-size": `${s.segmentGlowSize}px`,
      "--sst-segment-glow": `0 0 ${s.segmentGlowSize}px ${s.segmentGlowColor}`,
      "--sst-on-time": `${s.segmentOnDuration}ms`,
      "--sst-off-time": `${s.segmentOffDuration}ms`,
      "--sst-ease": s.transitionEasing,
      "--sst-dot-time": `${s.dotBlinkDuration}ms`,
      "--sst-rec-size": `${s.recLedSize}px`,
      "--sst-rec-on": s.recLedOnColor,
      "--sst-rec-off": s.recLedOffColor,
      "--sst-rec-glow": s.recLedGlowColor,
      "--sst-rec-glow-size": `${s.recLedGlowSize}px`,
      "--sst-rec-glow-effect": `0 0 ${s.recLedGlowSize}px ${s.recLedGlowColor}`,
      "--sst-rec-pulse": `${s.recPulseDuration}ms`,
      "--sst-rec-font": s.recFontFamily,
      "--sst-rec-font-size": `${s.recFontSize}px`,
      "--sst-rec-weight": String(s.recFontWeight),
      "--sst-rec-spacing": `${s.recLetterSpacing}px`,
      "--sst-rec-text": s.recTextColor,
      "--sst-rec-gap": `${s.recGap}px`,
      "--sst-widget-gap": `${s.recWidgetGap}px`,
      "--sst-bg": s.background,
      "--sst-padding": `${s.padding}px`,
      "--sst-scale": "1",
      "--sst-digit-width": `${s.segmentLength + s.segmentGap + s.segmentThickness}px`,
    };
    AnalogClock.#instances.set(this.id, {
      ...vars,
      "--sst-align": s.align,
    });
    this.#bindings.forEach(
      (/** @type {any} */ _variable, /** @type {any} */ name) => {
        const cssSetting = AnalogClock.CSS_SETTINGS[name];
        if (cssSetting)
          AnalogClock.#instances.get(this.id)[cssSetting[0]] = this.cssValue(
            name,
            cssSetting[1],
          );
      },
    );
    AnalogClock.refreshInstanceStyles();
    this.rec.setAttribute("data-visibility", String(s.recVisible));
    this.recLabel.textContent = s.recLabel;
    this.rec.classList.toggle("sst-enabled", s.recEnabled);
    this.rec.classList.toggle("sst-recording", s.recEnabled && s.recording);
    this.rec.classList.toggle(
      "sst-pulse",
      s.recEnabled && s.recording && s.recPulse,
    );
    if (rebuild) {
      if (this.#settings.value?.length !== this.digitCount()) {
        this.#settings.groupValues = undefined;
        this.#settings.value = undefined;
        this.#timeMilliseconds = null;
      } else
        this.#settings.groupValues = this.groupValuesFromDigits(
          this.#settings.value,
        );
      this.rebuildRenderer();
    }
    this.updateGeometry();
    this.renderValue(this.#settings.groupValues);
    cancelAnimationFrame(this.#fitRequest ?? 0);
    this.#fitRequest = requestAnimationFrame(() => {
      this.#fitRequest = undefined;
      if (!this.#destroyed) this.fit();
    });
    if (s.live && this.frameRequest === undefined) this.tick();
    if (!s.live) {
      cancelAnimationFrame(this.frameRequest ?? 0);
      this.frameRequest = undefined;
    }
    if (
      !preserveBindings &&
      this.#bindingRequest === undefined &&
      [...this.#bindings.keys()].some(
        (/** @type {any} */ name) =>
          !Object.hasOwn(AnalogClock.CSS_SETTINGS, name),
      )
    )
      this.#bindingRequest = requestAnimationFrame(() => this.watchBindings());
    return this;
  }
  /** Recompute sizes after layout-affecting changes.
   */
  updateGeometry() {
    const s = this.#settings;
    if (s.mode === "matrix") {
      if (this.matrix) {
        this.matrix.setAttribute("data-layout", String(s.matrixLayout));
        this.setInstanceVariable(
          "--sst-matrix-cols",
          String(this.matrixTemplateWidth()),
        );
        this.setInstanceVariable("--sst-matrix-rows", String(s.matrixRows));
        this.rebuildMatrixDots();
      }
      return;
    }
    const structure = this.normalizedStructure();
    this.digits.forEach((/** @type {any} */ segments) => {
      const svg = segments.values().next().value.ownerSVGElement;
      const item = structure[Number(svg.getAttribute("data-group-index"))];
      const length = item.segmentLength ?? s.segmentLength;
      const thickness = item.segmentThickness ?? s.segmentThickness;
      const gap = item.segmentGap ?? s.segmentGap;
      const halfLength = length / 2;
      const halfThickness = thickness / 2;
      const bevel = Math.min(halfThickness, length / 5);
      const points = [
        [-halfLength + bevel, -halfThickness],
        [halfLength - bevel, -halfThickness],
        [halfLength, 0],
        [halfLength - bevel, halfThickness],
        [-halfLength + bevel, halfThickness],
        [-halfLength, 0],
      ]
        .map((/** @type {any} */ point) => point.join(","))
        .join(" ");
      const digitWidth = length + gap + thickness;
      const center = digitWidth / 2;
      const left = halfThickness;
      const right = digitWidth - halfThickness;
      const top = Number(s.digitInset ?? 14) + halfThickness;
      const middle = 96;
      const bottom = 192 - Number(s.digitInset ?? 14) - halfThickness;
      const upper = (top + middle) / 2;
      const lower = (middle + bottom) / 2;
      /** @type {Record<string,number[]>} */
      const positions = {
        a: [center, top, 0],
        b: [right, upper, 90],
        c: [right, lower, 90],
        d: [center, bottom, 0],
        e: [left, lower, 90],
        f: [left, upper, 90],
        g: [center, middle, 0],
      };
      svg.style.inlineSize = `${item.digitWidth ?? digitWidth}px`;
      svg.style.blockSize = `${item.digitHeight ?? 192}px`;
      segments.forEach(
        (/** @type {any} */ segment, /** @type {any} */ name) => {
          const [x, y, angle] = positions[name] ?? [0, 0, 0];
          svg.setAttribute("viewBox", `0 0 ${digitWidth} 192`);
          segment.setAttribute("points", points);
          segment.setAttribute(
            "transform",
            `translate(${x} ${y}) rotate(${angle})`,
          );
        },
      );
    });
    this.separators.forEach((/** @type {any} */ separator) => {
      const ys = separator.kind === ":" ? [66, 126] : [178 - s.dotSize / 2];
      separator.dots.forEach(
        (/** @type {any} */ dot, /** @type {any} */ index) => {
          dot.setAttribute("cx", "12");
          dot.setAttribute("cy", String(ys[index]));
          dot.setAttribute("r", String(s.dotSize / 2));
        },
      );
    });
  }
  /** Scale the widget so it fits its container.
   */
  fit() {
    this.setInstanceVariable("--sst-scale", "1");
    if (this.#settings.mode === "matrix") return;
    const availableWidth = Math.max(
      0,
      this.root.clientWidth - this.#settings.padding * 2,
    );
    const availableHeight = Math.max(
      0,
      this.root.clientHeight - this.#settings.padding * 2,
    );
    const naturalWidth =
      this.clock.offsetWidth +
      (this.rec.getAttribute("data-visibility") === "hidden"
        ? 0
        : this.#settings.recWidgetGap + this.rec.offsetWidth);
    const naturalHeight = Math.max(
      this.clock.offsetHeight,
      this.rec.getAttribute("data-visibility") === "hidden"
        ? 0
        : this.rec.offsetHeight,
    );
    if (naturalHeight > 0)
      this.target.style.setProperty(
        "--dynamic-analog-clock-aspect",
        String(naturalWidth / naturalHeight),
      );
    const scale =
      naturalWidth > 0 && naturalHeight > 0
        ? Math.min(
            availableWidth / naturalWidth,
            availableHeight / naturalHeight,
          )
        : 1;
    this.setInstanceVariable("--sst-scale", String(Math.max(0, scale)));
  }
  /** Set one per-instance CSS variable.
   * @param {any} name
   * @param {any} value
   */
  setInstanceVariable(name, value) {
    const variables = AnalogClock.#instances.get(this.id) ?? {};
    variables[name] = value;
    AnalogClock.#instances.set(this.id, variables);
    AnalogClock.refreshInstanceStyles();
  }
  /** Set one digit group by index.
   * @param {any} index
   * @param {any} value
   * @returns {any}
   * @throws {RangeError}
   * @throws {TypeError}
   */
  setGroupValue(index, value) {
    const groups = this.groupItems();
    if (!Number.isInteger(index) || index < 0 || index >= groups.length)
      throw new RangeError("group index is outside the configured structure");
    const current = this.#settings.groupValues
      ? [...this.#settings.groupValues]
      : groups.map((/** @type {any} */ group) =>
          "0".repeat(Number(group.digits)),
        );
    const width = Number(groups[index].digits);
    const stringValue = String(value);
    if (!new RegExp(`^\\d{${width}}$`).test(stringValue))
      throw new TypeError(
        `group ${index + 1} must contain exactly ${width} digits`,
      );
    current[index] = stringValue;
    this.value = current;
    return this;
  }
  /** Validate and apply a settings update.
   * @param {any} settings
   * @returns {any}
   * @throws {TypeError}
   */
  set(settings) {
    this.assertActive();
    AnalogClock.validateSettings(settings);
    const value = settings.groupValues ?? settings.value;
    if (value !== undefined && value !== null && !this.validValue(value))
      throw new TypeError("value does not match the configured digit groups");
    if (
      Object.hasOwn(settings, "structure") &&
      (Object.hasOwn(settings, "value") ||
        Object.hasOwn(settings, "groupValues"))
    )
      throw new TypeError("configure structure before setting its value");
    const options = {
      ...settings,
    };
    delete options.value;
    delete options.groupValues;
    this.applySettings(options);
    if (
      Object.hasOwn(settings, "value") ||
      Object.hasOwn(settings, "groupValues")
    )
      this.value = value;
    return this;
  }
  /** Defensive configuration snapshot for persistence/integration.
   * @returns {any}
   */
  getSettings() {
    return {
      ...structuredClone(this.#settings),
      ...Object.fromEntries(this.#bindings),
    };
  }
  /** Externally driven timeline position. Does not start a playback timer.
   * @param {number} milliseconds
   * @returns {any}
   * @throws {Error}
   */
  setTime(milliseconds) {
    this.assertActive();
    const widths = this.groupItems().map(
      (/** @type {{digits:number}} */ group) => group.digits,
    );
    if (
      widths.length !== 4 ||
      widths.slice(0, 3).some((/** @type {number} */ width) => width !== 2) ||
      ![2, 3].includes(widths[3] ?? 0)
    )
      throw new Error(
        "timeline time requires HH:MM:SS with two frame digits or three millisecond digits",
      );
    this.value = AnalogClock.formatTime(milliseconds, {
      fps: this.#settings.fps,
      precision: widths[3] === 3 ? "milliseconds" : "frames",
    }).split(/[.:]/);
    this.#timeMilliseconds = milliseconds;
    return this;
  }
  /** Set the timeline to a frame number.
   * @param {any} frame
   * @returns {any}
   * @throws {Error}
   */
  setFrame(frame) {
    this.assertActive();
    const timecode = AnalogClock.formatFrame(frame, {
      fps: this.#settings.fps,
    });
    if (
      this.groupItems().length !== 4 ||
      this.groupItems().some((/** @type {any} */ group) => group.digits !== 2)
    )
      throw new Error("timeline time requires four two-digit groups");
    this.value = timecode.split(/[.:]/);
    this.#timeMilliseconds = frame * 1000 / this.#settings.fps;
    return this;
  }
  /** Clear the shown value and return to live mode.
   * @returns {any}
   */
  clear() {
    this.value = undefined;
    return this;
  }
  /** Resume the live playback loop.
   * @returns {any}
   */
  resume() {
    this.#timeMilliseconds = null;
    return this.set({
      live: true,
    });
  }
  /** Blink the separators once.
   */
  blink() {
    this.assertActive();
    if (!this.#settings.blinkSeparatorsOnSecond) return;
    this.clock.classList.add("sst-blink");
    clearTimeout(this.blinkTimer);
    this.blinkTimer = setTimeout(
      () => this.clock.classList.remove("sst-blink"),
      this.#settings.dotBlinkDuration,
    );
  }
  /** Advance the live clock by one animation frame.
   */
  tick() {
    if (this.#destroyed || !this.#settings.live) return;
    if (this.#settings.live) {
      const now = new Date();
      const second = now.getSeconds();
      const frame = Math.min(
        this.#settings.fps - 1,
        Math.floor(now.getMilliseconds() * this.#settings.fps / 1000),
      );
      if (this.lastSecond !== undefined && second !== this.lastSecond)
        this.blink();
      this.lastSecond = second;
      const liveDigits = `${AnalogClock.two(now.getHours())}${AnalogClock.two(now.getMinutes())}${AnalogClock.two(second)}${AnalogClock.two(frame)}`;
      const digits = liveDigits
        .padEnd(this.digitCount(), "0")
        .slice(0, this.digitCount());
      this.#settings.groupValues = this.groupValuesFromDigits(digits);
      this.#settings.value = digits;
      this.renderValue(digits);
    }
    this.frameRequest = requestAnimationFrame(() => this.tick());
  }
  /** Render a digit string through the active renderer.
   * @param {any} value
   * @returns {any}
   */
  renderValue(value) {
    const digitCount = this.digitCount();
    const rawDigits = Array.isArray(value)
      ? value.join("")
      : value
        ? String(value).replace(/\D/g, "")
        : this.#settings.groupValues
          ? this.#settings.groupValues.join("")
          : "-".repeat(digitCount);
    const digits = rawDigits.padEnd(digitCount, "-").slice(0, digitCount);
    let digitIndex = 0;
    const display = this.templateTokens()
      .map((/** @type {any} */ token) => {
        if (token !== "d") return token;
        return digits[digitIndex++] ?? "-";
      })
      .join("");
    this.clock.setAttribute("aria-label", display);
    if (this.#settings.mode === "matrix") this.renderMatrix(digits);
    else if (digits !== this.lastDigits) {
      this.digits.forEach(
        (/** @type {any} */ segments, /** @type {any} */ index) => {
          const active = AnalogClock.DIGITS[digits[index]] ?? "";
          segments.forEach(
            (/** @type {any} */ segment, /** @type {any} */ name) => {
              segment.classList.toggle("sst-on", active.includes(name));
            },
          );
        },
      );
      this.lastDigits = digits;
    }
  }
  /** Tear down observers, timers and the rendered DOM.
   */
  destroy() {
    if (this.#destroyed) return;
    this.#destroyed = true;
    cancelAnimationFrame(this.frameRequest ?? 0);
    cancelAnimationFrame(this.#fitRequest ?? 0);
    cancelAnimationFrame(this.#bindingRequest ?? 0);
    clearTimeout(this.blinkTimer);
    this.observer.disconnect();
    this.root.remove();
    this.target.removeAttribute("data-seven-segment");
    AnalogClock.#instances.delete(this.id);
    AnalogClock.refreshInstanceStyles();
  }
  static svg = (/** @type {string} */ name) =>
    /** @type {SVGElement} */ (document.createElementNS(AnalogClock.NS, name));
  static two = (/** @type {any} */ value) => String(value).padStart(2, "0");
  /** Whether a value fills every configured digit group.
   * @param {any} value
   * @returns {any}
   */
  validValue(value) {
    try {
      if (Array.isArray(value))
        return this.normalizeGroupValues(value).length > 0;
      return (
        typeof value === "string" &&
        /^[\d:.]+$/.test(value) &&
        value.replace(/\D/g, "").length === this.digitCount()
      );
    } catch {
      return false;
    }
  }
}
Object.assign(globalThis, {
  AnalogClock,
});
