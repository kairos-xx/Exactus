# Exactus MCP service

## Purpose

`exactus-mcp` provides a small, auditable remote boundary around Exactus. One
command starts a loopback Uvicorn server, creates an ngrok HTTPS tunnel, serves
a public connection page, and publishes an authenticated MCP Streamable HTTP
endpoint at `/mcp`.

The public HTML page is informational. It proves the service is online and
shows the MCP endpoint, but never returns the bearer token. The MCP endpoint
requires the token printed in the launching terminal.

## Requirements

- Python 3.13 or newer;
- the Exactus package and its declared `mcp>=2.3,<3` dependency;
- the ngrok v3 executable on `PATH`;
- an authenticated ngrok installation with a valid local configuration;
- a project root containing the policy and source files Exactus should inspect.

The service never downloads ngrok and never modifies ngrok authentication. To
verify the prerequisite independently, run:

```shell
ngrok version
ngrok config check
```

## Start the service

From an Exactus source checkout:

```shell
python -m exactus.packages.exactus_mcp --root /absolute/project/path
```

After both Uvicorn and ngrok are ready, the command prints:

```text
Exactus MCP is ready
Public page: https://example.ngrok-free.app/
MCP endpoint: https://example.ngrok-free.app/mcp
Bearer token: generated-secret
```

Keep the process running. Press `Ctrl-C` once to close the Uvicorn server and
the ngrok child process owned by this invocation.

### Dashboard and ChatGPT clients

The public origin without `/mcp` is an activity dashboard. It reports the
current phase, exact MCP connection URL, call totals, and the 100 most recent
tool calls with bounded request/response metadata and duration. Tokens,
authorization headers, raw report content, and raw arguments are never placed
in the activity response or page.

To connect the ChatGPT desktop/Codex app, open **Settings → MCP servers → Add
server**, select **Streamable HTTP**, enter the HTTPS URL ending in `/mcp`, add
the bearer token, save, and restart the app. To connect ChatGPT web in a
supported workspace, open **Settings → Plugins → + → Add custom MCP server**,
enter the same endpoint and authentication, create/publish the plugin, then
start a new chat and select Exactus with `@`.

OpenAI's current product documentation limits full custom MCP connections to
Business and Enterprise/Edu workspaces with the required workspace role. Pro
supports read/fetch custom MCP only. Personal Plus/Classic accounts do not
offer this custom MCP installation flow, which is an account entitlement and
cannot be enabled by Exactus. Verify current availability at
<https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt>
and <https://learn.chatgpt.com/docs/extend/mcp>.

Use a reserved ngrok origin for a durable ChatGPT web connection because its
saved plugin URL does not consult MantleDB. The configured
`https://exactus-mcp.ngrok-free.dev` custom subdomain requires a paid ngrok
plan for this account (`ERR_NGROK_313`) and is therefore disabled by default.
On the free plan, copy the current dynamic dashboard and `/mcp` URLs from the
macOS menu after each restart. Desktop/Codex may instead use the Exactus plugin
bridge and signed MantleDB discovery.

When Exactus is installed as a package, the equivalent console script is:

```shell
exactus-mcp --root /absolute/project/path
```

### Native macOS menu-bar controller

On macOS, both launch forms enable a native status item by default. The menu
remains available after **Stop Server**, so the service can be started again
without reopening a terminal. It shows the complete operational state in
words—Starting, Updating tunnel, Running, Stopping, Stopped, Restarting, or
Failed—rather than relying on color alone.

The read-only rows expose the configured project, local and public origins,
total and active MCP tool calls, the most recently called tool with its local
time, and the latest lifecycle or tool-call failure. The available actions are
grouped into **Server Controls** (Start, Stop, Restart) and **Connection**
(Open Status Page, Copy Connection URL), followed by **Quit Exactus MCP**.
Commands that cannot run in the current state are disabled. Restart is
serialized: the previous Uvicorn and ngrok generation shuts down before its
replacement starts.

The public row distinguishes configuration from failure. **Public tunnel:
Disabled** means this generation was deliberately launched with `--no-ngrok`.
With ngrok enabled, it shows **Updating…** during tunnel discovery, then the
actual HTTPS origin. If startup fails, the phase changes to **Failed** and the
menu adds a specific last-error row; it does not mislabel failure as a disabled
tunnel.

The menu uses the project's locked Tabler outline icon as a monochrome macOS
template image, so the system supplies the correct light/dark menu-bar color.
Run without the GUI for SSH, CI, or another headless Mac:

```shell
exactus-mcp --root /absolute/project/path --no-menu-bar
```

`--menu-bar` is macOS-only. Linux and Windows continue to use the terminal
lifecycle, and an explicit menu request on those platforms fails before
startup. The JSON key is `menu-bar`; project TOML documents the same key but
leaves it commented so platform-specific defaults remain portable.

### Project TOML and private JSON configuration

Service defaults can live in `[tool.exactus.mcp]`, and watcher defaults can
live in `[tool.exactus.mcp.wakeup]`. Exactus' shared configuration validator
recognizes this package-owned subtree; the MCP package then type-checks every
supported key and rejects unknown settings. `pyproject.toml` is intentionally
not a secret store, so bearer tokens, wake keys, and private MantleDB
namespaces are rejected there even though their complete option inventory is
shown as commented documentation.

For deployable settings and secrets, copy
`exactus/packages/exactus_mcp/examples/config.json.example` to a private path.
The JSON document can be flat for one command or contain `service` and
`wakeup` objects for both. Hyphenated and underscore keys are equivalent, and
relative paths resolve beside the JSON file. On POSIX systems, a JSON file
that contains `access-token` or `wake-key` must have mode `0600`; on Windows,
restrict its filesystem ACL to the owning user.

```shell
chmod 600 /private/path/exactus-mcp.json
exactus-mcp --config /private/path/exactus-mcp.json
exactus-mcp-wakeup --config /private/path/exactus-mcp.json install
```

Precedence is explicit CLI, environment, JSON, project TOML, then built-in
defaults. Bare `--config` as the final argument prints the effective
configuration and exits without starting a service. Secrets and the private
namespace are redacted. Supply a JSON path and then the bare form to inspect a
file safely:

```shell
exactus-mcp --config=/private/path/exactus-mcp.json --config
exactus-mcp-wakeup --config=/private/path/exactus-mcp.json --config
```

### Stable access token

By default, each process generates a new high-entropy token. For a stable
client configuration, inject a secret through the environment instead of a
shell-history argument:

```shell
EXACTUS_MCP_ACCESS_TOKEN='replace-with-a-secret' \
  exactus-mcp --root /absolute/project/path
```

### Loopback-only development

Disable the public tunnel while developing locally:

```shell
exactus-mcp --root /absolute/project/path --no-ngrok
```

Use `exactus-mcp --help` for port, timeout, log-level, ngrok executable, and
reserved-domain options.

### Named ngrok endpoint

When `ngrok.yml` defines a named endpoint and its upstream, bind Uvicorn to the
same port and start that endpoint by name:

```shell
exactus-mcp --root /absolute/project/path \
  --port 6100 \
  --ngrok-endpoint your_endpoint_name
```

Do not also pass `--ngrok-url`; the two ngrok modes are mutually exclusive.
Starting by name preserves an account-assigned endpoint exactly as configured
instead of asking ngrok to create a new custom-domain tunnel.

### Persist a dynamic URL with MantleDB

Free ngrok accounts may receive a new public origin each time the service
starts. Exactus can publish that active origin to an explicit MantleDB record:

```shell
EXACTUS_MCP_MANTLEDB_NAMESPACE='your-private-namespace' \
  exactus-mcp --root /absolute/project/path
```

The default record path is `url`; override it with `--mantledb-path` or
`EXACTUS_MCP_MANTLEDB_PATH`. Exactus writes only after ngrok is ready and
treats persistence failure as a startup failure, so a stale discovery record
is never presented as successful startup. The record carries an HMAC-SHA256
signature made with the MCP bearer token; the plugin verifies that signature
before sending the bearer token to the discovered endpoint. MantleDB is
disabled when no namespace is supplied.

The Exactus Engineering plugin ships a local stdio bridge that resolves this
record before every forwarded MCP message. Configure the plugin host with the
same namespace, path, and bearer token used by the service:

```shell
export EXACTUS_MCP_MANTLEDB_NAMESPACE='your-private-namespace'
export EXACTUS_MCP_MANTLEDB_PATH='url'
export EXACTUS_MCP_ACCESS_TOKEN='one-stable-secret'
```

Restart ChatGPT/Codex after changing its environment, and start the service
from an environment carrying those same values. The bridge refuses missing,
malformed, or incorrectly signed records and never forwards the bearer token
to an unsigned URL.

### Wake an offline Mac and recover its dynamic URL

URL discovery alone cannot help when the Mac, Exactus process, or ngrok tunnel
is offline. The optional wake flow adds a stable HTTPS trigger and a persistent
watcher without turning the public endpoint into an arbitrary command runner.

The protocol has four separately checked records and boundaries:

1. The plugin generates a fresh UUID v4 and current Unix timestamp. It signs
   `exactus-mcp-wake`, the UUID, and timestamp with
   `EXACTUS_MCP_WAKE_KEY`.
2. The stable Worker verifies the HMAC and two-minute replay window, then
   writes the exact signed document to the namespace's `wake/command` record.
3. The Mac watcher independently verifies the same command. A fresh UUID runs
   only the fixed local command configured when the watcher started. A live
   child is reused; remote data can never choose a command or argument.
4. The watcher publishes the matching UUID, ready URL, and a domain-separated
   response signature to `wake/response`. The plugin verifies it, then reads
   the ordinary `url` record and verifies that record with the MCP bearer
   token. The two normalized MCP URLs must match before the bearer is sent.

Use separate secrets for the two jobs:

- `EXACTUS_MCP_WAKE_KEY` authenticates wake commands and ready responses. The
  Worker needs this value as its `WAKE_HMAC_KEY` secret.
- `EXACTUS_MCP_ACCESS_TOKEN` authenticates MCP traffic and the final URL
  record. The Worker must never receive this value.

Run the watcher on the Mac from the target Exactus checkout:

```shell
export EXACTUS_MCP_MANTLEDB_NAMESPACE='your-private-namespace'
export EXACTUS_MCP_WAKE_KEY='a-separate-random-wake-key'
export EXACTUS_MCP_ACCESS_TOKEN='one-stable-mcp-secret'

exactus-mcp-wakeup run \
  --state "$PWD/.exactus-mcp-wakeup/last-id" \
  -- \
  exactus-mcp --root "$PWD" --port 6100
```

The command after `--` is parsed as an argument vector and launched without a
shell. Both output streams are combined only for public HTTPS URL discovery.
The watcher owns the child lifecycle and records a completed UUID atomically.
Use `--url-pattern` only when a service prints an unusual URL format. The
default accepts only the explicit `MCP endpoint:` line and therefore cannot
mistake an unrelated HTTPS URL in an ngrok error message for a ready service.

On Windows PowerShell, the equivalent foreground setup is:

```powershell
$env:EXACTUS_MCP_MANTLEDB_NAMESPACE = "your-private-namespace"
$env:EXACTUS_MCP_WAKE_KEY = "a-separate-random-wake-key"
$env:EXACTUS_MCP_ACCESS_TOKEN = "one-stable-mcp-secret"

exactus-mcp-wakeup run `
  --state "$PWD\.exactus-mcp-wakeup\last-id" `
  -- `
  exactus-mcp --root "$PWD" --port 6100
```

#### Install for startup on macOS, Linux, or Windows

The watcher exposes the same lifecycle commands on all supported desktop and
server operating systems:

```shell
exactus-mcp-wakeup install \
  --mantledb-namespace 'your-private-namespace' \
  --keep-service-running \
  -- \
  exactus-mcp --root /absolute/project/path --port 6100 \
  --ngrok-endpoint your_endpoint_name

exactus-mcp-wakeup status
exactus-mcp-wakeup uninstall
```

`install` reads `EXACTUS_MCP_WAKE_KEY` and `EXACTUS_MCP_ACCESS_TOKEN` from the
current environment, writes them to a separate private user configuration
file, writes a secret-free native service definition, enables automatic user
startup, and starts the watcher immediately. The selected backend is:

| Platform | Native backend | Startup boundary |
| --- | --- | --- |
| macOS | per-user LaunchAgent | login and immediate bootstrap |
| Linux | `systemd --user` service | user-manager startup and immediate enable |
| Windows | Task Scheduler `ONLOGON` task | login and immediate task run |

On POSIX systems the secret file is required to have mode `0600`. On Windows it
is stored below the current user's roaming application-data directory and is
protected by that profile's filesystem ACL. The native definition contains the
Python executable, watcher options, secret-file path, and fixed child argument
vector, but never the secret values.

`status` reports the backend, installation state, loaded state, running state,
and PID when the native API exposes one. It exits nonzero when the watcher is
not running. `uninstall` stops the service/task and deletes both its definition
and secrets file. It deliberately preserves logs and the last-UUID state for
diagnosis and safe reinstall. On Linux, an administrator may enable systemd
user lingering when the watcher must start at boot before interactive login.

Use `--keep-service-running` for a stable ChatGPT web connection. The watcher
starts the configured MCP child immediately at login and checks it before every
MantleDB polling pass, so an unexpectedly exited service is restarted with the
same fixed command. Configure that command with a reserved ngrok endpoint and a
matching fixed local port. The service still publishes its bearer-signed URL to
MantleDB, and signed wake commands remain available to local desktop bridges.

The deployable bridge is in
[`bridge/`](../../../packages/exactus_mcp/bridge/README.md). Replace its
MantleDB URLs, store the wake key with the provider's secret command, deploy it
explicitly, then configure the plugin host:

```shell
export EXACTUS_MCP_MANTLEDB_NAMESPACE='your-private-namespace'
export EXACTUS_MCP_MANTLEDB_PATH='url'
export EXACTUS_MCP_ACCESS_TOKEN='one-stable-mcp-secret'
export EXACTUS_MCP_WAKE_KEY='a-separate-random-wake-key'
export EXACTUS_MCP_WAKE_URL='https://your-stable-worker.example/'
```

`EXACTUS_MCP_WAKE_TIMEOUT` optionally controls the plugin's wait for the stable
trigger and defaults to 35 seconds. Run the plugin bridge with `--wake` for an
explicit end-to-end wake diagnostic. A 401 means the Worker rejected the wake
signature; 504 means no matching ready response arrived before its deadline;
an URL mismatch means the wake response and bearer-signed discovery record do
not identify the same endpoint.

## Connect an MCP client

Configure a Streamable HTTP client with the printed endpoint and bearer
header. A representative client entry is:

```json
{
  "mcpServers": {
    "exactus": {
      "type": "http",
      "url": "https://example.ngrok-free.app/mcp",
      "headers": {
        "Authorization": "Bearer generated-secret"
      }
    }
  }
}
```

Client configuration fields differ between MCP hosts. The invariant values
are the HTTPS URL ending in `/mcp` and the `Authorization: Bearer ...` header.
Opening the public page in a browser does not install a skill, plugin, or MCP
connector by itself.

## Runnable examples

The bundled examples exercise the official MCP client instead of manually
constructing protocol requests. The self-contained example creates an
ephemeral loopback service, performs an authenticated MCP round trip, and
stops the service without opening an ngrok tunnel:

```shell
python -m exactus.packages.exactus_mcp.examples
```

To inspect a service that is already running, provide its printed bearer token
through the environment and its printed MCP endpoint as the argument:

```shell
EXACTUS_MCP_ACCESS_TOKEN='token-printed-by-exactus-mcp' \
  python -m exactus.packages.exactus_mcp.examples.client \
  'https://example.ngrok-free.app/mcp'
```

The reusable client lists tools and resources and calls only
`get_exactus_status`; it does not start an Exactus check. The full example
contract and expected output are documented in
[`examples/README.md`](../../../packages/exactus_mcp/examples/README.md).
The signed wake setup is shown separately in
[`examples/wakeup.md`](../../../packages/exactus_mcp/examples/wakeup.md).

## Published MCP surface

### Tools

- `get_exactus_status` returns the configured root, connection metadata,
  authentication mode, and runnable subset.
- `list_exactus_tools` returns the complete Exactus catalog and clearly marks
  which report tools may run remotely.
- `run_exactus_check` runs one admitted report tool with optional safe,
  repository-relative include globs.
- `read_exactus_report` reads the newest Markdown or JSON report for an
  admitted tool.

The remotely runnable subset is deliberately limited to:

- `lints`;
- `kwargs_typehints`;
- `docs`;
- `readme`.

### Resources

- `exactus://policy/agents` returns the complete configured-root `AGENTS.md`.
- `exactus://policy/extended` returns the complete configured-root
  `AGENTS_EXTENDED.md`.

These resources let an MCP client read the same engineering contract enforced
by the global Exactus skill without copying or summarizing it.

## Security model

The service has two intentionally different surfaces:

| Surface | Authentication | Data exposed |
| --- | --- | --- |
| `/`, `/health`, `/api/status`, `/assets/*` | Public | Operational status and MCP URL only |
| `/mcp` | Bearer token | Exactus tools, reports, configured root, and policy resources |

Additional constraints are enforced in code:

- Uvicorn binds to loopback by default; ngrok is the only public ingress.
- Every remote Exactus execution uses `--dry`.
- The project root is fixed when the process starts.
- Include patterns reject absolute paths, parent traversal, excessive length,
  and excessive count.
- Checks are serialized to prevent reports from racing each other.
- No arbitrary command, executable path, working directory, or Exactus tool
  name is accepted from the MCP caller.
- The MCP SDK DNS-rebinding protection admits only explicit local and active
  ngrok hosts and origins.
- The generated page uses a restrictive content-security policy and ships no
  third-party browser assets.

Treat the bearer token and public URL as credentials. Stop the process to
invalidate the generated token and close its tunnel. For longer-lived use,
apply ngrok access policy and normal network monitoring in addition to the
application bearer check.

## Report behavior

`run_exactus_check` returns the process exit code, report status, total finding
count, machine-report path, and a bounded tail of process output. A timeout
returns exit code `124` with status `TIMEOUT`. Missing or malformed report
files are explicit (`MISSING` or `INVALID`) rather than presented as clean.

A clean result requires both a successful process exit and a clean Exactus
report. The MCP layer does not conceal diagnostics, weaken configuration, or
translate partial evidence into a pass.

## Troubleshooting

### `ngrok executable not found`

Install ngrok or provide its absolute path with `--ngrok-command`. Confirm the
same account environment can run `ngrok config check`.

### ngrok exits before advertising a URL

Run ngrok directly to inspect authentication, account, reserved-domain, or
network errors. The service returns the final bounded ngrok log records in its
startup error.

### MCP returns HTTP 401

Set the exact header printed by the process:

```text
Authorization: Bearer generated-secret
```

The public status API cannot return or recover this token.

### MCP host or origin rejected

Use the URL printed by the current process. A previous ngrok URL is not placed
on the new process allowlist.

### Check reports `MISSING`

Inspect the returned process output and verify the configured root contains a
valid Exactus project configuration. The report location follows the same
Exactus discovery rules as local CLI runs.

## Validation

Run the focused implementation gates:

```shell
ruff check exactus/packages/exactus_mcp \
  exactus/tests/packages/exactus_mcp
basedpyright exactus/packages/exactus_mcp \
  exactus/tests/packages/exactus_mcp
pytest -q exactus/tests/packages/exactus_mcp
node --check exactus/packages/exactus_mcp/web/app.js
node --check exactus/packages/exactus_mcp/bridge/worker.js
```

For an end-to-end check, start the service with ngrok enabled, request the
public `/health` route, initialize an MCP client with the bearer header, inspect
the page at narrow and wide viewports, and terminate the owning process. This
verifies tunnel allocation, public routing, authorization, MCP protocol
startup, packaged assets, responsive layout, and cleanup together.

## Automatic Cloudflare MCP publication

The supported ChatGPT publication path uses a permanent Cloudflare Worker as
an OAuth 2.1 protected MCP gateway and an ephemeral Cloudflare Quick Tunnel as
the private origin transport. `exactus-mcp-publish` bootstraps the Cloudflare
resources when they do not exist and then maintains the origin publication.

On first use the publisher checks Wrangler authentication, creates or reuses
the routing KV namespace, generates independent cryptographically random
control and OAuth login secrets, installs those secrets in the Worker, deploys
the Worker, records the stable Worker URL in the local environment file, starts
the loopback Exactus MCP service, starts `cloudflared`, and publishes the
current `trycloudflare.com` origin to KV. Secrets are never passed as command
line arguments. The local environment file is written with owner-only
permissions.

Subsequent invocations are idempotent. Existing Cloudflare resources and
secrets are reused, while a changed Quick Tunnel URL is republished
automatically. The Worker performs OAuth protected-resource discovery,
authorization-server discovery, dynamic client registration, authorization
code flow with PKCE/S256, resource binding, bearer validation, and private
origin authentication. The origin gateway validates and removes its private
credential and normalizes the Host header before dispatching to the MCP
transport. DNS-rebinding protection remains enabled.

The normal command is simply:

```console
exactus-mcp-publish
```

A browser authentication step can occur on first use when Wrangler has not yet
been authenticated with Cloudflare. No KV namespace ID, Worker secret, tunnel
URL, or `.env` value needs to be copied manually.
