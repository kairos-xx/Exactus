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

- [`__init__.py`](__init__.py) — Public API for the Exactus MCP and ngrok service.
- [`__main__.py`](__main__.py) — Run the Exactus MCP and ngrok service.
- [`activity.py`](activity.py) — Track Exactus MCP lifecycle and caller activity for local interfaces.
- [`cli.py`](cli.py) — Command line for the Exactus MCP and ngrok service.
- [`cloudflare.py`](cloudflare.py) — Publish Exactus MCP through a stable OAuth Cloudflare Worker.
- [`environment.py`](environment.py) — Minimal deterministic ``.env`` loading for command-line entry points.
- [`macos_menu.py`](macos_menu.py) — Present Exactus MCP lifecycle and controls in the macOS menu bar.
- [`mantledb.py`](mantledb.py) — Persist the active Exactus public URL through MantleDB.
- [`ngrok.py`](ngrok.py) — Own an ngrok child process and discover its public HTTPS origin.
- [`project_config.py`](project_config.py) — Load Exactus MCP command defaults from project configuration.
- [`runner.py`](runner.py) — Run a constrained Exactus report command for an MCP caller.
- [`service.py`](service.py) — MCP tools, resources, HTTP routes, and bearer protection for Exactus.
- [`startup.py`](startup.py) — Manage native startup for the Exactus MCP wake watcher.
- [`state.py`](state.py) — Mutable per-process state for the Exactus MCP service.
- [`supervisor.py`](supervisor.py) — Run the Exactus MCP asyncio service behind synchronous controls.
- [`wakeup.py`](wakeup.py) — Wake an Exactus MCP service through signed MantleDB commands.
- [`wakeup_cli.py`](wakeup_cli.py) — Run and manage the signed Exactus MCP wake watcher.

### Subdirectories

- [`bridge/`](bridge/README.md) — This Worker is the permanent public OAuth 2.1 endpoint for Exactus MCP. ChatGPT connects to `https://<worker>/mcp`. The Worker authenticates ChatGPT, reads the current ephemeral Quick Tunnel origin from KV, removes the external OAuth bearer token, adds a private origin credential, and streams the request to the local Exactus service.
- [`examples/`](examples/README.md) — This directory contains two executable MCP examples. Both use the official MCP Python client and send the required bearer header.
- [`macos/`](macos/README.md) — This directory contains static resources for the optional native Exactus MCP menu-bar controller in `../macos_menu.py`.
- [`web/`](web/README.md) — The public connection page reports service availability, obtains the public MCP endpoint from `/api/status`, copies it on request, and explains that the bearer token remains in the server terminal. Styling consumes the repository's shared widget token hierarchy.

<!-- exactus:inventory:end -->
