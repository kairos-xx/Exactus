# `examples/`

`run.py` demonstrates the loopback-server lifecycle end to end: it
serves the bundled `web/` directory through `exactus.packages.server.local.serve`,
waits for readiness, verifies the `/_exactus_check_ping` identity token,
fetches `index.html`, and shows `reuse_server` adopting the surviving
process rather than spawning a second one. The server is terminated and
its state file cleared when the demo exits.

```bash
python exactus/packages/server/examples
```

Artifacts — `server.log` and the `XDG_CACHE_HOME` reuse state — are
written under the git-ignored `.scratch/` folder, so re-runs leave the
checkout clean. Tests override the scratch directory with a temporary
path.

## Directory contents

- `__init__.py` — File.
- `__main__.py` — File.
- `run.py` — File.
- `web/` — Subdirectory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Runnable examples for ``exactus/server``.
- [`__main__.py`](__main__.py) — Run the server example with the project virtual environment.
- [`run.py`](run.py) — Runnable demonstration of the ``exactus.packages.server`` reuse contract.

### Subdirectories

- [`web/`](web/README.md) — Static content served by `../run.py` — the loopback demo site.

<!-- exactus:inventory:end -->


