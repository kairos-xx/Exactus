import { mountRunner } from "../../index.js";
const query = new URLSearchParams(location.search);
const theme = query.get("theme");
if (theme === "light" || theme === "dark") document.documentElement.setAttribute("data-theme", theme);
if (query.has("embed")) document.documentElement.setAttribute("data-embed", "");
const SAMPLES = new Map(Object.entries({
  variables: `const id = exactus.vars.get("user/id");
const size = exactus.vars.get("pagination/pageSize");
console.log("loading", id, { size });
const pages = Math.ceil(120 / size);
console.table(Array.from({ length: pages }, (_, page) => ({ page: page + 1, offset: page * size })));
return { id, pages };`,
  expression: "[3, 1, 2].map(n => n * 2).sort((a, b) => a - b)",
  async: `console.time("wait");
await new Promise(resolve => setTimeout(resolve, 300));
console.timeEnd("wait");
return "finished";`,
  error: `const scheme = exactus.vars.get("auth/scheme");
console.warn("about to read a missing field");
return scheme.profile.name;`,
  assert: `const size = exactus.vars.get("pagination/pageSize");
exactus.assert(size > 100, "page size must exceed 100");`,
  loop: "while (true) {}",
}));
const host = document.querySelector('[data-component="runner-host"]');
const carrier = document.querySelector('[data-component="snippet"]');
const saved = document.querySelector('[data-component="saved"]');
if (!(host instanceof HTMLElement) || !(carrier instanceof HTMLTextAreaElement) || !(saved instanceof HTMLElement))
  throw new Error("The demo markup is incomplete.");
const runner = mountRunner(carrier, {
  source: SAMPLES.get("variables") ?? "",
  outputName: "result",
  timeoutMs: 2000,
  variables: [
    { name: "user/id", value: "usr_28491" },
    { name: "pagination/pageSize", value: 25 },
    { name: "auth/scheme", value: "Bearer" },
    { name: "auth/apiToken", value: "sk_demo_12345678", secret: true },
  ],
});
runner.on("result", result => {
  saved.textContent = result.status === "ok" && result.saveAs && result.jsonSafe
    ? `Saved ${result.saveAs} = ${result.json}`
    : `Run ${result.status}; nothing saved.`;
});
if (query.has("run")) runner.run();
document.addEventListener("click", event => {
  const button = event.target instanceof Element ? event.target.closest("button") : null;
  const sample = button?.getAttribute("data-sample");
  const width = button?.getAttribute("data-width");
  if (sample) {
    runner.setValue(SAMPLES.get(sample) ?? "");
    runner.run();
  }
  if (width) {
    host.setAttribute("data-size", width);
    for (const toggle of document.querySelectorAll("[data-width]")) toggle.setAttribute("aria-pressed", String(toggle === button));
  }
});
