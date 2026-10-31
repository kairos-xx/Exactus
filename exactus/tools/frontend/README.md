# Frontend exactus

Execute a normal Studio project or an Actions recipe and organize its functional
results, JavaScript responses, assertions and browser/server diagnostics.
Screenshots are captured only when requested by the flow.

Independent workflow entry points run concurrently with four workers by default.
Connected flows and their actions remain sequential in an isolated browser.
Use `--workers 1` for flows that modify shared server data, or choose another
worker count with `--workers N`. Actions recipes can set `workers` in the
`frontend.run` arguments.

```sh
python -m exactus.tools.frontend.main --workspace project.pwflow.json
python -m exactus.tools.frontend.main --actions demo/actions/frontend.json
```

`core.py` provides `FrontendExactusInput`, `frontend`, `report_data` and
`markdown_report`. `main.py` provides the CLI. See [Actions](../../docs/ACTIONS.md)
for entrypoint ownership, responsive discovery and generated-project replay.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Frontend exactus tool.
- [`arguments.py`](arguments.py) — Declare the frontend grammar without importing its execution engine.
- [`core.py`](core.py) — Exactus saved Studio workflows with the shared functional test executor.
- [`main.py`](main.py) — Execute Studio workflows and report functional frontend evidence.
- [`progress.py`](progress.py) — Publish real frontend work into the shared tool heartbeat.
- [`report.py`](report.py) — Normalize frontend execution evidence for Markdown and web reports.

### Subdirectories

- [`templates/`](templates/README.md) — Provide mapping json content.

<!-- exactus:inventory:end -->


