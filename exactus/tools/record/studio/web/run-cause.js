/** How a run explains a failed or tolerated action.
 *
 * An action that fails with "continue with the next action" is recorded as a
 * warning. Both carry a cause, so the author can see the phase it failed in,
 * what was expected and what was found, the CSS it resolved to, and what the
 * browser said. Plain DOM builders, like selectors-panel.js.
 */
/** The phases a cause can name, in the words the author would use.
 * @type {Readonly<Record<string,string>>}
 */
const PHASES = Object.freeze({
  resolve: "Selector",
  count: "Match count",
  check: "Check",
  compile: "Selector CSS",
  execute: "Action",
  gate: "Wait",
  timeout: "Timed out",
  drift: "Changed since the baseline",
});
/** The worst status first, so a step with several results shows the one to read.
 * @type {readonly string[]}
 */
const SEVERITY = Object.freeze(["failed", "warning", "skipped", "succeeded"]);
/** Build an element.
 * @param {string} tag
 * @param {string} [className]
 * @param {string} [text]
 * @returns {HTMLElement}
 */
const make = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
/** The most serious status among a step's records.
 * @param {RunRecord[]} records
 * @returns {string}
 */
export const worstStatus = records =>
  SEVERITY.find(status =>
    records.some(record => record.status === status),
  ) ?? "";
/** One-line text for a record: its message, or its phase when it has none.
 * @param {RunRecord} record
 * @returns {string}
 */
export const causeSummary = record => {
  const cause = record.cause;
  const phase = cause?.phase ? (PHASES[cause.phase] ?? cause.phase) : "";
  const message = cause?.message || record.error || "";
  if (phase && message && !message.startsWith(phase))
    return `${phase}: ${message}`;
  return message || phase;
};
/** The facts of a cause as label and value pairs, empty ones left out.
 * @param {RunCause} cause
 * @returns {[string,string][]}
 */
export const causeFacts = cause => {
  /** @type {[string,string][]} */
  const facts = [];
  /** Append one non-empty fact row.
   * @param {string} label Fact name.
   * @param {unknown} value Fact value skipped when empty.
   * @returns {void}
   */
  const add = (label, value) => {
    if (value === null || value === undefined || value === "") return;
    facts.push([label, String(value)]);
  };
  add("Phase", cause.phase ? (PHASES[cause.phase] ?? cause.phase) : "");
  add("Expression", cause.expression);
  if (cause.expected_count !== undefined || cause.found_count !== undefined)
    add(
      "Expected and found",
      `${cause.expected_count === null ? "one or more" : (cause.expected_count ?? "?")} expected, ${cause.found_count ?? "?"} found`,
    );
  add("Resolved to", cause.resolved_css);
  add(
    "Match number",
    typeof cause.target_index === "number" ? cause.target_index + 1 : "",
  );
  add("Waited", cause.timeout_ms ? `${cause.timeout_ms} ms` : "");
  for (const failed of cause.failed ?? [])
    add(`Match ${failed.index + 1} failed`, (failed.checks ?? []).join(", "));
  for (const change of cause.changes ?? [])
    add(
      `${change.field} changed`,
      `${JSON.stringify(change.baseline)} to ${JSON.stringify(change.current)}`,
    );
  add("Browser said", cause.playwright_error);
  return facts;
};
/** Show the latest run's results for one step.
 * @param {HTMLElement} target
 * @param {RunRecord[]} records Records of this step in the latest run.
 * @returns {void}
 */
export const renderLastRun = (target, records) => {
  target.replaceChildren();
  target.hidden = !records.length;
  if (!records.length) return;
  target.append(make("h3", "", "Last run"));
  for (const record of records) {
    const item = make("div", "last-run-item");
    item.setAttribute("data-state", record.status);
    const head = make("div", "last-run-head");
    head.append(make("strong", "", record.status));
    if (record.unit)
      head.append(
        make(
          "small",
          "",
          `match ${record.unit.index + 1} of ${record.unit.count}`,
        ),
      );
    item.append(head);
    const summary = causeSummary(record);
    if (summary) item.append(make("p", "last-run-summary", summary));
    if (record.cause) {
      const facts = causeFacts(record.cause);
      if (facts.length) {
        const list = make("dl", "last-run-facts");
        for (const [label, value] of facts)
          list.append(make("dt", "", label), make("dd", "", value));
        item.append(list);
      }
    }
    const lines = (record.streams ?? []).filter(
      entry => entry.source === "snippet",
    );
    for (const entry of lines)
      item.append(make("p", `last-run-line ${entry.level}`, entry.message));
    target.append(item);
  }
};
