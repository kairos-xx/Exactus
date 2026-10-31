/** Console method semantics (groups, counters, timers, tables) feeding any entry sink.
 *
 * The class source is embedded verbatim in sandbox workers next to
 * `Describer`, so it may reference only itself and `Describer`.
 */
import { Describer } from "./describe.js";
/** @typedef {import("./console_view.js").EntryInput} EntryInput */
/**
 * @typedef {object} Sink
 * @property {(entry:EntryInput)=>void} append Receive one entry.
 * @property {()=>void} clear Receive a `console.clear()`.
 */
/** @typedef {(...args:any[])=>void} ConsoleMethod */
/**
 * @typedef {object} ConsoleMethods
 * @property {ConsoleMethod} log Write a log message.
 * @property {ConsoleMethod} info Write an info message.
 * @property {ConsoleMethod} warn Write a warning.
 * @property {ConsoleMethod} error Write an error.
 * @property {ConsoleMethod} debug Write a debug message.
 * @property {ConsoleMethod} dir Write one inspectable value.
 * @property {ConsoleMethod} dirxml Write values.
 * @property {ConsoleMethod} trace Write a message with a stack.
 * @property {ConsoleMethod} assert Write an error when the condition is falsy.
 * @property {ConsoleMethod} clear Clear the console.
 * @property {ConsoleMethod} count Count calls per label.
 * @property {ConsoleMethod} countReset Reset a counter.
 * @property {ConsoleMethod} time Start a timer.
 * @property {ConsoleMethod} timeLog Report a running timer.
 * @property {ConsoleMethod} timeEnd Report and stop a timer.
 * @property {ConsoleMethod} group Open a group.
 * @property {ConsoleMethod} groupCollapsed Open a group.
 * @property {ConsoleMethod} groupEnd Close the innermost group.
 * @property {ConsoleMethod} table Write tabular data.
 */
/** @typedef {(stack:string)=>({line:number, column:number}|undefined)} StackLocator */
/**
 * @typedef {object} RecorderOptions
 * @property {StackLocator} [locate] Map a stack to a snippet call site.
 */
/** Record console calls as console entries for a sink. */
export class ConsoleRecorder {
  /** @type {readonly string[]} */
  static NAMES = Object.freeze([
    "log", "info", "warn", "error", "debug", "trace", "assert", "clear", "count", "countReset",
    "time", "timeLog", "timeEnd", "group", "groupCollapsed", "groupEnd", "table", "dir", "dirxml",
  ]);
  /** @type {Sink} */
  sink;
  /** @type {RecorderOptions["locate"]} */
  locate;
  depth = 0;
  /** @type {Map<string, number>} */
  counts = new Map();
  /** @type {Map<string, number>} */
  timers = new Map();
  /**
   * @param {Sink} sink Destination of recorded entries.
   * @param {RecorderOptions} [options] Optional call-site locator.
   */
  constructor(sink, options = {}) {
    this.sink = sink;
    this.locate = options.locate;
  }
  /**
   * Record one entry at the current group depth.
   * @param {"log"|"info"|"warn"|"error"|"debug"} level Severity.
   * @param {"message"|"table"|"group"} kind Row presentation.
   * @param {unknown[]} args Values to describe.
   * @returns {void}
   */
  emit(level, kind, args) {
    /** @type {EntryInput} */
    const entry = { level, kind, parts: args.map(arg => Describer.describe(arg)), time: Date.now(), depth: this.depth };
    const source = this.locate?.(new Error().stack ?? "");
    if (source) entry.source = source;
    this.sink.append(entry);
  }
  /**
   * Build a console-like object whose calls feed the sink.
   * @returns {ConsoleMethods} Console methods.
   */
  methods() {
    return {
      log: (...args) => this.emit("log", "message", args),
      info: (...args) => this.emit("info", "message", args),
      warn: (...args) => this.emit("warn", "message", args),
      error: (...args) => this.emit("error", "message", args),
      debug: (...args) => this.emit("debug", "message", args),
      dir: (...args) => this.emit("log", "message", args.slice(0, 1)),
      dirxml: (...args) => this.emit("log", "message", args),
      trace: (...args) => this.emit("log", "message", ["Trace:", ...args, String(new Error().stack ?? "").split("\n").slice(2).join("\n")]),
      assert: (condition, ...args) => {
        if (!condition) this.emit("error", "message", args.length ? ["Assertion failed:", ...args] : ["Assertion failed"]);
      },
      clear: () => {
        this.depth = 0;
        this.sink.clear();
      },
      count: (label = "default") => {
        const next = (this.counts.get(String(label)) ?? 0) + 1;
        this.counts.set(String(label), next);
        this.emit("log", "message", [`${label}: ${next}`]);
      },
      countReset: (label = "default") => {
        this.counts.delete(String(label));
      },
      time: (label = "default") => {
        this.timers.set(String(label), performance.now());
      },
      timeLog: (label = "default", ...args) => this.stamp(String(label), false, args),
      timeEnd: (label = "default") => this.stamp(String(label), true, []),
      group: (...labels) => this.open(labels),
      groupCollapsed: (...labels) => this.open(labels),
      groupEnd: () => {
        this.depth = Math.max(0, this.depth - 1);
      },
      table: data => this.emit("log", "table", [data]),
    };
  }
  /**
   * Open a group with a header row.
   * @param {unknown[]} labels Header values.
   * @returns {void}
   */
  open(labels) {
    this.emit("log", "group", labels.length ? labels : ["console.group"]);
    this.depth += 1;
  }
  /**
   * Report a timer's elapsed time.
   * @param {string} label Timer label.
   * @param {boolean} finish Whether the timer ends.
   * @param {unknown[]} extra Extra values after the time.
   * @returns {void}
   */
  stamp(label, finish, extra) {
    const started = this.timers.get(label);
    if (started === undefined) {
      this.emit("warn", "message", [`Timer "${label}" does not exist`]);
      return;
    }
    this.emit("log", "message", [`${label}: ${(performance.now() - started).toFixed(2)} ms`, ...extra]);
    if (finish) this.timers.delete(label);
  }
}
