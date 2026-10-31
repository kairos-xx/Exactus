# Flow Studio

Studio owns the browser editor, authenticated local HTTP service, recovery,
command transport, and the separate Playwright target worker.

Launch with `python -m exactus.tools.record.studio --project /path/to/project`.
Studio delegates fixed-port replacement to `exactus.packages.server.ports`.
With a fixed port, such as `--port 8877`, a new launch automatically stops
an existing Studio package launcher on that port before binding. It first
requests graceful shutdown, then stops the verified process tree if needed.
Unrelated or unidentifiable listeners are never killed. Verification uses
`lsof` and `ps` on macOS/Linux; if unavailable, a busy port fails safely.
The default `--port 0` continues selecting an available port automatically.
The test browser is headless by default, so the Browser panel is the only view
of the page; pass `--headed` to also show its window while debugging (`--headless`
is still accepted).
`target_service.py` starts the configured service through `exactus.packages.http_process`,
detects the port it opened (or waits for the one you set) and stops its whole
process tree on shutdown. A project file can hold a command, so Studio never runs
it on open: only an explicit `target.start` does.
Recording, crawling, flow models, and functional replay belong to the parent
`exactus.tools.record` package. Screenshot acquisition and similarity comparison belong
to `exactus.packages.screenshot`.

## Files

- `__init__.py` — File.
- `bridge.py` — File.
- `browser.py` — File.
- `controller.py` — File.
- `events.py` — File.
- `__main__.py` — Package entry point.
- `persistence.py` — File.
- `recorder_server.py` — File.
- `service.py` — File.
- `window.py` — File.
- `worker.py` — File.

## Subdirectories

- `web/` — Subdirectory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Host the browser Flow Studio UI and its local service.
- [`__main__.py`](__main__.py) — Run browser Studio as a package with its automation worker.
- [`action_commands.py`](action_commands.py) — Reconfigure an authored action from the Properties panel.
- [`controller.py`](controller.py) — HTML-first Exactus Record host window.
- [`demo.py`](demo.py) — Create an editable demonstration using the ordinary Studio flow runtime.
- [`events.py`](events.py) — Publish bounded, ordered service events with snapshot recovery.
- [`persistence.py`](persistence.py) — Restrict workspace and artifact access to the selected project root.
- [`project_commands.py`](project_commands.py) — Editor commands for projects, apart from the large controller.
- [`projects.py`](projects.py) — Keep a library of projects, one folder each, under the Studio root.
- [`selector_commands.py`](selector_commands.py) — Editor commands for selectors, apart from the large controller.
- [`service.py`](service.py) — Serve the local editor, authenticated commands, events and artifacts.
- [`target_inspection.py`](target_inspection.py) — Read target element identity without dispatching an interaction.
- [`target_service.py`](target_service.py) — Start, detect and stop the service a project's target refers to.
- [`window.py`](window.py) — Resolve the Studio browser-window setting from CLI and pyproject.
- [`worker.py`](worker.py) — Keep synchronous Playwright objects on one service-owned worker thread.

### Subdirectories

- [`web/`](web/README.md) — The framework-free editor uses `index.html`, `editor.css`, `editor.js`, `transport.js` and the dock modules. `editor.css` imports `styles/style.css`, which loads the token hierarchy and each component in cascade order. HTTP commands and Server-Sent Events connect it to the service. Tabler outline icons and shared CSS tokens keep the dark editor consistent. The application under test runs in a separate owned Chromium that Studio drives with Playwright. It has no window of its own (headless is the default, `--headed` opts out): the Browser panel streams its pixels and sends clicks and keys back, so it behaves like an embedded frame without an iframe's limits (framing restrictions, no emulation, a different engine).

<!-- exactus:inventory:end -->



## Authorization handshake

Studio answers only tabs it authorized. `/studio/` is public and issues an
HttpOnly, SameSite=Strict cookie; the page then reads the launch token from
its URL fragment and posts it to `/api/session`. Every other `/api/*` route
requires that cookie, so pasting a data URL (for example `/api/snapshot`) into
a raw tab returns 401. A browser navigation receives a short page with a link
back to `/studio/`; other clients receive the JSON error envelope with code
`UNAUTHORIZED`. The check is never relaxed for direct localhost navigation.

## Projects

Each project is a folder under `<root>/projects/<slug>/` with its own project
file, selectors and evidence. A `flows.pwflow.json` directly in the root is the
`@root` project, so layouts from before the library keep working. The library,
the open project and its details travel in every snapshot as `library` and
`project`; the commands are `project.create`, `project.open`, `project.update`,
`project.duplicate`, `project.delete` and `project.import`. Opening or creating
a project needs `replace: true` when the open one has unsaved edits. Names are
unique across the library, ignoring case. Recently opened projects are kept in
`<root>/.exactus-library/recents.json`, and `GET /api/export?project=<slug>`
downloads any project. `exactus/packages/` files are served to the page under `/packages/`,
browser file types only.
