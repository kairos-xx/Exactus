# Exactus MCP Cloudflare gateway

This Worker is the permanent public OAuth 2.1 endpoint for Exactus MCP.
ChatGPT connects to `https://<worker>/mcp`. The Worker authenticates ChatGPT,
reads the current ephemeral Quick Tunnel origin from KV, removes the external
OAuth bearer token, adds a private origin credential, and streams the request
to the local Exactus service.

Bindings/secrets:

- KV binding `ROUTING` stores `current_backend_url`, OAuth clients/codes/tokens.
- `CONTROL_SECRET` authenticates both backend publication and Worker -> origin.
- `OAUTH_LOGIN_SECRET` is entered only on the Worker authorization page.

`CONTROL_SECRET` and `OAUTH_LOGIN_SECRET` must be different random secrets.
The local `.env` contains only `CONTROL_SECRET`; `OAUTH_LOGIN_SECRET` stays in
Cloudflare.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`package.json`](package.json) — Provide package json content.
- [`router.test.js`](router.test.js) — In-memory Worker KV namespace used by the router tests.
- [`worker.js`](worker.js) — Provide worker js content.
- [`wrangler.toml`](wrangler.toml) — Provide wrangler toml content.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
