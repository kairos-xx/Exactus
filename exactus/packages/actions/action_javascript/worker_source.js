/** Source text of the sandbox worker that runs one snippet. */
import { Describer } from "../../widgets/widget_console/describe.js";
import { ConsoleRecorder } from "../../widgets/widget_console/recorder.js";
/**
 * @typedef {object} WorkerScope
 * @property {(message:unknown)=>void} postMessage Send a message to the host.
 * @property {((event:{data:any})=>void)|null} onmessage Receive the run request.
 * @property {(type:string, listener:(event:any)=>void)=>void} addEventListener Listen for scope events.
 */
/**
 * Worker runtime. This function is stringified into the worker, where
 * `Describer` and `ConsoleRecorder` are defined by the preceding source.
 * @returns {void}
 * @throws {AssertionError} When a snippet assertion fails.
 * @throws {Error} When a page-only `exactus` member is read in the preview.
 */
const workerMain = () => {
  const scope = /** @type {WorkerScope} */ (/** @type {unknown} */ (self));
  const AsyncFunction = /** @type {FunctionConstructor} */ (Object.getPrototypeOf(async () => {}).constructor);
  const MAX_ENTRIES = 1000;
  /**
   * Send one message to the host page.
   * @param {unknown} message Message for the host.
   */
  const post = message => scope.postMessage(message);
  /** Error thrown when a snippet assertion fails. */
  class AssertionError extends Error {
    /** @param {string} message Failure text. */
    constructor(message) {
      super(message);
      this.name = "AssertionError";
    }
  }
  /**
   * @typedef {object} Compiled
   * @property {Function} run Compiled async function.
   * @property {number} from First compiled line that belongs to the returned tail.
   * @property {number} shift Lines the wrapper inserted before the tail.
   * @property {number} tailLine Snippet line on which the tail begins.
   * @property {number} prefix Characters of that line that precede the tail.
   */
  /**
   * Compile a snippet, preferring an implicit return of its last expression.
   * @param {string} code Snippet source.
   * @param {string} mode `auto`, `playback`, `expression` or `statements`.
   * @returns {Compiled} Compiled function and its line mapping.
   */
  const compile = (code, mode) => {
    /**
     * Compile a function body for the snippet runtime.
     * @param {string} body Function body.
     */
    const build = body => new AsyncFunction("exactus", "console", "__EXACTUS_FLOW__", body);
    if (mode === "expression") return { run: build(`return (\n${code}\n);`), from: 2, shift: 1, tailLine: 1, prefix: 0 };
    if (mode === "playback") {
      try {
        return { run: build(`return (\n${code}\n);`), from: 2, shift: 1, tailLine: 1, prefix: 0 };
      } catch {
        // Not a single expression: playback compiles the snippet as a function body.
        return { run: build(code), from: Number.POSITIVE_INFINITY, shift: 0, tailLine: 0, prefix: 0 };
      }
    }
    if (mode === "auto") {
      const lines = code.replace(/[;\s]+$/, "").split("\n");
      const last = lines.length - 1;
      for (let split = last; split >= Math.max(0, last - 24); split -= 1) {
        const tail = lines.slice(split).join("\n");
        if (tail.trim() === "") continue;
        const head = lines.slice(0, split).join("\n");
        try {
          return { run: build(`${head ? `${head}\n` : ""}return (\n${tail}\n);`), from: split + 2, shift: 1, tailLine: split + 1, prefix: 0 };
        } catch {
          continue;
        }
      }
      const line = lines[last] ?? "";
      const before = lines.slice(0, last).join("\n");
      let semicolon = line.lastIndexOf(";");
      for (let tries = 0; semicolon >= 0 && tries < 20; tries += 1) {
        const tail = line.slice(semicolon + 1);
        const kept = line.slice(0, semicolon + 1);
        if (tail.trim() !== "") {
          try {
            return { run: build(`${before ? `${before}\n` : ""}${kept}\nreturn (\n${tail}\n);`), from: lines.length + 2, shift: 2, tailLine: lines.length, prefix: kept.length };
          } catch {
            // This split is not a complete expression; try the previous semicolon.
          }
        }
        semicolon = line.lastIndexOf(";", semicolon - 1);
      }
    }
    return { run: build(code), from: Number.POSITIVE_INFINITY, shift: 0, tailLine: 0, prefix: 0 };
  };
  scope.onmessage = async event => {
    const { code, mode, variables, context } = event.data;
    const started = performance.now();
    /**
     * Compiled function and line mapping, filled once the snippet compiles.
     * @type {Compiled}
     */
    let mapping = { run: () => undefined, from: Number.POSITIVE_INFINITY, shift: 0, tailLine: 0, prefix: 0 };
    let sent = 0;
    /**
     * Map a stack to a snippet line and column.
     * @param {string} stack Error stack text.
     * @returns {{line:number, column:number}|undefined} Snippet position.
     */
    const locate = stack => {
      const found = /<anonymous>:(\d+):(\d+)/.exec(stack);
      if (!found) return undefined;
      const body = Number(found[1]) - 2;
      const line = body < mapping.from ? body : body - mapping.shift;
      const column = Number(found[2]) + (line === mapping.tailLine ? mapping.prefix : 0);
      return line >= 1 ? { line, column } : undefined;
    };
    const recorder = new ConsoleRecorder(
      {
        append: entry => {
          sent += 1;
          if (sent <= MAX_ENTRIES) post({ type: "entry", entry });
          else if (sent === MAX_ENTRIES + 1) post({ type: "entry", entry: { level: "warn", kind: "message", parts: [Describer.describe(`Output truncated after ${MAX_ENTRIES} messages.`)], time: Date.now(), depth: 0 } });
        },
        clear: () => post({ type: "clear" }),
      },
      { locate },
    );
    const methods = recorder.methods();
    const known = Object.hasOwn.bind(Object);
    /** @type {Record<string, unknown>} */
    const bag = { ...(variables ?? {}) };
    const given = /** @type {{flow?:{id?:string}, action?:{id?:string}, run?:{id?:string}, [section:string]: any}} */ (context ?? {});
    /**
     * Freeze a copy of one context section.
     * @param {string} name Section name.
     * @returns {object} Frozen copy.
     */
    const section = name => Object.freeze({ ...(given[name] ?? {}) });
    /**
     * Throw when an assertion condition is falsy.
     * @throws {AssertionError} When the condition is falsy.
     */
    const assertion = (/** @type {unknown} */ condition, /** @type {string|undefined} */ message) => {
      if (!condition) throw new AssertionError(message ?? "Assertion failed.");
    };
    const flow = {
      id: given.flow?.id ?? null,
      flowId: given.flow?.id ?? null,
      actionId: given.action?.id ?? null,
      runId: given.run?.id ?? null,
      index: 0,
      count: 1,
      targets: [],
      target: null,
      vars: bag,
      log: methods.log,
      warn: methods.warn,
      error: methods.error,
      assert: assertion,
    };
    const exactus = {
      project: section("project"),
      context: section("context"),
      flow: section("flow"),
      run: section("run"),
      action: section("action"),
      inputs: section("inputs"),
      vars: Object.freeze({
        get: (/** @type {string} */ name) => {
          if (!known(bag, name)) methods.warn(`exactus.vars.get: no value named "${String(name)}"`);
          return bag[name];
        },
        has: (/** @type {string} */ name) => known(bag, name),
        set: (/** @type {string} */ name, /** @type {unknown} */ value) => {
          bag[name] = value;
          return value;
        },
        metadata: (/** @type {string} */ name) => Object.freeze({ name, available: known(bag, name), type: typeof bag[name] }),
      }),
      index: 0,
      count: 1,
      log: methods.log,
      warn: methods.warn,
      error: methods.error,
      assert: assertion,
    };
    for (const name of ["page", "frame", "device", "selectors", "target", "targets", "graph"])
      Object.defineProperty(exactus, name, {
        enumerable: true,
        get: () => {
          throw new Error(`exactus.${name} is only available during playback; the preview worker has no page.`);
        },
      });
    Object.freeze(exactus);
    scope.addEventListener("unhandledrejection", rejection => methods.error("Unhandled promise rejection:", rejection.reason));
    /**
     * Describe a thrown value for the host.
     * @param {unknown} thrown Thrown value.
     * @returns {object} Error payload.
     */
    const failure = thrown => {
      const info = thrown !== null && typeof thrown === "object" ? Describer.errorInfo(thrown) : { name: "Uncaught", message: String(thrown), stack: "" };
      return { error: { ...info, location: locate(info.stack) ?? null }, value: Describer.describe(thrown) };
    };
    try {
      mapping = compile(String(code), String(mode));
      const produced = await mapping.run(exactus, methods, flow);
      const returned = typeof produced === "function" && String(mode) === "playback" ? await produced() : produced;
      let json;
      try {
        json = JSON.stringify(returned);
      } catch {
        json = undefined;
      }
      post({
        type: "done",
        result: {
          status: "ok",
          durationMs: performance.now() - started,
          value: Describer.describe(returned),
          jsonSafe: json !== undefined,
          json: json !== undefined && json.length <= 1000000 ? json : null,
        },
      });
    } catch (thrown) {
      post({ type: "done", result: { status: "error", durationMs: performance.now() - started, ...failure(thrown) } });
    }
  };
};
/**
 * Build the complete worker script.
 * @returns {string} Classic-script source for a Blob worker.
 */
export const buildWorkerSource = () =>
  `"use strict";\n${Describer.toString()}\n${ConsoleRecorder.toString()}\n(${workerMain.toString()})();\n`;
export { workerMain };
