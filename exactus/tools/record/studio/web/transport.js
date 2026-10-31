/** Connect one editor tab to the authenticated loopback service. */
export class StudioTransport {
  client = crypto.randomUUID();
  /** @type {((message:string)=>void)|null} */
  listener = null;
  /** @type {EventSource|null} */
  events = null;
  outbound = {
    /** @param {(message:string)=>void} handler */
    connect: handler => {
      this.listener = handler;
    },
  };
  /** Accept an optional legacy bootstrap token and open the event stream.
   * @returns {Promise<void>}
   * @throws {Error} When the local Studio session cannot be established.
   */
  async connect() {
    const token = new URLSearchParams(location.hash.slice(1)).get("token");
    if (token) {
      history.replaceState(null, "", location.pathname);
      const reply = await fetch("/api/session", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: "{}",
      });
      if (!reply.ok)
        throw new Error(
          "Studio authorization failed. Open the launch link again.",
        );
    }
    const state = await fetch(
      `/api/snapshot?client=${encodeURIComponent(this.client)}`,
    );
    if (!state.ok)
      throw new Error(
        "Studio session unavailable. Refresh the local Studio page.",
      );
    this.events = new EventSource(
      `/events?client=${encodeURIComponent(this.client)}`,
    );
    this.events.onmessage = event => this.listener?.(event.data);
    this.events.onerror = () => {
      const status = document.getElementById("status");
      if (status) status.textContent = "Reconnecting to Studio…";
    };
  }
  /** Queue a command without surfacing delivery failures.
   * @param {string} message Serialized command request.
   * @returns {void}
   */
  postMessage(message) {
    this.send(message).catch(() => undefined);
  }
  /** Deliver a command request and apply the acknowledged reply.
   * @param {string} message Serialized command request.
   * @returns {Promise<void>}
   */
  async send(message) {
    const request = JSON.parse(message);
    try {
      const response = await fetch("/api/command", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Studio-Client": this.client,
        },
        body: message,
      });
      this.listener?.(JSON.stringify(await response.json()));
    } catch {
      this.listener?.(
        JSON.stringify({
          protocol: 1,
          id: request.id,
          ok: false,
          error: "Studio connection interrupted. Reconnect before retrying.",
        }),
      );
    }
  }
}
