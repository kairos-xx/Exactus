import assert from "node:assert/strict";
import test from "node:test";
import { Router } from "./worker.js";
/** In-memory Worker KV namespace used by the router tests. */
class MemoryKV {
  /** Create an empty in-memory KV namespace. */
  constructor() {
    /** @type {string|null} */
    this.value = null;
    /** @type {Map<string, string>} */
    this.values = new Map();
  }
  /** Read a stored value.
   * @param {string} key Storage key.
   * @returns {Promise<string|null>} Stored value or null.
   */
  async get(key) {
    if (key === "current_backend_url") return this.value;
    return this.values.get(key) ?? null;
  }
  /** Store a value.
   * @param {string} key Storage key.
   * @param {string} value Stored value.
   * @returns {Promise<void>} Completion signal.
   */
  async put(key, value) {
    if (key === "current_backend_url") this.value = value;
    this.values.set(key, value);
  }
  /** Delete a stored value.
   * @param {string} key Storage key.
   * @returns {Promise<void>} Completion signal.
   */
  async delete(key) {
    this.values.delete(key);
  }
}
/** Build isolated Worker bindings.
 * @returns {{ROUTING: MemoryKV, CONTROL_SECRET: string, OAUTH_LOGIN_SECRET: string}} Worker bindings.
 */
const env = () => ({ ROUTING: new MemoryKV(), CONTROL_SECRET: "fixture-secret", OAUTH_LOGIN_SECRET: "oauth-secret" });
test("control endpoint authenticates and stores only Quick Tunnel origins", async () => {
  const bindings = env();
  const unauthorized = await Router.fetch(
    new Request("https://router.workers.dev/_control/backend", { method: "POST" }),
    bindings,
  );
  assert.equal(unauthorized.status, 401);
  const invalid = await Router.fetch(
    new Request("https://router.workers.dev/_control/backend", {
      method: "POST",
      headers: { Authorization: "Bearer fixture-secret" },
      body: JSON.stringify({ url: "https://example.com" }),
    }),
    bindings,
  );
  assert.equal(invalid.status, 400);
  const valid = await Router.fetch(
    new Request("https://router.workers.dev/_control/backend", {
      method: "POST",
      headers: { Authorization: "Bearer fixture-secret" },
      body: JSON.stringify({ url: "https://calm-river.trycloudflare.com" }),
    }),
    bindings,
  );
  assert.equal(valid.status, 200);
  assert.equal(bindings.ROUTING.value, "https://calm-river.trycloudflare.com");
});
test("proxy returns 503 before a backend is published", async () => {
  const response = await Router.fetch(
    new Request("https://router.workers.dev/healthz"),
    env(),
  );
  assert.equal(response.status, 503);
});
test("OAuth discovery advertises DCR, PKCE, and protected MCP resource", async () => {
  const bindings = env();
  const resource = await Router.fetch(new Request("https://router.workers.dev/.well-known/oauth-protected-resource"), bindings);
  const resourceBody = /** @type {{resource:string, authorization_servers:string[]}} */ (await resource.json());
  assert.equal(resourceBody.resource, "https://router.workers.dev/mcp");
  assert.deepEqual(resourceBody.authorization_servers, ["https://router.workers.dev"]);
  const metadata = await Router.fetch(new Request("https://router.workers.dev/.well-known/oauth-authorization-server"), bindings);
  const metadataBody = /** @type {{registration_endpoint:string, code_challenge_methods_supported:string[], authorization_response_iss_parameter_supported:boolean}} */ (await metadata.json());
  assert.equal(metadataBody.registration_endpoint, "https://router.workers.dev/oauth/register");
  assert.deepEqual(metadataBody.code_challenge_methods_supported, ["S256"]);
  assert.equal(metadataBody.authorization_response_iss_parameter_supported, true);
});
test("MCP endpoint challenges unauthenticated requests with resource metadata", async () => {
  const response = await Router.fetch(new Request("https://router.workers.dev/mcp"), env());
  assert.equal(response.status, 401);
  assert.match(response.headers.get("WWW-Authenticate") ?? "", /oauth-protected-resource/);
});
test("dynamic registration accepts ChatGPT HTTPS callbacks", async () => {
  const response = await Router.fetch(new Request("https://router.workers.dev/oauth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ redirect_uris: ["https://chatgpt.com/connector_platform_oauth_redirect"] }),
  }), env());
  assert.equal(response.status, 201);
  const body = /** @type {{client_id:string, token_endpoint_auth_method:string}} */ (await response.json());
  assert.match(body.client_id, /^client_/);
  assert.equal(body.token_endpoint_auth_method, "none");
});
