/**
 * Return a required HTML element.
 *
 * @param {string} id - Element identifier.
 * @returns {HTMLElement} Matching element.
 * @throws {Error} When the document contract is incomplete.
 */
const requiredElement = id => {
  const element = document.getElementById(id);
  if (!(element instanceof HTMLElement))
    throw new Error(`Missing required element: ${id}`);
  return element;
};
const endpoint = requiredElement("mcp-url");
const copyButton = requiredElement("copy-endpoint");
const copyStatus = requiredElement("copy-status");
const totalCalls = requiredElement("total-calls");
const activeCalls = requiredElement("active-calls");
const servicePhase = requiredElement("service-phase");
const activityRows = requiredElement("activity-rows");
const activityNote = requiredElement("activity-note");
const refreshActivity = requiredElement("refresh-activity");
const refreshIntervalMilliseconds = 3000;
/**
 * Render one text table cell.
 *
 * @param {string} value - Safe text value.
 * @returns {HTMLTableCellElement} Constructed cell.
 */
const textCell = value => {
  const cell = document.createElement("td");
  cell.textContent = value;
  return cell;
};
/**
 * Render redacted request and response activity.
 *
 * @param {unknown} value - Untrusted activity response.
 * @returns {void}
 * @throws {Error} When the activity response does not match its public contract.
 */
const renderActivity = value => {
  if (!value || typeof value !== "object")
    throw new Error("Activity response is not an object");
  const payload = value;
  if (
    !("events" in payload) ||
    !Array.isArray(payload.events) ||
    !("call_count" in payload) ||
    !("active_calls" in payload) ||
    !("phase" in payload)
  )
    throw new Error("Activity response is incomplete");
  totalCalls.textContent = String(payload.call_count);
  activeCalls.textContent = String(payload.active_calls);
  servicePhase.textContent = String(payload.phase);
  activityRows.replaceChildren();
  if (payload.events.length === 0) {
    const row = document.createElement("tr");
    const cell = textCell("No MCP calls yet.");
    cell.colSpan = 6;
    row.append(cell);
    activityRows.append(row);
    return;
  }
  payload.events.forEach(event => {
    if (!event || typeof event !== "object") return;
    const row = document.createElement("tr");
    const startedAt = "started_at" in event ? String(event.started_at) : "";
    const startedDate = new Date(startedAt);
    const request = "request" in event ? event.request : {};
    const response = "response" in event ? event.response : {};
    row.append(
      textCell(Number.isNaN(startedDate.valueOf()) ? "—" : startedDate.toLocaleTimeString()),
      textCell("tool" in event ? String(event.tool) : "Unknown"),
      textCell("state" in event ? String(event.state) : "Unknown"),
      textCell(
        "duration_ms" in event && event.duration_ms !== null
          ? `${String(event.duration_ms)} ms`
          : "In progress",
      ),
      textCell(JSON.stringify(request)),
      textCell(JSON.stringify(response)),
    );
    activityRows.append(row);
  });
};
/**
 * Load the redacted activity feed.
 *
 * @returns {Promise<void>} Completion after rendering.
 * @throws {Error} When activity cannot be loaded or validated.
 */
const loadActivity = async () => {
  const response = await fetch("/api/activity", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw new Error(`Activity request failed: ${response.status}`);
  renderActivity(await response.json());
  activityNote.textContent = "Secrets and raw report bodies are excluded.";
};
/**
 * Load public service metadata without exposing credentials.
 *
 * @returns {Promise<void>} Completion after the endpoint is rendered.
 * @throws {Error} When status cannot be loaded or validated.
 */
const loadStatus = async () => {
  const response = await fetch("/api/status", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw new Error(`Status request failed: ${response.status}`);
  /** @type {{mcp_url?: unknown}} */
  const payload = await response.json();
  if (typeof payload.mcp_url !== "string")
    throw new Error("Status response omitted the MCP URL");
  endpoint.textContent = payload.mcp_url;
};
copyButton.addEventListener("click", async () => {
  const value = endpoint.textContent;
  if (!value || value === "Loading endpoint…") return;
  try {
    await navigator.clipboard.writeText(value);
    copyStatus.textContent = "Address copied.";
  } catch {
    copyStatus.textContent = "Copy failed. Select the address manually.";
  }
});
refreshActivity.addEventListener("click", async () => {
  try {
    await loadActivity();
  } catch {
    activityNote.textContent = "Activity unavailable. Try again.";
  }
});
try {
  await loadStatus();
} catch {
  endpoint.textContent = "Address unavailable";
  copyStatus.textContent = "Reload after the public tunnel is ready.";
}
try {
  await loadActivity();
} catch {
  activityNote.textContent = "Activity unavailable. Try again.";
}
window.setInterval(async () => {
  try {
    await loadActivity();
  } catch {
    activityNote.textContent = "Live refresh paused. Use Refresh log.";
  }
}, refreshIntervalMilliseconds);
export {};
