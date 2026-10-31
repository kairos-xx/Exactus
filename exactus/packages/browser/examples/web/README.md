# Web example

Serve this directory with any static HTTP server and open `index.html`.

The page can open a new tab, append/clear local event-log entries, and request
closure of its current tab. Its JavaScript is deliberately independent from
the Python implementation so it can be unit-tested using Node's built-in test
runner.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`code.js`](code.js) — Maintains and renders a textual event log.
- [`index.html`](index.html) — Provide index html content.
- [`style.css`](style.css) — Provide style css content.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
