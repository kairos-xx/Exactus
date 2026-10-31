# tests/

The Exactus test suite: Python (pytest) and JavaScript (Node test
runner, shared Playwright harness) coverage mirroring `exactus/packages/`
and `exactus/tools/`.

## Files

| File | Description |
|---|---|
| `conftest.py` | Shared pytest fixtures and interpreter/path setup for the whole suite. |

## Groups

| Directory | What it verifies |
|---|---|
| `bundle/` | The small runtime layer that locates and exposes the generated platform bundle — repository-root discovery, deterministic source-tree signatures, stale-bundle warnings, host/architecture candidate selection on Linux (glibc and musl), macOS and Windows, and bundle entry-point dispatch. |
| `common/` | Contracts shared across packages, tools, command-line entry points and the test infrastructure itself: typed assertion helpers, check-command parsing/reporting, example-package contracts, JSON serialization, and package-independence rules. |
| `demo/` | The demonstrator application as a real HTTP server and as browser-side JavaScript: state transitions, static assets, error conversion, CLI lifetime and rendered DOM behavior. |
| `packages/` | One directory per `exactus/packages/` package — public API, CLI and examples as applicable, plus failure and lifecycle behavior. `test_packages.py` checks the package collection itself. |
| `standalone/` | Hermetic end-to-end audit: a resolved `exactus` executable (installed or rebuilt from `bin/release` when stale) runs over the self-contained `project/` fixture and asserts the `EXACTUS_RESULTS` reports are produced. |
| `tools/` | One directory per `exactus/tools/` tool — normalized report envelopes, findings, templates, CLI wiring and fix-mode behavior. |

## Behavior

- Python suites use temporary directories and injected platform/process
  boundaries so runs stay reproducible and never depend on the
  machine's installed bundle or developer state.
- JavaScript suites use Node's test runner and, where a real DOM is
  required, the shared Playwright harness (`common/browser.mjs`), which
  starts fixtures, opens pages and supplies deterministic cleanup.
- The coverage command also discovers package-owned `.test.mjs` files
  and combines their V8 coverage with Python coverage.
- Run everything with `python -m pytest exactus/tests`, or a single
  group with `python -m pytest exactus/tests/<group>`; browser suites
  run via `node --test`.
