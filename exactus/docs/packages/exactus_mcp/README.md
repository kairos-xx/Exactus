# Exactus MCP

Exactus MCP exposes the constrained Exactus report tools to ChatGPT through a
stable Cloudflare Worker while the actual service remains bound to loopback on
the local machine.

## Architecture

```text
ChatGPT -- OAuth 2.1 --> Cloudflare Worker (stable workers.dev /mcp)
                              |
                              | KV: current_backend_url
                              v
                     random trycloudflare.com Quick Tunnel
                              |
                              v
                         cloudflared
                              |
                              v
                       127.0.0.1:6100
                              |
                              v
                         Exactus MCP
```

The Worker implements protected-resource discovery, authorization-server
metadata, Dynamic Client Registration, authorization-code + PKCE/S256, bearer
token validation, and resource binding. It strips ChatGPT's OAuth token before
proxying. `CONTROL_SECRET` is added as `X-Exactus-Origin-Secret`; the local
boundary requires that credential for non-loopback MCP traffic, removes it,
normalizes `Host` to `127.0.0.1`, injects the internal bearer credential, and
then lets MCP's DNS-rebinding protection validate the normalized request.

The Quick Tunnel URL may change on every launch. `exactus-mcp-publish` detects
it and updates Worker KV automatically, so ChatGPT always uses the permanent
Worker URL.

## Local configuration

Copy `.env.example` to `.env` at the project root and set:

```text
EXACTUS_MCP_CLOUDFLARE_WORKER_URL=https://exactus-mcp-router.<subdomain>.workers.dev
EXACTUS_MCP_CLOUDFLARE_CONTROL_SECRET=<same value as Worker CONTROL_SECRET>
```

The publisher loads the nearest `.env` automatically. Existing process
environment values take precedence. `.env` must never be committed.

Install `cloudflared`, install the project, then normal operation is one command:

```text
exactus-mcp-publish
```

The publisher starts Exactus MCP without ngrok or the macOS menu controller,
waits for `/health`, starts `cloudflared`, discovers the Quick Tunnel URL,
publishes it to the Worker, prints the stable `/mcp` URL, and restarts and
republishes the tunnel if `cloudflared` exits.

## Worker deployment

The Worker sources are in `bridge/`. Create a KV namespace named `ROUTING`, put
its ID in `bridge/wrangler.toml`, and configure two Worker secrets:
`CONTROL_SECRET` and `OAUTH_LOGIN_SECRET`. Deploy with Wrangler. ChatGPT should
use the Worker's `/mcp` URL and Dynamic Client Registration (DCR).

The Worker backend-control endpoint accepts only authenticated HTTPS
`*.trycloudflare.com` origins. Direct access to the ephemeral Quick Tunnel
cannot invoke MCP because it lacks the private origin credential.

## Legacy components

The older ngrok/MantleDB wake modules remain in the package for compatibility
with existing callers, but the supported ChatGPT publication path is the
Cloudflare Worker + KV + Quick Tunnel publisher described above. The project
configuration sets `ngrok = false` by default.


## Automatic Cloudflare setup

`exactus-mcp-publish` provisions KV, secrets, Worker deployment, `.env`, and the Quick Tunnel automatically.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`DOCS.md`](DOCS.md) — `exactus-mcp` provides a small, auditable remote boundary around Exactus. One command starts a loopback Uvicorn server, creates an ngrok HTTPS tunnel, serves a public connection page, and publishes an authenticated MCP Streamable HTTP endpoint at `/mcp`.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
