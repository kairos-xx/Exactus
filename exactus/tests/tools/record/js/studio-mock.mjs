/** Deterministic Flow Studio service for browser tests: one workspace, two flows and a command log.
 *
 * Shared by `studio.test.mjs` and the stylesheet A/B check (`styles-ab.test.mjs`).
 */
export const flow = {
  id: "flow-one",
  name: "Checkout",
  device_modes: ["shared"],
  task_description: "Save an order",
  expected_behavior: "Saved",
  capture_record_images: true,
  capture_play_images: true,
  parameters: [
    {
      name: "user",
      value_type: "string",
      default_expression: "guest",
    },
  ],
  outputs: [
    {
      name: "order",
      value_type: "string",
      source: "url",
    },
  ],
  events: [
    {
      id: "open",
      kind: "url_change",
      url: "http://localhost/",
      label: "Open app",
      layer: "navigation",
      elapsed_ms: 0,
    },
    {
      id: "save",
      kind: "click",
      selector: "#save",
      label: "Save order",
      layer: "interaction",
      elapsed_ms: 1000,
      contract: {
        postconditions: [
          {
            id: "check",
            kind: "dom_text",
            target: "#result",
            expected: "Saved",
          },
        ],
      },
    },
    {
      id: "shot",
      kind: "javascript",
      payload: "__screenshot__",
      label: "Screenshot",
      layer: "capture",
      elapsed_ms: 2000,
    },
  ],
};
/** Authorize a real editor against a deterministic command service.
 * @param {any} page Playwright page driving the editor window.
 * @param {string} url Studio launch URL including the bootstrap token.
 * @param {Record<string, (payload: any, snapshot: any) => void>} [handlers] Per-command changes to the snapshot, as the real service would make.
 * @returns {Promise<{commands: any[], snapshot: any}>} Recorded commands and emitted events.
 * @throws {Error} When the studio editor fails to start or render.
 */
export const studio = async (page, url, handlers = {}) => {
  /** @type {any[]} */
  const commands = [];
  /** @type {string[]} */
  const startupErrors = [];
  page.on("pageerror", (/** @type {any} */ error) =>
    startupErrors.push(error.message),
  );
  const snapshot = {
    revision: 1,
    active_flow_id: flow.id,
    target_url: "http://localhost/",
    recorder_clients: 1,
    viewport: {
      width: 1440,
      height: 900,
    },
    device_mode: "desktop",
    target_state: "ready",
    target_address: "http://localhost/",
    target_service: { state: "idle" },
    target_check: null,
    target_suggestion: null,
    profile_schema: {
      fields: [
        {
          id: "width",
          label: "Width",
          kind: "length",
          unit: "px",
          min: 160,
          max: 8192,
        },
        {
          id: "height",
          label: "Height",
          kind: "length",
          unit: "px",
          min: 160,
          max: 8192,
        },
        {
          id: "scale",
          label: "Resolution",
          kind: "number",
          unit: "dppx",
          min: 0.5,
          max: 4,
        },
        {
          id: "screen_width",
          label: "Device width",
          kind: "length",
          unit: "px",
          min: 160,
          max: 8192,
          optional: true,
        },
        {
          id: "screen_height",
          label: "Device height",
          kind: "length",
          unit: "px",
          min: 160,
          max: 8192,
          optional: true,
        },
        {
          id: "touch",
          label: "Primary input",
          kind: "choice",
          options: ["mouse", "touch"],
        },
        { id: "mobile", label: "Mobile browser", kind: "toggle" },
        {
          id: "prefers-color-scheme",
          label: "Color scheme",
          kind: "choice",
          options: ["light", "dark"],
          group: "media",
        },
      ],
      unsupported: ["monochrome"],
    },
    workspace: {
      profiles: [
        {
          id: "desktop",
          name: "Desktop",
          width: 1440,
          height: 900,
          scale: 1,
          screen_width: null,
          screen_height: null,
          touch: false,
          mobile: false,
          media: {},
        },
        {
          id: "mobile",
          name: "Mobile",
          width: 390,
          height: 844,
          scale: 1,
          screen_width: null,
          screen_height: null,
          touch: false,
          mobile: false,
          media: {},
        },
      ],
      target: {
        mode: "url",
        url: "http://localhost",
        port: null,
        command: [],
        cwd: "",
        service_port: null,
        path: "/",
      },
      flows: [
        flow,
        {
          ...flow,
          id: "second",
          name: "Cleanup",
          events: [],
        },
      ],
      edges: [
        {
          source: flow.id,
          target: "second",
          mode: "always",
          condition_expression: "",
          priority: 1,
          max_traversals: 1,
        },
      ],
      runs: [
        {
          id: "run-one",
          status: "failed",
          initial_flow_id: flow.id,
          current_flow_id: flow.id,
          device_mode: "desktop",
          failure_reason: "Missing confirmation",
          action_records: [
            {
              event_id: "save",
              status: "failed",
              error: "Not saved",
            },
          ],
        },
      ],
      screenshots: [
        {
          id: "screen",
          flow_id: flow.id,
          event_id: "shot",
          path: "screenshots/test.png",
          phase: "play",
          width: 1440,
          height: 900,
        },
      ],
    },
  };
  await page.addInitScript(() => {
    /** @type {any} */
    (window).EventSource = class {
      constructor() {
        /** @type {any} */
        (window).studioEvents = this;
      }
    };
  });
  await page.route("**/api/**", async (/** @type {any} */ route) => {
    if (route.request().url().includes("/command")) {
      const request = route.request().postDataJSON();
      commands.push(request);
      if (request.command === "flow.select")
        snapshot.active_flow_id = request.payload.flow_id;
      handlers[request.command]?.(request.payload, snapshot);
      const result =
        request.command === "recorder.record"
          ? { ...snapshot, recording_state: "recording" }
          : request.command === "recorder.pause"
            ? { ...snapshot, recording_state: "paused" }
            : snapshot;
      await route.fulfill({
        json: {
          protocol: 1,
          id: request.id,
          ok: true,
          result,
        },
      });
    } else
      await route.fulfill({
        json: snapshot,
      });
  });
  await page.goto(
    `${url}/exactus/tools/record/studio/web/index.html#token=test`,
  );
  try {
    await page.waitForFunction(() =>
      /** @type {HTMLElement} */
      (document.getElementById("flows")).textContent.includes("Checkout"),
    );
  } catch (error) {
    throw new Error(`Studio startup failed: ${startupErrors.join(" | ")}`, {
      cause: error,
    });
  }
  return {
    commands,
    snapshot,
  };
};
/** Kinds that need a target before they can run, as the real service enforces. */
const NEEDS_TARGET = Object.freeze([
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
  "snapshot",
  "extract_value",
]);
/** Settings the real service copies from a command onto an action.
 * @type {readonly string[]}
 */
const ACTION_SETTINGS = Object.freeze([
  "selector",
  "selector_id",
  "url",
  "payload",
  "method",
  "output_variable",
  "when_expression",
]);
/** Command handlers that make the mock add and change actions like the real service.
 * Pass them as the third argument of {@link studio}.
 * @type {Record<string, (payload: any, snapshot: any) => void>}
 */
export const actionHandlers = Object.freeze({
  "event.add": (payload, snapshot) => {
    const flows = snapshot.workspace.flows;
    const current = flows[0];
    const added = {
      id: `added-${current.events.length}`,
      kind: payload.kind,
      label: payload.kind,
      layer: "interaction",
      elapsed_ms: 3000 + current.events.length,
      incomplete:
        NEEDS_TARGET.includes(payload.kind) &&
        !payload.selector &&
        !payload.selector_id,
      ...Object.fromEntries(
        ACTION_SETTINGS.filter(key => payload[key]).map(key => [key, payload[key]]),
      ),
    };
    flows[0] = { ...current, events: [...current.events, added] };
    snapshot.revision += 1;
  },
  "event.configure": (payload, snapshot) => {
    const flows = snapshot.workspace.flows;
    flows[0] = {
      ...flows[0],
      events: flows[0].events.map((/** @type {any} */ item) =>
        item.id === payload.event_id
          ? {
              ...item,
              ...Object.fromEntries(
                ACTION_SETTINGS.map(key => [key, payload[key] || undefined]),
              ),
              incomplete: false,
            }
          : item,
      ),
    };
    snapshot.revision += 1;
  },
  "event.update": (payload, snapshot) => {
    const flows = snapshot.workspace.flows;
    flows[0] = {
      ...flows[0],
      events: flows[0].events.map((/** @type {any} */ item) =>
        item.id === payload.event_id
          ? { ...item, when_expression: payload.when_expression || item.when_expression }
          : item,
      ),
    };
    snapshot.revision += 1;
  },
});
