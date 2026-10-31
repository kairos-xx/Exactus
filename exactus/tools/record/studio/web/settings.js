/** Settings: browser profiles and project recovery, rendered from the backend's field catalog.
 *
 * Every control comes from `snapshot.profile_schema`, the same description the
 * backend validates against, so a profile can only be edited in ways the test
 * browser can honour.
 */
/** @typedef {{id:string,label:string,kind:string,unit?:string,min?:number,max?:number,step?:number,options?:string[],optional?:boolean,group?:string,media?:string,derived_from?:string[]}} ProfileField */
/** @typedef {{fields:ProfileField[],unsupported:string[]}} ProfileSchema */
/** @typedef {{id:string,name:string,width:number,height:number,scale:number,screen_width:number|null,screen_height:number|null,touch:boolean,mobile:boolean,media:Record<string,string>}} Profile */
/** @typedef {{profile_schema?:ProfileSchema,device_mode?:string,dirty?:boolean,target_service?:ServiceState,target_check?:TargetCheck,target_suggestion?:Target|null,workspace?:{profiles?:Profile[],target?:Target,flows?:Array<{name:string,device_modes?:string[]}>}}} SettingsSnapshot */
/** @typedef {Record<string,string> & {name?:string,width?:string,height?:string,scale?:string,screen_width?:string,screen_height?:string}} Issues */
/** @typedef {{mode:"url"|"service",url:string,port:number|null,command:string[],cwd:string,service_port:number|null,path:string}} Target */
/** @typedef {{state:string,url?:string,port?:number,pid?:number,error?:string,command?:string[],candidates?:Array<{url:string,port:number,status:number}>}} ServiceState */
/** @typedef {{state:string,url?:string,status?:number|null,reason?:string|null,error?:string,process?:{pid:number,name:string}|null}|null} TargetCheck */
import {
  ACTION_GROUPS,
  loadActionPrefs,
  saveActionPrefs,
} from "./action-library.js";
/** Greatest common divisor of two positive integers.
 * @param {number} a
 * @param {number} b
 * @returns {number}
 */
export const gcd = (a, b) => b === 0 ? a : gcd(b, a % b);
/** Reduce a width and height to the smallest whole-number ratio.
 * @param {number} width
 * @param {number} height
 * @returns {[number,number]} Numerator and denominator, or 1:1 for invalid input.
 */
export const reduceRatio = (width, height) => {
  if (!Number.isInteger(width) || !Number.isInteger(height)) return [1, 1];
  if (width < 1 || height < 1) return [1, 1];
  const divisor = gcd(width, height);
  return [width / divisor, height / divisor];
};
/** Height that gives `width` the requested ratio.
 * @param {number} width
 * @param {number} numerator
 * @param {number} denominator
 * @returns {number} Rounded CSS pixels; 0 when the ratio is not positive.
 */
export const heightForRatio = (width, numerator, denominator) =>
  numerator > 0 && denominator > 0
    ? Math.round(width * denominator / numerator)
    : 0;
/** Derive a stable profile ID from a display name.
 * @param {string} name
 * @param {Iterable<string>} taken IDs already in use.
 * @returns {string} Lowercase ID that is not in `taken`.
 */
export const slugify = (name, taken) => {
  const used = new Set(taken);
  const base =
    name
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 28) || "profile";
  let candidate = base;
  for (let n = 2; used.has(candidate) || candidate === "shared"; n += 1)
    candidate = `${base}-${n}`;
  return candidate;
};
/** Parse text from a numeric input without ever blocking what was typed.
 * @param {string} text
 * @returns {number} NaN when the text is not a number.
 */
export const parseNumber = text =>
  text.trim() === "" ? Number.NaN : Number(text.trim());
/** Check a draft against the field catalog and return one message per bad field.
 * @param {Profile} draft
 * @param {ProfileField[]} fields
 * @returns {Issues} Field ID to message; empty when the draft is valid.
 */
export const issuesFor = (draft, fields) => {
  /** @type {Issues} */
  const issues = {};
  if (draft.name.trim() === "") issues.name = "Give the profile a name.";
  /** @type {Record<string,number|null>} */
  const numbers = {
    width: draft.width,
    height: draft.height,
    scale: draft.scale,
    screen_width: draft.screen_width,
    screen_height: draft.screen_height,
  };
  for (const field of fields) {
    if (!["length", "number"].includes(field.kind)) continue;
    const value = numbers[field.id];
    if (value === null || value === undefined) {
      if (!field.optional)
        issues[field.id] = `Enter the ${field.label.toLowerCase()}.`;
      continue;
    }
    const range = `${field.min ?? ""} to ${field.max ?? ""}${field.unit ? ` ${field.unit}` : ""}`;
    if (!Number.isFinite(value))
      issues[field.id] = `${field.label} must be a number (${range}).`;
    else if (
      (field.min !== undefined && value < field.min) ||
      (field.max !== undefined && value > field.max)
    )
      issues[field.id] = `${field.label} must be ${range}.`;
    else if (field.kind === "length" && !Number.isInteger(value))
      issues[field.id] = `${field.label} must be a whole number of pixels.`;
  }
  // Both device-screen sizes, or neither.
  if ((draft.screen_width === null) !== (draft.screen_height === null))
    issues[draft.screen_width === null ? "screen_width" : "screen_height"] =
      "Set both device width and height, or leave both empty.";
  return issues;
};
/** Short, readable description of what makes a profile different.
 * @param {Profile} profile
 * @returns {string}
 */
export const summary = profile => {
  const parts = [`${profile.width} × ${profile.height}`];
  if (profile.scale !== 1) parts.push(`${profile.scale}×`);
  if (profile.touch) parts.push("touch");
  if (profile.media["prefers-color-scheme"])
    parts.push(profile.media["prefers-color-scheme"]);
  return parts.join(" · ");
};
/** Split a command line into arguments the way a shell would, without running one.
 * @param {string} text
 * @returns {string[]} Arguments; quotes group words and backslash escapes one character.
 * @throws {Error} When a quote is never closed.
 */
export const splitCommand = text => {
  /** @type {string[]} */
  const args = [];
  let current = "";
  let started = false;
  /** @type {string|null} */
  let quote = null;
  for (let index = 0; index < text.length; index += 1) {
    const char = text.charAt(index);
    if (quote) {
      if (char === quote) quote = null;
      else if (char === "\\" && quote === '"' && index + 1 < text.length)
        current += text.charAt(index += 1);
      else current += char;
    } else if (char === '"' || char === "'") {
      quote = char;
      started = true;
    } else if (char === "\\" && index + 1 < text.length) {
      current += text.charAt(index += 1);
      started = true;
    } else if (/\s/.test(char)) {
      if (started) args.push(current);
      current = "";
      started = false;
    } else {
      current += char;
      started = true;
    }
  }
  if (quote) throw new Error("A quote in the command is not closed.");
  if (started) args.push(current);
  return args;
};
/** Write arguments back as one command line that `splitCommand` reads identically.
 * @param {string[]} args
 * @returns {string}
 */
export const joinCommand = args =>
  args
    .map(arg =>
      arg === "" || /[\s"'\\]/.test(arg)
        ? `"${arg.replace(/(["\\])/g, "\\$1")}"`
        : arg,
    )
    .join(" ");
/** Say in a sentence what a probe of the address found.
 * @param {TargetCheck} check
 * @returns {string}
 */
export const describeCheck = check => {
  if (!check) return "";
  const owner = check.process
    ? ` It is served by ${check.process.name} (process ${check.process.pid}).`
    : "";
  switch (check.state) {
    case "reachable":
      return `Reachable. The page answered ${check.status ?? ""} ${check.reason ?? ""}.${owner}`.replace(
        /\s+\./g,
        ".",
      );
    case "open":
      return "Something is listening there (HTTPS is not checked).";
    case "not-http":
      return `Something is listening there, but it does not answer HTTP.${owner}`;
    case "unreachable":
      return "Nothing is listening at that address and port.";
    case "unresolved":
      return check.error ?? "That host name could not be found.";
    case "unset":
      return "No address is set yet.";
    default:
      return "";
  }
};
/** Say in a sentence what the started service is doing.
 * @param {ServiceState|undefined} service
 * @returns {string}
 */
export const describeService = service => {
  switch (service?.state) {
    case "starting":
      return "Starting… waiting for it to serve a page.";
    case "running": {
      const others = (service.candidates ?? []).filter(
        item => item.port !== service.port,
      );
      return `Running at ${service.url ?? ""}${service.pid ? ` (process ${service.pid})` : ""}.${
        others.length
          ? ` Also listening on ${others.map(item => item.port).join(", ")}.`
          : ""
      }`;
    }
    case "failed":
    case "exited":
      return service.error ?? "The service stopped.";
    default:
      return "Not started.";
  }
};
/** Read a port field: empty means "not set"; anything else must be 1 to 65535.
 * @param {string} text
 * @returns {number|null} The port, or null when empty.
 * @throws {Error} When the text is not a valid port.
 */
export const parsePort = text => {
  const value = text.trim();
  if (value === "") return null;
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535)
    throw new Error("A port is a whole number from 1 to 65535.");
  return port;
};
/** Create an element with attributes and children, without parsing HTML.
 * @param {string} tag
 * @param {Record<string,string|boolean>} [attributes]
 * @param {...(Node|string)} children
 * @returns {HTMLElement}
 */
const el = (tag, attributes = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value === false) continue;
    node.setAttribute(name, value === true ? "" : value);
  }
  node.append(...children);
  return node;
};

/** The profile editor and recovery page of the Settings workspace. */
export class SettingsSurface {
  /** @type {string|null} Selected profile ID, or "" for a new profile. */
  selected = null;
  /** @type {Map<string,Profile>} Unsaved drafts keyed by profile ID. */
  drafts = new Map();
  /** @type {Set<string>} Fields the user has left, which may show errors. */
  touched = new Set();
  /** @type {SettingsSnapshot|null} */
  snapshot = null;
  /** @type {Target|null} Unsaved target, or null while the saved one is shown. */
  targetDraft = null;
  /** Whether the draft is the demo suggestion rather than something typed. */
  suggested = false;
  /** What the status line last reported, so a real change can replace a message. */
  targetKey = "";
  /**
   * @param {HTMLElement} root Container the page is drawn into.
   * @param {{call:(name:string,payload:Record<string,unknown>|null)=>Promise<unknown>,apply:(result:unknown)=>void,say:(text:string)=>void,confirm:(copy:{title:string,body:string,keep:string,remove:string})=>Promise<boolean>,projectSection?:()=>HTMLElement|null}} host
   */
  constructor(root, host) {
    this.root = root;
    this.host = host;
  }
  /** Profiles stored in the current workspace.
   * @returns {Profile[]}
   */
  get profiles() {
    return this.snapshot?.workspace?.profiles ?? [];
  }
  /** Field catalog describing each profile setting.
   * @returns {ProfileField[]}
   */
  get fields() {
    return this.snapshot?.profile_schema?.fields ?? [];
  }
  /** Draw the page; keep what the user is typing when a snapshot arrives.
   * @param {SettingsSnapshot} snapshot
   * @returns {void}
   */
  render(snapshot) {
    this.snapshot = snapshot;
    if (this.selected === null || !this.hasProfile(this.selected)) {
      const active = snapshot.device_mode ?? "";
      this.selected = this.hasProfile(active)
        ? active
        : (this.profiles[0]?.id ?? "");
    }
    const saved = snapshot.workspace?.target;
    const unset = !saved || (saved.url === "" && saved.command.length === 0);
    if (!this.targetDraft && unset && snapshot.target_suggestion) {
      this.targetDraft = structuredClone(snapshot.target_suggestion);
      this.suggested = true;
    }
    // A snapshot caused by typing elsewhere must not wipe a half-edited form,
    // but the service's progress still has to reach the screen.
    if (this.root.contains(document.activeElement) && this.root.firstChild) {
      this.refreshTarget();
      return;
    }
    const project = this.host.projectSection?.();
    this.root.replaceChildren(
      ...(project ? [project] : []),
      this.targetSection(),
      this.profileSection(),
      this.actionPaletteSection(),
      this.recoverySection(),
    );
  }
  /** Whether the id names a stored profile or the new-profile draft.
   * @param {string} id
   * @returns {boolean}
   */
  hasProfile(id) {
    return id === ""
      ? this.drafts.has("")
      : this.profiles.some(p => p.id === id);
  }
  /** The profile being edited, with any unsaved changes.
   * @returns {Profile|null}
   */
  current() {
    const id = this.selected ?? "";
    return (
      this.drafts.get(id) ??
      this.profiles.find(profile => profile.id === id) ??
      null
    );
  }
  /** The target being edited: the draft, else what is saved.
   * @returns {Target}
   */
  currentTarget() {
    return (
      this.targetDraft ??
      this.snapshot?.workspace?.target ?? {
        mode: "url",
        url: "",
        port: null,
        command: [],
        cwd: "",
        service_port: null,
        path: "/",
      }
    );
  }
  /** Read the target form, or explain what is wrong with it.
   * @param {HTMLFormElement} form
   * @returns {Target}
   * @throws {Error} When a port or the command cannot be read.
   */
  static readTarget = form => {
    /** @param {string} name */
    const value = name => {
      const field = form.elements.namedItem(name);
      return field instanceof HTMLInputElement ? field.value : "";
    };
    const mode = form.querySelector('input[name="mode"]:checked');
    const service =
      mode instanceof HTMLInputElement && mode.value === "service";
    const auto = form.querySelector('input[name="service-port-mode"]:checked');
    return {
      mode: service ? "service" : "url",
      url: value("url").trim(),
      port: parsePort(value("port")),
      command: splitCommand(value("command")),
      cwd: value("cwd").trim(),
      service_port:
        auto instanceof HTMLInputElement && auto.value === "manual"
          ? parsePort(value("service-port"))
          : null,
      path: value("path").trim() || "/",
    };
  };
  /** Card that owns the target service: address, port, and start/stop.
   * @returns {HTMLElement}
   */
  targetSection() {
    const draft = this.currentTarget();
    const form = /** @type {HTMLFormElement} */ (
      el("form", {
        class: "profile-form target-form",
        novalidate: true,
        "aria-label": "Target settings",
      })
    );
    /** @param {string} value
     * @param {string} label
     * @param {string} note
     * @returns {HTMLElement}
     */
    const mode = (value, label, note) => {
      const input = el("input", {
        type: "radio",
        name: "mode",
        value,
        ...(draft.mode === value ? { checked: true } : {}),
      });
      input.addEventListener("change", () => this.targetChanged(form));
      return el(
        "label",
        { class: "target-mode" },
        input,
        el("span", {}, el("strong", {}, label), el("small", {}, note)),
      );
    };
    const urlGroup = SettingsSurface.group(
      "Address",
      this.plain(
        "url",
        "Address",
        draft.url,
        "localhost or https://staging.example.com",
        form,
      ),
      this.plain(
        "port",
        "Port",
        draft.port === null ? "" : String(draft.port),
        "80",
        form,
        "numeric",
      ),
      el(
        "p",
        { class: "field-note" },
        "Empty uses 80 for http and 443 for https.",
      ),
    );
    urlGroup.setAttribute("data-mode-group", "url");
    const manual = draft.service_port !== null;
    const portAuto = el("input", {
      type: "radio",
      name: "service-port-mode",
      value: "auto",
      ...(manual ? {} : { checked: true }),
    });
    const portManual = el("input", {
      type: "radio",
      name: "service-port-mode",
      value: "manual",
      ...(manual ? { checked: true } : {}),
    });
    for (const radio of [portAuto, portManual])
      radio.addEventListener("change", () => this.targetChanged(form));
    const serviceGroup = SettingsSurface.group(
      "Service",
      this.plain(
        "command",
        "Command",
        joinCommand(draft.command),
        "npm run dev",
        form,
      ),
      this.plain("cwd", "Working folder", draft.cwd, "Project folder", form),
      this.plain("path", "Page to open", draft.path, "/", form),
      el(
        "div",
        { class: "settings-field", "data-field": "service-port" },
        el("span", { class: "field-label" }, "Port"),
        el(
          "span",
          { class: "field-control target-port" },
          el(
            "label",
            { class: "inline-choice" },
            portAuto,
            "Detect it automatically",
          ),
          el("label", { class: "inline-choice" }, portManual, "Use port"),
          this.plain(
            "service-port",
            "",
            draft.service_port === null ? "" : String(draft.service_port),
            "5173",
            form,
            "numeric",
            true,
          ),
        ),
      ),
      el("p", { class: "target-notice", "data-target-notice": true }),
    );
    serviceGroup.setAttribute("data-mode-group", "service");
    const start = el(
      "button",
      { type: "button", class: "accent", "data-target-start": true },
      "Start service",
    );
    const stop = el(
      "button",
      { type: "button", "data-target-stop": true },
      "Stop",
    );
    const check = el(
      "button",
      { type: "button", "data-target-check": true },
      "Check address",
    );
    start.addEventListener("click", () => {
      this.startService(form).catch(() => undefined);
    });
    stop.addEventListener("click", () => {
      this.run("target.stop", {}, "Service stopped.").catch(() => undefined);
    });
    check.addEventListener("click", () => {
      this.checkAddress(form).catch(() => undefined);
    });
    form.addEventListener("input", () => this.targetChanged(form));
    form.addEventListener("submit", event => {
      event.preventDefault();
      this.saveTarget(form).catch(() => undefined);
    });
    const save = () =>
      el("button", { type: "submit", "data-target-save": true }, "Save target");
    form.append(
      el(
        "fieldset",
        { class: "settings-group target-modes" },
        el("legend", {}, "How to reach the application"),
        mode("url", "Open an address", "It is already running."),
        mode(
          "service",
          "Start a service",
          "Studio runs a command and finds the port.",
        ),
      ),
      urlGroup,
      serviceGroup,
      el(
        "div",
        { class: "settings-actions" },
        el(
          "div",
          { class: "settings-actions-main", "data-mode-group": "url" },
          save(),
          check,
        ),
        el(
          "div",
          { class: "settings-actions-main", "data-mode-group": "service" },
          start,
          stop,
          save(),
        ),
        el("output", {
          class: "settings-status",
          role: "status",
          "aria-live": "polite",
          "data-target-status": true,
        }),
      ),
    );
    this.syncTargetForm(form);
    return el(
      "section",
      {
        class: "settings-section",
        id: "settings-target",
        "aria-labelledby": "settings-target-title",
      },
      el(
        "header",
        {},
        el("h3", { id: "settings-target-title" }, "Target"),
        el(
          "p",
          { class: "settings-intro" },
          "Where Studio finds the application to record and test.",
        ),
        ...(this.suggested
          ? [
              el(
                "p",
                { class: "field-note" },
                "Suggested: the bundled demo. Nothing is saved until you press Start or Save.",
              ),
            ]
          : []),
      ),
      form,
    );
  }
  /** A labelled text field read back by `readTarget`.
   * @param {string} name
   * @param {string} label
   * @param {string} value
   * @param {string} placeholder
   * @param {HTMLFormElement} form
   * @param {string} [inputmode]
   * @param {boolean} [bare] Omit the label row, for fields placed inside another.
   * @returns {HTMLElement}
   */
  plain(name, label, value, placeholder, form, inputmode, bare = false) {
    const input = el("input", {
      type: "text",
      name,
      value,
      placeholder,
      autocomplete: "off",
      spellcheck: "false",
      ...(inputmode ? { inputmode } : {}),
    });
    input.addEventListener("blur", () => {
      this.touched.add(name);
      this.syncTargetForm(form);
    });
    if (bare) {
      input.id = `field-${name}`;
      input.setAttribute("aria-label", "Port number");
      return input;
    }
    return SettingsSurface.field(name, label, input);
  }
  /** Remember what is typed and show only the fields the chosen mode uses.
   * @param {HTMLFormElement} form
   * @returns {void}
   */
  targetChanged(form) {
    try {
      this.targetDraft = SettingsSurface.readTarget(form);
      this.suggested = false;
    } catch {
      /* Typing is never blocked; the message appears when saving. */
    }
    this.syncTargetForm(form);
  }
  /** Show the fields of the current mode, the exact command, and the status.
   * @param {HTMLFormElement} form
   * @returns {void}
   */
  syncTargetForm(form) {
    const checked = form.querySelector('input[name="mode"]:checked');
    const service =
      checked instanceof HTMLInputElement && checked.value === "service";
    for (const group of form.querySelectorAll("[data-mode-group]"))
      group.toggleAttribute(
        "hidden",
        (group.getAttribute("data-mode-group") === "service") !== service,
      );
    const manual = form.querySelector(
      'input[name="service-port-mode"]:checked',
    );
    const port = form.elements.namedItem("service-port");
    if (port instanceof HTMLInputElement)
      port.disabled = !(
        manual instanceof HTMLInputElement && manual.value === "manual"
      );
    const notice = form.querySelector("[data-target-notice]");
    if (notice) {
      const command = form.elements.namedItem("command");
      const text =
        command instanceof HTMLInputElement ? command.value.trim() : "";
      notice.replaceChildren(
        "Studio runs this on your computer, in your project folder: ",
        el("code", {}, text || "(enter a command)"),
        ", only when you press Start service.",
      );
    }
    this.refreshTarget(form);
  }
  /** Update the status line and the Start, Stop and Check buttons.
   * @param {HTMLFormElement} [given]
   * @returns {void}
   */
  refreshTarget(given) {
    const form = given ?? this.root.querySelector(".target-form");
    if (!(form instanceof HTMLFormElement) || !this.snapshot) return;
    const service = this.snapshot.target_service;
    const state = service?.state ?? "idle";
    const busy = state === "starting" || state === "running";
    const command = form.elements.namedItem("command");
    const hasCommand =
      command instanceof HTMLInputElement && command.value.trim() !== "";
    const start = form.querySelector("[data-target-start]");
    if (start instanceof HTMLButtonElement) {
      start.disabled = busy || !hasCommand;
      start.title = busy
        ? "The service is already running."
        : hasCommand
          ? ""
          : "Enter the command that starts the service.";
    }
    const stop = form.querySelector("[data-target-stop]");
    if (stop instanceof HTMLButtonElement) {
      stop.disabled = !busy;
      stop.title = busy ? "" : "Nothing is running.";
    }
    const status = form.querySelector("[data-target-status]");
    // A one-off message gives way as soon as the service or the probe changes.
    const key = JSON.stringify([service, this.snapshot.target_check]);
    if (key !== this.targetKey) {
      this.targetKey = key;
      status?.removeAttribute("data-message");
    }
    if (status && !status.hasAttribute("data-message")) {
      const checked = form.querySelector('input[name="mode"]:checked');
      status.textContent =
        checked instanceof HTMLInputElement && checked.value === "service"
          ? describeService(service)
          : describeCheck(this.snapshot.target_check ?? null);
    }
  }
  /** Show a one-off message in the status line for a few seconds.
   * @param {HTMLFormElement} form
   * @param {string} text
   * @returns {void}
   */
  targetMessage(form, text) {
    const status = form.querySelector("[data-target-status]");
    if (!status) return;
    status.textContent = text;
    status.setAttribute("data-message", "");
    window.setTimeout(() => {
      status.removeAttribute("data-message");
      this.refreshTarget();
    }, 6000);
  }
  /** Save the target form.
   * @param {HTMLFormElement} form
   * @returns {Promise<boolean>} Whether the target is now saved.
   */
  async saveTarget(form) {
    /** @type {Target} */
    let target;
    try {
      target = SettingsSurface.readTarget(form);
    } catch (error) {
      this.targetMessage(
        form,
        error instanceof Error ? error.message : String(error),
      );
      return false;
    }
    try {
      this.host.apply(await this.host.call("target.save", { target }));
      this.targetDraft = null;
      this.suggested = false;
      this.targetMessage(form, "Target saved.");
      this.host.say("Target saved.");
      return true;
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      this.targetMessage(form, text);
      this.host.say(text);
      return false;
    }
  }
  /** Save, then start the service and open the Browser on its page.
   * @param {HTMLFormElement} form
   * @returns {Promise<void>}
   */
  async startService(form) {
    if (!await this.saveTarget(form)) return;
    try {
      this.host.apply(await this.host.call("target.start", { open: true }));
    } catch (error) {
      this.targetMessage(
        form,
        error instanceof Error ? error.message : String(error),
      );
    }
  }
  /** Save, then probe the address.
   * @param {HTMLFormElement} form
   * @returns {Promise<void>}
   */
  async checkAddress(form) {
    if (!await this.saveTarget(form)) return;
    try {
      this.host.apply(await this.host.call("target.check", {}));
      form
        .querySelector("[data-target-status]")
        ?.removeAttribute("data-message");
      this.refreshTarget(form);
    } catch (error) {
      this.targetMessage(
        form,
        error instanceof Error ? error.message : String(error),
      );
    }
  }
  /** Card listing every profile with the editor for the selected one.
   * @returns {HTMLElement}
   */
  profileSection() {
    const heading = el("h3", { id: "settings-profiles-title" }, "Profiles");
    const intro = el(
      "p",
      { class: "settings-intro" },
      "Browser conditions to record and test under.",
    );
    const list = el("ul", { class: "profile-list", "aria-label": "Profiles" });
    for (const profile of this.profiles) {
      const dirty = this.drafts.has(profile.id);
      const active = this.snapshot?.device_mode === profile.id;
      const button = el(
        "button",
        {
          type: "button",
          class: "profile-item",
          "aria-current": String(this.selected === profile.id),
          "data-profile": profile.id,
        },
        el("strong", {}, profile.name),
        el("small", {}, summary(profile)),
        ...(active ? [el("span", { class: "profile-badge" }, "In use")] : []),
        ...(dirty ? [el("span", { class: "profile-badge" }, "Unsaved")] : []),
      );
      button.addEventListener("click", () => this.select(profile.id));
      list.append(el("li", {}, button));
    }
    const add = el(
      "button",
      { type: "button", class: "profile-add", "data-profile-new": true },
      "New profile",
    );
    add.addEventListener("click", () => this.create());
    const draft = this.current();
    return el(
      "section",
      {
        class: "settings-section",
        id: "settings-profiles",
        "aria-labelledby": "settings-profiles-title",
      },
      el("header", {}, heading, intro),
      el(
        "div",
        { class: "settings-split" },
        el("div", { class: "profile-nav" }, list, add),
        draft
          ? this.form(draft)
          : el("p", { class: "surface-empty" }, "Create a profile to begin."),
      ),
    );
  }
  /** Choose which profile the editor shows.
   * @param {string} id
   */
  select(id) {
    this.selected = id;
    this.redraw();
  }
  /** Start a new profile from a copy of the one being viewed. */
  create() {
    const base = this.current() ?? this.profiles[0];
    this.drafts.set("", {
      id: "",
      name: "",
      width: base?.width ?? 1440,
      height: base?.height ?? 900,
      scale: base?.scale ?? 1,
      screen_width: null,
      screen_height: null,
      touch: false,
      mobile: false,
      media: {},
    });
    this.selected = "";
    this.touched.clear();
    this.redraw();
    this.root.querySelector('[name="name"]')?.dispatchEvent(new Event("focus"));
    const name = this.root.querySelector('[name="name"]');
    if (name instanceof HTMLElement) name.focus();
  }
  /** Redraw regardless of focus, after an explicit user choice. */
  redraw() {
    if (!this.snapshot) return;
    const hadFocus = this.root.contains(document.activeElement);
    if (hadFocus && document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
    this.render(this.snapshot);
  }
  /** Editor form for one profile draft.
   * @param {Profile} draft
   * @returns {HTMLFormElement}
   */
  form(draft) {
    const isNew = this.selected === "";
    const form = /** @type {HTMLFormElement} */ (
      el("form", {
        class: "profile-form",
        novalidate: true,
        "aria-label": "Profile settings",
      })
    );
    /** Remember a change and refresh dependent values without redrawing. */
    const change = () => {
      this.drafts.set(this.selected ?? "", draft);
      this.sync(form, draft);
    };
    form.append(
      SettingsSurface.group(
        "Identity",
        this.text(form, draft, "name", "Name", change, {
          placeholder: "Phone, tablet, dark desktop…",
        }),
        el(
          "p",
          { class: "field-note" },
          isNew
            ? "The ID is made from the name when you save."
            : `ID: ${draft.id}`,
        ),
      ),
      SettingsSurface.group(
        "Window",
        this.length(form, draft, "width", change),
        this.length(form, draft, "height", change),
        SettingsSurface.ratio(draft, change),
        SettingsSurface.orientation(draft, change),
      ),
      SettingsSurface.group(
        "Device",
        this.number(form, draft, "scale", change),
        this.length(form, draft, "screen_width", change),
        this.length(form, draft, "screen_height", change),
        this.choice("touch", draft.touch ? "touch" : "mouse", value => {
          draft.touch = value === "touch";
          change();
        }),
        this.toggle("mobile", draft.mobile, checked => {
          draft.mobile = checked;
          change();
        }),
      ),
      SettingsSurface.group(
        "Appearance and accessibility",
        ...this.fields
          .filter(field => field.group === "media")
          .map(field =>
            this.choice(
              field.id,
              draft.media[field.id] ?? "",
              value => {
                if (value === "") delete draft.media[field.id];
                else draft.media[field.id] = value;
                change();
              },
              true,
            ),
          ),
        this.unsupported(),
      ),
      this.actions(draft, isNew),
    );
    form.addEventListener("submit", event => {
      event.preventDefault();
      this.save(form, draft, isNew).catch(() => undefined);
    });
    this.sync(form, draft);
    return form;
  }
  /** Collapsible list of profile fields the backend cannot emulate.
   * @returns {HTMLElement}
   */
  unsupported() {
    const names = this.snapshot?.profile_schema?.unsupported ?? [];
    return el(
      "details",
      { class: "settings-unsupported" },
      el("summary", {}, "Not available in the test browser"),
      el(
        "p",
        {},
        "Chromium accepts these media features but ignores them, so a test could not rely on them: ",
        names.join(", "),
        ".",
      ),
    );
  }
  /** @param {string} title
   * @param {...Node} fields
   * @returns {HTMLElement}
   */
  static group = (title, ...fields) =>
    el(
      "fieldset",
      { class: "settings-group" },
      el("legend", {}, title),
      ...fields,
    );
  /** Wrap a control with its label, unit and an error slot.
   * @param {string} id
   * @param {string} label
   * @param {HTMLElement} control
   * @param {string} [unit]
   * @returns {HTMLElement}
   */
  static field = (id, label, control, unit) => {
    const error = el("small", {
      class: "field-error",
      id: `err-${id}`,
      role: "alert",
    });
    control.setAttribute("aria-describedby", `err-${id}`);
    control.id = `field-${id}`;
    return el(
      "div",
      { class: "settings-field", "data-field": id },
      el("label", { for: `field-${id}` }, label),
      el(
        "span",
        { class: "field-control" },
        control,
        ...(unit ? [el("span", { class: "field-unit" }, unit)] : []),
      ),
      error,
    );
  };
  /** A labelled text field bound to a draft value.
   * @param {HTMLFormElement} form
   * @param {Profile} draft
   * @param {"name"} id
   * @param {string} label
   * @param {()=>void} change
   * @param {{placeholder?:string}} [options]
   * @returns {HTMLElement}
   */
  text(form, draft, id, label, change, options = {}) {
    const input = el("input", {
      type: "text",
      name: id,
      value: draft[id],
      autocomplete: "off",
      spellcheck: "false",
      ...(options.placeholder ? { placeholder: options.placeholder } : {}),
    });
    input.addEventListener("input", () => {
      draft[id] = /** @type {HTMLInputElement} */ (input).value;
      change();
    });
    input.addEventListener("blur", () => {
      this.touched.add(id);
      this.sync(form, draft);
    });
    return SettingsSurface.field(id, label, input);
  }
  /** A pixel-size field validated against the field catalog.
   * @param {HTMLFormElement} form
   * @param {Profile} draft
   * @param {"width"|"height"|"screen_width"|"screen_height"} id
   * @param {()=>void} change
   * @returns {HTMLElement}
   */
  length(form, draft, id, change) {
    const spec = this.fields.find(field => field.id === id);
    const value = draft[id];
    const input = el("input", {
      type: "text",
      inputmode: "numeric",
      name: id,
      autocomplete: "off",
      value: value === null ? "" : String(value),
      placeholder: spec?.optional ? "Same as window" : "",
    });
    input.addEventListener("input", () => {
      const text = /** @type {HTMLInputElement} */ (input).value;
      const number = parseNumber(text);
      if (id === "screen_width" || id === "screen_height")
        draft[id] = text.trim() === "" ? null : number;
      else draft[id] = number;
      change();
    });
    input.addEventListener("blur", () => {
      this.touched.add(id);
      this.sync(form, draft);
    });
    return SettingsSurface.field(id, spec?.label ?? id, input, spec?.unit);
  }
  /** A decimal field validated against the field catalog.
   * @param {HTMLFormElement} form
   * @param {Profile} draft
   * @param {"scale"} id
   * @param {()=>void} change
   * @returns {HTMLElement}
   */
  number(form, draft, id, change) {
    const spec = this.fields.find(field => field.id === id);
    const input = el("input", {
      type: "text",
      inputmode: "decimal",
      name: id,
      autocomplete: "off",
      value: String(draft[id]),
    });
    input.addEventListener("input", () => {
      draft[id] = parseNumber(/** @type {HTMLInputElement} */ (input).value);
      change();
    });
    input.addEventListener("blur", () => {
      this.touched.add(id);
      this.sync(form, draft);
    });
    return SettingsSurface.field(id, spec?.label ?? id, input, spec?.unit);
  }
  /** Aspect ratio as two whole numbers; editing it changes the height.
   * @param {Profile} draft
   * @param {()=>void} change
   * @returns {HTMLElement}
   */
  static ratio = (draft, change) => {
    const [n, d] = reduceRatio(draft.width, draft.height);
    const left = el("input", {
      type: "text",
      inputmode: "numeric",
      name: "ratio-n",
      autocomplete: "off",
      "aria-label": "Aspect ratio width",
      value: String(n),
    });
    const right = el("input", {
      type: "text",
      inputmode: "numeric",
      name: "ratio-d",
      autocomplete: "off",
      "aria-label": "Aspect ratio height",
      value: String(d),
    });
    const apply = () => {
      const numerator = parseNumber(
        /** @type {HTMLInputElement} */ (left).value,
      );
      const denominator = parseNumber(
        /** @type {HTMLInputElement} */ (right).value,
      );
      if (!Number.isInteger(numerator) || !Number.isInteger(denominator))
        return;
      const height = heightForRatio(draft.width, numerator, denominator);
      if (height > 0) draft.height = height;
      change();
    };
    left.addEventListener("input", apply);
    right.addEventListener("input", apply);
    const group = el(
      "span",
      { class: "ratio-pair", role: "group", "aria-labelledby": "label-ratio" },
      left,
      el("span", { "aria-hidden": "true" }, ":"),
      right,
    );
    const wrapper = el(
      "div",
      { class: "settings-field", "data-field": "aspect-ratio" },
      el("span", { class: "field-label", id: "label-ratio" }, "Aspect ratio"),
      el("span", { class: "field-control" }, group),
      el("small", { class: "field-note" }, "Changing it adjusts the height."),
    );
    return wrapper;
  };
  /** Landscape/portrait select that keeps the ratio fields coherent.
   * @param {Profile} draft
   * @param {()=>void} change
   * @returns {HTMLElement}
   */
  static orientation = (draft, change) => {
    const select = el(
      "select",
      { name: "orientation" },
      el("option", { value: "landscape" }, "Landscape"),
      el("option", { value: "portrait" }, "Portrait"),
    );
    /** @type {HTMLSelectElement} */ (select).value =
      draft.width >= draft.height ? "landscape" : "portrait";
    select.addEventListener("change", () => {
      const wantsPortrait =
        /** @type {HTMLSelectElement} */ (select).value === "portrait";
      const isPortrait = draft.width < draft.height;
      if (wantsPortrait !== isPortrait)
        [draft.width, draft.height] = [draft.height, draft.width];
      change();
    });
    return SettingsSurface.field("orientation", "Orientation", select);
  };
  /** A choice from a fixed list; `optional` adds a "Browser default" entry.
   * @param {string} id
   * @param {string} value
   * @param {(value:string)=>void} onChange
   * @param {boolean} [optional]
   * @returns {HTMLElement}
   */
  choice(id, value, onChange, optional = false) {
    const spec = this.fields.find(field => field.id === id);
    const options = (spec?.options ?? []).map(option =>
      el("option", { value: option }, option.replace(/-/g, " ")),
    );
    const select = el(
      "select",
      { name: id },
      ...(optional ? [el("option", { value: "" }, "Browser default")] : []),
      ...options,
    );
    /** @type {HTMLSelectElement} */ (select).value = value;
    select.addEventListener("change", () =>
      onChange(/** @type {HTMLSelectElement} */ (select).value),
    );
    return SettingsSurface.field(id, spec?.label ?? id, select);
  }
  /** A checkbox bound to a boolean draft value.
   * @param {string} id
   * @param {boolean} checked
   * @param {(checked:boolean)=>void} onChange
   * @returns {HTMLElement}
   */
  toggle(id, checked, onChange) {
    const spec = this.fields.find(field => field.id === id);
    const input = el("input", {
      type: "checkbox",
      name: id,
      ...(checked ? { checked: true } : {}),
    });
    input.addEventListener("change", () =>
      onChange(/** @type {HTMLInputElement} */ (input).checked),
    );
    return el(
      "div",
      { class: "settings-field settings-toggle", "data-field": id },
      el("label", {}, input, spec?.label ?? id),
    );
  }
  /** Save and delete buttons for the profile form.
   * @param {Profile} draft
   * @param {boolean} isNew
   * @returns {HTMLElement}
   */
  actions(draft, isNew) {
    const save = el(
      "button",
      { type: "submit", class: "accent", "data-profile-save": true },
      isNew ? "Create profile" : "Save profile",
    );
    const dirty = this.drafts.has(this.selected ?? "");
    const inUse = (this.snapshot?.workspace?.flows ?? []).filter(flow =>
      flow.device_modes?.includes(draft.id),
    );
    const only = this.profiles.length <= 1;
    const use = el(
      "button",
      { type: "button", "data-profile-use": true },
      "Use in browser",
    );
    if (isNew || dirty) {
      use.setAttribute("disabled", "");
      use.setAttribute("title", "Save the profile first.");
    }
    use.addEventListener("click", () => {
      this.run(
        "viewport.preset",
        { mode: draft.id },
        "Showing the target with this profile.",
      ).catch(() => undefined);
    });
    const remove = el(
      "button",
      { type: "button", class: "link-danger", "data-profile-delete": true },
      "Delete profile",
    );
    const reason = isNew
      ? "This profile is not saved yet."
      : only
        ? "A project needs at least one profile."
        : inUse.length
          ? `${inUse.map((flow) => flow.name).join(", ")} ${inUse.length === 1 ? "is" : "are"} scoped to it.`
          : "";
    if (reason) {
      remove.setAttribute("disabled", "");
      remove.setAttribute("title", reason);
    }
    remove.addEventListener("click", async () => {
      const approved = await this.host.confirm({
        title: `Delete ${draft.name}?`,
        body: "Flows keep working under their other profiles.",
        keep: "Keep profile",
        remove: "Delete profile",
      });
      if (!approved) return;
      this.drafts.delete(draft.id);
      this.selected = null;
      await this.run(
        "profile.delete",
        { profile_id: draft.id },
        "Profile deleted.",
      );
    });
    return el(
      "div",
      { class: "settings-actions" },
      el("div", { class: "settings-actions-main" }, save, use),
      el("output", {
        class: "settings-status",
        role: "status",
        "aria-live": "polite",
      }),
      ...(reason ? [el("small", { class: "field-note" }, reason)] : []),
      remove,
    );
  }
  /** Show errors for fields the user has left, and update linked values.
   * @param {HTMLFormElement} form
   * @param {Profile} draft
   * @returns {void}
   */
  sync(form, draft) {
    const issues = issuesFor(draft, this.fields);
    for (const field of form.querySelectorAll("[data-field]")) {
      const id = field.getAttribute("data-field") ?? "";
      const shown = this.touched.has(id) ? (issues[id] ?? "") : "";
      const error = field.querySelector(".field-error");
      if (error) error.textContent = shown;
      const control = field.querySelector("input, select");
      if (control instanceof HTMLElement) {
        if (shown) control.setAttribute("aria-invalid", "true");
        else control.removeAttribute("aria-invalid");
      }
    }
    // Keep linked displays in step with the width and height being typed.
    const [n, d] = reduceRatio(draft.width, draft.height);
    SettingsSurface.setIfIdle(form, "ratio-n", String(n));
    SettingsSurface.setIfIdle(form, "ratio-d", String(d));
    const orientation = form.querySelector('select[name="orientation"]');
    if (
      orientation instanceof HTMLSelectElement &&
      orientation !== document.activeElement
    )
      orientation.value =
        draft.width >= draft.height ? "landscape" : "portrait";
    SettingsSurface.setIfIdle(
      form,
      "height",
      Number.isFinite(draft.height) ? String(draft.height) : undefined,
    );
    SettingsSurface.setIfIdle(
      form,
      "width",
      Number.isFinite(draft.width) ? String(draft.width) : undefined,
    );
  }
  /** Update an input unless the user is typing in it.
   * @param {HTMLFormElement} form
   * @param {string} name
   * @param {string|undefined} value
   * @returns {void}
   */
  static setIfIdle = (form, name, value) => {
    const input = form.querySelector(`[name="${name}"]`);
    if (
      value !== undefined &&
      input instanceof HTMLInputElement &&
      input !== document.activeElement &&
      input.value !== value
    )
      input.value = value;
  };
  /** Save the draft; refuse invalid values next to their fields.
   * @param {HTMLFormElement} form
   * @param {Profile} draft
   * @param {boolean} isNew
   * @returns {Promise<void>}
   */
  async save(form, draft, isNew) {
    for (const field of form.querySelectorAll("[data-field]"))
      this.touched.add(field.getAttribute("data-field") ?? "");
    this.sync(form, draft);
    const issues = issuesFor(draft, this.fields);
    const first = Object.keys(issues)[0];
    if (first) {
      const control = form.querySelector(
        `[data-field="${first}"] input, [data-field="${first}"] select`,
      );
      if (control instanceof HTMLElement) control.focus();
      SettingsSurface.status(form, "Fix the highlighted fields.");
      return;
    }
    const id = isNew
      ? slugify(
          draft.name,
          this.profiles.map(profile => profile.id),
        )
      : draft.id;
    const button = form.querySelector("[data-profile-save]");
    if (button instanceof HTMLButtonElement) button.disabled = true;
    try {
      const result = await this.host.call("profile.save", {
        profile: { ...draft, id, name: draft.name.trim() },
      });
      this.drafts.delete(this.selected ?? "");
      this.selected = id;
      this.touched.clear();
      this.host.apply(result);
      this.host.say("Profile saved.");
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      SettingsSurface.status(form, text);
      this.host.say(text);
    } finally {
      if (button instanceof HTMLButtonElement) button.disabled = false;
    }
  }
  /** @param {HTMLFormElement} form
   * @param {string} text
   * @returns {void}
   */
  static status = (form, text) => {
    const out = form.querySelector(".settings-status");
    if (out) out.textContent = text;
  };
  /** Run a command and apply its snapshot.
   * @param {string} name
   * @param {Record<string,unknown>} payload
   * @param {string} done
   * @returns {Promise<void>}
   */
  async run(name, payload, done) {
    try {
      this.host.apply(await this.host.call(name, payload));
      this.host.say(done);
      this.selected = null;
      this.redraw();
    } catch (error) {
      this.host.say(error instanceof Error ? error.message : String(error));
    }
  }
  /** Choose which actions the palette offers and which sit at the top.
   * @returns {HTMLElement}
   */
  actionPaletteSection() {
    const prefs = loadActionPrefs();
    const hidden = new Set(prefs.hidden);
    const pinned = new Set(prefs.pinned);
    /**
     * @param {Set<string>} set
     * @param {string} id
     * @param {boolean} on
     */
    const toggleIn = (set, id, on) => {
      if (on) set.add(id);
      else set.delete(id);
      saveActionPrefs({ hidden: [...hidden], pinned: [...pinned] });
    };
    /** Build one labelled preference checkbox.
     * @param {string} label
     * @param {boolean} checked
     * @param {(on: boolean) => void} change
     * @returns {HTMLElement}
     */
    const checkbox = (label, checked, change) => {
      const input = el("input", {
        type: "checkbox",
        ...(checked ? { checked: true } : {}),
      });
      input.addEventListener("change", () =>
        change(/** @type {HTMLInputElement} */ (input).checked),
      );
      return el("label", { class: "action-pref" }, input, label);
    };
    const groups = ACTION_GROUPS.map(group =>
      el(
        "fieldset",
        { class: "settings-group" },
        el("legend", {}, group.name),
        ...group.actions.map(action => {
          const show = checkbox("Show", !hidden.has(action.id), (/** @type {boolean} */ on) =>
            toggleIn(hidden, action.id, !on),
          );
          const pin = checkbox("Pin to top", pinned.has(action.id), (/** @type {boolean} */ on) =>
            toggleIn(pinned, action.id, on),
          );
          return el(
            "div",
            { class: "settings-field", "data-field": `action-${action.id}` },
            el("span", {}, action.label),
            el("span", { class: "field-control action-pref-row" }, show, pin),
          );
        }),
      ),
    );
    const reset = el("button", { type: "button" }, "Show all actions");
    reset.addEventListener("click", () => {
      saveActionPrefs({ hidden: [], pinned: [] });
      this.redraw();
    });
    return el(
      "section",
      {
        class: "settings-section",
        id: "settings-actions-palette",
        "aria-labelledby": "settings-actions-palette-title",
      },
      el(
        "header",
        {},
        el("h3", { id: "settings-actions-palette-title" }, "Actions palette"),
        el(
          "p",
          { class: "settings-intro" },
          "Hide actions you never use and pin the ones you reach for most. This applies to this browser only.",
        ),
      ),
      ...groups,
      el("div", { class: "settings-actions-main" }, reset),
    );
  }
  /** Card offering recovery of unsaved project work.
   * @returns {HTMLElement}
   */
  recoverySection() {
    const dirty = Boolean(this.snapshot?.dirty);
    const copy = el(
      "a",
      {
        class: "export-button",
        href: "/api/export",
        download: "workspace-copy.pwflow.json",
      },
      "Save a copy",
    );
    return el(
      "section",
      {
        class: "settings-section",
        id: "settings-recovery",
        "aria-labelledby": "settings-recovery-title",
      },
      el(
        "header",
        {},
        el("h3", { id: "settings-recovery-title" }, "Recovery"),
        el(
          "p",
          { class: "settings-intro" },
          dirty
            ? "Unsaved changes are kept in recovery, so a crash does not lose them."
            : "Everything is saved. If the file changes on disk, your version waits here.",
        ),
      ),
      el("div", { class: "settings-actions-main" }, copy),
    );
  }
}
