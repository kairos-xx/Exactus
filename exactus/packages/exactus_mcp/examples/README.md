# Exactus MCP examples

This directory contains two executable MCP examples. Both use the official
MCP Python client and send the required bearer header.

[`config.json.example`](config.json.example) is a complete shared service and
wake-watcher configuration template. Copy it outside the repository before
adding real values; on POSIX systems, secret-bearing JSON must be mode `0600`.

## Self-contained round trip

Run the package example from the repository root:

```shell
python -m exactus.packages.exactus_mcp.examples
```

The example starts the real Exactus MCP ASGI application on an ephemeral
loopback port, generates a process-local bearer token, initializes an MCP
session, lists its tools and resources, calls `get_exactus_status`, and shuts
the server down. It does not start ngrok or run an Exactus report, so it is
safe for package smoke tests and leaves no service behind.

## Inspect a running service

Start `exactus-mcp` in one terminal and copy the printed MCP endpoint and
token. In another terminal, keep the token out of shell history by exporting
it through the environment and run the reusable client module:

```shell
EXACTUS_MCP_ACCESS_TOKEN='token-printed-by-exactus-mcp' \
  python -m exactus.packages.exactus_mcp.examples.client \
  'https://example.ngrok-free.app/mcp'
```

The client initializes the Streamable HTTP session, prints every advertised
tool and resource, and prints the structured protected status result. It does
not invoke a report tool. A missing or incorrect token fails explicitly.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Runnable authenticated client examples for Exactus MCP.
- [`__main__.py`](__main__.py) — Run the Exactus MCP example through the project virtual environment.
- [`client.py`](client.py) — Inspect an authenticated Exactus MCP Streamable HTTP endpoint.
- [`config.json.example`](config.json.example) — Provide config.json example content.
- [`run.py`](run.py) — Run a self-contained authenticated Exactus MCP round trip.
- [`wakeup.md`](wakeup.md) — This example keeps the Exactus MCP service offline until the installed plugin needs it. Use three unrelated high-entropy values: a private MantleDB namespace, an MCP bearer token, and a wake-only HMAC key.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
