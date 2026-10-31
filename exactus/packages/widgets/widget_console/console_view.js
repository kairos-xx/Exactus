/** The console widget: a filterable, searchable message list with inspectable values. */
import { Describer } from "./describe.js";
import { applyFormat, partsText } from "./format.js";
import { icon } from "./icons.js";
import { renderTable, renderValue } from "./inspect.js";
import { ConsoleRecorder } from "./recorder.js";
/** @typedef {import("./describe.js").Descriptor} Descriptor */
/** @typedef {"log"|"info"|"warn"|"error"|"debug"} Level */
/** @typedef {"message"|"table"|"group"|"result"|"input"|"divider"} Kind */
/**
 * @typedef {object} EntryInput
 * @property {Level} [level] Severity, `log` by default.
 * @property {Kind} [kind] Row presentation, `message` by default.
 * @property {Descriptor[]} parts Message parts as descriptors.
 * @property {number} [time] Epoch milliseconds, now by default.
 * @property {number} [depth] Group nesting level.
 * @property {{line:number, column:number}} [source] Call site in the snippet.
 */
/**
 * @typedef {object} ConsoleEntry
 * @property {number} id Sequence number.
 * @property {Level} level Severity.
 * @property {Kind} kind Row presentation.
 * @property {Descriptor[]} parts Message parts.
 * @property {number} time Epoch milliseconds.
 * @property {number} depth Group nesting level.
 * @property {number} repeat Consecutive identical occurrences.
 * @property {{line:number, column:number}} [source] Call site in the snippet.
 */
/**
 * @typedef {object} ConsoleOptions
 * @property {string} [label] Title text.
 * @property {string|null} [theme] `light`, `dark`, or null to inherit.
 * @property {number} [maxEntries] Rows kept before the oldest are dropped.
 * @property {boolean} [timestamps] Show a time column.
 * @property {boolean} [search] Show the filter row.
 * @property {string} [emptyText] Text shown while there are no rows.
 */
/**
 * @typedef {object} Row
 * @property {ConsoleEntry} entry The stored entry.
 * @property {HTMLElement} node Its row element.
 * @property {string} text Lower-case searchable text.
 */
const LEVEL_NAMES = /** @type {Record<string, string>} */ ({
  all: "All levels",
  error: "Errors",
  warn: "Warnings",
  info: "Info",
  log: "Logs",
  debug: "Debug",
});
const MAX_DEPTH = 5;
/**
 * Create an element with an optional class and text.
 * @template {keyof HTMLElementTagNameMap} K
 * @param {K} tag Tag name.
 * @param {string} [className] Class list.
 * @param {string} [text] Text content.
 * @returns {HTMLElementTagNameMap[K]} The new element.
 */
const make = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
/**
 * Create a ghost icon button.
 * @param {import("./icons.js").IconName} name Icon name.
 * @param {string} label Accessible name and tooltip.
 * @returns {HTMLButtonElement} The button.
 */
const iconButton = (name, label) => {
  const button = make("button", "jc-button");
  button.type = "button";
  button.title = label;
  button.setAttribute("aria-label", label);
  button.append(icon(name));
  return button;
};
/**
 * Format epoch milliseconds as `HH:MM:SS.mmm`.
 * @param {number} time Epoch milliseconds.
 * @returns {string} Clock text.
 */
const clock = time => {
  const date = new Date(time);
  /** Pad one clock field with leading zeros. */
  const part = (/** @type {number} */ value, /** @type {number} */ width) => String(value).padStart(width, "0");
  return `${part(date.getHours(), 2)}:${part(date.getMinutes(), 2)}:${part(date.getSeconds(), 2)}.${part(date.getMilliseconds(), 3)}`;
};
/**
 * Build the marker glyph or icon for an entry.
 * @param {ConsoleEntry} entry Entry to mark.
 * @returns {Node} The marker content.
 */
const markerFor = entry => {
  if (entry.kind === "input") return document.createTextNode("›");
  if (entry.kind === "result") return document.createTextNode("‹");
  if (entry.level === "error") return icon("error");
  if (entry.level === "warn") return icon("warn");
  if (entry.level === "info") return icon("info");
  return document.createTextNode("");
};
/**
 * Render the message parts of one entry.
 * @param {ConsoleEntry} entry Entry to render.
 * @returns {HTMLElement} The message element.
 */
const renderMessage = entry => {
  const message = make("div", "jc-message");
  const [first] = entry.parts;
  if (entry.kind === "table" && first) {
    message.append(renderTable(first));
    return message;
  }
  const nestedStrings = entry.kind === "result" || entry.kind === "input";
  entry.parts.forEach((part, index) => {
    if (index > 0) message.append(" ");
    if (part.t === "string" && !nestedStrings)
      message.append(make("span", "jc-text", part.more ? `${part.v}… +${part.more} characters` : part.v));
     else
      message.append(renderValue(part, nestedStrings && part.t === "string"));
  });
  return message;
};
/**
 * Mount a console widget in a host element.
 * @param {HTMLElement} host Element that receives the widget.
 * @param {ConsoleOptions} [options] Widget options.
 * @returns The widget API.
 */
export const mountConsole = (host, options = {}) => {
  const { label = "Console", theme = null, maxEntries = 1000, emptyText = "No messages yet." } = options;
  const root = make("section", "jc-console");
  if (theme) root.setAttribute("data-theme", theme);
  root.setAttribute("aria-label", label);
  root.setAttribute("data-time", String(options.timestamps ?? false));
  const head = make("div", "jc-head");
  const title = make("span", "jc-title", label);
  const errorChip = /** @type {HTMLButtonElement} */ (make("button", "jc-chip"));
  const warnChip = /** @type {HTMLButtonElement} */ (make("button", "jc-chip"));
  for (const [chip, name] of /** @type {const} */ ([[errorChip, "error"], [warnChip, "warn"]])) {
    chip.type = "button";
    chip.hidden = true;
    chip.setAttribute("data-level", name);
    chip.append(icon(name), make("span", "jc-chip-count"));
  }
  const spacer = make("span", "jc-spacer");
  const timeButton = iconButton("clock", "Show timestamps");
  const copyButton = iconButton("copy", "Copy all messages");
  const clearButton = iconButton("clear", "Clear console");
  timeButton.setAttribute("aria-pressed", String(options.timestamps ?? false));
  head.append(title, errorChip, warnChip, spacer, timeButton, copyButton, clearButton);
  const tools = make("div", "jc-tools");
  const searchWrap = make("label", "jc-search");
  const searchInput = make("input");
  searchInput.type = "search";
  searchInput.placeholder = "Filter messages";
  searchInput.setAttribute("aria-label", "Filter messages");
  searchInput.autocomplete = "off";
  searchInput.spellcheck = false;
  searchWrap.append(icon("search"), searchInput);
  const levelWrap = make("span", "jc-select");
  const levelSelect = make("select");
  levelSelect.setAttribute("aria-label", "Show level");
  for (const [value, text] of Object.entries(LEVEL_NAMES)) {
    const option = make("option", "", text);
    option.value = value;
    levelSelect.append(option);
  }
  levelWrap.append(levelSelect);
  tools.append(searchWrap, levelWrap);
  tools.hidden = options.search === false;
  const list = make("div", "jc-list");
  list.setAttribute("role", "log");
  list.setAttribute("aria-live", "polite");
  list.setAttribute("aria-relevant", "additions");
  list.setAttribute("aria-label", `${label} messages`);
  list.tabIndex = 0;
  const empty = make("p", "jc-empty", emptyText);
  const trimmed = make("p", "jc-trimmed", "Older messages were removed.");
  trimmed.hidden = true;
  list.append(trimmed, empty);
  root.append(head, tools, list);
  host.append(root);
  /** @type {Row[]} */
  const rows = [];
  /** @type {Record<string, Set<(detail:any)=>void>>} */
  const listeners = {};
  let sequence = 0;
  let filter = "all";
  let query = "";
  /**
   * Notify registered listeners.
   * @param {string} type Event type.
   * @param {unknown} detail Event payload.
   * @returns {void}
   */
  const emit = (type, detail) => {
    for (const listener of listeners[type] ?? []) listener(detail);
  };
  /**
   * Count message rows per level.
   * @returns {Record<Level, number>} Counts by level.
   */
  const counts = () => {
    const total = { log: 0, info: 0, warn: 0, error: 0, debug: 0 };
    for (const { entry } of rows) {
      if (entry.kind === "message" || entry.kind === "table" || entry.kind === "group") total[entry.level] += entry.repeat;
    }
    return total;
  };
  /**
   * Decide whether a row passes the level and text filters.
   * @param {Row} row Row to test.
   * @returns {boolean} True when the row should show.
   */
  const passes = row => {
    const { kind, level } = row.entry;
    if (kind === "divider") return true;
    const levelOk = filter === "all" || kind === "input" || kind === "result" || level === filter;
    const queryOk = query === "" || kind === "input" || row.text.includes(query);
    return levelOk && queryOk;
  };
  /** Refresh row visibility, chips and the empty state. */
  const refresh = () => {
    let shown = 0;
    for (const row of rows) {
      const visible = passes(row);
      row.node.hidden = !visible;
      if (visible) shown += 1;
    }
    const total = counts();
    for (const [chip, level] of /** @type {const} */ ([[errorChip, "error"], [warnChip, "warn"]])) {
      chip.hidden = total[level] === 0;
      const count = chip.querySelector(".jc-chip-count");
      if (count) count.textContent = String(total[level]);
      chip.setAttribute("aria-pressed", String(filter === level));
      chip.setAttribute("aria-label", `${total[level]} ${LEVEL_NAMES[level]?.toLowerCase()}, ${filter === level ? "show all" : "show only"}`);
    }
    empty.hidden = shown > 0;
    empty.textContent = rows.length > 0 && shown === 0 ? "No messages match the filter." : emptyText;
    root.setAttribute("data-empty", String(rows.length === 0));
  };
  /** Notify listeners that the row set or counts changed. */
  const changed = () => {
    refresh();
    const total = counts();
    emit("change", { count: rows.length, errors: total.error, warnings: total.warn });
  };
  /**
   * Add one entry.
   * @param {EntryInput} input Entry fields.
   * @returns {number} The entry id, or the id of the folded duplicate.
   */
  const append = input => {
    const level = input.level ?? "log";
    const kind = input.kind ?? "message";
    const parts = kind === "message" ? applyFormat(input.parts) : input.parts;
    const text = partsText(parts).toLowerCase();
    const depth = Math.min(input.depth ?? 0, MAX_DEPTH);
    const previous = rows.at(-1);
    if (
      previous &&
      kind === "message" &&
      previous.entry.kind === "message" &&
      previous.entry.level === level &&
      previous.entry.depth === depth &&
      previous.text === text &&
      !input.source === !previous.entry.source
    ) {
      previous.entry.repeat += 1;
      const badge = previous.node.querySelector(".jc-repeat");
      if (badge instanceof HTMLElement) {
        badge.hidden = false;
        badge.textContent = `×${previous.entry.repeat}`;
      }
      changed();
      return previous.entry.id;
    }
    sequence += 1;
    /** @type {ConsoleEntry} */
    const entry = { id: sequence, level, kind, parts, time: input.time ?? Date.now(), depth, repeat: 1 };
    if (input.source) entry.source = input.source;
    const node = make("div", "jc-entry");
    node.setAttribute("data-level", level);
    node.setAttribute("data-kind", kind);
    node.setAttribute("data-depth", String(depth));
    if (kind === "divider")
      node.append(make("span", "jc-rule"), make("span", "jc-divider-text", partsText(parts)), make("span", "jc-rule"));
     else {
      const marker = make("span", "jc-marker");
      marker.append(markerFor(entry));
      const stamp = make("span", "jc-time", clock(entry.time));
      const repeat = make("span", "jc-repeat");
      repeat.hidden = true;
      node.append(marker, stamp, renderMessage(entry), repeat);
      if (entry.source) {
        const source = make("button", "jc-source", `${entry.source.line}:${entry.source.column}`);
        source.type = "button";
        source.title = `Go to line ${entry.source.line}`;
        const { line, column } = entry.source;
        source.addEventListener("click", () => emit("source", { line, column }));
        node.append(source);
      }
    }
    const stick = list.scrollHeight - list.scrollTop - list.clientHeight < 24;
    list.append(node);
    rows.push({ entry, node, text });
    if (rows.length > maxEntries) {
      rows.shift()?.node.remove();
      trimmed.hidden = false;
    }
    changed();
    if (stick) list.scrollTop = list.scrollHeight;
    return entry.id;
  };
  /**
   * Describe live values and add them as one entry.
   * @param {Level} level Severity.
   * @param {...unknown} values Values to describe.
   * @returns {number} The entry id.
   */
  const log = (level, ...values) => append({ level, parts: values.map(value => Describer.describe(value)) });
  /** Remove every row. */
  const clear = () => {
    for (const row of rows) row.node.remove();
    rows.length = 0;
    trimmed.hidden = true;
    changed();
  };
  /**
   * Show only one level, or all levels.
   * @param {string} level A level name or `all`.
   * @returns {void}
   */
  const setFilter = level => {
    filter = level in LEVEL_NAMES ? level : "all";
    levelSelect.value = filter;
    refresh();
  };
  /**
   * Show only rows containing text.
   * @param {string} text Case-insensitive substring.
   * @returns {void}
   */
  const setQuery = text => {
    query = text.trim().toLowerCase();
    if (searchInput.value !== text) searchInput.value = text;
    refresh();
  };
  /**
   * Show or hide the timestamp column.
   * @param {boolean} on Whether timestamps show.
   * @returns {void}
   */
  const setTimestamps = on => {
    root.setAttribute("data-time", String(on));
    timeButton.setAttribute("aria-pressed", String(on));
  };
  /**
   * Plain text of the rows that currently show.
   * @returns {string} Lines joined with newlines.
   */
  const text = () =>
    rows
      .filter(row => !row.node.hidden)
      .map(({ entry }) => `${"  ".repeat(entry.depth)}${partsText(entry.parts)}${entry.repeat > 1 ? ` (×${entry.repeat})` : ""}`)
      .join("\n");
  levelSelect.addEventListener("change", () => setFilter(levelSelect.value));
  searchInput.addEventListener("input", () => setQuery(searchInput.value));
  /**
   * Toggle a quick level filter.
   * @param {string} level Level to show, or all when it is already shown.
   * @returns {void}
   */
  const toggleLevel = level => setFilter(filter === level ? "all" : level);
  errorChip.addEventListener("click", () => toggleLevel("error"));
  warnChip.addEventListener("click", () => toggleLevel("warn"));
  timeButton.addEventListener("click", () => setTimestamps(root.getAttribute("data-time") !== "true"));
  clearButton.addEventListener("click", clear);
  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(text());
      emit("copy", { length: rows.length });
    } catch (error) {
      emit("copy", { error });
    }
  });
  const recorder = new ConsoleRecorder({ append, clear });
  const methods = recorder.methods();
  /**
   * Mirror a host console and uncaught errors into this widget.
   * @param {Console} [source] Console to mirror, the page console by default.
   * @param {Window} [target] Window that reports uncaught errors.
   * @returns {()=>void} Restore function.
   */
  const capture = (source = globalThis.console, target = window) => {
    const writable = /** @type {Record<string, (...args:unknown[])=>void>} */ (/** @type {unknown} */ (source));
    /** @type {Record<string, (...args:unknown[])=>void>} */
    const originals = {};
    const lookup = /** @type {Record<string, ((...args:unknown[])=>void)|undefined>} */ (/** @type {unknown} */ (methods));
    for (const name of ConsoleRecorder.NAMES) {
      const original = writable[name];
      const mirrored = lookup[name];
      if (!original || !mirrored) continue;
      originals[name] = original;
      writable[name] = (...args) => {
        original.apply(source, args);
        mirrored(...args);
      };
    }
    /**
     * Record an uncaught page error as a console entry.
     * @param {ErrorEvent} event Uncaught error.
     */
    const onError = event => log("error", event.error ?? event.message);
    /**
     * Record an unhandled rejection as a console entry.
     * @param {PromiseRejectionEvent} event Unhandled rejection.
     */
    const onRejection = event => log("error", event.reason);
    target.addEventListener("error", onError);
    target.addEventListener("unhandledrejection", onRejection);
    return () => {
      for (const [name, original] of Object.entries(originals)) writable[name] = original;
      target.removeEventListener("error", onError);
      target.removeEventListener("unhandledrejection", onRejection);
    };
  };
  refresh();
  const api = {
    element: root,
    list,
    append,
    log,
    clear,
    capture,
    console: methods,
    setFilter,
    setQuery,
    setTimestamps,
    text,
    counts,
    entries: () => rows.map(row => row.entry),
    /**
     * Subscribe to `change`, `source` or `copy` events.
     * @param {string} type Event type.
     * @param {(detail:any)=>void} listener Event listener.
     * @returns {()=>void} Unsubscribe function.
     */
    on: (type, listener) => {
      (listeners[type] ??= new Set()).add(listener);
      return () => listeners[type]?.delete(listener);
    },
    /**
     * Set or clear the widget theme.
     * @param {string|null} value `light`, `dark` or null.
     * @returns {void}
     */
    setTheme: value => value ? root.setAttribute("data-theme", value) : root.removeAttribute("data-theme"),
    /** Remove the widget from the page. */
    destroy: () => {
      root.remove();
      for (const set of Object.values(listeners)) set.clear();
    },
  };
  return api;
};
/** @typedef {ReturnType<typeof mountConsole>} ConsoleApi */
