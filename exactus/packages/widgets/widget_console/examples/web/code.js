import { mountConsole } from "../../index.js";
const query = new URLSearchParams(location.search);
const theme = query.get("theme");
if (theme === "light" || theme === "dark") document.documentElement.setAttribute("data-theme", theme);
if (query.has("embed")) document.documentElement.setAttribute("data-embed", "");
const host = document.querySelector('[data-component="console-host"]');
if (!(host instanceof HTMLElement)) throw new Error("Console host is missing.");
const view = mountConsole(host, { timestamps: query.has("time") });
const release = view.capture();
window.addEventListener("pagehide", release);
/** Open the Server-Timing-like sample used by several actions. */
const sample = () => ({
  id: "req_8f2c1",
  ok: true,
  user: { id: 28491, name: "Ada Lovelace", roles: ["admin", "developer"], profile: { timezone: null } },
  tags: new Set(["api", "console"]),
  when: new Date(0),
  pattern: /ab+c/gi,
  limit: 25n,
  handler: () => {},
});
/** @type {Record<string, () => void>} */
const ACTIONS = {
  log: () => console.log("Plain text message", 42, true, null, undefined),
  levels: () => {
    console.debug("debug detail");
    console.info("service ready");
    console.warn("cache is stale");
    console.error("request failed", { status: 502 });
  },
  object: () => console.log("response", sample()),
  collections: () => console.log(new Map(/** @type {[unknown, unknown][]} */ ([["alpha", { n: 1 }], [{ key: true }, [1, 2, 3]]])), new Set([1, "two", [3]])),
  error: () => console.error(new RangeError("index out of range", { cause: new Error("lookup failed") })),
  table: () => console.table([{ name: "Ada", role: "admin", active: true }, { name: "Linus", role: "dev" }, { name: "Grace", role: "admin", active: false }]),
  group: () => {
    console.group("fetch users");
    console.log("page", 1);
    console.group("retry");
    console.warn("timeout, retrying");
    console.groupEnd();
    console.groupEnd();
  },
  repeat: () => {
    for (let index = 0; index < 4; index += 1) console.log("tick");
  },
  format: () => console.log("%s has %d open items (%c%s)", "Ada", 3, "color: red", "styled", { extra: true }),
  uncaught: () => setTimeout(() => {
    throw new TypeError("Cannot read properties of undefined");
  }, 0),
  flood: () => {
    for (let index = 0; index < 1200; index += 1) console.log(`line ${index + 1}`);
  },
};
document.addEventListener("click", event => {
  const button = event.target instanceof Element ? event.target.closest("button[data-action]") : null;
  const action = button?.getAttribute("data-action");
  if (action) ACTIONS[action]?.();
});
