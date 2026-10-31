# http-process

A Python 3.13 package for starting processes, discovering TCP listeners owned by
their process trees, verifying HTTP endpoints, and resolving local listener
ownership.

## Import

```python
from http_process import HttpProcess

inspector = HttpProcess()
result = inspector.inspect(host="127.0.0.1", port=8000)
```

## CLI

Inspect an existing endpoint:

```bash
python -m http_process --host 127.0.0.1 --port 8000
```

Run a command and wait for an HTTP listener:

```bash
python -m http_process python -m http.server 0 --bind 127.0.0.1
```

## Examples

```bash
python -m http_process.examples.inspect_existing
python -m http_process.examples.run_server
```

Process metadata can only be resolved for listeners owned by the local operating
system and visible to the current user. Remote HTTP endpoints can be probed, but
their remote process metadata cannot be inferred from TCP/HTTP alone.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Public API for HTTP process discovery and inspection.
- [`__main__.py`](__main__.py) — Command-line interface for HTTP process inspection.
- [`cli.py`](cli.py) — Command-line interface for HTTP process inspection.
- [`process.py`](process.py) — Run processes and inspect HTTP servers and their owning processes.
- [`pyproject.toml`](pyproject.toml) — Provide pyproject toml content.

### Subdirectories

- [`examples/`](examples/README.md) — Examples for the http_process package.

<!-- exactus:inventory:end -->
