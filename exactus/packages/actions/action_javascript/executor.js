/** Host side of snippet execution: one disposable Worker per run. */
import { buildWorkerSource } from "./worker_source.js";
/** @typedef {import("../../widgets/widget_console/describe.js").Descriptor} Descriptor */
/** @typedef {import("../../widgets/widget_console/console_view.js").EntryInput} EntryInput */
/**
 * @typedef {object} RunRequest
 * @property {string} code Snippet source.
 * @property {"auto"|"playback"|"expression"|"statements"} mode How the snippet becomes a function.
 * @property {Record<string, unknown>} variables Values read by `exactus.vars` and `__EXACTUS_FLOW__.vars`.
 * @property {Record<string, unknown>} context Sections `project`, `context`, `flow`, `run`, `action` and `inputs` of `exactus`.
 * @property {number} timeoutMs Wall-clock limit before the worker is terminated.
 */
/**
 * @typedef {object} RunError
 * @property {string} name Error name.
 * @property {string} message Error message.
 * @property {string} stack Stack text.
 * @property {{line:number, column:number}|null} [location] Position in the snippet.
 */
/**
 * @typedef {object} RunResult
 * @property {"ok"|"error"|"timeout"|"cancelled"} status How the run ended.
 * @property {number} durationMs Elapsed time.
 * @property {Descriptor} [value] The return value, or the thrown value.
 * @property {boolean} [jsonSafe] Whether the return value survives JSON.
 * @property {string|null} [json] JSON text of the return value when safe.
 * @property {RunError} [error] Error details for failures.
 */
/**
 * @typedef {object} RunHandlers
 * @property {(entry:EntryInput)=>void} onEntry Receive one console entry.
 * @property {()=>void} onClear Receive a `console.clear()`.
 */
/**
 * @typedef {object} RunHandle
 * @property {Promise<RunResult>} promise Settles once, with the final result.
 * @property {()=>void} cancel Stop the run.
 */
/** @typedef {(request:RunRequest, handlers:RunHandlers)=>RunHandle} Execute */
/** Execute JavaScript snippets inside a disposable Worker. */
export class WorkerExecutor {
  /**
   * Run a snippet in a fresh Worker.
   * @type {Execute}
   */
  static run = (request, handlers) => {
    const started = performance.now();
    const url = URL.createObjectURL(new Blob([buildWorkerSource()], { type: "text/javascript" }));
    const worker = new Worker(url);
    /** @type {()=>void} */
    let cancel = () => {};
    /** @type {Promise<RunResult>} */
    const promise = new Promise(resolve => {
      /** @type {{settled:boolean, timer:ReturnType<typeof setTimeout>|undefined}} */
      const state = { settled: false, timer: undefined };
      /** @param {RunResult} result Final result. */
      const finish = result => {
        if (state.settled) return;
        state.settled = true;
        clearTimeout(state.timer);
        worker.terminate();
        URL.revokeObjectURL(url);
        resolve(result);
      };
      state.timer = setTimeout(() => finish({ status: "timeout", durationMs: performance.now() - started }), request.timeoutMs);
      const cancelRun = () => {
        finish({ status: "cancelled", durationMs: performance.now() - started });
      };
      cancel = cancelRun;
      worker.onmessage = ({ data }) => {
        if (data.type === "entry") handlers.onEntry(data.entry);
        else if (data.type === "clear") handlers.onClear();
        else if (data.type === "done") finish(data.result);
      };
      worker.onerror = event => {
        event.preventDefault();
        finish({
          status: "error",
          durationMs: performance.now() - started,
          error: { name: "Error", message: event.message || "The snippet crashed the worker.", stack: "", location: null },
        });
      };
      worker.postMessage({ code: request.code, mode: request.mode, variables: request.variables, context: request.context });
    });
    return { promise, cancel: () => cancel() };
  };
}
