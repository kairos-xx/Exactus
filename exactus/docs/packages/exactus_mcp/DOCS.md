# Exactus MCP service

## Purpose

`exactus-mcp` provides a small, auditable remote boundary around Exactus. One
command starts a loopback Uvicorn server, creates an ngrok HTTPS tunnel, serves
a public connection page, and publishes an authenticated MCP Streamable HTTP
endpoint at `/mcp`.

The public HTML page is informational. It proves the service is online and
shows the MCP endpoint, but never returns the bearer token. The MCP endpoint
requires the token printed in the launching terminal.

## Files

| File | Description |
|---|---|
| `__main__.py` | Module entry point for `python -m exactus.packages.exactus_mcp`. |
| `cli.py` | Service command line and asyncio orchestration: parses the grammar, then coordinates the Uvicorn server, ngrok child, MantleDB publish and menu-bar controller as concurrent tasks. |
| `service.py` | The ASGI application: MCP tools and resources, public HTTP routes (status page, `/api/status`, dashboard), bearer enforcement, and the restricted run/read surface. |
| `runner.py` | Executes admitted report tools for MCP callers — fixed root, forced `--dry`, serialized calls, bounded captured output, timeout handling. |
| `state.py` | Mutable per-process service state: root, host/port, access token, transport security, MCP URL. |
| `activity.py` | Lifecycle and caller-activity tracking behind the public dashboard and menu bar; never records tokens, authorization headers, report bodies, or raw arguments. |
| `supervisor.py` | Synchronous control surface (`start`/`stop`/`restart`) around the asyncio service for the menu bar and restart flow; serializes generations. |
| `ngrok.py` | Owns the ngrok child process and discovers its public HTTPS origin — dynamic tunnel or named `--ngrok-endpoint`. |
| `cloudflare.py` | `exactus-mcp-publish`: publishes the stable OAuth wake Worker through Wrangler — auth-server discovery, dynamic client registration, PKCE/S256 authorization flow, and secret provisioning without manual IDs. |
| `mantledb.py` | Writes the active public URL and signed wake records to MantleDB; discovery records carry an HMAC-SHA256 signature made with the bearer token so clients never trust an unsigned URL. |
| `wakeup.py` | Signed wake watcher core: polls the `wake/command` record, verifies the HMAC/replay window, launches only the fixed child command, and publishes the domain-separated `wake/response`. |
| `wakeup_cli.py` | `exactus-mcp-wakeup` command line: `run`, `install`, `status`, `uninstall` with `--` child argument vector parsing. |
| `startup.py` | Native startup backends for the watcher — per-user LaunchAgent (macOS), `systemd --user` service (Linux), Task Scheduler `ONLOGON` (Windows); writes secret-free definitions plus a `0600` secret file. |
| `macos_menu.py` | Native macOS status-item controller: textual lifecycle phase, live counters, server controls and connection actions. |
| `environment.py` | Minimal deterministic `.env` loading for the CLI entry points. |
| `project_config.py` | `[tool.exactus.mcp]`/JSON configuration loader: hyphen/underscore equivalence, relative-path resolution, `0600` secret-file enforcement, precedence merge. |
| `bridge/` | Deployable stdio MCP bridge that resolves the signed MantleDB record before every forwarded message. |
| `examples/` | Self-contained authenticated loopback round trip (`examples/run.py`), reusable inspector (`client.py`), `config.json.example`, `wakeup.md`. |
| `macos/` | Menu-bar assets including the monochrome template icon. |
| `web/` | Public status page and dashboard assets. |

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

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Public API for the Exactus MCP and ngrok service. |
| `__main__.py` | Run the Exactus MCP and ngrok service. |
| `activity.py` | Track Exactus MCP lifecycle and caller activity for local interfaces. |
| `bridge/` | Subdirectory. |
| `cli.py` | Command line for the Exactus MCP and ngrok service. |
| `cloudflare.py` | Publish Exactus MCP through a stable OAuth Cloudflare Worker. |
| `environment.py` | Minimal deterministic ``.env`` loading for command-line entry points. |
| `examples/` | Runnable demonstration for `exactus/packages/exactus_mcp/`. |
| `macos/` | Subdirectory. |
| `macos_menu.py` | Present Exactus MCP lifecycle and controls in the macOS menu bar. |
| `mantledb.py` | Persist the active Exactus public URL through MantleDB. |
| `ngrok.py` | Own an ngrok child process and discover its public HTTPS origin. |
| `project_config.py` | Load Exactus MCP command defaults from project configuration. |
| `runner.py` | Run a constrained Exactus report command for an MCP caller. |
| `service.py` | MCP tools, resources, HTTP routes, and bearer protection for Exactus. |
| `startup.py` | Manage native startup for the Exactus MCP wake watcher. |
| `state.py` | Mutable per-process state for the Exactus MCP service. |
| `supervisor.py` | Run the Exactus MCP asyncio service behind synchronous controls. |
| `wakeup.py` | Wake an Exactus MCP service through signed MantleDB commands. |
| `wakeup_cli.py` | Run and manage the signed Exactus MCP wake watcher. |
| `web/` | Subdirectory. |

Run it as a module: `python -m exactus.packages.exactus_mcp`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--config` | Load a JSON config; when used alone, print the effective configuration with secrets redacted. | metavar='JSON', nargs='?' |
| `--root` | Project root exposed to Exactus (default: current directory). | type=Path, default=Path.cwd() |
| `--host` | Loopback bind host (default: 127.0.0.1). | default=Constants.host |
| `--port` | Local port; zero chooses an available port (default: 0). | type=int, default=0 |
| `--access-token` | Bearer token; defaults to EXACTUS_MCP_ACCESS_TOKEN or a newly generated secret. Prefer the environment over command history. | default=environ.get('EXACTUS_MCP_ACCESS_TOKEN') |
| `--ngrok` | Create an ngrok HTTPS tunnel (default: enabled). | action=BooleanOptionalAction, default=True |
| `--ngrok-command` | Ngrok executable name or path (default: ngrok). | default='ngrok' |
| `--ngrok-url` | Optional reserved ngrok URL or custom domain. |  |
| `--ngrok-endpoint` | Named endpoint from ngrok.yml; its upstream must match --port. |  |
| `--mantledb-namespace` | Optional MantleDB namespace that receives the active public ngrok origin. | default=environ.get('EXACTUS_MCP_MANTLEDB_NAMESPACE') |
| `--mantledb-path` | MantleDB record path (default: url). | default=environ.get('EXACTUS_MCP_MANTLEDB_PATH', 'url') |
| `--mantledb-timeout` | Seconds allowed for MantleDB persistence (default: 10). | type=float, default=10.0 |
| `--tunnel-timeout` | Seconds to wait for ngrok (default: 30). | type=float, default=Constants.tunnel_timeout |
| `--check-timeout` | Seconds allowed for each Exactus check (default: 900). | type=float, default=Constants.check_timeout |
| `--log-level` | Uvicorn log level (default: info). | choices=('critical', 'error', 'warning', 'info', 'debug'), default='info' |
| `--menu-bar` | Run the native macOS status menu (default: enabled on macOS). | action=BooleanOptionalAction, default=sys_platform == 'darwin' |
| `url` | Streamable HTTP endpoint, for example https://host/mcp. |  |
| `--mantledb-namespace` |  | default=environ.get('EXACTUS_MCP_MANTLEDB_NAMESPACE') |
| `--wake-key` | Wake HMAC key; prefer EXACTUS_MCP_WAKE_KEY over shell history. | default=environ.get('EXACTUS_MCP_WAKE_KEY') |
| `--access-token` | MCP bearer token inherited by the service; prefer EXACTUS_MCP_ACCESS_TOKEN over shell history. | default=environ.get('EXACTUS_MCP_ACCESS_TOKEN') |
| `--secrets-file` | Private secrets file created by the install action. | type=Path |
| `--command-path` |  | default='wake/command' |
| `--response-path` |  | default='wake/response' |
| `--url-path` |  | default=environ.get('EXACTUS_MCP_MANTLEDB_PATH', 'url') |
| `--state` |  | type=Path, default=Path.home() / '.exactus' / 'mcp-wakeup' / 'last-id' |
| `--poll-interval` |  | type=float, default=Constants.default_poll_interval |
| `--request-timeout` |  | type=float, default=Constants.default_timeout |
| `--discovery-timeout` |  | type=float, default=Constants.default_discovery_timeout |
| `--retry-maximum` |  | type=float, default=Constants.default_retry_maximum |
| `--maximum-age` |  | type=float, default=Constants.default_maximum_age |
| `--mcp-path` |  | default='/mcp' |
| `--url-pattern` |  | default='(?<=MCP endpoint: )https://[^\\s<>\'\\"]+' |
| `--keep-service-running` | Start the fixed MCP service immediately and restart it after failure while continuing to process signed wake requests. | action=BooleanOptionalAction, default=False |
| `service_command` | Fixed local service command, placed after --. | nargs=REMAINDER, default=() if defaults is None else defaults.get('service_command', ()) |
| `--label` | Native user-service identifier. | default=StartupConstants.default_label |
| `--config` | Load a JSON config; when used alone, print the effective configuration with secrets redacted. | metavar='JSON', nargs='?' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Public API for the Exactus MCP and ngrok service.


### `__main__.py`

Run the Exactus MCP and ngrok service.


### `activity.py`

Track Exactus MCP lifecycle and caller activity for local interfaces.

- `class Constants` — Group bounded activity-log constants.
  - `maximum_records` = `100`
- `class ServicePhase` — Name every visible state of the managed MCP service.
  - `STARTING` = `'Starting'`
  - `UPDATING` = `'Updating tunnel'`
  - `RUNNING` = `'Running'`
  - `STOPPING` = `'Stopping'`
  - `STOPPED` = `'Stopped'`
  - `RESTARTING` = `'Restarting'`
  - `FAILED` = `'Failed'`
- `class CallState` — Name the lifecycle state of one safe activity-log entry.
  - `ACTIVE` = `'active'`
  - `SUCCEEDED` = `'succeeded'`
  - `FAILED` = `'failed'`
- `class CallRecord` — Describe one redacted MCP request and response summary.
  - Fields: `identifier: int`, `name: str`, `state: CallState`, `started_at: datetime`, `completed_at: datetime | None`, `duration_ms: int | None`, `request_metadata: dict[str, JsonValue]`, `response_metadata: dict[str, JsonValue]`
  - `to_json(self) -> dict[str, JsonValue]` — Return a JSON-safe activity dashboard record.
- `class ActivitySnapshot` — Describe one immutable view of current service activity.
  - Fields: `phase: ServicePhase`, `local_url: str | None`, `public_url: str | None`, `active_calls: int`, `call_count: int`, `last_call: str | None`, `last_call_at: datetime | None`, `last_error: str | None`
  - `mcp_url(self) -> str | None` — Return the preferred MCP endpoint URL when an origin is known.
- `class ServiceActivity` — Own thread-safe lifecycle and MCP call activity.
  - `__init__(self) -> None` — Create an initially stopped activity record.
  - `snapshot(self) -> ActivitySnapshot` — Return one consistent immutable activity snapshot.
  - `mark_starting(self) -> None` — Record that a new local server is starting.
  - `mark_updating(self, *, local_url: str) -> None` — Record local readiness while the public tunnel is updating.
  - `mark_running(self, *, local_url: str, public_url: str | None) -> None` — Record a ready service and its reachable origins.
  - `mark_stopping(self) -> None` — Record a requested graceful shutdown.
  - `mark_stopped(self) -> None` — Record a completed shutdown while preserving call history.
  - `mark_restarting(self) -> None` — Record that shutdown and subsequent startup were requested.
  - `mark_failed(self, *, error: str) -> None` — Record a terminal lifecycle failure.
  - `recent_calls(self, *, limit: int=50) -> list[dict[str, JsonValue]]` — Return newest redacted call records first.
  - `begin_call(self, *, name: str, request_metadata: dict[str, JsonValue] | None=None) -> int` — Record the start of one protected MCP tool call.
  - `finish_call(self, *, identifier: int, response_metadata: dict[str, JsonValue] | None=None, error: str | None=None) -> None` — Record completion of one protected MCP tool call.

### `cli.py`

Command line for the Exactus MCP and ngrok service.

- `class MenuBarEntryPoint(Protocol)` — Describe the lazily loaded macOS menu-bar entry point.
- `class Constants` — Group command-line defaults.
  - `host` = `'127.0.0.1'`
  - `startup_timeout` = `20.0`
  - `tunnel_timeout` = `30.0`
  - `check_timeout` = `900.0`
  - `maximum_port` = `65535`
- `class RuntimeConfig` — Validated service runtime configuration.
  - Fields: `root: Path`, `host: str`, `port: int`, `access_token: str | None`, `ngrok: bool`, `ngrok_command: str`, `ngrok_url: str | None`, `ngrok_endpoint: str | None`, `mantledb_namespace: str | None`, `mantledb_path: str`, `mantledb_timeout: float`, `tunnel_timeout: float`, `check_timeout: float`, `log_level: Literal['critical', 'error', 'warning', 'info', 'debug']`, `menu_bar: bool`
- `run_service(*, config: RuntimeConfig, activity: ServiceActivity | None=None, stop_requested: Event | None=None) -> int` — Run Uvicorn and ngrok under one lifecycle.
- `main() -> int` — Parse arguments and run the Exactus MCP service.

### `cloudflare.py`

Publish Exactus MCP through a stable OAuth Cloudflare Worker.

- `class Constants` — Group module-level constants.
  - `worker_url_key` = `'EXACTUS_MCP_CLOUDFLARE_WORKER_URL'`
  - `control_credential_key` = `'EXACTUS_MCP_CLOUDFLARE_CONTROL_SECRET'`
  - `cloudflared_key` = `'EXACTUS_MCP_CLOUDFLARED'`
  - `startup_timeout_key` = `'EXACTUS_MCP_CLOUDFLARE_STARTUP_TIMEOUT_SECONDS'`
  - `restart_delay_key` = `'EXACTUS_MCP_CLOUDFLARE_RESTART_DELAY_SECONDS'`
  - `tunnel_url_pattern` = `compile_pattern(pattern='https://[a-zA-Z0-9-]+\\.trycloudflare\\.com')`
  - `worker_url_pattern` = `compile_pattern(pattern='https://[a-zA-Z0-9.-]+\\.workers\\.dev')`
  - `kv_id_pattern` = `compile_pattern(pattern='[a-f0-9]{32}')`
  - `kv_placeholder` = `'REPLACE_WITH_KV_NAMESPACE_ID'`
  - `oauth_secret_key` = `'EXACTUS_MCP_CLOUDFLARE_OAUTH_LOGIN' + '_SECRET'`
  - `wrangler_version` = `'4.45.0'`
- `class CloudflareConfig` — Configure stable Worker routing to an ephemeral Quick Tunnel.
  - `cloudflared` = `'cloudflared'`
  - `startup_timeout_seconds` = `30.0`
  - `restart_delay_seconds` = `1.0`
  - Fields: `worker_url: str`, `control_secret: str`
  - `from_mapping(cls, *, values: Mapping[str, str]) -> Self` — Build publication settings from environment values.
  - `validate(self) -> None` — Reject incomplete or unsafe publication configuration.
- `class CloudflareBootstrapper` — Provision the Worker, KV namespace, and secrets when required.
  - `__init__(self, *, root: Path, values: dict[str, str]) -> None` — Store project and environment state.
  - `ensure(self) -> None` — Create all persistent Cloudflare resources and local credentials.
- `class PublicationSupervisor` — Own Exactus MCP and continuously republish Quick Tunnel URLs.
  - `__init__(self, *, config: CloudflareConfig, root: Path, port: int) -> None` — Store publication configuration.
  - `stop(*, process: Process | None) -> None` — Terminate one owned child process.
  - `run(self) -> int` — Run Exactus MCP and its self-healing Cloudflare tunnel.
  - `resolve_cloudflared(self) -> str` — Resolve the configured cloudflared executable.
  - `start_tunnel(self, *, cloudflared: str) -> Process` — Start one anonymous Quick Tunnel to the loopback server.
  - `read_tunnel_url(self, *, tunnel: Process) -> str` — Read the assigned trycloudflare URL from cloudflared output.
  - `publish(self, *, backend_url: str) -> None` — Publish the active tunnel URL to the stable Worker.
  - `wait_for_server(self, *, server: Process) -> None` — Wait until the local Exactus health endpoint succeeds.
- `configured_port(*, root: Path) -> int` — Read the fixed MCP port from the project pyproject.toml.
- `main() -> int` — Run the automatic Exactus Cloudflare publication stack.

### `environment.py`

Minimal deterministic ``.env`` loading for command-line entry points.

- `class Constants` — Group module-level constants.
  - `env_file_name` = `'.env'`
  - `export_prefix` = `'export '`
  - `quoted_value_length` = `2`
- `class EnvironmentLoader` — Merge project ``.env`` values without overriding process variables.
  - `load(cls, *, values: MutableMapping[str, str], directory: Path | None=None) -> Path | None` — Load the nearest project ``.env`` file into ``values``.

### `examples/__init__.py`

Runnable authenticated client examples for Exactus MCP.


### `examples/__main__.py`

Run the Exactus MCP example through the project virtual environment.


### `examples/client.py`

Inspect an authenticated Exactus MCP Streamable HTTP endpoint.

- `class Inspection` — Summarize one authenticated MCP inspection.
  - Fields: `tools: tuple[str, ...]`, `resources: tuple[str, ...]`, `status_json: str`
- `inspect_service(*, url: str, access_token: str) -> Inspection` — Initialize an MCP session and inspect the Exactus surface.
- `main() -> int` — Inspect a running Exactus MCP service.

### `examples/run.py`

Run a self-contained authenticated Exactus MCP round trip.

- `class Constants` — Group deterministic example settings.
  - `host` = `'127.0.0.1'`
  - `startup_timeout` = `10.0`
  - `check_timeout` = `30.0`
- `demonstrate(*, root: Path | None=None) -> Inspection` — Start, inspect, and stop one loopback Exactus MCP service.
- `main() -> int` — Run the self-contained MCP demonstration.

### `macos_menu.py`

Present Exactus MCP lifecycle and controls in the macOS menu bar.

- `class NativeMenuItem(Protocol)` — Describe the typed status-menu item surface Exactus uses.
  - `callback(self) -> MenuCallback | None` — Return the active command callback, when enabled.
  - `hidden(self) -> bool` — Return whether the item is hidden.
  - `hidden(self, value: bool) -> None` — Set whether the item is hidden.
  - `title(self) -> str` — Return the visible menu title.
  - `title(self, value: str) -> None` — Set the visible menu title.
  - `set_callback(self, callback: MenuCallback | None) -> None` — Enable the item with a callback or disable it with ``None``.
  - `add(self, menuitem: NativeMenuItem) -> None` — Append one child command to this item's submenu.
- `class NativeTimer(Protocol)` — Describe the native menu refresh timer.
  - `start(self) -> None` — Start the timer.
  - `stop(self) -> None` — Stop the timer.
- `class NativeApp(Protocol)` — Describe the native status application run loop.
  - `run(self) -> None` — Run the native application loop.
- `class NativeSeparator(Protocol)` — Mark the native menu separator sentinel.
- `class MenuItemFactory(Protocol)` — Describe construction of one native menu item.
- `class TimerFactory(Protocol)` — Describe construction of one native refresh timer.
- `class AppFactory(Protocol)` — Describe construction of one native status application.
- `class RumpsModule(Protocol)` — Describe the dynamically loaded macOS status library.
  - Fields: `App: AppFactory`, `MenuItem: MenuItemFactory`, `Timer: TimerFactory`, `separator: NativeSeparator`
  - `quit_application(self) -> None` — Terminate the shared native application.
- `class Constants` — Group menu presentation and shutdown constants.
  - `refresh_interval` = `0.5`
  - `shutdown_timeout` = `8.0`
- `class MacMenuBarApplication` — Own the native status item, menu copy, and service actions.
  - `__init__(self, *, activity: ServiceActivity, supervisor: ServiceSupervisor) -> None` — Create the Exactus status item and stable menu structure.
  - `run(self) -> None` — Run the menu application until the user chooses Quit.
- `run_menu_bar(*, config: RuntimeConfig, service_runner: ServiceRunner) -> int` — Run the native menu-bar application and managed MCP service.

### `mantledb.py`

Persist the active Exactus public URL through MantleDB.

- `class Constants` — Group MantleDB transport constants.
  - `host` = `'mantledb.sh'`
  - `http_error_minimum` = `400`
- `class HttpRequest` — Describe one constrained MantleDB HTTP request.
  - `data` = `None`
  - `headers` = `field(default_factory=dict)`
  - Fields: `url: str`, `method: str`
- `class UrlResponse(Protocol)` — Minimal HTTP response contract used by the URL store.
  - `read(self) -> bytes` — Read the response body.
- `class UrlOpener(Protocol)` — Injected HTTP boundary used by ``MantleUrlStore``.
- `class ManagedHttpResponse` — Own an HTTPS connection and its active response.
  - Fields: `connection: HTTPSConnection`, `response: HTTPResponse`
  - `read(self) -> bytes` — Read the active response body.
- `default_url_opener(*, request: HttpRequest, timeout: float) -> UrlResponse` — Open a MantleDB request through urllib.
- `class MantleUrlStore` — Store and retrieve one public URL using MantleDB.
  - `path` = `'url'`
  - `timeout` = `10.0`
  - `opener` = `field(default=default_url_opener, repr=False, compare=False)`
  - `signing_key` = `field(default=None, repr=False, compare=False)`
  - Fields: `namespace: str`
  - `endpoint(self) -> str` — Return the MantleDB endpoint for this store.
  - `save(self, *, url: str) -> None` — Save a URL, overwriting any existing value.
  - `update(self, *, url: str) -> None` — Update the currently stored URL.
  - `retrieve(self) -> str` — Retrieve the stored URL.

### `ngrok.py`

Own an ngrok child process and discover its public HTTPS origin.

- `class Constants` — Group ngrok lifecycle constants.
  - `log_tail` = `24`
- `class NgrokTunnel` — A running ngrok process and its allocated public origin.
  - Fields: `process: Process`, `public_url: str`
  - `start(cls, *, command: str, upstream_url: str, startup_timeout: float, requested_url: str | None, endpoint_name: str | None) -> NgrokTunnel` — Start ngrok and wait for its public URL.
  - `parse_public_url(*, line: str) -> str | None` — Extract a valid public URL from one ngrok JSON log line.
  - `wait(self) -> int` — Wait for ngrok to exit.
  - `close(self) -> None` — Stop the owned ngrok process and wait for cleanup.

### `project_config.py`

Load Exactus MCP command defaults from project configuration.

- `class Constants` — Group module-level constants.
  - `service_boolean_keys` = `frozenset(('menu-bar', 'ngrok'))`
  - `service_float_keys` = `frozenset(('check-timeout', 'mantledb-timeout', 'tunnel-timeout'))`
  - `service_integer_keys` = `frozenset(('port',))`
  - `service_path_keys` = `frozenset(('root',))`
  - `service_string_keys` = `frozenset(('access-token', 'host', 'log-level', 'mantledb-namespace', 'ma...`
  - `service_toml_string_keys` = `service_string_keys.difference(('access-token', 'mantledb-namespace'))`
  - `wake_boolean_keys` = `frozenset(('keep-service-running',))`
  - `wake_float_keys` = `frozenset(('discovery-timeout', 'maximum-age', 'poll-interval', 'request-...`
  - `wake_path_keys` = `frozenset(('secrets-file', 'state'))`
  - `wake_sequence_keys` = `frozenset(('service-command',))`
  - `wake_string_keys` = `frozenset(('command-path', 'label', 'mantledb-namespace', 'mcp-path', 're...`
  - `wake_toml_path_keys` = `frozenset(('state',))`
  - `wake_toml_string_keys` = `wake_string_keys.difference(('access-token', 'mantledb-namespace', 'wake-...`
- `class ConfigSelection` — Describe a removed ``--config`` option.
  - Fields: `path: Path | None`, `list_only: bool`, `arguments: tuple[str, ...]`
- `select_config(*, values: tuple[str, ...]) -> ConfigSelection` — Remove and classify the optional ``--config`` argument.
- `service_defaults(*, root: Path) -> dict[str, ArgumentDefault]` — Return validated `[tool.exactus.mcp]` argument defaults.
- `service_json_defaults(*, path: Path) -> dict[str, ArgumentDefault]` — Return service defaults from a private JSON configuration file.
- `wake_json_defaults(*, path: Path) -> dict[str, ArgumentDefault]` — Return watcher defaults from a private JSON configuration file.
- `wake_defaults(*, root: Path) -> dict[str, ArgumentDefault]` — Return validated `[tool.exactus.mcp.wakeup]` argument defaults.

### `runner.py`

Run a constrained Exactus report command for an MCP caller.

- `class Constants` — Group runner constants.
  - `output_tail` = `16000`
  - `maximum_includes` = `64`
  - `maximum_include_length` = `512`
  - `remote_tools` = `('docs', 'kwargs_typehints', 'lints', 'readme')`
- `class CheckResult` — Summarize one completed Exactus check.
  - Fields: `tool: RemoteTool`, `exit_code: int`, `status: str`, `findings: int`, `report_path: Path`, `output: str`, `report: JsonValue`
  - `to_json(self) -> dict[str, JsonValue]` — Return a JSON-compatible representation.
- `class Runner(Protocol)` — Contract used by the MCP service to run Exactus.
  - `list_tools() -> tuple[str, ...]` — Return the complete Exactus catalog.
  - `run(self, *, tool: RemoteTool, includes: tuple[str, ...]) -> CheckResult` — Run one protected Exactus check.
  - `read_report(self, *, tool: RemoteTool, report_format: ReportFormat) -> str` — Read one generated Exactus report.
- `class ExactusCommandRunner` — Execute Exactus with a fixed root, dry mode, and timeout.
  - `__init__(self, *, root: Path, timeout: float) -> None` — Create a constrained runner.
  - `list_tools() -> tuple[str, ...]` — Return the complete canonical Exactus tool catalog.
  - `run(self, *, tool: RemoteTool, includes: tuple[str, ...]) -> CheckResult` — Run one Exactus check without permitting source mutation.
  - `read_report(self, *, tool: RemoteTool, report_format: ReportFormat) -> str` — Read a generated report from the configured report tree.

### `service.py`

MCP tools, resources, HTTP routes, and bearer protection for Exactus.

- `class Constants` — Group service constants.
  - `asset_types` = `MappingProxyType(mapping={'app.js': 'text/javascript; charset=utf-8', 'ba...`
  - `content_security_policy` = `"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'se...`
- `class BearerAuthMiddleware` — Protect MCP locally and authenticate the Cloudflare origin gateway.
  - `origin_header` = `b'x-exactus-origin-secret'`
  - `host_header` = `b'host'`
  - `loopback_hosts` = `frozenset({b'127.0.0.1', b'localhost', b'[::1]'})`
  - `__init__(self, *, app: ASGIApp, access_token: str) -> None` — Create the local bearer and private-origin boundary.
- `class ExactusMcpService` — Expose Exactus reports through MCP and a public status page.
  - `__init__(self, *, state: ServiceState, runner: Runner, activity: ServiceActivity) -> None` — Create the service handlers.
  - `health(_request: Request) -> Response` — Return the unauthenticated service health probe.
  - `get_exactus_status(self) -> dict[str, str | list[str] | None]` — Return protected service and project status.
  - `list_exactus_tools(self) -> dict[str, str | list[str]]` — List the complete catalog and remotely runnable subset.
  - `run_exactus_check(self, tool: RemoteTool, includes: list[str] | None=None) -> dict[str, McpJson]` — Run a safe Exactus report check against the configured root.
  - `read_exactus_report(self, tool: RemoteTool, report_format: ReportFormat='markdown') -> str` — Read the newest generated report for one safe tool.
  - `agents_policy(self) -> str` — Return the complete repository AGENTS policy.
  - `extended_policy(self) -> str` — Return the complete extended repository policy.
  - `landing(self, _request: Request) -> Response` — Serve the public Exactus MCP connection page.
  - `public_status(self, _request: Request) -> Response` — Return public connection metadata without the bearer token.
  - `public_activity(self, _request: Request) -> Response` — Return redacted MCP activity for the public local dashboard.
  - `asset(self, request: Request) -> Response` — Serve one allowlisted stylesheet or script.
- `create_server(*, service: ExactusMcpService) -> MCPServer[None]` — Create the configured MCP server.
- `create_application(*, service: ExactusMcpService, state: ServiceState) -> ASGIApp` — Create the bearer-protected Streamable HTTP application.

### `startup.py`

Manage native startup for the Exactus MCP wake watcher.

- `class Constants` — Group native startup manager constants.
  - `default_label` = `'com.exactus.mcp-wakeup'`
  - `private_mode` = `384`
  - `public_mode` = `420`
- `class WatcherSecrets` — Hold secrets persisted outside native service definitions.
  - `wake_key` = `field(repr=False)`
  - `access_token` = `field(repr=False)`
  - `load(cls, *, path: Path, require_posix_mode: bool) -> WatcherSecrets` — Load credentials from a private JSON file.
  - `serialize(self) -> bytes` — Serialize credentials for a private JSON file.
- `class StartupStatus` — Describe native watcher installation and process state.
  - Fields: `backend: str`, `installed: bool`, `loaded: bool`, `running: bool`, `process_identifier: int | None`
- `class CommandRunner(Protocol)` — Run one local lifecycle command without a shell.
- `default_command_runner(*, arguments: tuple[str, ...]) -> CompletedProcess[str]` — Run one native lifecycle command without raising automatically.
- `class StartupWatcherManager` — Install and inspect the watcher through the native user service API.
  - `platform_name` = `platform`
  - `user_identifier` = `0`
  - `command_runner` = `field(default=default_command_runner, repr=False)`
  - Fields: `label: str`, `definition_path: Path`, `secrets_path: Path`, `stdout_path: Path`, `stderr_path: Path`
  - `backend(self) -> str` — Return the selected native startup backend.
  - `install(self, *, program_arguments: tuple[str, ...], secrets: WatcherSecrets) -> StartupStatus` — Persist and start the watcher through the native backend.
  - `uninstall(self) -> StartupStatus` — Stop the watcher and remove its definition and secrets.
  - `status(self) -> StartupStatus` — Return current installation and native process state.
- `default_startup_manager(*, label: str, home: Path, platform_name: str=platform) -> StartupWatcherManager` — Build the native startup manager and platform-specific paths.

### `state.py`

Mutable per-process state for the Exactus MCP service.

- `class ServiceState` — Describe one running Exactus MCP service.
  - Fields: `root: Path`, `host: str`, `port: int`, `access_token: str`, `transport_security: TransportSecuritySettings`
  - `local_url(self) -> str` — Return the local HTTP origin.
  - `public_url(self) -> str | None` — Return the active public HTTPS origin when exposed.
  - `mcp_url(self) -> str` — Return the preferred MCP endpoint URL.
  - `expose(self, *, public_url: str) -> None` — Record the public origin and admit it to transport checks.

### `supervisor.py`

Run the Exactus MCP asyncio service behind synchronous controls.

- `class ServiceRunner(Protocol)` — Describe the asynchronous Exactus MCP service entry point.
- `class ServiceSupervisor` — Provide non-blocking Start, Stop, and Restart service controls.
  - `__init__(self, *, config: RuntimeConfig, activity: ServiceActivity, service_runner: ServiceRunner) -> None` — Create a stopped supervisor.
  - `root(self) -> Path` — Return the configured project root.
  - `public_tunnel_enabled(self) -> bool` — Return whether service generations should create a public tunnel.
  - `is_running(self) -> bool` — Return whether a service generation is still alive.
  - `start(self) -> bool` — Start the service unless one generation is already alive.
  - `stop(self) -> bool` — Request graceful service shutdown without blocking the caller.
  - `restart(self) -> bool` — Request a serialized stop followed by a fresh start.
  - `shutdown(self, *, timeout: float) -> bool` — Stop the service and wait for bounded graceful cleanup.

### `wakeup.py`

Wake an Exactus MCP service through signed MantleDB commands.

- `class Constants` — Group signed wake protocol constants.
  - `command_domain` = `'exactus-mcp-wake'`
  - `response_domain` = `'exactus-mcp-ready'`
  - `url_pattern` = `'(?<=MCP endpoint: )https://[^\\s<>\'\\"]+'`
  - `process_stop_timeout` = `5.0`
  - `uuid_version` = `4`
- `class WakeError` — Report a wake protocol, transport, or launch failure.
- `class WakeCommand` — Represent one authenticated, short-lived wake request.
  - Fields: `identifier: UUID`, `issued_at: int`
  - `text(self) -> str` — Return the canonical request UUID.
  - `signature(self, *, key: str) -> str` — Sign this command with the configured wake key.
- `class WakeResponse` — Represent one authenticated ready response.
  - Fields: `identifier: UUID`, `url: str`
  - `identifier_text(self) -> str` — Return the canonical request UUID.
  - `signature(self, *, key: str) -> str` — Sign this response with the configured wake key.
- `class WakeStore(Protocol)` — Contract required by the wake watcher persistence boundary.
  - `retrieve_command(self) -> WakeCommand` — Retrieve one authenticated wake command.
  - `publish_response(self, *, response: WakeResponse) -> None` — Publish one authenticated ready response.
- `class ServiceLauncher(Protocol)` — Contract required by the wake watcher process boundary.
  - `start_and_resolve(self) -> str` — Start when needed and return the active public MCP URL.
- `class MantleWakeStore` — Read signed wake commands and publish matching ready responses.
  - `signing_key` = `field(repr=False, compare=False)`
  - `command_path` = `'wake/command'`
  - `response_path` = `'wake/response'`
  - `timeout` = `10.0`
  - `maximum_age` = `120.0`
  - `opener` = `field(default=default_url_opener, repr=False, compare=False)`
  - Fields: `namespace: str`
  - `retrieve_command(self, *, current_time: float | None=None) -> WakeCommand` — Retrieve and authenticate the current wake command.
  - `publish_response(self, *, response: WakeResponse) -> None` — Publish a signed URL bound to the triggering UUID.
- `class WakeStateStore` — Persist the last completed wake UUID atomically.
  - Fields: `path: Path`
  - `read(self) -> UUID | None` — Return the last completed UUID when the state is valid.
  - `write(self, *, identifier: UUID) -> None` — Atomically persist one completed UUID.
- `class WakeServiceLauncher` — Own a fixed service command and discover its public HTTPS URL.
  - `mcp_path` = `'/mcp'`
  - `url_pattern` = `Constants.url_pattern`
  - `environment` = `field(default=None, repr=False)`
  - Fields: `command: tuple[str, ...]`, `discovery_timeout: float`
  - `running(self) -> bool` — Return whether the owned service process is alive.
  - `start_and_resolve(self) -> str` — Start the service when needed and return its current MCP URL.
  - `close(self) -> None` — Stop the owned service process, if any.
- `class WakeWatcher` — Poll signed commands and publish the matching ready service URL.
  - `poll_interval` = `3.0`
  - `retry_maximum` = `30.0`
  - `keep_service_running` = `False`
  - Fields: `store: WakeStore`, `state: WakeStateStore`, `launcher: ServiceLauncher`
  - `poll_once(self) -> bool` — Process one fresh signed UUID and publish its ready response.
  - `run(self) -> None` — Poll forever with bounded retry backoff.

### `wakeup_cli.py`

Run and manage the signed Exactus MCP wake watcher.

- `class Constants` — Group wake watcher command-line defaults.
  - `default_poll_interval` = `3.0`
  - `default_timeout` = `10.0`
  - `default_discovery_timeout` = `45.0`
  - `default_retry_maximum` = `30.0`
  - `default_maximum_age` = `120.0`
  - `actions` = `frozenset(('install', 'run', 'status', 'uninstall'))`
- `class SubparserArguments` — Describe supported lifecycle subparser construction options.
  - Fields: `help: str`
- `class SubparserCollection(Protocol)` — Expose the parser factory used by argparse subcommands.
  - `add_parser(self, name: str, **arguments: Unpack[SubparserArguments]) -> ArgumentParser` — Create and return one action parser.
- `class WakeRuntimeConfig` — Validated wake watcher configuration.
  - Fields: `namespace: str`, `signing_key: str`, `access_token: str`, `command_path: str`, `response_path: str`, `url_path: str`, `state_path: Path`, `poll_interval: float`, `request_timeout: float`, `discovery_timeout: float`, `retry_maximum: float`, `maximum_age: float`, `mcp_path: str`, `url_pattern: str`, `service_command: tuple[str, ...]`, `keep_service_running: bool`
- `run_watcher(*, config: WakeRuntimeConfig) -> int` — Build and run the configured wake watcher.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Run or manage the native signed wake watcher.

## Examples

Runnable demonstration for `exactus/packages/exactus_mcp/`.

Run a self-contained authenticated Exactus MCP round trip.

```bash
python -m exactus.packages.exactus_mcp.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/client.py`, `examples/config.json.example`, `examples/run.py`, `examples/wakeup.md`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md), [`server`](../server/DOCS.md), [`common`](../../tools/common/DOCS.md)
- Used by: `tests/packages/exactus_mcp/test_activity.py`, `tests/packages/exactus_mcp/test_cli.py`, `tests/packages/exactus_mcp/test_cloudflare.py`, `tests/packages/exactus_mcp/test_environment.py`, `tests/packages/exactus_mcp/test_examples.py`, `tests/packages/exactus_mcp/test_macos_menu.py`, `tests/packages/exactus_mcp/test_mantledb.py`, `tests/packages/exactus_mcp/test_ngrok.py`, `tests/packages/exactus_mcp/test_project_config.py`, `tests/packages/exactus_mcp/test_runner.py`, `tests/packages/exactus_mcp/test_service.py`, `tests/packages/exactus_mcp/test_startup.py`, `tests/packages/exactus_mcp/test_state.py`, `tests/packages/exactus_mcp/test_supervisor.py`, `tests/packages/exactus_mcp/test_wakeup.py`, `tests/packages/exactus_mcp/test_wakeup_cli.py`

## Tests

Tests live in `exactus/tests/packages/exactus_mcp/`.

- `test_activity.py` — Validate Exactus MCP lifecycle and caller activity tracking. (2 tests)
  - `test_activity_preserves_last_failure_until_a_new_start`
  - `test_activity_tracks_lifecycle_urls_and_calls`
- `test_cli.py` — Validate Exactus MCP command-line configuration. (17 tests)
  - `test_config_rejects_invalid_port`
  - `test_config_rejects_invalid_timeouts_and_mantledb`
  - `test_config_rejects_missing_root`
  - `test_config_rejects_two_ngrok_modes`
  - `test_config_resolves_root_and_preserves_security_values`
  - `test_configuration_root_reads_both_option_forms`
  - `test_macos_menu_bar_guard_and_dispatch`
  - `test_main_lists_json_configuration_with_secrets_redacted`
  - `test_main_reports_errors_and_interrupts`
  - `test_main_runs_service_via_run_async`
  - `test_run_service_marks_failed_startup`
  - `test_run_service_serves_until_stop_requested`
  - `test_start_tunnel_disabled_returns_none`
  - `test_start_tunnel_publishes_url_and_mantledb_record`
  - `test_wait_for_runtime_surfaces_tunnel_exit`
  - `test_wait_for_stop_returns_once_event_set`
  - `test_wait_started_reports_early_exit_and_timeout`
- `test_cloudflare.py` — Tests for Exactus Cloudflare publication. (32 tests)
  - `test_bootstrapper_deploy_fallback_and_failures`
  - `test_bootstrapper_ensure_skips_provisioned_resources`
  - `test_bootstrapper_installs_missing_prerequisite`
  - `test_bootstrapper_login_reuses_existing_auth`
  - `test_bootstrapper_namespace_creation_failures`
  - `test_bootstrapper_provisions_missing_resources`
  - `test_bootstrapper_reads_namespace_state`
  - `test_bootstrapper_reports_failed_prerequisite_install`
  - `test_bootstrapper_requires_login_success`
  - `test_bootstrapper_requires_prerequisite_tools`
  - `test_bootstrapper_secret_upload_failure`
  - `test_bootstrapper_wrangler_invocation_uses_pinned_cli`
  - `test_bootstrapper_writes_env_without_existing_file`
  - `test_config_from_mapping`
  - `test_config_rejects_empty_control_secret`
  - `test_config_rejects_insecure_worker`
  - `test_config_rejects_invalid_values`
  - `test_configured_port_edge_cases`
  - `test_configured_port_reads_project`
  - `test_main_delegates_to_async_stack`
  - `test_publish_posts_backend_url`
  - `test_quick_tunnel_url_detection`
  - `test_read_tunnel_url_reports_early_exit`
  - `test_read_tunnel_url_requires_output_stream`
  - `test_read_tunnel_url_times_out`
  - `test_require_tool_accepts_present_executable`
  - `test_supervisor_resolves_cloudflared`
  - `test_supervisor_stop_is_idempotent`
  - `test_supervisor_stop_tolerates_vanished_process`
  - `test_wait_for_server_reports_early_exit`
  - `test_wait_for_server_retries_then_succeeds`
  - `test_wait_for_server_times_out`
- `test_environment.py` — Tests for deterministic .env loading. (1 tests)
  - `test_environment_loader_preserves_existing_values`
- `test_examples.py` — Validate runnable Exactus MCP examples. (3 tests)
  - `test_client_prints_inspection_summary`
  - `test_client_requires_access_token`
  - `test_self_contained_example_completes_authenticated_round_trip`
- `test_macos_menu.py` — Exercise native menu lifecycle with an isolated status-library adapter. (4 tests)
  - `test_menu_actions_use_supervisor_and_preferred_connection`
  - `test_menu_quits_after_stop_or_deadline`
  - `test_menu_renders_lifecycle_and_action_availability`
  - `test_native_timer_is_stopped_when_run_loop_exits`
- `test_mantledb.py` — Validate MantleDB URL persistence without network access. (8 tests)
  - `test_default_transport_owns_response_and_connection`
  - `test_default_transport_rejects_untrusted_origins`
  - `test_signature_requires_configured_key`
  - `test_store_rejects_invalid_url_payloads`
  - `test_store_rejects_unsigned_or_tampered_discovery`
  - `test_store_translates_transport_errors`
  - `test_store_updates_unsigned_records_and_rejects_empty_urls`
  - `test_store_writes_and_retrieves_public_url`
- `test_ngrok.py` — Validate ngrok public URL discovery. (7 tests)
  - `test_close_handles_exited_and_unresponsive_children`
  - `test_parse_public_url_accepts_started_https_tunnel`
  - `test_parse_public_url_rejects_incomplete_records`
  - `test_parse_public_url_rejects_unrelated_or_insecure_records`
  - `test_start_failure_reaps_child`
  - `test_start_rejects_missing_executable`
  - `test_start_wait_and_close_own_the_child`
- `test_project_config.py` — Validate Exactus MCP project configuration loading. (18 tests)
  - `test_config_selection_supports_listing_and_json_paths`
  - `test_private_json_supports_service_and_wake_secrets`
  - `test_secret_json_requires_private_posix_permissions`
  - `test_select_config_allows_bare_after_path`
  - `test_select_config_rejects_bare_followed_by_flag`
  - `test_select_config_rejects_empty_inline_value`
  - `test_select_config_rejects_repeated_path`
  - `test_service_and_wake_defaults_are_typed`
  - `test_service_defaults_reject_duplicate_setting`
  - `test_service_defaults_reject_invalid_toml`
  - `test_service_defaults_reject_invalid_value_type`
  - `test_service_defaults_reject_non_table_section`
  - `test_service_json_defaults_reject_invalid_json`
  - `test_service_json_defaults_reject_non_object`
  - `test_service_json_defaults_reject_non_object_section`
  - `test_toml_rejects_secret_settings`
  - `test_unknown_setting_is_rejected`
  - `test_wakeup_cli_lists_json_configuration_with_secrets_redacted`
- `test_runner.py` — Validate the constrained Exactus runner. (7 tests)
  - `test_report_path_rejects_unknown_tool`
  - `test_report_summary_reads_status_and_findings`
  - `test_report_summary_rejects_malformed_fields`
  - `test_run_collects_reports_and_bounds_output`
  - `test_run_rejects_parent_traversal_before_process_start`
  - `test_run_rejects_unsafe_include_limits`
  - `test_run_timeout_reaps_child`
- `test_service.py` — Validate MCP registration and the public HTTP boundary. (7 tests)
  - `test_origin_gateway_normalizes_authenticated_scopes`
  - `test_policy_resources_and_asset_serving`
  - `test_protected_tool_calls_return_results`
  - `test_public_page_and_bearer_boundary`
  - `test_server_registers_protected_exactus_tools`
  - `test_tool_call_updates_visible_activity`
  - `test_tool_error_paths_record_failures`
- `test_startup.py` — Validate native watcher lifecycle definitions without changing the host. (2 tests)
  - `test_linux_definition_quotes_each_argument`
  - `test_native_install_status_and_uninstall`
- `test_state.py` — Validate public URL and transport allowlist state. (2 tests)
  - `test_expose_adds_public_origin_to_transport_security`
  - `test_expose_rejects_non_https_origin`
- `test_supervisor.py` — Validate synchronous controls for the Exactus MCP async service. (2 tests)
  - `test_supervisor_serializes_restart_generations`
  - `test_supervisor_starts_and_stops_without_blocking`
- `test_wakeup.py` — Validate signed Exactus MCP wake-up behavior. (14 tests)
  - `test_discovered_origin_gets_mcp_path`
  - `test_keep_running_starts_service_before_duplicate_check`
  - `test_launcher_close_kills_unresponsive_process`
  - `test_launcher_discovers_url_and_reuses_process`
  - `test_launcher_rejects_invalid_startup_settings`
  - `test_launcher_reports_discovery_failures`
  - `test_retrieve_command_rejects_malformed_documents`
  - `test_signed_command_is_verified_and_ready_response_is_bound`
  - `test_stale_command_is_rejected`
  - `test_state_store_roundtrip_and_invalid_content`
  - `test_transport_failures_surface_as_wake_errors`
  - `test_wake_response_requires_absolute_https`
  - `test_watcher_deduplicates_completed_uuid`
  - `test_watcher_run_retries_with_backoff`
- `test_wakeup_cli.py` — Validate the wake watcher command-line lifecycle actions. (10 tests)
  - `test_main_handles_keyboard_interrupt`
  - `test_main_install_persists_secret_free_arguments`
  - `test_main_lists_effective_config`
  - `test_main_loads_json_config_defaults`
  - `test_main_reports_validation_failures`
  - `test_main_run_loads_secrets_file`
  - `test_main_run_validates_and_starts_watcher`
  - `test_main_status_reports_state`
  - `test_main_status_stopped_returns_nonzero`
  - `test_main_uninstall_removes_service`

<!-- exactus:reference:end -->
