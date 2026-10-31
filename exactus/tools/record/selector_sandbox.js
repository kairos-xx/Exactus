/**
 * Run a JavaScript action in the engine's isolated world.
 *
 * Evaluated as a function expression and called with one argument:
 * `{script, definitions, vars, logs, warnings, errors, flowId, actionId,
 * runId, targets, indices, count}`. It runs the script once per index (all at
 * the same time) and returns `{results, vars}` as plain JSON.
 */
/** @param {SandboxContext} ctx */
async ctx => {
  const Engine = /** @type {any} */ (globalThis).__EXACTUS_ES__;
  const engine = new Engine(document, { deep: true });
  for (const [name, expression] of Object.entries(ctx.definitions)) {
    try {
      engine.define(name, expression);
    } catch {
      // The resolver already reports selectors that cannot be defined.
    }
  }
  const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor;
  const names = [
    "document",
    "window",
    "globalThis",
    "self",
    "exactus",
    "__EXACTUS_FLOW__",
  ];
  /** Compile a snippet, preferring expression form.
   * @param {string} script Snippet source.
   * @returns {Function}
   */
  const compile = script => {
    try {
      return new AsyncFunction(...names, `return (${script}\n);`);
    } catch {
      return new AsyncFunction(...names, script);
    }
  };
  /** First line of an error message.
   * @param {any} error Caught value.
   * @returns {string}
   */
  const firstLine = error =>
    String(error?.message ?? error).split("\n")[0] ?? "";
  let run;
  try {
    run = compile(ctx.script);
  } catch (error) {
    return {
      results: ctx.indices.map(index => ({
        index,
        value: null,
        error: firstLine(error),
        out: [],
      })),
      vars: ctx.vars,
    };
  }
  /** Format one logged value for the stream.
   * @param {unknown} part Value to format.
   * @returns {string}
   */
  const format = part => {
    if (typeof part === "string") return part;
    try {
      return JSON.stringify(part) ?? String(part);
    } catch {
      return String(part);
    }
  };
  const facade = new Proxy(document, {
    get: (target, key) => {
      if (key === "querySelector") {
        return (/** @type {string} */ text) => engine.queryOne(text);
      }
      if (key === "querySelectorAll") {
        return (/** @type {string} */ text) => engine.query(text);
      }
      const value = Reflect.get(target, key, target);
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
  const sandboxWindow = new Proxy(window, {
    get: (target, key) => {
      if (key === "document") return facade;
      if (key === "window" || key === "self" || key === "globalThis")
        return sandboxWindow;
      const value = Reflect.get(target, key, target);
      return typeof value === "function" ? value.bind(target) : value;
    },
    set: (target, key, value) => Reflect.set(target, key, value, target),
  });
  const targets = ctx.targets.map(css => engine.queryChain(css)[0] ?? null);
  /** @type {Record<SandboxLevel, SandboxLogEntry[]>} */
  const history = {
    log: ctx.logs,
    warn: ctx.warnings,
    error: ctx.errors,
  };
  /** @type {Record<SandboxLevel, "logs"|"warnings"|"errors">} */
  const sources = { log: "logs", warn: "warnings", error: "errors" };
  const results = await Promise.all(
    ctx.indices.map(async index => {
      /** @type {SandboxLogEntry[]} */
      const out = [];
      const note =
        (/** @type {SandboxLevel} */ level) =>
        (/** @type {unknown[]} */ ...parts) => {
          const entry = {
            level,
            message: parts.map(format).join(" "),
            at: Date.now(),
          };
          out.push(entry);
          history[level].push(entry);
        };
      const flow = {
        id: ctx.flowId,
        flowId: ctx.flowId,
        actionId: ctx.actionId,
        runId: ctx.runId,
        index,
        count: ctx.count,
        targets,
        target: targets[index] ?? null,
        vars: ctx.vars,
        log: note("log"),
        warn: note("warn"),
        error: note("error"),
        assert: (
          /** @type {unknown} */ condition,
          /** @type {string|undefined} */ message,
        ) => {
          if (!condition) throw new Error(message ?? "Assertion failed.");
        },
      };
      const exactus = Object.freeze({
        project: Object.freeze({ ...ctx.project }),
        context: Object.freeze({ ...ctx.context }),
        flow: Object.freeze({ id: ctx.flowId, name: ctx.flowName }),
        graph: null,
        run: Object.freeze({ id: ctx.runId, mode: "playback", attempt: 1 }),
        action: Object.freeze({
          id: ctx.actionId,
          kind: ctx.actionKind,
          label: ctx.actionLabel,
          attempt: 1,
        }),
        page: Object.freeze({
          id: "main",
          url: window.location.href,
          origin: window.location.origin,
          title: document.title,
          isPopup: Boolean(window.opener),
        }),
        frame: Object.freeze({
          id: window === window.top ? "main" : "frame",
          url: window.location.href,
          name: window.name,
          isMain: window === window.top,
        }),
        device: Object.freeze({
          profileId: ctx.context.id,
          viewport: Object.freeze({
            width: window.innerWidth,
            height: window.innerHeight,
          }),
          orientation: window.innerWidth >= window.innerHeight
            ? "landscape"
            : "portrait",
          deviceScaleFactor: window.devicePixelRatio,
          touch: navigator.maxTouchPoints > 0,
          mobile: /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent),
          userAgent: navigator.userAgent,
          locale: navigator.language,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          colorScheme: window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light",
          platform: navigator.platform,
        }),
        inputs: Object.freeze({}),
        vars: Object.freeze({
          get: (/** @type {string} */ name) => ctx.vars[name],
          has: (/** @type {string} */ name) => Object.hasOwn(ctx.vars, name),
          set: (/** @type {string} */ name, /** @type {unknown} */ value) => {
            ctx.vars[name] = value;
            return value;
          },
          metadata: (/** @type {string} */ name) => Object.freeze({
            name,
            available: Object.hasOwn(ctx.vars, name),
            type: typeof ctx.vars[name],
          }),
        }),
        selectors: Object.freeze({
          query: (/** @type {string} */ source) => engine.query(source),
          queryOne: (/** @type {string} */ source) => engine.queryOne(source),
          describe: (/** @type {string} */ source) => Object.freeze({ source }),
        }),
        target: targets[index] ?? null,
        targets: Object.freeze([...targets]),
        index,
        count: ctx.count,
        logs: Object.freeze([...ctx.logs]),
        warnings: Object.freeze([...ctx.warnings]),
        errors: Object.freeze([...ctx.errors]),
        log: note("log"),
        warn: note("warn"),
        error: note("error"),
        assert: flow.assert,
      });
      for (const [level, property] of /** @type {[SandboxLevel, string][]} */ (
        Object.entries(sources)
      ))
        Object.defineProperty(flow, property, {
          get: () => history[level],
          enumerable: true,
        });
      try {
        const returned = await run(
          facade,
          sandboxWindow,
          sandboxWindow,
          sandboxWindow,
          exactus,
          flow,
        );
        const value =
          typeof returned === "function" ? await returned() : returned;
        let json = null;
        try {
          json = JSON.parse(JSON.stringify(value ?? null));
        } catch {
          json = String(value);
        }
        return { index, value: json, error: null, out };
      } catch (error) {
        return { index, value: null, error: firstLine(error), out };
      }
    }),
  );
  return { results, vars: ctx.vars };
};
