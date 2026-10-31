# Exactus MCP tests

These tests cover the public HTTP surface, MCP tool registration, bearer
boundary, fixed-root runner validation, ngrok log parsing, and URL allowlist
updates.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests for the Exactus MCP and ngrok service.
- [`test_activity.py`](test_activity.py) — Validate Exactus MCP lifecycle and caller activity tracking.
- [`test_cli.py`](test_cli.py) — Validate Exactus MCP command-line configuration.
- [`test_cloudflare.py`](test_cloudflare.py) — Tests for Exactus Cloudflare publication.
- [`test_environment.py`](test_environment.py) — Tests for deterministic .env loading.
- [`test_examples.py`](test_examples.py) — Validate runnable Exactus MCP examples.
- [`test_macos_menu.py`](test_macos_menu.py) — Exercise native menu lifecycle with an isolated status-library adapter.
- [`test_mantledb.py`](test_mantledb.py) — Validate MantleDB URL persistence without network access.
- [`test_ngrok.py`](test_ngrok.py) — Validate ngrok public URL discovery.
- [`test_project_config.py`](test_project_config.py) — Validate Exactus MCP project configuration loading.
- [`test_runner.py`](test_runner.py) — Validate the constrained Exactus runner.
- [`test_service.py`](test_service.py) — Validate MCP registration and the public HTTP boundary.
- [`test_startup.py`](test_startup.py) — Validate native watcher lifecycle definitions without changing the host.
- [`test_state.py`](test_state.py) — Validate public URL and transport allowlist state.
- [`test_supervisor.py`](test_supervisor.py) — Validate synchronous controls for the Exactus MCP async service.
- [`test_wakeup.py`](test_wakeup.py) — Validate signed Exactus MCP wake-up behavior.
- [`test_wakeup_cli.py`](test_wakeup_cli.py) — Validate the wake watcher command-line lifecycle actions.

### Subdirectories

- [`bridge/`](bridge/README.md) — Origin used by every request in this suite.
- [`web/`](web/README.md) — Provide app broken html content.

<!-- exactus:inventory:end -->

## Cloudflare publication coverage

`test_cloudflare.py` exercises automatic Cloudflare bootstrap and publication,
including resource discovery, namespace reuse/creation, secret generation and
installation, Worker deployment, Quick Tunnel URL handling, and failure
paths. `test_environment.py` covers local environment discovery/loading and
secret-safe persistence behavior. Worker-side OAuth and routing behavior is
also exercised by the JavaScript tests stored with the bridge implementation.
