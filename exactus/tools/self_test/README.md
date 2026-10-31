# `exactus/tools/self_test/`

The `exactus --self_test` self-diagnostic. Generates a seven-file
fixture project in a temporary directory, probes every expected tool —
the system-installed executable on `PATH` first, the pyz's bundled
toolchain as fallback — then runs the `unified` pipeline against the
fixture and verifies every `EXACTUS_RESULTS` report is fresh, PASS,
and issue-free. Writes the standard `EXACTUS_RESULTS/SELF_TEST`
report bundle and leaves nothing outside the temp tree.

## Files

- `main.py` — the complete self-test: fixture constants, tool/binary
  probes (system-first, bundle-fallback), loopback demo site, Xvfb
  display, pipeline run, report verification, and the standard report
  bundle output.
- `arguments.py` — the CLI grammar shared by execution and completion.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Self-test exactus tool.
- [`arguments.py`](arguments.py) — Declare the self_test grammar without importing its engine.
- [`main.py`](main.py) — Probe every tool reachable by this exactus and report the results.
- [`py.typed`](py.typed) — Provide py typed content.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
