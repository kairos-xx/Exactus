# Wake-up example

This example keeps the Exactus MCP service offline until the installed plugin
needs it. Use three unrelated high-entropy values: a private MantleDB namespace,
an MCP bearer token, and a wake-only HMAC key.

On the macOS or Linux host that owns the Exactus checkout:

```shell
export EXACTUS_MCP_MANTLEDB_NAMESPACE="replace-private-namespace"
export EXACTUS_MCP_ACCESS_TOKEN="replace-mcp-bearer-token"
export EXACTUS_MCP_WAKE_KEY="replace-wake-only-key"

python -m exactus.packages.exactus_mcp.wakeup_cli run \
  --state "$PWD/.exactus-mcp-wakeup/last-id" \
  -- \
  python -m exactus.packages.exactus_mcp \
  --root "$PWD" \
  --port 6100
```

On Windows PowerShell, use the same values with native environment and path
syntax:

```powershell
$env:EXACTUS_MCP_MANTLEDB_NAMESPACE = "replace-private-namespace"
$env:EXACTUS_MCP_ACCESS_TOKEN = "replace-mcp-bearer-token"
$env:EXACTUS_MCP_WAKE_KEY = "replace-wake-only-key"

python -m exactus.packages.exactus_mcp.wakeup_cli run `
  --state "$PWD\.exactus-mcp-wakeup\last-id" `
  -- `
  python -m exactus.packages.exactus_mcp `
  --root "$PWD" `
  --port 6100
```

To install the watcher for automatic user startup and keep the MCP endpoint
available to ChatGPT web on macOS, Linux, or Windows, use a reserved ngrok
endpoint and enable supervision:

```shell
exactus-mcp-wakeup install \
  --mantledb-namespace "replace-private-namespace" \
  --keep-service-running \
  -- \
  exactus-mcp --root /absolute/project/path --port 6100 \
  --ngrok-endpoint your_endpoint_name

exactus-mcp-wakeup status
exactus-mcp-wakeup uninstall
```

Native backends are LaunchAgent, `systemd --user`, and Task Scheduler,
respectively. `install` starts the watcher immediately and persists only a
secret-free command definition; the wake key and bearer token live in a
separate private user configuration file.

Deploy the Worker in `../bridge/` after replacing its two MantleDB endpoint
variables, and set `WAKE_HMAC_KEY` through the provider's secret store. On the
plugin host, provide the same namespace, bearer token, wake key, and the
Worker's stable HTTPS URL as `EXACTUS_MCP_WAKE_URL`.

The plugin first tries the currently signed URL. Only a recoverable offline or
expired-tunnel error triggers wake-up. After the Worker reports ready, the
plugin verifies the matching wake response and independently verifies the
normal bearer-signed URL record before it sends the bearer token.

For a read-only check of the current record:

```shell
python3 scripts/mantledb_mcp_bridge.py --print-url
```

To explicitly exercise wake-up and print the verified replacement URL:

```shell
python3 scripts/mantledb_mcp_bridge.py --wake
```
