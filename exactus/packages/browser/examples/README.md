# Examples

Run the bundled browser demo with Playwright Chromium:

```bash
python -m browser.examples
```

With no URL, the example serves `web/` through the shared loopback server used
by `screenshot`. An existing server for that directory is reused; otherwise the
example starts one, waits until it is ready, and terminates it on exit.

The example starts Playwright on its non-blocking worker, waits five seconds by default, and then explicitly closes and joins that worker. Override
the lifetime with `--duration SECONDS`; use `--duration 0` to wait until the
browser is closed manually.

Open an explicit URL instead of starting the bundled server:

```bash
python -m browser.examples https://example.com
```

Run native Chrome on macOS:

```bash
python -m browser.examples \
  --backend chrome \
  --chrome "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

Every observed lifecycle event is written to stdout with timestamp, backend,
event type, PID, URL, title, and exit status where available.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Runnable examples for the browser lifecycle package.
- [`__main__.py`](__main__.py) — Run the browser example with the project virtual environment.
- [`run.py`](run.py) — Interactive browser lifecycle demonstration.

### Subdirectories

- [`web/`](web/README.md) — Serve this directory with any static HTTP server and open `index.html`.

<!-- exactus:inventory:end -->
